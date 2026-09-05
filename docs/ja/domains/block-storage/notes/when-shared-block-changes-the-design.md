---
title: 共有ブロックが設計を変える条件 — 単独接続で足りるなら持ち込む理由はない
lifecycle: [assess, design]
domains: [block-storage, cost, performance]
evidence: documented
source: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volumes-multi.html
lang: ja
---

# 共有ブロックが設計を変える条件

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

## 結論

**FSx for ONTAP をブロックストレージとして選ぶ理由は、速さではなく構造です。** そして構造が効かない要件では、Amazon EBS のほうが素直です。

**単一の EC2 インスタンスだけが使うディスクに FSx for ONTAP を充てる理由はありません。** 最小構成でも SSD 1,024 GiB とスループット容量 384 MBps が立ち、東京リージョンの On-Demand で月あたり約 $927 になります。数十 GiB のデータ領域に対してこれは釣り合いません。

**構造が効くのは次の 4 つが要件に含まれるときです。**

1. 同じデータを**ファイル共有としても**出す
2. Snapshot を**世代数を気にせず**持ちたい
3. LUN を含むデータを**別リージョンへ複製**したい
4. 本番の複製を**実データのコピーなしで**作りたい

そして FSx for ONTAP 側のトレードオフも対称に置きます。**HA ペア 6 組の天井があり、ホスト側の multipath と書き込み整合性は利用者の責任として残り、制御面が AWS と ONTAP の 2 つになります。**

