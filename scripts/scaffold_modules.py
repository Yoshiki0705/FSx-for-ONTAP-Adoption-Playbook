#!/usr/bin/env python3
"""One-time scaffold for playbook and domain module hubs.

Generating both languages from one data table guarantees Tier 2 parity by construction, which
is the property `tools/check_i18n_parity.py` verifies afterwards. Re-running is safe: existing
files are skipped unless --force is passed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (group, dir, ja_title, en_title, ja_lead, en_lead, [(ja_question, en_question)])
MODULES = [
    (
        "playbooks",
        "01-assess",
        "Playbook 01 — 評価 (Assess)",
        "Playbook 01 — Assess",
        (
            "移行の前に、現行 NAS に何があり、何が制約になるかを把握します。ここでの見落としが、"
            "後続フェーズのやり直しコストに直結します。"
        ),
        (
            "Before migrating, establish what exists on the current NAS and what will constrain the "
            "move. Gaps here translate directly into rework cost in later phases."
        ),
        [
            (
                "容量・ファイル数・ディレクトリ構造をどう棚卸しするか",
                "How to inventory capacity, file counts, and directory structure",
            ),
            (
                "どのプロトコルが実際に使われているか",
                "Which protocols are actually in use",
            ),
            (
                "権限・ACL・ID マッピングの現状はどうなっているか",
                "The current state of permissions, ACLs, and ID mapping",
            ),
            (
                "移行のブロッカーになりうる機能依存は何か",
                "Which feature dependencies could block the migration",
            ),
            (
                "性能要件のベースラインをどう測るか",
                "How to measure a baseline for performance requirements",
            ),
        ],
    ),
    (
        "playbooks",
        "02-design",
        "Playbook 02 — 設計 (Design)",
        "Playbook 02 — Design",
        (
            "評価結果をもとに、移行先の構成を決めます。容量とスループットは後から変更できますが、"
            "一部の選択（セキュリティスタイル、SnapLock 有効化など）は不可逆です。"
        ),
        (
            "Turn assessment output into a target configuration. Capacity and throughput can be "
            "changed later, but some choices (security style, SnapLock enablement) are irreversible."
        ),
        [
            (
                "ファイルシステムと SVM をどう分割するか",
                "How to divide file systems and SVMs",
            ),
            (
                "容量とスループットをどう見積もるか",
                "How to size capacity and throughput",
            ),
            (
                "ボリュームのセキュリティスタイルをどう選ぶか",
                "How to choose volume security style",
            ),
            (
                "マルチ AZ とシングル AZ をどう判断するか",
                "How to decide between Multi-AZ and Single-AZ",
            ),
            (
                "不可逆な設定はどれで、いつ決める必要があるか",
                "Which settings are irreversible, and when they must be decided",
            ),
        ],
    ),
    (
        "playbooks",
        "03-migrate",
        "Playbook 03 — 移行 (Migrate)",
        "Playbook 03 — Migrate",
        (
            "移行方式の選択、切り替え手順、そして戻す手順を扱います。ロールバック手順のない移行計画は"
            "計画として未完成です。"
        ),
        (
            "Covers method selection, cutover, and rollback. A migration plan without a rollback "
            "procedure is an incomplete plan."
        ),
        [
            (
                "どの移行方式を選ぶか（SnapMirror / DataSync / ホスト側コピー）",
                "Which method to choose (SnapMirror / DataSync / host-side copy)",
            ),
            (
                "ACL を保持したまま移行するには何が必要か",
                "What is required to migrate while preserving ACLs",
            ),
            (
                "初期同期と差分同期をどう計画するか",
                "How to plan initial and incremental sync",
            ),
            (
                "切り替え時のダウンタイムをどう最小化するか",
                "How to minimize cutover downtime",
            ),
            (
                "どの時点まで、どうやって戻せるか",
                "Up to what point, and how, you can roll back",
            ),
        ],
    ),
    (
        "playbooks",
        "04-build",
        "Playbook 04 — 構築 (Build)",
        "Playbook 04 — Build",
        "手作業で作った環境は再現できません。IaC と自動化で、構築を検証可能・再現可能にします。",
        (
            "A hand-built environment cannot be reproduced. Infrastructure as code and automation make "
            "the build verifiable and repeatable."
        ),
        [
            (
                "IaC で何を管理し、何を管理しないか",
                "What to manage in IaC and what to leave out",
            ),
            (
                "Active Directory 連携をどう自動化するか",
                "How to automate Active Directory integration",
            ),
            ("シークレットをどう扱うか", "How to handle secrets"),
            (
                "構築後の検証をどう自動化するか",
                "How to automate post-build verification",
            ),
            (
                "環境の複製（開発・検証）をどう作るか",
                "How to clone environments for dev and test",
            ),
        ],
    ),
    (
        "playbooks",
        "05-operate",
        "Playbook 05 — 運用 (Operate)",
        "Playbook 05 — Operate",
        (
            "監視・容量管理・障害対応・変更管理を扱います。「動いている」ことの確認と「壊れたときに"
            "どうするか」の両方が必要です。"
        ),
        (
            "Covers monitoring, capacity management, incident response, and change management. You need "
            "both confirmation that things work and a plan for when they break."
        ),
        [
            (
                "何を監視し、どこに閾値を置くか",
                "What to monitor and where to set thresholds",
            ),
            (
                "容量の枯渇をどう予兆検知するか",
                "How to detect impending capacity exhaustion",
            ),
            (
                "性能劣化の切り分け手順はどうなるか",
                "How to triage performance degradation",
            ),
            (
                "ONTAP のバージョン更新をどう扱うか",
                "How to handle ONTAP version updates",
            ),
            (
                "インシデント時の初動をどう定義するか",
                "How to define first-response actions during an incident",
            ),
        ],
    ),
    (
        "playbooks",
        "06-optimize",
        "Playbook 06 — 最適化 (Optimize)",
        "Playbook 06 — Optimize",
        "定常運用に入ってからの性能とコストの詰めを扱います。最適化は測定なしには始められません。",
        (
            "Performance and cost tuning once you are in steady state. Optimization cannot begin "
            "without measurement."
        ),
        [
            (
                "どこがボトルネックかをどう特定するか",
                "How to identify where the bottleneck is",
            ),
            ("ティアリングをどう設定するか", "How to configure tiering"),
            (
                "ストレージ効率（重複排除・圧縮）の効果をどう測るか",
                "How to measure storage efficiency gains",
            ),
            (
                "スループット設定を上げる前に確認すべきことは何か",
                "What to check before raising the throughput setting",
            ),
            (
                "コスト削減と可用性のトレードオフをどう置くか",
                "How to position the cost-versus-availability trade-off",
            ),
        ],
    ),
    (
        "domains",
        "data-protection",
        "Domain — データ保護 (Data Protection)",
        "Domain — Data Protection",
        (
            "Snapshot、SnapMirror、SnapLock、バックアップ、ランサムウェア対策を扱います。"
            "「保護している」ことと「復旧できる」ことは別の主張です。"
        ),
        (
            "Covers Snapshot, SnapMirror, SnapLock, backup, and ransomware readiness. "
            '"Protected" and "recoverable" are two different claims.'
        ),
        [
            ("Snapshot ポリシーをどう設計するか", "How to design a Snapshot policy"),
            (
                "SnapMirror で何が守られ、何が守られないか",
                "What SnapMirror protects and what it does not",
            ),
            (
                "WORM / SnapLock をどう使い、何が不可逆か",
                "How to use WORM / SnapLock and what is irreversible",
            ),
            ("復旧手順をどう検証するか", "How to verify the recovery procedure"),
            (
                "ランサムウェア対策として何が有効か",
                "What is effective as ransomware readiness",
            ),
        ],
    ),
    (
        "domains",
        "data-utilization",
        "Domain — データ活用 (Data Utilization)",
        "Domain — Data Utilization",
        "NAS 上のデータを、コピーを増やさずに分析・AI・アプリケーションから使うための知見です。",
        (
            "How to use NAS-resident data from analytics, AI, and applications without multiplying "
            "copies of it."
        ),
        [
            (
                "S3 API 経由のアクセスで何ができ、何ができないか",
                "What is and is not possible over the S3 API",
            ),
            ("分析基盤にどう接続するか", "How to connect an analytics platform"),
            ("AI / RAG で権限をどう扱うか", "How to handle permissions in AI / RAG"),
            (
                "データコピーを増やさない設計とは",
                "What a copy-minimizing design looks like",
            ),
            (
                "読み取り加速をどこで効かせるか",
                "Where read acceleration is worth applying",
            ),
        ],
    ),
    (
        "domains",
        "security-governance",
        "Domain — セキュリティ・ガバナンス (Security & Governance)",
        "Domain — Security & Governance",
        (
            "暗号化、監査、権限設計、規制ワークロードでの考慮事項を扱います。ここに書かれているのは"
            "設計上の考慮事項であり、法務・コンプライアンス上の判断ではありません。"
        ),
        (
            "Covers encryption, audit, permission design, and considerations for regulated workloads. "
            "What is written here are design considerations, not legal or compliance judgments."
        ),
        [
            (
                "暗号化の選択肢とその境界はどこか",
                "The encryption options and where their boundaries lie",
            ),
            ("誰が何をしたかをどう記録するか", "How to record who did what"),
            (
                "権限設計をどう最小権限に寄せるか",
                "How to move permission design toward least privilege",
            ),
            (
                "規制ワークロードで問われる論点は何か",
                "Which points come up for regulated workloads",
            ),
            (
                "OT / IT 境界をまたぐ場合の考慮事項は何か",
                "Considerations when crossing the OT / IT boundary",
            ),
        ],
    ),
    (
        "domains",
        "performance",
        "Domain — 性能 (Performance)",
        "Domain — Performance",
        (
            "スループット設計、レイテンシ、キャッシュ、共有帯域の挙動を扱います。数値は必ず"
            "測定環境とセットで読んでください。"
        ),
        (
            "Covers throughput design, latency, caching, and shared-bandwidth behavior. Always read a "
            "number together with the environment it was measured in."
        ),
        [
            (
                "スループットはどこで決まり、どこで共有されるか",
                "Where throughput is determined and where it is shared",
            ),
            (
                "プロトコル間で帯域をどう分け合うか",
                "How bandwidth is shared across protocols",
            ),
            (
                "レイテンシのテール（p99）をどう見るか",
                "How to look at latency tails (p99)",
            ),
            (
                "キャッシュが効くワークロードの条件は何か",
                "What makes a workload benefit from caching",
            ),
            (
                "ベンチマークをどう設計すれば再現できるか",
                "How to design a benchmark that reproduces",
            ),
        ],
    ),
    (
        "domains",
        "cost",
        "Domain — コスト (Cost)",
        "Domain — Cost",
        (
            "容量、ティアリング、そして見積もりと実測の差分を扱います。見積もりが外れる原因は"
            "多くの場合、単価ではなく前提条件です。"
        ),
        (
            "Covers capacity, tiering, and the gap between estimates and measurements. Estimates "
            "usually miss because of assumptions, not unit prices."
        ),
        [
            ("何が課金対象で、何が課金されないか", "What is billed and what is not"),
            (
                "ティアリングでどこまで下がるか",
                "How far tiering actually brings cost down",
            ),
            (
                "見積もりが外れる典型的な前提は何か",
                "Which assumptions typically break an estimate",
            ),
            (
                "Snapshot が容量に与える影響をどう見るか",
                "How to account for Snapshot capacity impact",
            ),
            (
                "コストと可用性・性能のトレードオフをどう提示するか",
                "How to present the cost-availability-performance trade-off",
            ),
        ],
    ),
    (
        "domains",
        "multiprotocol-identity",
        "Domain — マルチプロトコル・ID (Multiprotocol & Identity)",
        "Domain — Multiprotocol & Identity",
        (
            "NFS と SMB の共存、Active Directory 連携、ID マッピングを扱います。"
            "多くの「権限がおかしい」問題は、ID マッピングの理解不足に起因します。"
        ),
        (
            "Covers NFS and SMB coexistence, Active Directory integration, and ID mapping. Most "
            '"permissions are wrong" problems trace back to ID mapping.'
        ),
        [
            (
                "セキュリティスタイルが権限評価をどう変えるか",
                "How security style changes permission evaluation",
            ),
            (
                "Active Directory 連携で何が前提になるか",
                "What Active Directory integration presupposes",
            ),
            (
                "win-unix / unix-win マッピングはいつ参照されるか",
                "When win-unix / unix-win mapping is consulted",
            ),
            (
                "同一データを NFS と SMB で共有する条件は何か",
                "What it takes to share the same data over NFS and SMB",
            ),
            (
                "AD が到達不能になると何が壊れるか",
                "What breaks when AD becomes unreachable",
            ),
        ],
    ),
]

JA = """# {title}

