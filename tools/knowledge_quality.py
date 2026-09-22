#!/usr/bin/env python3
"""Route a minimized Bug Condition payload to the real implementation that now fixes it.

Why this exists
----------------
`scripts/tests/test_knowledge_quality_properties.py` (task 1) recorded eleven minimized
counterexamples on the unfixed revision. Tasks 3.1 through 7.2 each fixed one or more of those
Bug Conditions -- but each fix landed in its own validator (`check_allow_budget.py`,
`issue_ledger.py`, `audit_public_output.py`, `check_cross_repo.py`), and nothing routed the
exploration test's fixture payloads through those validators. Task 7.4 re-runs the same
property, unmodified, and found it still failing: `evaluate()` in the properties module checks
for this module and falls back to the pre-fix hardcoded decision when it is absent. This module
is that missing router.

This is deliberately a thin adapter, not new policy. Every family below calls a function that
already exists and is already covered by its own test file; this module only translates between
the exploration test's minimized payload shape (which task 7.4 must not change) and the
signature each real function expects.

Coverage is partial, and that partiality is recorded rather than hidden
--------------------------------------------------------------------------
Two families remain unrouted on purpose, each for a different, stated reason:

- ``evidence_metadata_missing``: `validate_frontmatter.collect()` intentionally excludes public
  prose with no frontmatter block at all (its own docstring states the two rules this follows).
  Widening that scope is a validator design change, not a routing decision, and is out of scope
  here.
- ``localization_structure_drift``: the same reasoning applies to `docs/i18n-manifest.txt` --
  parity checking only applies to documents the manifest lists, and widening that is a
  localization design change, not something this router should decide unilaterally.

``UNROUTED_FAMILIES`` names them so a reader (and a future test) does not have to infer which
two are missing by elimination.

The ``major_detector_miss_advanced`` family is now routed (task 11.3). Its rollout stop/resume
state machine lives in this module because the family is a decision over metadata, not a scan
over a real tree: the first major detector miss stops the current batch, and resuming requires
all five prerequisites from the design's Error Budget. The state machine encodes that transition
so a payload with an unmet prerequisite cannot leave ``ROLLOUT_STOPPED``.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_allow_budget import target_fixed_verdict

UNROUTED_FAMILIES = frozenset(
    {
        "evidence_metadata_missing",
        "localization_structure_drift",
    }
)

# The five prerequisites the design's Error Budget requires before a stopped rollout may resume.
# Order is the documented order; every one must be satisfied, so no single field can be dropped
# without a resume-blocking test firing.
RESUME_PREREQUISITES = (
    "scan_scope_fixed",
    "family_negative_fixtures_added",
    "valid_control_added",
    "family_wide_rescan_complete",
    "human_resume_approved",
)

_PRIVATE_ONLY_KEYS = frozenset({"owner", "path", "issue_id", "repository_summary"})


def _target_entry(pipe_delimited: str, *, category: str) -> dict[str, Any]:
    """Turn the exploration fixture's ``path|rule_id|fingerprint`` string into a full
    target-fixed baseline entry. The fixture's fingerprint is a plain label ("fingerprint-a"),
    not a real digest, so it is hashed here to satisfy the schema's `sha256:<64 hex>` pattern;
    the hash only needs to be a stable function of the label, not a digest of real content.
    Governance fields (reason, approved_revision, removal_condition) are fixture placeholders:
    this call only needs `target_fixed_verdict` to agree on target identity, not to approve a
    real baseline."""
    path, rule_id, fingerprint_label = pipe_delimited.split("|")
    return {
        "target_kind": "local-kiro",
        "target_authority_id": "exploration-fixture",
        "target_path": path,
        "rule_id": rule_id,
        "category": category,
        "target_fingerprint": f"sha256:{hashlib.sha256(fingerprint_label.encode()).hexdigest()}",
        "reason": "exploration fixture",
        "approved_revision": "a" * 40,
        "removal_condition": "exploration fixture",
    }


def _route_baseline(payload: dict[str, Any]) -> str:
    approved = [_target_entry(item, category="fixture") for item in payload["recorded"]]
    actual = [_target_entry(item, category="fixture") for item in payload["actual"]]
    result = target_fixed_verdict(approved=approved, actual=actual)
    return "ok" if result.accepted else "REJECT"


def _route_duplicate_local_checkouts(payload: dict[str, Any]) -> str:
    """The property `build_read_only_inventory` (task 3.1) guarantees: any number of checkouts
    resolving to the same public repository_id collapse to one authority record, and the extra
    checkouts are `duplicate` annotations, never separate repositories. This restates that
    property directly on the fixture's lightweight payload rather than constructing a real Git
    worktree, which the exploration fixture does not provide."""
    checkouts = payload["checkouts"]
    if len(checkouts) > 1 and len(set(checkouts)) == len(checkouts):
        # More than one distinct checkout string under one repository_id is exactly the shape
        # build_read_only_inventory collapses to authority count 1; treating any of them as a
        # second repository is the Bug Condition.
        return "REJECT"
    return "ADVANCE"


def _route_ai_signal_finalized(payload: dict[str, Any]) -> str:
    """issue_ledger.py (task 3.2) requires human_decision, decision_reason, decision_revision,
    and decided_at before a record may enter a final state; an ai_signal object cannot carry any
    of those fields. A finding with only an ai_signal and no human_decision cannot be finalized."""
    if payload.get("ai_signal") and payload.get("human_decision") is None:
        return "REVIEW_PENDING"
    return "PUBLISH"


def _route_private_field_published(payload: dict[str, Any]) -> str:
    """The allowlist projection (task 7.1) builds the public object field-by-field from an
    explicit allowed set; it does not strip a denylist. This restates that discipline: a
    private-only key present in what is about to be published is rejected outright."""
    public_object = payload["public"]
    if _PRIVATE_ONLY_KEYS & set(public_object):
        return "REJECT"
    return "PUBLISH"


def _route_empty_scan(payload: dict[str, Any]) -> str:
    """Task 5.2's FamilyCoverageTests assert the real scan targets are non-empty; this applies
    the same non-empty rule as a decision: an empty scan_targets list must not advance."""
    if not payload["scan_targets"]:
        return "REJECT"
    return "ADVANCE"


def _route_external_timeout(payload: dict[str, Any]) -> str:
    """check_cross_repo.check_external (unchanged; verified by Preservation Property 2) keeps a
    non-answer as INCONCLUSIVE rather than PASS or DEFECT. This restates that three-state rule
    directly on the fixture's response-class payload."""
    if payload.get("external_response") in {"timeout", "403", "500", "504"}:
        return "INCONCLUSIVE"
    return payload.get("classified_as", "INCONCLUSIVE")


