---
title: ブロックの監視には LUN の次元もプロトコルの次元もない — 1 ボリューム 1 LUN が監視の設計判断になる
lifecycle: [design, operate]
domains: [block-storage, performance]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
lang: ja
---

# ブロックの監視には LUN の次元もプロトコルの次元もない

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

## 結論

**CloudWatch の `AWS/FSx` 名前空間には、LUN を指す次元がありません。プロトコルを分ける次元もありません。** iSCSI の I/O と NVMe/TCP の I/O と NFS の I/O は、同じメトリクスの中で混ざります。

**ただしボリューム単位の I/O メトリクスは存在します。** そのため **1 ボリュームに 1 LUN を置く構成では、ボリュームの次元が実質的に LUN の次元になります。** これは復旧の粒度の話とは別に、**監視の粒度としての 1:1 の理由**です。

**LUN 単位の数字が要るなら ONTAP 側に聞くことになります。** `statistics lun show` と `lun show -fields size-used` があります。

そして **ONTAP 側で作ったボリュームは CloudWatch に一切現れません。**

> **区分**: `verified`（検証日 2026-09-05、`ap-northeast-1`、`MULTI_AZ_2` 第 2 世代 1 HA ペア、ONTAP 9.18.1P5）— メトリクスと次元の一覧、ONTAP 作成ボリュームの不在、`FileServer` 次元の値。
> **メトリクスの一覧は実測時点のものです。** 増えることがあります。判断の前に自環境で `list-metrics` を実行してください。

---

## 実測した次元とメトリクス

`aws cloudwatch list-metrics --namespace AWS/FSx --dimensions Name=FileSystemId,Value=<fs-id>` は **129 件**を返しました。次元の組み合わせで整理します。

| 次元 | メトリクス |
|---|---|
| `FileSystemId` | `CPUUtilization`、`DataReadBytes` / `DataWriteBytes`、`DataReadOperations` / `DataWriteOperations`、`DataReadOperationTime` / `DataWriteOperationTime`、`DiskReadBytes` / `DiskWriteBytes`、`DiskReadOperations` / `DiskWriteOperations`、`DiskIopsUtilization`、`FileServerCacheHitRatio`、`FileServerDiskIopsBalance` / `FileServerDiskThroughputBalance`、`FileServerDiskIopsUtilization` / `FileServerDiskThroughputUtilization`、`NetworkReceivedBytes` / `NetworkSentBytes`、`NetworkThroughputUtilization`、`LogicalDataStored`、`MetadataOperations`、`MetadataOperationTime`、`StorageEfficiencySavings`、`StorageUsed`、`CapacityPoolRead*` / `CapacityPoolWrite*` |
| **`FileSystemId,FileServer`** | `CPUUtilization`、`FileServerCacheHitRatio`、`FileServerDiskIopsBalance` / `FileServerDiskThroughputBalance`、`FileServerDiskIopsUtilization` / `FileServerDiskThroughputUtilization`、`NetworkReceivedBytes` / `NetworkSentBytes`、`NetworkThroughputUtilization` |
| **`FileSystemId,VolumeId`** | `DataReadBytes` / `DataWriteBytes`、`DataReadOperations` / `DataWriteOperations`、`DataReadOperationTime` / `DataWriteOperationTime`、`MetadataOperations`、`MetadataOperationTime`、`StorageCapacity`、`StorageUsed`、`StorageCapacityUtilization`、`FilesCapacity`、`FilesUsed`、`CapacityPoolRead*` / `CapacityPoolWrite*` |
| `FileSystemId,Aggregate` | `DiskReadBytes` / `DiskWriteBytes`、`DiskReadOperations` / `DiskWriteOperations`、`DiskIopsUtilization` |
| `FileSystemId,DataType,StorageTier`（`+VolumeId` / `+Aggregate`） | `StorageCapacity`、`StorageUsed`、`StorageCapacityUtilization` |

