---
title: FSx for ONTAP S3 AP は「S3 として使える」わけではない — 前提条件と S3 との差分を先に確認する
lifecycle: [assess, design, build, operate]
domains: [data-utilization, security-governance]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html
lang: ja
---

# FSx for ONTAP S3 Access Points は S3 として使えるか？

使えません。前提条件と S3 との差分があり、ボリューム数上限も下がります。

## このノートで学べること

- S3 Access Points の前提条件（ONTAP 9.17.1 以降・同一アカウント同一リージョン）とボリューム数上限の低下
- 条件付き書き込み・Versioning・Lifecycle・Object Lock・Event Notifications が非対応で、S3 として設計すると詰まる箇所

## このノートが答えないこと

- オブジェクトサイズ上限の単位（"GB" 表記の解釈は未確認）や撤去時のバケット削除の帰属（未確認）
- WORM 要件を満たす保持設計の可否判断（SnapLock は不可逆なため別途承認が要る）

## 前提レベル

advanced

## 本文

<a id="fsx-for-ontap-s3-ap-はs3-として使えるわけではない"></a>

[🏠 リポジトリトップ](../../../../../README.md) | [Domain: データ活用](../README.md)

---

### 結論

FSx for ONTAP S3 AP を使えば、ファイルデータを S3 API で読めます。ただし、**Amazon S3 バケットに付ける Access Point とは制約が違います**。「S3 として扱える」前提で設計すると、次の 3 点で詰まります。

| 制約 | 影響 |
|---|---|
| ONTAP 9.17.1 以降が必須 | 既存ファイルシステムのバージョンが下回る場合、まずアップグレードの検討が必要です |
| 作成時は同一 AWS アカウント所有が必須 | 他アカウントのボリュームに AP を作れません。別アカウントからのデータ利用は別の論点で、AP ポリシーと呼び出し元の identity-based ポリシーの両方が許可すれば成立します |
| 同一リージョンが必須 | 対象ボリュームと同じリージョンにしか作れません |

さらに、見落としやすい点があります。**S3 AP を使うとファイルシステムあたりのボリューム数上限が下がります**。

> **Evidence**: `documented`。上記はすべて AWS 公式ドキュメントの記載に基づきます。
> オブジェクトサイズの実測値は別扱いです（後述）。適用前に自環境で確認してください。

---

### 下がるボリューム数上限

S3 AP を使う場合、ボリューム数の上限が下がります。容量設計をボリューム数の上限ぎりぎりで組んでいると、S3 AP の導入で上限に当たります。

| 構成 | 通常 | S3 AP 使用時 |
|---|---|---|
| 第 2 世代（1 HA ペア） | 500 | 491 |
| 第 2 世代（2 HA ペア） | 1,000 | 975 |
| 第 2 世代（12 HA ペア） | 1,000 | 903 |
| 第 1 世代 | 500 | 491 |

HA ペアが多いほど減少幅が大きくなります。「ペアを増やせばボリュームも増やせる」ではありません。

S3 Access Point 自体の数は、リージョンあたりアカウントあたり既定 10,000 です。これは Amazon S3 のサービスクォータで、Service Quotas から引き上げ可能です。同じ値が、1 つのファイルシステムまたはボリュームに付けられる AP 数の上限でもあります。

---

### S3 として扱えない部分

