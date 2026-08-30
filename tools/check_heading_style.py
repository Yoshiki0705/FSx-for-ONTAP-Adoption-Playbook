#!/usr/bin/env python3
"""Require Japanese section headings to be noun phrases.

A heading in a verb form, a question form, or a full predicate reads as a sentence fragment where a
Japanese reader expects a label. The rule and the conversion table are in
`docs/agent/documentation-design.md`; this file only enforces it.

What is deliberately NOT checked, and why each exclusion matters:

  H1  - the document title, which a separate convention requires to be a one-line claim. The same
        string is correct as a title and wrong as a section heading, so checking H1 would demand
        the opposite of the title rule.
  Fenced blocks - a `#` line inside a fence is a shell comment. One article surveyed while writing
        this rule had twelve of them, and a detector without fence tracking rewrites code.
  English headings - `Deleting a volume` and `How to choose` are both correct.
  Table cells, list items, prose - only a line that IS a heading is a heading.

Three genres are exempt because the heading is deliberately not a label: chronological narrative,
advice whose imperative mood is the content, and a stated goal. A mechanical check cannot tell those
from a verb-form label, so they need the escape hatch:

    ## 15:29 パスポートが無い事に気付く   <!-- allow:heading-style -->

Use it sparingly. Each marker is a claim that the heading is narrative rather than a label, and a
reviewer should be able to see why from the surrounding text.

Run:  python3 tools/check_heading_style.py [--path DIR]
      python3 tools/check_heading_style.py --selftest
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from frontmatter import IGNORED_DIRS

HEADING = re.compile(r"^(#{2,6})\s+(.*?)\s*$")
FENCE = re.compile(r"^\s*(?:```|~~~)")
ALLOW = re.compile(r"<!--\s*allow:heading-style\s*-->")
JAPANESE = re.compile(r"[ぁ-んァ-ヶ一-龠]")

# Verb (dictionary form), polite predicate, and question endings. The character class is hiragana
# only on purpose: it is the う-row, which is where a Japanese verb ends. Katakana `ク` in `リスク`
# and `グ` in `ログ` must not match, and they do not.
# `ない` is listed separately from the character class rather than folded into a blanket `い$`:
# a plain negative predicate (`…できない`) is a sentence, while `問い` and `扱い` are nouns that also
# end in い. Without this entry the checker passes a whole class of predicate headings, which it did
# on the first run.
# The character class is exactly the う-row, which is where a Japanese verb's dictionary form ends.
# Two boundaries were wrong on the first draft and are worth keeping visible:
#
#   `れ` is え-row, not う-row, so no dictionary-form verb ends in it. A bare `れ` ending is a
#   nominalized 連用形 — `流れ`, `崩れ`, `遅れ`, `ずれ` are all nouns. Including it flagged an
#   open-ended class of nouns, and no allowlist could have closed that set.
#
#   `ない` is listed by name rather than as a blanket `い$`, because a plain negative predicate
#   (`…できない`) is a sentence while `問い` and `扱い` are nouns. Omitting it passed twelve
#   predicate headings on the first run.
VERBAL = re.compile(
    r"(?:ます|ません|ました|でした|です|ください|でしょうか|のか|か|ない|[うくぐすずつぬふぶむる])$"
)

# Nouns whose last character falls inside the VERBAL pattern. Only the い group needs listing now
# that れ is out of the class. Kept short on purpose: a long allowlist is how a checker stops
# catching things.
NOUN_TAIL = re.compile(
    r"(?:問い|扱い|こと|もの|ちがい|違い|使い|作り|やり方|考え方|選び方)$"
)


def violations(text: str) -> list[tuple[int, str, str]]:
    """Return (line number, hashes, heading text) for each heading that is not a noun phrase."""
    found: list[tuple[int, str, str]] = []
    in_fence = False
    for number, line in enumerate(text.split("\n"), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or ALLOW.search(line):
            continue
        match = HEADING.match(line)
        if not match:
            continue
        heading = ALLOW.sub("", match.group(2)).strip()
        if not JAPANESE.search(heading):
            continue
        if NOUN_TAIL.search(heading):
            continue
        if VERBAL.search(heading):
            found.append((number, match.group(1), heading))
    return found


def markdown_files(base: Path) -> list[Path]:
    return sorted(
        path
        for path in base.rglob("*.md")
        if not any(part in IGNORED_DIRS for part in path.parts)
    )


SELFTEST_CASES: list[tuple[str, bool, str]] = [
    ("## 自分の環境で確かめる", True, "verb, dictionary form"),
    ("## 構築後の検証を自動化する", True, "verb, dictionary form"),
    ("## なぜこの区分が必要か", True, "question"),
    ("## 責務をどう分けるか", True, "question"),
    ("## 記録されない読み取りがあります", True, "polite predicate"),
    ("## 監査は 2 つの面に分かれます", True, "polite predicate"),
    ("## 既定は「同一リージョン」です", True, "copula"),
    ("## クロスアカウントのアクセスは成立する", True, "plain predicate"),
    ("## ボリュームは AWS 側からしか消せない", True, "plain negative predicate"),
    ("## 特権削除は満了したファイルには使えない", True, "plain negative predicate"),
    ("## 自環境での確認手順", False, "noun phrase"),
    ("## この区分が必要な理由", False, "noun phrase"),
    ("## 記録されない読み取りの存在", False, "noun with assertion carried by suffix"),
    ("## このモジュールが扱う問い", False, "formal noun ending in い"),
    (
        "## 知見を 1 つ追加する流れ",
        False,
        "nominalized 連用形 in れ is a noun, not a verb",
    ),
    ("## 最小権限の崩れ", False, "same class as 流れ"),
    ("## 実測の遅れ", False, "same class as 流れ"),
    ("## 権限の扱い", False, "noun ending in い"),
    ("## よくある誤解", False, "noun"),
    ("## 参照した一次情報", False, "noun"),
    ("## まとめ", False, "noun"),
    ("## 判断フロー", False, "katakana noun"),
    ("## ログの保存先", False, "katakana グ must not read as a verb ending"),
    ("## リスクの一覧", False, "katakana ク must not read as a verb ending"),
    ("## Deleting a volume", False, "English"),
    ("## How to choose", False, "English question, still English"),
    ("# タイトルは主張文で書く", False, "H1 is exempt"),
    (
        "## 15:29 パスポートが無い事に気付く <!-- allow:heading-style -->",
        False,
        "marker",
    ),
]


def selftest() -> int:
    """Prove both directions. A checker that only ever passes is indistinguishable from no checker."""
    failures = 0
    for line, should_flag, why in SELFTEST_CASES:
        flagged = bool(violations(line))
        if flagged != should_flag:
            verb = "flagged" if flagged else "allowed"
            want = "flag" if should_flag else "allow"
            print(
                f"selftest FAIL ({why}): {verb} but expected to {want}: {line}",
                file=sys.stderr,
            )
            failures += 1

    fenced = "```bash\n# コピー元で実行しておく\n```\n"
    if violations(fenced):
        print(
            "selftest FAIL: a `#` line inside a fence was treated as a heading",
            file=sys.stderr,
        )
        failures += 1

    if failures:
        print(f"selftest: {failures} case(s) failed", file=sys.stderr)
        return 1
    print(f"selftest: {len(SELFTEST_CASES) + 1} case(s) passed (flag, allow, fence)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="", help="limit the scan to this directory")
    parser.add_argument(
        "--selftest", action="store_true", help="check the checker, then exit"
    )
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    base = ROOT / args.path if args.path else ROOT
    total = 0
    files = 0
    for path in markdown_files(base):
        hits = violations(path.read_text(encoding="utf-8"))
        if not hits:
            continue
        files += 1
        print(f"\n{path.relative_to(ROOT)}")
        for number, hashes, heading in hits:
            print(f"  L{number:>4} {hashes} {heading}")
        total += len(hits)

    if total:
        print(
            f"\nheading style: {total} heading(s) in {files} file(s) are not noun phrases.\n"
            "Nominalize them, carrying any assertion with a suffix (〜の存在 / 〜の不成立 / 〜の必要)\n"
            "rather than dropping it. Genuine narrative headings take "
            "<!-- allow:heading-style -->.\n"
            "Rule and conversion table: docs/agent/documentation-design.md",
            file=sys.stderr,
        )
        return 1

    print("heading style: all Japanese section headings are noun phrases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