**`LUN` という次元は存在しません。** **`Protocol` に相当する次元も存在しません。**

---

## `FileServer` 次元がノードを指すこと

`FileServer` 次元の値は **ノード名そのもの**でした。

```text
FileServer = FsxId06c69f01d7b845789-01
FileServer = FsxId06c69f01d7b845789-02
```

**ここがノード単位の視点が得られる唯一の場所です。** そしてフェイルオーバーはここに現れます。ブロックの I/O が片方のノードに寄っているか、切り替わったかを見るための次元です。

**Multi-AZ で 1 HA ペアの構成では、aggregate を所有するのは片方のノードだけです。** つまり **平常時は片方の `FileServer` にほぼすべての I/O が出ます。** これはアンバランスではなく、その構成の正常な姿です。**「両ノードに均等に出ていないこと」をアラートの条件にしないでください。**

---

## LUN 単位が要るときの数え方

**ボリューム単位の I/O メトリクスが存在するので、1 ボリューム 1 LUN なら CloudWatch で LUN ごとの I/O が見えます。**

| 構成 | CloudWatch で見えるもの |
|---|---|
| 1 ボリューム 1 LUN | **その LUN の I/O と容量**（ボリュームの次元として） |
| 1 ボリュームに複数 LUN | **合計だけ。** どの LUN が使っているかは分かりません |

**復旧の粒度としての 1:1 の議論とは別に、監視の粒度としての理由がここにあります。** どちらの理由で 1:1 を選んだのかを設計文書に書き分けてください。復旧の粒度の話は [LUN の並べ方が決めているのは復旧の粒度](lun-layout-decides-recovery-granularity.md) にあります。

複数 LUN を 1 ボリュームに置く構成で LUN ごとの数字が要るなら、ONTAP 側にあります。

| 見たいもの | コマンド |
|---|---|
| LUN ごとの I/O カウンタ | `statistics lun show -vserver <svm>` |
| LUN の使用量と予約 | `lun show -vserver <svm> -fields path,size,size-used,space-reserve` |
| iSCSI のセッション | `vserver iscsi session show -vserver <svm> -fields lif,initiator-name,tpgroup` |
| NVMe のコントローラ | `vserver nvme subsystem controller show` |

**これらは CloudWatch には流れません。** ONTAP に接続して取る仕組みを別に作ることになります。

---

## ONTAP 側で作ったボリュームは監視に現れないこと

検証環境で、AWS の API で 2 ボリューム、ONTAP の CLI で 2 ボリュームを作りました。

| 数え方 | 結果 |
|---|---|
| `aws fsx describe-volumes` | **3 件**（root ボリューム + AWS で作った 2 件） |
| ONTAP の `volume show` | **5 件** |
| `aws cloudwatch list-metrics` の `VolumeId` の値 | **3 件**（`fsvol-` で始まる ID のみ） |

**ONTAP で作ったボリュームには `fsvol-` の ID が付きません。** 帰結です。

| 影響 | 内容 |
|---|---|
| CloudWatch | **`VolumeId` 次元に現れません。** 容量も I/O も監視できません |
| タグ | AWS の API でタグを付けられません |
| AWS Backup | 選択できません |
| コスト配分 | タグが無いので配分できません |

**ブロックの構築では ONTAP 側にしか作れないオブジェクトがあります**（LUN、igroup、namespace、subsystem）。**しかしボリューム自体は AWS の API でも作れます。** 監視とバックアップを AWS 側で回すなら、**ボリュームは AWS の API で作り、その中の LUN だけを ONTAP 側で作るのが噛み合う形です。**

