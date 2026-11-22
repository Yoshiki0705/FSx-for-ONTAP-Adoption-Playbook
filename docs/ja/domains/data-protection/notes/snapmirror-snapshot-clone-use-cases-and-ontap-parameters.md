---
title: SnapMirror・スナップショット・クローンの使われ方は 3 つの出発点に分かれ、コンソールで初めて見える ONTAP のパラメーターは 6 組ある
lifecycle: [assess, design]
domains: [data-protection, data-utilization]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/scheduled-replication.html
lang: ja
---

# SnapMirror、スナップショット、クローンは、誰がどの場面で使い、何を決めればよいか？

出発点は、オンプレミスの ONTAP、これから FSx for ONTAP を使う、すでに FSx for ONTAP を使っている、の 3 つです。決めるのは、ピアリング、ポリシー、保持の 3 層です。

## このノートで学べること

- 公開されている資料から読み取れる、SnapMirror、スナップショット、クローンの使われ方（出発点ごと）
- 連携する AWS サービスと他の製品の一覧と、各連携の根拠が公式資料か、このリポジトリの実測か
- コンソールの SnapMirror、スナップショット、ピアリングの画面に出る ONTAP のパラメーター 6 組と、決め方の考え方、読むべき NetApp の資料
- 他の方式（AWS Backup、AWS DataSync、FlexCache）との選び分け

## このノートが答えないこと

- 各事例の効果の大きさ。資料にある数値は、その資料の環境での値で、引用元の記述として扱う
- コンソールの操作手順（[手順のノート](console-snapmirror-needs-the-svm-peer-on-the-destination-side.md)）
- 法令や規制への適合の判断。保存と複製の設計は、要件への適合を保証しない

## 前提レベル

intermediate

## 本文

> **区分**: `documented`（2026-11-22 に公式の資料を読んで整理）— 事例は公開された資料の記述で、このリポジトリでは再現していません。再現した部分は、各表の「このリポジトリの実測」の列に書きます。人や組織の名前は書かず、資料へのリンクで示します。

### 想定する読み手と、読む順序

| 読み手 | 最初に読む節 | 次に読むもの |
|---|---|---|
| オンプレミスの ONTAP を運用している | 出発点 1 | [コンソールの手順](console-snapmirror-needs-the-svm-peer-on-the-destination-side.md)、ONTAP のパラメーターの節 |
| これから FSx for ONTAP を使う | 出発点 2 | [第 3 世代の上限](../../performance/notes/third-generation-file-systems-and-where-the-sources-disagree.md) |
| すでに FSx for ONTAP を使っている | 出発点 3 | [クローンから S3 Access Points まで](../../data-utilization/notes/a-console-clone-attaches-s3-access-points-in-minutes.md) |
| AI エージェント | 各表の「根拠」と「このリポジトリの実測」の列 | 一次資料のリンク |

### 出発点 1: オンプレミスの ONTAP の運用

