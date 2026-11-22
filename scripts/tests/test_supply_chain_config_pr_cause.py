"""A detector error is one cause when one pull request that changed the detector's configuration fixed it.

The Aggregator names the cause of a detector error from what it reads on GitHub: the pull requests merged
into the default branch between the opening and the closing of a resolved Issue. When exactly one of them
changed a file that configures the detector, the Issue's cause is ``config-pr:<owner>/<name>#<number>``, and
the Issues that pull request closed are one cause. In every other case the Issue stays its own cause, which
counts the errors on the high side. Nothing is guessed.

No test reaches the network. The fake HTTP layer is the one of ``test_supply_chain_aggregator.py``.
The functions under test are reached through the ``aggregator`` module, so that on code that does not have them
a test fails on its own assertion or attribute and not on an import of the whole file.
"""

from __future__ import annotations

import json
import sys
import unittest
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import supply_chain_aggregator as aggregator
from supply_chain import models
from supply_chain.models import Repo
from supply_chain_io import Client, GitHubApi, RateLimited, Response

from scripts.tests.test_supply_chain_aggregator import (
    NOW,
    OTHER,
    SPOKE_TOKEN,
    TARGET,
    FakeNet,
    execute,
    finding_issue_body,
    issue_item,
    ok,
    policy_text,
    world,
)

REPO = Repo(*TARGET.split("/"))
OTHER_REPO = Repo(*OTHER.split("/"))
OPENED = NOW - timedelta(days=10)
CLOSED = NOW - timedelta(days=3)
INSIDE = NOW - timedelta(days=5)
API_ROOT = "https://api.github.com"


def iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def key_of(number: int, repo: str = TARGET) -> str:
    return f"config-pr:{repo}#{number}"


def pull(
    number: int,
    merged_at: datetime | None,
    *,
    updated_at: datetime | None = None,
    base: str = "main",
) -> dict[str, Any]:
    """One item of ``GET /pulls?state=closed``: ``merged_at`` is ``None`` for a pull request closed unmerged."""
    updated = updated_at or merged_at or NOW - timedelta(days=1)
    return {
        "number": number,
        "merged_at": iso(merged_at) if merged_at else None,
        "updated_at": iso(updated),
        "base": {"ref": base},
    }


def changed(name: str, previous: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"filename": name}
    if previous is not None:
        item["previous_filename"] = previous
    return item


def resolved(
    numbers: tuple[int, ...] = (1, 2, 3),
    repo: Repo = REPO,
    opened: datetime = OPENED,
    closed: datetime = CLOSED,
) -> list[Any]:
    return [aggregator.ResolvedIssue(repo, n, opened, closed) for n in numbers]


def api_for(net: FakeNet) -> GitHubApi:
    return GitHubApi(
        Client(net, sleep=lambda _seconds: None, clock=lambda: 0.0), SPOKE_TOKEN
    )


def net_with(
    pulls: list[dict[str, Any]],
    files: dict[int, list[Any]] | None = None,
    repo: str = TARGET,
) -> FakeNet:
    """A network that lists ``pulls`` and, per pull request number, its changed files (strings or items)."""
    net = FakeNet()
    net.on("GET", rf"/repos/{repo}/pulls\?", ok(pulls))
    for number, names in (files or {}).items():
        items = [changed(n) if isinstance(n, str) else n for n in names]
        net.on("GET", rf"/repos/{repo}/pulls/{number}/files\?", ok(items))
    return net


def causes(
    net: FakeNet,
    issues: list[Any] | None = None,
    branches: dict[Repo, str | None] | None = None,
) -> tuple[dict[tuple[Repo, int], str], list[str]]:
    return aggregator.config_pr_causes(
        api_for(net),
        issues if issues is not None else resolved(),
        branches if branches is not None else {REPO: "main"},
    )


def page_of(url: str) -> int:
    values = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("page")
    return int(values[0]) if values else 1


def paged(
    items_of_page: Any, last_page: int, repo: str = TARGET, path: str = "pulls"
) -> Any:
    """A route answering with ``items_of_page(page)`` and a ``Link`` header to the next page up to ``last_page``."""

    def answer(url: str, _payload: Any) -> Response:
        page = page_of(url)
        headers = {}
        if page < last_page:
            target = f"{API_ROOT}/repos/{repo}/{path}?page={page + 1}"
            headers["link"] = f'<{target}>; rel="next"'
        return ok(items_of_page(page), headers=headers)

    return answer


