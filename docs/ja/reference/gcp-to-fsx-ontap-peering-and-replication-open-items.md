---
title: GCP と Amazon FSx for NetApp ONTAP のピアリングとレプリケーション未解決項目
lifecycle: [design, migrate, build]
domains: [data-protection, security-governance]
evidence: documented
source: https://cloud.google.com/netapp/volumes/docs/protect-data/replicate-ontap/overview
lang: ja
---

# GCP と Amazon FSx for NetApp ONTAP のピアリングとレプリケーション未解決項目

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

## 結論

この文書は、Google Cloud NetApp Volumes と Amazon FSx for NetApp ONTAP のクラスターピアリング、SVM ピアリング、SnapMirror、Break、Reverse Resync について、公開手順として確定できていない項目を記録します。ここにある操作は、一次資料と実環境の証拠が揃うまで実行可能なコマンドとして扱いません。

## はじめかた

| 段階 | 目的 | 主な担当 | 必要な証拠 | 停止条件 |
|---|---|---|---|---|
| 1 | 対象と方向の確定 | GCP / AWS 担当 | source/destination 台帳 | 方向が一致しなければ停止 |
| 2 | Provider interface の確定 | GCP / AWS 担当 | API/CLI の公式仕様 | interface が不明なら open |
| 3 | Peer state の双方向確認 | GCP / AWS 担当 | 両側の fresh read | 片側だけなら停止 |
| 4 | Replication state の確認 | ストレージ担当 | source/destination/role/state | state が矛盾すれば停止 |
| 5 | Sample data の確認 | GCP Linux 担当 | private run record | 証拠不足なら open |

所要時間は計画上の目安であり、provider の処理時間や本番見積りではありません。

## 対象トポロジー

| 役割 | Provider | Resource | Direction | 状態 |
|---|---|---|---|---|
| Cluster source | FSx for ONTAP または GCNV | `<source-cluster>` | source | 台帳で確定が必要 |
| SVM source | FSx for ONTAP または GCNV | `<source-svm>` | source | 台帳で確定が必要 |
| SnapMirror source volume | FSx for ONTAP | `<snapmirror-source-volume>` | FSx for ONTAP → GCNV | 手順の対象候補 |
| GCNV destination volume | GCNV | `<gcnv-destination-volume>` | destination | provider API の照合が必要 |
| Reverse destination | FSx for ONTAP | `<reverse-destination-volume>` | GCNV → FSx for ONTAP | DP/read-only の確認が必要 |
| FlexCache origin volume | `<provider>` | `<origin-svm>:<origin-volume>` | origin | topology 未確定、open |
| FlexCache cache volume | `<provider>` | `<cache-svm>:<cache-volume>` | cache | provider interface 未確定、open |

この表の値を、既存の実リソース名から推測して埋めてはいけません。run ledger と provider の read-only response で一致を確認します。

## クラスターピアリング

> **Status: open**
>
> GCNV 側の initiate interface、FSx for ONTAP 側の acceptance interface、generated ONTAP command、passphrase の受け渡し、expiry の判定を、この文書の公開手順として確定していません。これらを確定するには、現在の Google Cloud NetApp Volumes の公開 API/CLI 仕様、FSx for ONTAP の ONTAP CLI/REST 仕様、実際の response record が必要です。

必要な解決入力

- GCNV replication resource の完全な resource name。
- API method、request body、非同期 Operation の完了判定。
- `hybridPeeringDetails` 相当の response fields。
- generated command の正確な syntax と passphrase prompt。
- FSx for ONTAP 側で実行する actor、selector、pre-state、post-state。
- 両クラスタで同じ peer identity、intercluster address、availability、authentication を確認する方法。

以下は**実行コマンドではありません**。不足している入力を整理する非実行テンプレートです。

```text
GCNV replication resource: <resource-name>
GCNV method: <documented-method>
FSx for ONTAP acceptance interface: <documented-cli-or-rest-interface>
Peer cluster identity: <peer-cluster>
Peer intercluster addresses: <peer-addresses>
Passphrase handoff: <approved-private-channel>
Expiry predicate: <documented-expiry-field-and-condition>
```

## SVM ピアリング

> **Status: open**
>
> GCNV が initiate した SVM peer request を FSx for ONTAP がどの正式インターフェースで accept するか、対象 SVM/peer SVM の exact selector、applications、両側の post-state をこの公開文書では確定していません。

`peered` を片側で表示しただけでは完了としません。両側で次の値を fresh read し、同一 run ID に記録する必要があります。

- local SVM identity
- peer SVM identity
- peer cluster identity
- applications（SnapMirror / FlexCache など）
- peering state
- ownership and dedicated-role match

片側の read が取れない、identity が台帳と違う、applications が不足する場合は replication に進みません。

