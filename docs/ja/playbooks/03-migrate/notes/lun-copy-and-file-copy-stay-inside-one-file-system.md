---
title: ONTAP の LUN copy と file copy は、同じファイルシステムの中で SVM をまたぐコピーで、SnapMirror の機能ではない。ファイルシステムをまたぐなら SnapMirror か AWS DataSync を選ぶ
lifecycle: [migrate, operate]
domains: [block-storage, data-utilization]
evidence: verified
verified_on: 2026-11-23
region: ap-northeast-1
ontap_version: 9.19.1P4
lang: ja
---
# SVM ピアで許可する LUN copy と file copy は、何をどこまでコピーでき、AWS DataSync とどう使い分けるか？

LUN copy と file copy は、同じファイルシステムの中で、LUN またはファイルを別のボリュームや別の SVM へコピーする ONTAP の操作です。SnapMirror の関係は作らず、ファイルシステムをまたげません。2026-11-23 に東京の第 1 世代で、どちらも中身が一致するコピーができることと、Google Cloud NetApp Volumes とのクラスター間ピアにはどちらも許可できないことを確かめました。

## このノートで学べること

- LUN copy と file copy の範囲（同じ SVM、別の SVM、別のファイルシステム）と、SVM ピアに許可するアプリケーションとの関係
- `fsxadmin` で実行できるか、REST と CLI で何が違うか、失敗がどこに表示されるか
- AWS DataSync、SnapMirror、FlexClone、バックアップのコピーとの使い分け
- 同じファイルシステムの中で、ホスト側のコピーではなく ONTAP の機能を選ぶ理由
- robocopy、rsync、NetApp XCP、Cirrus Migrate Cloud（cMotion）、AWS Transform MGN、`dd`、LVM、Oracle ASM、Storage vMotion、AWS 規範ガイダンスに載っている移行ツールとの違い

## このノートが答えないこと

