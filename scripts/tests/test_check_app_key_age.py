"""The key-age check decides from the secret's `updated_at` and keeps one Issue in step with it.

No test reaches the network. A fake GitHub answers the three calls the script makes (read the secret,
list open Issues, write an Issue) and records every request, so a test can say what was *not* sent as
well as what was.

* The verdict is a pure function of the time and the answer, tried at 79, 80, 89 and 90 days.
* `ok` closes the Issue, `due` opens one and then leaves it alone, `overdue` rewrites it once and
  fails the job, and `unreadable` writes nothing at all.
* Nothing the job prints or writes may contain the token or the body of an answer.

The response shapes the fake returns (`updated_at` of a repository secret, the Issue list with
`pull_request` on pull requests, `state_reason` on close) are the ones the GitHub REST reference
documents. They were not checked against the live API.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_app_key_age as K

NOW = datetime(2026, 11, 16, 3, 31, tzinfo=timezone.utc)
REPO = "example-org/example-repo"
SECRET_PATH = f"/repos/{REPO}/actions/secrets/SUPPLY_CHAIN_APP_PRIVATE_KEY"
ISSUES_PATH = f"/repos/{REPO}/issues"
APP_TOKEN = "ghs_app_token_value_123"
ISSUE_TOKEN = "ghs_issue_token_value_456"
SECRET_BODY_TEXT = "body-text-that-must-not-be-printed"


def stamp(days: float) -> str:
    """The `updated_at` of a secret last set `days` days before NOW."""
    moment = NOW - timedelta(days=days)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeGitHub:
    """Answers the calls the script makes and records every one of them."""

    def __init__(
        self,
        *,
        updated_at: str | None = None,
        secret_status: int = 200,
        issues: list[dict[str, Any]] | None = None,
    ) -> None:
        self.updated_at = updated_at
        self.secret_status = secret_status
        self.issues: list[dict[str, Any]] = list(issues or [])
        self.calls: list[tuple[str, str, str, dict[str, Any] | None]] = []
        self.next_number = 1000

    def __call__(
        self, method: str, path: str, token: str, payload: dict[str, Any] | None
    ) -> K.Response:
        self.calls.append((method, path, token, payload))
        split = urllib.parse.urlsplit(path)
        query = urllib.parse.parse_qs(split.query)
        route = split.path
        if route == SECRET_PATH and method == "GET":
            if self.secret_status != 200:
                return K.Response(self.secret_status, {"message": SECRET_BODY_TEXT})
            if self.updated_at is None:
                return K.Response(200, {"name": "SUPPLY_CHAIN_APP_PRIVATE_KEY"})
            return K.Response(
                200,
                {
                    "name": "SUPPLY_CHAIN_APP_PRIVATE_KEY",
                    "created_at": self.updated_at,
                    "updated_at": self.updated_at,
                },
            )
        if route == ISSUES_PATH and method == "GET":
            assert query.get("per_page") == ["100"], "the Issue list must ask for 100"
            page = int(query.get("page", ["1"])[0])
            state = query.get("state", ["open"])[0]
            rows = [i for i in self.issues if state == "all" or i["state"] == state]
            return K.Response(200, rows[(page - 1) * 100 : page * 100])
        if route == ISSUES_PATH and method == "POST":
            assert payload is not None
            self.next_number += 1
            created = {
                "number": self.next_number,
                "state": "open",
                "title": payload["title"],
                "body": payload["body"],
            }
            self.issues.append(created)
            return K.Response(201, created)
        if route.startswith(ISSUES_PATH + "/"):
            tail = route[len(ISSUES_PATH) + 1 :].split("/")
            number = int(tail[0])
            found = next(i for i in self.issues if i["number"] == number)
            if len(tail) == 2 and tail[1] == "comments" and method == "POST":
                return K.Response(201, {"id": 1})
            if len(tail) == 1 and method == "PATCH":
                assert payload is not None
                found.update(payload)
                return K.Response(200, found)
        return K.Response(404, {"message": "unexpected request in the fake"})

    def writes(self) -> list[tuple[str, str, dict[str, Any] | None]]:
        return [(m, p, d) for m, p, _t, d in self.calls if m != "GET"]

    def issue_calls(self) -> list[tuple[str, str, str, dict[str, Any] | None]]:
        return [c for c in self.calls if c[1].startswith(ISSUES_PATH)]


def issue(
    number: int,
    body: str,
    *,
    state: str = "open",
    pull_request: bool = False,
    title: str = K.TITLE,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "number": number,
        "state": state,
        "title": title,
        "body": body,
    }
    if pull_request:
        row["pull_request"] = {"url": "https://example.invalid/pr"}
    return row


def env(**over: str) -> dict[str, str]:
    base = {
        "GH_REPO": REPO,
        "APP_TOKEN": APP_TOKEN,
        "ISSUE_TOKEN": ISSUE_TOKEN,
        "TOKEN_STEP_OUTCOME": "success",
    }
    base.update(over)
    return base


def run(fake: FakeGitHub, environment: dict[str, str] | None = None) -> tuple[int, str]:
    """Run the script's entry point against the fake; return the exit code and what it printed."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = K.main(env=environment or env(), now=NOW, send=fake)
    return code, out.getvalue()


