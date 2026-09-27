# AWS DevOps Agent を FSx for ONTAP 運用に使う

> 本番運用のインシデントを調査・予防するエージェント。FSx for ONTAP は **CloudWatch 経由の監視対象**として重ねる（ONTAP 管理面は MCP を自作して届かせる）。

[🏠 リポジトリトップ](../../../../README.md)

---

AWS DevOps Agent を Amazon FSx for NetApp ONTAP の運用に重ねられるかを扱います。**エージェントの仕様は公式ドキュメントで確認済みですが、FSx for ONTAP 運用への適合判断は著者環境での実測ではありません。** どの段落がどちらかは、各節で明示します。

---

## このページの但し書き

| 内容 | 確度 |
|---|---|
| DevOps Agent の用途・信号源・Skills の仕様 | AWS 公式ドキュメントに出典（本ページ末尾）。`documented` 相当 |
| FSx for ONTAP 運用への適合、どの指標を見るべきか | **未検証。** 著者が DevOps Agent を FSx for ONTAP 環境で動かして得た結果ではありません |

しきい値（「使用率 80% で警告」など）は**書きません**。環境依存で、著者の実測もないためです。代わりに「どの指標を見るか」の観点だけを残します。

---

## DevOps Agent とは（documented）

AWS DevOps Agent は、**本番運用のインシデントを解決・予防し、信頼性と性能を継続的に改善する**フロンティアエージェントです。AWS・マルチクラウド・オンプレミスの環境を対象とします。用途は次の 4 つです。

| 用途 | 何をするか |
|---|---|
| インシデント対応 | アラームやサポートチケットを起点に自動で調査を開始する。メトリクス・ログ・デプロイ履歴を相関させ、根本原因と緩和策を Slack / Jira などへ返す |
| 予防的なインシデント防止 | 過去のインシデント調査からパターンを分析し、可観測性・インフラ・パイプライン・アプリ回復性の改善点を出す |
| オンデマンドの SRE タスク | 自然言語でアーキテクチャの照会・健全性の分析・調査知見の参照を行う。定期実行するカスタムエージェントも作れる |
| リリース管理（プレビュー） | PR やチャットからリリース前レビューを実行する。依存関係・アクセス制御・組織標準への準拠を確認する |

動作の骨格（インシデント対応）は次のとおりです。

1. CloudWatch アラームやサポートチケットの発火を起点に自動起動する
2. メトリクス・ログ・ネットワークフロー・デプロイ履歴を突き合わせる
3. 根本原因の分析と、実行可能な緩和策を出す

見る信号源は、Amazon CloudWatch のほか Datadog / Dynatrace / New Relic / Splunk などの可観測性データと、GitHub / GitLab のデプロイ履歴です。デプロイとインシデントの相関を取れるのはこのためです。

---

## フェーズごとの使いどころ（適合判断・未検証）

**この節は著者の判断で、実測ではありません。** DevOps Agent の用途（運用）と FSx for ONTAP の管理面の構造から導いたものです。

| フェーズ | FSx for ONTAP 運用で何ができるか | 根拠（未検証） |
|---|---|---|
| 運用（05-operate / 06-optimize） | インシデント調査・原因分析・予防に重ねられる | インシデント検知・原因分析・予防が用途そのもの。FSx for ONTAP は CloudWatch にメトリクスを出すので、そのアラームを起点にできる |
| 構築（04-build） | デプロイとインシデントの相関に使える | GitHub / GitLab のデプロイ追跡と連携し、デプロイとインシデントの相関を取れる。ただし IaC を書く・デプロイするのが主目的のエージェントではない |
| 設計（01-assess / 02-design） | 既存構成の読み取り評価に限られる | 設計そのものを生成する用途ではない。既存構成の評価は後述の Well-Architected レビュー型 Skill で可能 |

### 2 つの管理面で分かれる届く範囲

