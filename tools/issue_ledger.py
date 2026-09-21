"""Validate private knowledge-quality issue records and their state transitions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA_VERSION = "knowledge-quality/issue-ledger/v1"

CATEGORIES = frozenset(
    {
        "evidence",
        "deterministic-prose",
        "judgment-prose",
        "authority-duplication",
        "public-safety",
        "baseline",
        "inventory",
        "ledger-completeness",
        "boundary",
        "adoption-contract",
        "detector-coverage",
        "rollout",
        "localization",
    }
)
SEVERITIES = frozenset({"critical", "major", "minor"})
EVIDENCE_CLASSES = frozenset(
    {"verified", "documented", "field-observation", "hypothesis", "open"}
)
DETERMINISM_VALUES = frozenset({"deterministic", "human-judgment"})
AUTHORITIES = frozenset(
    {
        "Hub",
        "sibling-authority",
        "public-GitHub",
        "local-Kiro-authority",
        "local-observation",
    }
)
EXPOSURES = frozenset({"private-detail", "public-aggregate"})
STATES = frozenset(
    {
        "discovered",
        "triaged",
        "blocked",
        "planned",
        "fixing",
        "verifying",
        "resolved",
        "accepted-baseline",
    }
)
TARGET_KINDS = frozenset({"public-github", "local-kiro"})
PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})
FINAL_STATES = frozenset({"resolved", "accepted-baseline"})
HUMAN_DECISIONS = frozenset({"approved", "rejected", "waived", "closed"})

REQUIRED_FIELDS = (
    "schema",
    "issue_id",
    "repository_summary",
    "target_kind",
    "target_authority_id",
    "affected_location",
    "category",
    "severity",
    "severity_decision_source",
    "evidence_class",
    "determinism",
    "authority",
    "exposure",
    "state",
    "impact",
    "remediation_direction",
    "dependencies",
    "verification_method",
    "accountable_owner",
    "priority",
    "completion_condition",
    "source_revision",
    "observed_at",
)

_ENUMS = {
    "category": CATEGORIES,
    "severity": SEVERITIES,
    "severity_decision_source": frozenset({"deterministic-rule", "human"}),
    "evidence_class": EVIDENCE_CLASSES,
    "determinism": DETERMINISM_VALUES,
    "authority": AUTHORITIES,
    "exposure": EXPOSURES,
    "state": STATES,
    "target_kind": TARGET_KINDS,
    "priority": PRIORITIES,
}

_ALLOWED_TRANSITIONS = {
    "discovered": frozenset({"triaged"}),
    "triaged": frozenset({"blocked", "planned", "accepted-baseline"}),
    "blocked": frozenset({"planned"}),
    "planned": frozenset({"fixing"}),
    "fixing": frozenset({"verifying"}),
    "verifying": frozenset({"resolved"}),
    "resolved": frozenset(),
    "accepted-baseline": frozenset(),
}

_AI_SIGNAL_FIELDS = frozenset({"candidate", "reason"})
_AI_FORBIDDEN_DECISION_FIELDS = frozenset(
    {
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
    }
)
_OPTIONAL_FIELDS = frozenset(
    {
        "severity_decision_revision",
        "ai_signal",
        "human_decision",
        "decision_reason",
        "decision_revision",
        "decided_at",
    }
)
_ALLOWED_FIELDS = frozenset(REQUIRED_FIELDS) | _OPTIONAL_FIELDS


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_human_final_decision(record: Mapping[str, Any]) -> bool:
    return (
        record.get("human_decision") in HUMAN_DECISIONS
        and _is_non_empty_string(record.get("decision_reason"))
        and _is_non_empty_string(record.get("decision_revision"))
        and _is_non_empty_string(record.get("decided_at"))
    )


def validation_errors(record: Mapping[str, Any]) -> list[str]:
    """Return deterministic schema and decision-boundary errors."""
    errors: list[str] = []
    unknown = set(record) - _ALLOWED_FIELDS
    if unknown:
        errors.append(f"unsupported issue fields: {sorted(unknown)}")
    for field in REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"missing required field: {field}")

    for field in REQUIRED_FIELDS:
        if field not in record or field == "dependencies":
            continue
        value = record[field]
        if isinstance(value, str) and not value.strip():
            errors.append(f"empty required field: {field}")

    dependencies = record.get("dependencies")
    if not isinstance(dependencies, list) or any(
        not _is_non_empty_string(item) for item in dependencies
    ):
        errors.append("dependencies must be a list of non-empty strings")

    completion = record.get("completion_condition")
    if (
        not isinstance(completion, Mapping)
        or set(completion) != {"check", "expected"}
        or not _is_non_empty_string(completion.get("check"))
        or "expected" not in completion
    ):
        errors.append(
            "completion_condition must contain only non-empty check and expected"
        )

    for field, allowed in _ENUMS.items():
        if field in record and record[field] not in allowed:
            errors.append(f"invalid {field}: {record[field]!r}")

    target_kind = record.get("target_kind")
    target_authority_id = record.get("target_authority_id")
    if target_kind == "public-github" and (
        not isinstance(target_authority_id, int)
        or isinstance(target_authority_id, bool)
        or target_authority_id <= 0
    ):
        errors.append(
            "public-github target_authority_id must be a positive repository ID"
        )
    elif target_kind == "local-kiro" and not _is_non_empty_string(target_authority_id):
        errors.append("local-kiro target_authority_id must be a private opaque key")

    if record.get("schema") != SCHEMA_VERSION:
        errors.append(f"schema must be {SCHEMA_VERSION}")
    if record.get("exposure") not in {None, "private-detail"}:
        errors.append("Issue Ledger records must use private-detail exposure")

    ai_signal = record.get("ai_signal")
    if ai_signal is not None:
        if not isinstance(ai_signal, Mapping):
            errors.append("ai_signal must be an object")
        else:
            unknown = set(ai_signal) - _AI_SIGNAL_FIELDS
            forbidden = set(ai_signal) & _AI_FORBIDDEN_DECISION_FIELDS
            if unknown:
                errors.append(f"ai_signal has unsupported fields: {sorted(unknown)}")
            if forbidden:
                errors.append(f"ai_signal cannot carry decisions: {sorted(forbidden)}")
            if not _is_non_empty_string(ai_signal.get("candidate")):
                errors.append("ai_signal candidate is required")
            if not _is_non_empty_string(ai_signal.get("reason")):
                errors.append("ai_signal reason is required")

    if record.get("severity_decision_source") == "human" and not _is_non_empty_string(
        record.get("severity_decision_revision")
    ):
        errors.append("human severity requires severity_decision_revision")

    if record.get("state") in FINAL_STATES and not _has_human_final_decision(record):
        errors.append(
            "final state requires human_decision, decision_reason, decision_revision, and decided_at"
        )
    return errors


def can_enter_roadmap(record: Mapping[str, Any]) -> bool:
    """Return whether a complete, triaged-or-later record can enter the roadmap."""
    if validation_errors(record):
        return False
    return record.get("state") != "discovered"


def transition_issue(
    record: Mapping[str, Any], target_state: str, *, actor: str
) -> dict[str, Any]:
    """Return a transitioned copy or reject an invalid/AI-driven transition."""
    if actor == "ai":
        raise ValueError(
            "AI assistive signals cannot perform state or phase transitions"
        )
    if actor not in {"human", "validator"}:
        raise ValueError(f"unsupported transition actor: {actor}")
    errors = validation_errors(record)
    if errors:
        raise ValueError("invalid issue record: " + "; ".join(errors))
    current = record["state"]
    if target_state not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid state transition: {current} -> {target_state}")
    if target_state in FINAL_STATES and actor != "human":
        raise ValueError("final state requires a human transition actor")
    transitioned = dict(record)
    transitioned["state"] = target_state
    final_errors = validation_errors(transitioned)
    if final_errors:
        raise ValueError("invalid transitioned record: " + "; ".join(final_errors))
    return transitioned
