"""Task 5.1 controls for the immutable Hub adoption contract.

The adopter's connection to the Hub is validated by
``check_cross_repo.validate_adoption_contract``. These controls fix that behavior against the
task's completion conditions:

- a contract pinned to an immutable Hub revision, with matching validator-artifact digests and the
  real rule-index anchor, is the only shape that passes;
- a mutable ref, a digest mismatch, a schema/profile/rule-index mismatch, a copied rule body, or an
  over-limit override each fails with its own ``[adoption-contract:<category>]`` category;
- the tracked JSON schema documents the same shape the validator enforces, and drifts fail here;
- the outbound generated probe contract and the inbound exactly-once check still hold, so wiring the
  adoption contract into both CLIs did not regress the existing cross-repository gates.

Digests for the pass control are computed at runtime from the real Hub files, so editing a
validator artifact does not silently break the control or require a tracked fixed digest.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check_cross_repo
import check_inbound_probes
from check_cross_repo import (
    _CONTRACT_FIELDS,
    _OVERRIDE_FIELDS,
    ADOPTION_CONTRACT_SCHEMA,
    HUB_REPOSITORY,
    MAX_OVERRIDES,
    OVERRIDE_LIMITS,
    OVERRIDE_SCHEMA,
    PROFILE_ARTIFACTS,
    RULE_INDEX,
    check_adoption_contract_file,
    validate_adoption_contract,
)

SCHEMA_PATH = ROOT / "tools" / "adoption-contract.schema.json"
PROFILE = "cross-repository-quality-v1"


def _digest(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def valid_contract() -> dict[str, Any]:
    """A contract that validates clean against the real Hub tree.

    Digests are read from the live files rather than pinned, so this control follows an edited
    validator artifact instead of turning into a stale fixture.
    """
    return {
        "contract_schema": ADOPTION_CONTRACT_SCHEMA,
        "hub_repository": HUB_REPOSITORY,
        "hub_revision": "a" * 40,
        "profile": PROFILE,
        "validator_artifacts": [
            {"path": path, "sha256": _digest(path)}
            for path in sorted(PROFILE_ARTIFACTS[PROFILE])
        ],
        "rule_index": RULE_INDEX,
        "repository_overrides": "overrides.json",
    }


def overrides_document(overrides: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema": OVERRIDE_SCHEMA, "overrides": overrides}


def categories(problems: list[Any]) -> set[str]:
    """Category tags from AdoptionContractProblem objects."""
    return {problem.category for problem in problems}


class AdopterTree:
    """A temporary adopter root holding only a repository_overrides document."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def write_overrides(
        self, document: Any, *, name: str = "overrides.json"
    ) -> AdopterTree:
        (self.root / name).write_text(
            document if isinstance(document, str) else json.dumps(document),
            encoding="utf-8",
        )
        return self


class PassControlTests(unittest.TestCase):
    def test_pinned_contract_with_live_digests_and_empty_overrides_passes(self) -> None:
        """**Validates: Requirements 1.9, 2.9, 3.2**"""
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
            problems = validate_adoption_contract(
                valid_contract(), adopter_root=adopter.root
            )
        self.assertEqual(problems, [], problems)

    def test_pinned_contract_with_narrow_overrides_passes(self) -> None:
        """**Validates: Requirements 2.3, 2.9**"""
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(
                overrides_document(
                    [
                        {
                            "category": "scan-root",
                            "value": "docs/adopter",
                            "reason": "The adopter documents live here.",
                        },
                        {
                            "category": "localization-tier",
                            "value": "ja-only",
                            "reason": "This adopter ships Japanese only.",
                        },
                    ]
                )
            )
            problems = validate_adoption_contract(
                valid_contract(), adopter_root=adopter.root
            )
        self.assertEqual(problems, [], problems)


