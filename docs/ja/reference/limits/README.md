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

## まだ実測していない項目 / Not yet measured

**ここに残っているものは `documented` のままです。** 実測には作成・変更・削除を伴うため、この検証では
行っていません。

These remain `documented`. Measuring them requires create, modify or delete operations, which this
verification did not perform.

| 項目 | 実測に必要な操作 |
|---|---|
| DP ボリュームがバックアップ対象外であること | 該当ボリュームへの `CreateBackup` 試行 |
| Snapshot 1,023 個 / バックアップ 4,091 個の上限 | 上限までの作成 |
| SSD 90% / 98% での階層化の挙動変化 | 意図的な容量圧迫 |
| 作成経路による階層化ポリシー既定の差 | コンソールと CLI の両方でのボリューム作成 |
| SnapLock の不可逆性と特権削除の挙動 | SnapLock ボリュームの作成 |
| パッチ適用時の I/O 一時停止 | メンテナンスウィンドウ中の観測 |
| inode を使い切ったときの書き込み失敗 | 意図的な inode 枯渇 |

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