class DetectorConfigPaths(unittest.TestCase):
    """The paths that configure the detector, as one list in one place."""

    def test_every_listed_shape_is_a_configuration_path(self) -> None:
        for path in (
            ".github/workflows/sbom.yml",
            ".github/workflows/sbom.yaml",
            ".github/workflows/sbom-generate.yml",
            ".github/workflows/sbom-x.yaml",
            "docs/agent/supply-chain-policy.json",
            "renovate.json",
            "renovate.json5",
            ".renovaterc",
            ".renovaterc.json",
            ".github/renovate.json",
            ".github/renovate.json5",
            ".gitlab/renovate.json",
            ".gitlab/renovate.json5",
        ):
            with self.subTest(path=path):
                self.assertTrue(aggregator.is_detector_config_path(path))

    def test_everything_else_is_not(self) -> None:
        for path in (
            ".vex/a.json",
            ".vex/renovate.json",
            ".github/workflows/ci.yml",
            ".github/workflows/sbom/x.yml",
            ".github/workflows/mysbom.yml",
            ".github/workflows/SBOM.yml",
            ".github/workflows/sbom.json",
            "sbom/readme.md",
            "sbom.yml",
            "README.md",
            "docs/x.md",
            "docs/agent/supply-chain-policy.json.bak",
            "docs/supply-chain-policy.json",
            "sub/renovate.json",
            "Renovate.json",
        ):
            with self.subTest(path=path):
                self.assertFalse(aggregator.is_detector_config_path(path))

    def test_the_list_is_one_constant_and_leaves_out_the_vex_directory(self) -> None:
        listed = aggregator.DETECTOR_CONFIG_PATHS
        self.assertIsInstance(listed, tuple | frozenset)
        self.assertFalse([p for p in listed if p.startswith(".vex")])
        self.assertIn("D-79", aggregator.is_detector_config_path.__doc__ or "")

    def test_the_previous_name_of_a_renamed_file_counts(self) -> None:
        self.assertTrue(
            aggregator.touches_detector_config(
                [changed("docs/old.md"), changed("docs/new.md", "renovate.json")]
            )
        )

    def test_the_new_name_of_a_renamed_file_counts(self) -> None:
        self.assertTrue(
            aggregator.touches_detector_config(
                [changed("renovate.json", "docs/old.md")]
            )
        )

    def test_files_that_are_not_configuration_do_not(self) -> None:
        self.assertFalse(
            aggregator.touches_detector_config(
                [changed("README.md"), changed("docs/b.md", "docs/a.md")]
            )
        )
        self.assertFalse(aggregator.touches_detector_config([]))


