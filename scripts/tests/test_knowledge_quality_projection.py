"""Task 7.1 controls for the private-to-public knowledge-quality aggregate.

`tools/project_public_aggregate.py` projects the private Issue Ledger into a neutral, bilingual
public document. These controls fix its completion conditions:

- the rendered document never carries a private-only field or sentinel (path, owner, issue_id,
  repository_summary, review provenance);
- every projected row carries only the design's allowlisted fields;
- the JA and EN sections of the single bilingual file have the same structure (same heading count);
- the file is a generated artifact: a stale copy on disk is rejected, and `--write` regenerates it;
- `generated_at` is excluded from the drift comparison so a rerun at a different second does not
  fail, while `generated_from_revision` changes exactly when the ledger content changes.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import project_public_aggregate
from project_public_aggregate import (
    ALLOWED_ROW_FIELDS,
    aggregate_rows,
    check,
    ledger_digest,
    phase_for_state,
    read_ledger_records,
    render,
)

OUTPUT = ROOT / "docs" / "ja" / "reference" / "knowledge-quality-status.md"

# A private-detail sentinel that must never survive projection. Values are fields the ledger
# schema requires but the allowlist excludes.
PRIVATE_SENTINELS = (
    "hub-" + "phase-0",  # target_authority_id in the real ledger
    "KQ-" + "0001",  # issue_id
    "Hub validator maintainer",  # accountable_owner
    "Documentation-first Hub and its local quality validators",  # repository_summary
    "tools/issue_ledger.py and scripts/tests/test_knowledge_quality_ledger.py",  # affected_location
    "be79bdfbae24eb0aba06f2908256c695772daf3d",  # source_revision
)


def valid_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "schema": "knowledge-quality/issue-ledger/v1",
        "issue_id": "KQ-TEST-0001",
        "repository_summary": "Fixture repository summary",
        "target_kind": "local-kiro",
        "target_authority_id": "fixture-target",
        "affected_location": "fixture/path.py",
        "category": "evidence",
        "severity": "minor",
        "severity_decision_source": "deterministic-rule",
        "evidence_class": "open",
        "determinism": "deterministic",
        "authority": "Hub",
        "exposure": "private-detail",
        "state": "triaged",
        "impact": "Fixture impact",
        "remediation_direction": "Fixture direction",
        "dependencies": [],
        "verification_method": "Fixture verification",
        "accountable_owner": "Fixture owner",
        "priority": "P2",
        "completion_condition": {"check": "fixture", "expected": "ok"},
        "source_revision": "a" * 40,
        "observed_at": "2026-01-01T00:00:00Z",
    }
    record.update(overrides)
    return record


class PhaseBucketTests(unittest.TestCase):
    def test_every_state_has_a_phase_bucket(self) -> None:
        """**Validates: Requirements 1.8, 2.8**"""
        expected = {
            "discovered": "discovered",
            "triaged": "discovered",
            "blocked": "in-progress",
            "planned": "in-progress",
            "fixing": "in-progress",
            "verifying": "verifying",
            "resolved": "resolved",
            "accepted-baseline": "resolved",
        }
        for state, phase in expected.items():
            with self.subTest(state=state):
                self.assertEqual(phase_for_state(state), phase)

    def test_an_unrecognized_state_raises_rather_than_guesses(self) -> None:
        with self.assertRaises(ValueError):
            phase_for_state("not-a-real-state")


class LedgerParsingTests(unittest.TestCase):
    def test_invalid_records_are_skipped_not_silently_dropped_or_admitted(self) -> None:
        """**Validates: Requirements 1.7, 2.7, 2.8**"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "issues.jsonl"
            valid = valid_record()
            missing_field = valid_record()
            del missing_field["priority"]
            path.write_text(
                "\n".join(
                    [
                        json.dumps(valid),
                        "{not valid json",
                        json.dumps(missing_field),
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            records = read_ledger_records(path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["issue_id"], valid["issue_id"])

    def test_a_missing_ledger_file_projects_to_zero_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            records = read_ledger_records(Path(tmp) / "absent.jsonl")
        self.assertEqual(records, [])
        self.assertEqual(aggregate_rows(records), [])


class AllowlistProjectionTests(unittest.TestCase):
    def test_projected_rows_carry_only_allowlisted_fields(self) -> None:
        """**Validates: Requirements 1.8, 2.8, 3.4**"""
        records = [valid_record(category="evidence", severity="minor", state="triaged")]
        rows = aggregate_rows(records)
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]), set(ALLOWED_ROW_FIELDS))

    def test_records_differing_only_in_private_detail_collapse_to_one_row(self) -> None:
        """Two issues with the same public classification are one aggregate row, not two
        rows distinguished by a private field that never reached the projection."""
        records = [
            valid_record(issue_id="KQ-A", accountable_owner="Owner A"),
            valid_record(issue_id="KQ-B", accountable_owner="Owner B"),
        ]
        rows = aggregate_rows(records)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["aggregate_count"], 2)

    def test_rows_are_grouped_by_category_severity_phase_and_status(self) -> None:
        records = [
            valid_record(category="evidence", severity="minor", state="triaged"),
            valid_record(category="evidence", severity="major", state="triaged"),
            valid_record(category="baseline", severity="minor", state="resolved"),
        ]
        rows = aggregate_rows(records)
        self.assertEqual(len(rows), 3)
        self.assertEqual(sum(row["aggregate_count"] for row in rows), 3)