FSx for ONTAP には AWS 管理面（CloudWatch メトリクス、Amazon FSx の API）と ONTAP 管理面（ONTAP REST API）という 2 つの真実の源があります。これは [ONTAP 側の設定に届く経路の比較](../../reference/comparison/ontap-configuration-routes.md) や [この設定はどこから作るか](../../reference/decision-trees/where-a-setting-is-created.md) で扱っている通りです。

DevOps Agent が既定で見るのは **AWS 管理面（CloudWatch）側**です。ONTAP 管理面の指標（アグリゲート使用率、SnapMirror の遅延、qtree quota、CIFS セッションなど）を取りに行くには、**ONTAP REST API を叩くカスタム MCP サーバと、それを呼ぶ Skill を自作する**必要があります。DevOps Agent が ONTAP REST を直接叩く組み込み機能を持つかは、公式ドキュメントでは確認できていません。

---

## スキルとメモリの分担（documented）

**DevOps Agent に外から知識を与える口は 2 系統あります。** スキルは「どう調べるか（手続き的知識）」、メモリは「判断に使う知識（情報的知識）」で、公式ドキュメントでも役割が分けられています。FSx for ONTAP の運用知識をどちらに載せるかで、書き方と更新の仕方が変わります。

| 系統 | 与える知識 | FSx for ONTAP での例 |
|---|---|---|
| スキル | 調査手順・判断分岐・出力形式（手続き的知識） | 「容量逼迫の調査手順」「SnapMirror 遅延の切り分け」を決定木で書く |
| メモリ | 構成・依存・過去の原因（情報的知識） | 「このボリュームは SnapMirror の宛先」「このアラームは夜間バッチで無視」を判断材料として持たせる |

スキルは 3 種類あります。

| スキルの種類 | 作成者 | 編集 | 位置づけ |
|---|---|---|---|
| AWS 提供スキル | AWS | 不可（内部・非公開） | 標準的な調査の土台。カスタムスキルが 1 つも無くても常に効く |
| カスタムスキル | ユーザー | 可 | 組織固有の手順を教える。この後の節で扱う |
| 学習済みスキル | DevOps Agent | 自動更新（メモリへ移行中） | 環境を自動で学ぶ。Agent Space Understanding / Code Dependencies / Pipeline Topology / ツールの使い方の蓄積（Tool Use）の 4 種 |

**FSx for ONTAP 向けに人が書くのはカスタムスキルです。** 学習済みスキルは自動で育つもので、AWS 提供スキルは触れません。以下、カスタムスキルの仕様を扱います。

---

## Skills の仕様（documented）

DevOps Agent の Skills は、エージェントに調査手順とドメイン知識を持たせるモジュールです。以下は公式ドキュメントに基づきます。

| 制約 | 内容 |
|---|---|
| コンテンツ | **非実行のみ**（Markdown / PDF / 画像 / データ）。`scripts/` を含む zip はアップロード時に拒否される（Sandbox プレビュー有効時を除く） |
| 必須ファイル | `SKILL.md`。frontmatter に `name` と `description` が必要 |
| `description` の書き方 | エージェント視点で、どの症状・サービス・エラー型で起動するかを列挙する。曖昧だとエージェントが Skill を読み飛ばす |
| サイズ | zip は 6 MB 以内、100 ファイル以内 |
| ターゲティング | agent type（Generic / On-demand / Incident Triage / Incident RCA / Incident Mitigation / Evaluation / Release testing）で読み込む文脈を絞れる |
| 手順の形 | 自由記述ではなく決定木・ステップ手順で書く（アラーム状態確認 → メトリクス分析 → 根本原因 → 所見要約） |
| 取り込み | GitHub リポジトリのディレクトリ URL から import できる。バージョン管理と相性が良い |

**このリポジトリの Skills（Kiro の `.kiro/skills/`）とは別物です。** ここで言う Skills は DevOps Agent 専用で、上の制約が効きます。

---

## FSx for ONTAP 向けに書くと有効そうな Skill 候補（適合判断・未検証）

