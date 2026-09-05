---
title: Multi-AZ が動かすのはアドレスではなくルート — ブロックのアドレスは動かないので Transit Gateway も不要
lifecycle: [design, build, operate]
domains: [block-storage, performance]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
lang: ja
---

# Multi-AZ が動かすのはアドレスではなくルート

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

## 結論

**Multi-AZ の FSx for ONTAP には、動くアドレスと動かないアドレスがあります。ブロックのアドレスは動かない側です。**

NFS・SMB・管理のアドレスは VPC の CIDR の外にある floating アドレスで、フェイルオーバーのときに **VPC ルートテーブルの `/32` エントリのターゲット ENI が書き換わります。** アドレスがサブネット内を移動するのではありません。

**iSCSI と NVMe/TCP のアドレスは VPC の CIDR 内の普通のプライベートアドレスで、AZ ごとに 1 つ、ENI に直接載っています。** `failover-policy` は `disabled` で、ノードに固定されていて移動しません。

帰結が 3 つあります。

| 帰結 | 内容 |
|---|---|
| ピアリング越しに届く | ブロックのアドレスは VPC CIDR 内なので、**Transit Gateway を要求する条件に当たりません** |
| 可用性はホスト側の仕組み | LIF が動かないので、**切り替えるのはホストの multipath です** |
| 最適パスは AZ で決まらない | **ALUA / ANA の optimized は「ボリュームを所有するノード」側です。** クライアントの AZ とは無関係 |

> **区分**: `verified`（検証日 2026-09-05、`ap-northeast-1`、`MULTI_AZ_2` 第 2 世代 1 HA ペア、384 MBps、ONTAP 9.18.1P5）— アドレスの配置、`failover-policy`、ルートテーブルの書き換え、ALUA の優先度の向き。
> **性能値は含めません。**

---

## アドレスの配置

エンドポイント IP アドレス範囲は **`198.19.174.0/24`** が自動で割り当てられました。VPC の CIDR は `10.0.x.x` の /16 なので、**この範囲は VPC の外側です。**

| LIF | アドレス | VPC CIDR 内か | `failover-policy` |
|---|---|---|---|
| `fsxadmin`（クラスタ管理） | 198.19.174.43 | **いいえ** | `broadcast-domain-wide` |
| `inter_1`（intercluster、ノード -01） | `<intercluster-1a>` | はい | **`disabled`** |
| `inter_2`（intercluster、ノード -02） | `<intercluster-1c>` | はい | **`disabled`** |
| `iscsi_1`（ノード -01） | `<iscsi-1a>` | はい | **`disabled`** |
| `iscsi_2`（ノード -02） | `<iscsi-1c>` | はい | **`disabled`** |
| `nfs_smb_management_1` | 198.19.174.120 | **いいえ** | `sfo-partner-only` |

ENI は AZ ごとに 1 本、**それぞれプライベートアドレスを 2 つだけ**持っていました。

| ENI | AZ | 載っているアドレス |
|---|---|---|
| `eni-081931…` | `ap-northeast-1a`（preferred） | `<intercluster-1a>`（intercluster）、`<iscsi-1a>`（iSCSI） |
| `eni-0c290c…` | `ap-northeast-1c`（standby） | `<intercluster-1c>`（intercluster）、`<iscsi-1c>`（iSCSI） |

**floating アドレスはどの ENI にも載っていません。** 関連付けたルートテーブルの `/32` エントリとして存在し、ターゲットが ENI になっています。

```text
198.19.174.43/32   -> eni-081931…   (クラスタ管理)
198.19.174.120/32  -> eni-081931…   (SVM の NFS / SMB / 管理)
```

**SVM の NFS / SMB / 管理の LIF は 1 本です。** AZ ごとに 1 本ではありません。

---

## フェイルオーバーで書き換わるもの

スループット容量を 384 → 768 MBps に変更してフェイルオーバーを誘発し、5 秒間隔でルートテーブルを見た結果です。

| 時刻（UTC） | `198.19.174.120/32` のターゲット |
|---|---|
| 07:27:40（変更を要求） | 1a の ENI |
| 07:28:10 → 07:28:31 の間 | **1c の ENI に書き換わる** |
| 07:39:26 → 07:39:52 の間 | **1a の ENI に戻る** |

**この間、iSCSI の 2 つのアドレスはそれぞれの ENI から動いていません。**

**これが、クライアント側の ARP 調整の話が Single-AZ に限定して書かれている理由です。** AWS はフェイルオーバー検知を 55〜60 秒から 15〜20 秒に短縮する `sysctl` の設定を示していますが、**その対象は Single-AZ のファイルシステムで、内容は ARP キャッシュの有効期間と近隣探索の調整です。** Single-AZ では floating アドレスが同じサブネット内でノード間を移動するので、クライアントは MAC アドレスの対応を学び直す必要があります。**Multi-AZ ではルートテーブルが書き換わるので、この調整が効く場面ではありません。**

**そして iSCSI にはどちらも関係しません。** アドレスが動かないので、学び直す対象がありません。

---

## Transit Gateway が要る条件と、ブロックが当たらない理由

