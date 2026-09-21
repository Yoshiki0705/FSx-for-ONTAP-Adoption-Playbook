from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from issue_ledger import (
    FINAL_STATES,
    REQUIRED_FIELDS,
    SCHEMA_VERSION,
    can_enter_roadmap,
    transition_issue,
    validation_errors,
)

from scripts.tests.gitenv import scrubbed_env

PRIVATE_DIR = ROOT / ".private" / "knowledge-quality"
SCHEMA_PATH = PRIVATE_DIR / "issue-ledger.schema.json"
LEDGER_PATH = PRIVATE_DIR / "issues.jsonl"


def complete_record(*, state: str = "triaged") -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "issue_id": "fixture-issue",
        "repository_summary": "Documentation Hub fixture",
        "target_kind": "local-kiro",
        "target_authority_id": "fixture-target",
        "affected_location": "fixture/path.md",
        "category": "judgment-prose",
        "severity": "minor",
        "severity_decision_source": "human",
        "severity_decision_revision": "a" * 40,
        "evidence_class": "open",
        "determinism": "human-judgment",
        "authority": "Hub",
        "exposure": "private-detail",
        "state": state,
        "impact": "A reviewer could reach a different publication decision.",
        "remediation_direction": "Route the candidate through recorded human review.",
        "dependencies": [],
        "verification_method": "Review the named revision and record the decision.",
        "accountable_owner": "Human phase approver",
        "priority": "P2",
        "completion_condition": {
            "check": "human decision record is complete",
            "expected": True,
        },
        "source_revision": "b" * 40,
        "observed_at": "2026-09-18T00:00:00Z",
        "ai_signal": {
            "candidate": "possible logical leap",
            "reason": "the conclusion introduces an unstated premise",
        },
    }


