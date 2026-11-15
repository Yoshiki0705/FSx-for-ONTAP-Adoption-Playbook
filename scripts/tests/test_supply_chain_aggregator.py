"""The Aggregator's I/O layer, run against a fake HTTP layer. No test reaches the network.

What is tested here is the order of the steps and what happens at the seams: the core decides, so
these tests do not re-test its rules. They pin the behaviours the design asks of the I/O layer:

* nothing is touched when the Policy_File cannot be read;
* one repository failing does not stop the others;
* a failed feed never closes an Issue (and a working feed does: the control);
* a run record is created, never overwritten;
* a Retry-After is honoured, and a wait longer than the run will serve stops the run;
* a body never exceeds 50,000 characters;
* every write carries one of the two tokens, the runs branch only the Hub token, and a redirect
  target (artifact storage) never receives a token;
* the watchdog appends to the open failure Issue instead of opening a second one;
* the record chain is guarded: the chain ledger is checked, the last written record is compared with the
  tag the previous run left, a finished month is sealed, and a month is read and written under one lock.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import multiprocessing
import os
import re
import sys
import tempfile
import time
import unittest
import urllib.parse
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import supply_chain_aggregator as aggregator
from supply_chain import issue_body, models, run_record
from supply_chain.models import Repo
from supply_chain_aggregator import (
    Config,
    RepoFetch,
    _mal_findings,
    apply_action,
    fetch_feeds,
    findings_from_alerts,
    list_managed_issues,
    notify_failure,
    run,
)
from supply_chain_io import (
    Client,
    GitHubApi,
    HttpError,
    Osv,
    RateLimited,
    Response,
    TransportError,
)

SPOKE_TOKEN = "spoke-token-value"
HUB_TOKEN = "hub-token-value"
NOTIFY_TOKEN = "notify-token-value"
HUB = Repo("example-org", "hub-repo")
TARGET = "example-org/example-repo"
OTHER = "example-org/other-repo"
NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
NOW_FEB = datetime(2026, 2, 3, 3, 4, 5, tzinfo=UTC)
SHA = "a" * 40
POLICY_SHA = "b" * 40
COMMIT = "c" * 40
RUN_ID = "1000-1"

DEFAULT_EXCLUDED = [
    "aws-samples/baseline-environment-on-aws",
    "aws-samples/baseline-environment-on-aws-for-financial-services-institute",
    "Yoshiki0705/baseline-environment-on-aws",
    "Yoshiki0705/baseline-environment-on-aws-for-financial-services-institute",
]


def policy_text(targets: list[str], limit: int = 10) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "target_repositories": targets,
            "excluded_repositories": DEFAULT_EXCLUDED,
            "opening_threshold": {
                "min_cvss_severity": "HIGH",
                "open_if_kev_listed": True,
                "open_if_malicious": True,
                "epss_used_for_opening": False,
            },
            "cooldown_days": {"default": 3, "major": 7},
            "package_manager_wait": {"default_days": 3},
            "dependency_scope": {"non_production_paths": ["test/", "tests/"]},
            "automerge": {
                "enabled_repositories": [],
                "include": [
                    {
                        "manager": "npm",
                        "dep_types": ["devDependencies"],
                        "update_types": ["patch"],
                    },
                    {"manager": "github-actions", "update_types": ["patch"]},
                ],
                "exclude": [
                    "vulnerability_fix",
                    "runtime_dependencies",
                    "minor",
                    "major",
                    "digest_only",
                    "unknown_dep_type",
                    "hub_reusable_workflow",
                ],
            },
            "vex": {
                "directory": ".vex",
                "exclude_statuses": ["not_affected", "fixed"],
                "approver_role": "VEX_Reviewer",
                "one_statement_per_document": True,
                "malicious_never_suppressed": True,
            },
            "response_target": {
                "detect_hours": 24,
                "fix_days_kev_or_malicious": 7,
                "fix_days_high": 30,
            },
            "issue_limits": {"max_new_issues_per_repo_per_run": limit},
        }
    )


@dataclass
class Call:
    method: str
    url: str
    token: str | None
    body: Any


class FakeNet:
    """A route table that records every request. The first matching route answers."""

    def __init__(self) -> None:
        self.calls: list[Call] = []
        self._routes: list[tuple[str, re.Pattern[str], Any]] = []
        # The annotated tags of the Hub: tag object SHA -> message, and tag name -> tag object SHA.
        self.tag_objects: dict[str, str] = {}
        self.tag_refs: dict[str, str] = {}

    def on(self, method: str, pattern: str, answer: Any) -> None:
        """Routes added later win, so a test can override the defaults."""
        self._routes.insert(0, (method, re.compile(pattern), answer))

    def request(
        self, method: str, url: str, headers: Any, body: bytes | None
    ) -> Response:
        auth = headers.get("Authorization")
        token = auth.removeprefix("Bearer ") if auth else None
        payload = json.loads(body) if body else None
        self.calls.append(Call(method, url, token, payload))
        for route_method, pattern, answer in self._routes:
            if route_method == method and pattern.search(url):
                return answer(url, payload) if callable(answer) else answer
        raise AssertionError(f"unrouted request: {method} {url}")

    def writes(self) -> list[Call]:
        return [
            c
            for c in self.calls
            if c.method != "GET" and not c.url.endswith("/v1/querybatch")
        ]

    def to(self, method: str, fragment: str) -> list[Call]:
        return [c for c in self.calls if c.method == method and fragment in c.url]


def ok(data: Any, status: int = 200, headers: dict[str, str] | None = None) -> Response:
    return Response(status, headers or {}, json.dumps(data).encode("utf-8"))


def spdx_doc(purls: list[tuple[str, str, str]]) -> dict[str, Any]:
    packages = [{"SPDXID": "SPDXRef-root", "name": "root", "versionInfo": SHA}]
    rels = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-root",
        }
    ]
    for i, (name, version, purl) in enumerate(purls):
        packages.append(
            {
                "SPDXID": f"SPDXRef-p{i}",
                "name": name,
                "versionInfo": version,
                "externalRefs": [
                    {
                        "referenceType": "purl",
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceLocator": purl,
                    }
                ],
            }
        )
        rels.append(
            {
                "spdxElementId": "SPDXRef-root",
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": f"SPDXRef-p{i}",
            }
        )
    return {
        "spdxVersion": "SPDX-2.3",
        "SPDXID": "SPDXRef-DOCUMENT",
        "dataLicense": "CC0-1.0",
        "name": "example",
        "documentNamespace": "https://example.test/spdx/example",
        "documentDescribes": ["SPDXRef-root"],
        "creationInfo": {
            "created": "2026-01-01T00:00:00Z",
            "creators": ["Tool: example-1.0"],
        },
        "packages": packages,
        "relationships": rels,
    }


def alert(
    cve: str | None = "CVE-2021-0001",
    severity: str = "high",
    name: str = "lodash",
    **advisory_extra: Any,
) -> dict[str, Any]:
    return {
        "number": 1,
        "state": "open",
        "security_advisory": {
            "ghsa_id": "GHSA-aaaa-bbbb-cccc",
            "cve_id": cve,
            "severity": severity,
            "published_at": "2025-12-01T00:00:00Z",
            **advisory_extra,
        },
        "security_vulnerability": {
            "package": {"ecosystem": "npm", "name": name},
            "severity": severity,
            "vulnerable_version_range": "< 4.17.21",
            "first_patched_version": {"identifier": "4.17.21"},
        },
    }


def kev_feed(ids: list[str] = ()) -> dict[str, Any]:
    return {
        "catalogVersion": "2026.01.01",
        "vulnerabilities": [
            {
                "cveID": i,
                "dateAdded": "2026-01-01",
                "knownRansomwareCampaignUse": "Unknown",
            }
            for i in ids
        ],
    }


def epss_file() -> Response:
    text = "#model_version:v2026.01.01,score_date:2026-01-02T12:00:00Z\ncve,epss,percentile\nCVE-2021-0001,0.5,0.9\n"
    return Response(200, {}, gzip.compress(text.encode("utf-8")))


def tree(paths: list[str], truncated: bool = False) -> Response:
    return ok(
        {"truncated": truncated, "tree": [{"path": p, "type": "blob"} for p in paths]}
    )


def file_response(text: str) -> Response:
    return ok(
        {
            "type": "file",
            "encoding": "base64",
            "content": base64.b64encode(text.encode()).decode(),
        }
    )


def finding_issue_body(
    vuln_id: str,
    *,
    kev: bool,
    repo: str = TARGET,
    severity: str | None = None,
    due_at: datetime = NOW,
    opened_at: datetime = NOW,
) -> str:
    owner, name = repo.split("/")
    return issue_body.render_finding(
        issue_body.FindingIssue(
            repo=Repo(owner, name),
            vuln_id=vuln_id,
            aliases=(),
            components=(
                models.Component("pkg:npm/lodash@4.17.20", "lodash", "4.17.20"),
            ),
            cvss_severity=severity,  # type: ignore[arg-type]
            kev=(date(2026, 1, 1), None) if kev else None,
            epss=None,
            fixed_version=None,
            origin_at=NOW,
            origin_is_date_only=False,
            detected_at=NOW,
            opened_at=opened_at,
            due_at=due_at,
            last_run_id="999-1",
            history=(issue_body.HistoryEntry("open", "999-1", NOW),),
        )
    )


def issue_item(
    number: int,
    body: str,
    state: str = "open",
    labels: tuple[str, ...] = ("supply-chain-aggregator",),
    *,
    title: str | None = None,
    created_at: str | None = None,
    closed_at: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "number": number,
        "state": state,
        "body": body,
        "labels": [{"name": name} for name in labels],
    }
    if title is not None:
        item["title"] = title
    if created_at is not None:
        item["created_at"] = created_at
    if closed_at is not None:
        item["closed_at"] = closed_at
    return item


def world(
    targets: list[str] | None = None, *, runs: list[str] | None = None
) -> FakeNet:
    """A network in which every call a healthy run makes is answered. Tests override single routes."""
    net = FakeNet()
    repos = targets or [TARGET]
    hub = f"{HUB.owner}/{HUB.name}"
    net.on("GET", r"/repos/[^/]+/[^/]+$", lambda url, _: ok({"default_branch": "main"}))
    net.on("GET", r"/branches/main$", ok({"commit": {"sha": SHA}}))
    net.on(
        "GET",
        r"/dependency-graph/sbom$",
        ok({"sbom": spdx_doc([("lodash", "4.17.20", "pkg:npm/lodash@4.17.20")])}),
    )
    net.on("GET", r"/dependabot/alerts", ok([]))
    net.on("GET", r"/actions/artifacts", ok({"artifacts": []}))
    net.on("GET", r"/contents/\.vex", ok({"message": "Not Found"}, 404))
    net.on(
        "GET", r"/protection/required_status_checks$", ok({"message": "Not Found"}, 404)
    )
    net.on("GET", r"/rules/branches/main", ok([]))
    net.on("GET", r"/repos/[^/]+/[^/]+/issues\?", ok([]))
    net.on("GET", r"/search/issues", ok({"items": []}))
    net.on("GET", r"/labels/", ok({"message": "Not Found"}, 404))
    net.on("POST", r"/labels$", ok({"name": "supply-chain-aggregator"}, 201))
    counter = {"n": 100}

    def create(url: str, payload: dict[str, Any]) -> Response:
        counter["n"] += 1
        return ok(
            {
                "number": counter["n"],
                "labels": [{"name": label} for label in payload["labels"]],
            },
            201,
        )

    net.on("POST", r"/repos/[^/]+/[^/]+/issues$", create)
    net.on("PATCH", r"/issues/\d+$", ok({"number": 1}))
    net.on("POST", r"/issues/\d+/comments$", ok({"id": 1}, 201))
    net.on("GET", r"cisa\.gov", ok(kev_feed()))
    net.on("GET", r"epss\.empiricalsecurity\.com", epss_file())
    net.on(
        "POST",
        r"/v1/querybatch",
        lambda url, payload: ok({"results": [{} for _ in payload["queries"]]}),
    )
    net.on("GET", r"api\.osv\.dev/v1/vulns/", ok({"message": "not found"}, 404))
    net.on("GET", rf"/repos/{hub}/git/trees/", tree(runs or []))
    net.on("PUT", rf"/repos/{hub}/contents/runs/", put_ok())
    net.on("PUT", rf"/repos/{hub}/contents/runs-extra/", put_ok())
    install_tags(net, hub)
    net.on("GET", rf"/repos/{hub}/issues\?", ok([]))
    for repo in repos:
        net.on("GET", rf"/repos/{repo}/issues\?", ok([]))
    return net


def put_ok() -> Response:
    """The answer to creating a file: the contents API returns the commit that holds it."""
    return ok({"content": {}, "commit": {"sha": COMMIT}}, 201)


def install_tags(net: FakeNet, hub: str) -> None:
    """Routes for annotated tags in the Hub, backed by ``net.tag_objects`` and ``net.tag_refs``."""

    def create_tag(url: str, payload: dict[str, Any]) -> Response:
        sha = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:40]
        net.tag_objects[sha] = payload["message"]
        return ok({"sha": sha, "tag": payload["tag"]}, 201)

    def create_ref(url: str, payload: dict[str, Any]) -> Response:
        net.tag_refs[payload["ref"].removeprefix("refs/tags/")] = payload["sha"]
        return ok({"ref": payload["ref"]}, 201)

    def matching(url: str, _: Any) -> Response:
        prefix = url.split("/git/matching-refs/tags/", 1)[1].split("?", 1)[0]
        return ok(
            [
                {
                    "ref": f"refs/tags/{name}",
                    "object": {"sha": sha, "type": "tag"},
                }
                for name, sha in sorted(net.tag_refs.items())
                if name.startswith(prefix)
            ]
        )

    def one_ref(url: str, _: Any) -> Response:
        name = url.split("/git/ref/tags/", 1)[1].split("?", 1)[0]
        if name not in net.tag_refs:
            return ok({"message": "Not Found"}, 404)
        return ok(
            {
                "ref": f"refs/tags/{name}",
                "object": {"sha": net.tag_refs[name], "type": "tag"},
            }
        )

    def tag_object(url: str, _: Any) -> Response:
        sha = url.rsplit("/", 1)[1].split("?", 1)[0]
        return ok({"sha": sha, "message": net.tag_objects[sha]})

    net.on("POST", rf"/repos/{hub}/git/tags$", create_tag)
    net.on("POST", rf"/repos/{hub}/git/refs$", create_ref)
    net.on("GET", rf"/repos/{hub}/git/matching-refs/tags/", matching)
    net.on("GET", rf"/repos/{hub}/git/ref/tags/", one_ref)
    net.on("GET", rf"/repos/{hub}/git/tags/[0-9a-f]+", tag_object)


def execute(
    net: FakeNet,
    policy: str,
    *,
    sleeps: list[float] | None = None,
    run_id: str = RUN_ID,
    ledger: str | None = None,
    now: datetime = NOW,
    observation: str | None = None,
) -> Any:
    log = sleeps if sleeps is not None else []
    client = Client(net, sleep=log.append, clock=lambda: 0.0)
    extra: dict[str, Any] = {} if ledger is None else {"chain_ack_text": ledger}
    if observation is not None:
        extra["observation_text"] = observation
    cfg = Config(HUB, run_id, SHA, policy, POLICY_SHA, **extra)
    return run(
        cfg,
        spoke=GitHubApi(client, SPOKE_TOKEN),
        hub=GitHubApi(client, HUB_TOKEN),
        client=client,
        osv=Osv(client),
        now_fn=lambda: now,
    )


class PolicyUnreadable(unittest.TestCase):
    def test_no_target_is_read_and_no_finding_issue_is_touched(self) -> None:
        net = world()
        outcome = execute(net, "{ not json")
        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(outcome.record.end_state, "failure")
        self.assertIsNone(outcome.record.policy_commit)
        self.assertIn("Policy_File", outcome.record.failure_reason or "")
        self.assertEqual(
            [c for c in net.calls if TARGET in c.url],
            [],
            "a target repository was read",
        )
        issue_writes = [c for c in net.writes() if "/issues" in c.url]
        self.assertEqual(
            issue_writes,
            [],
            "an Issue was written although the Policy_File was unreadable",
        )

    def test_the_failed_run_is_still_recorded_so_the_streak_can_be_counted(
        self,
    ) -> None:
        net = world()
        outcome = execute(net, "")
        puts = net.to("PUT", "/contents/runs/")
        self.assertEqual(len(puts), 1)
        self.assertEqual(puts[0].token, HUB_TOKEN)
        self.assertEqual(outcome.saved_path, "runs/2026/01/1000-1.json")

    def test_a_second_consecutive_failure_opens_the_failure_issue(self) -> None:
        previous = run_record.to_json(
            run_record.RunRecord(
                RUN_ID.replace("1000", "999"),
                NOW,
                NOW,
                "failure",
                "earlier",
                SHA,
                None,
                run_record.Repositories((), (), {}),
                run_record.Feeds((), ()),
                None,
                run_record.EpssInfo(None, None),
                (),
                (),
                (),
                (),
                (),
                (),
                {},
                {},
                (),
                run_record.RateLimitRecord((), ()),
                None,
            )
        )
        net = world(runs=["runs/2026/01/999-1.json"])
        net.on("GET", r"/contents/runs/2026/01/999-1\.json", file_response(previous))
        execute(net, "")
        created = net.to("POST", f"/repos/{HUB.owner}/{HUB.name}/issues")
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].token, SPOKE_TOKEN)


class OneRepositoryFailing(unittest.TestCase):
    def test_the_others_continue_and_the_failure_is_recorded(self) -> None:
        net = world([TARGET, OTHER])
        net.on("GET", rf"/repos/{TARGET}$", ok({"message": "boom"}, 500))
        net.on("GET", rf"/repos/{OTHER}/dependabot/alerts", ok([alert()]))
        outcome = execute(net, policy_text([TARGET, OTHER]))
        self.assertEqual(outcome.record.repositories.scanned, (OTHER,))
        failed = {f.repo for f in outcome.record.repositories.fetch_failed}
        self.assertIn(TARGET, failed)
        created = net.to("POST", f"/repos/{OTHER}/issues")
        self.assertEqual(len(created), 1, "the healthy repository was not processed")
        self.assertEqual(net.to("POST", f"/repos/{TARGET}/issues"), [])

    def test_a_repository_whose_issues_cannot_be_listed_is_not_planned(self) -> None:
        net = world()
        net.on("GET", rf"/repos/{TARGET}/issues\?", ok({"message": "nope"}, 403))
        net.on("GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert()]))
        execute(net, policy_text([TARGET]))
        self.assertEqual(
            net.to("POST", f"/repos/{TARGET}/issues"),
            [],
            "planned without knowing the existing Issues",
        )


class NetworkTrouble(unittest.TestCase):
    def test_a_dropped_connection_on_one_repository_does_not_stop_the_others(
        self,
    ) -> None:
        net = world([TARGET, OTHER])

        def dropped(url: str, payload: Any) -> Response:
            raise TransportError("connection reset")

        net.on("GET", rf"/repos/{TARGET}$", dropped)
        net.on("GET", rf"/repos/{OTHER}/dependabot/alerts", ok([alert()]))
        outcome = execute(net, policy_text([TARGET, OTHER]))
        self.assertEqual(outcome.record.repositories.scanned, (OTHER,))
        self.assertIn(
            TARGET, {f.repo for f in outcome.record.repositories.fetch_failed}
        )
        self.assertEqual(len(net.to("POST", f"/repos/{OTHER}/issues")), 1)

    def test_a_rate_limit_during_the_pull_request_search_ends_the_run_cleanly(
        self,
    ) -> None:
        body = finding_issue_body("CVE-2021-0001", kev=True, severity="HIGH")
        net = world()
        net.on("GET", rf"/repos/{TARGET}/issues\?", ok([issue_item(7, body)]))
        net.on(
            "GET",
            r"/search/issues",
            ok({"message": "limited"}, 429, {"retry-after": "9999"}),
        )
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.record.end_state, "failure")
        self.assertIn("rate limit", outcome.record.failure_reason or "")
        self.assertEqual(
            [c for c in net.writes() if "/issues" in c.url and c.method != "PUT"],
            [],
            "an Issue was written after the rate limit stopped the run",
        )


class FeedFailureNeverCloses(unittest.TestCase):
    def kev_only_issue(self) -> Any:
        body = finding_issue_body("CVE-2021-0001", kev=True, severity="LOW")
        return ok([issue_item(7, body)])

    def test_control_a_working_feed_with_no_finding_closes_the_issue(self) -> None:
        net = world()
        net.on("GET", rf"/repos/{TARGET}/issues\?", self.kev_only_issue())
        execute(net, policy_text([TARGET]))
        closes = [
            c
            for c in net.to("PATCH", "/issues/7")
            if (c.body or {}).get("state") == "closed"
        ]
        self.assertEqual(
            len(closes),
            1,
            "the control did not close: the next test would prove nothing",
        )
        self.assertEqual(closes[0].token, SPOKE_TOKEN)

    def test_a_failed_kev_feed_leaves_a_kev_only_issue_open(self) -> None:
        net = world()
        net.on("GET", rf"/repos/{TARGET}/issues\?", self.kev_only_issue())
        net.on("GET", r"cisa\.gov", ok({"message": "down"}, 503))
        outcome = execute(net, policy_text([TARGET]))
        closes = [
            c
            for c in net.to("PATCH", "/issues/7")
            if (c.body or {}).get("state") == "closed"
        ]
        self.assertEqual(closes, [])
        self.assertIn("kev", [f.name for f in outcome.record.feeds.failed])

    def test_a_failed_malicious_feed_does_not_close_a_mal_issue(self) -> None:
        body = finding_issue_body("MAL-2026-1", kev=False)
        net = world()
        net.on("GET", rf"/repos/{TARGET}/issues\?", ok([issue_item(8, body)]))
        net.on("POST", r"/v1/querybatch", ok({"message": "down"}, 500))
        outcome = execute(net, policy_text([TARGET]))
        closes = [
            c
            for c in net.to("PATCH", "/issues/8")
            if (c.body or {}).get("state") == "closed"
        ]
        self.assertEqual(closes, [])
        self.assertIn("malicious", [f.name for f in outcome.record.feeds.failed])

    def test_a_mal_id_that_left_the_feed_closes_only_when_the_record_says_withdrawn(
        self,
    ) -> None:
        body = finding_issue_body("MAL-2026-2", kev=False)
        for record, expect_close in (
            ({"id": "MAL-2026-2", "withdrawn": "2026-01-01T00:00:00Z"}, True),
            ({"id": "MAL-2026-2", "withdrawn": "garbage"}, False),
        ):
            with self.subTest(record=record):
                net = world()
                net.on("GET", rf"/repos/{TARGET}/issues\?", ok([issue_item(9, body)]))
                net.on("GET", r"api\.osv\.dev/v1/vulns/MAL-2026-2", ok(record))
                execute(net, policy_text([TARGET]))
                closes = [
                    c
                    for c in net.to("PATCH", "/issues/9")
                    if (c.body or {}).get("state") == "closed"
                ]
                self.assertEqual(bool(closes), expect_close)


class RunRecordStorage(unittest.TestCase):
    def test_a_new_record_is_created_without_a_sha_and_with_the_hub_token(self) -> None:
        net = world()
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        puts = net.to("PUT", "/contents/runs/")
        self.assertEqual(len(puts), 1)
        self.assertNotIn("sha", puts[0].body)
        self.assertEqual(puts[0].body["branch"], "supply-chain-runs")
        self.assertEqual(puts[0].token, HUB_TOKEN)
        saved = run_record.from_json(base64.b64decode(puts[0].body["content"]).decode())
        self.assertEqual(saved.run_id, RUN_ID)
        self.assertEqual(saved.policy_commit, POLICY_SHA)

    def test_a_record_names_the_one_before_it_in_the_same_month(self) -> None:
        first_net = world()
        execute(first_net, policy_text([TARGET]))
        first_put = first_net.to("PUT", "/contents/runs/")[0]
        first_text = base64.b64decode(first_put.body["content"]).decode()
        self.assertIsNone(run_record.from_json(first_text).prev_record_sha256)

        net = world(runs=["runs/2026/01/1000-1.json"])
        net.on("GET", r"/contents/runs/2026/01/1000-1\.json", file_response(first_text))
        outcome = execute(net, policy_text([TARGET]), run_id="1001-1")
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        second = run_record.from_json(
            base64.b64decode(
                net.to("PUT", "/contents/runs/")[0].body["content"]
            ).decode()
        )
        self.assertEqual(second.prev_record_sha256, run_record.sha256_text(first_text))

    def test_an_existing_path_is_never_overwritten(self) -> None:
        net = world(runs=["runs/2026/01/1000-1.json"])
        net.on(
            "GET",
            r"/contents/runs/2026/01/1000-1\.json",
            ok({"message": "unreadable"}, 500),
        )
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(
            net.to("PUT", "/contents/runs/"), [], "an existing record was written to"
        )
        self.assertEqual(outcome.exit_code, 1)
        self.assertIsNone(outcome.saved_path)

    def test_the_same_run_id_under_another_month_is_refused_too(self) -> None:
        net = world(runs=["runs/2025/12/1000-1.json"])
        net.on(
            "GET",
            r"/contents/runs/2025/12/1000-1\.json",
            ok({"message": "unreadable"}, 500),
        )
        execute(net, policy_text([TARGET]))
        self.assertEqual(net.to("PUT", "/contents/runs/"), [])

    def test_a_missing_runs_branch_is_not_created(self) -> None:
        net = world()
        net.on("GET", r"/git/trees/", ok({"message": "Not Found"}, 404))
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(
            [c for c in net.writes() if "/git/" in c.url or "/refs" in c.url], []
        )
        self.assertEqual(net.to("PUT", "/contents/runs/"), [])


class RetryAfter(unittest.TestCase):
    def client(self, responses: list[Response]) -> tuple[Client, list[float], FakeNet]:
        net = FakeNet()
        queue = list(responses)
        net.on("GET", r"example\.test", lambda url, _: queue.pop(0))
        sleeps: list[float] = []
        return Client(net, sleep=sleeps.append, clock=lambda: 1000.0), sleeps, net

    def test_retry_after_longer_than_the_backoff_is_honoured(self) -> None:
        client, sleeps, _ = self.client(
            [Response(429, {"retry-after": "7"}, b""), Response(200, {}, b"{}")]
        )
        self.assertEqual(client.send("GET", "https://example.test/a").status, 200)
        self.assertEqual(sleeps, [7.0])

    def test_the_backoff_is_used_when_it_is_longer(self) -> None:
        client, sleeps, _ = self.client(
            [
                Response(429, {"retry-after": "1"}, b""),
                Response(429, {"retry-after": "1"}, b""),
                Response(200, {}, b""),
            ]
        )
        client.send("GET", "https://example.test/a")
        self.assertEqual(sleeps, [2.0, 4.0])

    def test_a_primary_rate_limit_reset_is_read_when_there_is_no_retry_after(
        self,
    ) -> None:
        reset = {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1030"}
        client, sleeps, _ = self.client(
            [Response(403, reset, b""), Response(200, {}, b"")]
        )
        client.send("GET", "https://example.test/a")
        self.assertEqual(sleeps, [30.0])

    def test_a_wait_longer_than_the_run_will_serve_stops_without_sleeping(self) -> None:
        client, sleeps, _ = self.client([Response(429, {"retry-after": "3600"}, b"")])
        with self.assertRaises(RateLimited):
            client.send("GET", "https://example.test/a")
        self.assertEqual(sleeps, [])

    def test_the_sixth_retry_is_not_made(self) -> None:
        client, sleeps, net = self.client([Response(429, {}, b"")] * 6)
        with self.assertRaises(RateLimited):
            client.send("GET", "https://example.test/a")
        self.assertEqual(sleeps, [2.0, 4.0, 8.0, 16.0, 32.0])
        self.assertEqual(len(net.calls), 6)

    def test_a_server_error_is_not_retried_for_a_post(self) -> None:
        net = FakeNet()
        net.on("POST", r"example\.test", Response(502, {}, b""))
        client = Client(net, sleep=lambda _: None)
        self.assertEqual(client.send("POST", "https://example.test/a").status, 502)
        self.assertEqual(len(net.calls), 1)

    def test_a_rate_limit_during_the_run_stops_it_and_records_what_was_left(
        self,
    ) -> None:
        net = world([TARGET, OTHER])
        net.on("GET", rf"/repos/{OTHER}$", Response(429, {"retry-after": "3600"}, b""))
        outcome = execute(net, policy_text([TARGET, OTHER]))
        self.assertEqual(outcome.record.rate_limit.processed, (TARGET,))
        self.assertEqual(outcome.record.rate_limit.unprocessed, (OTHER,))
        self.assertEqual(outcome.record.end_state, "failure")


class BodyLength(unittest.TestCase):
    def test_a_body_with_hundreds_of_components_stays_within_the_limit(self) -> None:
        purls = [("lodash", f"1.0.{n}", f"pkg:npm/lodash@1.0.{n}") for n in range(600)]
        net = world()
        net.on("GET", r"/dependency-graph/sbom$", ok({"sbom": spdx_doc(purls)}))
        net.on("GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert()]))
        execute(net, policy_text([TARGET]))
        created = net.to("POST", f"/repos/{TARGET}/issues")
        self.assertEqual(len(created), 1)
        self.assertLessEqual(len(created[0].body["body"]), 50_000)
        self.assertIn(
            "omitted", created[0].body["body"].lower().replace("省略", "omitted")
        )


class TokensAndRedirects(unittest.TestCase):
    def test_every_write_carries_one_of_the_two_tokens_and_the_runs_branch_only_the_hub_token(
        self,
    ) -> None:
        net = world()
        net.on("GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert()]))
        execute(net, policy_text([TARGET]))
        writes = net.writes()
        self.assertTrue(writes, "the run wrote nothing, so this test checked nothing")
        for call in writes:
            self.assertIn(
                call.token, (SPOKE_TOKEN, HUB_TOKEN), f"{call.method} {call.url}"
            )
        for call in writes:
            if (
                "/contents/runs/" in call.url
                or "/contents/runs-extra/" in call.url
                or "/git/tags" in call.url
                or "/git/refs" in call.url
            ):
                self.assertEqual(call.token, HUB_TOKEN, f"{call.method} {call.url}")
            else:
                self.assertEqual(call.token, SPOKE_TOKEN, f"{call.method} {call.url}")
        for call in net.calls:
            self.assertIn(
                call.token,
                (SPOKE_TOKEN, HUB_TOKEN, None),
                f"unknown token on {call.url}",
            )

    def test_the_hub_token_is_never_used_for_an_issue(self) -> None:
        net = world()
        net.on("GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert()]))
        execute(net, policy_text([TARGET]))
        for call in net.calls:
            if call.token == HUB_TOKEN:
                self.assertTrue(
                    "/contents/runs/" in call.url
                    or "/git/trees/" in call.url
                    or "/git/" in call.url
                    or "/contents/" in call.url
                )
                self.assertNotIn("/issues", call.url)

    def test_the_artifact_redirect_target_gets_no_token(self) -> None:
        sbom = spdx_doc([("lodash", "4.17.20", "pkg:npm/lodash@4.17.20")])
        findings = {
            "schema_version": 1,
            "repo": TARGET,
            "commit": SHA,
            "layer": "B",
            "generated_at": "2026-01-01T00:00:00Z",
            "tool": {"name": "trivy", "version": "1.2.3"},
            "findings": [],
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("sbom.spdx.json", json.dumps(sbom))
            archive.writestr("findings.normalized.json", json.dumps(findings))
        net = world()
        net.on(
            "GET",
            r"/actions/artifacts\?",
            ok(
                {
                    "artifacts": [
                        {
                            "name": f"sbom-{SHA}",
                            "expired": False,
                            "archive_download_url": f"https://api.github.com/repos/{TARGET}/actions/artifacts/5/zip",
                            "workflow_run": {"head_branch": "main"},
                        }
                    ]
                }
            ),
        )
        net.on(
            "GET",
            r"/artifacts/5/zip$",
            Response(
                302, {"location": "https://storage.example.test/blob?sig=secret"}, b""
            ),
        )
        net.on("GET", r"storage\.example\.test", Response(200, {}, buffer.getvalue()))
        outcome = execute(net, policy_text([TARGET]))
        blob = [c for c in net.calls if "storage.example.test" in c.url]
        self.assertEqual(len(blob), 1)
        self.assertIsNone(blob[0].token, "the storage host received the GitHub token")
        first = [c for c in net.calls if c.url.endswith("/artifacts/5/zip")]
        self.assertEqual(first[0].token, SPOKE_TOKEN)
        self.assertEqual(outcome.record.repositories.fetch_failed, ())


class WatchdogNotice(unittest.TestCase):
    def hub_issues(self, items: list[dict[str, Any]]) -> FakeNet:
        net = FakeNet()
        net.on("GET", r"/issues\?", ok(items))
        net.on(
            "POST",
            r"/issues$",
            ok({"number": 5, "labels": [{"name": "supply-chain-aggregator"}]}, 201),
        )
        net.on("POST", r"/comments$", ok({"id": 1}, 201))
        net.on("GET", r"/labels/", ok({"message": "Not Found"}, 404))
        net.on("POST", r"/labels$", ok({"name": "x"}, 201))
        return net

    def test_it_opens_one_issue_when_none_is_open(self) -> None:
        net = self.hub_issues([])
        api = GitHubApi(Client(net, sleep=lambda _: None), NOTIFY_TOKEN)
        self.assertEqual(
            notify_failure(api, HUB, "2000-1", ["no run record in 12 hours"], NOW),
            "create",
        )
        self.assertEqual(len(net.to("POST", "/issues")), 1)
        self.assertTrue(all(c.token == NOTIFY_TOKEN for c in net.calls))

    def test_it_appends_to_the_open_issue_and_does_not_open_a_second(self) -> None:
        body = issue_body.render_failure(HUB, "1999-1", NOW, ["earlier"])
        net = self.hub_issues([issue_item(3, body)])
        api = GitHubApi(Client(net, sleep=lambda _: None), NOTIFY_TOKEN)
        self.assertEqual(
            notify_failure(api, HUB, "2000-1", ["no run record in 12 hours"], NOW),
            "append",
        )
        self.assertEqual(net.to("POST", "/issues/3/comments")[0].token, NOTIFY_TOKEN)
        self.assertEqual(
            [c for c in net.to("POST", "/issues") if c.url.endswith("/issues")], []
        )

    def test_repeating_the_notice_twice_still_leaves_one_issue(self) -> None:
        state: list[dict[str, Any]] = []
        net = self.hub_issues([])

        def create(url: str, payload: dict[str, Any]) -> Response:
            state.append(issue_item(5, payload["body"]))
            return ok(
                {"number": 5, "labels": [{"name": "supply-chain-aggregator"}]}, 201
            )

        net.on("POST", r"/issues$", create)
        net.on("GET", r"/issues\?", lambda url, _: ok(state))
        api = GitHubApi(Client(net, sleep=lambda _: None), NOTIFY_TOKEN)
        first = notify_failure(api, HUB, "2000-1", ["stale"], NOW)
        second = notify_failure(api, HUB, "2001-1", ["stale"], NOW)
        self.assertEqual((first, second), ("create", "append"))
        self.assertEqual(
            len(
                [
                    c
                    for c in net.calls
                    if c.method == "POST" and c.url.endswith("/issues")
                ]
            ),
            1,
        )


REPO = Repo("example-org", "example-repo")
OVERDUE = models.OVERDUE_LABEL
IDENT_LABEL = "supply-chain-aggregator"


def iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def created_body(net: FakeNet, repo: str = TARGET) -> str:
    posts = [
        c for c in net.to("POST", f"/repos/{repo}/issues") if c.url.endswith("/issues")
    ]
    return posts[0].body["body"]


def issue_api(net: FakeNet) -> GitHubApi:
    return GitHubApi(Client(net, sleep=lambda _: None), SPOKE_TOKEN)


def closes(net: FakeNet, number: int) -> list[Call]:
    return [
        c
        for c in net.to("PATCH", f"/issues/{number}")
        if (c.body or {}).get("state") == "closed"
    ]


class IssueLabels(unittest.TestCase):
    def test_listing_reads_the_labels_of_every_issue(self) -> None:
        body = finding_issue_body("CVE-2021-0001", kev=True, severity="LOW")
        net = world()
        net.on(
            "GET",
            rf"/repos/{TARGET}/issues\?",
            ok(
                [
                    issue_item(7, body, labels=(IDENT_LABEL, OVERDUE)),
                    issue_item(8, body, labels=(IDENT_LABEL,)),
                ]
            ),
        )
        issues, _ = list_managed_issues(issue_api(net), REPO)
        self.assertEqual(
            [i.labels for i in issues],
            [frozenset({IDENT_LABEL, OVERDUE}), frozenset({IDENT_LABEL})],
        )

    def test_a_label_only_update_writes_no_body_and_adds_the_label(self) -> None:
        action = models.IssueAction(
            "update",
            REPO,
            "finding",
            "CVE-2021-0001",
            7,
            None,
            None,
            add_labels=(OVERDUE,),
        )
        net = world()
        self.assertEqual(apply_action(issue_api(net), action, set()), 7)
        self.assertEqual(
            net.to("PATCH", "/issues/7"),
            [],
            "a body was written for a label-only update",
        )
        adds = [c for c in net.to("POST", "/issues/7/labels")]
        self.assertEqual([c.body for c in adds], [{"labels": [OVERDUE]}])
        self.assertEqual(adds[0].token, SPOKE_TOKEN)
        made = [
            c for c in net.to("POST", "/labels") if c.url.endswith(f"{TARGET}/labels")
        ]
        self.assertEqual([c.body["name"] for c in made], [OVERDUE])

    def test_an_existing_overdue_label_is_not_created_again(self) -> None:
        action = models.IssueAction(
            "update",
            REPO,
            "finding",
            "CVE-2021-0001",
            7,
            None,
            None,
            add_labels=(OVERDUE,),
        )
        net = world()
        net.on("GET", rf"/labels/{OVERDUE}$", ok({"name": OVERDUE}))
        apply_action(issue_api(net), action, set())
        self.assertEqual(
            [
                c
                for c in net.to("POST", "/labels")
                if c.url.endswith(f"{TARGET}/labels")
            ],
            [],
        )
        self.assertEqual(len(net.to("POST", "/issues/7/labels")), 1)

    def test_removing_a_label_that_is_already_gone_succeeds(self) -> None:
        action = models.IssueAction(
            "update",
            REPO,
            "finding",
            "CVE-2021-0001",
            7,
            None,
            None,
            remove_labels=(OVERDUE,),
        )
        for status in (200, 404):
            with self.subTest(status=status):
                net = world()
                net.on("DELETE", r"/issues/7/labels/", ok({"message": "x"}, status))
                self.assertEqual(apply_action(issue_api(net), action, set()), 7)
                deletes = net.to("DELETE", "/issues/7/labels/")
                self.assertEqual(len(deletes), 1)
                self.assertTrue(deletes[0].url.endswith(f"/issues/7/labels/{OVERDUE}"))
                self.assertEqual(deletes[0].token, SPOKE_TOKEN)
                self.assertEqual(net.to("PATCH", "/issues/7"), [])

    def test_any_other_failure_to_remove_a_label_is_an_error(self) -> None:
        action = models.IssueAction(
            "update",
            REPO,
            "finding",
            "CVE-2021-0001",
            7,
            None,
            None,
            remove_labels=(OVERDUE,),
        )
        net = world()
        net.on("DELETE", r"/issues/7/labels/", ok({"message": "no"}, 403))
        with self.assertRaises(HttpError):
            apply_action(issue_api(net), action, set())

    def test_a_refused_label_add_is_an_error(self) -> None:
        action = models.IssueAction(
            "update",
            REPO,
            "finding",
            "CVE-2021-0001",
            7,
            None,
            None,
            add_labels=(OVERDUE,),
        )
        net = world()
        net.on("POST", r"/issues/7/labels$", ok({"message": "no"}, 403))
        with self.assertRaises(HttpError):
            apply_action(issue_api(net), action, set())

    def test_create_and_reopen_carry_the_added_label(self) -> None:
        body = finding_issue_body("CVE-2021-0001", kev=True, severity="LOW")
        net = world()
        created = models.IssueAction(
            "create",
            REPO,
            "finding",
            "CVE-2021-0001",
            None,
            body,
            None,
            add_labels=(OVERDUE,),
        )
        apply_action(issue_api(net), created, set())
        post = [
            c
            for c in net.to("POST", f"/repos/{TARGET}/issues")
            if c.url.endswith("/issues")
        ]
        self.assertEqual(post[0].body["labels"], [IDENT_LABEL, OVERDUE])
        reopened = models.IssueAction(
            "reopen",
            REPO,
            "finding",
            "CVE-2021-0001",
            7,
            body,
            None,
            add_labels=(OVERDUE,),
        )
        apply_action(issue_api(net), reopened, set())
        patch = net.to("PATCH", "/issues/7")
        self.assertEqual(patch[0].body["state"], "open")
        self.assertEqual(
            [c.body for c in net.to("POST", "/issues/7/labels")],
            [{"labels": [OVERDUE]}],
        )

    def test_the_label_follows_the_due_time_in_a_run(self) -> None:
        first = world()
        first.on("GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert()]))
        execute(first, policy_text([TARGET]))
        body = created_body(first)
        due = iso(NOW + timedelta(days=30))
        self.assertIn(f'"due_at": "{due}"', body)
        late = body.replace(due, iso(NOW - timedelta(days=1)))

        def run_with(text: str, labels: tuple[str, ...]) -> FakeNet:
            net = world()
            net.on("GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert()]))
            net.on(
                "GET",
                rf"/repos/{TARGET}/issues\?",
                ok([issue_item(7, text, labels=labels)]),
            )
            net.on("DELETE", r"/issues/7/labels/", ok([{"name": IDENT_LABEL}]))
            execute(net, policy_text([TARGET]))
            return net

        past = run_with(late, (IDENT_LABEL,))
        self.assertEqual(past.to("PATCH", "/issues/7"), [], "the body was rewritten")
        self.assertEqual(
            [c.body for c in past.to("POST", "/issues/7/labels")],
            [{"labels": [OVERDUE]}],
        )
        self.assertEqual(past.to("DELETE", "/issues/7/labels/"), [])

        settled = run_with(late, (IDENT_LABEL, OVERDUE))
        self.assertEqual(settled.to("POST", "/issues/7/labels"), [])
        self.assertEqual(settled.to("DELETE", "/issues/7/labels/"), [])
        self.assertEqual(settled.to("PATCH", "/issues/7"), [])

        current = run_with(body, (IDENT_LABEL, OVERDUE))
        removed = current.to("DELETE", "/issues/7/labels/")
        self.assertEqual(len(removed), 1)
        self.assertEqual(current.to("POST", "/issues/7/labels"), [])
        self.assertEqual(current.to("PATCH", "/issues/7"), [])


class DuplicateIssues(unittest.TestCase):
    """A duplicate (an Issue under an alias of another Issue's vulnerability) stays open and says so."""

    def pair(self, dup_due: datetime = NOW, dup_text: str | None = None) -> FakeNet:
        keep = finding_issue_body("CVE-2021-0001", kev=False, severity="HIGH")
        dup = dup_text or finding_issue_body(
            "GHSA-aaaa-bbbb-cccc", kev=False, severity="HIGH", due_at=dup_due
        )
        net = world()
        net.on("GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert()]))
        net.on(
            "GET",
            rf"/repos/{TARGET}/issues\?",
            ok([issue_item(7, keep), issue_item(8, dup)]),
        )
        return net

    def test_the_duplicate_is_rewritten_with_duplicate_of_and_stays_open(self) -> None:
        net = self.pair()
        execute(net, policy_text([TARGET]))
        self.assertEqual(closes(net, 8), [], "the duplicate was closed")
        patches = net.to("PATCH", "/issues/8")
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0].token, SPOKE_TOKEN)
        self.assertNotIn("state", patches[0].body)
        text = patches[0].body["body"]
        state = issue_body.parse_state(text) or {}
        self.assertEqual(state["duplicate_of"], "CVE-2021-0001")
        self.assertEqual(state["vuln_id"], "GHSA-aaaa-bbbb-cccc")
        self.assertEqual(state["due_at"], iso(NOW))
        self.assertEqual(state["opened_at"], iso(NOW))
        marker = issue_body.parse_marker(text)
        self.assertEqual(marker.vuln_id if marker else None, "GHSA-aaaa-bbbb-cccc")
        self.assertIn("重複の代表", text)
        self.assertEqual(state["history"][-1]["run_id"], RUN_ID)

    def test_a_second_run_does_not_write_the_duplicate_again(self) -> None:
        first = self.pair()
        execute(first, policy_text([TARGET]))
        text = first.to("PATCH", "/issues/8")[0].body["body"]
        second = self.pair(dup_text=text)
        execute(second, policy_text([TARGET]))
        self.assertEqual(second.to("PATCH", "/issues/8"), [])
        self.assertEqual(closes(second, 8), [])

    def test_an_overdue_duplicate_is_not_counted_as_overdue(self) -> None:
        net = self.pair(dup_due=NOW - timedelta(days=1))
        outcome = execute(net, policy_text([TARGET]))
        metrics_row = outcome.record.response_metrics[TARGET]
        self.assertEqual(metrics_row.overdue_open, 0)


