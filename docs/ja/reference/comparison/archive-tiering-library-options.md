---
title: FSx for ONTAP のファイルをアーカイブ用のクラスへ移す 9 種類の仕組みの比較 — バックアップ製品との組み合わせを含む
lifecycle: [design, operate, optimize]
domains: [data-utilization, cost, data-protection]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html
lang: ja
---

# FSx for ONTAP のファイルをアーカイブ用のクラスへ移す 9 種類の仕組みの比較

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md) | [比較マトリクス](README.md)

---

この資料は、Amazon FSx for NetApp ONTAP（以下 FSx for ONTAP）のボリュームにある、めったに読まれないファイルを、Amazon S3 の S3 Glacier 系のクラスへ移して保管料金を下げたい人に向けたものです。この資料は、移す仕組みを 9 種類に分けて比べます。ボリュームの階層化、ストレージ内蔵の階層化とスタブ（元の場所に残す小さな参照）、ディレクトリを S3 へ写す機能、ファイルを被せるデータ管理ソフト、オブジェクトを正本にするファイル基盤、転送サービス、OSS のツールと層、デジタル保存システム、S3 API だけで照合と削除を行う仕組みです。それぞれが何を担い、何を担わないかを、各社の公開ページで並べます。アーカイブ用のバケットを守るバックアップ製品（Clumio など）は、別の表で比べ、組み合わせ方も書きます。

この資料で使う語は次のとおりです。

- 移す: コピー先にファイルを写し、元のボリュームからファイルを消すこと。コピーだけで元を残す操作は「写す」と書きます
- S3 Access Points: FSx for ONTAP のボリュームに付ける、S3 API の入口です。ファイルをオブジェクトとして読み書きでき、同じリージョンの汎用バケットとの間でサーバー側コピー（`CopyObject`）ができます
- 階層化: ボリュームの中で、読まれていないデータのブロックを SSD から容量プール（使った量だけ課金される低価格の保管領域）へ移す FSx for ONTAP の機能です。ファイルはそのまま見えます
- スタブ: 元のファイルの代わりに置く小さな参照（シンボリックリンク、独自形式のファイル）で、読まれたときに本体を呼び戻すためのものです
- 照合: コピー先の中身が元と同じかを、大きさとハッシュ（SHA-256 など）で確かめることです
- 台帳: どのファイルを、いつ、どこへ移したかと、属性とハッシュを記録したものです。戻すときの索引になります
- S3 Glacier 系のクラス: S3 Glacier Instant Retrieval（すぐに読める）、S3 Glacier Flexible Retrieval と S3 Glacier Deep Archive（読む前にバケットで復元が要る）の 3 つです。この資料で「復元が要る 2 クラス」と書くときは、後の 2 つを指します

