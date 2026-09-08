"""A published claim must not rest on a vendor's support reply.

AWS treats replies from AWS Support as its confidential information under the customer agreement,
and asked in a 2026-09 reply that they not be published. NetApp, Databricks and Snowflake carry
comparable terms, so the rule is vendor-neutral.

This inverts a permission that this repository used to grant deliberately. Several notes were
sourced to "AWS Support confirmed X (date)" on the reasoning that attribution records where a fact
came from rather than sending the reader to a support desk. That reasoning was right about referrals
and wrong about publication: attribution makes the published claim rest on a source the reader
cannot consult and the author is not free to quote.

A reply may still change what you conclude. What it cannot do is appear as the reason. After a reply
one of three things has to happen before publishing: find the public page that says it, observe it
yourself, or leave the question open and say so.

**Paraphrasing is not a way around it**, because what is confidential is the content and not the
wording. `BLOCKED` therefore carries the same finding in several shapes, including ones with no
vendor name adjacent to the verb.

`PERMITTED` is checked with the same weight. Two shapes matter most there. Recording *that* a
question was asked, and when, is the ledger's own field and must stay publishable, otherwise the
rule removes the only honest way to say "asked, no answer yet". And "サポート対象" / "サポートされ
ません" is about whether a product supports something, which has nothing to do with a support desk;
sweeping it up would make the rule intolerable in a storage repository.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from audit_public_output import audit_line

CATEGORY = "support-attribution"

# The first three were published in this repository under the old permission.
BLOCKED = (
    "AWS Support confirmed that neither event is visible to customers by design (2026-09-03).",
    "AWS Support reproduced this on the same version and identified the mechanism (2026-09-02).",
    "**この節は AWS Support が確認した内容を報告しています。** 当環境では再現していません。",
    "AWS サポートの回答によれば、現在の指定を表すフィールドは `AuditLogVolume` です。",
    "**仕様であるとの回答を得ました。**",
    "サポート回答: ONTAP の S3 機能と S3 AP は同じ SVM では併存しません。",
    "この点は AWS サポートに確認済みで、削除以外の回避策はありません。",
    "NetApp サポートの見解では、9.15.1 以降でも同じ挙動になります。",
    "Databricks Support confirmed S3 Access Points are not a supported storage location.",
    "Snowflake サポートの案内に沿って `REFRESH_MODE = FULL` を指定しています。",
    "Per AWS Support, the field is populated only for Lustre.",
    "According to NetApp Support this cannot be cleared without a revert.",
    "サポート側で同じ事象を再現し、`launchStatus` では判定できないと説明がありました。",
    # Missed by the first version: 確認 was not in the reply-noun list. Found in a sibling
    # repository, not by re-reading the pattern.
    "包括的な互換性マトリクス、既知の制約（2026年5月 AWS サポート確認済み）については以下を参照:",
    # The English half was narrower than the Japanese half: it only saw the desk as the subject
    # of a verb. These are what four sibling repositories actually wrote.
    "known constraints (confirmed with AWS Support, May 2026), refer to:",
    "The number entered this documentation from the May 2026 AWS Support discussion.",
    "## AWS Support findings (2026-08)",
    "### AWS Support Confirmation (August 2026)",
    "## What AWS Support answered (from a case in 2026-08)",
    '"source": "Databricks Support response",',
    "## Alternative Paths Identified by Snowflake Support",
    "access_point field added per Databricks support recommendation",
    "Added 2026-08-12 after AWS Support escalated the charset behaviour",
    "AWS Support considers this ONTAP-side processing rather than specific to FSx for ONTAP.",
    "AWS Support declined to state it as specified behaviour.",
)

# Publishable: the act of asking, the filing, product-support wording, portal names.
PERMITTED = (
    "この挙動は AWS サポートに確認中で、回答が来るまでは open として扱います。",
    "AWS サポートに確認を出しました（2026-09-04 起票）。",
    "A documentation request has been filed with the vendor (2026-09-03).",
    "機能改善要望として起票済みです。ケース番号は `.private/` で追跡します。",
    "**7 組を超えるファイルシステムではサポートされません。**",
    "`If-None-Match` は非サポートで、HTTP 501 を返します。",
    "FlexCache は 9.13.1 以降でサポート対象です。",
    "NetApp Support のログインが必要で、本ノート作成時点では参照できていません。",
    "| `documented` | ベンダー / AWS 公式ドキュメントに記載あり。`source` に出典 |",
    "公開ドキュメントの [DescribeFileSystems](https://example.invalid/) に Lustre 用と明記されています。",
    "当環境で 2026-07-22 に ap-northeast-1 へデプロイして動作しました。",
    "LUN は igroup にマップします。",
    # Flagged by the first version, which made the vendor name optional in the subject
    # alternative, so any "サポートが...確認" matched. This sentence is about whether a feature
    # works, and a rule that sweeps it up is a rule that gets switched off.
    "自社の特定の環境に対して FSx for ONTAP S3 AP のサポートが実際に機能することを確認できます。",
    # Drafting an inquiry, planning one, and naming a portal all stay publishable. Widening the
    # English half made these the near misses, so they are pinned.
    "Wording for an AWS Support case about the monitoring coverage.",
    "What to confirm with AWS Support",
    "## AWS Support Submission Text",
    "## NetApp Support Diagnostic Bundle",
    "| NetApp アカウント | **必要**（NSS: NetApp Support Site アカウント） |",
    "aws support describe-services and record it",
)


def categories(line: str) -> set[str]:
    return {category for category, _ in audit_line(line)}


class SupportAttributionRule(unittest.TestCase):
    def test_it_blocks_a_reply_used_as_the_basis(self) -> None:
        for line in BLOCKED:
            with self.subTest(line=line):
                self.assertIn(
                    CATEGORY,
                    categories(line),
                    f"a support reply was left standing as the published basis: {line!r}",
                )

    def test_it_leaves_the_act_of_asking_alone(self) -> None:
        """Otherwise the rule removes the only honest way to say "asked, no answer yet"."""
        for line in PERMITTED:
            with self.subTest(line=line):
                self.assertNotIn(
                    CATEGORY,
                    categories(line),
                    f"publishable prose was flagged as attribution: {line!r}",
                )

    def test_the_line_marker_suppresses_it(self) -> None:
        """A file whose job is to define the rule has to be able to quote what it forbids."""
        line = BLOCKED[0] + "  <!-- allow:support-attribution -->"
        self.assertNotIn(CATEGORY, categories(line))

    def test_an_unrelated_line_reports_nothing(self) -> None:
        self.assertEqual(categories("LUN は igroup にマップします。"), set())


if __name__ == "__main__":
    unittest.main()