class ConfigPrCauses(unittest.TestCase):
    """The rule of the cause, one Issue at a time and with no state."""

    def test_one_config_pr_is_the_cause_of_every_issue_it_preceded(self) -> None:
        net = net_with([pull(12, INSIDE)], {12: [".github/workflows/sbom.yml"]})
        found, notes = causes(net)
        self.assertEqual(found, {(REPO, n): key_of(12) for n in (1, 2, 3)})
        self.assertEqual(notes, [])

    def test_a_single_issue_gets_the_value_too(self) -> None:
        net = net_with(
            [pull(12, INSIDE)], {12: ["docs/agent/supply-chain-policy.json"]}
        )
        found, _notes = causes(net, resolved((7,)))
        self.assertEqual(found, {(REPO, 7): key_of(12)})

    def test_no_pull_request_in_the_window_gives_no_cause(self) -> None:
        found, notes = causes(net_with([]))
        self.assertEqual(found, {})
        self.assertEqual(notes, [])

    def test_two_config_prs_give_no_cause(self) -> None:
        net = net_with(
            [pull(12, INSIDE), pull(13, INSIDE + timedelta(hours=1))],
            {12: ["renovate.json"], 13: [".github/workflows/sbom.yml"]},
        )
        found, _notes = causes(net)
        self.assertEqual(found, {})

    def test_pull_requests_that_change_no_configuration_give_no_cause(self) -> None:
        for names in (["README.md"], ["docs/x.md"], [".vex/a.json"]):
            with self.subTest(names=names):
                found, _notes = causes(net_with([pull(12, INSIDE)], {12: names}))
                self.assertEqual(found, {})

    def test_a_pull_request_that_changes_no_configuration_does_not_hide_the_one_that_does(
        self,
    ) -> None:
        net = net_with(
            [pull(12, INSIDE), pull(13, INSIDE + timedelta(hours=1))],
            {12: ["README.md"], 13: ["renovate.json"]},
        )
        found, _notes = causes(net)
        self.assertEqual(found, {(REPO, n): key_of(13) for n in (1, 2, 3)})

    def test_the_window_is_after_opening_and_up_to_closing(self) -> None:
        cases = {
            "after the closing": (CLOSED + timedelta(seconds=1), False),
            "at the closing": (CLOSED, True),
            "just after the opening": (OPENED + timedelta(seconds=1), True),
            "at the opening": (OPENED, False),
            "before the opening": (OPENED - timedelta(days=1), False),
        }
        for label, (merged, counted) in cases.items():
            with self.subTest(label):
                net = net_with([pull(12, merged)], {12: ["renovate.json"]})
                found, _notes = causes(net, resolved((1,)))
                self.assertEqual(found, {(REPO, 1): key_of(12)} if counted else {})
                self.assertEqual(len(net.to("GET", "/pulls/12/files")), int(counted))

    def test_a_pull_request_closed_without_merging_is_ignored(self) -> None:
        net = net_with([pull(12, None, updated_at=INSIDE)], {12: ["renovate.json"]})
        found, _notes = causes(net)
        self.assertEqual(found, {})
        self.assertEqual(net.to("GET", "/files"), [])

    def test_a_pull_request_into_another_branch_is_ignored(self) -> None:
        net = net_with([pull(12, INSIDE, base="develop")], {12: ["renovate.json"]})
        self.assertEqual(causes(net)[0], {})

    def test_each_issue_has_its_own_window(self) -> None:
        later = [aggregator.ResolvedIssue(REPO, 9, INSIDE + timedelta(days=1), CLOSED)]
        net = net_with([pull(12, INSIDE)], {12: ["renovate.json"]})
        found, _notes = causes(net, [*resolved((1,)), *later])
        self.assertEqual(found, {(REPO, 1): key_of(12)})

    def test_the_files_of_a_pull_request_are_listed_once_for_all_its_issues(
        self,
    ) -> None:
        net = net_with([pull(12, INSIDE)], {12: ["renovate.json"]})
        causes(net)
        self.assertEqual(len(net.to("GET", "/pulls/12/files")), 1)

    def test_another_repository_is_another_cause_even_with_the_same_number(
        self,
    ) -> None:
        net = net_with([pull(7, INSIDE)], {7: ["renovate.json"]}, TARGET)
        net.on("GET", rf"/repos/{OTHER}/pulls\?", ok([pull(7, INSIDE)]))
        net.on(
            "GET",
            rf"/repos/{OTHER}/pulls/7/files\?",
            ok([changed(".github/workflows/sbom.yml")]),
        )
        found, _notes = causes(
            net,
            [*resolved((1, 2)), *resolved((1, 2), OTHER_REPO)],
            {REPO: "main", OTHER_REPO: "main"},
        )
        self.assertEqual(found[(REPO, 1)], key_of(7, TARGET))
        self.assertEqual(found[(OTHER_REPO, 1)], key_of(7, OTHER))
        self.assertNotEqual(found[(REPO, 1)], found[(OTHER_REPO, 1)])
        self.assertEqual(len(found), 4)

    def test_the_list_is_asked_for_in_the_documented_form(self) -> None:
        net = net_with([])
        causes(net)
        (call,) = net.to("GET", "/pulls?")
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(call.url).query)
        self.assertEqual(
            {k: v[0] for k, v in query.items()},
            {
                "state": "closed",
                "base": "main",
                "sort": "updated",
                "direction": "desc",
                "per_page": "100",
            },
        )
        self.assertEqual(call.method, "GET")

    def test_nothing_is_written(self) -> None:
        net = net_with([pull(12, INSIDE)], {12: ["renovate.json"]})
        causes(net)
        self.assertEqual([c for c in net.calls if c.method != "GET"], [])

    def test_an_unknown_default_branch_gives_no_cause_and_a_note(self) -> None:
        net = net_with([pull(12, INSIDE)], {12: ["renovate.json"]})
        found, notes = causes(net, branches={REPO: None})
        self.assertEqual(found, {})
        self.assertEqual(len(notes), 1)
        self.assertIn(TARGET, notes[0])
        self.assertEqual(net.calls, [])

    def test_an_issue_without_an_opening_time_is_left_without_a_cause(self) -> None:
        net = net_with([pull(12, INSIDE)], {12: ["renovate.json"]})
        issues = [aggregator.ResolvedIssue(REPO, 1, None, CLOSED)]
        self.assertEqual(causes(net, issues)[0], {})


