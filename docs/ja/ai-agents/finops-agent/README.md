# AWS FinOps Agent を FSx for ONTAP のコスト運用に使う

[🏠 リポジトリトップ](../../../../README.md)

---

AWS FinOps Agent を Amazon FSx for NetApp ONTAP のコスト運用に重ねられるかを扱います。**エージェントの仕様は公式ドキュメントで確認済みですが、FSx for ONTAP のコスト構造への適合判断は著者環境での実測ではありません。** どの記述がどちらかは、各節で明示します。

---

## このページの但し書き

| 内容 | 確度 |
|---|---|
| FinOps Agent の用途・データソース・提供状態 | AWS 公式ブログに出典（本ページ末尾）。`documented` 相当 |
| FSx for ONTAP 固有のコスト構造への適合、どの指標を見るべきか | **未検証。** 著者が FinOps Agent を FSx for ONTAP 環境で動かして得た結果ではありません |

しきい値（「前月比 20% 増で調査」など）や削減率は**書きません**。環境依存で、著者の実測もないためです。代わりに「どの指標を見るか」の観点だけを残します。

---

## FinOps Agent とは（documented）

AWS FinOps Agent は、**コスト異常の根本原因調査**と、**エンジニアからの自然言語コスト質問への応答**に軸足を置くエージェントです。定期的なダッシュボードレビューから、継続的なコスト運用へ移す用途とされています。

動作の骨格は次のとおりです。

1. AWS Cost Anomaly Detection のイベントを受け取る
2. コスト変化を AWS CloudTrail のイベント（誰が・何を・いつ変えたか）と相関させる
3. スパイクを引き起こした変更を特定し、根本原因と責任者を含む調査サマリを出す
4. 任意で Jira チケットの起票や Slack への投稿で通知する

見るデータソースは、AWS Cost Explorer、AWS Cost Anomaly Detection、AWS Cost Optimization Hub、AWS Compute Optimizer です。account-to-owner マッピングやタグ規約などの context ファイルをアップロードすると、組織の用語で質問を解釈させられます。

---

## 提供状態とリージョン（documented・2026-09 調査時点）

**提供状態は変わります。本番採用前に最新の状態を確認してください。**

| 項目 | 2026-09 調査時点 |
|---|---|
| 提供状態 | **Public Preview** |
| エージェントの動作リージョン | **US East（バージニア北部, us-east-1）**。管理アカウントに設定すると、全 AWS リージョン・全アカウントのコストを対象にできる |
| 価格 | **プレビュー期間中は無料**（月次の使用量上限あり）。FinOps Agent と併用する他の AWS サービスには標準料金が適用される |

**エージェント自体が us-east-1 でしか動かない点と、対象コストは全リージョンをカバーできる点は別の話です。** 東京リージョンの FSx for ONTAP を運用していても、コストの調査対象にはできます。ただしエージェントの設定・実行は us-east-1 です。**プレビューの価格・上限・リージョンは変わりうるので、この表を根拠に本番設計しないでください。**

---

## FSx for ONTAP のどのフェーズに効くか（適合判断・未検証）

**この節は著者の判断で、実測ではありません。** FinOps Agent の用途（コスト運用）と FSx for ONTAP のコスト構造から導いたものです。

| フェーズ | 見込み | 根拠（未検証） |
|---|---|---|
| 最適化（06-optimize） | 効きやすい | コスト異常調査と最適化推奨の集約が用途そのもの。FSx for ONTAP のコストは Cost Explorer / Cost Optimization Hub に現れる |
| 運用（05-operate） | 効きやすい | 定期レポートと異常検知を継続運用に載せる用途。手作業のダッシュボード集計を置き換える方向 |
| 設計・構築（01〜04） | 効きにくい | コスト構造の設計そのものを生成する用途ではない |

### AWS のコストデータは見えるが、FSx for ONTAP 固有構造の解釈は未検証

