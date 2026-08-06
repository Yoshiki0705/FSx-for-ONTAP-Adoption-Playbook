# Domain — セキュリティ・ガバナンス (Security & Governance)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/security-governance/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

暗号化、監査、権限設計、規制ワークロードでの考慮事項を扱います。ここに書かれているのは設計上の考慮事項であり、法務・コンプライアンス上の判断ではありません。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | 暗号化の選択肢とその境界はどこか | _未追加_ |
| 2 | 誰が何をしたかをどう記録するか | _未追加_ |
| 3 | 権限設計をどう最小権限に寄せるか | _未追加_ |
| 4 | 規制ワークロードで問われる論点は何か | _未追加_ |
| 5 | OT / IT 境界をまたぐ場合の考慮事項は何か | _未追加_ |

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
🌐 [日本語](README.md) | [English](../../../en/domains/security-governance/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
