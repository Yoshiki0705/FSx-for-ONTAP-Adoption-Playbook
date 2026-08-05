# Playbook 06 — 最適化 (Optimize)

[English](README.en.md) | [🏠 リポジトリトップ](../../README.md)

---

定常運用に入ってからの性能とコストの詰めを扱います。最適化は測定なしには始められません。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | どこがボトルネックかをどう特定するか | _未追加_ |
| 2 | ティアリングをどう設定するか | _未追加_ |
| 3 | ストレージ効率（重複排除・圧縮）の効果をどう測るか | _未追加_ |
| 4 | スループット設定を上げる前に確認すべきことは何か | _未追加_ |
| 5 | コスト削減と可用性のトレードオフをどう置くか | _未追加_ |

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

判断基準の詳細は [知見の分類ポリシー](../../docs/ja/evidence-policy.md) を参照してください。

---

## 関連

- [テーマ軸で探す](../../docs/ja/navigation.md#テーマ軸--domains)
- [移行方式 決定ツリー](../../reference/decision-trees/migration-method.md)
- [ナビゲーションガイド](../../docs/ja/navigation.md)
- [用語集](../../reference/glossary/)

---

[English](README.en.md) | [🏠 リポジトリトップ](../../README.md)
