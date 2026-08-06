# 上限値・クォータ / Limits and Quotas

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md)

---

## 記載ルール / Recording rules

各値には **出典** と **検証日** を付けます。ドキュメント記載値と実測値が異なる場合は
**両方**を残します。片方だけを書くと、読者はどちらの前提で設計すべきか判断できません。

Every value carries a **source** and a **verification date**. Where the documented value and the
measured value differ, keep **both** — recording only one leaves readers unable to tell which
premise to design against.

| 列 / Column | 内容 / Contents |
|---|---|
| 項目 / Item | 何の上限か / What the limit applies to |
| 値 / Value | 単位を明示。GB と GiB を区別する / State the unit explicitly; distinguish GB from GiB |
| 出典 / Source | ドキュメント URL、または「実測」/ Documentation URL, or "measured" |
| 検証日 / Verified | `YYYY-MM-DD` |
| 備考 / Notes | 検証環境、エラーの出方、回避策 / Environment, how the error surfaces, workaround |

---

## ONTAP バージョンの取得経路 / Where the ONTAP version comes from

**AWS CLI では取得できず、ONTAP REST API では取得できました。** バージョン依存の挙動を記録するには
バージョンが必要なので、取得経路そのものを記録しておきます。

The AWS CLI does not return it; the ONTAP REST API does. Recording version-specific behaviour requires
the version, so the retrieval path is itself worth recording.

| 経路 / Path | 結果 / Result |
|---|---|
| `aws fsx describe-file-systems` の `FileSystemTypeVersion` | **返りません**（`None`） |
| ONTAP REST `GET /api/cluster?fields=version` | **`NetApp Release 9.17.1P7D1`** |

| 項目 | 値 | 出典 | 検証日 | 備考 |
|---|---|---|---|---|
| ONTAP バージョン | `9.17.1P7D1` | 実測 | 2026-08-06 | ビルド日時も併せて返ります |
| ONTAP REST の認証 | `fsxadmin` の Basic 認証 | 実測 | 2026-08-06 | 未認証は `401` |

> **取得したのは検証環境 2 台のうち 1 台だけです。** もう 1 台は管理エンドポイントが別 VPC にあり、
> 本検証では取得していません。**以降の記述で「ONTAP 9.17.1P7D1」と書いてあるのは、この 1 台で
> 実施した検証に限ります。**
>
> **Only one of the two file systems was queried.** The other has its management endpoint in a different
> VPC and was not reached. **Where a section below states ONTAP 9.17.1P7D1, that applies only to
> verification performed on that one file system.**

### 管理エンドポイントへの到達方法 / Reaching the management endpoint

管理エンドポイントは VPC 内のプライベート IP です。**同一 VPC の EC2 に Session Manager の
ポートフォワードを張ると、手元から到達できます。**

| 前提 / Prerequisite | 内容 |
|---|---|
| SSM エージェント | `AWS-StartPortForwardingSessionToRemoteHost` に対応するバージョン |
| EC2 の配置 | 管理エンドポイントと**同一 VPC**（本検証では同一 VPC 内の別サブネット） |
| ローカル | `session-manager-plugin` |

```bash
aws ssm start-session \
  --target <instance-id> \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["<management-ip>"],"portNumber":["443"],"localPortNumber":["18443"]}'
```

> **資格情報の扱い**: この方法では **EC2 に IAM 権限を追加する必要がなく、パスワードが SSM の
> コマンド履歴に残りません。** `aws ssm send-command --parameters` に資格情報を渡す方法は、
> 履歴に平文で永続化されるため避けてください。
>
> **Credential handling**: this path needs **no additional IAM permission on the instance, and no
> password enters SSM command history.** Passing credentials through `aws ssm send-command
> --parameters` persists them in that history in clear text — avoid it.

---

## FSx for ONTAP S3 AP — オブジェクトサイズ / Object size

姉妹リポジトリで実測された値です。詳細は
[S3 AP object size limit verification](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/s3ap-object-size-limits-verification.md)
を参照してください。

| 項目 | 値 | 出典 | 検証日 | 備考 |
|---|---|---|---|---|
| 単一 `PutObject` | 5 GiB (5,368,709,120 B) | 実測 | 2026-08-02 | `Content-Length` で即時拒否。400 `EntityTooLarge` + `MaxSizeAllowed` |
| `UploadPart` 1 パート | 5 GiB | 実測 | 2026-08-02 | 同上 |
| オブジェクト全体 | 50 GiB (53,687,091,200 B) | 実測 | 2026-08-02 | **`CompleteMultipartUpload` でのみ検査**。全ペイロード転送後に判明する |

