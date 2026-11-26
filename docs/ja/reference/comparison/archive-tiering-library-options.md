---
title: FSx for ONTAP のファイルをアーカイブ用のクラスへ移す 8 種類の仕組みの比較 — バックアップ製品との組み合わせを含む
lifecycle: [design, operate, optimize]
domains: [data-utilization, cost, data-protection]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html
lang: ja
---

# FSx for ONTAP のファイルをアーカイブ用のクラスへ移す 8 種類の仕組みの比較

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md) | [比較マトリクス](README.md)

---

この資料は、Amazon FSx for NetApp ONTAP（以下 FSx for ONTAP）のボリュームにある、めったに読まれないファイルを、Amazon S3 の S3 Glacier 系のクラスへ移して保管料金を下げたい人に向けたものです。この資料は、移す仕組みを 8 種類に分けて比べます。ボリュームの階層化、ストレージ内蔵の階層化とスタブ（元の場所に残す小さな参照）、ファイルを被せるデータ管理ソフト、オブジェクトを正本にするファイル基盤、転送サービス、OSS のツールと層、デジタル保存システム、S3 API だけで照合と削除を行う仕組みです。それぞれが何を担い、何を担わないかを、各社の公開ページで並べます。アーカイブ用のバケットを守るバックアップ製品（Clumio など）は、別の表で比べ、組み合わせ方も書きます。

この資料で使う語は次のとおりです。

- 移す: コピー先にファイルを写し、元のボリュームからファイルを消すこと。コピーだけで元を残す操作は「写す」と書きます
- S3 Access Points: FSx for ONTAP のボリュームに付ける、S3 API の入口です。ファイルをオブジェクトとして読み書きでき、同じリージョンの汎用バケットとの間でサーバー側コピー（`CopyObject`）ができます
- 階層化: ボリュームの中で、読まれていないデータのブロックを SSD から容量プール（使った量だけ課金される低価格の保管領域）へ移す FSx for ONTAP の機能です。ファイルはそのまま見えます
- スタブ: 元のファイルの代わりに置く小さな参照（シンボリックリンク、独自形式のファイル）で、読まれたときに本体を呼び戻すためのものです
- 照合: コピー先の中身が元と同じかを、大きさとハッシュ（SHA-256 など）で確かめることです
- 台帳: どのファイルを、いつ、どこへ移したかと、属性とハッシュを記録したものです。戻すときの索引になります
- S3 Glacier 系のクラス: S3 Glacier Instant Retrieval（すぐに読める）、S3 Glacier Flexible Retrieval と S3 Glacier Deep Archive（読む前にバケットで復元が要る）の 3 つです。この資料で「復元が要る 2 クラス」と書くときは、後の 2 つを指します