> **区分**: `documented` — 各サービスの制約と上限は AWS / NetApp 公式ドキュメントの記載に基づきます（2026-09-05 に確認）。最小構成コストは Price List API から同日取得しました。
> **性能の比較は含めません。** 公開されている数値の読み方は [公開ベンチマークの読み方](#公開ベンチマークの読み方) にあります。
> 自環境での確認手順は [自環境での確認手順](#自環境での確認手順) にあります。

---

## 単独接続で足りる場合の判断

**「ブロックストレージが必要」は「共有ブロックが必要」ではありません。** ここを分けないまま FSx for ONTAP を検討すると、要件に対して過剰な構成になります。

| 要件 | 素直な選択 | 理由 |
|---|---|---|
| 起動ディスク | Amazon EBS | **FSx for ONTAP の LUN は起動ディスクにできません。** ブロックプロトコルはゲスト OS が起動した後に確立されます |
| 1 インスタンス専用のデータ領域 | Amazon EBS | 共有の調停もファイル共有も不要で、制御面が EC2 だけで済みます |
| 一時的な作業領域 | インスタンスストア | 永続性が不要なら最も速く、追加コストがありません |
| 同一 AZ・2 ノードのクラスタで、Snapshot はホスト側でよい | Amazon EBS Multi-Attach | EC2 の制御面だけで済みます。`io2` なら NVMe reservation による I/O fencing に対応します |

**AWS Transform でブロックストレージを移行する場合も、起動ボリュームは EBS のまま残り、データボリュームが iSCSI で接続されます。** この分担は移行後もそのままです。詳細は [直近のアップデートと設計への影響](../../../reference/recent-updates.md) にあります。

---

## 構造が効く 4 つの条件

### ファイルとブロックが同じストレージから出ること

**同一のファイルシステム・SVM から NFS・SMB・iSCSI・NVMe/TCP・S3 Access Point を同時に提供できます。** 同じデータセットを分析基盤には NFS で見せ、データベースには LUN で見せる、という構成が 1 台で組めます。

**ただしボリュームの粒度では話が変わります。** NetApp は **SAN の LUN と NAS 共有を同じ FlexVol に混在させることを推奨していません。** 技術的に不可能なのではなく、容量計算と Snapshot の扱いが両者で異なるためです。**「1 台で両方出せる」は正しく、「1 ボリュームで両方出すのが普通」は誤りです。**

### Snapshot が確保済み容量を消費すること

FSx for ONTAP の Snapshot は、**すでに確保している SSD 容量を消費します。別建ての課金項目にはなりません。** Amazon EBS の Snapshot は GB-月で別に課金されます。

**世代を多く持つ設計では、この差が積み上がります。** 一方で、**容量を食うという事実は消えません。** SSD が満杯になると LUN が read-only に落ちるという別の失敗経路が現れます。そちらは [容量は 3 か所で数えられる](capacity-is-counted-in-three-places.md) の範囲です。

### SnapMirror がボリューム単位で動くこと

**LUN を含むボリュームをそのまま別のファイルシステムへ複製できます。** ホストを経由しないため、複製のためにアプリケーションを止める必要がありません。

**宛先で LUN がそのまま使えるわけではありません。** 宛先ボリュームを書き込み可能にした後、**LUN を igroup にマップし、ホストから iSCSI セッションを張り、再スキャンする**必要があります。**igroup のマッピングはデータと一緒に移りません。**

### FlexClone が実データをコピーしないこと

**本番 LUN の書き込み可能な複製を、実データのコピーなしで作れます。** Amazon EBS では Snapshot から新しいボリュームを作る形になり、コピーが発生します。

AWS は SQL Server の文脈で、**1 TB のデータベースの iSCSI LUN のクローンが通常 5 分以内で完了する**と記載しています。ただしこの数値は構成に依存します。

---

## FSx for ONTAP 側のトレードオフ

**上の 4 つと同じ重みで置きます。** 該当する要件がないなら、これらは払う必要のないコストです。

| トレードオフ | 内容 | 逃げ道 |
|---|---|---|
| **HA ペア 6 組の天井** | 7 組目を追加した時点で iSCSI と NVMe/TCP が使えなくなります。**追加した HA ペアは削除できません** | 6 組を上限に設計する。詳細は [デプロイタイプは一度しか決められない](../../../playbooks/02-design/notes/deployment-type-is-decided-once.md) |
| **ホスト側 multipath の責任** | パスの構成・タイムアウト・切り替わりの確認はホスト側の作業です | 手順は文書化されています。[パスはフェイルオーバーの仕組みそのもの](paths-are-the-failover-mechanism.md) |
| **書き込み整合性の責任** | 複数ホストから同じ LUN に書くとき、調停はホスト側のクラスタ機能が行います | Amazon EBS Multi-Attach でも同じです。**共有ブロックに共通の性質です** |
| **制御面が 2 つ** | LUN・igroup・NVMe subsystem は AWS の API に存在しません | [LUN と igroup は AWS の API の外側にある](block-objects-are-outside-the-aws-api.md) |
| **既定の Snapshot は crash-consistent** | アプリケーションを静止させる仕組みは別に必要です | [LUN の Snapshot は既定で crash-consistent](a-snapshot-of-a-lun-is-crash-consistent.md) |
| **最小構成のコスト** | SSD 1,024 GiB + スループット 384 MBps が下限です | 小さい要件には Amazon EBS を使う |
| **NVMe/TCP は第 2 世代のみ** | 第 1 世代では作り直し以外に道がありません。Windows 向けの手順も見当たりません | [ブロックプロトコルの選択肢は世代と HA ペア数で先に狭まる](protocol-choice-is-bounded-before-you-choose.md) |
| **スループットは HA ペア単位で共有** | NFS・SMB・S3 Access Point と同じ帯域を分け合います | [スループットは 1 つの設定値では決まらない](../../performance/notes/where-throughput-is-determined-and-shared.md) |

---

## 公開ベンチマークの読み方

**FSx for ONTAP のブロック性能について最もよく引用される数値は「100 万 IOPS」です。この数値は 1 つのファイルシステムのものではありません。**

AWS Storage Blog の [SAN: A million IOPs in AWS from Amazon FSx NetApp ONTAP](https://aws.amazon.com/blogs/storage/san-a-million-iops-in-aws-from-amazon-fsx-netapp-ontap/) は 2022-09-08 の記事で、測定条件は次のとおりです。 <!-- allow:naming - 記事タイトルの原文 -->

| 項目 | 内容 |
|---|---|
| ファイルシステム数 | **10 台**（Single-AZ）を並列に使用 |
| 1 台あたりの構成 | SSD 約 5.3 TB、**プロビジョンド SSD IOPS 80,000**、スループット 2 GB/s |
| 階層化ポリシー | Snapshot Only。**ブロック I/O はすべて SSD から供給** |
| クライアント側 | 10 台の iSCSI LUN を **LVM で 1 つの論理ボリュームに束ねて 1 クライアントから使用** |
| インスタンス | i3 / m6 / X2 ファミリ、RHEL 系 AMI（設計上は RHEL 8.2 ベースと記載） |
| 負荷生成 | FIO（ランダム read / write / 混合 / スループット） |
| 結果として記載されているもの | 小ブロックランダム I/O で平均レイテンシがサブミリ秒、大ブロック read はクライアントのネットワークを 100% 使用、大ブロック write は約 7.5 GB/s |

**記事自身が挙げている留保が 4 つあります。**

| 留保 | 内容 |
|---|---|
| 1 台の上限 | 当時の 1 ファイルシステムは「数十万 IOPS」と 2 GB/s まで |
| キャッシュの影響 | ワークロードがキャッシュに乗ると、**実測 IOPS はプロビジョンド IOPS を超えることがある** |
| SSD のサイジング | **2 TB のボリューム全体と Snapshot の余地が SSD に載るように**意図的にサイジングされている |
| Snapshot の整合 | **10 台にまたがる Snapshot には調整スクリプトが必要**で、アプリケーション整合にはホスト側の関与が必要 |

**そして数値そのものが古くなっています。** 同記事の[日本語版](https://aws.amazon.com/jp/blogs/news/san-a-million-iops-in-aws-from-amazon-fsx-netapp-ontap/) には、翻訳時点で 1 ファイルシステムの上限が **160,000 IOPS / 4 GB/s** に上がっていることが訳注として書かれています。現在の上限は [Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) を参照してください。

**この記事から引くべきなのは数値ではなく方法です。**

| 引ける方法 | 内容 |
|---|---|
| SSD に載せる | 階層化を Snapshot Only にし、測定対象がキャッシュ層と容量プールのどちらから供給されているかを確定させる |
| 束ね方を明示する | 複数ファイルシステムを LVM で束ねたなら、それは 1 台の性能ではありません |
| キャッシュの影響を分離する | プロビジョンド IOPS を超えた値が出たら、それはキャッシュヒットの寄与です |
| 整合性を別に数える | 束ねた構成では Snapshot の整合が別の問題として現れます |

**このリポジトリのノートは性能値を持っていません。** 検証は 384 MBps の最小構成で挙動のみを確認しており、スループットや IOPS は測っていません。数値が必要なら上の条件をそろえて自環境で測ってください。ベンチマーク設計そのものは [再現できるベンチマークの条件](../../performance/notes/what-you-cannot-read-from-cloudwatch.md#再現できるベンチマークの条件) にあります。

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | ブロックデバイスを同時に使うホスト数を数える | 1 なら Amazon EBS で足ります |
| 2 | 同じデータをファイル共有としても出す要件があるかを確認する | 構造が効く条件 1 に該当するか |
| 3 | 保持したい Snapshot の世代数と 1 世代あたりの変化量を見積もる | 構造が効く条件 2 の効果と、SSD 容量への影響 |
| 4 | 別リージョンへの複製要件と RPO を確認する | 構造が効く条件 3 に該当するか |
| 5 | AZ をまたぐ必要があるかを確認する | **Amazon EBS Multi-Attach は同一 AZ のみ**なので、またぐなら選択肢から外れます |
| 6 | HA ペアを 7 組以上に増やす計画があるかを確認する | **計画があるならブロックは使えません** |
| 7 | 現行の料金ページで最小構成の月額を試算し、要件のデータ量と比べる | 過剰な構成になっていないか |

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| ブロックストレージが必要なら共有ブロックが必要 | 別の要件です。**単独接続で足りるなら Amazon EBS のほうが素直です** |
| FSx for ONTAP の LUN を起動ディスクにできる | **できません。** ブロックプロトコルはゲスト OS の起動後に確立されます |
| 100 万 IOPS は 1 台のファイルシステムで出た数値 | **10 台を LVM で束ねた構成**の値で、当時の 1 台の上限は 80,000 IOPS です |
| 公開ベンチマークの数値をそのまま設計値にできる | 階層化ポリシー・SSD サイジング・インスタンス・ブロックサイズがそろわないと再現しません |
| Snapshot が別課金でないので容量を気にしなくてよい | **確保済み SSD を消費します。** 満杯になると LUN が read-only に落ちます |
| SnapMirror で複製すれば宛先でそのまま LUN が使える | **LUN マップと iSCSI セッションと再スキャンが宛先で必要です。** igroup は移りません |
| 1 つのボリュームでファイルとブロックを混ぜるのが普通 | 同一ファイルシステム・SVM からは両方出せます。**同じ FlexVol への混在は推奨されていません** |
| 共有ブロックにすれば複数ホストから安全に書ける | **調停はホスト側の責任です。** Amazon EBS Multi-Attach でも同じです |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| Multi-Attach の 16 インスタンス・同一 AZ・Nitro・起動ディスク不可・クラスタファイルシステム必須・`io2` の I/O fencing | [AWS: Attach an EBS volume to multiple EC2 instances using Multi-Attach](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volumes-multi.html) |
| 100 万 IOPS の測定条件（10 ファイルシステム、1 台 80,000 IOPS / 2 GB/s、LVM、FIO、階層化 Snapshot Only）と 4 つの留保 | [AWS Storage Blog: SAN: A million IOPs in AWS from Amazon FSx NetApp ONTAP](https://aws.amazon.com/blogs/storage/san-a-million-iops-in-aws-from-amazon-fsx-netapp-ontap/) <!-- allow:naming - 記事タイトルの原文 --> |
| 翻訳時点で 1 ファイルシステム上限が 160,000 IOPS / 4 GB/s に上がっていること | [同記事の日本語版](https://aws.amazon.com/jp/blogs/news/san-a-million-iops-in-aws-from-amazon-fsx-netapp-ontap/) |
| 第 2 世代 1 HA ペアの最小スループット 384 MBps と最小 SSD 1,024 GiB、現行の IOPS / スループット上限 | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) |
| ボリュームが thin provisioned で、LUN 内のデータ削除で容量が戻ること | [AWS: How FSx for ONTAP works](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/how-it-works-fsx-ontap.html) |
| SAN の LUN と NAS 共有を同じ FlexVol に混在させることが推奨されないこと | [NetApp: SAN volumes](https://docs.netapp.com/us-en/ontap/volumes/san-volumes-concept.html) |
| SnapMirror 宛先で LUN マップ・iSCSI セッション・再スキャンが必要であること | [NetApp: Destination volume data access](https://docs.netapp.com/us-en/ontap/data-protection/configure-destination-volume-data-access-concept.html) |
| 1 TB のデータベースの iSCSI LUN クローンが通常 5 分以内であること | [AWS: Using SnapCenter to protect SQL Server workloads](https://aws.amazon.com/blogs/storage/using-netapp-snapcenter-with-amazon-fsx-for-netapp-ontap-to-protect-your-sql-server-workloads) |
| iSCSI は HA ペア 6 組以下、NVMe/TCP は第 2 世代かつ 6 組以下 | [AWS: Accessing your FSx for ONTAP data](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-from-on-premises.html) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [ブロックストレージの選択肢の比較](../../../reference/comparison/block-storage-options.md) — この判断の比較表版
- [ブロックプロトコルとレイアウトの決定木](../../../reference/decision-trees/block-protocol-and-layout.md) — 選んだ後の判断
- [ブロックプロトコルの選択肢は世代と HA ペア数で先に狭まる](protocol-choice-is-bounded-before-you-choose.md) — 世代と HA ペアの制約
- [容量は 3 か所で数えられる](capacity-is-counted-in-three-places.md) — Snapshot が容量を食う経路
- [スループットは 1 つの設定値では決まらない](../../performance/notes/where-throughput-is-determined-and-shared.md) — HA ペア単位の共有
- [再現できるベンチマークの条件](../../performance/notes/what-you-cannot-read-from-cloudwatch.md#再現できるベンチマークの条件) — 測定の設計
- [ブロックストレージ横断リソースマップ](../../../reference/block-storage-resource-map.md) — 一次情報の索引
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)