def purl_less(doc: dict[str, Any]) -> dict[str, Any]:
    for package in doc["packages"]:
        package.pop("externalRefs", None)
    return doc


def declared_empty() -> dict[str, Any]:
    doc = spdx_doc([])
    doc["relationships"].append(
        {
            "spdxElementId": "SPDXRef-root",
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": "NONE",
        }
    )
    return doc


def artifact(
    net: FakeNet, sbom: dict[str, Any], extra_members: dict[str, str] | None = None
) -> None:
    findings = {
        "schema_version": 1,
        "repo": TARGET,
        "commit": SHA,
        "layer": "B",
        "generated_at": "2026-01-01T00:00:00Z",
        "tool": {"name": "trivy", "version": "1.2.3"},
        "findings": [],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("sbom.spdx.json", json.dumps(sbom))
        archive.writestr("findings.normalized.json", json.dumps(findings))
        for member, text in (extra_members or {}).items():
            archive.writestr(member, text)
    net.on(
        "GET",
        r"/actions/artifacts\?",
        ok(
            {
                "artifacts": [
                    {
                        "name": f"sbom-{SHA}",
                        "expired": False,
                        "archive_download_url": f"https://api.github.com/repos/{TARGET}/actions/artifacts/5/zip",
                        "workflow_run": {"head_branch": "main"},
                    }
                ]
            }
        ),
    )
    net.on("GET", r"/artifacts/5/zip$", Response(200, {}, buffer.getvalue()))


class UnscannedSbom(unittest.TestCase):
    """An SBOM with no component and incomplete coverage was not scanned; it is no ground to close an Issue."""

    def net(self) -> FakeNet:
        body = finding_issue_body("CVE-2021-0001", kev=True, severity="LOW")
        net = world()
        net.on("GET", rf"/repos/{TARGET}/issues\?", ok([issue_item(7, body)]))
        return net

    def test_control_a_scanned_sbom_with_no_finding_closes_the_issue(self) -> None:
        net = self.net()
        execute(net, policy_text([TARGET]))
        self.assertEqual(len(closes(net, 7)), 1, "the control did not close")

    def test_control_an_sbom_that_declares_itself_empty_still_closes(self) -> None:
        net = self.net()
        net.on("GET", r"/dependency-graph/sbom$", ok({"sbom": declared_empty()}))
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(len(closes(net, 7)), 1)
        self.assertEqual(outcome.record.repositories.scanned, (TARGET,))

    def test_an_export_with_no_package_that_has_a_purl_closes_nothing(self) -> None:
        net = self.net()
        sbom = purl_less(spdx_doc([("lodash", "4.17.20", "pkg:npm/lodash@4.17.20")]))
        net.on("GET", r"/dependency-graph/sbom$", ok({"sbom": sbom}))
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(closes(net, 7), [])
        self.assertEqual(outcome.record.repositories.scanned, ())
        failed = {(f.repo, f.layer) for f in outcome.record.repositories.fetch_failed}
        self.assertIn((TARGET, "A"), failed)
        self.assertEqual(outcome.record.end_state, "failure")

    def test_the_artifact_sbom_is_judged_the_same_way(self) -> None:
        control = self.net()
        artifact(control, spdx_doc([("lodash", "4.17.20", "pkg:npm/lodash@4.17.20")]))
        execute(control, policy_text([TARGET]))
        self.assertEqual(len(closes(control, 7)), 1, "the control did not close")

        net = self.net()
        artifact(
            net, purl_less(spdx_doc([("lodash", "4.17.20", "pkg:npm/lodash@4.17.20")]))
        )
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(closes(net, 7), [])
        self.assertEqual(outcome.record.repositories.scanned, ())
        failed = {(f.repo, f.layer) for f in outcome.record.repositories.fetch_failed}
        self.assertIn((TARGET, "B"), failed)

    def test_one_unscanned_repository_does_not_stop_the_other(self) -> None:
        net = world([TARGET, OTHER])
        net.on(
            "GET",
            rf"/repos/{TARGET}/dependency-graph/sbom$",
            ok(
                {
                    "sbom": purl_less(
                        spdx_doc([("lodash", "4.17.20", "pkg:npm/lodash@4.17.20")])
                    )
                }
            ),
        )
        net.on("GET", rf"/repos/{OTHER}/dependabot/alerts", ok([alert()]))
        outcome = execute(net, policy_text([TARGET, OTHER]))
        self.assertEqual(outcome.record.repositories.scanned, (OTHER,))
        self.assertEqual(len(net.to("POST", f"/repos/{OTHER}/issues")), 1)


class AdvisoryFields(unittest.TestCase):
    def read(self, **advisory_extra: Any) -> models.Finding:
        found = findings_from_alerts(RepoFetch(REPO), [alert(**advisory_extra)], NOW)
        self.assertEqual(len(found), 1)
        return found[0]

    def test_a_malware_type_is_read_and_carries_no_severity(self) -> None:
        finding = self.read(type="malware")
        self.assertEqual(finding.advisory_type, "malware")
        self.assertIsNone(finding.cvss_severity)
        self.assertIsNone(finding.cvss_source)

    def test_the_other_documented_types_are_a_vulnerability(self) -> None:
        for kind in ("reviewed", "unreviewed"):
            with self.subTest(kind=kind):
                finding = self.read(type=kind)
                self.assertEqual(finding.advisory_type, "vulnerability")
                self.assertEqual(finding.cvss_severity, "HIGH")

    def test_a_missing_or_unknown_type_is_none(self) -> None:
        self.assertIsNone(self.read().advisory_type)
        self.assertIsNone(self.read(type="something-new").advisory_type)
        self.assertIsNone(self.read(type=5).advisory_type)

    def test_the_source_of_the_severity_follows_the_scores_that_are_present(
        self,
    ) -> None:
        v3 = {
            "vector_string": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "score": 9.8,
        }
        v4 = {
            "vector_string": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N",
            "score": 9.3,
        }
        empty = {"vector_string": None, "score": 0.0}
        cases = (
            ({"cvss_v3": v3, "cvss_v4": empty}, "GHSA:CVSS_V3"),
            ({"cvss_v3": v3, "cvss_v4": v4}, "GHSA:CVSS_V4"),
            ({"cvss_v3": empty, "cvss_v4": v4}, "GHSA:CVSS_V4"),
            ({"cvss_v3": empty, "cvss_v4": empty}, None),
            ({}, None),
        )
        for severities, expected in cases:
            with self.subTest(severities=severities):
                self.assertEqual(
                    self.read(cvss_severities=severities).cvss_source, expected
                )
        self.assertIsNone(self.read().cvss_source)
        self.assertIsNone(self.read(cvss_severities="garbage").cvss_source)

    def test_there_is_no_source_without_a_severity(self) -> None:
        for severity in (None, "", "unknown"):
            with self.subTest(severity=severity):
                found = findings_from_alerts(
                    RepoFetch(REPO),
                    [
                        alert(
                            severity=severity,  # type: ignore[arg-type]
                            cvss_severities={
                                "cvss_v3": {"vector_string": "x", "score": 7.0}
                            },
                        )
                    ],
                    NOW,
                )
                self.assertIsNone(found[0].cvss_severity)
                self.assertIsNone(found[0].cvss_source)

    def test_a_malware_alert_opens_an_issue_as_a_malicious_package(self) -> None:
        net = world()
        net.on(
            "GET",
            rf"/repos/{TARGET}/dependabot/alerts",
            ok([alert(cve=None, severity="low", type="malware")]),
        )
        execute(net, policy_text([TARGET]))
        state = issue_body.parse_state(created_body(net)) or {}
        self.assertIs(state["malicious"], True)
        self.assertEqual(state["due_at"], iso(NOW + timedelta(days=7)))

    def test_the_severity_source_is_written_to_the_issue_state(self) -> None:
        net = world()
        net.on(
            "GET",
            rf"/repos/{TARGET}/dependabot/alerts",
            ok(
                [
                    alert(
                        cvss_severities={
                            "cvss_v4": {"vector_string": "v", "score": 8.7}
                        }
                    )
                ]
            ),
        )
        execute(net, policy_text([TARGET]))
        state = issue_body.parse_state(created_body(net)) or {}
        self.assertEqual(state["cvss_sources"], ["GHSA:CVSS_V4"])


class Aliases(unittest.TestCase):
    """Aliases come from OSV ``aliases`` and from GitHub's ``ghsa_id`` and ``cve_id``, and from nothing else."""

    def finding_for(self, record: dict[str, Any]) -> models.Finding:
        component = models.Component("pkg:npm/evil@1.0.0", "evil", "1.0.0")
        fetch = RepoFetch(REPO, components={component.purl: component})
        fetch.layer_ok["A"] = True
        found = _mal_findings(
            [fetch], {component.purl: ["MAL-2026-1"]}, {"MAL-2026-1": record}, NOW
        )
        self.assertEqual(len(found), 1)
        return found[0]

    def test_osv_related_and_upstream_are_not_aliases(self) -> None:
        finding = self.finding_for(
            {
                "id": "MAL-2026-1",
                "aliases": [],
                "related": ["CVE-2099-0001"],
                "upstream": ["CVE-2099-0002"],
                "published": "2026-01-01T00:00:00Z",
            }
        )
        self.assertEqual(finding.aliases, ())

    def test_osv_aliases_are_read_without_the_id_itself(self) -> None:
        finding = self.finding_for(
            {
                "id": "MAL-2026-1",
                "aliases": ["GHSA-aaaa-bbbb-cccc", "MAL-2026-1"],
                "related": ["CVE-2099-0001"],
            }
        )
        self.assertEqual(finding.aliases, ("GHSA-aaaa-bbbb-cccc",))

    def test_an_alert_names_its_ghsa_as_the_alias_of_its_cve_and_nothing_more(
        self,
    ) -> None:
        extra = {
            "identifiers": [
                {"type": "GHSA", "value": "GHSA-aaaa-bbbb-cccc"},
                {"type": "CVE", "value": "CVE-2021-0001"},
            ],
            "references": [{"url": "https://example.test/CVE-2099-0001"}],
        }
        with_cve = findings_from_alerts(RepoFetch(REPO), [alert(**extra)], NOW)[0]
        self.assertEqual(
            (with_cve.vuln_id, with_cve.aliases),
            ("CVE-2021-0001", ("GHSA-aaaa-bbbb-cccc",)),
        )
        without = findings_from_alerts(RepoFetch(REPO), [alert(cve=None)], NOW)[0]
        self.assertEqual(
            (without.vuln_id, without.aliases), ("GHSA-aaaa-bbbb-cccc", ())
        )


class KevItems(unittest.TestCase):
    CATALOGUE: ClassVar[dict[str, Any]] = {
        "catalogVersion": "2026.01.02",
        "dateReleased": "2026-01-02T01:02:03.456Z",
        "vulnerabilities": [
            {
                "cveID": "CVE-2021-0001",
                "dateAdded": "2026-01-01",
                "dueDate": "2026-01-22",
                "forensicTriage": "Yes",
                "knownRansomwareCampaignUse": "Known",
            }
        ],
    }

    def test_a_listed_issue_shows_the_due_date_and_the_forensic_triage(self) -> None:
        net = world()
        net.on("GET", r"cisa\.gov", ok(self.CATALOGUE))
        net.on(
            "GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert(severity="low")])
        )
        execute(net, policy_text([TARGET]))
        text = created_body(net)
        state = issue_body.parse_state(text) or {}
        self.assertEqual(
            state["kev"],
            {
                "date_added": "2026-01-01",
                "known_ransomware_campaign_use": True,
                "due_date": "2026-01-22",
                "forensic_triage": True,
            },
        )
        self.assertIn("2026-01-22", text)

    def test_the_snapshot_carries_the_entries_and_the_release_time(self) -> None:
        net = world()
        net.on("GET", r"cisa\.gov", ok(self.CATALOGUE))
        client = Client(net, sleep=lambda _: None)
        result = fetch_feeds(client, Osv(client), [], [], {}, NOW)
        entry = (result.snapshot.kev or {})["CVE-2021-0001"]
        self.assertIsInstance(entry, models.KevEntry)
        self.assertEqual(entry.due_date, date(2026, 1, 22))
        self.assertIs(entry.forensic_triage, True)
        self.assertEqual(
            result.snapshot.kev_released_at, datetime(2026, 1, 2, 1, 2, 3, tzinfo=UTC)
        )

    def test_a_failed_catalogue_leaves_both_empty(self) -> None:
        net = world()
        net.on("GET", r"cisa\.gov", ok({"message": "down"}, 503))
        client = Client(net, sleep=lambda _: None)
        result = fetch_feeds(client, Osv(client), [], [], {}, NOW)
        self.assertIsNone(result.snapshot.kev)
        self.assertIsNone(result.snapshot.kev_released_at)


def make_record(
    run_id: str,
    prev: str | None = None,
    *,
    started: datetime = NOW,
    end_state: str = "success",
    reason: str | None = None,
) -> run_record.RunRecord:
    return run_record.RunRecord(
        run_id=run_id,
        started_at=started,
        finished_at=started,
        end_state=end_state,  # type: ignore[arg-type]
        failure_reason=reason,
        aggregator_commit=SHA,
        policy_commit=POLICY_SHA,
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
        prev_record_sha256=prev,
    )


def record_text(run_id: str, prev: str | None = None, **kwargs: Any) -> str:
    return run_record.to_json(make_record(run_id, prev, **kwargs))


def digest(text: str) -> str:
    return run_record.sha256_text(text)


def record_path(run_id: str, month: str = "2026/01") -> str:
    return f"runs/{month}/{run_id}.json"


def chain_net(records: dict[str, str]) -> FakeNet:
    """A world whose runs branch already holds ``records`` (path -> text)."""
    net = world(runs=list(records))
    for path, text in records.items():
        net.on("GET", rf"/contents/{re.escape(path)}", file_response(text))
    return net


def seed_tag(net: FakeNet, name: str, sha256: str, path: str = "runs/2026/01") -> None:
    """A tag a previous run left, with the two-line annotation this module writes."""
    obj = hashlib.sha256(name.encode()).hexdigest()[:40]
    net.tag_objects[obj] = f"path: {path}\nsha256: {sha256}\n"
    net.tag_refs[name] = obj


def ledger_json(*abandoned: tuple[str, str, str]) -> str:
    """A chain ledger; each entry is ``(month, sha256, decision)``."""
    return json.dumps(
        {
            "schema_version": 1,
            "accepted_forks": [
                {
                    "month": month,
                    "abandoned_record_sha256": sha,
                    "decision": decision,
                }
                for month, sha, decision in abandoned
            ],
        }
    )


def put_texts(net: FakeNet) -> list[str]:
    return [
        base64.b64decode(c.body["content"]).decode()
        for c in net.to("PUT", "/contents/runs/")
    ]


class ChainLedger(unittest.TestCase):
    """The chain ledger is read before a record is written; an unusable one stops the write."""

    def forked(self) -> tuple[str, str, str, FakeNet]:
        """A month with one root and two records that both name it (two tips)."""
        root = record_text("998-1")
        x = record_text("999-1", digest(root))
        y = record_text("999-2", digest(root))
        net = chain_net(
            {
                record_path("998-1"): root,
                record_path("999-1"): x,
                record_path("999-2"): y,
            }
        )
        return root, x, y, net

    def healthy(self) -> tuple[str, str, FakeNet]:
        root = record_text("998-1")
        x = record_text("999-1", digest(root))
        net = chain_net({record_path("998-1"): root, record_path("999-1"): x})
        return root, x, net

    def test_two_tips_and_an_empty_ledger_write_nothing(self) -> None:
        _root, _x, _y, net = self.forked()
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 1)
        self.assertIsNone(outcome.saved_path)
        self.assertEqual(net.to("PUT", "/contents/runs/"), [])
        self.assertTrue(
            any("chain tips" in m for m in outcome.messages), outcome.messages
        )

    def test_after_the_abandoned_tip_is_registered_the_record_is_written(self) -> None:
        _root, x, y, net = self.forked()
        ledger = ledger_json(("2026-01", digest(y), "Issue 12"))
        outcome = execute(net, policy_text([TARGET]), ledger=ledger)
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        written = put_texts(net)
        self.assertEqual(len(written), 1)
        self.assertEqual(
            run_record.from_json(written[0]).prev_record_sha256,
            digest(x),
            "the new record must name the tip that stayed in the chain",
        )

    def test_a_ledger_entry_for_a_record_that_has_a_child_writes_nothing(self) -> None:
        root, _x, net = self.healthy()
        ledger = ledger_json(("2026-01", digest(root), "Issue 12"))
        outcome = execute(net, policy_text([TARGET]), ledger=ledger)
        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(net.to("PUT", "/contents/runs/"), [])
        self.assertTrue(any("tips" in m for m in outcome.messages), outcome.messages)

    def test_a_ledger_entry_for_an_unknown_sha_writes_nothing(self) -> None:
        _root, _x, net = self.healthy()
        ledger = ledger_json(("2026-01", "f" * 64, "Issue 12"))
        outcome = execute(net, policy_text([TARGET]), ledger=ledger)
        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(net.to("PUT", "/contents/runs/"), [])
        self.assertTrue(
            any("no record has this SHA-256" in m for m in outcome.messages),
            outcome.messages,
        )

    def test_a_ledger_that_is_not_readable_writes_nothing(self) -> None:
        _root, _x, net = self.healthy()
        for text in ("{ not json", ""):
            with self.subTest(text=text):
                outcome = execute(net, policy_text([TARGET]), ledger=text)
                self.assertEqual(outcome.exit_code, 1)
                self.assertEqual(net.to("PUT", "/contents/runs/"), [])

    def test_control_a_healthy_month_with_an_empty_ledger_is_written(self) -> None:
        _root, x, net = self.healthy()
        outcome = execute(net, policy_text([TARGET]), ledger=ledger_json())
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        self.assertEqual(
            run_record.from_json(put_texts(net)[0]).prev_record_sha256, digest(x)
        )

    def test_an_entry_of_another_month_is_not_judged_against_this_one(self) -> None:
        _root, _x, net = self.healthy()
        ledger = ledger_json(("2025-06", "e" * 64, "Issue 3"))
        outcome = execute(net, policy_text([TARGET]), ledger=ledger)
        self.assertEqual(outcome.exit_code, 0, outcome.messages)


