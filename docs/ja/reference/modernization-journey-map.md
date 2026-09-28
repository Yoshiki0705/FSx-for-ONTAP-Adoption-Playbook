---
title: モダナイゼーション旅程マップ — 移行を入口に、各段階でどのモジュール・決定木・実装パターンを読むかの導線
lifecycle: [assess, design, migrate, operate]
domains: [block-storage, data-protection, data-utilization, security-governance, observability, cost]
evidence: documented
source: https://aws.amazon.com/fsx/netapp-ontap/
lang: ja
---
# モダナイゼーション旅程マップ

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

---

## 結論

**このマップは「移行の先」を時間軸で並べたものです。入り方は 2 本あります。**

- **順番に進みたいなら** → [旅程の段階表](#旅程の段階表)。移行を入口に、コンテナ化・データ活用・DR・運用最適化へと進む順序です
- **局面から入りたいなら** → [局面別索引](#局面別索引)。段階ごとに spoke・決定木・設計ノートを並べています

**このマップは選択には答えません。答えるのは順序です。** どの経路を選ぶか、どのプロトコルで出すか、どのデータストアを使うかといった分岐は、既存の[決定木](decision-trees/)にあります。ここは「いま自分は旅程のどこにいて、次にどこを読むか」だけを扱い、選択そのものは決定木へリンクで渡します。

**業種から入りたい場合は別のマップです。** 同じ spoke 群を業種で並べたものが[業種別リソースマップ](industry-resource-map.md)、課題別の ISV / SaaS 選択肢が[ISV / SaaS 選択肢マップ](isv-solution-map.md)です。このマップはそれらを「モダナイゼーションの段階」で並べ替えた導線です。

**弧の中心は 1 つです。** VMware から EC2 + Amazon FSx for NetApp ONTAP への移行を入口に、コンテナ化・サーバーレス化・分析 / AI・DR / レジリエンス・運用最適化へと進むあいだ、FSx for ONTAP をデータ基盤の中核に据え続ける、という前提でつないでいます。姉妹のブログシリーズと連動し、第 1 回・第 2 回は公開済みです。第 3 回・第 4 回は未公開です（[ブログ関連記事](#ブログ関連記事)）。

> **区分**: `documented` — 各 spoke リポジトリへのリンクの所在と、Hub 内モジュールの所在を記載しています。段階ごとの「判断が集中する所」は、リンク先のノートで扱う論点の要約であって、このマップで新たに検証した結果ではありません。
---

## 旅程の段階表

**段階は 0 から 5 の 6 つです。** 移行を入口（段階 1）に置き、その前に評価（段階 0）、その先にモダナイゼーションの各局面を並べています。

**先に 1 つ断っておきます。段階は「順番に全部通る」ことを強制しません。** コンテナ化を経ずにサーバーレスへ進む経路もあれば、移行と同時に DR を設計する経路もあります。この表は代表的な弧を 1 本描いたものです。自分の経路に無い段階は飛ばし、必要な段階だけ読んでください。

| 段階 | 何をするか | 主に読む（Hub 内） | 実装パターン（spoke） | この段階で判断が集中する所 |
|---|---|---|---|---|
| 0. 評価 | 移行対象と形の棚卸し | [評価](../playbooks/01-assess/) | — | ファイル数の棚卸し。容量が余っていても書けなくなります |
| 1. 移行（入口） | VMware → EC2 + FSx for ONTAP | [移行](../playbooks/03-migrate/) / [移行方式の決定木](decision-trees/migration-method.md) | [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) | 切り戻せる時点がいつ閉じるか。ブートは常に Amazon EBS |
| 2. コンテナ化 | ECS / EKS へ replatform、データ層を継続 | [データストア選択の決定木](decision-trees/container-datastore-selection.md) / [ブロックストレージ](../domains/block-storage/) | [Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) | 実行環境（EC2 / Fargate）で到達形態が決まること。Trident PV のボリューム数上限 |
| 3. サーバーレス / 分析 / AI | S3 Access Points 経由でデータを活用 | [クライアント到達経路の決定木](decision-trees/client-access-route.md) / [データ活用](../domains/data-utilization/) | [Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) / [Lakehouse-Integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) / [S3-Burst](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) / [Agentic-RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | S3 Access Points は「S3 として使える」わけではないこと。元の ACL は引き継がれません |
| 4. DR / レジリエンス | 複製・Snapshot・ランサムウェア対策 | [データ保護](../domains/data-protection/) / [セキュリティ・ガバナンス](../domains/security-governance/) | [Cyber-Resilience-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns) | 有効化とロックが別だという点。不可逆な選択が 3 段あります |
| 5. 運用 / 可観測性 / 最適化 | 監視・容量・階層化・コスト | [運用](../playbooks/05-operate/) / [最適化](../playbooks/06-optimize/) / [請求が想定より高いときの決定木](decision-trees/cost-higher-than-expected.md) | [Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) | 監視が平均値で失敗すること。確保した量と使った量で課金が分かれます |

**どの段階でも先に通すもの**があります。段階の行より優先してください。

| 通すもの | なぜ全段階か |
|---|---|
| [本番投入前レビュー](../playbooks/04-build/checklists/pre-production-review.md) | **後から変えられない項目**は段階を問いません。SnapLock、Snapshot locking、セキュリティスタイル、`NetworkOrigin` |
| [知見の分類ポリシー](../evidence-policy.md) | 事例やベンチマークの数値をそのまま設計根拠にしないための区分 |
| [上限値・クォータ](limits/) | 上限に当たるかどうかは構成で決まり、段階では決まりません |

---

## 局面別索引

段階ごとに、実装パターン（spoke）・Hub 内の決定木・設計ノートを並べます。ノート個別リンクは[業種別リソースマップ](industry-resource-map.md)で実在確認済みのものを流用しています。

### 0. 評価

| 種類 | リソース | 論点 |
|------|----------|------|
| 決定木 | [ファイルストレージの選択](decision-trees/file-storage-selection.md) | 何をどのプロトコルで出すか、入口で決める |
| ノート | [容量が余っていても書けなくなる](../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) | ファイル数の棚卸し。バイト数を数えることはファイル数を数えることではありません |

### 1. 移行（入口）

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) | VMware → EC2 + FSx for ONTAP の 2 経路を実機検証 |
| 決定木 | [移行方式の選択](decision-trees/migration-method.md) | どの移行方式を選ぶか |
| ノート | [切り戻せる時点はクライアントが書き始めた瞬間に閉じる](../playbooks/03-migrate/notes/where-the-rollback-window-closes.md) | 移行の切り替え判断 |
| ノート | [ACL 保持は権限の問題であってツールの問題ではない](../playbooks/03-migrate/notes/preserving-acls-during-migration.md) | 移行時の権限保持 |

### 2. コンテナ化

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) | ECS / EKS のデータストア |
| 決定木 | [コンテナデータストアの選択](decision-trees/container-datastore-selection.md) | 実行環境で到達形態が決まる |
| ノート | [Kubernetes のブロック PV はボリューム数の上限に当たる](../domains/block-storage/notes/kubernetes-block-volumes-and-the-volume-limit.md) | `ontap-san` と `ontap-san-economy` の分岐点。詰まるのは容量ではありません |

### 3. サーバーレス / 分析 / AI

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | S3 Access Points 経由の業種別 UC |
| パターン | [Lakehouse-Integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) | Athena / Glue / Spark 連携 |
| パターン | [S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) | S3 で収集 → FlexCache の NFS / SMB で利用 |
| パターン | [Agentic-Access-Aware-RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | アクセス制御対応 Agentic RAG |
| 決定木 | [クライアント到達経路の選択](decision-trees/client-access-route.md) | どの経路でデータへ到達するか |
| ノート | [S3 Access Points は「S3 として使える」わけではない](../domains/data-utilization/notes/s3-access-point-constraints.md) | 同一アカウント・リージョン等の制約 |
| ノート | [S3 Access Points は全リクエストを 1 つの ID で認可する](../domains/data-utilization/notes/reaching-data-without-copies.md) | 元の ACL は AI パイプラインに引き継がれません |

### 4. DR / レジリエンス

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [Cyber-Resilience-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns) | ARP + File Security + FPolicy の多層防御 |
| ノート | [SnapLock は有効化とロックが別](../domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md) | 不可逆な選択が 3 段あります |
| ノート | [Snapshot があることと復旧できることは別](../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md) | データ保護設計 |

### 5. 運用 / 可観測性 / 最適化

| 種類 | リソース | 論点 |
|------|----------|------|
| パターン | [Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) | 監査ログを Datadog / Splunk 等へ転送 |
| 決定木 | [請求が想定より高いとき](decision-trees/cost-higher-than-expected.md) | 確保した量か使った量か。どちらかで打ち手が変わります |
| ノート | [監視は平均値で失敗する](../playbooks/05-operate/notes/monitoring-fails-on-averages.md) | 待機系ノードが平均を引き下げる問題 |
| ノート | [課金は「確保した量」と「使った量」に分かれる](../domains/cost/notes/provisioned-versus-consumed.md) | TCO の構造 |

---

## ブログ関連記事

各段階に対応するブログ回の対応です。**第 1 回・第 2 回は公開済みで、下の表にリンクを張っています。第 3 回・第 4 回は未公開です。** 第 3 回・第 4 回は公開後にこの表へリンクを足します。日本語記事を主に、英語記事を併記します。

| 段階 | ブログ回 |
|---|---|
| 1. 移行 | [第 1 回（入口の設計）](https://hakobiya.hatenablog.com/entry/fsxn-vmware-migration-options-ec2)（[English](https://dev.to/aws-builders/designing-aws-modernization-with-vmware-migration-as-the-entry-point-why-fsx-for-ontap-as-the-3k24)）/ [第 2 回（AWS Transform の実機）](https://hakobiya.hatenablog.com/entry/fsxn-aws-transform-mgn-migration-target)（[English](https://dev.to/aws-builders/aws-transform-now-supports-block-storage-migration-to-fsx-for-ontap-benefits-and-pitfalls-from-a-1hhe)） |
| 2-4. モダナイゼーション | 第 3 回（コンテナ化・S3 Access Points・DR）— 未公開 |
| 1. 移行（既存資産） | 第 4 回（Shift Toolkit）— 未公開 |

---

## 読み方のガイド

1. **いまいる段階を見つける** — 段階表から。**段階は順番に全部通る前提ではありません。** 自分の経路に無い段階は飛ばしてください
2. **主に読むのは Hub 内のモジュール** — playbooks（ライフサイクル軸）と domains（テーマ軸）。選択の分岐は決定木へ渡します
3. **実装パターンは spoke リポジトリ** — SAM / CDK / CFn を含む、動くテンプレートです
4. **「判断が集中する所」はリンク先のノートで扱う論点** — このマップの要約であり、設計根拠にするならリンク先とノートの区分を確認してください
5. **段階の行より先に、全段階共通の 3 つを通す** — [段階表](#旅程の段階表)の末尾にあります。**後から変えられない項目は段階を問いません**

---

## sibling リポジトリ一覧

| リポジトリ | 内容 | 形式 |
|---|---|---|
| [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) | VMware 移行の入口。2 経路を実機検証 | CFn |
| [FSx-for-ONTAP-Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) | ECS / EKS のデータストア | 実装パターン |
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | 業種別 UC + OPS + GenAI + ファイルポータル UI | SAM + Amplify Gen2 |
| [FSx-for-ONTAP-Lakehouse-Integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) | Athena / Glue / Spark 連携 | S3 Access Points |
| [S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) | S3 で収集 → FlexCache の NFS / SMB で利用 | CFn + SAM |
| [FSx-for-ONTAP-Agentic-Access-Aware-RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | アクセス制御対応 Agentic RAG | CDK |
| [FSx-for-ONTAP-Cyber-Resilience-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns) | ARP + File Security + FPolicy 多層防御 | 実装パターン |
| [FSx-for-ONTAP-Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) | 監査ログ → Datadog / Splunk 等 | Lambda + S3 Access Points |

---
[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)
<!-- lang-switcher:start -->
🌐 [日本語](modernization-journey-map.md) | [English](../../en/reference/modernization-journey-map.md) | [🏠 リポジトリトップ](../../../README.md)
<!-- lang-switcher:end -->