class TheVerdictIsAPureFunction(unittest.TestCase):
    def verdict(self, days: float) -> K.Verdict:
        return K.classify(stamp(days), NOW, warn_days=80, max_days=90)

    def test_the_boundaries_at_79_80_89_and_90_days(self) -> None:
        for days, state in [
            (0, "ok"),
            (79, "ok"),
            (80, "due"),
            (89, "due"),
            (90, "overdue"),
            (200, "overdue"),
        ]:
            with self.subTest(days=days):
                self.assertEqual(self.verdict(days).state, state)

    def test_a_fraction_of_a_day_is_cut_off_not_rounded(self) -> None:
        """79 days 23 hours is still 79 days, so it is `ok`; rounding would call it `due`."""
        result = K.classify(
            (NOW - timedelta(days=79, hours=23)).isoformat(), NOW, 80, 90
        )
        self.assertEqual((result.state, result.days), ("ok", 79))

    def test_the_days_are_reported(self) -> None:
        self.assertEqual(self.verdict(85).days, 85)

    def test_a_timestamp_in_the_future_counts_as_zero_days(self) -> None:
        self.assertEqual(self.verdict(-3).days, 0)
        self.assertEqual(self.verdict(-3).state, "ok")

    def test_the_thresholds_are_taken_from_the_arguments(self) -> None:
        self.assertEqual(K.classify(stamp(10), NOW, 10, 20).state, "due")
        self.assertEqual(K.classify(stamp(20), NOW, 10, 20).state, "overdue")

    def test_an_unreadable_timestamp_is_unreadable(self) -> None:
        for value in [None, "", "yesterday", "2026-13-45T00:00:00Z", 12345]:
            with self.subTest(value=value):
                self.assertEqual(
                    K.classify(value, NOW, 80, 90).state,  # type: ignore[arg-type]
                    "unreadable",
                )

    def test_an_offset_timestamp_is_converted_to_utc(self) -> None:
        local = (NOW - timedelta(days=80)).astimezone(timezone(timedelta(hours=9)))
        self.assertEqual(K.classify(local.isoformat(), NOW, 80, 90).state, "due")


class TheConfigurationIsRead(unittest.TestCase):
    def test_the_defaults(self) -> None:
        cfg = K.load_config(env())
        self.assertEqual(cfg.secret_name, "SUPPLY_CHAIN_APP_PRIVATE_KEY")
        self.assertEqual((cfg.warn_days, cfg.max_days), (80, 90))

    def test_overrides(self) -> None:
        cfg = K.load_config(env(SECRET_NAME="OTHER", WARN_DAYS="5", MAX_DAYS="7"))
        self.assertEqual(
            (cfg.secret_name, cfg.warn_days, cfg.max_days), ("OTHER", 5, 7)
        )

    def test_a_repository_that_is_not_owner_slash_name_is_refused(self) -> None:
        for bad in ["", "no-slash", "a/b/c", "/name", "owner/"]:
            with self.subTest(bad=bad), self.assertRaises(K.ConfigError):
                K.load_config(env(GH_REPO=bad))

    def test_thresholds_that_are_not_whole_numbers_or_not_ordered_are_refused(
        self,
    ) -> None:
        for name, value in [("WARN_DAYS", "x"), ("MAX_DAYS", "-1")]:
            with self.subTest(name=name), self.assertRaises(K.ConfigError):
                K.load_config(env(**{name: value}))
        with self.assertRaises(K.ConfigError):
            K.load_config(env(WARN_DAYS="90", MAX_DAYS="80"))

    def test_a_missing_issue_token_is_an_error_exit_not_a_crash(self) -> None:
        fake = FakeGitHub(updated_at=stamp(1))
        code, printed = run(fake, env(ISSUE_TOKEN=""))
        self.assertEqual(code, 1)
        self.assertIn("::error::", printed)
        self.assertEqual(fake.issue_calls(), [])


