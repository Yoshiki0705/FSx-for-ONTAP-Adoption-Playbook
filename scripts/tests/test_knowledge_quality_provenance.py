"""Task 5.3 controls for audit provenance, pre-mortem/recovery, and dependency pinning.

Four concerns, each a completion condition of the task:

- a run record carries every field that makes a verification reproducible, and the tracked schema
  documents the same shape the validator enforces;
- design's pre-mortem scenarios are each connected to an implementation control that exists, and a
  failure that publishes something a revert cannot erase is classified as an incident rather than a
  reversible rollback;
- every pip dependency is exact-pinned, so a lint verdict does not depend on the day it runs;
- every GitHub Action is pinned to a full commit SHA, so a moved tag cannot change what runs.

The dependency and Action pins are already in place; these are regression controls that fail if a
future change loosens them. No workflow or requirements file is modified here.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from provenance import (
    EXTERNAL_STATES,
    RECOVERY_CLASSES,
    REQUIRED_FIELDS,
    SCHEMA,
    validate_run_record,
)

SCHEMA_PATH = ROOT / "tools" / "provenance-run.schema.json"
MATRIX = ROOT / ".private" / "knowledge-quality" / "phase-1-premortem-recovery.md"
REQUIREMENTS = ROOT / "requirements-dev.txt"
WORKFLOWS = ROOT / ".github" / "workflows"

MATRIX_START = "<!-- premortem-matrix:start -->"
MATRIX_END = "<!-- premortem-matrix:end -->"

SHA1 = re.compile(r"^[0-9a-f]{40}$")
# uses: owner/repo@<ref>  — the ref must be a full 40-char commit SHA, not a tag or branch.
USES_RE = re.compile(r"^\s*uses:\s*(?P<action>[^@\s]+)@(?P<ref>[^\s#]+)")


def valid_run_record() -> dict[str, object]:
    """A record that validates clean; individual tests delete or corrupt one field at a time."""
    return {
        "run_id": "phase-1-selfcheck",
        "public_repository_id": 1,
        "input_sha": "a" * 40,
        "local_head": "b" * 40,
        "local_dirty": False,
        "hub_revision": "c" * 40,
        "validator_artifact_digests": {"tools/check_cross_repo.py": "d" * 64},
        "exact_command": "make test",
        "scan_roots": ["tools", "scripts"],
        "excluded_roots": [".private", ".kiro"],
        "tool_versions": {"ruff": "0.16.7", "shellcheck": "not-run: offline"},
        "action_shas": ["e" * 40],
        "runner_image": "ubuntu-latest",
        "deterministic_result": "pass",
        "external_result": "INCONCLUSIVE",
        "baseline_before": "sha256:" + "0" * 64,
        "baseline_after": "sha256:" + "0" * 64,
        "aggregate_digest": "f" * 64,
        "human_phase_decision": "phase-1-human-decision.json",
        "recovery_class": "reversible",
    }


class ProvenanceRecordTests(unittest.TestCase):
    def test_a_complete_record_is_accepted(self) -> None:
        """**Validates: Requirements 1.11, 2.11**"""
        self.assertEqual(validate_run_record(valid_run_record()), [])

    def test_deleting_any_required_field_is_rejected(self) -> None:
        """**Validates: Requirements 1.11, 2.11** — every field is load-bearing."""
        for field in REQUIRED_FIELDS:
            with self.subTest(field=field):
                record = valid_run_record()
                del record[field]
                problems = validate_run_record(record)
                self.assertTrue(problems)
                self.assertTrue(any(field in problem for problem in problems))

    def test_external_result_keeps_three_state_vocabulary(self) -> None:
        """**Validates: Requirements 3.6** — a non-answer is never a silent pass or defect."""
        self.assertEqual(set(EXTERNAL_STATES), {"PASS", "DEFECT", "INCONCLUSIVE"})
        record = valid_run_record()
        record["external_result"] = "OK"
        self.assertTrue(
            any("external_result" in problem for problem in validate_run_record(record))
        )

    def test_recovery_class_is_constrained(self) -> None:
        record = valid_run_record()
        record["recovery_class"] = "maybe"
        self.assertTrue(
            any("recovery_class" in problem for problem in validate_run_record(record))
        )

    def test_malformed_sha_fields_are_rejected(self) -> None:
        for field in ("input_sha", "local_head", "hub_revision", "aggregate_digest"):
            with self.subTest(field=field):
                record = valid_run_record()
                record[field] = "not-a-digest"
                self.assertTrue(
                    any(field in problem for problem in validate_run_record(record))
                )

    def test_unknown_field_is_rejected(self) -> None:
        record = valid_run_record()
        record["surprise"] = 1
        self.assertTrue(
            any("unknown" in problem for problem in validate_run_record(record))
        )

    def test_non_object_record_is_rejected(self) -> None:
        self.assertTrue(validate_run_record(["not", "an", "object"]))


class SchemaValidatorSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_schema_id_required_and_properties_match_the_validator(self) -> None:
        self.assertEqual(self.schema["$id"], SCHEMA)
        self.assertEqual(set(self.schema["required"]), set(REQUIRED_FIELDS))
        self.assertEqual(set(self.schema["properties"]), set(REQUIRED_FIELDS))
        self.assertFalse(self.schema["additionalProperties"])

    def test_schema_enums_match_the_validator(self) -> None:
        self.assertEqual(
            set(self.schema["properties"]["external_result"]["enum"]),
            set(EXTERNAL_STATES),
        )
        self.assertEqual(
            set(self.schema["properties"]["recovery_class"]["enum"]),
            set(RECOVERY_CLASSES),
        )


def parse_matrix() -> list[dict[str, str]]:
    """Rows of the machine-readable pre-mortem table: number, scenario, control, recovery_class."""
    lines = MATRIX.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if MATRIX_START in line)
    end = next(i for i, line in enumerate(lines) if MATRIX_END in line)
    rows: list[dict[str, str]] = []
    for raw in lines[start + 1 : end]:
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 4 or cells[0] in {"#"} or cells[0].startswith("---"):
            continue
        rows.append(
            {
                "number": cells[0],
                "scenario": cells[1],
                "control": cells[2],
                "recovery_class": cells[3],
            }
        )
    return rows


@unittest.skipUnless(
    MATRIX.exists(),
    "the pre-mortem/recovery matrix lives under .private/, which is gitignored and absent in CI. "
    "These tests read the real matrix to confirm each scenario names a control that exists; where "
    "it is absent they are skipped, not passed. Skipping must not be read as agreement.",
)
class ScenarioToControlCompletenessTests(unittest.TestCase):
    def test_at_least_five_scenarios_connect_to_an_existing_control(self) -> None:
        """**Validates: Requirements 1.11, 2.11** — a scenario names a control that exists."""
        rows = parse_matrix()
        self.assertGreaterEqual(len(rows), 5, "fewer than five scenarios are recorded")
        missing = [
            row["control"] for row in rows if not (ROOT / row["control"]).is_file()
        ]
        self.assertEqual(
            missing, [], f"these controls name a file that does not exist: {missing}"
        )

    def test_every_recovery_class_is_valid(self) -> None:
        rows = parse_matrix()
        invalid = [
            row["recovery_class"]
            for row in rows
            if row["recovery_class"] not in RECOVERY_CLASSES
        ]
        self.assertEqual(invalid, [], f"invalid recovery_class values: {invalid}")

    def test_public_leak_scenarios_are_classified_as_incident(self) -> None:
        """**Validates: Requirements 2.10, 3.1** — a leak is not an ordinary reversible rollback.

        A revert does not erase a published secret, PII, or Git history. The two scenarios whose
        failure publishes something (the private-ledger leak, and a suppression broad enough to let
        a real violation reach a published file) must be classified incident, not reversible.
        """
        rows = parse_matrix()
        leak_rows = [
            row
            for row in rows
            if "leak" in row["scenario"].lower()
            or "suppression" in row["scenario"].lower()
        ]
        self.assertTrue(leak_rows, "no public-leak scenario found to classify")
        misclassified = [
            row["scenario"] for row in leak_rows if row["recovery_class"] != "incident"
        ]
        self.assertEqual(
            misclassified,
            [],
            f"these leak scenarios are not incident-classified: {misclassified}",
        )


class DependencyPinningTests(unittest.TestCase):
    def test_every_pip_dependency_is_exact_pinned(self) -> None:
        """**Validates: Requirements 3.1** — an unpinned dependency makes the verdict drift."""
        unpinned: list[str] = []
        for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "==" not in line or any(
                op in line for op in (">=", "<=", "~=", ">", "<", "!=")
            ):
                unpinned.append(line)
        self.assertEqual(
            unpinned, [], f"these dependencies are not exact-pinned: {unpinned}"
        )


class WorkflowActionPinningTests(unittest.TestCase):
    def test_every_action_is_pinned_to_a_full_commit_sha(self) -> None:
        """**Validates: Requirements 3.1** — a moved tag must not change what CI runs."""
        workflows = sorted(WORKFLOWS.glob("*.y*ml"))
        self.assertTrue(workflows, "no workflow files found, so this check is vacuous")
        unpinned: list[str] = []
        for path in workflows:
            for raw in path.read_text(encoding="utf-8").splitlines():
                match = USES_RE.match(raw)
                if match and SHA1.fullmatch(match.group("ref")) is None:
                    unpinned.append(
                        f"{path.name}: {match.group('action')}@{match.group('ref')}"
                    )
        self.assertEqual(
            unpinned, [], f"these Actions are not pinned to a full SHA: {unpinned}"
        )

    def test_the_parser_detects_an_unpinned_action(self) -> None:
        """The break case: a green run must be distinguishable from a dead parser."""
        match = USES_RE.match("      uses: actions/checkout@v4")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIsNone(SHA1.fullmatch(match.group("ref")))


if __name__ == "__main__":
    unittest.main()
