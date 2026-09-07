"""The shrink-only rule for audit allow markers, as a truth table.

Every allow marker silences a detector. **Adding one looks exactly like fixing the problem it
silences, because the audit passes either way** - so the failure is a check that quietly stops
covering something, not a crash. Both directions have to fail, and the quieter one is the surplus:
a budget recording more than exists breaks nothing today, which is why the marker it once counted
can come back without a word.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from audit_public_output import audit_line
from check_allow_budget import (
    FAILING,
    allow_verdict,
    suppression_verdict,
)


class GrowthIsRefused(unittest.TestCase):
    def test_a_marker_the_budget_does_not_record_is_added(self) -> None:
        self.assertEqual(allow_verdict(recorded=None, actual=1), "added")

    def test_one_more_than_recorded_is_added(self) -> None:
        self.assertEqual(allow_verdict(recorded=3, actual=4), "added")

    def test_added_fails_the_check(self) -> None:
        """A verdict that does not fail is a verdict that changes nothing."""
        self.assertIn("added", FAILING)


class SurplusIsRefused(unittest.TestCase):
    def test_fewer_than_recorded_is_stale(self) -> None:
        self.assertEqual(allow_verdict(recorded=3, actual=2), "stale")

    def test_a_marker_that_is_gone_entirely_is_stale(self) -> None:
        self.assertEqual(allow_verdict(recorded=1, actual=0), "stale")

    def test_stale_fails_the_check(self) -> None:
        """The quieter half. Surplus is headroom for a silent return, so it cannot be a warning."""
        self.assertIn("stale", FAILING)


class UnchangedIsAccepted(unittest.TestCase):
    def test_equal_counts_are_ok(self) -> None:
        self.assertEqual(allow_verdict(recorded=3, actual=3), "ok")

    def test_absent_on_both_sides_is_ok(self) -> None:
        """Cannot occur, and answers rather than raising: a guard that crashes on an impossible
        input gets its caller wrapped in a try block."""
        self.assertEqual(allow_verdict(recorded=None, actual=0), "ok")

    def test_ok_does_not_fail_the_check(self) -> None:
        """A check that refuses every clean run gets switched off."""
        self.assertNotIn("ok", FAILING)


if __name__ == "__main__":
    unittest.main()


class ASuppressionMustEarnItsPlace(unittest.TestCase):
    """The predicate is "ignoring the marker increases the report", not "the report is unchanged".

    A sibling repository implemented the second form first and reported the correction. Testing for
    an unchanged report finds only markers that suppress nothing, and **misses a marker that makes
    the checker report something that is not there.** Same-report is the quiet failure; more-report
    is the loud one, and **a rule written to hunt quiet failures will not look for loud ones.**
    """

    def test_a_marker_that_hides_a_finding_is_justified(self) -> None:
        self.assertEqual(
            suppression_verdict(findings_with=0, findings_without=1), "justified"
        )

    def test_a_marker_that_hides_nothing_is_inert(self) -> None:
        """Not merely useless: **headroom.** Exempt today, silently exempt tomorrow."""
        self.assertEqual(
            suppression_verdict(findings_with=0, findings_without=0), "inert"
        )

    def test_a_marker_that_adds_a_finding_is_not_justified(self) -> None:
        """The loud half, and the row that fails under the wrong predicate.

        `findings_without != findings_with` calls this justified, because the count did change.
        Cannot occur with today's categories, which is exactly why it is pinned.
        """
        self.assertEqual(
            suppression_verdict(findings_with=1, findings_without=0), "inert"
        )

    def test_an_unchanged_nonzero_report_is_inert(self) -> None:
        self.assertEqual(
            suppression_verdict(findings_with=1, findings_without=1), "inert"
        )


class MarkersAreDirectivesNotMentions(unittest.TestCase):
    """A marker has to be an HTML comment, and not shown as code.

    Both looser readings were live holes: **a line merely mentioning `allow:naming` in prose
    suppressed the detector on that line**, backticks included, so every line documenting the markers
    exempted itself - and appending a code-span marker to any sentence did the same.
    """

    FORBIDDEN = "FSxN is the short form"

    def test_a_real_marker_suppresses(self) -> None:
        self.assertEqual(audit_line(f"{self.FORBIDDEN} <!-- allow:naming -->"), [])

    def test_a_reason_after_the_category_still_suppresses(self) -> None:
        """The form actually used in this repository."""
        self.assertEqual(
            audit_line(f"{self.FORBIDDEN} <!-- allow:naming - citation title -->"), []
        )

    def test_a_bare_prose_mention_does_not_suppress(self) -> None:
        """No backticks, so only the required HTML comment wrapper refuses this one.

        The mutation harness found that the backticked version does not exercise the wrapper at all:
        code spans are stripped before markers are extracted, so it passes either way. Two fixes
        cover two different sentences, and each needs its own case.
        """
        self.assertTrue(
            audit_line(f"{self.FORBIDDEN}, described in allow:naming above")
        )

    def test_a_backticked_mention_does_not_suppress(self) -> None:
        self.assertTrue(audit_line(f"{self.FORBIDDEN} (see `allow:naming`)"))

    def test_a_marker_shown_as_code_does_not_suppress(self) -> None:
        """Documenting the syntax must not activate it."""
        self.assertTrue(audit_line(f"{self.FORBIDDEN} `<!-- allow:naming -->`"))

    def test_a_forbidden_term_inside_a_code_span_is_still_reported(self) -> None:
        """Only marker extraction ignores code spans. Findings still match the original line."""
        self.assertTrue(audit_line("the `FSxN` short form"))
