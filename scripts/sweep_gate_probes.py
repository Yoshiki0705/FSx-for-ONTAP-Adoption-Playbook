#!/usr/bin/env python3
"""Remove probe files a killed test run left in the tree.

The gate tests write a probe into `docs/` or `examples/`, run a gate against it, and remove it in a
`finally`. **That cleanup does not run when the process is killed** - a timeout, a Ctrl-C, an editor
closing the terminal - and the leftover then fails every subsequent gate for a reason unrelated to
whatever the next person is doing.

It happened twice in one session: a `git push` was refused because the pre-push gate found a probe
note with an `evidence` tier and no supporting body, and a second time because `shellcheck` was
handed a probe script that vanished between the glob and the read. Both were worked around by hand,
which is the wrong repair - **the next person hits the same wall and has no reason to suspect a dead
test run.**

So the sweep is not cleanup after the fact. It runs *before* the checks, so a poisoned tree heals
instead of blocking, and it prints what it removed rather than doing it silently: a file appearing
under `docs/` is worth one line of output.

The name is the contract. Anything matching `zz-gate-probe*` is a test artifact and nothing else may
be called that; `test_no_probe_name_collision` in the gate tests holds that.

Usage:
    python3 scripts/sweep_gate_probes.py           # remove and report
    python3 scripts/sweep_gate_probes.py --check   # report and fail if any exist
    python3 scripts/sweep_gate_probes.py --selftest
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The prefix the gate tests use for every artifact they write into the tree.
PREFIX = "zz-gate-probe"

# Where a probe can legitimately appear. Bounded rather than a whole-tree walk: an unbounded delete
# keyed on a name pattern is a worse failure than the one being fixed.
SEARCH_DIRS = ("docs", "examples")


def stale_probes(root: Path = ROOT) -> list[Path]:
    """Probe files present in the tree, sorted for a stable report."""
    found: list[Path] = []
    for directory in SEARCH_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        found.extend(p for p in base.rglob(f"{PREFIX}*") if p.is_file())
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report without removing, and exit non-zero if any exist",
    )
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        # A real file under a temporary root, because the point of this script is filesystem state.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs" / "ja").mkdir(parents=True)
            (root / "docs" / "ja" / f"{PREFIX}.md").write_text("x", encoding="utf-8")
            (root / "docs" / "ja" / "real-note.md").write_text("x", encoding="utf-8")
            found = stale_probes(root)
            if [p.name for p in found] != [f"{PREFIX}.md"]:
                print(f"FAIL: found {[p.name for p in found]}")
                return 1
            if stale_probes(root / "nowhere"):
                print("FAIL: a missing root reported probes")
                return 1
        print("selftest: 2 case(s) passed")
        return 0

    found = stale_probes()
    if not found:
        return 0
    for path in found:
        print(
            f"gate probe left by a killed test run: {path.relative_to(ROOT)}",
            file=sys.stderr,
        )
    if args.check:
        print(
            "  Run `python3 scripts/sweep_gate_probes.py` to remove them.",
            file=sys.stderr,
        )
        return 1
    for path in found:
        path.unlink()
    print(f"swept {len(found)} stale gate probe(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
