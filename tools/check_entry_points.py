#!/usr/bin/env python3
"""Every module README carries an entry point, not only a table of contents.

The module template says a module needs an **entry point** and that **the entry point is not a table
of contents**. Three of the four elements it names are visible when absent - a missing decision tree
or comparison is a missing file. **An absent entry point looks like nothing at all**, which is why
twelve of fourteen modules went without one while the criterion sat in the template.

The check matches on the heading alone. That is deliberate and it is what rejects the question table
for free: a README with only `## このモジュールが扱う問い` fails, because the heading is not one of the
accepted forms. **Do not widen the match to accept a table of contents.**

It does not look inside the section. "Three rows keyed on what the reader arrives with" is guidance,
and a regex adjudicating it would fail on a fourth row that is worth having.

Accepted headings are a small set rather than one literal, because two shapes are both correct:
`performance` has an order, so `読む順序` fits it, and the routers added later name what the reader
gets. The set appears in the failure message so the fix does not require reading this file.

Usage:
    python3 tools/check_entry_points.py            # verify
    python3 tools/check_entry_points.py --selftest # verdict truth table, no filesystem
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Both languages, because an English reader arrives at the English README.
ACCEPTED_JA = ("読む順序", "最初に読むもの")
ACCEPTED_EN = ("Read first", "Start here", "Reading order")

HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)
FENCE = re.compile(r"^\s*(```|~~~)")

# A README that is only a table of contents. Named so the failure message can say what was found
# instead of the entry point, rather than only what was missing.
CONTENTS_JA = "このモジュールが扱う問い"
CONTENTS_EN = "Questions this module answers"

CASES = [
    ("## 最初に読むもの\n\n## このモジュールが扱う問い\n", "ja", "ok"),
    ("## 読む順序\n\n## このモジュールが扱う問い\n", "ja", "ok"),
    # The case the whole check exists for: a table of contents and nothing else.
    ("## このモジュールが扱う問い\n", "ja", "missing"),
    ("## 構成\n\n## 読み方\n", "ja", "missing"),
    ("## Read first\n\n## Questions this module answers\n", "en", "ok"),
    ("## Questions this module answers\n", "en", "missing"),
    # Inside a fence it is an example, not a heading. The same rule the heading-style and
    # allow-marker checks use, and the reason those two both had to learn it separately.
    (
        "```markdown\n## 最初に読むもの\n```\n\n## このモジュールが扱う問い\n",
        "ja",
        "missing",
    ),
]


def headings(text: str) -> list[str]:
    """Level-2 headings outside fenced blocks."""
    found: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(line)
        if match:
            found.append(match.group(1).strip())
    return found


def entry_verdict(text: str, lang: str) -> str:
    """Whether this README has an entry point: "ok" or "missing"."""
    accepted = ACCEPTED_EN if lang != "ja" else ACCEPTED_JA
    return "ok" if any(h in accepted for h in headings(text)) else "missing"


def module_readmes() -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for lang_dir in sorted((ROOT / "docs").iterdir()):
        if not lang_dir.is_dir():
            continue
        for axis in ("domains", "playbooks"):
            for module in sorted((lang_dir / axis).glob("*/README.md")):
                if "_template" in module.parts:
                    continue
                found.append((module, lang_dir.name))
    return found


def selftest() -> int:
    failures = 0
    for text, lang, expected in CASES:
        got = entry_verdict(text, lang)
        if got != expected:
            print(
                f"FAIL: entry_verdict({text!r:.40}, {lang!r}) = {got!r}, expected {expected!r}"
            )
            failures += 1
    # A table of contents must never be accepted as the entry point. Asserted separately from the
    # cases so that widening ACCEPTED_* to include it fails here even if a case is edited to match.
    for contents, lang in ((CONTENTS_JA, "ja"), (CONTENTS_EN, "en")):
        if entry_verdict(f"## {contents}\n", lang) != "missing":
            print(f"FAIL: {contents!r} is accepted as an entry point")
            failures += 1
    print(
        f"selftest: {len(CASES) + 2} case(s) passed"
        if not failures
        else f"{failures} failure(s)"
    )
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()

    readmes = module_readmes()
    if not readmes:
        print("no module README found, so this check verified nothing", file=sys.stderr)
        return 1

    problems: list[str] = []
    for path, lang in readmes:
        text = path.read_text(encoding="utf-8")
        if entry_verdict(text, lang) == "missing":
            accepted = ACCEPTED_EN if lang != "ja" else ACCEPTED_JA
            found = (
                ", ".join(f"'{h}'" for h in headings(text)[:3]) or "no level-2 heading"
            )
            problems.append(
                f"{path.relative_to(ROOT)}: no entry point. Add a section headed one of "
                f"{' / '.join(accepted)} above the question table. Found: {found}. "
                "The entry point routes on what the reader arrives with; the question table is the "
                "table of contents and does not count."
            )
    if problems:
        print(f"entry points failed ({len(problems)} issue(s)):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(f"entry points: {len(readmes)} module README(s) route the reader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
