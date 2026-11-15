#!/usr/bin/env python3
"""Supply-chain Aggregator: fetch, hand the inputs to the pure core, apply the plan, save the run.

Usage:
    python3 tools/supply_chain_aggregator.py run
    python3 tools/supply_chain_aggregator.py notify-failure --run-id ID --message TEXT [--message TEXT ...]

This module decides nothing. Thresholds, de-duplication, when an Issue closes, the per-run limit,
the staleness limit of the watchdog, the failure streak and the retry waits are all in tools/supply_chain/
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
    CHAIN_ACK_FILE     path of the chain ledger in the same checkout (docs/agent/supply-chain-chain-ack.json).
                       A file that does not exist is an empty ledger: no decision has been made.
    RUNNER_TEMP        where the per-month lock files go (the system temporary directory when unset)
    OBSERVATION_FILE   path of the pilot observation input (optional). Without it, the file
                       ``supply-chain-observation.json`` beside POLICY_FILE is used when it exists; with neither,
                       the pilot is counted with no window. See ``parse_observation``.

POLICY_FILE is the path inside the directory where the workflow checked out the policy
repository at SUPPLY_CHAIN_POLICY_REF. SPOKE_TOKEN is a GitHub App installation token with
contents:read, issues:write, dependabot_alerts:read, actions:read and metadata:read. HUB_TOKEN is a
second installation token limited to this one repository with contents:write only; the job's own
GITHUB_TOKEN never writes the runs branch. Create both with actions/create-github-app-token from
the App's client ID (variable SUPPLY_CHAIN_APP_CLIENT_ID) and private key (secret SUPPLY_CHAIN_APP_PRIVATE_KEY),
and fail with a clear message when either is unset. The runs branch ``supply-chain-runs`` must
already exist; it is never created here.

The record chain is guarded around the write of the run record (``guard_chain``), under one lock per month:

* the chain ledger is read, and the month's records are read through it (``chain_recovery.effective_entries``);
  a ledger that cannot be read or cannot stand stops the write;
* the SHA-256 of the record the previous run wrote is read from the newest annotated tag
  ``supply-chain-runs-tip-<YYYY-MM>-<run id>`` and compared with the month (``run_record.verify_month_tip``);
* the first run of a month seals the month before it with the annotated tag ``supply-chain-runs-<YYYY-MM>``, or
  checks the seal that is already there (``run_record.verify_month_seal``);
* after the write, the SHA-256 of the new record goes into the job summary and into a new tip tag.

A tag that cannot be created is a warning: the record stays, and the next run starts without a recorded value.
Protecting the tags with a ruleset is a maintainer's setting and is not made here.

The run record has no place for ``skipped_paths`` or for the pilot's counts, and its schema is a copy that is not
changed here. So a second file, the extra record, is written after the run record, on the same branch, at
``runs-extra/<YYYY>/<MM>/<run id>.json``. It names the run record (path and SHA-256) and carries ``skipped_paths``
(per repository, from the ``generation.json`` of the layer B artifact that was scanned) and ``pilot`` (what the
maintainer reads to judge the detector: ``metrics.compute_pilot_rates`` and the rest, fed here, not recomputed).
It is not under ``runs/``, which the watchdog and ``recent_outcomes`` read as run records, and it is not part of the
chain: no ``prev_record_sha256``, tip tag or seal covers it. It is created, never overwritten. A failure to write it
is a warning and changes neither the run record nor the exit code.

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
import contextlib
import dataclasses
import fcntl
import io
import json
import math
import os
import re
import sys
import tempfile
import urllib.parse
import zipfile
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from supply_chain import (
    chain_recovery,
    issue_body,
    metrics,
    models,
    normalized,
    planner,
    run_record,
    threshold,
    vex,
)
from supply_chain.models import (
    Component,
    Finding,
    KevEntry,
    ManagedIssue,
    PullRequestRef,
    Repo,
)
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
OVERDUE_COLOR = "b60205"
OVERDUE_DESCRIPTION = "The Response_Target due time of this Issue has passed (set by the supply-chain Aggregator)"
# name -> (color, description), for every label this module may create.
LABEL_SPECS = {
    LABEL: (LABEL_COLOR, LABEL_DESCRIPTION),
    models.OVERDUE_LABEL: (OVERDUE_COLOR, OVERDUE_DESCRIPTION),
}
RUNS_BRANCH = "supply-chain-runs"
EXTRA_DIR = "runs-extra"
EXTRA_SCHEMA_VERSION = 1
OBSERVATION_FILE_NAME = "supply-chain-observation.json"
RECENT_OUTCOMES = max(run_record.FAILURE_STREAK_THRESHOLD, 3)
PR_SEARCH_CAP = 60
MAX_ZIP_MEMBER_BYTES = 200 * 1024 * 1024
HEX40 = re.compile(r"[0-9a-f]{40}")
FINDING_TITLE_PREFIX = "[supply-chain] "
SUMMARY_TITLE = "[supply-chain] 起票数の上限を超えた脆弱性の一覧"
FAILURE_TITLE = "[supply-chain] Aggregator の実行失敗"
# Annotated tags that pin the record chain. The two-line annotation is ``path: ...`` and ``sha256: ...``.
TIP_TAG_PREFIX = "supply-chain-runs-tip-"
SEAL_TAG_PREFIX = "supply-chain-runs-"
_SHA256_LINE = re.compile(r"^sha256: ?([0-9a-f]{64})$", re.MULTILINE)

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
                closed_at=parse_osv_time(item.get("closed_at")),
                labels=_label_names(item.get("labels")),
            )
        )
        raw_items.append(item)
    return managed, raw_items


def _label_names(raw: object) -> frozenset[str]:
    """Names of the labels of an Issue as the API lists them (objects, or bare strings in older shapes)."""
    names: set[str] = set()
    for label in raw if isinstance(raw, list) else ():
        name = label if isinstance(label, str) else (label or {}).get("name")
        if isinstance(name, str) and name:
            names.add(name)
    return frozenset(names)


def ensure_label(api: GitHubApi, repo: Repo, done: set[str], name: str = LABEL) -> None:
    """Create a label (by default the identification label) once per repository if it does not exist."""
    key = f"{_repo_text(repo).lower()}:{name}"
    if key in done:
        return
    color, description = LABEL_SPECS[name]
    path = f"/repos/{_repo_text(repo)}/labels"
    if api.get(f"{path}/{urllib.parse.quote(name, safe='')}").status == 404:
        resp = api.write(
            "POST",
            path,
            {"name": name, "color": color, "description": description},
        )
        if resp.status not in (201, 422):  # 422: it was created in between
            raise HttpError("POST", path, resp.status, resp.text()[:200])
    done.add(key)


def set_issue_labels(
    api: GitHubApi,
    repo: Repo,
    number: int,
    add: Sequence[str],
    remove: Sequence[str],
    labels_done: set[str],
) -> None:
    """Add and remove labels on an Issue. A label that is already off the Issue is not an error.

    Endpoints (GitHub REST, Issues > Labels): ``POST /repos/{owner}/{repo}/issues/{n}/labels`` with
    ``{"labels": [...]}`` and ``DELETE /repos/{owner}/{repo}/issues/{n}/labels/{name}``. These were written from
    memory of the reference, without a network to read it against.
    """
    base = f"/repos/{_repo_text(repo)}/issues/{number}/labels"
    if add:
        for name in add:
            ensure_label(api, repo, labels_done, name)
        resp = api.write("POST", base, {"labels": list(add)})
        if not resp.ok:
            raise HttpError("POST", base, resp.status, resp.text()[:200])
    for name in remove:
        path = f"{base}/{urllib.parse.quote(name, safe='')}"
        resp = api.delete(path)
        if not resp.ok and resp.status != 404:
            raise HttpError("DELETE", path, resp.status, resp.text()[:200])


def apply_action(
    api: GitHubApi, action: models.IssueAction, labels_done: set[str]
) -> int | None:
    """Apply one planned Issue operation. Returns the Issue number. Raises HttpError on a refusal.

    An ``update`` with no body changes labels and nothing else: no body is written for it.
    """
    base = f"/repos/{_repo_text(action.repo)}/issues"
    if action.op == "create":
        ensure_label(api, action.repo, labels_done)
        for name in action.add_labels:
            ensure_label(api, action.repo, labels_done, name)
        title = (
            SUMMARY_TITLE
            if action.kind == "summary"
            else f"{FINDING_TITLE_PREFIX}{action.vuln_id}"
        )
        resp = api.write(
            "POST",
            base,
            {
                "title": title,
                "body": action.body,
                "labels": [LABEL, *action.add_labels],
            },
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
    payload: dict[str, Any] | None
    if action.op == "update":
        payload = {"body": action.body} if action.body is not None else None
    elif action.op == "reopen":
        payload = {"state": "open"}
        if action.body is not None:
            payload["body"] = action.body
    else:  # close
        payload = {
            "state": "closed",
            "state_reason": "completed"
            if action.close_reason == "resolved"
            else "not_planned",
        }
    if payload is not None:
        resp = api.write("PATCH", path, payload)
        if not resp.ok:
            raise HttpError("PATCH", path, resp.status, resp.text()[:200])
    if action.op == "close":
        # the reason is recorded as a comment; failing to comment does not undo the close
        api.write(
            "POST",
            f"{path}/comments",
            {"body": f"Closed by the Aggregator: {action.close_reason}"},
        )
    elif action.add_labels or action.remove_labels:
        set_issue_labels(
            api,
            action.repo,
            action.number,
            action.add_labels,
            action.remove_labels,
            labels_done,
        )
    return action.number


# --- duplicates ----------------------------------------------------------------------------------------


def _state_date(raw: object) -> date | None:
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _rebuild_finding_issue(
    issue: ManagedIssue,
    body: object,
    representative: str,
    run_id: str,
    now: datetime,
) -> issue_body.FindingIssue | None:
    """Rebuild what the body of ``issue`` shows from its state block, with ``duplicate_of`` set.

    Returns ``None`` when the state cannot be read back faithfully: a missing time, a KEV listing without its
    date, or components left out of the body for length (a rebuilt body would no longer say so). The Issue is
    then left as it is.
    """
    state = issue.body_state or {}
    marker = issue_body.parse_marker(body if isinstance(body, str) else None)
    detected, opened, due = (
        _parse_time(state.get(k)) for k in ("detected_at", "opened_at", "due_at")
    )
    if (
        marker is None
        or issue.vuln_id is None
        or detected is None
        or opened is None
        or due is None
    ):
        return None
    if state.get("components_omitted") not in (0, None):
        return None
    components: list[Component] = []
    raw_components = state.get("components")
    for item in raw_components if isinstance(raw_components, list) else ():
        if not isinstance(item, Mapping) or not isinstance(item.get("purl"), str):
            return None
        version = (
            item["version"] if isinstance(item.get("version"), str) else models.UNKNOWN
        )
        components.append(
            Component(
                purl=item["purl"],
                name=normalized.component_from_purl(item["purl"]).name,
                version=version,
            )
        )
    kev: KevEntry | None = None
    if state.get("kev_listed") is True:
        raw_kev = state.get("kev")
        if not isinstance(raw_kev, Mapping):
            return None
        added = _state_date(raw_kev.get("date_added"))
        if added is None:
            return None
        triage = raw_kev.get("forensic_triage")
        kev = KevEntry(
            added,
            True if raw_kev.get("known_ransomware_campaign_use") is True else None,
            _state_date(raw_kev.get("due_date")),
            triage if isinstance(triage, bool) else None,
        )
    epss: tuple[str, date, str] | None = None
    raw_epss = state.get("epss")
    if isinstance(raw_epss, Mapping):
        when = _state_date(raw_epss.get("date"))
        score, model = raw_epss.get("score"), raw_epss.get("model_version")
        if when is None or not isinstance(score, str) or not isinstance(model, str):
            return None
        epss = (score, when, model)
    severity = state.get("cvss_severity")
    history: list[issue_body.HistoryEntry] = []
    raw_history = state.get("history")
    for entry in raw_history if isinstance(raw_history, list) else ():
        if not isinstance(entry, Mapping):
            continue
        at = _parse_time(entry.get("at"))
        if (
            at is not None
            and isinstance(entry.get("op"), str)
            and isinstance(entry.get("run_id"), str)
        ):
            history.append(issue_body.HistoryEntry(entry["op"], entry["run_id"], at))
    history.append(issue_body.HistoryEntry("update", run_id, now))
    sources = state.get("cvss_sources")
    fixed, alias_only = state.get("fixed_version"), state.get("vex_names_alias_only")
    malicious = state.get("malicious")
    return issue_body.FindingIssue(
        repo=issue.repo,
        vuln_id=issue.vuln_id,
        aliases=marker.aliases,
        components=tuple(components),
        cvss_severity=severity
        if severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        else None,
        kev=kev,
        epss=epss,
        fixed_version=fixed if isinstance(fixed, str) else None,
        origin_at=_parse_time(state.get("origin_at")),
        origin_is_date_only=state.get("origin_is_date_only") is True,
        detected_at=detected,
        opened_at=opened,
        due_at=due,
        last_run_id=run_id,
        history=tuple(history),
        malicious=malicious if isinstance(malicious, bool) else None,
        kev_first_release_at=_parse_time(state.get("kev_first_release_at")),
        cvss_sources=tuple(s for s in sources if isinstance(s, str))
        if isinstance(sources, list)
        else (),
        duplicate_of=representative,
        vex_names_alias_only=alias_only if isinstance(alias_only, str) else None,
    )


def duplicate_updates(
    plan: models.Plan,
    issues: Sequence[ManagedIssue],
    raw: Mapping[tuple[str, int], Mapping[str, Any]],
    run_id: str,
    now: datetime,
) -> list[models.IssueAction]:
    """Updates that write ``duplicate_of`` into the Issues the plan names as duplicates.

    The Issue stays open. One whose state already names the same representative is left alone, so the next
    run writes nothing. The plan names the duplicates and the representative; it does not render their bodies.
    """
    by_key = {(_repo_text(i.repo).lower(), i.number): i for i in issues}
    out: list[models.IssueAction] = []
    for repo, number, representative in plan.duplicate_of:
        key = (_repo_text(repo).lower(), number)
        issue, item = by_key.get(key), raw.get(key)
        if issue is None or item is None or issue.vuln_id is None:
            continue
        if (issue.body_state or {}).get("duplicate_of") == representative:
            continue
        data = _rebuild_finding_issue(
            issue, item.get("body"), representative, run_id, now
        )
        if data is None:
            continue
        out.append(
            models.IssueAction(
                "update",
                repo,
                "finding",
                issue.vuln_id,
                number,
                issue_body.render_finding(data),
                None,
            )
        )
    return out


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
    # An SBOM with no component and incomplete coverage was read: the repository was not scanned, and nothing
    # read from it (a missing finding included) is a ground to close an Issue.
    unscanned: bool = False
    # The ``skipped_paths`` of the ``generation.json`` in the layer B artifact that was scanned. ``None``: no
    # layer B artifact was used, or it did not say (an empty list is a statement: nothing was excluded).
    skipped_paths: list[str] | None = None
    # Things worth a line in the job log that do not fail the run.
    warnings: list[str] = field(default_factory=list)

    def fail(self, layer: models.Layer, reason: str) -> None:
        self.failures.append(
            run_record.FetchFailure(_repo_text(self.repo), layer, reason[:300])
        )


def _sbom_unscanned(info: spdx.SbomInfo) -> bool:
    """True when the SBOM lists no addressable package and says so by incomplete coverage (Requirement 4.14).

    A document that declares itself empty (``CONTAINS`` -> ``NONE``) has complete coverage and is a real empty.
    """
    return info.component_count == 0 and not info.coverage_complete


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


def _advisory_type(raw: object) -> models.AdvisoryType | None:
    """The advisory ``type`` of a Dependabot alert's ``security_advisory``, read the way the core reads it.

    ``malware`` stays ``malware``; ``reviewed``, ``unreviewed`` and ``vulnerability`` are ``vulnerability``;
    anything else, and a missing field, is ``None``. Whether the alert object carries ``type`` at all was not
    confirmed against the reference (no network when this was written), so a missing field is the normal case.
    """
    text = raw.strip().lower() if isinstance(raw, str) else ""
    if text == "malware":
        return "malware"
    return (
        "vulnerability" if text in ("reviewed", "unreviewed", "vulnerability") else None
    )


def _cvss_source(advisory: Mapping[str, Any]) -> str | None:
    """Which CVSS version the alert carries a score for, as ``GHSA:CVSS_V4`` or ``GHSA:CVSS_V3``. Display only.

    Version 4 is named when its score is above zero, else version 3. This reads the presence of a score in
    ``cvss_severities``; it does not know which of the two GitHub's ``severity`` was derived from, so it is a
    guess about the source and never an input to a decision.
    """
    severities = advisory.get("cvss_severities")
    if not isinstance(severities, Mapping):
        return None
    for key, name in (("cvss_v4", "GHSA:CVSS_V4"), ("cvss_v3", "GHSA:CVSS_V3")):
        entry = severities.get(key)
        score = entry.get("score") if isinstance(entry, Mapping) else None
        if isinstance(score, int | float) and not isinstance(score, bool) and score > 0:
            return name
    return None


def findings_from_alerts(
    repo: RepoFetch, alerts: Iterable[Mapping[str, Any]], now: datetime
) -> list[Finding]:
    """Convert open Dependabot alerts to Findings (layer A). The CVE is the representative id.

    Aliases are the GHSA identifier of a record that has a CVE, and nothing else.
    """
    out: list[Finding] = []
    for alert in alerts:
        advisory, vulnerability = (
            alert["security_advisory"],
            alert["security_vulnerability"],
        )
        cve, ghsa = advisory.get("cve_id"), advisory["ghsa_id"]
        patched = vulnerability.get("first_patched_version") or {}
        package = vulnerability["package"]
        advisory_type = _advisory_type(advisory.get("type"))
        # A malware advisory has no severity, as in the normalized findings of layer B.
        severity = (
            None
            if advisory_type == "malware"
            else normalized.normalize_severity(advisory.get("severity"))
        )
        for component in _purl_for_alert(repo, package["ecosystem"], package["name"]):
            out.append(
                Finding(
                    repo=repo.repo,
                    vuln_id=cve or ghsa,
                    aliases=(ghsa,) if cve else (),
                    component=component,
                    cvss_severity=severity,
                    fixed_version=patched.get("identifier"),
                    advisory_published_at=parse_osv_time(advisory.get("published_at")),
                    layer="A",
                    first_observed_component_at=now,
                    advisory_type=advisory_type,
                    cvss_source=_cvss_source(advisory) if severity else None,
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


def _generation_skipped_paths(
    members: Mapping[str, bytes],
) -> tuple[list[str] | None, str | None]:
    """The ``skipped_paths`` of the artifact's ``generation.json``, or ``None`` and why it was not read.

    An empty list is returned as an empty list: "nothing was excluded" is a statement, a missing key is not.
    ``sbom-generate.yml`` writes ``skipped_paths`` as the list of the lines of its ``skip-paths`` input.
    """
    raw = members.get("generation.json")
    if raw is None:
        return None, "the artifact has no generation.json"
    try:
        doc = json.loads(raw)
    except ValueError as exc:  # includes a UnicodeDecodeError
        return None, f"generation.json is not JSON: {exc}"
    if not isinstance(doc, dict) or "skipped_paths" not in doc:
        return None, "generation.json has no skipped_paths"
    value = doc["skipped_paths"]
    if not isinstance(value, list) or not all(isinstance(p, str) for p in value):
        return None, "skipped_paths is not an array of strings"
    return list(value), None


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
        info = spdx.parse_spdx(sbom)
        if _sbom_unscanned(info):
            result.unscanned = True
            raise ValueError(
                "no package of the export has a purl with a version, so nothing was scanned"
            )
        for component in info.components:
            result.components.setdefault(component.purl, component)
    except (
        HttpError,
        TransportError,
        KeyError,
        ValueError,
        spdx.SbomFormatError,
    ) as exc:
        result.fail("A", f"sbom export: {exc}")
    if result.unscanned:
        return (
            result  # not scanned: neither the alerts nor layer B are read as an answer
        )
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
        sbom_info = spdx.parse_spdx(json.loads(members["sbom.spdx.json"]))
        if _sbom_unscanned(sbom_info):
            result.unscanned = True
            raise ValueError(
                "no package of the artifact SBOM has a purl with a version, so nothing was scanned"
            )
        components = sbom_info.components
        for component in components:
            result.components.setdefault(component.purl, component)
        doc = json.loads(members["findings.normalized.json"])
        parsed = normalized.findings_from_normalized(
            doc, components=components, first_observed_at=now
        )
        if parsed.repo != repo:
            raise ValueError(f"artifact is for {_repo_text(parsed.repo)}")
        result.findings.extend(parsed.findings)
        # Only now is the artifact the one that was scanned; a failure above leaves ``skipped_paths`` unset.
        result.skipped_paths, note = _generation_skipped_paths(members)
        if note is not None:
            result.warnings.append(f"{name}: skipped_paths not recorded: {note}")
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
    kev: dict[str, KevEntry] | None = None
    kev_on: date | None = None
    kev_released: datetime | None = None
    try:
        kev, catalog, kev_released = fetch_kev(client)
        kev_on = now.date()
        fetched.append(run_record.FeedFetched("kev", now, catalog))
    except (HttpError, RateLimited, TransportError, KeyError, ValueError) as exc:
        kev = None
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
        kev_released_at=kev_released,
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


def read_vex_merged_at(
    api: GitHubApi, fetch: RepoFetch, docs: Sequence[models.VexDocument]
) -> tuple[dict[str, datetime], list[str]]:
    """When each ``.vex/`` document last changed, from the head commit this run read.

    One request per document: the newest commit that touched its path (``GitHubApi.last_commit_time``). The key
    is ``doc.path`` (``<owner>/<name>:<path>``), the form ``effective_exclusions`` looks the documents up by.
    A document that has no usable time is left out by itself. A request that GitHub refuses leaves out the times
    of the whole repository, because a time for one document without the others would decide nothing; the run
    goes on, and the reason comes back as a warning. A rate limit is not caught here: it stops the run like any
    other read.

    Returns:
        ``(times, warnings)``; ``times`` is empty when nothing could be read.
    """
    name = _repo_text(fetch.repo)
    times: dict[str, datetime] = {}
    warnings: list[str] = []
    for doc in docs:
        rel = doc.path.partition(":")[2]
        try:
            when = api.last_commit_time(name, rel, fetch.head_sha or "")
        except (HttpError, TransportError, KeyError, ValueError) as exc:
            return {}, [
                f"{name}: vex_merged_at left out for the repository: {exc}"[:300]
            ]
        if when is None:
            warnings.append(f"{name}: vex_merged_at left out for {rel}: no commit time")
            continue
        times[doc.path] = when
    return times, warnings


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
        duplicate_of = state.get("duplicate_of")
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
                duplicate_of=duplicate_of if isinstance(duplicate_of, str) else None,
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


# --- the pilot record: what the maintainer reads to judge the detector ---------------------------------------


class ObservationError(ValueError):
    """The observation input cannot be used."""


@dataclass(frozen=True)
class Observation:
    """The optional input of the observation (``supply-chain-observation.json``, ``schema_version`` 1).

    Attributes:
        observed_repos: The repositories under observation; ``None`` (a missing or empty list) means every
            repository of the Policy_File.
        window_start: Start of a restarted observation (UTC). ``None`` when not given.
        window_end: The time the set is cut at (UTC). ``None`` when not given.
        restarts_done: Restarts already made (0 or more).
        extensions_exhausted: The extensions are used up.
        max_rate_percent: The false-positive rate limit the maintainer decided; ``None`` when none is decided.
        detector_error_issues: Issues a maintainer classified as the detector's own error.
        test_issues: Issues opened to check for a false negative. They are not counted.
        from_file: True when the values came from a file, False for the defaults of "no input".
    """

    observed_repos: frozenset[Repo] | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    restarts_done: int = 0
    extensions_exhausted: bool = False
    max_rate_percent: float | None = None
    detector_error_issues: frozenset[tuple[Repo, int]] = frozenset()
    test_issues: frozenset[tuple[Repo, int]] = frozenset()
    from_file: bool = False


_OBSERVATION_KEYS = frozenset(
    {
        "schema_version",
        "observed_repos",
        "window_start",
        "window_end",
        "restarts_done",
        "extensions_exhausted",
        "max_rate_percent",
        "detector_error_issues",
        "test_issues",
    }
)
_REPO_NAME = re.compile(r"[^/\s#]+/[^/\s#]+")
_ISSUE_REF = re.compile(r"([^/\s#]+/[^/\s#]+)#([1-9][0-9]*)")


def _observation_list(data: Mapping[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ObservationError(f"{key} must be an array of strings")
    return value


def _observation_time(data: Mapping[str, Any], key: str) -> datetime | None:
    value = data.get(key)
    if value is None:
        return None
    when = parse_osv_time(value)
    if when is None:
        raise ObservationError(f"{key} must be an ISO 8601 time with a zone")
    return when


def parse_observation(text: str | None) -> Observation:
    """Read the observation input. ``None`` (no file) is "no input": every default, no window.

    Args:
        text: The text of the file, ``None`` when there is no file. An empty text is a file that could not be
            read, and is refused like any other text that is not an observation.

    Raises:
        ObservationError: The text is not JSON, is not an object, has a key this module does not know (a
            misspelled key is refused, not ignored), or a value has the wrong type.
    """
    if text is None:
        return Observation()
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ObservationError(f"not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ObservationError("the top level must be an object")
    unknown = sorted(set(data) - _OBSERVATION_KEYS)
    if unknown:
        raise ObservationError(f"unknown key: {', '.join(unknown)}")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ObservationError("schema_version must be 1")
    restarts = data.get("restarts_done", 0)
    if type(restarts) is not int or restarts < 0:
        raise ObservationError("restarts_done must be an integer of 0 or more")
    exhausted = data.get("extensions_exhausted", False)
    if not isinstance(exhausted, bool):
        raise ObservationError("extensions_exhausted must be true or false")
    rate = data.get("max_rate_percent")
    if rate is not None and (
        isinstance(rate, bool)
        or not isinstance(rate, int | float)
        or not math.isfinite(rate)
        or rate < 0
    ):
        raise ObservationError("max_rate_percent must be a number of 0 or more")
    observed: list[Repo] = []
    for name in _observation_list(data, "observed_repos"):
        if not _REPO_NAME.fullmatch(name):
            raise ObservationError(f"observed_repos: {name!r} is not owner/name")
        observed.append(_split_repo(name))
    issue_sets: dict[str, frozenset[tuple[Repo, int]]] = {}
    for key in ("detector_error_issues", "test_issues"):
        refs = []
        for text_ref in _observation_list(data, key):
            found = _ISSUE_REF.fullmatch(text_ref)
            if found is None:
                raise ObservationError(f"{key}: {text_ref!r} is not owner/name#number")
            refs.append((_split_repo(found.group(1)), int(found.group(2))))
        issue_sets[key] = frozenset(refs)
    return Observation(
        observed_repos=frozenset(observed) or None,
        window_start=_observation_time(data, "window_start"),
        window_end=_observation_time(data, "window_end"),
        restarts_done=restarts,
        extensions_exhausted=exhausted,
        max_rate_percent=float(rate) if rate is not None else None,
        detector_error_issues=issue_sets["detector_error_issues"],
        test_issues=issue_sets["test_issues"],
        from_file=True,
    )


def observation_path(policy_file: str, override: str | None) -> str:
    """The observation input: ``OBSERVATION_FILE`` when set, else the file beside the Policy_File."""
    return override or str(Path(policy_file).parent / OBSERVATION_FILE_NAME)


def read_observation(path: str | None) -> str | None:
    """The text of the observation input, ``None`` when there is no file, ``""`` when it cannot be read.

    ``""`` is not an observation, so ``parse_observation`` refuses it and the pilot says so; a file that exists
    but cannot be read must not look like "no input".
    """
    if not path:
        return None
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError):
        return ""


@dataclass(frozen=True)
class PilotCandidate:
    """One finding Issue the pilot may count, as the run saw it."""

    repo: Repo
    number: int
    vuln_id: str | None
    opened_at: (
        datetime | None
    )  # ``created_at`` of the Issue; ``None`` when GitHub gave none that can be read
    duplicate: bool  # its state block names a representative (Requirement 8.38)


def pilot_candidates(
    issues: Sequence[ManagedIssue],
    raw: Mapping[tuple[str, int], Mapping[str, Any]],
    actions: Sequence[models.IssueAction],
    results: Mapping[int, int | None],
    now: datetime,
) -> list[PilotCandidate]:
    """The finding Issues of this run: those that were listed, and those this run opened.

    An Issue is a finding Issue of the Aggregator when its marker says so and its title starts with
    ``[supply-chain] `` (the title ``apply_action`` gives). Open and closed Issues count alike. One opened by
    this run counts with ``now`` as its opening time, and is undecided by construction.
    """
    out: list[PilotCandidate] = []
    for issue in sorted(issues, key=lambda i: (_repo_text(i.repo).lower(), i.number)):
        if issue.kind != "finding":
            continue
        item = raw.get((_repo_text(issue.repo).lower(), issue.number), {})
        title = item.get("title")
        if not (isinstance(title, str) and title.startswith(FINDING_TITLE_PREFIX)):
            continue
        named = (issue.body_state or {}).get("duplicate_of")
        out.append(
            PilotCandidate(
                issue.repo,
                issue.number,
                issue.vuln_id,
                parse_osv_time(item.get("created_at")),
                isinstance(named, str) and bool(named),
            )
        )
    for index, action in enumerate(actions):
        number = results.get(index)
        if action.op == "create" and action.kind == "finding" and number is not None:
            out.append(PilotCandidate(action.repo, number, action.vuln_id, now, False))
    return out


def issue_cap_record(
    plan: models.Plan, managed_repos: Collection[Repo]
) -> dict[str, Any]:
    """Which repositories reached the per-run limit of new Issues, and why (Requirements 22.49, 22.50).

    ``cause`` is ``initial_bulk`` when, before this run, the repository had no Issue of the Aggregator at all
    (open or closed, of any kind), and ``ongoing`` otherwise. The rule is a hypothesis: it reads "the first
    run in a repository" from the absence of Issues, and has not been checked against a real first run. A
    repository whose Issues were all deleted by hand would read as ``initial_bulk`` again.

    ``deferred_initial_bulk`` is the sum of ``overflow`` of the ``initial_bulk`` rows: the Findings the next runs
    take up. Nothing here carries them over. The plan holds no memory: a Finding that did not get an Issue is
    a Finding with no Issue in the next run too, and is opened then, up to the limit again (the summary Issue
    lists them meanwhile).
    """
    rows: list[dict[str, Any]] = []
    deferred = 0
    for repo, overflow in sorted(
        plan.overflow_counts.items(), key=lambda kv: _repo_text(kv[0]).lower()
    ):
        if overflow <= 0:
            continue
        cause = "ongoing" if repo in managed_repos else "initial_bulk"
        rows.append({"repo": _repo_text(repo), "overflow": overflow, "cause": cause})
        deferred += overflow if cause == "initial_bulk" else 0
    return {"repos": rows, "deferred_initial_bulk": deferred}


def _optional_time(value: datetime | None) -> str | None:
    return None if value is None else _time_text(value)


def build_pilot(
    observation_text: str | None,
    *,
    policy_repos: Sequence[Repo],
    candidates: Sequence[PilotCandidate],
    plan: models.Plan,
    decisions: Mapping[tuple[str, str, str], tuple[str, str | None]],
    lines: Sequence[metrics.IssueTimeline],
    managed_repos: Collection[Repo],
    now: datetime,
) -> tuple[dict[str, Any], list[str]]:
    """The ``pilot`` of the extra record, and the warnings. Feeds ``metrics``; it counts nothing itself.

    ``metrics.compute_pilot_rates``, ``review_low_sample``, ``observation_restart_status`` and ``sli_counts``
    decide every number; this function chooses which Issues they see. It makes no pass/fail field: the decision
    to start the next batch is the maintainer's, from these counts and a reading of each Issue.

    The status and justification of an Issue come from the statement that excludes its Finding
    (``plan.vex_exclusions``), so an ``affected`` or ``under_investigation`` statement, which excludes nothing,
    is not seen: such an Issue counts as undecided. An Issue whose Finding is no longer reported has no
    exclusion either.

    Args:
        observation_text: The observation input, ``None`` for no file.
        policy_repos: The repositories of the Policy_File (all of them are observed when the input names none).
        candidates: The finding Issues (``pilot_candidates``).
        plan: The plan of this run: ``vex_exclusions``, ``duplicate_of`` and ``overflow_counts``.
        decisions: ``(vex path, vulnerability id, purl)`` -> ``(status, justification)`` of the statements read.
        lines: Timelines of the Issues of the repositories that were read, for the SLI.
        managed_repos: Repositories that had an Issue of the Aggregator before this run.
        now: The run time.

    Returns:
        ``(pilot, warnings)``. ``pilot`` is ``{"error": reason}`` when the input cannot be used or a count
        cannot be made; the reason is also the one warning.
    """
    try:
        observation = parse_observation(observation_text)
    except ObservationError as exc:
        return _pilot_error(f"observation input unusable: {exc}")
    observed = observation.observed_repos or frozenset(policy_repos)
    exclusions: dict[tuple[Repo, str], list[tuple[str, str, str]]] = {}
    for finding, path in plan.vex_exclusions:
        for name in (finding.vuln_id, *finding.aliases):
            exclusions.setdefault((finding.repo, name), []).append(
                (path, finding.vuln_id, finding.component.purl)
            )
    duplicates = {(repo, number) for repo, number, _rep in plan.duplicate_of}
    outcomes: list[metrics.PilotIssueOutcome] = []
    outside = tests = 0
    for cand in candidates:
        key = (cand.repo, cand.number)
        if key in observation.test_issues:
            tests += 1
            continue
        if cand.repo not in observed:
            outside += 1
            continue
        status: str | None = None
        justification: str | None = None
        for path, vuln_id, purl in sorted(
            exclusions.get((cand.repo, cand.vuln_id or ""), [])
        ):
            if (path, vuln_id, purl) in decisions:
                status, justification = decisions[(path, vuln_id, purl)]
                break
        outcomes.append(
            metrics.PilotIssueOutcome(
                vex_status=status,
                justification=justification,
                detector_error=key in observation.detector_error_issues,
                duplicate=cand.duplicate or key in duplicates,
                opened_at=cand.opened_at,
            )
        )
    try:
        rates = metrics.compute_pilot_rates(
            outcomes,
            window_start=observation.window_start,
            window_end=observation.window_end,
        )
        review = metrics.review_low_sample(
            rates,
            max_rate_percent=observation.max_rate_percent,
            extensions_exhausted=observation.extensions_exhausted,
            restarts_done=observation.restarts_done,
        )
        restart = metrics.observation_restart_status(observation.restarts_done)
        sli = metrics.sli_counts(lines, now)
    except ValueError as exc:
        return _pilot_error(f"the counts cannot be made: {exc}")
    pilot: dict[str, Any] = {
        "observation": {
            "input_file": observation.from_file,
            "observed_repos": sorted(_repo_text(r) for r in observed),
            "window_start": _optional_time(observation.window_start),
            "window_end": _optional_time(observation.window_end),
            "restarts_done": observation.restarts_done,
            "extensions_exhausted": observation.extensions_exhausted,
            "max_rate_percent": observation.max_rate_percent,
        },
        # The six counts of Requirement 22.17, under its names.
        "counts": {
            "issued": rates.issued,
            "detector_errors": rates.false_positive,
            "not_affected_other": rates.not_affected_other,
            "fixed": rates.fixed,
            "affected": rates.affected,
            "undecided": rates.undecided,
        },
        "rates": dataclasses.asdict(rates),
        "review": dataclasses.asdict(review),
        "restart": dataclasses.asdict(restart),
        "sli": {"met": sli.met, "denominator": sli.denominator},
        "issue_cap": issue_cap_record(plan, managed_repos),
        "excluded_outside_observation": outside,
        "excluded_test_issues": tests,
    }
    # through JSON once, so that what is returned is what is written (tuples become lists)
    return json.loads(json.dumps(pilot, allow_nan=False)), []


def _pilot_error(reason: str) -> tuple[dict[str, Any], list[str]]:
    return {"error": reason}, [f"pilot record not computed: {reason}"[:300]]


@dataclass(frozen=True)
class ExtraData:
    """What the extra record will carry, decided before the run record is written.

    Attributes:
        skipped_paths: ``owner/name`` -> the ``skipped_paths`` of the layer B artifact that was scanned.
        pilot: The pilot record (``build_pilot``).
        warnings: Lines for the job log; none of them fails the run.
    """

    skipped_paths: dict[str, list[str]]
    pilot: dict[str, Any]
    warnings: tuple[str, ...] = ()


def extra_record_path(record_path: str) -> str:
    """``runs-extra/<YYYY>/<MM>/<run id>.json`` for ``runs/<YYYY>/<MM>/<run id>.json``."""
    return f"{EXTRA_DIR}/{record_path.removeprefix('runs/')}"


def render_extra(
    extra: ExtraData, run_id: str, record_path: str, record_sha256: str
) -> str:
    """The text of the extra record: fixed key order, UTF-8, one newline at the end."""
    body = {
        "schema_version": EXTRA_SCHEMA_VERSION,
        "run_id": run_id,
        "record_path": record_path,
        "record_sha256": record_sha256,
        "skipped_paths": extra.skipped_paths,
        "pilot": extra.pilot,
    }
    return json.dumps(body, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


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


class ChainGuardError(Exception):
    """The month's records cannot take a new record; nothing is written."""


