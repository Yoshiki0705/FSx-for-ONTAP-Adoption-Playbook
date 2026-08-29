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
| ONTAP REST `GET /api/cluster?fields=version` | **返ります**（2026-08-06 は `NetApp Release 9.17.1P7D1`、2026-08-17 は `NetApp Release 9.18.1P3D1`） |

| 項目 | 値 | 出典 | 検証日 | 備考 |
|---|---|---|---|---|
| ONTAP バージョン | `9.17.1P7D1` | 実測 | 2026-08-06 | ビルド日時も併せて返ります |
| ONTAP バージョン（同一ファイルシステム、再取得） | **`9.18.1P3D1`** | 実測 | 2026-08-17 | ビルド 2026-06-20。**11 日で世代が上がっています** |
| ONTAP REST の認証 | `fsxadmin` の Basic 認証 | 実測 | 2026-08-06 / 2026-08-17 | 未認証は `401` |

> **記録したバージョンは古くなります。** 同じファイルシステムで 11 日後に再取得したら別の版でした。
> ONTAP のパッチ適用はサービス側で実施され、14 日ごとに保守が発生するため、**バージョンを前提にした
> 記述は取得日と一緒に読む必要があります。** 版に依存する挙動を書くときは、取得日を必ず添えてください。
>
> **A recorded version goes stale.** Re-reading the same file system 11 days later returned a different
> release. ONTAP patching is performed by the service and maintenance occurs at least every 14 days, so
> **any statement premised on a version has to be read together with the date it was read.** Always
> attach that date when recording version-dependent behaviour.

> **保存された資格情報は、実際のパスワードと無言で乖離します。** 2026-08-17 の再取得時、Secrets Manager に
> 保存されていた `fsxadmin` の値は `401 User is not authorized` になりました。過去 3 バージョンを試しても
> 同じでした。パスワード更新の管理アクションは完了しており、シークレットはその後に書き直されていた
> ため、**「シークレットが最近更新されている」ことは、その値が通ることの証拠になりません。**
>
> **A stored credential diverges from the real password silently.** On 2026-08-17 the `fsxadmin` value
> held in Secrets Manager returned `401 User is not authorized`, and so did the three preceding
> versions — even though the password-update administrative action had completed and the secret had
> been rewritten afterwards. **"The secret was updated recently" is not evidence that its value works.**

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

## FSx for ONTAP S3 AP — アクセスポイントポリシーのサイズ / Access point policy size

**ドキュメント記載値と、拒否が始まる実際のバイト数が一致しない項目です。** 判定が**正規化後**の
文書に対して行われるため、手元の JSON のバイト数を予算として使えません。

This is an item where the documented value and the byte count at which rejection begins **do not
line up**, because the check runs against the **normalized** document. The byte count of the JSON in
your editor is therefore not a usable budget.