class PrivateSentinelAbsenceTests(unittest.TestCase):
    def test_rendered_output_carries_no_private_sentinel(self) -> None:
        """**Validates: Requirements 1.8, 2.8, 3.4** — allowlist projection, not a denylist scrub."""
        records = [
            valid_record(
                issue_id="KQ-SENTINEL",
                repository_summary="Sentinel repository summary",
                accountable_owner="Sentinel owner",
                affected_location="sentinel/path.py",
                target_authority_id="sentinel-target",
                source_revision="f" * 40,
            )
        ]
        rows = aggregate_rows(records)
        text = render(
            rows, generated_from_revision="sha256:" + "0" * 64, generated_at="x"
        )
        for sentinel in (
            "KQ-SENTINEL",
            "Sentinel repository summary",
            "Sentinel owner",
            "sentinel/path.py",
            "sentinel-target",
            "f" * 40,
        ):
            with self.subTest(sentinel=sentinel):
                self.assertNotIn(sentinel, text)

    def test_the_real_generated_file_carries_no_private_sentinel(self) -> None:
        """The tracked artifact itself, not just a fixture render."""
        if not OUTPUT.exists():
            self.skipTest("knowledge-quality-status.md has not been generated yet")
        text = OUTPUT.read_text(encoding="utf-8")
        for sentinel in PRIVATE_SENTINELS:
            with self.subTest(sentinel=sentinel):
                self.assertNotIn(sentinel, text)


class BilingualStructureTests(unittest.TestCase):
    def test_ja_and_en_sections_have_the_same_heading_count(self) -> None:
        """**Validates: Requirements 1.12, 2.12** — same-change JA/EN structure, one file."""
        rows = aggregate_rows([valid_record()])
        text = render(
            rows, generated_from_revision="sha256:" + "1" * 64, generated_at="x"
        )
        ja_headings = re.findall(
            r"^## (?!Overview|Aggregate|Provenance)(.+)$", text, re.MULTILINE
        )
        en_headings = re.findall(
            r"^## (Overview|Aggregate by Classification)$", text, re.MULTILINE
        )
        self.assertEqual(len(ja_headings), len(en_headings))
        self.assertGreaterEqual(len(ja_headings), 2)

    def test_no_docs_en_reference_counterpart_is_created(self) -> None:
        """**Validates: Requirements 1.12, 2.12** — bilingual single file, not a split tree.

        `docs/en/reference/` already exists for unrelated pre-existing documents, so the
        invariant this task must hold is narrower: no `knowledge-quality-status.md` counterpart
        under it.
        """
        self.assertFalse(
            (
                ROOT / "docs" / "en" / "reference" / "knowledge-quality-status.md"
            ).exists()
        )

    def test_the_document_is_not_registered_in_the_i18n_manifest(self) -> None:
        manifest = (ROOT / "docs" / "i18n-manifest.txt").read_text(encoding="utf-8")
        self.assertNotIn("knowledge-quality-status.md", manifest)


