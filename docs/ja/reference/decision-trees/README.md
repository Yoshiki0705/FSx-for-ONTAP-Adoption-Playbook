# 決定ツリー / Decision Trees

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md)

---

複数の選択肢からどれを選ぶかを、判断順に整理した資料を置きます。
mermaid の `graph TD` で図示し、その下に表で各分岐の根拠を書きます。

Flowcharts that organize a choice between options into the order the decisions should be made.
Rendered as mermaid `graph TD`, with a table below giving the reasoning for each branch.

---

## 一覧 / Index

| 決定ツリー / Decision tree | 扱う判断 / Decision covered |
|---|---|
| [移行方式の選択](migration-method.md) | ONTAP 間か否か、ACL 保持要件、停止時間から移行方式を選ぶ / Choosing a migration method from source type, ACL requirements, and downtime tolerance |
| [S3 Access Point 経由のリクエストはどう判定されるか](access-point-authorization.md) | 二段の認可の評価順序を追い、症状から落ちた段を逆引きする / Following the two-layer authorization evaluation order, and working back from a symptom to the layer that refused |

---

## 執筆ルール / Authoring rules

| ルール / Rule | 理由 / Reason |
|---|---|
| 制約の強い判断を先に置く / Put the strongest constraint first | 候補が早く絞れる / It narrows the candidates fastest |
| 分岐の根拠を表で補う / Back each branch with a table | 図だけでは「なぜその分岐か」が伝わらない / A diagram alone does not convey why |
| 「よくある誤解」を必ず入れる / Always include common misconceptions | 誤った前提での分岐が最も多い失敗 / Branching on a false premise is the most common failure |
| 推奨案の制約も書く / State the recommended option's constraints too | 一方的な推奨は判断材料にならない / A one-sided recommendation is not decision material |

---

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md)