> **設計上の注意**: オブジェクト全体の上限は転送完了後にしか検査されません。`UploadPart` に
> 累積チェックはなく、`Complete` のエラーには `MaxSizeAllowed` が含まれません。
> **クライアント側で事前にサイズ検証してください。**
>
> **Design note**: The whole-object limit is checked only after the full payload has transferred.
> `UploadPart` has no cumulative check, and the `Complete` error omits `MaxSizeAllowed`.
> **Validate object size client-side before uploading.**

> **単位の注意**: ドキュメントは "5 GB" / "50 GB" と記載していますが、実測値はいずれも **binary
> (GiB)** です。
>
> **Unit note**: Documentation says "5 GB" / "50 GB", but both measured values are **binary (GiB)**.

検証環境 / Environment: `ap-northeast-1`

---

## FSx for ONTAP — 既定の inode 容量 / Default inode capacity

**ドキュメント記載値と実測値が食い違う項目です。** 上の記載ルールに従い両方を残します。

This is an item where the documented value and the measured value **disagree**. Per the recording
rule above, both are kept.

| 項目 | 値 | 出典 | 検証日 | 備考 |
|---|---|---|---|---|
| 既定の比率 | 32 KiB あたり 1 個 | [AWS: Volume storage capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html) | — | ドキュメント記載 |
| 648 GiB 以上のボリューム | **21,251,126 個で固定** | 同上 | — | **実測では再現しませんでした** |
| 100 GiB の FlexVol（2 本） | 3,112,959 個 | 実測 | 2026-08-06 | 34,493 B / inode |
| 1 TiB の FlexVol | 31,876,709 個 | 実測 | 2026-08-06 | 34,493 B / inode。648 GiB 超だが固定値ではない |
| 2 TiB の FlexVol | 63,753,417 個 | 実測 | 2026-08-06 | 1 TiB の**ちょうど 2.0 倍** |
| 約 1.85 TiB の FlexGroup（3 構成要素） | 58,988,760 個 | 実測 | 2026-08-06 | FlexVol と同じ比率 |
| 引き上げ可能な比率 | 4 KiB あたり 1 個 | [AWS: Volume storage capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html) | — | ONTAP CLI で設定 |
| 1 ボリュームの絶対上限 | 20 億個 | 同上 | — | — |

実測値はいずれも `サイズ × 0.95 ÷ 32 KiB` と誤差 1〜24 個で一致します。**約 5% の予約を除いた容量に
対して 32 KiB あたり 1 個**、という既定比率がサイズによらず適用されている形です。

All measured values match `size × 0.95 ÷ 32 KiB` to within 1–24 inodes, consistent with the documented
default ratio being applied to post-reserve capacity **at every size**, rather than capping.

> **どちらの前提でも設計上の結論は同じです。** inode は有限で、使い切ると空き容量があっても書けません。
> 変わるのは「どのくらいで詰まるか」だけなので、**数値を仮定せず自環境の `FilesCapacity` を読んでください。**
>
> **The design conclusion holds either way**: inodes are finite, and exhausting them stops writes even
> with free capacity. Only the threshold differs — so **read `FilesCapacity` in your own environment
> rather than assuming a number.**

---

## FSx for ONTAP — 既定値の実測 / Measured defaults

同じ検証環境で読み取り専用に観測した既定値です。**いずれもドキュメントの記載と一致しました。**

Defaults observed read-only in the same environment. **All matched the documentation.**

