# Playbook 06 — 最適化 (Optimize)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/playbooks/06-optimize/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

定常運用に入ってからの性能とコストの詰めを扱います。最適化は測定なしには始められません。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | どこがボトルネックかをどう特定するか | [性能劣化の切り分け順](../05-operate/notes/monitoring-fails-on-averages.md#性能劣化の切り分け順) |
| 2 | ティアリングをどう設定するか | [階層化の既定値は作成方法で違う](notes/tiering-defaults-differ-by-creation-method.md) |
| 3 | ストレージ効率（重複排除・圧縮）の効果をどう測るか | [効果をどう測るか](notes/tiering-defaults-differ-by-creation-method.md#ストレージ効率の効果の測り方) |
| 4 | スループット設定を上げる前に確認すべきことは何か | [変更の順序は「戻せるか」で決める](notes/tiering-defaults-differ-by-creation-method.md#戻せるかで決める変更の順序) |
| 5 | コスト削減と可用性のトレードオフをどう置くか | [トレードオフの見比べかた](../../domains/cost/notes/provisioned-versus-consumed.md#トレードオフの見比べかた) |

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
🌐 [日本語](README.md) | [English](../../../en/playbooks/06-optimize/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