class TipRecord(unittest.TestCase):
    """The SHA-256 of what was written is kept, and the next run compares it with the month."""

    def test_the_written_sha_is_in_the_outcome_and_in_an_annotated_tag(self) -> None:
        net = world()
        outcome = execute(net, policy_text([TARGET]))
        text = put_texts(net)[0]
        self.assertEqual(outcome.tip_sha256, digest(text))
        name = f"supply-chain-runs-tip-2026-01-{RUN_ID}"
        self.assertEqual(outcome.tip_tag, name)
        created = net.to("POST", "/git/tags")
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].token, HUB_TOKEN)
        self.assertEqual(created[0].body["tag"], name)
        self.assertEqual(created[0].body["type"], "commit")
        self.assertEqual(created[0].body["object"], COMMIT)
        self.assertEqual(
            created[0].body["message"].splitlines(),
            [f"path: {outcome.saved_path}", f"sha256: {digest(text)}"],
        )
        refs = net.to("POST", "/git/refs")
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].token, HUB_TOKEN)
        self.assertEqual(refs[0].body["ref"], f"refs/tags/{name}")
        self.assertIn(refs[0].body["sha"], net.tag_objects)
        summary = aggregator.render_summary(outcome)
        self.assertIn(digest(text), summary)
        self.assertIn(name, summary)

    def test_a_first_run_with_nothing_recorded_goes_ahead(self) -> None:
        root = record_text("998-1")
        net = chain_net({record_path("998-1"): root})
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 0, outcome.messages)

    def test_control_an_unchanged_tip_goes_ahead(self) -> None:
        root = record_text("998-1")
        net = chain_net({record_path("998-1"): root})
        seed_tag(net, "supply-chain-runs-tip-2026-01-998-1", digest(root))
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        self.assertEqual(len(net.to("PUT", "/contents/runs/")), 1)

    def test_a_tip_edited_by_one_character_stops_the_run(self) -> None:
        root = record_text("998-1")
        edited = root.replace(POLICY_SHA, "b" * 39 + "c", 1)
        self.assertNotEqual(root, edited)
        net = chain_net({record_path("998-1"): edited})
        seed_tag(net, "supply-chain-runs-tip-2026-01-998-1", digest(root))
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(net.to("PUT", "/contents/runs/"), [])
        self.assertTrue(
            any("tip_changed" in m for m in outcome.messages), outcome.messages
        )

    def test_a_recorded_tip_whose_record_is_gone_stops_the_run(self) -> None:
        root = record_text("998-1")
        net = chain_net({record_path("998-1"): root})
        seed_tag(net, "supply-chain-runs-tip-2026-01-999-1", "d" * 64)
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(net.to("PUT", "/contents/runs/"), [])

    def test_an_abandoned_tip_as_the_recorded_value_goes_ahead_once_listed(
        self,
    ) -> None:
        root = record_text("998-1")
        x = record_text("999-1", digest(root))
        y = record_text("999-2", digest(root))
        net = chain_net(
            {
                record_path("998-1"): root,
                record_path("999-1"): x,
                record_path("999-2"): y,
            }
        )
        seed_tag(net, "supply-chain-runs-tip-2026-01-999-2", digest(y))
        ledger = ledger_json(("2026-01", digest(y), "PR 40"))
        outcome = execute(net, policy_text([TARGET]), ledger=ledger)
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        self.assertEqual(len(net.to("PUT", "/contents/runs/")), 1)

    def test_only_the_newest_tag_is_compared_and_newest_is_numeric(self) -> None:
        root = record_text("998-1")
        net = chain_net({record_path("998-1"): root})
        # 999 sorts after 1001 as text, and before it as a number. The newer one names a record that is gone.
        seed_tag(net, "supply-chain-runs-tip-2026-01-999-1", digest(root))
        seed_tag(net, "supply-chain-runs-tip-2026-01-1001-1", "d" * 64)
        outcome = execute(net, policy_text([TARGET]), run_id="1002-1")
        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(net.to("PUT", "/contents/runs/"), [])

    def test_a_newest_tag_without_a_sha_stops_the_run(self) -> None:
        root = record_text("998-1")
        net = chain_net({record_path("998-1"): root})
        obj = "9" * 40
        net.tag_objects[obj] = "path: runs/2026/01/998-1.json\n"
        net.tag_refs["supply-chain-runs-tip-2026-01-998-1"] = obj
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(net.to("PUT", "/contents/runs/"), [])

    def test_a_tag_that_cannot_be_created_is_a_warning_and_the_record_stays(
        self,
    ) -> None:
        net = world()
        net.on("POST", r"/git/tags$", ok({"message": "no"}, 422))
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        self.assertEqual(len(net.to("PUT", "/contents/runs/")), 1)
        self.assertTrue(any("tag" in m for m in outcome.messages), outcome.messages)
        self.assertIsNone(outcome.tip_tag)
        self.assertEqual(outcome.tip_sha256, digest(put_texts(net)[0]))


