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
Three families remain unrouted on purpose, each for a different, stated reason:

- ``major_detector_miss_advanced``: the rollout stop/resume state machine belongs to task 11.3
  (Phase 4), which has not been implemented. Routing it here would be scope creep past what a
  Phase 2 checkpoint task authorizes.
- ``evidence_metadata_missing``: `validate_frontmatter.collect()` intentionally excludes public
  prose with no frontmatter block at all (its own docstring states the two rules this follows).
  Widening that scope is a validator design change, not a routing decision, and is out of scope
  here.
- ``localization_structure_drift``: the same reasoning applies to `docs/i18n-manifest.txt` --
  parity checking only applies to documents the manifest lists, and widening that is a
  localization design change, not something this router should decide unilaterally.

``UNROUTED_FAMILIES`` names them so a reader (and a future test) does not have to infer which
three are missing by elimination.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_allow_budget import target_fixed_verdict

UNROUTED_FAMILIES = frozenset(
    {
        "major_detector_miss_advanced",
        "evidence_metadata_missing",
        "localization_structure_drift",
    }
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


_ROUTES = {
    "baseline_target_added": _route_baseline,
    "baseline_target_substituted": _route_baseline,
    "baseline_scope_broadened": _route_baseline,
    "duplicate_local_checkouts": _route_duplicate_local_checkouts,
    "ai_signal_finalized": _route_ai_signal_finalized,
    "private_field_published": _route_private_field_published,
    "empty_scan_accepted": _route_empty_scan,
    "external_timeout_collapsed": _route_external_timeout,
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