@dataclass(frozen=True)
class ChainGuard:
    """What the checks before a write decided.

    Attributes:
        prev_record_sha256: The SHA-256 the new record names as its predecessor, ``None`` for the first of a month.
        seal: ``(tag name, SHA-256)`` of the month before, to be created after the write; ``None`` when there is
            nothing to seal or the seal is already there.
    """

    prev_record_sha256: str | None
    seal: tuple[str, str] | None


def _record_month(record: run_record.RunRecord) -> str:
    """``YYYY-MM`` of the month the record will be stored under (the month it started in)."""
    return f"{record.started_at.year:04d}-{record.started_at.month:02d}"


def _previous_month(month: str) -> str:
    year, number = int(month[:4]), int(month[5:7])
    return f"{year - 1:04d}-12" if number == 1 else f"{year:04d}-{number - 1:02d}"


def _path_month(path: str) -> str:
    """``YYYY-MM`` of ``runs/<YYYY>/<MM>/<file>``; empty for any other path."""
    parts = path.split("/")
    return f"{parts[1]}-{parts[2]}" if len(parts) == 4 else ""


def month_lock_path(month: str) -> Path:
    """The lock file of one month. Under ``$RUNNER_TEMP``, outside ``.git/`` and outside the records."""
    return (
        Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir())
        / f"supply-chain-aggregator-{month}.lock"
    )


