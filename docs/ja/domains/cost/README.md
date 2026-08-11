# Domain — コスト (Cost)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/cost/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

容量、ティアリング、そして見積もりと実測の差分を扱います。見積もりが外れる原因は多くの場合、単価ではなく前提条件です。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | 何が課金対象で、何が課金されないか | [何が課金対象か](notes/provisioned-versus-consumed.md#何が課金対象か) |
| 2 | ティアリングでどこまで下がるか | [階層化は「常に安くなる」わけではありません](notes/provisioned-versus-consumed.md#階層化は常に安くなるわけではありません) |
| 3 | 見積もりが外れる典型的な前提は何か | [見積もりが外れる典型的な前提](notes/provisioned-versus-consumed.md#見積もりが外れる典型的な前提) |
| 4 | Snapshot が容量に与える影響をどう見るか | [Snapshot は容量として現れます](notes/provisioned-versus-consumed.md#snapshot-は容量として現れます) |
| 5 | コストと可用性・性能のトレードオフをどう見比べて決めるか | [トレードオフの見比べかた](notes/provisioned-versus-consumed.md#トレードオフの見比べかた) |

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
🌐 [日本語](README.md) | [English](../../../en/domains/cost/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