class IssueLedgerSchemaTests(unittest.TestCase):
    @unittest.skipUnless(
        SCHEMA_PATH.exists() and LEDGER_PATH.exists(),
        "the private schema and ledger live under .private/, which is gitignored and absent in CI. "
        "This test checks that the real private artifacts use the implemented vocabulary; where "
        "they are absent it is skipped, not a pass. Skipping must not be read as agreement.",
    )
    def test_private_schema_and_ledger_use_the_implemented_vocabulary(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], SCHEMA_VERSION)
        self.assertEqual(set(schema["required"]), set(REQUIRED_FIELDS))
        records = [
            json.loads(line)
            for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(records)
        for record in records:
            self.assertEqual(validation_errors(record), [])
            self.assertTrue(can_enter_roadmap(record))

    def test_complete_record_is_admitted(self) -> None:
        """**Validates: Requirements 1.7, 2.7, 3.4**"""
        record = complete_record()
        self.assertEqual(validation_errors(record), [])
        self.assertTrue(can_enter_roadmap(record))

    def test_schema_boundary_rejects_unknown_fields_and_wrong_authority_types(
        self,
    ) -> None:
        """**Validates: Requirements 1.6, 1.7, 2.6, 2.7**"""
        unknown = complete_record()
        unknown["approval"] = "AI-proposed-value"
        self.assertIn(
            "unsupported issue fields: ['approval']", validation_errors(unknown)
        )
        self.assertFalse(can_enter_roadmap(unknown))

        extra_completion = complete_record()
        extra_completion["completion_condition"]["note"] = "unvalidated"
        self.assertTrue(
            any(
                "completion_condition must contain only" in error
                for error in validation_errors(extra_completion)
            )
        )

        for kind, authority_id in (
            ("public-github", "123"),
            ("public-github", True),
            ("public-github", 0),
            ("local-kiro", 123),
        ):
            with self.subTest(kind=kind, authority_id=authority_id):
                record = complete_record()
                record["target_kind"] = kind
                record["target_authority_id"] = authority_id
                self.assertTrue(validation_errors(record))
                self.assertFalse(can_enter_roadmap(record))

        public_record = complete_record()
        public_record["target_kind"] = "public-github"
        public_record["target_authority_id"] = 123
        self.assertEqual(validation_errors(public_record), [])


class RequiredFieldDeletionPropertyTests(unittest.TestCase):
    def test_deleting_any_required_field_or_nonempty_subset_rejects_admission(
        self,
    ) -> None:
        """**Validates: Requirements 1.7, 2.7, 3.4**"""
        original = complete_record()
        deletion_sets = [{field} for field in REQUIRED_FIELDS]
        deletion_sets.extend(
            {REQUIRED_FIELDS[index], REQUIRED_FIELDS[index + 1]}
            for index in range(len(REQUIRED_FIELDS) - 1)
        )
        deletion_sets.append(set(REQUIRED_FIELDS))
        for deleted in deletion_sets:
            with self.subTest(deleted=sorted(deleted)):
                candidate = {
                    key: value for key, value in original.items() if key not in deleted
                }
                self.assertFalse(can_enter_roadmap(candidate))
                for field in deleted:
                    self.assertIn(
                        f"missing required field: {field}", validation_errors(candidate)
                    )


class HumanDecisionStatePropertyTests(unittest.TestCase):
    def test_every_final_state_requires_human_decision_reason_revision_and_time(
        self,
    ) -> None:
        """**Validates: Requirements 1.2, 2.2, 3.3**"""
        decision = {
            "human_decision": "closed",
            "decision_reason": "The named revision satisfies the completion condition.",
            "decision_revision": "c" * 40,
            "decided_at": "2026-09-18T01:00:00Z",
        }
        for final_state in FINAL_STATES:
            for missing in decision:
                with self.subTest(final_state=final_state, missing=missing):
                    record = complete_record(state=final_state)
                    record.update(decision)
                    del record[missing]
                    self.assertTrue(
                        any(
                            "final state requires human_decision" in error
                            for error in validation_errors(record)
                        )
                    )
                    self.assertFalse(can_enter_roadmap(record))

    def test_ai_signal_cannot_finalize_decisions_or_transitions(self) -> None:
        """**Validates: Requirements 1.2, 2.2, 3.3**"""
        forbidden_fields = (
            "severity",
            "waiver",
            "approval",
            "rejection",
            "closure",
            "phase_transition",
            "human_decision",
            "decision_reason",
            "decision_revision",
            "decided_at",
            "state",
        )
        for field in forbidden_fields:
            with self.subTest(field=field):
                record = complete_record()
                record["ai_signal"][field] = "AI-proposed-value"
                self.assertTrue(
                    any("ai_signal" in error for error in validation_errors(record))
                )
                self.assertFalse(can_enter_roadmap(record))
        with self.assertRaisesRegex(ValueError, "AI assistive signals"):
            transition_issue(complete_record(), "planned", actor="ai")

    def test_state_machine_accepts_only_defined_edges_and_human_finalization(
        self,
    ) -> None:
        allowed_path = (
            "discovered",
            "triaged",
            "planned",
            "fixing",
            "verifying",
            "resolved",
        )
        record = complete_record(state=allowed_path[0])
        for target in allowed_path[1:-1]:
            record = transition_issue(record, target, actor="validator")
            self.assertEqual(record["state"], target)
        with self.assertRaisesRegex(ValueError, "human transition actor"):
            transition_issue(record, "resolved", actor="validator")
        record.update(
            {
                "human_decision": "closed",
                "decision_reason": "The objective verification completed.",
                "decision_revision": "d" * 40,
                "decided_at": "2026-09-18T02:00:00Z",
            }
        )
        resolved = transition_issue(record, "resolved", actor="human")
        self.assertEqual(resolved["state"], "resolved")
        with self.assertRaisesRegex(ValueError, "invalid state transition"):
            transition_issue(resolved, "planned", actor="human")


class PrivateBoundaryTests(unittest.TestCase):
    def test_private_ledger_sentinels_are_absent_from_tracked_files(self) -> None:
        """**Validates: Requirements 1.8, 2.8, 3.4**"""
        sentinels = ("KQ-" + "0001", "hub-" + "phase-0")
        tracked = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            env=scrubbed_env(),
        ).stdout.split(b"\0")
        hits: list[str] = []
        for raw_path in tracked:
            if not raw_path:
                continue
            path = ROOT / raw_path.decode()
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for sentinel in sentinels:
                if sentinel in content:
                    hits.append(f"{path.relative_to(ROOT)}: {sentinel}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