@contextlib.contextmanager
def month_lock(month: str) -> Iterator[None]:
    """Hold the lock of one month while the month's records are read, ``prev_record_sha256`` is decided and the
    record is written.

    ``flock`` guards only processes on one machine, such as two runs a maintainer starts by hand. On GitHub
    Actions nothing is shared between runners, so the only exclusion there is the workflow's ``concurrency``.
    """
    with month_lock_path(month).open("a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def read_chain_ack(path: str | None) -> str | None:
    """The text of the chain ledger, or ``None`` when there is no file (no decision has been made)."""
    if not path:
        return None
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def tag_message(path: str, sha256: str) -> str:
    """The annotation of a tip or seal tag: two lines, ``path`` and ``sha256``."""
    return f"path: {path}\nsha256: {sha256}\n"


def _annotated_sha256(
    hub: GitHubApi, hub_repo: Repo, tag_object_sha: str
) -> str | None:
    """The ``sha256`` line of an annotated tag object, or ``None`` when it has none.

    ``GET /repos/{owner}/{repo}/git/tags/{tag_sha}``. The shape (a ``message`` string) was written from memory of
    the reference, without a network to read it against.
    """
    data = hub.get_json(f"/repos/{_repo_text(hub_repo)}/git/tags/{tag_object_sha}")
    message = data.get("message") if isinstance(data, dict) else None
    found = _SHA256_LINE.search(message) if isinstance(message, str) else None
    return found.group(1) if found else None


def recorded_tip(hub: GitHubApi, hub_repo: Repo, month: str) -> str | None:
    """The SHA-256 the newest tip tag of ``month`` carries, or ``None`` when the month has no tip tag.

    The newest is the one with the highest ``<run id>-<attempt>``, in the order of ``_record_sort_key``. A newest
    tag that is not annotated or has no ``sha256`` line is not skipped for an older one: the check fails.
    ``GET /repos/{owner}/{repo}/git/matching-refs/{ref}`` lists refs by prefix; the shape was written from memory
    of the reference.
    """
    prefix = f"{TIP_TAG_PREFIX}{month}-"
    try:
        refs = list(
            hub.pages(f"/repos/{_repo_text(hub_repo)}/git/matching-refs/tags/{prefix}")
        )
    except HttpError as exc:
        if exc.status != 404:
            raise
        refs = []
    newest: tuple[tuple[str, str, int], str, dict[str, Any]] | None = None
    for ref in refs:
        name = (
            str(ref.get("ref", "")).removeprefix("refs/tags/")
            if isinstance(ref, dict)
            else ""
        )
        found = re.fullmatch(re.escape(prefix) + r"([0-9]+-[0-9]+)", name)
        if found is None:
            continue
        key = _record_sort_key(f"runs/{month.replace('-', '/')}/{found.group(1)}.json")
        if newest is None or key > newest[0]:
            newest = (key, name, ref)
    if newest is None:
        return None
    _key, name, ref = newest
    target = ref.get("object")
    if (
        not isinstance(target, dict)
        or target.get("type") != "tag"
        or not isinstance(target.get("sha"), str)
    ):
        raise ChainGuardError(f"the tag {name} is not an annotated tag")
    sha256 = _annotated_sha256(hub, hub_repo, target["sha"])
    if sha256 is None:
        raise ChainGuardError(f"the tag {name} carries no sha256 line")
    return sha256


def _tag_object(hub: GitHubApi, hub_repo: Repo, name: str) -> dict[str, Any] | None:
    """The ``object`` of ``refs/tags/<name>``, or ``None`` when there is no such tag.

    ``GET /repos/{owner}/{repo}/git/ref/tags/{name}``; the shape was written from memory of the reference.
    """
    resp = hub.get(f"/repos/{_repo_text(hub_repo)}/git/ref/tags/{name}")
    if resp.status == 404:
        return None
    if not resp.ok:
        raise HttpError("GET", f"git/ref/tags/{name}", resp.status, resp.text()[:200])
    target = resp.json().get("object")
    return target if isinstance(target, dict) else {}


def create_annotated_tag(
    hub: GitHubApi, hub_repo: Repo, name: str, commit_sha: str, message: str
) -> None:
    """Create an annotated tag on ``commit_sha``: the tag object first, then the ref that points at it.

    ``POST /repos/{owner}/{repo}/git/tags`` (``tag``, ``message``, ``object``, ``type``) and
    ``POST /repos/{owner}/{repo}/git/refs`` (``ref``, ``sha``). Both bodies were written from memory of the
    reference, without a network to read it against; ``tagger`` is left out.

    Raises:
        HttpError: GitHub refused one of the two requests.
        KeyError: The tag object response has no ``sha``.
    """
    base = f"/repos/{_repo_text(hub_repo)}/git"
    resp = hub.write(
        "POST",
        f"{base}/tags",
        {"tag": name, "message": message, "object": commit_sha, "type": "commit"},
    )
    if resp.status != 201:
        raise HttpError("POST", f"{base}/tags", resp.status, resp.text()[:200])
    resp = hub.write(
        "POST", f"{base}/refs", {"ref": f"refs/tags/{name}", "sha": resp.json()["sha"]}
    )
    if resp.status != 201:
        raise HttpError("POST", f"{base}/refs", resp.status, resp.text()[:200])


def _month_entries(
    hub: GitHubApi, cfg: Config, existing: Sequence[str], month: str
) -> list[tuple[str, str]]:
    """``(path, text)`` of every record stored for ``month``."""
    return [
        (path, hub.read_file(_repo_text(cfg.hub), path, cfg.runs_branch))
        for path in existing
        if _path_month(path) == month
    ]


def _previous_month_seal(
    hub: GitHubApi,
    cfg: Config,
    month: str,
    existing: Sequence[str],
    ledger: Sequence[chain_recovery.AcceptedFork],
    *,
    first_of_month: bool,
) -> tuple[str, str] | None:
    """Check the seal of the month before ``month``, or return the one to create.

    A seal that exists is compared with the month only in the first run of ``month`` (it reads every record of
    the month before). A seal that is missing is looked for in every run, so that a failed creation is tried again.
    """
    previous = _previous_month(month)
    if not any(_path_month(p) == previous for p in existing):
        return None
    name = f"{SEAL_TAG_PREFIX}{previous}"
    target = _tag_object(hub, cfg.hub, name)
    if target is not None and not first_of_month:
        return None
    entries = _month_entries(hub, cfg, existing, previous)
    kept, problems = chain_recovery.effective_entries(
        entries, [f for f in ledger if f.month == previous]
    )
    if problems:
        raise ChainGuardError(
            f"the chain ledger cannot stand for {previous}: " + "; ".join(problems)
        )
    if target is None:
        try:
            seal = run_record.month_seal(previous, kept)
        except run_record.RunRecordError as exc:
            raise ChainGuardError(f"{previous} cannot be sealed: {exc}") from exc
        return seal
    sealed = (
        _annotated_sha256(hub, cfg.hub, target["sha"])
        if target.get("type") == "tag" and "sha" in target
        else None
    )
    if sealed is None:
        raise ChainGuardError(
            f"the seal tag {name} is not an annotated tag with a sha256 line"
        )
    broken = run_record.verify_month_seal(previous, kept, sealed)
    if broken is not None:
        raise ChainGuardError(f"{broken.reason} at {broken.path}")
    return None


def guard_chain(
    hub: GitHubApi,
    cfg: Config,
    month: str,
    record: run_record.RunRecord,
    existing: Sequence[str],
) -> ChainGuard:
    """The checks before the record of ``month`` is written. Raises ``ChainGuardError`` when it must not be.

    In this order: an existing path is refused; the chain ledger is read; the month's records are read through the
    ledger; the SHA-256 the last run wrote is compared with the month; the one tip is found; the month before is
    sealed or its seal checked. Entries of the ledger for other months are not judged here, because only this
    month and the one before are read, and an entry for an older record would read as "no record has this SHA-256".

    Raises:
        ChainGuardError: A check failed.
        HttpError, TransportError, RateLimited: A record or a tag could not be read.
        run_record.RunRecordError: The record's path or run id is refused.
    """
    run_record.new_record_path(record, existing)
    try:
        ledger = chain_recovery.parse_ledger(
            chain_recovery.render_ledger(())
            if cfg.chain_ack_text is None
            else cfg.chain_ack_text
        )
    except chain_recovery.LedgerError as exc:
        raise ChainGuardError(f"the chain ledger cannot be used: {exc}") from exc
    entries = _month_entries(hub, cfg, existing, month)
    accepted = [f for f in ledger if f.month == month]
    kept, problems = chain_recovery.effective_entries(entries, accepted)
    if problems:
        raise ChainGuardError("the chain ledger cannot stand: " + "; ".join(problems))
    broken = run_record.verify_month_tip(
        month,
        entries,
        recorded_tip(hub, cfg.hub, month),
        abandoned=frozenset(f.abandoned_record_sha256 for f in accepted),
    )
    if broken is not None:
        raise ChainGuardError(f"{broken.reason} at {broken.path}")
    try:
        previous = run_record.previous_record_sha256(text for _path, text in kept)
    except run_record.RunRecordError as exc:
        raise ChainGuardError(str(exc)) from exc
    seal = _previous_month_seal(
        hub, cfg, month, existing, ledger, first_of_month=not entries
    )
    return ChainGuard(previous, seal)


def save_record_commit(
    hub: GitHubApi,
    hub_repo: Repo,
    branch: str,
    record: run_record.RunRecord,
    existing: Sequence[str],
) -> tuple[str, str | None]:
    """Create the record file with a PUT that carries no ``sha``: an existing path is refused, never overwritten.

    Returns the path and the SHA of the commit that holds it (``commit.sha`` of the contents API response, from
    memory of the reference), or ``None`` for the commit when the response does not carry one.
    """
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
    commit = (resp.json().get("commit") or {}).get("sha")
    return path, commit if isinstance(commit, str) else None


def save_record(
    hub: GitHubApi,
    hub_repo: Repo,
    branch: str,
    record: run_record.RunRecord,
    existing: Sequence[str],
) -> str:
    """``save_record_commit`` without the commit: the path of the new file."""
    return save_record_commit(hub, hub_repo, branch, record, existing)[0]


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
    # The text of the chain ledger. ``None`` is an empty ledger (no decision has been made); a text that cannot be
    # read as a ledger stops the write.
    chain_ack_text: str | None = None
    # The text of the observation input. ``None`` is "no input" (every default, no window); a text that cannot be
    # read as one makes the pilot record ``{"error": ...}`` and nothing else.
    observation_text: str | None = None


@dataclass
class Outcome:
    record: run_record.RunRecord
    exit_code: int
    saved_path: str | None
    messages: list[str]
    # SHA-256 of the record that was written, and the annotated tag that keeps it; ``None`` when the record was
    # not saved, or the tag could not be created.
    tip_sha256: str | None = None
    tip_tag: str | None = None
    # What the extra record carries (``None`` when the run ended before there was anything to say), and where
    # it was saved (``None`` when it was not).
    extra: ExtraData | None = None
    extra_path: str | None = None


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
    fetch_ok_repos = [
        f for f in listed if (f.layer_ok["A"] or f.layer_ok["B"]) and not f.unscanned
    ]
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
    vex_merged: dict[Repo, dict[str, datetime]] = {}
    warnings: list[str] = []
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
        if not docs:
            continue  # no document, no time to ask for
        try:
            merged, notes = read_vex_merged_at(spoke, fetch, docs)
        except RateLimited as exc:
            rate_limited = True
            reasons.append(f"rate limit stopped the run: {exc}")
            break
        warnings.extend(notes)
        if merged:
            vex_merged[fetch.repo] = merged

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
            vex_merged_at=vex_merged or None,
        )
    )

    entries: list[run_record.IssueEntry] = []
    results: dict[int, int | None] = {}
    # The duplicates' ``duplicate_of`` bodies are written after the plan's own actions.
    actions = [
        *plan.actions,
        *duplicate_updates(plan, issues, raw, cfg.run_id, now),
    ]
    for index, action in enumerate(actions):
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

    lines = timelines(issues, raw, actions, results, now)
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
            lines,
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
    pilot, pilot_notes = build_pilot(
        cfg.observation_text,
        policy_repos=policy.target_repositories,
        candidates=pilot_candidates(issues, raw, actions, results, now),
        plan=plan,
        decisions=_vex_decisions(vex_docs),
        lines=[t for t in lines if t.repo in fetch_ok],
        managed_repos=frozenset(i.repo for i in issues),
        now=now,
    )
    extra = ExtraData(
        skipped_paths={
            _repo_text(f.repo): list(f.skipped_paths)
            for f in sorted(fetch_ok_repos, key=lambda f: _repo_text(f.repo).lower())
            if f.skipped_paths is not None
        },
        pilot=pilot,
        warnings=(
            *(w for f in fetch_ok_repos for w in f.warnings),
            *warnings,
            *pilot_notes,
        ),
    )
    return _finish(cfg, record, reasons, spoke, hub, now_fn, labels_done, extra)


