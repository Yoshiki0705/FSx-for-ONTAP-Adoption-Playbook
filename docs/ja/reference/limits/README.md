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
**ONTAP バージョンは取得できていません**（`DescribeFileSystems` が `FileSystemTypeVersion` を
返しませんでした）。

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

| 項目 | 結果 |
|---|---|
| マウント位置 | **`/snaplock_audit_log` のみ**。他のジャンクションパスは拒否: `SnapLock audit log volume can only be mounted at the junction path /snaplock_audit_log` |
| **AWS API での削除** | **できません。** `BypassSnaplockEnterpriseRetention=true` でも `Lifecycle` が `CREATED` に戻ります。理由: `Cannot delete the volume because it is configured as a SnapLock audit log volume` |
| `AuditLogVolume=false` への変更 | 適用されませんでした |
| SVM 側の指定 | **Amazon FSx の API に露出していません** <!-- allow:naming - AWS の API 名 --> |

Enterprise ボリュームの削除拒否メッセージは、阻害要因を 4 つ列挙します。**未期限の WORM ファイル、
リーガルホールド下のファイル、未期限のロック済み Snapshot、未期限の監査ログボリューム**です。

> **監査ログボリュームは作る前に置き場所を決めてください。** AWS API では取り消せません。
>
> **Decide where an audit log volume goes before creating one.** The AWS API cannot undo it.

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
128 MBps、SSD 1,024 GiB。inode 検証のみ別ファイルシステム（同一構成、同一リージョン）で実施し、
NFSv3 でマウントしました。**ONTAP バージョンは取得できていません。**

---

## 実測できなかった項目 / Could not be measured

| 項目 | 理由 |
|---|---|
| Snapshot 1,023 個の上限 | **`CreateSnapshot` は FSx for OpenZFS 専用**です。ONTAP ボリュームでは `Unable to create a snapshot because the volume was not found` になります。ONTAP CLI / REST が必要で、`fsxadmin` の資格情報がありません |
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