### 実環境の read-only 状態

> **Evidence: verified**（2026-09-28、`ap-northeast-1`、ONTAP 9.18.1P6）
>
> 対象 SVM は `running` で、SVM peer は `peered`、applications は `snapmirror, flexcache` でした。一方、対応する cluster peer は `Unavailable` でした。既存の SnapMirror relationship は `Snapmirrored`、`Idle`、`Healthy true` でした。

この結果は、SVM peer と SnapMirror relationship が存在することを示します。cluster peer の `Unavailable` が残っているため、今回の read-only 確認だけでは end-to-end の replication 成立や Reverse Resync の実行可否を証明しません。新しい relationship の作成、break、resync、FlexCache の作成には進みません。

## FlexCache

> **Status: open**
>
> このスレッドでは、FlexCache 用の origin volume を SnapMirror 用 volume と分けて FSx for ONTAP 側に用意し、SVM ピアリングの applications に `flexcache` を含めました。しかし、GCNV 側の cache volume 作成インターフェース、cache volume の所有者、origin/cache の exact resource identity、作成後の cache state、read/write モードは確定していません。GCNV 側で実際の cache volume を作成したことと、FlexCache の状態を確認したことも、このスレッドでは検証していません。

FlexCache を開始する前に、次の台帳を確定します。

| 項目 | 必要な値 |
|---|---|
| Origin provider / cluster / SVM / volume | `<origin-provider>` / `<origin-cluster>` / `<origin-svm>` / `<origin-volume>` |
| Cache provider / cluster / SVM / volume | `<cache-provider>` / `<cache-cluster>` / `<cache-svm>` / `<cache-volume>` |
| Origin/cache direction | `<origin-to-cache-direction>` |
| Volume type and security style | `<origin-volume-type>` / `<cache-volume-type>` / `<security-style>` |
| Client protocol | `<nfs-or-smb>` |
| Creation interface | `<documented-gcnv-or-ontap-interface>` |
| Post-state query | `<documented-cache-state-query>` |

作成後は、origin と cache の identity、cache state、SVM peer state、content read の結果を別々に確認します。cache の作成・変更・削除は、作成者、対象 resource、現在 state、依存関係、逆操作が台帳にない場合は実行しません。FlexCache は S3 Access Point と同じ経路ではなく、cache volume への NFS/SMB アクセス経路を別に確認します。

### FlexCache の方向別図

- [FlexCache: FSx for ONTAP origin → GCNV cache](../../_assets/images/gcp-fsx-ontap-flexcache-fsx-origin-to-gcnv-cache.svg)（[ダークテーマ版](../../_assets/images/gcp-fsx-ontap-flexcache-fsx-origin-to-gcnv-cache-dark.svg)）
- [FlexCache: GCNV origin → FSx for ONTAP cache](../../_assets/images/gcp-fsx-ontap-flexcache-gcnv-origin-to-fsx-cache.svg)（[ダークテーマ版](../../_assets/images/gcp-fsx-ontap-flexcache-gcnv-origin-to-fsx-cache-dark.svg)）

この図の Open は、cache 作成 interface と作成後 state を検証していないことを示します。SVM peering の applications に `flexcache` が含まれることだけでは、cache 作成成功の証拠になりません。

## SnapMirror と Reverse Resync

> **Status: open**
>
> FSx for ONTAP → GCNV の relationship create/initialize、GCNV 側の break/stop、GCNV → FSx for ONTAP の Reverse Resync について、provider control plane と ONTAP command の責任分界を公開手順として確定していません。したがって、この文書は `snapmirror resync` などの未確認コマンドを実行手順として掲載しません。

### SnapMirror と Reverse Resync の方向別図

- [SnapMirror: FSx for ONTAP → GCNV](../../_assets/images/gcp-fsx-ontap-snapmirror-fsx-to-gcnv.svg)（[ダークテーマ版](../../_assets/images/gcp-fsx-ontap-snapmirror-fsx-to-gcnv-dark.svg)）
- [Reverse Resync: GCNV → FSx for ONTAP](../../_assets/images/gcp-fsx-ontap-reverse-resync-gcnv-to-fsx.svg)（[ダークテーマ版](../../_assets/images/gcp-fsx-ontap-reverse-resync-gcnv-to-fsx-dark.svg)）

図の矢印はデータまたは関係の向きを示します。実行前に source、destination、操作主体、post-state を run ledger と provider の fresh read で対応付けます。

状態確認で最低限対応させる項目

