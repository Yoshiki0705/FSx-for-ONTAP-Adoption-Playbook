---
title: ブロックの監視には LUN の次元もプロトコルの次元もない — 1 ボリューム 1 LUN が監視の設計判断になる
lifecycle: [design, operate]
domains: [block-storage, performance]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
deployment_type: MULTI_AZ_2
lang: ja
---

# ブロックの監視には何が見えないか？

LUN の次元もプロトコルの次元もありません。だから 1 ボリューム 1 LUN が監視の設計判断になります。

<!-- lang-switcher:start -->
🌐 [日本語](what-block-monitoring-shows.md) | [English](../../../../en/domains/block-storage/notes/what-block-monitoring-shows.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->

## このノートで学べること

- CloudWatch の `AWS/FSx` に LUN 次元もプロトコル次元もなく、1 ボリューム 1 LUN でボリューム次元が LUN 次元の代わりになること
- ONTAP 側で作ったボリュームは CloudWatch にも AWS Backup にも現れないこと

## このノートが答えないこと

- フェイルオーバー中に `FileServer` 次元がどう動くか（測っていない）
- ボリューム操作時間メトリクスからテール（p99）を出せるか（平均のみ、別ノート参照）

## 前提レベル

intermediate

## 本文

<a id="ブロックの監視には-lun-の次元もプロトコルの次元もない"></a>

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

### 結論

**CloudWatch の `AWS/FSx` 名前空間には、LUN を指す次元がありません。プロトコルを分ける次元もありません。** iSCSI の I/O と NVMe/TCP の I/O と NFS の I/O は、同じメトリクスの中で混ざります。

**ただしボリューム単位の I/O メトリクスは存在します。** そのため **1 ボリュームに 1 LUN を置く構成では、ボリュームの次元が実質的に LUN の次元になります。** これは復旧の粒度の話とは別に、**監視の粒度としての 1:1 の理由**です。

**ただし置き換わるのは粒度だけで、統計の種類は置き換わりません。** ボリュームの `DataReadOperationTime` / `DataReadOperations`、`DataWriteOperationTime` / `DataWriteOperations`、`MetadataOperationTime` / `MetadataOperations` は合計値で、有効な統計は `Sum` です。**各ペアから出せるレイテンシは平均で、テールは出せません**（[ボリュームの操作時間メトリクスから p99 は出せない](../../performance/notes/what-you-cannot-read-from-cloudwatch.md)）。ほかのボリューム容量メトリクスには `Average` や `Maximum` を取るものもあるため、ボリュームメトリクス全体を `Sum` のみとは扱いません。

**LUN 単位の数字が要るなら ONTAP 側に聞くことになります。** `statistics lun show` と `lun show -fields size-used` があります。

そして **ONTAP 側で作ったボリュームは CloudWatch に一切現れません。**

> **区分**: `verified`（検証日 2026-09-05、`ap-northeast-1`、`MULTI_AZ_2` 第 2 世代 1 HA ペア、ONTAP 9.18.1P5）— メトリクスと次元の一覧、ONTAP 作成ボリュームの不在、`FileServer` 次元の値。
> **メトリクスの一覧は実測時点のものです。** 増えることがあります。判断の前に自環境で `list-metrics` を実行してください。

---

### 実測した次元とメトリクス

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

### `FileServer` 次元がノードを指すこと

`FileServer` 次元の値は **ノード名そのもの**でした。

```text
FileServer = FsxIdEXAMPLE-01
FileServer = FsxIdEXAMPLE-02
```

**ここがノード単位の視点が得られる唯一の場所です。** 確認したのは次元の値がノード名であることまでで、**フェイルオーバー中にこの次元がどう動くかは測っていません。** [実測したフェイルオーバー](paths-are-the-failover-mechanism.md#実測したフェイルオーバー) は `nvme ana-log` とマルチパスとルートテーブルで観測したもので、CloudWatch 側では記録していません。

平常時にどちらのノードに I/O が出るかも測っていません。**片ノードに寄った利用率をどう読むかは、[監視は平均値で失敗する](../../../playbooks/05-operate/notes/monitoring-fails-on-averages.md) が preferred / standby の設計から説明しています。**

---

### LUN 単位が要るときの数え方

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
| **NVMe/TCP の経路別バイト数** | **`nvmf_tcp_port` のカウンタ。** `nvmf_lif` と `lif` では取れません（下記） |

**これらは CloudWatch には流れません。** ONTAP に接続して取る経路が別に必要になります。**自作する前に [可観測性](../../observability/) の経路の比較を見てください** — NetApp Harvest の サポート対象ダッシュボードには LUN のものが含まれ、NVMe Namespaces は既定で無効なだけです（[オンプレのダッシュボードはそのまま移らない](../../observability/notes/on-prem-dashboards-do-not-transfer.md)）。自作は「欲しい値が数個だけ」のときの選択肢です。

---

### NVMe/TCP の経路別バイト数を持つテーブルが 1 つだけであること（引用）

**当方の検証ではありません。** 以下は sibling repo の実測の転記です。

**2 本目のパスが実際にトラフィックを運んでいるかを ONTAP 側で確かめるとき、名前から先に試す 2 つが
どちらも空を返します。**

| テーブル | NVMe/TCP のトラフィックに対する挙動 |
|---|---|
| `nvmf_lif` | **行を 0 件返す。** 600 GiB を書いたあとでも空 |
| `lif` | 2 本の LIF を **0 バイト**と報告する（NVMe-oF を数えていない） |
| **`nvmf_tcp_port`** | **実データを持つ。** 経路ごとに読み・書きのバイト数と ops |

**どちらの空も「トラフィックが無い」と同じ見え方をします。** 引用元は `nvmf_tcp_port` の差分で、
optimized 側に約 1,012 GiB の読みと 730 GiB の書き、**non-optimized 側に ±0 バイト**を割り当てて
います（[引用元の測定結果](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md)）。

**クライアント側の出力は代わりになりません。** `nvme list-subsys` は経路が 2 本あることを示しますが、
**2 本使っていることは示しません。**

> **0 行を 0 として報告しないこと。** 「テーブルはあるが空」と「このバージョンにそのテーブルは無い」は、
> 合計すると同じ見え方になります。**取得側は 0 行で失敗させてください。**
> これは監視の作り方の話で、[可観測性](../../observability/) の経路にも同じことが言えます。

> **区分**: `documented`（sibling repo の実測の引用、ONTAP 9.18.1、`ap-northeast-1`）。
> **`nvmf_lif` が空である理由は引用元でも未解明**で、ベンダーへの確認事項として残っています。
> **「NVMe-oF では per-LIF カウンタが取れない仕様」と読まないでください。**

---

### ONTAP 側で作ったボリュームは監視に現れないこと

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

### よくある誤解

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
| NVMe/TCP の経路別バイト数は `nvmf_lif` で取れる | **行を 0 件返します**（引用）。`lif` は NVMe-oF を数えません。実データは `nvmf_tcp_port` です |

---

### 検証環境

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

### 参照した一次情報

| 論点 | 出典 |
|---|---|
| `AWS/FSx` 名前空間のメトリクスと次元の定義 | [AWS: Monitoring with Amazon CloudWatch](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-cloudwatch.html) |
| 詳細モニタリングでボリューム単位・aggregate 単位のメトリクスが増えること | [AWS: FSx for ONTAP metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/fsx-ontap-metrics.html) |
| ONTAP の LUN 統計 | [NetApp: statistics lun show](https://docs.netapp.com/us-en/ontap-cli/statistics-lun-show.html) |
| ONTAP の LUN の使用量と予約 | [NetApp: lun show](https://docs.netapp.com/us-en/ontap-cli/lun-show.html) |
| iSCSI セッションの確認 | [NetApp: vserver iscsi session show](https://docs.netapp.com/us-en/ontap-cli/vserver-iscsi-session-show.html) |

---

### 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [LUN と igroup は AWS の API の外側にある](block-objects-are-outside-the-aws-api.md) — 制御面の境界の全体像
- [LUN の並べ方が決めているのは復旧の粒度](lun-layout-decides-recovery-granularity.md) — 1:1 のもう 1 つの理由
- [Multi-AZ が動かすのはアドレスではなくルート](multi-az-moves-a-route-not-an-address.md) — `FileServer` 次元で見る対象
- [パスはフェイルオーバーの仕組みそのもの](paths-are-the-failover-mechanism.md) — ホスト側から見た切り替わり
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `list-metrics` で `AWS/FSx` の次元とメトリクスの全量を取る | **その時点で存在する次元とメトリクスの全量。増えていることがあります** |
| 2 | 上の結果を次元の組み合わせで集約する | **LUN やプロトコルの次元が増えていないか** |
| 3 | `CPUUtilization` の `FileServer` の値を見る | ノード名。**フェイルオーバーを見る足場** |
| 4 | `aws fsx describe-volumes` の件数と ONTAP の `volume show` の件数を比べる | **AWS から見えていないボリュームの有無** |
| 5 | `statistics lun show -vserver <svm>` | ONTAP 側の LUN ごとのカウンタ |
| 6 | 1 ボリュームに複数 LUN がある場合、`VolumeId` 次元の `DataWriteBytes` と各 LUN の書き込みを突き合わせる | **合計しか見えないことの確認** |

手順 4 の「AWS から見えないボリューム」は、次の読み取り専用コマンドの件数を ONTAP の `volume show` と比べて確認します。

```bash
aws fsx describe-volumes --query 'length(Volumes)'
```

### 期待結果

```text
aws fsx describe-volumes の件数が ONTAP の volume show より少ないことがある。
ONTAP 側で作ったボリュームは fsvol- の ID を持たず、CloudWatch にも AWS Backup にも現れない
```

このコマンドはボリュームを数えるだけで、ボリュームにもメトリクスにも変更を加えません。LUN やプロトコルの次元は現時点では存在しないため、LUN ごとの数字は ONTAP 側で取ります。

## Read next

[NVMe/TCP は AWS 側の面から抜けているか？](nvme-tcp-is-thin-on-the-aws-side.md)