class ConfigPrCausesFailToNone(unittest.TestCase):
    """Whatever cannot be read, or cannot be read to the end, is not guessed."""

    def test_a_refused_list_gives_no_cause_a_note_and_no_exception(self) -> None:
        net = FakeNet()
        net.on("GET", r"/pulls\?", ok({"message": "Not Found"}, 404))
        found, notes = causes(net)
        self.assertEqual(found, {})
        self.assertEqual(len(notes), 1)
        self.assertIn(TARGET, notes[0])

    def test_one_repository_failing_does_not_stop_the_next(self) -> None:
        net = net_with([pull(7, INSIDE)], {7: ["renovate.json"]}, OTHER)
        net.on("GET", rf"/repos/{TARGET}/pulls\?", ok({"message": "x"}, 404))
        found, notes = causes(
            net,
            [*resolved((1,)), *resolved((1,), OTHER_REPO)],
            {REPO: "main", OTHER_REPO: "main"},
        )
        self.assertEqual(found, {(OTHER_REPO, 1): key_of(7, OTHER)})
        self.assertEqual(len(notes), 1)

    def test_a_list_item_that_cannot_be_read_gives_no_cause(self) -> None:
        for bad in ({"merged_at": None}, "text", {"number": "x", "updated_at": "y"}):
            with self.subTest(bad=bad):
                found, notes = causes(net_with([bad]))
                self.assertEqual(found, {})
                self.assertEqual(len(notes), 1)

    def test_a_refused_file_list_gives_no_cause_for_the_issues_it_decides(
        self,
    ) -> None:
        net = net_with([pull(12, INSIDE)])
        net.on("GET", r"/pulls/12/files\?", ok({"message": "x"}, 404))
        found, notes = causes(net)
        self.assertEqual(found, {})
        self.assertEqual(len(notes), 1)
        self.assertEqual(len(net.to("GET", "/pulls/12/files")), 1)

    def test_a_pull_request_that_cannot_be_read_is_not_ruled_out(self) -> None:
        """Another pull request that does change the configuration is not enough: the unread one might too."""
        net = net_with(
            [pull(12, INSIDE), pull(13, INSIDE + timedelta(hours=1))],
            {13: ["renovate.json"]},
        )
        net.on("GET", r"/pulls/12/files\?", ok({"message": "x"}, 404))
        self.assertEqual(causes(net)[0], {})

    def test_a_list_not_read_to_its_end_within_the_limit_gives_no_cause(self) -> None:
        net = FakeNet()
        net.on(
            "GET",
            r"/pulls\?",
            paged(
                lambda page: [
                    pull(page * 1000 + i, None, updated_at=NOW - timedelta(days=1))
                    for i in range(100)
                ],
                last_page=50,
            ),
        )
        found, notes = causes(net)
        self.assertEqual(found, {})
        self.assertEqual(len(net.to("GET", "/pulls?")), aggregator.PR_LIST_PAGE_LIMIT)
        self.assertEqual(len(notes), 1)
        self.assertIn(TARGET, notes[0])

    def test_a_list_that_ends_before_the_limit_is_complete(self) -> None:
        net = FakeNet()
        net.on(
            "GET",
            r"/pulls\?",
            paged(
                lambda page: [
                    pull(page * 1000 + i, None, updated_at=NOW - timedelta(days=1))
                    for i in range(100)
                ],
                last_page=aggregator.PR_LIST_PAGE_LIMIT - 1,
            ),
        )
        net.on("GET", r"/pulls/\d+/files\?", ok([]))
        found, notes = causes(net)
        self.assertEqual(found, {})
        self.assertEqual(notes, [])
        self.assertEqual(
            len(net.to("GET", "/pulls?")), aggregator.PR_LIST_PAGE_LIMIT - 1
        )

    def test_paging_stops_once_the_list_is_older_than_the_oldest_opening(self) -> None:
        net = FakeNet()
        stale = pull(5, OPENED - timedelta(days=5))
        net.on(
            "GET",
            r"/pulls\?",
            paged(lambda page: [pull(12, INSIDE), stale], last_page=3),
        )
        net.on("GET", r"/pulls/12/files\?", ok([changed("renovate.json")]))
        found, notes = causes(net)
        self.assertEqual(found, {(REPO, n): key_of(12) for n in (1, 2, 3)})
        self.assertEqual(notes, [])
        self.assertEqual(len(net.to("GET", "/pulls?")), 1)

    def test_paging_goes_on_while_the_list_is_not_older_than_the_opening(self) -> None:
        net = FakeNet()
        net.on(
            "GET",
            r"/pulls\?",
            paged(
                lambda page: [pull(page, INSIDE + timedelta(minutes=page))],
                last_page=3,
            ),
        )
        net.on("GET", r"/pulls/\d+/files\?", ok([]))
        causes(net)
        self.assertEqual(len(net.to("GET", "/pulls?")), 3)

    def test_files_cut_at_the_api_maximum_without_a_config_file_give_no_cause(
        self,
    ) -> None:
        net = net_with([pull(12, INSIDE)])
        net.on(
            "GET",
            r"/pulls/12/files\?",
            paged(
                lambda page: [changed(f"d/{page}/{i}.md") for i in range(100)],
                last_page=30,
                path="pulls/12/files",
            ),
        )
        found, notes = causes(net)
        self.assertEqual(found, {})
        self.assertEqual(len(notes), 1)
        self.assertEqual(len(net.to("GET", "/pulls/12/files")), 30)

    def test_a_config_file_found_in_a_cut_list_still_decides(self) -> None:
        """A match is certain even when the list is cut; only the absence of one is not."""
        net = net_with([pull(12, INSIDE)])
        net.on(
            "GET",
            r"/pulls/12/files\?",
            paged(
                lambda page: [
                    changed("renovate.json" if page == 1 and i == 5 else f"d/{i}.md")
                    for i in range(100)
                ],
                last_page=30,
                path="pulls/12/files",
            ),
        )
        found, notes = causes(net, resolved((1,)))
        self.assertEqual(found, {(REPO, 1): key_of(12)})
        self.assertEqual(notes, [])

    def test_the_listings_of_files_of_one_repository_are_capped(self) -> None:
        pulls = [pull(n, INSIDE + timedelta(minutes=n)) for n in (1, 2, 3)]
        net = net_with(
            pulls, {1: ["README.md"], 2: ["README.md"], 3: ["renovate.json"]}
        )
        with mock.patch.object(aggregator, "PR_FILES_LISTING_LIMIT", 2):
            found, notes = causes(net)
        self.assertEqual(found, {})
        self.assertEqual(len(notes), 1)
        self.assertEqual(len(net.to("GET", "/files")), 2)

    def test_a_rate_limit_is_not_swallowed(self) -> None:
        net = FakeNet()
        net.on("GET", r"/pulls\?", Response(429, {"retry-after": "9999"}, b""))
        with self.assertRaises(RateLimited):
            causes(net)


