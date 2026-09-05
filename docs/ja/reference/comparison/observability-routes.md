---
title: 監視経路の比較 — 何を見たいかと、どこにデータを置けるかで分かれる
lifecycle: [assess, design]
domains: [observability, security-governance, cost]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-harvest-grafana.html
lang: ja
---

# 監視経路の比較

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md) | [比較マトリクス](README.md)

---

## 結論

**Amazon FSx for NetApp ONTAP の監視経路に、どの状況でも最適な 1 つはありません。** 分かれ目は 2 つです。

1. **AWS が公開するメトリクスで足りるか、ONTAP 内部の粒度が要るか**
2. **データを AWS の VPC 内に留めるか、外に出せるか**

前者が「追加基盤を持つかどうか」を決め、後者が「SaaS を選べるかどうか」を決めます。**どちらも「何を見たいか」より前に決まっていることが多い**条件です。

> **Evidence**: `documented` — 各経路の性質は AWS / ベンダーの公式ドキュメントに基づきます（**取得日 2026-09-05**）。**当リポジトリでの実測は含みません。** 価格・提供リージョン・製品名は変動するため、選定時に各ベンダーの最新の情報で確認してください。

---

## 比較

| 観点 | 経路 1: Amazon CloudWatch | 経路 2: NetApp Harvest + Prometheus + Grafana | 経路 3: SaaS オブザーバビリティ | 経路 4: ONTAP REST 直叩き |
|---|---|---|---|---|
| **得意なこと** | AWS ネイティブ。追加基盤ゼロ。コンソールに既製のダッシュボードがある | ONTAP 内部の粒度。既製ダッシュボード。オンプレミスと近い見え方 | 既存投資の活用。ログとメトリクスの統合。アラートと通知の作り込み済みの仕組み | 欲しい値だけを取れる。中間層がない |
| **トレードオフ** | **ONTAP 内部の粒度は出ない。** レイテンシは平均のみ。Health / Headroom 相当の指標を自分で組む | **収集基盤の運用が増える。** 既製ダッシュボードのうち 10 種が非サポート、8 種が既定で無効。Amazon Managed Service for Prometheus へは 1 ホップ挟む | **取り込み量に応じた課金。** データが AWS の VPC 外に出る。所在の確認が要る | **作り込みと保守が自分に来る。** ダッシュボード・保存・アラートも自分で用意する |
| **追加で運用するもの** | なし | Harvest と Prometheus と Grafana（AWS 提供テンプレートは Amazon EC2 1 台）。監視面の死活監視 | 収集エージェントまたは転送の仕組み。ベンダー側の設定 | 収集の実装、保存先、可視化、それらの死活監視 |
| **認証・アクセス制御** | IAM で完結 | ONTAP 側は `fsxadmin` の資格情報。画面側は Grafana または Amazon Managed Grafana。**Amazon Managed Grafana は匿名アクセス不可、IdP 起点ログインも未サポート** | ベンダーの ID 管理。既存の SSO に載せられる場合がある | ONTAP 側の資格情報。**権限を絞ったユーザーを自分で設計できる** |
| **データの所在** | AWS のリージョン内 | **自分が置いた場所**（VPC 内に留められる） | **ベンダーの基盤。AWS の VPC 外。** 保管される国は選択によるが、**選べる範囲はベンダーごとに違う** | **自分が置いた場所**（VPC 内に留められる） |
| **課金の発生点** | メトリクスとダッシュボードとアラーム | 監視用インスタンスと関連 AWS サービス。Amazon Managed Service for Prometheus / Amazon Managed Grafana を使う場合はそれぞれ | 取り込み量・保持期間・利用者数など | 実装を動かす基盤 |
| **拠点をまたぐとき** | AWS アカウント単位。他プラットフォームは対象外 | クロスアカウントは到達性の確保。**拠点をまたぐと収集元を分散させる構成に変わる** | ベンダー側が集約点になるため、拠点の追加は接続の追加で済む場合がある | 実装次第。分散も集約も自分で設計する |

**経路 1 のトレードオフを「粒度が出ない」の 1 行で終わらせていません。** Health と Headroom 相当を自分で組む作業が発生します。これは経路 2 の「収集基盤の運用が増える」と同じ種類のコストで、**置き場所が違うだけ**です。

詳細は [オンプレのダッシュボードはそのまま移らない](../../domains/observability/notes/on-prem-dashboards-do-not-transfer.md)、[Harvest は remote_write を持たない](../../domains/observability/notes/harvest-has-no-remote-write.md)、[経路は認証とアクセス経路で先に狭まる](../../domains/observability/notes/route-choice-is-bounded-by-access-and-auth.md) にあります。

