---
title: EDA ログのゼロコピー分析を 90 分に収める — 機械の時間はほぼゼロで、律速は Quick のインデックス待ち
lifecycle: [assess, build]
domains: [data-utilization, multiprotocol-identity]
evidence: hypothesis
lang: ja
---

# EDA ログのゼロコピー分析を 90 分に収める

[🏠 リポジトリトップ](../../../../README.md) | [Workshop Studio](../README.md)

対象は AWS Workshop Studio 公開ワークショップ
[FSx for NetApp ONTAP S3 Access Points Workshop](https://catalog.us-east-1.prod.workshops.aws/workshops/9cd82e0b-8348-456b-932a-818b9e5825a1/en-US)
です。本家は 2〜3 時間・18 モジュール構成で、全部は実施できません。

> **このタイムテーブル自体は未検証です。** 個々のモジュールの所要時間は
> [実測値](measured-timings.md) のとおり測りましたが、90 分を通しでリハーサルした結果ではありません。
> 参加者の手が止まる箇所は人数と回線で変わります。初回開催前に一度通してください。

## 結論を先に

3 つだけ覚えておけば構成できます。

1. **機械の時間は無視していい。** 採用モジュールの API・スクリプト実行時間の合計は
   実測 **35 秒程度**でした。90 分の中身はほぼ全部、説明と画面操作と待ち時間です。
2. **律速は Amazon Quick のナレッジベース同期だけで、本家の記載より長い。** 本家は「3〜5 分」
   および「5〜10 分」と書いていますが、実測では **11.5 分を超えても完了しませんでした**。
   **経過 40 分の時点で開始し、質問する時間までに 25 分空ける**構成にしています。
3. **モジュールを単純に削ると壊れる。** 集計 CSV を作るのは「QuickSight Dashboards」の Step 1 ですが、
   「Athena SQL Queries」がその CSV に依存します。詳細は [依存関係](#モジュール間の隠れた依存)。

## 90 分タイムテーブル

イベント全体 2 時間のうち、ハンズオン本体を 90 分とした場合の配分です。

| 経過 | 分 | 内容 | 本家モジュール | 種別 |
|---|---|---|---|---|
| 00:00 | 10 | 導入。EDA の課題とゼロコピーの考え方、構成図 | Architecture Overview / S3 Access Points | 説明 |
| 00:10 | 8 | EDA ログ生成（500 ジョブ / 1,952 ファイル） | Generate EDA Data | 実習 |
| 00:18 | 10 | FSx for ONTAP S3 AP を作成し、NFS で書いたものが S3 API で見えることを確認 | Create S3 Access Points | 実習 |
| 00:28 | 12 | Amazon Quick セットアップ。**この枠の終わりで同期を開始する** | Setup Amazon Quick | 実習 |
| 00:40 | 5 | 集計 CSV を生成（この後の Athena の前提） | QuickSight Dashboards の Step 1 のみ | 実習 |
| 00:45 | 15 | Athena で SQL 5 本 | Athena SQL Queries | 実習 |
| 01:00 | 5 | ストレージ側の質疑。同期の余裕を吸収する枠 | — | 説明 |
| 01:05 | 17 | Amazon Quick に自然言語で質問 | AI-Powered Analytics | 実習 |
| 01:22 | 8 | まとめ。撤収手順の案内 | Architecture Recap / Cleanup | 説明 |

残り 30 分は受付・接続確認に 15 分、質疑とクロージングに 15 分を想定しています。

**同期に与える猶予は 25 分です**（00:40 開始 → 01:05 に質問開始）。実測が 11.5 分超なので、
倍以上の余裕を取っています。本家記載の 5〜10 分を信じて 15 分しか空けないと間に合いません。

**時間調整は Athena と 01:00 の質疑枠で行います。** クエリ 1 本の実行は実測 2〜3 秒なので、
5 本を 2 本に減らせば Athena の枠は 8 分程度まで縮みます。逆に同期が長引いたときは
クエリを増やし、質疑枠を延ばして吸収します。

> **確実性を上げる選択肢**: 同期を**開催前に済ませておく**方法もあります。データが固定なら
> 前日までにナレッジベースを作って同期を終わらせ、当日は設定画面の説明と質問だけにします。
> 参加者に手を動かしてもらう体験は減りますが、90 分から最大の不確実性を取り除けます。

## モジュールの取捨選択

Storage-JAWS として「ストレージの価値が伝わるか」を基準に選びました。

### 採用

| モジュール | 採用理由 |
|---|---|
| Generate EDA Data | 分析対象の実体を作る。NFS 側の書き込みという「もう一方のプロトコル」を体験する唯一の場面 |
| Create S3 Access Points | 本題。ここを削ると題材が成立しない |
| Setup Amazon Quick | 参加者の関心が高い。ゼロコピーの価値が「コピーせずに AI が読む」形で最も分かりやすく出る |
| AI-Powered Analytics | 上の成果を実際に触る。ここまで来ないとセットアップだけで終わる |
| Athena SQL Queries | 同期待ちを埋められる。かつ「同じデータが SQL からも読める」多用途性が示せる |
| QuickSight Dashboards の Step 1 のみ | 上記 2 つが依存する CSV の生成。ダッシュボード作成本体は不採用 |

### 不採用

| モジュール | 不採用の理由 |
|---|---|
| Deploy AgentCore Gateway | 手順 790 行・8 ステップ。Cognito ユーザープール、Lambda、IAM ロールを CloudFormation で作成します。全部を参加者が構築する形なら **35〜45 分**の見積もりで、90 分には入りません。事前構築すれば 15〜20 分、実演のみなら 8〜10 分まで下がります。詳細は[見積もり](measured-timings.md#agentcore-gateway-を入れる場合の見積もり) |
| QuickSight Dashboards（Step 2 以降） | ビジュアル作成は人の作業時間が支配的で、削っても学びが減りにくい一方、時間の読みが最も外れます |
| Quick Automations | Quick セットアップ完了が前提で、スケジュール実行の結果はイベント中に見られません |
| Glue Data Catalog | **自アカウント開催では失敗リスクが最も高い**モジュールです。理由は [開催時の落とし穴](facilitation-risks.md) |
| Event-Driven Processing / Transfer Family | ストレージの主題から距離があり、それぞれ 20 分枠 |

## モジュール間の隠れた依存

本家のモジュール一覧は独立して選べる見た目ですが、実際には依存があります。

```text
Generate EDA Data ──> 1,952 個のログファイル
                          │
                          ├──> Create S3 Access Points ──> S3 API で参照可能
                          │                                    │
                          │                                    ├──> Setup Amazon Quick ──> AI-Powered Analytics
                          │                                    │                              │
                          │                                    │                              └──> Quick Automations
                          │                                    │
                          └──> QuickSight Dashboards の Step 1 ──> 集計 CSV
                                                                     │
                                                                     ├──> Athena SQL Queries
                                                                     └──> Glue Data Catalog
```

同じ内容を表でも示します。図が読めない環境でも判断できるようにしています。

| モジュール | 前提になるもの | 前提を落とすと |
|---|---|---|
| Create S3 Access Points | 対象ボリューム（データは後でもよい） | AP は作れるが見せる中身がない |
| Setup Amazon Quick | S3 AP のエイリアス、ログ実体 | ナレッジベースが空のまま同期完了する |
| AI-Powered Analytics | Quick の同期完了 | 質問しても答えが返らない |
| Athena SQL Queries | 集計 CSV | テーブル定義は作れるがクエリが 0 行 |
| Glue Data Catalog | 集計 CSV | クロール対象なし |

**注意すべきは Athena です。** 「QuickSight Dashboards」を丸ごと不採用にすると、その Step 1 で作られる
集計 CSV が存在しないため、Athena のクエリが 0 行になります。本家の並び順ではこの依存が見えません。

## 事前に済ませておくこと

当日の 90 分を守るために、開催前に終わらせておく作業です。

| 作業 | 理由 |
|---|---|
| リージョンを揃える | 本家は `us-east-1`（または `us-west-2`）前提で、IAM とアクセスポイントのポリシー ARN に `us-east-1` が直接書かれています。Workshop Studio のイベントとして開催するならイベント側のリージョンに合わせれば整合します。自アカウントで東京リージョンを使うなら全モジュールで置換が必要です |
| Amazon Quick のサインアップを事前に完了 | 初回サインアップとサービスロール設定を当日やると、それだけで 15 分の枠を使い切ります |
| **Quick の「Quick access to AWS services」で Amazon S3 を有効化** | **本家の手順に書かれていない設定です。**これが無いと IAM とアクセスポイントのポリシーを正しく設定してもナレッジベース作成が失敗します。詳細は[落とし穴](facilitation-risks.md#iam-だけでは-s3-に届かない-amazon-quick) |
| アクセスポイントのエイリアスを Quick のバケット一覧に登録 | 一覧には実バケットしか出ないため、自由入力で追加する必要があります |
| ナレッジベースの同期を前日までに完了させる（任意） | 実測 11.5 分超。当日の最大の不確実要因を消せます。`aws quicksight create-knowledge-base` は CLI に存在します |
| Quick の画面導線を一度たどる | 本家の「Explore → Knowledge」は現行 UI では **More → Knowledge** です |
| Athena のクエリ結果出力先バケットを用意 | 未設定だと Query editor の初回に設定ダイアログで止まります |
| 撤収手順を先に読む | 本家の Cleanup モジュールを開催前に確認します。作成物の削除順序は当日に読むものではありません |

## 関連

| ドキュメント | 内容 |
|---|---|
| [実測値](measured-timings.md) | 各操作の実測時間と、測定した環境の条件 |
| [開催時の落とし穴](facilitation-risks.md) | 自アカウント開催で詰まった箇所と切り分け |
| [FSx for ONTAP S3 AP の前提条件](../../domains/data-utilization/notes/s3-access-point-constraints.md) | アクセスポイント自体の制約 |
| [S3 Access Point の認可モデル](../../domains/data-utilization/notes/reaching-data-without-copies.md) | 1 つの ID で全リクエストを認可する構造 |
