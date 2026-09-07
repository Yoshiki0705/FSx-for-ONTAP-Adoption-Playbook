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

from check_allow_budget import FAILING, allow_verdict


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
