# Playbook 02 — 設計 (Design)

[English](README.en.md) | [🏠 リポジトリトップ](../../README.md)

---

評価結果をもとに、移行先の構成を決めます。容量とスループットは後から変更できますが、一部の選択（セキュリティスタイル、SnapLock 有効化など）は不可逆です。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | ファイルシステムと SVM をどう分割するか | _未追加_ |
| 2 | 容量とスループットをどう見積もるか | _未追加_ |
| 3 | ボリュームのセキュリティスタイルをどう選ぶか | _未追加_ |
| 4 | マルチ AZ とシングル AZ をどう判断するか | _未追加_ |
| 5 | 不可逆な設定はどれで、いつ決める必要があるか | _未追加_ |

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
