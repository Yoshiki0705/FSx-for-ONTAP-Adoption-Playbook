#!/usr/bin/env python3
"""Validate one audit-provenance run record.

A gate passing is not evidence of what it ran against. A run record ties a verification to the
inputs that produced it: which commit, which Hub revision, which validator artifacts by digest,
the exact command, the scan scope, the tool versions, the pinned Action SHAs, the runner image,
the deterministic result, the three-state external result, the baseline before and after, the
generated aggregate digest, and the human phase decision. Without those, "it passed" cannot be
reproduced or audited.

This module is the authoritative check. ``tools/provenance-run.schema.json`` documents the same
shape so a reader has a schema to look at, and ``test_knowledge_quality_provenance.py`` fails if the
two drift.

Scope (Task 5.3, Phase 1): this defines the record's form and its required-field rule. Real run
records are written by the Phase 2 pilot wiring (task 7.3) into ``.private/knowledge-quality/runs/``;
none is created here. SLSA L1 equivalence for this documentation-first repository means the
verification is reproducible from the record — input revision, dependency versions, command,
artifact digests, and result — not that a build artifact is signed.

``external_result`` keeps the three-state vocabulary the rest of the cross-repository checks use: a
server that did not answer is ``INCONCLUSIVE``, never silently a pass or a defect.

``recovery_class`` records whether a failure of this run is recoverable by an ordinary revert of
reversible repository content (``reversible``), or whether it published something a revert does not
erase — a secret, PII, or Git history exposure — and so requires a human-led incident response
(``incident``). The distinction is design's, and it is a required field because misclassifying an
incident as reversible is how a leak gets treated as a rollback.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SCHEMA = "knowledge-quality/provenance-run/v1"

EXTERNAL_STATES = ("PASS", "DEFECT", "INCONCLUSIVE")
RECOVERY_CLASSES = ("reversible", "incident")

# Every field a run record must carry. Absence of any one leaves the verification unreproducible in
# a way the record itself does not disclose, which is the failure this guards.
REQUIRED_FIELDS = (
    "run_id",
    "public_repository_id",
    "input_sha",
    "local_head",
    "local_dirty",
    "hub_revision",
    "validator_artifact_digests",
    "exact_command",
    "scan_roots",
    "excluded_roots",
    "tool_versions",
    "action_shas",
    "runner_image",
    "deterministic_result",
    "external_result",
    "baseline_before",
    "baseline_after",
    "aggregate_digest",
    "human_phase_decision",
    "recovery_class",
)

_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def validate_run_record(record: object) -> list[str]:
    """Return the problems in one run record; an empty list means it is well formed.

    The check is structural, not a judgement on the values: it enforces that every required field
    is present and that the small, closed vocabularies (external result, recovery class, SHA
    shapes) hold. Whether the recorded run was itself correct is the reviewer's call, not this
    function's.
    """
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["run record must be a JSON object"]

    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        problems.append(f"missing required fields: {sorted(missing)}")
    unknown = sorted(set(record) - set(REQUIRED_FIELDS))
    if unknown:
        problems.append(f"unknown fields: {unknown}")

    external = record.get("external_result")
    if external not in EXTERNAL_STATES:
        problems.append(
            f"external_result must be one of {list(EXTERNAL_STATES)}, got {external!r}"
        )

    recovery = record.get("recovery_class")
    if recovery not in RECOVERY_CLASSES:
        problems.append(
            f"recovery_class must be one of {list(RECOVERY_CLASSES)}, got {recovery!r}"
        )

    _check_sha(problems, record, "input_sha", _SHA1)
    _check_sha(problems, record, "local_head", _SHA1)
    _check_sha(problems, record, "hub_revision", _SHA1)
    _check_sha(problems, record, "aggregate_digest", _SHA256)

    if "local_dirty" in record and not isinstance(record["local_dirty"], bool):
        problems.append("local_dirty must be a boolean")

    for field in ("scan_roots", "excluded_roots", "action_shas"):
        if field in record and not isinstance(record[field], list):
            problems.append(f"{field} must be an array")

    for field in ("validator_artifact_digests", "tool_versions"):
        if field in record and not isinstance(record[field], Mapping):
            problems.append(f"{field} must be an object")

    return problems


def _check_sha(
    problems: list[str], record: Mapping[str, Any], field: str, pattern: re.Pattern[str]
) -> None:
    if field not in record:
        return
    value = record[field]
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        width = 40 if pattern is _SHA1 else 64
        problems.append(f"{field} must be a {width}-character lowercase hex digest")


def main() -> int:
    import json
    import sys
    from pathlib import Path

    if len(sys.argv) != 2:
        print("usage: python3 tools/provenance.py <run-record.json>", file=sys.stderr)
        return 2
    record = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    issues = validate_run_record(record)
    for issue in issues:
        print(f"  {issue}", file=sys.stderr)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
