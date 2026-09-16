#!/usr/bin/env python3
"""Report how much of each module is still Japanese-only, so the backlog is measured rather than recalled.

This exists because the backlog was reported as "7 pages" when it was 83. Nobody had lied — the number
had simply never been derived, and a figure carried in someone's head is a figure that is wrong by the
time it is quoted. `docs/agent/localization.md` gives two conditions for translating a note, and both
are properties of the tree rather than opinions: whether an English reader reaches it from a module
README, and whether its content has settled. So both are computed here.

**This is not a gate.** An untranslated note is not a failure — `localization.md` says explicitly not
to translate one merely because it is untranslated. What a gate would produce is pressure to translate
for the sake of the number, which is the opposite of the rule. It reports and exits 0.

The settledness column is a proxy and is labelled as one: commits touching the file, and the date of
the most recent one. A note revised several times over weeks has settled in a way that a note written
once yesterday has not, and the two are indistinguishable from a count alone. The date is what
separates them.

Run:  make i18n-status
      python3 tools/report_i18n_status.py [--module NAME]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JA = ROOT / "docs" / "ja"
EN = ROOT / "docs" / "en"


def git_facts(path: Path) -> tuple[int, str]:
    """Return (commits touching the file, date of the most recent) as a settledness proxy."""
    rel = str(path.relative_to(ROOT))
    log = subprocess.run(
        ["git", "log", "--format=%ad", "--date=short", "--", rel],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    return len(log), (log[0] if log else "-")


def leaves(area: str) -> list[Path]:
    """Localizable leaves under one area of docs/ja, excluding the bilingual hubs."""
    found: list[Path] = []
    for sub in ("notes", "checklists"):
        found += sorted((JA / area).glob(f"*/{sub}/*.md"))
    return [p for p in found if "_template" not in p.parts]


def rows(area: str) -> list[tuple[str, int, int, int, int, int, str]]:
    out = []
    for module_dir in sorted(d for d in (JA / area).iterdir() if d.is_dir()):
        module = module_dir.name
        if module.startswith("_"):
            continue
        ja_files = [p for p in leaves(area) if p.relative_to(JA).parts[1] == module]
        if not ja_files:
            continue
        untranslated = [p for p in ja_files if not (EN / p.relative_to(JA)).is_file()]
        facts = [git_facts(p) for p in untranslated]
        out.append(
            (
                f"{area}/{module}",
                len(ja_files),
                len(ja_files) - len(untranslated),
                len(untranslated),
                sum(sum(1 for _ in p.open()) for p in untranslated),
                max((c for c, _ in facts), default=0),
                max((d for _, d in facts), default="-"),
            )
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", help="report one module only, e.g. performance")
    args = parser.parse_args()

    table = rows("domains") + rows("playbooks")
    if args.module:
        table = [r for r in table if r[0].endswith("/" + args.module)]
        if not table:
            print(f"no module matching {args.module!r}", file=sys.stderr)
            return 1

    head = f"{'module':<32} {'ja':>3} {'en':>3} {'todo':>4} {'lines':>6} {'max cm':>6}  newest"
    print(head)
    print("-" * len(head))
    for name, ja, en, todo, lines, cm, newest in table:
        state = "complete" if not todo else newest
        print(
            f"{name:<32} {ja:>3} {en:>3} {todo:>4} {lines:>6} "
            f"{(cm if todo else 0):>6}  {state}"
        )
    total_todo = sum(r[3] for r in table)
    total_lines = sum(r[4] for r in table)
    closed = sum(1 for r in table if not r[3])
    print("-" * len(head))
    print(
        f"{len(table)} module(s), {closed} closed, "
        f"{total_todo} page(s) Japanese-only, {total_lines} line(s)"
    )
    print(
        "'max cm' and 'newest' are a settledness proxy, not a verdict: a note revised several "
        "times over weeks has settled in a way one written once yesterday has not."
    )
    print(
        "Translating is not required. docs/agent/localization.md gives the two conditions; this "
        "report supplies the inputs, not the decision."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
