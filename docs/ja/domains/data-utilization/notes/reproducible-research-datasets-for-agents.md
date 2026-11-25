---
title: エージェントに渡す研究データセットは Snapshot の UUID で再現する：実験ごとのクローンに S3 Access Points を付けて読ませる
lifecycle: [design, build, operate]
domains: [data-utilization, data-protection]
evidence: documented
source: https://aws.amazon.com/about-aws/whats-new/2026/11/amazon-fsx-for-netapp-ontap-additional-resources/
lang: ja
---

# エージェントに渡す研究データを、後から同じ入力で再現するには？

版ごとに Snapshot を作って名前と UUID を記録し、実験ごとのクローンに付けた S3 Access Points のエイリアスだけからエージェントに読ませます。

<!-- lang-switcher:start -->
🌐 [日本語](reproducible-research-datasets-for-agents.md) | [English](../../../../en/domains/data-utilization/notes/reproducible-research-datasets-for-agents.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->

## このノートで学べること

- 版ごとの Snapshot、実験ごとの FlexClone、クローンに付けた S3 Access Points という 3 つの組み合わせで、エージェントに渡す入力を固定できること
- 実験の記録に残す識別子（Snapshot の UUID、クローンの名前、アクセスポイントの ARN など）
- クローン作成の所要時間が、小さなファイルが多いデータセットで長くなること。並列に走らせる実験の数に影響する
- 後片付けの順序と、クローンを消したあとに親ボリュームが消せなくなる条件

## このノートが答えないこと

- NTFS スタイルのクローンにアクセスポイントを付けること（未測定、`open`）
- クローンのアクセスポイントへの操作で、CloudTrail に記録されるリソース（未測定、`open`）
- 研究の被験者や個人データを扱ってよいかの判断。ここに書くのは技術的な挙動で、法令上の判断や法的助言ではない
- データセットの版のローテーション、ボリューム数の上限、コンソールでの作成経路。それぞれ [学習データセットの版](dataset-versions-and-experiment-branches.md) と [コンソールで作ったクローン](a-console-clone-attaches-s3-access-points-in-minutes.md) にある

## 前提レベル

advanced

## 本文

<a id="エージェントに渡す研究データセットは-snapshot-の-uuid-で再現する"></a>

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — データ活用](../README.md)

---

### 結論

**エージェントに研究データを渡すときは、データセットの版ごとに Snapshot を作ってその名前と UUID を記録し、実験ごとに FlexClone を作り、クローンに付けた S3 Access Points のエイリアスだけからエージェントに読ませます。** 実験の記録に識別子を残せば、同じ Snapshot から同じ入力を作り直せます。