---

## データの所在についての確認事項

**経路 3 を検討する場合に確認する項目です。** 特定のベンダーの問題ではなく、SaaS 経路に共通する性質です。

> **鮮度に関する補足**: **提供リージョンは変動します。** Datadog や New Relic のように東京リージョンを提供しているベンダーもあります。**この表の記載は 2026-09-05 時点の調査であり、選定時には各ベンダーの最新のドキュメントで確認してください。** 古い情報を前提にすると、選択肢を実際より狭く見積もることがあります。

**遵守できるかどうかの判断は、このドキュメントの領域ではありません。** 確認すべき問いを並べます。**回答は読者と法務・コンプライアンスの領域です。**

| # | 問い | なぜ効くか |
|---|---|---|
| 1 | テレメトリのラベルに含まれる**ボリューム名・共有名・パス**が個人を識別しうるか | 命名規約によって個人情報が混入しえます |
| 2 | 収集対象に**利用者の識別子やメールアドレス**が含まれる設定になっていないか | 機能の有効化で収集範囲が広がる場合があります |
| 3 | 保管される国が自組織の要件に合うか。**越境移転の根拠を自組織で持てるか** | 所在は選択で決まりますが、選べる範囲はベンダーごとに違います |
| 4 | 監査要件が **AWS の VPC 外**での保管を許すか | 経路 1・2・4 と経路 3 の分かれ目です |
| 5 | 所在の変更が**後から**可能か | 不可逆なら、選択の時点が唯一の判断点になります |
| 6 | 保持期間と削除要求の扱いが要件に合うか | 課金と要件の両方に効きます |
| 7 | 一部の情報が**選択したリージョン以外に置かれる**設計になっていないか | 「リージョンを選べる」は「すべてがそこに置かれる」を意味しません |

**問い 7 は見落とされます。** 次の節が実例です。

---

## NetApp Data Infrastructure Insights の扱い

