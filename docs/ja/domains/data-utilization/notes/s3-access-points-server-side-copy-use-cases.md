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
- 「S3 が正本で、ファイルとしての性能が欲しい」構成（HiL テスト、EDA、メディア、ゲノム解析など）で、コピーが受け持つ範囲
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
| バケット側の機能が要る | S3 Glacier Deep Archive への退避、S3 Lifecycle、イベント通知、Amazon Macie、クロスリージョンレプリケーション | Access Point の側には、これらの機能がありません（[対応表](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)） |
| ファイルとして渡す | データレイクのバケットにあるデータを、NFS / SMB で読む装置やアプリへ渡す | 読む側が S3 API を話せません |
| 別のファイルシステムへ渡す | 別のファイルシステム、別のアカウントの Access Point へ写す | 同じリージョンの中で、マウントせずに写したい |

Amazon Athena、AWS Glue、Amazon Bedrock Knowledge Bases のように Access Point を直接読めるサービスへ渡すだけなら、コピーは要りません（[AWS サービスでの利用](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-access-points-with-aws-services.html)）。コピーは複製なので、正本が 2 か所になり、どちらを更新するかの約束が要ります。

> **区分**: 機能の範囲は `documented`（What's New とユーザーガイドを 2026-11-24 に閲覧）。下の「[実機で確かめた範囲](#実機で確かめた範囲)」は、このリポジトリで 2026-11-24 に `ap-northeast-1` の第 1 世代 `SINGLE_AZ_1`（ONTAP 9.19.1P4）で 1 回ずつ確かめた `verified` です。用途、連携先、費用の節で「推測」と書いた箇所は、測っていません。

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
| 7 | アーカイブ用のストレージクラスとの往復 | [制約ノートの往復の表](s3-access-point-constraints.md#アーカイブ用のストレージクラスとの往復)にまとめた。`GLACIER` と `DEEP_ARCHIVE` から戻すときは、先にバケット側で復元が要る |

![2 つの枠が上下に並ぶ。上の枠は退避で、FSx for ONTAP のボリュームから S3 Access Points を通り、CopyObject または UploadPartCopy で Amazon S3 の汎用バケットへ写す。下の枠は戻す流れで、汎用バケットのオブジェクトを RestoreObject で復元した後、CopyObject で S3 Access Points を通してボリュームへ写す。右の欄に、退避できた 7 つのストレージクラス、そのまま戻せた 3 つのクラス、先に復元が要る 2 つのクラス、コピー先がボリュームのときは SSE-FSX と FSX_ONTAP だけであることを書いている。](../../../../_assets/images/s3ap-server-side-copy-archive.svg)

図 1: S3 Access Points のサーバー側コピーによるアーカイブの往復。上下の FSx for ONTAP は同じファイルシステムでもよい。右の欄の内容は、上の表の 7 と[制約ノートの往復の表](s3-access-point-constraints.md#アーカイブ用のストレージクラスとの往復)と同じで、2026-11-24 に ap-northeast-1 で 1 回ずつ確かめた結果です。

結果 4 から、コピーはファイルの中身を写す操作で、POSIX の所有者・モード・更新時刻は写らないことが分かります。コピー先の所有者は、コピー先の Access Point に設定したファイルシステムユーザーで決まります（[認可は 1 つの ID で行われる](reaching-data-without-copies.md)）。属性を保ったまま移す用途は、AWS DataSync や rsync、ボリューム単位なら SnapMirror の側です。NTFS の ACL を持つボリュームでは測っていません。

結果 2 と 3 から、5 GiB を超えるファイルは `UploadPartCopy` を使えば写せます。AWS CLI の `aws s3 cp` と `aws s3 sync` は、大きなオブジェクトを自動でマルチパートのコピーにします。コピー先が FSx for ONTAP のボリュームなら、1 オブジェクトのアップロード上限 50 GiB（[対応表](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)）は残ります。

---

### 直接読むか、コピーするかの判断

先に、読む側が何を話せるかで分けます。

| 読む側 | 第一の選択肢 | コピーが要る場合 |
|---|---|---|
| S3 API を話し、Access Point のエイリアスか ARN を指定できる（Athena、Glue、Bedrock Knowledge Bases、SageMaker など） | Access Point を直接読む | バケット側の機能（Lifecycle、イベント通知、Macie、バージョニング、レプリケーション）が要るとき |
| NFS / SMB だけを話す（物理装置、既存の業務アプリ、Windows のクライアント） | ボリュームをマウントする | 正本がバケットにあり、装置の近くのボリュームへ写す必要があるとき |
| 別のファイルシステムや別のアカウント | FlexCache、SnapMirror、Access Point ポリシーでの共有 | ボリューム全体ではなく、選んだファイルだけを写したいとき |

サーバー側コピーは、ファイル単位で、属性を持たず、増分の仕組みもありません。SnapMirror のような整合性のあるボリュームの複製や、FlexCache のような読まれた分だけを持つキャッシュとは、受け持つ範囲が違います。

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
| 7 | 開発・テスト用のボリュームへ、選んだデータを写す | 既存 | Access Point → Access Point | NFS でのコピー | ボリューム全体なら FlexClone のほうが速く、容量も使いません（推測）。個人情報の匿名化は別の工程 | 実測 1、推測 |
| 8 | 大きなメディアファイルを配信・保管用のバケットへ送る | 既存 | Access Point → バケット | クライアントで取得して再アップロード | 5 GiB を超えるとマルチパートのコピーが要る（実測 2、3） | 実測 2、3 |
| 9 | アプリがボリュームに出すログやダンプを、分析・保管用のバケットへ送る | 既存 | Access Point → バケット | cron と AWS CLI | 新しいファイルの検出は一覧の走査になる。FSx for ONTAP のバックアップの代わりにはならない | 実測 1、文書 |
| 10 | 大量のファイルをまとめてコピーする | 新規、既存 | 両方向 | 自作のスクリプト | S3 Batch Operations の Copy ジョブが使えた（実測 5、6）。マニフェストは自分で作る（Access Point に S3 Inventory を付けられないため） | 実測 5、6 |

用途 1 と 2 を組み合わせると、ボリュームを作業場所、S3 Glacier 系のクラスを長期の保管場所にして、ファイルを行き来させる運用ができます。ファイルの一覧と、どのファイルをどこへ移したかの記録は、利用者が持つことになります。[ファイルポータルと既存の実装](#ファイルポータルと既存の実装)の節も参照してください。

---

### S3 が正本で、ファイルとしての性能が欲しい構成

[S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) は、S3 API で集めたデータを、FlexCache を通して NFS / SMB で読ませる構成を扱います。このリポジトリの基準構成では、正本は FSx for ONTAP のボリューム（Origin）で、S3 Access Points は書き込みの入口です。正本が汎用バケットにある形は、比較の対象や、移行の出発点として出てきます。サーバー側コピーが変えるのは、正本がバケットにある形です。

下の表のユースケースと試算は、S3-Burst-on-ONTAP-Files の [architecture.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/architecture.md) と [finops-s3-vs-s3ap.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/comparison/finops-s3-vs-s3ap.md) にあるものです。試算は ap-northeast-1、2026-08-09 取得の単価による計算で、実測ではありません。「コピーで変わること」は、すべて推測です。

| ユースケース | 読む側 | オブジェクトの大きさ（試算の前提） | 正本がバケットにあるときのこれまでの取り込み | コピーで変わること（推測） |
|---|---|---|---|---|
| 自動車の AV / ADAS の HiL（Hardware-in-the-Loop）テスト。走行ログとセンサーデータをテストベンチで再生する | AWS の外に置いた物理のテストベンチ（NFS / SMB） | 約 1 MiB、月 2,000 万件 | DataSync | DataSync のタスクと中継のホストなしで、バケットから Origin へ写せる。1 件が 5 GiB に届かないので 1 回の `CopyObject` で足りる。月 2,000 万件のリクエスト料金と所要時間は試算していない |
| EDA / CAE。設計ジョブの入出力 | HPC のジョブ（NFS） | 約 256 KiB、月 6,000 万件 | DataSync | 小さなファイルが多いので、1 件 1 リクエストの料金と、Access Point のリクエストレートの上限が先に問題になりうる |
| メディア / VFX のレンダリング素材 | 制作端末、レンダリングノード（SMB / NFS） | 約 500 MiB、月 5 万件 | DataSync | 5 GiB を超える素材はマルチパートのコピー（実測 3）。50 GiB を超える素材は Access Point へ写せない |
| ゲノム解析のシーケンサー出力 | HPC クラスタ（NFS） | 約 8 MiB、月 200 万件 | DataSync | 5 GiB を超える BAM / FASTQ はマルチパートのコピー。S3 Glacier 系に退避済みのデータは、先に復元が要る |
| 車載 / IoT のテレメトリ | 解析ジョブ | 約 64 KiB、月 3 億件 | DataSync（比較対象） | 小さなファイルが多く、コピーのリクエスト料金が DataSync の転送料金を上回る可能性がある |
| AWS の外の利用者が同じデータを繰り返し読む | AWS の外のクライアント | 4 MiB、20 TiB を月 30 回 | DataSync で全量を写す案 | 全量を写す手段に、コピーが加わる。読まれた分だけを運ぶ FlexCache の性質は変わらない |
| 石油・ガス、製造の品質検査、医療画像、IoT / エッジ、リモートワーク | NFS / SMB の端末 | 試算なし | 記述なし | 判断する材料がない |

HiL テストを例に、取り込みの経路を比べます。

| 経路 | 正本 | テストベンチへの届け方 | 向いている場面 |
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
| 外部のデータ管理ツールで、ファイル単位にアーカイブする | 最終アクセス日時などで選び、元のパスから読み戻せるようにする | コピーは移動の部分だけを受け持つ。選別、元のパスからの読み戻し、メタデータの管理はコピーに含まれない | [AWS Storage Blog の製造業の事例](https://aws.amazon.com/blogs/storage/cost-optimized-file-storage-with-amazon-fsx-for-netapp-ontap-and-komprise/)、[アーカイブと階層化の順序](../../cost/notes/archiving-and-tiering-are-ordered-not-alternatives.md) |
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

単価は 2026-11-24 に Price List API で ap-northeast-1 について取得しました。下の金額は単価 × 数量の計算例で、請求額ではありません。表にない費目（Access Point のリクエスト料金、容量プールのリクエスト料金、スループット容量、復元した一時コピーの保管料金）は含みません。

| 単価（ap-northeast-1） | 値 |
|---|---|
| FSx for ONTAP Single-AZ の SSD | $0.150 / GB-月 |
| FSx for ONTAP Single-AZ の容量プール | $0.0238 / GB-月 |
| S3 Glacier Flexible Retrieval の保管 | $0.0045 / GB-月 |
| S3 Glacier Deep Archive の保管 | $0.002 / GB-月 |
| S3 Glacier Deep Archive への `CopyObject` | $0.065 / 1,000 リクエスト |
| S3 Glacier Deep Archive からの取り出し（Standard / Bulk） | $0.022 / GB、$0.005 / GB |
| S3 Glacier Deep Archive の復元リクエスト（Standard / Bulk） | $0.1142 / 1,000、$0.025 / 1,000 |

計算の前提は、10 TiB（10,240 GB）、平均 100 MiB のファイル 10 万件を容量プールから S3 Glacier Deep Archive へ移し、そのうち 1 TiB（1 万件）を 1 回戻す、というものです。

| 項目 | 計算 | 金額 |
|---|---|---|
| 容量プールに置いたままの保管 | 10,240 GB × $0.0238 | $243.71 / 月 |
| S3 Glacier Deep Archive に置いた保管 | 10,240 GB × $0.002 | $20.48 / 月 |
| 移すときのコピー | 10 万件 × $0.065 / 1,000 | $6.50（1 回） |
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

ファイルポータルにアーカイブの操作を加えるなら、どのファイルを、いつ、どのクラスへ移したかの記録と、復元にかかる時間（Standard の取り出しで最大 12 時間ほど）を利用者に示す画面が要ります。

---

### 測っていないこと

- NTFS の ACL を持つボリューム（SMB の利用者がいる環境）での、コピー先のファイルの所有者と ACL
- アカウントをまたぐコピー、FlexCache のボリュームに付けた Access Point からのコピー
- S3 Glacier Deep Archive から復元した後のボリュームへのコピー（復元を 2026-11-24 に要求し、完了待ち）
- 小さなファイルを大量にコピーしたときのリクエストレートの上限と所要時間

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
| 2 | 5 GiB を超えるファイルを `aws s3 cp` で写し、NFS で読んだ SHA-256 を比べる | マルチパートのコピーが自分の環境で通るか |
| 3 | コピー先のファイルを `stat` で読む | 所有者とモードが、アプリの期待どおりか |
| 4 | `--storage-class DEEP_ARCHIVE` でバケットへ写したファイルを、復元してから戻す | 往復の手順と所要時間 |

```bash
aws s3api copy-object \
  --bucket <destination-access-point-alias> \
  --key check/sample.bin \
  --copy-source <source-bucket>/check/sample.bin
aws s3api head-object --bucket <destination-access-point-alias> --key check/sample.bin \
  --query '[StorageClass,ServerSideEncryption,ContentLength]'
```

### 期待結果

```text
"FSX_ONTAP"
"aws:fsx"
<コピー元と同じバイト数>
```

1 つ目のコマンドは、コピー先のボリュームにファイルを 1 つ作ります。終わったら `aws s3api delete-object` で消してください。手順 4 の S3 Glacier Deep Archive は 180 日の最小保管期間があり、早く消しても残りの日数分の保管料金がかかります。

## Read next

[FSx for ONTAP S3 Access Points は S3 として使えるか](s3-access-point-constraints.md)
