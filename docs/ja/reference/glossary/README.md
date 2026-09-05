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
| FPolicy | ファイル操作イベントを外部に通知する仕組み。監視できるのは NFS / SMB のみで、S3 Access Point 経由の操作は対象外 / A mechanism for notifying external systems of file operation events. It can watch NFS and SMB only; operations through an S3 access point are outside its scope |

---

## ブロックストレージ / Block storage

| 用語 / Term | 定義 / Definition |
|---|---|
| LUN | iSCSI で公開されるブロックデバイス。**ボリュームの中に置かれるオブジェクト**で、ボリュームそのものではない。最大 128 TB / A block device exposed over iSCSI. **An object placed inside a volume**, not the volume itself. Maximum 128 TB ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-iscsi-lun.html)) |
| Namespace | NVMe/TCP で公開されるブロックデバイス。iSCSI の LUN に対応する / The block device exposed over NVMe/TCP, the counterpart of a LUN in iSCSI ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/provision-nvme-linux.html)) |
| igroup (initiator group) | LUN を見せる相手を IQN で列挙したグループ。**LUN マップは igroup に対して行う** / A group listing, by IQN, the hosts a LUN is shown to. **A LUN is mapped to an igroup**, not to a host directly ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-iscsi-lun.html)) |
| Subsystem | NVMe/TCP で igroup に対応するもの。**host NQN を登録する** / The NVMe/TCP counterpart of an igroup. **Host NQNs are registered to it** ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/provision-nvme-linux.html)) |
| IQN (iSCSI Qualified Name) | iSCSI の initiator と target を識別する名前。Linux では `/etc/iscsi/initiatorname.iscsi` にある / The name identifying an iSCSI initiator or target. On Linux it is in `/etc/iscsi/initiatorname.iscsi` ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-luns-linux.html)) |
| NQN (NVMe Qualified Name) | NVMe の host と subsystem を識別する名前。Linux では `/etc/nvme/hostnqn` にある / The name identifying an NVMe host or subsystem. On Linux it is in `/etc/nvme/hostnqn` ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/provision-nvme-linux.html)) |
| ALUA / ANA | 複数パスのうちどれが最適かをホストに伝える仕組み。**ONTAP は iSCSI で ALUA、NVMe で ANA を使う** / The mechanism telling a host which of several paths is optimal. **ONTAP uses ALUA for iSCSI and ANA for NVMe** ([NetApp](https://docs.netapp.com/us-en/ontap/san-config/host-support-multipathing-concept.html)) |
| Multipath / MPIO | 複数パスを 1 つのデバイスに束ねるホスト側の仕組み。**ブロックではフェイルオーバーの仕組みそのもので、ホスト側の責任** / The host-side mechanism binding several paths into one device. **For block it is the failover mechanism, and it is the host's responsibility** ([パスはフェイルオーバーの仕組みそのもの](../../domains/block-storage/notes/paths-are-the-failover-mechanism.md)) |
| Selective LUN Map (SLM) | LUN を所有するノードとその HA パートナー上のパスに限ってアクセスを許す設定。**新しい LUN マップでは既定で有効** / A setting restricting access to paths on the LUN's owning node and its HA partner. **Enabled by default on new LUN maps** ([NetApp](https://docs.netapp.com/us-en/ontap/san-admin/selective-lun-map-concept.html)) |
| Space reservation / `space-reserve` | LUN のサイズ分の容量をボリュームから確保する設定。**書き込みが 0 でも消費される。既定は無効** / A setting reserving the LUN's size from the volume. **Consumed even with nothing written. Disabled by default** ([容量は 3 か所で数えられる](../../domains/block-storage/notes/capacity-is-counted-in-three-places.md)) |
| Space allocation / `space-allocation` | ホストが解放したブロックを回収できるようにする設定（SCSI の UNMAP）。**これがないと LUN 上でファイルを消しても容量が戻らない** / A setting letting freed blocks be reclaimed (SCSI UNMAP). **Without it, deleting a file inside a LUN does not return capacity** ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-iscsi-lun.html)) |
| Fractional reserve | 上書きのための予備領域を表すボリューム属性。**0 か 100 しか取らず、ボリュームの guarantee が `none` のときは既定で 0** / A volume attribute for overwrite reserve. **Only 0 or 100, and 0 by default when the volume guarantee is `none`** ([NetApp](https://docs.netapp.com/us-en/ontap/san-admin/set-fractional-reserve-concept.html)) |
| `os_type` | LUN のブロックオフセットを決める属性。**Windows は版を問わず `windows_2008`。`windows_2022` は存在しない** / The attribute fixing a LUN's block offset. **`windows_2008` for every Windows version; `windows_2022` does not exist** ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-iscsi-lun.html)) |
| Fibre Channel (FC) | **AWS のドキュメントのプロトコル列挙に現れません。** 使えないと明記されているのではなく、記載がない状態です。未記載を非対応と読み替えないこと / **Absent from the protocol enumerations in the AWS documentation.** It is not stated to be unsupported; it is simply not mentioned. Do not read silence as a documented negative |

---

## ID と認証 / Identity and authentication

| 用語 / Term | 定義 / Definition |
|---|---|
| Active Directory | SVM が参加するディレクトリサービス。**参加は SVM 単位**で、SMB と Kerberos 認証の前提になる / The directory service an SVM joins. **Membership is per SVM**, and is the premise for SMB and for Kerberos authentication ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/data-protection.html)) |
| SID (Security Identifier) | Windows の ID を表す識別子。**SMB の資格情報は 1 つの主 SID と、所属グループに対応する複数のグループ SID から成る** / The identifier representing a Windows identity. **An SMB credential consists of one primary SID plus group SIDs for the groups the user belongs to** ([NetApp](https://docs.netapp.com/us-en/ontap/nfs-admin/smb-access-nfs-clients-concept.html)) |
| LDAP | ユーザー・グループ・netgroup を格納するディレクトリへのアクセスプロトコル。**Active Directory に参加していなくても、LDAP でドメインに参加した SVM では Kerberos による転送時暗号化が使える** / A protocol for accessing a directory holding users, groups, and netgroups. **Kerberos-based encryption in transit is available on an SVM joined to a domain over LDAP, not only on one joined to Active Directory** ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/data-protection.html)) |
| Kerberos | NFS・SMB の転送時暗号化に使う認証方式。**SVM が Active Directory または LDAP でドメインに参加していることが前提** / The authentication mechanism used for encryption in transit over NFS and SMB. **Requires the SVM to be joined to a domain through Active Directory or LDAP** ([AWS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-in-transit.html)) |
| DACL / SACL | NTFS のアクセス許可（DACL）と監査設定（SACL）。**移行ツールの既定では SACL が落ちることがある** / NTFS access permissions (DACL) and audit settings (SACL). **Migration tool defaults can omit the SACL** ([移行時の ACL 保持](../../playbooks/03-migrate/notes/preserving-acls-during-migration.md#落ちるもの)) |

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