class MonthSeal(unittest.TestCase):
    """The first run of a new month seals the month before it, and checks a seal that exists."""

    def run_in_february(self, net: FakeNet) -> Any:
        return execute(net, policy_text([TARGET]), run_id="1100-1", now=NOW_FEB)

    def january(self) -> tuple[str, FakeNet]:
        jan = record_text("998-1")
        return jan, chain_net({record_path("998-1"): jan})

    def test_the_first_run_of_a_month_creates_the_seal_of_the_month_before(
        self,
    ) -> None:
        jan, net = self.january()
        outcome = self.run_in_february(net)
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        tags = {c.body["tag"]: c for c in net.to("POST", "/git/tags")}
        self.assertIn("supply-chain-runs-2026-01", tags)
        self.assertIn(
            f"sha256: {digest(jan)}", tags["supply-chain-runs-2026-01"].body["message"]
        )
        self.assertIn("supply-chain-runs-tip-2026-02-1100-1", tags)
        self.assertIn("supply-chain-runs-2026-01", net.tag_refs)

    def test_a_seal_that_exists_is_not_created_again(self) -> None:
        jan, net = self.january()
        seed_tag(net, "supply-chain-runs-2026-01", digest(jan))
        outcome = self.run_in_february(net)
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        made = [c.body["tag"] for c in net.to("POST", "/git/tags")]
        self.assertNotIn("supply-chain-runs-2026-01", made)

    def test_a_sealed_month_that_lost_its_last_record_stops_the_run(self) -> None:
        first = record_text("998-1")
        last = record_text("999-1", digest(first))
        net = chain_net({record_path("998-1"): first})  # the last record is gone
        seed_tag(net, "supply-chain-runs-2026-01", digest(last))
        outcome = self.run_in_february(net)
        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(net.to("PUT", "/contents/runs/"), [])
        self.assertTrue(
            any("seal_mismatch" in m for m in outcome.messages), outcome.messages
        )

    def test_a_month_with_two_tips_is_not_sealed_and_nothing_is_written(self) -> None:
        net = chain_net(
            {
                record_path("998-1"): record_text("998-1"),
                record_path("999-1"): record_text("999-1"),
            }
        )
        outcome = self.run_in_february(net)
        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(net.to("PUT", "/contents/runs/"), [])
        self.assertEqual(net.to("POST", "/git/tags"), [])

    def test_a_seal_that_cannot_be_created_is_a_warning(self) -> None:
        _jan, net = self.january()
        net.on("POST", r"/git/tags$", ok({"message": "no"}, 422))
        outcome = self.run_in_february(net)
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        self.assertEqual(len(net.to("PUT", "/contents/runs/")), 1)
        self.assertTrue(any("seal" in m for m in outcome.messages), outcome.messages)

    def test_a_month_with_no_record_before_it_creates_no_seal(self) -> None:
        net = world()
        self.run_in_february(net)
        made = [c.body["tag"] for c in net.to("POST", "/git/tags")]
        self.assertEqual(made, ["supply-chain-runs-tip-2026-02-1100-1"])