| Phase | Source | Destination | 必須確認 |
|---|---|---|---|
| initialized | `<source-system>:<source-volume>` | `<destination-system>:<destination-volume>` | source/destination、role、mirror state、relationship status、health |
| synchronized | 同上 | 同上 | `Snapmirrored` と `Idle` など、実際の ONTAP 出力に対応した predicate |
| broken | GCNV destination | GCNV destination | break 後の write-enabled/read-only state と provider state |
| reverse resync | GCNV | FSx for ONTAP | authoritative operation、new direction、post-state、content evidence |
| final | 台帳と一致 | 台帳と一致 | relationship state とファイル内容を別々に合格判定 |

`healthy`、`transfer-state`、`mirrorState` などの名称は、各 provider の実際の response field と対応付けてから使用します。推測した field 名や、別の関係の `Available`/`ok` を対象関係の証拠にしません。

## Mutation 操作の承認手順

この節は、read-only state が合格した後に別の承認を取って実行する手順です。今回の環境では cluster peer が `Unavailable` だったため、ここにある mutation は実行していません。

### SnapMirror relationship の作成と初期化

事前条件は、source / destination cluster と SVM の peering、destination volume の `DP`、source / destination path の台帳一致、policy と schedule の選択、owner、rollback、transfer window です。NetApp の手順でも、relationship 作成前に cluster と SVM が peered であることを要求し、作成後に `snapmirror show` で確認します（[Create an ONTAP SnapMirror replication relationship](https://docs.netapp.com/us-en/ontap/data-protection/create-replication-relationship-task.html)）。

```text
# destination cluster で実行する。値は台帳から置き換える。
snapmirror create \
  -source-path <source-svm>:<source-volume> \
  -destination-path <destination-svm>:<destination-volume> \
  -type XDP \
  -schedule <approved-schedule> \
  -policy <approved-policy>

snapmirror show -destination-path <destination-svm>:<destination-volume>

# relationship が作成済みで、source / destination / role が一致した場合だけ
# destination cluster または destination SVM で初期化する。
snapmirror initialize \
  -source-path <source-svm>:<source-volume> \
  -destination-path <destination-svm>:<destination-volume>
```

`Snapmirrored`、`Idle`、`Healthy true` などの期待値は、対象 relationship の実際の出力に対応付けます。cluster peer が `Unavailable`、identity が不一致、destination が `DP` でない、active transfer がある場合は STOP です。

### 外部レプリケーションの stop、resume、reverse

Google Cloud NetApp Volumes の外部 replication は SnapMirror を使用し、create、stop、resume、reverse、delete を提供します。ただし、外部 ONTAP 側が管理する状態は ONTAP の `snapmirror show` で確認する必要があります（[External replication overview](https://docs.cloud.google.com/netapp/volumes/docs/protect-data/replicate-ontap/overview)、[Manage your external replications](https://docs.cloud.google.com/netapp/volumes/docs/protect-data/replicate-ontap/manage-external-replication)）。

```bash
set -euo pipefail
export GCP_PROJECT_ID="<gcp-project-id>"
export GCP_REGION="<gcp-region>"
export GCNV_VOLUME="<gcnv-volume>"
export REPLICATION_NAME="<replication-name>"

gcloud config set project "$GCP_PROJECT_ID"
gcloud netapp volumes replications list \
  --volume="$GCNV_VOLUME" --location="$GCP_REGION"
```

`hybridReplicationUserCommands` が返る場合は、そこに含まれる ONTAP command をそのまま private run ledger に保存します。source、destination、SVM、cluster、方向を placeholder から推測して書き換えません。

- **Stop**: Google Cloud 側で stop を要求し、外部 ONTAP destination の場合は `snapmirror show` で `Snapmirrored` / `Idle` を確認してから、返された `snapmirror break` を実行します。
- **Resume**: Google Cloud 側で resume を要求し、返された `snapmirror resync` を新しい方向と一致させて実行します。
- **Reverse**: 先に replication を stop し、Google Cloud 側で reverse を開始します。新しい destination が ONTAP なら、Google Cloud が返す `hybridReplicationUserCommands` の `snapmirror resync`、schedule、modify command だけを実行します。
- **Delete**: replication が stopped であること、outdated SnapMirror connection がないこと、最後の replication である場合の cluster peer cleanup 承認が揃った場合だけ実行します。

現在の `cluster peer Unavailable` 状態では、上記のいずれも実行しません。

### FlexCache relationship の作成

AWS の FlexCache 手順は、intercluster LIF、cluster peering、SVM peering、cache volume 作成、`volume flexcache show` の順序です。異なるネットワーク間では必要な経路と intercluster TCP 11104 / 11105 を事前に確認します（[Creating a FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-flexcache.html)）。NetApp の現行手順でも、cluster peer、SVM peer、`volume flexcache create`、`volume flexcache show` の順で扱います（[Create ONTAP FlexCache volumes](https://docs.netapp.com/us-en/ontap/flexcache/create-volume-task.html)）。

```text
# cluster peer が Available で、intercluster LIF と経路を確認した後だけ実行する。
cluster peer create -address-family ipv4 -peer-addrs <origin-intercluster-lif-1>,<origin-intercluster-lif-2>

# cache SVM 側。application は flexcache とする。
vserver peer create \
  -vserver <cache-svm> \
  -peer-vserver <origin-svm> \
  -peer-cluster <origin-cluster> \
  -applications flexcache

# origin 側の accept は、provider の正式な手順と actor が確定した場合だけ実行する。
vserver peer accept \
  -vserver <origin-svm> \
  -peer-vserver <cache-svm> \
  -local-name <cache-local-name>

# cache SVM 上で作成する。write-back は別承認が必要。
volume flexcache create \
  -vserver <cache-svm> \
  -volume <cache-volume> \
  -auto-provision-as flexgroup \
  -size <cache-size> \
  -origin-vserver <origin-svm> \
  -origin-volume <origin-volume>

volume flexcache show
```

`cluster peer show` が `Available`、SVM peer が `peered`、application が `flexcache`、origin/cache identity と security style が台帳と一致し、逆操作が記録されるまで STOP です。現在は cluster peer が `Unavailable` なので、FlexCache 作成には進みません。

### Rollback と破壊操作の境界

relationship を削除する前に、active transfer がないこと、client access を停止したこと、owner が承認したこと、inverse operation と post-state が ledger にあることを確認します。Reverse Resync の公開手順は、common snapshot、source / destination の切り替え、update、quiesce、break、delete、release、original relationship の resync までを順序付けています（[Reactivate the original ONTAP source volume](https://docs.netapp.com/us-en/ontap/data-protection/reactivate-original-source-volume-task.html)）。

- `snapmirror break`、`snapmirror delete`、`snapmirror release` は active transfer 中に実行しません。
- shared VPN、route、security group、SVM、volume、cluster peer は run-created と証明できなければ削除しません。
- rollback の実行結果は、AWS console / AWS CLI と ONTAP CLI の両面で読み戻します。

## 48 ファイル結果の扱い

> **Status: open**
>
> 会話中には 48 ファイル、SHA-256 48/48、FAILED 0、欠落 0、DP read-only の観測があります。しかし、この公開文書から参照できる run ID、環境、日付、fixture 方式、元の manifest を含む retained record がありません。したがって、ここでは verified result として確定しません。

verified に昇格するために必要な記録

- `sample_run_id`
- GCP client、region、protocol、NFS source/export
- AWS file system、SVM、volume、region
- measurement date
- total files = 48
- hash success = 48
- failed = 0
- missing = 0
- extra = 0
- DP/read-only result
- original manifest or reproducible fixture specification

## 片付け境界

この文書は peering、replication、volume、SVM、VPN、Cloud Router、VGW、route、security rule の削除を実行しません。cleanup には次を要求します。

1. run ledger の owner と exact resource identity を fresh read する。
2. shared/pre-existing resource は leave in place とする。
3. active transfer、dependency、peer relationship が残る場合は停止する。
4. destructive operation ごとに直前の確認と個別承認を取る。
5. provider の inverse operation と post-state を記録する。

## Related documents

- [GCP / FSx for ONTAP preflight and sample validation](gcp-to-fsx-ontap-preflight-and-sample-validation.md)
- [Evidence policy](../evidence-policy.md)
- [Localization workflow](../../agent/localization.md)
- [Data protection](../domains/data-protection/)
- [S3 Access Points の制約](../domains/data-utilization/notes/s3-access-point-constraints.md)
- [Google Cloud: external replication overview](https://cloud.google.com/netapp/volumes/docs/protect-data/replicate-ontap/overview)
- [Google Cloud: ONTAP communication prerequisites](https://cloud.google.com/netapp/volumes/docs/migrate/ontap/prerequisites-ontap-netapp-volumes)
- [NetApp TR-4743: ONTAP FlexCache and FlexGroup technical reports](https://docs.netapp.com/us-en/ontap-technical-reports/nas-containers.html)
- [NetApp TR-4015: data protection and disaster recovery technical reports](https://docs.netapp.com/us-en/ontap-technical-reports/data-protection-disaster-recovery.html)
- [AWS Blog: scalable replication with FSx for ONTAP and SnapMirror](https://aws.amazon.com/blogs/storage/highly-scalable-solution-design-to-replicate-data-using-amazon-fsx-for-netapp-ontap-and-snapmirror/)

<!-- lang-switcher:start -->
🌐 [日本語](gcp-to-fsx-ontap-peering-and-replication-open-items.md) | [English](../../en/reference/gcp-to-fsx-ontap-peering-and-replication-open-items.md) | [🏠 リポジトリトップ](../../../README.md)
<!-- lang-switcher:end -->