このノートは、AWS CTO のブログ記事 [Tech predictions for 2027 and beyond](https://www.allthingsdistributed.com/2026/11/tech-predictions-for-2027-and-beyond.html)（2026-11-24）が触れる、研究者とエージェントの協働における再現性を、Amazon FSx for NetApp ONTAP のデータの側から受けるときの判断としてまとめたものです。記事の内容は写していません。新しい測定も足していません。既にある記録へのリンクで組み立てています。

> **Evidence**: `documented`。手順の各段は、リンク先の実測（`verified`）や文書（`documented`）の引用です。このリポジトリでは再測定していません。
> 実測の環境と日付は、各段に書いています。測っていない範囲は `open` と書きます。

---

### 再現の流れ

1. 版ごとの Snapshot を作り、Snapshot の名前と UUID を記録します
2. 実験ごとに FlexClone を作ります。クローンの元になるボリュームを、以降は親ボリュームと呼びます
3. クローンに S3 Access Points を付けます
4. エージェントは、そのアクセスポイントのエイリアスだけから読みます
5. 実験の記録に、親ボリュームの UUID、Snapshot の UUID、クローンの名前、アクセスポイントの ARN、IAM のプリンシパル、CloudTrail のイベント ID を残します
6. 再現するときは、同じ Snapshot から作り直します
7. 後片付けは、アクセスポイントを外してからクローンを消します

#### 手順 3 のクローンへの S3 Access Points

S3-Burst on ONTAP Files の [S3 Access Points の相互運用の記録](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/limits/s3ap-interoperability.md) が測っています。

| 項目 | 内容 |
|---|---|
| 測定日と環境 | 2026-08-26、ap-northeast-1、ONTAP 9.18.1P3D1、UNIX スタイル |
| 区分 | `verified` |

結果は次のとおりです。

- アクセスポイントを付けたボリュームの FlexClone を作れました
- クローンにアクセスポイントを付けられました
- クローンのアクセスポイント経由の LIST と GET が成功しました
- 256 MiB のファイルの sha256 が、親ボリュームと一致しました

クローンへの PUT が親ボリュームに見えないことも、同じ記録にあります。実験の出力をクローンに書いても、その内容は親ボリュームから見えません。

#### 手順 2 のテンプレートでの宣言

2026-11-23 の [What's New](https://aws.amazon.com/about-aws/whats-new/2026/11/amazon-fsx-for-netapp-ontap-additional-resources/) で、クローンを Amazon FSx API と AWS CloudFormation から作れるようになりました。`CreateVolume` の `OntapConfiguration` に `CloneConfiguration` を指定します。手順 2 をテンプレートで宣言できます。コンソールで作る経路は [コンソールで作ったクローン](a-console-clone-attaches-s3-access-points-in-minutes.md) にあります。

#### 手順 7 の後片付け

S3 Access Points Serverless Patterns の [ボリュームのライフサイクルの落とし穴](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/agent/pitfalls-volume-lifecycle.md) が、次を記録しています（2026-08-15 に測った記録）。

- ONTAP REST でクローンを作るときは、`clone.is_flexclone: true` が要ります
- 分割していないクローンを消すと、削除済みのクローンは recovery queue に残ります。既定は 12 時間です。その間、親ボリュームを削除できません

アクセスポイントを外してからクローンを消し、親ボリュームを消す予定があるなら、recovery queue の残留を見込んで順序を組みます。

---

### 並列に走らせる実験の数

Cyber Resilience Patterns の [復旧の測定結果](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ja/recovery-measurement-results.md) に、クローン作成の所要時間があります。

| データセット | クローン作成の中央値 |
|---|---|
| 大きなファイル 1 GiB | 1.5 秒 |
| 大きなファイル 10 GiB | 2.5 秒 |
| 大きなファイル 50 GiB | 4.0 秒 |
| 約 80,000 個の小さなファイル（10 GiB） | 193 秒 |

各 4 回の中央値です。測定は 2026-11-18 から 2026-11-19、東京の検証用ファイルシステムで、sample run であり、本番の見積りではありません。

**小さなファイルが多いと、同じ 10 GiB でもクローン作成が遅くなります。** 遅い理由は、その記録でも推論（`hypothesis`）です。並列に走らせる実験の数は、自分のデータセットでクローン作成を測った値から決めます。

---

### 監査

S3 Access Points 経由の操作は、ONTAP のファイルアクセス監査ログに要求者が残りません。Cyber Resilience Patterns の [根拠の登録](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/agent/evidence-ledger.json) の E-018 が記録しています（`verified`）。

誰が読んだかは、CloudTrail のデータイベントで残します。実験の記録に CloudTrail のイベント ID を含めるのは、そのためです。クローンのアクセスポイントへの操作で、CloudTrail にどのリソースが記録されるかは測っていません（`open`）。

---

### 古い版の読み取り

クローンのアクセスポイントからも、`.snapshot/<Snapshot 名>/<パス>` で Snapshot の中身を読める可能性があります。元のボリュームで測った記録は、Cyber Resilience Patterns の [削除の依頼と削除後も残るコピー](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md) にあります（2026-11-24、`verified`）。そこでは、`.snapshot/<Snapshot 名>/<パス>` のキーで `GetObject` すると読めました。

**クローンでは測っていません（`open`）。** エージェントに別の版を読ませないなら、アクセスポイントポリシーで `<アクセスポイント ARN>/object/.snapshot/*` への `s3:GetObject` を拒否します。書き方は [S3 Access Point の認可は 2 層のどちらで絞るか](../../security-governance/notes/access-point-authorization-layers.md) にあります。

```json
{
  "Sid": "DenySnapshotDirectoryReads",
  "Effect": "Deny",
  "Principal": "*",
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:ap-northeast-1:123456789012:accesspoint/<access-point-name>/object/.snapshot/*"
}
```

---

### AWS HealthOmics との境界

HealthOmics の run の入力と出力は Amazon S3 の URI で、FSx for ONTAP の S3 Access Points は指定できません。S3 Access Points Serverless Patterns の [根拠の登録](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/agent/evidence-ledger.json) の E-009 が記録しています（`documented`）。

run のタスクに自前のファイルシステムをマウントする仕組みは、文書にありません。同じ登録の E-014 です（`open`）。ゲノム・HPC パイプラインのデータの置き場所は、[ゲノム・HPC パイプラインのデータは 3 か所に分かれる](where-genomics-pipeline-data-lives.md) にあります。

---

### 機関をまたぐ共同研究

S3 Access Points は、同じアカウントと同じリージョンのボリュームにだけ付けられます。条件は [FSx for ONTAP S3 AP は「S3 として使える」わけではない](s3-access-point-constraints.md) にあります。

別の機関のデータは、SnapMirror で受けてから、受け側のボリュームか、そのクローンにアクセスポイントを付けます。

---

### 研究者ごとのクローンのパターン

S3 Access Points Serverless Patterns の [FlexClone のサーバーレスパターン](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/guides/flexclone-serverless-patterns.md) の Pattern 4（研究データセットの分岐）が、研究者ごとに FlexClone を作って共通データを 1 コピーに保つ形を扱っています。

---

### 測っていないこと

| 項目 | 区分 |
|---|---|
| NTFS スタイルのクローンにアクセスポイントを付けること | `open` |
| クローンのアクセスポイントへの操作で CloudTrail に記録されるリソース | `open` |
| クローンのアクセスポイントから `.snapshot` の中身が読めるか | `open` |

---

## 自環境での確認手順

読み取りだけの手順です。

```bash
aws fsx describe-snapshots --filters Name=volume-id,Values=<volume-id>
```

```bash
curl -sk -u <admin-user> "https://<management-endpoint>/api/storage/volumes?clone.is_flexclone=true&fields=clone.parent_snapshot"
```

```bash
aws fsx describe-s3-access-point-attachments
```

```bash
aws s3control get-access-point-policy --account-id <account-id> --name <access-point-name> --query Policy --output text
```

### 期待結果

```text
{ "Snapshots": [ { "SnapshotId": "<snapshot-id>", "Name": "<snapshot-name>", ... } ] }
{ "records": [ { "name": "<clone-name>", "uuid": "<clone-uuid>", "clone": { "parent_snapshot": { "name": "<snapshot-name>", "uuid": "<snapshot-uuid>" } } } ] }
{ "S3AccessPointAttachments": [ { "Name": "<access-point-name>", ... } ] }
{ "Statement": [ ... ] }
```

分かることは、版ごとの Snapshot の ID と名前、クローンの元の Snapshot、クローンに付いたアクセスポイント、アクセスポイントポリシーに `.snapshot/*` の拒否があるかです。

分からないことは、クローンのアクセスポイントから `.snapshot` の中身が実際に読めるか、クローン作成にかかる時間、CloudTrail に記録されるリソースです。

---

### 参照した一次情報

| 論点 | 出典 |
|---|---|
| クローンの CloudFormation と Amazon FSx API からの作成 | [What's New 2026-11-23](https://aws.amazon.com/about-aws/whats-new/2026/11/amazon-fsx-for-netapp-ontap-additional-resources/) |
| クローンに付けた S3 Access Points の読み取りと内容の一致 | [S3-Burst on ONTAP Files: S3 Access Points の相互運用の記録](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/limits/s3ap-interoperability.md) |
| クローンの後片付けと recovery queue | [S3 Access Points Serverless Patterns: ボリュームのライフサイクルの落とし穴](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/agent/pitfalls-volume-lifecycle.md) |
| クローン作成の所要時間 | [Cyber Resilience Patterns: 復旧の測定結果](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ja/recovery-measurement-results.md) |
| 監査ログに要求者が残らないこと | [Cyber Resilience Patterns: 根拠の登録](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/agent/evidence-ledger.json) |
| 古い版の読み取り | [Cyber Resilience Patterns: 削除の依頼と削除後も残るコピー](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md) |
| HealthOmics の入出力 | [S3 Access Points Serverless Patterns: 根拠の登録](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/agent/evidence-ledger.json) |
| 研究者ごとのクローン | [S3 Access Points Serverless Patterns: FlexClone のサーバーレスパターン](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/guides/flexclone-serverless-patterns.md) |

---

### 関連ドキュメント

- [Domain — データ活用](../README.md)
- [学習データセットの版はスケジュール Snapshot に載せてよいか](dataset-versions-and-experiment-branches.md)
- [クローンを S3 Access Points につなぐまでの待ち時間は、作る経路で変わるか](a-console-clone-attaches-s3-access-points-in-minutes.md)
- [知見の分類ポリシー](../../../evidence-policy.md)

---

## Read next

[学習データセットの版はスケジュール Snapshot に載せてよいか](dataset-versions-and-experiment-branches.md)
