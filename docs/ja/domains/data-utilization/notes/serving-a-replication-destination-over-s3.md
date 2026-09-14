---
title: SnapMirror の宛先は break せずに S3 API で読める — 止めるのは junction path であってボリューム種別ではない
lifecycle: [design, build, operate]
domains: [data-utilization, data-protection]
evidence: documented
source: https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/docs/en/s3ap-flexcache-snapmirror-considerations.md
lang: ja
---
# SnapMirror の宛先は break せずに S3 API で読める

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — データ活用](../README.md)

---

> **Evidence**: `documented` — 実測は sibling プロジェクト [FSx-for-ONTAP-Lakehouse-Integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) が持ちます。**本ノートは数値を再掲せず、設計判断だけを扱います。** 測定は 1 ファイルシステム・同一リージョン内・ONTAP 9.18.1P5 での観測であり、一般的なサービス挙動の保証ではありません。

## 結論

**複製先のデータを分析基盤に読ませるために SnapMirror を break する必要はありません。** 宛先ボリュームを ONTAP 側で mount すれば S3 Access Point を取り付けられ、関係は稼働したまま読み取りを提供できます。書き込みは拒否されます。書き込みが必要なら宛先の Snapshot をクローンし、クローンに取り付けます。

**break が必要なのは、宛先で本番サービスを引き継ぐ場合だけです。** 読み取りの要件に break を持ち込むと、片方向レプリケーションを止めることになります。

## 背景

「複製先を分析基盤から読みたい」という要件は、複製の設計と分析基盤の設計が別々に決まったあとに出てきます。そのとき最初に確認されるのが「宛先は read-only なのだから S3 Access Point は取り付けられないのではないか」で、**この問いの立て方が誤りです。**

Amazon FSx は Access Point の取り付け条件を「ボリュームが mount されていること（junction path を持つこと）」と規定しており、`RW` か `DP` かには言及していません。**判定しているのは junction path の有無です。**

## 詳細

### 宛先側で成立する構成

| 宛先側の対象 | 取り付け | 読み取り | 書き込み | 使いどころ |
|---|:---:|:---:|:---:|---|
| DP ボリューム（Amazon FSx API で junction path 設定を試行） | ❌ | — | — | 成立しません（下記） |
| **DP ボリューム（ONTAP で mount）** | ✅ | ✅ | ❌ | 各転送に追従して読む |
| **宛先 Snapshot のクローン** | ✅ | ✅ | ✅ | 書き込む、または時点を固定して渡す |
| break して RW 化 | ✅ | ✅ | ✅ | 宛先で本番サービスを引き継ぐ（DR フェイルオーバー） |

**転送が届いたデータは、同じ Access Point 経由でそのまま読めます。** Access Point の作り直しも再 mount も不要です。クローン経由は切り出した Snapshot の時点で固定されるので、進めるには新しいクローンが必要になります。

### junction path を設定するのは ONTAP 側の操作

**Amazon FSx API はこの設定に使えません。** `CreateVolume` は DP ボリュームに対する `JunctionPath` をフィールド名を挙げて拒否します。問題は `UpdateVolume` の側です。

| API | DP ボリュームへの junction path 指定 |
|---|---|
| `CreateVolume` | フィールド名を挙げて拒否。**失敗が分かります** |
| `UpdateVolume` | **HTTP 200 で Volume オブジェクト全体を返し、何もしません。** エラーも `AdministrativeActions` エントリも失敗メッセージもありません |
| ONTAP（`vol mount` / `PATCH nas.path`） | 成立します |

**同一の不正入力に対して 2 つの API が異なる拒否の仕方をしており、状態を変更する側が沈黙します。** `UpdateVolume` の 200 応答を設定成功の証拠として扱う自動化は、誤った前提で先へ進みます。**判定は `DescribeVolumes` で `JunctionPath` を読み直して行ってください。**

### 取り付け可能になるまでの待ち時間が設計上のコスト

ONTAP 側の操作は数秒で終わりますが、その junction path が Amazon FSx コントロールプレーンに反映されるまで **数分から数十分**かかります。反映前に取り付けを試みると `the volume is not mounted` で失敗します。

**「クローンを作って分単位で分析基盤に渡す」は初回セットアップでは成立しません。** セットアップ後の定常状態は別で、転送から数秒で読めます。

| 判断 | 内容 |
|---|---|
| ポーリング対象 | `DescribeVolumes` の `JunctionPath` が non-null になること。**`VolumeType` を使わないこと**（break 後も `DP` を報告し続けます） |
| デモ・PoC の組み方 | Access Point を事前に用意し、**鮮度の速さを見せる**。セットアップ自体を見せない |
| 見積り | 初回は数十分。特定の秒数を前提にしない（測定値のばらつきが大きく、経路の違いでは説明できません） |

実測値と再現手順は [sibling プロジェクトの設計考慮事項](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/docs/en/s3ap-flexcache-snapmirror-considerations.md) にあります。**数値は測定環境と一体で意味を持つため、ここには転記しません。**

### 分析エンジンから見た違いの不在

**read-only の複製先であることは、クエリエンジンから区別できません。** sibling プロジェクトが Amazon Athena で、同一ファイルから作った RW 由来のテーブルを同一セッションのコントロールとして比較し、行も集計値も一致しています。パーティション検出とパーティション枝刈りも read-only ボリュームに対して機能します。

`INSERT` は S3 の 403 がエンジン側の権限エラーとして表面化して失敗し、**ボリューム上には何も残りません。**