| 項目 | 値 | 出典 | 検証日 | 備考 |
|---|---|---|---|---|
| SSD IOPS の既定 | **3 IOPS / GiB** | 実測 | 2026-08-06 | 3,072 IOPS ÷ 1,024 GiB。`Mode` は `AUTOMATIC`、2 ファイルシステムとも同一 |
| `AUTO` の cooling period 既定 | **31 日** | 実測 | 2026-08-06 | 該当ボリューム 17 本すべて 31 |
| `SNAPSHOT_ONLY` の cooling period 既定 | **2 日** | 実測 | 2026-08-06 | 該当ボリューム 15 本すべて 2 |
| `NONE` の cooling period | 値なし | 実測 | 2026-08-06 | 階層化しないため |
| cooling period の設定可能性 | 7 日 / 90 日の実例あり | 実測 | 2026-08-06 | 既定以外の値が設定できることの確認 |
| 第 1 世代 Single-AZ の HA ペア数 | **1** | 実測 | 2026-08-06 | 2 ファイルシステムとも `HAPairs=1` |
| デプロイタイプの変更可否 | **変更手段なし** | 実測 | 2026-08-06 | `aws fsx update-file-system` に該当パラメータが存在しません（0 件） |
| メンテナンスウィンドウの形式 | `d:HH:MM`（UTC） | 実測 | 2026-08-06 | `4:16:00` と `6:20:00` を観測 |
| ボリュームスタイルの既定 | HA ペア 1 組では FlexVol | 実測 | 2026-08-06 | FlexGroup は明示指定したものだけでした |
| セキュリティスタイル | `UNIX` / `NTFS` / `MIXED` が併存 | 実測 | 2026-08-06 | 同一ファイルシステム内で混在可能 |
| ボリューム種別 | `RW` と `DP` が併存 | 実測 | 2026-08-06 | `DP` は SnapMirror の複製先 |

