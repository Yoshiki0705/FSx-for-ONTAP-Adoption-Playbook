---
title: 本家 18 モジュールと 90 分構成の対応表 — SMB 版で差し込む位置とデータの渡し方
lifecycle: [assess, build]
domains: [data-utilization, multiprotocol-identity]
evidence: documented
source: https://catalog.us-east-1.prod.workshops.aws/workshops/9cd82e0b-8348-456b-932a-818b9e5825a1/en-US
lang: ja
---

# 本家 18 モジュールと 90 分構成の対応表

[🏠 リポジトリトップ](../../../README.md) | [Workshop Studio](README.md)

[FSx for NetApp ONTAP S3 Access Points Workshop](https://catalog.us-east-1.prod.workshops.aws/workshops/9cd82e0b-8348-456b-932a-818b9e5825a1/en-US)
の全 18 モジュールを、90 分のイベントでどう扱うかを 1 枚に対応付けます。
時間の根拠は[実測値](eda-s3-access-points-90min/measured-timings.md)です。

> **タイムテーブル自体は未検証です。** モジュール単位の所要時間は実測しましたが、
> 90 分を通しでリハーサルした結果ではありません。

## Workshop Studio が最初に払い出すもの

構成の前提なので先に確定させます。本家のモジュール 2 に記載された内容です。

| リソース | 構成 |
|---|---|
| VPC | `/16`、Multi-AZ（CIDR は下記） |
| Amazon FSx for NetApp ONTAP | 2 TiB、Multi-AZ、512 MBps |
| SVM | `workshop-svm`、**UNIX セキュリティスタイル** |
| ボリューム | `design_data`（1 TiB）、`logs`（512 GB） |
| EC2 | Linux `t3.medium` 2 台、IAM ロール付き |
| IAM | PowerUserAccess + IAMFullAccess |
| リージョン | us-east-1 または us-west-2 |

VPC の CIDR は `10.0.0.0/16` です。 <!-- allow:pii - published workshop value, not a private environment address -->

**払い出しはイベント開始と同時に自動で始まり、約 20 分かかります。** 本家はこの 20 分を
Architecture Overview を読む時間で吸収する設計です。

**Active Directory、Windows インスタンス、SMB 共有、NTFS ボリュームはいずれも含まれません。**
全 37 ページを検索しても SMB・CIFS・Active Directory への言及は存在せず、
唯一の関連記述が上表の「UNIX セキュリティスタイル」です。SMB 版はここを自作することになります。

## 18 モジュールの対応表

`分` は 90 分の本体に占める時間です。事前・事後は本体に含めません。

| # | モジュール | NFS 版 | SMB 版 | 分 | 判断理由 |
|---|---|---|---|---|---|
| 1 | Architecture Overview | 採用 | 採用 | 10 | 導入。5 と統合し、ゼロコピーの考え方をここで説明 |
| 2 | Getting Started | **事前** | **事前** | 0 | アカウント参加とリージョン確認。受付時間に済ませる |
| 3 | Setup & Deployment | **事前** | **事前** | 0 | Workshop Studio が自動実行（約 20 分）。SMB 版はここに AD を足す |
| 4 | Verify Infrastructure | 採用（短縮） | 採用（短縮） | ↑1 に含む | 環境変数の確認のみ。本家枠 2 分を導入に吸収 |
| 5 | S3 Access Points | 採用 | 採用 | ↑1 に含む | 概念説明。手を動かさない |
| 6 | Generate EDA Data | 採用 | **差し替え** | 8 | 実測 2.50 秒。SMB 版は文書生成に置き換え（実測 1.68 秒） |
| 7 | Create S3 Access Points | 採用 | 採用（ID 変更） | 10〜12 | UNIX ID 実測 14.3 秒 / Windows ID 実測 33.9 秒 |
| 8 | Setup Amazon Quick | 採用 | 採用 | 12 | **枠の終わりで同期を開始**。ここが全体の律速 |
| 9 | Deploy AgentCore Gateway | 不採用 | 不採用 | 0 | 全構築 35〜45 分。実演のみなら 8〜10 分で差し込み可 |
| 10 | AI-Powered Analytics | 採用 | 採用 | 17 | 応答は実測 54 秒以内。同期完了が前提 |
| 11 | QuickSight Dashboards | **Step 1 のみ** | **Step 1 のみ** | 5 | 集計 CSV の生成（実測 1.20 秒）。13 が依存するため外せない |
| 12 | Quick Automations | 不採用 | 不採用 | 0 | スケジュール実行の結果がイベント中に見られない |
| 13 | Athena SQL Queries | 採用 | 採用 | 10〜15 | 5 本で実測 12 秒。**8 の同期待ちを埋める緩衝材** |
| 14 | Glue Data Catalog | 不採用 | 不採用 | 0 | Lake Formation 有効環境で失敗。自アカウント開催で最高リスク |
| 15 | Event-Driven Processing | 不採用 | 不採用 | 0 | ストレージの主題から距離があり本家枠 20 分 |
| 16 | Transfer Family (SFTP) | 不採用 | 不採用 | 0 | 同上。ただし[データ受け渡しの代替案](#方法-4-transfer-family-sftp)としては検討価値あり |
| 17 | Architecture Recap | 採用 | 採用 | 8 | 18 の案内と合わせてまとめ |
| 18 | Cleanup | **事前案内＋事後** | 同左 | ↑17 に含む | 手順は事前に読む。撤収自体はイベント後 |

採用は 8 モジュール（うち 1 つは部分採用）、不採用 6、事前・事後 4 です。

## NFS 版のタイムテーブル

| 経過 | 分 | モジュール | 内容 |
|---|---|---|---|
| 00:00 | 10 | 1 + 4 + 5 | 導入、環境確認、ゼロコピーの概念 |
| 00:10 | 8 | 6 | EDA ログ生成（500 ジョブ / 1,952 ファイル） |
| 00:18 | 10 | 7 | S3 AP 作成（UNIX ID）とゼロコピー確認 |
| 00:28 | 12 | 8 | Quick セットアップ。**枠末で同期開始** |
| 00:40 | 5 | 11 Step 1 | 集計 CSV 生成 |
| 00:45 | 15 | 13 | Athena で SQL 5 本 |
| 01:00 | 5 | — | 予備・質疑 |
| 01:05 | 17 | 10 | Quick に自然言語で質問 |
| 01:22 | 8 | 17 + 18 | まとめと撤収案内 |

同期の猶予は 25 分（00:40 → 01:05）。実測 11.5〜14.1 分に対し倍近い余裕です。

## SMB 版のタイムテーブル

差分は **6 の差し替え**と **7 の ID 変更**、そして **8 の待ち時間に権限モデルの解説を足す**ことだけです。
モジュールの骨格は変わりません。

| 経過 | 分 | モジュール | 内容 | NFS 版との差 |
|---|---|---|---|---|
| 00:00 | 10 | 1 + 4 + 5 | 導入。ファイルサーバーのデータが分析に使えていない話 | 題材の入れ替え |
| 00:10 | 8 | **6 差し替え** | SMB 共有へ文書を投入（部門フォルダー 6 個 / 23 ファイル） | **EDA ログ生成を置換** |
| 00:18 | 12 | 7 | **Windows ID** の S3 AP 作成とゼロコピー確認 | ID が UNIX → WINDOWS、+2 分 |
| 00:30 | 12 | 8 | Quick セットアップ。**枠末で同期開始** | 同じ |
| 00:42 | 8 | **追加** | NTFS ACL と S3 AP の認可モデルの対比 | **SMB 版のみ。同期待ちを埋める** |
| 00:50 | 10 | 13 | Athena で集計 CSV を SQL 参照 | 15 分 → 10 分に短縮 |
| 01:00 | 5 | — | 予備・質疑 | 同じ |
| 01:05 | 17 | 10 | Quick に文書の内容を質問 | 同じ |
| 01:22 | 8 | 17 + 18 | まとめと撤収案内 | 同じ |

同期の猶予は 23 分（00:42 → 01:05）。

**11 Step 1（集計 CSV）を落として 13 も外すなら**、00:50 の 10 分が空きます。
ここに 9 の実演（8〜10 分）を差し込めます。ただし
「同じデータが SQL からも読める」話と、[AI の回答を突き合わせる場面](eda-s3-access-points-90min/measured-timings.md#回答内容の正しさを検証した)は失われます。

## SMB 版で 3 に足すもの

**AD の作成時間は 90 分の外に出せます。** ここが前回の説明で不足していた点です。
Workshop Studio の払い出しはイベント開始時に自動で走り、本家構成でも既に約 20 分かかります。
テンプレートに AD を足せば、その作成時間は**この払い出し時間に吸収されます。**

| 追加リソース | 目安 | 備考 |
|---|---|---|
| AWS Managed Microsoft AD | 15〜30 分 | 払い出し時間が本家の約 20 分から 30〜45 分に伸びます |
| SVM の AD 参加 | 2〜5 分 | `FileSystemAdministratorsGroup` は `Domain Admins`。NetBIOS 名はドメイン短縮名と別にする |
| NTFS ボリュームと SMB 共有 | 5 分 | セキュリティスタイル NTFS |
| Windows EC2（ドメイン参加） | 5〜10 分 | `AWS::SSM::Association` と `AWS-JoinDirectoryServiceDomain` を使う。DNS を AD の IP に向ける UserData が必要 |

**運営上の含意**: 払い出しが 30〜45 分に伸びるので、**Workshop Studio のイベントを開始 45〜60 分前に開けて**
おく必要があります。受付・接続確認の 15 分では足りません。

### 事前に必ず確認すること

SVM に手動構成の ONTAP S3 オブジェクトストレージサーバーがあると、
FSx for ONTAP が管理する S3 アクセスポイントは作成できません。検証では 37 秒後に `FAILED` になり、
`LifecycleTransitionReason` が既存 S3 サーバーの削除を指示しました。
新規に払い出す環境では起きませんが、使い回しの検証環境でリハーサルするときに踏みます。

## Workshop Studio 環境への SMB データの渡し方

4 通りあります。**方法 1 を推奨**します。

### 方法 1: 環境内で生成する（推奨・検証済み）

Windows インスタンス上の PowerShell で文書を生成します。**外部からのデータ転送が発生しません。**

本家が EDA ログでやっているのと同じ考え方です。本家はページ内に Python スクリプトを埋め込み、
参加者がコピー＆ペーストして実行します。SMB 版も PowerShell スクリプトを埋め込むだけです。

| 項目 | 実測 |
|---|---|
| 23 ファイル（.docx 7 / .csv 6 / .html 6 / .txt 3 / .md 1、14.8 KiB）の生成 | **1.68 秒** |
| 部門フォルダー | 6 個（Sales / HR / Finance / Engineering / Legal / IT-Operations） |

`.docx` は OOXML の zip を `System.IO.Compression` で組み立てれば、Word を入れずに実物が作れます。

| 利点 | 注意点 |
|---|---|
| 転送量ゼロ、サイズ上限なし | PowerShell が長くなる（本家の Python 生成器も 615 行） |
| 実データを一切持ち出さないので情報漏洩の懸念がない | 角括弧を含むパス（`[Content_Types].xml`）は `-LiteralPath` か .NET 直書きが必要 |
| 再現性がある | |

> **注意**: 検証中、`Set-Content "[Content_Types].xml"` が角括弧をワイルドカードと解釈して
> パラメーターバインドに失敗しました。`[System.IO.File]::WriteAllText` を使うと回避できます。

### 方法 2: Workshop Studio の静的アセットとして配る（検証済み）

Workshop Studio はコンテンツと一緒に静的ファイルを配信できます。**動作を確認しました。**

```bash
curl -sS -o documents.zip \
  "https://static.us-east-1.prod.workshops.aws/public/<content-id>/static/documents.zip"
```

本家も構成図をこの仕組みで配信しており、`/static/` 配下のファイルは HTTP 200 で取得できます
（ディレクトリ一覧は 403）。

| 利点 | 注意点 |
|---|---|
| 実物の Office 文書をそのまま配れる | 配布する文書は公開物になるため、合成データに限る |
| 参加者の手順が 1 行で済む | アセットのサイズ上限は未確認 |
| | ダウンロード時間が参加者の回線に依存する |

### 方法 3: Linux EC2 から SMB マウントする（未検証）

Windows デスクトップを参加者に配らずに SMB 経路を通す案です。
本家の Linux EC2 に `cifs-utils` を入れ、`mount -t cifs` で NTFS ボリュームに書き込みます。

| 利点 | 注意点 |
|---|---|
| Windows インスタンスとその接続手段が不要 | **未検証。** AD の資格情報が必要で、手順書に平文で書けない |
| 参加者の操作が CLI だけで完結 | 実際の Windows クライアントが付ける ACL と所有者にはならない |

### 方法 4: Transfer Family (SFTP)

本家のモジュール 16 をデータ投入に転用する案です。**目的が逆**なので推奨しません。
本家の 16 は「成果物を外部パートナーに渡す」ためのもので、投入経路としては構成が過剰です。
本家枠も 20 分あります。

### 方法 5: SMB をやめる（現実的な折衷案）

Active Directory を用意せず、**MIXED セキュリティスタイル**のボリュームに UNIX ID の
アクセスポイントを付けて、置くデータだけを「ファイルサーバーらしい文書」にします。

| 利点 | 失うもの |
|---|---|
| 本家の払い出しをほぼそのまま使える | SMB と NTFS の真正性。Windows ACL の話ができない |
| AD が当日の依存にならない | 「Windows ファイルサーバーを題材にした」と言いにくい |
| 払い出し時間が伸びない | |

Quick に見せる文書の中身は方法 1 と同じにできるので、
**AI 活用の見せ場は変わりません。** 準備時間が取れない初回開催では有力な選択です。

## 選び方

| 状況 | 推奨 |
|---|---|
| 初回開催、運営を固めたい | NFS 版（本家をほぼそのまま） |
| 参加者層に Windows ファイルサーバーが多い | SMB 版 + 方法 1 |
| 準備時間が取れないが題材は文書にしたい | 方法 5（MIXED + UNIX ID） |
| AI エージェントを見せたい | 9 を実演のみで差し込み、13 を外す |

## 関連

| ドキュメント | 内容 |
|---|---|
| [NFS 版 90 分シナリオ](eda-s3-access-points-90min/) | 実測値の根拠と落とし穴 |
| [SMB 版 90 分シナリオ](smb-fileserver-quick-90min/) | Windows ファイルサーバー版の詳細 |
| [実測値](eda-s3-access-points-90min/measured-timings.md) | すべての時間の測定条件 |
| [開催時の落とし穴](eda-s3-access-points-90min/facilitation-risks.md) | エラーが原因を指さない 3 パターン |
