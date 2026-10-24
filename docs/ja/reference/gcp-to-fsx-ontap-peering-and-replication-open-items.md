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
| FlexCache origin | `<provider>` | `<origin-svm>:<origin-volume>` | origin | topology 未確定、open |

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

## SnapMirror と Reverse Resync

> **Status: open**
>
> FSx for ONTAP → GCNV の relationship create/initialize、GCNV 側の break/stop、GCNV → FSx for ONTAP の Reverse Resync について、provider control plane と ONTAP command の責任分界を公開手順として確定していません。したがって、この文書は `snapmirror resync` などの未確認コマンドを実行手順として掲載しません。

状態確認で最低限対応させる項目

| Phase | Source | Destination | 必須確認 |
|---|---|---|---|
| initialized | `<source-system>:<source-volume>` | `<destination-system>:<destination-volume>` | source/destination、role、mirror state、relationship status、health |
| synchronized | 同上 | 同上 | `Snapmirrored` と `Idle` など、実際の ONTAP 出力に対応した predicate |
| broken | GCNV destination | GCNV destination | break 後の write-enabled/read-only state と provider state |
| reverse resync | GCNV | FSx for ONTAP | authoritative operation、new direction、post-state、content evidence |
| final | 台帳と一致 | 台帳と一致 | relationship state とファイル内容を別々に合格判定 |

`healthy`、`transfer-state`、`mirrorState` などの名称は、各 provider の実際の response field と対応付けてから使用します。推測した field 名や、別の関係の `Available`/`ok` を対象関係の証拠にしません。

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

<!-- lang-switcher:start -->
🌐 [日本語](gcp-to-fsx-ontap-peering-and-replication-open-items.md) | [English](../../en/reference/gcp-to-fsx-ontap-peering-and-replication-open-items.md) | [🏠 リポジトリトップ](../../../README.md)
<!-- lang-switcher:end -->