<!-- lang-switcher:start -->
<!-- lang-switcher:end -->

---

{lead}

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
{questions}

---

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`notes/`](notes/) | 知見の最小単位。1 ファイル = 1 論点。frontmatter に `evidence` 区分を持ちます |
| [`checklists/`](checklists/) | 現場で使うチェックリスト |

---

## 読み方

各ノートの frontmatter にある `evidence` を必ず確認してください。

| 区分 | 意味 |
|---|---|
| `verified` | 記載環境で著者が再現済み。`verified_on` に検証日 |
| `documented` | ベンダー / AWS 公式ドキュメントに記載あり。`source` に出典 |
| `field-observation` | 現場で一度観測。再現確認は未実施。一般化しないこと |
| `hypothesis` | 未検証の推論 |

判断基準の詳細は [知見の分類ポリシー](../../evidence-policy.md) を参照してください。

---

## 関連

{related_ja}
- [ナビゲーションガイド](../../navigation.md)
- [用語集](../../reference/glossary/)

---

<!-- lang-switcher:start -->
<!-- lang-switcher:end -->
"""

EN = """# {title}

<!-- lang-switcher:start -->
<!-- lang-switcher:end -->

---

{lead}

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
{questions}

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](checklists/) | Checklists for field use |

---

## How to read this

