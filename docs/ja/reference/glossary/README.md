# 用語集 / Glossary

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md)

---

ONTAP と AWS の用語を、このリポジトリで使う意味に限定して定義します。
用語そのものは翻訳しません（`ONTAP`、`SnapMirror` などは原語のまま使います）。

Definitions are scoped to how each term is used in this repository. The terms themselves are not
translated — `ONTAP`, `SnapMirror`, and similar stay in the original form.

---

## ストレージ構造 / Storage structure

| 用語 / Term | 定義 / Definition |
|---|---|
| SVM (Storage Virtual Machine) | データアクセスの論理単位。プロトコル設定、AD 参加、ボリュームを持つ / The logical unit of data access; owns protocol configuration, AD membership, and volumes |
| Volume | データを格納する論理単位。セキュリティスタイルを持つ / The logical container for data; carries a security style |
| LIF (Logical Interface) | IP を持つ論理ネットワークインターフェース。管理用とデータ用がある / A logical network interface with an IP; management and data variants exist |
| Aggregate | 物理ディスクをまとめた領域。ボリュームの配置先 / A pool of physical storage where volumes are placed |
| Security style | ボリュームの権限評価方式（`UNIX` / `NTFS` / `MIXED`）。**権限の種類**を決めるもので、アクセス可能なプロトコルを制限するものではない / How permissions are evaluated on a volume; determines the **type** of permissions used, not which protocols may access it |
| HA ペア / HA pair | ファイルサーバーのアクティブ・スタンバイ構成の 1 組。**各 HA ペアが 1 つの aggregate を持つ**ため、性能と容量の共有単位でもある / An active-standby pair of file servers. **Each HA pair has one aggregate**, which makes it the unit across which performance and capacity are shared ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/HA-pairs.html)) |
| FlexVol | 単一のボリュームスタイル。HA ペア 1 組の構成では既定 / The single-container volume style; the default when a file system has one HA pair ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html)) |
| FlexGroup | 複数の構成要素（constituent）からなるボリュームスタイル。HA ペアが複数ある構成では既定 / A volume style composed of multiple constituents; the default when a file system has more than one HA pair ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html)) |
| Constituent | FlexGroup を構成する個々の FlexVol。データはこの単位に分散される / An individual FlexVol making up a FlexGroup; data is distributed across them ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html)) |
| inode | ファイルとディレクトリのメタデータ 1 件を保持する構造。**有限で、使い切ると空き容量があっても新規作成が失敗する** / The structure holding metadata for one file or directory. **Finite — exhausting it fails new creation even with free capacity** ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html)、実測値は [上限値](../limits/README.md#fsx-for-ontap--既定の-inode-容量--default-inode-capacity)) |

---

## データ保護 / Data protection

| 用語 / Term | 定義 / Definition |
|---|---|
| Snapshot | ある時点のボリューム状態への参照。作成は瞬時で、変更ブロック分のみ容量を消費 / A point-in-time reference to volume state; instantaneous, consuming capacity only for changed blocks |
| SnapMirror | ボリュームをブロックレベルで複製する仕組み。DR と移行の両方に使う / Block-level volume replication, used for both DR and migration |
| SnapLock | 書き込み後変更不可（WORM）を強制する機能。**有効化は不可逆** / Enforces write-once-read-many. **Enablement is irreversible** |
| FlexClone | Snapshot から書き込み可能なコピーを瞬時に作る機能。初期容量消費なし / Creates a writable copy from a Snapshot instantly, with no initial capacity consumption |
| FabricPool | アクセス頻度の低いブロックを低コスト層へ自動移動する階層化機能 / Automatic tiering of infrequently accessed blocks to a lower-cost tier |
| XDP (extended data protection) | SnapMirror の関係種別。**ONTAP のバージョンに依存しない**ため、移行やバージョン差のある複製で前提になる / A SnapMirror relationship type that is **independent of the ONTAP version**, which is why it is the premise for migration and for replication across version differences ([NetApp](https://docs.netapp.com/us-en/ontap/snaplock/mirror-worm-files-task.html)) |
| 共通 Snapshot / Common snapshot | 複製元と複製先の双方に存在する Snapshot。**差分転送はこれを基点にするため、失うと初期同期からやり直しになる** / A snapshot present on both source and destination. **Incremental transfer starts from it, so losing it forces a fresh baseline sync** ([NetApp](https://docs.netapp.com/us-en/ontap-cli/snapmirror-resync.html)) |
| Compliance Clock | SnapLock が保持期間の判定に使う改変不能な時計。**ボリューム側の Compliance Clock は SnapLock ボリューム作成時に自動で初期化される** / The tamper-resistant clock SnapLock uses to evaluate retention. **The volume Compliance Clock is initialized automatically when a SnapLock volume is created** ([NetApp](https://docs.netapp.com/us-en/ontap/snaplock/initialize-complianceclock-task.html)) |

---

## アクセス / Access

| 用語 / Term | 定義 / Definition |
|---|---|
| FlexCache | 別の場所に読み取りキャッシュボリュームを置く機能 / A read cache volume placed at a different location |
| FSx for ONTAP S3 AP | ボリュームへの S3 API アクセスを提供する Access Point / An access point providing S3 API access to a volume |
| Export policy | NFS クライアントのアクセス制御ルール / Access control rules for NFS clients |
| Name mapping | SMB・Kerberos・UNIX の各 ID を相互に対応付ける設定。NFS クライアントから来ても SMB クライアントから来ても適切な権限を得るために使われる / Configuration mapping SMB, Kerberos, and UNIX identities to one another, so that correct access is obtained whether the request arrives from an NFS or an SMB client ([NetApp](https://docs.netapp.com/us-en/ontap/nfs-admin/how-name-mappings-used-concept.html)) |
| FPolicy | ファイル操作イベントを外部に通知する仕組み / A mechanism for notifying external systems of file operation events |

---

## ID と認証 / Identity and authentication

| 用語 / Term | 定義 / Definition |
|---|---|
| Active Directory | SVM が参加するディレクトリサービス。**参加は SVM 単位**で、SMB と Kerberos 認証の前提になる / The directory service an SVM joins. **Membership is per SVM**, and is the premise for SMB and for Kerberos authentication ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/data-protection.html)) |
| SID (Security Identifier) | Windows の ID を表す識別子。**SMB の資格情報は 1 つの主 SID と、所属グループに対応する複数のグループ SID から成る** / The identifier representing a Windows identity. **An SMB credential consists of one primary SID plus group SIDs for the groups the user belongs to** ([NetApp](https://docs.netapp.com/us-en/ontap/nfs-admin/smb-access-nfs-clients-concept.html)) |
| LDAP | ユーザー・グループ・netgroup を格納するディレクトリへのアクセスプロトコル。**Active Directory に参加していなくても、LDAP でドメインに参加した SVM では Kerberos による転送時暗号化が使える** / A protocol for accessing a directory holding users, groups, and netgroups. **Kerberos-based encryption in transit is available on an SVM joined to a domain over LDAP, not only on one joined to Active Directory** ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/data-protection.html)) |
| Kerberos | NFS・SMB の転送時暗号化に使う認証方式。**SVM が Active Directory または LDAP でドメインに参加していることが前提** / The authentication mechanism used for encryption in transit over NFS and SMB. **Requires the SVM to be joined to a domain through Active Directory or LDAP** ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-in-transit.html)) |
| DACL / SACL | NTFS のアクセス許可（DACL）と監査設定（SACL）。**移行ツールの既定では SACL が落ちることがある** / NTFS access permissions (DACL) and audit settings (SACL). **Migration tool defaults can omit the SACL** ([移行時の ACL 保持](../../playbooks/03-migrate/notes/preserving-acls-during-migration.md#何が落ちるのか)) |

---

## 性能と課金の単位 / Performance and billing units

| 用語 / Term | 定義 / Definition |
|---|---|
| スループット容量 / Throughput capacity | 各ファイルサーバーがネットワーク経由でデータを供給できる水準。**キャッシュ用メモリと NVMe 容量、ディスク I/O 性能も同時に決まり、追加プロビジョニングした場合の SSD IOPS の上限もこの値が規定する** / The level at which each file server can serve data over the network. **It also fixes cache memory and NVMe capacity and disk I/O performance, and it caps the SSD IOPS achievable even when additional IOPS are provisioned** ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)) |
| ベースライン / バースト / Baseline and burst | 性能仕様は水準ごとにベースライン値とバースト値の 2 段で定義される。**バーストは継続的に使える値ではない** / Performance specifications are defined as a baseline and a burst figure per level. **Burst is not a level that can be sustained** ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)) |
| SSD 層 / SSD tier | 利用者がプロビジョニングする高性能層。データセットのうち活動中の部分に充てる / The user-provisioned, high-performance tier, intended for the active portion of the data set ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-storage-capacity.html)) |
| 容量プール層 / Capacity pool tier | 自動で拡張する弾力的な層。アクセス頻度の低いデータ向けにコスト最適化されている / A fully elastic tier that scales automatically, cost-optimized for infrequently accessed data ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-storage-capacity.html)) |
| 階層化ポリシー / Tiering policy | ボリューム単位の設定で、SSD 層のデータを容量プール層へ移すかどうかと、いつ移すかを決める / A per-volume setting that determines whether and when data in the SSD tier moves to the capacity pool tier ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-storage-capacity.html)) |

---

## 用語の使い方 / Usage conventions

| ルール / Rule | 内容 / Detail |
|---|---|
| サービス名 / Service name | 初出は **Amazon FSx for NetApp ONTAP**、以降 **FSx for ONTAP** / First mention in full, then the short form |
| 略称 / Abbreviations | `FSxN`、単独の `FSx`、`FSx ONTAP` は使わない / Not used <!-- allow:naming --> |
| Access Point | FSx for ONTAP の文脈では **FSx for ONTAP S3 AP** と書く / Written in full when the context matters |
| 単位 / Units | GB と GiB を区別する。実測値は単位を明示 / GB and GiB are distinguished; measured values state the unit |

---

## 関連ドキュメント / Related documents

- [ナビゲーションガイド](../../navigation.md) / [Navigation Guide](../../../en/navigation.md)
- [AGENTS.md](../../../../AGENTS.md) — 命名規約の権威 / authoritative naming rules

---

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md)
