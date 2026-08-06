# Playbook 05 — 運用 (Operate)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/playbooks/05-operate/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

監視・容量管理・障害対応・変更管理を扱います。「動いている」ことの確認と「壊れたときにどうするか」の両方が必要です。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | 何を監視し、どこに閾値を置くか | _未追加_ |
| 2 | 容量の枯渇をどう予兆検知するか | _未追加_ |
| 3 | 性能劣化の切り分け手順はどうなるか | _未追加_ |
| 4 | ONTAP のバージョン更新をどう扱うか | _未追加_ |
| 5 | インシデント時の初動をどう定義するか | _未追加_ |

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
🌐 [日本語](README.md) | [English](../../../en/playbooks/05-operate/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
