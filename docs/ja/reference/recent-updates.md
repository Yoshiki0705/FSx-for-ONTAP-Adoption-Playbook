---
title: 直近のアップデートと設計への影響 — 2026 年 5〜8 月
lifecycle: [design, build, operate]
domains: [performance, cost, security-governance, data-utilization, data-protection]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/document-history.html
lang: ja
---

# 直近のアップデートと設計への影響

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

---

## 結論

**2026 年 5〜8 月に、設計判断に影響するアップデートが 4 つの軸で出ています。**

1. **データ保護の到達範囲** — バックアップを別リージョン・別アカウントへコピー可能に。**既存の制約記述が 1 つ無効になりました**
2. **リージョン拡張と世代制限の緩和** — 第 2 世代が使えるリージョンが増え、性能上限の格差が縮まりつつある
3. **マルチプロトコル統合の拡大** — Transfer Family (SFTP/FTPS/FTP) が S3 AP 経由で FSx for ONTAP に接続可能に
4. **VMware 関連パスの追加** — 経路が 2 つあり、役割も状態も異なる。AWS Transform は **EC2 リホスト時のデータボリュームのターゲットストレージ**（2026-08-30 GA）、Amazon EVS は **VMware を継続したままの外部データストア**（2025-06 に public preview として告知、GA 告知は未確認）

以下は各アップデートの概要と、このリポジトリの既存ノートとの対応です。

> **区分**: `documented` — すべて AWS 公式 What's New / Document History / Blog の記載に基づきます。
> 具体的なスループット値やレイテンシの実測は含みません。

---

## FSx for ONTAP 本体のアップデート

### バックアップを別リージョン・別アカウントへコピー可能に（2026-08）

**それ以前は、ファイルシステムと同一リージョン・同一アカウントでバックアップを作成し復元することしかできませんでした。** 別リージョンへの退避は SnapMirror が唯一の経路で、そのために宛先でファイルシステムを起動し続ける必要がありました。

| 経路 | 手段 |
|---|---|
| 別リージョン・同一アカウント | FSx for ONTAP のコンソール / CLI / API (`CopyBackup`) |
| 別アカウント（fan-in / fan-out） | **AWS Backup + AWS Organizations**（FSx for ONTAP の API 単体では不可） |