class OkClosesTheIssueAndOtherwiseDoesNothing(unittest.TestCase):
    def test_ok_without_an_issue_writes_nothing(self) -> None:
        fake = FakeGitHub(updated_at=stamp(10))
        code, _ = run(fake)
        self.assertEqual(code, 0)
        self.assertEqual(fake.writes(), [])

    def test_ok_with_an_open_issue_comments_and_closes_it_as_completed(self) -> None:
        fake = FakeGitHub(
            updated_at=stamp(2),
            issues=[issue(7, K.render_body("due", stamp(85), 85))],
        )
        code, _ = run(fake)
        self.assertEqual(code, 0)
        methods = [(m, p) for m, p, _d in fake.writes()]
        self.assertEqual(
            methods,
            [
                ("POST", f"{ISSUES_PATH}/7/comments"),
                ("PATCH", f"{ISSUES_PATH}/7"),
            ],
        )
        comment = fake.writes()[0][2]
        assert comment is not None
        self.assertIn(stamp(2), comment["body"])
        patch = fake.writes()[1][2]
        self.assertEqual(patch, {"state": "closed", "state_reason": "completed"})
        self.assertEqual(fake.issues[0]["state"], "closed")

    def test_the_comment_is_written_before_the_issue_is_closed(self) -> None:
        fake = FakeGitHub(
            updated_at=stamp(2),
            issues=[issue(7, K.render_body("due", stamp(85), 85))],
        )
        run(fake)
        self.assertEqual([m for m, _p, _d in fake.writes()], ["POST", "PATCH"])


class DueOpensOneIssueAndThenLeavesItAlone(unittest.TestCase):
    def test_due_with_no_issue_creates_exactly_one(self) -> None:
        fake = FakeGitHub(updated_at=stamp(81))
        code, _ = run(fake)
        self.assertEqual(code, 0)
        posts = [w for w in fake.writes() if w[0] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][1], ISSUES_PATH)
        payload = posts[0][2]
        assert payload is not None
        self.assertEqual(payload["title"], K.TITLE)
        self.assertEqual(payload["body"].splitlines()[0], K.MARKER)
        self.assertNotIn("labels", payload)

    def test_a_second_run_does_not_open_another_or_touch_the_first(self) -> None:
        fake = FakeGitHub(updated_at=stamp(81))
        run(fake)
        before = [dict(i) for i in fake.issues]
        fake.calls.clear()
        code, _ = run(fake)
        self.assertEqual(code, 0)
        self.assertEqual(fake.writes(), [])
        self.assertEqual(len(fake.issues), 1)
        self.assertEqual(fake.issues, before)

    def test_due_with_an_issue_changes_neither_body_nor_comments(self) -> None:
        old = K.render_body("due", stamp(80), 80)
        fake = FakeGitHub(updated_at=stamp(88), issues=[issue(7, old)])
        code, _ = run(fake)
        self.assertEqual(code, 0)
        self.assertEqual(fake.writes(), [])
        self.assertEqual(fake.issues[0]["body"], old)

    def test_a_closed_issue_does_not_count_as_existing(self) -> None:
        closed = issue(3, K.render_body("due", stamp(81), 81), state="closed")
        fake = FakeGitHub(updated_at=stamp(82), issues=[closed])
        run(fake)
        self.assertEqual(len([w for w in fake.writes() if w[0] == "POST"]), 1)
        self.assertEqual(fake.issues[0]["state"], "closed")