def observation_text(**fields: Any) -> str:
    return json.dumps({"schema_version": 1, **fields})


def closed_issue(
    number: int,
    repo: str = TARGET,
    *,
    state: str = "closed",
    reason: str | None = "completed",
) -> dict[str, Any]:
    vuln = f"CVE-2021-{9000 + number}"
    item = issue_item(
        number,
        finding_issue_body(vuln, kev=False, repo=repo, severity="HIGH"),
        state=state,
        title=f"[supply-chain] {vuln}",
        created_at=iso(OPENED),
        closed_at=iso(CLOSED) if state == "closed" else None,
    )
    if reason is not None:
        item["state_reason"] = reason
    return item


def classified(numbers: tuple[int, ...], repo: str = TARGET) -> list[str]:
    return [f"{repo}#{n}" for n in numbers]


def pilot_of(net: FakeNet, observation: str, targets: list[str] | None = None) -> Any:
    outcome = execute(net, policy_text(targets or [TARGET]), observation=observation)
    if outcome.exit_code != 0:
        raise AssertionError(f"the run failed: {outcome.messages}")
    return outcome


def issues_in(net: FakeNet, repo: str, items: list[dict[str, Any]]) -> None:
    net.on("GET", rf"/repos/{repo}/issues\?", ok(items))