| 場面 | 仕組み | 根拠（公式の資料） | このリポジトリの実測 |
|---|---|---|---|
| クラウドへの災害復旧 | オンプレミスのボリュームを FSx for ONTAP に SnapMirror で複製し、被災時に昇格する | [AWS の移行手順](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/migrating-fsx-ontap-snapmirror.html)、[VMware Cloud on AWS の災害復旧](https://aws.amazon.com/blogs/apn/vmware-cloud-on-aws-disaster-recovery-with-amazon-fsx-for-netapp-ontap-and-snapmirror/) | なし |
| クラウドへの移行 | 初回転送のあと差分を更新し、切り替え時に関係を解除する。重複排除と圧縮の状態は転送でも保たれ、元のスナップショットも移る | [AWS の移行手順](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/migrating-fsx-ontap-snapmirror.html) | なし |
| 仮想化基盤の災害復旧 | NFS データストアの ONTAP ボリュームを複製し、VM の登録とネットワークの対応を手順化する | [NetApp の解説](https://www.netapp.com/learn/aws-fsxo-blg-disaster-recovery-orchestrator-dro-a-scripted-solution-with-vmware-cloud-on-aws-and-amazon-fsx-for-netapp-ontap/) | なし |
| データベースの高可用性と災害復旧 | SQL Server のフェイルオーバークラスターのストレージを FSx for ONTAP にし、SnapMirror で別の場所へ複製する | [NetApp の解説](https://www.netapp.com/blog/sql-server-always-on-fci-fsx-ontap/) | なし |
| 設計業務の計算をクラウドへ広げる | SnapMirror ではなく FlexCache で、オンプレミスの元ボリュームとクラウドのキャッシュを双方向に結ぶ | [AWS の参照アーキテクチャ](https://docs.aws.amazon.com/reference-architecture-diagrams/latest/electronics-hpc/cloud-bursting-eda-fsx-netapp-ontap.html) | FlexCache の別の記録あり（[Lakehouse の対応表](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations)） |

**コンソールで変わる点:** これまで、AWS 外の ONTAP を相手にするクラスターピアと関係の作成は、ONTAP の CLI や NetApp 側の管理ツールで行う場面が中心でした（ユーザーガイドの SnapMirror の節もそう書いています）。コンソールに、相手のクラスター間 IP アドレスと `SVM 名:ボリューム名` を入れる画面ができました。AWS 外の相手への作成は、まだ実機で確かめていません。

### 出発点 2: FSx for ONTAP の新規利用

| 場面 | 仕組み | 根拠 | このリポジトリの実測 |
|---|---|---|---|
| 別リージョンへの災害復旧 | 2 つの FSx for ONTAP の間で SnapMirror。宛先は Single-AZ にして費用を抑える構成も記載されている | [AWS Storage Blog](https://aws.amazon.com/blogs/storage/cross-region-disaster-recovery-with-amazon-fsx-for-netapp-ontap) | 同一リージョン内の 2 つで、作成から転送成功まで |
| 別アカウントへの隔離したバックアップ | 本番と別のアカウントのファイルシステムに SnapMirror で複製し、バックアップ製品が管理する | [AWS Prescriptive Guidance（SAP HANA とバックアップ製品）](https://docs.aws.amazon.com/prescriptive-guidance/latest/accelerate-sap-hana-recovery-with-f-sx-for-ontap/f-sx-for-ontap-as-the-storage-solution.html) | 別アカウントは未実施 |
| 開発とテストの環境更新 | 本番ボリュームのスナップショットから FlexClone を作り、環境を短時間で更新する | [AWS Storage Blog](https://aws.amazon.com/blogs/storage/accelerate-development-refresh-cycles-and-optimize-cost-with-amazon-fsx-for-netapp-ontap-cloning/) | [コンソールのクローン](../../data-utilization/notes/a-console-clone-attaches-s3-access-points-in-minutes.md) |
| データベースのレプリケーションとクローン | SAP HANA や Oracle のボリュームを複製し、複製先でクローンを作る | [SAP HANA](https://aws.amazon.com/blogs/storage/replicate-and-clone-sap-hana-databases-with-amazon-fsx-for-netapp-ontap/)、[Oracle と Amazon EVS](https://repost.aws/articles/AR3bnQsABSSIS0J8pO8mIUCA/oracle-database-deployment-on-amazon-evs-and-fsx-for-netapp-ontap-best-practices) | なし |

### 出発点 3: FSx for ONTAP の既存利用

| 場面 | 使う機能 | 今回の更新で変わる点 |
|---|---|---|
| 既存の SnapMirror 関係の確認 | 一覧画面 | ONTAP に入らなくても、関係、ピア、ポリシーを AWS の画面で見られる。東京の第 1 世代でも表示された |
| スナップショットの保持の見直し | スナップショットポリシー | コンソールでポリシーを作り、ボリュームに名前で指定できる。これまでは ONTAP の CLI か REST API |
| 開発環境の更新の自動化 | クローンと S3 アクセス | AWS 側で作ると、API に現れるまでの待ちが観測されなかった（1 回） |
| 性能の増設 | 第 3 世代（HA ペアの追加、スループットの変更） | 第 3 世代は米国 3 リージョンで作成を受け付けた。既存の第 1・第 2 世代からの移行は、SnapMirror、AWS DataSync、バックアップからの復元のいずれかで、デプロイタイプは変更できない |

### 連携する AWS のサービスと他の製品

次の表は、「どのシステムが、どの機能の出力を、どの経路で使うか」です。**根拠の列が公式の資料なら、そのリポジトリでは実測していません。**

| 連携先の種類 | 使う機能 | データの経路 | 根拠 | このリポジトリの Spoke |
|---|---|---|---|---|
| 分析（Athena、Glue、Redshift、Quick） | S3 Access Points | S3 API でボリュームを読む | [AWS: アクセスポイントと AWS サービス](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-access-points-with-aws-services.html) | [S3AccessPoints-Serverless](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns)、[Lakehouse](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) |
| 機械学習と生成 AI（SageMaker、Bedrock） | S3 Access Points | 同上。RAG の取り込み | [AWS Machine Learning Blog](https://aws.amazon.com/blogs/machine-learning/build-rag-based-generative-ai-applications-in-aws-using-amazon-fsx-for-netapp-ontap-with-amazon-bedrock/) | [Agentic-Access-Aware-RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) |
| データ基盤の SaaS（Snowflake、Databricks） | S3 Access Points | S3 互換 API で読む | [NetApp の解説](https://www.netapp.com/blog/data-access-s3-access-points-fsx-ontap/) | [Lakehouse](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) |
| 仮想化基盤（Amazon EVS、VMware Cloud on AWS） | NFS データストア、SnapMirror | データストアとして使い、複製で災害復旧 | [Oracle と Amazon EVS](https://repost.aws/articles/AR3bnQsABSSIS0J8pO8mIUCA/oracle-database-deployment-on-amazon-evs-and-fsx-for-netapp-ontap-best-practices) | [VMware-Migration](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) |
| バックアップ製品 | スナップショット、SnapMirror | 製品がスナップショットを制御し、別アカウントへ複製 | [AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/accelerate-sap-hana-recovery-with-f-sx-for-ontap/implementation.html) | [Cyber-Resilience](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns) |
| コンテナ（Amazon EKS） | ボリューム、スナップショット、クローン | CSI 経由でスナップショットとクローンを作る | [AWS Storage Blog](https://aws.amazon.com/blogs/storage/run-containerized-applications-efficiently-using-amazon-fsx-for-netapp-ontap-and-amazon-eks/) | [Container-Datastore](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) |
| 監視（Amazon CloudWatch） | ファイルシステムとボリュームのメトリクス | 容量とレプリケーションの監視 | [CloudWatch の記述](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-cloudwatch.html) | [Observability](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) |

### コンソールで初めて見える ONTAP のパラメーター

FSx for ONTAP では、これらを ONTAP の CLI や REST API で扱う場面が多く、AWS の画面で入力を求められるのは今回が初めてです。ONTAP の資料は、バージョンによる差があるので、ONTAP の版を確かめてから読んでください。

| 画面の項目 | ONTAP での意味 | 決め方の考え方 | 読む資料 |
|---|---|---|---|
| クラスターピアのパスフレーズ、クラスター間 IP | 2 つのクラスターが信頼しあうための共有の合言葉と、クラスター間通信用の LIF（インタークラスター LIF）の住所。通信は TLS の事前共有鍵で暗号化される（画面の説明） | 両側で同じパスフレーズを使う。AWS 外とつなぐときは、クラスター間 IP 宛ての通信を通す経路と許可ポートが先に要る | [NetApp: クラスターピアの作成](https://docs.netapp.com/us-en/ontap/peering/create-cluster-relationship-93-later-task.html) |
| SVM ピアのアプリケーション | その SVM 間で許す機能（SnapMirror、FlexCache、ファイルコピー、LUN コピー）。両側が同じものを許可する | 使う機能だけを許可する。後から更新できる（画面の説明） | [NetApp: ONTAP のピアリング](https://docs.netapp.com/us-en/ontap/peering/index.html) |
| SnapMirror ポリシーのコピーモード | ポリシーの種類。非同期ミラー（災害復旧）、ボールト（長期保管）、ミラーとボールトの統合（unified replication）がある | 災害復旧だけなら非同期ミラー。同じ宛先で履歴も残すなら統合型 | [NetApp: カスタムのレプリケーションポリシー](https://docs.netapp.com/us-en/ontap/data-protection/create-custom-replication-policy-concept.html)、[既定のポリシー](https://docs.netapp.com/us-en/ontap/data-protection/default-protection-policies-concept.html) |
| リテンションルール（SnapMirror ラベル、カウント） | 統合型やボールトで、宛先に残すスナップショットを、ラベルが一致するものに絞り、ラベルごとに保持数を決める | 送信元のスナップショットポリシーのラベルと、宛先のルールのラベルを一致させる。一致しないスナップショットは宛先に残らない | [NetApp: 統合レプリケーション](https://docs.netapp.com/us-en/ontap/data-protection/snapmirror-unified-replication-concept.html) |
| 転送スケジュール、スロットル、ネットワーク圧縮 | 転送の頻度（ONTAP のジョブスケジュール名）、帯域の上限（KB/s、0 は無制限）、転送中の圧縮 | 目標復旧時点（RPO）から頻度を決める。AWS 外とつなぐ回線では、スロットルと圧縮が効果を持つ。圧縮は CPU の使用が増える（画面の説明） | [NetApp: snapmirror policy create](https://docs.netapp.com/us-en/ontap-cli/snapmirror-policy-create.html) |
| スナップショットポリシーのスケジュール、プレフィックス、SnapMirror ラベル | いつ、何世代、どんな名前の接頭辞とラベルでスナップショットを作るか。スケジュール名は ONTAP のジョブスケジュール（`5min`、`hourly`、`daily` など） | 保持は「数日でローテーションする」特性を持つ。[版の保存に使うと消える](../../data-utilization/notes/dataset-versions-and-experiment-branches.md)ので、保持の用途を先に決める | [AWS: スナップショットポリシー](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snapshots-ontap.html) |

**FSx for ONTAP 側の制約:** ユーザーガイドによると、サポートされるのはボリューム単位の SnapMirror で、SVM 単位の災害復旧（SVMDR）と同期型（StrictSync を含む）はサポートされません（2026-11-22 に読んだ）。

### 他の方式との選び分け

| 方式 | 向く場面 | その方式の制約 |
|---|---|---|
| SnapMirror | ボリューム単位で、頻繁に差分を複製する。ONTAP の相手（オンプレミス、他のクラウド、別の FSx for ONTAP）と複製する | 相手も ONTAP。ボリューム単位のみで、同期型は使えない。ピアリングの経路とポリシーの設計が要る |
| Amazon FSx のバックアップと AWS Backup | AWS で完結する世代管理。ONTAP の知識が少なくても運用できる | 複製先は AWS のバックアップの仕組みの中。ONTAP のボリュームとして直接読めない |
| AWS DataSync | ONTAP 以外の NAS からの移行、ファイル単位の同期 | ファイル単位の複製で、ボリュームのスナップショットの履歴は移らない |
| FlexCache | 元のボリュームを残したまま、遠い場所から読み取りを速くする | 複製ではなくキャッシュ。バックアップや災害復旧の代わりにならない |

**選び方:** 複製の目的が「別の場所で ONTAP のボリュームとして使い続ける」なら SnapMirror、「AWS の運用の中でまとめて世代管理する」ならバックアップ、「ONTAP 以外から移す」なら DataSync、「読み取りを近づける」なら FlexCache、と目的から選びます。

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 目的を「災害復旧」「別アカウントの隔離」「環境更新」「分析への入口」から選ぶ | 上の表のどの行が当てはまるか |
| 2 | 相手が AWS 内か、AWS 外の ONTAP かを決める | クラスターピアの 2 つの方法のどちらを使うか |
| 3 | 目標復旧時点と保持日数から、転送スケジュールとリテンションルールを決める | ポリシーの値 |
| 4 | [コンソールの手順](console-snapmirror-needs-the-svm-peer-on-the-destination-side.md)の順に作り、空のボリュームで最初の転送を確かめる | ピアリングと権限が通っていること |

### 期待結果

```text
手順 4: 関係の状態が SnapMirrored になり、転送の状態が success になる
```

## Read next

[コンソールの SnapMirror は、SVM ピアを宛先側から作らないと関係を作れない](console-snapmirror-needs-the-svm-peer-on-the-destination-side.md)