| 項目 | 値 | 出典 | 検証日 | 備考 |
|---|---|---|---|---|
| ポリシーの上限 | 20 KB | [AWS: Access points restrictions and limitations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-points-restrictions-limitations-naming-rules.html) | — | ドキュメント記載。正規化後の文書に対する上限 |
| 受理された最大 | 24,620 B | 実測 | 2026-08-17 | 整形なし JSON、`Allow` 文 102 個 |
| 拒否された最小 | 24,861 B | 実測 | 2026-08-17 | `MalformedPolicy: Normalized policy document exceeds the maximum allowed size` |
| Amazon FSx API のフィールド制約 | 1〜200,000 文字 | [AWS: CreateAndAttachS3AccessPoint](https://docs.aws.amazon.com/fsx/latest/APIReference/API_CreateAndAttachS3AccessPointOntapConfiguration.html) | — | **実効上限ではありません。** S3 側がこれよりはるかに早く拒否します <!-- allow:naming - AWS のサービス名 --> |

> **設計上の注意**: 境界はポリシーの書き方で動きます。**上限に近づく設計を避け、Access Point を
> 分けてください。** ポリシーを渡す API がフィールドとして受け付ける文字数は、通ることの保証では
> ありません。
>
> **Design note**: the boundary moves with how the policy is written. **Avoid designs that approach
> the limit; split into more access points instead.** The character count a field accepts is not a
> guarantee that the document will be accepted.

検証環境 / Environment: `ap-northeast-1`。測定手順と全パターンは
[S3 Access Point の権限設計 — 評価順序と、絞り込みを担う 2 つの層](../../domains/security-governance/notes/access-point-authorization-layers.md)
にあります。

---

## FSx for ONTAP — SVM の数はスループット容量で決まる / The SVM count depends on throughput capacity

**SVM の上限はファイルシステム単位の固定値ではなく、スループット容量に紐づきます。** 検証用に
SVM を追加しようとして拒否され、エラー本文に上限とその根拠が含まれていました。

The SVM ceiling is **not a fixed per-file-system number** — it is tied to the file system's
throughput capacity. The refusal message states both the ceiling and what it depends on.

| 項目 | 値 | 出典 | 検証日 | 備考 |
|---|---|---|---|---|
| 128 MBps 構成の SVM 上限 | 6 | 実測 | 2026-08-18 | `ServiceLimitExceeded: ... more than 6 storage virtual machines for an ONTAP file system with 128 MBps of throughput capacity` |

> **設計上の注意**: **SVM を増やす計画は、スループット容量の計画と同時に決めてください。** 上限に
> 当たったときの選択肢はスループット容量の引き上げで、これは課金に直結します。**検証や一時的な
> 用途で SVM を消費すると、後から本番用の SVM を追加できなくなります。**
>
> **Design note**: **plan SVM count together with throughput capacity.** The remedy when you hit the
> ceiling is to raise throughput capacity, which changes the bill. **Consuming SVMs for verification
> or temporary purposes can block adding a production SVM later.**

検証環境 / Environment: `ap-northeast-1`、ONTAP `9.18.1P3D1`。

---

## FSx for ONTAP — バックアップのリージョン間コピー / Cross-Region backup copies

**2026 年 8 月に追加された経路です。** それ以前は同一リージョン・同一アカウントでの作成と復元に
限られていました。**復元先がバックアップと同一リージョンである制約は変わっていません。**

A path added in August 2026. Before it, creation and restore were confined to the file system's own
Region and account. **The constraint that a restore target must sit in the backup's Region is unchanged.**

| 項目 | 値 | 出典 | 検証日 | 備考 |
|---|---|---|---|---|
| 同時コピー数（1 ボリューム・1 宛先リージョン・1 KMS キー） | 5 件 | [AWS: Copying backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copy-backups.html) | — | ドキュメント記載。**未実測** |
| 同時コピー数（アカウント単位） | 1,000 件 | 同上 | — | 超過分は拒否。**未実測** |
| パーティション跨ぎ | 不可 | 同上 | — | 商用 / 中国 / GovCloud の 3 セット間。**未実測** |
| FlexGroup バックアップのコピー | 非対応 | 同上 | — | **踏めていません**（下記） |
| 別アカウントコピー | AWS Backup + AWS Organizations が前提 | 同上 | — | FSx for ONTAP の API 単体では不可。**未実測** |
| 初回コピー | 別リージョンへの初回は必ずフル | 同上 | — | 以降は同一 KMS キーかつ既存コピー保持が条件で増分 |
| コピー中のソース削除 | **拒否** | 実測 | 2026-08-28 | `BadRequest ... is being copied, can't be deleted` |
| 削除済みボリュームのバックアップのコピー | **成功** | 実測 | 2026-08-28 | `Volume.Lifecycle: DELETED` のバックアップをコピーできました |
| コピー所要時間（9.4 MiB） | 7 分 15 秒 | 実測 | 2026-08-28 | `ap-northeast-1` → `ap-northeast-3` |
| 同一宛先への 2 回目（11.4 MiB） | 6 分 01 秒 | 実測 | 2026-08-28 | **増分かどうかはこの規模では判定できません** |
| コピー済みバックアップからの復元（`CREATED` まで） | 13 分 21 秒 | 実測 | 2026-08-28 | 第 1 世代 `SINGLE_AZ_1` / 128 MBps、データ 9.4 MiB |
| 宛先ファイルシステムの作成 | 約 20 分 | 実測 | 2026-08-28 | **復旧手順に含める場合、この時間が RTO に乗ります** |

> **所要時間は固定オーバーヘッドが支配しています。** 9.4 MiB のデータに対する値であり、**サイズ依存の
> 部分はほとんど見えていません。自環境の RTO の根拠には使えません。** 公式ドキュメントは復元を
> 「数分から数時間」とし、サイズ依存であることを明記しています。
>
> **These durations are dominated by fixed overhead.** They were measured against 9.4 MiB, so the
> size-dependent component is essentially invisible. **They cannot serve as an RTO basis for another
> environment.** AWS documents restore as taking "a few minutes to a few hours", depending on size.

### 復元中は `OntapVolumeType` が `DP` と返ります / `OntapVolumeType` reads `DP` mid-restore

| 状態 | `OntapVolumeType` | 出典 | 検証日 |
|---|---|---|---|
| 復元中（`CREATING`） | **`DP`** | 実測 | 2026-08-28 |
| 復元完了後（`CREATED`） | `RW` | 実測 | 2026-08-28 |

`CREATED` 直後の値を読んで `DP` と記録し、恒久的な性質と誤読しかけました。**クライアントからの書き込みは
成功し**、読み直すと `RW` でした。`OntapVolumeType: RW` を明示した 2 回目の復元でも `CREATING` の間は
`DP` を返したため、CLI の既定値ではなく過渡状態です。

An initial reading taken right at `CREATED` caught `DP` and looked like a permanent property. **A write
from the client succeeded**, and a re-read returned `RW`. A second restore that stated
`OntapVolumeType: RW` explicitly also reported `DP` while `CREATING`, so the value is transient rather
than a CLI default.

> **この値を自動化の判定に使う場合、復元中は `DP` を見ます。** DP ボリュームはバックアップ対象外なので、
> 「復元直後に自動でバックアップを取る」処理は状態に依存して結果が揺れます。
>
> **Automation that reads this field sees `DP` during a restore.** Since DP volumes are not backupable, a
> "back up immediately after restore" step behaves differently depending on when it reads.

### 復元で引き継がれない属性 / Attributes not carried over by a restore

| 属性 | ソース | 復元後 | 出典 | 検証日 |
|---|---|---|---|---|
| `StorageEfficiencyEnabled` | `false` | **`true`**（CLI で省略時）/ `false`（明示時） | 実測 | 2026-08-28 |
| `SecurityStyle` | `UNIX` | **API 応答では空**（CLI・コンソールの両方） | 実測 | 2026-08-28 |
| `VolumeStyle` | `FLEXVOL` | `FLEXVOL` | [AWS: using-backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-backups.html) | — |
| ボリュームサイズ（コンソールの既定） | 1 GiB | **1 TiB** | 実測 | 2026-08-28 |

> **訂正**: `StorageEfficiencyEnabled` は当初「引き継がれない」と記載していました。**誤りです。**
> コンソールから復元するとバックアップ元の値が初期選択され、そのまま `false` で復元されました。
> 最初に `true` になったのは **CLI でこのフィールドを省略したため**で、復元の挙動ではなく API の既定値です。
>
> **Correction**: this row originally read as "not carried over". **That was wrong.** Restoring through the
> console pre-selects the source value and it restored as `false`. The initial `true` came from **omitting
> the field in the CLI call** — an API default, not restore behaviour.

`SecurityStyle` が空になる件は **CLI とコンソールの 2 経路で同じ結果**です。ただしソースボリュームは
同一（UNIX）で、他のセキュリティスタイルでは確認していません。NFS 経由のパーミッション動作は UNIX
として正しく、フィールドのみ空でした。

The empty `SecurityStyle` reproduced across **both the CLI and the console**, though against the same
UNIX-style source volume; other security styles were not tested. UNIX mode bits behaved correctly over
NFS — only the field was empty.

**コンソールのサイズ既定は事故になりえます。** ソースが 1 GiB でも既定は 1 TiB で、1,024 GiB の
宛先ファイルシステムではこれで容量を使い切ります。

**The console's size default is a hazard.** It is 1 TiB even for a 1 GiB source, which fills a
1,024 GiB destination file system on its own.

### コンソール操作時の挙動 / Console-specific behaviour

| 項目 | 挙動 | 出典 | 検証日 |
|---|---|---|---|
| コピー画面の送信先リージョン既定 | **同一リージョン**。別リージョンは明示的な変更が必要 | 実測 | 2026-08-28 |
| 宛先リージョン変更時の KMS キー表示 | **宛先リージョンの既定キーに切り替わる** | 実測 | 2026-08-28 |
| 復元ダイアログの必須項目 | ファイルシステムに加えて **SVM が必須** | 実測 | 2026-08-28 |
| 復元中のボリューム詳細 | 「作成」+ `DP` を表示。RW を明示していても同じ | 実測 | 2026-08-28 |
| 復元完了時の詳細画面 | **自動更新されません。** 再読み込みまで `DP` のまま表示 | 実測 | 2026-08-28 |
| 復元ダイアログの SnapLock | **この画面から有効化できます**（不可逆。有効化は別承認） | 実測 | 2026-08-28 |

### FlexGroup — バックアップ作成が非同期で失敗しました / FlexGroup backup creation failed asynchronously

**ドキュメントの制約はコピーに掛かっており、作成には言及がありません。** 検証では作成側で止まりました。

| 操作 | 結果 | 出典 | 検証日 |
|---|---|---|---|
| FlexGroup への `CreateBackup`（API 応答） | **受理**（`CREATING`） | 実測 | 2026-08-28 |
| 約 30 秒後の状態 | **`FAILED`**。`Backup failed. Please delete the backup and try again.` | 実測 | 2026-08-28 |
| 対照: FlexVol RW への `CreateBackup` | **成功**（`USER_INITIATED`） | 実測 | 2026-08-28 |
| SnapLock FlexGroup のバックアップ | 不可 | [AWS: using-backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-backups.html) | — |

> **1 ボリュームでの 1 回の観測で、再現確認は未実施です。一般化しません。** 対象は単一コンスティチュエント・
> 1 アグリゲート・113 GiB プロビジョンの非 SnapLock FlexGroup で、対照の FlexVol は同一セッション・同一
> 資格情報で成功しています。公式ドキュメントは FlexGroup バックアップの**復元**挙動を記述しており、
> 作成できない前提とは読めません。**`AVAILABLE` な FlexGroup バックアップが得られなかったため、
> ドキュメント記載のコピー制約そのものは踏めていません。**
>
> **Observed once on one volume and not reproduced; not generalized.** The target was a non-SnapLock
> FlexGroup with a single constituent on one aggregate, 113 GiB provisioned, and the FlexVol control
> succeeded in the same session with the same credentials. AWS documentation describes the *restore*
> behaviour of FlexGroup backups, which does not read as creation being unsupported. **Because no
> `AVAILABLE` FlexGroup backup was produced, the documented copy restriction itself was never exercised.**

検証環境 / Environment: コピー元 `ap-northeast-1`、コピー先 `ap-northeast-3`、いずれも第 1 世代
`SINGLE_AZ_1` / SSD 1,024 GiB / 128 MBps、既定 KMS キー（`aws/fsx`）、同一アカウント。
ONTAP `9.17.1P7D1`。詳細は
[バックアップコピーは復元するまでファイルシステムを持たない](../../domains/data-protection/notes/backup-copies-across-regions-and-accounts.md)
にあります。

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

#### 期間を縛るパラメータはボリュームの保持期間ではありません / The binding parameter is not the volume retention

**SnapLock には保持期間を表すパラメータが複数あり、ロックの原因になるのは 1 つです。** 混同すると
「保持期間を最小にしたのにロックされた」という状況になります。

SnapLock exposes more than one retention setting and only one causes the lock. Conflating them produces
the situation where the volume retention is already at its minimum and the lock still happens.

| パラメータ | 設定できる値 | 何を縛るか | 本検証での値 |
|---|---|---|---|
| ボリュームの `RetentionPeriod` | 秒〜年。**0 も可** | ボリューム上の WORM ファイル | Default **0 YEARS** / Minimum **0 YEARS** |
| **監査ログ設定の保持期間** | ドキュメント上の下限 **6 か月** | 監査ログファイル → ボリュームの `expiry_time` | **`P6M`**（既定値が適用） |

| API | 監査ログ保持期間の指定 | 出典 |
|---|---|---|
| Amazon FSx `CreateSnaplockConfiguration` | **不可。** フィールドは `SnaplockType` / `AuditLogVolume` / `AutocommitPeriod` / `PrivilegedDelete` / `RetentionPeriod` / `VolumeAppendModeEnabled` の 6 つで、`RetentionPeriod` は**ボリュームの WORM ファイル用**です | [API Reference](https://docs.aws.amazon.com/fsx/latest/APIReference/API_CreateSnaplockConfiguration.html) <!-- allow:naming - AWS の API 名 --> |
| ONTAP `snaplock log create -retention-period` | **可** | [NetApp Docs](https://docs.netapp.com/us-en/ontap/snaplock/create-audit-log-task.html) |

> **`AuditLogVolume=true` を AWS API で渡すと、保持期間は選べず既定値が適用されます。** 値を制御するには
> ONTAP 側で作成する必要があります。**「最小値を設定する」運用ルールは、指定手段のない API では機能しません。**
>
> **Passing `AuditLogVolume=true` through the AWS API applies the default; the value cannot be chosen there.**
> Controlling it requires creating the log configuration through ONTAP. **A "always use the minimum" policy
> does not function on an API that cannot express the value.**

> **6 か月より短い値が拒否されるかは実測していません**（`documented`）。試すには監査ログボリュームを
> もう 1 本作る必要があり、失敗すれば同じロックが増えます。
>
> **Whether a value below six months is rejected was not measured** (`documented`). Testing it requires
> creating another audit log volume, where a failed test adds another six-month lock.

#### AWS API 経由では解除できません / The AWS API cannot release it

| 操作 | 結果 |
|---|---|
| `delete-volume` | **`DELETING` に入ったのち `CREATED` に戻ります。エラーは返りません** |
| `BypassSnaplockEnterpriseRetention=true` | **効きません**（同上） |
| `SkipFinalBackup=true` との併用 | 効きません |
| `AuditLogVolume=false` への変更 | 適用されませんでした |
| SVM 側の指定 | **Amazon FSx の API に露出していません** <!-- allow:naming - AWS の API 名 --> |

> **ONTAP 側で指定を解除した後、AWS API は `AuditLogVolume: False` を返すようになりました。
> しかしボリュームは依然として削除できません。** ONTAP 側の `snaplock.is_audit_log` は `true` のままで、
> こちらが削除を阻害します。**AWS API の表示だけを見ると「監査ログボリュームではない」と読めるため、
> 削除できない理由が消えたように見えます。** 実際には変わっていません。
>
> **After releasing the designation at the ONTAP level, the AWS API began reporting
> `AuditLogVolume: False` — while the volume remained undeletable.** ONTAP's own `snaplock.is_audit_log`
> is still `true`, and that is what blocks deletion. **Read only the AWS API and the volume no longer looks
> like an audit log volume**, which makes the blocker appear to have gone. It has not.

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

### ボリューム削除の失敗理由は `LifecycleTransitionReason` にあります / The reason for a failed volume deletion is in `LifecycleTransitionReason`

> **訂正**: 本節は当初「AWS API からは失敗理由が分からない」と記載していました。**誤りです。**
> `DescribeVolumes` の **`LifecycleTransitionReason`** に理由が入ります。当初は `Lifecycle` と
> `AdministrativeActions` しか読んでいませんでした。
>
> **Correction**: this section originally claimed the reason was unavailable from the AWS API. **That was
> wrong.** It is in `LifecycleTransitionReason` on `DescribeVolumes`. Only `Lifecycle` and
> `AdministrativeActions` had been read.

**`delete-volume` の応答自体には理由が含まれず、`DELETING` を経て `CREATED` に戻ります。**
理由は**その後の `DescribeVolumes`** で取得します。

The `delete-volume` response itself carries no reason — the volume moves to `DELETING` and returns to
`CREATED`. The reason is retrieved by a **subsequent `DescribeVolumes`**.

| 観測点 | AWS API | ONTAP REST |
|---|---|---|
| 呼び出しの応答 | 成功（`DELETING`）。理由なし | `202` + ジョブ ID |
| 失敗の通知 | `CREATED` に戻る（コンソールでは警告アイコン） | ジョブが `state: failure` |
| 失敗理由 | **`LifecycleTransitionReason.Message`** | `message` に理由と ONTAP エラーコード |
| `AdministrativeActions` | `null`（削除操作は記録されません） | — |

本件で実際に返った値です。

| フィールド | 値 |
|---|---|
| `Lifecycle` | `CREATED` |
| **`LifecycleTransitionReason.Message`** | **`Cannot delete the volume because it contains unexpired log files.`** |

> **AWS API のほうが的確でした。** ONTAP は 5 条件を列挙しますが、AWS は「未期限のログファイル」と
> 原因を特定して返します。**取得手段がなかったのではなく、正しいフィールドを読んでいませんでした。**
>
> **The AWS API was the more precise of the two.** ONTAP enumerates five conditions; AWS names the actual
> cause. **The information was not missing — the right field had not been read.**

この挙動は AWS ドキュメントに記載があります。`DELETING` から `CREATED` へ戻るのが失敗のサインであり、
コンソールでは警告アイコンから理由を確認できます。出典:
[You can't delete a storage virtual machine or volume](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/cannot-delete-svm.html)

> **ただし同ページは阻害要因として SnapLock 監査ログボリュームを挙げていません。** 列挙されているのは
> ルートテーブル / ピア関係 / SnapMirror / Kerberos LIF / その他 / FlexCache です。**トラブルシューティング
> ページだけを見ると、今回の原因には到達できません。**
>
> **That page does not list SnapLock audit log volumes among the causes**, however — it covers route
> tables, peer relationships, SnapMirror, Kerberos LIFs, "other", and FlexCache. **The troubleshooting page
> alone does not lead to this cause.**

#### 阻害要因は 1 つずつしか出ません / Blockers surface one at a time

**同一ボリュームで、解消するたびに別の理由が現れました。** 事前に一覧を得る方法はありませんでした。
これは `LifecycleTransitionReason` でも ONTAP のジョブメッセージでも同じです。

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

## Snapshot locking（Tamperproof Snapshot）/ Snapshot locking (Tamperproof Snapshot)

**SnapLock 監査ログボリュームと同じ「削除できなくする」分類の機能です。** 監査ログボリュームより
適用範囲が広く、**SnapLock ボリュームでなくても有効にできます。**

The same "removes the ability to delete" class as the SnapLock audit log volume, with **wider reach: it can
be enabled on volumes that are not SnapLock volumes at all.**

> **本節は `documented` です。実測していません。** 有効化すると同種の削除ロックを新たに発生させるため、
> 本リポジトリでは検証しません。
>
> **This section is `documented`, not measured.** Enabling it would create a fresh lock of the same kind, so
> it is deliberately not verified here.

### 「SnapLock を使っていない」は保護になりません / "We do not use SnapLock" is not protection

| 項目 | 内容 |
|---|---|
| 対象ボリューム | **非 SnapLock ボリュームでも可**（ONTAP 9.12.1 以降） |
| 必要なもの | SnapLock ライセンス（ONTAP One に含まれる）、**コンプライアンスクロックの初期化** |
| 必要バージョン | ONTAP CLI は 9.12.1 以降、System Manager は 9.13.1 以降 |
| **無効化** | **全ロック済み Snapshot が失効するまで不可** |
| **ボリュームの削除** | **未期限のロック済み Snapshot があると不可** |
| ボリュームの `expiry_time` | **ロック済み Snapshot の最大失効時刻**が設定されます |
| ONTAP のダウングレード | 全ロック済み Snapshot 失効＋ locking 無効化までリバート不可 |
| リストア | ロック済み Snapshot は**最新のものだけ**復元可。より新しい未期限 Snapshot があると失敗 |
| FlexGroup | root constituent にロックがかかり、**その失効までボリュームを削除できません** |

ONTAP CLI は有効化時に警告と確認を出します。**構造は監査ログボリュームと同一です。**

> `Warning: snapshot locking is being enabled on volume "vol1" in Vserver "vs1". It cannot be disabled
> until all locked snapshots are past their expiry time. A volume with unexpired locked snapshots cannot
> be deleted.`

**これは `525057` の 5 条件のうち「未期限のロック済み Snapshot」に対応します。** 監査ログボリュームと
同じ経路で削除を阻害します。

### 保持期間は短く設定できます / The retention period can be set short

**監査ログボリュームとの決定的な違いです。** 監査ログには 6 か月の下限がありますが、Snapshot locking の
保持期間は**時間単位まで**選べます。

| 単位 | 範囲 |
|---|---|
| Years | 0 – 100 |
| Months | 0 – 1200 |
| Days | 0 – 36500 |
| **Hours** | **0 – 24** |

| 指定方法 | コマンド |
|---|---|
| ポリシーで一括 | `volume snapshot policy create -policy <name> -enabled true -schedule1 <sched> -count1 <n> -retention-period1 <period>` |
| 個別 Snapshot（作成時） | `volume snapshot create -volume <vol> -snapshot <name> -snaplock-expiry-time <datetime>` |
| 個別 Snapshot（既存） | `volume snapshot modify-snaplock-expiry-time -volume <vol> -snapshot <name> -snaplock-expiry-time <datetime>` |
| SnapMirror 宛先の長期保持 | `snapmirror policy add-rule ... -retention-period "<n> months"` |

> **短い値を選べるからこそ、値を決めずに有効化してはいけません。** 監査ログボリュームは「下限が許容できない」
> ケースでしたが、Snapshot locking は「**選べたのに選ばなかった**」になり得ます。
>
> **Precisely because a short value is available, do not enable this without choosing one.** With the audit
> log volume the floor itself was unacceptable; here the failure mode is **having had the choice and not
> making it.**

### 保持期間は世代数より優先されます — 1,023 上限との複合 / Retention overrides keep count, which compounds with the 1,023 ceiling

**ロック済み Snapshot は、ポリシーの `count` を超えても削除されません。** 保持期間が世代数より優先されます。

Locked snapshots are **not** reclaimed when the policy's keep count is exceeded — the retention period takes
precedence.

ここに実測値が効いてきます。

| 要素 | 値 | 区分 |
|---|---|---|
| 1 ボリュームあたりの Snapshot 上限 | **1,023 個** | **実測**（[上記](#snapshot-は-1-ボリューム-1023-個で止まる--the-snapshot-ceiling-is-1023-per-volume)） |
| Snapshot 1 個あたりのメタデータ | 空のボリュームで約 **150 KiB** | **実測** |
| ロック済み Snapshot への `count` 適用 | **されません** | `documented` |

> **毎時スケジュール × 長い保持期間で、世代数の上限が効かないまま 1,023 に近づきます。** そして
> **到達したロック済み Snapshot は削除できません。** 新規 Snapshot の作成が止まり、
> **保持期間の満了を待つ以外に復旧手段がありません。**
>
> **An hourly schedule with a long retention approaches 1,023 with the keep count not applying** — and the
> locked snapshots that got there **cannot be deleted.** New snapshot creation stops, and **waiting out the
> retention period is the only recovery.**
>
> 保持期間 × スケジュール頻度が 1,023 を超えないことを、有効化前に計算してください。
> Calculate that retention × schedule frequency stays under 1,023 **before** enabling.

### FabricPool との関係はドキュメント間で記述が異なります / The FabricPool relationship is stated differently across documents

**FSx for ONTAP の容量プール階層化は FabricPool です。** そのため、この点は本サービスでは直接効きます。

| 出典 | 記載 |
|---|---|
| [NetApp Docs: Lock an ONTAP snapshot](https://docs.netapp.com/us-en/ontap/snaplock/snapshot-lock-concept.html) | **Unsupported features** に FabricPool を挙げ、FabricPool は削除能力を要するため snapshot lock と同一ボリュームで併用できないと記載 |
| [NetApp KB: Setting up Tamperproof or Snapshot locking fails for FabricPool volumes](https://kb.netapp.com/onprem/ontap/dp/SnapLock/Setting_up_Tamperproof_or_Snapshot_locking_fails_for_FabricPool_volumes) | 階層化ポリシーが `none` 以外、またはオブジェクトストアへ階層化済みのボリュームでは有効化できないと記載 |
| [NetApp KB: Why is TPS supported on fabricpool volumes in FSx but not on-prem ONTAP](https://kb.netapp.com/on-prem/ontap/DP/SnapLock-KBs/Why_is_TPS_supported_on_fabricpool_volumes_in_FSx_but_not_on-prem_ONTAP%3F) <!-- allow:naming --> | **FSx for ONTAP では** ONTAP インスタンスとオブジェクトストアが完全にマネージドでアクセス不能なため、SnapLock Compliance と Tamperproof Snapshot Locking をサポートできると記載 |

> **記述の緊張をそのまま記録します。断定しません。** オンプレミス ONTAP では階層化ポリシーが `none` で
> かつ未階層のボリュームに限られる、という制約が示されており、FSx for ONTAP については別扱いという KB があります。
> **本リポジトリでは実測していないため、どちらが FSx for ONTAP の正式な挙動かを断定しません。** AWS サポートに
> 確認を依頼しています。
>
> **The tension is recorded as-is rather than resolved.** For on-premises ONTAP the constraint is a tiering
> policy of `none` on a volume with nothing yet tiered; a separate KB treats FSx for ONTAP as an exception.
> **This is not verified here, so no determination is made.** A clarification has been requested from AWS
> Support.

**実務上の含意は、どちらであっても同じ方向です。** 階層化を使う設計と Snapshot locking を使う設計は、
少なくとも同一ボリューム上では衝突しうるため、**両方を前提にした設計をレビューで確認してください。**

### Amazon FSx for NetApp ONTAP の API には該当パラメータがありません / The AWS API has no parameter for it

| API | Snapshot locking の指定 |
|---|---|
| `CreateOntapVolumeConfiguration` | **不可。** フィールドは `StorageVirtualMachineId` / `AggregateConfiguration` / `CopyTagsToBackups` / `JunctionPath` / `OntapVolumeType` / `SecurityStyle` / `SizeInBytes` / `SizeInMegabytes` / `SnaplockConfiguration` / `SnapshotPolicy` / `StorageEfficiencyEnabled` / `TieringPolicy` / `VolumeStyle` <!-- allow:naming - AWS の API 名 --> |
| `CreateSnaplockConfiguration` | **不可**（SnapLock 用の 6 フィールドのみ） |
| ONTAP CLI / REST | **可**（`-snapshot-locking-enabled true`） |

> **AWS API 側にパラメータがないということは、AWS 側のガードレールも効かないということです。**
> IAM の条件キーやコンソールの警告で止められません。**ONTAP へ到達できる資格情報が、そのまま
> 削除ロックを作れる権限になります。**
>
> **No AWS API parameter also means no AWS-side guardrail.** It cannot be gated by an IAM condition key or
> a console warning. **Any credential that reaches ONTAP is a credential that can create this lock.**

境界の整理は [IaC の境界は API の表面で決まる](../../playbooks/04-build/notes/what-iac-cannot-reach.md) にあります。

---

## 実測できなかった項目 / Could not be measured

| 項目 | 理由 |
|---|---|
| **Snapshot locking の挙動全般** | **実施しません。** 有効化すると全ロック済み Snapshot の失効までボリュームを削除できなくなり、同種の削除ロックを新たに作ります。本リポジトリの[不可逆操作の承認ゲート](../../domains/security-governance/notes/irreversible-operations-need-separate-approval.md)に従い、値と範囲の合意なしには実行しません |
| Snapshot locking と FabricPool の併用可否（FSx for ONTAP での正式な挙動） | 上記のとおりドキュメント間で記述が異なります。実測には有効化が必要なため行わず、AWS サポートに確認中です |
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