class PilotCauseThroughTheRun(unittest.TestCase):
    """What the pilot record says once ``run`` supplies the cause."""

    def scenario(
        self,
        pulls: list[dict[str, Any]],
        files: dict[int, list[Any]],
        **issue_args: Any,
    ) -> tuple[FakeNet, Any]:
        net = world()
        issues_in(net, TARGET, [closed_issue(n, **issue_args) for n in (1, 2, 3)])
        net.on("GET", rf"/repos/{TARGET}/pulls\?", ok(pulls))
        for number, names in files.items():
            net.on(
                "GET",
                rf"/repos/{TARGET}/pulls/{number}/files\?",
                ok([changed(n) for n in names]),
            )
        outcome = pilot_of(
            net, observation_text(detector_error_issues=classified((1, 2, 3)))
        )
        return net, outcome

    def counts(self, outcome: Any) -> tuple[int, int, int]:
        pilot = outcome.extra.pilot
        return (
            pilot["review"]["detector_errors"],
            pilot["review"]["detector_error_issues"],
            pilot["rates"]["false_positive_causes"],
        )

    def test_one_config_pr_makes_three_issues_one_cause(self) -> None:
        net, outcome = self.scenario(
            [pull(12, INSIDE)], {12: [".github/workflows/sbom.yml"]}
        )
        self.assertEqual(self.counts(outcome), (1, 3, 1))
        self.assertEqual(outcome.extra.pilot["rates"]["false_positive"], 3)
        self.assertEqual(outcome.extra.pilot["counts"]["detector_errors"], 3)
        self.assertEqual(outcome.extra.pilot["rates"]["issued"], 3)
        self.assertEqual(len(net.to("GET", "/pulls/12/files")), 1)

    def test_no_pull_request_leaves_every_issue_its_own_cause(self) -> None:
        _net, outcome = self.scenario([], {})
        self.assertEqual(self.counts(outcome), (3, 3, 3))

    def test_two_config_prs_leave_every_issue_its_own_cause(self) -> None:
        _net, outcome = self.scenario(
            [pull(12, INSIDE), pull(13, INSIDE + timedelta(hours=1))],
            {12: ["renovate.json"], 13: [".github/workflows/sbom.yml"]},
        )
        self.assertEqual(self.counts(outcome), (3, 3, 3))

    def test_pull_requests_that_change_no_configuration_leave_them_alone(self) -> None:
        for names in (["README.md"], ["docs/x.md"], [".vex/a.json"]):
            with self.subTest(names=names):
                _net, outcome = self.scenario([pull(12, INSIDE)], {12: names})
                self.assertEqual(self.counts(outcome), (3, 3, 3))

    def test_a_pull_request_outside_the_window_or_unmerged_is_ignored(self) -> None:
        for label, pulls in {
            "after the closing": [pull(12, CLOSED + timedelta(hours=1))],
            "before the opening": [pull(12, OPENED)],
            "unmerged": [pull(12, None, updated_at=INSIDE)],
        }.items():
            with self.subTest(label):
                _net, outcome = self.scenario(pulls, {12: ["renovate.json"]})
                self.assertEqual(self.counts(outcome), (3, 3, 3))

    def test_another_repository_is_another_cause(self) -> None:
        net = world([TARGET, OTHER])
        issues_in(net, TARGET, [closed_issue(n) for n in (1, 2)])
        issues_in(net, OTHER, [closed_issue(n, OTHER) for n in (1, 2)])
        for repo in (TARGET, OTHER):
            net.on("GET", rf"/repos/{repo}/pulls\?", ok([pull(7, INSIDE)]))
            net.on(
                "GET",
                rf"/repos/{repo}/pulls/7/files\?",
                ok([changed("renovate.json")]),
            )
        observation = observation_text(
            detector_error_issues=[*classified((1, 2)), *classified((1, 2), OTHER)]
        )
        outcome = pilot_of(net, observation, [TARGET, OTHER])
        self.assertEqual(self.counts(outcome), (2, 4, 2))

    def test_an_issue_the_detector_did_not_get_wrong_is_not_given_a_cause(self) -> None:
        """Closed as resolved but not a detector error (a fix): no pull request is even listed."""
        net = world()
        issues_in(net, TARGET, [closed_issue(n) for n in (1, 2, 3)])
        net.on("GET", rf"/repos/{TARGET}/pulls\?", ok([pull(12, INSIDE)]))
        outcome = pilot_of(net, observation_text())
        self.assertEqual(outcome.extra.pilot["rates"]["false_positive"], 0)
        self.assertEqual(net.to("GET", "/pulls?"), [])

    def test_an_issue_closed_as_not_planned_is_not_given_one(self) -> None:
        net = world()
        issues_in(
            net, TARGET, [closed_issue(n, reason="not_planned") for n in (1, 2, 3)]
        )
        net.on("GET", rf"/repos/{TARGET}/pulls\?", ok([pull(12, INSIDE)]))
        net.on(
            "GET",
            rf"/repos/{TARGET}/pulls/12/files\?",
            ok([changed("renovate.json")]),
        )
        outcome = pilot_of(
            net, observation_text(detector_error_issues=classified((1, 2, 3)))
        )
        self.assertEqual(self.counts(outcome), (3, 3, 3))
        self.assertEqual(net.to("GET", "/pulls?"), [])

    def test_a_refused_list_is_a_note_and_the_run_goes_on(self) -> None:
        net = world()
        issues_in(net, TARGET, [closed_issue(n) for n in (1, 2, 3)])
        net.on("GET", rf"/repos/{TARGET}/pulls\?", ok({"message": "Not Found"}, 404))
        outcome = pilot_of(
            net, observation_text(detector_error_issues=classified((1, 2, 3)))
        )
        self.assertEqual(self.counts(outcome), (3, 3, 3))
        self.assertTrue(
            any("config PR" in m for m in outcome.messages), outcome.messages
        )
        self.assertTrue(any("config PR" in w for w in outcome.extra.warnings))

    def test_a_rate_limit_is_recorded_like_the_others_and_stops_the_run(self) -> None:
        net = world()
        issues_in(net, TARGET, [closed_issue(n) for n in (1, 2, 3)])
        net.on(
            "GET",
            rf"/repos/{TARGET}/pulls\?",
            Response(429, {"retry-after": "9999"}, b""),
        )
        outcome = execute(
            net,
            policy_text([TARGET]),
            observation=observation_text(detector_error_issues=classified((1, 2, 3))),
        )
        self.assertEqual(outcome.exit_code, 1)
        self.assertIn("rate limit stopped the run", outcome.record.failure_reason or "")
        self.assertEqual(self.counts(outcome), (3, 3, 3))

    def test_nothing_is_written_to_a_pull_request(self) -> None:
        net, _outcome = self.scenario([pull(12, INSIDE)], {12: ["renovate.json"]})
        self.assertEqual([c for c in net.writes() if "/pulls" in c.url], [])