検証環境 / Environment: `ap-northeast-1`、`SINGLE_AZ_1`（第 1 世代）、HA ペア 1 組、スループット
128 MBps、SSD 1,024 GiB、SSD IOPS 3,072（`AUTOMATIC`）、ファイルシステム 2 台・ボリューム 43 本。
**ONTAP バージョンはこの節の観測時点では取得できていません**（`DescribeFileSystems` は
`FileSystemTypeVersion` を返しません）。後日 2 台のうち 1 台のみ ONTAP REST API で `9.17.1P7D1` を
確認しました。取得経路は
「[ONTAP バージョンの取得経路](#ontap-バージョンの取得経路--where-the-ontap-version-comes-from)」にあります。

測定方法 / Method: AWS CLI と CloudWatch の**読み取り専用の観測のみ**。作成・変更・削除は行っていません。
`FilesCapacity` と `FilesUsed` は `Maximum` 統計、期間 3,600 秒。

> **この節が示すのは「この環境の既定値」です。** サービス全体の仕様として引用しないでください。
> 第 2 世代・Multi-AZ・他リージョンでは異なりえます。
>
> **This section records defaults in this environment**, not service-wide specifications. Second
> generation, Multi-AZ, and other Regions may differ.

---

## 作成・変更・削除を伴う実測 / Measured with mutating operations

専用に作成したボリューム上で実施し、**終了後に削除しました**（1 件を除く。後述）。
検証日 2026-08-06、環境は下記。

Performed on purpose-created volumes and **deleted afterwards** (with one exception, noted below).
Verified 2026-08-06 in the environment recorded below.

### inode を使い切ったときの挙動 / Behaviour on inode exhaustion

**このリポジトリで最も重要な実測結果です。** 20 MiB（FlexVol の最小サイズ）のボリュームを NFSv3 で
マウントし、ファイルを作り続けました。

| 項目 | 値 | 備考 |
|---|---|---|
| 総 inode 数（20 MiB ボリューム） | **566** | `df -i` |
| **作成直後に使用済みの inode** | **96** | 空のボリュームでも 0 ではありません |
| 作成できたファイル数 | 470 | 566 − 96 |
| 使い切った時点の `df -i` | `IUsed 566 / IFree 0 / IUse% 100%` | — |
| 同時点の `df -h` | **19M 中 448K 使用（3%）** | **容量はほぼ空です** |
| **新規ファイルの作成** | **失敗**: `No space left on device` | — |
| **既存ファイルへのデータ書き込み** | **成功** | 書き込み自体は止まりません |

> **エラーメッセージが間違ったリソースを指します。** `No space left on device`（`ENOSPC`）は容量不足を
> 示す文面ですが、実際に枯渇しているのは inode です。**容量を見て「空いている」と判断すると原因に到達できません。**
> そして**止まるのは「作成」だけで、既存ファイルへの書き込みは続きます。** 症状が部分的なため、
> アプリケーションによっては一部の操作だけが失敗します。
>
> **The error names the wrong resource.** `No space left on device` (`ENOSPC`) reads as a capacity
> problem, but what is exhausted is inodes. **Checking free capacity leads away from the cause.** And
> only *creation* stops — writes to existing files continue, so the symptom is partial.

**20 MiB での比率は大きいボリュームと一致しません。** 37,052 B/inode であり、100 GiB〜2 TiB で観測した
34,493 B/inode とは異なります。**上の比率は最小サイズまで外挿できません。**

### Snapshot は 1 ボリューム 1,023 個で止まる / The snapshot ceiling is 1,023 per volume

ドキュメント記載の 1,023 を実測で確認しました。**ただし到達には十分な容量が必要で、小さいボリュームでは
先に容量で止まります。** 対照実験として 2 つのサイズで実施しました。

The documented ceiling of 1,023 was reproduced. **Reaching it requires enough space, though — on a small
volume the space limit binds first.** Run as a two-size control.

| ボリュームサイズ | 止まった個数 | 止まった理由 | エラーコード |
|---|---|---|---|
| 100 MiB | **694** | `No space left on device. Additional space required: 68.0KB.` | `524479` |
| 同ボリュームを 8 GiB に拡張後 | **1,023** | `Cannot exceed maximum number of snapshots.` | `525062` |

| 項目 | 値 | 出典 | 検証日 | 備考 |
|---|---|---|---|---|
| 1 ボリュームあたりの Snapshot 上限 | **1,023 個** | 実測 | 2026-08-06 | 1,024 個目が `500` で拒否。`num_records` は 1,023 |
| 上限到達時のエラー | `Cannot exceed maximum number of snapshots.` | 実測 | 2026-08-06 | ONTAP エラーコード `525062` |
| 1,023 個分の Snapshot メタデータ | **156,659,712 B**（約 149 MiB） | 実測 | 2026-08-06 | **空のボリューム**で。1 個あたり約 150 KiB |
| Snapshot 予約の既定 | **5%** | 実測 | 2026-08-06 | 8 GiB では 429,494,272 B |
| 予約に対する使用率 | 36% | 実測 | 2026-08-06 | 1,023 個時点 |

> **1,023 は「容量が足りていれば」の上限です。** 小さいボリュームでは Snapshot メタデータの置き場所が
> 先に尽きます。100 MiB では 694 個で `No space left on device` になりました。**inode 枯渇と同じく、
> このエラーも容量不足の文面で出ます。**
>
> **1,023 is the ceiling *given enough space*.** On a small volume the room for snapshot metadata runs
> out first — 694 on 100 MiB, reported as `No space left on device`. **As with inode exhaustion, the
> message reads as a capacity problem.**

> **空のボリュームでも 1 個あたり約 150 KiB を消費します。** データを持つボリュームでは変化する前提の
> 値ですが、**「Snapshot はほぼ容量を食わない」という前提で保持数を決めると予約を超えます。**
>
> **Even on an empty volume each snapshot costs roughly 150 KiB.** The figure will differ on a volume
> holding data, but **planning retention on the assumption that snapshots are nearly free will overrun
> the reserve.**

測定方法 / Method: ONTAP REST `POST /api/storage/volumes/{uuid}/snapshots` を連続実行。
**`CreateSnapshot` は FSx for OpenZFS 専用**のため、この用途には使えません（下記参照）。
検証後、ボリュームは削除しました。

### DP ボリュームはバックアップできない / DP volumes are not backupable

**対照実験として RW ボリュームでも同じ操作を行いました。**

| 対象 | 結果 |
|---|---|
| `DP` ボリューム（SnapMirror 複製先） | **拒否**: `BadRequest ... Volume with type DP is not backupable.` |
| `RW` ボリューム（対照） | **成功**: `USER_INITIATED` のバックアップが作成された |

### 階層化ポリシーの既定は作成経路で決まる / The tiering default follows the creation path

**AWS CLI で `TieringPolicy` を指定せずにボリュームを作成しました。** 作成経路を自分で制御したので、
相関ではなく**因果の確認**です。

| 作成方法 | 結果 |
|---|---|
| AWS CLI、`TieringPolicy` 未指定 | **`SNAPSHOT_ONLY` / cooling `2`** |

コンソール側（`AUTO` / 31）はこの検証では作成していません。**ドキュメント記載と、環境内に `AUTO` /
31 のボリュームが存在することの 2 点にとどまります。**

### 階層化ポリシーの変更は無停止 / Changing the tiering policy is non-disruptive

| 操作 | 結果 |
|---|---|
| `SNAPSHOT_ONLY` / 2 → `AUTO` / 45 | 適用された。`Lifecycle` は一貫して `CREATED` |

### SnapLock の不可逆性 / SnapLock irreversibility

| 項目 | 結果 |
|---|---|
| `SnaplockType` の変更 | **`UpdateVolume` に該当パラメータが存在しません。** 受理されるのは `AuditLogVolume` / `AutocommitPeriod` / `PrivilegedDelete` / `RetentionPeriod` / `VolumeAppendModeEnabled` の 5 つのみ |
| `PrivilegedDelete` の既定 | `DISABLED` |
| `AuditLogVolume` の既定 | `false` |
| `AutocommitPeriod` の既定 | `NONE` |
| `RetentionPeriod` の既定 | 既定 0 YEARS / 最小 0 YEARS / **最大 30 YEARS** |
| 作成時の `PrivilegedDelete=ENABLED` | 成功 |
| `PERMANENTLY_DISABLED` からの復帰 | **`ENABLED` も `DISABLED` も拒否**: `Privileged-delete is permanently disabled on this volume.` |

**特権削除の有効化に監査ログボリュームが必要かどうかは判定できていません。** 監査ログボリュームの作成
前と作成後の両方で有効化を試したため、**どちらが成立したのか帰属できません。**

### SnapLock 監査ログボリュームの制約 / Audit log volume constraints

**このリポジトリで最も影響が大きい制約です。** 監査ログボリュームを 1 本作ると、**そのボリューム・SVM・
ファイルシステムの 3 つが最低 6 か月間削除できなくなります。Enterprise モードでも同じです。**

The most consequential constraint recorded here. Creating a single audit log volume makes **the volume,
its SVM, and the file system undeletable for at least six months — Enterprise mode included.**

> **6 か月間削除できないのはボリュームだけではありません。** AWS ドキュメントは警告として、
> 保持期間が満了するまで**監査ログボリューム・SVM・そのSVMが属するファイルシステム**のいずれも
> 削除できないと記載しています。
>
> **The six-month lock is not limited to the volume.** AWS documentation states in a warning that until
> the retention period expires, neither the audit log volume, nor the SVM, nor the file system
> associated with that SVM can be deleted.
>
> 出典 / Source: [AWS: Deleting SnapLock volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snaplock-delete-volume.html)

| 項目 | 結果 | 区分 |
|---|---|---|
| 最小保持期間 | **6 か月**（実測値は `P6M`） | `documented` + 実測一致 |
| 削除できなくなる対象 | **ボリューム / SVM / ファイルシステム** | `documented` |
| Enterprise モードでの例外 | **ありません** | `documented` |
| マウント位置 | **`/snaplock_audit_log` のみ**。他は拒否: `SnapLock audit log volume can only be mounted at the junction path /snaplock_audit_log` | 実測 |
| ボリュームの `expiry_time` | 作成から 6 か月後の日時が入ります | 実測 |
| ログファイルの保持 | `privileged_delete` / `system` の各ログに個別の失効日時 | 実測 |

#### AWS API 経由では解除できません / The AWS API cannot release it

| 操作 | 結果 |
|---|---|
| `delete-volume` | **`DELETING` に入ったのち `CREATED` に戻ります。エラーは返りません** |
| `BypassSnaplockEnterpriseRetention=true` | **効きません**（同上） |
| `SkipFinalBackup=true` との併用 | 効きません |
| `AuditLogVolume=false` への変更 | 適用されませんでした |
| SVM 側の指定 | **Amazon FSx の API に露出していません** <!-- allow:naming - AWS の API 名 --> |

#### ONTAP REST では解除できますが、削除はできません / ONTAP REST releases the designation but not the volume

**SVM 側の指定は ONTAP REST で解除できました。しかしそれでもボリュームは削除できません。**
解除と削除可能性は別の話です。

| # | 操作 | 結果 |
|---|---|---|
| 1 | `DELETE /api/storage/snaplock/audit-logs/{svm.uuid}`（マウント状態のまま） | **失敗**: `Current SnapLock audit log volume must be unmounted before modifying or deleting the log configuration.`（`13763189`） |
| 2 | `PATCH /api/storage/volumes/{uuid}` で `nas.path` を空にしてアンマウント | 成功 |
| 3 | 再度 `DELETE .../audit-logs/{svm.uuid}` | **成功**。SVM 側の指定は消え、`num_records` が 0 になりました |
| 4 | `PATCH` で `snaplock.is_audit_log` を `false` に | **拒否**: `Field "snaplock.is_audit_log" cannot be set in this operation`（`262196`）。**読み取り専用です** |
| 5 | ボリュームをオフラインにして `DELETE /api/storage/volumes/{uuid}` | **失敗**（下記 `525057`） |

**ONTAP レベルの削除拒否メッセージは阻害要因を 5 つ列挙します。**

> `Failed to delete the volume ... The volume has unexpired WORM files or it contains files under legal
> hold or it contains unexpired locked snapshots or the volume is an unexpired SnapLock Enterprise audit
> log volume or the volume must be made online in order to permit a pending WAFL scan to complete.`
> （`525057`）

未期限の WORM ファイル / リーガルホールド下のファイル / 未期限のロック済み Snapshot /
**未期限の監査ログボリューム** / 保留中の WAFL スキャンのためオンラインが必要 — の 5 つです。

> **順序が要ります。** SVM 側の指定解除には先にアンマウントが必要で、指定を解除しても
> ボリューム側の `is_audit_log` は残ります。このフラグは読み取り専用なので、**保持期間の満了を待つ以外に
> 削除する手段が見つかりませんでした。**
>
> **The order matters.** Releasing the SVM-level designation requires unmounting first, and releasing it
> does not clear the volume's own `is_audit_log` flag. That field is read-only, so **no path to deletion
> was found other than waiting out the retention period.**

> **特権削除を恒久無効にしていると、ログファイル自体も消せません。** 本検証では
> `PrivilegedDelete=PERMANENTLY_DISABLED` を先に設定していたため、WORM 状態のログファイルを
> 特権削除で消す経路も残っていませんでした。**不可逆な操作を組み合わせた順序が、退路を狭めます。**
>
> **With privileged delete permanently disabled, the log files cannot be removed either.** This
> verification had already set `PERMANENTLY_DISABLED`, so that route was closed too. **The order in
> which irreversible operations are combined narrows the exits.**

> **検証環境で試すときも、使い捨てのファイルシステムで行ってください。** ボリューム 1 本の
> 作り直しでは済まず、**ファイルシステムごと 6 か月削除できなくなります。**
>
> **Even when testing, use a disposable file system.** The cost is not one volume to recreate — **the
> whole file system becomes undeletable for six months.**

### ボリューム削除の失敗理由は AWS API からは分かりません / A failed volume deletion cannot be diagnosed from the AWS API

**`delete-volume` は受理されて `DELETING` になり、失敗すると `CREATED` に戻ります。エラーは返りません。**
`AdministrativeActions` にも記録されません。**理由を知る手段は ONTAP REST のジョブメッセージだけでした。**

`delete-volume` is accepted, moves to `DELETING`, and on failure returns to `CREATED` — with no error and
no `AdministrativeActions` entry. **The only place the reason appeared was the ONTAP REST job message.**

| 観測点 | AWS API | ONTAP REST |
|---|---|---|
| 呼び出しの応答 | 成功（`DELETING`） | `202` + ジョブ ID |
| 失敗の通知 | **なし**（`CREATED` に戻るだけ） | ジョブが `state: failure` |
| 失敗理由 | **取得手段なし** | `message` に理由と ONTAP エラーコード |

#### 阻害要因は 1 つずつしか出ません / Blockers surface one at a time

**同一ボリュームで、解消するたびに別の理由が現れました。** 事前に一覧を得る方法はありませんでした。

| 順 | ONTAP が返した理由 | コード | 実際の原因 |
|---|---|---|---|
| 1 | SnapMirror 関係の存在（`... is the destination or source endpoint of one or more SnapMirror relationships`） | `917858` | **残っていた Amazon FSx のバックアップ** <!-- allow:naming - AWS のサービス名 --> |
| 2 | 未期限の監査ログボリューム（`525057` の 5 条件） | `525057` | SnapLock 監査ログの 6 か月保持 |

**1 番目のメッセージは調査を誤った方向へ導きます。** SnapMirror 関係を疑って
`GET /api/snapmirror/relationships/` を見ても、**該当ボリュームの関係は出てきませんでした。**

| 確認 | 結果 |
|---|---|
| `/api/snapmirror/relationships/` | 1 件。ただし**別 SVM の無関係な関係**でした |
| `/api/snapmirror/relationships/?list_destinations_only=true` | **0 件** |
| ボリューム上の Snapshot | **`backup-<backup-id>` という名前の Snapshot** が存在 |
| `describe-backups` | 同じ ID のバックアップが `AVAILABLE` / `USER_INITIATED` |

**バックアップを削除すると、この理由は出なくなりました。** バックアップが内部的に SnapMirror を使うため、
ユーザーに見える関係一覧には現れない形で削除を阻害します。

> **診断の手がかりは Snapshot 名です。** Amazon FSx のバックアップはボリューム上に <!-- allow:naming - AWS のサービス名 -->
> `backup-<backup-id>` という Snapshot を残します。**SnapMirror のエラーが出て関係一覧が空なら、
> バックアップの残骸を疑ってください。**
>
> **The diagnostic fingerprint is the snapshot name.** A backup leaves a snapshot named
> `backup-<backup-id>` on the volume. **If a SnapMirror error appears while the relationship list is
> empty, suspect a leftover backup.**

> **検証で作ったボリュームを消すときは `SkipFinalBackup=true` を付けてください。** 付けないと
> 最終バックアップが作られ、**そのバックアップ自身が次の削除を阻害します。**
>
> **Delete verification volumes with `SkipFinalBackup=true`.** Otherwise a final backup is created, and
> **that backup then blocks the next deletion.**

### `UpdateVolume` は非同期で痕跡を残さない / `UpdateVolume` is asynchronous and leaves no trace

| 項目 | 結果 |
|---|---|
| 反映までの時間 | 30 秒では未反映、120〜180 秒で反映を確認 |
| `AdministrativeActions` | **記録されません**（`null`） |
| 連続実行 | **拒否**: `Unable to perform the volume update. There is an update already in progress.` |

> **API が成功を返しても、反映されたことにはなりません。** `AdministrativeActions` にも残らないため、
> **`DescribeVolumes` を読み直す以外に確認手段がありません。** 短い待ち時間で状態を読むと
> 「無視された」と誤診します（この検証で実際に一度誤診しました）。
>
> **A successful API response is not confirmation.** Nothing is recorded in `AdministrativeActions`,
> so re-reading `DescribeVolumes` is the only way to confirm. Reading state too soon produces a false
> "silently ignored" diagnosis — which happened once during this verification.

検証環境 / Environment: `ap-northeast-1`、`SINGLE_AZ_1`（第 1 世代）、HA ペア 1 組、スループット
128 MBps、SSD 1,024 GiB。

| 検証 | ファイルシステム | ONTAP バージョン | 経路 | 検証日 |
|---|---|---|---|---|
| inode 枯渇 | 2 台のうち一方 | **未取得** | NFSv3 マウント | 2026-08-06 |
| DP バックアップ / 階層化 / SnapLock | もう一方 | **未取得**（当時） | AWS CLI | 2026-08-06 |
| Snapshot 上限 / SnapLock 監査ログの解除 | 上記と同じ一方 | **`9.17.1P7D1`** | ONTAP REST API | 2026-08-06 |

**バージョンを取得できたのは 3 行目の検証のみです。** 1〜2 行目の結果にバージョンを付けて引用しないでください。

**The version is known only for the third row.** Do not cite the first two rows as version-specific.

---

## 実測できなかった項目 / Could not be measured

| 項目 | 理由 |
|---|---|
| バックアップ 4,091 個の上限 | 現実的な回数ではありません |
| SSD 90% / 98% での階層化の挙動変化 | **実施しませんでした。** 稼働ファイルシステムの SSD 層を意図的に埋める必要があり、同一ファイルシステムの全ボリュームに影響します。テストボリュームに隔離できません |
| パッチ適用時の I/O 一時停止 | メンテナンスウィンドウの到来と、その間の継続的な I/O 負荷の両方が必要です |
| 作成経路のうちコンソール側 | この検証ではコンソールを使用していません |
| 特権削除と監査ログボリュームの因果 | 上記のとおり帰属できません |

---

## 追加テンプレート / Template for new entries

```markdown
## <対象 / Subject>

| 項目 | 値 | 出典 | 検証日 | 備考 |
|---|---|---|---|---|
| TODO | TODO | TODO | YYYY-MM-DD | TODO |

検証環境 / Environment: TODO
```

---

## 関連ドキュメント / Related documents

- [知見の分類ポリシー](../../evidence-policy.md) / [Evidence Policy](../../../en/evidence-policy.md)
- [Playbook 02 — 設計](../../playbooks/02-design/) / [Design](../../../en/playbooks/02-design/README.md)

---

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md)
