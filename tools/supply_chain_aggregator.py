#!/usr/bin/env python3
"""Supply-chain Aggregator: fetch, hand the inputs to the pure core, apply the plan, save the run.

Usage:
    python3 tools/supply_chain_aggregator.py run
    python3 tools/supply_chain_aggregator.py notify-failure --run-id ID --message TEXT [--message TEXT ...]

This module decides nothing. Thresholds, de-duplication, when an Issue closes, the per-run limit,
the 12-hour staleness limit, the failure streak and the retry waits are all in tools/supply_chain/
(a byte-for-byte copy, see docs/agent/supply-chain-source.json). What is here is the order of the
steps and the translation between GitHub, the feeds and the core's plain values.

``run`` reads its settings from the environment (set by .github/workflows/supply-chain-aggregator.yml):

    SPOKE_TOKEN        token for reading the target repositories and for Issue writes
    HUB_TOKEN          token that can write contents of this repository, for the runs branch only
    GITHUB_REPOSITORY  this repository, <owner>/<name>
    GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT, GITHUB_SHA
    POLICY_FILE        path of the checked-out Policy_File
    SUPPLY_CHAIN_POLICY_REF   the 40-hex commit the Policy_File was checked out at
                       (repository variable; the workflow must not hard-code a SHA)

POLICY_FILE is the path inside the directory where the workflow checked out the policy
repository at SUPPLY_CHAIN_POLICY_REF. SPOKE_TOKEN is a GitHub App installation token with
contents:read, issues:write, dependabot_alerts:read, actions:read and metadata:read. HUB_TOKEN is a
second installation token limited to this one repository with contents:write only; the job's own
GITHUB_TOKEN never writes the runs branch. Create both with actions/create-github-app-token from
the App ID (variable SUPPLY_CHAIN_APP_ID) and private key (secret SUPPLY_CHAIN_APP_PRIVATE_KEY),
and fail with a clear message when either is unset. The runs branch ``supply-chain-runs`` must
already exist; it is never created here.

``notify-failure`` (used by the watchdog) reads NOTIFY_TOKEN (a SPOKE_TOKEN-style token that can
write Issues in this repository) and GITHUB_REPOSITORY. It appends to the open failure Issue, or
opens one when none is open, and exits non-zero when the notice could not be sent.

Exit codes: 0 the run ended in success, 1 it ended in failure (or could not be saved), 2 bad usage.
The run record is saved even when the run failed, so that the watchdog sees the run and the
failure streak can be counted. A record that cannot be saved makes the run abnormal.
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import io
import json
import os
import re
import sys
import urllib.parse
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from supply_chain import (
    issue_body,
    metrics,
    models,
    normalized,
    planner,
    run_record,
    threshold,
    vex,
)
from supply_chain.models import Component, Finding, ManagedIssue, PullRequestRef, Repo
from supply_chain.policy import PolicyError, parse_policy
from supply_chain_adapters import spdx
from supply_chain_io import (
    Client,
    GitHubApi,
    HttpError,
    Osv,
    RateLimited,
    TransportError,
    UrllibTransport,
    fetch_epss,
    fetch_kev,
    parse_osv_time,
)

LABEL = "supply-chain-aggregator"
LABEL_COLOR = "ededed"
LABEL_DESCRIPTION = "Opened and maintained by the supply-chain Aggregator"
RUNS_BRANCH = "supply-chain-runs"
RECENT_OUTCOMES = max(run_record.FAILURE_STREAK_THRESHOLD, 3)
PR_SEARCH_CAP = 60
MAX_ZIP_MEMBER_BYTES = 200 * 1024 * 1024
HEX40 = re.compile(r"[0-9a-f]{40}")
FINDING_TITLE_PREFIX = "[supply-chain] "
SUMMARY_TITLE = "[supply-chain] 起票数の上限を超えた脆弱性の一覧"
FAILURE_TITLE = "[supply-chain] Aggregator の実行失敗"

# Dependabot ecosystem names to purl types. From the purl type names, not confirmed against a
# live alert for every ecosystem; an unlisted ecosystem falls back to ``generic``.
PURL_TYPES = {
    "actions": "githubactions",
    "composer": "composer",
    "erlang": "hex",
    "go": "golang",
    "maven": "maven",
    "npm": "npm",
    "nuget": "nuget",
    "pip": "pypi",
    "pub": "pub",
    "rubygems": "gem",
    "rust": "cargo",
    "swift": "swift",
}


def utc_now() -> datetime:
    """The current time in UTC with whole seconds (the run record refuses fractions)."""
    return datetime.now(UTC).replace(microsecond=0)


def _time_text(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(raw: object) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _repo_text(repo: Repo) -> str:
    return f"{repo.owner}/{repo.name}"


def _split_repo(text: str) -> Repo:
    owner, _, name = text.partition("/")
    return Repo(owner, name)


# --- Issues --------------------------------------------------------------------------------------


def list_managed_issues(
    api: GitHubApi, repo: Repo
) -> tuple[list[ManagedIssue], list[dict[str, Any]]]:
    """List the Issues the Aggregator owns in ``repo`` (label and marker), all states.

    Returns the managed Issues and the raw API objects (closing times and reasons are read from
    those). An Issue with the label whose marker does not name this repository is not managed.
    """
    managed: list[ManagedIssue] = []
    raw_items: list[dict[str, Any]] = []
    for item in api.pages(
        f"/repos/{_repo_text(repo)}/issues", {"labels": LABEL, "state": "all"}
    ):
        if "pull_request" in item:
            continue
        marker = issue_body.parse_marker(item.get("body"))
        if not issue_body.is_managed(marker, repo) or marker is None:
            continue
        managed.append(
            ManagedIssue(
                repo=repo,
                number=item["number"],
                kind=marker.kind,  # type: ignore[arg-type]
                vuln_id=marker.vuln_id,
                state=item["state"],
                body_state=issue_body.parse_state(item.get("body")),
            )
        )
        raw_items.append(item)
    return managed, raw_items


def ensure_label(api: GitHubApi, repo: Repo, done: set[str]) -> None:
    """Create the identification label once per repository if it does not exist."""
    key = _repo_text(repo).lower()
    if key in done:
        return
    path = f"/repos/{_repo_text(repo)}/labels"
    if api.get(f"{path}/{urllib.parse.quote(LABEL)}").status == 404:
        resp = api.write(
            "POST",
            path,
            {"name": LABEL, "color": LABEL_COLOR, "description": LABEL_DESCRIPTION},
        )
        if resp.status not in (201, 422):  # 422: it was created in between
            raise HttpError("POST", path, resp.status, resp.text()[:200])
    done.add(key)


def apply_action(
    api: GitHubApi, action: models.IssueAction, labels_done: set[str]
) -> int | None:
    """Apply one planned Issue operation. Returns the Issue number. Raises HttpError on a refusal."""
    base = f"/repos/{_repo_text(action.repo)}/issues"
    if action.op == "create":
        ensure_label(api, action.repo, labels_done)
        title = (
            SUMMARY_TITLE
            if action.kind == "summary"
            else f"{FINDING_TITLE_PREFIX}{action.vuln_id}"
        )
        resp = api.write(
            "POST", base, {"title": title, "body": action.body, "labels": [LABEL]}
        )
        if resp.status != 201:
            raise HttpError("POST", base, resp.status, resp.text()[:200])
        created = resp.json()
        names = {
            (label if isinstance(label, str) else label.get("name"))
            for label in created.get("labels", [])
        }
        if LABEL not in names:
            raise HttpError(
                "POST", base, 201, "Issue created without the identification label"
            )
        return int(created["number"])
    if action.number is None:
        raise HttpError("PATCH", base, 0, "action has no Issue number")
    path = f"{base}/{action.number}"
    if action.op == "update":
        payload: dict[str, Any] = {"body": action.body}
    elif action.op == "reopen":
        payload = {"state": "open", "body": action.body}
    else:  # close
        payload = {
            "state": "closed",
            "state_reason": "completed"
            if action.close_reason == "resolved"
            else "not_planned",
        }
    resp = api.write("PATCH", path, payload)
    if not resp.ok:
        raise HttpError("PATCH", path, resp.status, resp.text()[:200])
    if (
        action.op == "close"
    ):  # the reason is recorded as a comment; failing to comment does not undo the close
        api.write(
            "POST",
            f"{path}/comments",
            {"body": f"Closed by the Aggregator: {action.close_reason}"},
        )
    return action.number


# --- layers A and B ------------------------------------------------------------------------------


@dataclass
class RepoFetch:
    """What one repository yielded this run."""

    repo: Repo
    default_branch: str | None = None
    head_sha: str | None = None
    components: dict[str, Component] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    layer_ok: dict[str, bool] = field(default_factory=lambda: {"A": False, "B": False})
    failures: list[run_record.FetchFailure] = field(default_factory=list)

    def fail(self, layer: models.Layer, reason: str) -> None:
        self.failures.append(
            run_record.FetchFailure(_repo_text(self.repo), layer, reason[:300])
        )


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _purl_for_alert(repo: RepoFetch, ecosystem: str, name: str) -> list[Component]:
    purl_type = PURL_TYPES.get(ecosystem.lower(), "generic")
    matches = [
        c
        for c in repo.components.values()
        if c.purl.startswith(f"pkg:{purl_type}/")
        and _normalize_name(c.name) == _normalize_name(name)
    ]
    if matches:
        return sorted(matches, key=lambda c: c.purl)
    return [
        normalized.component_from_purl(
            f"pkg:{purl_type}/{urllib.parse.quote(name, safe='/@:')}"
        )
    ]


def findings_from_alerts(
    repo: RepoFetch, alerts: Iterable[Mapping[str, Any]], now: datetime
) -> list[Finding]:
    """Convert open Dependabot alerts to Findings (layer A). The CVE is the representative id."""
    out: list[Finding] = []
    for alert in alerts:
        advisory, vulnerability = (
            alert["security_advisory"],
            alert["security_vulnerability"],
        )
        cve, ghsa = advisory.get("cve_id"), advisory["ghsa_id"]
        patched = vulnerability.get("first_patched_version") or {}
        package = vulnerability["package"]
        for component in _purl_for_alert(repo, package["ecosystem"], package["name"]):
            out.append(
                Finding(
                    repo=repo.repo,
                    vuln_id=cve or ghsa,
                    aliases=(ghsa,) if cve else (),
                    component=component,
                    cvss_severity=normalized.normalize_severity(
                        advisory.get("severity")
                    ),
                    fixed_version=patched.get("identifier"),
                    advisory_published_at=parse_osv_time(advisory.get("published_at")),
                    layer="A",
                    first_observed_component_at=now,
                )
            )
    return out


def _read_zip(blob: bytes) -> dict[str, bytes]:
    members: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            if info.file_size > MAX_ZIP_MEMBER_BYTES:
                raise ValueError(f"archive member too large: {info.filename}")
            members[info.filename] = archive.read(info)
    return members


def fetch_repo(api: GitHubApi, repo: Repo, now: datetime) -> RepoFetch:
    """Read layers A and B of one repository. A failure of one part is recorded and the rest goes on."""
    result = RepoFetch(repo)
    name = _repo_text(repo)
    try:
        info = api.get_json(f"/repos/{name}")
        result.default_branch = info["default_branch"]
        branch = api.get_json(
            f"/repos/{name}/branches/{urllib.parse.quote(result.default_branch, safe='')}"
        )
        result.head_sha = branch["commit"]["sha"]
    except (HttpError, TransportError, KeyError, ValueError) as exc:
        for layer in ("A", "B"):
            result.fail(layer, f"repository not readable: {exc}")  # type: ignore[arg-type]
        return result

    try:  # layer A: the dependency graph export, which only supplies components
        sbom = api.get_json(f"/repos/{name}/dependency-graph/sbom")["sbom"]
        for component in spdx.parse_spdx(sbom).components:
            result.components.setdefault(component.purl, component)
    except (
        HttpError,
        TransportError,
        KeyError,
        ValueError,
        spdx.SbomFormatError,
    ) as exc:
        result.fail("A", f"sbom export: {exc}")
    try:  # layer A: Dependabot alerts, which supply the findings
        alerts = list(api.pages(f"/repos/{name}/dependabot/alerts", {"state": "open"}))
        result.findings.extend(findings_from_alerts(result, alerts, now))
        result.layer_ok["A"] = True
    except (HttpError, TransportError, KeyError, ValueError) as exc:
        result.fail("A", f"dependabot alerts: {exc}")

    try:  # layer B: the newest sbom-generate artifact built from the default branch
        artifact = next(
            (
                a
                for a in api.pages(f"/repos/{name}/actions/artifacts", key="artifacts")
                if a["name"].startswith("sbom-")
                and not a["expired"]
                and (a.get("workflow_run") or {}).get("head_branch")
                == result.default_branch
            ),
            None,
        )
        if artifact is None:
            raise ValueError("no sbom-* artifact built from the default branch")
        members = _read_zip(api.download(artifact["archive_download_url"]))
        components = spdx.parse_spdx(json.loads(members["sbom.spdx.json"])).components
        for component in components:
            result.components.setdefault(component.purl, component)
        doc = json.loads(members["findings.normalized.json"])
        parsed = normalized.findings_from_normalized(
            doc, components=components, first_observed_at=now
        )
        if parsed.repo != repo:
            raise ValueError(f"artifact is for {_repo_text(parsed.repo)}")
        result.findings.extend(parsed.findings)
        result.layer_ok["B"] = True
    except (
        HttpError,
        TransportError,
        KeyError,
        ValueError,
        zipfile.BadZipFile,
        spdx.SbomFormatError,
        normalized.NormalizedFindingsError,
    ) as exc:
        result.fail("B", f"sbom artifact: {exc}")
    return result


# --- feeds ---------------------------------------------------------------------------------------


@dataclass
class FeedResult:
    snapshot: models.FeedSnapshot
    fetched: list[run_record.FeedFetched]
    failed: list[run_record.FeedFailed]
    kev_fetched_on: date | None
    epss_info: run_record.EpssInfo
    extra_findings: list[Finding]


def _mal_findings(
    fetches: Sequence[RepoFetch],
    ids_by_purl: Mapping[str, list[str]],
    records: Mapping[str, Mapping[str, Any] | None],
    now: datetime,
) -> list[Finding]:
    out: list[Finding] = []
    for fetch in fetches:
        for purl, component in fetch.components.items():
            for vuln_id in ids_by_purl.get(purl, []):
                record = records.get(vuln_id) or {}
                aliases = tuple(
                    a
                    for a in record.get("aliases", [])
                    if isinstance(a, str) and a != vuln_id
                )
                out.append(
                    Finding(
                        repo=fetch.repo,
                        vuln_id=vuln_id,
                        aliases=aliases,
                        component=component,
                        cvss_severity=None,
                        fixed_version=None,
                        advisory_published_at=parse_osv_time(record.get("published")),
                        layer="A" if fetch.layer_ok["A"] else "B",
                        first_observed_component_at=now,
                    )
                )
    return out


def fetch_feeds(
    client: Client,
    osv: Osv,
    fetches: Sequence[RepoFetch],
    findings: Sequence[Finding],
    open_mal_issues: Mapping[str, ManagedIssue],
    now: datetime,
) -> FeedResult:
    """Fetch KEV, EPSS and OSV. A failed feed is recorded and its value is ``None``; nothing is invented."""
    fetched: list[run_record.FeedFetched] = []
    failed: list[run_record.FeedFailed] = []
    kev: dict[str, tuple[date, bool | None]] | None = None
    kev_on: date | None = None
    try:
        kev, catalog = fetch_kev(client)
        kev_on = now.date()
        fetched.append(run_record.FeedFetched("kev", now, catalog))
    except (HttpError, RateLimited, TransportError, KeyError, ValueError) as exc:
        failed.append(run_record.FeedFailed("kev", now, str(exc)[:300]))

    cve_ids = sorted(
        {i for f in findings for i in (f.vuln_id, *f.aliases) if i.startswith("CVE-")}
    )
    epss: dict[str, tuple[str, date, str]] | None = None
    epss_info = run_record.EpssInfo(None, None)
    try:
        epss = fetch_epss(client, cve_ids)
        sample = next(iter(epss.values()), None)
        epss_info = run_record.EpssInfo(
            sample[1] if sample else None, sample[2] if sample else None
        )
        fetched.append(run_record.FeedFetched("epss", now, epss_info.model_version))
    except (HttpError, RateLimited, TransportError, ValueError, OSError) as exc:
        failed.append(run_record.FeedFailed("epss", now, str(exc)[:300]))

    malicious: dict[str, datetime | None] | None = None
    withdrawn: dict[str, datetime] = {}
    delisted: set[str] = set()
    unconfirmed: set[str] = set()
    extra: list[Finding] = []
    try:
        purls = sorted(
            {
                p
                for f in fetches
                for p, c in f.components.items()
                if c.version != models.UNKNOWN
            }
        )
        found = osv.query_purls(purls)
        ids_by_purl = {
            p: [i for i in ids if i.startswith(threshold.MALICIOUS_PREFIX)]
            for p, ids in found.items()
        }
        mal_ids = sorted({i for ids in ids_by_purl.values() for i in ids})
        records: dict[str, Mapping[str, Any] | None] = {}
        malicious = {}
        for mal_id in mal_ids:
            try:
                resp = osv.get_vuln(mal_id)
                records[mal_id] = resp.json() if resp.ok else None
            except (RateLimited, TransportError, ValueError):
                records[mal_id] = None
            malicious[mal_id] = parse_osv_time((records[mal_id] or {}).get("published"))
        extra = _mal_findings(fetches, ids_by_purl, records, now)
        for mal_id, issue in sorted(
            open_mal_issues.items()
        ):  # step 6: MAL- ids that left the feed
            if mal_id in malicious:
                continue
            try:
                resp = osv.get_vuln(mal_id)
                body = resp.json() if resp.ok else None
            except (RateLimited, TransportError, ValueError):
                body = None
            if not isinstance(body, dict):
                unconfirmed.add(mal_id)
            elif "withdrawn" in body:
                when = parse_osv_time(body["withdrawn"])
                if when is None:
                    unconfirmed.add(mal_id)
                else:
                    withdrawn[mal_id] = when
            else:
                delisted.add(mal_id)
        fetched.append(run_record.FeedFetched("malicious", now, None))
    except (HttpError, RateLimited, TransportError, KeyError, ValueError) as exc:
        malicious = None
        withdrawn, delisted, unconfirmed, extra = {}, set(), set(), []
        failed.append(run_record.FeedFailed("malicious", now, str(exc)[:300]))

    snapshot = models.FeedSnapshot(
        kev=kev,
        epss=epss,
        malicious=malicious,
        malicious_withdrawn=withdrawn,
        malicious_delisted=frozenset(delisted),
        malicious_unconfirmed=frozenset(unconfirmed),
    )
    return FeedResult(snapshot, fetched, failed, kev_on, epss_info, extra)


# --- VEX, required checks, pull requests -----------------------------------------------------------


def read_vex(
    api: GitHubApi, fetch: RepoFetch
) -> tuple[list[models.VexDocument], list[run_record.RejectedVexEntry]]:
    """Read ``.vex/`` from the default branch commit. A document that does not parse is reported, not used.

    ``doc.path`` is ``<owner>/<name>:<path>`` so that a rejection in the plan (which names a path only)
    can be attributed to a repository.
    """
    name = _repo_text(fetch.repo)
    docs: list[models.VexDocument] = []
    rejected: list[run_record.RejectedVexEntry] = []
    listing = api.get(f"/repos/{name}/contents/.vex", {"ref": fetch.head_sha})
    if listing.status == 404:
        return docs, rejected
    if not listing.ok:
        raise HttpError("GET", f"/repos/{name}/contents/.vex", listing.status)
    for entry in listing.json():
        if entry.get("type") != "file" or not entry["name"].endswith(".json"):
            continue
        rel = f".vex/{entry['name']}"
        try:
            text = api.read_file(name, rel, fetch.head_sha or "")
            docs.append(vex.parse_openvex(text, f"{name}:{rel}"))
        except vex.VexError as exc:
            rejected.append(
                run_record.RejectedVexEntry(
                    name, rel, f"not valid OpenVEX: {exc.violations[0].message}"[:300]
                )
            )
        except (HttpError, TransportError, ValueError, KeyError) as exc:
            rejected.append(
                run_record.RejectedVexEntry(name, rel, f"not readable: {exc}"[:300])
            )
    return docs, rejected


def count_required_checks(api: GitHubApi, fetch: RepoFetch) -> int | None:
    """Required status checks on the default branch (classic protection plus rulesets), or None if unreadable.

    A 404 from branch protection is read as "no classic protection". GitHub also answers 404 to a token
    that may not read it, so this can undercount; the cases are not told apart here.
    """
    name = _repo_text(fetch.repo)
    branch = urllib.parse.quote(fetch.default_branch or "", safe="")
    contexts: set[str] = set()
    protection = api.get(
        f"/repos/{name}/branches/{branch}/protection/required_status_checks"
    )
    if protection.status == 200:
        data = protection.json()
        contexts.update(data.get("contexts", []))
        contexts.update(c["context"] for c in data.get("checks", []))
    elif protection.status != 404:
        return None
    for rule in api.pages(f"/repos/{name}/rules/branches/{branch}"):
        if rule.get("type") == "required_status_checks":
            contexts.update(
                c["context"]
                for c in rule.get("parameters", {}).get("required_status_checks", [])
            )
    return len(contexts)


def search_pull_requests(
    api: GitHubApi, issues: Sequence[tuple[Repo, str]]
) -> list[PullRequestRef]:
    """Find the pull request that answers each (repo, vuln id), by search. Capped per run."""
    found: list[PullRequestRef] = []
    for repo, vuln_id in issues[:PR_SEARCH_CAP]:
        query = f"repo:{_repo_text(repo)} is:pr {vuln_id} in:title,body"
        resp = api.get(
            "/search/issues",
            {"q": query, "sort": "created", "order": "asc", "per_page": 5},
        )
        if not resp.ok:
            continue
        for item in resp.json().get("items", []):
            created = parse_osv_time(item.get("created_at"))
            if created is None:
                continue
            merged = parse_osv_time((item.get("pull_request") or {}).get("merged_at"))
            found.append(PullRequestRef(repo, vuln_id, created, merged))
    return found


# --- timelines for the response metrics ------------------------------------------------------------


def timelines(
    issues: Sequence[ManagedIssue],
    raw: Mapping[tuple[str, int], Mapping[str, Any]],
    actions: Sequence[models.IssueAction],
    results: Mapping[int, int | None],
    now: datetime,
) -> list[metrics.IssueTimeline]:
    """Issue timelines from the Issues as listed, overlaid with what this run did to them."""
    states: dict[tuple[str, int], dict[str, Any]] = {}
    for issue in issues:
        if issue.kind == "finding" and issue.vuln_id:
            item = raw.get((_repo_text(issue.repo).lower(), issue.number), {})
            states[(_repo_text(issue.repo).lower(), issue.number)] = {
                "repo": issue.repo,
                "vuln_id": issue.vuln_id,
                "state": issue_body.parse_state(item.get("body")) or {},
                "closed_at": parse_osv_time(item.get("closed_at")),
                "reason": "resolved"
                if item.get("state_reason") == "completed"
                else None,
            }
    for index, action in enumerate(actions):
        number = results.get(index)
        if action.kind != "finding" or number is None or action.vuln_id is None:
            continue
        key = (_repo_text(action.repo).lower(), number)
        if action.op in ("create", "update", "reopen") and action.body:
            states[key] = {
                "repo": action.repo,
                "vuln_id": action.vuln_id,
                "state": issue_body.parse_state(action.body) or {},
                "closed_at": None,
                "reason": None,
            }
        elif action.op == "close" and key in states:
            states[key]["closed_at"] = now
            states[key]["reason"] = action.close_reason
    out: list[metrics.IssueTimeline] = []
    for entry in states.values():
        state = entry["state"]
        opened = _parse_time(state.get("opened_at"))
        if opened is None:
            continue
        history = state.get("history") if isinstance(state.get("history"), list) else []
        first = next(
            (h for h in history if isinstance(h, dict) and h.get("op") == "open"), {}
        )
        closed = entry["closed_at"]
        reason = entry["reason"] if closed is not None else None
        if closed is not None and reason is None:
            reason = "withdrawn"  # closed by someone, not by a resolved fix; never counted as resolved
        out.append(
            metrics.IssueTimeline(
                repo=entry["repo"],
                vuln_id=entry["vuln_id"],
                origin_at=_parse_time(state.get("origin_at")),
                opened_at=opened,
                opened_run_id=str(first.get("run_id", "")),
                due_at=_parse_time(state.get("due_at")),
                closed_at=closed,
                close_reason=reason,
            )
        )
    return out


def response_metrics(
    lines: Sequence[metrics.IssueTimeline],
    prs: Sequence[PullRequestRef],
    repos: Sequence[Repo],
    detect_hours: int,
    now: datetime,
    run_id: str,
) -> dict[str, run_record.RepoResponseMetrics]:
    """Per-repository figures of ``metrics.compute_metrics`` in the shape of the run record."""
    out: dict[str, run_record.RepoResponseMetrics] = {}
    for repo in repos:
        mine = [t for t in lines if t.repo == repo]
        result = metrics.compute_metrics(
            mine, [p for p in prs if p.repo == repo], detect_hours, now, run_id, [repo]
        )
        row = result.by_repo[0]

        def hours(stats: metrics.IntervalStats) -> tuple[float, ...]:
            return tuple(round(d.total_seconds() / 3600, 2) for d in stats.durations)

        out[_repo_text(repo)] = run_record.RepoResponseMetrics(
            overdue_open=row.overdue_open,
            detect_over_24h=row.detection_over_target,
            origin_unknown_excluded=result.excluded_unknown_origin,
            detect_to_open_hours=hours(result.detection),
            open_to_pr_hours=hours(result.opened_to_pr),
            pr_to_merge_hours=hours(result.pr_to_merge),
        )
    return out


# --- run record storage and the failure notice -------------------------------------------------------


def _record_sort_key(path: str) -> tuple[str, str, int]:
    parts = path.split("/")
    run, _, attempt = parts[-1].removesuffix(".json").partition("-")
    return (
        (parts[1], parts[2], int(run) * 1000 + int(attempt or 0))
        if len(parts) == 4
        else ("", "", 0)
    )


def list_run_paths(hub: GitHubApi, hub_repo: Repo, branch: str) -> list[str]:
    """Paths of the run records on the runs branch. The branch must exist; it is never created here."""
    tree = hub.get_json(
        f"/repos/{_repo_text(hub_repo)}/git/trees/{urllib.parse.quote(branch)}",
        {"recursive": "1"},
    )
    if tree.get("truncated"):
        raise HttpError(
            "GET",
            "git/trees",
            200,
            "tree listing truncated; cannot check that a path is new",
        )
    return sorted(
        (
            e["path"]
            for e in tree["tree"]
            if e["type"] == "blob"
            and re.fullmatch(r"runs/\d{4}/\d{2}/\d+-\d+\.json", e["path"])
        ),
        key=_record_sort_key,
    )


def recent_outcomes(
    hub: GitHubApi, hub_repo: Repo, branch: str, paths: Sequence[str]
) -> list[run_record.RunOutcome]:
    out: list[run_record.RunOutcome] = []
    for path in paths[-RECENT_OUTCOMES:]:
        try:
            record = run_record.from_json(
                hub.read_file(_repo_text(hub_repo), path, branch)
            )
        except (
            HttpError,
            TransportError,
            run_record.RunRecordError,
            ValueError,
            KeyError,
        ):
            continue  # a record that cannot be read is not a sign of anything
        out.append(run_record.RunOutcome(record.run_id, record.end_state))
    return out


def save_record(
    hub: GitHubApi,
    hub_repo: Repo,
    branch: str,
    record: run_record.RunRecord,
    existing: Sequence[str],
) -> str:
    """Create the record file with a PUT that carries no ``sha``: an existing path is refused, never overwritten."""
    path = run_record.new_record_path(record, existing)
    text = run_record.to_json(record)
    resp = hub.write(
        "PUT",
        f"/repos/{_repo_text(hub_repo)}/contents/{path}",
        {
            "message": f"chore: record supply-chain run {record.run_id}",
            "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "branch": branch,
        },
    )
    if resp.status != 201:
        raise HttpError("PUT", f"contents/{path}", resp.status, resp.text()[:200])
    return path


def apply_failure_notice(
    api: GitHubApi,
    hub_repo: Repo,
    decision: run_record.NoticeDecision,
    messages: Sequence[str],
    now: datetime,
    existing: ManagedIssue | None,
    labels_done: set[str],
) -> None:
    """Carry out the decision of ``run_record.decide_failure_notice``. Raises HttpError when GitHub refuses."""
    if decision.action == "none" or decision.run_id is None:
        return
    base = f"/repos/{_repo_text(hub_repo)}/issues"
    if decision.action == "create":
        ensure_label(api, hub_repo, labels_done)
        body = issue_body.render_failure(hub_repo, decision.run_id, now, messages)
        resp = api.write(
            "POST", base, {"title": FAILURE_TITLE, "body": body, "labels": [LABEL]}
        )
        if resp.status != 201:
            raise HttpError("POST", base, resp.status, resp.text()[:200])
        return
    if existing is None:
        raise HttpError("POST", base, 0, "no open failure Issue to update")
    path = f"{base}/{existing.number}"
    if decision.action == "append":
        text = "\n".join(f"- {m}" for m in messages)
        resp = api.write(
            "POST",
            f"{path}/comments",
            {
                "body": f"Run {decision.run_id} failed again ({_time_text(now)}).\n\n{text}"
            },
        )
    else:  # close
        api.write(
            "POST", f"{path}/comments", {"body": f"Run {decision.run_id} succeeded."}
        )
        resp = api.write(
            "PATCH", path, {"state": "closed", "state_reason": "completed"}
        )
    if not resp.ok:
        raise HttpError("POST", path, resp.status, resp.text()[:200])


def open_failure_issue(api: GitHubApi, hub_repo: Repo) -> ManagedIssue | None:
    issues, _ = list_managed_issues(api, hub_repo)
    return next((i for i in issues if i.kind == "failure" and i.state == "open"), None)


# --- the run -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    hub: Repo
    run_id: str
    aggregator_commit: str
    policy_text: str
    policy_commit: str
    runs_branch: str = RUNS_BRANCH


@dataclass
class Outcome:
    record: run_record.RunRecord
    exit_code: int
    saved_path: str | None
    messages: list[str]


def _empty_record(
    cfg: Config,
    started: datetime,
    finished: datetime,
    reasons: Sequence[str],
    policy_commit: str | None,
) -> run_record.RunRecord:
    return run_record.RunRecord(
        run_id=cfg.run_id,
        started_at=started,
        finished_at=finished,
        end_state="failure",
        failure_reason="; ".join(reasons)[:1000],
        aggregator_commit=cfg.aggregator_commit,
        policy_commit=policy_commit,
        repositories=run_record.Repositories((), (), {}),
        feeds=run_record.Feeds((), ()),
        kev_fetched_on=None,
        epss=run_record.EpssInfo(None, None),
        findings=(),
        issues=(),
        vex_exclusions=(),
        rejected_vex=(),
        unscored=(),
        malicious_withdrawn_unconfirmed=(),
        summary_overflow={},
        response_metrics={},
        pull_requests=(),
        rate_limit=run_record.RateLimitRecord((), ()),
        failure_notice_error=None,
    )


def run(
    cfg: Config,
    *,
    spoke: GitHubApi,
    hub: GitHubApi,
    client: Client,
    osv: Osv,
    now_fn: Callable[[], datetime] = utc_now,
) -> Outcome:
    """Run the Aggregator once. See the module docstring for the order and the exit codes."""
    started = now_fn()
    reasons: list[str] = []
    labels_done: set[str] = set()
    try:
        policy = parse_policy(cfg.policy_text)
    except PolicyError as exc:
        # Nothing is fetched and no finding Issue is touched: with no Policy_File there is no
        # target list, and acting on a guess could close real Issues.
        reasons.append(f"Policy_File could not be read: {str(exc)[:300]}")
        record = _empty_record(cfg, started, now_fn(), reasons, None)
        return _finish(cfg, record, reasons, spoke, hub, now_fn, labels_done)

    now = started
    fetches: list[RepoFetch] = []
    processed: list[str] = []
    unprocessed: list[str] = []
    rate_limited = False
    targets = list(policy.target_repositories)
    for position, repo in enumerate(targets):
        try:
            fetches.append(fetch_repo(spoke, repo, now))
            processed.append(_repo_text(repo))
        except RateLimited as exc:
            rate_limited = True
            unprocessed = [_repo_text(r) for r in targets[position:]]
            reasons.append(f"rate limit stopped the run: {exc}")
            break

    # step 5: Issues that exist. A repository whose list cannot be read is left out of planning,
    # because planning without them would open duplicates.
    issues: list[ManagedIssue] = []
    raw: dict[tuple[str, int], dict[str, Any]] = {}
    listed: list[RepoFetch] = []
    for fetch in fetches:
        if fetch.default_branch is None:
            continue
        try:
            found, items = list_managed_issues(spoke, fetch.repo)
        except (HttpError, TransportError) as exc:
            fetch.fail("A", f"issue list: {exc}")
            continue
        except RateLimited as exc:
            rate_limited = True
            reasons.append(f"rate limit stopped the run: {exc}")
            break
        issues.extend(found)
        for issue, item in zip(found, items, strict=True):
            raw[(_repo_text(issue.repo).lower(), issue.number)] = item
        listed.append(fetch)
    fetch_ok_repos = [f for f in listed if f.layer_ok["A"] or f.layer_ok["B"]]
    fetch_ok = frozenset(f.repo for f in fetch_ok_repos)

    findings = list(
        normalized.dedupe_findings(
            f for fetch in fetch_ok_repos for f in fetch.findings
        )
    )
    open_mal = {
        i.vuln_id: i
        for i in issues
        if i.kind == "finding"
        and i.state == "open"
        and i.vuln_id
        and i.vuln_id.startswith(threshold.MALICIOUS_PREFIX)
        and i.repo in fetch_ok
    }
    feeds = fetch_feeds(client, osv, fetch_ok_repos, findings, open_mal, now)
    findings = list(normalized.dedupe_findings([*findings, *feeds.extra_findings]))

    vex_docs: dict[Repo, tuple[models.VexDocument, ...]] = {}
    rejected_vex: list[run_record.RejectedVexEntry] = []
    for fetch in fetch_ok_repos:
        try:
            docs, rejected = read_vex(spoke, fetch)
        except RateLimited as exc:
            rate_limited = True
            reasons.append(f"rate limit stopped the run: {exc}")
            break
        except (HttpError, TransportError) as exc:
            fetch.fail("A", f"vex directory: {exc}")
            continue
        vex_docs[fetch.repo] = tuple(docs)
        rejected_vex.extend(rejected)

    required: dict[str, int | None] = {}
    for fetch in fetches:
        if fetch.default_branch is None:
            continue
        try:
            required[_repo_text(fetch.repo)] = count_required_checks(spoke, fetch)
        except RateLimited as exc:
            rate_limited = True
            reasons.append(f"rate limit stopped the run: {exc}")
            break
        except (HttpError, TransportError, KeyError, ValueError):
            required[_repo_text(fetch.repo)] = (
                None  # could not be read; recorded as such
            )

    wanted = [
        (i.repo, i.vuln_id)
        for i in issues
        if i.kind == "finding" and i.vuln_id and i.repo in fetch_ok
    ]
    try:
        pull_requests = search_pull_requests(spoke, wanted)
    except RateLimited as exc:
        rate_limited = True
        pull_requests = []
        reasons.append(f"rate limit stopped the run: {exc}")

    plan = planner.plan(
        models.PlanInputs(
            policy=policy,
            run_id=cfg.run_id,
            now=now,
            pull_requests=tuple(pull_requests),
            findings=frozenset(findings),
            fetch_ok=fetch_ok,
            feeds=feeds.snapshot,
            vex=vex_docs,
            issues=tuple(i for i in issues if i.repo in fetch_ok),
        )
    )

    entries: list[run_record.IssueEntry] = []
    results: dict[int, int | None] = {}
    for index, action in enumerate(plan.actions):
        if rate_limited:
            entries.append(
                run_record.IssueEntry(
                    _repo_text(action.repo),
                    action.number,
                    action.op,
                    action.vuln_id,
                    False,
                )
            )
            continue
        try:
            number = apply_action(spoke, action, labels_done)
            results[index] = number
            entries.append(
                run_record.IssueEntry(
                    _repo_text(action.repo), number, action.op, action.vuln_id, True
                )
            )
        except (HttpError, TransportError) as exc:
            reasons.append(
                f"Issue {action.op} failed in {_repo_text(action.repo)}: {exc}"[:300]
            )
            entries.append(
                run_record.IssueEntry(
                    _repo_text(action.repo),
                    action.number,
                    action.op,
                    action.vuln_id,
                    False,
                )
            )
        except RateLimited as exc:
            rate_limited = True
            reasons.append(f"rate limit stopped the run: {exc}")
            entries.append(
                run_record.IssueEntry(
                    _repo_text(action.repo),
                    action.number,
                    action.op,
                    action.vuln_id,
                    False,
                )
            )

    kev_ids = frozenset(feeds.snapshot.kev or ())
    epss_table = feeds.snapshot.epss or {}
    finding_entries = tuple(
        run_record.FindingEntry(
            repo=_repo_text(f.repo),
            vuln_id=f.vuln_id,
            purl=f.component.purl,
            cvss_severity=f.cvss_severity,
            kev_listed=any(i in kev_ids for i in (f.vuln_id, *f.aliases)),
            malicious=threshold.is_malicious(f),
            epss=next(
                (epss_table[i][0] for i in (f.vuln_id, *f.aliases) if i in epss_table),
                None,
            ),
            meets_threshold=threshold.meets_opening_threshold(
                f,
                None if feeds.snapshot.kev is None else kev_ids,
                policy.opening_threshold,
            ),
        )
        for f in sorted(
            findings,
            key=lambda f: (_repo_text(f.repo).lower(), f.vuln_id, f.component.purl),
        )
    )
    heads = {_repo_text(f.repo).lower(): f.head_sha or "" for f in fetches}
    statuses = _vex_statuses(vex_docs)
    exclusions = tuple(
        run_record.VexExclusion(
            repo=_repo_text(finding.repo),
            vuln_id=finding.vuln_id,
            path=path.partition(":")[2],
            commit=heads.get(_repo_text(finding.repo).lower(), ""),
            status=statuses.get(
                (path, finding.vuln_id, finding.component.purl), "unknown"
            ),
        )
        for finding, path in plan.vex_exclusions
    )
    rejected_vex.extend(
        run_record.RejectedVexEntry(
            path.partition(":")[0], path.partition(":")[2], reason
        )
        for path, reason in plan.rejected_vex
    )

    failures = tuple(x for f in fetches for x in f.failures)
    scanned = tuple(sorted(_repo_text(f.repo) for f in fetch_ok_repos))
    if targets and not scanned:
        reasons.append("no target repository could be read")
    if any(not e.ok for e in entries) and not any("Issue" in r for r in reasons):
        reasons.append("some Issue operations were not applied")

    finished = now_fn()
    record = run_record.RunRecord(
        run_id=cfg.run_id,
        started_at=started,
        finished_at=finished,
        end_state="failure" if reasons else "success",
        failure_reason="; ".join(reasons)[:1000] if reasons else None,
        aggregator_commit=cfg.aggregator_commit,
        policy_commit=cfg.policy_commit,
        repositories=run_record.Repositories(
            scanned, failures, dict(sorted(required.items()))
        ),
        feeds=run_record.Feeds(tuple(feeds.fetched), tuple(feeds.failed)),
        kev_fetched_on=feeds.kev_fetched_on,
        epss=feeds.epss_info,
        findings=finding_entries,
        issues=tuple(entries),
        vex_exclusions=exclusions,
        rejected_vex=tuple(rejected_vex),
        unscored=tuple(
            run_record.UnscoredEntry(_repo_text(f.repo), f.vuln_id)
            for f in plan.unscored
        ),
        malicious_withdrawn_unconfirmed=tuple(
            run_record.WithdrawnUnconfirmed(_repo_text(r), n, i)
            for r, n, i in plan.malicious_withdrawn_unconfirmed
        ),
        summary_overflow={
            _repo_text(r): n
            for r, n in sorted(
                plan.overflow_counts.items(), key=lambda kv: _repo_text(kv[0]).lower()
            )
        },
        response_metrics=response_metrics(
            timelines(issues, raw, plan.actions, results, now),
            pull_requests,
            [f.repo for f in fetch_ok_repos],
            policy.response_target.detect_hours,
            now,
            cfg.run_id,
        ),
        pull_requests=tuple(pull_requests),
        rate_limit=run_record.RateLimitRecord(tuple(processed), tuple(unprocessed)),
        failure_notice_error=None,
    )
    return _finish(cfg, record, reasons, spoke, hub, now_fn, labels_done)


def _vex_statuses(
    docs: Mapping[Repo, Sequence[models.VexDocument]],
) -> dict[tuple[str, str, str], str]:
    table: dict[tuple[str, str, str], str] = {}
    for repo_docs in docs.values():
        for doc in sorted(repo_docs, key=lambda d: d.path):
            for statement in doc.statements:
                for vuln_id in (statement.vuln_id, *statement.aliases):
                    for product in statement.products:
                        table.setdefault((doc.path, vuln_id, product), statement.status)
    return table


def _finish(
    cfg: Config,
    record: run_record.RunRecord,
    reasons: Sequence[str],
    spoke: GitHubApi,
    hub: GitHubApi,
    now_fn: Callable[[], datetime],
    labels_done: set[str],
) -> Outcome:
    """Decide and send the failure notice, then save the record. The notice comes first so that a
    notice that could not be sent is written into the record: the record is never rewritten."""
    messages = list(reasons)
    notice_error: str | None = None
    try:
        existing_paths = list_run_paths(hub, cfg.hub, cfg.runs_branch)
    except (HttpError, RateLimited, TransportError, ValueError, KeyError) as exc:
        # The runs branch is never created here, and without it neither the streak nor the save
        # is possible. The run is abnormal; the watchdog sees the missing record.
        messages.append(f"run record not saved: runs branch not readable: {exc}"[:300])
        return Outcome(record, 1, None, messages)
    try:
        outcomes = recent_outcomes(hub, cfg.hub, cfg.runs_branch, existing_paths)
        outcomes.append(run_record.RunOutcome(cfg.run_id, record.end_state))
        notice_open = open_failure_issue(spoke, cfg.hub)
        decision = run_record.decide_failure_notice(outcomes, notice_open is not None)
        apply_failure_notice(
            spoke,
            cfg.hub,
            decision,
            messages or ["(no reason recorded)"],
            now_fn(),
            notice_open,
            labels_done,
        )
    except (HttpError, RateLimited, TransportError, ValueError) as exc:
        notice_error = f"failure notice not sent: {exc}"[:300]
        messages.append(notice_error)
    if notice_error is not None:
        record = _with(
            record,
            end_state="failure",
            failure_reason="; ".join(messages)[:1000],
            failure_notice_error=notice_error,
        )
    saved: str | None = None
    try:
        saved = save_record(hub, cfg.hub, cfg.runs_branch, record, existing_paths)
    except (HttpError, RateLimited, TransportError, run_record.RunRecordError) as exc:
        messages.append(f"run record not saved: {exc}"[:300])
        return Outcome(record, 1, None, messages)
    return Outcome(record, 1 if record.end_state == "failure" else 0, saved, messages)


def _with(record: run_record.RunRecord, **changes: Any) -> run_record.RunRecord:
    return dataclasses.replace(record, **changes)


# --- command line -----------------------------------------------------------------------------------------


def _env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"error: environment variable {name} is not set")
    return value


def _write_summary(outcome: Outcome) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    record = outcome.record
    lines = [
        f"## Supply-chain Aggregator run {record.run_id}",
        f"- end state: {record.end_state}",
        f"- started: {_time_text(record.started_at)}, finished: {_time_text(record.finished_at)}",
        f"- repositories scanned: {len(record.repositories.scanned)}, fetch failures: {len(record.repositories.fetch_failed)}",
        f"- Issue operations: {len(record.issues)}, not applied: {sum(1 for i in record.issues if not i.ok)}",
        f"- run record: {outcome.saved_path or 'not saved'}",
        *(f"- {m}" for m in outcome.messages),
    ]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def cmd_run() -> int:
    policy_ref = _env("SUPPLY_CHAIN_POLICY_REF")
    if not HEX40.fullmatch(policy_ref):
        print(
            "error: SUPPLY_CHAIN_POLICY_REF must be 40 lowercase hex digits",
            file=sys.stderr,
        )
        return 1
    sha = _env("GITHUB_SHA")
    if not HEX40.fullmatch(sha):
        print("error: GITHUB_SHA must be 40 lowercase hex digits", file=sys.stderr)
        return 1
    try:
        policy_text = Path(_env("POLICY_FILE")).read_text(encoding="utf-8")
    except OSError as exc:
        policy_text = ""
        print(f"error: Policy_File not readable: {exc}", file=sys.stderr)
    client = Client(UrllibTransport())
    cfg = Config(
        hub=_split_repo(_env("GITHUB_REPOSITORY")),
        run_id=f"{_env('GITHUB_RUN_ID')}-{_env('GITHUB_RUN_ATTEMPT')}",
        aggregator_commit=sha,
        policy_text=policy_text,
        policy_commit=policy_ref,
    )
    outcome = run(
        cfg,
        spoke=GitHubApi(client, _env("SPOKE_TOKEN")),
        hub=GitHubApi(client, _env("HUB_TOKEN")),
        client=client,
        osv=Osv(client),
    )
    _write_summary(outcome)
    for message in outcome.messages:
        print(message, file=sys.stderr)
    return outcome.exit_code


def notify_failure(
    api: GitHubApi, hub_repo: Repo, run_id: str, messages: Sequence[str], now: datetime
) -> str:
    """Append to the open failure Issue, or open one. Returns the action taken.

    The caller (the watchdog) has already established a failure that spans at least two scheduled
    runs, so two consecutive failures are passed to ``decide_failure_notice``; it still makes the
    create-or-append decision.
    """
    outcomes = [
        run_record.RunOutcome(f"{run_id}-earlier", "failure"),
        run_record.RunOutcome(run_id, "failure"),
    ]
    existing = open_failure_issue(api, hub_repo)
    decision = run_record.decide_failure_notice(outcomes, existing is not None)
    apply_failure_notice(api, hub_repo, decision, messages, now, existing, set())
    return decision.action


def cmd_notify_failure(args: argparse.Namespace) -> int:
    if not re.fullmatch(r"[0-9]+(-[0-9]+)?", args.run_id):
        print("error: --run-id must be digits", file=sys.stderr)
        return 2
    api = GitHubApi(Client(UrllibTransport()), _env("NOTIFY_TOKEN"))
    try:
        action = notify_failure(
            api,
            _split_repo(_env("GITHUB_REPOSITORY")),
            args.run_id,
            args.message,
            utc_now(),
        )
    except (HttpError, RateLimited, TransportError) as exc:
        print(f"error: failure notice not sent: {exc}", file=sys.stderr)
        return 1
    print(f"failure notice: {action}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="run the Aggregator once")
    notify = sub.add_parser(
        "notify-failure", help="append to or open the failure Issue"
    )
    notify.add_argument("--run-id", required=True)
    notify.add_argument("--message", action="append", required=True)
    args = parser.parse_args(argv)
    return cmd_run() if args.command == "run" else cmd_notify_failure(args)


if __name__ == "__main__":
    sys.exit(main())
