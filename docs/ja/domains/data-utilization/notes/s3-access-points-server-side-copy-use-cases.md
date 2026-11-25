---
title: S3 Access Points のサーバー側コピーは、直接読めない用途と、バケット側の機能が要る用途に使う
lifecycle: [design, migrate, operate]
domains: [data-utilization, cost]
evidence: verified
verified_on: 2026-11-24
region: ap-northeast-1
ontap_version: 9.19.1P4
lang: ja
---

# S3 Access Points のサーバー側コピーは、どの用途で使い、どの用途で使わないか

ボリュームのファイルをバケットへ、バケットのオブジェクトをボリュームへ、サーバー側で写せるようになりました。使うのは、読む側が Access Point を直接読めないときと、バケット側にしかない機能（アーカイブ用のストレージクラス、S3 Lifecycle、イベント通知など）が要るときです。直接読めるなら、コピーしない構成を先に検討します。

## このノートで学べること

- 2026-11-22 に告知されたサーバー側コピー（`CopyObject` / `UploadPartCopy`）で、新しく組めるようになった用途と、組めない用途
- 5 GiB を超えるファイル、ファイルの属性、S3 Batch Operations、アーカイブ用のストレージクラスとの往復を、実機で確かめた結果
- 「S3 が正本で、ファイルとしての性能が欲しい」構成（HiL テスト、EDA、メディア、ゲノム解析など）で、コピーを使う範囲
- オンプレミスの ONTAP で同じ目的に使われている運用が、FSx for ONTAP ではどう置き換わるか
- 連携する AWS サービスと外部ツールのうち、Access Point での動作を出典か実測で確かめられたものと、確かめられていないもの

## このノートが答えないこと

- SnapMirror、FlexCache、FlexClone によるボリューム単位の複製の設計。サーバー側コピーはオブジェクト単位で、これらの代わりにはなりません
- S3 Object Lock などの WORM 機能を使った保持設計。不可逆な設定なので、保持期間を名指しした承認を別に取ってください（[不可逆な操作の承認は作業の承認とは別に取る](../../security-governance/notes/irreversible-operations-need-separate-approval.md)）
- 料金の見積り。下の金額は単価 × 数量の計算例で、請求額ではありません

## 前提レベル

intermediate

## 本文

[🏠 リポジトリトップ](../../../../../README.md) | [Domain: データ活用](../README.md)

---

### 結論