**FinOps Agent が見るのは AWS のコスト/使用量データ（Cost Explorer など）です。** FSx for ONTAP の課金は、この経路に**課金明細レベルで現れます**。したがって、FSx for ONTAP のコストを異常調査・質問応答の対象にすること自体は、データソースの構造から見込めます。

**ただし、FSx for ONTAP 固有のコスト構造を "解釈" できるかは未検証です。** FSx for ONTAP の課金は次のように分かれます（詳細は [課金は「確保した量」と「使った量」に分かれる](../../domains/cost/notes/provisioned-versus-consumed.md)）。

| コスト構造 | 内容 | FinOps Agent が解釈できるか |
|---|---|---|
| 確保 vs 消費 | SSD 容量・IOPS・スループット容量は確保量課金、容量プール・バックアップは消費量課金 | **未検証。** 課金明細としては見えるが、「確保したが使っていない」を最適化余地として提示するかは確認していない |
| 階層化の per-request 課金 | 容量プールのデータ読み書きにリクエスト課金が乗る | **未検証。** リクエスト課金の異常を FSx for ONTAP 文脈で切り分けるかは確認していない |
| スループット容量の月額比重 | スループット容量は確保量で月額に効く | **未検証** |

**したがって、このページは「FinOps Agent で FSx for ONTAP のコスト削減ができる」とは書きません。** 見込めるのは「AWS コストデータ上で FSx for ONTAP のコストを異常調査・質問応答の対象にできる」ところまでです。**確保 vs 消費のどちらの異常を追えるか、階層化のリクエスト課金を切り分けられるかは、対象環境で確かめる項目です。**

### 異常調査の CloudTrail 相関は用途に合う（documented + 適合判断）

**FinOps Agent がコスト変化を CloudTrail と相関させて原因の変更を特定する仕組みは documented です。** FSx for ONTAP のコストが動く典型（スループット容量やプロビジョン SSD の変更、階層化ポリシーの変更）は AWS API 経由の操作なので、CloudTrail に記録されます。**この相関が FSx for ONTAP の構成変更に対して有効に働くかは未検証ですが、仕組みの上では噛み合う方向です。**

---

## Skill / context の書き方（適合判断・未検証）

FinOps Agent は context ファイル（account-to-owner マッピング、タグ規約、レビュー頻度）で組織の用語に合わせられます。FSx for ONTAP 向けに書くなら、**しきい値ではなく「どの指標を見るか」の観点を context に持たせる**のが、このリポジトリの証拠区分の規律に沿います。

- **証拠区分を持ち込む。** 「使用率が高い」の基準は環境依存。context に固定のしきい値を焼き込むより、「確保 vs 消費のどちらの異常か」を切り分ける観点を書く
- **確保と消費を分けて質問する。** 「確保したが使っていない SSD 容量」と「消費が増えた容量プール」は別の最適化余地。まとめて聞くと切り分けが甘くなる
- **命名を守る。** 初出は Amazon FSx for NetApp ONTAP、以降は FSx for ONTAP

---

## 参考資料（一次情報）

- [Announcing the public preview of AWS FinOps Agent（AWS 公式ブログ）](https://aws.amazon.com/blogs/aws-cloud-financial-management/aws-finops-agent-is-now-public-preview/) — 用途、データソース（Cost Explorer / Cost Anomaly Detection / Cost Optimization Hub / Compute Optimizer）、CloudTrail 相関、Public Preview の提供状態・リージョン・価格
- [AWS Cost Anomaly Detection](https://docs.aws.amazon.com/cost-management/latest/userguide/getting-started-ad.html) — 異常検知のイベント源
- [AWS Cost Optimization Hub](https://docs.aws.amazon.com/cost-management/latest/userguide/cost-optimization-hub.html) — 最適化推奨の集約元

---

## 関連

- [AI エージェントのジャンル入口](../README.md)
- [課金は「確保した量」と「使った量」に分かれる](../../domains/cost/notes/provisioned-versus-consumed.md) — FSx for ONTAP 固有のコスト構造
- [Domain — コスト](../../domains/cost/) — コスト設計の知見

---

[🏠 リポジトリトップ](../../../../README.md)