class OverdueFailsAndRewritesTheIssueOnce(unittest.TestCase):
    def test_overdue_with_no_issue_creates_the_overdue_version_and_fails(self) -> None:
        fake = FakeGitHub(updated_at=stamp(95))
        code, printed = run(fake)
        self.assertEqual(code, 1)
        posts = [w for w in fake.writes() if w[0] == "POST"]
        self.assertEqual(len(posts), 1)
        payload = posts[0][2]
        assert payload is not None
        self.assertTrue(K.is_overdue_body(payload["body"]))
        self.assertIn("overdue", printed)

    def test_overdue_with_a_due_issue_rewrites_the_body(self) -> None:
        fake = FakeGitHub(
            updated_at=stamp(91),
            issues=[issue(7, K.render_body("due", stamp(85), 85))],
        )
        code, _ = run(fake)
        self.assertEqual(code, 1)
        self.assertEqual(
            [(m, p) for m, p, _d in fake.writes()], [("PATCH", f"{ISSUES_PATH}/7")]
        )
        self.assertTrue(K.is_overdue_body(fake.issues[0]["body"]))
        self.assertEqual(fake.issues[0]["body"].splitlines()[0], K.MARKER)

    def test_overdue_with_an_overdue_issue_does_not_rewrite_it_again(self) -> None:
        """The body names the elapsed days, which change daily; the version is what is compared."""
        fake = FakeGitHub(
            updated_at=stamp(99),
            issues=[issue(7, K.render_body("overdue", stamp(91), 91))],
        )
        code, _ = run(fake)
        self.assertEqual(code, 1)
        self.assertEqual(fake.writes(), [])

    def test_two_overdue_runs_in_a_row_write_once(self) -> None:
        fake = FakeGitHub(updated_at=stamp(95))
        run(fake)
        fake.calls.clear()
        code, _ = run(fake)
        self.assertEqual(code, 1)
        self.assertEqual(fake.writes(), [])
        self.assertEqual(len(fake.issues), 1)


class UnreadableWritesNothingAndFails(unittest.TestCase):
    def assert_unreadable(self, fake: FakeGitHub, environment: dict[str, str]) -> str:
        code, printed = run(fake, environment)
        self.assertEqual(code, 1)
        self.assertEqual(fake.issue_calls(), [], "an Issue was read or written")
        self.assertIn("::error::", printed)
        self.assertIn("unreadable", printed)
        return printed

    def test_no_app_token(self) -> None:
        fake = FakeGitHub(updated_at=stamp(1))
        self.assert_unreadable(fake, env(APP_TOKEN=""))
        self.assertEqual(fake.calls, [], "the secret was read with no token")

    def test_the_token_step_did_not_succeed(self) -> None:
        for outcome in ["failure", "skipped", "cancelled", ""]:
            with self.subTest(outcome=outcome):
                fake = FakeGitHub(updated_at=stamp(1))
                self.assert_unreadable(fake, env(TOKEN_STEP_OUTCOME=outcome))
                self.assertEqual(fake.calls, [])

    def test_an_answer_other_than_200(self) -> None:
        for status in [401, 403, 404, 500, 0]:
            with self.subTest(status=status):
                fake = FakeGitHub(secret_status=status)
                self.assert_unreadable(fake, env())

    def test_an_answer_without_a_readable_updated_at(self) -> None:
        self.assert_unreadable(FakeGitHub(updated_at=None), env())

    def test_the_message_names_the_missing_permission_for_403_and_404(self) -> None:
        for status in [403, 404]:
            with self.subTest(status=status):
                printed = self.assert_unreadable(
                    FakeGitHub(secret_status=status), env()
                )
                self.assertIn("Secrets: Read-only", printed)

    def test_an_open_issue_is_left_exactly_as_it_was(self) -> None:
        body = K.render_body("due", stamp(85), 85)
        fake = FakeGitHub(secret_status=403, issues=[issue(7, body)])
        run(fake)
        self.assertEqual(fake.issues[0]["body"], body)
        self.assertEqual(fake.issues[0]["state"], "open")