| 設計への影響 | 関連ノート |
|---|---|
| **平常時にコピー先のファイルシステムを持たなくてよくなった。** 復旧時に作る時間（実測 20 分）が RTO に乗る | [バックアップコピーは復元するまでファイルシステムを持たない](../domains/data-protection/notes/backup-copies-across-regions-and-accounts.md) |
| 「バックアップではリージョン障害に備えられない」が成り立たなくなった。**復元先が同一リージョンである制約は変わっていない** | [Snapshot があることと復旧できることは別](../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md#守れる対象) |
| SnapMirror との選び分けが「可用性か保管か」で分かれる。**切り戻し経路はバックアップコピーにはない** | [データ保護方式の比較](comparison/data-protection-methods.md) |
| 隔離アカウントへの退避が、資格情報の漏洩や KMS キーの侵害への層として使える | [プラットフォームが与えるものと自分に残るもの](../domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md) |

出典: [What's New — FSx for ONTAP 側](https://aws.amazon.com/about-aws/whats-new/2026/08/fsx-ontap-cross-region-backup-copy/)、[What's New — AWS Backup 側](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-backup-amazon-fsx-netapp-cross-account-region/)、[Copying backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copy-backups.html)

**東京から大阪へのコピーと、コピー先での復元・内容照合を実測しました**（2026-08-28）。所要時間と、復元中に `OntapVolumeType` が `DP` として返る挙動は上記ノートにあります。

---

### Nitro ベースの転送時暗号化 — 全リージョン対応（2026-07-20）

第 2 世代ファイルシステムで、Nitro System による転送時暗号化（encryption of data in transit）が**全リージョン**で利用可能になりました。第 1 世代は新たに 5 リージョン（Malaysia, New Zealand, Taipei, Thailand, Mexico）に拡張。

| 設計への影響 | 関連ノート |
|---|---|
| 「転送時暗号化が使えるリージョン」という制約がなくなった | [保存時の暗号化は自動、転送時は既定で無効](../domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md) |
| 第 2 世代 + Nitro 暗号化が全リージョン共通になり、リージョン選定基準がシンプルに | [スループットは 1 つの設定値では決まらない](../domains/performance/notes/where-throughput-is-determined-and-shared.md)（リージョン別上限セクション） |

出典: [Document History](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/document-history.html) — July 20, 2026

---

### 第 2 世代のリージョン拡張（2026-06-03）

第 2 世代（Multi-AZ 2, Single-AZ 2）が**Europe (London)、Asia Pacific (Hyderabad)、South America (São Paulo)、AWS GovCloud (US-West)** で利用可能に。

加えて 2026-05-01 に **Asia Pacific (New Zealand)** が全世代で利用可能に。

| 設計への影響 | 関連ノート |
|---|---|
| 第 1 世代の「リージョンで性能が半減する」問題が、第 2 世代へ移行すれば解消されるリージョンが増えた | [スループットは 1 つの設定値では決まらない](../domains/performance/notes/where-throughput-is-determined-and-shared.md) |
| GovCloud (US-West) で第 2 世代が使えるため、公共セクターの性能要件に対応しやすくなった | [業種別リソースマップ — 防衛/公共](industry-resource-map.md#防衛--公共) |

出典: [What's New — 2026/04](https://aws.amazon.com/about-aws/whats-new/2026/04/second-gen-amazon-fsx-ontap-regions/)

---

## 周辺サービスとの統合

### AWS Transfer Family が FSx for ONTAP をサポート（2026-01）

AWS Transfer Family 経由で **SFTP / FTPS / FTP** を使って FSx for ONTAP のファイルシステムに直接アクセス可能に。S3 Access Point を通じて接続し、既存の NFS/SMB アクセスと同時に利用できます。

| 設計への影響 | 関連ノート |
|---|---|
| 外部パートナーへのセキュアなファイル受け渡しに VPN や EC2 が不要に | [S3 AP は「S3 として使える」わけではない](../domains/data-utilization/notes/s3-access-point-constraints.md) |
| 「NFS/SMB + S3 AP + SFTP」の 4 プロトコル同時アクセスが可能に | [S3 AP は全リクエストを 1 つの ID で認可する](../domains/data-utilization/notes/reaching-data-without-copies.md) |
| IAM + S3 AP ポリシーによるアクセス制御はそのまま適用される | — |

出典: [What's New — 2026/01](https://aws.amazon.com/about-aws/whats-new/2026/01/aws-transfer-family-amazon-fsx-netapp-ontap/)

**ワークロード**: パートナー企業とのファイル交換（金融・物流・製造）、外部ベンダーからの定期データ受領、PCIDSS 環境での FTP 代替

---

### AWS Transform が FSx for ONTAP をサポート（GA, 2026-08）

AWS Transform（旧 AWS Application Migration Service / MGN）で、ブロックストレージのマイグレーション先として **FSx for ONTAP を選択可能**に。EBS に加えて FSx for ONTAP をターゲットにでき、VMware ワークロードの移行で ONTAP のストレージ機能を移行直後から利用できる。2026-06 に Public Preview として告知され、**2026-08-30 に GA**。

**スコープの限定**: GA したのは「**データボリューム**のターゲットストレージ種別」としての対応であり、VMware の**データストア**として FSx for ONTAP を提示する機能ではない。後者は次節の Amazon EVS の経路で、状態も異なる。ブートボリュームは常に EBS に残り、データボリュームが iSCSI で接続される。

| 設計への影響 | 関連ノート |
|---|---|
| VMware からの移行で「一度 EBS に移して後から NAS を構成する」手順が不要に | [切り戻せる時点はクライアントが書き始めた瞬間に閉じる](../playbooks/03-migrate/notes/where-the-rollback-window-closes.md) |
| MGN ベースの自動化と FSx for ONTAP の組み合わせで、SnapMirror 以外の移行パスが増えた | [業種別リソースマップ — sibling repos](industry-resource-map.md#sibling-リポジトリ一覧)（vmware-migration-ec2-ontap） |
| 移行後の LUN 配置が ONTAP の推奨と異なるため、移行後に整える工程が必要 | [LUN の並べ方が決めているのは復旧の粒度](../domains/block-storage/notes/lun-layout-decides-recovery-granularity.md) |
| **Finalize で物理容量が最大になる。移行データ 1 本分の追加容量が一時的に必要** | [AWS Transform の Finalize は後片付けではなく、物理容量が最大になる工程](../playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md) |

**移行時に見積もる制約**: GA 済みだが、設計時に効く制約がある。

| 制約 | 内容 |
|---|---|
| ブートボリューム | 常に EBS。FSx for ONTAP から直接ブートはできない |
| レプリケーション方式 | エージェント型のみ |
| ファイルシステム数 | 1 アカウントで同時に最大 5 台 |
| LUN 配置 | 1 ソースサーバー = 1 ボリューム内に複数 LUN。ONTAP 推奨の 1:1 ではないため、スナップショットポリシーや階層化をディスク単位に分けるには移行後に `lun move start` で移設する |
| ONTAP 設定の引き継ぎ | アクセス権限・quota・スナップショットポリシー・スケジュールは移行されない。ターゲット側で再設定する |
| Finalize | **不可逆**。FlexClone を親から分離しレプリケーションを停止する。実行前に受け入れテストを完了させる |
| 事前に無効化する設定 | 自動バックアップ（Finalize を阻害しうる）と ARP（レプリケーションボリューム削除を阻害しうる）。いずれもファイルシステム単位の設定であり、同一ファイルシステム上の他ボリュームにも影響する |

出典: [What's New — 2026/09](https://aws.amazon.com/about-aws/whats-new/2026/09/aws-transform-fsx-netapp-ontap-support/)、[AWS Transform Change log — 2026-08-30](https://docs.aws.amazon.com/transform/latest/userguide/change-log.html)、[FSx for ONTAP configuration（MGN ユーザーガイド）](https://docs.aws.amazon.com/mgn/latest/ug/fsx-ontap.html)

**検証レポート**: スコープの確定と実機での API レベル確認は sibling repo の [ATX FSx for ONTAP GA 検証レポート](https://github.com/Yoshiki0705/vmware-migration-ec2-ontap/blob/main/docs/ja/atx-fsxn-ga-verification.md) にある。レプリケーションから Finalize までを通した実測は [AWS Transform の Finalize は後片付けではなく、物理容量が最大になる工程](../playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md) に昇格させた。**SNAPSHOT フェーズがボリューム Snapshot、LAUNCH フェーズが FlexClone の作成である**ことも、そちらで時刻を突き合わせて確定している。最小 ONTAP バージョン要件は公開ドキュメントに記載が見つかっていない（2026-09-04 調査）。

---

### Amazon EVS が FSx for ONTAP と統合（2025-06 告知）

Amazon Elastic VMware Service（EVS）— VPC 内で VMware Cloud Foundation を実行するサービス — が、FSx for ONTAP を**外部データストア**として利用可能に。コンピュートとストレージの独立スケーリング、自動階層化によるコスト最適化が可能。前節の AWS Transform とは異なり、**VMware を継続利用したままストレージだけを FSx for ONTAP に寄せる**経路である。

**状態**: 2025-06 の What's New は public preview と記載している。現在の EVS ユーザーガイドに preview の表記はなく、検証済み機能として NFS v3 / NFS v4.1 / NVMe / iSCSI VMFS の各データストア、ゲスト mount の iSCSI ディスク、SnapCenter Plug-in for VMware vSphere、Expansion VLAN 経由のデプロイが列挙されている。ただし **GA 告知は確認できていない**（2026-09-04 調査、What's New と EVS ユーザーガイドを対象）。本番採用前に最新の提供状態を確認すること。

| 設計への影響 | 関連ノート |
|---|---|
| VMware から EC2 への全面移行を選ばなくても、FSx for ONTAP のストレージ機能が使える | [業種別リソースマップ — sibling repos](industry-resource-map.md#sibling-リポジトリ一覧)（vmware-migration-ec2-ontap） |
| ブロックは iSCSI と NVMe/TCP のどちらでも VMFS データストアになる。NVMe/TCP は第 2 世代かつ HA ペア 6 以下が条件 | [ブロックプロトコルの選択肢は世代と HA ペア数で先に狭まる](../domains/block-storage/notes/protocol-choice-is-bounded-before-you-choose.md) |
| Oracle Database on EVS + FSx for ONTAP の構成ガイドが出ている（re:Post） | [公開事例](../case-studies/public-case-studies.md) |
| SnapMirror による cross-region DR が EVS 構成でも利用可能 | [Snapshot があることと復旧できることは別](../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md) |

出典: [What's New — 2025/06](https://aws.amazon.com/about-aws/whats-new/2025/06/amazon-elastic-vmware-service-fsx-netapp-ontap/)、[Run high-performance workloads with Amazon FSx for NetApp ONTAP（EVS ユーザーガイド）](https://docs.aws.amazon.com/evs/latest/userguide/fsx-ontap.html)、[Configure FSx for NetApp ONTAP as a block datastore](https://docs.aws.amazon.com/evs/latest/userguide/config-fsx-iscsi-datastore.html)、[AWS Blog](https://aws.amazon.com/blogs/aws/introducing-amazon-elastic-vmware-service-for-running-vmware-cloud-foundation-on-aws)

---

### SQL Server ベストプラクティス構成ガイド（Blog, 2026-05）

AWS Storage Blog にて、FSx for ONTAP 上の SQL Server ワークロード向けの構成ベストプラクティスが公開。FlexClone による空間効率の高い開発・テスト環境のレプリカ構成を含む。

| 設計への影響 | 関連ノート |
|---|---|
| SQL Server FCI + FSx for ONTAP のリファレンス構成が公式化 | [公開事例 — SQL Server](../case-studies/public-case-studies.md#ワークロードからの探し方) |
| FlexClone による dev/test パターンは SaaS テナント設計と同じ発想 | [IaC の境界は API の表面で決まる](../playbooks/04-build/notes/what-iac-cannot-reach.md) |

出典: [AWS Storage Blog](https://aws.amazon.com/blogs/storage/best-practice-configuration-of-amazon-fsx-for-netapp-ontap-for-microsoft-sql-server-workloads/)

---

### Komprise との連携によるコスト最適化（Blog, 2026-07）

Komprise と FSx for ONTAP を組み合わせた、ハイブリッドクラウドのライフサイクル管理構成が公開。アクティブデータはエッジと FSx for ONTAP に、非アクティブデータは S3 等に自動配置。

| 設計への影響 | 関連ノート |
|---|---|
| FabricPool（容量プール階層化）とは別のアプローチでコスト最適化できる | [課金は「確保した量」と「使った量」に分かれる](../domains/cost/notes/provisioned-versus-consumed.md) |
| 製造業 3 PB 移行事例と同じ文脈 | [業種別リソースマップ — 製造](industry-resource-map.md#製造) |

出典: [AWS Storage Blog](https://aws.amazon.com/blogs/storage/cost-optimized-file-storage-with-amazon-fsx-for-netapp-ontap-and-komprise/)

---

### レガシーとモダンの橋渡し — S3 AP のサーバーレスパターン（Blog, 2026）

NFS/SMB で稼働するレガシーアプリとクラウドネイティブアプリを、データ複製なしに同一ストレージから同時に利用する 3 パターン（ECS Fargate / Lambda / Step Functions）を解説。イベント駆動で AI 推論・ログ変換・データセット加工を自動起動する構成。

| 設計への影響 | 関連ノート |
|---|---|
| 「S3 API でできること」の範囲がアプリケーションアーキテクチャに拡大 | [S3 AP は「S3 として使える」わけではない](../domains/data-utilization/notes/s3-access-point-constraints.md) |
| Fargate から S3 API で直接アクセスすれば NFS クライアント設定が不要 | [データ活用ドメイン — 動く実装](../domains/data-utilization/README.md#動く実装--sibling-リポジトリ) |

出典: [AWS Storage Blog](https://aws.amazon.com/blogs/storage/bridge-legacy-and-modern-applications-with-amazon-s3-access-points-for-amazon-fsx/)

---

### ハイブリッド HPC — 理研 × FlexCache × ParallelCluster（NetApp Blog）

理化学研究所のチームが採用したハイブリッド HPC 構成。オンプレミスの ONTAP に保存された研究データをクラウドへ移動せず、FlexCache で AWS 上にキャッシュのみを展開。ParallelCluster で GPU/CPU ノードをオンデマンドに起動し、ジョブ完了後に自動スケールイン。1,000 ノード規模への拡大を検討中。

| 設計への影響 | 関連ノート |
|---|---|
| FlexCache の「データを動かさない」特性が HPC バーストに有効な実例 | [スループットは 1 つの設定値では決まらない](../domains/performance/notes/where-throughput-is-determined-and-shared.md) |
| 書き込みワークロードにも対応可能（派生データを AWS 側で保持） | [S3 Burst on ONTAP Files](https://github.com/Yoshiki0705/s3-burst-on-ontap-files) |

出典: [NetApp Blog（日本語）](https://www.netapp.com/ja/blog/hybrid-hpc/)

---

### SFTP ファイル共有 — Transfer Family + S3 AP（Blog, 2026）

金融機関のユースケース。内部ユーザーは SMB/NFS、外部パートナーは SFTP で**同一ファイル**にアクセスする構成。データコピー不要。Transfer Family の認証と S3 AP の固定ファイルシステム ID による二重のセキュリティレイヤー。

| 設計への影響 | 関連ノート |
|---|---|
| 「NFS/SMB + S3 + SFTP」の 4 プロトコル同時アクセスの構成例 | [AD への依存は参加時ではなく生涯続く](../domains/multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) |
| 金融機関のコンプライアンス要件との組み合わせ | [業種別リソースマップ — 金融](industry-resource-map.md#金融) |

出典: [AWS Storage Blog](https://aws.amazon.com/blogs/storage/secure-sftp-file-sharing-with-aws-transfer-family-amazon-fsx-for-netapp-ontap-and-s3-access-points/)

---

### Oracle HA — Multi-AZ + Auto Scaling + Lambda（Architecture Blog, 2026）

FSx for ONTAP Multi-AZ を共有ストレージとして、EC2 Auto Scaling + Lambda + AWS Backup による Oracle HA を構築。RTO 2-5 分、RPO ≒ 0（同期 Multi-AZ レプリケーション）。AMI 管理を自動化し、フェイルオーバー後のインスタンスが最新構成で起動。

| 設計への影響 | 関連ノート |
|---|---|
| Oracle HA でクラスタソフトウェアを使わないアプローチ | [デプロイタイプは一度しか決められない](../playbooks/02-design/notes/deployment-type-is-decided-once.md) |
| 共有ストレージ + Auto Scaling のパターンは SQL Server FCI と同構造 | [公開事例 — SQL Server](../case-studies/public-case-studies.md#ワークロードからの探し方) |

出典: [AWS Architecture Blog](https://aws.amazon.com/blogs/architecture/building-highly-available-oracle-databases-with-amazon-fsx-for-netapp-ontap/)

---

### データディスカバリー — S3 AP + S3 Tables + Athena（Blog, 2026）

ファイルメタデータ（パス・サイズ・拡張子・最終アクセス日・エージ）を S3 AP 経由で収集し、Apache Iceberg テーブルとして Athena でクエリ可能にする CDK ソリューション。「どのフォルダが最も容量を消費しているか」「1 年以上アクセスされていないファイルはどれだけあるか」を SQL で即答。

| 設計への影響 | 関連ノート |
|---|---|
| 容量管理の判断材料を「推定」から「実測」に変える | [容量が余っていても書けなくなる](../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) |
| 階層化ポリシーの最適化に必要なアクセス頻度データが得られる | [課金は「確保した量」と「使った量」に分かれる](../domains/cost/notes/provisioned-versus-consumed.md) |

出典: [AWS Storage Blog](https://aws.amazon.com/blogs/storage/data-discovery-how-to-find-out-whats-on-your-amazon-fsx-for-netapp-ontap-volumes/)

---

### AD 環境での AI 分析 — S3 AP + Active Directory + Quick Suite（Blog, 2026）

Windows Active Directory 統合環境で S3 AP を構成し、AD グループ単位で AI 分析サービス（Amazon Quick Suite）へのアクセスを制御する方法。部門ごとにボリュームを分離し、AD グループで読み取り/書き込みを制御する構成例。

| 設計への影響 | 関連ノート |
|---|---|
| S3 AP の「全リクエストを 1 つの ID で認可する」制約を AD グループで補完するパターン | [S3 AP は全リクエストを 1 つの ID で認可する](../domains/data-utilization/notes/reaching-data-without-copies.md) |
| AD 参加 SVM での S3 AP 利用時の考慮事項 | [AD への依存は参加時ではなく生涯続く](../domains/multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) |
| **AD は S3 AP の前提ではありません。** この構成例は AD グループで認可を分ける 1 つのパターンで、**S3 AP 自体はローカルユーザーでも成立します**（実測）。また **AD グループで分けても、ファイルアクセス監査には AP に紐づく ID しか残りません** | [S3 Access Point の権限設計 — 評価順序と、絞り込みを担う 2 つの層](../domains/security-governance/notes/access-point-authorization-layers.md) |

出典: [AWS Storage Blog](https://aws.amazon.com/blogs/storage/enabling-ai-powered-analytics-on-enterprise-file-data-configuring-s3-access-points-for-amazon-fsx-for-netapp-ontap-with-active-directory/)

---

### Multi-AZ ML トレーニング — FlexCache + SnapMirror（GitHub, 2026-03）

GPU インスタンスが複数 AZ に分散する ML トレーニングで、FlexCache で読み取りキャッシュ、SnapMirror でチェックポイント非同期レプリケーションを行うアーキテクチャ。Single-AZ 2nd gen をオリジンに使い、コストを抑えつつ一貫したデータアクセスを実現。

| 設計への影響 | 関連ノート |
|---|---|
| FlexCache の読み取りキャッシュは ML データ配信に有効（キャッシュミス時 1-2 ms） | [スループットは 1 つの設定値では決まらない](../domains/performance/notes/where-throughput-is-determined-and-shared.md) |
| チェックポイントを各 AZ のローカルボリュームに書き、SnapMirror で集約 | [Snapshot があることと復旧できることは別](../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md) |

出典: [GitHub — kyongki/fsxn-multi-az-ml-training](https://github.com/kyongki/fsxn-multi-az-ml-training)

---

### Microsoft Entra ID 統合 — Entra Domain Services + VPN ブリッジ（Blog, 2026）

オンプレミス AD を廃止して Microsoft Entra ID に移行済みの環境で、FSx for ONTAP の SMB 認証を Entra Domain Services 経由で実現する構成。Entra ID → Entra Domain Services（マネージドドメインコントローラー）→ VPN → FSx for ONTAP SVM のドメイン参加。

| 設計への影響 | 関連ノート |
|---|---|
| AD 廃止後も FSx for ONTAP の SMB 認証が可能に（ただし Entra Domain Services が必要） | [AD への依存は参加時ではなく生涯続く](../domains/multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) |
| PTR レコード構成が FSx for ONTAP のみ追加で必要 | [ボリュームのセキュリティスタイル](../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) |

出典: [AWS Storage Blog](https://aws.amazon.com/blogs/storage/integrating-amazon-fsx-for-netapp-ontap-and-amazon-fsx-for-windows-file-server-with-microsoft-entra-id/)

---

### ストレージクォータ管理 — qtree ベースの容量ガバナンス（Blog, 2026）

共有ボリューム上のワークロードごとに容量上限を設定する構成。qtree + ツリークォータポリシールールで、ETL ジョブの暴走やログの肥大化による他ワークロードへの影響を防ぐ。ハードリミット・ソフトリミット・閾値アラートを組み合わせ、NFS/SMB 問わずストレージレイヤーで強制。

| 設計への影響 | 関連ノート |
|---|---|
| 「確保した量」の中をワークロードごとに区切れる | [課金は「確保した量」と「使った量」に分かれる](../domains/cost/notes/provisioned-versus-consumed.md) |
| 容量計画を「推定」から「制御」に変える手段 | [容量が余っていても書けなくなる](../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) |
| IaC で到達できない ONTAP レベルの設定の一例 | [IaC の境界は API の表面で決まる](../playbooks/04-build/notes/what-iac-cannot-reach.md) |

出典: [AWS Storage Blog](https://aws.amazon.com/blogs/storage/manage-storage-consumption-at-scale-with-quotas-on-amazon-fsx-for-netapp-ontap/)

---

## 2025 年後半のアップデート（設計に長期的な影響）

| 日付 | アップデート | 設計への影響 |
|---|---|---|
| 2025-09-30 | **Dual-stack IPv6 対応** | IPv6 クライアントからのアクセスが可能に。既存ファイルシステムのネットワークタイプを変更可能 |
| 2025-08-14 | **SSD ストレージ容量の縮小が可能**（第 2 世代） | コスト最適化で「一度確保したら下げられない」制約がなくなった |
| 2025-11-05 | **Secrets Manager 統合** | AD 資格情報を Secrets Manager で管理可能に。ローテーション運用が改善 |

---

## 更新の追跡方法

**Document History だけを追うと取りこぼします。** バックアップの別リージョン・別アカウントコピー（2026-08）は What's New が 2 本出ている一方で、**ONTAP ユーザーガイドの Document History には項目がありません**。このリポジトリは「復元先は同一リージョン」という記述を制約として複数のドキュメントに書いていたため、前提が崩れたことに気づくのが遅れました。

| 情報源 | 追う理由 |
|---|---|
| [Document History](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/document-history.html) | ドキュメント本文の変更が日付付きで並ぶ。**ただし全件ではありません** |
| What's New（FSx for ONTAP と **AWS Backup の両方**） | 機能追加の一次情報。周辺サービス側にしか出ない項目があります |
| ユーザーガイドの該当ページ本文 | **制約を引用している箇所は、引用元の現行版を読み直す**。History に出ない改訂があります |

**制約を根拠に設計判断を書いている箇所は、定期的に出典の現行版と突き合わせてください。** 「できない」という記述は、機能追加によって静かに古くなります。

---

## このドキュメントの更新方針

このファイルは四半期ごとに更新し、古い内容は各ドメインのノートに昇格させます。「ノートに書くべき設計判断の変更」と「知っておくと便利な新機能の紹介」を区別し、前者を優先します。

---

## 関連ドキュメント

- [Reference](README.md) — このディレクトリのハブ
- [業種別リソースマップ](industry-resource-map.md) — 業種から引く横断索引
- [知見の分類ポリシー](../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)
