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
| [SMB のユーザー管理と監査は 2 つの選択で決まる](smb-identity-and-audit.md) | ID をワークグループと AD 参加のどちらに置くか、監査を常時有効にするか。各枝が引き受ける制約を選択前に示す / Choosing between a workgroup and AD membership, and whether auditing runs continuously, with what each branch commits you to shown before the choice。**英語版あり / [English version](../../../en/reference/decision-trees/smb-identity-and-audit.md)** |
| [ブロックプロトコルとレイアウトの選択](block-protocol-and-layout.md) | 世代・HA ペア数・ホスト OS で選択肢が先に狭まる順序をたどり、LUN のレイアウトと容量と整合性まで続ける / Following the order in which generation, HA pair count, and host OS narrow the choice, then on to LUN layout, capacity, and consistency |

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