この資料が比べる「S3 API だけで照合と削除を行う仕組み」は、このリポジトリで設計を始めたもので、まだ実装していません。その欄は、公開ページの記載ではなく設計上の意図です。中身は「[S3 API だけの照合と削除の仕組み](#s3-api-だけの照合と削除の仕組み)」の節にあります。

## 結論

- **ファイルを利用者から見えたままにしたいなら、ボリュームの階層化で足ります。** 容量プールの保管料金は、東京リージョンの Single-AZ で $0.0238 / GB-月で、S3 Standard の $0.025 / GB-月と同じくらいです（2026-11-24 取得）。Multi-AZ は $0.0476 / GB-月で、約 1.9 倍です。容量プールには読み取りと書き込みのリクエスト料金も別にかかります。S3 Glacier 系のクラスほどは下がりませんが、復元を待つ時間も、照合と削除の運用も要りません（[容量プールに置いたままにするか、バケットへ移すかの判断](../../domains/data-utilization/notes/s3-access-points-server-side-copy-use-cases.md#容量プールに置いたままにするかバケットへ移すかの判断)）
- **復元が要る 2 クラスへ移したいなら、今回読んだ範囲に、写して元を消すところまで行えると書いた製品はありませんでした。** 対象は FSx for ONTAP のボリュームのファイルです。階層化とスタブ型の製品の多くは、S3 Glacier Instant Retrieval までを対象にしています。復元が要る 2 クラスについては、Dell PowerScale CloudPools、ONTAP の FabricPool、Nasuni が対象外と書いています。Hammerspace、Panzura、CTERA は、読んだページに記載がありませんでした。写すだけなら、AWS DataSync が全クラスへ書けます。DataSync に元を消す機能の記載は、読んだページにありませんでした
- **S3 API だけの照合と削除の仕組みは、設計では次の 3 つを加えます（未実装で、設計上の意図です）。** ボリュームをマウントしない（S3 Access Points だけを使う）こと、復元が要る 2 クラスへ `CopyObject` で直接写すこと、照合で一致したファイルだけを、人の承認の後に消すことです。このうち、`CopyObject` で復元が要る 2 クラスへ写せることは実測しました。照合と削除と承認の流れは測っていません。代わりに、スタブも透過な呼び戻しもなく、移したファイルは利用者のフォルダーから消えます
- **アーカイブ用のバケットを守るバックアップ製品は、復元が要る 2 クラスのオブジェクトを対象外にしています。** AWS Backup、Clumio、Commvault、Veeam が公開ページで対象外と書き、Druva は Flexible Retrieval を読み飛ばすと書いています。S3 のレプリケーションも、この 2 クラスのオブジェクトを複製しません。そのため、復元が要る 2 クラスに置くなら、2 つ目の写しを移す時点で作ります（経路 C、手順は確かめていません）。バックアップ製品で守るなら、アーカイブ用のクラスを S3 Glacier Instant Retrieval にします（経路 B）。移す前のボリュームのバックアップ（経路 A）は、どちらにも組み合わせられます

> **区分** — `documented`。各社の公開ページ（2026-11-26 に閲覧）の記述をまとめたもので、どの製品も、この資料のために動かしてはいません。「記載を見つけられなかった」は、読んだページにその記述がないという意味で、機能がないという意味ではありません。読めなかったページは「[比較時点](#比較時点)」の節に数を書きました。
>
> **法令や規制への適合の判断ではありません。** 保持期間や不変性は、システム設計上の考慮として書いています。

## 比較

### 仕組みの種類ごとの役割

行は仕組みの種類で、製品名は例です。列の意味は次のとおりです。

- 被せる相手: その仕組みがファイルを読み書きするときの入口（マウントするプロトコルや API）です
- 元のファイル: 移した後に元の場所に何が残るかです
- 消す前の照合: 元を消す前に、コピー先の中身が元と同じかを確かめる段階を、その仕組みが持つかです
- FabricPool: ONTAP の機能で、読まれていないブロックをオブジェクトストアへ移します

| 種類 | 例 | 被せる相手 | 元のファイル | 復元が要る 2 クラスへの書き込み | 消す前の照合 | 台帳 |
|---|---|---|---|---|---|---|
| ボリュームの階層化 | FSx for ONTAP の容量プール（ONTAP の FabricPool） | ボリュームの内部 | そのまま見える（ブロックだけが移る） | 該当しない（容量プールは AWS が管理する保管領域。利用者が階層先のバケットやクラスを選ぶ方法は、読んだユーザーガイドに記載なし） | 該当しない（消さない） | 不要 |
| ストレージ内蔵の階層化とスタブ | Dell PowerScale CloudPools、IBM Storage Scale、Quantum StorNext、Versity ScoutAM | 自社のファイルシステム | スタブ、またはデータブロックの解放 | CloudPools は S3 Glacier 系を非対応と記載。読んだ範囲で、復元が要る 2 クラスへ書くと書いた製品はない | 必須と書いた製品はない。StorNext は書き込み後に読み戻して検証しないと記載 | 製品の内部 |
| ディレクトリを S3 へ写す機能 | Qumulo（Shift-To） | 自社のファイルシステム | 元は残る。スタブにしない | 書き込み先は S3 Standard のみ。Glacier 系を含むバケットではジョブが失敗すると記載 | 記載なし | 記載なし |
| ファイルを被せるデータ管理ソフト | Komprise、Starfish、Hammerspace、Datadobi、Data Dynamics StorageX | NFS、SMB のマウント、S3 API | Komprise は動的リンク（シンボリックリンク）、Hammerspace は自動で呼び戻す、Starfish はマニフェストを残せる | Hammerspace は S3 Glacier Instant Retrieval まで。Komprise は Glacier 系を一覧に挙げるが、直接書くとは書いていない | Starfish は「早すぎる削除を防ぐ制御」とだけ記載。必須と書いた製品はない | Komprise の Global Metadatabase、Starfish のカタログ |
| オブジェクトを正本にするファイル基盤 | Nasuni、CTERA、Panzura | エッジのキャッシュ（SMB、NFS） | 正本は最初からオブジェクトストア | Panzura と CTERA は S3 Glacier Instant Retrieval までを対象にしている。Nasuni は Instant Retrieval をライフサイクル経由でのみ置き、直接は書けない。復元が要る 2 クラスは、Nasuni が対象外と記載し、Panzura は記載なし、CTERA は対象クラスの一覧にない | 該当しない | 製品の内部 |
| 転送サービス | AWS DataSync | NFS、SMB（FSx for ONTAP は場所の種類として記載あり） | そのまま（元を消す機能は、読んだページに記載なし） | 全クラスへ書ける | 転送中のチェックサムと、終了時の検証モードがある | なし |
| OSS のツールと層 | rclone、Mountpoint for Amazon S3、iRODS、Lustre HSM | S3 API、POSIX | rclone の `move` は元を消す。iRODS は次の階層へ複製し、大きさかチェックサムで検証してから元を消す（検証の水準は設定で選び、既定はカタログへの登録確認だけ） | rclone、Mountpoint はクラスを指定して書ける | rclone は MD5 で照合するが、FSx for ONTAP の S3 Access Points では MD5 が取れない（下の注記） | iRODS のカタログ |
| デジタル保存システム | Archivematica、Preservica、Ex Libris Rosetta | 取り込み（保管形式のパッケージを作る） | 保管形式へ取り込む設計で、容量を空ける目的ではない | Preservica は S3 と Glacier のストレージアダプタを持つ。Archivematica と Rosetta は、Glacier 系への書き込みの記載を見つけられなかった | 保存前と定期のチェックサム検証。Archivematica は削除を「要求」と「管理者の承認」の 2 段階にしている | 保存システムのカタログ |
| S3 API だけの照合と削除の仕組み（設計中。実装なし。この行は設計上の意図） | このリポジトリで設計中 | S3 Access Points | 消える設計（スタブなし） | `CopyObject` で直接書く設計。`CopyObject` で書けることは実測（ap-northeast-1、第 1 世代 `SINGLE_AZ_1`、ONTAP 9.19.1P4、2026-11-24、各 1 回） | 設計では、一致したファイルだけを、人の承認の後に消す。この流れは測っていない | 自前で持つ設計（DynamoDB を想定） |

> **注記**: FSx for ONTAP の S3 Access Points では、ETag は MD5 ではありません。アップロード時に指定したチェックサムは受け付ける前に検証されますが、その値はボリュームに保存されず、応答にも返りません（[サポートする API の一覧](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)）。このため、MD5 を比べる道具（rclone の `check` など）は、ボリューム側のハッシュを得られません。rclone で実際にそうなった記録は、[FSx-for-ONTAP-S3AccessPoints-Client-Access-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Client-Access-Patterns) にあります（2026-11-24、rclone 1.76.0）。

### FSx for ONTAP との組み合わせの記載

各社の公開ページに、FSx for ONTAP（または ONTAP）をどう使うかの記載があるかです。

| 製品 | 記載の内容 |
|---|---|
| Komprise | FSx for ONTAP を、NFS と SMB でマウントして使う構成として記載（[AWS のブログ](https://aws.amazon.com/blogs/storage/cost-optimized-file-storage-with-amazon-fsx-for-netapp-ontap-and-komprise/)） |
| Datadobi | FSx for ONTAP を、移行先として記載 |
| AWS DataSync | FSx for ONTAP を、NFS v3 または SMB の場所として記載（[場所の作成](https://docs.aws.amazon.com/datasync/latest/userguide/create-ontap-location.html)） |
| Commvault | FSx for ONTAP の SMB 共有と NFS エクスポートのバックアップを記載（[Commvault のドキュメント](https://documentation.commvault.com/11.46/software/amazon_fsx_for_netapp_ontap.html)） |
| AWS Backup | FSx for ONTAP のボリューム単位のバックアップと、別リージョン・別アカウントへのコピーを記載 |
| Hammerspace | ONTAP を NFSv3 で取り込む記載。FSx for ONTAP の名前はない |
| 上記以外（今回調べた製品とサービスのうち、この資料の表に載せたもの） | FSx for ONTAP の記載を見つけられなかった |

**FSx for ONTAP の S3 Access Points を、移す元か移す先として書いた製品は、今回読んだページに 1 つもありませんでした。** OSS では、rclone と Mountpoint for Amazon S3 が S3 Access Points で動いた記録が、上の Client-Access-Patterns のリポジトリにあります。ボリュームからバケットへ写す向きの記録はありません。

### アーカイブ用のバケットを守る製品の扱い

条件: FSx for ONTAP から移したファイルが、汎用バケットに S3 Glacier 系のクラスのオブジェクトとして入っている場合に、その製品がバケットを守れるか。

| 製品 | S3 Glacier Instant Retrieval | 復元が要る 2 クラス | S3 のバージョニング |
|---|---|---|---|
| AWS Backup | 対象。バックアップのたびに取得料金がかかると記載 | 対象外と記載 | 必須 |
| Clumio（Commvault の傘下、製品名 Clumio CloudRecover） | 公式サイトの FAQ は対象と記載。ドキュメントの Get started は「Glacier と Glacier Deep Archive は非対応」と記載し、2 つの記載が食い違う | 対象外と記載 | バケット内の巻き戻し（Backtrack）だけが必須 |
| Commvault Cloud | 記載なし | 失敗する項目として記載 | オブジェクトの過去の版はバックアップしない |
| Veeam | 記載なし | 対象外と記載 | 版の履歴は対象外 |
| Rubrik | 対象。既定では除外 | 対象クラスの一覧にない | 記載なし |
| Druva | 対応クラスは Standard と Intelligent-Tiering と記載。Instant Retrieval の記載なし | S3 Glacier Flexible Retrieval（`GLACIER`）のオブジェクトは読み飛ばしてエラーを記録すると記載。Deep Archive の記載は読んだページにない | 記載なし |
| S3 のレプリケーション（参考） | — | 複製しない。復元して別のクラスへコピーしてから複製すると記載 | 必須 |

出典: [AWS Backup の S3 バックアップ](https://docs.aws.amazon.com/aws-backup/latest/devguide/s3-backups.html)、[Clumio の S3 バックアップ](https://documentation.commvault.com/clumio/s3_backups.html)、[Clumio の始め方](https://documentation.commvault.com/clumio/get_started_with_clumio_protect_for_s3.html)、[S3 のレプリケーションで複製しないもの](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication-what-is-isnot-replicated.html)。そのほかの製品の出典は、各社のドキュメント（2026-11-26 に閲覧）です。

### 各種類のトレードオフ

| 種類 | 向いている状況 | 引き受けること |
|---|---|---|
| ボリュームの階層化 | 利用者がファイルを今までどおり開く。運用を増やしたくない | 保管料金の下げ幅は容量プールまで。SSD の確保容量を減らさなければ SSD の料金は下がらない |
| ストレージ内蔵の階層化とスタブ | その製品のファイルシステムを使っている | 各製品の資料は、自社のファイルシステムに内蔵の機能として説明している。FSx for ONTAP のボリュームに使えるかは、読んだ資料に記載がない。被せる構成は想定されていないと考えている（未確認） |
| ファイルを被せるデータ管理ソフト | 多くの NAS を横断して、選別、分析、移動を 1 か所で決めたい | NFS か SMB でマウントする構成になる。製品のライセンスがかかる。復元が要る 2 クラスへの直接書き込みと、消す前の照合の必須化は、読んだ範囲に記載がない |
| オブジェクトを正本にするファイル基盤 | 正本を最初からオブジェクトストアに置き、拠点にキャッシュを置きたい | 既存のボリュームのファイルを移す仕組みではない。復元が要る 2 クラスは対象外か記載なし |
| 転送サービス（DataSync） | 大量のファイルを、検証つきでバケットへ写す | 元を消す機能、台帳、人の承認の 3 つは、読んだページに記載がないため、使う場合は自分で組む前提で考える。NFS か SMB の場所として使う |
| OSS のツールと層 | 自分でスクリプトを組める。ライセンスをかけたくない | FSx for ONTAP の S3 Access Points ではボリューム側のハッシュが取れないので、rclone の照合はそのままでは使えない。iRODS は自分のカタログの内側で動く |
| デジタル保存システム | 長期保存の手順（取り込み、定期の再検証、メタデータの標準）が求められる | 容量を空ける目的の仕組みではない。保存システムの運用が加わる |
| S3 API だけの照合と削除の仕組み（設計中） | 設計では、下の「[選び方](#選び方)」の条件に当てはまる | まだ実装がなく、実装の前に確かめる項目が 7 つ残っている。スタブも透過な呼び戻しもない。戻すのに、クラスと取り出しの種類に応じて数分から 48 時間かかる。最小保管期間（S3 Glacier Deep Archive は 180 日）がある。スナップショットが消したファイルのブロックを持っている間は、ボリュームの容量は空かない。照合のためにボリュームのファイルを一度読む（読み取りのリクエスト料金がかかり、容量プールにあればその読み取り料金もかかる）。自前で作るので保守も自前 |

## S3 API だけの照合と削除の仕組み

このリポジトリで設計を始めた仕組みです。実装は [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) に置く予定で、まだありません。以下は設計上の意図です。

実測した範囲は、実測ノートの `CopyObject` と復元の挙動です。環境は ap-northeast-1 の第 1 世代 `SINGLE_AZ_1`（ONTAP 9.19.1P4）、2026-11-24、各 1 回です。この環境の外と、流れ全体は測っていません。

### 流れ

| 段階 | 処理 | 使う機能 |
|---|---|---|
| 1. 選ぶ | 最後に読まれた日時、パス、大きさで対象を一覧にする | ONTAP REST API か NFS の `stat`。S3 API の `LastModified` は更新時刻で、最後に読まれた日時は返らない |
| 2. 記録する | パス、大きさ、所有者、モード、更新時刻、SHA-256 を台帳に書く | AWS Lambda（S3 Access Points から `GetObject` してハッシュを計算）、Amazon DynamoDB |
| 3. 写す | アーカイブ用のクラスを指定して `CopyObject` で写す。5 GiB を超えるものは `UploadPartCopy`。コピー元の ETag を `--copy-source-if-match` に付ける設計。違う ETag では `PreconditionFailed` で止まることは実測した。ファイルの更新で ETag が変わるかは測っていない | AWS Step Functions の Distributed Map |
| 4. 照合する | コピー先の大きさを台帳と比べる。SHA-256 は、バケットが返す `ChecksumSHA256` を台帳の値と比べる設計。この値が内容の SHA-256 と一致するかは、実装の前に確かめる | Lambda |
| 5. 承認する | 一致したファイルの一覧を人が確かめる | Step Functions のタスクトークン |
| 6. 消す | 承認されたファイルだけを、S3 Access Points の `DeleteObject` で消す | Lambda |
| 7. 戻す | 台帳から探し、バケットで復元を要求し、完了の通知を待って `CopyObject` で戻し、所有者、モード、更新時刻を台帳の値で付け直す | Step Functions、Amazon EventBridge（Object Restore Completed）、ONTAP REST API か NFS |

段階 3 の `--copy-source-if-match` の拒否と、バケットがコピー時に SHA-256 のチェックサムを返すことは、確かめました（環境は上の実測の範囲のとおり。[サーバー側コピーの用途](../../domains/data-utilization/notes/s3-access-points-server-side-copy-use-cases.md)）。段階 7 の、復元してから戻せることも同じノートにあります。所有者、モード、更新時刻がコピーで写らないことも、同じノートで確かめています。コピー先の Access Point のファイルシステムユーザーが root の場合の結果で、root 以外は試していません。だから段階 2 で属性を記録し、段階 7 で付け直します。

### 実装の前に確かめること

次の 7 つは、まだ確かめていません。実装の最初に、それぞれ 1 回確かめます。

- 5 GiB を超えるファイルを `UploadPartCopy` で写したときに、オブジェクト全体の SHA-256 で照合できるか。マルチパートのチェックサムは、パートごとの値を組み合わせた形になることがある
- `CopyObject` に `--checksum-algorithm SHA256` を付けたときにバケットが返す `ChecksumSHA256` が、ボリューム上のファイルの SHA-256 と一致するか。実測ノートは、値が返ることまでを確かめている
- NFS や SMB でファイルを更新したときに、ETag が変わるか。変わらなければ、`--copy-source-if-match` は更新を捕まえない
- S3 Access Points の `DeleteObject` が、条件付きの削除（`If-Match`）を受け付けるか。受け付けるなら、照合した版だけを消せる
- 移した後にボリュームの容量がいつ空くか。スナップショットの保持期間の分だけ遅れる（実測ノートの手順に記載）が、量は測っていない
- 2 つ目の写しの作り方（下の節の経路 C）が、実際にどの手順で成り立つか
- Lambda や Step Functions からコピーを呼ぶ構成。実測ノートでも測っていない

実測ノートが測っていない構成は、ほかに、第 2 世代と Multi-AZ のファイルシステム、NTFS の ACL を持つボリューム、並列に写したときの性能があります。

### 他の仕組みと組み合わせる経路

| 経路 | 組み合わせ | 担うこと | 引き受けること |
|---|---|---|---|
| A | 移す前に、AWS Backup で FSx for ONTAP のボリュームをバックアップする | 消す前の安全網。消したファイルは、ボリュームのバックアップから戻せる。別リージョン、別アカウントへのコピーも記載がある | バックアップの保管料金がかかる。戻すのはボリューム単位。復元先の扱いは、本調査では読んでいない。バックアップ用スナップショットでボリュームの SSD 使用率が 98% を超えると、バックアップは失敗すると記載されている |
| B | アーカイブ用のクラスを S3 Glacier Instant Retrieval にし、アーカイブ用のバケットを AWS Backup か Clumio で守る（Clumio は、公式サイトとドキュメントの記載が食い違うため、使う前に製品側へ確認が要る） | バケットの 2 つ目の写し、別アカウントへの写し、復元テスト（AWS Backup の Restore testing） | 保管料金は復元が要る 2 クラスより高い。バックアップのたびに取得料金がかかると AWS Backup が記載している。AWS Backup はバージョニングを必須にしている |
| C | 復元が要る 2 クラスに置き、2 つ目の写しは移す時点で別のバケットへも写して作る | バックアップ製品とレプリケーションが扱えないクラスでも、2 つ目の写しを持てる | S3 Access Points からの `CopyObject` は同じリージョンの中だけなので、別リージョンへ写す手順は別に要る。どの手順で成り立つかは確かめていない（未確認の経路） |
| D | 選別をデータ管理ソフト（Komprise など）に任せ、照合と削除をこの仕組みが担う | 多くの NAS を横断した分析と選別 | データ管理ソフトは NFS か SMB でマウントする構成になる。2 つの台帳をつなぐ必要がある |

経路 B と C の使い分けは、保管料金の差と、2 つ目の写しをどう管理するかで決まります。Clumio の保管庫（SecureVault）の料金は、公式の料金ページに載っています（[Clumio の料金](https://www.clumio.com/pricing)、日付とリージョンの記載はありません）。

## 選び方

| # | 確認すること | 判断 |
|---|---|---|
| 1 | 移した後も、利用者がファイルを元のフォルダーで開く必要があるか | 必要ならボリュームの階層化を選ぶ。スタブで見せたいなら、マウントして被せるデータ管理ソフト（Komprise の動的リンクなど）を選ぶ。S3 API だけの仕組み（設計中）はファイルを消す設計なので向かない |
| 2 | 容量プールの保管料金で足りるか | 足りるなら階層化で終わる。足りないなら、S3 Glacier 系のクラスへ移す仕組みを選ぶ |
| 3 | 戻すまでに何時間待てるか | Instant Retrieval は復元が要らない。Flexible Retrieval は迅速で 1〜5 分、標準で 3〜5 時間、大容量で 5〜12 時間（AWS のドキュメントの目安）。Deep Archive は標準で 12 時間以内、大容量で 48 時間以内 |
| 4 | アーカイブ用のバケットを、バックアップ製品で守る必要があるか | 必要なら、S3 Glacier Instant Retrieval に置いて経路 B を選ぶ。復元が要る 2 クラスに置くなら、経路 C で 2 つ目の写しを自分で作る（経路 C の手順は未確認） |
| 5 | ボリュームをマウントするホストを置けるか | 置けるなら、DataSync やデータ管理ソフトも選べる。置かずに S3 API だけで済ませたいなら、S3 API だけの仕組みが候補になる（設計中で、実装はまだない） |
| 6 | 消す前に照合と人の承認を必ず挟む必要があるか | 必要なら、S3 API だけの仕組み（設計中で未実装）か、Archivematica のような 2 段階の削除を持つ保存システムが候補になる。iRODS は、検証をチェックサムに設定すれば、照合してから元を消す。ただし人の承認の段階は、読んだ範囲に記載がない。ほかの製品では、照合と承認の両方の記載がない |
| 7 | 長期保存の手順（定期の再検証、標準のメタデータ）が求められるか | 求められるなら、デジタル保存システムを選ぶか、組み合わせる |

## よくある誤解

| 誤解 | 実際 |
|---|---|
| バックアップ製品に任せれば、アーカイブ用のバケットも守れる | 復元が要る 2 クラスのオブジェクトは、AWS Backup、Clumio、Commvault、Veeam が対象外と書き、Druva は Flexible Retrieval を読み飛ばすと書いている。S3 のレプリケーションも複製しない |
| FSx for ONTAP の階層化を使えば、S3 Glacier Deep Archive まで下げられる | 容量プールは AWS が管理する保管領域で、利用者が階層先のバケットやクラスを選ぶ方法は、読んだ FSx for ONTAP のユーザーガイドに記載がなかった。ONTAP の FabricPool は、オンプレミスでも S3 Glacier Flexible Retrieval と S3 Glacier Deep Archive を対象にしていない |
| ファイルを消せば、すぐにボリュームの容量が空く | ONTAP では、スナップショットが消したファイルのブロックを持っている間は、容量は空かない（実測ノートの手順に記載。移した後に容量が空くまでの時間は測っていない） |
| S3 API で照合するなら、ETag を比べればよい | FSx for ONTAP の S3 Access Points の ETag は MD5 ではなく、ボリューム側にチェックサムも保存されない。元のファイルを一度読んでハッシュを計算する |
| S3 API で、使われていないファイルを選べる | `LastModified` は更新時刻で、最後に読まれた日時は返らない。最後に読まれた日時は ONTAP REST API か NFS で読む |

## 比較時点

2026-11-26 に閲覧した公開ページの情報です。4 つの領域（FUSE と OSS、データ管理ソフトと SaaS、ハードウェアとテープと保存システム、バックアップ製品）を調べました。調査記録の表の行で数えて 62 行です（同じ製品が 2 つの領域に出るものは、重複して数えています）。読めなかったページは 48 件ありました（ログインが必要、HTTP 403、本文を取得できないもの）。読めなかったページの内容は、この資料の判断に使っていません。この資料の表に載せたのは、復元が要る 2 クラスや元の扱いで比較できた製品です。載せていない製品（オブジェクトストレージとテープのライブラリー、IBM Storage Deep Archive と HPE Data Management Framework のように公式ページを読めなかったものなど）の結果は、この資料に書いていません。版が古い資料だけで書いた記述（IBM Storage Scale の Transparent Cloud Tiering は 2018 年の資料）は、現行版で同じかを確かめていません。

## 関連ドキュメント

- [S3 Access Points のサーバー側コピーの用途](../../domains/data-utilization/notes/s3-access-points-server-side-copy-use-cases.md) — ストレージクラスごとの往復の実測、復元にかかった時間、アーカイブの往復の費用
- [S3 Access Points の制約](../../domains/data-utilization/notes/s3-access-point-constraints.md)
- [階層化ポリシーの比較](tiering-policies.md)
- [データ保護方式の比較](data-protection-methods.md)
