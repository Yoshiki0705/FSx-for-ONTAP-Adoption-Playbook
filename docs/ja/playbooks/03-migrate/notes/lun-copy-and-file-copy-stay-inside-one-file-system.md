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

## このノートが答えないこと

- スループットと、大きな LUN・多数のファイルでの所要時間（試したのは 1 GiB の LUN と 8 MiB のファイル 1 つ）
- ファイルシステムをまたぐコピーを別の経路（REST の `copy.source.peer` など）で通せるか（クラスター間ピアに許可を設定できないことは確かめた）
- NTFS ACL と UNIX の所有者・権限が引き継がれるか（試したファイルは既定の権限のままで、差が出ない条件だった）
- AWS DataSync と SnapMirror の実測（このノートの比較は各ドキュメントの記載に基づく）

## 前提レベル

intermediate

## 結論

- LUN copy と file copy は、SVM ピアの許可項目に SnapMirror や FlexCache と並んでいますが、SnapMirror の機能ではありません。SnapMirror の関係は作らず、1 回のコピーで終わります。
- 範囲は同じファイルシステムの中です。別の SVM へコピーするには、同じファイルシステム内の SVM ピアと、そのピアでの `lun-copy` または `file-copy` の許可が要ります。別のクラスター（Google Cloud NetApp Volumes）とのピアには、`lun-copy` も `file-copy` も許可として設定できませんでした。
- 操作は ONTAP の CLI か REST API で行います。AWS の API にはなく、CloudTrail の `fsx.amazonaws.com` にも記録されません。
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
| 12 | 同じファイルシステムと Google Cloud NetApp Volumes の SVM をコピー元にして LUN copy と file copy（CLI） | LUN copy は「ピアに `lun-copy` が含まれていない」、file copy は「相手の SVM の識別子を引けない」で拒否 |
| 13 | CloudTrail の `fsx.amazonaws.com` のイベント（テストの時間帯） | AWS API の呼び出し（ボリュームの作成と削除など）だけで、LUN copy と file copy に当たるイベントはなかった |

ここから、運用で気をつける点が 3 つ出ます。

1. REST の file copy は、許可の不足を受け付け（202）の後で黙って失敗します。結果は宛先のファイルで確かめてください。理由が要るときは CLI で実行します。
2. LUN を別の SVM へコピーするときは、CLI の `lun copy start -source-vserver` を使います。REST の `copy.source` に名前か UUID を渡す形では通りませんでした。
3. LUN に file copy を使わないでください。失敗したまま再試行が残ります。LUN には LUN copy を使います。

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

LUN をファイルシステムの外へコピーする AWS のサービスは、上の表にはありません。LUN を含むボリュームを SnapMirror で複製するか、ホストから LUN の中身をファイルとして読み出してコピーします（[LUN の中身はファイルプロトコルに現れるか](../../../domains/block-storage/notes/lun-contents-do-not-reach-file-protocols.md)）。

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
| SVM ピアを作れば、別のファイルシステムへもコピーできる | 範囲は同じクラスター（同じファイルシステム）の中。クラスター間のピアには `lun-copy` も `file-copy` も許可できなかった（Google Cloud NetApp Volumes との組で確認）。ファイルシステムをまたぐなら SnapMirror か AWS DataSync |
| REST が 202 を返したので、file copy は成功した | 許可が足りないと、202 の後で何も作らずに終わった。結果は宛先で確かめる |
| file copy は LUN にも使える | `LUN unsupported` で失敗し、再試行が残った。LUN には LUN copy を使う |
| コピーは AWS の監査ログに残る | ONTAP 側の操作で、CloudTrail の `fsx.amazonaws.com` には記録されなかった |

## 参照した一次情報

すべて 2026-11-23 に閲覧しました。

- NetApp: [vserver peer create](https://docs.netapp.com/us-en/ontap-cli/vserver-peer-create.html)、[lun copy start](https://docs.netapp.com/us-en/ontap-cli/lun-copy-start.html)、[LUN のコピーの前に確認すること](https://docs.netapp.com/us-en/ontap/san-admin/copy-luns-concept.html)、[POST /storage/luns](https://docs.netapp.com/us-en/ontap-restapi/ontap/post-storage-luns.html)、[POST /storage/file/copy](https://docs.netapp.com/us-en/ontap-restapi/post-storage-file-copy.html)、[volume file clone create](https://docs.netapp.com/us-en/ontap-cli/volume-file-clone-create.html)
- AWS（FSx for ONTAP）: [ONTAP CLI と REST API の使用](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-resources-ontap-apps.html)、[ONTAP のロールとユーザー](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/roles-and-users.html)、[SnapMirror によるレプリケーション](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/scheduled-replication.html)、[バックアップのコピー](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copy-backups.html)、[DataSync による移行](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/migrate-files-to-fsx-datasync.html)
- AWS（DataSync）: [FSx for ONTAP のロケーション](https://docs.aws.amazon.com/datasync/latest/userguide/create-ontap-location.html)、[コピーされるメタデータ](https://docs.aws.amazon.com/datasync/latest/userguide/metadata-copied.html)、[タスクのスケジュール](https://docs.aws.amazon.com/datasync/latest/userguide/task-scheduling.html)、[ロケーションの組み合わせ](https://docs.aws.amazon.com/datasync/latest/userguide/working-with-locations.html)、[料金](https://aws.amazon.com/datasync/pricing/)

## 関連ドキュメント

- [移行方式の選択](../../../reference/decision-trees/migration-method.md)
- [コンソールの SnapMirror は、SVM ピアを宛先側から作らないと関係を作れない](../../../domains/data-protection/notes/console-snapmirror-needs-the-svm-peer-on-the-destination-side.md)
- [LUN の中身はファイルプロトコルに現れるか](../../../domains/block-storage/notes/lun-contents-do-not-reach-file-protocols.md)