def _vex_decisions(
    docs: Mapping[Repo, Sequence[models.VexDocument]],
) -> dict[tuple[str, str, str], tuple[str, str | None]]:
    """``(document path, vulnerability id, product purl)`` -> ``(status, justification)`` of the statements read.

    The first statement in the order of document path and statement position that names the key. It is not
    always the statement that decided an exclusion (the newest does); the same limit as ``_vex_statuses``.
    """
    table: dict[tuple[str, str, str], tuple[str, str | None]] = {}
    for repo_docs in docs.values():
        for doc in sorted(repo_docs, key=lambda d: d.path):
            for statement in doc.statements:
                for vuln_id in (statement.vuln_id, *statement.aliases):
                    for product in statement.products:
                        table.setdefault(
                            (doc.path, vuln_id, product),
                            (statement.status, statement.justification),
                        )
    return table


def _vex_statuses(
    docs: Mapping[Repo, Sequence[models.VexDocument]],
) -> dict[tuple[str, str, str], str]:
    return {key: value[0] for key, value in _vex_decisions(docs).items()}


def _finish(
    cfg: Config,
    record: run_record.RunRecord,
    reasons: Sequence[str],
    spoke: GitHubApi,
    hub: GitHubApi,
    now_fn: Callable[[], datetime],
    labels_done: set[str],
    extra: ExtraData | None = None,
) -> Outcome:
    """Decide and send the failure notice, then save the record. The notice comes first so that a
    notice that could not be sent is written into the record: the record is never rewritten.

    The month's lock is held from the listing of the records to the end of the write, so that two runs of one
    month do not read the same tip. The extra record is written under the same lock, after the run record.
    """
    with month_lock(_record_month(record)):
        outcome = _finish_locked(cfg, record, reasons, spoke, hub, now_fn, labels_done)
        return _save_extra(hub, cfg, outcome, extra)