Amazon FSx for NetApp ONTAP（以下 FSx for ONTAP）のボリュームに付けた S3 Access Points と、Amazon S3 の汎用バケットの間で、`CopyObject` と `UploadPartCopy` によるサーバー側のコピーができます（[What's New、2026-11-22](https://aws.amazon.com/about-aws/whats-new/2026/11/s3-access-points-server-side-copy-fsx/)）。データはコピーを指示したクライアントを通りません。これまでは、EC2 や AWS Lambda がオブジェクトを一度取得し、アップロードし直していました。

用途は次の 3 つに分かれます。

| 用途の型 | 例 | コピーが要る理由 |
|---|---|---|
| バケット側の機能が要る | S3 Glacier Deep Archive への退避、S3 Lifecycle、イベント通知、Amazon Macie、クロスリージョンレプリケーション | Access Point の側では、ストレージクラスは `FSX_ONTAP` だけで、Lifecycle とイベント通知は非対応です（[対応表](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)）。Macie とレプリケーションは対応表に載っていません |
| ファイルとして渡す | データレイクのバケットにあるデータを、NFS / SMB で読む装置やアプリへ渡す | 読む側が S3 API に対応していません |
| 別のファイルシステムへ渡す | 別のファイルシステム、別のアカウントの Access Point へ写す | 同じリージョンの中で、マウントせずに写したい |

Amazon Athena、AWS Glue、Amazon Bedrock Knowledge Bases のように Access Point を直接読めるサービスへ渡すだけなら、コピーは要りません（[AWS サービスでの利用](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-access-points-with-aws-services.html)）。コピーは複製なので、正本が 2 か所になり、どちらを更新するかの約束が要ります。

設計の前に知っておく制約は次の 4 つです。

1. 写るのは中身だけです。所有者、パーミッション、更新時刻はコピー先の設定とコピーした時刻になり、パーミッションは 640 が 644 になりました（2026-11-24 の実測）
2. 1 回の `CopyObject` は 5 GiB までです。それを超えるファイルは `UploadPartCopy` を使うマルチパートのコピーで写せます（6 GiB で実測）
3. 50 GiB を超えるファイルは、Access Point を通してボリュームへ写せません。ボリューム側のアップロード上限で、ユーザーガイドの対応表の記載です（測ったのは 6 GiB まで）
4. S3 Glacier Flexible Retrieval と S3 Glacier Deep Archive から戻すときは、先にバケット側で復元が要ります（実測）

> **区分**: 機能の範囲は、What's New とユーザーガイドの記載です（2026-11-24 に閲覧）。下の「[実機で確かめた範囲](#実機で確かめた範囲)」は、このリポジトリで 2026-11-24 に `ap-northeast-1` の第 1 世代 `SINGLE_AZ_1`（ONTAP 9.19.1P4）で 1 回ずつ確かめた結果です。用途、連携先、費用の節で「推測」と書いた箇所は、測っていません。

---

### 実機で確かめた範囲

環境は次のとおりです。コピーはすべて AWS CLI から実行しました。

| 項目 | 値 |
|---|---|
| コピー元 | 第 1 世代 `SINGLE_AZ_1`、ONTAP 9.19.1P4、UNIX セキュリティスタイルのボリュームに付けた Access Point（ファイルシステムユーザーは UNIX の root） |
| コピー先 | 別の第 1 世代 `SINGLE_AZ_1` のボリュームに付けた Access Point、同じリージョンの汎用バケット |
| 比べ方 | NFS でマウントして読んだファイルの SHA-256、`HeadObject`、`stat` |
| 回数 | 各 1 回。所要時間はサンプル実行で、本番の見積りではありません |

| # | 確かめたこと | 結果 |
|---|---|---|
| 1 | 8 MiB のオブジェクトを、バケット → Access Point、Access Point → バケット、同じ Access Point の中、別のファイルシステムの Access Point へ `CopyObject` | すべて成功し、中身が一致（[制約ノートの表](s3-access-point-constraints.md#バケットと別の-access-point-の間のサーバー側のコピー)） |
| 2 | 6 GiB のファイルを 1 回の `CopyObject` でバケットへ、また別の Access Point へ | どちらも `InvalidRequest`（The specified copy source is larger than the maximum allowable size for a copy source: 5368709120） |
| 3 | 同じ 6 GiB を `aws s3 cp`（768 パートの `UploadPartCopy`）で、Access Point → バケット、バケット → 別の Access Point、Access Point → 別の Access Point | 3 つとも成功し、中身が一致。所要時間は順に 24 秒、129 秒、131 秒 |
| 4 | 所有者 1234:5678、モード 640、更新時刻 2020-01-02 のファイルを、別の Access Point へ直接、またバケット経由でコピー | 中身は一致。コピー先の所有者は 0:1、モードは 644、更新時刻はコピーした時刻になった。コピー元の `HeadObject` は `LastModified` にファイルの更新時刻を返したが、ユーザー定義のメタデータは空 |
| 5 | S3 Batch Operations の `S3PutObjectCopy` ジョブで、バケットのオブジェクトを Access Point へ（`TargetResource` に Access Point のエイリアスを指定） | 2 件とも成功。コピー先のストレージクラスは `FSX_ONTAP` |
| 6 | 同じジョブ型で、マニフェストの `Bucket` 列に Access Point のエイリアスを書き、バケットへ | 1 件成功。中身が一致 |
| 7 | S3 のストレージクラスとの往復 | [制約ノートの往復の表](s3-access-point-constraints.md#s3-のストレージクラスとの往復)にまとめた。`GLACIER` と `DEEP_ARCHIVE` から戻すときは、先にバケット側で復元が要る |

![2 つの枠が上下に並ぶ。上の枠は書き出しで、FSx for ONTAP のボリュームから S3 Access Points を通り、CopyObject または UploadPartCopy で Amazon S3 の汎用バケットへ写す。下の枠は取り込みで、汎用バケットのオブジェクトを CopyObject で S3 Access Points を通してボリュームへ写す。2 つのクラスは先に RestoreObject で復元する。右の欄に、汎用バケットの 8 つのクラスすべてへ書き出せたこと、そのまま取り込めた 6 つのクラス、先に復元が要る 2 つのクラス、コピー先がボリュームのときは SSE-FSX と FSX_ONTAP だけであることを書いている。](../../../../_assets/images/s3ap-server-side-copy-archive.svg)

図 1: S3 Access Points のサーバー側コピーによるアーカイブの往復。上下の FSx for ONTAP は同じファイルシステムでもよい。右の欄の内容は、下の「[ストレージクラスとコピーのオプションの実測一覧](#ストレージクラスとコピーのオプションの実測一覧)」と[制約ノートの往復の表](s3-access-point-constraints.md#s3-のストレージクラスとの往復)と同じで、2026-11-24 に ap-northeast-1 で 1 回ずつ確かめた結果です。

結果 4 から、コピーはファイルの中身を写す操作で、POSIX の所有者・モード・更新時刻は写らないことが分かります。今回のコピー先の Access Point はファイルシステムユーザーが UNIX の root で、所有者 0:1 はこの設定によるものと考えています（[認可は 1 つの ID で行われる](reaching-data-without-copies.md)）。root 以外のユーザーは試していません。モードが 644 になるので、ほかのユーザーに読ませたくないファイルは、写した後にモードを付け直すか、読める範囲を絞ったディレクトリへ写します。属性を保ったまま移す用途は、POSIX の属性なら rsync や AWS DataSync（NFS）、NTFS の ACL なら DataSync（SMB）、ボリューム単位なら SnapMirror の側です。NTFS の ACL を持つボリュームでは測っていません。

コピー元の Access Point の `HeadObject` と `ListObjectsV2` は、`LastModified` にファイルの更新時刻を返しました。更新されていないファイルを選ぶ処理はこの値で組めます。最後に読まれた時刻は S3 API では返らないので、読まれていないファイルを選ぶなら、NFS で `stat` を取るか ONTAP の機能で調べます。

結果 2 と 3 から、5 GiB を超えるファイルは `UploadPartCopy` を使えば写せます。AWS CLI の `aws s3 cp` と `aws s3 sync` は、大きなオブジェクトを自動でマルチパートのコピーにします。コピー先が FSx for ONTAP のボリュームなら、1 オブジェクトのアップロード上限 50 GiB（[対応表](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)）は残ります。

---

### ストレージクラスとコピーのオプションの実測一覧

汎用バケットのストレージクラスごとに、両方向のコピーを 3 つの大きさで確かめました。環境は上の「実機で確かめた範囲」と同じで、2026-11-24 に 1 回ずつ実行しました。所要時間は `aws s3 cp`（6 GiB は 768 パートのマルチパートのコピー）のサンプルで、本番の見積りではありません。中身は、ボリューム側は NFS で読んだファイルの SHA-256、バケット側は取得したオブジェクトの SHA-256 で比べました。

| ストレージクラス | Access Point → バケット | バケット → Access Point（復元なし） | 1 KiB の往復 | 6 GiB: Access Point → バケット | 6 GiB: バケット → Access Point |
|---|---|---|---|---|---|
| S3 Standard（`STANDARD`） | 成功 | 成功 | 成功 | 24 秒 | 130 秒 |
| S3 Reduced Redundancy（`REDUCED_REDUNDANCY`） | 成功 | 成功 | 試していない | 20 秒 | 134 秒、135 秒 |
| S3 Standard-IA（`STANDARD_IA`） | 成功 | 成功 | 成功 | 20 秒 | 223 秒、130 秒 |
| S3 One Zone-IA（`ONEZONE_IA`） | 成功 | 成功 | 成功 | 19 秒 | 134 秒 |
| S3 Intelligent-Tiering（`INTELLIGENT_TIERING`） | 成功 | 成功 | 成功 | 20 秒 | 134 秒 |
| S3 Glacier Instant Retrieval（`GLACIER_IR`） | 成功 | 成功 | 成功 | 22 秒 | 133 秒 |
| S3 Glacier Flexible Retrieval（`GLACIER`） | 成功 | `InvalidObjectState`。迅速取り出しで復元した後は成功 | - | 24 秒 | - |
| S3 Glacier Deep Archive（`DEEP_ARCHIVE`） | 成功 | `InvalidObjectState`。復元した後は完了待ち | - | 23 秒 | - |

表の読み方を補足します。

- 「バケット → Access Point」で中身が一致したコピーは、どれもコピー先のクラスが `FSX_ONTAP` になりました
- 6 GiB の「バケット → Access Point」で 2 つの値があるのは、2 回実行した結果です。S3 Standard-IA は 1 回目が 223 秒、2 回目が 130 秒でした。1 回ずつのサンプルなので、クラスによる差とは読めません
- S3 Standard-IA、S3 One Zone-IA、S3 Glacier Instant Retrieval は、128 KB 未満のオブジェクトも 128 KB として課金されます（[Amazon S3 のストレージクラスの比較](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html)）。1 KiB のファイルも写せましたが、料金は 128 KB 分です
- S3 Reduced Redundancy は、AWS が使わないよう勧めているクラスです（[Amazon S3 のストレージクラスの比較](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html)）。写せることを確かめただけで、勧めるものではありません
- S3 Intelligent-Tiering で試したのは、すぐに読める層にあるオブジェクトです。アーカイブ用の層（Archive Access、Deep Archive Access）へ移るには 90 日以上アクセスがないことが要るので、試していません
- コピー先のボリュームが満杯になると、`CompleteMultipartUpload` が `InsufficientCapacity` で失敗しました。同じ状況で `ServiceUnavailable` が返ったこともあります。大きなファイルを写す前に、ボリュームの空き容量を確かめてください

ストレージクラス以外の指定と、汎用バケット以外のコピー先も確かめました。

| 確かめたこと | 結果 |
|---|---|
| Access Point → 汎用バケット、`--storage-class` に `EXPRESS_ONEZONE`、`OUTPOSTS`、`SNOW` | `InvalidStorageClass` |
| Access Point → 汎用バケット、`--storage-class FSX_ONTAP` | `InvalidArgument`（FSX_ONTAP is not allowed.） |
| バケット → Access Point、`--storage-class FSX_ONTAP` | 成功。`FSX_ONTAP` を明示してもよい |
| バケット → Access Point、`--storage-class` に `STANDARD_IA`、`GLACIER_IR` | `InvalidStorageClass` |
| Access Point → 別の Access Point、`--storage-class FSX_ONTAP` | 成功 |
| Access Point → S3 Express One Zone のディレクトリバケット | `InternalServerError`（3 回とも） |
| S3 Express One Zone のディレクトリバケット → Access Point | `InvalidArgument`（Invalid copy source header） |
| 対照: 汎用バケットとディレクトリバケットの間（タグのないオブジェクト） | 両方向とも成功。タグの付いたオブジェクトは、ディレクトリバケットへは `NotImplemented` |
| バージョニングと SSE-KMS（AWS マネージドキー）を有効にしたバケットの古いバージョン → Access Point（`?versionId=` を指定） | 成功。古いバージョンの中身が写り、コピー先の暗号化は `aws:fsx` |
| Access Point → バージョニングと SSE-KMS を有効にしたバケット | 成功。コピー先は `aws:kms` で、新しいバージョンができた |
| Access Point → バケット、`--server-side-encryption` に `AES256`、`aws:kms` | どちらも成功し、指定した暗号化になった |
| バケット → Access Point、`--server-side-encryption aws:fsx` | 成功（`AES256` は `InvalidArgument`） |
| タグ（既定の `COPY`） | バケット → Access Point、Access Point → バケットのどちらでも、コピー元のタグが写った |
| タグ（`--tagging-directive REPLACE`）、バケット → Access Point | 成功。指定したタグに置き換わった |
| ユーザー定義のメタデータ（`--metadata-directive REPLACE`） | 両方向とも成功。Access Point 側でも `HeadObject` がメタデータと Content-Type を返した |
| `--checksum-algorithm SHA256` | どちらのコピー先でも成功。バケットは `ChecksumSHA256` を返し、Access Point は返さなかった |
| `--copy-source-if-match`（Access Point のオブジェクトの ETag） | 正しい ETag で成功、違う ETag で `PreconditionFailed` |
| `UploadPartCopy` の `--copy-source-range`、Access Point → バケット、2 パート | 成功。中身が一致 |

S3 Express One Zone のディレクトリバケットとの間のコピーは、What's New とユーザーガイドが挙げる「汎用バケット」の範囲の外で、今回は両方向とも失敗しました。ディレクトリバケットとの間でデータを動かすなら、汎用バケットを経由します。

---

### 直接読むか、コピーするかの判断

先に、読む側が対応しているプロトコルで分けます。

| 読む側 | 第一の選択肢 | コピーが要る場合 |
|---|---|---|
| S3 API で読み、Access Point のエイリアスか ARN を指定できる（Athena、Glue、Bedrock Knowledge Bases、SageMaker など） | Access Point を直接読む | バケット側の機能（Lifecycle、イベント通知、Macie、バージョニング、レプリケーション）が要るとき |
| NFS / SMB でしか読めない（物理装置、既存の業務アプリ、Windows のクライアント） | ボリュームをマウントする | 正本がバケットにあり、装置の近くのボリュームへ写す必要があるとき |
| 別のファイルシステムや別のアカウント | FlexCache、SnapMirror、Access Point ポリシーでの共有 | ボリューム全体ではなく、選んだファイルだけを写したいとき |

サーバー側コピーは、ファイル単位で、属性を持たず、増分の仕組みもありません。SnapMirror のような整合性のあるボリュームの複製や、FlexCache のような読まれた分だけを持つキャッシュとは、使う場面が違います。

---

### 新規の利用者と既存の利用者の用途

「新規」は、これから FSx for ONTAP を入れる利用者、「既存」は、すでにボリュームを運用している利用者です。根拠の列の「実測」は上の表の番号、「文書」はユーザーガイドか What's New、「推測」は測っていないものです。

| # | 用途 | 主な利用者 | 方向 | これまでの方法 | 確かめる制約 | 根拠 |
|---|---|---|---|---|---|---|
| 1 | アクセスの少ないファイルを S3 Glacier Deep Archive へ退避する | 既存 | Access Point → バケット | クライアントで取得して再アップロード、または外部のアーカイブツール | 属性が写らない（実測 4）。ボリューム側の削除は別の操作。最小保管期間 180 日 | 実測 7、文書 |
| 2 | 退避したファイルをボリュームへ戻す | 既存 | バケット → Access Point | 復元後にクライアントで取得して書き込み | 先にバケット側で `RestoreObject`。Access Point の側は `RestoreObject` 非対応 | 実測 7、文書 |
| 3 | データレイクのバケットにあるデータを、NFS / SMB の業務アプリへ渡す | 新規、既存 | バケット → Access Point | マウントしたホストで `aws s3 sync` | 所有者はコピー先 Access Point のユーザーになる（実測 4）。アプリが期待する所有者は別に設定する | 実測 1、4 |
| 4 | 移行の初期投入（バケットにある過去のデータを入れる） | 新規 | バケット → Access Point | DataSync、マウントしたホストでのコピー | NTFS の ACL など属性が要るなら DataSync の側。属性が要らなければマウント用のホストが要らない | 実測 1、3、4 |
| 5 | 処理結果をバケットへ公開し、イベント通知や Lifecycle に載せる | 既存 | Access Point → バケット | クライアントで取得して再アップロード | Access Point の側にイベント通知はないので、コピーのきっかけは定期実行か、書き込んだアプリからの呼び出し | 実測 1、文書 |
| 6 | 別のファイルシステム、別のアカウントへ選んだファイルを渡す | 既存 | Access Point → Access Point | NFS で両方をマウントしてコピー | 同じリージョンだけ。アカウントをまたぐ場合は両側の IAM と Access Point ポリシー。アカウントをまたぐコピーは測っていない | 実測 1、文書 |
| 7 | 開発・テスト用のボリュームへ、選んだデータを写す | 既存 | Access Point → Access Point | NFS でのコピー | ボリューム全体なら FlexClone を検討する。FlexClone は元のボリュームとブロックを共有するので、変更した分だけ容量を使う。個人情報の匿名化は別の工程 | 実測 1、推測 |
| 8 | 大きなメディアファイルを配信・保管用のバケットへ送る | 既存 | Access Point → バケット | クライアントで取得して再アップロード | 5 GiB を超えるとマルチパートのコピーが要る（実測 2、3） | 実測 2、3 |
| 9 | アプリがボリュームに出すログやダンプを、分析・保管用のバケットへ送る | 既存 | Access Point → バケット | cron と AWS CLI | 新しいファイルの検出は一覧の走査になる。FSx for ONTAP のバックアップの代わりにはならない | 実測 1、文書 |
| 10 | 大量のファイルをまとめてコピーする | 新規、既存 | 両方向 | 自作のスクリプト | S3 Batch Operations の Copy ジョブが使えた（実測 5、6）。ジョブで写せるのは 1 件 5 GB まで、コピー元とコピー先はそれぞれ 1 つ（[Batch Operations の制限](https://docs.aws.amazon.com/AmazonS3/latest/userguide/batch-ops-copy-object.html)）。マニフェストは `ListObjectsV2` の結果から作った | 実測 5、6、文書 |

用途 1 と 2 を組み合わせると、ボリュームを作業場所、S3 Glacier 系のクラスを長期の保管場所にして、ファイルを行き来させる運用ができます。ファイルの一覧と、どのファイルをどこへ移したかの記録は、利用者が持つことになります。[ファイルポータルと既存の実装](#ファイルポータルと既存の実装)の節も参照してください。

退避した後にボリュームのファイルを消すときは、次の順で確かめます。

1. 写す前に、ファイルごとにパス、大きさ、更新時刻、所有者、モード、SHA-256 を記録する。戻したときに属性を付け直すのにも使う
2. 写した後、バケットの `HeadObject` で大きさを比べる。ETag は中身の MD5 ではなく、ボリューム側にはチェックサムが保存されない（[対応表](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)）ので、中身の一致は SHA-256 を自分で比べる
3. 確認できたファイルだけを消す。スナップショットが消したファイルのブロックを持っている間は、容量は空かない

マルチパートのコピーが途中で止まると、パートが残ります。バケット側は S3 Lifecycle の不完全なマルチパートアップロードの削除で、ボリューム側は `AbortMultipartUpload` で片付けます。対応表は、中断したパートがファイルシステムの使用量に数えられると書いています。

コピー先のバケットに S3 Object Lock の既定の保持期間が設定されていると、写したオブジェクトにもその保持期間がかかり、期間中は消せません。保持の設計は、法令や規制の判断ではなく、システム設計上の考慮として扱い、保持期間を名指しした承認を取ってから設定してください。

退避先のバケットについては、次の項目を設計の段階で決めておきます。いずれもシステム設計上の確認事項で、法令や規制への適合の判断ではありません。

| 項目 | 決めること |
|---|---|
| 保管場所 | バケットのリージョン。コピーは同じリージョンの中だけ |
| 暗号化 | バケットの既定の暗号化（SSE-S3 か SSE-KMS）。SSE-KMS なら、コピーを呼ぶ側に鍵の権限が要る |
| アクセス制御 | バケットポリシーと、Block Public Access の設定 |
| 保持 | S3 Lifecycle による削除の時期。S3 Object Lock を使うかどうかは、保持期間を名指しした承認を取ってから |
| 記録 | 誰がいつ写し、戻したかを残す方法（AWS CloudTrail のデータイベントなど） |

---

### S3 が正本で、ファイルとしての性能が欲しい構成

[S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) は、S3 API で集めたデータを、FlexCache を通して NFS / SMB で読ませる構成を扱います。このリポジトリの基準構成では、正本は FSx for ONTAP のボリューム（Origin）で、S3 Access Points は書き込みの入口です。正本が汎用バケットにある形は、比較の対象や、移行の出発点として出てきます。サーバー側コピーが変えるのは、正本がバケットにある形です。

下の表のユースケースと試算は、S3-Burst-on-ONTAP-Files の [architecture.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/architecture.md) と [finops-s3-vs-s3ap.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/comparison/finops-s3-vs-s3ap.md) にあるものです。試算は ap-northeast-1、2026-08-09 取得の単価による計算で、実測ではありません。「コピーで変わること」は、すべて推測です。

| ユースケース | 読む側 | オブジェクトの大きさ（試算の前提） | 正本がバケットにあるときのこれまでの取り込み | コピーで変わること（推測） |
|---|---|---|---|---|
| 自動車の AV / ADAS の HiL（Hardware-in-the-Loop）テスト。走行ログとセンサーデータをテストベンチで再生する | AWS の外に置いた物理のテストベンチ（NFS / SMB） | 約 1 MiB、月 2,000 万件 | DataSync | DataSync のタスクと中継のホストなしで、バケットから Origin へ写せる。1 件が 5 GiB より小さいので 1 回の `CopyObject` で足りる。月 2,000 万件のリクエスト料金と所要時間、写したファイルが Cache から読めるまでの時間は測っていない |
| EDA / CAE。設計ジョブの入出力 | HPC のジョブ（NFS） | 約 256 KiB、月 6,000 万件 | DataSync | 小さなファイルが多いので、1 件 1 リクエストの料金と、Access Point のリクエストレートの上限が先に問題になりうる |
| メディア / VFX のレンダリング素材 | 制作端末、レンダリングノード（SMB / NFS） | 約 500 MiB、月 5 万件 | DataSync | 5 GiB を超える素材はマルチパートのコピー（実測 3）。50 GiB を超える素材は Access Point へ写せない |
| ゲノム解析のシーケンサー出力 | HPC クラスタ（NFS） | 約 8 MiB、月 200 万件 | DataSync | 5 GiB を超える BAM / FASTQ はマルチパートのコピー。S3 Glacier 系に退避済みのデータは、先に復元が要る |
| 車載 / IoT のテレメトリ | 解析ジョブ | 約 64 KiB、月 3 億件 | DataSync（比較対象） | 小さなファイルが多く、コピーのリクエスト料金が DataSync の転送料金を上回る可能性がある |
| AWS の外の利用者が同じデータを繰り返し読む | AWS の外のクライアント | 4 MiB、20 TiB を月 30 回 | DataSync で全量を写す案 | 全量を写す手段に、コピーが加わる。読まれた分だけを持ち込む FlexCache の性質は変わらない |
| 石油・ガス、製造の品質検査、医療画像、IoT / エッジ、リモートワーク | NFS / SMB の端末 | 試算なし | 記述なし | 判断する材料がない |

HiL テストを例に、取り込みの経路を比べます。

| 経路 | 正本 | テストベンチへの渡し方 | 向いている場面 |
|---|---|---|---|
| 基準構成 | Origin のボリューム。走行ログは Access Point へ `PutObject` で集める | FlexCache の Cache を NFS / SMB で読む | 新しく収集の経路を作れる |
| バケットが正本、コピーで取り込む | 汎用バケット | 必要なログだけを Origin へ `CopyObject` し、FlexCache で配る | 収集はすでにバケットへ流れていて、変えられない |
| バケットが正本、DataSync で取り込む | 汎用バケット | DataSync のタスクで Origin へ写し、FlexCache で配る | ファイルの属性やスケジュールの管理を DataSync に任せたい |
| バケットが正本、Amazon S3 Files で読む | 汎用バケット | S3 Files を NFSv4.1 / v4.2 でマウントする | 読む側が AWS 上の Linux で、マウントヘルパーを入れられる |

S3-Burst-on-ONTAP-Files は、HiL のテストベンチが NFSv3 に固定された AWS の外の装置である前提で、S3 Files を「要件を満たさない」としています。この前提が自分の環境で成り立つかを先に確かめてください。S3 Files の速さと月額は、[S3 Files の実測の記事](https://hakobiya.hatenablog.com/entry/fsxn-s3files-value-measured)にあります。

---

### オンプレミスの ONTAP での運用からの置き換え

オンプレミスの ONTAP には、ファイルを選んで S3 Glacier 系のクラスへサーバー側で写す機能は見つかりませんでした。FabricPool、ONTAP S3、SnapMirror Cloud の NetApp のドキュメントを 2026-11-24 に確かめた結果です。同じ目的には、次の運用が使われています。

| オンプレミスでの運用 | 目的 | FSx for ONTAP とサーバー側コピーでの扱い | 出典 |
|---|---|---|---|
| FabricPool で、冷えたブロックを Amazon S3 へ階層化する | SSD の容量を空ける。ファイルからは透過的 | FSx for ONTAP では容量プールの階層化が同じ役割を持つ。FabricPool はブロック単位で、Amazon S3 の S3 Glacier Flexible Retrieval と S3 Glacier Deep Archive は対象外。ファイル単位でクラスを選ぶコピーとは別の層 | [FabricPool の要件](https://docs.netapp.com/us-en/ontap/fabricpool/requirements-concept.html) |
| 外部のデータ管理ツールで、ファイル単位にアーカイブする | 最終アクセス日時などで選び、元のパスから読み戻せるようにする | コピーで置き換えられるのは移動の部分だけ。選別、元のパスからの読み戻し、メタデータの管理はコピーに含まれない | [AWS Storage Blog の製造業の事例](https://aws.amazon.com/blogs/storage/cost-optimized-file-storage-with-amazon-fsx-for-netapp-ontap-and-komprise/)、[アーカイブと階層化の順序](../../cost/notes/archiving-and-tiering-are-ordered-not-alternatives.md) |
| SnapMirror Cloud で、オブジェクトストレージへバックアップする | ボリューム単位の保護と復元 | FSx for ONTAP では、バックアップと SnapMirror が同じ役割を持つ。コピーはボリュームの保護手段ではない | [SnapMirror Cloud の概要](https://docs.netapp.com/us-en/ontap/concepts/snapmirror-cloud-backups-object-store-concept.html) |
| ONTAP S3 のマルチプロトコル（NAS バケット）で、NAS のデータを S3 API のアプリに見せる | 分析・機械学習から、コピーせずに読む | FSx for ONTAP では S3 Access Points が同じ目的の機能。コピーは、Access Point とバケットの間の移動を加える | [ONTAP S3 マルチプロトコル](https://docs.netapp.com/us-en/ontap/s3-multiprotocol/) |
| オンプレミスから SnapMirror で FSx for ONTAP へ移し、その後アーカイブする | 段階的な移行とアーカイブ | 移したボリュームの Access Point から、バケットの各クラスへコピーできる。この流れを手順として公開した事例は見つかっていない | [SnapMirror による移行](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/migrating-fsx-ontap-snapmirror.html) |

この表の外部ツールは、公開された事例に出てくるものとして名前を挙げています。推奨ではありません。

---

### 連携する AWS サービスと外部ツール

「Access Point での動作」の列は、FSx for ONTAP の Access Point で動くことを、出典か実測で確かめたかどうかです。

| サービス、ツール | コピーとの関係 | Access Point での動作 | 出典、補足 |
|---|---|---|---|
| AWS CLI、AWS SDK | コピーを呼ぶ | 実測 1〜4 | `aws s3 cp` は 5 GiB を超えると自動でマルチパートのコピーになる |
| S3 Batch Operations | 大量のコピーをジョブにする | 実測 5、6 | マニフェストの作成、IAM ロール、完了レポートの置き場所は利用者が用意する |
| AWS Lambda | コピーを呼ぶ処理 | 同じ Access Point の中は記録あり | Lambda から同じ Access Point の中で `copy_object` を呼ぶ実装が、[FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) のファイルポータルにある。バケットとの間のコピーを Lambda から呼ぶ形は、AWS CLI と同じ API なので組める（推測） |
| AWS Step Functions | コピーの順序、再試行、記録 | 測っていない | 同じリポジトリの [大量バッチ処理のガイド](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/large-batch-processing-guide.md) は、1,000 件を超える処理で Distributed Map への移行を勧めている。目的は処理の並列化で、コピーではない <!-- spoke-checked: copyobject --> |
| Amazon EventBridge Scheduler | 定期的なコピーのきっかけ | 該当なし | Access Point の側にイベント通知がないので、定期実行が起点になる |
| AWS DataSync | 別の転送の仕組み | 該当なし | ファイルの属性を保つ移行や、スケジュールの管理が要るときの選択肢 |
| AWS Transfer Family | 外部とのファイル受け渡しの入口 | 文書 | [Transfer Family と S3 Access Points](https://docs.aws.amazon.com/transfer/latest/userguide/fsx-s3-access-points.html)。バケットで受けたデータを共有領域へ写す後段にコピーを置ける（推測） |
| Amazon Athena、AWS Glue | Access Point を直接読む | 文書 | [Athena のチュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)。コピーは要らない |
| Amazon Bedrock Knowledge Bases | Access Point をデータソースにする | 文書 | [RAG のチュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html)。コピーは要らない |
| Amazon Macie | バケットの機密データの検出 | 対象外の記録あり | [FSx-for-ONTAP-Cyber-Resilience-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns) の記録は、Macie がストレージクラス `FSX_ONTAP` のオブジェクトを対象外にすると整理している。検査が要るならバケットへのコピーが前提になる（推測） |
| S3 Lifecycle | バケットへ写した後のクラスの移動、期限切れの削除 | バケット側の機能 | コピーの時点でクラスを指定できる（実測 7）ので、Lifecycle を待たずに S3 Glacier 系へ置ける |
| AWS CloudTrail | コピーの記録 | データイベントは記録あり | Access Point 経由の操作が S3 のデータイベントとして記録されることは、[制約ノート](s3-access-point-constraints.md)と [FSx-for-ONTAP-Observability-integrations の記録](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/blob/main/integrations/grafana/docs/en/cloudtrail-trigger-alternative.md)にある。`CopyObject` がコピー元とコピー先のどちらのイベントとして出るかは測っていない <!-- spoke-checked: cloudtrail --> |
| rclone、s5cmd などの S3 互換ツール | コピーを呼ぶ | 記録では未確認 | [FSx-for-ONTAP-S3AccessPoints-Client-Access-Patterns の互換性マトリクス](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Client-Access-Patterns/blob/main/docs/compatibility-matrix.md)は、rclone と s5cmd の一覧・取得・書き込み・マルチパート・削除をすべて未確認としている。コピーは列にない。Access Point のエイリアスを `CopySource` に渡せるかは、ツールごとに確かめる <!-- spoke-checked: rclone --> |

---

### アーカイブの往復の費用

単価は 2026-11-24 に Price List API で ap-northeast-1 について取得しました。下の金額は単価 × 数量の計算例で、請求額ではありません。表にない費目（容量プールのリクエスト料金、スループット容量、S3 Batch Operations のジョブ料金）は含みません。S3 Standard の保管単価（最初の 50 TB）は $0.025 / GB-月、Access Point の PUT・COPY は $0.00108 / 1,000 件です。

| 単価（ap-northeast-1） | 値 |
|---|---|
| FSx for ONTAP Single-AZ の SSD | $0.150 / GB-月 |
| FSx for ONTAP Single-AZ の容量プール | $0.0238 / GB-月 |
| S3 Glacier Flexible Retrieval の保管 | $0.0045 / GB-月 |
| S3 Glacier Deep Archive の保管 | $0.002 / GB-月 |
| S3 Glacier Deep Archive への `CopyObject` | $0.065 / 1,000 リクエスト |
| S3 Glacier Deep Archive からの取り出し（Standard / Bulk） | $0.022 / GB、$0.005 / GB |
| S3 Glacier Deep Archive の復元リクエスト（Standard / Bulk） | $0.1142 / 1,000、$0.025 / 1,000 |

計算の前提は、10 TiB（10,240 GB）、平均約 105 MiB のファイル 10 万件を容量プールから S3 Glacier Deep Archive へ移し、そのうち 1 TiB（1 万件）を 1 回戻す、というものです。

| 項目 | 計算 | 金額 |
|---|---|---|
| 容量プールに置いたままの保管 | 10,240 GB × $0.0238 | $243.71 / 月 |
| S3 Glacier Deep Archive に置いた保管 | 10,240 GB × $0.002 | $20.48 / 月 |
| 移すときのコピー（S3 Glacier Deep Archive 側） | 10 万件 × $0.065 / 1,000 | $6.50（1 回） |
| 移すときのコピー（Access Point 側のリクエスト） | 10 万件 × $0.00108 / 1,000 | 約 $0.11（1 回） |
| 復元した一時コピーを 7 日置く | 1,024 GB × $0.025 × 7 / 30 | 約 $5.97（1 回） |
| 1 TiB を Standard の取り出しで戻す | 1,024 GB × $0.022 + 1 万件 × $0.1142 / 1,000 | $23.67（1 回） |
| 1 TiB を Bulk の取り出しで戻す | 1,024 GB × $0.005 + 1 万件 × $0.025 / 1,000 | $5.37（1 回） |

S3 Glacier Deep Archive には 180 日の最小保管期間があり、それより前に削除すると残りの日数分の保管料金がかかります。オブジェクトごとに 40 KB のメタデータも課金されます（[Amazon S3 の料金](https://aws.amazon.com/s3/pricing/)）。小さなファイルが多いと、コピーと復元のリクエスト料金とメタデータの比重が上がります。ボリュームへ戻したデータが SSD と容量プールのどちらに置かれるかは、ボリュームの階層化ポリシーで決まります（推測。確かめていません）。

---

### ファイルポータルと既存の実装

関連するリポジトリには、コピーを使う実装が 2 つあります。どちらも、今回のリリースより前の前提で書かれています。

| 実装 | 現在の動き | サーバー側コピーで変えられること（推測） |
|---|---|---|
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) のファイルポータル（`solutions/amplify-portal/functions/list-files/index.py`） | 名前の変更、移動、コピー、ゴミ箱への移動と復元を、同じ Access Point の中の `copy_object` で行う。5 GiB を超えると理由を示して断る | バケットへの退避と、バケットからの復元を画面の操作として加えられる。5 GiB を超えるファイルもマルチパートのコピーで扱える |
| [FSx-for-ONTAP-Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) の管理コンソール（`management-console/lambda/s3_copy_handler.py`） | ダウンロード用の一時バケットへ、Lambda がオブジェクトを取得してアップロードし直す。本文をメモリに読み込む | 一時バケットへのサーバー側コピーに置き換えれば、Lambda のメモリと実行時間がファイルの大きさに縛られなくなる |

ファイルポータルにアーカイブの操作を加えるなら、どのファイルを、いつ、どのクラスへ移したかの記録と、復元にかかる時間を利用者に示す画面が要ります。ドキュメントの目安は、S3 Glacier Flexible Retrieval が迅速 1〜5 分、標準 3〜5 時間、大容量 5〜12 時間、S3 Glacier Deep Archive が標準 12 時間以内、大容量 48 時間以内です（[Understanding archive retrieval options](https://docs.aws.amazon.com/AmazonS3/latest/userguide/restoring-objects-retrieval-options.html)）。S3 Intelligent-Tiering でも、アーカイブ用の層へ移ったオブジェクトは復元が要ります。

---

### 測っていないこと

- NTFS の ACL を持つボリューム（SMB の利用者がいる環境）での、コピー先のファイルの所有者と ACL
- アカウントをまたぐコピー、FlexCache のボリュームに付けた Access Point からのコピー
- S3 Glacier Deep Archive から復元した後のボリュームへのコピー（復元を 2026-11-24 に要求し、完了待ち）
- S3 Intelligent-Tiering のアーカイブ用の層に移ったオブジェクトのコピー
- S3 Glacier Flexible Retrieval の標準・大容量取り出しと、S3 Glacier Deep Archive の大容量取り出しにかかった時間（2026-11-24 に要求し、完了待ち）
- 小さなファイルを大量にコピーしたときのリクエストレートの上限と所要時間
- FlexCache の Origin のボリュームへ写したファイルが、Cache から読めるようになるまでの時間
- 第 2 世代、Multi-AZ のファイルシステムでのコピー
- 並列に写したときのスループットと、ペタバイト規模での所要時間（コピーは 1 件ずつ順に実行した）
- コピー元のバケットが SSE-KMS で暗号化されている場合、バージョニングや Object Lock が有効な場合
- AWS Lambda や AWS Step Functions からコピーを呼ぶ構成

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| サーバー側コピーで、ファイルの属性ごと移せる | 中身だけが写る。所有者、モード、更新時刻は、コピー先の Access Point の設定とコピーした時刻になった（実測 4） |
| 5 GiB を超えるファイルはコピーできない | 1 回の `CopyObject` は 5 GiB まで。`UploadPartCopy` を使うマルチパートのコピーで 6 GiB を写せた（実測 2、3） |
| コピーできるなら、SnapMirror や FlexClone は要らない | コピーはオブジェクト単位で、整合性のあるボリュームの複製も、差分の転送もない |
| S3 Glacier Deep Archive へ移したファイルは、すぐ戻せる | 先にバケット側で復元を要求し、完了を待つ。Access Point の側では `RestoreObject` は使えない |
| Access Point を直接読めるサービスにも、バケットへのコピーが要る | Athena、Glue、Bedrock Knowledge Bases は Access Point を直接読める |

---

### 参照した一次情報

- [What's New: Amazon S3 Access Points for Amazon FSx now support server-side copy](https://aws.amazon.com/about-aws/whats-new/2026/11/s3-access-points-server-side-copy-fsx/)（2026-11-22）
- [Access point compatibility（FSx for ONTAP ユーザーガイド）](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)
- [Restoring an archived object（Amazon S3 ユーザーガイド）](https://docs.aws.amazon.com/AmazonS3/latest/userguide/restoring-objects.html)
- [Copying objects with S3 Batch Operations（Amazon S3 ユーザーガイド）](https://docs.aws.amazon.com/AmazonS3/latest/userguide/batch-ops-copy-object.html)
- [Amazon S3 の料金](https://aws.amazon.com/s3/pricing/)

### 関連ドキュメント

- [FSx for ONTAP S3 Access Points は S3 として使えるか](s3-access-point-constraints.md)
- [コピーを増やさずにデータへ届けるにはどうするか](reaching-data-without-copies.md)
- [外部ツールのアーカイブと容量プール階層の順序](../../cost/notes/archiving-and-tiering-are-ordered-not-alternatives.md)
- [不可逆な操作の承認は作業の承認とは別に取る](../../security-governance/notes/irreversible-operations-need-separate-approval.md)

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 小さなファイルを 1 つ、バケットから Access Point へ `CopyObject` で写す | 権限とネットワークの前提が整っているか |
| 2 | 5 GiB を超えるファイルを `aws s3 cp` で写し、NFS で読んだ SHA-256 を比べる | コピー元と一致すれば、マルチパートのコピーが通っている |
| 3 | コピー先のファイルを `stat` で読む | 所有者とモードが、アプリの期待どおりか。ファイルシステムユーザーが root の Access Point では `0:1` と `644` だった |
| 4 | `--storage-class DEEP_ARCHIVE` でバケットへ写したファイルを復元し、`head-object` の `Restore` が `ongoing-request="false"` になってから `CopyObject` で戻す | 往復の手順と所要時間 |

```bash
aws s3api copy-object \
  --bucket <destination-access-point-alias> \
  --key check/sample.bin \
  --copy-source <source-bucket>/check/sample.bin
aws s3api head-object --bucket <destination-access-point-alias> --key check/sample.bin \
  --query '[StorageClass,ServerSideEncryption,ContentLength]' --output text
```

### 期待結果

```text
FSX_ONTAP    aws:fsx    <コピー元と同じバイト数>
```

実際の出力では、3 つの値がタブで区切られます。

1 つ目のコマンドは、コピー先のボリュームにファイルを 1 つ作ります。終わったら `aws s3api delete-object` で消してください。手順 4 の S3 Glacier Deep Archive は 180 日の最小保管期間があり、早く消しても残りの日数分の保管料金がかかります。

## Read next

[FSx for ONTAP S3 Access Points は S3 として使えるか](s3-access-point-constraints.md)
