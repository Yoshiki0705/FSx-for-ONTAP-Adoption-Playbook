# Domain — データ保護 (Data Protection)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/data-protection/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

Snapshot、SnapMirror、SnapLock、バックアップ、ランサムウェア対策を扱います。「保護している」ことと「復旧できる」ことは別の主張です。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | Snapshot ポリシーをどう設計するか | [上限と保持期間から逆算する](notes/snapshots-are-not-a-recovery-plan.md#上限と保持期間) |
| 2 | SnapMirror で何が守られ、何が守られないか | [Snapshot があることと復旧できることは別](notes/snapshots-are-not-a-recovery-plan.md#何から守れるのか) |
| 3 | WORM / SnapLock をどう使い、何が不可逆か | [SnapLock は有効化とロックが別](notes/snaplock-and-layered-ransomware-readiness.md) |
| 4 | 復旧手順をどう検証するか | [復元を実際に試す手順](notes/snapshots-are-not-a-recovery-plan.md#自分の環境で確かめる) |
| 5 | ランサムウェア対策として何が有効か | [ランサムウェア対策は層で考える](notes/snaplock-and-layered-ransomware-readiness.md#ランサムウェア対策は層で考える) |
| 6 | 別リージョン・別アカウントへどう退避するか | [バックアップコピーは復元するまでファイルシステムを持たない](notes/backup-copies-across-regions-and-accounts.md) |
| 7 | バックアップコピーと SnapMirror をどう選び分けるか | [SnapMirror との選び分け](notes/backup-copies-across-regions-and-accounts.md#snapmirror-との選び分け) |
| 8 | Snapshot をデータセットの「版」として使えるか | [版を Snapshot に載せるときの 3 つの落とし穴](../data-utilization/notes/dataset-versions-and-experiment-branches.md#版を-snapshot-に載せるときの-3-つの落とし穴) |

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

- [ライフサイクル軸で探す](../../navigation.md#ライフサイクル軸--playbooks)
- [比較マトリクス](../../reference/comparison/)
- [ナビゲーションガイド](../../navigation.md)
- [用語集](../../reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/data-protection/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
