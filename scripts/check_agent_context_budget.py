#!/usr/bin/env python3
"""Check for drift between AGENTS.md and .kiro/steering/project-knowledge-base.md.

This script does NOT require content duplication — it checks that:
1. AGENTS.md stays within a size budget (it is loaded every turn).
2. The workspace steering file is a thin loader (< 50% of AGENTS.md size).
3. Both declare the authority relationship ("AGENTS.md wins").

It is deliberately not checking content overlap or heading correspondence,
because the two files serve different purposes: AGENTS.md is the public,
comprehensive reference for all collaborators; the steering file is the
workflow-oriented subset for Kiro sessions. Forcing them to mirror each
other would create the very duplication that learned-constraints #1 warns
against.

What this DOES catch:
- AGENTS.md growing unchecked (the budget is generous — 45 KB — but exists).
- The steering file growing into a second copy of AGENTS.md.
- The authority relationship disappearing (which would leave ambiguity about
  which file wins on disagreement).

Run:  python3 scripts/check_agent_context_budget.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_MD = ROOT / "AGENTS.md"
STEERING = ROOT / ".kiro" / "steering" / "project-knowledge-base.md"

# Budgets (bytes). These are deliberately generous: the goal is to catch
# unbounded growth, not to force minimalism.
AGENTS_MAX_BYTES = 45_000  # ~45 KB
STEERING_MAX_RATIO = 0.60  # steering must be < 60% of AGENTS.md size

# Authority markers: at least one of these must appear in each file.
AUTHORITY_MARKERS_AGENTS = [
    "AGENTS.md wins",
    "This file is committed",
    "what collaborators and other agents actually receive",
]
AUTHORITY_MARKERS_STEERING = [
    "AGENTS.md wins",
    "When they disagree",
    "committed equivalent",
]


def main() -> int:
    problems: list[str] = []

    # 1. AGENTS.md size budget
    if not AGENTS_MD.exists():
        problems.append("AGENTS.md not found at repository root")
    else:
        size = AGENTS_MD.stat().st_size
        if size > AGENTS_MAX_BYTES:
            problems.append(
                f"AGENTS.md is {size:,} bytes (budget: {AGENTS_MAX_BYTES:,}). "
                "Consider extracting task-specific content to docs/ and leaving "
                "an index line in AGENTS.md."
            )

    # 2. Steering ratio
    if STEERING.exists() and AGENTS_MD.exists():
        s_size = STEERING.stat().st_size
        a_size = AGENTS_MD.stat().st_size
        ratio = s_size / a_size if a_size > 0 else 0
        if ratio > STEERING_MAX_RATIO:
            problems.append(
                f".kiro/steering/ is {s_size:,} bytes ({ratio:.0%} of AGENTS.md). "
                f"It should be a thin loader (< {STEERING_MAX_RATIO:.0%}). "
                "Move prose to AGENTS.md and keep steering as workflow notes only."
            )

    # 3. Authority relationship
    if AGENTS_MD.exists():
        content = AGENTS_MD.read_text(encoding="utf-8")
        if not any(m in content for m in AUTHORITY_MARKERS_AGENTS):
            problems.append(
                "AGENTS.md does not declare itself as the authoritative source. "
                "Add a statement like 'This file is committed and travels with the repo.'"
            )

    if STEERING.exists():
        content = STEERING.read_text(encoding="utf-8")
        if not any(m in content for m in AUTHORITY_MARKERS_STEERING):
            problems.append(
                ".kiro/steering/ does not defer to AGENTS.md. "
                "Add: 'When they disagree, AGENTS.md wins.'"
            )

    if problems:
        print(f"drift: {len(problems)} issue(s):")
        for p in problems:
            print(f"  - {p}")
        return 1

    # Report sizes when healthy (informational)
    a_size = AGENTS_MD.stat().st_size if AGENTS_MD.exists() else 0
    s_size = STEERING.stat().st_size if STEERING.exists() else 0
    ratio = s_size / a_size if a_size > 0 else 0
    print(
        f"drift: healthy "
        f"(AGENTS.md {a_size:,}B / {AGENTS_MAX_BYTES:,}B budget, "
        f"steering {ratio:.0%} ratio)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