def dir_hub(net: FakeNet, directory: Path, delay: float) -> None:
    """Makes the runs branch of ``net`` a directory, so that two processes see each other's records."""
    hub = f"{HUB.owner}/{HUB.name}"

    def listing(url: str, _: Any) -> Response:
        paths = sorted(
            p.relative_to(directory).as_posix() for p in directory.rglob("*.json")
        )
        time.sleep(
            delay
        )  # the window in which an unlocked second run reads the same month
        return tree(paths)

    def read(url: str, _: Any) -> Response:
        rel = url.split("/contents/", 1)[1].split("?", 1)[0]
        return file_response((directory / rel).read_text(encoding="utf-8"))

    def write(url: str, payload: dict[str, Any]) -> Response:
        target = directory / url.split("/contents/", 1)[1]
        if target.exists():
            return ok({"message": "exists"}, 422)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            base64.b64decode(payload["content"]).decode("utf-8"), encoding="utf-8"
        )
        return put_ok()

    net.on("GET", rf"/repos/{hub}/git/trees/", listing)
    net.on("GET", rf"/repos/{hub}/contents/runs/", read)
    net.on("PUT", rf"/repos/{hub}/contents/runs/", write)


def race_child(directory: str, run_id: str, barrier: Any, lock_dir: str) -> None:
    os.environ["RUNNER_TEMP"] = lock_dir
    net = world()
    dir_hub(net, Path(directory), 0.5)
    barrier.wait(timeout=60)
    outcome = execute(net, policy_text([TARGET]), run_id=run_id)
    sys.exit(outcome.exit_code)


class MonthLock(unittest.TestCase):
    def test_two_processes_writing_the_same_month_leave_one_chain(self) -> None:
        ctx = multiprocessing.get_context("fork")
        barrier = ctx.Barrier(2)
        with (
            tempfile.TemporaryDirectory() as hub_dir,
            tempfile.TemporaryDirectory() as lock_dir,
        ):
            procs = [
                ctx.Process(target=race_child, args=(hub_dir, rid, barrier, lock_dir))
                for rid in ("3000-1", "3001-1")
            ]
            for proc in procs:
                proc.start()
            for proc in procs:
                proc.join(timeout=180)
            self.assertEqual([p.exitcode for p in procs], [0, 0])
            entries = [
                (p.relative_to(hub_dir).as_posix(), p.read_text(encoding="utf-8"))
                for p in sorted(Path(hub_dir).rglob("*.json"))
            ]
            self.assertEqual(len(entries), 2)
            self.assertEqual(run_record.verify_chain(entries), ())

    def test_the_lock_file_is_under_runner_temp_and_outside_the_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            saved = os.environ.get("RUNNER_TEMP")
            os.environ["RUNNER_TEMP"] = temp
            try:
                path = aggregator.month_lock_path("2026-01")
                self.assertEqual(path.parent, Path(temp))
                self.assertIn("2026-01", path.name)
                with aggregator.month_lock("2026-01"):
                    self.assertTrue(path.exists())
            finally:
                if saved is None:
                    del os.environ["RUNNER_TEMP"]
                else:
                    os.environ["RUNNER_TEMP"] = saved

    def test_without_runner_temp_the_system_temporary_directory_is_used(self) -> None:
        saved = os.environ.pop("RUNNER_TEMP", None)
        try:
            self.assertEqual(
                aggregator.month_lock_path("2026-01").parent,
                Path(tempfile.gettempdir()),
            )
        finally:
            if saved is not None:
                os.environ["RUNNER_TEMP"] = saved


class WorkflowAndLedgerFile(unittest.TestCase):
    WORKFLOW = ROOT / ".github" / "workflows" / "supply-chain-aggregator.yml"

    def test_runs_queue_instead_of_being_dropped(self) -> None:
        text = self.WORKFLOW.read_text(encoding="utf-8")
        block = re.search(r"^concurrency:\n((?:  .*\n)+)", text, re.MULTILINE)
        self.assertIsNotNone(block)
        body = block.group(1) if block else ""
        self.assertIn("queue: max", body)
        self.assertIn("cancel-in-progress: false", body)

    def test_the_ledger_path_is_passed_to_the_aggregator_step(self) -> None:
        text = self.WORKFLOW.read_text(encoding="utf-8")
        step = text.split("- name: Run the Aggregator", 1)[1]
        self.assertIn(
            "CHAIN_ACK_FILE: policy/docs/agent/supply-chain-chain-ack.json", step
        )

    def test_a_missing_ledger_file_is_an_empty_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ack.json"
            self.assertIsNone(aggregator.read_chain_ack(None))
            self.assertIsNone(aggregator.read_chain_ack(str(path)))
            path.write_text("{}", encoding="utf-8")
            self.assertEqual(aggregator.read_chain_ack(str(path)), "{}")


VEX_PURL = "pkg:npm/lodash@4.17.20"
STALE = "vex_stale_non_excluding"


def vex_text(
    doc_id: str,
    status: str,
    stamp: str,
    *,
    justification: str | None = None,
    impact: str | None = None,
    vuln: str = "CVE-2021-0001",
    purl: str = VEX_PURL,
) -> str:
    statement: dict[str, Any] = {
        "vulnerability": {"name": vuln},
        "products": [{"@id": purl}],
        "status": status,
        "timestamp": stamp,
    }
    if justification:
        statement["justification"] = justification
    if impact:
        statement["impact_statement"] = impact
    return json.dumps(
        {
            "@context": "https://openvex.dev/ns/v0.2.0",
            "@id": f"https://example.test/vex/{doc_id}",
            "author": "VEX reviewer role",
            "timestamp": stamp,
            "version": 1,
            "statements": [statement],
        }
    )


WINNER = vex_text(
    "win",
    "not_affected",
    "2025-12-20T00:00:00Z",
    justification="vulnerable_code_not_present",
    impact="the vulnerable function is not called",
)
LOSER = vex_text("lose", "under_investigation", "2025-12-01T00:00:00Z")


def vex_commit_sha(name: str) -> str:
    """A fake commit SHA per file name, so that two files can be told apart by the commit they were made in."""
    return hashlib.sha256(name.encode()).hexdigest()[:40]


AUTHOR = "alice"
REVIEWER = "bob"
PR_HEAD = "9" * 40
VEX_MERGED = "2025-12-21T00:00:00Z"
OWNED_BY_REVIEWER = f"/.vex/ @{REVIEWER}\n"


def pull_item(
    number: int,
    *,
    author: str | None = AUTHOR,
    merged_at: str | None = VEX_MERGED,
    head: str | None = PR_HEAD,
) -> dict[str, Any]:
    """A pull request of ``GET /commits/{sha}/pulls`` as the tests fake it (field names from memory)."""
    item: dict[str, Any] = {
        "number": number,
        "state": "closed" if merged_at else "open",
        "merged_at": merged_at,
        "user": {"login": author},
    }
    if head is not None:
        item["head"] = {"sha": head}
    return item


def review_item(
    login: str,
    state: str,
    *,
    commit_id: str = PR_HEAD,
    at: str = "2025-12-19T00:00:00Z",
) -> dict[str, Any]:
    """A review of ``GET /pulls/{n}/reviews`` as the tests fake it (field names from memory)."""
    return {
        "user": {"login": login},
        "state": state,
        "commit_id": commit_id,
        "submitted_at": at,
    }


def install_vex_approval(
    net: FakeNet,
    merged: dict[str, str],
    *,
    codeowners: str | None = OWNED_BY_REVIEWER,
) -> None:
    """Routes under which every file of ``merged`` (name -> merge time) is approved by ``REVIEWER``.

    Each file has its own last commit and its own merged pull request (number 100, 101, ...). The pull request
    was made by ``AUTHOR`` and its head is ``PR_HEAD``; ``REVIEWER`` approved that head and owns ``.vex/``.
    Tests override a single route afterwards; a route added later wins.
    """
    numbers = {name: 100 + index for index, name in enumerate(merged)}
    by_sha = {vex_commit_sha(name): name for name in merged}

    def commits(url: str, _: Any) -> Response:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        return ok([{"sha": vex_commit_sha(query["path"][0].removeprefix(".vex/"))}])

    def pulls(url: str, _: Any) -> Response:
        name = by_sha[url.split("/commits/", 1)[1].split("/pulls", 1)[0]]
        return ok([pull_item(numbers[name], merged_at=merged[name])])

    net.on("GET", rf"/repos/{TARGET}/commits\?", commits)
    net.on("GET", rf"/repos/{TARGET}/commits/[0-9a-f]{{40}}/pulls", pulls)
    net.on(
        "GET",
        rf"/repos/{TARGET}/pulls/\d+/reviews",
        ok([review_item(REVIEWER, "APPROVED")]),
    )
    net.on(
        "GET",
        rf"/repos/{TARGET}/contents/(?:\.github/|docs/)?CODEOWNERS\?",
        ok({"message": "Not Found"}, 404),
    )
    if codeowners is not None:
        net.on(
            "GET",
            rf"/repos/{TARGET}/contents/\.github/CODEOWNERS\?",
            file_response(codeowners),
        )


def vex_world(
    files: dict[str, str],
    merged: dict[str, str] | None = None,
    *,
    codeowners: str | None = OWNED_BY_REVIEWER,
) -> FakeNet:
    """One finding that the document ``win.json`` excludes; ``merged`` names the merge time of each file.

    Every file is approved (see ``install_vex_approval``); a test that needs a refusal overrides one route.
    """
    net = world()
    net.on("GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert()]))
    net.on(
        "GET",
        r"/contents/\.vex\?",
        ok([{"type": "file", "name": name} for name in files]),
    )
    for name, text in files.items():
        net.on("GET", rf"/contents/\.vex/{re.escape(name)}\?", file_response(text))
    install_vex_approval(
        net,
        {name: VEX_MERGED for name in files} if merged is None else merged,
        codeowners=codeowners,
    )
    return net


def rejected_reasons(outcome: Any) -> list[tuple[str, str]]:
    return [(r.path, r.reason) for r in outcome.record.rejected_vex]


def reason_of(outcome: Any, path: str) -> str:
    found = [reason for p, reason in rejected_reasons(outcome) if p == path]
    assert len(found) == 1, f"{path}: {found}"
    return found[0]


class VexMergedAt(unittest.TestCase):
    """``PlanInputs.vex_merged_at`` is the merge time of the pull request that approved each ``.vex/`` document.

    It decides ``vex_stale_non_excluding``.
    """

    FILES: ClassVar[dict[str, str]] = {"win.json": WINNER, "lose.json": LOSER}

    def captured(self, net: FakeNet) -> tuple[Any, models.PlanInputs]:
        seen: list[models.PlanInputs] = []
        real = aggregator.planner.plan

        def spy(inputs: models.PlanInputs) -> Any:
            seen.append(inputs)
            return real(inputs)

        with mock.patch.object(aggregator.planner, "plan", spy):
            outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(len(seen), 1)
        return outcome, seen[0]

    def test_each_document_is_asked_for_its_last_commit_from_the_head_commit(
        self,
    ) -> None:
        net = vex_world(self.FILES, {"win.json": VEX_MERGED, "lose.json": VEX_MERGED})
        execute(net, policy_text([TARGET]))
        asked = net.to("GET", f"/repos/{TARGET}/commits?")
        self.assertEqual(len(asked), 2)
        queries = [
            urllib.parse.parse_qs(urllib.parse.urlsplit(c.url).query) for c in asked
        ]
        self.assertEqual(
            sorted(q["path"][0] for q in queries), [".vex/lose.json", ".vex/win.json"]
        )
        for query in queries:
            self.assertEqual(query["sha"], [SHA])
            self.assertEqual(query["per_page"], ["1"])
        self.assertTrue(all(c.token == SPOKE_TOKEN for c in asked))

    def test_the_time_is_the_merge_time_of_the_pull_request_not_the_commit_time(
        self,
    ) -> None:
        net = vex_world(
            self.FILES,
            {"win.json": "2025-12-21T01:02:03Z", "lose.json": "2025-12-25T00:00:00Z"},
        )
        _outcome, inputs = self.captured(net)
        merged = (inputs.vex_merged_at or {})[REPO]
        self.assertEqual(
            merged,
            {
                f"{TARGET}:.vex/win.json": datetime(2025, 12, 21, 1, 2, 3, tzinfo=UTC),
                f"{TARGET}:.vex/lose.json": datetime(2025, 12, 25, tzinfo=UTC),
            },
        )
        self.assertEqual(
            sorted(d.path for d in inputs.vex[REPO]),
            [f"{TARGET}:.vex/lose.json", f"{TARGET}:.vex/win.json"],
        )

    def test_the_merge_time_is_in_utc_without_a_fraction_of_a_second(self) -> None:
        net = vex_world(
            {"win.json": WINNER}, {"win.json": "2025-12-21T10:02:03.456+09:00"}
        )
        _outcome, inputs = self.captured(net)
        self.assertEqual(
            (inputs.vex_merged_at or {})[REPO],
            {f"{TARGET}:.vex/win.json": datetime(2025, 12, 21, 1, 2, 3, tzinfo=UTC)},
        )

    def test_a_non_excluding_statement_merged_after_the_one_that_wins_is_reported(
        self,
    ) -> None:
        net = vex_world(
            self.FILES,
            {"win.json": "2025-12-21T00:00:00Z", "lose.json": "2025-12-25T00:00:00Z"},
        )
        outcome = execute(net, policy_text([TARGET]))
        self.assertIn((".vex/lose.json", STALE), rejected_reasons(outcome))
        self.assertEqual(len(outcome.record.vex_exclusions), 1, "the control: win.json")
        self.assertEqual(outcome.exit_code, 0, outcome.messages)

    def test_the_reverse_order_reports_nothing(self) -> None:
        net = vex_world(
            self.FILES,
            {"win.json": "2025-12-21T00:00:00Z", "lose.json": "2025-12-10T00:00:00Z"},
        )
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(len(net.to("GET", f"/repos/{TARGET}/commits?")), 2)
        self.assertNotIn(STALE, [reason for _path, reason in rejected_reasons(outcome)])
        self.assertEqual(len(outcome.record.vex_exclusions), 1)

    def test_a_document_that_is_not_approved_has_no_merge_time(self) -> None:
        net = vex_world(self.FILES)
        net.on(
            "GET",
            r"/pulls/101/reviews",
            ok([review_item(REVIEWER, "CHANGES_REQUESTED")]),
        )
        _outcome, inputs = self.captured(net)
        self.assertEqual(
            list((inputs.vex_merged_at or {})[REPO]), [f"{TARGET}:.vex/win.json"]
        )

    def test_a_refused_query_leaves_that_document_out_and_the_run_goes_on(
        self,
    ) -> None:
        for status in (404, 500):
            with self.subTest(status=status):
                net = vex_world(self.FILES)
                net.on(
                    "GET",
                    rf"/repos/{TARGET}/commits\?path=\.vex%2Fwin\.json",
                    ok({"message": "refused"}, status),
                )
                outcome = execute(net, policy_text([TARGET]))
                self.assertEqual(outcome.exit_code, 0, outcome.messages)
                self.assertEqual(outcome.record.end_state, "success")
                self.assertTrue(
                    reason_of(outcome, ".vex/win.json").startswith("vex_unverifiable:")
                )
                self.assertEqual(outcome.record.vex_exclusions, ())
                self.assertNotIn(".vex/lose.json", dict(rejected_reasons(outcome)))

    def test_a_document_with_no_commit_is_not_verifiable(self) -> None:
        net = vex_world(self.FILES)
        net.on(
            "GET",
            rf"/repos/{TARGET}/commits\?path=\.vex%2Flose\.json",
            ok([]),
        )
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        self.assertTrue(
            reason_of(outcome, ".vex/lose.json").startswith("vex_unverifiable:")
        )
        self.assertEqual(len(outcome.record.vex_exclusions), 1)

    def test_a_repository_without_vex_documents_is_never_asked(self) -> None:
        net = world()
        net.on("GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert()]))
        execute(net, policy_text([TARGET]))
        self.assertEqual(net.to("GET", "/commits"), [])
        self.assertEqual(net.to("GET", "CODEOWNERS"), [])

    def test_a_repository_whose_only_document_is_not_valid_is_never_asked(
        self,
    ) -> None:
        net = vex_world({"bad.json": "{ nope"})
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(net.to("GET", "/commits"), [])
        self.assertIn(".vex/bad.json", dict(rejected_reasons(outcome)))
        self.assertFalse(
            reason_of(outcome, ".vex/bad.json").startswith("vex_un"),
            "an unparseable document is not an approval question",
        )

    def test_a_rate_limit_on_the_query_stops_the_run_like_any_other_read(self) -> None:
        net = vex_world(self.FILES)
        net.on(
            "GET",
            rf"/repos/{TARGET}/commits\?",
            Response(429, {"retry-after": "3600"}, b""),
        )
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.record.end_state, "failure")
        self.assertIn("rate limit", outcome.record.failure_reason or "")

    def test_a_rate_limit_on_the_pull_request_list_stops_the_run_too(self) -> None:
        net = vex_world(self.FILES)
        net.on(
            "GET",
            rf"/repos/{TARGET}/commits/[0-9a-f]{{40}}/pulls",
            Response(429, {"retry-after": "3600"}, b""),
        )
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.record.end_state, "failure")
        self.assertIn("rate limit", outcome.record.failure_reason or "")


