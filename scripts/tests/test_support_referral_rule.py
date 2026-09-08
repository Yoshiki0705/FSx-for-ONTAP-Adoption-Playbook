"""A published note must not send the reader to a vendor's support desk.

The rule exists because the sentences in `BLOCKED` were written into this repository and merged.
A note concluded that a FlexClone relationship blocking a volume deletion could not be cleared, and
offered "wait, or file with the vendor" as the remedy. The mechanism was ONTAP's volume recovery
queue -- documented, with a one-command fix -- and it was found only after a reviewer asked whether
the question had been researched at all.

So the incident had two halves. The unresearched claim of impossibility is a judgement and cannot be
regex-matched without flagging every legitimate "this cannot be changed after creation" in the tree;
that half lives in `docs/agent/pitfalls.md`. The support referral is the half a pattern can see, and
it is a reliable marker of the other, because the two arrive together.

**The allow direction matters as much here.** `PERMITTED` is checked with the same weight as
`BLOCKED`, because a rule that flags ordinary prose gets switched off wholesale. What belongs in
`PERMITTED` changed once, though: attribution to a case that happened used to be listed here, on the
reasoning that recording where a fact came from is not a referral. It is not -- it is a separate
failure, and it now has its own category. See `test_support_attribution_rule.py`.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from audit_public_output import audit_line

CATEGORY = "support-referral"

# Taken from what was actually published, plus the shapes a reader would reach for next.
BLOCKED = (
    "解消手段は背景処理を待つか、ベンダーに上げるかのどちらかでした。",
    "**AWS Support に問い合わせてください。**",
    "孤立したクローン関係レコードの削除は NetApp Support に相談する必要があります。",
    "解決しない場合はサポートに起票してください。",
    "If it persists, file a case with AWS Support.",
    "The only remaining route is to open a support ticket with NetApp.",
    "Contact AWS Support to have the record removed.",
    "この時点でサポートケースを開きます。",
)

# Not a referral. Attribution to a case moved to `test_support_attribution_rule.py`, so what is
# left here is prose that a loose pattern would sweep up.
PERMITTED = (
    "A documentation request has been filed with the vendor (2026-09-03).",
    "| `documented` | ベンダー / AWS 公式ドキュメントに記載あり。`source` に出典 |",
    "**7 組を超えるファイルシステムではサポートされません。**",
    "`Get-MSDSMSupportedHW` に載っていました。",
    "NetApp Support のログインが必要で、本ノート作成時点では参照できていません。",
    "この挙動は AWS サポートに確認中で、回答が来るまでは open として扱います。",
)


def categories(line: str) -> set[str]:
    return {category for category, _ in audit_line(line)}


class SupportReferralRule(unittest.TestCase):
    def test_it_blocks_what_was_actually_published(self) -> None:
        for line in BLOCKED:
            with self.subTest(line=line):
                self.assertIn(
                    CATEGORY,
                    categories(line),
                    f"a reader-facing support referral went unreported: {line!r}",
                )

    def test_it_leaves_attribution_alone(self) -> None:
        """Recording where a fact came from is not the same as sending the reader away."""
        for line in PERMITTED:
            with self.subTest(line=line):
                self.assertNotIn(
                    CATEGORY,
                    categories(line),
                    f"attribution or an unrelated phrase was flagged as a referral: {line!r}",
                )

    def test_the_line_marker_suppresses_it(self) -> None:
        """A genuine exception has to be declarable, or the rule gets switched off wholesale."""
        line = BLOCKED[1] + "  <!-- allow:support-referral -->"
        self.assertNotIn(CATEGORY, categories(line))

    def test_an_unrelated_line_reports_nothing(self) -> None:
        self.assertEqual(categories("LUN は igroup にマップします。"), set())


if __name__ == "__main__":
    unittest.main()
