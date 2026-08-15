#!/usr/bin/env python3
"""Keep always-loaded agent context small, and keep the knowledge itself public.

Two failure modes, pulling in opposite directions
------------------------------------------------
1. `AGENTS.md` is read on every turn and cannot be made conditional. Material that
   only matters during one kind of work — a pitfalls table, a translation
   procedure, diagram export rules — is paid for on every turn where it is
   irrelevant. Left alone it grows monotonically, because adding a section is
   always locally justified.

2. The obvious fix is to move that material into `.kiro/steering/`. But `.kiro/`
   is gitignored here (BLEA convention), so moving prose there *deletes it from
   the published repository* while leaving the agent apparently well-informed.
   Collaborators lose it, CI cannot check it, and nothing reports the loss.

So the rule is: the body lives in a tracked file, `.kiro/steering/` holds only a
thin loader recording when to read it, and `AGENTS.md` keeps a one-line index.
This script checks all three ends of that arrangement, plus the reachability
rules that decide whether a steering file is loaded at all.

An earlier version guarded `.kiro/` with `if STEERING.exists()`, which meant the
loader checks silently did nothing in CI — the exact "gate that never runs"
shape it was written to prevent. Absence is now reported, not skipped.

Run:  python3 scripts/check_agent_context_budget.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_MD = ROOT / "AGENTS.md"
STEERING_DIR = ROOT / ".kiro" / "steering"
AGENT_DOCS_DIR = ROOT / "docs" / "agent"

# Budgets in bytes. Set close to current size so growth is a decision, not a drift.
# Raising one is allowed; doing it silently is what this prevents.
AGENTS_MAX_BYTES = 30_000
LOADER_MAX_BYTES = 2_000  # one steering file
STEERING_MAX_TOTAL = 6_000  # all steering files together

AUTHORITY_MARKERS_AGENTS = (
    "AGENTS.md wins",
    "This file is committed",
    "what collaborators and other agents actually receive",
)
AUTHORITY_MARKERS_LOADER = ("AGENTS.md",)

VALID_INCLUSION = {"always", "fileMatch", "manual", "auto"}
FRONT_MATTER_FIELD = re.compile(r"^([a-zA-Z_][\w-]*)\s*:\s*(.*)$")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    for line in text[3:end].splitlines():
        match = FRONT_MATTER_FIELD.match(line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def tracked_paths() -> set[str]:
    done = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return set(done.stdout.split())


def check_agents_md(problems: list[str]) -> None:
    if not AGENTS_MD.exists():
        problems.append("AGENTS.md not found at repository root")
        return
    size = AGENTS_MD.stat().st_size
    if size > AGENTS_MAX_BYTES:
        problems.append(
            f"AGENTS.md is {size:,} bytes (budget {AGENTS_MAX_BYTES:,}). It is loaded on "
            "every turn. Move task-specific material to docs/agent/, add a thin "
            ".kiro/steering/ loader, and leave one index line here."
        )
    content = AGENTS_MD.read_text(encoding="utf-8")
    if not any(marker in content for marker in AUTHORITY_MARKERS_AGENTS):
        problems.append(
            "AGENTS.md does not declare itself authoritative. Without that, a stale "
            "copy in .kiro/ can silently win."
        )


def check_index_is_reachable_and_tracked(
    problems: list[str], tracked: set[str]
) -> None:
    """Every indexed document must exist, and must be published.

    An index line pointing into gitignored territory is worse than no index: it
    reads as though the material is available to everyone.
    """
    if not AGENTS_MD.exists():
        return
    content = AGENTS_MD.read_text(encoding="utf-8")
    indexed = {t for t in MD_LINK.findall(content) if t.startswith("docs/agent/")}

    for target in sorted(indexed):
        relative = target.split("#", 1)[0]
        if not (ROOT / relative).exists():
            problems.append(f"AGENTS.md indexes {relative}, which does not exist")
        elif relative not in tracked:
            problems.append(
                f"AGENTS.md indexes {relative}, which is not tracked by git. "
                "Readers of the public repository would not have it."
            )

    if AGENT_DOCS_DIR.is_dir():
        for path in sorted(AGENT_DOCS_DIR.glob("*.md")):
            relative = path.relative_to(ROOT).as_posix()
            if relative not in indexed:
                problems.append(
                    f"{relative} exists but AGENTS.md does not index it, so nothing "
                    "tells an agent when to read it."
                )


def check_steering_loaders(
    problems: list[str], notes: list[str], tracked: set[str]
) -> None:
    if not STEERING_DIR.is_dir():
        # Not a failure: .kiro/ is gitignored, so it is legitimately absent in CI.
        # It must be stated, or a green run implies a check that did not happen.
        notes.append(
            ".kiro/steering/ is absent, so loader thinness and loader reachability were "
            "NOT checked here. That is expected in CI (.kiro/ is gitignored) and a "
            "problem locally — run `make drift` on a working copy that has it."
        )
        return

    files = sorted(STEERING_DIR.glob("*.md"))
    if not files:
        problems.append(".kiro/steering/ exists but holds no steering file")
        return

    total = 0
    for path in files:
        where = f".kiro/steering/{path.name}"
        size = path.stat().st_size
        total += size
        if size > LOADER_MAX_BYTES:
            problems.append(
                f"{where} is {size:,} bytes (loader budget {LOADER_MAX_BYTES:,}). "
                "A steering file this size is holding content, not a pointer — and "
                ".kiro/ is not published, so that content is invisible to everyone else."
            )

        fields = front_matter(path)
        inclusion = fields.get("inclusion", "always")
        if inclusion not in VALID_INCLUSION:
            problems.append(f"{where}: inclusion '{inclusion}' is not a valid value")
        if inclusion == "auto":
            missing = [k for k in ("name", "description") if not fields.get(k)]
            if missing:
                problems.append(
                    f"{where}: inclusion:auto without {' and '.join(missing)}. Kiro does "
                    "not register the file, so it is never loaded and never errors."
                )
        if inclusion == "fileMatch" and not fields.get("fileMatchPattern"):
            problems.append(f"{where}: inclusion:fileMatch without fileMatchPattern")

        body = path.read_text(encoding="utf-8")
        if not any(marker in body for marker in AUTHORITY_MARKERS_LOADER):
            problems.append(
                f"{where} does not point back at AGENTS.md as authoritative"
            )

        for target in MD_LINK.findall(body):
            relative = target.split("#", 1)[0]
            if relative.startswith(("http://", "https://")):
                continue
            resolved = (path.parent / relative).resolve()
            try:
                as_posix = resolved.relative_to(ROOT).as_posix()
            except ValueError:
                problems.append(f"{where} links outside the repository: {relative}")
                continue
            if not resolved.exists():
                problems.append(f"{where} links to {as_posix}, which does not exist")
            elif as_posix not in tracked:
                problems.append(
                    f"{where} links to {as_posix}, which is not tracked by git. The "
                    "body of a loader must be published, or only this machine has it."
                )

    if total > STEERING_MAX_TOTAL:
        problems.append(
            f".kiro/steering/ totals {total:,} bytes (budget {STEERING_MAX_TOTAL:,})"
        )


def main() -> int:
    problems: list[str] = []
    notes: list[str] = []
    tracked = tracked_paths()

    check_agents_md(problems)
    check_index_is_reachable_and_tracked(problems, tracked)
    check_steering_loaders(problems, notes, tracked)

    for note in notes:
        print(f"drift: note: {note}")

    if problems:
        print(f"drift: {len(problems)} issue(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    size = AGENTS_MD.stat().st_size if AGENTS_MD.exists() else 0
    steering_total = (
        sum(p.stat().st_size for p in STEERING_DIR.glob("*.md"))
        if STEERING_DIR.is_dir()
        else 0
    )
    print(
        f"drift: healthy (AGENTS.md {size:,}B / {AGENTS_MAX_BYTES:,}B budget, "
        f"steering {steering_total:,}B / {STEERING_MAX_TOTAL:,}B)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
