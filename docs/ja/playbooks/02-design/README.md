# Playbook 02 — 設計 (Design)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/playbooks/02-design/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

評価結果をもとに、移行先の構成を決めます。容量とスループットは後から変更できますが、一部の選択（セキュリティスタイル、SnapLock 有効化など）は不可逆です。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | 後から HA ペアを足しても活かせるボリューム粒度にするには何を考えるか | [HA ペアを足すときに起きること](notes/deployment-type-is-decided-once.md#ha-ペアを足すときに起きること) |
| 2 | 1 組の HA ペアで足りるか、スケールアウトが必要か | [単一 HA ペアの天井](notes/deployment-type-is-decided-once.md#単一-ha-ペアの天井) |
| 3 | ボリュームのセキュリティスタイルをどう選ぶか | [セキュリティスタイルが権限評価のモデルを決める](../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) |
| 4 | マルチ AZ とシングル AZ をどう判断するか | [Multi-AZ と Single-AZ の判断](notes/deployment-type-is-decided-once.md#multi-az-と-single-az-の判断) |
| 5 | 不可逆な設定はどれで、いつ決める必要があるか | [デプロイタイプは一度しか決められない](notes/deployment-type-is-decided-once.md) |
| 6 | ファイルシステムと SVM をどの単位で分割するか | _未追加_ |
| 7 | 容量とスループットの初期値をどう見積もるか | _未追加_ |

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
- [本番投入前レビュー](../04-build/checklists/pre-production-review.md) — **不可逆な項目はこのフェーズで確定させます**
- [ナビゲーションガイド](../../navigation.md)
- [用語集](../../reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/playbooks/02-design/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
