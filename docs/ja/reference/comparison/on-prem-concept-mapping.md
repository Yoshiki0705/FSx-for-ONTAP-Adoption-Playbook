---
title: オンプレミスの NAS / SAN 運用概念と ONTAP の対応は一対一ではない
lifecycle: [assess, design, migrate]
domains: [block-storage, multiprotocol-identity, data-protection]
evidence: documented
source: https://aws.amazon.com/fsx/netapp-ontap/faqs/
lang: ja
---

# オンプレミスの NAS / SAN 運用概念と ONTAP の対応

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md) | [比較マトリクス](README.md)

---

## 結論

既存環境の用語をそのまま ONTAP のリソース名に置き換えると、管理境界、公開単位、復旧単位を取り違えます。
この表は棚卸し時の聞き換えに使い、構成の同一性を示す対応表としては使いません。

> **区分** — `documented`。Amazon FSx for NetApp ONTAP と ONTAP の一次情報に基づく概念整理です。
> 製品固有の構成を移行できることや、同じ可用性・性能になることは示していません。

---

## 使い方と非同義である点

「既存環境の何を管理・公開・保護しているか」を聞き出し、対応する ONTAP の確認先へ進むために使います。
同じ行にある語でも、責務や粒度が同じとは限りません。たとえば [SVM](../glossary/#ストレージ構造--storage-structure) はデータアクセスと管理の境界ですが、基盤の容量とスループットは同じファイルシステム上の SVM 間で共有します。

---

## 概念対応表

| 一般的な運用概念 | ONTAP で確認する概念 | 移行時に確認する境界 | 一次情報 |
|---|---|---|---|
| ファイルサーバー | SVM（Storage Virtual Machine） | クライアントは SVM のデータエンドポイントへ接続。基盤はファイルシステムと HA ペアが担う | [AWS FAQ](https://aws.amazon.com/fsx/netapp-ontap/faqs/) |
| 名前空間 / 共有 / エクスポート | SVM 名前空間と junction path、SMB share、NFS export policy | パスの配置、共有名、クライアント許可は別の設定 | [AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) / [NetApp SMB](https://docs.netapp.com/us-en/ontap/smb-config/create-share-task.html) / [NetApp NFS](https://docs.netapp.com/us-en/ontap/nfs-config/create-export-policy-task.html) |
| ストレージ VM / テナント境界 | SVM | 管理資格情報とデータエンドポイントは分離できるが、ファイルシステムの容量とスループットは共有 | [AWS FAQ](https://aws.amazon.com/fsx/netapp-ontap/faqs/) |
| ボリューム | [FlexVol / FlexGroup](../glossary/#ストレージ構造--storage-structure) volume | NAS の junction と SAN の LUN / namespace の格納先。ボリューム自体が LUN ではない | [AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |
| LUN | [iSCSI LUN / NVMe namespace](../glossary/#ブロックストレージ--block-storage) | プロトコルごとに対象と識別子が異なる。いずれも volume 内に作る | [AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-fsx-clients.html) |
| イニシエータグループ | iSCSI [igroup / NVMe subsystem](../glossary/#ブロックストレージ--block-storage) | igroup は IQN、subsystem は host NQN を登録し、LUN / namespace をマップ | [AWS iSCSI](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-luns-linux.html) / [AWS NVMe/TCP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/provision-nvme-linux.html) |
| マルチパス | ホスト MPIO / multipath と ALUA / ANA | 複数 LIF への経路をホストで 1 デバイスに束ねる。SVM の設定だけでは完結しない | [NetApp](https://docs.netapp.com/us-en/ontap/san-config/host-support-multipathing-concept.html) |
| スナップショット | [Snapshot](../glossary/#データ保護--data-protection) | volume 単位の同一ファイルシステム内コピー。volume やファイルシステムの喪失には独立しない | [AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snapshots-ontap.html) |
| レプリケーション | SnapMirror の volume-level replication | 宛先は別 volume。FSx for ONTAP では SVMDR と同期 SnapMirror は対象外 | [AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/scheduled-replication.html) |
| 階層化 | [volume tiering policy](../glossary/#性能と課金の単位--performance-and-billing-units) と SSD / capacity pool tier | ポリシーは volume 単位。読み戻し動作と cooling period も含めて確認 | [AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html) |
| クォータ | SVM quota policy、volume quota rule、enforced quota | rule は volume を対象とし、割り当てた policy を volume ごとに有効化 | [NetApp](https://docs.netapp.com/us-en/ontap/volumes/quota-rules-policies-enforced-quotas-concept.html) |
| 監査 | SVM の SMB / NFS audit と FPolicy | 監査対象プロトコル、SACL / NFSv4 ACL、ログ保管先を分けて確認 | [NetApp](https://docs.netapp.com/us-en/ontap/nas-audit/index.html) |

---

## 選び方

| 確認の起点 | 最初に見る ONTAP の単位 | 次の確認 |
|---|---|---|
| 利用者、部門、管理者の境界 | SVM | 認証、管理ロール、共有する容量と性能 |
| 共有パスやドライブ | volume、junction、SMB share / NFS export policy | ACL、export rule、qtree、quota |
| ホストから見えるディスク | LUN / namespace、igroup / subsystem | LIF、multipath、ファイルシステム整合性 |
| 復旧点と遠隔コピー | Snapshot、backup、SnapMirror | 障害範囲、保持期間、RPO / RTO、復旧訓練 |
| コールドデータと容量制御 | tiering policy、quota | アクセスパターン、cooling period、hard / soft limit |
| 操作証跡 | SVM audit / FPolicy と AWS 側の操作ログ | データ操作と管理操作の収集先、保持、検索手順 |

同じ一般用語が複数行にまたがる場合は、一つへ寄せずに境界ごとに棚卸しします。
移行方式の決定は、この対応表の後に [移行方式 決定ツリー](../decision-trees/migration-method.md) で行います。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| SVM ごとに物理的な容量と性能が専有される | SVM は論理境界で、同じファイルシステムの容量とスループットを共有します |
| volume はホストから見えるディスクである | SAN では volume 内の LUN または namespace をホストへ公開します |
| SMB share と NFS export policy は同じ設定である | share は SMB の公開点、export policy は NFS クライアント許可です |
| multipath はストレージ側だけで完結する | ホスト側ソフトウェアが複数パスを一つのデバイスとして扱う必要があります |
| Snapshot は独立したバックアップである | 同じ volume とファイルシステムに依存します |
| audit を一つ有効にすれば全操作が記録される | データプロトコルの監査と AWS / ONTAP の管理操作ログは収集面が異なります |

---

## 比較時点

2026-09-20 時点の公開情報です。設計時にはリンク先の現行仕様と対象 ONTAP バージョンを確認してください。

---

## 関連ドキュメント

- [比較マトリクス](README.md) — 比較資料の索引
- [用語集](../glossary/) — このリポジトリでの ONTAP / AWS 用語
- [ブロックストレージの選択肢の比較](block-storage-options.md) — LUN / namespace を含む接続方式
- [データ保護方式の比較](data-protection-methods.md) — Snapshot、backup、SnapMirror の障害別範囲
- [移行方式 決定ツリー](../decision-trees/migration-method.md) — 棚卸し後の移行経路
- [知見の分類ポリシー](../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md) | [比較マトリクス](README.md)