AWS は Transit Gateway の追加設定が必要な条件を、**「エンドポイント IP アドレス範囲が VPC の CIDR の外側にある Multi-AZ ファイルシステム」**と書いています。VPC CIDR 内なら追加設定は不要です。

**検証環境ではエンドポイント範囲が VPC の外側でした**（`198.19.174.0/24`）。つまり **NFS / SMB / 管理はこの条件に当たります。** 一方 **iSCSI と NVMe/TCP のアドレスは VPC CIDR 内なので当たりません。**

AWS のクライアント要件の表も、Transit Gateway が必要かという問いに対して **iSCSI と NVMe/TCP を「No」**としています。

**ピアリング先から使う設計では、この区別が構成を変えます。**

| 使うプロトコル | ピアリング越しの追加要件 |
|---|---|
| iSCSI / NVMe/TCP のみ | **VPC ピアリングで届きます。** ルートテーブルへの追加は不要 |
| NFS / SMB / ONTAP 管理を含む | エンドポイント範囲が VPC 外なら **Transit Gateway と、その範囲へのルートが必要**。Transit Gateway のアタッチメントを置くサブネットのルートテーブルを、ファイルシステムに関連付ける必要もあります |

**ブロックだけを使うなら経路の要件は素直です。** ただし **ONTAP の管理を同じ経路から行うなら管理 LIF は floating 側なので、そちらの要件が残ります。**

---

## 最適パスの向き

**1 HA ペアの構成では aggregate が 1 つしかありません。** 検証環境の `aggr1` はノード -01（1a 側）が所有し、**すべてのボリュームがそこにありました。** ノード -02 はフェイルオーバーまで何も所有しません。

`lun mapping show -fields reporting-nodes` は所有ノードと HA パートナーの 2 ノードを列挙します。だから **パスは 2 本**になります。

2 つの AZ にクライアントを置いて、同じ LUN の優先度を比べました。

| クライアントの AZ | `<iscsi-1a>`（1a の LIF）経由 | `<iscsi-1c>`（1c の LIF）経由 |
|---|---|---|
| `ap-northeast-1a` | **prio=50 active** | prio=10 enabled |
| `ap-northeast-1c` | **prio=50 active** | prio=10 enabled |

**どちらのクライアントも、optimized なパスは 1a の LIF でした。** ボリュームを所有するノードがそこにあるからです。

**standby AZ にクライアントを置いても、そのクライアントのブロックアクセスがローカルになるわけではありません。** 同一 AZ 側のパスが non-optimized になり、**通常の I/O は AZ をまたぎます。** レイテンシと AZ 間のデータ転送の両方に効きます。

NVMe/TCP も同じ向きでした。ネイティブ multipath が無効なカーネルでも、コントローラごとに ANA の状態は読めます。

```text
nvme ana-log /dev/nvme3   (traddr=<iscsi-1a>)  ->  state: optimized
nvme ana-log /dev/nvme2   (traddr=<iscsi-1c>)  ->  state: non-optimized
```

**デバイス名の順番は optimized かどうかを表しません。** 検証環境では non-optimized 側が先に `/dev/nvme2n1` として現れました。

---

## Multi-AZ で使える容量

`set -unit B` での実測です。

| 項目 | バイト | 備考 |
|---|---|---|
| SSD プロビジョニング | — | 1,024 GiB を要求 |
| `aggr1` のサイズ | 925,224,214,528 | **861.7 GiB** |
| `aggr1` の空き（空の状態） | 922,878,918,656 | |

**ラウンド 1 の Single-AZ 環境では、同じ 1,024 GiB から aggregate が 907.03 GiB でした。** Multi-AZ では 861.7 GiB です。

