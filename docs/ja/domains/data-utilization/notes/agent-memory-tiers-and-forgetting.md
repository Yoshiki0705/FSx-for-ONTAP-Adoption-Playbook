---
title: エージェントの記憶は 3 層に分けて置く：忘れる処理は原本だけでなく Snapshot とバックアップとクローンまで及ぶ必要がある
lifecycle: [design, operate]
domains: [data-utilization, data-protection, cost]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html
lang: ja
---

# エージェントの記憶は、置き場所をどう決め、どう忘れさせるか？

短期、長期、真実の源の 3 層に分けて置き場所を決め、忘れる処理は Snapshot、バックアップ、クローンまで及ばせます。

<!-- lang-switcher:start -->
🌐 [日本語](agent-memory-tiers-and-forgetting.md) | [English](../../../../en/domains/data-utilization/notes/agent-memory-tiers-and-forgetting.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->

## このノートで学べること

- エージェントの記憶を、短期の出来事、長期の記録、真実の源の 3 層に分けること。FSx for ONTAP に置く原本の層は、ボリュームの階層化ポリシーで SSD と容量プールの置き場所を決める
- 「忘れる」は、原本のファイルを消すだけでは終わらないこと。Snapshot が残る間は、削除したファイルが S3 Access Points から読めた実測がある
- 保存するバイト数を減らす仕組み（重複排除、圧縮、コンパクション）が、容量プールに移ったデータでどう変わるか

## このノートが答えないこと

- 容量プールからの読み出しの遅さと費用の実測。このノートは AWS の文書の記述だけを使い、測っていない（`open`）
- 個人データの削除義務を満たすかどうかの判断。ここに書くのは技術的な挙動で、法令上の判断や法的助言ではない
- AgentCore Memory で保持期間が満了したときの削除の実際の挙動。API リファレンスの記述だけを引く
- 電力やエネルギーの削減量。保存するバイト数の削減しか扱わない

## 前提レベル

intermediate

## 本文

<a id="エージェントの記憶は-3-層に分けて置く"></a>

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — データ活用](../README.md)

---

### 結論

**Amazon FSx for NetApp ONTAP に置くのは、エージェントの記憶のうち真実の源の層です。** 短期の出来事（会話やセッションの記録）と長期の記録（抽出・統合された記憶）は、エージェント基盤の側に置かれることが多く、原本から作り直せる派生物として扱います。原本の層には、ボリュームの階層化ポリシーで SSD と容量プールの置き場所を決めます。

**「忘れる」は、記録を消すことです。そして消す対象は、原本だけでは足りません。** 原本のファイルを削除しても、それを含む Snapshot が残る間は、削除したファイルを読める経路が残ります。バックアップとクローンも同じ前提で数えます。