class VexApproval(unittest.TestCase):
    """A document counts only when a Code Owner other than the author approved the head that was merged."""

    FILES: ClassVar[dict[str, str]] = {"win.json": WINNER}

    def world(self, **kwargs: Any) -> FakeNet:
        return vex_world(self.FILES, **kwargs)

    def decided(self, net: FakeNet) -> Any:
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        return outcome

    def assert_unapproved(self, net: FakeNet, *words: str) -> str:
        outcome = self.decided(net)
        reason = reason_of(outcome, ".vex/win.json")
        self.assertTrue(reason.startswith("vex_unapproved:"), reason)
        for word in words:
            self.assertIn(word, reason)
        self.assertEqual(
            outcome.record.vex_exclusions, (), "an unapproved document was applied"
        )
        return reason

    def assert_unverifiable(self, net: FakeNet) -> str:
        outcome = self.decided(net)
        reason = reason_of(outcome, ".vex/win.json")
        self.assertTrue(reason.startswith("vex_unverifiable:"), reason)
        self.assertEqual(
            outcome.record.vex_exclusions, (), "an unverifiable document was applied"
        )
        return reason

    def test_control_an_approved_document_is_applied(self) -> None:
        outcome = self.decided(self.world())
        self.assertEqual(len(outcome.record.vex_exclusions), 1)
        self.assertEqual(outcome.record.rejected_vex, ())

    def test_one_file_costs_a_commit_a_pull_request_list_and_a_review_list(
        self,
    ) -> None:
        net = self.world()
        self.decided(net)
        self.assertEqual(len(net.to("GET", f"/repos/{TARGET}/commits?")), 1)
        self.assertEqual(len(net.to("GET", "/pulls")), 2)  # the list and the reviews
        self.assertEqual(len(net.to("GET", "/reviews")), 1)
        self.assertEqual(len(net.to("GET", "CODEOWNERS")), 1)
        self.assertTrue(
            all(
                c.token == SPOKE_TOKEN
                for c in net.calls
                if "/commits" in c.url or "/pulls" in c.url or "CODEOWNERS" in c.url
            )
        )

    def test_a_later_changes_requested_cancels_an_earlier_approval(self) -> None:
        net = self.world()
        net.on(
            "GET",
            r"/pulls/100/reviews",
            ok(
                [
                    review_item(REVIEWER, "APPROVED", at="2025-12-19T00:00:00Z"),
                    review_item(
                        REVIEWER, "CHANGES_REQUESTED", at="2025-12-19T01:00:00Z"
                    ),
                ]
            ),
        )
        self.assert_unapproved(net, "approval")

    def test_a_later_dismissal_cancels_an_earlier_approval(self) -> None:
        net = self.world()
        net.on(
            "GET",
            r"/pulls/100/reviews",
            ok(
                [
                    review_item(REVIEWER, "APPROVED", at="2025-12-19T00:00:00Z"),
                    review_item(REVIEWER, "DISMISSED", at="2025-12-19T01:00:00Z"),
                ]
            ),
        )
        self.assert_unapproved(net, "approval")

    def test_the_order_is_by_time_not_by_position_in_the_answer(self) -> None:
        net = self.world()
        net.on(
            "GET",
            r"/pulls/100/reviews",
            ok(
                [
                    review_item(
                        REVIEWER, "CHANGES_REQUESTED", at="2025-12-19T00:00:00Z"
                    ),
                    review_item(REVIEWER, "APPROVED", at="2025-12-19T01:00:00Z"),
                ]
            ),
        )
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)

    def test_reviews_at_the_same_time_keep_the_order_of_the_answer(self) -> None:
        same = "2025-12-19T00:00:00Z"
        for states, applied in (
            (("CHANGES_REQUESTED", "APPROVED"), True),
            (("APPROVED", "CHANGES_REQUESTED"), False),
        ):
            with self.subTest(states=states):
                net = self.world()
                net.on(
                    "GET",
                    r"/pulls/100/reviews",
                    ok([review_item(REVIEWER, s, at=same) for s in states]),
                )
                outcome = self.decided(net)
                self.assertEqual(bool(outcome.record.vex_exclusions), applied)

    def test_a_comment_after_an_approval_does_not_change_it(self) -> None:
        net = self.world()
        net.on(
            "GET",
            r"/pulls/100/reviews",
            ok(
                [
                    review_item(REVIEWER, "APPROVED", at="2025-12-19T00:00:00Z"),
                    review_item(REVIEWER, "COMMENTED", at="2025-12-19T01:00:00Z"),
                ]
            ),
        )
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)

    def test_a_comment_alone_is_not_an_approval(self) -> None:
        net = self.world()
        net.on("GET", r"/pulls/100/reviews", ok([review_item(REVIEWER, "COMMENTED")]))
        self.assert_unapproved(net, "approval")

    def test_a_pending_review_is_not_an_approval(self) -> None:
        net = self.world()
        pending = review_item(REVIEWER, "PENDING")
        del pending["submitted_at"]
        net.on("GET", r"/pulls/100/reviews", ok([pending]))
        self.assert_unapproved(net, "approval")

    def test_the_approval_of_the_author_alone_is_refused(self) -> None:
        net = self.world(codeowners=f"/.vex/ @{AUTHOR}\n")
        net.on("GET", r"/pulls/100/reviews", ok([review_item(AUTHOR, "APPROVED")]))
        self.assert_unapproved(net, "author")

    def test_the_author_is_compared_without_regard_to_case(self) -> None:
        net = self.world(codeowners=f"/.vex/ @{AUTHOR}\n")
        net.on(
            "GET", r"/pulls/100/reviews", ok([review_item(AUTHOR.upper(), "APPROVED")])
        )
        self.assert_unapproved(net, "author")

    def test_an_approval_by_someone_else_still_counts_beside_the_authors(self) -> None:
        net = self.world(codeowners=f"/.vex/ @{AUTHOR} @{REVIEWER}\n")
        net.on(
            "GET",
            r"/pulls/100/reviews",
            ok([review_item(AUTHOR, "APPROVED"), review_item(REVIEWER, "APPROVED")]),
        )
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)

    def test_an_approval_of_an_earlier_head_is_refused(self) -> None:
        net = self.world()
        net.on(
            "GET",
            r"/pulls/100/reviews",
            ok([review_item(REVIEWER, "APPROVED", commit_id="8" * 40)]),
        )
        self.assert_unapproved(net, "commit")

    def test_the_head_is_read_from_the_pull_request_when_the_list_has_none(
        self,
    ) -> None:
        net = self.world()
        sha = vex_commit_sha("win.json")
        net.on(
            "GET",
            rf"/repos/{TARGET}/commits/{sha}/pulls",
            ok([pull_item(100, head=None)]),
        )
        net.on(
            "GET",
            rf"/repos/{TARGET}/pulls/100$",
            ok({"number": 100, "head": {"sha": PR_HEAD}}),
        )
        outcome = self.decided(net)
        self.assertEqual(len(outcome.record.vex_exclusions), 1)
        self.assertEqual(len(net.to("GET", f"/repos/{TARGET}/pulls/100")), 2)

    def test_a_pull_request_whose_head_cannot_be_found_is_not_verifiable(self) -> None:
        net = self.world()
        sha = vex_commit_sha("win.json")
        net.on(
            "GET",
            rf"/repos/{TARGET}/commits/{sha}/pulls",
            ok([pull_item(100, head=None)]),
        )
        net.on("GET", rf"/repos/{TARGET}/pulls/100$", ok({"number": 100}))
        self.assert_unverifiable(net)

    def test_a_reviewer_who_is_not_a_code_owner_is_refused(self) -> None:
        net = self.world(codeowners="/.vex/ @carol\n")
        self.assert_unapproved(net, "Code Owner")

    def test_without_a_codeowners_file_nobody_owns_the_directory(self) -> None:
        net = self.world(codeowners=None)
        reason = self.assert_unapproved(net, "CODEOWNERS")
        self.assertNotIn("is not a Code Owner", reason)
        self.assertEqual(len(net.to("GET", "CODEOWNERS")), 3, "the three places")

    def test_only_a_team_as_the_owner_leaves_no_approver(self) -> None:
        net = self.world(codeowners="/.vex/ @example-org/vex-reviewers\n")
        self.assert_unapproved(net, "Code Owner")

    def test_an_email_address_as_the_owner_is_not_counted(self) -> None:
        net = self.world(codeowners="/.vex/ reviewer" + chr(64) + "example.test\n")
        self.assert_unapproved(net, "Code Owner")

    def test_a_user_beside_a_team_counts(self) -> None:
        net = self.world(codeowners=f"/.vex/ @example-org/team @{REVIEWER}\n")
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)

    def test_user_names_are_compared_without_regard_to_case(self) -> None:
        net = self.world(codeowners=f"/.vex/ @{REVIEWER.upper()}\n")
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)

    def test_the_last_matching_line_decides(self) -> None:
        later = self.world(codeowners=f"/.vex/ @{REVIEWER}\n/.vex/* @carol\n")
        self.assert_unapproved(later, "Code Owner")
        earlier = self.world(codeowners=f"/.vex/* @carol\n/.vex/ @{REVIEWER}\n")
        self.assertEqual(len(self.decided(earlier).record.vex_exclusions), 1)

    def test_a_later_line_that_names_no_owner_takes_the_directory_away(self) -> None:
        net = self.world(codeowners=f"/.vex/ @{REVIEWER}\n/.vex/win.json\n")
        self.assert_unapproved(net, "Code Owner")

    def test_a_line_that_does_not_match_leaves_the_earlier_one(self) -> None:
        net = self.world(codeowners=f"/.vex/ @{REVIEWER}\n/docs/ @carol\n*.md @carol\n")
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)

    def test_a_line_in_a_syntax_that_is_not_supported_after_the_last_match_is_not_decidable(
        self,
    ) -> None:
        net = self.world(codeowners=f"/.vex/ @{REVIEWER}\n[ab]* @carol\n")
        self.assert_unverifiable(net)

    def test_a_line_in_a_syntax_that_is_not_supported_before_the_last_match_does_not_matter(
        self,
    ) -> None:
        net = self.world(codeowners=f"!/x @carol\n/.vex/ @{REVIEWER}\n")
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)

    def test_comments_are_not_lines(self) -> None:
        net = self.world(
            codeowners=f"# [x] !y\n/.vex/ @{REVIEWER} # @carol [not a pattern]\n"
        )
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)

    def test_the_first_codeowners_in_the_search_order_is_the_only_one_read(
        self,
    ) -> None:
        net = self.world()  # .github/CODEOWNERS names the reviewer
        net.on(
            "GET",
            rf"/repos/{TARGET}/contents/CODEOWNERS\?",
            file_response("/.vex/ @carol\n"),
        )
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)
        self.assertEqual(len(net.to("GET", "CODEOWNERS")), 1)

    def test_the_root_file_is_used_when_there_is_none_under_dot_github(self) -> None:
        net = self.world(codeowners=None)
        net.on(
            "GET",
            rf"/repos/{TARGET}/contents/CODEOWNERS\?",
            file_response(OWNED_BY_REVIEWER),
        )
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)

    def test_a_file_under_dot_github_wins_over_the_root_one(self) -> None:
        net = self.world(codeowners="/.vex/ @carol\n")
        net.on(
            "GET",
            rf"/repos/{TARGET}/contents/CODEOWNERS\?",
            file_response(OWNED_BY_REVIEWER),
        )
        self.assert_unapproved(net, "Code Owner")

    def test_the_docs_file_is_the_last_place(self) -> None:
        net = self.world(codeowners=None)
        net.on(
            "GET",
            rf"/repos/{TARGET}/contents/docs/CODEOWNERS\?",
            file_response(OWNED_BY_REVIEWER),
        )
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)

    def test_a_pull_request_that_was_not_merged_is_refused(self) -> None:
        net = self.world()
        sha = vex_commit_sha("win.json")
        net.on(
            "GET",
            rf"/repos/{TARGET}/commits/{sha}/pulls",
            ok([pull_item(100, merged_at=None)]),
        )
        self.assert_unapproved(net, "not merged")

    def test_a_commit_with_no_pull_request_is_refused_with_its_own_reason(self) -> None:
        net = self.world()
        sha = vex_commit_sha("win.json")
        net.on("GET", rf"/repos/{TARGET}/commits/{sha}/pulls", ok([]))
        reason = self.assert_unapproved(net, "no pull request")
        self.assertNotIn("not merged", reason)

    def test_two_merged_pull_requests_are_refused_with_their_own_reason(self) -> None:
        net = self.world()
        sha = vex_commit_sha("win.json")
        net.on(
            "GET",
            rf"/repos/{TARGET}/commits/{sha}/pulls",
            ok([pull_item(100), pull_item(101)]),
        )
        reason = self.assert_unapproved(net, "2 merged pull requests")
        self.assertNotIn("not merged", reason)

    def test_an_unmerged_pull_request_beside_one_merged_does_not_matter(self) -> None:
        net = self.world()
        sha = vex_commit_sha("win.json")
        net.on(
            "GET",
            rf"/repos/{TARGET}/commits/{sha}/pulls",
            ok([pull_item(99, merged_at=None), pull_item(100)]),
        )
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)

    def test_a_failure_to_read_is_not_a_refusal(self) -> None:
        sha = vex_commit_sha("win.json")
        for label, route, status in (
            ("commits", rf"/repos/{TARGET}/commits\?", 500),
            ("pulls 5xx", rf"/repos/{TARGET}/commits/{sha}/pulls", 502),
            ("pulls 404", rf"/repos/{TARGET}/commits/{sha}/pulls", 404),
            ("reviews", r"/pulls/100/reviews", 500),
            ("codeowners", rf"/repos/{TARGET}/contents/\.github/CODEOWNERS\?", 500),
        ):
            with self.subTest(label):
                net = self.world()
                net.on("GET", route, ok({"message": "down"}, status))
                self.assert_unverifiable(net)

    def test_a_dropped_connection_is_not_a_refusal_either(self) -> None:
        def dropped(url: str, payload: Any) -> Response:
            raise TransportError("connection reset")

        net = self.world()
        net.on("GET", r"/pulls/100/reviews", dropped)
        self.assert_unverifiable(net)

    def test_an_answer_of_the_wrong_shape_is_not_a_refusal(self) -> None:
        sha = vex_commit_sha("win.json")
        pulls = rf"/repos/{TARGET}/commits/{sha}/pulls"
        bad_pull = pull_item(100)
        del bad_pull["merged_at"]
        no_author = pull_item(100, author=None)
        no_author["user"] = None
        bad_number = pull_item(100)
        bad_number["number"] = "100"
        bad_time = pull_item(100, merged_at="yesterday")
        for label, route, body in (
            ("pulls is an object", pulls, {"pulls": []}),
            ("a pull is not an object", pulls, ["x"]),
            ("a pull has no merged_at", pulls, [bad_pull]),
            ("a pull has no author", pulls, [no_author]),
            ("a pull has no number", pulls, [bad_number]),
            ("merged_at is not a time", pulls, [bad_time]),
            ("reviews is an object", r"/pulls/100/reviews", {"reviews": []}),
            ("a review is not an object", r"/pulls/100/reviews", ["x"]),
            (
                "a review has no state",
                r"/pulls/100/reviews",
                [{"user": {"login": REVIEWER}, "submitted_at": "2025-12-19T00:00:00Z"}],
            ),
            (
                "a review has no time",
                r"/pulls/100/reviews",
                [{"user": {"login": REVIEWER}, "state": "APPROVED"}],
            ),
        ):
            with self.subTest(label):
                net = self.world()
                net.on("GET", route, ok(body))
                self.assert_unverifiable(net)

    def test_reviews_are_read_to_the_last_page(self) -> None:
        net = self.world()
        first = ok(
            [review_item("carol", "COMMENTED")],
            headers={
                "link": f'<https://api.github.com/repos/{TARGET}/pulls/100/reviews?page=2>; rel="next"'
            },
        )

        def reviews(url: str, _: Any) -> Response:
            if "page=2" in url:
                return ok([review_item(REVIEWER, "APPROVED")])
            return first

        net.on("GET", r"/pulls/100/reviews", reviews)
        self.assertEqual(len(self.decided(net).record.vex_exclusions), 1)
        self.assertEqual(len(net.to("GET", "/pulls/100/reviews")), 2)

    def test_two_files_of_one_commit_ask_for_the_pull_request_and_its_reviews_once(
        self,
    ) -> None:
        other = vex_text(
            "other",
            "not_affected",
            "2025-12-20T00:00:00Z",
            justification="vulnerable_code_not_present",
            impact="the vulnerable function is not called",
            vuln="CVE-2021-9999",
        )
        net = vex_world({"win.json": WINNER, "other.json": other})
        same = vex_commit_sha("win.json")
        net.on(
            "GET",
            rf"/repos/{TARGET}/commits\?",
            ok([{"sha": same}]),
        )
        net.on(
            "GET",
            rf"/repos/{TARGET}/commits/{same}/pulls",
            ok([pull_item(100)]),
        )
        outcome = self.decided(net)
        self.assertEqual(len(net.to("GET", f"/repos/{TARGET}/commits/{same}/pulls")), 1)
        self.assertEqual(len(net.to("GET", "/pulls/100/reviews")), 1)
        self.assertEqual(len(net.to("GET", "CODEOWNERS")), 1)
        self.assertEqual(outcome.record.rejected_vex, ())

    def test_one_unapproved_file_does_not_take_the_others_with_it(self) -> None:
        net = vex_world({"win.json": WINNER, "lose.json": LOSER})
        net.on(
            "GET",
            r"/pulls/100/reviews",
            ok([review_item(REVIEWER, "CHANGES_REQUESTED")]),
        )
        outcome = self.decided(net)
        self.assertTrue(
            reason_of(outcome, ".vex/win.json").startswith("vex_unapproved:")
        )
        self.assertNotIn(".vex/lose.json", dict(rejected_reasons(outcome)))

    def test_the_path_of_a_refusal_is_the_path_in_the_repository(self) -> None:
        net = self.world(codeowners="/.vex/ @carol\n")
        outcome = self.decided(net)
        entry = outcome.record.rejected_vex[0]
        self.assertEqual((entry.repo, entry.path), (TARGET, ".vex/win.json"))

    def test_the_summary_counts_both_kinds(self) -> None:
        files = {"win.json": WINNER, "lose.json": LOSER, "third.json": WINNER}
        net = vex_world(files)
        net.on("GET", r"/pulls/100/reviews", ok([review_item(REVIEWER, "COMMENTED")]))
        net.on("GET", r"/pulls/101/reviews", ok({"message": "down"}, 500))
        outcome = self.decided(net)
        lines = aggregator.render_summary(outcome).splitlines()
        self.assertIn("- VEX documents not approved (vex_unapproved): 1", lines)
        self.assertIn(
            "- VEX documents that could not be verified (vex_unverifiable): 1", lines
        )

    def test_the_summary_says_zero_when_there_is_nothing_to_report(self) -> None:
        lines = aggregator.render_summary(execute(world(), policy_text([TARGET])))
        self.assertIn("- VEX documents not approved (vex_unapproved): 0", lines)
        self.assertIn(
            "- VEX documents that could not be verified (vex_unverifiable): 0", lines
        )