class WhichIssuesAreAsked(unittest.TestCase):
    """Only a resolved, closed detector error with a known opening time is looked up."""

    def candidate(
        self,
        number: int,
        *,
        repo: Repo = REPO,
        opened: datetime | None = OPENED,
        closed: datetime | None = CLOSED,
        resolved_flag: bool = True,
    ) -> Any:
        return aggregator.PilotCandidate(
            repo,
            number,
            f"CVE-2021-{9000 + number}",
            opened,
            False,
            (),
            closed,
            resolved_flag,
        )

    def asked(self, candidates: list[Any], **observation: Any) -> list[Any]:
        plan = SimpleNamespace(vex_exclusions=())
        return aggregator.detector_error_candidates(
            observation_text(**observation),
            policy_repos=[REPO, OTHER_REPO],
            candidates=candidates,
            plan=plan,
            decisions={},
        )

    def test_a_resolved_closed_detector_error_is_asked(self) -> None:
        found = self.asked([self.candidate(1)], detector_error_issues=classified((1,)))
        self.assertEqual(found, [aggregator.ResolvedIssue(REPO, 1, OPENED, CLOSED)])

    def test_everything_else_is_not(self) -> None:
        listed = {"detector_error_issues": classified((1, 2, 3, 4, 5))}
        candidates = [
            self.candidate(1, closed=None, resolved_flag=False),  # still open
            self.candidate(2, resolved_flag=False),  # closed, not resolved
            self.candidate(3, opened=None),  # no opening time
            self.candidate(4, repo=OTHER_REPO),  # not the listed Issue
            self.candidate(6),  # not a detector error
        ]
        self.assertEqual(self.asked(candidates, **listed), [])

    def test_an_unusable_observation_asks_for_nothing(self) -> None:
        plan = SimpleNamespace(vex_exclusions=())
        found = aggregator.detector_error_candidates(
            "{ not json",
            policy_repos=[REPO],
            candidates=[self.candidate(1)],
            plan=plan,
            decisions={},
        )
        self.assertEqual(found, [])

    def test_an_issue_outside_the_observed_repositories_is_not_asked(self) -> None:
        found = self.asked(
            [self.candidate(1)],
            detector_error_issues=classified((1,)),
            observed_repos=[OTHER],
        )
        self.assertEqual(found, [])