**以下は候補で、実際に有効かは対象環境での検証が要ります。** 公式の RDS 性能調査 Skill と同じ形（決定木 + 観点 + references）で、FSx for ONTAP の運用知識を Skill 化する想定です。**しきい値は各環境で決めるものとし、ここには書きません。**

| Skill 候補 | 見る観点 | 備考 |
|---|---|---|
| 容量調査 | SSD 使用率、アグリゲート容量、ボリューム auto-grow、階層化（FabricPool / Capacity Pool）の逼迫 | CloudWatch のストレージ系列が起点。ONTAP 側の qtree / volume 使用率は MCP 経由 |
| 性能調査 | スループット / IOPS の頭打ち、スループット利用率、レイテンシ上昇 | SSD IOPS とスループット容量は別の上限。[スループットは 1 つの設定値では決まらない](../../domains/performance/notes/where-throughput-is-determined-and-shared.md)を参照 |
| SnapMirror / バックアップの調査 | レプリケーションの遅延と失敗の切り分け | Incident RCA / Mitigation 向け。**破壊的操作（切替・削除）を Skill の自動手順に含めない**（後述） |
| マルチプロトコル / アクセス調査 | SMB 共有可視性、AD 参加 SVM の AccessDenied、name-mapping、S3 Access Points の到達性 | ドメイン参加 SVM では一部の到達性確認が誤って成功する場合がある。[AD への依存は参加時ではなく生涯続く](../../domains/multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md)を参照 |
| Well-Architected レビュー型 | 既存構成の読み取り評価 | Evaluation 向け。[sample-skills の WA review](https://github.com/aws-samples/sample-skills-for-AWS-Devops-agent) を FSx for ONTAP 文脈に絞る |

---

## Skill を書くときの観点（このリポジトリの規律から）

- **証拠区分を Skill 本文に持ち込む。** しきい値は「検証済み（環境明記）」か「出典あり」か「未検証」かを区別して書く。断定できない数値は「未検証」と明記する
- **AWS 管理面と ONTAP 管理面を混ぜない。** どのステップが CloudWatch / Amazon FSx の API で、どこから ONTAP REST（＝ MCP が必要）かを各ステップで示す
- **命名を守る。** 初出は Amazon FSx for NetApp ONTAP、以降は FSx for ONTAP

> **不可逆操作に関する補足**: SnapLock、Amazon S3 Object Lock、SnapMirror の切替、ボリューム削除といった戻せない操作は、Skill の自動実行手順に**埋め込まないでください**。これらは調査手順に留め、実行は人間の承認を経る前提にします。理由は [SnapLock は有効化とロックが別](../../domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md) にあるとおりで、戻せない操作が正しく効いたとき、それは自分で起こした障害と区別がつきません。

---

## 参考資料（一次情報）

- [DevOps Agent Skills（AWS 公式）](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html) — Skill 構造、frontmatter、agent type、6 MB 制約、RDS 調査の完全例
- [DevOps Agent Memories（AWS 公式）](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-memories.html) — スキル（手続き的知識）とメモリ（情報的知識）の区別
- [Learned skills（AWS 公式）](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-learned-skills.html) — 学習済みスキル 4 種とメモリへの移行
- [aws-samples/sample-skills-for-AWS-Devops-agent](https://github.com/aws-samples/sample-skills-for-AWS-Devops-agent) — EKS resilience / Well-Architected review / マルチアカウントの実例。FSx for ONTAP 向け Skill の雛形に使える
- [Custom agents（AWS 公式）](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html) — system prompt・ツール・Skill・memory を束ねた専用エージェント定義
- [Production operations（AWS 公式）](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-production-operations-index.html) — インシデントライフサイクル全体での位置づけ

---

## 関連

- [AI エージェントのジャンル入口](../README.md)
- [観測性 — 監視経路の選定](../../domains/observability/) — DevOps Agent が見る CloudWatch 経路を含む収集経路の選び方
- [ONTAP 側の設定に届く経路の比較](../../reference/comparison/ontap-configuration-routes.md) — MCP で ONTAP REST を叩く前提の背景

---

[🏠 リポジトリトップ](../../../../README.md)
