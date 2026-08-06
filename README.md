# Amazon FSx for NetApp ONTAP — Adoption Playbook

![docs](https://img.shields.io/badge/docs-lint%20passing-brightgreen) ![i18n](https://img.shields.io/badge/i18n-8%20languages-blue) ![license](https://img.shields.io/badge/license-MIT-blue) ![region](https://img.shields.io/badge/verified-ap--northeast--1-blue)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](docs/en/README.md) | [한국어](docs/ko/README.md) | [简体中文](docs/zh-CN/README.md) | [繁體中文](docs/zh-TW/README.md) | [Français](docs/fr/README.md) | [Deutsch](docs/de/README.md) | [Español](docs/es/README.md)
<!-- lang-switcher:end -->

---

> **Amazon FSx for NetApp ONTAP** への移行と、その後の設計・構築・運用を進めるための知見集です。
> ライフサイクル（評価 → 設計 → 移行 → 構築 → 運用 → 最適化）と、テーマ（データ保護・データ活用・セキュリティ・性能・コスト・マルチプロトコル ID）の **2 軸**で引けます。
>
> 技術支援の現場で得た知見を、匿名化した参考情報として整理しています。人間の読者と、AI エージェント / Web クローラーの双方から参照できる構造を意図しています。

---

## はじめる

| やりたいこと | ガイド | 所要時間 |
|---|---|---|
| このリポジトリの歩き方を知る | [ナビゲーションガイド](docs/ja/navigation.md) | 3 分 |
| 移行できるか / どう移行するか判断する | [移行方式 決定ツリー](docs/ja/reference/decision-trees/migration-method.md) | 10 分 |
| 検証済みの上限値を確認する | [上限値・クォータ](docs/ja/reference/limits/) | 5 分 |
| 選択肢のトレードオフを比べる | [比較マトリクス](docs/ja/reference/comparison/) | 10 分 |
| 知見の信頼度の見かたを知る | [知見の分類ポリシー](docs/ja/evidence-policy.md) | 5 分 |
| 公開情報から一次情報を探す | [公開されている一次情報と事例の入口](docs/ja/case-studies/public-references.md) | 5 分 |
| 自分の業種・ワークロードの事例を探す | [公開されている FSx for ONTAP の事例](docs/ja/case-studies/public-case-studies.md) | 10 分 |
| 判断を誤った事例から学ぶ | [事例集](docs/ja/case-studies/) | 10 分 |
| 知見を追加する（執筆） | [CONTRIBUTING.md](CONTRIBUTING.md) | 10 分 |

> **収録状況**: **12 モジュールすべてに中身があります。**
> 各モジュールの README に、そのモジュールが答える問いと、対応するノートが一覧されています。
> **答えが未収録の問いは `_未追加_` と表示されます。**

### いま読める知見

各ノートは「1 ファイル = 1 論点」で、**一次情報の出典**と**自分の環境で確かめる手順**を必ず含みます。

| 知見 | 答えていること |
|---|---|
| [容量が余っていても書けなくなる](docs/ja/playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) | 棚卸しでファイル数を数える理由。inode の既定値は 648 GiB を超えると増えません |
| [デプロイタイプは一度しか決められない](docs/ja/playbooks/02-design/notes/deployment-type-is-decided-once.md) | 可用性の選択がスケールアウトの上限も決めます。Multi-AZ は HA ペア 1 組で固定です |
| [ACL 保持は権限の問題であってツールの問題ではない](docs/ja/playbooks/03-migrate/notes/preserving-acls-during-migration.md) | 既定値のまま実行すると ACL が黙って落ち、それでも「成功」で終わります |
| [切り戻せる時点はクライアントが書き始めた瞬間に閉じる](docs/ja/playbooks/03-migrate/notes/where-the-rollback-window-closes.md) | 「切り替えを戻す」操作は存在しません。差分同期は共通 Snapshot に依存します |
| [IaC の境界は API の表面で決まる](docs/ja/playbooks/04-build/notes/what-iac-cannot-reach.md) | テンプレートが成功しても構成は完成しません。ONTAP レベルの設定は届きません |
| [本番投入前レビュー](docs/ja/playbooks/04-build/checklists/pre-production-review.md) | 不可逆な設定と、本番前に実際に試しておく項目のチェックリスト |
| [監視は平均値で失敗する](docs/ja/playbooks/05-operate/notes/monitoring-fails-on-averages.md) | 閾値より先に統計値を決める理由。待機系ノードが平均を引き下げます |
| [メンテナンスは 14 日を超えて延期できない](docs/ja/playbooks/05-operate/notes/maintenance-cannot-be-deferred.md) | SSD 90% 超と route 不足が、パッチ適用を悪化させます |
| [階層化の既定値は作成方法で違う](docs/ja/playbooks/06-optimize/notes/tiering-defaults-differ-by-creation-method.md) | コンソールと IaC で既定のポリシーが違います。変更は戻せる順に試します |
| [Snapshot があることと復旧できることは別](docs/ja/domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md) | 仕組みごとに守れる障害が違います。Snapshot はボリュームと一緒に失われます |
| [SnapLock は有効化とロックが別](docs/ja/domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md) | 不可逆な選択が 3 段あります。特権削除は満了後には使えません |
| [FSx for ONTAP S3 AP は「S3 として使える」わけではない](docs/ja/domains/data-utilization/notes/s3-access-point-constraints.md) | 同一アカウント・同一リージョンなどの前提条件が設計段階の制約になります |
| [S3 Access Point は全リクエストを 1 つの ID で認可する](docs/ja/domains/data-utilization/notes/reaching-data-without-copies.md) | 元の ACL は AI / RAG のパイプラインに引き継がれません |
| [保存時の暗号化は自動、転送時は既定で無効](docs/ja/domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md) | 監査ログには記録されない読み取りがあります。1 オブジェクトにつき最初の 1 回だけです |
| [スループットは 1 つの設定値では決まらない](docs/ja/domains/performance/notes/where-throughput-is-determined-and-shared.md) | 世代・構成・リージョンで上限が変わり、FlexVol は 1 HA ペアを超えられません |
| [p99 は CloudWatch のメトリクスからは出せない](docs/ja/domains/performance/notes/what-you-cannot-read-from-cloudwatch.md) | レイテンシは平均しか得られません。ベンチマークはクレジット残高に左右されます |
| [課金は「確保した量」と「使った量」に分かれる](docs/ja/domains/cost/notes/provisioned-versus-consumed.md) | 階層化には読み書きのリクエスト課金が伴います。重複排除は請求を下げません |
| [ボリュームのセキュリティスタイルが権限評価のモデルを決める](docs/ja/domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) | ID マッピングを止めても NTFS スタイルの SMB アクセスは止まりません |
| [AD への依存は参加時ではなく生涯続く](docs/ja/domains/multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) | 資格情報の失効は平常時に無症状で、次のメンテナンスで顕在化します |

---

<details>
<summary><strong>🗺️ 2 軸ナビゲーション（クリックで展開）</strong></summary>

### ライフサイクル軸 — `playbooks/`

「いま自分はどのフェーズにいるか」から引く入口です。

| # | モジュール | 扱う問い |
|---|---|---|
| 01 | [`01-assess/`](docs/ja/playbooks/01-assess/) | 現行 NAS に何があり、何が移行の制約になるか |
| 02 | [`02-design/`](docs/ja/playbooks/02-design/) | どの構成・容量・スループット・保護方式を選ぶか |
| 03 | [`03-migrate/`](docs/ja/playbooks/03-migrate/) | どの方式で、どう切り替え、どう戻すか |
| 04 | [`04-build/`](docs/ja/playbooks/04-build/) | IaC・自動化・再現可能な構築をどう組むか |
| 05 | [`05-operate/`](docs/ja/playbooks/05-operate/) | 監視・容量・障害対応・変更管理をどう回すか |
| 06 | [`06-optimize/`](docs/ja/playbooks/06-optimize/) | 性能とコストをどこまで詰めるか |

### テーマ軸 — `domains/`

「この論点を調べたい」から引く入口です。ライフサイクル横断で参照されます。

| モジュール | 扱う問い |
|---|---|
| [`data-protection/`](docs/ja/domains/data-protection/) | Snapshot / SnapMirror / SnapLock / バックアップ・ランサム対策 |
| [`data-utilization/`](docs/ja/domains/data-utilization/) | 分析・AI/RAG・S3 API 経由のデータ活用 |
| [`security-governance/`](docs/ja/domains/security-governance/) | 暗号化・監査・権限設計・規制対応の考え方 |
| [`performance/`](docs/ja/domains/performance/) | スループット設計・レイテンシ・キャッシュ・共有帯域 |
| [`cost/`](docs/ja/domains/cost/) | 容量・ティアリング・見積もりと実測の差分 |
| [`multiprotocol-identity/`](docs/ja/domains/multiprotocol-identity/) | NFS / SMB 共存・Active Directory 連携・ID マッピング |

### 横断リファレンス — `reference/`

| ディレクトリ | 概要 |
|---|---|
| [`decision-trees/`](docs/ja/reference/decision-trees/) | 選択フローチャート（移行方式・保護方式・プロトコル） |
| [`comparison/`](docs/ja/reference/comparison/) | 選択肢の比較マトリクス（トレードオフを対称に記載） |
| [`limits/`](docs/ja/reference/limits/) | 上限値・クォータと、その出典・検証日 |
| [`glossary/`](docs/ja/reference/glossary/) | ONTAP / AWS 用語の対訳と定義 |

</details>

<details>
<summary><strong>📁 モジュールの共通構造（拡張のしかた）</strong></summary>

`playbooks/` と `domains/` の各モジュールは **同一の内部構造**を持ちます。新しいモジュールを足すときは `_template/` をコピーしてください。

```text
docs/<lang>/{playbooks,domains}/<module>/
├── README.md          # モジュールのハブ
├── notes/             # 知見の最小単位。1 ファイル = 1 論点
│   └── <slug>.md      # YAML frontmatter 必須
└── checklists/        # 現場で使うチェックリスト
    └── <slug>.md
```

`notes/` の各ファイルは YAML frontmatter でメタデータを持ちます。これは AI エージェントと Web クローラーが構造として解釈できるようにするためです。

```yaml
---
title: SnapMirror の初期同期でスループットが出ない場合の切り分け
lifecycle: [migrate]          # playbooks 軸のタグ
domains: [performance]        # domains 軸のタグ
evidence: verified            # verified | documented | field-observation | hypothesis
verified_on: 2026-08-06       # evidence: verified のとき必須
ontap_version: 9.17.1P7D1     # 検証時のバージョン（該当する場合）
region: ap-northeast-1        # 検証リージョン（該当する場合）
lang: ja
---
```

`evidence` の 4 段階は、読者が「どこまで信頼して使えるか」を判断するための区分です。詳細は [知見の分類ポリシー](docs/ja/evidence-policy.md) を参照してください。

</details>

<details>
<summary><strong>📚 事例の扱い（匿名化ポリシー）</strong></summary>

`case-studies/` には技術支援の現場で得た知見を載せますが、**公開できない情報は一切含めません**。

| 載せないもの | 代わりに書くもの |
|---|---|
| 企業名・組織名・部門名 | 業種と規模帯（例: 製造業 / 数百 TB 規模） |
| 具体的なホスト名・IP・アカウント ID | プレースホルダー（`10.0.x.x`、`123456789012`） |
| 実際の構成図そのまま | 論点が伝わる範囲に抽象化した構成 |
| 担当者名・レビュアー名 | 役割ベースの表記（例: ストレージ運用担当の観点） |
| サポートケース番号・内部チケット ID | 「ベンダーに確認済み（追跡中）」 |

事例は「何が問題で、どう判断し、結果どうなったか」を **一般化された教訓**として書きます。テンプレートは [`case-studies/_template/`](docs/ja/case-studies/_template/) にあります。公開前チェックは `make audit` で自動化されています。

</details>

<details>
<summary><strong>🌐 多言語ポリシー（8 言語）</strong></summary>

翻訳コストと鮮度を両立させるため、**3 ティア**に分けています。

| ティア | 対象 | 言語 |
|---|---|---|
| Tier 1 | ルート `README`、`docs/<lang>/` の主要ガイド | 8 言語すべて |
| Tier 2 | 各モジュールの `README` | 日本語 + English |
| Tier 3 | `notes/`、`checklists/` の個別ファイル | 日本語（English は任意） |

対応言語: 日本語 / English / 한국어 / 简体中文 / 繁體中文 / Français / Deutsch / Español

Tier 1 は **セクション構成と数が言語間で一致**していることを CI で検査します（`make i18n-check`）。翻訳しないもの: ファイルパス、コマンド、バッジ URL、アンカー ID、製品名・技術用語（ONTAP、SnapMirror、FlexCache、SnapLock、S3 Access Point など）。

</details>

<details>
<summary><strong>🤖 AI エージェント / クローラー向け</strong></summary>

このリポジトリは人間の読者と機械の読者の双方を想定しています。

| ファイル | 用途 |
|---|---|
| [`llms.txt`](llms.txt) | LLM 向けのリポジトリ全体マップ（[llmstxt.org](https://llmstxt.org/) 準拠） |
| [`AGENTS.md`](AGENTS.md) | コーディングエージェント向けの規約・禁止事項・検証手順 |
| `notes/*.md` の frontmatter | 機械可読なメタデータ（ライフサイクル / テーマ / 証跡レベル / 検証日） |
| [`reference/limits/`](docs/ja/reference/limits/) | 上限値を出典・検証日付きで構造化 |

**知見を引用する側への注意**: `evidence: hypothesis` や `field-observation` のノートは検証済みの事実ではありません。frontmatter の `evidence` を必ず確認してください。

</details>

<details>
<summary><strong>🔧 コントリビュート・ローカル検証</strong></summary>

```bash
make help          # 利用可能なターゲット一覧
make lint          # Markdown lint + frontmatter スキーマ検証
make i18n-check    # Tier 1 ドキュメントの言語間パリティ検査
make audit         # 公開前チェック（命名 / 中立性 / 個人情報 / 内部 ID）
make links         # リンク切れ検査
make all           # 上記すべて
```

Issue / Pull Request を歓迎します。執筆規約は [CONTRIBUTING.md](CONTRIBUTING.md)、
知見の分類基準は [知見の分類ポリシー](docs/ja/evidence-policy.md) を参照してください。

</details>

---

## 関連リポジトリ

| リポジトリ | 概要 |
|---|---|
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | S3 Access Points サーバーレス処理パターン集（45+） |
| [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) | 可観測性統合（メトリクス、アラート、自動対応） |
| [fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations) | Lakehouse 統合（Databricks / Snowflake / Athena / Glue / EMR） |
| [vmware-migration-ec2-ontap](https://github.com/Yoshiki0705/vmware-migration-ec2-ontap) | VMware → EC2 + FSx for ONTAP 移行 |

---

## 免責

本リポジトリは個人が整理した技術情報であり、所属組織の公式見解ではありません。
ガバナンスや規制対応に関する記述は**一般的な設計上の考慮事項**であり、法務・コンプライアンス上の判断ではありません。ベンチマーク値は記載された検証環境での実測であり、一般的なサービス上限や本番環境での再現を保証するものではありません。

本リポジトリの日本語版が技術的な正典です。他言語版は機械支援による翻訳で、公開前のネイティブレビューを経ていません。内容が食い違う場合は日本語版が優先します。誤りを見つけた場合は [Issue](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues) でお知らせください。

## ライセンス

MIT — [LICENSE](LICENSE)

---

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](docs/en/README.md) | [한국어](docs/ko/README.md) | [简体中文](docs/zh-CN/README.md) | [繁體中文](docs/zh-TW/README.md) | [Français](docs/fr/README.md) | [Deutsch](docs/de/README.md) | [Español](docs/es/README.md)
<!-- lang-switcher:end -->