class ImmutableRevisionTests(unittest.TestCase):
    def test_mutable_or_short_refs_are_rejected(self) -> None:
        """**Validates: Requirements 1.9, 2.9**"""
        for revision in ("main", "v1.0.0", "a" * 39, "a" * 41, "A" * 40, "g" * 40, ""):
            with self.subTest(revision=revision), tempfile.TemporaryDirectory() as tmp:
                adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
                contract = valid_contract()
                contract["hub_revision"] = revision
                problems = validate_adoption_contract(
                    contract, adopter_root=adopter.root
                )
                self.assertIn("mutable-revision", categories(problems))

    def test_full_lowercase_sha_is_the_only_accepted_form(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
            contract = valid_contract()
            contract["hub_revision"] = "0123456789abcdef0123456789abcdef01234567"
            problems = validate_adoption_contract(contract, adopter_root=adopter.root)
        self.assertNotIn("mutable-revision", categories(problems))


class SchemaAndProfileTests(unittest.TestCase):
    def test_schema_mismatch_is_rejected(self) -> None:
        """**Validates: Requirements 2.9**"""
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
            contract = valid_contract()
            contract["contract_schema"] = "knowledge-quality/adoption-contract/v2"
            problems = validate_adoption_contract(contract, adopter_root=adopter.root)
        self.assertIn("schema-mismatch", categories(problems))

    def test_hub_repository_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
            contract = valid_contract()
            contract["hub_repository"] = "someone/else"
            problems = validate_adoption_contract(contract, adopter_root=adopter.root)
        self.assertIn("hub-repository", categories(problems))

    def test_unknown_profile_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
            contract = valid_contract()
            contract["profile"] = "nonexistent-profile"
            problems = validate_adoption_contract(contract, adopter_root=adopter.root)
        self.assertIn("profile-mismatch", categories(problems))

    def test_unknown_or_missing_fields_are_rejected(self) -> None:
        for mutate in (
            lambda c: c.update({"extra": 1}),
            lambda c: c.pop("profile"),
        ):
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as tmp:
                adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
                contract = valid_contract()
                mutate(contract)
                problems = validate_adoption_contract(
                    contract, adopter_root=adopter.root
                )
                self.assertIn("schema", categories(problems))


class ValidatorArtifactTests(unittest.TestCase):
    def test_digest_mismatch_is_rejected(self) -> None:
        """**Validates: Requirements 1.9, 2.9**"""
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
            contract = valid_contract()
            contract["validator_artifacts"][0]["sha256"] = "0" * 64
            problems = validate_adoption_contract(contract, adopter_root=adopter.root)
        self.assertIn("artifact-digest-mismatch", categories(problems))

    def test_missing_artifact_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
            contract = valid_contract()
            contract["validator_artifacts"].append(
                {"path": "tools/does-not-exist.py", "sha256": "0" * 64}
            )
            problems = validate_adoption_contract(contract, adopter_root=adopter.root)
        self.assertIn("artifact-path", categories(problems))

    def test_partial_profile_artifact_set_is_rejected(self) -> None:
        """The set must equal exactly the profile's required artifacts."""
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
            contract = valid_contract()
            contract["validator_artifacts"] = contract["validator_artifacts"][:1]
            problems = validate_adoption_contract(contract, adopter_root=adopter.root)
        self.assertIn("profile-artifacts", categories(problems))

    def test_unsafe_artifact_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
            contract = valid_contract()
            contract["validator_artifacts"][0]["path"] = "../tools/check_cross_repo.py"
            problems = validate_adoption_contract(contract, adopter_root=adopter.root)
        self.assertIn("artifact-path", categories(problems))

    def test_malformed_digest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
            contract = valid_contract()
            contract["validator_artifacts"][0]["sha256"] = "not-a-digest"
            problems = validate_adoption_contract(contract, adopter_root=adopter.root)
        self.assertIn("artifact-digest", categories(problems))


class RuleIndexTests(unittest.TestCase):
    def test_wrong_rule_index_is_rejected(self) -> None:
        """**Validates: Requirements 2.9, 3.2**"""
        for rule_index in (
            "docs/ja/reference/cross-repo-index.md#wrong-anchor",
            "docs/ja/reference/other.md#引用表",
            "docs/ja/reference/cross-repo-index.md",
        ):
            with (
                self.subTest(rule_index=rule_index),
                tempfile.TemporaryDirectory() as tmp,
            ):
                adopter = AdopterTree(Path(tmp)).write_overrides(overrides_document([]))
                contract = valid_contract()
                contract["rule_index"] = rule_index
                problems = validate_adoption_contract(
                    contract, adopter_root=adopter.root
                )
                self.assertIn("rule-index", categories(problems))


class OverrideTests(unittest.TestCase):
    def test_unknown_override_category_is_rejected(self) -> None:
        """**Validates: Requirements 2.3, 2.9**"""
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(
                overrides_document(
                    [{"category": "invented", "value": "x", "reason": "y"}]
                )
            )
            problems = validate_adoption_contract(
                valid_contract(), adopter_root=adopter.root
            )
        self.assertIn("override-category", categories(problems))

    def test_duplicate_override_is_rejected(self) -> None:
        entry = {
            "category": "scan-root",
            "value": "docs/adopter",
            "reason": "documents live here",
        }
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(
                overrides_document([dict(entry), dict(entry)])
            )
            problems = validate_adoption_contract(
                valid_contract(), adopter_root=adopter.root
            )
        self.assertIn("override-duplicate", categories(problems))

    def test_per_category_limit_is_enforced(self) -> None:
        """**Validates: Requirements 2.3, 2.9**"""
        limit = OVERRIDE_LIMITS["scan-root"]
        overrides = [
            {
                "category": "scan-root",
                "value": f"docs/root-{index}",
                "reason": f"scan root {index}",
            }
            for index in range(limit + 1)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(
                overrides_document(overrides)
            )
            problems = validate_adoption_contract(
                valid_contract(), adopter_root=adopter.root
            )
        self.assertIn("override-limit", categories(problems))

    def test_total_override_limit_is_enforced(self) -> None:
        overrides = [
            {
                "category": "repository-rule",
                "value": f"local rule {index}",
                "reason": f"reason {index}",
            }
            for index in range(MAX_OVERRIDES + 1)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(
                overrides_document(overrides)
            )
            problems = validate_adoption_contract(
                valid_contract(), adopter_root=adopter.root
            )
        self.assertIn("override-limit", categories(problems))

    def test_empty_reason_or_value_is_rejected(self) -> None:
        for field in ("value", "reason"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                override = {
                    "category": "scan-root",
                    "value": "docs/adopter",
                    "reason": "documents live here",
                }
                override[field] = "  "
                adopter = AdopterTree(Path(tmp)).write_overrides(
                    overrides_document([override])
                )
                problems = validate_adoption_contract(
                    valid_contract(), adopter_root=adopter.root
                )
                self.assertIn("override-schema", categories(problems))

    def test_unsafe_override_path_value_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(
                overrides_document(
                    [
                        {
                            "category": "exclusion",
                            "value": "../outside",
                            "reason": "escape attempt",
                        }
                    ]
                )
            )
            problems = validate_adoption_contract(
                valid_contract(), adopter_root=adopter.root
            )
        self.assertIn("override-path", categories(problems))


class CopiedRuleMutationTests(unittest.TestCase):
    def test_repository_rule_copying_the_hub_index_is_rejected(self) -> None:
        """A repository-rule override that transcribes a Hub rule-index line is drift.

        **Validates: Requirements 1.3, 2.3, 2.9**
        """
        index_body = (ROOT / "docs/ja/reference/cross-repo-index.md").read_text(
            encoding="utf-8"
        )
        long_line = next(
            " ".join(raw.strip().lstrip("#").strip().split())
            for raw in index_body.splitlines()
            if len(" ".join(raw.strip().lstrip("#").strip().split())) >= 32
        )
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(
                overrides_document(
                    [
                        {
                            "category": "repository-rule",
                            "value": long_line,
                            "reason": "copied the Hub rule text instead of referencing it",
                        }
                    ]
                )
            )
            problems = validate_adoption_contract(
                valid_contract(), adopter_root=adopter.root
            )
        self.assertIn("copied-rule-body", categories(problems))

    def test_short_repository_rule_that_only_references_is_allowed(self) -> None:
        """A path-only, non-transcribing repository rule is not a copy — pass control."""
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(
                overrides_document(
                    [
                        {
                            "category": "repository-rule",
                            "value": "See RULE_INDEX for naming.",
                            "reason": "reference only, no transcription",
                        }
                    ]
                )
            )
            problems = validate_adoption_contract(
                valid_contract(), adopter_root=adopter.root
            )
        self.assertNotIn("copied-rule-body", categories(problems))


class OverrideDocumentShapeTests(unittest.TestCase):
    def test_wrong_override_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides(
                {"schema": "wrong/schema/v1", "overrides": []}
            )
            problems = validate_adoption_contract(
                valid_contract(), adopter_root=adopter.root
            )
        self.assertIn("override-schema", categories(problems))

    def test_missing_override_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            problems = validate_adoption_contract(
                valid_contract(), adopter_root=Path(tmp)
            )
        self.assertIn("override-path", categories(problems))

    def test_invalid_override_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adopter = AdopterTree(Path(tmp)).write_overrides("{not json")
            problems = validate_adoption_contract(
                valid_contract(), adopter_root=adopter.root
            )
        self.assertIn("override-schema", categories(problems))


class SchemaValidatorSyncTests(unittest.TestCase):
    """The tracked JSON schema documents exactly what the validator enforces.

    Drift between the two is the only thing that justifies keeping a second copy, so it fails here.
    Procedural checks the validator performs and JSON Schema cannot express are asserted absent from
    the schema and guarded by the mutation controls above.
    """

    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_schema_id_and_contract_shape_match_the_validator(self) -> None:
        self.assertEqual(self.schema["$id"], ADOPTION_CONTRACT_SCHEMA)
        self.assertEqual(
            self.schema["properties"]["contract_schema"]["const"],
            ADOPTION_CONTRACT_SCHEMA,
        )
        self.assertEqual(set(self.schema["required"]), set(_CONTRACT_FIELDS))
        self.assertEqual(set(self.schema["properties"]), set(_CONTRACT_FIELDS))
        self.assertEqual(
            self.schema["properties"]["hub_repository"]["const"], HUB_REPOSITORY
        )
        self.assertEqual(self.schema["properties"]["rule_index"]["const"], RULE_INDEX)

    def test_schema_profile_enum_matches_the_validator(self) -> None:
        self.assertEqual(
            set(self.schema["properties"]["profile"]["enum"]),
            set(PROFILE_ARTIFACTS),
        )

    def test_schema_override_shape_matches_the_validator(self) -> None:
        override = self.schema["$defs"]["override"]
        self.assertEqual(set(override["required"]), set(_OVERRIDE_FIELDS))
        self.assertEqual(set(override["properties"]), set(_OVERRIDE_FIELDS))
        self.assertEqual(
            set(override["properties"]["category"]["enum"]),
            set(OVERRIDE_LIMITS),
        )
        overrides_document_schema = self.schema["$defs"]["repositoryOverridesDocument"]
        self.assertEqual(
            overrides_document_schema["properties"]["schema"]["const"],
            OVERRIDE_SCHEMA,
        )
        self.assertEqual(
            overrides_document_schema["properties"]["overrides"]["maxItems"],
            MAX_OVERRIDES,
        )


class CliIntegrationTests(unittest.TestCase):
    """The adoption contract is reachable from both cross-repository CLIs."""

    def _run(self, tool: str, extra: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "tools" / tool), *extra],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_both_clis_reject_a_mutable_ref_contract(self) -> None:
        """**Validates: Requirements 1.9, 2.9**"""
        with tempfile.TemporaryDirectory() as tmp:
            adopter = Path(tmp)
            (adopter / "overrides.json").write_text(
                json.dumps(overrides_document([])), encoding="utf-8"
            )
            contract_path = adopter / "contract.json"
            contract = valid_contract()
            contract["hub_revision"] = "main"
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            for tool in ("check_cross_repo.py", "check_inbound_probes.py"):
                with self.subTest(tool=tool):
                    result = self._run(
                        tool,
                        [
                            "--adoption-contract",
                            str(contract_path),
                            "--adopter-root",
                            str(adopter),
                        ],
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(
                        "adoption-contract:mutable-revision",
                        result.stdout + result.stderr,
                    )

    def test_check_adoption_contract_file_renders_category_prefixed_messages(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adopter = Path(tmp)
            (adopter / "overrides.json").write_text(
                json.dumps(overrides_document([])), encoding="utf-8"
            )
            contract_path = adopter / "contract.json"
            contract = valid_contract()
            contract["hub_revision"] = "main"
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            messages = check_adoption_contract_file(contract_path, adopter_root=adopter)
        self.assertTrue(
            any(
                msg.startswith("[adoption-contract:mutable-revision]")
                for msg in messages
            )
        )


class PreservationTests(unittest.TestCase):
    """Wiring the contract into both CLIs did not regress the existing gates."""

    def test_outbound_generated_contract_still_matches_the_table(self) -> None:
        """**Validates: Requirements 3.1, 3.2**"""
        rows, problems = check_cross_repo.parse_table()
        self.assertEqual(problems, [], problems)
        self.assertEqual(check_cross_repo.check_contract(rows), [])

    def test_inbound_probes_still_hold_exactly_once(self) -> None:
        """**Validates: Requirements 3.1, 3.2**"""
        rows, _unknown, problems = check_inbound_probes.parse_contract()
        self.assertEqual(problems, [], problems)
        self.assertEqual(check_inbound_probes.check(rows), [])


if __name__ == "__main__":
    unittest.main()