class CodeownersOwners(unittest.TestCase):
    """``codeowners_owners``: the owners of one path under the last matching line, in the supported syntax."""

    PATH = ".vex/a.openvex.json"

    def owners(self, text: str, path: str = PATH) -> frozenset[str]:
        return aggregator.codeowners_owners(text, path)

    def test_the_forms_that_cover_the_directory(self) -> None:
        for pattern in (
            "/.vex/",
            "/.vex/*",
            ".vex/",
            "/.vex",
            ".vex",
            ".vex/*",
            "/.vex/**",
            "**/.vex/",
            "*",
            "**",
            "/**/a.openvex.json",
            "*.json",
            "/.vex/a.openvex.json",
            "/.vex/?.openvex.json",
            "/.v?x/",
        ):
            with self.subTest(pattern):
                self.assertEqual(self.owners(f"{pattern} @bob\n"), {"bob"})

    def test_the_forms_that_do_not_cover_it(self) -> None:
        for pattern in (
            "/.github/",
            "/docs/",
            ".vexx/",
            "/vex/",
            "/other/.vex/",
            "*.md",
            "/*.json",
            "/.vex/b.openvex.json",
            "/.vex/??.openvex.json",
            "a.openvex.json/",
            "/.vex/*/",
        ):
            with self.subTest(pattern):
                self.assertEqual(self.owners(f"{pattern} @bob\n"), frozenset())

    def test_a_directory_deeper_in_the_tree_is_reached_by_an_unanchored_name(
        self,
    ) -> None:
        self.assertEqual(self.owners(".vex/ @bob\n", "pkg/.vex/a.json"), {"bob"})
        self.assertEqual(self.owners("/.vex/ @bob\n", "pkg/.vex/a.json"), frozenset())

    def test_star_does_not_cross_a_slash(self) -> None:
        self.assertEqual(self.owners("/.vex/* @bob\n", ".vex/sub/a.json"), {"bob"})
        self.assertEqual(
            self.owners("/*/a.json @bob\n", ".vex/sub/a.json"), frozenset()
        )

    def test_owners_are_users_in_lower_case_only(self) -> None:
        text = (
            "/.vex/ @Bob @org/team carol"
            + chr(64)
            + "example.test @a-b @-bad @bad- bob\n"
        )
        self.assertEqual(self.owners(text), {"bob", "a-b"})

    def test_the_last_match_replaces_the_owners_and_does_not_add_to_them(self) -> None:
        self.assertEqual(self.owners("/.vex/ @a\n/.vex/* @b\n"), {"b"})

    def test_a_line_with_no_owner_that_matches_leaves_none(self) -> None:
        self.assertEqual(self.owners("/.vex/ @a\n/.vex/\n"), frozenset())

    def test_blank_lines_and_comments_are_skipped(self) -> None:
        self.assertEqual(self.owners("\n  # c\n\n/.vex/ @a # @b\n"), {"a"})

    def test_a_line_that_cannot_be_read_after_the_last_match_is_undecidable(
        self,
    ) -> None:
        for odd in ("[ab] @c", "!x @c", "\\#x @c", "a**b @c", "/.vex/[a]* @c", "// @c"):
            with (
                self.subTest(odd),
                self.assertRaises(aggregator.CodeownersUndecidable),
            ):
                self.owners(f"/.vex/ @a\n{odd}\n")

    def test_the_same_line_before_the_last_match_is_harmless(self) -> None:
        for odd in ("[ab] @c", "!x @c", "\\#x @c", "a**b @c"):
            with self.subTest(odd):
                self.assertEqual(self.owners(f"{odd}\n/.vex/ @a\n"), {"a"})

    def test_a_file_with_no_line_for_the_path_has_no_owner(self) -> None:
        self.assertEqual(self.owners(""), frozenset())
        self.assertEqual(self.owners("# only\n"), frozenset())


class ReopenAfterALongClose(unittest.TestCase):
    """An Issue closed for longer than its Response_Target starts a new response when it is reopened."""

    def reopened(self, closed_days_ago: int | None) -> dict[str, Any]:
        opened = NOW - timedelta(days=50)
        due = NOW - timedelta(days=20)
        body = finding_issue_body(
            "CVE-2021-0001", kev=False, severity="HIGH", due_at=due, opened_at=opened
        )
        closed = (
            None
            if closed_days_ago is None
            else iso(NOW - timedelta(days=closed_days_ago))
        )
        net = world()
        net.on("GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert()]))
        net.on(
            "GET",
            rf"/repos/{TARGET}/issues\?",
            ok([issue_item(7, body, state="closed", closed_at=closed)]),
        )
        execute(net, policy_text([TARGET]))
        patches = [c for c in net.to("PATCH", "/issues/7") if c.body.get("body")]
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0].body["state"], "open")
        return issue_body.parse_state(patches[0].body["body"]) or {}

    def test_closed_for_longer_than_the_target_the_deadline_starts_again(self) -> None:
        state = self.reopened(40)  # the target for a HIGH finding is 30 days
        self.assertEqual(state["opened_at"], iso(NOW))
        self.assertEqual(state["due_at"], iso(NOW + timedelta(days=30)))

    def test_control_closed_for_less_the_earlier_deadline_continues(self) -> None:
        state = self.reopened(10)
        self.assertEqual(state["opened_at"], iso(NOW - timedelta(days=50)))
        self.assertEqual(state["due_at"], iso(NOW - timedelta(days=20)))

    def test_an_issue_with_no_closing_time_continues_the_earlier_deadline(self) -> None:
        state = self.reopened(None)
        self.assertEqual(state["opened_at"], iso(NOW - timedelta(days=50)))


class SkippedPaths(unittest.TestCase):
    """The ``skipped_paths`` of the artifact that was scanned are recorded, never judged."""

    SBOM = spdx_doc([("lodash", "4.17.20", "pkg:npm/lodash@4.17.20")])

    def run_with(self, members: dict[str, str] | None) -> tuple[Any, FakeNet]:
        net = world()
        artifact(net, self.SBOM, members)
        return execute(net, policy_text([TARGET])), net

    def test_the_paths_of_generation_json_are_recorded_for_the_repository(self) -> None:
        text = json.dumps({"skipped_paths": ["test/fixtures", "docs/**/sample"]})
        outcome, net = self.run_with({"generation.json": text})
        self.assertEqual(
            outcome.extra.skipped_paths,
            {TARGET: ["test/fixtures", "docs/**/sample"]},
        )
        self.assertEqual(outcome.extra.warnings, ())
        self.assertEqual(
            extra_json(net)["skipped_paths"],
            {TARGET: ["test/fixtures", "docs/**/sample"]},
        )

    def test_an_empty_array_stays_an_empty_array(self) -> None:
        outcome, net = self.run_with({"generation.json": '{"skipped_paths": []}'})
        self.assertEqual(outcome.extra.skipped_paths, {TARGET: []})
        self.assertEqual(extra_json(net)["skipped_paths"], {TARGET: []})

    def test_what_cannot_be_read_is_not_recorded_and_says_so_once_and_changes_no_scan(
        self,
    ) -> None:
        control, _ = self.run_with({"generation.json": '{"skipped_paths": []}'})
        bad = {
            "no generation.json": None,
            "not JSON": {"generation.json": "{ nope"},
            "not an object": {"generation.json": "[]"},
            "no skipped_paths": {"generation.json": '{"component_count": 1}'},
            "not an array": {"generation.json": '{"skipped_paths": "a"}'},
            "a non-string element": {"generation.json": '{"skipped_paths": ["a", 1]}'},
            "null": {"generation.json": '{"skipped_paths": null}'},
        }
        for label, members in bad.items():
            with self.subTest(label):
                outcome, _net = self.run_with(members)
                self.assertEqual(outcome.extra.skipped_paths, {})
                notes = [m for m in outcome.messages if "skipped_paths" in m]
                self.assertEqual(len(notes), 1, outcome.messages)
                self.assertIn(TARGET, notes[0])
                self.assertEqual(outcome.exit_code, 0, outcome.messages)
                self.assertEqual(
                    outcome.record.repositories.scanned,
                    control.record.repositories.scanned,
                )
                self.assertEqual(outcome.record.findings, control.record.findings)

    def test_a_repository_scanned_through_layer_a_is_not_recorded(self) -> None:
        net = world()
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.record.repositories.scanned, (TARGET,))
        self.assertEqual(outcome.extra.skipped_paths, {})
        self.assertEqual(outcome.extra.warnings, ())

    def test_only_the_repositories_that_were_scanned_are_recorded(self) -> None:
        # the artifact names TARGET, so OTHER's layer B fails and its scan comes from layer A alone
        net = world([TARGET, OTHER])
        artifact(net, self.SBOM, {"generation.json": '{"skipped_paths": ["a"]}'})
        outcome = execute(net, policy_text([TARGET, OTHER]))
        self.assertEqual(sorted(outcome.extra.skipped_paths), [TARGET])


def extra_put(net: FakeNet) -> Call:
    puts = net.to("PUT", "/contents/runs-extra/")
    assert len(puts) == 1, f"{len(puts)} writes to runs-extra"
    return puts[0]


def extra_json(net: FakeNet) -> dict[str, Any]:
    return json.loads(base64.b64decode(extra_put(net).body["content"]).decode())


class ExtraRecord(unittest.TestCase):
    """The side record sits beside the run record and is not part of the chain."""

    def test_it_is_written_after_the_run_record_under_runs_extra(self) -> None:
        net = world()
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        run_put = net.to("PUT", "/contents/runs/")[0]
        put = extra_put(net)
        self.assertLess(net.calls.index(run_put), net.calls.index(put))
        self.assertEqual(outcome.extra_path, "runs-extra/2026/01/1000-1.json")
        self.assertTrue(put.url.endswith("/contents/runs-extra/2026/01/1000-1.json"))
        self.assertNotIn("sha", put.body)
        self.assertEqual(put.body["branch"], "supply-chain-runs")
        self.assertEqual(put.token, HUB_TOKEN)
        text = base64.b64decode(put.body["content"]).decode()
        self.assertTrue(text.endswith("}\n") and not text.endswith("\n\n"))
        data = json.loads(text)
        self.assertEqual(
            list(data),
            [
                "schema_version",
                "run_id",
                "record_path",
                "record_sha256",
                "skipped_paths",
                "pilot",
            ],
        )
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["run_id"], RUN_ID)
        self.assertEqual(data["record_path"], outcome.saved_path)
        self.assertEqual(data["record_sha256"], digest(put_texts(net)[0]))
        self.assertEqual(data["record_sha256"], outcome.tip_sha256)

    def test_the_run_record_and_the_chain_do_not_change(self) -> None:
        net = world()
        execute(net, policy_text([TARGET]))
        first = put_texts(net)[0]
        for word in ("pilot", "skipped_paths", "runs-extra"):
            self.assertNotIn(word, first)
        run_record.from_json(first)
        # the next run lists the extra record in the tree and still chains to the run record
        net2 = world(
            runs=["runs/2026/01/1000-1.json", "runs-extra/2026/01/1000-1.json"]
        )
        net2.on("GET", r"/contents/runs/2026/01/1000-1\.json", file_response(first))
        outcome = execute(net2, policy_text([TARGET]), run_id="1001-1")
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        second = run_record.from_json(put_texts(net2)[0])
        self.assertEqual(second.prev_record_sha256, digest(first))

    def test_a_failed_write_changes_neither_the_result_nor_the_exit_code(self) -> None:
        net = world()
        net.on(
            "PUT",
            r"/contents/runs-extra/",
            ok({"message": "sha wasn't supplied"}, 422),
        )
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        self.assertEqual(outcome.record.end_state, "success")
        self.assertEqual(outcome.saved_path, "runs/2026/01/1000-1.json")
        self.assertIsNone(outcome.extra_path)
        self.assertEqual(len(net.to("PUT", "/contents/runs-extra/")), 1)
        self.assertEqual(len(net.to("PUT", "/contents/runs/")), 1)
        self.assertEqual(
            len([m for m in outcome.messages if "extra record not saved" in m]), 1
        )
        self.assertIsNotNone(outcome.tip_tag, "the tip tag was still made")

    def test_nothing_is_written_when_the_run_record_was_not_saved(self) -> None:
        net = world()
        net.on("GET", r"/git/trees/", ok({"message": "Not Found"}, 404))
        outcome = execute(net, policy_text([TARGET]))
        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(net.to("PUT", "/contents/runs-extra/"), [])
        self.assertIsNone(outcome.extra_path)

    def test_nothing_is_written_when_the_policy_could_not_be_read(self) -> None:
        net = world()
        execute(net, "")
        self.assertEqual(net.to("PUT", "/contents/runs-extra/"), [])

    def test_the_job_summary_names_it(self) -> None:
        net = world()
        artifact(
            net,
            spdx_doc([("lodash", "4.17.20", "pkg:npm/lodash@4.17.20")]),
            {"generation.json": '{"skipped_paths": ["a", "b"]}'},
        )
        outcome = execute(net, policy_text([TARGET]))
        lines = aggregator.render_summary(outcome).splitlines()
        self.assertIn("- run extra record: runs-extra/2026/01/1000-1.json", lines)
        self.assertIn("- repositories with skipped_paths recorded: 1", lines)
        self.assertIn("- pilot issued: 0", lines)
        self.assertEqual(
            len([x for x in lines if "extra" in x or "pilot" in x or "skipped" in x]),
            3,
            "no body is added to the summary",
        )

    def test_the_summary_says_when_it_was_not_saved(self) -> None:
        net = world()
        net.on("PUT", r"/contents/runs-extra/", ok({"message": "no"}, 422))
        outcome = execute(net, policy_text([TARGET]))
        self.assertIn(
            "- run extra record: not saved", aggregator.render_summary(outcome)
        )


# --- the pilot record ------------------------------------------------------------------------------


def cve_of(index: int) -> str:
    return f"CVE-2021-{2000 + index}"


def pilot_world(
    count: int,
    decided: int = 0,
    false_positives: int = 0,
    *,
    existing: int | None = None,
    created_at: Any = None,
    targets: list[str] | None = None,
    extra_items: list[dict[str, Any]] | None = None,
) -> FakeNet:
    """``count`` HIGH findings; the first ``existing`` (default all) already have an Issue.

    The first ``decided`` findings are excluded by one VEX document (``not_affected``); the first
    ``false_positives`` of those say ``component_not_present`` and the rest ``vulnerable_code_not_present``.
    """
    net = world(targets)
    net.on(
        "GET",
        r"/dependency-graph/sbom$",
        ok(
            {
                "sbom": spdx_doc(
                    [
                        (f"pkg{i}", "1.0.0", f"pkg:npm/pkg{i}@1.0.0")
                        for i in range(count)
                    ]
                )
            }
        ),
    )
    net.on(
        "GET",
        rf"/repos/{TARGET}/dependabot/alerts",
        ok(
            [
                alert(cve=cve_of(i), name=f"pkg{i}", ghsa_id=f"GHSA-aaaa-bbbb-{i:04d}")
                for i in range(count)
            ]
        ),
    )
    stamp = iso(NOW - timedelta(days=10))
    items = []
    for i in range(count if existing is None else existing):
        body = finding_issue_body(cve_of(i), kev=False, severity="HIGH")
        items.append(
            issue_item(
                i + 1,
                body,
                title=f"[supply-chain] {cve_of(i)}",
                created_at=created_at(i) if created_at else stamp,
            )
        )
    net.on("GET", rf"/repos/{TARGET}/issues\?", ok([*items, *(extra_items or [])]))
    if decided:
        statements = [
            {
                "vulnerability": {"name": cve_of(i)},
                "products": [{"@id": f"pkg:npm/pkg{i}@1.0.0"}],
                "status": "not_affected",
                "justification": "component_not_present"
                if i < false_positives
                else "vulnerable_code_not_present",
                "impact_statement": "reviewed",
                "timestamp": "2025-12-20T00:00:00Z",
            }
            for i in range(decided)
        ]
        doc = json.dumps(
            {
                "@context": "https://openvex.dev/ns/v0.2.0",
                "@id": "https://example.test/vex/pilot",
                "author": "VEX reviewer role",
                "timestamp": "2025-12-20T00:00:00Z",
                "version": 1,
                "statements": statements,
            }
        )
        net.on(
            "GET",
            rf"/repos/{TARGET}/contents/\.vex\?",
            ok([{"type": "file", "name": "p.json"}]),
        )
        net.on("GET", rf"/repos/{TARGET}/contents/\.vex/p\.json\?", file_response(doc))
        install_vex_approval(net, {"p.json": VEX_MERGED})
    return net


