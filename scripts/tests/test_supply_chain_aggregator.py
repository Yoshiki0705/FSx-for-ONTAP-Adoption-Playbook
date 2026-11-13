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
* the watchdog appends to the open failure Issue instead of opening a second one.
"""

from __future__ import annotations

import base64
import gzip
import io
import json
import re
import sys
import unittest
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from supply_chain import issue_body, models, run_record
from supply_chain.models import Repo
from supply_chain_aggregator import Config, notify_failure, run
from supply_chain_io import (
    Client,
    GitHubApi,
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
SHA = "a" * 40
POLICY_SHA = "b" * 40
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
            "package_manager_wait": {"default_days": 3, "major_days": 7},
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
        "name": "example",
        "documentDescribes": ["SPDXRef-root"],
        "creationInfo": {
            "created": "2026-01-01T00:00:00Z",
            "creators": ["Tool: example-1.0"],
        },
        "packages": packages,
        "relationships": rels,
    }


def alert(
    cve: str = "CVE-2021-0001", severity: str = "high", name: str = "lodash"
) -> dict[str, Any]:
    return {
        "number": 1,
        "state": "open",
        "security_advisory": {
            "ghsa_id": "GHSA-aaaa-bbbb-cccc",
            "cve_id": cve,
            "severity": severity,
            "published_at": "2025-12-01T00:00:00Z",
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
    vuln_id: str, *, kev: bool, repo: str = TARGET, severity: str | None = None
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
            opened_at=NOW,
            due_at=NOW,
            last_run_id="999-1",
            history=(issue_body.HistoryEntry("open", "999-1", NOW),),
        )
    )


def issue_item(number: int, body: str, state: str = "open") -> dict[str, Any]:
    return {
        "number": number,
        "state": state,
        "body": body,
        "labels": [{"name": "supply-chain-aggregator"}],
    }


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
    net.on("PUT", rf"/repos/{hub}/contents/runs/", ok({"content": {}}, 201))
    net.on("GET", rf"/repos/{hub}/issues\?", ok([]))
    for repo in repos:
        net.on("GET", rf"/repos/{repo}/issues\?", ok([]))
    return net


def execute(net: FakeNet, policy: str, *, sleeps: list[float] | None = None) -> Any:
    log = sleeps if sleeps is not None else []
    client = Client(net, sleep=log.append, clock=lambda: 0.0)
    cfg = Config(HUB, RUN_ID, SHA, policy, POLICY_SHA)
    return run(
        cfg,
        spoke=GitHubApi(client, SPOKE_TOKEN),
        hub=GitHubApi(client, HUB_TOKEN),
        client=client,
        osv=Osv(client),
        now_fn=lambda: NOW,
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
            if "/contents/runs/" in call.url:
                self.assertEqual(call.token, HUB_TOKEN)
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
