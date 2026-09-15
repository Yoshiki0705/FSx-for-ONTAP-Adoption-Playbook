---
title: 課題別 ISV / SaaS ソリューションマップ — 組み合わせが公表されている選択肢と、まだ確認できていないもの
lifecycle: [assess, design, build]
domains: [security-governance, data-protection, data-utilization, observability, block-storage]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-vscan.html
lang: ja
---

# 課題別 ISV / SaaS ソリューションマップ

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

---

## 結論

**この索引は「どの製品が良いか」に答えません。答えるのは 2 つです。**

- **その課題に対して、Amazon FSx for NetApp ONTAP との組み合わせが公表されている選択肢があるか**
- **このリポジトリに、その組み合わせを選ぶ前に読む判断ノートがあるか**

**2 番目を列として持つ理由は、索引の性格を読者が判別できるようにするためです。** 判断ノートがある行は、こちら側で一次情報を読んで制約を整理してあります。無い行は**リンク集としてのみ働きます。** 同じ表に混ぜたまま区別を示さないと、読者は「この索引はどこまで確認済みなのか」を判断できません。

**製品の形態は課題では決まりません。** 同じ課題に対して、EC2 に載せるソフトウェア・SaaS・AWS のマネージドサービスが並びます。だから形態は列の 1 つとして持ち、括りには使いません。

> **区分**: `documented` — 各行の出典の所在を記載しています。**製品の動作を当リポジトリで検証したものは、判断ノートの列に記載があるものだけ**です。検索日は各行に記載しています。

---

## 掲載基準

**次のいずれかを満たすものを本表に載せます。**

1. AWS または NetApp が publish した資料に、FSx for ONTAP との組み合わせが記載されている
2. ベンダー自身が FSx for ONTAP 対応を公式に告知している

