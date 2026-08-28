---
title: 公開されている FSx for ONTAP の事例 — 業種とワークロードから探す
lifecycle: [assess, design]
domains: [cost, performance, data-protection]
evidence: documented
source: https://aws.amazon.com/fsx/netapp-ontap/resources/
lang: ja
---

# 公開されている FSx for ONTAP の事例

[🏠 リポジトリトップ](../../../README.md) | [Case Studies](README.md)

---

## 結論

**自分の業種とワークロードに近い事例から読んでください。** 下に 2 つの索引があります。同じ事例が両方に出てきます。

- [業種から探す](#業種から探す)
- [ワークロードから探す](#ワークロードから探す)

そして読むときの前提が 1 つあります。**公開事例はベンダーまたは AWS が publish したものです。** 導入した組織が同意した範囲で書かれており、**多くは ONTAP バージョン・リージョン・構成・測定方法を明記していません。**

つまり **事例に載っている数値は、このリポジトリの区分では `documented` にも届きません。** 「その組織がそう発表した」という事実です。設計の根拠にする前に、自環境で測る対象として扱ってください。

> **区分**: `documented` — 各事例の URL と、そこに書かれている論点の所在を記載しています。
> **事例中の数値は再掲しません。** 測定条件が明記されていない数値を切り出すと誤用されます。
> 数値が必要な場合はリンク先を読み、**自環境で測り直す前提**で扱ってください。

---

## 業種から探す

| 業種 | 事例 | 何が読めるか |
|---|---|---|
| エネルギー | [Phillips 66](https://aws.amazon.com/solutions/case-studies/phillips66-migration-case-study/) | オンプレミスからのクラウド移行。移行そのものを主題にした AWS 公式事例 |
| 半導体 / EDA | [NVIDIA](https://aws.amazon.com/jp/solutions/case-studies/nvidia-case-study/) | オンプレミス EDA 環境のハイブリッド拡張。FlexCache + write-shunt filer で 15-20 種のフローを同時実行。5,000 並列ジョブを 5 ターゲットに分散 |
| 半導体 / EDA | [Amazon Annapurna Labs](https://aws.amazon.com/fsx/netapp-ontap/customers/) | ストレージ容量を 2 倍にスケールしつつ性能維持。100% 可用性を実現し、ストレージコスト 35% 削減 |
| 半導体 / EDA | [Arm](https://aws.amazon.com/solutions/case-studies/arm-ltd-case-study/) | チップ設計ワークロードの性能スケール。EDA の代表例 |
| 半導体 / 自動車 | [Vitesco](https://aws.amazon.com/fsx/netapp-ontap/customers/) | コンピュートコストの可視化と制御 |
| 金融（クレジットカード） | [PayPay カード](https://aws.amazon.com/jp/solutions/case-studies/paypay-card-case-study/) | メインフレームからの基幹システム移行。PCIDSS 準拠、Multi-AZ 構成、大阪 DR。ファイル共有にレスポンス性で FSx for ONTAP を採用。**日本のクレジットカード事業会社初の AWS 移行** |
| 金融（ウェルスマネジメント技術） | [AdvisorEngine](https://www.netapp.com/customers/advisorengine-amazon-fsx-ontap-case-study/) | PoC を経た SQL Server の再アーキテクチャ。コストと性能の両方を論点にしています |
| 金融（ウェルスマネジメント） | [Orion Advisor Solutions](https://aws.amazon.com/fsx/netapp-ontap/customers/) | コスト削減が主要な導入効果 |
| 金融（ポストトレード） | [Arcesium](https://aws.amazon.com/fsx/netapp-ontap/customers/) | ストレージ効率 53%、コスト 46% 削減、リフレッシュコスト 80% 削減、Snapshot 速度 5 倍。DR 環境の有効活用 |
| 金融（銀行） | [Banco Pan](https://aws.amazon.com/solutions/case-studies/banco-pan-case-study/) | **コスト 51% 削減**。ブラジルのデジタルバンク |
| 金融（市場データ） | [S&P Global Market Intelligence](https://aws.amazon.com/blogs/storage/why-sp-global-chose-amazon-fsx-for-netapp-ontap-to-achieve-high-availability-and-disaster-recovery-for-sql-server/) | SQL Server FCI DR。SnapMirror で RPO 短縮。「使った分だけ」の課金に言及 |
| ヘルスケア（SaaS 提供） | [Infor](https://www.netapp.com/customers/infor/) | **シングルテナント構成を個別に調整する**設計。SaaS 事業者側の視点 |
| ヘルスケア（SaaS） | [AdvancedMD](https://aws.amazon.com/fsx/netapp-ontap/customers/) | ボリュームサイズ管理からの解放。圧縮・重複排除・階層化で想定以上のコスト削減 |
| 医療機器 | [オンプレミス SQL Server の移行](https://docs.netapp.com/us-en/netapp-solutions-databases/mssql/customer-usecase-mssql-fsx1.html) | 課題・解決・結果の形式で書かれた SQL Server 移行。技術文書側に置かれています |
| 通信（BSS/OSS） | [Amdocs](https://aws.amazon.com/solutions/case-studies/amdocs-case-study/) | 通信向けソフトウェアのストレージ性能スケーリング |
| 通信（SaaS 提供） | [MYCOM OSI](https://aws.amazon.com/jp/blogs/news/how-mycom-osi-optimized-saas-storage-with-amazon-fsx-for-netapp-ontap/)（日本語） | SaaS のストレージのコストパフォーマンス改善 |
| 公共医療・教育 | [NetApp の事例まとめ](https://www.netapp.com/blog/aws-fsxo-blg-customer-success-stories-with-amazon-fsx-for-netapp-ontap/) | eHealth NSW（公共医療）と Pearson（教育）を含む複数事例の入口 |
| 防衛 / 公共 | [Peraton](https://www.netapp.com/customers/peraton-amazon-fsx-case-study/) | セキュリティ重視のオンプレミス移行。FedRAMP / DoD SRG 対応 |
| 保険 | [Nordcloud: Swiss insurer](https://nordcloud.com/case-studies/swiss-insurance-provider/) | オンプレミス NetApp からの無停止 AWS 移行。複数リージョン |
| 物流 / VDI | [Allcargo](https://aws.amazon.com/blogs/storage/how-allcargo-migrated-vdi-workload-to-amazon-fsx-using-aws-datasync/) | 3,500 VDI ユーザーのグローバル移行。ログインストーム対策。DataSync + SnapMirror |
| 物流 | [Kerry Logistics](https://aws.amazon.com/fsx/netapp-ontap/customers/) | セキュアな情報共有。フルマネージドで物理インフラの運用負荷を排除 |
| エンタープライズコンテンツ管理 | [Hyland](https://aws.amazon.com/fsx/netapp-ontap/customers/) | 2 PB → 14 PB（3 年で 7 倍）。数百万の小ファイルの DR レプリケーション |
| スポーツ / 小売 | [adidas](https://aws.amazon.com/fsx/netapp-ontap/customers/) | 大規模インスタンスでの高速処理。リストアの迅速性 |
| 製造 | [Komprise + FSx for ONTAP](https://www.komprise.com/blog/manufacturing-case-study-komprise-amazon-fsx-for-ontap/) | 3 PB 移行、コスト 50% 以上削減。工場データの一元化 |
| メディア・エンタメ | [メディア業界の事例](https://www.netapp.com/blog/benefits-of-cloud-computing-in-media-industry/) | 制作ワークフローを主題にした事例群 |
| メディア・エンタメ（アニメ制作） | [コミックス・ウェーブ・フィルム](https://aws.amazon.com/jp/solutions/case-studies/comix-wave-film/) | クラウドで最大 300 台同時レンダリング。55.61 TB / 1,690 万ファイル。DR 対策として 7 日分バックアップ。CG 部以外の全部署で FSx for ONTAP を採用 |
| メディア・エンタメ（動画配信） | [Mediasite (Sonic Foundry)](https://aws.amazon.com/fsx/netapp-ontap/customers/) | オンプレミスからの移行でコンテンツ配信を迅速スケール。運用負荷削減 |
| 航空 / eVTOL | [Joby Aviation](https://aws.amazon.com/blogs/industries/navigating-the-cloud-joby-aviations-plm-migration-to-aws/) | PLM（製品ライフサイクル管理）の AWS 移行 |
| ソフトウェア / DevOps | [Atlassian](https://aws.amazon.com/partners/success/atlassian-netapp/) | — |
| AI / ドキュメント | [Vaultedge](https://aws.amazon.com/fsx/netapp-ontap/customers/) | ドキュメント AI スタートアップ。データのスケーラビリティ・永続性・可用性を確保 |
| SaaS / 計画プラットフォーム | [Anaplan](https://aws.amazon.com/fsx/netapp-ontap/customers/) | 6 か月間に複数の重大障害を経験後に移行。グローバルスケール。前ベンダーのパブリッククラウド不足が契機 |
| 旅行 | [Ávoris](https://aws.amazon.com/fsx/netapp-ontap/customers/) | Astra Trident + コンテナで数百の同時 DevOps プロジェクトを展開。需要変化への迅速な適応 |
| SAP | [Inventum](https://aws.amazon.com/fsx/netapp-ontap/customers/) | SAP HANA 環境。SnapMirror で環境の即時コピー。「将来に備えた SAP 環境」 |
| エンジニアリング / 建設 | [Ayesa](https://aws.amazon.com/fsx/netapp-ontap/customers/) | Global File Cache で拠点間ファイル共有。自動階層化でコスト最適化 |
| 環境サービス | [Veolia](https://aws.amazon.com/fsx/netapp-ontap/customers/) | IaC + 自動階層化でオンプレミスより高いスケーラビリティとコスト効率。アプリケーション変更なしで移行 |
| 教育（ERP） | [Pearson](https://aws.amazon.com/fsx/netapp-ontap/customers/) | ミッションクリティカルな ERP のデータリフレッシュが 10 倍高速化。ジョブ性能 3 倍。RTO/RPO を時間単位から分単位に |
| 教育（大学向け SaaS） | [Universitas XXI](https://aws.amazon.com/fsx/netapp-ontap/customers/) | DR 環境へのデータ複製。RPO/RTO 要件を運用上の複雑さなしに達成 |
| 教育（LMS） | [Blackboard (Anthology)](https://aws.amazon.com/fsx/netapp-ontap/customers/) | 30 年来の NetApp 利用。運用負荷 90% 削減 |
| 動物医薬品 | [Zenex](https://aws.amazon.com/fsx/netapp-ontap/customers/) | レガシー Windows ファイルサーバーからの移行。29% のストレージ最適化 |
| IT（自社導入） | [NetApp IT](https://www.netapp.com/customers/it-use-cases/amazon-fsx/) / [ハイブリッドクラウド戦略](https://www.netapp.com/customers/it-use-cases/fsx-ontap-hybrid-cloud-strategy/) | **ベンダー自身の IT 部門**による導入。複数リージョンへの展開に触れています |
| 業種非公開 | [ストレージ TCO を 28% 削減](https://aws.amazon.com/blogs/storage/how-a-customer-reduced-storage-tco-by-28-with-amazon-fsx-for-netapp-ontap/) | **FlexCache の write-back を含む拠点間構成**。前提条件が具体的に書かれています |

**業種が一致しなくても、ワークロードが一致するなら読む価値があります。** 逆も同様です。

---

## ワークロードから探す

| ワークロード | 事例・資料 | 論点 |
|---|---|---|
| オンプレミス NAS からの移行 | [Phillips 66](https://aws.amazon.com/solutions/case-studies/phillips66-migration-case-study/) / [Nordcloud: Swiss insurer](https://nordcloud.com/case-studies/swiss-insurance-provider/) / [Veolia](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [移行手順の解説](https://aws.amazon.com/blogs/storage/migrating-on-premises-file-shares-to-amazon-fsx-for-netapp-ontap/) | 移行方式と切り替え。**Veolia は IaC でアプリケーション変更なしに移行**。手順側は [切り戻せる時点](../playbooks/03-migrate/notes/where-the-rollback-window-closes.md) と対応します |
| SQL Server（HA / DR） | [S&P Global](https://aws.amazon.com/blogs/storage/why-sp-global-chose-amazon-fsx-for-netapp-ontap-to-achieve-high-availability-and-disaster-recovery-for-sql-server/) / [AdvisorEngine](https://www.netapp.com/customers/advisorengine-amazon-fsx-ontap-case-study/) / [医療機器メーカーの移行](https://docs.netapp.com/us-en/netapp-solutions-databases/mssql/customer-usecase-mssql-fsx1.html) / [ベストプラクティス](https://aws.amazon.com/blogs/storage/best-practice-configuration-of-amazon-fsx-for-netapp-ontap-for-microsoft-sql-server-workloads) | FCI DR + SnapMirror、再アーキテクチャとコスト。SQL Server 構成の公式ガイドもあります |
| EDA / チップ設計 | [NVIDIA](https://aws.amazon.com/jp/solutions/case-studies/nvidia-case-study/) / [Amazon Annapurna Labs](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [Arm](https://aws.amazon.com/solutions/case-studies/arm-ltd-case-study/) / [Vitesco](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [IBM LSF との組み合わせ](https://aws.amazon.com/blogs/industries/eda-scale-with-fsx-for-netapp-ontap-and-ibm-lsf/) | **NVIDIA は FlexCache + write-shunt で 5,000 並列ジョブ**。**Annapurna は容量 2 倍 + コスト 35% 削減**。設計指針は下の EDA 資料にあります |
| SAP | [Inventum](https://aws.amazon.com/fsx/netapp-ontap/customers/) | SAP HANA 環境。SnapMirror で環境の即時コピー。前の環境より高いコスト効率 |
| VDI / ファイルサーバー移行 | [Allcargo](https://aws.amazon.com/blogs/storage/how-allcargo-migrated-vdi-workload-to-amazon-fsx-using-aws-datasync/) / [PayPay カード](https://aws.amazon.com/jp/solutions/case-studies/paypay-card-case-study/) / [Zenex](https://aws.amazon.com/fsx/netapp-ontap/customers/) | ログインストーム対策。DataSync で ACL 保持。**Zenex はレガシー Windows サーバーから 29% 最適化** |
| SaaS / マルチテナント | [Hyland](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [Infor](https://www.netapp.com/customers/infor/) / [MYCOM OSI](https://aws.amazon.com/jp/blogs/news/how-mycom-osi-optimized-saas-storage-with-amazon-fsx-for-netapp-ontap/) / [Anaplan](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [AdvancedMD](https://aws.amazon.com/fsx/netapp-ontap/customers/) | **Hyland は 2 PB → 14 PB（7 倍）。Anaplan は前ベンダーの障害を機に移行**。AdvancedMD は圧縮・重複排除で想定以上の削減 |
| 拠点間・ハイブリッド | [NVIDIA](https://aws.amazon.com/jp/solutions/case-studies/nvidia-case-study/) / [Ayesa](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [TCO 28% 削減](https://aws.amazon.com/blogs/storage/how-a-customer-reduced-storage-tco-by-28-with-amazon-fsx-for-netapp-ontap/) / [NetApp IT](https://www.netapp.com/customers/it-use-cases/fsx-ontap-hybrid-cloud-strategy/) | FlexCache / Global File Cache でオンプレミスを拡張。**Ayesa は File2Cloud アーキテクチャ**。適用条件は [FlexCache が効く条件](../domains/data-utilization/notes/reaching-data-without-copies.md#flexcache-が効く条件) にあります |
| 映像制作 / レンダリング | [コミックス・ウェーブ・フィルム](https://aws.amazon.com/jp/solutions/case-studies/comix-wave-film/) / [Mediasite](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [メディア業界の事例](https://www.netapp.com/blog/benefits-of-cloud-computing-in-media-industry/) | **300 台同時レンダリング、55 TB / 1,690 万ファイル**。Mediasite はコンテンツ配信のスケール |
| PLM / 製品設計 | [Joby Aviation](https://aws.amazon.com/blogs/industries/navigating-the-cloud-joby-aviations-plm-migration-to-aws/) | eVTOL の PLM（製品ライフサイクル管理）を AWS へ移行 |
| AI / ドキュメント処理 | [Vaultedge](https://aws.amazon.com/fsx/netapp-ontap/customers/) | ドキュメント AI スタートアップ。データのスケーラビリティ・永続性・可用性 |
| コスト最適化 / 大量データ移行 | [Banco Pan](https://aws.amazon.com/solutions/case-studies/banco-pan-case-study/) / [Komprise + FSx for ONTAP](https://www.komprise.com/blog/manufacturing-case-study-komprise-amazon-fsx-for-ontap/) / [Arcesium](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [Orion](https://aws.amazon.com/fsx/netapp-ontap/customers/) | **Banco Pan 51% 削減、Arcesium 46% 削減 + リフレッシュ 80% 削減**。課金構造は [確保と消費](../domains/cost/notes/provisioned-versus-consumed.md) を参照 |
| データ保護 / DR | [Peraton](https://www.netapp.com/customers/peraton-amazon-fsx-case-study/) / [コミックス・ウェーブ・フィルム](https://aws.amazon.com/jp/solutions/case-studies/comix-wave-film/) / [Universitas XXI](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [Pearson](https://aws.amazon.com/fsx/netapp-ontap/customers/) | FedRAMP 認証、DR 7 日間保持、**Pearson は RTO/RPO を時間→分に短縮**。制約は [Snapshot と復旧](../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md) を参照 |
| 複数リージョン展開 | [NetApp IT](https://www.netapp.com/customers/it-use-cases/amazon-fsx/) / [Nordcloud: Swiss insurer](https://nordcloud.com/case-studies/swiss-insurance-provider/) / [Anaplan](https://aws.amazon.com/fsx/netapp-ontap/customers/) | Anaplan はグローバル SaaS 基盤。制約は [デプロイタイプは一度しか決められない](../playbooks/02-design/notes/deployment-type-is-decided-once.md) と併読 |
| 大規模バッチ / HPC | [NVIDIA](https://aws.amazon.com/jp/solutions/case-studies/nvidia-case-study/) / [Amazon Annapurna Labs](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [adidas](https://aws.amazon.com/fsx/netapp-ontap/customers/) | **NVIDIA 6,202 タスク/週**。Annapurna は 100% 可用性を維持しつつスケール |
| Kubernetes / コンテナ | [MYCOM OSI](https://aws.amazon.com/jp/blogs/news/how-mycom-osi-optimized-saas-storage-with-amazon-fsx-for-netapp-ontap/) / [Ávoris](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [Infor](https://www.netapp.com/customers/infor/) / [EKS + Trident](https://aws.amazon.com/blogs/storage/run-containerized-applications-efficiently-using-amazon-fsx-for-netapp-ontap-and-amazon-eks/) | **Ávoris は数百の同時 DevOps プロジェクト**。Infor は EKS + Raima/SQLite。Trident CSI + FlexClone |
| PCIDSS / コンプライアンス | [PayPay カード](https://aws.amazon.com/jp/solutions/case-studies/paypay-card-case-study/) / [Peraton（FedRAMP / DoD SRG）](https://www.netapp.com/customers/peraton-amazon-fsx-case-study/) | セキュアネットワーク分離。暗号化の既定は [プラットフォームが与えるもの](../domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md) を参照 |
| ERP / ミッションクリティカル | [Pearson](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [adidas](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [Blackboard (Anthology)](https://aws.amazon.com/fsx/netapp-ontap/customers/) | **Pearson はリフレッシュ 10 倍高速化、ジョブ性能 3 倍**。Blackboard は運用負荷 90% 削減 |
| 拠点間ファイル共有 | [Kerry Logistics](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [Ayesa](https://aws.amazon.com/fsx/netapp-ontap/customers/) / [Hyland](https://aws.amazon.com/fsx/netapp-ontap/customers/) | セキュアな情報共有。Global File Cache + 自動階層化。数百万の小ファイル DR |

---

## 業種固有の設計資料

**事例ではありませんが、業種の要件に踏み込んだ資料です。** 事例より設計の判断材料になります。

| 業種 | 資料 | 内容 |
|---|---|---|
| 半導体 / EDA | [EDA ワークロードのベストプラクティス（PDF）](https://d1.awsstatic.com/fsx/FSx_for_ONTAP_EDA_Best_Practices_2.pdf) | EDA クラスタの構成、ボリュームとディレクトリ設計、データ種別、性能要件、サイジング |
| 金融 | [FSI 向けサービス解説](https://aws.amazon.com/blogs/industries/fsi-services-spotlight-featuring-amazon-fsx-for-netapp-ontap/) | 金融業界で問われる論点に沿った整理。[日本語版](https://aws.amazon.com/jp/blogs/news/fsi-services-spotlight-featuring-amazon-fsx-for-netapp-ontap/) もあります |
| ヘルスケア（EHR） | TR-4937: EHR on AWS | 本番と DR の構成、性能・データ保護・移行の考慮事項。NetApp の技術レポート番号で検索してください |

TR-4937 を URL で載せていないのは、**配布 URL が変わりやすいためです。** 番号で引くほうが長持ちします。

---

## 読むときに確認すること

**公開事例は「できた」ことを示しますが、「なぜその値になったか」は多くの場合書かれていません。** 次の観点で読むと、自分の設計に持ち出せる部分が判別できます。

| # | 確認すること | 書かれていない場合の扱い |
|---|---|---|
| 1 | ONTAP バージョン | 記載がなければ、バージョン依存の挙動は前提にできません |
| 2 | リージョン | **第 1 世代は 4 つのリージョン以外で上限が半分になります。** 記載がなければ性能値は比較できません |
| 3 | デプロイタイプと世代 | 上限とスケールアウトの可否が変わります |
| 4 | スループット容量と SSD IOPS の設定値 | 性能値の前提です |
| 5 | 測定方法（ツール・並列度・ファイルサイズ・回数） | 記載がなければ再現できません |
| 6 | 比較対象の構成 | 「削減率」は比較元が分からないと意味を持ちません |
| 7 | 発表時期 | 機能は変わります。古い事例は当時の制約で書かれています |

**多くの事例は 1 から 6 のいくつかを書いていません。** それは事例の欠陥ではなく、事例という形式の性質です。**数値を持ち出すのではなく、論点の所在を知るために読んでください。**

区分の考え方は [知見の分類ポリシー](../evidence-policy.md) にあります。

---

## 事例を継続的に探す

個別の事例は増減します。**一覧ページから引くほうが確実です。**

| 入口 | 内容 |
|---|---|
| [FSx for ONTAP のリソースページ](https://aws.amazon.com/fsx/netapp-ontap/resources/) | AWS 公式のリソース集約 |
| [AWS Storage Blog の FSx for ONTAP カテゴリ](https://aws.amazon.com/blogs/storage/category/storage/amazon-fsx-netapp-ontap/) | 新しい記事が最初に出る場所 |
| [NetApp の事例まとめ](https://www.netapp.com/blog/aws-fsxo-blg-customer-success-stories-with-amazon-fsx-for-netapp-ontap/) | 複数事例の入口 |

情報源の種類ごとの重みづけは [公開されている一次情報と事例の入口](public-references.md) にあります。**仕様・上限を確認したい場合はそちらが先です。**

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| 公開事例の数値を設計の根拠にできる | 測定条件が明記されていないものが多く、**再現できません** |
| 削減率がそのまま自環境に当てはまる | 比較元の構成が分からなければ意味を持ちません |
| 同じ業種の事例だけ読めばよい | **ワークロードが一致するほうが参考になる場合があります** |
| 事例に書かれていない項目は重要でない | 事例という形式では書かれないだけです。設計では必要です |
| ベンダー公開の事例だから信頼度が高い | 発表者が同意した範囲の記述です。区分としては実測の代わりになりません |
| 事例が少ない業種では使えない | 事例の数は採用可否の指標ではありません。要件との一致で判断します |

---

## 更新について

**リンク切れや新しい事例に気づいたら Issue でお知らせください。** 個別の事例は公開・非公開が変わります。

このページは**網羅を目的にしていません。** 業種とワークロードから当たりをつけられる程度の密度を保つことを目的にしています。

---

## 関連ドキュメント

- [Case Studies](README.md) — このディレクトリのハブ
- [公開されている一次情報と事例の入口](public-references.md) — 情報源の種類と重みづけ
- [知見の分類ポリシー](../evidence-policy.md) — 事例中の数値をどう扱うか
- [移行方式 決定ツリー](../reference/decision-trees/migration-method.md) — 移行方式の選択
- [比較マトリクス](../reference/comparison/) — 選択肢のトレードオフ

---

[🏠 リポジトリトップ](../../../README.md) | [Case Studies](README.md)
