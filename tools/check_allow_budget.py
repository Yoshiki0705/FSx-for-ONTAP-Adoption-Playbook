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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from audit_public_output import (
    ALLOW,
    CODE_SPAN,
    FENCE,
    FILE_ALLOW,
    FILE_ALLOW_SCAN_LINES,
    audit_line,
    file_allowances,
    iter_files,
)

BUDGET = ROOT / "docs" / "agent" / "allow-marker-budget.txt"

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
            if in_fence or not ALLOW.search(CODE_SPAN.sub("", line)):
                continue
            bare = ALLOW.sub("", line)
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
            for match in ALLOW.finditer(CODE_SPAN.sub("", line)):
                key = (rel, match.group(1))
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
    args = parser.parse_args()
    if args.selftest:
        return selftest()

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