この資料が比べる「S3 API だけで照合と削除を行う仕組み」は、この Hub（FSx for ONTAP Adoption Playbook）で設計し、実装は別のリポジトリ [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/data-lifecycle/archive-verify-delete) にあります。以下、この実装を「パターン」と書きます。FSx for ONTAP の 1 つのファイルシステムで、3 つの確認（「5.5 GiB を含む 7 ファイルの通し」「除外と承認を確かめる通し」「直接呼び出しを確かめる確認」）を実行しました。その欄は、公開ページの記載ではなく、この実装とその実行の結果です。多数のファイルと、この環境の外の構成は測っていません。中身は「[S3 API だけの照合と削除の仕組み](#s3-api-だけの照合と削除の仕組み)」の節にあります。どの用途に合うかは、[ファイルを消して S3 Glacier 系へ移す用途と連携先のノート](../../domains/data-utilization/notes/archive-use-cases-and-integrations.md)にあります。

> **実機での確認は 3 つで、値は確認ごとに書きます**: 「5.5 GiB を含む 7 ファイルの通し」は、Fargate を通る大きなファイルの写しと戻しを含みます。「除外と承認を確かめる通し」は 11 ファイルを作り、4 ファイルが選ばれた構成で、除外条件、承認の検査、戻した後の照合を確かめました。Fargate は通っていません。「直接呼び出しを確かめる確認」は 256 KiB のファイル 8 つで、承認が実行と時間に結び付いていることを、delete 関数の直接呼び出しで確かめました。3 つとも ap-northeast-1、2026-11-26 に、各手順 1 回です。たとえば 5.5 GiB を含む 7 ファイルの通しの 64 B のファイル 3 つは、除外と承認を確かめる通しの既定の最小サイズ（128 KiB）では選ばれません。削除の再試行と再開は、単体テストだけで、実機では通していません。

## 結論

- **ファイルを利用者から見えたままにしたいなら、ボリュームの階層化で足ります。** 容量プールの保管料金は、東京リージョンの Single-AZ で $0.0238 / GB-月で、S3 Standard の $0.025 / GB-月と同じくらいです（2026-11-24 取得）。Multi-AZ は $0.0476 / GB-月で、約 1.9 倍です。容量プールには読み取りと書き込みのリクエスト料金も別にかかります。S3 Glacier 系のクラスほどは下がりませんが、復元を待つ時間も、照合と削除の運用も要りません。S3 Glacier 系へ移して得になるかは、1 オブジェクトの追加メタデータ、最小保管期間、取り出しとリクエストの料金で変わります（[保管料金の損益分岐の考え方](../../domains/data-utilization/notes/archive-use-cases-and-integrations.md#保管料金の損益分岐の考え方)。[容量プールに置いたままにするか、バケットへ移すかの判断](../../domains/data-utilization/notes/s3-access-points-server-side-copy-use-cases.md#容量プールに置いたままにするかバケットへ移すかの判断)）
- **復元が要る 2 クラスへ移したいなら、「写す、照合する、人が承認する、元を消す」を 1 つの製品で行えると書いたページは、今回読んだ範囲にありませんでした。** 部分的な記載はあります。OSS の rclone は `move` で元を消せ、クラスを指定して書けます（FSx for ONTAP の S3 Access Points ではボリューム側の MD5 が取れず、MD5 での照合は成り立ちません）。iRODS は次の階層へ複製し、大きさかチェックサムで検証してから元を消します（人の承認の記載はありません）。Archivematica は削除を「要求」と「管理者の承認」の 2 段階にしています（復元が要る 2 クラスへの書き込みの記載は見つけられませんでした）。対象は FSx for ONTAP のボリュームのファイルです。階層化とスタブ型の製品の多くは、S3 Glacier Instant Retrieval までを対象にしています。復元が要る 2 クラスについては、Dell PowerScale CloudPools、ONTAP の FabricPool、Nasuni が対象外と書いています。Hammerspace、Panzura、CTERA は、読んだページに記載がありませんでした。写すだけなら、AWS DataSync が全クラスへ書けます。DataSync に元を消す機能の記載は、読んだページにありませんでした
- **S3 API だけの照合と削除の仕組み（パターン）が前提にするのは、次の 3 つです。** ファイルの読み取り、コピー、削除に NFS のマウントを使わず、S3 Access Points の S3 API だけで行うこと、復元が要る 2 クラスへ `CopyObject` で直接写すこと、照合で一致したファイルだけを、人の承認の後に消すことです。ただし、最終アクセス時刻で選ぶときは VPC 内の AWS Lambda から ONTAP REST API を呼び（ONTAP の認証情報と管理エンドポイントへの到達性が要る）、戻した後の所有者・モード・更新時刻の付け直しには、NFS でボリュームをマウントしたホストが要ります。実装して 3 つの確認を実行しました（ap-northeast-1、2026-11-26、各手順 1 回）。5.5 GiB を含む 7 ファイルの通しでは、7 ファイルのうち 6 ファイルが消え、承認待ちの間に書き換えたファイル 1 つは消えず、承認を拒否すると何も消えず、消した 6 ファイルは戻せて、SHA-256 が事前に記録した値と一致しました。「除外と承認を確かめる通し」では、11 ファイルのうち 4 ファイルが選ばれ、同じ実行 ID の再利用、起動者と同じ申告の承認、承認を経ない直接の削除が拒否され、書き換えたファイルは `CHANGED` で残り、戻した 3 ファイルは戻した後の再ハッシュで台帳と一致しました（`RESTORE_VERIFIED`）。「直接呼び出しを確かめる確認」では、別の実行の ARN と止めた実行自身の ARN での delete 関数の直接呼び出しが拒否されました。5 GiB を超えるファイルの戻した後の照合（Fargate の経路）は通していません。条件は「[実機での通しの結果](#実機での通しの結果)」。起動者と承認者を分ける検査は、申告された 2 つの値の比較で、主体の証明ではありません。実際に承認した主体は、AWS CloudTrail の `userIdentity` で後から確かめます。代わりに、スタブも透過な呼び戻しもなく、移したファイルは利用者のフォルダーから消えます
- **アーカイブ用のバケットを守るバックアップ製品は、復元が要る 2 クラスのオブジェクトを対象外にしています。** AWS Backup、Clumio、Commvault、Veeam が公開ページで対象外と書き、Druva は Flexible Retrieval を読み飛ばすと書いています。S3 のレプリケーションも、この 2 クラスのオブジェクトを複製しません。バックアップ製品もレプリケーションも使えないので、復元が要る 2 クラスに置くなら、バケットのオブジェクトの別のコピー（2 つ目の写し）を、移す時点で自分で作ります。これが経路 C です（A、B、D も含めた 4 つの経路は次の文のとおりです）。試した範囲では、S3 Access Points（インターネット起点、1 つ）から大阪のバケットへの直接のコピーは `AccessDenied` になり、一度東京のバケットへ S3 Standard で写してから大阪へ送る手順は成功しました（2026-11-26、1 MiB、各 1 回）。直接のコピーが失敗した原因が Access Point の設定なのか、リージョンをまたぐ制約一般なのかは区別していません。バックアップ製品で守るなら、アーカイブ用のクラスを S3 Glacier Instant Retrieval にします。これが経路 B です。どちらの場合も、移す前に AWS Backup でボリュームをバックアップしておく経路 A を組み合わせられます。選別だけをデータ管理ソフトに任せる経路 D もあります。経路 A から D の内容は「[他の仕組みと組み合わせる経路](#他の仕組みと組み合わせる経路)」の表にあります

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
| S3 API だけの照合と削除の仕組み（実装あり。実機の確認 3 つ） | この Hub で設計した [archive-verify-delete](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/data-lifecycle/archive-verify-delete) | S3 Access Points | 消える（スタブなし） | `CopyObject` で直接書く。S3 Glacier Flexible Retrieval への書き込みと、そこからの戻しを実機で通した（ap-northeast-1、第 1 世代 `SINGLE_AZ_1`、ONTAP 9.19.1P4D1、2026-11-26、各 1 回） | 一致したファイルだけを、人の承認の後に消す。承認の拒否で何も消えないことと、承認待ちの間に書き換えたファイルが消えないことを確認した（各 1 回）。削除するのは、同じ実行で承認され、承認から `ApprovalValidityHours`（既定 24 時間）以内の項目だけ（別の実行の ARN と、止めた実行自身の ARN での直接呼び出しの拒否は実機で確認。期間の超過は単体テストのみ）。起動者と承認者の分離は申告値の比較 | DynamoDB の台帳 |

> **注記**: FSx for ONTAP の S3 Access Points では、ETag は MD5 ではありません。アップロード時に指定したチェックサムは受け付ける前に検証されますが、その値はボリュームに保存されず、応答にも返りません（[サポートする API の一覧](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)）。このため、MD5 を比べる道具（rclone の `check` など）は、ボリューム側のハッシュを得られません。rclone で実際にそうなった記録は、[FSx-for-ONTAP-S3AccessPoints-Client-Access-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Client-Access-Patterns) にあります（2026-11-24、rclone 1.76.0）。

上の表の根拠の区分は行によって違います。最初の 8 行は、各社の公開ページの記載（`documented`）です。最終行だけが、この資料の筆者が作った実装と、その 2 回の実測です。表の中の優劣を示すものではなく、根拠の強さが違う行が並んでいることを示しています。照合と削除を AWS DataSync と自前のスクリプトで組む構成も、同じ目的に使える別の組み立てです（下の「選び方」の 6 番）。

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
| S3 API だけの照合と削除の仕組み | 下の「[選び方](#選び方)」の条件に当てはまる | 実機の確認は、5.5 GiB を含む 7 ファイルの通し、11 ファイルから 4 ファイルが選ばれた除外と承認を確かめる通し、8 ファイルで直接呼び出しを確かめる確認の 3 つで、多数のファイルでの所要時間と料金、第 2 世代、Multi-AZ、NTFS は測っていない。削除の再試行と再開は、単体テストだけで、実機では通していない。ETag は内容でなく更新時刻と大きさに連動するので、大きさと更新時刻を変えない内容の変更は、消す前の確認で検出できない。スタブも透過な呼び戻しもない。戻すのに、クラスと取り出しの種類に応じて数分から 48 時間かかる。最小保管期間（S3 Glacier Deep Archive は 180 日）がある。1 GiB のファイルを消しても、スナップショットがある間は、ボリュームの使用量は作成前に戻らなかった（実測、1 回。使用量が元に戻ったのは、そのスナップショットを消した後）。照合のためにボリュームのファイルを一度読む（読み取りのリクエスト料金がかかり、容量プールにあればその読み取り料金もかかる）。単一ファイルが 50 GiB を超えると、Access Points へ戻せない（公式ページは、アップロードの上限が 50 GiB で、それを超えるオブジェクトのダウンロードはできると書く。バケットから直接ダウンロードする手順は通していない。パターンは、50 GiB を超えるファイルを選択から外す。`SKIPPED_TOO_LARGE`。51 GiB の疎ファイルが外れることだけを確かめ、写しと戻しは行っていない）。消したファイルはスナップショットには残り、SnapMirror の宛先への伝わり方は確かめていない（[消した結果が及ぶ範囲](../../domains/data-utilization/notes/archive-use-cases-and-integrations.md#消した結果が及ぶ範囲)）。起動者と承認者の分離は、申告された 2 つの値の比較で、主体の単位で強制するには IAM の設計が要る。自前で作るので保守も自前 |

## S3 API だけの照合と削除の仕組み

この Hub で設計し、別のリポジトリ [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/data-lifecycle/archive-verify-delete) に実装した仕組み（パターン）です。流れ全体を、FSx for ONTAP の 1 つのファイルシステムで 3 つの確認を実行しました（「[実機での通しの結果](#実機での通しの結果)」）。

![構成図。上の枠の AWS Step Functions が、AWS Lambda（5 GiB 以下のハッシュ）、AWS Fargate（5 GiB 超のハッシュとコピー）、Amazon DynamoDB（台帳）、Amazon SNS（承認の依頼）を呼び、承認する人が結果を返す。AWS Step Functions は、Amazon S3 Access Points に CopyObject、DeleteObject、元の HeadObject を呼び、アーカイブ用の汎用バケットにコピー先の HeadObject（照合）を呼ぶ。下の段では、Amazon FSx for NetApp ONTAP のボリュームのファイルが、S3 Access Points からチェックサム付きのサーバー側コピーで、汎用バケット（S3 Glacier Instant Retrieval、Flexible Retrieval、Deep Archive）へ写る。同じリージョンの別のバケットの 2 つ目の写しは、汎用バケットからではなく S3 Access Points から直接作る（経路 C）。移す前のボリュームは AWS Backup でバックアップできる（経路 A）。バケットが S3 Glacier Instant Retrieval のときは、AWS Cloud の内側の AWS Backup と、AWS の外のバックアップ製品（Clumio など）で守れる（経路 B）。選別は Komprise などのデータ管理ソフトに任せられる（経路 D）。戻す流れは図の下の注記にある](../../../_assets/images/archive-verify-delete.svg)

図の内容は、戻す流れを除き本文の表と同じです。2 つ目の写しは、アーカイブ用のバケットからではなく、S3 Access Points から直接作ります。戻す流れは「流れ」の表の段階 7 にあります（[暗い背景の版](../../../_assets/images/archive-verify-delete-dark.svg)、[English](../../../_assets/images/archive-verify-delete-en.svg)）。

部品の挙動は、2026-11-24 と 2026-11-26 に、通しの実行の前に確かめました。環境は ap-northeast-1 の第 1 世代 `SINGLE_AZ_1`（スループット容量 128 MBps、ONTAP 9.19.1P4D1）、UNIX セキュリティスタイルのボリュームで、Access Point のファイルシステムユーザーは UNIX の root です。クライアントは Amazon Linux 2023 の EC2（AWS CLI 2.38.0、boto3 1.40.31）で、どの確認も 1 回ずつです。この環境の外（第 2 世代、Multi-AZ、NTFS のボリューム、root 以外のユーザー）は測っていません。

### 流れ

| 段階 | 処理 | 使う機能 |
|---|---|---|
| 1. 選ぶ | 最後に読まれた日時、パス、大きさで対象を一覧にする | ONTAP REST API か NFS の `stat`。S3 API の `LastModified` は更新時刻で、最後に読まれた日時は返らない。ONTAP REST API は VPC 内の Lambda から呼ぶ。VM のディスクイメージ、データベースのファイル、表形式のメタデータは、除外パターン（`ExcludePatterns`）の既定で外れる |
| 2. 記録する | パス、大きさ、所有者、モード、更新時刻、ETag、SHA-256 と CRC64NVME を台帳に書く | AWS Lambda（S3 Access Points から `GetObject` してハッシュを計算。5 GiB を超えるファイルは AWS Fargate のタスク）、Amazon DynamoDB |
| 3. 写す | アーカイブ用のクラスを指定して写す。5 GiB 以下は `CopyObject` に `--checksum-algorithm SHA256`、5 GiB を超えるものはマルチパートのコピーに `CRC64NVME`。台帳の ETag を `--copy-source-if-match` に付ける | AWS Step Functions の SDK 統合（`aws-sdk:s3:copyObject`）と Distributed Map。5 GiB を超えるファイルは Fargate のタスクがマルチパートのコピーを行う |
| 4. 照合する | コピー先の大きさと、バケットが返すチェックサムを、台帳の値と比べる | Step Functions の SDK 統合（`headObject` に `ChecksumMode: ENABLED`） |
| 5. 承認する | 一致したファイルの一覧を人が確かめる | Step Functions のタスクトークン（`waitForTaskToken`）。通知は Amazon SNS、トークンは AWS Systems Manager Parameter Store に置く（実行が失敗したらトークンは削除する） |
| 6. 消す | 同じ実行で承認され、承認から `ApprovalValidityHours`（既定 24 時間）以内のファイルについて、Access Point の `HeadObject` で ETag が台帳と同じことを確かめてから、`DeleteObject` で消す | Step Functions の SDK 統合（`headObject`、`deleteObject`） |
| 7. 戻す | 台帳から探し、バケットで復元を要求し、完了を待って `CopyObject` で戻し、所有者、モード、更新時刻を台帳の値で付け直す | Step Functions。完了の待ちはポーリング（`HeadObject` の `Restore` ヘッダー）。付け直しは、生成したスクリプトを NFS でマウントしたホストで実行する。戻した後に再ハッシュして台帳と比べ、一致を `RESTORE_VERIFIED`、不一致を `RESTORE_MISMATCH` にする（`RESTORE_MISMATCH` は再戻しの指定で戻し直せる）。付け直しの対象は `RESTORE_VERIFIED` のファイルだけ |

### 部品ごとに確かめたこと

| 段階 | 確かめたこと | 設計への反映 |
|---|---|---|
| 3、4 | 64 B と 8 MiB を `CopyObject` に `--checksum-algorithm SHA256` を付けて写すと、バケットが返す `ChecksumSHA256`（型は `FULL_OBJECT`）は、NFS で読んだファイルの SHA-256 と一致した。S3 Glacier Deep Archive と S3 Standard の両方で同じ。Access Point の `HeadObject` はチェックサムを返さない | 5 GiB 以下は、台帳の SHA-256 とバケットの `ChecksumSHA256` を比べる |
| 3、4 | 5.5 GiB（5,905,580,032 バイト、704 パート）をマルチパートで写すと、SHA-256 は `COMPOSITE`（8 MiB ごとの SHA-256 を組み合わせた値）になり、ファイル全体の SHA-256 とは別の値になった。CRC64NVME は `FULL_OBJECT` で、ファイル全体から計算した値と一致した。CRC64NVME で S3 Standard へ写すのに 16.5 秒かかった | 台帳には SHA-256 と CRC64NVME の両方を書く。5 GiB を超えるものは CRC64NVME で照合する |
| 3 | NFS で、同じ大きさで中身を上書きする、追記する、`touch` で更新時刻だけを変えると、Access Point の ETag が変わり、古い ETag を付けた `--copy-source-if-match` は `PreconditionFailed` になった。`chmod` だけでは ETag も `LastModified` も変わらなかった。変更なしの対照は成功した。ETag は中身ではなく、更新時刻と大きさに連動していた（UNIX スタイルのボリュームのみ）。公式ページ（[サポートする API の一覧](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)、2026-11-26 閲覧）は、ETag が反映するのはオブジェクトの内容の変更だけで、メタデータの変更は反映しないと書いている。この測定は 1 回で、公式の記述との食い違いの理由は調べていない。`chown` と、中身を変えて更新時刻を元に戻す操作は、この確認では試していない（通しの実行では、同じ大きさと同じ更新時刻で内容の違うファイルが同じ ETag を返した） | 中身の上書き、追記、更新時刻の変更は、ETag の変化で捕まえられる。大きさと更新時刻を変えない内容の変更は、ETag では捕まえられない。所有者とモードの変化は ETag では分からない（`chmod` は確認、`chown` は未測定）。パターンは消す前に ETag と大きさだけを確かめ、台帳のハッシュと属性の読み直しは行わない。読み直す場合は、NFS か ONTAP REST API で行う別の段階になる（変更時刻（ctime）が ONTAP REST API で取れるかは未確認） |
| 6 | Access Point の `DeleteObject` は条件付きの削除（`If-Match`）を受け付けず、正しい ETag でも `NotImplemented` で、ファイルは消えなかった。`DeleteObjects` は ETag を付けると `MalformedXML` になった | 消す直前に `HeadObject` で ETag を確かめる。確かめてから消すまでの間に書き換えられる余地は残る |
| 6 | ランダムデータの 1 GiB のファイルを作り（使用量 8,440 MiB → 9,478 MiB）、通常のスナップショットを取ってから、Access Point の `DeleteObject` で消した。60〜180 秒後の使用量は 8,679 MiB で、削減は約 800 MiB だった（作成前より約 240 MiB 多い）。スナップショットの使用量は 224 MiB から 1,253 MiB に増えた。そのスナップショットを消すと、30 秒後に使用量は 8,450 MiB に戻った。スナップショットなしで消した対照は取っていない | 容量が作成前の水準に戻ったのは、そのスナップショットを消した後だった。スナップショットの保持期間を、効果が出るまでの時間として示す。対照を取っていないため、約 240 MiB が残った原因がスナップショットだけかは未確認 |
| 7 | S3 Standard のバケットのオブジェクト（256 KiB）を、Access Point へ `CopyObject` で戻した。戻したファイルは、所有者 0:1、モード 644、更新時刻は戻した時刻になり、元は所有者 1234:5678、モード 640、更新時刻 2020-01-02 03:04:05 だった。NFS の `chown`、`chmod`、`touch -d` で、4 つとも元の値に付け直せ、中身の SHA-256 は元と一致した。S3 Glacier Flexible Retrieval と S3 Glacier Deep Archive からの復元を経た戻しは、この確認では行っていない（復元を経た戻しは、[サーバー側コピーの用途のノート](../../domains/data-utilization/notes/s3-access-points-server-side-copy-use-cases.md)で別に測った） | 段階 2 で記録した値で付け直す |
| 全体 | Step Functions の SDK 統合だけで、`copyObject`（`--checksum-algorithm SHA256` 相当）→ バケットの `headObject` → Access Point の `headObject` → `waitForTaskToken` → `deleteObject` を通せた（1 回、25 秒）。承認は、通知先を SQS にせず、SSM の `putParameter` でトークンを書き出し、`SendTaskSuccess` を手で送って行った。`CopyObject` に `--copy-source-if-match` を付けた実行は、この確認では行っていない（付けた場合は、段階 3 の行で CLI から確認した）。Lambda は要らなかった。実行ロールにバケットと Access Point の両方の ARN への S3 の権限が要り、Access Point のポリシーにも実行ロールの許可が要った | コピー、照合、削除は SDK 統合で組む。Lambda はハッシュの計算（段階 2）だけに使う |

### 2 つ目の写しの作り方

「2 つ目の写し」は、アーカイブ用のバケットのオブジェクトを、別のバケットや別のリージョンに持つ、もう 1 つのコピーのことです。試した Access Point は、インターネット起点の 1 つです。オブジェクトは 1 MiB で、コピー先のクラスは S3 Glacier Deep Archive、各手順 1 回です。

| 手順 | 結果（2026-11-26） |
|---|---|
| Access Point から同じリージョンの別のバケットへ `CopyObject`（S3 Glacier Deep Archive を指定） | 成功。チェックサムも一致 |
| Access Point から別のリージョン（大阪）のバケットへ `CopyObject` | `AccessDenied`（"Cannot access through this access point"）。エイリアスでも ARN でも同じ。原因が Access Point の設定か、リージョンをまたぐ制約一般かは区別していない |
| 東京のバケット（S3 Standard）から大阪のバケットへ `CopyObject`（S3 Glacier Deep Archive を指定） | 成功 |
| 東京のバケットのレプリケーション（宛先は大阪、宛先のクラスは S3 Glacier Deep Archive） | S3 Standard で写したオブジェクトは約 1 秒で複製され、宛先で S3 Glacier Deep Archive になった。S3 Glacier Deep Archive で写したオブジェクトは、15 分待っても複製されなかった |

別のリージョンに 2 つ目の写しを置く手順として、2 通りを確かめました。一度 S3 Standard で東京のバケットへ写し、そこから大阪のバケットへ S3 Glacier Deep Archive を指定して `CopyObject` で写す手順と、東京のバケットから大阪へのレプリケーション（宛先のクラスは S3 Glacier Deep Archive）で送る手順です。どちらも、東京の S3 Standard の写しを、送った後で S3 Glacier Deep Archive に変える操作は測っていません。S3 Standard の写しを持つ間は、その分の保管料金がかかります。

### 実機での通しの結果

実装した流れ全体を、同じ FSx for ONTAP のファイルシステムで、次の 3 つの確認を実行しました。環境は ap-northeast-1、第 1 世代 `SINGLE_AZ_1`、ONTAP 9.19.1P4D1、UNIX セキュリティスタイルのボリュームで、Access Point のファイルシステムユーザーは UNIX の root です。実行日は 3 つとも 2026-11-26（時刻は日本時間）で、各手順は 1 回です。3 つが確かめた範囲は違います。

| 確認 | ファイル | 確かめた範囲 | 通っていない範囲 |
|---|---|---|---|
| 5.5 GiB を含む 7 ファイルの通し | 7 ファイル（5.5 GiB を含む） | 写し、照合、承認の拒否、承認待ちの間の書き換え、削除、戻し。Fargate が行う 5.5 GiB のコピー | Fargate 経路での戻した後の台帳との照合（SHA-256 は、事前に NFS で記録した値と一致） |
| 除外と承認を確かめる通し | 11 ファイルを作り、4 ファイルが選ばれた（最大 1 MiB） | 除外条件、実行 ID の再利用の拒否、自己承認と直接の削除の拒否、書き換えの検出、戻した後の再ハッシュ、通知とアラーム | Fargate の経路（5 GiB 超のハッシュとコピー、戻した後の照合）。50 GiB 超の写しと戻し。削除の再試行と再開（単体テストのみ） |
| 直接呼び出しを確かめる確認 | 256 KiB のファイル 8 つ | 承認の結び付け（別の実行の ARN での直接呼び出しの拒否、止めた実行自身の ARN の拒否）、`reconcile` での復帰、承認後と拒否後のトークンの削除 | 承認の期間（`ApprovalValidityHours`）の超過、ウォッチドッグによる古いトークンの削除、削除の再試行と再開（単体テストのみ） |

#### 5.5 GiB を含む 7 ファイルの通し: 7 ファイルと大きなファイルの戻し

構成は、最終アクセス時刻での選択（`selection=ATIME`）、アーカイブ先のクラスは S3 Glacier Flexible Retrieval（`GLACIER`）、2 つ目の写しあり、AWS Fargate は arm64 の 2 vCPU と 8 GiB です。データは 7 ファイルで、小さい 6 つ（64 B が 3 つ、8 MiB が 3 つ。所有者 1234:5678、モード 640、更新時刻と最終アクセス時刻は 2020-01-02）と、5,905,580,032 B（約 5.5 GiB）のファイル 1 つです。記録の原本は、パターンの `solutions/data-lifecycle/archive-verify-delete/README.md` にあります。

| 手順 | 結果 | 所要 |
|---|---|---|
| dry run（削除なし） | 7 ファイルとも照合が一致（SHA-256 が 6、CRC64NVME が 1）。2 つ目の写しも一致。削除は 0 バイトで、NFS では 7 ファイルとも残った | 244 秒（承認の待ち約 70 秒を含む） |
| 承認待ちの間の書き換え | 1 ファイルを NFS で同じ大きさのまま 4 KiB 上書き（更新時刻は更新）。承認後に `CHANGED`（ETag または大きさの不一致）になり、消えなかった | |
| 本番と承認 | 6 ファイルを削除し、書き換えた 1 ファイルは `CHANGED` で残した。削除した量は 5,922,357,440 バイト | 310 秒（承認要求まで 172 秒、承認から完了まで約 6 秒） |
| 戻し（`Expedited`） | 6 ファイルが戻り、SHA-256 は 5.5 GiB を含む 6 ファイルとも、事前に NFS で記録した値と一致。戻した直後は所有者 0:1、モード 644、更新時刻は戻した時刻。生成された再付与スクリプトを root で実行すると、1234:5678、640、2020-01-02 03:04:05 に戻り、内容の SHA-256 は変わらなかった | 287 秒（5.5 GiB の Fargate によるコピーが 2 分 38 秒） |
| 承認の拒否 | 実行は拒否で終わり、3 ファイルは照合が一致したまま残り、削除されなかった。NFS では 3 ファイルとも残った | 16 秒 |
| Lambda で約 4.94 GiB のハッシュ | 照合が一致（SHA-256 が NFS の値と一致）。ハッシュを計算する関数は 69.8 秒、使用メモリ 152 MB（設定 2048 MB） | |

この通しで必要になった権限と設定は、[デプロイと運用の前提条件](#デプロイと運用の前提条件)にまとめました。

#### 除外と承認を確かめる通し: 除外条件、承認の検査、戻した後の照合

構成は、`selection=ATIME`、除外パターン `*.vmdk` と保全用のプレフィックス 1 つ、アーカイブ先は `GLACIER`、2 つ目の写しあり、並列度 2（既定は 1）、AWS Fargate は arm64 の 2 vCPU と 8 GiB（この回は通っていない）です。データは 11 ファイルで、所有者 1234:5678、モード 640、更新時刻 2020-01-02 です。

| 作ったファイル | 大きさ | 期待 | 結果 |
|---|---|---|---|
| 64 B が 3 つ、131,071 B が 1 つ | 最小サイズ（128 KiB = 131,072 B）未満 | 外れる | 外れた（4 件） |
| 131,073 B が 1 つ、1 MiB が 3 つ | 最小サイズ以上 | 選ばれる | 4 件が選ばれた |
| `*.vmdk` の 1 MiB が 1 つ | 除外パターンに一致 | 外れる | 外れた |
| 保全用のプレフィックスの下の 1 MiB が 1 つ | 除外プレフィックスに一致 | 外れる | 外れた |
| 疎ファイル 1 つ | 54,760,833,024 B（51 GiB） | 50 GiB 超で外れる | `SKIPPED_TOO_LARGE`。写しも戻しもしていない |

| 手順 | 結果 | 所要 |
|---|---|---|
| dry run（削除なし） | 4 ファイルが `VERIFIED`。除外の内訳は、大きすぎる 1、小さすぎる 4、パターン 1、プレフィックス 1。マニフェストと結果の `data_classification` は `RESTRICTED` | 66 秒 |
| 入力の拒否 | 同じ実行 ID での再実行が `InvalidInput`（台帳に項目が既にある）。`dryRun=false` で起動者の指定がないものも `InvalidInput`。失敗の通知は、カスタマー管理キーで暗号化した SNS トピックを経由して届いた | |
| 自己承認と直接の削除の拒否 | 承認待ちの間に delete 関数を直接呼ぶと `NOT_APPROVED` でファイルは残った。起動者と同じ ARN で承認を送ると `APPROVAL_REFUSED`。`DELETED` は 0、全件 `VERIFIED` のまま | 66 秒 |
| 別の承認者の申告と書き換え | 承認待ちの間に 1 ファイルを NFS で 4 KiB 上書き（大きさは同じ、更新時刻は更新）。承認者は別の IAM ユーザーの ARN を申告して受理された（同じ SSO の主体が別の ARN を申告した。2 つ目の主体は用意していない）。3 ファイルが `DELETED`、書き換えた 1 ファイルは `CHANGED` で残った。`deletedBy` は台帳の `approvedBy` と一致し、承認者と起動者を書いた承認の記録が出力された | 45 秒 |
| 戻し（`Expedited`） | `RESTORE_VERIFIED` が 3 件。`CHANGED` で残った 1 ファイルは写しがあるため選ばれたが、Access Point に同じキーがあるので上書きせず `EXISTS`。NFS の SHA-256 は 3 件とも、手順の前の値と一致。戻した直後は root:bin、モード 644。再付与スクリプトは `RESTORE_VERIFIED` の 3 件分が生成された | 192 秒（ポーリング間隔 1 分に設定） |
| アラーム | 6 個がデプロイされた。`FilesMismatchAlarm` を手で ALARM にすると、通知が発行された。`ApprovalPendingHours` のメトリクスが出ていることは確認し、ALARM になるまでは待っていない | |

この通しで必要になった権限は、[デプロイと運用の前提条件](#デプロイと運用の前提条件)にまとめました。

1 ファイルあたりの状態遷移は、除外と承認を確かめる通しの実行ごとに、dry run が 18（4 ファイルで 72）、承認の拒否が 18.25（73）、3 削除と 1 `CHANGED` の本番が 19.5（78）、戻しが 14（56）でした。5.5 GiB を含む 7 ファイルの通しは約 17 から 18 です。いずれも、親と子の実行の遷移の合計を割った値で、1 回の実測です。

5.5 GiB を含む 7 ファイルの通しなどで分かった、パターンが吸収していない挙動です。

| 挙動 | 影響 |
|---|---|
| 最終アクセス時刻で選ぶとき、ハッシュ計算の読み取りがファイルの最終アクセス時刻を更新する。dry run の直後に同じ入力で本番を回すと、候補が 0 件で終わった | dry run の後に本番を回すなら、更新時刻で選ぶ（`LastModified` は読み取りで変わらない） |
| Access Point の ETag は内容でなく更新時刻と大きさに連動する。同じ大きさと同じ更新時刻で内容の違う 3 ファイルが、同じ ETag を返した | 消す前の ETag と大きさの確認は、大きさと更新時刻を変えない内容の変更を検出できない。承認待ちの間に、大きさが同じで更新時刻が変わった書き換えは検出できた |
| Access Point で最後のファイルを消すと、空になった親ディレクトリも消える | 戻しの `CopyObject` が親ディレクトリを作り直す |
| `touch -d` で最終アクセス時刻を戻した約 10 秒後の実行で、候補が 0 件だった | 約 17 分後の確認では 2020 年の値が返り、別の確認でも 6 件が返った。原因は特定しておらず、再現もしていない |

#### 直接呼び出しを確かめる確認: 承認の結び付け

delete 関数を直接呼ぶ入力が、承認と実行に結び付いているかを確かめました。構成は `selection=MTIME`、アーカイブ先は `GLACIER`、Fargate なし、2 つ目の写しなし、並列度 1（既定）、`ApprovalTimeoutHours=1`、256 KiB のファイル 8 つです。Access Point は前の 2 つと同じです。

| 手順 | 結果 |
|---|---|
| デプロイ | Fargate なしで成功した。必要な許可は[前提条件](#デプロイと運用の前提条件)の (7) |
| 承認トークン | 承認待ちのパラメーターは SecureString で、スタックの KMS キーで暗号化されていた。承認の直後と、拒否の直後に、`GetParameter` が `ParameterNotFound` を返した |
| 承認の直後に実行を止める | 承認の記録の後に `StopExecution`。実行は `ABORTED` で、台帳に `APPROVED` が 8 件残った |
| 別の `claim` での直接呼び出し | 別の実行の ARN、文字列 `manual`、削除済みの `approvedBy` を付けた入力の 3 通りとも `NOT_APPROVED`（`approval not current`）。8 件とも `APPROVED` のまま |
| 止めた実行自身の ARN を `claim` にした呼び出し | `NOT_APPROVED`（`claiming execution is not running`）で、何も消えなかった。止めた実行の ARN は台帳に載っていて、台帳を読める人は渡せるので、delete 関数は `claim` の実行が実行中かを確かめる。`reconcile` は残った `APPROVED` の項目を `VERIFIED` に戻した |
| 対照 | 承認して最後まで流すと、承認した項目がすべて `DELETED`（実行状態の確認が通り、`states:DescribeExecution` の権限が足りている）。拒否（`send-task-failure`）した実行は全件 `VERIFIED` のまま、トークンは削除済み |

この確認で確かめていないのは、承認の期間（`ApprovalValidityHours`）の超過、ウォッチドッグが古いトークンを消す動作、実行中の実行が `DescribeExecution` を経て再試行し `DELETED` に至る経路です。`states:SendTaskSuccess` は IAM でリソースを絞れない（AWS の Service Authorization Reference で確認）ため、承認者のポリシーが絞れるのは、トークンを読む経路です。

### デプロイと運用の前提条件

パターンが前提にする権限と設定です。満たさないと、表の症状で止まります。

| 条件 | 満たさないときの症状 | パターンでの扱い |
|---|---|---|
| (1) `selection=ATIME` では、アーカイブのステートマシンのロールが ONTAP REST 関数を呼べる（`lambda:InvokeFunction`） | 候補の選択で権限エラーになる | ロールに ONTAP REST 関数の呼び出しを許可する |
| (2) FSx for ONTAP の管理エンドポイントの証明書は、公的な認証局の署名ではない | `CERTIFICATE_VERIFY_FAILED` | パラメーター `OntapVerifySsl`（既定 `false`）で検証の有無を選ぶ。`false` の間は相手を認証しない接続で、経路は VPC 内に限る |
| (3) 復元要求の二重投入は HTTP 409 `RestoreAlreadyInProgress` で返り、Step Functions の SDK 統合はこれを `S3.S3Exception` で返す | `S3.RestoreAlreadyInProgressException` の `Catch` に一致せず、実行が失敗する | `S3.S3Exception` を受けて完了待ちへ進む |
| (4) ステートマシンのログ出力に、ログの配信先への権限（`logs:CreateLogDelivery` など）が要る | デプロイが `The state machine IAM Role is not authorized to access the Log Destination` で失敗する | ロールに配信の権限を付ける |
| (5) `s3:ListBucket` のない主体は、存在しないキーの `HeadObject` が 404 でなく 403 になる | 削除の再試行と `reconcile` が失敗する | delete 関数と restore 関数に、IAM と Access Point のポリシーの両方で `s3:ListBucket` を付ける |
| (6) Amazon CloudWatch のアラームから KMS 暗号化の SNS トピックへ発行するには、キーとトピックの両方のポリシーに `cloudwatch.amazonaws.com` が要る | `CloudWatch Alarms is not authorized to perform: SNS:Publish` で通知が出ない | 両方のポリシーに許可を入れる |
| (7) ステートマシンに `ecs:runTask.sync` の状態があると、ロールの `events:PutRule` などが作成時に検査される（Fargate を使わなくても） | `is not authorized to create managed-rule` でデプロイが失敗する | 許可を `UseFargate` の条件の外に置く |

### まだ確かめていないこと

- 多数のファイルでの所要時間と料金。S3 のリクエスト数（リクエストメトリクスを有効にしていない）
- `Standard` と `Bulk` の復元の完了待ち（実機では `Expedited` のみ）。復元が要る 2 クラスのうち、通したのは S3 Glacier Flexible Retrieval だけ
- 5 GiB を超えるファイルの戻した後の照合（Fargate の経路）。除外と承認を確かめる通しは最大 1 MiB で、Fargate のタスクは 0 件だった。5.5 GiB を含む 7 ファイルの通しの 5.5 GiB の戻しは、SHA-256 が事前に NFS で記録した値と一致したことまで。Fargate の戻した後の照合の経路は単体テストだけ
- 2 つ目の主体による承認。除外と承認を確かめる通しは、同じ SSO の主体が別の ARN を申告して受理側を確かめた。主体の単位の分離は、IAM と CloudTrail の設計による
- 削除の再試行と再開（`DELETING` と同じ `claimedBy`）の実機での通し。この経路は単体テストだけ
- 承認の期間（`ApprovalValidityHours`）の超過と、ウォッチドッグが古いトークンを消す動作（単体テストのみ）
- `ApprovalPendingAlarm` が実際に ALARM になるまでの待ち（メトリクスが出ていることだけを確認）
- `S3.SlowDownException` の再試行。SDK 統合が返す名前を観測していない。復元要求の二重投入（前提条件の (3)）と同じ型の食い違いが起きる恐れがある
- AWS CloudTrail のデータイベントでの削除の記録（実行したアカウントのトレイルが、対象の Access Point のデータイベントを含むかを確認していない）
- 50 GiB を超えるファイルの写し（マルチパートコピー）と、バケットからの直接のダウンロード。実測は 5.5 GiB まで。51 GiB の疎ファイルが選択から外れることだけを確かめた
- NTFS ボリューム、root 以外のファイルシステムユーザー、第 2 世代、Multi-AZ、Access Point にポリシーを付けない場合の動作
- 戻し先に同名のファイルがある場合の経路（実行していない）
- 送り終えた東京の S3 Standard の写しを S3 Glacier Deep Archive に変える操作（ライフサイクルの遷移か再コピー）と、その間の保管料金
- 通知先を SQS などにした承認の流れ（通しでは SNS の通知と Parameter Store のトークンで、承認と拒否を行った）
- レプリケーションが S3 Glacier Deep Archive のオブジェクトを複製しなかった理由。ドキュメントは、このクラスのオブジェクトを複製しないと書いている（[複製しないもの](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication-what-is-isnot-replicated.html)）

### 他の仕組みと組み合わせる経路

| 経路 | 組み合わせ | 担うこと | 引き受けること |
|---|---|---|---|
| A | 移す前に、AWS Backup で FSx for ONTAP のボリュームをバックアップする | 消す前の安全網。消したファイルは、ボリュームのバックアップから戻せる。別リージョン、別アカウントへのコピーも記載がある | バックアップの保管料金がかかる。戻すのはボリューム単位。復元先の扱いは、本調査では読んでいない。ボリュームのスナップショットや SnapMirror の宛先が既にあるなら、それらも消す前の安全網になりうるが、消した後の状態は確かめていない（上の「消した結果が及ぶ範囲」）。バックアップ用スナップショットでボリュームの SSD 使用率が 98% を超えると、バックアップは失敗すると記載されている |
| B | アーカイブ用のクラスを S3 Glacier Instant Retrieval にし、アーカイブ用のバケットを AWS Backup か Clumio で守る（Clumio は、公式サイトとドキュメントの記載が食い違うため、使う前に製品側へ確認が要る） | バケットの 2 つ目の写し、別アカウントへの写し、復元テスト（AWS Backup の Restore testing） | 保管料金は復元が要る 2 クラスより高い。バックアップのたびに取得料金がかかると AWS Backup が記載している。AWS Backup はバージョニングを必須にしている |
| C | 復元が要る 2 クラスに置き、2 つ目の写しは移す時点で作る（手順は「[2 つ目の写しの作り方](#2-つ目の写しの作り方)」） | バックアップ製品が扱えないクラスでも、2 つ目の写しを持てる | 別のリージョンへの直接のコピーは、試した 1 つの Access Point（インターネット起点）では `AccessDenied` だった。原因は未区別。東京のバケットへ S3 Standard で写してから送ったので、その間の保管料金がかかる。同じリージョンの別バケットへの 2 つ目の写しは、通しの実行で成功した（7 ファイル）。別のリージョンへ送る手順は、通しでは試していない |
| D | 選別をデータ管理ソフト（Komprise など）に任せ、照合と削除をこの仕組みが担う | 多くの NAS を横断した分析と選別 | データ管理ソフトは NFS か SMB でマウントする構成になる。2 つの台帳をつなぐ必要がある |

経路 B と C の使い分けは、保管料金の差と、2 つ目の写しをどう管理するかで決まります。Clumio の保管庫（SecureVault）の料金は、公式の料金ページに載っています（[Clumio の料金](https://www.clumio.com/pricing)、日付とリージョンの記載はありません）。

## 選び方

| # | 確認すること | 判断 |
|---|---|---|
| 0 | データを使うアプリケーションが、古いデータの退避や階層化を自分で持つか | 持つなら、ファイルを外から動かす前に、そのアプリケーションの機能を検討する（データベースのデータや表形式のデータをファイル単位で移さない理由は、[ファイル単位で移してはいけないデータ](../../domains/data-utilization/notes/archive-use-cases-and-integrations.md#ファイル単位で移してはいけないデータ)） |
| 1 | 移した後も、利用者がファイルを元のフォルダーで開く必要があるか | 必要ならボリュームの階層化を選ぶ。スタブで見せたいなら、マウントして被せるデータ管理ソフト（Komprise の動的リンクなど）を選ぶ。S3 API だけの仕組みはファイルを消すので向かない |
| 2 | 容量プールの保管料金で足りるか | 足りるなら階層化で終わる。足りないなら、S3 Glacier 系のクラスへ移す仕組みを選ぶ |
| 3 | 戻すまでに何時間待てるか | Instant Retrieval は復元が要らない。Flexible Retrieval は迅速で 1〜5 分、標準で 3〜5 時間、大容量で 5〜12 時間（AWS のドキュメントの目安）。Deep Archive は標準で 12 時間以内、大容量で 48 時間以内 |
| 4 | アーカイブ用のバケットを、バックアップ製品で守る必要があるか | 必要なら、S3 Glacier Instant Retrieval に置いて経路 B を選ぶ。復元が要る 2 クラスに置くなら、経路 C で 2 つ目の写しを自分で作る（同じリージョンの別バケットへの写しは通しで確認。別のリージョンへ送る手順は通しでは未確認） |
| 5 | ボリュームをマウントするホストを置けるか | 置けるなら、DataSync やデータ管理ソフトも選べる。ファイルの読み書きと削除を S3 API だけで済ませたいなら、S3 API だけの仕組みが候補になる。ただし、最終アクセス時刻で選ぶなら ONTAP REST API への到達性が要り、戻した後の所有者、モード、更新時刻の付け直しは、NFS でボリュームをマウントしたホストで、生成されたスクリプトを実行する |
| 6 | 消す前に照合と人の承認を必ず挟む必要があるか | 必要なら、Archivematica のような 2 段階の削除を持つ保存システム、AWS DataSync（検証つきの転送）に照合の結果の確認と削除を自前で足す組み立て、S3 API だけの仕組み（パターン。この資料の実装は一例）が選択肢になる。iRODS は、検証をチェックサムに設定すれば、照合してから元を消す。ただし人の承認の段階は、読んだ範囲に記載がない。ほかの製品では、照合と承認の両方の記載がない |
| 7 | 長期保存の手順（定期の再検証、標準のメタデータ）が求められるか | 求められるなら、デジタル保存システムを選ぶか、組み合わせる |

## よくある誤解

| 誤解 | 実際 |
|---|---|
| バックアップ製品に任せれば、アーカイブ用のバケットも守れる | 復元が要る 2 クラスのオブジェクトは、AWS Backup、Clumio、Commvault、Veeam が対象外と書き、Druva は Flexible Retrieval を読み飛ばすと書いている。S3 のレプリケーションも複製しない |
| FSx for ONTAP の階層化を使えば、S3 Glacier Deep Archive まで下げられる | 容量プールは AWS が管理する保管領域で、利用者が階層先のバケットやクラスを選ぶ方法は、読んだ FSx for ONTAP のユーザーガイドに記載がなかった。ONTAP の FabricPool は、オンプレミスでも S3 Glacier Flexible Retrieval と S3 Glacier Deep Archive を対象にしていない |
| ファイルを消せば、すぐにボリュームの容量が空く | ランダムデータの 1 GiB、ストレージ効率化ありのボリューム、1 回の実測では、スナップショットがある間、使用量は約 800 MiB 減っただけで、作成前の水準には戻らなかった。戻ったのは、そのスナップショットを消した後だった。スナップショットなしの対照と、圧縮できるデータでの結果と、移した後に容量が空くまでの時間は測っていない |
| S3 API で照合するなら、ETag を比べればよい | FSx for ONTAP の S3 Access Points の ETag は MD5 ではなく、ボリューム側にチェックサムも保存されない。元のファイルを一度読んでハッシュを計算する |
| S3 API で、使われていないファイルを選べる | `LastModified` は更新時刻で、最後に読まれた日時は返らない。最後に読まれた日時は ONTAP REST API か NFS で読む |

## 比較時点

2026-11-26 に閲覧した公開ページの情報です。4 つの領域（FUSE と OSS、データ管理ソフトと SaaS、ハードウェアとテープと保存システム、バックアップ製品）を調べました。調査記録の表の行で数えて 62 行です（同じ製品が 2 つの領域に出るものは、重複して数えています）。読めなかったページは 48 件ありました（ログインが必要、HTTP 403、本文を取得できないもの）。読めなかったページの内容は、この資料の判断に使っていません。この資料の表に載せたのは、復元が要る 2 クラスや元の扱いで比較できた製品です。載せていない製品（オブジェクトストレージとテープのライブラリー、IBM Storage Deep Archive と HPE Data Management Framework のように公式ページを読めなかったものなど）の結果は、この資料に書いていません。版が古い資料だけで書いた記述（IBM Storage Scale の Transparent Cloud Tiering は 2018 年の資料）は、現行版で同じかを確かめていません。

## 関連ドキュメント

- [S3 Access Points のサーバー側コピーの用途](../../domains/data-utilization/notes/s3-access-points-server-side-copy-use-cases.md) — ストレージクラスごとの往復の実測、復元にかかった時間、アーカイブの往復の費用
- [ファイルを消して S3 Glacier 系へ移す用途と連携先](../../domains/data-utilization/notes/archive-use-cases-and-integrations.md) — 業界別の用途、保持規則の例、連携先と流れの段階の対応、自環境での始め方
- [S3 Access Points の制約](../../domains/data-utilization/notes/s3-access-point-constraints.md)
- [階層化ポリシーの比較](tiering-policies.md)
- [データ保護方式の比較](data-protection-methods.md)
