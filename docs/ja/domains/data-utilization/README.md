# Domain — データ活用 (Data Utilization)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/data-utilization/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

NAS 上のデータを、コピーを増やさずに分析・AI・アプリケーションから使うための知見です。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | S3 API 経由のアクセスで何ができ、何ができないか | [FSx for ONTAP S3 AP は「S3 として使える」わけではない](notes/s3-access-point-constraints.md) |
| 2 | 分析基盤にどう接続するか | _未追加_ |
| 3 | AI / RAG で権限をどう扱うか | _未追加_ |
| 4 | データコピーを増やさない設計とは | _未追加_ |
| 5 | 読み取り加速をどこで効かせるか | _未追加_ |

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
🌐 [日本語](README.md) | [English](../../../en/domains/data-utilization/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