このノートは、AWS CTO のブログ記事 [Tech predictions for 2027 and beyond](https://www.allthingsdistributed.com/2026/11/tech-predictions-for-2027-and-beyond.html)（2026-11-24）が触れる、エージェントの記憶と忘却を、FSx for ONTAP のデータの側から受けるときの判断としてまとめたものです。記事の内容は写していません。新しい測定も足していません。既にある記録へのリンクで組み立てています。

> **Evidence**: `documented`。階層化ポリシーとストレージ効率は AWS 公式ドキュメント、AgentCore Memory の保持期間は API リファレンスの記述です。
> 削除したファイルが Snapshot から読めたことは、Cyber Resilience Patterns の実測（`verified`、2026-11-24）の引用で、このリポジトリでは再測定していません。

---

### 記憶の 3 層

| 層 | 中身 | 置き場所の考え方 | 消すときに及ぶ範囲 |
|---|---|---|---|
| 短期の出来事 | 会話やセッションの記録 | エージェント基盤の記憶サービス。保持期間を持つ | 保持期間の満了、または利用者単位の削除 |
| 長期の記録 | 短期の出来事から抽出・統合した記憶、ベクトル | エージェント基盤の記憶サービス、ベクトルの索引 | 原本から作り直せるので、消してよいかは原本の側で決まる |
| 真実の源 | 原本のファイルとデータ | FSx for ONTAP のボリューム | 原本、Snapshot、バックアップ、クローン |

**長期の記録を消しても、原本が残っていれば同じ記憶は作り直せます。** 忘れることを意図したなら、原本の側を先に消し、派生物を作り直さないことが必要です。エッジのデータを扱う構成では、記憶とベクトルと真実の源を区別する前提を、ONTAP Edge to Cloud AI の [Agentic AI on AWS](https://github.com/Yoshiki0705/ONTAP-Edge-to-Cloud-AI/blob/main/docs/ja/agentic-ai-on-aws.md) が 4 節（記憶、ベクトル、真実の源の区別）で書いています。未確認・未実装の項目は 7 節にあります。

---

### 階層化ポリシーの 4 つの選択肢

ボリュームの階層化ポリシーは、データを SSD に置くか、容量プールへ移すかを決めます。

| ポリシー | データの置き場所 |
|---|---|
| `Auto` | ユーザーデータと Snapshot の冷えたデータを容量プールへ移す。Amazon FSx コンソールでボリュームを作るときの既定 |
| `Snapshot Only` | Snapshot のデータだけを容量プールへ移す。AWS CLI、Amazon FSx API、ONTAP CLI で作るときの既定 |
| `All` | すべてを冷えたデータとして扱う。書き込みはいったん SSD に入り、バックグラウンドで容量プールへ移る |
| `None` | データを SSD に置く |

冷却期間の既定は、`Auto` が 31 日、`Snapshot Only` が 2 日です。冷却期間は 2 日から 183 日の範囲で設定でき、期間が過ぎてから 24 時間から 48 時間で階層化されます。ファイルのメタデータは常に SSD に残ります。

SSD の使用率によって動きが変わります。

| SSD の使用率 | 階層化の動き |
|---|---|
| 50 % 以下 | `All` だけが階層化する |
| 90 % 以上 | 容量プールから読んだデータを SSD に戻さない |
| 98 % 以上 | 階層化が止まる |

---

### 記憶の層とポリシーの対応

次の表は、FSx for ONTAP に置く原本の層に限った対応の例です。選ぶ側の事情で変わるので、利点と引き換えにするものを並べます。

| 置くもの | 向くポリシーの例 | 得るもの | 引き換えにするもの |
|---|---|---|---|
| 頻繁に読む真実の源の原本 | `Auto` | 冷えたデータだけが容量プールへ移り、よく読むデータは SSD に残る | 冷却期間を過ぎたデータの読み出しは、容量プールから行うので遅くなり、読み出しの費用がかかる |
| 古い版と、読む頻度が低い履歴 | `Snapshot Only` または `All` | SSD の容量を使わずに履歴を持てる | 履歴を読み返す処理が容量プールからの読み出しになる。`All` は原本の読み出しも容量プールからになる |
| 低い遅延が常に要るデータ | `None` | 読み出しが SSD から行われる | SSD の容量と費用を、データの全量について払う |

どの行も、容量プールに移したデータの読み出しの遅さと費用は、このノートでは測っていません。自環境で測る場合は、読み出しの頻度が高いデータを `All` に置かないように確認します。

---

### 保存するバイト数の削減

重複排除、圧縮、コンパクションは、インラインの処理と、SSD の上でのバックグラウンドの処理で行われます。

- 容量プールに移ったデータには、バックグラウンドの処理は行われません。SSD にいた間に得た削減は保たれます
- DP ボリュームではストレージ効率を有効にできません。ただし、元の RW ボリュームで得た削減は、レプリケーション先でも保たれます
- ボリュームをまたぐ重複排除はありません

ここで言えるのは、保存するバイト数の削減だけです。電力やエネルギーの数値は、このノートでは書きません。

---

### 忘れる処理が及ぶ範囲

**原本のファイルを削除しても、それを含む Snapshot がある間は、削除したファイルが読めました。** Cyber Resilience Patterns の [削除の依頼と削除後も残るコピー](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md) が測っています。

| 項目 | 内容 |
|---|---|
| 測定日と環境 | 2026-11-24、ap-northeast-1、第 1 世代 SINGLE_AZ_1、ONTAP 9.19.1P4 |
| ボリュームとユーザー | UNIX スタイルのボリューム、ファイルシステムのユーザーは root |
| 回数 | 読み取り 3 回、閉じ方は各 1 回 |
| 区分 | `verified` |

結果は次のとおりです。

1. ファイルを削除したあとも、それを含む Snapshot がある間は、S3 Access Points で `.snapshot/<Snapshot 名>/<パス>` のキーを `GetObject` すると削除したファイルが返りました
2. `ListObjectsV2` には、そのキーが出ませんでした。一覧に出ないので、一覧だけを見て消えたと判断できません
3. この経路は、次のどれでも閉じました。Snapshot の削除、ボリュームの `snapshot_directory_access_enabled=false`、アクセスポイントポリシーで `<アクセスポイント ARN>/object/.snapshot/*` への `s3:GetObject` を拒否すること

**エージェントのロールが使うアクセスポイントには、古い版を読む理由がなければ、この拒否を置くことを勧めます。** 拒否の書き方と、`Allow` を狭くしても絞れない理由は、[S3 Access Point の認可は 2 層のどちらで絞るか](../../security-governance/notes/access-point-authorization-layers.md)にあります。

バックアップとクローンについては、Snapshot 以外のコピーの扱いをリンク先の記録に従います。このノートは新しい測定を足していません。

測っていないこと（`open`）は次のとおりです。

- NTFS スタイルのボリューム
- root 以外のユーザー
- FlexGroup
- ほかの ONTAP 版

---

### 記憶サービス側の保持期間

AgentCore Memory の `CreateMemory` には `eventExpiryDuration` があります。単位は日です。[CreateMemory](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateMemory.html) の Valid Range は 3 から 3650 です（2026-11-24 に確認、`documented`）。

**同じページの説明文は「between 7 and 3650 days」と書いており、範囲の欄と食い違っています。** このノートは範囲の欄の値を書きます。食い違いの解消は、AWS 側の文書の更新を待つ必要があります。保持期間を設計の入力にする場合は、自環境で作成して境界の値が受け付けられるかを確かめます。

記録の一覧と削除を利用者の名前空間で行う実装の例は、Agentic Access-Aware RAG の [エピソード記憶の実装](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG/blob/main/docker/nextjs/src/lib/agentcore/episodic-memory.ts) にあります。`deleteEpisode` の所在がそこです。

---

### 設計の手順

1. 記憶の層ごとに、原本がどこにあるかを決める。派生物は原本から作り直せる状態に保つ
2. 原本のボリュームごとに階層化ポリシーを決め、冷却期間と SSD の使用率の閾値を確認する
3. 忘れる要件がある場合は、削除の対象に Snapshot、バックアップ、クローンを数える
4. エージェントのロールが使うアクセスポイントに、`.snapshot/*` への `s3:GetObject` の拒否を置く
5. 保持期間を持つ記憶サービスでは、期間の値を自環境で作成して確かめる

---

## 自環境での確認手順

読み取りだけの手順です。

```bash
aws fsx describe-volumes --volume-ids <volume-id> --query "Volumes[0].OntapConfiguration.[TieringPolicy,SnapshotPolicy]"
```

```bash
curl -sk -u <admin-user> "https://<management-endpoint>/api/storage/volumes/<volume-uuid>?fields=snapshot_directory_access_enabled"
```

```bash
aws s3control get-access-point-policy --account-id <account-id> --name <access-point-name> --query Policy --output text
```

```bash
aws fsx describe-backups --filters Name=volume-id,Values=<volume-id>
```

### 期待結果

```text
[ { "Name": "AUTO", "CoolingPeriod": 31 }, "<snapshot-policy>" ]
{ "snapshot_directory_access_enabled": true }
{ "Statement": [ ... "Resource": "<access-point-arn>/object/.snapshot/*" ... ] }
{ "Backups": [ ... ] }
```

分かることは、ボリュームの階層化ポリシーと冷却期間、Snapshot ディレクトリへのアクセスの有効か無効か、アクセスポイントポリシーに `.snapshot/*` の拒否があるか、削除の対象に数えるバックアップの有無です。

分からないことは、容量プールからの読み出しの遅さと費用、削除したファイルが実際に読めなくなったか、NTFS スタイルのボリュームでの挙動です。削除後に読めないことは、削除したキーで `GetObject` して確かめます。

---

### 参照した一次情報

| 論点 | 出典 |
|---|---|
| 階層化ポリシー、冷却期間、SSD の使用率の閾値 | [AWS: Volume storage capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html) |
| 重複排除、圧縮、コンパクション | [AWS: Managing storage efficiencies](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/manage-vol-SE.html) |
| AgentCore Memory の保持期間 | [AWS: CreateMemory](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateMemory.html) |
| 削除後も残るコピーの実測 | [Cyber Resilience Patterns: 削除の依頼と削除後も残るコピー](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md) |
| エピソード記憶の削除の実装 | [Agentic Access-Aware RAG: episodic-memory.ts](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG/blob/main/docker/nextjs/src/lib/agentcore/episodic-memory.ts) |
| 記憶、ベクトル、真実の源の区別 | [ONTAP Edge to Cloud AI: Agentic AI on AWS](https://github.com/Yoshiki0705/ONTAP-Edge-to-Cloud-AI/blob/main/docs/ja/agentic-ai-on-aws.md) |

---

### 関連ドキュメント

- [Domain — データ活用](../README.md)
- [S3 Access Point の認可は 2 層のどちらで絞るか](../../security-governance/notes/access-point-authorization-layers.md)
- [知見の分類ポリシー](../../../evidence-policy.md)

---

## Read next

[エージェントに渡す研究データセットは Snapshot の UUID で再現する](reproducible-research-datasets-for-agents.md)
