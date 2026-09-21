#!/usr/bin/env python3
"""Keep the set of audit allow markers shrink-only.

Every allow marker silences a detector on a line or a whole file. **Adding one looks exactly like
fixing the problem it silences: the audit passes either way.** That is the failure this guards -- not
a crash, but a check that quietly stops covering something. A sibling repository named the shape
while keeping a list of known-divergent pairs shrink-only, and reached the same conclusion: **losing
the property leaves the run looking normal**, so nothing surfaces until someone reads the list.

The budget is a generated baseline of `path<TAB>category<TAB>count`. Counting per file and category
rather than per line is deliberate: line numbers move on almost every edit in a documentation
repository, and a baseline that churns is a baseline nobody reads.

Two verdicts fail, for opposite reasons:

- **`added`** -- a marker exists that the budget does not record. A new silencing has to be a
  deliberate act, which is what regenerating the file makes it.
- **`stale`** -- the budget records more than exists. Harmless today, and **that is the trap**: the
  surplus is headroom, so re-adding the marker later passes in silence. The same class of bug as the
  one above, one step removed.

Usage:
    python3 tools/check_allow_budget.py            # verify
    python3 tools/check_allow_budget.py --write    # regenerate after a deliberate change
    python3 tools/check_allow_budget.py --selftest # verdict truth table, no filesystem
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from audit_public_output import (
    FENCE,
    FILE_ALLOW,
    FILE_ALLOW_SCAN_LINES,
    audit_line,
    file_allowances,
    iter_files,
    marker_categories,
    strip_markers,
)

BUDGET = ROOT / "docs" / "agent" / "allow-marker-budget.txt"
TARGET_FIXED_SCHEMA = "knowledge-quality/target-fixed-baseline/v1"
TARGET_FIXED_ENTRY_FIELDS = (
    "target_kind",
    "target_authority_id",
    "target_path",
    "rule_id",
    "category",
    "target_fingerprint",
    "reason",
    "approved_revision",
    "removal_condition",
)
TARGET_KINDS = frozenset({"public-github", "local-kiro"})
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_BROAD_SCOPE = re.compile(r"[*?\[\]{}]")


@dataclass(frozen=True)
class TargetFixedResult:
    """Decision for one approved/observed/proposed target-fixed baseline."""

    verdict: str
    problems: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.verdict in {"ok", "reduced"}


HEADER = """\
# Audit allow markers, counted per file and category. Generated - do not hand-edit.
#
# Regenerate with: python3 tools/check_allow_budget.py --write
# Every marker silences a detector. Adding one looks identical to fixing the problem it silences,
# because the audit passes either way - so the set is kept shrink-only and a rise has to be
# deliberate. A fall is also reported: surplus in this file is headroom that would let the marker
# come back unnoticed.
#
# Format: <path>\\t<category>\\t<count>, sorted. "file:" prefixes a whole-file declaration.
"""

# Deliberately not read from a variable: a mutation that widens this to include "stale" has to
# change this line, and the selftest pins the four rows below.
FAILING = ("added", "stale")


def suppression_verdict(*, findings_with: int, findings_without: int) -> str:
    """Whether one marker is earning its place: "justified" or "inert".

    **The predicate is "ignoring the marker increases the report", not "the report is unchanged".** A
    sibling repository got this wrong first in the mirror-image way and reported the correction: a
    test for "unchanged" finds only markers that suppress nothing, and misses a marker that makes the
    checker report something that is not there. Same-report is the quiet failure; more-report is the
    loud one, and **a rule written to hunt quiet failures will not look for loud ones.**

    Only the quiet half can occur here, because these markers can only remove findings from the line
    they sit on. The predicate is written in the general form anyway, so the loud half cannot slip
    through if a category ever gains cross-line state.

    An inert marker is not merely useless. **It is pre-authorized headroom**: the line suppresses
    nothing today, and silently suppresses a real violation the day the text changes.
    """
    return "justified" if findings_without > findings_with else "inert"


def inert_markers() -> list[str]:
    """Every line-level marker that suppresses nothing, as `path:line`."""
    inert: list[str] = []
    for path in iter_files(ROOT):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        allowed = frozenset(file_allowances(lines))
        in_fence = False
        for number, line in enumerate(lines, 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            # A marker inside a fence is an example of the syntax. `CONTRIBUTING.md` documents the
            # markers in a ```markdown block, and a first version of this check reported those as
            # inert and had them deleted - the rule about excluding fences is already recorded in
            # this repository for the heading detector, and was not applied here.
            # The same extraction the audit uses, or this disagrees with it about what a marker is.
            # A marker inside a code span is documentation of the syntax; `AGENTS.md` tells authors
            # to write one, and searching the raw line reported those two lines as inert markers.
            if in_fence or not marker_categories(line):
                continue
            bare = strip_markers(line)
            verdict = suppression_verdict(
                findings_with=len(audit_line(line, allowed)),
                findings_without=len(audit_line(bare, allowed)),
            )
            if verdict == "inert":
                inert.append(f"{path.relative_to(ROOT).as_posix()}:{number}")
    return inert


def allow_verdict(*, recorded: int | None, actual: int) -> str:
    """Compare one file-and-category count against its baseline.

    | recorded | actual | verdict |
    |---|---|---|
    | absent | > 0 | `added` -- a silencing nobody signed off on |
    | n | > n | `added` |
    | n | < n | `stale` -- surplus is headroom for a silent return |
    | n | n | `ok` |

    `recorded=None, actual=0` cannot occur (nothing generates the key) but answers `ok` rather than
    raising: a guard that crashes on an impossible input gets its caller wrapped in a try block.
    """
    if recorded is None:
        return "added" if actual > 0 else "ok"
    if actual > recorded:
        return "added"
    if actual < recorded:
        return "stale"
    return "ok"


def snapshot() -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for path in iter_files(ROOT):
        rel = path.relative_to(ROOT).as_posix()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        in_fence = False
        for line in lines:
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            # The audit's own extraction, or the two disagree about what a marker is. They did: this
            # counted raw lines while the inert check stripped code spans, so a table cell in
            # `pitfalls.md` showing the syntax was budgeted as a live marker.
            #
            # Fences are skipped on both sides now. The audit stopped honouring a marker inside a
            # fence, so counting one here would budget something that is not a directive, and the
            # asymmetry this comment used to explain away is gone. One definition of what a fence is,
            # imported rather than repeated - two definitions of "what is a marker" already
            # disagreed once.
            for category in marker_categories(line):
                key = (rel, category)
                counts[key] = counts.get(key, 0) + 1
        for line in lines[:FILE_ALLOW_SCAN_LINES]:
            match = FILE_ALLOW.search(line)
            if not match:
                continue
            for category in (c.strip() for c in match.group(1).split(",")):
                if category:
                    key = (rel, f"file:{category}")
                    counts[key] = counts.get(key, 0) + 1
    return counts


def render(counts: dict[tuple[str, str], int]) -> str:
    body = "".join(
        f"{path}\t{category}\t{count}\n"
        for (path, category), count in sorted(counts.items())
    )
    return HEADER + body


def stored() -> dict[tuple[str, str], int] | None:
    if not BUDGET.exists():
        return None
    counts: dict[tuple[str, str], int] = {}
    for line in BUDGET.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        path, category, count = line.split("\t")
        counts[(path, category)] = int(count)
    return counts


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def target_entry_key(entry: Mapping[str, Any]) -> tuple[str, ...]:
    """Return a hashable complete key for an approved or observed JSON entry."""
    return tuple(
        json.dumps(entry.get(field), sort_keys=True, separators=(",", ":"))
        for field in TARGET_FIXED_ENTRY_FIELDS
    )


def target_entry_errors(entry: Mapping[str, Any]) -> list[str]:
    """Reject incomplete entries and any path/rule/category scope broadening."""
    errors: list[str] = []
    unknown = set(entry) - set(TARGET_FIXED_ENTRY_FIELDS)
    missing = set(TARGET_FIXED_ENTRY_FIELDS) - set(entry)
    if unknown:
        errors.append(f"unsupported entry fields: {sorted(unknown)}")
    if missing:
        errors.append(f"missing entry fields: {sorted(missing)}")

    for field in TARGET_FIXED_ENTRY_FIELDS:
        if field == "target_authority_id" or field not in entry:
            continue
        if not _non_empty_string(entry[field]):
            errors.append(f"empty entry field: {field}")

    kind = entry.get("target_kind")
    authority = entry.get("target_authority_id")
    if kind not in TARGET_KINDS:
        errors.append(f"invalid target_kind: {kind!r}")
    elif kind == "public-github" and (
        not isinstance(authority, int) or isinstance(authority, bool) or authority <= 0
    ):
        errors.append(
            "public-github target_authority_id must be a positive repository ID"
        )
    elif kind == "local-kiro" and not _non_empty_string(authority):
        errors.append("local-kiro target_authority_id must be a private opaque key")

    path_value = entry.get("target_path")
    if isinstance(path_value, str):
        path = PurePosixPath(path_value)
        if (
            path.is_absolute()
            or path_value.endswith("/")
            or "\\" in path_value
            or any(part in {"", ".", ".."} for part in path_value.split("/"))
            or _BROAD_SCOPE.search(path_value)
        ):
            errors.append("target_path must name one exact repository-relative target")

    for field in ("rule_id", "category"):
        value = entry.get(field)
        if isinstance(value, str) and (
            _BROAD_SCOPE.search(value) or value in {"all", "file:all"}
        ):
            errors.append(f"{field} must not broaden scope")

    fingerprint = entry.get("target_fingerprint")
    if isinstance(fingerprint, str) and not _SHA256.fullmatch(fingerprint):
        errors.append("target_fingerprint must be sha256:<64 lowercase hex characters>")
    revision = entry.get("approved_revision")
    if isinstance(revision, str) and not _REVISION.fullmatch(revision):
        errors.append("approved_revision must be an immutable 40- or 64-hex revision")
    return errors


def entries_digest(entries: Sequence[Mapping[str, Any]]) -> str:
    """Bind a decision record to the exact sorted set it reviewed."""
    canonical = sorted(
        (
            {field: entry.get(field) for field in TARGET_FIXED_ENTRY_FIELDS}
            for entry in entries
        ),
        key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
    )
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


_DECISION_FIELDS = {
    "decision",
    "decision_source",
    "reason",
    "decision_revision",
    "decided_at",
    "baseline_before_sha256",
    "baseline_after_sha256",
}


def _decision_shape_errors(decision: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(decision) != _DECISION_FIELDS:
        errors.append("human decision record fields do not match the required schema")
    if decision.get("decision") != "APPROVED":
        errors.append("baseline reduction requires an APPROVED decision")
    if decision.get("decision_source") != "human-user":
        errors.append("baseline reduction decision_source must be human-user")
    for field in ("reason", "decision_revision", "decided_at"):
        if not _non_empty_string(decision.get(field)):
            errors.append(f"human decision record has empty {field}")
    revision = decision.get("decision_revision")
    if isinstance(revision, str) and not _REVISION.fullmatch(revision):
        errors.append("decision_revision must be an immutable 40- or 64-hex revision")
    for field in ("baseline_before_sha256", "baseline_after_sha256"):
        digest = decision.get(field)
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            errors.append(f"{field} must be sha256:<64 lowercase hex characters>")
    return errors


def _decision_errors(
    decision: Mapping[str, Any] | None,
    approved: Sequence[Mapping[str, Any]],
    proposed: Sequence[Mapping[str, Any]],
) -> list[str]:
    if not isinstance(decision, Mapping):
        return ["baseline reduction requires a human decision record"]
    errors = _decision_shape_errors(decision)
    if decision.get("baseline_before_sha256") != entries_digest(approved):
        errors.append("human decision record does not bind the approved baseline")
    if decision.get("baseline_after_sha256") != entries_digest(proposed):
        errors.append("human decision record does not bind the proposed baseline")
    return errors


def target_fixed_verdict(
    *,
    approved: Sequence[Mapping[str, Any]],
    actual: Sequence[Mapping[str, Any]],
    proposed: Sequence[Mapping[str, Any]] | None = None,
    human_decision_record: Mapping[str, Any] | None = None,
) -> TargetFixedResult:
    """Accept equality or a human-reviewed true subset; reject every other change.

    `approved` is the last reviewed baseline, `actual` is the detector result, and `proposed` is an
    optional replacement baseline. A reduction passes only when the detector result equals the
    proposed true subset and the decision record binds both exact sets. This lets remediation and
    baseline removal land together without leaving stale surplus.
    """
    candidate = approved if proposed is None else proposed
    problems: list[str] = []
    for label, entries in (
        ("approved", approved),
        ("actual", actual),
        ("proposed", candidate),
    ):
        for index, entry in enumerate(entries):
            problems.extend(
                f"{label}[{index}]: {error}" for error in target_entry_errors(entry)
            )
        keys = [target_entry_key(entry) for entry in entries]
        if len(keys) != len(set(keys)):
            problems.append(f"{label}: duplicate target-fixed entry")

    approved_keys = {target_entry_key(entry) for entry in approved}
    candidate_keys = {target_entry_key(entry) for entry in candidate}
    if candidate_keys == approved_keys:
        change = "ok"
    elif candidate_keys < approved_keys:
        change = "reduced"
        problems.extend(_decision_errors(human_decision_record, approved, candidate))
    else:
        added = candidate_keys - approved_keys
        removed = approved_keys - candidate_keys
        problems.append(
            "substitution is forbidden"
            if added and removed
            else "baseline addition is forbidden"
        )
        change = "rejected"

    effective_keys = {target_entry_key(entry) for entry in candidate}
    actual_keys = {target_entry_key(entry) for entry in actual}
    if actual_keys - effective_keys:
        problems.append("actual target addition or substitution is not approved")
    if effective_keys - actual_keys:
        problems.append("stale baseline surplus is forbidden")

    if problems:
        return TargetFixedResult("rejected", tuple(problems))
    return TargetFixedResult(change)


def validate_target_fixed_document(document: Mapping[str, Any]) -> list[str]:
    """Validate a private target-fixed baseline document without changing it."""
    errors: list[str] = []
    allowed = {"schema", "entries", "human_decision_record"}
    missing = allowed - set(document)
    if missing:
        errors.append(f"missing document fields: {sorted(missing)}")
    if set(document) - allowed:
        errors.append(f"unsupported document fields: {sorted(set(document) - allowed)}")
    if document.get("schema") != TARGET_FIXED_SCHEMA:
        errors.append(f"schema must be {TARGET_FIXED_SCHEMA}")
    entries = document.get("entries")
    if not isinstance(entries, list):
        return errors + ["entries must be an array"]
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            errors.append(f"entries[{index}] must be an object")
            continue
        errors.extend(
            f"entries[{index}]: {error}" for error in target_entry_errors(entry)
        )
    keys = [target_entry_key(entry) for entry in entries if isinstance(entry, Mapping)]
    if len(keys) != len(set(keys)):
        errors.append("entries must be unique")
    decision = document.get("human_decision_record")
    if decision is not None and not isinstance(decision, Mapping):
        errors.append("human_decision_record must be an object or null")
    elif isinstance(decision, Mapping):
        errors.extend(_decision_shape_errors(decision))
    return errors


def load_target_fixed_document(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError("target-fixed baseline must be a JSON object")
    errors = validate_target_fixed_document(document)
    if errors:
        raise ValueError("; ".join(errors))
    return document


def _run_target_fixed_check(
    baseline_path: Path, actual_path: Path, candidate_path: Path | None
) -> int:
    try:
        baseline = load_target_fixed_document(baseline_path)
        actual = load_target_fixed_document(actual_path)
        candidate = (
            load_target_fixed_document(candidate_path)
            if candidate_path is not None
            else None
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"target-fixed baseline failed: {error}", file=sys.stderr)
        return 1
    result = target_fixed_verdict(
        approved=baseline["entries"],
        actual=actual["entries"],
        proposed=candidate["entries"] if candidate else None,
        human_decision_record=(candidate or {}).get("human_decision_record"),
    )
    if not result.accepted:
        print("target-fixed baseline failed:", file=sys.stderr)
        for problem in result.problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(
        f"target-fixed baseline: {len(actual['entries'])} entr(ies), {result.verdict}"
    )
    return 0


def selftest() -> int:
    suppression_cases = [
        ({"findings_with": 0, "findings_without": 1}, "justified"),
        ({"findings_with": 0, "findings_without": 0}, "inert"),
        ({"findings_with": 1, "findings_without": 1}, "inert"),
        # The loud half: a marker that adds a finding. Cannot occur with today's categories, and the
        # predicate refuses it anyway rather than reading "changed" as "earning its place".
        ({"findings_with": 1, "findings_without": 0}, "inert"),
    ]
    cases = [
        ({"recorded": None, "actual": 1}, "added"),
        ({"recorded": 3, "actual": 4}, "added"),
        ({"recorded": 3, "actual": 2}, "stale"),
        ({"recorded": 3, "actual": 3}, "ok"),
        ({"recorded": None, "actual": 0}, "ok"),
        ({"recorded": 1, "actual": 0}, "stale"),
    ]
    failures = 0
    for kwargs, expected in suppression_cases:
        got = suppression_verdict(**kwargs)  # type: ignore[arg-type]
        if got != expected:
            print(
                f"FAIL: suppression_verdict({kwargs}) = {got!r}, expected {expected!r}"
            )
            failures += 1
    for kwargs, expected in cases:
        got = allow_verdict(**kwargs)  # type: ignore[arg-type]
        if got != expected:
            print(f"FAIL: allow_verdict({kwargs}) = {got!r}, expected {expected!r}")
            failures += 1
    # Both directions have to fail, or the shrink-only property is only half enforced.
    for verdict in ("added", "stale"):
        if verdict not in FAILING:
            print(f"FAIL: {verdict!r} does not fail the check")
            failures += 1
    if "ok" in FAILING:
        print("FAIL: 'ok' fails the check, which refuses every clean run")
        failures += 1
    print("selftest: 13 case(s) passed" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--target-fixed-baseline", type=Path)
    parser.add_argument("--target-fixed-actual", type=Path)
    parser.add_argument("--target-fixed-candidate", type=Path)
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    target_fixed_requested = any(
        (
            args.target_fixed_baseline,
            args.target_fixed_actual,
            args.target_fixed_candidate,
        )
    )
    if target_fixed_requested:
        if args.write:
            parser.error("--write cannot update a target-fixed baseline")
        if not args.target_fixed_baseline or not args.target_fixed_actual:
            parser.error(
                "--target-fixed-baseline and --target-fixed-actual are required together"
            )
        return _run_target_fixed_check(
            args.target_fixed_baseline,
            args.target_fixed_actual,
            args.target_fixed_candidate,
        )

    counts = snapshot()
    if args.write:
        BUDGET.parent.mkdir(parents=True, exist_ok=True)
        BUDGET.write_text(render(counts), encoding="utf-8")
        total = sum(counts.values())
        print(f"allow budget: wrote {len(counts)} entr(ies), {total} marker(s)")
        return 0

    inert = inert_markers()
    if inert:
        print(
            "allow budget failed: marker(s) that suppress nothing. Each one is headroom - the line "
            "is exempt today and silently exempt for a real violation tomorrow. Delete them:",
            file=sys.stderr,
        )
        for entry in inert:
            print(f"  {entry}", file=sys.stderr)
        return 1

    recorded = stored()
    if recorded is None:
        print(
            f"{BUDGET.relative_to(ROOT)} is missing. Generate it with --write.",
            file=sys.stderr,
        )
        return 1

    problems: list[str] = []
    for key in sorted(set(recorded) | set(counts)):
        verdict = allow_verdict(recorded=recorded.get(key), actual=counts.get(key, 0))
        if verdict not in FAILING:
            continue
        path, category = key
        was, now = recorded.get(key, 0), counts.get(key, 0)
        if verdict == "added":
            problems.append(
                f"{path}: allow:{category} {was} -> {now}. A new marker silences a detector; "
                "confirm it is the narrowest option, then run --write."
            )
        else:
            problems.append(
                f"{path}: allow:{category} {was} -> {now}. The budget now records more than "
                "exists, and the surplus would let the marker return unnoticed. Run --write."
            )
    if problems:
        print("allow budget failed:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(
        f"allow budget: {len(counts)} entr(ies), {sum(counts.values())} marker(s), unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
