# Domain — データ活用 (Data Utilization)

---

NAS 上のデータを、コピーを増やさずに分析・AI・アプリケーションから使うための知見です。

---

## 最初に読むもの

**手元にある材料から、次に読む 1 ページを決めます。** 下の「扱う問い」は目次で、これは入口です。

| 手元にあるもの | 最初に読むもの | そこで分かること |
|---|---|---|
| **S3 API で読み書きしたい** | [FSx for ONTAP S3 AP は「S3 として使える」わけではない](notes/s3-access-point-constraints.md) | **同一アカウント・同一リージョンなどの前提が設計段階の制約になります** |
| **AI / RAG に載せたい** | [権限が平坦化されることの意味](notes/reaching-data-without-copies.md#権限が平坦化されることの意味) | **元の ACL は引き継がれません。** 判定を索引側に設計する必要があります |
| **コピーを増やしたくない** | [コピーを増やさない 3 つの手段](notes/reaching-data-without-copies.md#コピーを増やさない-3-つの手段) | 3 つの手段と、それぞれが引き受ける制約 |
| **複製先を分析基盤から読みたい** | [SnapMirror の宛先は break せずに S3 API で読める](notes/serving-a-replication-destination-over-s3.md) | **break は不要です。** 止めているのは junction path であってボリューム種別ではありません |
| **クローンをすぐ S3 Access Points につなぎたい** | [コンソールで作ったクローンは API に即座に現れ、S3 Access Points まで 1 回の観測で約 93 秒](notes/a-console-clone-attaches-s3-access-points-in-minutes.md) | **遅れるのは ONTAP 側で作ったクローンです。** コンソールで作る経路は、クローンと S3 アクセスを 1 回の操作で指定できます |
| **ファイルの到着でパイプラインを起動したい** | [FPolicy が適合するかは、データをどう読むかではなく、どう書くかで決まる](notes/fpolicy-fits-by-how-writes-land.md) | **判定は書き込みが着地するプロトコルです。** 読む側は入りません |
| **ゲノム / HPC の解析データをどこに置くか迷う** | [ゲノム・HPC パイプラインのデータは 3 か所に分かれる](notes/where-genomics-pipeline-data-lives.md) | **マネージドなオブジェクトストアは POSIX 共有ファイル層を置き換えません。** 共有層を自分で用意するかは実行基盤ごとに違います（HealthOmics の run は自前で提供） |
| **バケットとボリュームの間でファイルを写したい、アーカイブしたい** | [S3 Access Points のサーバー側コピーは、どの用途で使い、どの用途で使わないか](notes/s3-access-points-server-side-copy-use-cases.md) | **直接読めるなら、コピーは要りません。** 属性は写らず、S3 Glacier 系から戻すときは先に復元が要ります |
| **めったに読まれないファイルを S3 Glacier 系へ移して消してよいか、業界ごとに知りたい** | [ファイルを消して S3 Glacier 系へ移す用途は戻しを待てるデータに限られ、連携できる AWS サービスの多くはバケット側にしか届かない](notes/archive-use-cases-and-integrations.md) | **戻しを数時間から 48 時間待てて、元のパスで開く必要のないデータが合います。** 連携できる AWS サービスの多くは、Access Points ではなくアーカイブ用のバケットにしか届きません |
| **S3 Files のバケットと FSx for ONTAP の間で、選んだファイルを渡したい** | [S3 Files のバケットと FSx for ONTAP のボリュームをサーバー側コピーでつなぐ](notes/s3-files-and-access-points-bridged-by-copy.md) | **属性は既定では写りません。** 反映の待ちは、ボリュームから S3 Files へ約 1.5 秒、S3 Files からボリュームへ約 60 秒 |
| **S3 Access Points で受け入れたファイルを NFS か SMB で読みたい（プロトコルの版を選びたい）** | [S3 Access Points で書いたファイルを NFS と SMB で読むまで、プロトコルの版とクライアントのキャッシュでどれだけ違うか](notes/s3-access-points-write-read-over-nfs-versions.md) | **新しいファイルは NFS でも SMB でも数 ms で読めました。** NFSv3 の既定のマウントでは新しいディレクトリの最初の 1 件が約 28 秒遅れ、UNIX ボリュームを Linux の既定のオプションで SMB マウントすると、10 ms ごとに開き直す読み方では上書きが 120 秒以内に見えませんでした |
| **クロスクラウド / クロスリージョンで分析したい** | [クロスクラウド分析でコピーを増やさない](notes/cross-cloud-analytics-without-extra-copies.md) | 書き込みはローカルに寄せ、クロスな依存は読み取り側に。**他クラウド ONTAP との FlexCache は、公式ドキュメントに記載はあるが実機の公開記録がない** |

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | S3 API 経由のアクセスで何ができ、何ができないか | [FSx for ONTAP S3 AP は「S3 として使える」わけではない](notes/s3-access-point-constraints.md) |
| 2 | 分析基盤にどう接続するか | [分析基盤への接続](notes/reaching-data-without-copies.md#分析基盤への接続) |
| 3 | AI / RAG で権限をどう扱うか | [権限が平坦化されることの意味](notes/reaching-data-without-copies.md#権限が平坦化されることの意味) |
| 4 | データコピーを増やさない設計とは | [コピーを増やさない 3 つの手段](notes/reaching-data-without-copies.md#コピーを増やさない-3-つの手段) |
| 5 | 読み取り加速をどこで効かせるか | [FlexCache が効く条件](notes/reaching-data-without-copies.md#flexcache-が効く条件) |
| 6 | エンドユーザーにブラウザや SFTP で見せる経路はどれか | [エンドユーザーがデータに届く経路は 4 つある](../../playbooks/02-design/notes/how-end-users-reach-the-data.md) |
| 7 | AI / ML の学習データセットの版と実験ブランチをどう扱うか | [学習データセットの版をスケジュール Snapshot に載せると消える](notes/dataset-versions-and-experiment-branches.md) |
| 8 | 書いたものが反対側で見えるまでどれくらいか。方向で違うか | [書いた側と読む側が違うと、見えるまでの時間は方向で決まる](notes/how-long-until-a-write-is-visible.md) |
| 9 | 複製先のデータを分析基盤に読ませられるか。SnapMirror を止める必要はあるか | [SnapMirror の宛先は break せずに S3 API で読める](notes/serving-a-replication-destination-over-s3.md) |
| 10 | ファイルの到着をイベントとして受け取れるか。FPolicy が使えるのはどの場合か | [FPolicy が適合するかは、データをどう読むかではなく、どう書くかで決まる](notes/fpolicy-fits-by-how-writes-land.md) |
| 11 | ゲノム / HPC の解析データはどこに置かれるか。実行基盤ごとに共有ファイル層を自分で用意する必要はあるか | [ゲノム・HPC パイプラインのデータは 3 か所に分かれる](notes/where-genomics-pipeline-data-lives.md) |
| 12 | クロスクラウド / クロスリージョンでコピーを増やさず分析するには | [クロスクラウド分析でコピーを増やさない](notes/cross-cloud-analytics-without-extra-copies.md) |
| 13 | クローンを分析基盤につなぐまでの待ち時間は、作る経路で変わるか | [コンソールで作ったクローンは API に即座に現れ、S3 Access Points まで 1 回の観測で約 93 秒](notes/a-console-clone-attaches-s3-access-points-in-minutes.md) |
| 14 | バケットとボリュームの間のサーバー側コピーは、どの用途で使い、どの用途で使わないか | [S3 Access Points のサーバー側コピーは、どの用途で使い、どの用途で使わないか](notes/s3-access-points-server-side-copy-use-cases.md) |
| 15 | S3 Files のバケットと FSx for ONTAP のボリュームの間でファイルを写すと、何が写り、どれだけ待つか | [S3 Files のバケットと FSx for ONTAP のボリュームをサーバー側コピーでつなぐ](notes/s3-files-and-access-points-bridged-by-copy.md) |
| 16 | S3 Access Points で書いたファイルを NFS と SMB で読むまで、プロトコルの版とクライアントのキャッシュでどれだけ違うか | [S3 Access Points で書いたファイルを NFS と SMB で読むまで](notes/s3-access-points-write-read-over-nfs-versions.md) |
| 17 | めったに読まれないファイルを S3 Glacier 系へ移して消す流れは、どの業界の用途に合い、どの AWS サービスや製品とつながるか | [ファイルを消して S3 Glacier 系へ移す用途は戻しを待てるデータに限られ、連携できる AWS サービスの多くはバケット側にしか届かない](notes/archive-use-cases-and-integrations.md) |

---

## 動く実装 — sibling リポジトリ

このモジュールの知見を実装したリファレンスアーキテクチャです。知見だけでは判断しにくい「実際にどう組むか」を示します。

| プロジェクト | 何ができるか | 技術スタック |
|---|---|---|
| [S3 Burst on ONTAP Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) | S3 API でデータを収集し、FlexCache の NFS/SMB で利用する。コピージョブなし、反映 p50 8 ms。HiL テストベンチ・EDA・レンダリング・IoT に向く | CFn + SAM。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-s3burst-flexcache-collect-s3-consume-files)。続編: [Part 2（3 つの経路の天井）](https://hakobiya.hatenablog.com/entry/fsxn-s3burst-throughput-ceilings-three-paths)、[S3 Files の速さと月額の実測](https://hakobiya.hatenablog.com/entry/fsxn-s3files-value-measured)（English: [dev.to](https://dev.to/aws-builders/i-measured-the-speed-and-monthly-cost-of-amazon-s3-files-which-lets-you-use-s3-as-files-and-how-1970)） |
| [ファイルポータル UI (Amplify Gen2)](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/amplify-portal) | NAS 上のファイルに VPN なしでブラウザアクセス + AI 処理（分類・異常検知・セマンティック検索）。Nextcloud との併用も可能 | Amplify Gen2 + Bedrock。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-file-portal-1-browser-access) |
| [Lakehouse 連携](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) | Athena / Glue / Spark から S3 AP 経由でファイルを分析。データは NAS に残したまま | S3 AP + Glue / Athena |
| [Agentic RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | 権限を意識した RAG。**元の ACL が引き継がれるのではなく、権限を別の索引に再構成して検索時に判定**します（[平坦化の意味](notes/reaching-data-without-copies.md#権限が平坦化されることの意味)を読んでから） | CDK + Bedrock |

**「このモジュールのノートを読んだが、具体的なコードが欲しい」場合は上のリポジトリに進んでください。** 各リポジトリは独立して deploy 可能で、この Playbook は判断の根拠を、リポジトリは実装を担います。

---

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`notes/`](notes/) | 知見の最小単位。1 ファイル = 1 論点。frontmatter に `evidence` 区分を持ちます |

---

## 読み方

各ノートの frontmatter にある `evidence` を必ず確認してください。

| 区分 | 意味 |
|---|---|
| `verified` | 記載環境で著者が再現済み。`verified_on` に検証日 |
| `documented` | ベンダー / AWS 公式ドキュメントに記載あり。`source` に出典 |
| `field-observation` | 現場で一度観測。再現確認は未実施。一般化しないこと |
| `hypothesis` | 未検証の推論 |

判断基準の詳細は [知見の分類ポリシー](../../evidence-policy.md) を参照してください。

---

## 関連

- [性能実測の所在マップ](../../reference/performance-evidence-map.md) — **NFS / SMB / S3 Access Points / FlexCache の性能は Spoke で実測済みです。** 「性能は未測定」と書く前にここで所在を確認してください
- [プロジェクト間の引用索引](../../reference/cross-repo-index.md) — どの主張をどの Spoke から引いているか
- [ライフサイクル軸で探す](../../navigation.md#ライフサイクル軸--playbooks)
- [比較マトリクス](../../reference/comparison/)
- [ナビゲーションガイド](../../navigation.md)
- [用語集](../../reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/data-utilization/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
