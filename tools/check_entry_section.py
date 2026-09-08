#!/usr/bin/env python3
"""Check that every module README opens with an entry point.

Both `_template` READMEs list four elements that make a module done, and the first is the entry
point: "ここから読む", routing the reader in three steps or fewer at the top of `README.md`. When
this check was written the criterion was met by **one module out of fourteen** — including the one
the criterion came from. A criterion that the session which wrote it did not apply has no reason to
be applied by anyone later.

The other three elements are at least visible. A missing decision tree or comparison shows up as an
absent file. **An absent entry point shows up as nothing at all** — the reader lands on a table of
contents, which looks like a page that works.

So this gate asserts the position, not the prose:

  The first `##` heading of a module README is one of the accepted entry-point headings.

Requiring it to be *first* is what rejects a table of contents as the entry point. `##
このモジュールが扱う問い` is a good section and a bad entry point: it lists what the module covers
without telling a reader which single page to open. Matching on the heading alone gives that for
free, so the accepted set stays small and deliberately does not include it.

**The contents are not checked.** Three rows keyed on what the reader arrives with is guidance, not
something a regex should adjudicate. And there is no exemption marker: if a module legitimately
needs no entry point, that is an argument against the criterion rather than for a marker, and it
belongs in an issue.

A language whose heading is not listed here fails rather than passes. The accepted set is printed
with the failure, because the fix for a newly translated tree is to add its form to the set — and a
gate that silently accepts an unknown heading would let the next language ship without an entry
point at all.

Run:  python3 tools/check_entry_section.py [--path DIR]
      python3 tools/check_entry_section.py --selftest
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The two navigation axes that have modules. `case-studies` and `reference` are not modules and have
# no completion criterion.
AXES = ("domains", "playbooks")

# Accepted entry-point headings, per language that has module READMEs. Two forms per language rather
# than one: `performance` routes by reading order and `block-storage` routes by what the reader
# arrives with, and both satisfy the criterion. Widening this set is how the gate stops meaning
# anything, so a new entry belongs with a module that uses it.
ACCEPTED = (
    "最初に読むもの",
    "読む順序",
    "Read first",
    "Reading order",
)

HEADING = re.compile(r"^##\s+(.+?)\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")


def first_h2(text: str) -> str | None:
    """The first `##` heading outside a fenced block, or None when there is none.

    Fences are skipped because a shell comment inside one is not a heading. Reading them as headings
    is how a detector ends up reporting on code it should not see.
    """
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        found = HEADING.match(line)
        if found:
            return found.group(1)
    return None


def module_readmes(base: Path) -> list[Path]:
    """Every module README under any language tree, excluding the templates."""
    found: list[Path] = []
    for language in sorted(p for p in base.iterdir() if p.is_dir()):
        for axis in AXES:
            axis_dir = language / axis
            if not axis_dir.is_dir():
                continue
            for module in sorted(p for p in axis_dir.iterdir() if p.is_dir()):
                if module.name.startswith("_"):
                    continue
                readme = module / "README.md"
                if readme.is_file():
                    found.append(readme)
    return found


def check(base: Path) -> list[str]:
    issues: list[str] = []
    for readme in module_readmes(base):
        relative = readme.relative_to(ROOT) if readme.is_absolute() else readme
        heading = first_h2(readme.read_text(encoding="utf-8"))
        if heading is None:
            issues.append(f"{relative}: no `##` section at all")
        elif heading not in ACCEPTED:
            issues.append(f"{relative}: opens with `## {heading}`")
    return issues


def selftest() -> int:
    """Check the detector on inputs whose verdict is known, in both directions."""
    body = "\n| a | b |\n|---|---|\n| c | d |\n\n## このモジュールが扱う問い\n"
    cases: list[tuple[str, str, bool]] = [
        ("entry point first, ja", "## 最初に読むもの" + body, True),
        ("entry point first, en", "## Read first" + body, True),
        ("reading order, ja", "## 読む順序" + body, True),
        ("reading order, en", "## Reading order" + body, True),
        (
            "table of contents first",
            "## このモジュールが扱う問い\n\n## 最初に読むもの\n",
            False,
        ),
        ("entry point present but not first", "## 構成\n\n## 読む順序\n", False),
        ("no section at all", "prose with no heading\n", False),
        ("h3 does not count", "### 最初に読むもの\n\n## 構成\n", False),
        (
            "a fenced heading is not a heading",
            "```sh\n## Read first\n```\n\n## 構成\n",
            False,
        ),
    ]
    failures = 0
    for name, text, expected in cases:
        actual = first_h2(text) in ACCEPTED
        if actual is not expected:
            print(f"  selftest FAILED: {name} (expected {expected}, got {actual})")
            failures += 1

    # The walk, not the pattern. A template must stay exempt, and a language without module
    # directories must contribute nothing rather than raising.
    import tempfile

    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        (base / "xx" / "domains" / "_template").mkdir(parents=True)
        (base / "xx" / "domains" / "_template" / "README.md").write_text(
            "## 構成\n", encoding="utf-8"
        )
        (base / "yy").mkdir()
        (base / "yy" / "README.md").write_text("## anything\n", encoding="utf-8")
        walked = module_readmes(base)
        if walked:
            print(f"  selftest FAILED: walk included {walked}")
            failures += 1

    if failures:
        print(f"entry-point selftest failed ({failures} case(s))")
        return 1
    print(f"selftest: {len(cases)} case(s) + the walk")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path", default="docs", help="directory containing the language trees"
    )
    parser.add_argument(
        "--selftest", action="store_true", help="check the detector, not the tree"
    )
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    readmes = module_readmes(Path(args.path))
    issues = check(Path(args.path))
    if issues:
        print(f"entry points failed ({len(issues)} module README(s)):")
        for issue in issues:
            print(f"  {issue}")
        print("\nThe first `##` section of a module README must be one of:")
        for accepted in ACCEPTED:
            print(f"  ## {accepted}")
        print(
            "\nA table of contents is not an entry point: name the single page to open next.\n"
            "Adding a language means adding its heading to ACCEPTED in this file."
        )
        return 1
    print(f"entry points: {len(readmes)} module README(s) open with one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
