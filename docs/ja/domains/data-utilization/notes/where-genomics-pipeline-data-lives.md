---
title: ゲノム・HPC パイプラインのデータは 3 か所に分かれて置かれる — マネージドなオブジェクトストアが POSIX 共有ファイルシステムを置き換えるわけではない
lifecycle: [design]
domains: [data-utilization, performance]
evidence: documented
source: https://docs.aws.amazon.com/omics/latest/dev/sequence-stores.html
lang: ja
---

# ゲノム・HPC パイプラインのデータはどこに置かれるか

AWS HealthOmics の Sequence Store、Amazon S3、POSIX 共有ファイルシステムは役割が別です。オブジェクトストアは中間解析の共有層を置き換えません。

## このノートで学べること

- ゲノム二次解析の 3 つのデータ置き場（Sequence Store / S3・S3 Tables / POSIX 共有ファイルシステム）の役割の違い
- 実行基盤（AWS HealthOmics / AWS Batch の EC2 と Fargate / 自前の HPC クラスタ）ごとに、POSIX 共有ファイル層を自分で用意する必要があるかどうかが違うこと
- FSx for ONTAP がこの図のどこに入り、どの公開事例が同じ形を採っているか

## このノートが答えないこと

- HealthOmics のワークフロー課金や Sequence Store の階層別ストレージ料金の具体額
- FASTQ / BAM / VCF の具体的なサイズとパイプライン実行時間の実測値（二次解析の性能は[別ノート](../../performance/notes/where-throughput-is-determined-and-shared.md)とワークロード依存）

## 前提レベル

intermediate

## 本文

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — データ活用](../README.md)

---

### 結論

**ゲノムやロングリードの二次解析パイプラインでは、データが役割の違う 3 か所に分かれて置かれます。** どれか 1 つに寄せられるものではありません。

| 置き場 | 役割 | アクセスの形 |
|---|---|---|
| **マネージドなシーケンスストア**（AWS HealthOmics Sequence Store など） | 生のシーケンスデータ（FASTQ / BAM / CRAM）を長期にコスト最適に保管し、ワークフローへ取り込ませる | サービス API 経由の取り込み・参照。**POSIX のファイルパスでマウントして読むものではありません** |
| **オブジェクトストア**（Amazon S3 / S3 Tables） | ワークフローの入出力（BAM / VCF）と、構造化したバリアントのクエリ対象 | S3 API。VCF を S3 Tables に変換するとコホート横断のクエリ性能が上がります |
| **POSIX 共有ファイルシステム**（FSx for ONTAP など） | 複数ホストが同時に読み書きする中間成果物、参照ゲノムやアノテーション DB、ツールが POSIX の入出力を前提とする工程 | NFS / SMB でマウント。複数ホストから同じパスが見えます |

**ここで取り違えやすいのは、マネージドなオブジェクトストアを導入すると共有ファイルシステムが不要になる、という読み方です。** 実際には役割が別で、**同じパイプラインの中で両方が要る場面があります。** Sequence Store は保管と取り込みの層で、解析ツールが数十キロ塩基のロングリードを POSIX のパスで読み書きする工程は別の層です。

> **Evidence**: `documented` — Sequence Store・ワークフロー・S3 Tables の役割は AWS HealthOmics の公式ドキュメントと AWS 公開ブログの記載に基づきます（2026-11-02 に確認）。**FASTQ / BAM / VCF のサイズや実行時間の実測値は含みません。** FSx for ONTAP を POSIX 共有ファイル層として複数ホストから使うときの性能（NFS / SMB の台数試験、S3 Access Points のスループット・レイテンシ）は、Spoke で実測済みです — 所在と測定環境は [性能実測の所在マップ](../../../reference/performance-evidence-map.md) にあります。**本ノートが実測していないのは、ゲノム / HPC という特定ワークロードの end-to-end パイプライン**であって、FSx for ONTAP が共有ファイル層として機能すること自体ではありません。

---

### サーバーレスな実行基盤での共有ファイル層の要否

**実行基盤によって、POSIX 共有ファイル層を自分で用意するかどうかが変わります。** 基盤ごとの扱いは次のとおりです。