この境界の全体像は [LUN と igroup は AWS の API の外側にある](block-objects-are-outside-the-aws-api.md) にあります。

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `aws cloudwatch list-metrics --namespace AWS/FSx --dimensions Name=FileSystemId,Value=<fs-id>` | **その時点で存在する次元とメトリクスの全量。増えていることがあります** |
| 2 | 上の結果を次元の組み合わせで集約する | **LUN やプロトコルの次元が増えていないか** |
| 3 | `list-metrics --metric-name CPUUtilization` で `FileServer` の値を見る | ノード名。**フェイルオーバーを見る足場** |
| 4 | `aws fsx describe-volumes` の件数と ONTAP の `volume show` の件数を比べる | **AWS から見えていないボリュームの有無** |
| 5 | `statistics lun show -vserver <svm>` | ONTAP 側の LUN ごとのカウンタ |
| 6 | 1 ボリュームに複数 LUN がある場合、`VolumeId` 次元の `DataWriteBytes` と各 LUN の書き込みを突き合わせる | **合計しか見えないことの確認** |

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| CloudWatch で LUN ごとの I/O が見える | **LUN の次元はありません。** ボリュームの次元までです |
| iSCSI の I/O だけを CloudWatch で分離できる | **プロトコルの次元はありません** |
| ボリューム単位では容量しか見えない | **I/O メトリクスもあります。** `DataReadBytes` などが `VolumeId` 次元を持ちます |
| 1 ボリューム 1 LUN は復旧の粒度のための話 | **監視の粒度としての理由もあります。** ボリューム次元が LUN 次元の代わりになります |
| ノード単位では見られない | **`FileServer` 次元があります。** 値はノード名です |
| ノード間で I/O が偏っていたら異常 | **1 HA ペアでは aggregate を片方が所有します。** 偏るのが正常です |
| ONTAP で作ったボリュームも CloudWatch に出る | **出ません。** `fsvol-` の ID が無いためです |
| ブロックだからボリュームも ONTAP 側で作るしかない | **ボリュームは AWS の API で作れます。** ONTAP 側でしか作れないのは LUN・igroup・namespace・subsystem です |

---

## 検証環境

| 項目 | 値 |
|---|---|
| ONTAP バージョン | 9.18.1P5 |
| リージョン | `ap-northeast-1` |
| デプロイタイプ | `MULTI_AZ_2`（第 2 世代、1 HA ペア） |
| スループット容量 | 384 MBps |
| ボリューム | AWS の API で 2 件、ONTAP の CLI で 2 件 |
| `list-metrics` の件数 | 129 |
| 検証日 | 2026-09-05 |

> **注意**: メトリクスと次元は追加されることがあります。**この一覧は 2026-09-05 時点の実測です。** 「無い」という判断を再利用する前に、自環境で `list-metrics` を実行してください。

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| `AWS/FSx` 名前空間のメトリクスと次元の定義 | [AWS: Monitoring with Amazon CloudWatch](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-cloudwatch.html) |
| 詳細モニタリングでボリューム単位・aggregate 単位のメトリクスが増えること | [AWS: FSx for ONTAP metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/fsx-ontap-metrics.html) |
| ONTAP の LUN 統計 | [NetApp: statistics lun show](https://docs.netapp.com/us-en/ontap-cli/statistics-lun-show.html) |
| ONTAP の LUN の使用量と予約 | [NetApp: lun show](https://docs.netapp.com/us-en/ontap-cli/lun-show.html) |
| iSCSI セッションの確認 | [NetApp: vserver iscsi session show](https://docs.netapp.com/us-en/ontap-cli/vserver-iscsi-session-show.html) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [LUN と igroup は AWS の API の外側にある](block-objects-are-outside-the-aws-api.md) — 制御面の境界の全体像
- [LUN の並べ方が決めているのは復旧の粒度](lun-layout-decides-recovery-granularity.md) — 1:1 のもう 1 つの理由
- [Multi-AZ が動かすのはアドレスではなくルート](multi-az-moves-a-route-not-an-address.md) — `FileServer` 次元で見る対象
- [パスはフェイルオーバーの仕組みそのもの](paths-are-the-failover-mechanism.md) — ホスト側から見た切り替わり
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)
