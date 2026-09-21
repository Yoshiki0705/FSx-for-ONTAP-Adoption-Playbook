"""Exploration properties for the unfixed cross-repository quality process.

The fixtures are deliberately minimal and live only in a temporary directory.  This task does not
implement the production decision path.  Until ``tools/knowledge_quality.py`` provides
``evaluate_quality_input``, the adapter records the currently observable ACCEPT, ADVANCE, or PUBLISH
result for controls that are absent or whose present scan scope does not cover the input.

The test is expected to fail on the unfixed revision.  Its JSONL output is the minimized input set
that a later fix must reject, hold for review, classify as inconclusive, or stop from advancing.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Self
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
COUNTEREXAMPLES = (
    ROOT / ".private" / "knowledge-quality" / "exploration-counterexamples.jsonl"
)
PRESERVATION_BASELINE = (
    ROOT / ".private" / "knowledge-quality" / "preservation-baseline.json"
)
sys.path.insert(0, str(TOOLS))

import audit_public_output
import check_i18n_parity
import sync_lang_switcher
import validate_frontmatter
from audit_public_output import audit_line, iter_files
from check_allow_budget import allow_verdict
from check_cross_repo import Row as OutboundRow
from check_cross_repo import (
    check_contract,
    check_external,
    check_offline,
    contract_lines,
    parse_table,
    stored_contract,
)
from check_inbound_probes import check as check_inbound
from check_inbound_probes import parse_contract as parse_inbound_contract
from validate_frontmatter import collect

from scripts.tests.test_ci_gate_parity import (
    COVERED_ANOTHER_WAY,
    MAKEFILE,
    calls_in_all_workflows,
    leaf_gates,
    prerequisites,
)
from scripts.tests.test_mutation_discrimination import MUTATIONS

MUTATION_NAMES = frozenset(mutation["name"] for mutation in MUTATIONS)


def load_tests(
    loader: unittest.TestLoader,
    tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    """Exclude only the intentionally failing exploration from routine discovery.

    Task 1 invokes the fully qualified exploration class, which bypasses this module-level hook and
    preserves the expected failure.  Preservation is expected to pass before and after the fix, so
    routine discovery includes it alongside the exploration fixture-generation control.
    """
    del tests, pattern
    return unittest.TestSuite(
        [
            unittest.FunctionTestCase(_check_exploration_fixture_generation),
            loader.loadTestsFromTestCase(FamilyCoverageTests),
            loader.loadTestsFromTestCase(PreservationPropertyTests),
        ]
    )


@dataclass(frozen=True)
class BugInput:
    family: str
    payload: dict[str, Any]
    original_decision: str
    expected_decision: str


@dataclass(frozen=True)
class Observation:
    family: str
    minimized_input: dict[str, Any]
    original_decision: str
    expected_decision: str


def generated_bug_conditions() -> tuple[BugInput, ...]:
    """Generate one minimized member of every required exploration family.

    **Validates: Requirements 1.1–1.12, 2.1–2.12**
    """
    return (
        BugInput(
            "evidence_metadata_missing",
            {"evidence": "verified", "missing": "region"},
            "ACCEPT",
            "REJECT",
        ),
        BugInput(
            "baseline_target_added",
            {"recorded": [], "actual": ["docs/new.md|rule-a|fingerprint-a"]},
            "ACCEPT",
            "REJECT",
        ),
        BugInput(
            "baseline_target_substituted",
            {
                "recorded": ["docs/a.md|rule-a|fingerprint-a"],
                "actual": ["docs/b.md|rule-a|fingerprint-b"],
            },
            "ACCEPT",
            "REJECT",
        ),
        BugInput(
            "baseline_scope_broadened",
            {
                "recorded": ["docs/a.md|rule-a|fingerprint-a"],
                "actual": ["docs/*|rule-a|fingerprint-a"],
            },
            "ACCEPT",
            "REJECT",
        ),
        BugInput(
            "duplicate_local_checkouts",
            {"repository_id": 1, "checkouts": ["checkout-a", "checkout-b"]},
            "ADVANCE",
            "REJECT",
        ),
        BugInput(
            "ai_signal_finalized",
            {"ai_signal": "logical-leap", "human_decision": None},
            "PUBLISH",
            "REVIEW_PENDING",
        ),
        BugInput(
            "private_field_published",
            {"public": {"category": "boundary", "owner": "private-owner"}},
            "PUBLISH",
            "REJECT",
        ),
        BugInput(
            "empty_scan_accepted",
            {"scan_targets": []},
            "ADVANCE",
            "REJECT",
        ),
        BugInput(
            "external_timeout_collapsed",
            {"external_response": "timeout", "classified_as": "PASS"},
            "ADVANCE",
            "INCONCLUSIVE",
        ),
        BugInput(
            "localization_structure_drift",
            {"ja_headings": ["概要"], "en_headings": []},
            "ADVANCE",
            "REJECT",
        ),
        BugInput(
            "major_detector_miss_advanced",
            {"major_miss_count": 1, "family_rescan_complete": False},
            "ADVANCE",
            "ROLLOUT_STOPPED",
        ),
    )


def _check_exploration_fixture_generation() -> None:
    """Keep fixture generation covered without running the expected-failing property."""
    cases = generated_bug_conditions()
    families = {case.family for case in cases}
    if not cases or len(families) != len(cases):
        raise AssertionError(
            "Bug Condition exploration families must be non-empty and unique"
        )
    if any(
        case.original_decision not in {"ACCEPT", "ADVANCE", "PUBLISH"} for case in cases
    ):
        raise AssertionError(
            "every exploration case must expose an unsafe original decision"
        )


def _fixed_evaluator() -> Callable[[dict[str, Any]], dict[str, Any]] | None:
    """Load the future implementation without making its absence an import error."""
    try:
        module = importlib.import_module("knowledge_quality")
    except ModuleNotFoundError as exc:
        if exc.name == "knowledge_quality":
            return None
        raise
    evaluator = getattr(module, "evaluate_quality_input", None)
    if not callable(evaluator):
        return None
    return evaluator


def _materialize_fixture(root: Path, case: BugInput) -> None:
    """Materialize only the files needed to observe current scan boundaries."""
    if case.family == "evidence_metadata_missing":
        # Public prose outside notes/ and without frontmatter is outside collect(root).
        (root / "public-claim.md").write_text("A verified claim.\n", encoding="utf-8")
    elif case.family == "localization_structure_drift":
        ja = root / "docs" / "ja"
        ja.mkdir(parents=True)
        (ja / "quality-guidance.md").write_text(
            "# Guidance\n\n## 概要\n", encoding="utf-8"
        )


def original_process(case: BugInput, fixture_root: Path) -> str:
    """Return the unfixed externally observable decision for one minimized case."""
    if case.family == "evidence_metadata_missing":
        return "ACCEPT" if collect(fixture_root) == [] else "REJECT"
    if case.family == "baseline_target_substituted":
        # The current budget compares a per-path/category count. Equal counts are accepted even
        # though the generalized target and fingerprint changed.
        return "ACCEPT" if allow_verdict(recorded=1, actual=1) == "ok" else "REJECT"
    if case.family == "empty_scan_accepted":
        return "ADVANCE" if list(iter_files(fixture_root)) == [] else "REJECT"
    return case.original_decision


def evaluate(case: BugInput, fixture_root: Path) -> str:
    evaluator = _fixed_evaluator()
    if evaluator is None:
        return original_process(case, fixture_root)
    result = evaluator({"family": case.family, **case.payload})
    # A family the router declines to handle (`routed: False`, `tools/knowledge_quality.py`'s
    # documented, deliberate gap) falls back to the pre-fix behavior for that family alone,
    # rather than the whole property reading "None" as if the router had rejected it.
    if not result.get("routed", True):
        return original_process(case, fixture_root)
    return str(result["decision"])


class BugConditionExplorationTests(unittest.TestCase):
    """Property 1: every Bug Condition must stop unsafe acceptance or advancement."""

    def test_bug_conditions_are_not_accepted(self) -> None:
        """**Validates: Requirements 1.1–1.12, 2.1–2.12**"""
        observations: list[Observation] = []
        with tempfile.TemporaryDirectory() as tmp:
            fixture_root = Path(tmp)
            for case in generated_bug_conditions():
                case_root = fixture_root / case.family
                case_root.mkdir()
                _materialize_fixture(case_root, case)
                actual = evaluate(case, case_root)
                if actual != case.expected_decision:
                    observations.append(
                        Observation(
                            family=case.family,
                            minimized_input=case.payload,
                            original_decision=actual,
                            expected_decision=case.expected_decision,
                        )
                    )

        COUNTEREXAMPLES.parent.mkdir(parents=True, exist_ok=True)
        COUNTEREXAMPLES.write_text(
            "".join(
                json.dumps(asdict(item), ensure_ascii=False, sort_keys=True) + "\n"
                for item in observations
            ),
            encoding="utf-8",
        )

        self.assertEqual(
            observations,
            [],
            "unfixed process accepted, advanced, or published minimized Bug Conditions; "
            f"recorded {len(observations)} counterexamples in "
            ".private/knowledge-quality/exploration-counterexamples.jsonl",
        )


class _Response:
    def __init__(self, body: str) -> None:
        self.body = body.encode()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def _raise_http(status: int) -> Callable[..., _Response]:
    def raise_error(request: object, timeout: int = 0) -> _Response:
        del timeout
        url = getattr(request, "full_url", "https://example.invalid/control")
        error = urllib.error.HTTPError(url, status, "fixture", None, None)
        error.close()
        raise error

    return raise_error


def _external_decision(response_class: str) -> str:
    row = OutboundRow(
        citing="control",
        repo="example-repository",
        path="docs/control.md",
        probe="stable claim",
        role="authority",
        what="preservation control",
        line=1,
    )
    if response_class == "success":

        def successful_response(request: object, timeout: int = 0) -> _Response:
            del request, timeout
            return _Response("stable claim\n")

        side_effect: object = successful_response
    elif response_class == "timeout":
        side_effect = TimeoutError("fixture timeout")
    else:
        side_effect = _raise_http(int(response_class))

    if isinstance(side_effect, BaseException):
        patcher = mock.patch(
            "check_cross_repo.urllib.request.urlopen", side_effect=side_effect
        )
    else:
        patcher = mock.patch("check_cross_repo.urllib.request.urlopen", new=side_effect)
    output = io.StringIO()
    with patcher, contextlib.redirect_stdout(output):
        problems = check_external([row])
    if problems:
        return "DEFECT"
    if "undetermined" in output.getvalue():
        return "INCONCLUSIVE"
    return "PASS"


def generated_valid_notes() -> tuple[tuple[str, str, str], ...]:
    """Generate valid members of every existing evidence tier."""
    common = (
        "title: The control remains reviewable\n"
        "lifecycle: [design]\n"
        "domains: [performance]\n"
        "lang: en\n"
    )
    return (
        (
            "verified",
            common
            + "evidence: verified\nverified_on: 2020-01-01\nregion: ap-northeast-1\n",
            "Reproduced in the stated environment.\n",
        ),
        (
            "documented",
            common
            + "evidence: documented\nsource: https://example.invalid/documentation\n",
            "The source documents this behavior.\n",
        ),
        (
            "field-observation",
            common + "evidence: field-observation\n",
            "Observed once and not reproduced.\n",
        ),
        (
            "hypothesis",
            common + "evidence: hypothesis\n",
            "This hypothesis is untested.\n",
        ),
    )


def generated_preservation_cases() -> tuple[tuple[str, str], ...]:
    """Generate every observable family required by Preservation Property 2.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**
    """
    return (
        ("gate_entry_points", "3.1"),
        ("valid_evidence", "3.1"),
        ("valid_public_output_and_narrow_allow", "3.1"),
        ("claim_authority_and_probe_contracts", "3.2"),
        ("human_judgment_non_blocking", "3.3"),
        ("private_scan_exclusion", "3.4"),
        ("manifest_derived_localization", "3.5"),
        ("disk_derived_switchers", "3.5"),
        ("external_three_state", "3.6"),
        ("no_remote_or_shared_write", "3.7"),
        ("unmeasured_style_signal_non_blocking", "3.8"),
    )


def _write_note(root: Path, name: str, metadata: str, body: str) -> Path:
    notes = root / "docs" / "en" / "domains" / "performance" / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    path = notes / name
    path.write_text(f"---\n{metadata}---\n\n{body}", encoding="utf-8")
    return path


# Each deterministic family in Task 5.2's requirements, indexed to the controls that guard it.
# The index is the deliverable: it puts, in one place, the assertion that every family has a
# negative that fires, a valid control that passes, a plausible-wrong-fix mutation registered in
# test_mutation_discrimination.py, and a scan whose target set is non-empty. The negatives and
# valid controls themselves live in the per-family test files (test_cjk_word_boundaries,
# test_role_label_vocabulary, test_allow_budget_verdicts, ...) and are re-exercised here through
# the same validator entry points, not duplicated.
#
# family -> (mutation names that discriminate a wrong fix for it). Every listed name must exist in
# MUTATIONS, so deleting a mutation without updating this index fails rather than going unnoticed.
FAMILY_MUTATIONS: dict[str, tuple[str, ...]] = {
    "evidence-metadata": ("region requirement removed from the verified tier",),
    "deterministic-prose-naming": (
        "ASCII boundaries emptied",
        "ASCII boundaries replaced by the word boundary they replaced",
        "underscore dropped from the boundary class",
    ),
    "deterministic-prose-role-label": (
        "ordinary viewpoint words returned to the token-free path",
        "the end-anchor dropped from の視点",
        "prefix guards removed from the Japanese role tokens",
    ),
    "public-safety-allow-budget": (
        "allow budget accepts a grown set",
        "allow budget stops reporting surplus",
        "suppression predicate accepts any change",
    ),
    "detector-coverage": (
        "own-org path check removed",
        "self-link path check removed",
        "cited-anchor subset collapsed into every anchor",
    ),
}


class FamilyCoverageTests(unittest.TestCase):
    """Task 5.2: every deterministic family has negative, valid control, mutation, non-empty scope.

    A family is routed to a deterministic validator only if that validator can be shown to fire on
    a bad input, stay silent on a good one, be discriminated from a lazy fix by a registered
    mutation, and run over a non-empty scan target. Missing any leg is the state Requirement 1.10
    forbids: a gate that exists and does not actually guard.
    """

    # --- evidence-metadata (1.1 / 2.1) ---------------------------------------------------------

    def test_evidence_metadata_negative_fires(self) -> None:
        """**Validates: Requirements 1.1, 2.1** — a verified note missing region is rejected.

        This is also the must_fail target of the "region requirement removed from the verified
        tier" mutation: emptying the region check makes this note validate, and this assertion is
        what then fails.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(validate_frontmatter, "ROOT", root):
                path = _write_note(
                    root,
                    "missing-region.md",
                    "title: A verified claim with no region\n"
                    "lifecycle: [design]\n"
                    "domains: [performance]\n"
                    "lang: en\n"
                    "evidence: verified\n"
                    "verified_on: 2020-01-01\n",
                    "Reproduced, but the environment is not named.\n",
                )
                errors, tier = validate_frontmatter.validate(path)
        self.assertEqual(tier, "verified")
        self.assertTrue(
            any("region" in error for error in errors),
            f"a verified note without region must be rejected; got {errors}",
        )

    def test_evidence_metadata_valid_control_passes(self) -> None:
        """The valid control, and the must_pass side of the evidence mutation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(validate_frontmatter, "ROOT", root):
                path = _write_note(
                    root,
                    "with-region.md",
                    "title: A verified claim with its environment named\n"
                    "lifecycle: [design]\n"
                    "domains: [performance]\n"
                    "lang: en\n"
                    "evidence: verified\n"
                    "verified_on: 2020-01-01\n"
                    "region: ap-northeast-1\n",
                    "Reproduced in the stated environment.\n",
                )
                errors, tier = validate_frontmatter.validate(path)
        self.assertEqual((errors, tier), ([], "verified"))

    def test_evidence_metadata_scan_target_is_non_empty(self) -> None:
        """**Validates: Requirements 1.10, 2.10** — the frontmatter scan is not empty."""
        self.assertTrue(
            validate_frontmatter.collect(ROOT),
            "frontmatter validation scanned no files, so a green run guards nothing",
        )

    # --- deterministic prose: naming / PII / internal identifier (1.2 / 2.2, 1.4 / 2.4) --------

    def test_naming_negative_fires_and_valid_control_passes(self) -> None:
        """**Validates: Requirements 1.2, 1.4, 2.2, 2.4**"""
        forbidden = (
            "FS" + "xN"
        )  # kept split so this file is not itself a naming finding
        self.assertTrue(audit_line(f"We deployed {forbidden} in production."))
        self.assertEqual(
            audit_line("Amazon FSx for NetApp ONTAP is the documented name."), []
        )

    def test_public_output_scan_target_is_non_empty(self) -> None:
        """**Validates: Requirements 1.10, 2.10** — the public-output scan is not empty."""
        self.assertTrue(
            list(iter_files(ROOT)),
            "the public-output audit scanned no files, so a green run guards nothing",
        )

    # --- deterministic prose: role label (1.2 / 2.2) -------------------------------------------

    def test_role_label_negative_fires_and_subject_label_passes(self) -> None:
        """**Validates: Requirements 1.2, 2.2**"""
        self.assertTrue(audit_line("> **AppSec lens**: reviewed"))
        self.assertEqual(audit_line("> **Cost note**: reviewed"), [])

    # --- public safety: allow budget / suppression (1.4 / 2.4) ---------------------------------

    def test_allow_budget_negative_fires_and_unchanged_passes(self) -> None:
        """**Validates: Requirements 1.4, 2.4**"""
        self.assertEqual(allow_verdict(recorded=1, actual=2), "added")
        self.assertEqual(allow_verdict(recorded=1, actual=0), "stale")
        self.assertEqual(allow_verdict(recorded=1, actual=1), "ok")

    # --- detector coverage: gate reachability (3.1) and non-empty citation scope (1.10 / 2.10) -

    def test_gate_reachability_has_no_unreached_gate(self) -> None:
        """**Validates: Requirements 3.1** — every gate in make all runs in a workflow."""
        gates = leaf_gates(prerequisites(MAKEFILE.read_text(encoding="utf-8")))
        self.assertTrue(gates)
        self.assertEqual(
            gates - calls_in_all_workflows() - set(COVERED_ANOTHER_WAY), set()
        )

    def test_citation_scan_target_is_non_empty(self) -> None:
        """**Validates: Requirements 1.10, 2.10** — the citation table is not empty."""
        rows, problems = parse_table()
        self.assertEqual(problems, [], problems)
        self.assertTrue(
            rows, "the citation table scanned no rows, so a green run guards nothing"
        )

    # --- the index itself ----------------------------------------------------------------------

    def test_every_family_has_a_registered_mutation(self) -> None:
        """Each deterministic family names at least one mutation, and all names exist.

        **Validates: Requirements 1.10, 2.10** — a family with no discriminating mutation cannot
        tell a correct fix from a lazy one, so the index requires one and fails if a referenced
        mutation is deleted from test_mutation_discrimination.py.
        """
        missing: list[str] = []
        for family, names in FAMILY_MUTATIONS.items():
            self.assertTrue(names, f"family {family} names no mutation")
            missing += [name for name in names if name not in MUTATION_NAMES]
        self.assertEqual(
            missing,
            [],
            f"these mutation names are referenced by a family but absent from MUTATIONS: {missing}",
        )


class PreservationPropertyTests(unittest.TestCase):
    """Property 2: non-Bug-Condition inputs retain their observable decisions."""

    def test_non_buggy_inputs_preserve_observable_decisions(self) -> None:
        """**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**"""
        observers = {
            "gate_entry_points": self._gate_entry_points,
            "valid_evidence": self._valid_evidence,
            "valid_public_output_and_narrow_allow": self._valid_public_output,
            "claim_authority_and_probe_contracts": self._claim_authority,
            "human_judgment_non_blocking": self._human_judgment,
            "private_scan_exclusion": self._private_scan_exclusion,
            "manifest_derived_localization": self._manifest_localization,
            "disk_derived_switchers": self._disk_switchers,
            "external_three_state": self._external_states,
            "no_remote_or_shared_write": self._no_remote_write,
            "unmeasured_style_signal_non_blocking": self._style_non_blocking,
        }
        cases = generated_preservation_cases()
        self.assertEqual(set(observers), {family for family, _ in cases})
        self.assertEqual(
            {requirement for _, requirement in cases},
            {f"3.{n}" for n in range(1, 9)},
        )
        for family, requirement in cases:
            with self.subTest(family=family, requirement=requirement):
                observers[family]()

    def _gate_entry_points(self) -> None:
        gates = leaf_gates(prerequisites(MAKEFILE.read_text(encoding="utf-8")))
        called = calls_in_all_workflows()
        self.assertTrue(gates)
        self.assertEqual(gates - called - set(COVERED_ANOTHER_WAY), set())

    def _valid_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "docs" / "en" / "domains" / "performance" / "notes"
            notes.mkdir(parents=True)
            with mock.patch.object(validate_frontmatter, "ROOT", root):
                for tier, metadata, body in generated_valid_notes():
                    path = notes / f"{tier}.md"
                    path.write_text(f"---\n{metadata}---\n\n{body}", encoding="utf-8")
                    errors, observed_tier = validate_frontmatter.validate(path)
                    self.assertEqual(errors, [])
                    self.assertEqual(observed_tier, tier)

    def _valid_public_output(self) -> None:
        self.assertEqual(
            audit_line("Amazon FSx for NetApp ONTAP is the documented name."), []
        )
        forbidden = "FS" + "xN"
        marker = "<!" + "-- allow:naming --" + ">"
        self.assertEqual(audit_line(f"External title: {forbidden} {marker}"), [])

    def _claim_authority(self) -> None:
        rows, problems = parse_table()
        self.assertTrue(rows, "outbound authority table must not be empty")
        self.assertEqual(problems + check_offline(rows) + check_contract(rows), [])
        self.assertEqual(stored_contract(), contract_lines(rows))
        inbound, unknown, inbound_problems = parse_inbound_contract()
        self.assertTrue(
            inbound or unknown, "inbound coverage must be explicit, including unknown"
        )
        self.assertEqual(inbound_problems + check_inbound(inbound), [])

    def _human_judgment(self) -> None:
        signals = (
            "The contribution requires a human originality review.",
            "A reviewer should assess whether the conclusion follows from the evidence.",
        )
        for signal in signals:
            self.assertEqual(audit_line(signal), [])

    def _private_scan_exclusion(self) -> None:
        scanned = list(iter_files(ROOT))
        self.assertTrue(
            scanned, "the public-output scan must not pass over an empty tree"
        )
        for path in scanned:
            self.assertFalse({".private", ".kiro"} & set(path.relative_to(ROOT).parts))
        self.assertTrue(set(validate_frontmatter.ROOT.parts))
        self.assertTrue(set(audit_public_output.SKIP_DIRS) >= {".private", ".kiro"})

    def _manifest_localization(self) -> None:
        entries = check_i18n_parity.read_manifest()
        self.assertTrue(entries, "the localization manifest must not be empty")
        for name, languages in entries:
            self.assertTrue(name)
            self.assertTrue(languages)
            self.assertLessEqual(set(languages), set(check_i18n_parity.TIER1_LANGS))

    def _disk_switchers(self) -> None:
        localized = sync_lang_switcher.eligible()
        self.assertTrue(localized, "switcher discovery must find localized documents")
        for rel in localized:
            split = sync_lang_switcher.split_rel(rel)
            self.assertIsNotNone(split)
            assert split is not None
            _, subpath = split
            expected = [
                lang
                for lang in sync_lang_switcher.LANGS
                if sync_lang_switcher.path_for(lang, subpath).exists()
            ]
            self.assertEqual(sync_lang_switcher.available(subpath), expected)
            self.assertEqual(sync_lang_switcher.sync_file(rel, write=False), [])

    def _external_states(self) -> None:
        expected = {
            "success": "PASS",
            "404": "DEFECT",
            "403": "INCONCLUSIVE",
            "500": "INCONCLUSIVE",
            "timeout": "INCONCLUSIVE",
        }
        for response_class, decision in expected.items():
            with self.subTest(response_class=response_class):
                self.assertEqual(_external_decision(response_class), decision)

    def _no_remote_write(self) -> None:
        if not PRESERVATION_BASELINE.exists():
            return
        baseline = json.loads(PRESERVATION_BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(baseline["remote_writes"], 0)
        self.assertEqual(baseline["shared_resource_changes"], 0)
        self.assertEqual(set(baseline["requirements"]), {f"3.{n}" for n in range(1, 9)})

    def _style_non_blocking(self) -> None:
        graph = prerequisites(MAKEFILE.read_text(encoding="utf-8"))
        blocking_style_targets = {"style-threshold", "ai-style", "originality"}
        self.assertEqual(blocking_style_targets & set(graph), set())
        self.assertEqual(
            audit_line("This paragraph may need a human style review."), []
        )


if __name__ == "__main__":
    unittest.main()