| 実行基盤 | 共有ファイル層の扱い | FSx for ONTAP の出番 |
|---|---|---|
| **AWS HealthOmics のワークフロー** | **run ごとに一時的な共有ファイルシステム（run storage）をサービスが提供します。** 既定は DYNAMIC で、容量を決めなくても使用量に応じて伸びます。STATIC は 1,200 GiB から 2,400 GiB 刻みで確保します | **run の内側にはありません。** 中間成果物は run storage が担います。出番があるのは run の外側、つまり入力を渡す前の置き場、結果を受け取った後の解析・共有、オンプレミスの解析環境との行き来です |
| **AWS Batch（EC2 起動タイプ）** | 共有ファイル層は自分で用意します。AWS の公開事例には Arm の EDA で AWS Batch と FSx for ONTAP を併用した構成があります | **候補になります。** ホスト OS から NFS / SMB でマウントして使います |
| **AWS Batch（Fargate 起動タイプ）** | ECS Fargate が対応するボリュームは bind mount と Amazon EFS に限られます | **マウントできません。** 永続が要るなら S3 Access Points 経由のオブジェクトアクセスになります（[コンテナの決定木](../../../reference/decision-trees/container-datastore-selection.md)） |
| **自前の HPC クラスタ / Nextflow on EC2 / オンプレミス** | 共有ファイル層は自分で用意します | **候補になります。** オンプレミスの NetApp ONTAP があれば、FlexCache で必要な分だけ取得するか、SnapMirror で複製して持ち込めます |

**そのうえで、共有ファイル層を自分で用意する基盤では、要るかどうかをワークロードの形で決めます。** 判断軸は 3 つです。

| 軸 | 共有ファイル層を経由する側 | オブジェクトストアで足りる側 |
|---|---|---|
| **複数ホストが同じデータを同時に読み書きするか** | する（例: 参照ゲノムを多数のジョブが同時参照、中間成果物を次工程が読む） | 各ジョブが独立にオブジェクトを取得して完結する |
| **ツールが POSIX の入出力を前提とするか** | する（多くのバイオインフォ / CAE / レンダリングツールはファイルパスとランダムアクセスを前提） | S3 SDK / オブジェクト API に対応している |
| **ファイルが大きく、ランダムアクセスや追記があるか** | ある（BAM のインデックス参照、レンダリングの中間フレーム） | 書いたら読むだけ（write-once-read-many） |

**3 つのどれかで左側に当たり、かつ共有ファイル層を自分で用意する基盤なら、POSIX 共有ファイルシステムが要ります。** 逆に 3 つとも右側なら、S3 で完結します。

