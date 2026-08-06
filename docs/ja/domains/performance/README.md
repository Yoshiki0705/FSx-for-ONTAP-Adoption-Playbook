# Domain — 性能 (Performance)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/performance/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

スループット設計、レイテンシ、キャッシュ、共有帯域の挙動を扱います。数値は必ず測定環境とセットで読んでください。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | スループットはどこで決まり、どこで共有されるか | [スループットは 1 つの設定値では決まらない](notes/where-throughput-is-determined-and-shared.md) |
| 2 | プロトコル間で帯域をどう分け合うか | [プロトコル間で帯域はどう分け合われるか](notes/what-you-cannot-read-from-cloudwatch.md#プロトコル間で帯域はどう分け合われるか) |
| 3 | レイテンシのテール（p99）をどう見るか | [p99 は CloudWatch のメトリクスからは出せない](notes/what-you-cannot-read-from-cloudwatch.md) |
| 4 | キャッシュが効くワークロードの条件は何か | [キャッシュが効く条件](notes/what-you-cannot-read-from-cloudwatch.md#キャッシュが効く条件) |
| 5 | ベンチマークをどう設計すれば再現できるか | [再現できるベンチマークの条件](notes/what-you-cannot-read-from-cloudwatch.md#再現できるベンチマークの条件) |

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
🌐 [日本語](README.md) | [English](../../../en/domains/performance/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