Always check the `evidence` field in each note's frontmatter.

| Tier | Meaning |
|---|---|
| `verified` | Reproduced by the author in the stated environment. `verified_on` gives the date |
| `documented` | Stated in vendor / AWS documentation. `source` gives the reference |
| `field-observation` | Observed once in the field, not reproduced. Do not generalize |
| `hypothesis` | Reasoned expectation, untested |

See the [Evidence Policy](../../evidence-policy.md) for the full criteria.

---

## Related

{related_en}
- [Navigation Guide](../../navigation.md)
- [Glossary](../../../ja/reference/glossary/)

---

<!-- lang-switcher:start -->
<!-- lang-switcher:end -->
"""

# The two-axis navigation lives inside a <details><summary>, which GitHub does not turn into a
# linkable anchor - so these point at the navigation guide, which has real headings.
RELATED_JA = {
    "playbooks": "- [テーマ軸で探す](../../navigation.md#テーマ軸--domains)\n"
    "- [移行方式 決定ツリー](../../reference/decision-trees/migration-method.md)",
    "domains": "- [ライフサイクル軸で探す](../../navigation.md#ライフサイクル軸--playbooks)\n"
    "- [比較マトリクス](../../reference/comparison/)",
}
# reference/ is not split per language yet, so the English module hubs point into docs/ja/.
RELATED_EN = {
    "playbooks": "- [Browse by topic](../../navigation.md#topic-axis--domains)\n"
    "- [Migration Method Decision Tree](../../../ja/reference/decision-trees/migration-method.md)",
    "domains": "- [Browse by lifecycle](../../navigation.md#lifecycle-axis--playbooks)\n"
    "- [Comparison Matrices](../../../ja/reference/comparison/)",
}


def rows(questions: list[tuple[str, str]], index: int) -> str:
    return "\n".join(
        f"| {number} | {question[index]} | _未追加_ |"
        if index == 0
        else f"| {number} | {question[index]} | _not yet added_ |"
        for number, question in enumerate(questions, start=1)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="overwrite existing README files"
    )
    args = parser.parse_args()

    written = 0
    for group, directory, ja_title, en_title, ja_lead, en_lead, questions in MODULES:
        # A document's language is its directory. notes/ and checklists/ are Tier 3 and exist only
        # in Japanese, so they are created once rather than per language.
        ja_module = ROOT / "docs" / "ja" / group / directory
        (ja_module / "notes").mkdir(parents=True, exist_ok=True)
        (ja_module / "checklists").mkdir(parents=True, exist_ok=True)

        for lang, template, title, lead, related, index in (
            ("ja", JA, ja_title, ja_lead, RELATED_JA[group], 0),
            ("en", EN, en_title, en_lead, RELATED_EN[group], 1),
        ):
            target = ROOT / "docs" / lang / group / directory / "README.md"
            if target.exists() and not args.force:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                template.format(
                    title=title,
                    lead=lead,
                    questions=rows(questions, index),
                    related_ja=related,
                    related_en=related,
                ),
                encoding="utf-8",
            )
            written += 1
            print(f"wrote {target.relative_to(ROOT)}")

    print(f"\n{written} file(s) written")
    if written:
        # The templates ship empty switcher markers on purpose: which languages a switcher lists
        # depends on what exists on disk, which is only knowable after the files are written.
        print("next: make switcher-write   (fills the language switcher blocks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