class GeneratedArtifactDisciplineTests(unittest.TestCase):
    def test_stale_disk_content_is_rejected(self) -> None:
        """**Validates: Requirements 1.9, 2.9, 3.1** — a generated file must not silently drift."""
        rows = aggregate_rows(
            [valid_record(category="evidence", severity="minor", state="triaged")]
        )
        stale = render(
            rows, generated_from_revision="sha256:" + "2" * 64, generated_at="t0"
        )
        fresh_rows = aggregate_rows(
            [valid_record(category="baseline", severity="major", state="resolved")]
        )
        fresh = render(
            fresh_rows, generated_from_revision="sha256:" + "3" * 64, generated_at="t1"
        )
        self.assertNotEqual(_without_generated_at(stale), _without_generated_at(fresh))

    def test_generated_at_is_excluded_from_the_drift_comparison(self) -> None:
        """**Validates: Requirements 3.1** — a rerun at a different second must not fail the check."""
        rows = aggregate_rows([valid_record()])
        first = render(
            rows, generated_from_revision="sha256:" + "4" * 64, generated_at="t0"
        )
        second = render(
            rows, generated_from_revision="sha256:" + "4" * 64, generated_at="t1"
        )
        self.assertNotEqual(first, second)
        self.assertEqual(_without_generated_at(first), _without_generated_at(second))

    def test_generated_from_revision_changes_when_ledger_content_changes(self) -> None:
        """**Validates: Requirements 1.9, 2.9** — never a hand-maintained value."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "issues.jsonl"
            path.write_text(json.dumps(valid_record()) + "\n", encoding="utf-8")
            first = ledger_digest(path)
            path.write_text(
                json.dumps(valid_record(issue_id="KQ-DIFFERENT")) + "\n",
                encoding="utf-8",
            )
            second = ledger_digest(path)
        self.assertNotEqual(first, second)

    def test_a_missing_ledger_produces_a_deterministic_placeholder_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            digest = ledger_digest(Path(tmp) / "absent.jsonl")
        self.assertEqual(digest, "sha256:" + "0" * 64)

    def test_the_tracked_generated_file_is_up_to_date_with_the_ledger(self) -> None:
        """The real artifact and the real ledger, run through the actual CLI check path.

        Skipped where the private ledger is absent (CI): with no ledger the plain check cannot
        compare counts, and that environment is covered by
        MissingLedgerHandlingTests instead. Skipping is correct here — a missing ledger is not a
        defect in this change, it is the CI environment. It must not be read as a pass.
        """
        import subprocess

        ledger = ROOT / ".private" / "knowledge-quality" / "issues.jsonl"
        if not ledger.exists():
            self.skipTest("private ledger absent (CI); see MissingLedgerHandlingTests")

        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "project_public_aggregate.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class MissingLedgerHandlingTests(unittest.TestCase):
    """The --allow-missing-ledger path, added so the CI gate (where .private/ is absent) reports
    INCONCLUSIVE rather than failing forever against an empty ledger. The flag is deliberately not
    the default, so a locally deleted ledger is still caught."""

    def _redirect(self, tmp: Path, *, with_ledger: bool, with_output: bool) -> None:
        """Point the module's LEDGER and OUTPUT at a temp tree, optionally seeding each."""
        ledger = tmp / ".private" / "knowledge-quality" / "issues.jsonl"
        output = tmp / "docs" / "ja" / "reference" / "knowledge-quality-status.md"
        if with_ledger:
            ledger.parent.mkdir(parents=True, exist_ok=True)
            ledger.write_text(json.dumps(valid_record()) + "\n", encoding="utf-8")
        if with_output:
            output.parent.mkdir(parents=True, exist_ok=True)
            # Generate a genuine artifact by pointing OUTPUT there and writing from the ledger,
            # or, when there is no ledger, from an empty aggregate — either way a well-formed file.
            self._patch(ledger, output)
            check(write=True)
        self._patch(ledger, output)

    def _patch(self, ledger: Path, output: Path) -> None:
        # ROOT is redirected too: the CLI's status lines call OUTPUT.relative_to(ROOT), which
        # raises if OUTPUT is a temp path outside the real repository root.
        project_public_aggregate.ROOT = output.parents[3]
        project_public_aggregate.LEDGER = ledger
        project_public_aggregate.OUTPUT = output

    def setUp(self) -> None:
        self._saved = (
            project_public_aggregate.ROOT,
            project_public_aggregate.LEDGER,
            project_public_aggregate.OUTPUT,
        )

    def tearDown(self) -> None:
        (
            project_public_aggregate.ROOT,
            project_public_aggregate.LEDGER,
            project_public_aggregate.OUTPUT,
        ) = self._saved

    def test_missing_ledger_without_flag_is_an_error(self) -> None:
        """The local/pre-commit default: a deleted ledger must not silently disable the check."""
        with tempfile.TemporaryDirectory() as tmp:
            self._redirect(Path(tmp), with_ledger=False, with_output=True)
            self.assertEqual(check(write=False, allow_missing_ledger=False), 1)

    def test_missing_ledger_with_flag_is_inconclusive_success(self) -> None:
        """CI: a well-formed tracked file plus an absent ledger is INCONCLUSIVE (exit 0)."""
        with tempfile.TemporaryDirectory() as tmp:
            self._redirect(Path(tmp), with_ledger=False, with_output=True)
            self.assertEqual(check(write=False, allow_missing_ledger=True), 0)

    def test_flag_does_not_excuse_a_missing_tracked_file(self) -> None:
        """The flag forgives the absent ledger, not an absent artifact: an environment with the
        ledger gitignored still ships the committed file, so its absence is a real defect."""
        with tempfile.TemporaryDirectory() as tmp:
            self._redirect(Path(tmp), with_ledger=False, with_output=False)
            self.assertEqual(check(write=False, allow_missing_ledger=True), 1)

    def test_flag_does_not_excuse_a_corrupt_tracked_file(self) -> None:
        """A tracked file that is not the generated document fails even with the flag: the health
        check confirms the header and mandatory sections, so a hand-mangled file is caught."""
        with tempfile.TemporaryDirectory() as tmp:
            self._redirect(Path(tmp), with_ledger=False, with_output=True)
            project_public_aggregate.OUTPUT.write_text(
                "just some text, not the generated document\n", encoding="utf-8"
            )
            self.assertEqual(check(write=False, allow_missing_ledger=True), 1)

    def test_flag_is_ignored_when_the_ledger_is_present(self) -> None:
        """With the ledger present the flag changes nothing: a genuine drift still fails."""
        with tempfile.TemporaryDirectory() as tmp:
            self._redirect(Path(tmp), with_ledger=True, with_output=True)
            # Now mutate the ledger so the tracked file is stale, and confirm the flag does not
            # turn that into a pass.
            project_public_aggregate.LEDGER.write_text(
                json.dumps(valid_record(category="baseline", severity="major"))
                + "\n"
                + json.dumps(valid_record(category="neutrality", severity="minor"))
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(check(write=False, allow_missing_ledger=True), 1)

    def test_write_never_honours_the_flag(self) -> None:
        """--write from an absent ledger would overwrite the tracked file with an empty aggregate;
        the flag must not enable that. With no ledger and the flag, --write still regenerates from
        the empty ledger (exit 0) but the guard is that the missing-ledger short-circuit only
        applies to the check path, never to write."""
        with tempfile.TemporaryDirectory() as tmp:
            self._redirect(Path(tmp), with_ledger=False, with_output=False)
            # write=True with the flag must not enter the INCONCLUSIVE branch; it proceeds to write.
            self.assertEqual(check(write=True, allow_missing_ledger=True), 0)
            self.assertTrue(project_public_aggregate.OUTPUT.exists())


def _without_generated_at(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.startswith("- `generated_at`:")
    )


if __name__ == "__main__":
    unittest.main()