| 未測定 | 扱い |
|---|---|
| Athena 以外の特定のエンジン | 読み取りは同じ `GetObject` / `ListObjectsV2` の面を通るため、リスクは低いと読めます。**ただし推論であって測定ではありません。**「検証済み」として提示しないこと |
| クロスリージョン | 同一リージョン内のみの観測です |
| 規模 | 少数の小さなオブジェクトのみ |
| Access Point を残したままの break / resync 通過 | 未確認 |
| WINDOWS の `FileSystemIdentity` | UNIX のみ。SMB 主体の環境では SVM の AD 参加が別途必要です |

### FlexCache は対象外

**FlexCache の Cache Volume に S3 Access Point は取り付けられません。** ボリューム種別で Amazon FSx コントロールプレーンが拒否します。

**ONTAP のバージョンでは解決しません。** NetApp は ONTAP **ネイティブ**の S3 NAS bucket について Cache Volume 対応を ONTAP 9.18.1 以降と記載していますが、これは別の機構です。sibling プロジェクトが 9.18.1 の 2 つのパッチレベル・2 リージョンで実測し、いずれも同一のエラーで拒否されています。

**リモートのデータを S3 API で読ませたいなら、FlexCache ではなく本ノートの SnapMirror 宛先経路を使ってください。**

## 参照した一次情報

- [Amazon FSx: Creating access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-access-points.html) — 取り付けにはボリュームが mount されていることが必要。ボリューム種別への言及はありません
- [NetApp: Create and delete SnapMirror failover test volumes](https://docs.netapp.com/us-en/ontap/data-protection/create-delete-snapmirror-failover-test-task.html) — ONTAP 9.14.1 以降、稼働中の関係を妨げずに宛先のクローンを作る手順。宛先と同一 Storage VM 上、1 関係につきクローン 1 つ、SnapLock vault 関係は対象外
- [NetApp: Configure the destination volume for data access](https://docs.netapp.com/us-en/ontap/data-protection/configure-destination-volume-data-access-concept.html) — break を前提に書かれていますが、対象は宛先で本番サービスを引き継ぐ場合です
- 実測: [sibling プロジェクトの設計考慮事項 §3.2](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/docs/en/s3ap-flexcache-snapmirror-considerations.md)

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 宛先ボリュームに対して `aws fsx update-volume --ontap-configuration '{"JunctionPath":"/x"}'` を実行し、直後に `aws fsx describe-volumes` で `JunctionPath` を読む | 200 が返っても値が `null` のままであること。**応答を成功の証拠にしてはいけない理由** |
| 2 | ONTAP REST で `PATCH /api/storage/volumes/{uuid}` に `nas.path` を指定し、ONTAP 側で反映を確認 | ONTAP は DP ボリュームを mount すること |
| 3 | `aws fsx describe-volumes` を 30 秒間隔でポーリングし、`JunctionPath` が現れるまでの時間を記録 | 自環境での反映待ち時間。**運用手順のタイムアウト値の根拠** |
| 4 | 反映後に `aws fsx create-and-attach-s3-access-point` を実行 | 取り付けが成立すること。反映前は `the volume is not mounted` で失敗します |
| 5 | Access Point 経由で `ListObjectsV2` と `GetObject`、続けて `PutObject` | 読めること、書き込みが拒否されること |
| 6 | ソースに書き込んで転送を起こし、同じ Access Point で再読み取り | 転送が Access Point の変更なしに反映されること |
| 7 | ONTAP で `snapmirror show` の `state` と `healthy` を通しで確認 | 関係が稼働し続けていること |

適用手順の全体像は [本番に取り入れる前の確認](../../../evidence-policy.md#本番に取り入れる前の確認) を参照してください。

## よくある誤解

| 誤解 | 実際 |
|---|---|
| 宛先は read-only なので S3 Access Point は取り付けられない | 取り付けられます。止めているのは junction path の不在であって read-only であることではありません |
| 複製先を読ませるには break が必要 | 不要です。break は宛先で本番サービスを引き継ぐ場合の手順です |
| `UpdateVolume` が 200 を返したので junction path は設定された | DP ボリュームでは無言で破棄されます。`DescribeVolumes` で読み直してください |
| ONTAP が mount できないから取り付けられない | ONTAP は mount します。拒否しているのは Amazon FSx API 側です |
| クローンなら分単位で分析基盤に渡せる | クローン作成は数秒ですが、Amazon FSx コントロールプレーンへの反映に数分から数十分かかります |
| FlexCache の Cache Volume も ONTAP 9.18.1 なら取り付けられる | 取り付けられません。9.18.1 で対応したのは ONTAP ネイティブの S3 NAS bucket という別の機構です |
| クローンを削除すれば親ボリュームもすぐ削除できる | recovery queue に入っている間は削除できません。[クローンを消しても親が消せない期間](../../block-storage/notes/lun-layout-decides-recovery-granularity.md#クローンを消しても親が消せない期間) を先に読んでください |

## 関連ドキュメント

- [FSx for ONTAP S3 AP は「S3 として使える」わけではない](s3-access-point-constraints.md) — 前提条件、S3 との差分、撤去時の停滞
- [コピーせずにデータへ到達する](reaching-data-without-copies.md) — S3 Access Point / FlexClone / FlexCache の選び方
- [クローンを消しても親が消せない期間](../../block-storage/notes/lun-layout-decides-recovery-granularity.md#クローンを消しても親が消せない期間) — recovery queue。本ノートのクローン経路の撤去で必ず当たります
- [Snapshot は復旧計画ではない](../../data-protection/notes/snapshots-are-not-a-recovery-plan.md) — DP ボリュームと FlexCache はバックアップ対象にできません
- [プラットフォームが持つ責任と自分に残る責任](../../security-governance/notes/what-the-platform-gives-and-what-stays-yours.md) — 宛先の read-only は関係の状態であって設定ではありません