> **出典と確認日**: HealthOmics の run storage（DYNAMIC / STATIC、1,200 GiB と 2,400 GiB 刻み）は [Run storage types in HealthOmics workflows](https://docs.aws.amazon.com/omics/latest/dev/workflows-run-types.html) と [HealthOmics pricing](https://aws.amazon.com/healthomics/pricing/)、Sequence Store を S3 URI（S3 Access Points ベース）で直接 list / read できることは [AWS for Industries: HealthOmics の新機能](https://aws.amazon.com/blogs/industries/aws-healthomics-announces-new-capabilities-for-seamless-integration-of-omics-data-stores-and-analysis-tools/) の記載です（2026-11-02 に確認）。AWS Batch と FSx for ONTAP の組み合わせは [Arm の事例](https://aws.amazon.com/solutions/case-studies/arm-ltd-case-study/) の「AWS Services Used」に並ぶ記載で、構成の詳細は公開されていません。

**どの形に当たるかを判断する決定木**は [AI・HPC ワークロードのデータ層に FSx for ONTAP を経由させるかを決める](../../../reference/decision-trees/ai-workload-data-layer.md) にあります。このノートは「データが置かれる場所は基盤ごとに違う」という事実を示し、決定木が「自分はどこに当たるか」を引きます。

---

### FSx for ONTAP が入る位置

![データの置き場は 2 つの枠に分かれる。上の枠は run の外側で、オンプレミスの NetApp ONTAP から FlexCache または SnapMirror で FSx for ONTAP（POSIX 共有ファイル層）へ届き、SnapMirror の宛先などに付けた S3 Access Points で同じデータを S3 API から読める（FlexCache の Cache には付けられない）。下の枠はマネージドな解析で、AWS HealthOmics が構造化テーブルとして Amazon S3 Tables に載せ、Amazon Bedrock AgentCore がバリアントをクエリする。2 つの枠は線で結ばない。](../../../../_assets/images/genomics-hpc-data-layers.svg)

図 1: データの置き場は 2 つの枠に分かれる。FSx for ONTAP は run の外側（共有ファイル層を自分で用意する側）、HealthOmics の run は共有ファイルシステムをサービスが提供する。

**FSx for ONTAP が入るのは中間の共有ファイル層です。** シーケンスデータの長期保管は Sequence Store、構造化バリアントのクエリは S3 Tables が担い、その間で**複数ホストが POSIX で同時に触る中間成果物・参照 DB・ツールの作業領域**を FSx for ONTAP が受け持ちます。

**オンプレミスのシーケンサー施設や解析環境を持っている場合**は、ここに ONTAP のデータモビリティが重なります。オンプレミスの NetApp ONTAP を Origin、FSx for ONTAP を Cache にした FlexCache は、**必要になった分だけを取得します。** SnapMirror は宛先に複製を持つので、全量が宛先にも存在します。 手段ごとの権限・管理経路・制約は [コピーを増やさずにデータへ届く](reaching-data-without-copies.md#コピーを増やさない-3-つの手段) にあります。ここでは機構を再説明しません。

**ただし他クラウドの ONTAP ベースサービス（Google Cloud NetApp Volumes, Azure NetApp Files）を Origin にした FlexCache 構成は、このリポジトリでは未確認です。** クロスクラウドのデータモビリティで引ける範囲と引けない範囲は [クロスクラウド分析でコピーを増やさない](cross-cloud-analytics-without-extra-copies.md) に分けて書いています。

---

### 同じ形を採っている公開事例

**以下は「シーケンス/HPC の解析で ONTAP または FSx for ONTAP が使われている」公開事例です。** 構成や数値は各組織が同意した範囲の記載で、ONTAP バージョン・リージョン・構成は明記されていないことが多いので、設計の根拠にする前に自環境で測ってください。

| 領域 | 事例 | この図での位置づけ |
|---|---|---|
| ライフサイエンス（データファブリック） | [AstraZeneca](https://www.netapp.com/customers/astrazeneca-data-fabric-case-study/) | 研究データをオンプレミスとクラウドにまたいで扱うデータファブリック。中間共有層とデータモビリティ |
| ハイブリッド HPC（研究） | [研究データを動かさずに HPC をクラウドへ拡張する](https://www.netapp.com/ja/blog/hybrid-hpc/) | 理研チームらが FlexCache でオンプレミスの研究データを Origin、クラウドを Cache にした技術検証。**まさに「データを動かさず HPC をクラウドへ」の形** |
| 生成 AI（研究・ライフサイエンス） | [NetApp と AWS — 広島大学との実証実験](https://www.netapp.com/ja/blog/hiroshima-university-aws-genai-2/) | 大学の研究データを FSx for ONTAP に置き、生成 AI から利用 |
| ハイブリッド ML 推論 | [Hybrid ML inferencing on Amazon EKS with Amazon FSx for NetApp ONTAP and on-premises NetApp](https://aws.amazon.com/blogs/storage/hybrid-ml-inferencing-on-amazon-eks-with-amazon-fsx-for-netapp-ontap-and-on-premises-netapp/) | オンプレミスの ONTAP と FSx for ONTAP をまたいだ ML 推論。モデル・特徴量の共有層 |
| EDA / 半導体（HPC） | [Arm](https://aws.amazon.com/solutions/case-studies/arm-ltd-case-study/) / [NetApp: Optimize HPC workloads on AWS](https://www.netapp.com/blog/optimize-hpc-aws-scalable-storage/) | 高度に並列な HPC ジョブが同じストレージを同時に叩く。中間共有層の典型 |
| CAE / CFD（HPC） | [FSx for ONTAP と SOCA による製品エンジニアリング](https://aws.amazon.com/blogs/industries/the-business-and-engineering-benefits-of-fsx-for-netapp-ontap-for-product-engineering-workloads/) / [3D シミュレーションの生産性](https://www.netapp.com/blog/3d-simulation-ontap/) | シミュレーションの入出力を共有ファイルシステムに置く。Scale-Out Computing on AWS（SOCA）と組み合わせた HPC |
| seismic（HPC） | [Petrobras が EC2 Spot で HPC のコストと容量を最適化](https://aws.amazon.com/jp/blogs/news/petrobras-optimizes-cost-and-capacity-of-hpc-applications-with-amazon-ec2-spot-instances/) / [upstream ワークロード](https://aws.amazon.com/jp/blogs/storage/enhance-your-upstream-workloads-with-amazon-fsx-for-netapp-ontap/) | 地震探査データの大規模並列処理。共有ファイルシステムが前提 |
| レンダリング / VFX | [映画『すずめの戸締まり』を支えた FSx for ONTAP（コミックス・ウェーブ・フィルム）](https://www.netapp.com/customers/cwf-case-study/) / [CGWorld の制作データ管理記事](https://cgworld.jp/article/202304-cgw294-szmdata.html) | ハイブリッドクラウドレンダリング。多数のレンダリングノードが中間フレームを同時に読み書きする共有層に FSx for ONTAP |

**レンダリングと EDA と seismic を同じ表に並べているのは理由があります。** どれも「多数のホストが同じ共有ファイルシステムを同時に叩く、大量ファイルの HPC」という**同じワークロードの形**で、だから同じ置き方になります。**自分の業種が表に無くても、形が近い行が参考になります。** 業種からの入口は [業種別リソースマップ](../../../reference/industry-resource-map.md) にあります。

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| マネージドなシーケンスストアを使えば共有ファイルシステムは要らない | **役割が別です。** 保管・取り込みの層と、POSIX で中間成果物を同時に触る層は別で、同じパイプラインで両方要ることがあります |
| サーバーレスな基盤なら POSIX 共有層はどれも不要 | **基盤ごとに違います。** HealthOmics の run は共有ファイルシステム（run storage）をサービスが提供するので run の内側では不要です。AWS Batch の EC2 起動タイプは自分で用意し、Fargate 起動タイプは FSx for ONTAP をマウントできません |
| HealthOmics を使うなら FSx for ONTAP は出番がない | run の**内側**にはありません。入力を渡す前の置き場、結果を受け取った後の解析、オンプレミスの解析環境との行き来は run の外側で、そこで共有ファイル層が要るかをワークロードの形で決めます |
| VCF は S3 に置けばよい | 長期保管とコホート横断クエリは S3 / S3 Tables が向きますが、**解析ツールが POSIX で触る中間 VCF は共有ファイルシステム側です** |
| オンプレのシーケンサーデータはクラウドへ全量コピーするしかない | FlexCache は必要な分だけ取得します。SnapMirror は複製なので宛先にも全量が存在します。どちらを使うかは、読み取り主体でワーキングセットが小さいかで決まります（[3 つの手段](reaching-data-without-copies.md#コピーを増やさない-3-つの手段)） |
| 他クラウドの ONTAP サービスを Origin にした FlexCache も同じように組める | **このリポジトリでは未確認です**（[クロスクラウドのノート](cross-cloud-analytics-without-extra-copies.md)） |

---

### 関連ドキュメント

- [Domain — データ活用](../README.md) — このモジュールのハブ
- [AI・HPC ワークロードのデータ層に FSx for ONTAP を経由させるかを決める](../../../reference/decision-trees/ai-workload-data-layer.md) — 自分がどの形に当たるかを引く決定木
- [コピーを増やさずにデータへ届く](reaching-data-without-copies.md) — FlexCache / FlexClone / SnapMirror の機構・権限・制約
- [クロスクラウド分析でコピーを増やさない](cross-cloud-analytics-without-extra-copies.md) — クロスクラウド・クロスリージョンでの引ける範囲と未確認の境界
- [スループットは 1 つの設定値では決まらない](../../performance/notes/where-throughput-is-determined-and-shared.md) — 共有ファイル層の性能が何で決まるか
- [業種別リソースマップ](../../../reference/industry-resource-map.md) — 業種とワークロードの形からの入口
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — データ活用](../README.md)
