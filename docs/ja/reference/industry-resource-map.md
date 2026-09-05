---
title: 業種別リソースマップ — 公開事例・実装パターン・設計ノートの横断索引
lifecycle: [assess, design]
domains: [cost, performance, data-protection, data-utilization, security-governance]
evidence: documented
source: https://aws.amazon.com/fsx/netapp-ontap/customers/
lang: ja
---

# 業種別リソースマップ

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

---

## 結論

**業種から入る道は 2 本あります。**

- **決めることから知りたいなら** → [業種から入ったときの読む順序](#業種から入ったときの読む順序)。このリポジトリのどのモジュールへ戻るかの対応です
- **材料を集めたいなら** → [業種別索引](#業種別索引)。3 種類のリソースを並べています

索引の 3 種類は次のものです。

- **公開事例** — AWS または NetApp が publish した導入事例。何が達成されたかの概要
- **実装パターン** — 動くテンプレートを含む sibling リポジトリへのリンク
- **設計ノート** — このリポジトリ内の、業種を問わず当たる判断基準

**UC の実装はこのリポジトリに置きません。** 同じ実装を 2 か所に置くと、片方だけが更新されて古い側が新しい側を上書きします。分担の原則は [プロジェクト間の引用索引](cross-repo-index.md) にあります。

事例は導入した組織が同意した範囲で書かれており、多くは ONTAP バージョン・リージョン・構成を明記していません。数値を設計の根拠にする前に自環境で測ってください。

**ブロックストレージ（iSCSI / NVMe-oF）の一次情報は業種軸ではなく [ブロックストレージ横断リソースマップ](block-storage-resource-map.md) に集めています。**

> **区分**: `documented` — 各事例 URL の所在と、sibling リポジトリへのリンクを記載しています。

---

## 業種から入ったときの読む順序

**この索引は sibling リポジトリへのリンク集としては働きますが、それだけでは「で、自分は何を決めればいいのか」に答えません。** 下の表は、業種を入口にしたときにこのリポジトリのどこへ戻るかの対応です。

**先に 1 つ断っておきます。読むモジュールを決めているのは業種ではなく、ワークロードの形です。** 大量の小さなファイルか、少数の巨大なファイルか、複数ホストから同じデータを読むのか、ブロックで出すのか。**だから自分の業種が表に無くても、形が近い行を読む価値があります。** 逆に、同じ業種でも形が違えば別の行を読んでください。

| 業種 | 最初に読む | 次に読む | この業種で判断が集中するところ |
|---|---|---|---|
| エネルギー | [移行](../playbooks/03-migrate/) | [設計](../playbooks/02-design/) | 切り戻せる時点がいつ閉じるか。**巨大な逐次読みは単一接続で測ると上限を測ります**（[切り分け](decision-trees/measured-throughput-triage.md)） |
| 半導体 / EDA | [性能](../domains/performance/) | [データ活用](../domains/data-utilization/) | 並列度と接続数。**設定 1 つで最も大きく動いたのは接続数でした**（[手段の比較](comparison/throughput-levers.md)） |
| 自動車 / ADAS / 自動運転 | [データ活用](../domains/data-utilization/) | [性能](../domains/performance/) | 収集と利用でプロトコルが変わること。S3 AP の制約は設計段階で効きます |
| 製造 | [評価](../playbooks/01-assess/) | [データ活用](../domains/data-utilization/) | **ファイル数の棚卸し。容量が余っていても書けなくなります** |
| 金融 | [ブロックストレージ](../domains/block-storage/) | [データ保護](../domains/data-protection/) | **不可逆な保持設定と、戻したあとにアプリが起動するか**（[本番投入前レビュー](../playbooks/04-build/checklists/pre-production-review.md)） |
| 保険 | [移行](../playbooks/03-migrate/) | [マルチプロトコル・ID](../domains/multiprotocol-identity/) | 権限が移行先に持ち越されるか |
| ヘルスケア / 医療 | [データ保護](../domains/data-protection/) | [セキュリティ・ガバナンス](../domains/security-governance/) | **Snapshot があることと復旧できることが別だという点** |
| 通信 | [運用](../playbooks/05-operate/) | [性能](../domains/performance/) | **監視が平均値で失敗すること。p99 は CloudWatch から出せません** |
| 防衛 / 公共 | [セキュリティ・ガバナンス](../domains/security-governance/) | [データ保護](../domains/data-protection/) | 責任境界と、不可逆な設定の承認手順 |
| メディア / エンタメ | [設計](../playbooks/02-design/) | [性能](../domains/performance/) | **デプロイタイプは一度しか決められません。** 同時台数はデータを共有するかで 5.5 倍変わります |
| 教育 | [マルチプロトコル・ID](../domains/multiprotocol-identity/) | [コスト](../domains/cost/) | 利用者が多いときの ID の置き方と、確保した量への課金 |
| 物流 | [移行](../playbooks/03-migrate/) | [運用](../playbooks/05-operate/) | ログインストームのような同時アクセスの山 |
| スポーツ / 小売 | [データ活用](../domains/data-utilization/) | [コスト](../domains/cost/) | **容量プール階層のリクエスト課金。読み直すデータを下げると高くなります** |
| AI / 機械学習 | [データ活用](../domains/data-utilization/) | [セキュリティ・ガバナンス](../domains/security-governance/) | **元の ACL が AI パイプラインに引き継がれないこと** |
| SaaS / マルチテナント | [ブロックストレージ](../domains/block-storage/) | [コスト](../domains/cost/) | **詰まるのは容量ではなくボリューム数の上限です** |
| サイバーレジリエンス（業種横断） | [データ保護](../domains/data-protection/) | [セキュリティ・ガバナンス](../domains/security-governance/) | **有効化とロックが別だという点。** 不可逆な選択が 3 段あります |
| 可観測性（業種横断） | [性能](../domains/performance/) | [セキュリティ・ガバナンス](../domains/security-governance/) | 何が見えないか。SMB 監査は最初の読みと書きしか記録しません |
| データレイク / Lakehouse（業種横断） | [データ活用](../domains/data-utilization/) | [性能](../domains/performance/) | S3 AP の制約と、接続数で当たる上限が変わること |

**どの業種でも共通して先に通すもの**があります。業種の行より優先してください。

| 通すもの | なぜ全業種か |
|---|---|
| [本番投入前レビュー](../playbooks/04-build/checklists/pre-production-review.md) | **後から変えられない項目**は業種を問いません。SnapLock、Snapshot locking、セキュリティスタイル、`NetworkOrigin` |
| [知見の分類ポリシー](../evidence-policy.md) | 事例の数値をそのまま設計根拠にしないための区分 |
| [上限値・クォータ](limits/) | 上限に当たるかどうかは構成で決まり、業種では決まりません |

---

## 業種別索引

### エネルギー

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [Phillips 66](https://aws.amazon.com/solutions/case-studies/phillips66-migration-case-study/) | オンプレミスからのクラウド移行。移行そのものが主題 |
| パターン | [UC8: energy-seismic](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/energy-seismic/) | SEG-Y 地震探査データの S3 経由分析 |
| ノート | [切り戻せる時点はクライアントが書き始めた瞬間に閉じる](../playbooks/03-migrate/notes/where-the-rollback-window-closes.md) | 移行の切り替え判断 |

### 半導体 / EDA

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [NVIDIA](https://aws.amazon.com/jp/solutions/case-studies/nvidia-case-study/) | ハイブリッド EDA。オンプレ FlexCache をクラウドに拡張し 15-20 種のフローを同時実行。write-shunt filer で 5,000 並列ジョブ対応 |
| 事例 | [Amazon Annapurna Labs](https://aws.amazon.com/fsx/netapp-ontap/customers/) | 容量 2 倍にスケール、性能維持、100% 可用性、ストレージコスト 35% 削減 |
| 事例 | [Arm](https://aws.amazon.com/solutions/case-studies/arm-ltd-case-study/) | チップ設計ワークロードの性能スケール |
| 事例 | [Vitesco](https://aws.amazon.com/fsx/netapp-ontap/customers/) | 自動車半導体。コンピュートコストの可視化と制御 |
| 技術資料 | [EDA ベストプラクティス（PDF）](https://d1.awsstatic.com/fsx/FSx_for_ONTAP_EDA_Best_Practices_2.pdf) | ボリューム設計・データ種別・サイジング |
| 技術資料 | [EDA Scale with IBM LSF](https://aws.amazon.com/blogs/industries/eda-scale-with-fsx-for-netapp-ontap-and-ibm-lsf/) | バッチスケジューラとのスケール |
| パターン | [UC6: semiconductor-eda](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/semiconductor-eda/) | GDS/OASIS バリデーション |
| 技術資料 | [AI Projects Are Data Projects: Lessons from Semiconductor Defect Classification](https://medium.com/@janhavi.giri/ai-projects-are-data-projects-lessons-from-semiconductor-defect-classification-f47fddae1cf7) | 欠陥分類 AI のデータ層の摩擦と自己サービス運用モデルの整理。**educational mimic であり実測値の出典ではありません** |
| ノート | [スループットは 1 つの設定値では決まらない](../domains/performance/notes/where-throughput-is-determined-and-shared.md) | 世代・構成・リージョンで上限が変わる |
| ノート | [学習データセットの版をスケジュール Snapshot に載せると消える](../domains/data-utilization/notes/dataset-versions-and-experiment-branches.md) | 欠陥分類 AI のデータセット版管理と実験ブランチの制約 |
| ノート | [実験ブランチを配るときに縛る対象は権限だけではない](../domains/security-governance/notes/self-service-without-storage-admin.md) | 解析エンジニアに管理者権限を渡さない運用モデル |

### 自動車 / ADAS / 自動運転

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) | FlexCache + S3 AP で ADAS HIL テスト。リファレンスアーキテクチャ。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-s3burst-flexcache-collect-s3-consume-files) |
| パターン | [UC9: autonomous-driving](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/autonomous-driving/) | 映像/LiDAR 前処理パイプライン |
| ノート | [S3 AP は「S3 として使える」わけではない](../domains/data-utilization/notes/s3-access-point-constraints.md) | 同一アカウント・リージョン等の制約 |
| ノート | [単一接続で測った値はストレージの性能ではない](../domains/performance/notes/a-single-connection-measures-the-client.md) | **HIL テストのように多数のクライアントから読む形では、当たる上限がデータを共有しているかで変わります** |

### 製造

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [Komprise + FSx for ONTAP](https://www.komprise.com/blog/manufacturing-case-study-komprise-amazon-fsx-for-ontap/) | 3 PB 移行、コスト 50% 以上削減 |
| パターン | [UC3: manufacturing-analytics](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/manufacturing-analytics/) | IoT センサー・品質検査画像分析 |
| パターン | [ONTAP-Edge-to-Cloud-AI](https://github.com/Yoshiki0705/ONTAP-Edge-to-Cloud-AI) | エッジデバイスデータの集約と AI 活用 |
| ノート | [容量が余っていても書けなくなる](../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) | ファイル数の棚卸し |

### 金融

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [PayPay カード](https://aws.amazon.com/jp/solutions/case-studies/paypay-card-case-study/) | クレジットカード基幹システムの AWS 移行。PCIDSS 準拠、Multi-AZ 構成、DR は大阪リージョン。FSx for ONTAP をファイル共有に採用 |
| 事例 | [Banco Pan](https://aws.amazon.com/solutions/case-studies/banco-pan-case-study/) | コスト 51% 削減 |
| 事例 | [AdvisorEngine](https://www.netapp.com/customers/advisorengine-amazon-fsx-ontap-case-study/) | SQL Server 再アーキテクチャ。コストと性能 |
| 事例 | [S&P Global Market Intelligence](https://aws.amazon.com/blogs/storage/why-sp-global-chose-amazon-fsx-for-netapp-ontap-to-achieve-high-availability-and-disaster-recovery-for-sql-server/) | SQL Server FCI DR。SnapMirror で RPO 短縮 |
| 技術資料 | [SQL Server の高可用性](https://aws.amazon.com/jp/blogs/modernizing-with-aws/sql-server-high-availability-amazon-fsx-for-netapp-ontap/) | FCI を iSCSI 共有ストレージで組む。両ノードの IQN を 1 つの igroup に入れる |
| ノート | [LUN の並べ方が決めているのは復旧の粒度](../domains/block-storage/notes/lun-layout-decides-recovery-granularity.md) | **AWS の 2 記事が LUN レイアウトで一致していません。** 決めているのは復旧の粒度です |
| ノート | [LUN の Snapshot は既定で crash-consistent](../domains/block-storage/notes/a-snapshot-of-a-lun-is-crash-consistent.md) | データベースを戻すのに静止の仕組みが必要かどうか |
| 技術資料 | [FSI 向けサービス解説](https://aws.amazon.com/blogs/industries/fsi-services-spotlight-featuring-amazon-fsx-for-netapp-ontap/) / [日本語版](https://aws.amazon.com/jp/blogs/news/fsi-services-spotlight-featuring-amazon-fsx-for-netapp-ontap/) | 金融業界で問われる論点の整理 |
| パターン | [UC2: financial-idp](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/financial-idp/) | 帳票 OCR・エンティティ抽出 |
| ノート | [課金は「確保した量」と「使った量」に分かれる](../domains/cost/notes/provisioned-versus-consumed.md) | TCO の構造 |

### 保険

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [Nordcloud: Swiss insurer](https://nordcloud.com/case-studies/swiss-insurance-provider/) | オンプレミス NetApp からの無停止 AWS 移行。複数リージョン |
| パターン | [UC14: insurance-claims](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/insurance-claims/) | 損害査定パイプライン |
| ノート | [ACL 保持は権限の問題であってツールの問題ではない](../playbooks/03-migrate/notes/preserving-acls-during-migration.md) | 移行時の権限保持 |

### ヘルスケア / 医療

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [eHealth NSW](https://www.netapp.com/blog/aws-fsxo-blg-customer-success-stories-with-amazon-fsx-for-netapp-ontap/) | 公共医療のクラウド移行 |
| 事例 | [Duke Health](https://www.netapp.com/industries/healthcare/case-study-duke-health/) | ミッションクリティカル + HPC ワークロード |
| 事例 | [医療機器メーカー SQL Server 移行](https://docs.netapp.com/us-en/netapp-solutions-databases/mssql/customer-usecase-mssql-fsx1.html) | オンプレミス SQL Server のコスト削減 |
| パターン | [UC5: healthcare-dicom](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/healthcare-dicom/) | DICOM 匿名化パイプライン |
| ノート | [Snapshot があることと復旧できることは別](../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md) | データ保護設計 |

### 通信

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [MYCOM OSI](https://aws.amazon.com/jp/blogs/news/how-mycom-osi-optimized-saas-storage-with-amazon-fsx-for-netapp-ontap/) | SaaS ストレージのコストパフォーマンス改善。Kubernetes 連携 |
| 事例 | [Amdocs](https://aws.amazon.com/solutions/case-studies/amdocs-case-study/) | ストレージ性能スケーリング。通信向け BSS/OSS |
| パターン | [UC18: telecom-network-analytics](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/telecom-network-analytics/) | CDR/ネットワークログ分析 |
| ノート | [監視は平均値で失敗する](../playbooks/05-operate/notes/monitoring-fails-on-averages.md) | 待機系ノードが平均を引き下げる問題 |

### 防衛 / 公共

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [Peraton](https://www.netapp.com/customers/peraton-amazon-fsx-case-study/) | セキュリティ重視のオンプレミス移行。FedRAMP / DoD SRG 対応 |
| 認証 | [FedRAMP / DoD SRG IL2-IL5 対応](https://www.netapp.com/blog/fsx-ontap-fedramp-and-dod-authorized/) | GovCloud (US) リージョン |
| パターン | [UC15: defense-satellite](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/defense-satellite/) | 衛星画像解析 |
| パターン | [UC16: government-archives](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/government-archives/) | 公文書・FOIA |
| ノート | [保存時の暗号化は自動、転送時は既定で無効](../domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md) | セキュリティの責任境界 |

### メディア / エンタメ

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [コミックス・ウェーブ・フィルム](https://aws.amazon.com/jp/solutions/case-studies/comix-wave-film/) | クラウドで最大 300 台同時レンダリング。55.61 TB / 1,690 万ファイル。DR バックアップ 7 日分。CG 部以外の全部署で採用 |
| 事例 | [メディア業界の事例](https://www.netapp.com/blog/benefits-of-cloud-computing-in-media-industry/) | VFX 制作ワークフロー |
| パターン | [UC4: media-vfx](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/media-vfx/) | VFX レンダリング品質チェック |
| ノート | [デプロイタイプは一度しか決められない](../playbooks/02-design/notes/deployment-type-is-decided-once.md) | スループット上限に直結する選択 |

### 教育

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [Pearson](https://www.netapp.com/blog/aws-fsxo-blg-customer-success-stories-with-amazon-fsx-for-netapp-ontap/) | アジャイルなファイルワークロード運用 |
| パターン | [UC13: education-research](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/education-research/) | 論文分類・引用分析 |
| ノート | [ローカルユーザーの棚卸しに最終ログオン属性は無い](../domains/multiprotocol-identity/notes/local-user-inventory-without-last-logon.md) | 利用者が多い環境で、使われていないアカウントを特定する手段 |
| ノート | [課金は「確保した量」と「使った量」に分かれる](../domains/cost/notes/provisioned-versus-consumed.md) | 学期で利用が波打つときに、確保した量への課金が効く構造 |

### 物流

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [Allcargo](https://aws.amazon.com/blogs/storage/how-allcargo-migrated-vdi-workload-to-amazon-fsx-using-aws-datasync/) | 3,500 VDI ユーザーの移行。ログインストーム・Outlook キャッシュ書き込みストーム対策。DataSync + SnapMirror |
| パターン | [UC12: logistics-ocr](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/logistics-ocr/) | 配送伝票 OCR |
| ノート | [メンテナンスは 14 日を超えて延期できない](../playbooks/05-operate/notes/maintenance-cannot-be-deferred.md) | SSD 90% 超のリスク |

### スポーツ / 小売

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [adidas](https://aws.amazon.com/fsx/netapp-ontap/customers/) | 大規模インスタンスでの処理速度。リストアの高速性 |
| パターン | [UC11: retail-catalog](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/retail-catalog/) | 商品画像タグ付け |
| ノート | [課金は「確保した量」と「使った量」に分かれる](../domains/cost/notes/provisioned-versus-consumed.md) | **容量プール階層はリクエストにも課金されます。** 読み直す画像を下げると高くなります |
| ノート | [階層化の既定値は作成方法で違う](../playbooks/06-optimize/notes/tiering-defaults-differ-by-creation-method.md) | コンソールで作った検証環境と IaC で作った本番が別のポリシーになること |

### AI / 機械学習

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [ファイルポータル UI (Amplify Gen2)](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/amplify-portal) | NAS 上のファイルにブラウザアクセス + AI 処理（分類・異常検知・セマンティック検索）。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-file-portal-1-browser-access) |
| パターン | [FSx-for-ONTAP-Agentic-Access-Aware-RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | アクセス制御対応 Agentic RAG（CDK） |
| 技術資料 | [SageMaker + FSx for ONTAP](https://docs.netapp.com/us-en/netapp-solutions-ai/cloud/ai-mlops-fsxn-sagemaker.html) | モデルトレーニングのデータソース |
| 技術資料 | [Dremio Cloud + FSx for ONTAP](https://www.dremio.com/blog/from-file-systems-to-ai-insights-dremio-cloud-amazon-fsx-for-netapp-ontap/) | ファイルシステムから AI インサイトへ |
| ノート | [S3 AP は全リクエストを 1 つの ID で認可する](../domains/data-utilization/notes/reaching-data-without-copies.md) | 元の ACL は AI パイプラインに引き継がれない |

### SaaS / マルチテナント

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [Hyland](https://aws.amazon.com/fsx/netapp-ontap/customers/) | エンタープライズコンテンツ管理 SaaS。2 PB → 14 PB にスケール（3 年間で 7 倍）。数百万の小さなファイルのレプリケーション |
| 事例 | [Infor](https://www.netapp.com/customers/infor/) | シングルテナント構成の個別調整 |
| 事例 | [MYCOM OSI](https://aws.amazon.com/jp/blogs/news/how-mycom-osi-optimized-saas-storage-with-amazon-fsx-for-netapp-ontap/) | Kubernetes + iSCSI でのコスト最適化 |
| ノート | [Kubernetes のブロック PV はボリューム数の上限に当たる](../domains/block-storage/notes/kubernetes-block-volumes-and-the-volume-limit.md) | `ontap-san` と `ontap-san-economy` の分岐点。詰まるのは容量ではありません |
| ノート | [容量は 3 か所で数えられる](../domains/block-storage/notes/capacity-is-counted-in-three-places.md) | 予約付き LUN は書き込み 0 でも容量を食います |
| パターン | [ファイルポータル UI (Amplify Gen2)](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/amplify-portal) | NAS にブラウザアクセス + AI 処理。VPN 不要。Nextcloud との併用可。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-file-portal-1-browser-access) |
| 技術資料 | [SaaS デプロイのコスト・TTM 削減](https://aws.amazon.com/blogs/apn/reduce-saas-deployment-costs-and-time-to-market-with-amazon-fsx-for-netapp-ontap/) | FlexClone によるテナント展開 |
| ノート | [IaC の境界は API の表面で決まる](../playbooks/04-build/notes/what-iac-cannot-reach.md) | テンプレートが成功しても構成は完成しない |

### サイバーレジリエンス（業種横断）

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [FSx-for-ONTAP-Cyber-Resilience-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns) | ARP + File Security + FPolicy の多層防御 |
| 技術資料 | [Protecting data against ransomware](https://aws.amazon.com/blogs/storage/protecting-data-against-ransomware-with-amazon-fsx-for-netapp-ontap/) | AWS 公式のランサムウェア対策ガイド |
| ノート | [SnapLock は有効化とロックが別](../domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md) | 不可逆な選択が 3 段ある |

### 可観測性（業種横断）

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [FSx-for-ONTAP-Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) | Datadog / Splunk / New Relic 等への監査ログ転送 |
| ノート | [p99 は CloudWatch のメトリクスからは出せない](../domains/performance/notes/what-you-cannot-read-from-cloudwatch.md) | レイテンシは平均しか得られない |

### データレイク / Lakehouse（業種横断）

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [FSx-for-ONTAP-Lakehouse-Integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) | Athena / Glue / Spark 等からの S3 AP 経由アクセス |
| パターン | [S3 Burst on ONTAP Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) | S3 で収集 → FlexCache の NFS/SMB で利用。反映 p50 8 ms。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-s3burst-flexcache-collect-s3-consume-files) |
| ノート | [S3 AP は「S3 として使える」わけではない](../domains/data-utilization/notes/s3-access-point-constraints.md) | 設計段階の制約 |

---

## 読み方のガイド

1. **自分の業種を見つける** — 上の索引から。**読むモジュールを決めているのはワークロードの形なので、一致しなくても形が近ければ読む価値があります**
2. **事例は「何が達成されたか」の参考** — 構成や数値は明記されていないことが多い。設計根拠にするなら自環境で測る
3. **パターンは「どう実装するか」のテンプレート** — SAM / CDK / CFn が含まれます。そのまま deploy 可能
4. **ノートは「なぜそうするか、何に気をつけるか」の根拠** — 業種を問わず当たる壁の説明
5. **業種の行より先に、全業種共通の 3 つを通す** — [読む順序](#業種から入ったときの読む順序)の末尾にあります。**後から変えられない項目は業種を問いません**

---

## sibling リポジトリ一覧

| リポジトリ | 内容 | 形式 |
|---|---|---|
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | 28 業種別 UC + OPS + GenAI + SAP + [ファイルポータル UI](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/amplify-portal) | SAM + Amplify Gen2。[ポータル解説](https://hakobiya.hatenablog.com/entry/fsxn-file-portal-1-browser-access) |
| [S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) | S3 で収集 → FlexCache NFS/SMB で利用。反映 p50 8 ms | CFn + SAM。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-s3burst-flexcache-collect-s3-consume-files) |
| [FSx-for-ONTAP-Agentic-Access-Aware-RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | アクセス制御対応 Agentic RAG | CDK |
| [FSx-for-ONTAP-Cyber-Resilience-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns) | ARP + File Security + FPolicy 多層防御 | 実装パターン |
| [FSx-for-ONTAP-Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) | 監査ログ → Datadog / Splunk 等 | Lambda + S3 AP |
| [FSx-for-ONTAP-Lakehouse-Integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) | Athena / Glue / Spark 連携 | S3 AP |
| [ONTAP-Edge-to-Cloud-AI](https://github.com/Yoshiki0705/ONTAP-Edge-to-Cloud-AI) | IoT エッジ → クラウド AI | CDK |
| [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) | VMware 移行 | — |
| [BLEA-FSx-for-ONTAP-Usecase](https://github.com/Yoshiki0705/BLEA-FSx-for-ONTAP-Usecase) | BLEA ゲストシステムユースケース | CDK |