def _save_extra(
    hub: GitHubApi, cfg: Config, outcome: Outcome, extra: ExtraData | None
) -> Outcome:
    """Attach ``extra`` to the outcome and, when the run record was saved, create the extra record beside it.

    The file is created with a PUT that carries no ``sha``, so an existing path is refused and never
    overwritten. Whatever goes wrong here is a warning in ``outcome.messages``: the run record, its tags and the
    exit code are already settled and are not touched.
    """
    if extra is None:
        return outcome
    outcome.extra = extra
    outcome.messages.extend(extra.warnings)
    if outcome.saved_path is None or outcome.tip_sha256 is None:
        return outcome  # no run record, so nothing for the extra record to name
    path = extra_record_path(outcome.saved_path)
    try:
        text = render_extra(
            extra, outcome.record.run_id, outcome.saved_path, outcome.tip_sha256
        )
        resp = hub.write(
            "PUT",
            f"/repos/{_repo_text(cfg.hub)}/contents/{path}",
            {
                "message": f"chore: record supply-chain run extras {outcome.record.run_id}",
                "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
                "branch": cfg.runs_branch,
            },
        )
        if resp.status != 201:
            raise HttpError("PUT", f"contents/{path}", resp.status, resp.text()[:200])
    except (HttpError, RateLimited, TransportError, ValueError) as exc:
        outcome.messages.append(f"run extra record not saved: {exc}"[:300])
        return outcome
    outcome.extra_path = path
    return outcome


