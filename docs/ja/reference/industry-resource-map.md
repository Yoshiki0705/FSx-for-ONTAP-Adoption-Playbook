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

**自分の業種を見つけ、3 つの列を左から読んでください。**

- **公開事例** — AWS または NetApp が publish した導入事例。何が達成されたかの概要
- **実装パターン** — 動くテンプレートを含む sibling リポジトリへのリンク
- **設計ノート** — このリポジトリ内の、業種を問わず当たる判断基準

事例は導入した組織が同意した範囲で書かれており、多くは ONTAP バージョン・リージョン・構成を明記していません。数値を設計の根拠にする前に自環境で測ってください。

> **区分**: `documented` — 各事例 URL の所在と、sibling リポジトリへのリンクを記載しています。

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
| ノート | [スループットは 1 つの設定値では決まらない](../domains/performance/notes/where-throughput-is-determined-and-shared.md) | 世代・構成・リージョンで上限が変わる |

### 自動車 / ADAS / 自動運転

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [s3-burst-on-ontap-files](https://github.com/Yoshiki0705/s3-burst-on-ontap-files) | FlexCache + S3 AP で ADAS HIL テスト。リファレンスアーキテクチャ。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-s3burst-flexcache-collect-s3-consume-files) |
| パターン | [UC9: autonomous-driving](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/autonomous-driving/) | 映像/LiDAR 前処理パイプライン |
| ノート | [S3 AP は「S3 として使える」わけではない](../domains/data-utilization/notes/s3-access-point-constraints.md) | 同一アカウント・リージョン等の制約 |

### 製造

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [Komprise + FSx for ONTAP](https://www.komprise.com/blog/manufacturing-case-study-komprise-amazon-fsx-for-ontap/) | 3 PB 移行、コスト 50% 以上削減 |
| パターン | [UC3: manufacturing-analytics](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/industry/manufacturing-analytics/) | IoT センサー・品質検査画像分析 |
| パターン | [ontap-edge-to-cloud-ai](https://github.com/Yoshiki0705/ontap-edge-to-cloud-ai) | エッジデバイスデータの集約と AI 活用 |
| ノート | [容量が余っていても書けなくなる](../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) | ファイル数の棚卸し |

### 金融

| 種類 | リソース | 論点 |
|------|----------|------|
| 事例 | [PayPay カード](https://aws.amazon.com/jp/solutions/case-studies/paypay-card-case-study/) | クレジットカード基幹システムの AWS 移行。PCIDSS 準拠、Multi-AZ 構成、DR は大阪リージョン。FSx for ONTAP をファイル共有に採用 |
| 事例 | [Banco Pan](https://aws.amazon.com/solutions/case-studies/banco-pan-case-study/) | コスト 51% 削減 |
| 事例 | [AdvisorEngine](https://www.netapp.com/customers/advisorengine-amazon-fsx-ontap-case-study/) | SQL Server 再アーキテクチャ。コストと性能 |
| 事例 | [S&P Global Market Intelligence](https://aws.amazon.com/blogs/storage/why-sp-global-chose-amazon-fsx-for-netapp-ontap-to-achieve-high-availability-and-disaster-recovery-for-sql-server/) | SQL Server FCI DR。SnapMirror で RPO 短縮 |
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
| パターン | [ファイルポータル UI (Amplify Gen2)](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/amplify-portal) | NAS にブラウザアクセス + AI 処理。VPN 不要。Nextcloud との併用可。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-file-portal-1-browser-access) |
| 技術資料 | [SaaS デプロイのコスト・TTM 削減](https://aws.amazon.com/blogs/apn/reduce-saas-deployment-costs-and-time-to-market-with-amazon-fsx-for-netapp-ontap/) | FlexClone によるテナント展開 |
| ノート | [IaC の境界は API の表面で決まる](../playbooks/04-build/notes/what-iac-cannot-reach.md) | テンプレートが成功しても構成は完成しない |

### サイバーレジリエンス（業種横断）

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [fsxn-cyber-resilience-patterns](https://github.com/Yoshiki0705/fsxn-cyber-resilience-patterns) | ARP + File Security + FPolicy の多層防御 |
| 技術資料 | [Protecting data against ransomware](https://aws.amazon.com/blogs/storage/protecting-data-against-ransomware-with-amazon-fsx-for-netapp-ontap/) | AWS 公式のランサムウェア対策ガイド |
| ノート | [SnapLock は有効化とロックが別](../domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md) | 不可逆な選択が 3 段ある |

### 可観測性（業種横断）

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) | Datadog / Splunk / New Relic 等への監査ログ転送 |
| ノート | [p99 は CloudWatch のメトリクスからは出せない](../domains/performance/notes/what-you-cannot-read-from-cloudwatch.md) | レイテンシは平均しか得られない |

### データレイク / Lakehouse（業種横断）

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations) | Athena / Glue / Spark 等からの S3 AP 経由アクセス |
| パターン | [S3 Burst on ONTAP Files](https://github.com/Yoshiki0705/s3-burst-on-ontap-files) | S3 で収集 → FlexCache の NFS/SMB で利用。反映 p50 8 ms。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-s3burst-flexcache-collect-s3-consume-files) |
| ノート | [S3 AP は「S3 として使える」わけではない](../domains/data-utilization/notes/s3-access-point-constraints.md) | 設計段階の制約 |

---

## 読み方のガイド

1. **自分の業種を見つける** — 上の索引から。一致しなくてもワークロードが近ければ読む価値があります
2. **事例は「何が達成されたか」の参考** — 構成や数値は明記されていないことが多い。設計根拠にするなら自環境で測る
3. **パターンは「どう実装するか」のテンプレート** — SAM / CDK / CFn が含まれます。そのまま deploy 可能
4. **ノートは「なぜそうするか、何に気をつけるか」の根拠** — 業種を問わず当たる壁の説明

---

## sibling リポジトリ一覧

| リポジトリ | 内容 | 形式 |
|---|---|---|
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | 28 業種別 UC + OPS + GenAI + SAP + [ファイルポータル UI](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/amplify-portal) | SAM + Amplify Gen2。[ポータル解説](https://hakobiya.hatenablog.com/entry/fsxn-file-portal-1-browser-access) |
| [s3-burst-on-ontap-files](https://github.com/Yoshiki0705/s3-burst-on-ontap-files) | S3 で収集 → FlexCache NFS/SMB で利用。反映 p50 8 ms | CFn + SAM。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-s3burst-flexcache-collect-s3-consume-files) |
| [FSx-for-ONTAP-Agentic-Access-Aware-RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | アクセス制御対応 Agentic RAG | CDK |
| [fsxn-cyber-resilience-patterns](https://github.com/Yoshiki0705/fsxn-cyber-resilience-patterns) | ARP + File Security + FPolicy 多層防御 | 実装パターン |
| [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) | 監査ログ → Datadog / Splunk 等 | Lambda + S3 AP |
| [fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations) | Athena / Glue / Spark 連携 | S3 AP |
| [ontap-edge-to-cloud-ai](https://github.com/Yoshiki0705/ontap-edge-to-cloud-ai) | IoT エッジ → クラウド AI | CDK |
| [vmware-migration-ec2-ontap](https://github.com/Yoshiki0705/vmware-migration-ec2-ontap) | VMware 移行 | — |
| [blea-fsxn-usecase](https://github.com/Yoshiki0705/blea-fsxn-usecase) | BLEA ゲストシステムユースケース | CDK |