class TheIssueIsFoundByItsMarkerAlone(unittest.TestCase):
    def test_the_title_does_not_identify_the_issue(self) -> None:
        stranger = issue(5, "no marker here")
        fake = FakeGitHub(updated_at=stamp(85), issues=[stranger])
        run(fake)
        self.assertEqual(len([w for w in fake.writes() if w[0] == "POST"]), 1)
        self.assertEqual(stranger["body"], "no marker here")

    def test_the_marker_must_be_the_first_line(self) -> None:
        late = issue(5, "intro\n" + K.MARKER + "\n")
        fake = FakeGitHub(updated_at=stamp(85), issues=[late])
        run(fake)
        self.assertEqual(len([w for w in fake.writes() if w[0] == "POST"]), 1)

    def test_the_aggregators_issue_is_never_touched(self) -> None:
        """Another marker, another title: the aggregator's own failure Issue stays as it is."""
        other = issue(
            9,
            "<!-- supply-chain-aggregator:v1 -->\nbody",
            title="[supply-chain] Aggregator failed",
        )
        fake = FakeGitHub(updated_at=stamp(2), issues=[other])
        run(fake)
        self.assertEqual(fake.writes(), [])
        self.assertEqual(other["state"], "open")

    def test_a_pull_request_with_the_marker_is_skipped(self) -> None:
        pr = issue(5, K.render_body("due", stamp(85), 85), pull_request=True)
        fake = FakeGitHub(updated_at=stamp(2), issues=[pr])
        run(fake)
        self.assertEqual(fake.writes(), [], "a pull request was closed as if an Issue")

    def test_a_pull_request_does_not_stop_an_issue_from_being_opened(self) -> None:
        pr = issue(5, K.render_body("due", stamp(85), 85), pull_request=True)
        fake = FakeGitHub(updated_at=stamp(85), issues=[pr])
        run(fake)
        self.assertEqual(len([w for w in fake.writes() if w[0] == "POST"]), 1)

    def test_the_issue_on_the_second_page_is_found(self) -> None:
        filler = [issue(100 + n, "unrelated", title="other") for n in range(100)]
        target = issue(7, K.render_body("due", stamp(85), 85))
        fake = FakeGitHub(updated_at=stamp(85), issues=[*filler, target])
        run(fake)
        pages = [
            urllib.parse.parse_qs(urllib.parse.urlsplit(p).query)["page"]
            for _m, p, _t, _d in fake.calls
            if p.startswith(ISSUES_PATH) and "page=" in p
        ]
        self.assertEqual(pages, [["1"], ["2"]])
        self.assertEqual(fake.writes(), [], "a second Issue was opened")

    def test_paging_stops_at_a_short_page(self) -> None:
        fake = FakeGitHub(updated_at=stamp(2), issues=[issue(1, "x", title="o")])
        run(fake)
        listed = [
            c for c in fake.calls if c[0] == "GET" and c[1].startswith(ISSUES_PATH)
        ]
        self.assertEqual(len(listed), 1)

    def test_an_issue_list_that_fails_is_an_error_not_a_second_issue(self) -> None:
        class Broken(FakeGitHub):
            def __call__(
                self,
                method: str,
                path: str,
                token: str,
                payload: dict[str, Any] | None,
            ) -> K.Response:
                if path.startswith(ISSUES_PATH) and method == "GET":
                    self.calls.append((method, path, token, payload))
                    return K.Response(500, {"message": SECRET_BODY_TEXT})
                return super().__call__(method, path, token, payload)

        fake = Broken(updated_at=stamp(85))
        code, printed = run(fake)
        self.assertEqual(code, 1)
        self.assertEqual(fake.writes(), [])
        self.assertIn("::error::", printed)
        self.assertNotIn(SECRET_BODY_TEXT, printed)


class TheTwoTokensAreNotMixed(unittest.TestCase):
    def test_the_secret_is_read_with_the_app_token_and_issues_with_the_job_token(
        self,
    ) -> None:
        fake = FakeGitHub(updated_at=stamp(85))
        run(fake)
        self.assertTrue(fake.calls)
        for method, path, token, _payload in fake.calls:
            with self.subTest(path=path, method=method):
                expected = APP_TOKEN if path == SECRET_PATH else ISSUE_TOKEN
                self.assertEqual(token, expected)