def _finish_locked(
    cfg: Config,
    record: run_record.RunRecord,
    reasons: Sequence[str],
    spoke: GitHubApi,
    hub: GitHubApi,
    now_fn: Callable[[], datetime],
    labels_done: set[str],
) -> Outcome:
    month = _record_month(record)
    messages = list(reasons)
    notice_error: str | None = None
    try:
        existing_paths = list_run_paths(hub, cfg.hub, cfg.runs_branch)
    except (HttpError, RateLimited, TransportError, ValueError, KeyError) as exc:
        # The runs branch is never created here, and without it neither the streak nor the save
        # is possible. The run is abnormal; the watchdog sees the missing record.
        messages.append(f"run record not saved: runs branch not readable: {exc}"[:300])
        return Outcome(record, 1, None, messages)
    guard: ChainGuard | None = None
    try:
        guard = guard_chain(hub, cfg, month, record, existing_paths)
    except (
        ChainGuardError,
        HttpError,
        RateLimited,
        TransportError,
        ValueError,
        KeyError,
    ) as exc:
        # A run that cannot be chained is a failed run, and counts as one in the streak, although its record
        # is not stored.
        messages.append(f"run record not saved: {exc}"[:300])
        record = _with(
            record, end_state="failure", failure_reason="; ".join(messages)[:1000]
        )
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
    if guard is None:
        return Outcome(record, 1, None, messages)
    record = _with(record, prev_record_sha256=guard.prev_record_sha256)
    try:
        saved, commit_sha = save_record_commit(
            hub, cfg.hub, cfg.runs_branch, record, existing_paths
        )
    except (HttpError, RateLimited, TransportError, run_record.RunRecordError) as exc:
        messages.append(f"run record not saved: {exc}"[:300])
        return Outcome(record, 1, None, messages)
    sha256 = run_record.sha256_text(run_record.to_json(record))
    tip_name = f"{TIP_TAG_PREFIX}{month}-{record.run_id}"
    pending = [("tip", tip_name, tag_message(saved, sha256))]
    if guard.seal is not None:
        sealed_dir = f"runs/{_previous_month(month).replace('-', '/')}"
        pending.append(("seal", guard.seal[0], tag_message(sealed_dir, guard.seal[1])))
    # A tag that cannot be made does not undo the record: the next run then has no recorded value to compare.
    made: set[str] = set()
    for label, name, message in pending:
        try:
            if commit_sha is None:
                raise ValueError("the write response carries no commit SHA")
            create_annotated_tag(hub, cfg.hub, name, commit_sha, message)
            made.add(name)
        except (HttpError, RateLimited, TransportError, KeyError, ValueError) as exc:
            messages.append(f"{label} tag {name} not created: {exc}"[:300])
    return Outcome(
        record,
        1 if record.end_state == "failure" else 0,
        saved,
        messages,
        tip_sha256=sha256,
        tip_tag=tip_name if tip_name in made else None,
    )


