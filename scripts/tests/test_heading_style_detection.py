"""The noun-phrase heading rule must fire on predicates and stay quiet on nouns.

Why this exists
---------------
Two boundaries in this detector were wrong on the first draft, in opposite
directions, and each one was found only by running it against the whole tree.

`れ` was in the verb-ending character class. It is え-row, not う-row, so no
dictionary-form verb ends in it — a bare `れ` ending is a nominalized 連用形, and
`流れ`, `崩れ`, `遅れ`, `ずれ` are all nouns. That flagged an open-ended class of
nouns, and no allowlist could have closed the set. An over-eager rule gets
switched off, which is the same outcome as no rule.

`ない` was missing. A plain negative predicate is a sentence, but it ends in い,
which the class deliberately excludes because `問い` and `扱い` are nouns. Listing
`ない` by name was the fix; without it the checker silently passed twelve
predicate headings.

So this asserts both directions, and the exclusions too: H1 is exempt because a
separate convention requires the title to be a one-line claim, a `#` line inside
a fence is a shell comment rather than a heading, and English headings are not
in scope at all.

`SELFTEST_CASES` inside the tool covers the same ground so that `make headings`
can prove the checker still flags before it reports a clean tree. This file is
what fails in CI when someone widens the pattern without thinking about the
noun classes it would swallow.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from check_heading_style import SELFTEST_CASES, violations

# (heading line, expected to be flagged, why it is here)
CASES: list[tuple[str, bool, str]] = [
    # Verb, dictionary form.
    ("## 自分の環境で確かめる", True, "う-row verb ending"),
    ("## 構築後の検証を自動化する", True, "する"),
    ("### 3 深い階層と特殊なケースを選ぶ", True, "ぶ"),
    ("## 仕様・上限を確認する", True, "する on a numbered step"),
    # Question.
    ("## なぜこの区分が必要か", True, "なぜ〜か"),
    ("## 責務をどう分けるか", True, "どう〜か"),
    ("## 何が起きたのか", True, "のか"),
    # Predicate.
    ("## 記録されない読み取りがあります", True, "polite predicate"),
    ("## 監査は 2 つの面に分かれました", True, "past polite"),
    ("## 既定は「同一リージョン」です", True, "copula"),
    ("## クロスアカウントのアクセスは成立する", True, "plain predicate"),
    # Plain negative. The class this detector missed entirely on the first run.
    ("## ボリュームは AWS 側からしか消せない", True, "plain negative"),
    ("## FPolicy はこの経路を見ていない", True, "plain negative"),
    ("## アクセスポイントのエイリアスは一覧に出ない", True, "plain negative"),
    # Nouns. The class an over-eager version swallows.
    ("## 自環境での確認手順", False, "noun"),
    ("## この区分が必要な理由", False, "noun"),
    ("## 記録されない読み取りの存在", False, "assertion carried by a suffix"),
    ("## AWS API での解除の不可", False, "assertion carried by a suffix"),
    ("## 知見を 1 つ追加する流れ", False, "nominalized 連用形 in れ"),
    ("## `SvmAdminPassword` の省略による最小権限の崩れ", False, "same class as 流れ"),
    ("## 実測の遅れ", False, "same class as 流れ"),
    ("## このモジュールが扱う問い", False, "formal noun in い"),
    ("## 止められるものと止められないもの", False, "formal noun もの"),
    ("## よくある誤解", False, "noun"),
    ("## 判断フロー", False, "katakana noun"),
    ("## ログの保存先", False, "katakana グ is not a verb ending"),
    ("## リスクの一覧", False, "katakana ク is not a verb ending"),
    # Out of scope.
    ("## Deleting a volume", False, "English"),
    ("## How to choose", False, "English question is still English"),
    (
        "# 課金は「確保した量」と「使った量」に分かれる",
        False,
        "H1 is the title, exempt",
    ),
    (
        "## 15:29 パスポートが無い事に気付く <!-- allow:heading-style -->",
        False,
        "narrative, marked",
    ),
]


class HeadingStyleDetection(unittest.TestCase):
    def test_both_directions(self) -> None:
        for line, should_flag, why in CASES:
            with self.subTest(why=why, line=line):
                self.assertEqual(bool(violations(line)), should_flag)

    def test_a_hash_line_inside_a_fence_is_a_shell_comment(self) -> None:
        """Twelve of these existed in one article surveyed while writing the rule."""
        fenced = "```bash\n# コピー元で実行しておく\n# バックアップを取る\n```\n"
        self.assertEqual(violations(fenced), [])

    def test_fence_state_recovers_after_the_block_closes(self) -> None:
        text = "```bash\n# 実行しておく\n```\n\n## 設定を確認する\n"
        self.assertEqual(len(violations(text)), 1)

    def test_the_rule_covers_h2_through_h6(self) -> None:
        for depth in range(2, 7):
            with self.subTest(depth=depth):
                self.assertEqual(len(violations(f"{'#' * depth} 設定を確認する")), 1)

    def test_negative_endings_are_a_literal_and_not_a_blanket_i(self) -> None:
        """This is the load-bearing decision, and there is no allowlist behind it.

        An earlier draft carried a noun allowlist. Once `れ` left the character class it stopped
        firing entirely, because every word in it already failed to match — it protected nothing
        while looking like protection, so it was removed. What actually keeps `問い` and `扱い` clean
        is that `ない` is a literal rather than `い$`. Widening it would break an open class of
        nouns that no list could close, so assert the boundary directly.
        """
        from check_heading_style import VERBAL

        for noun in ("問い", "扱い", "違い", "使い", "気付き", "重み"):
            with self.subTest(noun=noun):
                self.assertIsNone(VERBAL.search(noun))
        for predicate in ("できない", "見ていない", "出ない"):
            with self.subTest(predicate=predicate):
                self.assertIsNotNone(VERBAL.search(predicate))

    def test_the_tools_selftest_asserts_both_directions(self) -> None:
        """A selftest with no negative cases would let an over-eager pattern through."""
        self.assertTrue(any(flag for _, flag, _ in SELFTEST_CASES))
        self.assertTrue(any(not flag for _, flag, _ in SELFTEST_CASES))

    def test_the_repository_is_clean(self) -> None:
        """The migration is only done when nothing is left to convert."""
        from check_heading_style import markdown_files

        offenders = {
            path.relative_to(ROOT).as_posix(): violations(
                path.read_text(encoding="utf-8")
            )
            for path in markdown_files(ROOT)
        }
        self.assertEqual({k: v for k, v in offenders.items() if v}, {})


if __name__ == "__main__":
    unittest.main()