**このリポジトリでは経路として扱いません。** AWS の公式ドキュメントが監視手段として挙げているため、事実だけを置きます。出典は [NetApp: Information and Region](https://docs.netapp.com/us-en/data-infrastructure-insights/security_information_and_region.html)（取得日 2026-09-05）です。

| # | 事実 |
|---|---|
| a | **現行の名称は NetApp Data Infrastructure Insights**（旧称 Cloud Insights）。AWS 側の記載には旧称が残っています |
| b | ホストリージョンは **US `us-east-1` / EMEA `eu-central-1` / APAC `ap-southeast-2` の 3 つ**。**日本から使う場合、APAC を選んでもオーストラリアに置かれます** |
| c | **ホストリージョンをどこにしても米国に置かれる情報があります**（テナント情報、認可に関する情報、利用者とテナントの関連） |
| d | Workload Security を有効にすると**共有上のファイル名とディレクトリ名**を参照し、User Directory コレクタを併用すると **Active Directory の表示名と会社のメールアドレス**を収集・保管します |
| e | **収集先の資格情報の秘密鍵は Acquisition Unit にのみ保管され、顧客環境を出ません**（緩和側の事実） |

**b と c が上の問い 3・7 に直接当たります。** e を併記しているのは、トレードオフを対称に読むために必要だからです。

扱わない理由は、当該製品が**このリポジトリの製品選定の規約で扱わない管理基盤の提供に統合されている**ためです。同等の目的は Amazon CloudWatch、ONTAP REST API、NetApp Harvest の組み合わせで達成できます。

---

## 選び方

**上から順に当てはめてください。先に当たった条件が経路を決めます。**

| # | 条件 | 経路 | 理由 |
|---|---|---|---|
| 1 | データを AWS の VPC 外に出せない | **経路 3 を除外** | 所在が要件に反します。以降を 1・2・4 で判断します |
| 2 | 見たいものが AWS の公開メトリクスで足りる | **経路 1** | 追加基盤を持たない選択が最も運用が軽くなります |
| 3 | ONTAP 内部の粒度が要り、既製ダッシュボードを使いたい | **経路 2** | 導入前に非サポート 10 種を確認してください |
| 4 | ONTAP 内部の粒度が要るが、欲しい値が数個だけ | **経路 4** | 収集基盤を持つコストが、得られる値に見合いません |
| 5 | 既存の SaaS に監視を集約しており、所在の要件を満たせる | **経路 3** | 集約による運用の一元化が効きます |
| 6 | 自社ポータルに監視の画面を持たせたい | **経路によらず追加設計** | Amazon Managed Grafana は匿名アクセス不可、IdP 起点ログインも未サポートです |

### 組み合わせが成立する場合

**排他ではありません。** 実際には次の組み合わせが成立します。

| 組み合わせ | 成立する条件 |
|---|---|
| 経路 1 + 経路 2 | 平常時のアラームは CloudWatch、掘り下げは Grafana。**アラームの二重化に注意** |
| 経路 1 + 経路 4 | 標準メトリクスは CloudWatch、足りない数個だけ REST。追加基盤が最小になります |
| 経路 2 + 経路 3 | Prometheus で収集し、SaaS へ転送。**問い 1〜7 は転送の時点で当たります** |

### 決めきれない場合

分岐の形は [監視経路の選択 決定木](../decision-trees/observability-route.md)、選定前の確認項目は [経路選定チェックリスト](../../domains/observability/checklists/route-selection.md) にあります。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| どの状況でも最適な経路が 1 つある | **分かれ目は「粒度」と「所在」の 2 つ**で、状況によって答えが変わります |
| CloudWatch は追加コストがないので常に有利 | **Health / Headroom 相当を自分で組む作業が発生します。** コストの置き場所が違うだけです |
| Harvest を入れれば運用が楽になる | 収集基盤の運用が増えます。**監視面の死活監視も必要**です |
| SaaS は所在だけ気をつければよい | **取り込み量に応じた課金**も設計対象です |
| SaaS のリージョンを選べば所在が確定する | **選んだリージョン以外に置かれる情報がある場合があります** |
| REST 直叩きは一番自由なので有利 | 保存・可視化・アラート・死活監視のすべてが自分に来ます |
| 経路は 1 つに絞らなければならない | **組み合わせが成立します。** 上の表を参照してください |
| 提供リージョンの一覧は固定である | 変動します。選定時に最新を確認してください |

---

## 参照した一次情報

| 論点 | 出典 | 取得日 |
|---|---|---|
| Harvest の既製ダッシュボードの分類（サポート 19 / 既定で無効 8 / 非サポート 10）、AWS 提供テンプレートが Amazon EC2 1 台構成であること、`fsxadmin` の資格情報を Secrets Manager 経由で渡すこと、サイジング指針 | [AWS: Monitoring FSx for ONTAP file systems using Harvest and Grafana](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-harvest-grafana.html) | 2026-09-05 |
| Harvest のエクスポータが Prometheus のプルエンドポイントであること | [Harvest 25.08: Prometheus Exporter](https://netapp.github.io/harvest/25.08/prometheus-exporter/) | 2026-09-05 |
| Amazon Managed Grafana の認証方式、匿名アクセスの不在、IdP 起点ログインの未サポート | [AWS: Authenticate users in Amazon Managed Grafana workspaces](https://docs.aws.amazon.com/grafana/latest/userguide/authentication-in-AMG.html) | 2026-09-05 |
| クロスアカウント構成の構成要素 | [re:Post: Harvest と Grafana によるクロスアカウント監視](https://repost.aws/knowledge-center/fsx-ontap-monitor-cross-accounts) | 2026-09-05 |
| Data Infrastructure Insights のホストリージョンと保管される情報 | [NetApp: Information and Region](https://docs.netapp.com/us-en/data-infrastructure-insights/security_information_and_region.html) | 2026-09-05 |
| CloudWatch のメトリクスから得られる統計の範囲 | [AWS: Volume metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-metrics.html) | 2026-09-05 |

---

## 関連ドキュメント

- [Domain — 可観測性](../../domains/observability/README.md) — このモジュールのハブ
- [監視経路の選択 決定木](../decision-trees/observability-route.md) — 分岐の形と段階的な広げ方
- [経路選定チェックリスト](../../domains/observability/checklists/route-selection.md) — 選定前の確認項目
- [オンプレのダッシュボードはそのまま移らない](../../domains/observability/notes/on-prem-dashboards-do-not-transfer.md)
- [Harvest は remote_write を持たない](../../domains/observability/notes/harvest-has-no-remote-write.md)
- [クロスアカウントは IAM ではなくネットワークの問題](../../domains/observability/notes/cross-account-is-a-network-problem.md)
- [経路は認証とアクセス経路で先に狭まる](../../domains/observability/notes/route-choice-is-bounded-by-access-and-auth.md)
- [監視は平均値で失敗する](../../playbooks/05-operate/notes/monitoring-fails-on-averages.md) — 何を監視し閾値をどこに置くか
- [知見の分類ポリシー](../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md) | [比較マトリクス](README.md)
