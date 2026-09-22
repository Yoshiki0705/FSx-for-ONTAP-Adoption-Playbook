"""Task 11.3 controls for the first-major-miss rollout stop/resume state machine.

The design's Error Budget freezes the current batch on the first major detector miss and forbids
resuming until five prerequisites are all satisfied: (1) the scan scope and matching rule are
fixed, (2) a negative fixture exists for every known form of the same violation family, (3) a
valid-input control fixture exists, (4) the family-wide rescan of the current and deployed scope
is complete, and (5) a human has approved the result. Adding the missed finding to the baseline
to resume is forbidden.

These tests exercise the state-transition logic in ``tools.knowledge_quality.rollout_decision``
directly. Each prerequisite-deletion case confirms that dropping any single condition keeps the
rollout in ``ROLLOUT_STOPPED``; the all-true control confirms the only path out. The router entry
that the exploration property observes is covered by its own assertion here so the two agree.
"""

from __future__ import annotations

import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from knowledge_quality import (
    RESUME_PREREQUISITES,
    evaluate_quality_input,
    rollout_decision,
)


def all_satisfied() -> dict[str, bool]:
    return dict.fromkeys(RESUME_PREREQUISITES, True)


class FirstMajorMissStopsRollout(unittest.TestCase):
    """**Validates: Requirements 1.10, 2.10** — the first major miss stops the rollout."""

    def test_any_positive_miss_count_stops_the_rollout(self) -> None:
        for miss_count in range(1, 6):
            with self.subTest(miss_count=miss_count):
                result = rollout_decision(miss_count=miss_count)
                self.assertEqual(result.decision, "ROLLOUT_STOPPED")
                self.assertGreaterEqual(result.miss_count, 1)
                self.assertTrue(result.family_rescan_required)

    def test_zero_misses_do_not_stop_and_impose_no_rescan(self) -> None:
        result = rollout_decision(miss_count=0)
        self.assertEqual(result.decision, "CONTINUE")
        self.assertFalse(result.family_rescan_required)
        self.assertFalse(result.resume_allowed)
        self.assertEqual(result.unmet_prerequisites, ())

    def test_negative_miss_count_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            rollout_decision(miss_count=-1)


class ResumePrerequisitesAreConjunctive(unittest.TestCase):
    """A stopped rollout resumes only when all five prerequisites are satisfied."""

    def test_all_five_satisfied_allows_resume(self) -> None:
        """**Validates: Requirements 2.10, 3.6** — the one path out of ROLLOUT_STOPPED."""
        result = rollout_decision(miss_count=1, prerequisites=all_satisfied())
        self.assertEqual(result.decision, "ROLLOUT_STOPPED")
        self.assertTrue(result.resume_allowed)
        self.assertEqual(result.unmet_prerequisites, ())

    def test_dropping_any_single_prerequisite_blocks_resume(self) -> None:
        """**Validates: Requirements 1.10, 2.10, 3.3, 3.6** — resume is conjunctive.

        Deleting exactly one prerequisite (setting it false, or removing the key entirely) must
        keep the rollout stopped. This is the resume-prerequisite deletion property: no single
        condition may be dropped and still resume.
        """
        for dropped in RESUME_PREREQUISITES:
            for mode in ("false", "missing"):
                with self.subTest(dropped=dropped, mode=mode):
                    prerequisites = all_satisfied()
                    if mode == "false":
                        prerequisites[dropped] = False
                    else:
                        del prerequisites[dropped]
                    result = rollout_decision(miss_count=1, prerequisites=prerequisites)
                    self.assertFalse(result.resume_allowed)
                    self.assertIn(dropped, result.unmet_prerequisites)

    def test_any_incomplete_subset_below_all_five_blocks_resume(self) -> None:
        """Every proper subset of the prerequisites is insufficient to resume."""
        for size in range(len(RESUME_PREREQUISITES)):
            for satisfied in itertools.combinations(RESUME_PREREQUISITES, size):
                with self.subTest(satisfied=satisfied):
                    prerequisites = dict.fromkeys(satisfied, True)
                    result = rollout_decision(miss_count=1, prerequisites=prerequisites)
                    self.assertFalse(result.resume_allowed)
                    self.assertEqual(
                        set(result.unmet_prerequisites),
                        set(RESUME_PREREQUISITES) - set(satisfied),
                    )

    def test_no_prerequisites_argument_is_treated_as_none_satisfied(self) -> None:
        result = rollout_decision(miss_count=2)
        self.assertFalse(result.resume_allowed)
        self.assertEqual(set(result.unmet_prerequisites), set(RESUME_PREREQUISITES))

    def test_an_unknown_prerequisite_key_does_not_satisfy_a_required_one(self) -> None:
        prerequisites = all_satisfied()
        prerequisites["not_a_real_prerequisite"] = True
        del prerequisites[RESUME_PREREQUISITES[0]]
        result = rollout_decision(miss_count=1, prerequisites=prerequisites)
        self.assertFalse(result.resume_allowed)
        self.assertIn(RESUME_PREREQUISITES[0], result.unmet_prerequisites)


class ExplorationRouterAgrees(unittest.TestCase):
    """The router the exploration property calls must return ROLLOUT_STOPPED for the fixture."""

    def test_router_returns_rollout_stopped_for_the_exploration_fixture(self) -> None:
        """**Validates: Requirements 1.10, 2.10** — the family is routed, not deferred."""
        result = evaluate_quality_input(
            {
                "family": "major_detector_miss_advanced",
                "major_miss_count": 1,
                "family_rescan_complete": False,
            }
        )
        self.assertTrue(result["routed"])
        self.assertEqual(result["decision"], "ROLLOUT_STOPPED")


if __name__ == "__main__":
    unittest.main()
