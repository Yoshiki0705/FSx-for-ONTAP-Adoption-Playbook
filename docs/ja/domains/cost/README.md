# Domain — コスト (Cost)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/cost/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

容量、ティアリング、そして見積もりと実測の差分を扱います。見積もりが外れる原因は多くの場合、単価ではなく前提条件です。

---

## 最初に読むもの

**手元にある材料から、次に読む 1 ページを決めます。** 下の「扱う問い」は目次で、これは入口です。

| 手元にあるもの | 最初に読むもの | そこで分かること |
|---|---|---|
| **請求書**（想定より高い） | [請求が想定より高いとき](../../reference/decision-trees/cost-higher-than-expected.md) | **確保で課金か消費で課金かが最初の分岐。** 使用量を減らしても動かない項目があります |
| **見積もり**（これから作る） | [見積もりが外れる典型的な前提](notes/provisioned-versus-consumed.md#見積もりが外れる典型的な前提) | 外れる前提。**重複排除と圧縮は SSD の請求を下げません** |
| **削る候補が決まっている** | [トレードオフの見比べかた](notes/provisioned-versus-consumed.md#トレードオフの見比べかた) | 削ると何を引き換えにするか。**要件で確保量が決まっているなら削れません** |

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | 何が課金対象で、何が課金されないか | [何が課金対象か](notes/provisioned-versus-consumed.md#課金対象) |
| 2 | ティアリングでどこまで下がるか | [階層化は「常に安くなる」わけではありません](notes/provisioned-versus-consumed.md#階層化が常に安くなるとは限らない理由) |
| 3 | 見積もりが外れる典型的な前提は何か | [見積もりが外れる典型的な前提](notes/provisioned-versus-consumed.md#見積もりが外れる典型的な前提) |
| 4 | Snapshot が容量に与える影響をどう見るか | [Snapshot は容量として現れます](notes/provisioned-versus-consumed.md#容量として現れる-snapshot) |
| 5 | コストと可用性・性能のトレードオフをどう見比べて決めるか | [トレードオフの見比べかた](notes/provisioned-versus-consumed.md#トレードオフの見比べかた) |
| 6 | 請求が想定より高いとき、どこから確かめるか | [請求が想定より高いとき](../../reference/decision-trees/cost-higher-than-expected.md) |
| 7 | 最小構成そのものが高いのではないか。複製が 1 つだけの場合はどうか | [最小構成の床](../../domains/block-storage/notes/when-ebs-stops-being-the-cheaper-answer.md#最小構成の床) / [台数の問いから複製の問いへ](../../domains/block-storage/notes/when-ebs-stops-being-the-cheaper-answer.md#台数の問いから複製の問いへの置き換え) |

---

## アーキテクチャを決めたあとの費用

**このモジュールが持っているのは FSx for ONTAP の課金モデルです。** 何が確保で課金され、何が消費で課金されるか、階層化がどこまで下がるか。

**構成そのものの費用構造は、その構成を運用しているリポジトリが持っています。** ここには転記していません。同じ数値を 2 か所に置くと、片方だけが古くなります。

| 決めた構成 | 費用構造の所在 | そこにあるもの |
|---|---|---|
| **S3 で集めて、ファイルプロトコルで読む** | [FinOps — S3 標準と FSx for ONTAP S3 AP](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/comparison/finops-s3-vs-s3ap.md) | **課金次元の対応**と 3 つの構造的な違い。「同じデータを繰り返し読むか、1 回だけか」で向く選択が変わります |
| **性能試験をこれから回す** | [FinOps — 性能試験のパターン別費用](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/comparison/finops-performance-test-patterns.md) | **測定環境そのものの費用**。何が時間課金で何が従量課金か、消し忘れると何が起きるか |
| **監視経路を選ぶ** | [コストモデル — Direct Send / Collector / Firehose](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/blob/main/docs/ja/cost-model.md) | 3 経路の月額の比較と、**見積りに必要な入力値の一覧** |
| **監視を動かしたあと、見積りが合っているか** | [コスト検証](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/blob/main/docs/ja/cost-validation.md) | 見積りと**実際の請求データの突き合わせ**の手順 |
| **分析基盤に載せる（メタデータのみ / 全複製）** | [Cost Estimation](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/docs/adoption-guide/cost-estimation.md) | 構成要素別の内訳と**スケーリングの算定式**。メタデータのみと全複製の比較 |
| **S3 Access Point のポータルを動かした** | [コスト計測](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/ja/cost-measurement.md) | **Cost Explorer から実測する手順**。見積りではありません |

**数値をここに持ってくるときは引用として登録します**（[引用索引](../../reference/cross-repo-index.md)）。単価を含む数値には取得日とリージョンが付いており、それを落とすと比較に使えません。

**単価そのものは [AWS の料金ページ](https://aws.amazon.com/jp/fsx/netapp-ontap/pricing/) です。** どのリポジトリの数値も取得時点のもので、料金ページの代わりにはなりません。

---

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`notes/`](notes/) | 知見の最小単位。1 ファイル = 1 論点。frontmatter に `evidence` 区分を持ちます |

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
