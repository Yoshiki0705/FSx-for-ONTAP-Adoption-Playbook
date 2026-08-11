---
title: 直近のアップデートと設計への影響 — 2026 年 5〜8 月
lifecycle: [design, build, operate]
domains: [performance, cost, security-governance, data-utilization]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/document-history.html
lang: ja
---

# 直近のアップデートと設計への影響

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

---

## 結論

**2026 年 5〜8 月に、設計判断に影響するアップデートが 3 つの軸で出ています。**

1. **リージョン拡張と世代制限の緩和** — 第 2 世代が使えるリージョンが増え、性能上限の格差が縮まりつつある
2. **マルチプロトコル統合の拡大** — Transfer Family (SFTP/FTPS/FTP) が S3 AP 経由で FSx for ONTAP に接続可能に
3. **VMware 移行パスの追加** — AWS Transform と Amazon EVS が FSx for ONTAP をストレージターゲットとしてサポート

以下は各アップデートの概要と、このリポジトリの既存ノートとの対応です。

> **区分**: `documented` — すべて AWS 公式 What's New / Document History / Blog の記載に基づきます。
> 具体的なスループット値やレイテンシの実測は含みません。

---

## FSx for ONTAP 本体のアップデート

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

### AWS Transform が FSx for ONTAP をサポート（Public Preview, 2026-06）

AWS Transform（旧 AWS Application Migration Service / MGN）で、ブロックストレージのマイグレーション先として **FSx for ONTAP を選択可能**に。EBS に加えて FSx for ONTAP をターゲットにでき、VMware ワークロードの移行で NAS ストレージの継続利用が可能。

| 設計への影響 | 関連ノート |
|---|---|
| VMware からの移行で「一度 EBS に移して後から NAS を構成する」手順が不要に | [切り戻せる時点はクライアントが書き始めた瞬間に閉じる](../playbooks/03-migrate/notes/where-the-rollback-window-closes.md) |
| MGN ベースの自動化と FSx for ONTAP の組み合わせで、SnapMirror 以外の移行パスが増えた | [業種別リソースマップ — sibling repos](industry-resource-map.md#sibling-リポジトリ一覧)（vmware-migration-ec2-ontap） |

出典: [What's New — 2026/06](https://aws.amazon.com/about-aws/whats-new/2026/06/aws-transform-vmware-fsx-for-ontap-preview/)

**注意**: Public Preview であり、本番利用には GA を待つことを推奨。

---

### Amazon EVS が FSx for ONTAP と統合（2025-06、GA）

Amazon Elastic VMware Service（EVS）— VPC 内で VMware Cloud Foundation を実行するサービス — が、FSx for ONTAP を **NFS 外部データストア**として利用可能に。コンピュートとストレージの独立スケーリング、自動階層化によるコスト最適化が可能。

| 設計への影響 | 関連ノート |
|---|---|
| VMware から EC2 への全面移行を選ばなくても、FSx for ONTAP のストレージ機能が使える | [業種別リソースマップ — sibling repos](industry-resource-map.md#sibling-リポジトリ一覧)（vmware-migration-ec2-ontap） |
| Oracle Database on EVS + FSx for ONTAP の構成ガイドが出ている（re:Post） | [公開事例](../case-studies/public-case-studies.md) |
| SnapMirror による cross-region DR が EVS 構成でも利用可能 | [Snapshot があることと復旧できることは別](../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md) |

出典: [What's New — 2025/06](https://aws.amazon.com/about-aws/whats-new/2025/06/amazon-elastic-vmware-service-fsx-netapp-ontap/)、[AWS Blog](https://aws.amazon.com/blogs/aws/introducing-amazon-elastic-vmware-service-for-running-vmware-cloud-foundation-on-aws)

---

### SQL Server ベストプラクティス構成ガイド（Blog, 2026-05）

AWS Storage Blog にて、FSx for ONTAP 上の SQL Server ワークロード向けの構成ベストプラクティスが公開。FlexClone による空間効率の高い開発・テスト環境のレプリカ構成を含む。

| 設計への影響 | 関連ノート |
|---|---|
| SQL Server FCI + FSx for ONTAP のリファレンス構成が公式化 | [公開事例 — SQL Server](../case-studies/public-case-studies.md#ワークロードから探す) |
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

## 2025 年後半のアップデート（設計に長期的な影響）

| 日付 | アップデート | 設計への影響 |
|---|---|---|
| 2025-09-30 | **Dual-stack IPv6 対応** | IPv6 クライアントからのアクセスが可能に。既存ファイルシステムのネットワークタイプを変更可能 |
| 2025-08-14 | **SSD ストレージ容量の縮小が可能**（第 2 世代） | コスト最適化で「一度確保したら下げられない」制約がなくなった |
| 2025-11-05 | **Secrets Manager 統合** | AD 資格情報を Secrets Manager で管理可能に。ローテーション運用が改善 |

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
