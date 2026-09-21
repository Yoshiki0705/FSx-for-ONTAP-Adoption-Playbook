"""Task 3.3 controls for target-fixed, shrink-only allowance baselines."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from check_allow_budget import (
    TARGET_FIXED_ENTRY_FIELDS,
    TARGET_FIXED_SCHEMA,
    entries_digest,
    target_fixed_verdict,
    validate_target_fixed_document,
)

SCHEMA_PATH = ROOT / "tools" / "target-fixed-baseline.schema.json"


def empty_baseline() -> dict[str, Any]:
    return {
        "schema": TARGET_FIXED_SCHEMA,
        "entries": [],
        "human_decision_record": None,
    }


def entry(index: int = 0, **changes: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "target_kind": "local-kiro",
        "target_authority_id": "hub-" + "phase-0",
        "target_path": f"docs/fixture-{index}.md",
        "rule_id": f"fixture-rule-{index}",
        "category": "public-safety",
        "target_fingerprint": f"sha256:{index + 1:064x}",
        "reason": f"Existing fixture violation {index} requires staged remediation.",
        "approved_revision": "a" * 40,
        "removal_condition": f"The fixture-rule-{index} finding is absent.",
    }
    value.update(changes)
    return value


def human_decision(
    before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "decision": "APPROVED",
        "decision_source": "human-user",
        "reason": "Reviewed remediation removes only the named target.",
        "decision_revision": "b" * 40,
        "decided_at": "2026-09-18T03:00:00Z",
        "baseline_before_sha256": entries_digest(before),
        "baseline_after_sha256": entries_digest(after),
    }


class TargetFixedSchemaTests(unittest.TestCase):
    def test_tracked_schema_and_initial_zero_baseline_match_the_validator(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        baseline = empty_baseline()
        self.assertEqual(schema["$id"], TARGET_FIXED_SCHEMA)
        self.assertEqual(
            set(schema["$defs"]["entry"]["required"]),
            set(TARGET_FIXED_ENTRY_FIELDS),
        )
        authority_conditions = schema["$defs"]["entry"]["allOf"]
        self.assertEqual(
            {
                condition["if"]["properties"]["target_kind"]["const"]
                for condition in authority_conditions
            },
            {"public-github", "local-kiro"},
        )
        self.assertEqual(validate_target_fixed_document(baseline), [])
        self.assertEqual(baseline["entries"], [])
        self.assertIsNone(baseline["human_decision_record"])

    def test_missing_human_decision_field_is_rejected_like_the_schema(self) -> None:
        document = empty_baseline()
        del document["human_decision_record"]
        self.assertIn(
            "missing document fields: ['human_decision_record']",
            validate_target_fixed_document(document),
        )

    def test_partial_or_extra_human_decision_record_is_rejected(self) -> None:
        valid = human_decision([], [])
        malformed = (
            {},
            {"decision": "APPROVED"},
            {**valid, "unexpected": True},
            {**valid, "baseline_after_sha256": "not-a-digest"},
        )
        for decision in malformed:
            with self.subTest(decision=decision):
                document = empty_baseline()
                document["human_decision_record"] = decision
                self.assertTrue(validate_target_fixed_document(document))

    def test_malformed_entry_types_are_reported_without_crashing(self) -> None:
        for field, value in (
            ("reason", []),
            ("removal_condition", {}),
            ("target_path", ["docs", "fixture.md"]),
        ):
            with self.subTest(field=field):
                malformed = entry(**{field: value})
                document = empty_baseline()
                document["entries"] = [malformed]
                self.assertTrue(validate_target_fixed_document(document))
                result = target_fixed_verdict(approved=[malformed], actual=[malformed])
                self.assertFalse(result.accepted)
                self.assertTrue(any(field in problem for problem in result.problems))

    def test_empty_reason_and_removal_condition_are_rejected(self) -> None:
        """**Validates: Requirements 1.5, 2.5**"""
        for field in ("reason", "removal_condition"):
            with self.subTest(field=field):
                candidate = entry(**{field: "  "})
                result = target_fixed_verdict(approved=[candidate], actual=[candidate])
                self.assertFalse(result.accepted)
                self.assertTrue(any(field in problem for problem in result.problems))

    def test_authority_id_type_is_fixed_by_target_kind(self) -> None:
        """**Validates: Requirements 1.5, 2.5, 2.6**"""
        invalid = (
            entry(target_kind="public-github", target_authority_id="123"),
            entry(target_kind="public-github", target_authority_id=True),
            entry(target_kind="local-kiro", target_authority_id=123),
        )
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                self.assertTrue(
                    any(
                        "target_authority_id" in error
                        for error in validate_target_fixed_document(
                            {
                                "schema": TARGET_FIXED_SCHEMA,
                                "entries": [candidate],
                                "human_decision_record": None,
                            }
                        )
                    )
                )

        public = entry(target_kind="public-github", target_authority_id=123)
        self.assertEqual(
            validate_target_fixed_document(
                {
                    "schema": TARGET_FIXED_SCHEMA,
                    "entries": [public],
                    "human_decision_record": None,
                }
            ),
            [],
        )


class TargetSetPropertyTests(unittest.TestCase):
    def test_any_addition_or_same_count_substitution_is_rejected(self) -> None:
        """**Validates: Requirements 1.5, 2.5**"""
        for size in range(9):
            approved = [entry(index) for index in range(size)]
            added = approved + [entry(size)]
            with self.subTest(size=size, mutation="addition"):
                result = target_fixed_verdict(approved=approved, actual=added)
                self.assertFalse(result.accepted)
                self.assertIn(
                    "actual target addition or substitution is not approved",
                    result.problems,
                )
            if not approved:
                continue
            substituted = list(approved)
            substituted[-1] = entry(size + 100)
            with self.subTest(size=size, mutation="substitution"):
                result = target_fixed_verdict(
                    approved=approved,
                    actual=substituted,
                    proposed=substituted,
                    human_decision_record=human_decision(approved, substituted),
                )
                self.assertFalse(result.accepted)
                self.assertIn("substitution is forbidden", result.problems)

    def test_every_nonempty_true_subset_needs_an_exact_human_decision_record(
        self,
    ) -> None:
        """**Validates: Requirements 1.5, 2.5, 3.1**"""
        for size in range(1, 9):
            approved = [entry(index) for index in range(size)]
            for retained in range(size):
                proposed = approved[:retained]
                with self.subTest(size=size, retained=retained):
                    unreviewed = target_fixed_verdict(
                        approved=approved,
                        actual=proposed,
                        proposed=proposed,
                    )
                    self.assertFalse(unreviewed.accepted)
                    reviewed = target_fixed_verdict(
                        approved=approved,
                        actual=proposed,
                        proposed=proposed,
                        human_decision_record=human_decision(approved, proposed),
                    )
                    self.assertTrue(reviewed.accepted)
                    self.assertEqual(reviewed.verdict, "reduced")

    def test_a_decision_record_cannot_be_reused_for_another_reduction(self) -> None:
        approved = [entry(0), entry(1), entry(2)]
        first = approved[:2]
        other = approved[1:]
        result = target_fixed_verdict(
            approved=approved,
            actual=other,
            proposed=other,
            human_decision_record=human_decision(approved, first),
        )
        self.assertFalse(result.accepted)
        self.assertIn(
            "human decision record does not bind the proposed baseline",
            result.problems,
        )


class MutationAndPassControls(unittest.TestCase):
    def test_scope_broadening_mutations_are_rejected(self) -> None:
        """**Validates: Requirements 1.5, 2.5**"""
        mutations = (
            {"target_path": "docs/**"},
            {"target_path": "docs/"},
            {"target_path": "../docs/fixture.md"},
            {"rule_id": "public-*"},
            {"category": "all"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                broadened = entry(**mutation)
                result = target_fixed_verdict(approved=[broadened], actual=[broadened])
                self.assertFalse(result.accepted)
                self.assertTrue(
                    any(
                        "scope" in problem or "exact" in problem
                        for problem in result.problems
                    )
                )

    def test_stale_surplus_mutation_is_rejected(self) -> None:
        approved = [entry(0), entry(1)]
        result = target_fixed_verdict(approved=approved, actual=approved[:1])
        self.assertFalse(result.accepted)
        self.assertIn("stale baseline surplus is forbidden", result.problems)

    def test_same_target_with_changed_governance_metadata_is_substitution(self) -> None:
        approved = [entry(0)]
        for field, value in (
            ("reason", "A different reason"),
            ("approved_revision", "c" * 40),
            ("removal_condition", "A broader removal condition"),
        ):
            with self.subTest(field=field):
                proposed = [entry(0, **{field: value})]
                result = target_fixed_verdict(
                    approved=approved,
                    actual=proposed,
                    proposed=proposed,
                    human_decision_record=human_decision(approved, proposed),
                )
                self.assertFalse(result.accepted)
                self.assertIn("substitution is forbidden", result.problems)

    def test_observed_governance_metadata_substitution_is_rejected(self) -> None:
        approved = [entry(0)]
        for field, value in (
            ("reason", "A different observed reason"),
            ("approved_revision", "d" * 40),
            ("removal_condition", "A different observed removal condition"),
        ):
            with self.subTest(field=field):
                actual = [entry(0, **{field: value})]
                result = target_fixed_verdict(approved=approved, actual=actual)
                self.assertFalse(result.accepted)
                self.assertIn(
                    "actual target addition or substitution is not approved",
                    result.problems,
                )
                self.assertIn("stale baseline surplus is forbidden", result.problems)

    def test_duplicate_observed_identity_with_changed_metadata_is_rejected(
        self,
    ) -> None:
        approved = [entry(0)]
        actual = [entry(0), entry(0, reason="A second reason")]
        result = target_fixed_verdict(approved=approved, actual=actual)
        self.assertFalse(result.accepted)
        self.assertIn(
            "actual target addition or substitution is not approved",
            result.problems,
        )

    def test_unchanged_exact_baseline_remains_a_pass_control(self) -> None:
        approved = [entry(0), entry(1)]
        result = target_fixed_verdict(
            approved=approved, actual=list(reversed(approved))
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.verdict, "ok")

    def test_cli_accepts_the_existing_private_zero_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            actual = Path(tmp) / "actual.json"
            document = json.dumps(empty_baseline()) + "\n"
            baseline.write_text(document, encoding="utf-8")
            actual.write_text(document, encoding="utf-8")
            run = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "check_allow_budget.py"),
                    "--target-fixed-baseline",
                    str(baseline),
                    "--target-fixed-actual",
                    str(actual),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("0 entr(ies), ok", run.stdout)


if __name__ == "__main__":
    unittest.main()