class PilotCandidateClosing(unittest.TestCase):
    """``closed_at`` and ``resolved`` of a candidate: read like the timelines read them."""

    def candidates(
        self, items: list[dict[str, Any]], actions: list[Any] | None = None
    ) -> dict[int, Any]:
        managed = [
            models.ManagedIssue(
                repo=REPO,
                number=item["number"],
                kind="finding",
                vuln_id=f"CVE-2021-{9000 + item['number']}",
                state=item["state"],
                body_state=None,
                closed_at=None,
                labels=frozenset(),
            )
            for item in items
        ]
        raw = {(TARGET.lower(), item["number"]): item for item in items}
        acts = actions or []
        results = {index: act.number for index, act in enumerate(acts)}
        found = aggregator.pilot_candidates(managed, raw, acts, results, NOW)
        return {c.number: c for c in found}

    def action(self, op: str, number: int, reason: str | None = None) -> Any:
        return models.IssueAction(
            op=op,
            repo=REPO,
            kind="finding",
            vuln_id=f"CVE-2021-{9000 + number}",
            number=number,
            body=None,
            close_reason=reason,
        )

    def test_the_defaults_leave_existing_callers_alone(self) -> None:
        cand = aggregator.PilotCandidate(REPO, 1, "CVE-2021-1", NOW, False)
        self.assertIsNone(cand.closed_at)
        self.assertFalse(cand.resolved)

    def test_a_listed_issue_is_read_from_its_closing_time_and_reason(self) -> None:
        found = self.candidates(
            [
                closed_issue(1),
                closed_issue(2, reason="not_planned"),
                closed_issue(3, state="open", reason=None),
            ]
        )
        self.assertEqual((found[1].closed_at, found[1].resolved), (CLOSED, True))
        self.assertEqual((found[2].closed_at, found[2].resolved), (CLOSED, False))
        self.assertEqual((found[3].closed_at, found[3].resolved), (None, False))

    def test_an_issue_this_run_closes_as_resolved_gets_now_and_true(self) -> None:
        found = self.candidates(
            [closed_issue(1, state="open", reason=None)],
            [self.action("close", 1, "resolved")],
        )
        self.assertEqual((found[1].closed_at, found[1].resolved), (NOW, True))

    def test_an_issue_this_run_closes_for_another_reason_is_not_resolved(self) -> None:
        found = self.candidates(
            [closed_issue(1, state="open", reason=None)],
            [self.action("close", 1, "withdrawn")],
        )
        self.assertEqual((found[1].closed_at, found[1].resolved), (NOW, False))

    def test_an_issue_this_run_reopens_is_no_longer_closed(self) -> None:
        found = self.candidates([closed_issue(1)], [self.action("reopen", 1)])
        self.assertEqual((found[1].closed_at, found[1].resolved), (None, False))


if __name__ == "__main__":
    unittest.main()