**2 つの環境の差はデプロイタイプですが、それ以外の要因を切り分ける検証はしていません。** 「Multi-AZ では同じプロビジョニング容量から使える量が少なかった」という 2 環境の観測です。**容量設計では自環境で数えてください。**

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `aws fsx describe-file-systems --query 'FileSystems[0].OntapConfiguration.EndpointIpAddressRange'` | **その範囲が VPC CIDR の内か外か。Transit Gateway の要否がここで決まります** |
| 2 | `aws fsx describe-storage-virtual-machines --query 'StorageVirtualMachines[].Endpoints'` | iSCSI のアドレスが VPC CIDR 内にあること。**`Nvme` は `null` で返ります**（後述） |
| 3 | `aws ec2 describe-network-interfaces --network-interface-ids <fs の ENI>` | ENI に載っているアドレスと、載っていないアドレスの区別 |
| 4 | 関連付けたルートテーブルで `/32` のエントリとそのターゲット ENI を確認する | **floating アドレスの実装** |
| 5 | `network interface show -fields address,home-node,failover-policy` | **iSCSI が `disabled` であること** |
| 6 | 2 つの AZ からそれぞれ接続し、`multipath -ll` の prio を比べる | **optimized がどちらの AZ を向いているか** |
| 7 | `storage aggregate show -fields aggregate,node` | 1 HA ペアなら aggregate は 1 つで、片方のノードが所有します |
| 8 | `nvme ana-log /dev/nvmeN` をコントローラごとに実行する | **ネイティブ multipath が無いカーネルでの optimized の判別** |

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| Multi-AZ ではフェイルオーバー時にアドレスがノード間を移動する | **移動するのはルートテーブルの `/32` のターゲットです** |
| iSCSI のアドレスもフェイルオーバーで移動する | **移動しません。** `failover-policy` は `disabled` です |
| Multi-AZ をピアリング越しに使うには Transit Gateway が必要 | **エンドポイント範囲が VPC 外のときだけです。** ブロックのアドレスは VPC 内なので当たりません |
| クライアント側の `sysctl` 調整でブロックのフェイルオーバーも速くなる | **あの調整は Single-AZ の NFS 向けで、ARP の学び直しを速くするものです。** アドレスが動かない iSCSI には効く場面がありません |
| standby AZ にクライアントを置けばローカルアクセスになる | **optimized はボリューム所有ノード側です。** 通常 I/O が AZ をまたぎます |
| iSCSI の LIF は AZ ごとに複数ある | **AZ ごとに 1 本、SVM 単位で計 2 本でした** |
| NFS の LIF も AZ ごとにある | **SVM に 1 本です** |
| AWS の API で NVMe のエンドポイントが取れる | **`Nvme` は `null` で返りました。** ONTAP 側に聞く必要があります |
| Multi-AZ でも使える容量は Single-AZ と同じ | **同じ 1,024 GiB から 861.7 GiB と 907.03 GiB でした**（2 環境の観測） |

---

## 検証環境

| 項目 | 値 |
|---|---|
| ONTAP バージョン | 9.18.1P5 |
| リージョン | `ap-northeast-1` |
| デプロイタイプ | `MULTI_AZ_2`（第 2 世代、1 HA ペア） |
| スループット容量 | 384 MBps（測定後に 768 MBps へ変更） |
| SSD 容量 | 1,024 GiB、`AUTOMATIC` IOPS = 3,072 |
| VPC CIDR | `10.0.x.x` の /16 |
| preferred サブネット | `ap-northeast-1a`（`10.0.0.x` 側の /20） |
| standby サブネット | `ap-northeast-1c`（`10.0.16.x` 側の /20） |
| エンドポイント IP 範囲 | `198.19.174.0/24`（自動割り当て） |
| クライアント | Amazon Linux 2023、kernel 6.18.44-99.149.amzn2023.x86_64、各 AZ に 1 台 |
| 検証日 | 2026-09-05 |

> **注意**: 上記はこの環境での実測です。**エンドポイント IP 範囲は作成時に指定でき、VPC CIDR 内にすることもできます。** 自動割り当ての結果が VPC 外だったのはこの環境での事実であって、常にそうなるという意味ではありません。

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| エンドポイント範囲が VPC CIDR の外側にある Multi-AZ で Transit Gateway の追加ルートが必要なこと。VPC CIDR 内なら不要なこと。アタッチメントのサブネットのルートテーブルを関連付ける必要があること | [AWS: Configure routing to access Multi-AZ file systems from on-premises](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configure-routing-maz-on-prem.html) |
| iSCSI と NVMe/TCP が Transit Gateway を要求しないこと | [AWS: Supported clients and access methods](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-fsx-clients.html) |
| Single-AZ の NFS クライアント向けの `sysctl` 調整（`base_reachable_time_ms`、`delay_first_probe_time`、`ucast_solicit`、`tcp_syn_retries`）と、検知時間が 55〜60 秒から 15〜20 秒になること | [AWS: Troubleshooting I/O errors and NFS lock reclaim failures](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/nfs-failover-issues.html) |
| フェイルオーバーの契機が 4 つあること、通常 60 秒未満で完了すること、Multi-AZ では preferred が復旧すると自動でフェイルバックすること | [AWS: Availability, durability, and deployment options](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/high-availability-AZ.html) |
| スループット容量の変更でフェイルオーバーを試験できること、ファイルサーバーが直列に置き換わること | [AWS: Managing throughput capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-throughput-capacity.html) |
| Selective LUN Map が reporting node を所有ノードと HA パートナーに絞ること | [NetApp: Selective LUN Map](https://docs.netapp.com/us-en/ontap/san-admin/selective-lun-map-concept.html) |
| ONTAP が iSCSI で ALUA、NVMe で ANA を使うこと | [NetApp: Multipathing](https://docs.netapp.com/us-en/ontap/san-config/host-support-multipathing-concept.html) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [パスはフェイルオーバーの仕組みそのもの](paths-are-the-failover-mechanism.md) — この配置の上で実際に測ったフェイルオーバー
- [ブロックプロトコルの選択肢は世代と HA ペア数で先に狭まる](protocol-choice-is-bounded-before-you-choose.md) — LIF とポートの前提
- [ブロックの監視で見えるものと見えないもの](what-block-monitoring-shows.md) — `FileServer` 次元でノードの切り替わりを見る
- [デプロイタイプは一度しか決められない](../../../playbooks/02-design/notes/deployment-type-is-decided-once.md)
- [ブロックストレージ横断リソースマップ](../../../reference/block-storage-resource-map.md)
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)
