"""Detector errors are counted by cause, not by Issue (Requirement 22.65 onward, D-78).

The cases are those of the source repository's ``test_supply_chain_metrics_cause.py`` (8 cases, same meaning),
written as ``unittest`` for this repository. They run against the byte-for-byte copy in ``tools/supply_chain/``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from supply_chain import metrics


def _fp(cause: str | None = None) -> metrics.PilotIssueOutcome:
    return metrics.PilotIssueOutcome(
        "not_affected", "component_not_present", cause_key=cause
    )


class DetectorErrorCauses(unittest.TestCase):
    def test_three_issues_one_cause_is_one_error(self) -> None:
        rates = metrics.compute_pilot_rates(
            [_fp("pkg:pypi/cryptography@1|skip-paths")] * 3
        )
        self.assertEqual(rates.false_positive, 3)  # Issues: keeps the 22.31 sum
        self.assertEqual(rates.false_positive_causes, 1)
        review = metrics.review_low_sample(rates)
        self.assertEqual(review.detector_errors, 1)
        self.assertEqual(review.detector_error_issues, 3)
        self.assertTrue(review.within_error_limit)
        self.assertFalse(review.needs_cause_classification)

    def test_no_cause_key_means_one_cause_per_issue(self) -> None:
        rates = metrics.compute_pilot_rates([_fp(), _fp(), _fp()])
        self.assertEqual(rates.false_positive_causes, 3)
        self.assertTrue(metrics.review_low_sample(rates).needs_cause_classification)

    def test_three_distinct_causes_exceed_the_limit(self) -> None:
        rates = metrics.compute_pilot_rates([_fp("a"), _fp("a"), _fp("b"), _fp("c")])
        self.assertEqual((rates.false_positive, rates.false_positive_causes), (4, 3))
        self.assertFalse(metrics.review_low_sample(rates).within_error_limit)

    def test_cause_is_counted_only_among_detector_errors(self) -> None:
        fixed = metrics.PilotIssueOutcome("fixed", cause_key="a")
        rates = metrics.compute_pilot_rates([fixed, _fp("b")])
        self.assertEqual(rates.false_positive_causes, 1)

    def test_sum_of_issue_counts_still_equals_issued(self) -> None:
        items = [_fp("a")] * 3 + [
            metrics.PilotIssueOutcome("fixed"),
            metrics.PilotIssueOutcome(None),
        ]
        r = metrics.compute_pilot_rates(items)
        self.assertEqual(
            r.issued,
            r.false_positive
            + r.not_affected_other
            + r.fixed
            + r.affected
            + r.undecided,
        )

    def test_duplicate_side_does_not_add_a_cause(self) -> None:
        dup = metrics.PilotIssueOutcome(
            "not_affected", "component_not_present", duplicate=True, cause_key="z"
        )
        self.assertEqual(
            metrics.compute_pilot_rates([_fp("a"), dup]).false_positive_causes, 1
        )

    def test_rate_numerator_is_causes_denominator_is_issues(self) -> None:
        items = [_fp("a")] * 10 + [metrics.PilotIssueOutcome("fixed")] * 10
        r = metrics.compute_pilot_rates(items)
        self.assertEqual(r.issued, 20)
        self.assertEqual(r.rate_percent, 100.0 * 1 / 20)

    def test_majority_uses_causes(self) -> None:
        r = metrics.compute_pilot_rates(
            [_fp("a")] * 3 + [metrics.PilotIssueOutcome("fixed")] * 3
        )
        self.assertFalse(metrics.review_low_sample(r).errors_are_majority)
        r2 = metrics.compute_pilot_rates(
            [
                _fp("a"),
                _fp("b"),
                metrics.PilotIssueOutcome("fixed"),
                metrics.PilotIssueOutcome("fixed"),
            ]
        )
        self.assertTrue(metrics.review_low_sample(r2).errors_are_majority)


if __name__ == "__main__":
    unittest.main()