**満たさないものは [掲載基準を満たさないもの](#掲載基準を満たさないもの) に分けます。** そこに置くことは「非対応」を意味しません。**「FSx for ONTAP を名指しした記述に到達できていない」という、こちらの調査状態の記録です。**

個人ブログ・コミュニティ記事は基準に含めません。**技術的に誤っているからではなく、その資料を根拠に `documented` を名乗ると出典の強さを偽ることになるためです。**

---

## 課題別索引

| 課題 | 選択肢の数 | 判断ノート | 節 |
|---|---|---|---|
| マルウェア / ウイルススキャン | 6 | **あり** | [マルウェア / ウイルススキャン](#マルウェア--ウイルススキャン) |
| アプリケーションの単一障害点の除去 | 1 | あり（原則のみ） | [アプリケーションの単一障害点の除去](#アプリケーションの単一障害点の除去) |
| NAS 移行とデータの可視化 | 2 | あり（移行方式） | [NAS 移行とデータの可視化](#nas-移行とデータの可視化) |
| ブロックを含むサーバー移行 | 1 | なし | [ブロックを含むサーバー移行](#ブロックを含むサーバー移行) |
| 既存バックアップ基盤への統合 | 1 | なし | [既存バックアップ基盤への統合](#既存バックアップ基盤への統合) |
| 監視・ログの集約 | 3 | **あり** | [監視・ログの集約](#監視ログの集約) |
| ファイル転送 / データ連携 | 0 | なし | [ファイル転送--データ連携](#ファイル転送--データ連携) |
| VMware ワークロードの移行と保護 | 2 | なし | [VMware ワークロードの移行と保護](#vmware-ワークロードの移行と保護) |

---

### マルウェア / ウイルススキャン

**この課題は AWS 自身のユーザーガイドに専用ページがあります。** 本表の中で、AWS のドキュメントが ISV 名を列挙している唯一の行です。

| 選択肢 | 形態 | 出典 | 検索日 |
|---|---|---|---|
| Deep Instinct / SentinelOne / Symantec / Trellix / Trend Micro / OPSWAT（ONTAP Vscan 経由） | EC2 に載せるソフトウェア（Vscan サーバー） | [AWS: Use NetApp ONTAP Vscan with FSx for ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-vscan.html) · [NetApp: Vscan パートナー解決策](https://docs.netapp.com/ja-jp/ontap/antivirus/vscan-partner-solutions.html) · [AWS Storage Blog](https://aws.amazon.com/jp/blogs/storage/securing-your-amazon-fsx-for-ontap-windows-share-smb-against-viruses/) | 2026-09-15 |

**選ぶ前に決まることが 4 つあります。** AD 参加の有無、対象プロトコル、`scan-mandatory` の設定、既定の除外条件。**6 社の差はこの 4 つの後にしか効きません。**

- 判断ノート: [ウイルス対策の選択はベンダーより前に決まる](../domains/security-governance/notes/vscan-scope-is-bounded-before-the-vendor.md)
- 決定木: [ウイルス対策の適用範囲をどこまでにするか](decision-trees/vscan-antivirus-scope.md)

---

### アプリケーションの単一障害点の除去

| 選択肢 | 形態 | 出典 | 検索日 |
|---|---|---|---|
| SIOS LifeKeeper | EC2 に載せるソフトウェア | [AWS Prescriptive Guidance ブログ](https://aws.amazon.com/jp/blogs/psa/high-availability-solution-with-sios-lifekeeper-and-amazon-fsx-for-netapp-ontap/) · [ベンダー告知（2024-11-28）](https://sios.jp/news/info/2024/20241128_lk-fsx.html) | 2026-09-15 |

**ベンダー告知に記載されている対応範囲**は、Linux 版が iSCSI と NFS、Windows 版が iSCSI です（LifeKeeper for Linux ver.9.9.0 / LifeKeeper for Windows ver.8.10.1、2024-11-28 開始）。

**判断ノートは製品名を主題にしていません。** 複数ホストから同じ LUN に書くときの調停はホスト側の責任である、という原則が先にあり、この製品はその責任を引き受ける実装の 1 つです。**原則側を読んでから製品を見てください。**

- 判断ノート: [共有ブロックが設計を変える条件 — 書き込み整合性の責任](../domains/block-storage/notes/when-shared-block-changes-the-design.md#ホスト側のクラスタ機能を担う製品)
- 決定木: [ブロックプロトコルとレイアウトの選択](decision-trees/block-protocol-and-layout.md)

---

### NAS 移行とデータの可視化

| 選択肢 | 形態 | 出典 | 検索日 |
|---|---|---|---|
| Komprise | SaaS（管理面）+ 移行ワーカー | [AWS Storage Blog: Cost-optimized file storage with FSx for ONTAP and Komprise](https://aws.amazon.com/blogs/storage/cost-optimized-file-storage-with-amazon-fsx-for-netapp-ontap-and-komprise/) · [ベンダー告知](https://www.komprise.com/blog/komprise-and-aws-fsx-for-netapp-ontap/) | 2026-09-15 |
| Datadobi StorageMAP | ソフトウェア | [ベンダー告知](https://datadobi.com/post_news/organizations-can-now-accelerate-journey-to-the-cloud-with-amazon-fsx-for-netapp-ontap-and-datadobis-storagemap/) | 2026-09-15 |

**AWS ネイティブの手立てが同じ課題に並びます。** AWS DataSync と、移行元が ONTAP なら NetApp SnapMirror。**製品を検討する前に方式が決まっている場合があります。**

- 決定木: [移行方式の選択](decision-trees/migration-method.md)
- 判断ノート: [ACL 保持は権限の問題であってツールの問題ではない](../playbooks/03-migrate/notes/preserving-acls-during-migration.md)
- 参考: 製造業の事例（3 PB 移行）は [業種別リソースマップ](industry-resource-map.md#製造) にあります

---

### ブロックを含むサーバー移行

| 選択肢 | 形態 | 出典 | 検索日 |
|---|---|---|---|
| Cirrus Data Migrate Cloud | ソフトウェア（ホストに導入） | [NetApp: FSx for ONTAP を使用した EC2 への VM 移行](https://docs.netapp.com/ja-jp/netapp-solutions-virtualization/migration/migrate-vms-to-ec2-fsxn-deploy.html) · [ベンダーページ](https://cirrusdata.com/cloud-migration-amazon-fsxn) | 2026-09-15 |

**このリポジトリに判断ノートはありません。** ブロックの移行方式そのものは扱っていますが、この製品を前提にした判断は整理していません。**手順は一次情報側にあります。**

---

### 既存バックアップ基盤への統合

| 選択肢 | 形態 | 出典 | 検索日 |
|---|---|---|---|
| Veeam Backup & Replication | ソフトウェア | [ベンダーユーザーガイド](https://helpcenter.veeam.com/docs/vbaws/guide/add_fsx_policy_byb.html) · [NetApp ONTAP プラグインのリリース情報](https://www.veeam.com/kb4904) | 2026-09-15 |

**制約が先に決まる行です。** ベンダーのユーザーガイドは、**AWS 向けの製品では FSx for ONTAP のクラウドネイティブバックアップを作成できず**、Backup & Replication 側のコンソールを使う、と記載しています。**「既存のバックアップ製品を使っているから同じ運用で入る」という前提が崩れる箇所です。**

**AWS ネイティブの手立てが並びます。** FSx for ONTAP のボリュームバックアップと AWS Backup、および ONTAP の Snapshot と SnapMirror。

- 判断ノート: [Snapshot があることと復旧できることは別](../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md)
- 判断ノート: [バックアップコピーはリストアするまでファイルシステムを持たない](../domains/data-protection/notes/backup-copies-across-regions-and-accounts.md)

---

### 監視・ログの集約

**この課題は既に専用のモジュールで扱っています。この索引では重複させません。**

| 選択肢 | 形態 | 扱っている場所 |
|---|---|---|
| Datadog / Splunk / Elastic ほか | SaaS | [Domain — 可観測性の経路 3](../domains/observability/README.md) |

**SaaS 経路を選ぶ場合、データの所在の確認事項が 7 件あります。** 粒度は後から足せますが、出したデータを出さなかったことにはできません。

- 決定木: [監視経路の選択](decision-trees/observability-route.md)
- 比較表: [監視経路の比較](comparison/observability-routes.md)
- 判断ノート: [経路は認証とアクセス経路で先に狭まる](../domains/observability/notes/route-choice-is-bounded-by-access-and-auth.md)

---

### ファイル転送 / データ連携

**掲載基準を満たす選択肢が 0 件です。** 詳細は [掲載基準を満たさないもの](#掲載基準を満たさないもの) にあります。

**AWS ネイティブの手立ては存在します。** AWS Transfer Family は FSx for ONTAP と S3 Access Points を組み合わせた SFTP 共有の構成が AWS Storage Blog に記載されています（[出典](https://aws.amazon.com/blogs/storage/secure-sftp-file-sharing-with-aws-transfer-family-amazon-fsx-for-netapp-ontap-and-s3-access-points/)、検索日 2026-09-15）。

---

### VMware ワークロードの移行と保護

| 選択肢 | 形態 | 出典 | 検索日 |
|---|---|---|---|
| VMware HCX（移行） | ソフトウェア | [NetApp: HCX を使用した FSx for ONTAP データストアへの移行](https://docs.netapp.com/ja-jp/netapp-solutions-cloud/vmware/vmw-aws-vmc-migrate-hcx.html) | 2026-09-15 |
| Veeam Backup & Replication（NFS データストア上の VM の保護） | ソフトウェア | [NetApp: VMware Cloud での Veeam のバックアップとリストア](https://docs.netapp.com/ja-jp/netapp-solutions-cloud/vmware/vmw-aws-vmc-backup-restore-veeam.html) | 2026-09-15 |

**判断ノートはありません。** VMware 側の構成はこのリポジトリの範囲外で、**sibling リポジトリ** [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) に実装があります。

---

## 掲載基準を満たさないもの

**ここに置くことは「非対応」を意味しません。** こちらが FSx for ONTAP を名指しした記述に到達できていない、という調査状態の記録です。

| 候補 | 課題 | 確認できたこと | 到達できなかったこと | 検索日 |
|---|---|---|---|---|
| NEC CLUSTERPRO X | アプリケーションの単一障害点の除去 | AWS 向けの HA クラスタ構築ガイド（Linux / Windows、複数版）と動作確認済みソフトウェア一覧が公開されています。HULFT を AWS 上で冗長化する手順の記事もあります | **FSx for ONTAP を名指しした対応記述**。上記の資料群の中で確認できませんでした | 2026-09-15 |
| HULFT | ファイル転送 / データ連携 | HULFT10 for Container Services が Amazon ECS / AWS Fargate と Amazon S3 に対応していること。ベンダー技術者による AWS 連携記事が複数あること | **FSx for ONTAP との組み合わせを記載した資料**。0 件でした | 2026-09-15 |

**この 2 行を落とさずに置く理由**は、日本の読者がこの課題領域で必ず想起する製品だからです。**行が無いと「調べていない」のか「非対応」のかを読者が区別できません。**

**ベンダーへの確認は行っていません。** 上の表は公開情報の検索結果のみです。

---

## 検証予定の項目

**HULFT については、公開資料が無いので自環境で測る計画です。** 現時点では `hypothesis` としても本表に載せません（**未検証の推論を索引に混ぜると、掲載基準の意味が消えます**）。

| # | 測る対象 | なぜこれを測るか |
|---|---|---|
| 1 | FSx for ONTAP の NFS ボリュームを配信先にした集配信の成否と整合性 | 組み合わせが成立するかの最小の問い |
| 2 | ファイルシステムのフェイルオーバー中の転送の挙動（継続するか / 再送されるか / 失敗するか） | **マネージドなフェイルオーバーとファイル転送ミドルウェアの相互作用。** 公開資料が無い部分で、かつ設計判断に効きます |

**スループットは測りません。** クライアントのインスタンスタイプと配置に支配される値になり、製品の性質を表さないためです。同じ理由は [公開ベンチマークの読み方](../domains/block-storage/notes/when-shared-block-changes-the-design.md#公開ベンチマークの読み方) にあります。

**検証環境は 24 時間以内に削除します。** 不可逆な保持設定（SnapLock、Snapshot locking）は使いません。

---

## 選び方

**「どれが良いか」ではなく、決まっている前提から引きます。**

| 手元の状況 | 索引の使い方 |
|---|---|
| 課題が決まっていて、製品はまだ決まっていない | **判断ノートの列が「あり」の行から読む。** 製品を選ぶ前に決まることが整理されています |
| すでに特定の製品を導入済みで、FSx for ONTAP と組み合わせたい | その製品の行の出典を読む。**無ければ [掲載基準を満たさないもの](#掲載基準を満たさないもの) を確認する** |
| AWS ネイティブの機能で足りるか判断したい | 各節の「AWS ネイティブの手立て」を先に読む。**製品を足さない選択が最も運用が軽くなります** |
| 製品を並べて比較したい | **この索引は比較表ではありません。** 同じ課題の選択肢は形態も責任範囲も違うので、対称なトレードオフは各判断ノート側にあります |

**どの行にも共通する前提**があります。

| 前提 | 内容 |
|---|---|
| **出典の日付** | 対応状況は変わります。各行の検索日を見て、選定時点で最新を確認してください |
| **版の組み合わせ** | 「対応」の記載は特定の版の組み合わせを意味します。ベンダーの相互運用性情報で確認が必要です |
| **サポート境界** | AWS のサポート範囲と ベンダーのサポート範囲は別です。**組み合わせた構成の切り分け責任がどちらにあるかを契約時に確定させてください** |

---

## このリポジトリが扱わない範囲

| 扱わないもの | 理由 |
|---|---|
| 製品の導入手順 | 一次情報側にあり、版で変わります。**同じ手順を 2 か所に置くと片方だけが更新されます** |
| ベンダー固有の管理ツール経由の手順 | このリポジトリはネイティブな機構（ONTAP REST API、SnapMirror、FabricPool、Amazon CloudWatch）で書きます。**読み替えられない部分は扱わず、一次情報へ送ります** |
| 製品の価格・ライセンス条件 | 契約により変わります |
| どの製品が優れているか | 用途と前提で決まります。**この索引は選択肢の所在と、選ぶ前に決まることを示すものです** |
| VMware / EDR / バックアップ製品側の内部構成 | 対象の外です |

---

## 関連ドキュメント

- [Reference](README.md) — 横断リファレンスのハブ
- [業種別リソースマップ](industry-resource-map.md) — 業種から入ったときの読む順序と公開事例の索引
- [プロジェクト間の引用索引](cross-repo-index.md) — 実装を置く場所の分担
- [ウイルス対策の選択はベンダーより前に決まる](../domains/security-governance/notes/vscan-scope-is-bounded-before-the-vendor.md) — 判断ノートがある課題の例
- [移行方式の選択](decision-trees/migration-method.md) — 製品より先に決まる方式
- [知見の分類ポリシー](../evidence-policy.md) — 掲載基準と `evidence` 区分の関係

---

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)