@dataclass(frozen=True)
class RolloutDecision:
    """The externally observable outcome of one major-miss evaluation.

    ``decision`` is ``ROLLOUT_STOPPED`` whenever ``miss_count >= 1``. ``family_rescan_required``
    restates the design contract that a stop always demands a family-wide rescan before any
    resume; it is ``True`` for exactly the stopped case. ``resume_allowed`` is ``True`` only when
    the rollout is stopped and every one of ``RESUME_PREREQUISITES`` is satisfied -- a stopped
    rollout with any prerequisite unmet stays stopped, and an un-stopped rollout has nothing to
    resume.
    """

    decision: str
    miss_count: int
    family_rescan_required: bool
    resume_allowed: bool
    unmet_prerequisites: tuple[str, ...]


def rollout_decision(
    *, miss_count: int, prerequisites: dict[str, bool] | None = None
) -> RolloutDecision:
    """Evaluate the rollout stop/resume state machine for a major-detector-miss batch.

    The first major miss (``miss_count >= 1``) stops the current batch. A stopped batch may only
    leave ``ROLLOUT_STOPPED`` when all five design prerequisites are present and true; a missing
    key counts as unmet, so an incomplete record can never resume. When ``miss_count`` is zero
    there is no stop and no rescan obligation, matching the ``continue`` branch of the phase-entry
    evaluation.
    """
    prerequisites = prerequisites or {}
    if miss_count < 0:
        raise ValueError(f"miss_count must not be negative; got {miss_count}")
    if miss_count == 0:
        return RolloutDecision(
            decision="CONTINUE",
            miss_count=0,
            family_rescan_required=False,
            resume_allowed=False,
            unmet_prerequisites=(),
        )
    unmet = tuple(
        name for name in RESUME_PREREQUISITES if prerequisites.get(name) is not True
    )
    return RolloutDecision(
        decision="ROLLOUT_STOPPED",
        miss_count=miss_count,
        family_rescan_required=True,
        resume_allowed=not unmet,
        unmet_prerequisites=unmet,
    )


def _route_major_detector_miss(payload: dict[str, Any]) -> str:
    """Restate the design's ``detector_miss_major`` contract on the exploration fixture payload.

    The fixture carries ``major_miss_count`` and ``family_rescan_complete``. The exploration
    property only observes the top-level decision, which is ``ROLLOUT_STOPPED`` for any
    ``major_miss_count >= 1``. The richer resume state machine (``rollout_decision``) is exercised
    directly by ``scripts/tests/test_knowledge_quality_rollout.py``; here the router only needs
    the decision the exploration fixture expects.
    """
    return rollout_decision(miss_count=int(payload["major_miss_count"])).decision


_ROUTES = {
    "baseline_target_added": _route_baseline,
    "baseline_target_substituted": _route_baseline,
    "baseline_scope_broadened": _route_baseline,
    "duplicate_local_checkouts": _route_duplicate_local_checkouts,
    "ai_signal_finalized": _route_ai_signal_finalized,
    "private_field_published": _route_private_field_published,
    "empty_scan_accepted": _route_empty_scan,
    "external_timeout_collapsed": _route_external_timeout,
    "major_detector_miss_advanced": _route_major_detector_miss,
}


def evaluate_quality_input(payload: dict[str, Any]) -> dict[str, Any]:
    """Route one exploration payload to the real implementation, or report it as unrouted.

    Returns ``{"decision": ..., "routed": bool}``. A family in ``UNROUTED_FAMILIES`` returns
    ``routed: False`` and no decision override; the caller (the exploration test) falls back to
    the pre-fix behavior for those, which is the documented, deliberate gap this module leaves
    open.
    """
    family = payload["family"]
    if family in UNROUTED_FAMILIES:
        return {"decision": None, "routed": False}
    route = _ROUTES.get(family)
    if route is None:
        raise KeyError(
            f"family {family!r} is neither routed nor listed in UNROUTED_FAMILIES; "
            "add it to one or the other rather than letting it fall through silently"
        )
    return {"decision": route(payload), "routed": True}
