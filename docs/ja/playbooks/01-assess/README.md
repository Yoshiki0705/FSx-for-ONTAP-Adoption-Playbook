# Playbook 01 — 評価 (Assess)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/playbooks/01-assess/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

移行の前に、現行 NAS に何があり、何が制約になるかを把握します。ここでの見落としが、後続フェーズのやり直しコストに直結します。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | 容量・ファイル数・ディレクトリ構造をどう棚卸しするか | [容量が余っていても書けなくなる](notes/counting-bytes-is-not-counting-files.md) |
| 2 | どのプロトコルが実際に使われているか | [「設定されている」と「使われている」は違う](notes/counting-bytes-is-not-counting-files.md#設定されていると使われているは違う) |
| 3 | 権限・ACL・ID マッピングの現状はどうなっているか | [棚卸し項目の逆算表](notes/counting-bytes-is-not-counting-files.md#棚卸し項目は後で戻せない判断から逆算する) |
| 4 | 移行のブロッカーになりうる機能依存は何か | [移行方式の決定木](../../reference/decision-trees/migration-method.md) |
| 5 | 性能要件のベースラインをどう測るか | [比較可能な形で取る](notes/counting-bytes-is-not-counting-files.md#性能のベースラインは比較可能な形で取る) |
| 6 | 移行元が SaaS / クラウドストレージの場合、追加で採取すべき数値は何か | [Assess フェーズで採取すべき数値](../03-migrate/notes/saas-source-migration-scoping.md#3-assess-フェーズで採取すべき数値) |

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

- [テーマ軸で探す](../../navigation.md#テーマ軸--domains)
- [移行方式 決定ツリー](../../reference/decision-trees/migration-method.md)
- [ナビゲーションガイド](../../navigation.md)
- [用語集](../../reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/playbooks/01-assess/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
