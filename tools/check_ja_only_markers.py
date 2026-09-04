#!/usr/bin/env python3
"""Require a `(日本語)` marker on every English link into a Japanese-only note or checklist.

`docs/agent/localization.md` states the promise this enforces: "A Japanese-only note is linked from
English with a `(日本語)` marker, so a missing translation is a labelled link rather than a broken
promise." Nothing enforced it, so the rule held in module READMEs and drifted everywhere else — an
English reader following a link from body prose landed in Japanese with no warning, and three
translations added in one afternoon introduced thirteen such links without any gate noticing.

What is deliberately NOT flagged, and why each exclusion matters:

  `reference/`   - its hubs are bilingual single files by design (`docs/agent/localization.md`), so the
                   Japanese and English prose share the same tables. A marker there would announce a
                   missing translation that is not missing. The exemption is structural rather than a
                   listed exclusion: the pattern below only covers `notes/` and `checklists/`. It
                   therefore also skips a Japanese-only *leaf* under `reference/`, which the hubs
                   argument does not justify. `switcher-check` is what reports a link left pointing at
                   a leaf that has since been translated, and widening this pattern to `reference/`
                   would put one rule behind two gates that then drift apart.
  Directory links - `notes/` and `checklists/` resolve to a listing, not to Japanese prose. The
                   localized directory is chosen by `sync_lang_switcher.py`; that is its concern.
  Switcher blocks - the generated `🌐 [日本語](…)` line names the language in the link text already.
  Links whose text already says 日本語 - the warning is present, just spelled differently.
  Anything under `docs/en/**` that resolves inside `docs/en/` - not a cross-language link at all.

The marker has to follow the closing parenthesis, because that is where a reader meets it:

    [Pre-production review](../../../../ja/playbooks/04-build/checklists/x.md) (日本語)

Run:  python3 tools/check_ja_only_markers.py [--path DIR]
      python3 tools/check_ja_only_markers.py --selftest
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A link into Japanese prose that has its own per-file translation status.
JA_PROSE = re.compile(
    r"ja/(?:playbooks|domains|case-studies)/[^)]*?/(?:notes|checklists)/[^)/]+\.md"
)
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
MARKER = "(日本語)"


def offending_links(text: str) -> list[tuple[int, str]]:
    """Return (line number, link text) for each unmarked link into Japanese prose."""
    found: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), 1):
        if re.match(r"\s*(```|~~~)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # The switcher is generated and names the language in its link text.
        if "lang-switcher" in line or line.lstrip().startswith("🌐"):
            continue
        for match in LINK.finditer(line):
            label, href = match.group(1), match.group(2)
            if not JA_PROSE.search(href):
                continue
            if "日本語" in label:
                continue
            if line[match.end() :].lstrip().startswith(MARKER):
                continue
            found.append((number, label))
    return found


def check(base: Path) -> list[str]:
    issues: list[str] = []
    english = base / "en"
    if not english.is_dir():
        return issues
    for path in sorted(english.rglob("*.md")):
        for number, label in offending_links(path.read_text(encoding="utf-8")):
            rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
            issues.append(
                f"{rel}:{number}: link into a Japanese-only page without {MARKER}: [{label}]"
            )
    return issues


def selftest() -> int:
    unmarked = "See [ACL preservation](../../ja/playbooks/03-migrate/notes/preserving-acls.md) for it.\n"
    marked = "See [ACL preservation](../../ja/playbooks/03-migrate/notes/preserving-acls.md) (日本語).\n"
    reference = "See [Limits](../../ja/reference/limits/README.md) for the numbers.\n"
    directory = "See [`notes/`](../../ja/playbooks/03-migrate/notes/) for the rest.\n"
    switcher = "🌐 [日本語](../../ja/playbooks/03-migrate/notes/preserving-acls.md) | [English](x.md)\n"
    fenced = "```text\n[x](../../ja/domains/cost/notes/y.md)\n```\n"
    labelled = (
        "See [ACL preservation (日本語)](../../ja/domains/cost/notes/y.md) below.\n"
    )

    cases = [
        ("unmarked link is flagged", unmarked, 1),
        ("marked link is accepted", marked, 0),
        ("bilingual reference is not a missing translation", reference, 0),
        ("directory link is the switcher's concern", directory, 0),
        ("generated switcher names the language itself", switcher, 0),
        ("fenced example is not a link", fenced, 0),
        ("marker inside the link text is accepted", labelled, 0),
    ]
    failures = 0
    for name, body, expected in cases:
        actual = len(offending_links(body))
        status = "ok  " if actual == expected else "FAIL"
        if actual != expected:
            failures += 1
        print(f"  {status} {name} (expected {expected}, got {actual})")
    print("selftest: " + ("passed" if not failures else f"{failures} case(s) failed"))
    return 1 if failures else 0


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

    issues = check(Path(args.path))
    if issues:
        print(f"ja-only markers failed ({len(issues)} issue(s)):")
        for issue in issues:
            print(f"  {issue}")
        return 1
    print("ja-only markers: every English link into Japanese prose is labelled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