def _with(record: run_record.RunRecord, **changes: Any) -> run_record.RunRecord:
    return dataclasses.replace(record, **changes)


# --- command line -----------------------------------------------------------------------------------------


def _env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"error: environment variable {name} is not set")
    return value


def render_summary(outcome: Outcome) -> str:
    """The text of the job summary of one run."""
    record = outcome.record
    lines = [
        f"## Supply-chain Aggregator run {record.run_id}",
        f"- end state: {record.end_state}",
        f"- started: {_time_text(record.started_at)}, finished: {_time_text(record.finished_at)}",
        f"- repositories scanned: {len(record.repositories.scanned)}, fetch failures: {len(record.repositories.fetch_failed)}",
        f"- Issue operations: {len(record.issues)}, not applied: {sum(1 for i in record.issues if not i.ok)}",
        f"- run record: {outcome.saved_path or 'not saved'}",
        f"- run record SHA-256: {outcome.tip_sha256 or 'none'}"
        + (f" (tag {outcome.tip_tag})" if outcome.tip_tag else ""),
        *_extra_summary_lines(outcome),
        *(f"- {m}" for m in outcome.messages),
    ]
    return "\n".join(lines) + "\n"


def _extra_summary_lines(outcome: Outcome) -> list[str]:
    """Three lines about the extra record: where it is, how many repositories carry ``skipped_paths``, and
    how many Issues the pilot counted. No body of it goes into the summary."""
    extra = outcome.extra
    if extra is None:
        return []
    issued = (extra.pilot.get("rates") or {}).get("issued")
    return [
        f"- run extra record: {outcome.extra_path or 'not saved'}",
        f"- repositories with skipped_paths recorded: {len(extra.skipped_paths)}",
        f"- pilot issued: {issued if issued is not None else 'not computed'}",
    ]


def _write_summary(outcome: Outcome) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(render_summary(outcome))


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
    try:
        chain_ack_text = read_chain_ack(os.environ.get("CHAIN_ACK_FILE"))
    except OSError as exc:
        # An unreadable ledger is not an empty one: "" cannot be read as a ledger, so the write is refused.
        chain_ack_text = ""
        print(f"error: chain ledger not readable: {exc}", file=sys.stderr)
    cfg = Config(
        hub=_split_repo(_env("GITHUB_REPOSITORY")),
        run_id=f"{_env('GITHUB_RUN_ID')}-{_env('GITHUB_RUN_ATTEMPT')}",
        aggregator_commit=sha,
        policy_text=policy_text,
        policy_commit=policy_ref,
        chain_ack_text=chain_ack_text,
        observation_text=read_observation(
            observation_path(_env("POLICY_FILE"), os.environ.get("OBSERVATION_FILE"))
        ),
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