| 観点 | 実際 |
|---|---|
| 対応する S3 API 操作 | バケット向け Access Point と同一ではありません。設計を変える差分は、下の[対応表を読むときに設計を変える差分](#対応表を読むときに設計を変える差分)にあります |
| ストレージクラス | FSx for ONTAP ボリューム上のファイルは、`StorageClass` が `FSX_ONTAP` として識別されます。`STANDARD` 等を前提にした処理は動きません |
| クロスアカウント（AP の作成） | 不可。ファイルシステムと AP は同一アカウント所有が必須です |
| クロスアカウント（AP 経由のデータアクセス） | 可能です。AP ポリシーで許可すれば、別アカウント・別組織のプリンシパルから読めます（実測）。[S3 Access Point の権限設計: 評価順序と、絞り込みを担う 2 つの層](../../security-governance/notes/access-point-authorization-layers.md#クロスアカウントデータアクセスの成立) を参照 |
| S3 Event Notifications | 使えません。FPolicy は代替になりません（下記の実測制約を参照）。Amazon EventBridge Scheduler によるポーリングか、ONTAP のネイティブ監査ログを起点にします |

**`StorageClass` を条件分岐に使っている既存コードは、そのままでは動きません**。分析基盤やデータパイプラインを繋ぐ前に確認してください。

### TR-4814 の上限値と挙動が S3 Access Points に当てはまらないこと

NetApp の TR-4814（ONTAP の S3 の推奨事項をまとめた Technical Report）は ONTAP S3 サーバの文書です。そこに書かれた上限値と挙動を、FSx for ONTAP S3 Access Points の設計に持ち込まないでください。TR-4814 の内容は 2024 年 7 月から ONTAP の製品ドキュメントに統合されていると NetApp は書いています（[Learn about ONTAP S3 configuration](https://docs.netapp.com/us-en/ontap/s3-config/index.html)、2025-02-25 更新）。

次の表は、各行で 2 つの別の機構を並べています。

| 観点 | ONTAP S3 サーバ（TR-4814 / NetApp の ONTAP S3 ドキュメントが対象） | FSx for ONTAP S3 Access Points（このノートが対象） |
|---|---|---|
| 何か | ONTAP 9.8 以降、ONTAP のクラスタ上で動くオブジェクトストレージのサーバ。バケット、ユーザー、ポリシーを ONTAP 側で持ちます。NetApp の TR 索引は、TR-4814 の範囲にネイティブの S3 アプリケーション向けのオブジェクトストアと FabricPool の階層先の両方を挙げています | AWS 側のアクセスポイントを FSx for ONTAP のボリュームに取り付け、S3 API でファイルを読み書きする機構。ONTAP 9.17.1 以降が必要です（上の「[結論](#結論)」） |
| 上限値 | ONTAP S3 の文書の値は、この機構についての値です | アップロードの上限は二進表記で、単一 `PutObject` と `UploadPart` が 5 GiB、オブジェクト全体が 50 GiB です。読み取り側は縛られません（下の「[方向で非対称なサイズ上限](#方向で非対称なサイズ上限)」）。二進表記であることの実測は、[FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns の検証記録](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/s3ap-object-size-limits-verification.md) と、[S3-Burst-on-ONTAP-Files の収集層の上限値](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/limits/s3-access-point.md) にあります |
| 認可と API の範囲 | ONTAP S3 のユーザーとバケットポリシーで判定します | IAM と Access Point ポリシー、そして Access Point に設定した 1 つのファイルシステム ID で判定します。対応する API はバケット向け Access Point と同一ではありません（上の表） |
| 同じ SVM での併存 | 該当なし | 同じ SVM に別のオブジェクトストアサーバーがあると、Access Point の取り付けが失敗します（下の「[オブジェクトストアサーバーとの併存不可](#オブジェクトストアサーバーとの併存不可)」） |

用語の整理は、[S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) リポジトリの [ONTAP 上のオブジェクトアクセスの用語集](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/glossary/object-access-on-ontap.md) にあります。ONTAP の版と S3 Access Points の機能を結びつけているのは、AWS が記載する ONTAP 9.17.1 以降という前提だけです。ONTAP S3 の版ごとの機能追加を、S3 Access Points の機能の根拠にしないでください。

---

### 対応表を読むときに設計を変える差分

[対応表](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)の全行はここに写しません。AWS 自身が partial list と明記しているので写しても網羅にならず、写した表は更新されないまま残ります。ここに置くのは設計を変える行だけです。2026-09-14 に全文を確認しました。

#### パターンごと成立しない 4 つの不在

| 使えないもの | 成立しなくなるパターン |
|---|---|
| 条件付き書き込み（conditional writes） | `If-None-Match` / `If-Match` による楽観的排他が使えません。「同じキーが既にあれば書かない」「読んだときの版のままなら書く」を S3 の側で表現できないので、上書き競合の防止を、アプリケーション側かファイル側のロックに移す必要があります |
| Object Versioning（`ListObjectVersions` も非対応） | 世代管理を S3 の機能で持てません。版が要るなら ONTAP の Snapshot 側で設計します |
| Object Lifecycle | 経過日数による移行・削除の自動化ができません。階層化は FabricPool 側の仕組みで、ライフサイクルルールとは別の設定です |
| Object Lock（`PutObjectRetention` / `PutObjectLegalHold` も非対応） | WORM をこの経路では表現できません。必要なら SnapLock で、これは不可逆なので保持期間を名指しした承認が要ります（[不可逆な操作の承認は作業の承認とは別に取る](../../security-governance/notes/irreversible-operations-need-separate-approval.md)） |

他に非対応なのは、ACL（`bucket-owner-full-control` 以外）、Object Annotations、Requester Pays、Static Website Hosting、MFA delete、`RestoreObject`、そしてバケット設定の読み取り系（`GetBucketAcl` / `GetBucketCors` / `GetBucketPolicy` / `GetBucketNotificationConfiguration`）です。`GetBucketNotificationConfiguration` が非対応であることは、イベント通知が無いことと同じ側の事実です。

#### 完全性の検証がそのままでは移らないこと

ETag もチェックサムも、**Amazon S3 で使っていた形では使えません**。

| 項目 | この経路での挙動 |
|---|---|
| ETag | オブジェクト内容のハッシュですが、MD5 ダイジェストではありません。メタデータの変更では変わりません |
| チェックサム | アップロード時に指定すると転送中の検証には使われます。ただし値はボリュームに保存されず、応答にも返らず、ダウンロード時の検証には使われません |

収集パイプラインが完全性を ETag の突き合わせやチェックサムの再検証で担保しているなら、そこは作り直しになります。「S3 に置いたから同じ検証ができる」とは読めません。

#### バケットと別の Access Point の間のサーバー側のコピー

`CopyObject` と `UploadPartCopy` で、Amazon S3 のバケットと、FSx for ONTAP のボリュームに付けた S3 Access Points の間を、サーバー側でコピーできます。2026-11-22 の [What's New](https://aws.amazon.com/about-aws/whats-new/2026/11/s3-access-points-server-side-copy-fsx/) で告知されました。ユーザーガイドの[ドキュメント履歴](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/document-history.html)には、2026-10-08 の項目として載っています。

- 組み合わせ: バケットから Access Point、Access Point からバケット、Access Point から別の Access Point（Amazon FSx for OpenZFS のボリュームとの間を含む）
- 同じリージョンの中だけ。アカウントをまたぐコピーはできると書かれている
- コピー先が FSx for ONTAP のボリュームのときは、暗号化は `SSE-FSX`、ストレージクラスは `FSX_ONTAP` だけ
- 以前は、オブジェクトを一度サーバーに取得してアップロードし直す必要があった

> **区分**: 上の組み合わせは、告知とユーザーガイドの記載です（2026-11-24 に閲覧）。次の表は、このリポジトリで 2026-11-24 に `ap-northeast-1` の第 1 世代 `SINGLE_AZ_1`（ONTAP 9.19.1P4、UNIX セキュリティスタイル）で 1 回ずつ確かめた結果です。オブジェクトは 8 MiB（9 と 10 は 6 GiB）で、中身は SHA-256 で比べました。

| # | コピー | 結果 |
|---|---|---|
| 1 | バケット → Access Point（`CopyObject`） | 成功。中身が一致 |
| 2 | Access Point → バケット（`CopyObject`） | 成功。中身が一致 |
| 3 | 同じ Access Point の中（`CopyObject`） | 成功。中身が一致 |
| 4 | ファイルシステム A の Access Point → ファイルシステム B の Access Point（`CopyObject`） | 成功。中身が一致 |
| 5 | バケット → Access Point、`--server-side-encryption AES256` を指定 | `InvalidArgument`（The encryption method specified is not supported） |
| 6 | バケット → Access Point、`--storage-class STANDARD` を指定 | `InvalidStorageClass` |
| 7 | 別の Access Point をコピー元にした `UploadPartCopy`（コピー元のキー `ssc/obj.bin` は `/` を含む、2 パート） | 成功。`CompleteMultipartUpload` の後、中身が一致 |
| 8 | `aws s3 cp` でバケットから Access Point のエイリアスへ | 成功。中身が一致 |
| 9 | 6 GiB のファイルを 1 回の `CopyObject` で、バケットへ、また別の Access Point へ | `InvalidRequest`（コピー元の上限 5368709120 バイトを超える） |
| 10 | 同じ 6 GiB を `aws s3 cp`（768 パートの `UploadPartCopy`）で、Access Point → バケット、バケット → Access Point、Access Point → 別の Access Point | 3 つとも成功。中身が一致 |

ファイルの所有者、モード、更新時刻はコピー先に写りません。用途ごとの使い分け、属性と S3 Batch Operations の実測は、[S3 Access Points のサーバー側コピーは、どの用途で使い、どの用途で使わないか](s3-access-points-server-side-copy-use-cases.md)にあります。

コピー先の `HeadObject` は、ストレージクラス `FSX_ONTAP`、暗号化 `aws:fsx` を返しました。`CopyObject` では `x-amz-object-annotation-directive` ヘッダーが非対応です（ユーザーガイドの対応表）。

#### S3 のストレージクラスとの往復

ボリュームのファイルを、汎用バケットのどのストレージクラスへも写せます。アーカイブ用のクラスへ移して必要になったら戻す使い方も、サーバー側のコピーで組めます。戻す方向では、S3 Glacier Flexible Retrieval（`GLACIER`）と S3 Glacier Deep Archive（`DEEP_ARCHIVE`）のオブジェクトだけ、先にバケット側で復元が要ります。

> **区分**: 2026-11-24 に、上の表と同じ環境で 1 回ずつ確かめた結果です。オブジェクトは特記のない限り 8 MiB で、中身は SHA-256 で比べました。コピーはすべて `CopyObject` です。

| 方向 | ストレージクラス | 結果 |
|---|---|---|
| Access Point → バケット（`--storage-class` でコピー先のクラスを指定） | `STANDARD`、`REDUCED_REDUNDANCY`、`STANDARD_IA`、`ONEZONE_IA`、`INTELLIGENT_TIERING`、`GLACIER_IR`、`GLACIER`、`DEEP_ARCHIVE` | 8 つとも成功。`STANDARD` 以外は、コピー先の `HeadObject` が指定したクラスを返した（`STANDARD` のときは S3 がクラスを返さない） |
| バケット → Access Point（復元なし） | `STANDARD`、`REDUCED_REDUNDANCY`、`STANDARD_IA`、`ONEZONE_IA`、`INTELLIGENT_TIERING`、`GLACIER_IR` | 成功。中身が一致し、コピー先のクラスは `FSX_ONTAP` |
| バケット → Access Point（復元なし） | `GLACIER`、`DEEP_ARCHIVE` | `InvalidObjectState`（Operation is not valid for the source object's storage class） |
| バケット → Access Point（`GLACIER` を Expedited で復元した後） | `GLACIER` | 成功。中身が一致し、コピー先のクラスは `FSX_ONTAP` |

`DEEP_ARCHIVE` を復元した後のコピーは、復元の完了を待っている段階で、まだ確かめていません。6 GiB と 1 KiB での往復、コピー先に指定できないクラス、コピーのオプションは、[ストレージクラスとコピーのオプションの実測一覧](s3-access-points-server-side-copy-use-cases.md#ストレージクラスとコピーのオプションの実測一覧)にあります。

復元（`RestoreObject`）は、コピー元のバケットに対して呼びます。Access Point の側では `RestoreObject` は非対応ですが、この往復ではボリュームの側に復元が要るオブジェクトはありません。復元にかかる時間と料金は取り出しの階層（Expedited、Standard、Bulk）で変わり、Amazon S3 の [Restoring an archived object](https://docs.aws.amazon.com/AmazonS3/latest/userguide/restoring-objects.html) に従います。

1 GiB のファイルでの所要時間は次のとおりです。いずれもこの環境での 1 回のサンプル実行で、本番の見積りではありません。

| コピー | 所要時間 |
|---|---|
| `aws s3 cp` で Access Point → バケット（`DEEP_ARCHIVE`、128 パートのマルチパートコピー） | 3 秒 |
| `aws s3 cp` で Access Point → バケット（`GLACIER_IR`） | 4 秒 |
| `aws s3 cp` でバケット（`GLACIER_IR`）→ 別のファイルシステムの Access Point | 21 秒。NFS で読んだファイルの SHA-256 が元と一致 |

バケット側で Object Lock や S3 Lifecycle を組み合わせる設計はありえますが、Object Lock は保持期間中に削除できなくなる不可逆な設定です。このリポジトリでは試しておらず、設定するなら保持期間を名指しした承認を別に取ってください（[不可逆な操作の承認は作業の承認とは別に取る](../../security-governance/notes/irreversible-operations-need-separate-approval.md)）。

#### Presign が対応に変わっていること

対応表は現在 `Presign` を Supported としています（2026-09-14 に確認）。署名付き URL による、短命で資格情報なしのアクセスがこの経路で使えます。ブラウザ経路を自分で組む場合の選択肢に入ります（[エンドユーザーがデータに届く経路](../../../playbooks/02-design/notes/how-end-users-reach-the-data.md#ブラウザ経路を自分で組む場合の選択肢)）。

> このリポジトリでは測っていません。[S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) が 2026-08-19 に `PutObject` / `HeadObject` / `GetObject` の 3 つで成功を実測しています。ただし、その時点の対応表は非対応としており、記録も「対応表が非対応としている間は依存させない」という条件付きの助言でした。表が変わったのでその条件は解けましたが、実測は表の変更より前です。依存する前に自環境で確認してください。

この節を「非対応の網羅」として引かないでください。元の表が partial list です。「X ができない」の根拠にするときは、表が網羅でないことを添えてください。

---

### AWS ドキュメントに載っていない実測の制約

この節は公式ドキュメントの記載ではなく、[S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) と [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) での実測に基づきます。このノートの `documented` 区分の外にあります。自環境で再確認してください。

| 実測された挙動 | 実務上の意味 |
|---|---|
| オブジェクトサイズの上限はバイナリ単位（ドキュメント上の "GB" 表記と一致しない） | 境界値ぎりぎりの設計は破綻します |
| 単一 `PutObject` と `UploadPart` あたり 5 GiB、オブジェクト全体で 50 GiB | Amazon S3 本体（単一 PUT 5 GB / オブジェクト最大 50 TB）とは桁が違います |
| 全体サイズの超過は `CompleteMultipartUpload` の時点で初めて判定される | 全ペイロードを転送し終えた後に失敗します。転送時間と転送料が無駄になります |
| 50 GiB は書き込みの上限で、読み取りの上限ではありません | 下の[方向で非対称なサイズ上限](#方向で非対称なサイズ上限)を参照。ファイル側で作った 50 GiB 超のファイルは、S3 API で取得できます |
| AP 経由の操作は FPolicy 通知を発火しない。`mandatory` 指定の同期ポリシーでも遮断されない | FPolicy を前提にしたリアルタイム検知・DLP・遮断は、この経路では機能しません。同じボリュームを NFS / SMB で触れば発火します。適合するかは書き込みが着地するプロトコルで決まり、読む側は判定に入りません（[FPolicy が適合するかは、データをどう読むかではなく、どう書くかで決まる](fpolicy-fits-by-how-writes-land.md)） |
| AP 経由の操作は ONTAP ネイティブ監査ログには記録される。ただし要求者は記録されない | 「何が操作されたか」は追えます。「誰が」は追えません。要求元の IAM プリンシパルは、[CloudTrail の S3 データイベント](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-points-monitoring-logging.html)を構成すると Access Point 経由のリクエストとして記録できます |
| AP 経由の書き込みは ARP が検知する | ランサムウェア検知については、FPolicy の穴を ARP が埋めます（実測: AP 経由で書いた高エントロピーオブジェクトが suspect として記録、2026-08-26 / ONTAP 9.18.1P3D1 / ARP/AI。手順と件数は [この経路を見ない FPolicy](../../security-governance/notes/access-point-authorization-layers.md#この経路を見ない-fpolicy) 側に書いてあります。件数はこちらでは持ちません）。観測された検知理由は高エントロピーのみで、他の理由で検知されるかは測っていません。改名・削除のレートも ARP の検知入力ですが、閾値がサージ判定なので同じようには検知されません（[暗号化を伴わない攻撃](../../data-protection/notes/snaplock-and-layered-ransomware-readiness.md#暗号化を伴わない攻撃)）。ただし、検知は遮断ではありません。ベンダーの応答手順は警告・Snapshot・管理者による分類で、書き込みを拒否する段がありません（[ベンダーのドキュメント](https://docs.netapp.com/us-en/ontap/anti-ransomware/index.html)は「detecting and warning」と記載、2026-09-05 に確認）。遮断は AP ポリシーと IAM の側で表現してください |
| 同一 SVM に ONTAP のオブジェクトストアサーバーがあると AP を作成できない | 下記のとおり自環境で実測。ONTAP の S3 機能と S3 AP は、同じ SVM では併存しませんでした |
| オブジェクトタグの一部の Unicode 文字が `InvalidTag` で拒否される | 後述のとおり不具合であり、意図された制限ではありません。修正までタグ値を ASCII に限定してください |
| `UploadPartCopy` が同一 AP 内のコピーで `NoSuchKey` を返す（2026-08 の実測） | 2026-11-24 の確認では、キーに `/` を含むコピー元からの `UploadPartCopy` が成功し、再現しませんでした（[上の表](#バケットと別の-access-point-の間のサーバー側のコピー)の 7） |

#### 方向で非対称なサイズ上限

**50 GiB を「オブジェクトサイズの上限」として読むと、経路を 1 つ落とします**。AWS の記載は、書き込みだけを縛っています。

> Maximum object size is 50 GiB for uploads, but you can download objects larger than that

| 経路 | 50 GiB を超えるオブジェクト |
|---|---|
| S3 API で書く | 作れません。`CompleteMultipartUpload` で失敗します |
| NFS / SMB で書いたものを S3 API で読む | 取得できます |

つまり、収集を S3 API に寄せた設計でも、大きいファイルだけファイル側で作れば S3 から読めます。これは実測されています（2026-09-11、`ap-northeast-1`、第 1 世代 `SINGLE_AZ_1` / 128 MBps、SSD 1,024 GiB、ボリューム 70 GiB / UNIX、NFSv3、S3 AP は `NetworkOrigin=VPC` / `FileSystemIdentityType=UNIX`）。50 GiB + 1 バイト（53,687,091,201 バイト）の全体 GET が成功し、Range GET も先頭・末尾ともに成功しました。

同じ測定の中に、対照が置かれています。1 GiB のファイルを同じ手順で取得して成功しており、経路が正常であることを示さずに大きい側だけ測ると、失敗したときに「50 GiB 超だから」と「経路が壊れていた」を区別できません。

> 所要 537 秒を、読み取り性能として引かないでください。測定対象のファイルは `truncate` で作った疎ファイル（`blocks=0`）です。S3 から見えるサイズは apparent size で決まるのでサイズ上限の判定には影響しませんが、ディスクを読んでいません。引用元は、ONTAP のバージョンを記録しておらず、環境を消したあとなので取得できないと明記しています。

出典は [収集層の上限値](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/limits/s3-access-point.md) です。このリポジトリでは再測定していません。

書き込み側の境界も、別の構成で測られています。上の読み取り側（`NetworkOrigin=VPC`）とは別に、`NetworkOrigin=Internet` の S3 Access Point に対して書き込み方向を測った記録があります（2026-10-07、`ap-northeast-1`、`SINGLE_AZ_1` / 128 MBps / UNIX、クライアントは同一リージョンの `c5n.2xlarge`、1 構成・限られた回数のサンプル実行。このリポジトリでは再測定していません）。

| 試験 | 結果 |
|---|---|
| 単一パート 5 GiB ちょうど | 成功 |
| 単一パート 5 GiB + 1 MiB | 失敗。ただし `EntityTooLarge` ではなく、クライアント側に接続エラー（SSL validation failed）として現れた |
| 全体 50 GiB ちょうど（5 GiB × 10 パート） | 成功。`CompleteMultipartUpload` が 2,513 秒（約 42 分）戻らず、接続は切れないまま最後に成功 |
| 全体 50 GiB + 1 バイト | パート上限で先に拒否され、`CompleteMultipartUpload` には到達していない（全体超過の判定は未観測） |

設計に影響するのは、次の 3 点です。

- 5 GiB 超のパート拒否が、接続エラーの形で現れうる。エラーコードで分岐する処理は、これをサイズ超過ではなく通信障害と誤認して再試行する可能性があります。パートサイズは送信前にクライアント側で 5 GiB 以下に抑えてください。（1 回観測、再現未確認）
- 50 GiB に近いオブジェクトの `CompleteMultipartUpload` は、長時間戻らない。上の記録では 42 分でした。収集を S3 API に寄せる設計では、完了待ちの所要を呼び出し側の上限（Lambda の実行時間、プロキシ / ロードバランサーのアイドルタイムアウト）と比べてください。所要時間がサイズやスループットキャパシティとどう関係するかは測られていません。
- 「全体 50 GiB 超過が `CompleteMultipartUpload` で拒否される」ことは、この測定では観測されていません。パート 10 を 5 GiB 超にしたため、パート上限で手前で弾かれました。全体超過の判定を見るには、どのパートも 5 GiB 以下に保ったまま合計を 50 GiB 超にする必要があります。上の「方向で非対称なサイズ上限」の表で `CompleteMultipartUpload` で失敗するとした行は、ドキュメント記載と別の実測に基づくもので、この測定では変えていません。

出典は [S3 Access Point マルチパートアップロード（Internet origin）](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/s3ap-multipart-internet-origin.md#マルチパートアップロードのサイズ境界) です。値はすべて Internet origin・この構成のもので、S3 Access Point 一般の性質としては読めません。同一条件（同じクライアント・ツール・データ）での VPC origin は未測定です。ただし、別条件の記録では、VPC origin の S3 Access Point が同じ 128 MBps 構成で書き込み 129.5〜131.2 MB/s に達しているため（[スループット・IOPS・並列度](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/throughput-iops-concurrency.md)）、「S3 Access Point 経由だから速度が出ない」とは読めません。origin・エンドポイント・ツール・インスタンス・リクエストの形が同時に違うので、この差を NetworkOrigin に帰すこともできません。スループットの比較は [単一接続で測った値はストレージの性能ではない](../../performance/notes/a-single-connection-measures-the-client.md#s3-access-point-経由の書き込みを律速する別の上限) にあります。

#### ONTAP の機能と併用したときに測られたこと

AP を付けたボリュームで ONTAP の機能が使えるかは、対照付きで測られています。以下は [S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) の実測（UNIX スタイル、identity は UNIX / `root`）で、このリポジトリでは再測定していません（[S3 Access Point 経路で ONTAP の機能は使えるか](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/limits/s3ap-interoperability.md)）。

| 機能 | 結果 |
|---|---|
| qtree | 作成でき、`--delimiter /` の `CommonPrefixes` に現れる。AP を持たない対照ボリュームと差は出ません |
| tree クォータ | 有効。S3 経由で書いたファイルが files used に計上されます |
| FlexClone（ボリューム単位） | 作成でき、クローンにも AP を取り付けられます。クローン経由の PUT は親に現れません |
| FlexClone（ファイル単位） | S3 側から通常のオブジェクトとして見え、読め、上書きできます。S3 が書いていないファイルでも同じです |
| FlexGroup | AP を取り付けられ、PUT / GET / LIST とマルチパートが通り、スナップショットとクローンも作れました |

設計に影響するのは、次の 2 つの失敗の形です。

| 症状 | 実際の原因 |
|---|---|
| PUT が HTTP 507 `InsufficientCapacity` / `Maximum storage capacity of file system has been reached.` を返す | qtree のファイル数クォータです。ファイルシステムは満杯ではありません。files の上限を 10 → 50 に上げただけで、拒否された同一キー・同一ボディの PUT が通りました |
| ファイル単位クローンが何も作らない | `POST /api/storage/file/clone` は 202 とジョブ UUID を返しますが、その UUID が解決できません（`404 entry doesn't exist`、ジョブ一覧 166 件を検索しても該当なし）。ボリューム作成とボリュームクローンは同一セッションで 200 と `state=success` を返しており、権限の問題ではありません。成否は宛先ファイルを見て判定してください |

1 行目のエラー文は、運用判断を誤らせます。507 と「ファイルシステムの容量上限」を読んだ担当者はファイルシステムの拡張を検討します。クォータを使うなら、この応答が何を意味するかを runbook に書いてください。

2 行目は、このリポジトリが別の箇所で記録している形と同じで、拒否が成功の形で返り、値を読み直すまで分かりません（[分割の単位が決めているのは、後で決め直せない範囲](../../../playbooks/02-design/notes/the-split-decides-what-cannot-be-revisited.md#分けても独立にならない-2-つの経路)）。

副産物が 1 つあります。AP を取り付けたボリュームの直下に、S3 レイヤーが作る内部ディレクトリ `____NTAP_S3_MAPPING` が現れ、NFS / SMB から見えます。収集層のボリュームを人が覗く運用では、これが何かを説明できるようにしておいてください。

#### オブジェクトストアサーバーとの併存不可

S3 AP をアタッチするとき、FSx for ONTAP は、対象ボリュームが属する SVM 上に管理用のオブジェクトストアサーバーを作成します。その SVM に既に別のオブジェクトストアサーバーが存在すると、この作成が失敗し、AP は `FAILED` で終わります。

| 確認したこと | 結果 |
|---|---|
| 同一 SVM 内での回避策 | 見つけられませんでした（未確認）。既存のオブジェクトストアサーバーを削除すると作成できることは実測しています |
| 制約の適用単位 | SVM 単位 |
| 回避策 | オブジェクトストアサーバーが無い別の SVM のボリュームに AP をアタッチする |
| 別 SVM 側の前提 | `vserver add-protocols -vserver <svm> -protocols s3` で S3 プロトコルを有効化しておく |

つまり、ONTAP S3 を使っている SVM は現構成のまま残し、S3 AP は別 SVM のボリュームに向ける、という分離になります。既存の S3 クライアントが利用中のサーバーを止める必要はありません。

ただし、この回避策が使えない用途が 1 つあります。監査ログの取得です。ファイルアクセス監査の宛先は `vserver audit` の `-destination` で指定するパスで、監査対象ボリュームと同一 SVM の名前空間内に置く必要があります。したがって EVTX を S3 AP 経由で読みたい場合、AP は当該 SVM のボリュームにアタッチするしかなく、その SVM に既にオブジェクトストアサーバーがあると、別 SVM へ逃がせません。

| 用途 | 別 SVM への回避 |
|---|---|
| 任意のデータを S3 AP で公開する | 使える |
| 同一 SVM の監査ログ（EVTX）を S3 AP で読む | 使えない（宛先が SVM をまたげない） |

この場合の選択肢は、既存のオブジェクトストアサーバーを削除するか、S3 AP 以外の取得経路を使うことです。ONTAP REST のファイル API でマウント無しに EVTX を取得できることは実測しています（[監査宛先が枯渇するとクライアントアクセスは止まる](../../security-governance/notes/audit-log-space-and-client-access.md#監査ログの取り出し)）。

> **Evidence**: 制約そのものは実測（`verified`、2026-09-01）。この排他が SVM 単位なのか別の粒度なのか、
> および内部の機構は当方で確かめられていないため未確認です。前提条件および制約としてドキュメントへの
> 記載を要望として起票済みです（2026-09-02 起票）。本ノート作成時点で公開ドキュメントには未記載です。

#### 不具合として区分された 2 件

上の表のうち 2 件は、AWS サポートから、仕様ではなく不具合であるという判断を得ています。制限として設計に織り込むのではなく、修正を待つ対象として扱ってください。区別が要るのは、恒久的な制限なら回避策を設計に固定しますが、不具合なら修正後に解除できるためです。

| 事象 | 区分 | 現時点の扱い |
|---|---|---|
| オブジェクトタグのキー / 値に含まれる特定の Unicode 文字が `InvalidTag` で拒否される | ONTAP 側の不具合（NetApp KB [CONTAP-771956](https://kb.netapp.com/on-prem/ontap/da/S3/S3-Issues/CONTAP-771956)）。将来の ONTAP バージョンで修正予定 | タグ値を ASCII に限定する |
| 同一 AP 内のコピーで `UploadPartCopy` が `NoSuchKey` を返す | 2026-08 に観測した事象。2026-11-24 の確認では再現しなかった | 自分の環境で、下の対照（`CopyObject`）と並べて確かめる |

`UploadPartCopy` の失敗には対照付きの実測があります。[検証記録](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/s3ap-operations.md)（2026-08-19、ap-northeast-1、`SINGLE_AZ_1` / 128 MBps、UNIX）で、同一の `CopySource` を与えた `CopyObject` が同一実行内で成功しています。つまり、`NoSuchKey` は署名や権限や手順の誤りではなく、この API 呼び出しに固有です。自分の環境で同じ症状に当たったときは、まず `CopyObject` を対照として流してください。通れば経路と権限は正常で、切り分けが 1 手で済みます。

ただし、この検証記録は `UploadPartCopy` そのものの対応可否を未判定としています。その時点（2026-08-19）では別 AP をソースとするコピーが `CopyObject` でも拒否されたため、「同一 AP 内では失敗する」ことと「この API が非対応である」ことを、その測定では分離できていません。不具合という区分は AWS サポートの判断で、この測定から導いた結論ではありません。

オブジェクトタグは Amazon S3 と同等の Unicode 対応が意図された仕様で、現在拒否される文字があることは仕様ではありません。ASCII への限定は修正までの回避策であり、恒久的な設計制約として文書化すると、修正後も不要な制限を残すことになります。

#### 到達性を決めるのは設定値

> 2026-11-24 の確認では、`UploadPartCopy` の `NoSuchKey` は再現しませんでした（[サーバー側のコピーの表](#バケットと別の-access-point-の間のサーバー側のコピー)の 7）。修正されたという告知は見つかっていないので、この節は、自分の環境で再現するかを確かめるときの手がかりとして残します。

`UploadPartCopy` を使うかどうかは、自分のコードがそれを呼ぶかどうかでは決まりません。

Spark / S3A で書く経路がこの不具合に当たるかを決めているのは `fs.s3a.multipart.threshold` です。
Hadoop はこの値について、「rename されるファイルの partition size も制御する。rename は source の
コピーを伴うため」と記載しています。つまり、rename は常に 1 回の `CopyObject` ではなく、
出力 part がしきい値を超えると `UploadPartCopy` になります。

そのため、この不具合に当たるかどうかは 3 つの設定の組み合わせで決まり、どれか 1 つを見ても分かりません。

| 設定 | 役割 |
|---|---|
| `fs.s3a.multipart.threshold` | この値を超える part の rename が `UploadPartCopy` を使います |
| 出力 part のサイズ（例: `spark.sql.files.maxPartitionBytes`） | しきい値との大小関係を決めます |
| output committer | 未指定なら rename ベースの既定が有効で、rename が発生します |

出力 part をしきい値以下に保つのが、この経路で取れる唯一の、元に戻せる対処です。修正が入った時点で
設定を元に戻せます。

#### 採用できない回避策を回避策として書かないこと

「copy-source のキーにパーセントエンコード対象の文字を含めない」という回避策は、採用できません。
`/` を含むプレフィックス設計と両立しないためです。

`/` を使わないキー設計は、このリポジトリが扱うどのプレフィックス設計とも両立せず、
不具合が修正された後も残ります。恒久的な設計制約として文書化すると、修正後に不要な制限が
残ります。これは、オブジェクトタグの ASCII 限定について書いたのと同じ理屈です。

採用できないものは回避策ではなく、同一 AP 内のコピーがいまは使えないという事実です。同一 AP 内のコピー自体は
サポートされている操作なので、失敗を仕様と読んで別経路を設計すると、余計な作りになります。

> **Evidence**: `documented`。`fs.s3a.multipart.threshold` が rename の partition size も制御する
> という記述は、Hadoop のドキュメントに基づきます。この 3 設定が不具合への到達を決めるという分析は、
> この 3 設定を持つ実装を運用している FSx-for-ONTAP-Lakehouse-Integrations リポジトリからの報告です（2026-09-07、
> [Issue #121](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/issues/121)）。
> 著者による実測は含みません。

オブジェクトサイズの上限についても補足があります。上の表がバイナリ単位であるという読みは、拒否される境界の実測と整合します。ただし、公開ドキュメントの表記は "GB" なので、単位の解釈そのものは未確認です。表記の明確化を要望として起票済みです。数値そのものはこのノートでは再掲しません（後述）。

#### `read_timeout` の既定値で足りること

`read_timeout` の挙動は、自環境で測らなくても、公開ドキュメントで確認できます。

[Amazon S3 の `CompleteMultipartUpload` API リファレンス](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CompleteMultipartUpload.html)に、処理中は接続がタイムアウトしないように Amazon S3 が定期的に空白文字を送ると記載されています。つまり、レスポンスはアセンブリ完了後に初めて返るのではなく、処理中も流れています。したがって、オブジェクトサイズに比例した `read_timeout` の下限を設ける必要はありません。

「SDK の既定値では失敗する」という推論は、上記により成り立ちません。

また、200 が返ることは成功を意味しません。同じページに、初回の `200 OK` を送った後でもリクエストは失敗し得ること、`200 OK` のレスポンスは成功とエラーのどちらも含み得ること、エラーレスポンスが `200 OK` の中に埋め込まれ得ることが記載されています。

| 呼び出し方 | エラー検出の責任 |
|---|---|
| AWS SDK | SDK が埋め込みエラーを検出し、設定に従ってエラーハンドリング（必要に応じた再試行を含む）を適用します |
| API を直接呼ぶ | 自分でレスポンスの内容を解析する必要があります。ステータスコードだけで判定すると、失敗を成功として扱います |

これは FSx for ONTAP S3 AP 固有ではなく、Amazon S3 の汎用バケットについて文書化されている挙動です。S3 互換の経路を使う限り同じ扱いが必要になります。

残っている未確認は 1 点です。アセンブリ中にクライアントが接続を中断した場合、サービスがアセンブリを完了させるのか中止するのかは、上記のページにも記載がありません。この点は、タイムアウト後の正しい動作（オブジェクトの存在を再確認するのか、再試行するのか）を決めます。AWS サポートに照会中で、回答待ちです（2026-09-09 時点）。既定値ではタイムアウトしないため、この分岐に入るのは例外的な経路に限られます。

> **Evidence**: 拒否・失敗の挙動そのものは実測（`verified`、2026-08-02 および 2026-08-26、ap-northeast-1）。
> 意図された制限なのか不具合なのか、修正の予定があるのかは、公開情報から判断できないため未確認です。
> 不具合として扱ってほしい旨は起票済みです（オブジェクトタグは 2026-09-02、`UploadPartCopy` とサイズ上限は
> 2026-08-26 起票）。本ノート作成時点で、いずれも公開ドキュメントには未記載です。修正の提供や
> ドキュメント更新は公開されるまで未反映として扱ってください。

サイズについては、クライアント側で事前に検証してください。サーバー側の判定を待つと、大きいオブジェクトほど失敗コストが大きくなります。

監視については、機構ごとに答えが違います。「ストレージ層の制御はすべて適用される」も「S3 経路は何も見えない」も誤りです。何を担保したいかで、使う機構が変わります。

実測の詳細と再現手順は [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) にあります。このリポジトリでは、数値を再掲せずリンクします。実測値は測定環境と一体で意味を持つため、切り離して引用すると誤用されます。

---

### 撤去時の停滞: AWS 側からしか消せなくなるボリューム

この節も実測です。導入時ではなく撤去時に問題になるので、検証環境を作る前に確認してください。

S3 AP を一度取り付けたボリュームは、AP を全部外した後も、**ONTAP 側からは削除できません**。

```text
Cannot delete volume "..." in SVM "..." because it is associated with the following
object store NAS buckets: "amazon-fsx-<volume-id>"
```

| 確認したこと | 結果 |
|---|---|
| バケット名の由来 | ボリューム ID と完全一致。AP 単位ではなくボリューム単位に作られ、AP を外しても残ります |
| AP を全部削除したあと | 拒否は続きます。数時間後も同じです |
| ボリュームを online・マウント済みに戻す | 拒否は続きます |
| AP を再取り付けして正しい順序で外す | 拒否は続きます。AP のライフサイクルとは独立しています |
| `aws fsx delete-volume` | 成功します。ボリュームとバケットが一緒に消えます |

取り付けが失敗した場合も同じ状態になります。2026-09-01 に再現しました。`CreateAndAttachS3AccessPoint` が `AVAILABLE` に到達せず `FAILED` で終わった AP でも、バケットの関連付けは作られていました。

| 確認したこと | 結果 |
|---|---|
| AP の `Lifecycle` | `FAILED`（同一 SVM の ONTAP S3 サーバが理由。[前節](#aws-ドキュメントに載っていない実測の制約)の併存不可） |
| `DetachAndDeleteS3AccessPoint` | 成功。`DescribeS3AccessPointAttachments` から消えます |
| その後の ONTAP `volume delete` | 拒否。`amazon-fsx-<volume-id>` を理由に挙げます |
| `aws fsx delete-volume` | 成功 |

「作成に失敗したのだから何も残っていない」は成立しません。失敗した AP のために作ったボリュームを片付ける段で詰まります。検証環境を何度も作り直す場面ほど当たりやすい経路です。

運用手順書への含意は 1 つです。**S3 AP を取り付けた、あるいは取り付けようとしたボリュームの撤去は、AWS 側の API で行ってください**。ONTAP CLI の `volume delete` を前提にした手順書は、この経路では詰まります。ONTAP 側で offline にしてから AWS 側で消す、という順序も不要です（online のまま `aws fsx delete-volume` で通ります）。

#### 観測できた範囲と、そこから言えないこと

実測で分かった範囲は、次のとおりです。

| 項目 | 当環境での観測 |
|---|---|
| バケット名 | `amazon-fsx-fsvol-<ボリューム ID>`（`verified`） |
| デタッチ時 | 削除されない（`verified`） |
| 作成処理が途中で失敗した場合 | 削除されない（`verified`） |
| ONTAP CLI からの削除 | 関連付けが残っている間は失敗する（`verified`） |
| FSx for ONTAP API / コンソールからの削除 | 成功し、バケットも一緒に消える（`verified`） |
| バケットを独立に消す経路 | 見つけられませんでした（存在しないことの確認ではありません。未確認） |
| バケット削除がどちらの処理に属するか | 未確認。上の非対称から Amazon FSx 側の削除処理に含まれると読めますが、当方では確かめられません |

実務上の結論は、観測だけで足ります。バケットを独立に消す経路が見つからず、ONTAP CLI では失敗し、
FSx for ONTAP API では成功する。だから撤去は AWS 側の API で行います。エラー文言は ONTAP が出力するため、
改善を求める先も ONTAP 側の表示になります。

AP 作成失敗時・削除時に関連付けを確実に解除することを改善要望として、また「AP をアタッチしたボリュームは
ONTAP CLI から削除できない場合がある / その場合は FSx for ONTAP API・コンソールから削除する」を
ドキュメント記載の要望として、それぞれ起票済みです（2026-09-02 起票）。バケットが ONTAP CLI から
確認できない点も同じ起票に含めています。

#### 見えないものを「無い」と読まないこと

この件の副産物として、次の観測が得られました。

| リーダー | このバケット / S3 サーバをどう見せるか |
|---|---|
| ONTAP REST `/protocols/s3/buckets` | 列挙しない |
| ONTAP CLI `vserver object-store-server bucket show` | 列挙しない |
| ONTAP REST `/svm/svms`（`s3` フィールド） | S3 サーバを `enabled` として見せる |
| ONTAP REST `/protocols/s3/services` | 同じ SVM を列挙しない |

**AWS が管理するオブジェクトは、標準の ONTAP S3 ビューから隠れています**。バケットの不在を 2 つのリーダーで確認しても、両方が同じ盲点を持っていました。

この盲点が FSx for ONTAP が管理するオブジェクトに固有かどうかは、当方では確かめていません。利用者が手動で作成した `type nas` のバケットが `/protocols/s3/buckets` や `vserver object-store-server bucket show` に現れるかを試していないためで、ここは未確認です。どちらであっても、切り分けの結論は変わりません。これらのリーダーに何も出ないことを「バケットは無い」と読んではいけません。もし利用者作成のバケットが見えるのであれば、同じコマンドで自分の作ったものが見えるぶん、管理バケットが見えないことに気づきにくくなります。

NetApp が文書化している [NAS バケット構成の削除手順](https://docs.netapp.com/us-en/ontap/revert/remove-nas-bucket-task.html) は `vserver object-store-server bucket delete -vserver <svm> -bucket <bucket>` を使いますが、対象を列挙できないのでこの経路には適用できません。同種の症状の KB は [Cannot delete volume "because this volume is associated with object store bucket"](https://kb.netapp.com/onprem/ontap/da/S3/Cannot_delete_volume_%22because_this_volume_is_associated_with_object_store_bucket%22) にありますが、解決手順の本文は NetApp Support のログインが必要で、本ノート作成時点では参照できていません。

> **Evidence**: 挙動と「FSx for ONTAP API から削除すると通る」ことは `verified`（実測、2026-09）。
> バケット削除がどちらの処理に属するかは未確認で、上の非対称からの推論にとどまります。
> 公開ドキュメントには本ノート作成時点で未記載で、記載追加は要望として起票済みの段階です。
> 起票は公開ではないため、ドキュメントに反映されるまでは「未記載の挙動」として扱ってください。
> 自環境で撤去手順を通してから本番設計に組み込んでください。

---

### 判断フロー

```mermaid
graph TD
    V{ONTAP 9.17.1 以降か} -->|いいえ| UP[アップグレードを検討<br/>または別の連携方式]
    V -->|はい| ACC{ファイルシステムと AP が<br/>同一アカウントか}

    ACC -->|いいえ| NO[S3 AP は使えない<br/>アカウント設計を見直す]
    ACC -->|はい| VOL{ボリューム数上限に<br/>余裕があるか}

    VOL -->|ない| VOL2[上限が下がることを織り込んで再設計]
    VOL -->|ある| API{必要な S3 API 操作が<br/>対応一覧にあるか}

    API -->|ない| ALT[別の連携方式を検討]
    API -->|ある| SIZE[オブジェクトサイズ上限を<br/>クライアント側で検証する設計に]
```

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| S3 バケットと同じように使える | 対応する API 操作、ストレージクラス、クロスアカウントの扱いが異なります |
| どのバージョンの FSx for ONTAP でも使える | ONTAP 9.17.1 以降が必須です |
| 他アカウントのボリュームに AP を作れる | 作れません。ファイルシステムと AP は同一アカウント所有が必須です |
| 同一アカウント所有が必須なので、他アカウントからデータも読めない | 読めます。制約は作成側です。AP ポリシーで許可すれば別組織のアカウントからも通ります（実測） |
| S3 AP を有効にしてもボリューム数上限は変わらない | 下がります。HA ペアが多いほど減少幅が大きくなります |
| オブジェクトサイズ上限は Amazon S3 と同じ | 桁が違います。全体で 50 GiB 水準です（実測。[参照した一次情報](#参照した一次情報)の出典を参照） |
| サイズ超過は転送前に弾かれる | 全体サイズの判定は `CompleteMultipartUpload` 時点です。転送し終えてから失敗します |
| 50 GiB を超えるオブジェクトはこの経路では扱えない | 上限があるのは書き込みだけです。ファイル側で作った 50 GiB 超のファイルは S3 API で取得できます（実測、50 GiB + 1 バイト） |
| ETag を突き合わせれば完全性を検証できる | MD5 ダイジェストではありません。チェックサムも保存されず応答に返らないので、ダウンロード時の検証には使えません |
| `If-None-Match` で上書き競合を防げる | 条件付き書き込みが非対応です。排他はアプリケーション側かファイル側のロックに移します |
| S3 のライフサイクルで階層化を自動化できる | 非対応です。階層化は FabricPool 側の別の設定です |
| 署名付き URL は使えない | 対応表は現在 Supported としています（2026-09-14 に確認）。以前の対応表は非対応と記載していました |
| `CopyObject` は同じ Access Point の中でしか使えない | 2026-11-22 に告知されたとおり、バケットと Access Point の間、別の Access Point との間でもサーバー側でコピーできます（同じリージョンの中だけ。2026-11-24 に実測） |
| S3 Event Notifications でイベント駆動にできる | 使えません。EventBridge Scheduler によるポーリングか、ONTAP ネイティブ監査ログを起点にします |
| S3 Event が無くても FPolicy で代替できる | できません。AP 経由の操作は FPolicy 通知を発火せず、`mandatory` 指定でも遮断されません（実測） |
| FPolicy はイベントソースとして使えない | 使えます。効かないのは AP 経由の書き込みに対してだけで、NFS / SMB で着地する書き込みには動きます（[書き込みの着地経路で決まること](fpolicy-fits-by-how-writes-land.md)） |

---

### 参照した一次情報

| 論点 | 出典 |
|---|---|
| ONTAP 9.17.1 以降、同一アカウント、同一リージョンの各要件 | [AWS: Access points naming rules, restrictions, and limitations](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html) |
| TR-4814 が ONTAP S3 サーバ（ネイティブの S3 アプリケーション向けと FabricPool の階層先）の文書であること、その内容が 2024 年 7 月から ONTAP の製品ドキュメントに統合されたこと、ONTAP S3 が ONTAP 9.8 以降であること（ONTAP 一般） | [NetApp: ONTAP technical reports: S3](https://docs.netapp.com/us-en/ontap-technical-reports/s3.html)（PDF 生成日 2026-09-30）、[NetApp: Learn about ONTAP S3 configuration](https://docs.netapp.com/us-en/ontap/s3-config/index.html)（2025-02-25 更新、2026-10-02 に確認） |
| S3 AP 使用時のボリューム数上限、AP 数のクォータ | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) |
| `StorageClass` が `FSX_ONTAP`、対応 API 操作の一覧の所在 | [AWS: Using access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-usage-examples.html) |
| `Presign` が Supported であること、条件付き書き込み / Object Versioning / Object Lifecycle / Object Lock / Object Annotations / Requester Pays / Static Website Hosting / MFA delete / `RestoreObject` / バケット設定の読み取り系が非対応であること、`CopyObject` と `UploadPartCopy` が同一 Access Point 内の同一リージョンコピーに限られること、ETag が MD5 ダイジェストでないこと、チェックサムが保存も返却もされずダウンロード時の検証に使われないこと、50 GiB がアップロードの上限でダウンロードには上限がないこと、表が partial list であること | [AWS: Access point compatibility](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)（2026-09-14 に全文確認） |
| オブジェクトサイズ上限と判定タイミング（実測であり、AWS ドキュメントの記載ではありません） | [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) |

---

### 関連ドキュメント

- [Domain: データ活用](../README.md): このモジュールのハブ
- [FPolicy が適合するかは、データをどう読むかではなく、どう書くかで決まる](fpolicy-fits-by-how-writes-land.md): 上表の「FPolicy は代替になりません」の肯定側。NFS / SMB で着地する書き込みには動き、そのときの運用要件
- [SnapMirror の宛先は break せずに S3 API で読める](serving-a-replication-destination-over-s3.md): 複製先に AP を取り付ける経路。FlexCache の Cache Volume には取り付けられません
- [LUN の中身はファイルプロトコルに現れない](../../block-storage/notes/lun-contents-do-not-reach-file-protocols.md): ブロックのデータは AP の対象外。分析するまでの 4 段
- [ブロックからファイルへ運ぶ経路の比較](../../../reference/comparison/block-to-file-routes.md): AP を転送先にする経路の `hypothesis` を含みます
- [Domain: マルチプロトコル・ID](../../multiprotocol-identity/): AD 参加済み SVM での前提
- [Playbook 02: 設計](../../../playbooks/02-design/): 不可逆な項目（`NetworkOrigin` など）は設計時に確定します
- [本番投入前レビュー](../../../playbooks/04-build/checklists/pre-production-review.md): S3 AP 関連の確認項目
- [公開されている一次情報と事例の入口](../../../case-studies/public-references.md): 関連リポジトリの位置づけ
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain: データ活用](../README.md)

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | ファイルシステムの ONTAP バージョンを確認する | 9.17.1 以降という前提を満たすか |
| 2 | 対象ボリュームと AP のアカウント・リージョンを確認する | 同一所有・同一リージョンの要件 |
| 3 | 現在のボリューム数と上限を比較する | S3 AP 導入で上限に当たらないか |
| 4 | 使う予定の S3 API 操作を対応一覧と突き合わせる | 実装前に非対応を見つける |
| 5 | 想定する最大オブジェクトサイズで実際に転送を試す | 上限の判定タイミングを含めて確認する |

手順 5 は、成功だけでなく失敗も試してください。上限を超えるオブジェクトで、どの時点でどのエラーが返るかを見ておくと、クライアント側の検証を正しく設計できます。疎通確認では `HeadBucket` だけに依存せず、`ListObjectsV2` などのデータ操作も確認してください（AD 到達不能時に `HeadBucket` だけ成功するという主張は未確認）。

手順 1 の ONTAP バージョンは、次の読み取り専用コマンドで確認できます。

```bash
curl -sk -u fsxadmin "https://<management-endpoint>/api/cluster?fields=version"
```

### 期待結果

```text
version.generation.major が 9.17.1 以上でなければ Access Point を作れない
(AWS CLI の describe-file-systems はバージョンを None で返すことがあるため、ONTAP REST で読む)
```

このコマンドはクラスタのバージョンを読むだけで、ファイルシステムにも Access Point にも変更を加えません。オブジェクトサイズ上限（実測）や撤去手順は本文の該当節を、検証環境で先に通してください。

## Read next

[コピーを増やさずにデータへ届けるにはどうするか？](reaching-data-without-copies.md)