def observation_text(**fields: Any) -> str:
    return json.dumps({"schema_version": 1, **fields})


class PilotRecord(unittest.TestCase):
    """The pilot's counts and signals come from ``metrics``; this layer feeds them and writes them down."""

    def pilot(self, net: FakeNet, **kwargs: Any) -> dict[str, Any]:
        targets = kwargs.pop("targets", [TARGET])
        outcome = execute(net, policy_text(targets), **kwargs)
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        self.assertEqual(outcome.extra.pilot, extra_json(net)["pilot"])
        return outcome.extra.pilot

    def test_no_issue_at_all_still_writes_zero(self) -> None:
        pilot = self.pilot(world())
        self.assertEqual(pilot["rates"]["issued"], 0)
        self.assertTrue(pilot["review"]["applies"])
        self.assertFalse(pilot["review"]["next_batch_conditions_hold"])
        self.assertEqual(pilot["sli"], {"met": 0, "denominator": 0})
        self.assertEqual(pilot["issue_cap"], {"repos": [], "deferred_initial_bulk": 0})

    def test_nineteen_issues_give_no_rate_but_the_six_counts_and_two_signals(
        self,
    ) -> None:
        pilot = self.pilot(pilot_world(19, decided=19, false_positives=1))
        self.assertIsNone(pilot["rates"]["rate_percent"])
        self.assertEqual(
            pilot["counts"],
            {
                "issued": 19,
                "detector_errors": 1,
                "not_affected_other": 18,
                "fixed": 0,
                "affected": 0,
                "undecided": 0,
            },
        )
        review = pilot["review"]
        self.assertTrue(review["applies"])
        self.assertIs(review["errors_are_majority"], False)
        self.assertIs(review["next_batch_conditions_hold"], True)
        self.assertNotIn("passed", pilot)
        self.assertNotIn("verdict", pilot)

    def test_twenty_issues_with_a_quarter_undecided_withhold_the_rate(self) -> None:
        pilot = self.pilot(pilot_world(20, decided=15, false_positives=3))
        self.assertEqual(pilot["rates"]["issued"], 20)
        self.assertEqual(pilot["rates"]["undecided"], 5)
        self.assertTrue(pilot["rates"]["awaiting_decisions"])
        self.assertIsNone(pilot["rates"]["rate_percent"])

    def test_once_they_are_decided_the_rate_is_reported(self) -> None:
        pilot = self.pilot(pilot_world(20, decided=20, false_positives=3))
        self.assertFalse(pilot["rates"]["awaiting_decisions"])
        self.assertEqual(pilot["rates"]["false_positive"], 3)
        self.assertEqual(pilot["rates"]["not_affected_other"], 17)
        self.assertEqual(pilot["rates"]["rate_percent"], 15.0)
        self.assertFalse(pilot["review"]["applies"])

    def test_the_status_and_the_justification_come_from_the_excluding_statement(
        self,
    ) -> None:
        pilot = self.pilot(pilot_world(3, decided=2, false_positives=1))
        rates = pilot["rates"]
        self.assertEqual(
            (rates["false_positive"], rates["not_affected_other"], rates["undecided"]),
            (1, 1, 1),
        )

    def test_the_sli_leaves_out_not_affected_and_withdrawn_issues(self) -> None:
        closed = []
        for number, reason in ((50, "completed"), (51, "not_planned")):
            vuln = f"CVE-2021-{5000 + number}"
            item = issue_item(
                number,
                finding_issue_body(vuln, kev=False, severity="HIGH"),
                state="closed",
                title=f"[supply-chain] {vuln}",
                created_at=iso(NOW - timedelta(days=10)),
                closed_at=iso(NOW - timedelta(days=1)),
            )
            item["state_reason"] = reason
            closed.append(item)
        # three Issues close as vex_not_affected in this run; of the two closed before it, one was a fix
        # made in time (counted, met) and one was closed without a fix (left out)
        net = pilot_world(3, decided=3, extra_items=closed)
        self.assertEqual(self.pilot(net)["sli"], {"met": 1, "denominator": 1})

    def test_an_issue_opened_after_the_window_is_carried_over_not_undecided(
        self,
    ) -> None:
        def created(i: int) -> str:
            return iso(NOW - timedelta(days=10 if i < 15 else 1))

        net = pilot_world(20, decided=15, created_at=created)
        window = observation_text(window_end=iso(NOW - timedelta(days=5)))
        pilot = self.pilot(net, observation=window)
        rates = pilot["rates"]
        self.assertEqual(rates["carried_over"], 5)
        self.assertEqual(rates["undecided"], 0)
        self.assertEqual(rates["issued"], 15)
        self.assertEqual(
            pilot["observation"]["window_end"], iso(NOW - timedelta(days=5))
        )

    def test_an_issue_opened_before_the_window_start_is_not_counted(self) -> None:
        net = pilot_world(4, decided=4)
        window = observation_text(window_start=iso(NOW - timedelta(days=1)))
        rates = self.pilot(net, observation=window)["rates"]
        self.assertEqual(rates["before_window"], 4)
        self.assertEqual(rates["issued"], 0)

    def test_an_issue_without_a_creation_time_and_a_window_is_an_error_not_a_guess(
        self,
    ) -> None:
        def untimed() -> FakeNet:
            return pilot_world(3, decided=3, created_at=lambda i: None)

        net = untimed()
        outcome = execute(
            net,
            policy_text([TARGET]),
            observation=observation_text(window_end=iso(NOW)),
        )
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        self.assertEqual(list(outcome.extra.pilot), ["error"])
        self.assertIn("opened_at", outcome.extra.pilot["error"])
        self.assertTrue(any("pilot" in m for m in outcome.messages), outcome.messages)
        self.assertEqual(extra_json(net)["pilot"], outcome.extra.pilot)
        # without a window the same Issues are counted
        self.assertEqual(self.pilot(untimed())["rates"]["issued"], 3)

    def test_test_issues_and_issues_of_other_repositories_are_not_counted(self) -> None:
        net = pilot_world(3, decided=3, targets=[TARGET, OTHER])
        other = [
            issue_item(
                n,
                finding_issue_body(f"CVE-2021-{7000 + n}", kev=False, repo=OTHER),
                title=f"[supply-chain] CVE-2021-{7000 + n}",
                created_at=iso(NOW - timedelta(days=10)),
            )
            for n in (1, 2)
        ]
        net.on("GET", rf"/repos/{OTHER}/issues\?", ok(other))
        observation = observation_text(
            observed_repos=[TARGET], test_issues=[f"{TARGET}#2", f"{OTHER}#1"]
        )
        pilot = self.pilot(net, targets=[TARGET, OTHER], observation=observation)
        self.assertEqual(pilot["counts"]["issued"], 2)
        self.assertEqual(pilot["excluded_test_issues"], 2)
        self.assertEqual(pilot["excluded_outside_observation"], 1)
        self.assertEqual(pilot["observation"]["observed_repos"], [TARGET])

    def test_without_observed_repos_every_policy_repository_counts(self) -> None:
        net = pilot_world(2, decided=2, targets=[TARGET, OTHER])
        other = issue_item(
            1,
            finding_issue_body("CVE-2021-7001", kev=False, repo=OTHER),
            title="[supply-chain] CVE-2021-7001",
            created_at=iso(NOW - timedelta(days=10)),
        )
        net.on("GET", rf"/repos/{OTHER}/issues\?", ok([other]))
        pilot = self.pilot(net, targets=[TARGET, OTHER])
        self.assertEqual(pilot["counts"]["issued"], 3)
        self.assertEqual(pilot["excluded_outside_observation"], 0)

    def test_a_detector_error_named_in_the_input_is_counted_as_one(self) -> None:
        net = pilot_world(3, decided=0)
        pilot = self.pilot(
            net, observation=observation_text(detector_error_issues=[f"{TARGET}#1"])
        )
        self.assertEqual(pilot["counts"]["detector_errors"], 1)
        self.assertEqual(pilot["counts"]["undecided"], 2)

    def test_an_issue_that_is_not_a_finding_issue_by_title_is_not_counted(self) -> None:
        item = issue_item(
            9,
            finding_issue_body("CVE-2021-9999", kev=False, severity="HIGH"),
            title="Something else",
            created_at=iso(NOW - timedelta(days=10)),
        )
        net = pilot_world(2, decided=0, extra_items=[item])
        self.assertEqual(self.pilot(net)["counts"]["issued"], 2)

    def test_the_duplicate_side_is_counted_as_a_duplicate_only(self) -> None:
        keep = finding_issue_body("CVE-2021-0001", kev=False, severity="HIGH")
        dup = finding_issue_body("GHSA-aaaa-bbbb-cccc", kev=False, severity="HIGH")
        stamp = iso(NOW - timedelta(days=10))
        net = world()
        net.on("GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert()]))
        net.on(
            "GET",
            rf"/repos/{TARGET}/issues\?",
            ok(
                [
                    issue_item(
                        7,
                        keep,
                        title="[supply-chain] CVE-2021-0001",
                        created_at=stamp,
                    ),
                    issue_item(
                        8,
                        dup,
                        title="[supply-chain] GHSA-aaaa-bbbb-cccc",
                        created_at=stamp,
                    ),
                ]
            ),
        )
        pilot = self.pilot(net)
        self.assertEqual(pilot["rates"]["duplicates"], 1)
        self.assertEqual(pilot["rates"]["issued"], 1)
        self.assertEqual(pilot["rates"]["undecided"], 1)

    def test_an_issue_opened_by_this_run_is_counted(self) -> None:
        net = world()
        net.on("GET", rf"/repos/{TARGET}/dependabot/alerts", ok([alert()]))
        pilot = self.pilot(net)
        self.assertEqual(len(net.to("POST", f"/repos/{TARGET}/issues")), 1)
        self.assertEqual(pilot["rates"]["issued"], 1)
        self.assertEqual(pilot["rates"]["undecided"], 1)

    def test_three_restarts_require_a_redesign(self) -> None:
        pilot = self.pilot(world(), observation=observation_text(restarts_done=3))
        self.assertIs(pilot["restart"]["redesign_required"], True)
        self.assertEqual(pilot["restart"]["remaining"], 0)
        self.assertIs(pilot["review"]["may_restart_now"], False)

    def test_the_limits_of_the_input_reach_the_review(self) -> None:
        pilot = self.pilot(
            pilot_world(3, decided=0),
            observation=observation_text(
                extensions_exhausted=True, max_rate_percent=10
            ),
        )
        self.assertEqual(pilot["observation"]["max_rate_percent"], 10)
        self.assertIs(pilot["observation"]["extensions_exhausted"], True)
        world_empty = self.pilot(
            world(), observation=observation_text(extensions_exhausted=True)
        )
        self.assertIn(
            "no_issues_after_extensions", world_empty["review"]["restart_causes"]
        )

    def test_no_input_file_means_no_window(self) -> None:
        pilot = self.pilot(pilot_world(2, decided=2))
        self.assertIs(pilot["observation"]["input_file"], False)
        self.assertIsNone(pilot["observation"]["window_start"])
        self.assertIsNone(pilot["observation"]["window_end"])
        self.assertEqual(pilot["rates"]["issued"], 2)

    def test_an_input_that_cannot_be_used_is_an_error_and_the_run_goes_on(self) -> None:
        bad = {
            "not JSON": "{ nope",
            "empty (unreadable file)": "",
            "not an object": "[]",
            "wrong version": json.dumps({"schema_version": 2}),
            "unknown key": observation_text(restarts_don=1),
            "negative restarts": observation_text(restarts_done=-1),
            "restarts as text": observation_text(restarts_done="1"),
            "flag as text": observation_text(extensions_exhausted="yes"),
            "rate as text": observation_text(max_rate_percent="5"),
            "bad time": observation_text(window_end="yesterday"),
            "time without a zone": observation_text(window_end="2026-01-01T00:00:00"),
            "repo list as text": observation_text(observed_repos="a/b"),
            "bad repo": observation_text(observed_repos=["nope"]),
            "bad issue reference": observation_text(test_issues=["a/b#0"]),
            "window reversed": observation_text(
                window_start=iso(NOW), window_end=iso(NOW - timedelta(days=1))
            ),
        }
        for label, text in bad.items():
            with self.subTest(label):
                net = pilot_world(2, decided=2)
                outcome = execute(net, policy_text([TARGET]), observation=text)
                self.assertEqual(outcome.exit_code, 0, outcome.messages)
                self.assertEqual(outcome.record.end_state, "success")
                self.assertEqual(list(outcome.extra.pilot), ["error"])
                self.assertEqual(
                    len([m for m in outcome.messages if "pilot" in m]),
                    1,
                    outcome.messages,
                )
                self.assertEqual(extra_json(net)["pilot"], outcome.extra.pilot)
                self.assertEqual(
                    len(net.to("PUT", "/contents/runs/")),
                    1,
                    "the run record is the same",
                )


class IssueCapCause(unittest.TestCase):
    """Why the per-run limit was reached: the first run in a repository, or a run after it."""

    def cap(self, net: FakeNet) -> dict[str, Any]:
        outcome = execute(net, policy_text([TARGET], limit=1))
        self.assertEqual(outcome.exit_code, 0, outcome.messages)
        return outcome.extra.pilot["issue_cap"]

    def test_a_repository_with_no_managed_issue_is_an_initial_bulk(self) -> None:
        cap = self.cap(pilot_world(3, existing=0))
        self.assertEqual(
            cap,
            {
                "repos": [{"repo": TARGET, "overflow": 2, "cause": "initial_bulk"}],
                "deferred_initial_bulk": 2,
            },
        )

    def test_a_repository_that_has_managed_issues_is_ongoing(self) -> None:
        cap = self.cap(pilot_world(3, existing=1))
        self.assertEqual(
            cap,
            {
                "repos": [{"repo": TARGET, "overflow": 1, "cause": "ongoing"}],
                "deferred_initial_bulk": 0,
            },
        )

    def test_a_closed_managed_issue_also_makes_it_ongoing(self) -> None:
        net = pilot_world(3, existing=0)
        body = finding_issue_body("CVE-2021-8000", kev=False, severity="HIGH")
        net.on(
            "GET",
            rf"/repos/{TARGET}/issues\?",
            ok(
                [
                    issue_item(
                        90, body, state="closed", title="[supply-chain] CVE-2021-8000"
                    )
                ]
            ),
        )
        self.assertEqual(self.cap(net)["repos"][0]["cause"], "ongoing")

    def test_nothing_over_the_limit_leaves_the_list_empty(self) -> None:
        self.assertEqual(
            self.cap(pilot_world(1, existing=0)),
            {"repos": [], "deferred_initial_bulk": 0},
        )

    def test_the_findings_over_the_limit_come_back_in_the_next_run(self) -> None:
        first = pilot_world(3, existing=0)
        execute(first, policy_text([TARGET], limit=1))
        opened_first = [
            c.body["title"]
            for c in first.to("POST", f"/repos/{TARGET}/issues")
            if c.url.endswith("/issues")
            and c.body["title"].startswith("[supply-chain] CVE")
        ]
        second = pilot_world(3, existing=1)
        execute(second, policy_text([TARGET], limit=1))
        opened_second = [
            c.body["title"]
            for c in second.to("POST", f"/repos/{TARGET}/issues")
            if c.url.endswith("/issues")
            and c.body["title"].startswith("[supply-chain] CVE")
        ]
        self.assertEqual(opened_first, [f"[supply-chain] {cve_of(0)}"])
        self.assertEqual(opened_second, [f"[supply-chain] {cve_of(1)}"])


class ObservationFile(unittest.TestCase):
    def test_the_path_is_the_override_or_the_file_beside_the_policy(self) -> None:
        self.assertEqual(
            aggregator.observation_path("policy/docs/agent/p.json", "x/obs.json"),
            "x/obs.json",
        )
        self.assertEqual(
            aggregator.observation_path("policy/docs/agent/p.json", None),
            "policy/docs/agent/supply-chain-observation.json",
        )
        self.assertEqual(
            aggregator.observation_path("policy/docs/agent/p.json", ""),
            "policy/docs/agent/supply-chain-observation.json",
        )

    def test_a_missing_file_is_no_input_and_a_present_one_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "obs.json"
            self.assertIsNone(aggregator.read_observation(str(path)))
            path.write_text('{"schema_version": 1}', encoding="utf-8")
            self.assertEqual(
                aggregator.read_observation(str(path)), '{"schema_version": 1}'
            )

    def test_a_file_that_cannot_be_decoded_is_an_unusable_input_not_an_absent_one(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "obs.json"
            path.write_bytes(b"\xff\xfe\x00")
            self.assertEqual(aggregator.read_observation(str(path)), "")


class Helpers(unittest.TestCase):
    def test_the_fake_refuses_an_unrouted_request(self) -> None:
        with self.assertRaises(AssertionError):
            FakeNet().request("GET", "https://example.test/x", {}, None)

    def test_a_policy_fixture_parses(self) -> None:
        from supply_chain.policy import parse_policy

        self.assertEqual(
            len(parse_policy(policy_text([TARGET])).target_repositories), 1
        )


if __name__ == "__main__":
    unittest.main()