- スループットと、大きな LUN・多数のファイルでの所要時間（試したのは 1 GiB の LUN と 8 MiB のファイル 1 つ）
- ファイルシステムをまたぐコピーを別の経路（REST の `copy.source.peer` など）で通せるか（クラスター間ピアに許可を設定できないことは確かめた）
- NTFS ACL と UNIX の所有者・権限が引き継がれるか（試したファイルは既定の権限のままで、差が出ない条件だった）
- AWS DataSync と SnapMirror の実測（このノートの比較は各ドキュメントの記載に基づく）
- robocopy、rsync、NetApp XCP、サードパーティの移行製品、ブロック単位のツールの動作（どれも試していない。比較は公式ページの記載に基づく。実機での確認は [Issue #427](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/427) で管理）

## 前提レベル

intermediate

## このノートの用語

このノートは、次の用語を前提にしています。初めて読む方は、先にこの表を見てください。

| 用語 | このノートでの意味 |
|---|---|
| ファイルシステム | Amazon FSx for NetApp ONTAP（以下 FSx for ONTAP）で作る 1 つの単位。中身は ONTAP の 1 つのクラスターで、`fs-` で始まる ID を持つ |
| SVM（ストレージ仮想マシン） | ファイルシステムの中に作る、論理的なファイルサーバー。ボリュームは必ずどれかの SVM に属し、1 つのファイルシステムに複数の SVM を作れる |
| ボリューム | SVM の中に作るデータの入れ物。NFS や SMB で共有するファイルと、iSCSI などで使う LUN はボリュームの中に置く |
| LUN | ボリュームの中に作るブロックデバイス。サーバーは iSCSI などで接続し、ローカルのディスクのように使う |
| Snapshot | ボリュームのある時点の状態を、読み取り専用で残したもの。作成は数秒で終わり、変わったブロックの分だけ容量を使う |
| SVM ピア | 2 つの SVM の間で、どの機能の通信を許すかを決める関係。相手の SVM ごとに、SnapMirror、FlexCache、file copy、LUN copy から許可する機能を選ぶ |
| LUN copy、file copy | ONTAP の機能。LUN またはファイルを、ストレージの中で別のボリュームへコピーする。SnapMirror とは別の機能 |
| ホスト側のコピー | サーバー（EC2 など）でコピー元とコピー先の両方をマウントまたは接続し、サーバーのコマンドやツールでデータを読み書きするコピー。robocopy、rsync、`dd` など |
| 管理エンドポイント | ONTAP の CLI や REST API を受け付ける、ファイルシステムの管理用の接続先。VPC の中からだけ到達できる |

## 結論

- LUN copy と file copy は、SVM ピアの許可項目に SnapMirror や FlexCache と並んでいますが、SnapMirror の機能ではありません。SnapMirror の関係は作らず、1 回のコピーで終わります。
- 範囲は同じファイルシステムの中です。別の SVM へコピーするには、同じファイルシステム内の SVM ピアと、そのピアでの `lun-copy` または `file-copy` の許可が要ります。別のクラスター（Google Cloud NetApp Volumes）とのピアには、`lun-copy` も `file-copy` も許可として設定できませんでした。既存のピアへの追加、REST でのピアの新規作成、コンソールでのピアの新規作成の 3 つの経路とも、ONTAP が同じエラーで拒否しました。
- 操作は ONTAP の CLI か REST API で行います。AWS の API にはなく、CloudTrail の `fsx.amazonaws.com` にも記録されません。
- 同じファイルシステムの中なら、ONTAP の機能はコピー用のサーバーなしで動き、Snapshot から一貫した時点を写せます。理由とトレードオフは [同じファイルシステム内で ONTAP の機能を選ぶ理由](#同じファイルシステム内で-ontap-の機能を選ぶ理由) にあります。
- ファイルシステムやリージョンをまたぐ場合、継続して複製する場合、ONTAP 以外のストレージとの間でコピーする場合は、SnapMirror、AWS DataSync、バックアップのコピーから選びます。

## 本文

### LUN copy と file copy の位置づけ

> **区分**: `documented`。ONTAP のコマンドリファレンスと REST API リファレンスに基づきます（2026-11-23 に閲覧）。

SVM ピアには、相手の SVM に許可するアプリケーションとして `snapmirror`、`file-copy`、`lun-copy`、`flexcache` を指定します（[vserver peer create](https://docs.netapp.com/us-en/ontap-cli/vserver-peer-create.html)）。Amazon FSx for NetApp ONTAP（以下 FSx for ONTAP）のコンソールの SVM ピアの作成画面でも、同じ 4 つを選べます（[コンソールの SnapMirror とスナップショットポリシー](../../../domains/data-protection/notes/console-snapmirror-and-snapshot-policies-use-unpublished-api-operations.md#svm-ピアで選べるアプリケーションと設計で読む資料)）。この 4 つは、ピアの相手に何を許すかの項目です。LUN copy と file copy は、SnapMirror とは別のコマンドと API で動きます。

| 項目 | LUN copy | file copy |
|---|---|---|
| CLI | `lun copy start`（`show`、`modify`、`pause`、`resume`、`cancel` がある） | `volume file copy start` |
| REST API | `POST /api/storage/luns` に `copy.source` を指定 | `POST /api/storage/file/copy`（ONTAP 9.8 から） |
| 範囲 | クラスター内のボリューム間。同じ SVM でも別の SVM でもよい | 同じクラスター内。クラスターをまたぐコピーは非対応 |
| 帯域の制限 | `-max-throughput`。コピー中も変えられる | `max_throughput` |
| コピーされないもの | LUN のマッピング。宛先でホストにマップし直す | 記載なし |
| 対象外 | ファイルから作った LUN、NVFAIL 状態の LUN など | FlexGroup、SnapMirror の同期関係にあるボリューム |

FSx for ONTAP では 1 つのファイルシステムが ONTAP の 1 クラスターに当たるので、「クラスター内」は「同じファイルシステムの中」と読み替えます。FSx for ONTAP のユーザーガイドには、LUN copy と file copy の記述は見つかりませんでした（2026-11-23、`docs.aws.amazon.com/fsx/latest/ONTAPGuide` の SVM ピア、SnapMirror、FlexCache、ONTAP CLI の各ページと Web 検索で確認）。

### 実機で確かめたこと

> **区分**: `verified`。下の「検証環境」で 1 回ずつ確かめた結果です。

| # | 操作 | 結果 |
|---|---|---|
| 1 | `fsxadmin` のロールの確認（`security login role show` に当たる REST） | ロールは `DEFAULT` を `all` とし、制限は 31 のコマンドディレクトリだけ。`lun copy`、`volume file`、`vserver peer` は制限されていなかった |
| 2 | 同じ SVM 内の LUN copy（REST の `copy.source.name`） | 21 秒で `complete`。宛先の LUN は開始直後から `online`。書き込んだ 2 か所（各 1 MiB）と書いていない 1 か所の sha256 がコピー元と一致。シリアル番号は新しい値。使用量はコピー元と同じ 2,121,728 バイト |
| 3 | SVM ピアなしで、別の SVM へ LUN copy（CLI） | 拒否。「SVM が同じクラスター内の SVM ピアの関係にない」 |
| 4 | 別の SVM へ LUN copy（REST の `copy.source.name` または `copy.source.uuid`） | ピアの有無にかかわらず拒否。コピー元を宛先の SVM の中で探し、「見つからない」と返した。`copy.source.peer` は試していない |
| 5 | `lun-copy` と `file-copy` を許可した SVM ピアを作り、別の SVM へ LUN copy（CLI の `lun copy start -source-vserver`） | 27 秒で `complete`。中身はコピー元と一致 |
| 6 | 同じ SVM 内と、別の SVM への file copy（REST）。8 MiB のファイル | どちらも成功。中身の sha256 が一致。同じ SVM 内のジョブは 1 秒以内に終わった。宛先の更新日時はコピーした時刻で、コピー元の時刻は引き継がれなかった |
| 7 | ピアの許可を `lun_copy` だけにして file copy（REST） | 202（受け付け）が返り、宛先にファイルはできなかった。ジョブの記録は数秒後に消え、EMS にも理由は残らなかった |
| 8 | 同じ条件で file copy（CLI の `volume file copy start`） | 拒否。「ピアの関係に `file-copy` が含まれていない」と理由を返した |
| 9 | ピアの許可を `file_copy` だけにして LUN copy（CLI） | 拒否。「ピアの関係に `lun-copy` が含まれていない」 |
| 10 | LUN のファイルを file copy（CLI） | 開始は 200 で受け付けられたが、宛先はできず、`Cannot quiesce source file. LUN unsupported.` で再試行を続けた。ドキュメントにも REST にも中止の手段が見つからず、コピー元の LUN を消すと一覧から消えた |
| 11 | Google Cloud NetApp Volumes とのクラスター間ピア（許可は `snapmirror` と `flexcache`）に `file_copy` か `lun_copy` を足す（REST の `PATCH /api/svm/peers`） | 202 の後、ジョブが失敗。理由は `Cannot specify "file-copy" as an intercluster application.`（`lun-copy` も同じ）。ピアの許可は元のまま |
| 12 | 同じ相手と SVM ピアを新しく作る（REST の `POST /api/svm/peers`）。アプリケーションは (a) `lun_copy` だけ、(b) `file_copy` だけ、(c) `snapmirror`・`lun_copy`・`file_copy` の 3 通り | 3 通りとも 202 の後でジョブが失敗し、ピアは作られなかった。理由は (a) が `Cannot specify "lun-copy" as an intercluster application.`、(b) と (c) が同じ文の `"file-copy"` 版 |
| 13 | コンソールの「Create SVM peer」で、相手の場所に「In another AWS account or Region or on premises」を選び、Google Cloud NetApp Volumes の SVM 名とクラスター名を入れ、アプリケーションに File copy と LUN copy だけを選んで作る | 画面は作成を受け付け、一覧に `Creating` で表示した。数十秒後に `Failed` になり、詳細画面の「Lifecycle transition message」は `Cannot specify "file-copy" as an intercluster application. (ONTAP error code: 9895996)`。ONTAP 側にピアはできなかった。失敗した SVM ピアは AWS 側に記録として残るので、コンソールの「Delete SVM peer」で削除した |
| 14 | 同じファイルシステムと Google Cloud NetApp Volumes の SVM をコピー元にして LUN copy と file copy（CLI） | LUN copy は「ピアに `lun-copy` が含まれていない」、file copy は「相手の SVM の識別子を引けない」で拒否 |
| 15 | CloudTrail の `fsx.amazonaws.com` のイベント（テストの時間帯） | AWS API の呼び出し（ボリュームの作成と削除など）だけで、LUN copy と file copy に当たるイベントはなかった |

ここから、運用で気をつける点が 4 つ出ます。

1. REST の file copy は、許可の不足を受け付け（202）の後で黙って失敗します。結果は宛先のファイルで確かめてください。理由が要るときは CLI で実行します。
2. LUN を別の SVM へコピーするときは、CLI の `lun copy start -source-vserver` を使います。REST の `copy.source` に名前か UUID を渡す形では通りませんでした。
3. LUN に file copy を使わないでください。失敗したまま再試行が残ります。LUN には LUN copy を使います。
4. コンソールは、別のクラスターを相手にする SVM ピアでも File copy と LUN copy を選ばせます。作成は ONTAP が拒否し、`Failed` の記録が AWS 側に残ります。別のファイルシステムやオンプレミスの ONTAP、他のクラウドとのピアでは、SnapMirror と FlexCache だけを選びます。

### AWS のコピー手段との違い

> **区分**: `documented`。各サービスのドキュメントに基づきます（2026-11-23 に閲覧）。LUN copy と file copy の行の「記録」は、上の実機の結果です。

| 手段 | 範囲 | 対象 | 操作する場所 | 1 回か継続か | 引き継ぐもの |
|---|---|---|---|---|---|
| LUN copy | 同じファイルシステム内（SVM をまたげる） | LUN | ONTAP の CLI・REST | 1 回 | LUN の中身。マッピングは引き継がない |
| file copy | 同じファイルシステム内（SVM をまたげる） | ファイル（LUN は不可） | ONTAP の CLI・REST | 1 回 | ファイルの中身。更新日時は引き継がなかった（1 回の観測） |
| FlexClone、`volume file clone create` | 同じファイルシステム内。ファイルのクローンは同じボリューム内 | ボリューム、ファイル、LUN | ONTAP の CLI・REST（ボリュームのクローンは FSx for ONTAP のコンソールにも画面がある） | 1 回。全量のコピーを待たない | 親とブロックを共有する |
| SnapMirror | ファイルシステム、リージョン、オンプレミスの ONTAP との間 | ボリューム | ONTAP の CLI・REST | 継続（最短 5 分間隔） | Snapshot と効率化の状態 |
| AWS DataSync | ファイルシステム、リージョン、他のストレージとの間 | NFS（v3）と SMB で見えるファイル。iSCSI は対象外 | AWS のコンソール・API | 1 回か、スケジュール（最短 1 時間） | NFS は時刻・UID/GID・POSIX 権限、SMB は所有者 SID・DACL・SACL など。プロトコルをまたぐと ACL は引き継がない |
| バックアップのコピー（`CopyBackup`、AWS Backup） | リージョン、アカウントの間 | ボリューム（FlexGroup は不可） | AWS のコンソール・API | 1 回か、AWS Backup のスケジュール | ボリューム全体。使うには新しいボリュームへ復元する |

### 使い分け

| 状況 | 向く手段 | 理由 | その手段のトレードオフ |
|---|---|---|---|
| 同じファイルシステム内で、LUN を別のボリュームや別の SVM へ複製する | LUN copy | LUN の中身だけを、ホストを経由せずにコピーできる。`-max-throughput` で帯域を絞れる | ONTAP の管理者の資格情報と、管理エンドポイントへの到達経路が要る。別の SVM へは SVM ピアと `lun-copy` の許可が要る。AWS 側の記録に残らない。ホストへのマップは別に行う |
| 同じファイルシステム内で、ファイルを別のボリュームや別の SVM へ複製する | file copy | ホストでマウントせずにコピーできる | 同じ管理面の条件が付く。REST では許可の不足が黙って失敗する。権限や ACL を引き継ぐかは確かめていない |
| 同じボリューム内で、大きなファイルやテスト用のコピーをすぐ作る | `volume file clone create`、ボリューム単位なら FlexClone | 全量のコピーを待たずに作れる | 親とブロックを共有するので、親と切り離したいときは別の手段が要る。ファイルのクローンは同じボリューム内だけ |
| 別のファイルシステムやリージョンへ、継続して複製する（DR を含む） | SnapMirror | ボリューム単位の差分複製で、最短 5 分間隔 | クラスターピアと SVM ピア、インタークラスター LIF への到達経路が要る。宛先は切り離すまで読み取り専用。SVM 単位の DR と同期型は FSx for ONTAP で使えない |
| ONTAP 以外の NAS から移行する、またはファイル単位で別のファイルシステムへコピーする | AWS DataSync | AWS の API で操作でき、スケジュール、帯域の制限、同じプロトコルでのメタデータの引き継ぎがある | 転送量（GB）あたりの料金がかかる。iSCSI の LUN は対象外。SMB は NTLM 認証が要る。オンプレミスとの間はエージェントが要る |
| 別のリージョンやアカウントに、ボリュームの複製を 1 回置く | バックアップのコピー | AWS の API で完結し、AWS Backup ならアカウントをまたげる | 使うには新しいボリュームへの復元が要る。FlexGroup は対象外 |

LUN をファイルシステムの外へコピーする AWS のサービスは、上の表にはありません。LUN を含むボリュームを SnapMirror で複製するか、次の節のブロック単位のツールを使います（LUN の中身とファイルの関係は [LUN の中身はファイルプロトコルに現れるか](../../../domains/block-storage/notes/lun-contents-do-not-reach-file-protocols.md)）。

### 同じファイルシステム内で ONTAP の機能を選ぶ理由

同じファイルシステムの中でボリュームをまたいでファイルや LUN をコピーする方法は、大きく 2 つあります。ストレージの中で動く ONTAP の機能（LUN copy、file copy）と、サーバーで動かすホスト側のコピーや AWS DataSync です。どちらでもコピーはできますが、ONTAP の機能を選ぶと次の 5 点が変わります。各項目の後ろの括弧は、根拠の種類です。

1. **コピーのためのサーバーが要らない**（実測）
   ホスト側のコピーでは、コピー元とコピー先の両方をマウントまたは接続したサーバーを用意し、データはそのサーバーを通ります。ONTAP の機能では、データはストレージの中だけを動きます。このノートの実測でも、LUN copy と file copy はサーバーを使わずに完了しました。コピー用の EC2 を立てる手間、その費用、そのサーバーのネットワーク帯域による上限がなくなります。
2. **LUN を使ったまま、ある時点の状態を写せる**（ドキュメント）
   LUN copy は、Snapshot の中の LUN をコピー元にできます（[lun copy start](https://docs.netapp.com/us-en/ontap-cli/lun-copy-start.html)）。Snapshot は数秒で作れるので、サーバーが LUN に書き込み続けていても、ある時点の一貫した状態を複製できます。ホスト側でブロックを読む `dd` のようなコピーは、書き込み中の LUN を読むと途中の状態が混ざるので、サーバーの停止か、ファイルシステムの静止が前提になります。
3. **データを書いていない領域が、コピーで実データにならなかった**（実測）
   1 GiB の LUN のうち書き込んだのは 2 MiB で、コピー元の使用量は 2,121,728 バイトでした。LUN copy の後、コピー先の使用量も同じ 2,121,728 バイトでした。ホスト側のブロックのコピーは、書いていない領域も含めて 1 GiB 全体を読み書きします。その場合にコピー先の使用量がどうなるかは、このノートでは確かめていません。
4. **コピー先を、コピーの完了を待たずに扱える**（実測）
   LUN copy のコピー先の LUN は、コピーの開始直後から `online` でした。サーバーへの割り当て（マッピング）などの準備を、コピーと並行して進められます。
5. **転送量の料金がかからず、帯域を絞れる**（ドキュメント）
   AWS DataSync は転送量（GB）あたりの料金がかかります（[DataSync の料金](https://aws.amazon.com/datasync/pricing/)）。LUN copy と file copy には、このような転送量の料金がありません。どちらもコピーの帯域の上限（`max-throughput`、`max_throughput`）を指定できます。同じファイルシステムのスループットを本番の読み書きと分け合うので、上限を付けて本番への影響を抑えます（上限を付けたときの効果は測っていない）。

ONTAP の機能にも、次のトレードオフがあります。

- ONTAP の管理者（`fsxadmin` など）の資格情報と、管理エンドポイントへの到達経路が要ります。
- 操作は ONTAP 側の記録に残り、AWS の CloudTrail には残りません。
- 1 回のコピーだけで、続けて差分を送る仕組みはありません。
- file copy は、コピー元の更新日時を引き継ぎませんでした（1 回の実測）。

次の条件では、AWS DataSync などのツールを選びます。

- 操作を AWS の API で行い、CloudTrail に記録を残したい
- ONTAP の管理者の資格情報を、コピーの作業に使いたくない
- 何度も差分を同期したい
- ディレクトリのツリーを、更新日時や ACL を含めて移したい
- FlexGroup ボリュームが絡む（file copy は FlexGroup に対応しない）

### 汎用のコピーツール・移行ツールとの違い

> **区分**: `documented`。各ツールの公式ページ（製品ドキュメント、マニュアル、AWS Marketplace の掲載ページ、AWS 規範ガイダンス）を 2026-11-23 に読んだ内容です。サードパーティ製品はどれも試していません。AWS 規範ガイダンスの各ツールのページは、パートナーが記入し AWS が検証していないものだと、ページ自身に書かれています。

ONTAP の機能（LUN copy、file copy、SnapMirror、FlexClone）は、ストレージの中でデータを動かします。ホストや専用のエージェントで動くツールは、データをクライアント経由で読んで書きます。この違いから、次の 4 点が分かれます。

1. **扱える相手**: ONTAP の機能は相手も ONTAP に限られ、LUN copy と file copy は同じファイルシステムの中に限られます。ホスト側のツールは、ONTAP 以外のストレージとの間でも使えます。
2. **引き継ぐもの**: SnapMirror は、重複排除・圧縮の状態と既存の Snapshot を引き継ぐとユーザーガイドに書かれています（[SnapMirror による移行](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/migrating-fsx-ontap-snapmirror.html)）。ホスト側のツールについては、読んだページのどれにも、ONTAP の効率化の状態や移行元の Snapshot がどうなるかの記述はありませんでした。データはクライアントを通って書き直され、宛先で効率化がかかるかは宛先のボリュームの設定次第です。
3. **稼働中の切り替え**: 稼働中のまま切り替えまで扱う仕組みを持つのは、ブロック単位のツールの一部（cMotion、LVM の `pvmove`、Oracle ASM のリバランス、Storage vMotion）です。ファイル単位のツールは、増分を繰り返したあと、最後の同期と接続先の切り替えを利用者が行います。
4. **操作の記録**: AWS DataSync と AWS Transform MGN は AWS のサービスなので、操作が AWS の API と CloudTrail に残ります。ONTAP の機能は ONTAP 側に、ホスト側のツールはホストかツールの管理画面に記録されます。

#### ファイル単位のツール

| ツール | 動く場所 | FSx for ONTAP への接続 | 稼働中のコピーと増分 | 引き継ぐもの | 主な制約 |
|---|---|---|---|---|---|
| AWS DataSync | AWS のマネージドサービス。オンプレミスとの間はエージェント（VM か EC2） | NFS v3 か SMB。iSCSI は対象外（ドキュメントに記載） | 変更分だけを転送する設定とスケジュール。書き込み中のファイルは検証で不一致になり、再実行が要る | NFS は UID/GID・権限・時刻、SMB は所有者・DACL・SACL。送り元と宛先のプロトコルをそろえる必要がある | SMB は NTLM 認証。DFS 名前空間は対象外。スケジュールは最短 1 時間。転送量（GB）あたりの料金 |
| robocopy | Windows のホストのコマンド | SMB の共有（UNC パス）への書き込み。FSx for ONTAP の名前はページになく、SMB で使えるという推論 | 再実行で変更のないファイルを飛ばす。`/mon`・`/mot` で変化を待って再実行。切り替えは手動 | 既定は `/COPY:DAT`（データ・属性・時刻）で ACL を含まない。`/COPYALL` で所有者・ACL・監査情報 | `/B`（バックアップモード）には特権が要る。ACL の扱いは [SMB 移行で ACL が落ちるのはツールのせいか](preserving-acls-during-migration.md) |
| rsync | Linux などのホストのプロセス（ssh か rsync デーモン） | NFS か SMB でマウントしたパスへの書き込み。推論 | 大きさと更新時刻で差分を選び、差分だけを送る。切り替えは手動 | `-a` は権限・時刻・所有者など。ACL（`-A`）、拡張属性（`-X`）、ハードリンク（`-H`）は別の指定。Windows の NTFS ACL は記載なし | 所有者の保持は受け側で特権が要る |
| NetApp XCP | NFS はホストかクラウドのインスタンス、SMB は Windows のホスト | NFS v3 のエクスポートと SMB の共有。FSx for ONTAP の名前はページになく、推論 | NFS は移行元を使ったままのコピーができる（使用中のファイルは飛ばして記録）。`sync` で増分、`verify` で中身を比較 | NFS の `verify` は権限と時刻も比べる。SMB の ACL の既定の扱いは確認できていない | NetApp のライセンスが要る。SMB は管理者権限と監査ログの管理権限が要る |
| Komprise Elastic Data Migration | SaaS かエージェント | AWS Marketplace の掲載ページが、移行先として FSx for ONTAP を挙げている | 1 回、定期、継続の転送と変更の追跡（規範ガイダンス） | メタデータの保持と SID の対応付けを、製品ページが挙げている | 製品の詳細な仕組みはページに記載なし |
| Vcinity の WAN 転送製品（[規範ガイダンスの掲載ページ](https://docs.aws.amazon.com/prescriptive-guidance/latest/migration-tools/data-mobility-vcinity.html)） | 両端に置くソフトウェアのアプライアンス | NFS のバックエンドを一般に扱うが、FSx for ONTAP の記載はなし | 1 回の転送だけが、規範ガイダンスで「使える」になっている | 記載なし | WAN 越しの転送と遠隔アクセスが目的。両端にインスタンスが要る |

#### ブロック単位のツール

| ツール | 動く場所 | FSx for ONTAP への接続 | 稼働中のコピーと切り替え | 主な制約 |
|---|---|---|---|---|
| Cirrus Migrate Cloud（cMotion、MigrateOps） | 移行元と宛先のホストのエージェントと、SaaS の管理画面 | iSCSI（マルチパス）。製品から FSx for ONTAP のボリューム・LUN・igroup を作って割り当てる手順が、NetApp の手順書にある | 移行元を使ったまま同期し、cMotion が I/O を宛先へ切り替える。切り替えは戻せ、戻すときは変わったブロックだけを同期し直す | 製品のアカウントとライセンス。速度はネットワークと宛先のインスタンスの帯域次第 |
| AWS Transform MGN（AWS Application Migration Service） | 移行元のエージェントと AWS のサービス。FSx for ONTAP を移行先にする場合はエージェント方式だけ | iSCSI。サーバーのデータディスクを、FSx for ONTAP のボリューム内の LUN（ディスクごとに 1 つ）として置く。ブートボリュームは EBS（[MGN のユーザーガイド](https://docs.aws.amazon.com/mgn/latest/ug/fsx-ontap.html)） | ディスクをブロック単位で継続複製し、テスト用インスタンスで確かめてから切り替える | 移行元のサーバー 1 台につき FSx for ONTAP のボリュームは 1 つ。ONTAP の設定は移さない。サーバー単位の移行で、LUN だけを選んで移す道具ではない |
| `dd`（GNU coreutils） | ホストのコマンド | iSCSI か NVMe/TCP の LUN をブロックデバイスとして使えば書ける。推論 | 増分も切り替えの仕組みもない。範囲を指定したコピーはできる | 書き込み先を切り詰めないには `conv=notrunc` が要る。稼働中のデータの整合は取らない |
| LVM の `pvmove` | Linux のホスト（device-mapper） | FSx for ONTAP の LUN を物理ボリュームとして足せば、そこへエクステントを移せる。推論 | 一時的なミラーで区間ごとに同期し、同期した区間から切り替える。中断しても続きから再開できる | 移行元のディスクが LVM で管理されていること。マニュアルは、移動中にファイルシステムをマウントしたままでよいとは明記していない |
| Oracle ASM のディスクの追加・削除とリバランス | Oracle ASM のインスタンス | FSx for ONTAP の LUN を ASM のディスクとして足せば、そこへデータを移せる。推論 | データベースを止めずにディスクを足し、古いディスクを外すとデータが残りのディスクへ移る | ASM のディスクグループの中のデータだけが対象。読んだのは Oracle Database 18 の管理者ガイド |
| VMware Storage vMotion | vCenter とハイパーバイザー | 読んだページに記載なし。FSx for ONTAP を VMware のデータストアにする経路は [Amazon EVS との統合](../../../reference/recent-updates.md#amazon-evs-が-fsx-for-ontap-と統合2025-06-告知) にある | 仮想マシンを動かしたまま、仮想ディスクを別のデータストアへ移す。切り替えには時間の上限（既定 100 秒） | 共有ディスクを持つ仮想マシンは停止して移す。主な資料は Broadcom のナレッジベースで、vSphere の管理ガイドは読めなかった |

#### ストレージのコピーとは別の層のツール

AWS 規範ガイダンスの[アプリケーションモビリティ](https://docs.aws.amazon.com/prescriptive-guidance/latest/migration-tools/app-mobility.html)と[データモビリティ](https://docs.aws.amazon.com/prescriptive-guidance/latest/migration-tools/data-mobility.html)に載っている残りのツールは、ストレージの中身をコピーする道具ではありません。各ツールのページと、製品ページか AWS Marketplace のページを読んだ範囲で、FSx for ONTAP を移行先として挙げたものはありませんでした。

| ツール | 主に移すもの | FSx for ONTAP との関係 |
|---|---|---|
| CloudHedge OmniDeq | アプリケーションの評価と、コードやコンテナへの変換 | 移行先は EC2、Lambda、ECS、EKS。ストレージは別に決める |
| Concierto.cloud | アプリケーションとサーバーの移行と変換 | 同上 |
| Deloitte ATAsphere | サーバーとアプリケーションの移行（サービスとして提供） | 移行先は EC2、ECS、EKS。製品ページは読めなかった |
| Matilda Cloud | アプリケーションとサーバーの評価と移行 | 製品のブログが、評価とサイジングの段階で FSx for ONTAP の構成に対応づけると書いている。データのコピーの経路ではない |
| RiverMeadow | 仮想マシンやサーバー単位のワークロード | 移行先は EC2、Amazon EVS、VMware Cloud on AWS など。FSx for ONTAP の記載なし |
| Stromasys Charon | SPARC などの古い計算機のエミュレーション | 計算機を EC2 上で再現する道具で、コピーの道具ではない |
| Cirata Data Migrator | Hadoop の HDFS のデータと Hive のメタデータ | データレイクの移行用。NAS のコピーの道具ではない |
| Tessell DBaaS | データベース（RMAN と Data Guard による移行） | 自前のストレージを持つデータベースのサービス |

#### 公開されている実施記録

各ツールを FSx for ONTAP と組み合わせて使った公開記事です。2026-11-23 に開いて、本文に FSx for ONTAP が出てくることを確かめたものだけを載せています。「手順あり」は手順・画面・結果を含むもの、「概要」は構成や事例の紹介です。記事の数値は各記事の環境のもので、このリポジトリでは再現していません。

| ツール | 記事 | 発行元・日付 | 内容 | 種類 |
|---|---|---|---|---|
| AWS DataSync | [Migrating file shares to Amazon FSx for NetApp ONTAP using AWS DataSync](https://aws.amazon.com/blogs/storage/migrating-file-shares-to-amazon-fsx-for-netapp-ontap-using-aws-datasync/)（[日本語訳](https://aws.amazon.com/jp/blogs/news/migrating-file-shares-to-amazon-fsx-for-netapp-ontap-using-aws-datasync/)） | AWS Storage Blog | 階層化ポリシーと DataSync の移行の関係。スループット容量 512 MB/s、約 1.1 TiB で 2 回の転送の平均を示す | 手順あり |
| AWS DataSync | [AWS DataSync が Amazon FSx for NetApp ONTAP をサポートしました](https://dev.classmethod.jp/articles/aws-datasync-copy-data-amazon-fsx-netapp-ontap/) | DevelopersIO（クラスメソッド） | SMB の共有と S3 バケットの間を、エージェントなしでコピーする手順。Snapshot はコピーされないとまとめている | 手順あり |
| AWS DataSync | [Amazon FSx for NetApp ONTAP のデータを AWS DataSync で Amazon S3 に移行する](https://zenn.dev/kameoncloud/articles/63a05e2fc9db4c) | Zenn、2025-03-14 更新 | FSx for ONTAP を移行元にして、NFS のデータを S3 へ移す手順 | 手順あり |
| robocopy、rsync、NetApp XCP | [Migrating on-premises file shares to Amazon FSx for NetApp ONTAP](https://aws.amazon.com/blogs/storage/migrating-on-premises-file-shares-to-amazon-fsx-for-netapp-ontap/) | AWS Storage Blog | ホスト側のツールと SnapMirror などの比較表。手順は SnapMirror だけ | 概要 |
| robocopy、rsync | [Preserve FlexClone space efficiency when migrating to Amazon FSx for NetApp ONTAP](https://aws.amazon.com/blogs/storage/preserve-flexclone-space-efficiency-when-migrating-to-amazon-fsx-for-netapp-ontap/) | AWS Storage Blog | ファイル単位のコピーでは FlexClone の共有ブロックが全量のコピーになることを示し、SnapMirror で保つ手順 | 手順あり（SnapMirror） |
| Komprise | [Cost-optimized file storage with Amazon FSx for NetApp ONTAP and Komprise](https://aws.amazon.com/blogs/storage/cost-optimized-file-storage-with-amazon-fsx-for-netapp-ontap-and-komprise/) | AWS Storage Blog | 製造業の約 3 PB の移行事例（企業名は非公開） | 概要 |
| Cirrus Migrate Cloud | [Migrate VMs to Amazon EC2 using Amazon FSx for ONTAP](https://docs.netapp.com/us-en/netapp-solutions/vmware/migrate-vms-to-ec2-fsxn-deploy.html) | NetApp のドキュメント | MigrateOps で FSx for ONTAP のボリューム・LUN・igroup を作り、iSCSI で SQL Server の仮想マシンを移す手順 | 手順あり |
| Cirrus Migrate Cloud | [VMware 環境から FSx for ONTAP と Amazon EC2 への移行](https://aws.amazon.com/blogs/storage/seamless-migration-from-any-vmware-environment-to-amazon-fsx-for-netapp-ontap-and-amazon-ec2/) | AWS Storage Blog | MigrateOps による VMware の仮想マシンとブロックストレージの移行の構成と、デモ動画 | 概要 |
| AWS Transform MGN | [FSx for ONTAP configuration](https://docs.aws.amazon.com/mgn/latest/ug/fsx-ontap.html) | AWS のドキュメント | FSx for ONTAP を移行先のストレージにする設定と制約 | 手順あり |
| AWS Transform MGN | [Migrate VMware Storage to Amazon FSx for NetApp ONTAP using AWS Transform](https://aws.amazon.com/blogs/storage/migrate-vmware-storage-to-amazon-fsx-for-netapp-ontap-using-aws-transform/) | AWS Storage Blog | 仮想マシンのエージェントから FSx for ONTAP の iSCSI ボリュームへの複製、テスト、切り戻し、切り替え | 概要 |
| AWS Transform MGN | [AWS Transform の FSx for ONTAP サポート GA 検証レポート](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP/blob/main/docs/ja/atx-fsxn-ga-verification.md) | このプロジェクトの VMware 移行のリポジトリ、2026-09-04 実測 | ap-northeast-1 で、移行先に `FSX_ONTAP` を設定し、複製からテスト起動、切り替え、データの整合の確認まで行った記録 | 手順あり |
| Storage vMotion | [Migration from VMware Cloud on AWS to Amazon EVS with FSx for ONTAP](https://repost.aws/articles/ARo3N3YBmQR0WcL1SOya6GfQ/migration-from-vmware-cloud-on-aws-to-amazon-evs-with-fsx-for-ontap) | AWS re:Post | 仮想マシンを FSx for ONTAP の NFS データストアへ Storage vMotion で移し、SnapMirror で Amazon EVS 側へ渡す流れ | 手順あり（文章のみ） |

次のツールは、FSx for ONTAP と組み合わせた公開記事を見つけられませんでした（2026-11-23、Web 検索。ツール名と「FSx for NetApp ONTAP」または「FSx for ONTAP」の組み合わせ、日本語の検索も含む）。見つからなかったことは、使えないことを意味しません。

- Vcinity、`dd`、LVM の `pvmove`（オンプレミスの ONTAP への移行の記事はある）、Oracle ASM のディスクの入れ替え、Concierto.cloud、Deloitte ATAsphere、RiverMeadow、Stromasys Charon、Cirata Data Migrator
- CloudHedge、Matilda Cloud、Tessell は FSx for ONTAP を扱う記事があるが、評価・サイジングか、データベースの保存先としての利用で、データのコピーの記録ではない

#### 状況ごとの選び方

| 状況 | 向く手段 | その手段のトレードオフ |
|---|---|---|
| ONTAP（オンプレミス、他のクラウド、別の FSx for ONTAP）から FSx for ONTAP へ移す | SnapMirror | 相手も ONTAP であることと、クラスターピア・SVM ピアの設定が要る。ボリューム単位 |
| Windows のファイルサーバーから SMB で移し、ACL を保つ | AWS DataSync（SMB）、robocopy `/COPYALL`、NetApp XCP（SMB） | どれも最後の同期と切り替えは手作業。ACL を読む権限と特権の準備が要る |
| Linux の NAS から NFS で移す | AWS DataSync（NFS v3）、rsync、NetApp XCP（NFS） | ACL や拡張属性は既定では引き継がないツールがある。XCP はライセンスが要る |
| 複数の NAS 製品から、まとめて移す | AWS DataSync、Komprise Elastic Data Migration | DataSync は転送量の料金。Komprise は製品のライセンス |
| SAN の LUN を、アプリケーションを止めずに FSx for ONTAP の iSCSI LUN へ移す | Cirrus Migrate Cloud（cMotion）。ホストが LVM か Oracle ASM を使っていれば `pvmove` かリバランス | Cirrus は製品のアカウントとライセンス。LVM と ASM は、ホストのボリューム管理がその仕組みであることが前提 |
| LUN を止めて 1 回だけ写す | ホストの `dd` | 増分も整合の確保もないので、停止中に行う |
| 同じ FSx for ONTAP の中で、LUN やファイルを別の SVM へ写す | LUN copy、file copy（このノート） | ONTAP の管理者の資格情報と管理エンドポイントへの経路が要る |
| サーバーごと EC2 へ移し、データディスクを FSx for ONTAP に置く | AWS Transform MGN（移行先のストレージに FSx for ONTAP を指定） | エージェント方式だけ。ブートボリュームは EBS に残る。移行元のサーバー単位で、ONTAP の設定は移らない |
| VMware のまま仮想マシンのディスクを移す | Storage vMotion | 移行先のデータストアに FSx for ONTAP を使えるかは、VMware の環境側の対応による |

## 検証環境

| 項目 | 値 |
|---|---|
| ONTAP バージョン | 9.19.1P4 |
| リージョン | ap-northeast-1 |
| 構成 | 第 1 世代 `SINGLE_AZ_1`、1 HA ペア、128 MBps、SSD 1,024 GiB。既存の 2 つの SVM（NFS と iSCSI が有効、片方は AD 参加）。クラスター間の確認には、Google Cloud NetApp Volumes の SVM との既存の SVM ピアを使った（変更は拒否され、設定は変わっていない） |
| テスト用の資源 | 4 GiB のボリューム 3 つ（UNIX セキュリティスタイル、Snapshot ポリシーなし、階層化なし）を AWS API で作成。1 GiB の LUN（中身は REST の LUN データ API で 1 MiB のランダムなデータを 2 か所に書いた）、8 MiB のファイル（REST のファイル API で書いた）。一時的な SVM ピア（`lun_copy` と `file_copy` だけを許可） |
| 操作の経路 | 管理エンドポイントへ Session Manager のポートフォワードで到達し、`fsxadmin` で ONTAP REST API を呼んだ。CLI は REST の CLI パススルー（`/api/private/cli`）で実行した |
| 検証日 | 2026-11-23（日本時間） |
| 後始末 | LUN、SVM ピア、ボリュームを削除し、ONTAP と AWS API の両方で残っていないことを確認 |

> **注意**: 上記はこの環境での 1 回ずつの実測で、一般的なサービス上限や本番環境での再現を保証するものではありません。所要時間はコピーの準備を含み、スループットの測定ではありません。

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `security login role show -role fsxadmin -access !all` で、`lun copy` と `volume file` が制限されていないか見る | 管理者のロールで実行できるか |
| 2 | 使い捨てのボリュームを 2 つ作り、`lun copy start` で同じ SVM 内のコピーを実行し、`lun copy show` で `Complete` まで見る | LUN copy が動くか |
| 3 | 別の SVM へコピーする前に `vserver peer show -fields applications` を見る。`lun-copy` か `file-copy` がなければ、許可を足すか、テスト用のピアを作る | 別の SVM へのコピーの前提 |
| 4 | file copy は CLI の `volume file copy start` で実行し、宛先のファイルの有無で結果を判定する | 失敗の理由がその場で返るか |
| 5 | テストの時間帯の CloudTrail で `fsx.amazonaws.com` のイベント名を数える | AWS 側の記録に何が残るか |

手順 2 以降はリソースを作ります。使い捨てのボリュームで行い、終わったら削除してください。適用手順の全体像は [本番に取り入れる前の確認](../../../evidence-policy.md#本番に取り入れる前の確認) を参照してください。

## よくある誤解

| 誤解 | 実際 |
|---|---|
| LUN copy と file copy は SnapMirror の一部である | SVM ピアの許可項目に並んでいるだけで、別のコマンドと API で動く。SnapMirror の関係は作らない |
| SVM ピアを作れば、別のファイルシステムへもコピーできる | 範囲は同じクラスター（同じファイルシステム）の中。クラスター間のピアには、既存のピアへの追加でも新規作成（REST、コンソール）でも、`lun-copy` と `file-copy` を許可できなかった（Google Cloud NetApp Volumes との組で確認）。ファイルシステムをまたぐなら SnapMirror か AWS DataSync |
| コンソールのピア作成画面で File copy と LUN copy を選べるので、別のクラスターとのピアにも使える | 画面は選ばせて作成を受け付けるが、ONTAP が拒否して `Failed` になる。選べるのは同じファイルシステム内のピアに限って意味がある |
| REST が 202 を返したので、file copy は成功した | 許可が足りないと、202 の後で何も作らずに終わった。結果は宛先で確かめる |
| file copy は LUN にも使える | `LUN unsupported` で失敗し、再試行が残った。LUN には LUN copy を使う |
| コピーは AWS の監査ログに残る | ONTAP 側の操作で、CloudTrail の `fsx.amazonaws.com` には記録されなかった |

## 参照した一次情報

すべて 2026-11-23 に閲覧しました。

- NetApp: [vserver peer create](https://docs.netapp.com/us-en/ontap-cli/vserver-peer-create.html)、[lun copy start](https://docs.netapp.com/us-en/ontap-cli/lun-copy-start.html)、[LUN のコピーの前に確認すること](https://docs.netapp.com/us-en/ontap/san-admin/copy-luns-concept.html)、[POST /storage/luns](https://docs.netapp.com/us-en/ontap-restapi/ontap/post-storage-luns.html)、[POST /storage/file/copy](https://docs.netapp.com/us-en/ontap-restapi/post-storage-file-copy.html)、[volume file clone create](https://docs.netapp.com/us-en/ontap-cli/volume-file-clone-create.html)
- AWS（FSx for ONTAP）: [ONTAP CLI と REST API の使用](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-resources-ontap-apps.html)、[ONTAP のロールとユーザー](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/roles-and-users.html)、[SnapMirror によるレプリケーション](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/scheduled-replication.html)、[バックアップのコピー](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copy-backups.html)、[DataSync による移行](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/migrate-files-to-fsx-datasync.html)
- 汎用のツール: [robocopy](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy)、[rsync(1)](https://download.samba.org/pub/rsync/rsync.1)、[NetApp XCP: NFS の移行](https://docs.netapp.com/us-en/xcp/xcp-migrate-data.html)、[NetApp XCP: SMB の移行](https://docs.netapp.com/us-en/xcp/xcp-migrate-smb-data.html)、[GNU dd](https://www.gnu.org/software/coreutils/manual/html_node/dd-invocation.html)、[pvmove(8)](https://man7.org/linux/man-pages/man8/pvmove.8.html)、[Oracle ASM: ディスクグループの変更（Oracle Database 18）](https://docs.oracle.com/en/database/oracle/oracle-database/18/ostmg/alter-diskgroups.html)、[Broadcom KB 387001: Storage vMotion](https://knowledge.broadcom.com/external/article/387001/how-to-migrate-storage-vmotion-datastore.html)
- 移行製品: [AWS Marketplace: Cirrus Migrate Cloud](https://aws.amazon.com/marketplace/pp/prodview-stsxln5eru5wo)、[NetApp: Cirrus Data を使った FSx for ONTAP への移行手順](https://docs.netapp.com/us-en/netapp-solutions/vmware/migrate-vms-to-ec2-fsxn-deploy.html)、[AWS Application Migration Service](https://docs.aws.amazon.com/mgn/latest/ug/what-is-mgn.html)、[AWS Marketplace: Komprise](https://aws.amazon.com/marketplace/pp/prodview-gre4qozwl6vqi)、AWS 規範ガイダンスの[アプリケーションモビリティ](https://docs.aws.amazon.com/prescriptive-guidance/latest/migration-tools/app-mobility.html)と[データモビリティ](https://docs.aws.amazon.com/prescriptive-guidance/latest/migration-tools/data-mobility.html)の各ツールのページ
- AWS（DataSync）: [FSx for ONTAP のロケーション](https://docs.aws.amazon.com/datasync/latest/userguide/create-ontap-location.html)、[コピーされるメタデータ](https://docs.aws.amazon.com/datasync/latest/userguide/metadata-copied.html)、[タスクのスケジュール](https://docs.aws.amazon.com/datasync/latest/userguide/task-scheduling.html)、[ロケーションの組み合わせ](https://docs.aws.amazon.com/datasync/latest/userguide/working-with-locations.html)、[料金](https://aws.amazon.com/datasync/pricing/)

## 関連ドキュメント

- [移行方式の選択](../../../reference/decision-trees/migration-method.md)
- [コンソールの SnapMirror は、SVM ピアを宛先側から作らないと関係を作れない](../../../domains/data-protection/notes/console-snapmirror-needs-the-svm-peer-on-the-destination-side.md)
- [LUN の中身はファイルプロトコルに現れるか](../../../domains/block-storage/notes/lun-contents-do-not-reach-file-protocols.md)