class NothingSecretIsPrintedOrWritten(unittest.TestCase):
    def test_no_token_and_no_answer_body_in_output_or_summary(self) -> None:
        for status in [200, 403, 500]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                summary = Path(tmp) / "summary.md"
                fake = FakeGitHub(
                    updated_at=stamp(95) if status == 200 else None,
                    secret_status=status,
                )
                _code, printed = run(fake, env(GITHUB_STEP_SUMMARY=str(summary)))
                written = summary.read_text(encoding="utf-8")
                for text in (printed, written):
                    self.assertNotIn(APP_TOKEN, text)
                    self.assertNotIn(ISSUE_TOKEN, text)
                    self.assertNotIn(SECRET_BODY_TEXT, text)
                    self.assertNotIn("BEGIN", text)

    def test_the_issue_body_names_no_key_material(self) -> None:
        for state in ["due", "overdue"]:
            body = K.render_body(state, stamp(85), 85)
            self.assertNotIn("PRIVATE KEY", body)
            self.assertNotIn("-----", body)


class TheSummaryHoldsOneTable(unittest.TestCase):
    def test_the_verdict_the_timestamp_and_the_days_are_in_one_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.md"
            run(
                FakeGitHub(updated_at=stamp(83)),
                env(GITHUB_STEP_SUMMARY=str(summary)),
            )
            text = summary.read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if line.startswith("|")]
        self.assertEqual(len(rows), 3, "header, separator and one data row")
        self.assertIn("due", rows[2])
        self.assertIn(stamp(83), rows[2])
        self.assertIn("83", rows[2])

    def test_an_unreadable_secret_still_writes_the_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.md"
            run(
                FakeGitHub(secret_status=403),
                env(GITHUB_STEP_SUMMARY=str(summary)),
            )
            text = summary.read_text(encoding="utf-8")
        self.assertIn("unreadable", text)

    def test_no_summary_file_is_fine(self) -> None:
        code, _ = run(FakeGitHub(updated_at=stamp(1)), env())
        self.assertEqual(code, 0)


class TheIssueBody(unittest.TestCase):
    def test_the_first_line_is_the_marker_and_the_state_is_on_the_second(self) -> None:
        for state in ["due", "overdue"]:
            body = K.render_body(state, stamp(85), 85)
            self.assertEqual(
                body.splitlines()[0], "<!-- supply-chain-key-rotation:v1 -->"
            )
            self.assertEqual(K.is_overdue_body(body), state == "overdue", state)

    def test_it_carries_the_facts_and_the_four_steps(self) -> None:
        body = K.render_body("due", "2026-08-27T00:00:00Z", 81)
        self.assertIn("2026-08-27T00:00:00Z", body)
        self.assertIn("81", body)
        self.assertIn("80 日", body)
        self.assertIn("90 日", body)
        self.assertIn(
            "https://github.com/settings/apps/sc-aggregator-yoshiki0705", body
        )
        self.assertIn("scripts/rotate_app_key.sh", body)
        self.assertEqual(body.count("- [ ] "), 4)

    def test_headings_are_noun_phrases(self) -> None:
        for state in ["due", "overdue"]:
            headings = [
                line
                for line in K.render_body(state, stamp(85), 85).splitlines()
                if line.startswith("#")
            ]
            self.assertTrue(headings)
            for heading in headings:
                self.assertNotRegex(heading, r"(ます|ません|です|ください|か)$")

    def test_plain_text_is_not_an_overdue_body(self) -> None:
        self.assertFalse(K.is_overdue_body("plain text"))


class TheTransport(unittest.TestCase):
    def test_a_redirect_is_not_followed(self) -> None:
        """The token travels in a header, and urllib would forward it to wherever it was sent."""
        handler = K.NoRedirect()
        self.assertIsNone(
            handler.redirect_request(
                None,  # type: ignore[arg-type]
                None,
                301,
                "",
                {},  # type: ignore[arg-type]
                "https://example.invalid/",
            )
        )


if __name__ == "__main__":
    unittest.main()
