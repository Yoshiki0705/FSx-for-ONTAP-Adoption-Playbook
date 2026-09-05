---
title: クロスアカウントは IAM ではなくネットワークの問題 — 拠点をまたぐと構成が質的に変わる
lifecycle: [design, build, operate]
domains: [observability, security-governance]
evidence: documented
source: https://repost.aws/knowledge-center/fsx-ontap-monitor-cross-accounts
lang: ja
---

# クロスアカウントは IAM ではなくネットワークの問題

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 可観測性](../README.md)

---

## 結論

**NetApp Harvest の接続先は ONTAP の管理エンドポイントで、AWS の API ではありません。**

したがって別アカウントのファイルシステムを監視する作業は、**IAM ロールの引き受けではなくネットワーク到達性の確保**になります。公式手順は AWS Transit Gateway・AWS Resource Access Manager による共有・双方向の静的ルート・セキュリティグループでの CIDR 許可の組み合わせです。

**そして拠点をまたぐ（オンプレミスや他のクラウド上の ONTAP を含める）と、この構成は延長では済みません。** 収集元を 1 か所に集める形から、**拠点ごとに収集元を置く形**に変わります。

> **Evidence**: `documented` — クロスアカウントの構成要素は AWS の公式ナレッジの記載に基づきます（**取得日 2026-09-05**）。**著者による実測は含みません。** クロスプラットフォームの節は**設計上の推論**で、検証していません（節内に明記）。

---

## IAM ではなくネットワークである理由

Amazon FSx for NetApp ONTAP に対する操作は 2 つの管理面に分かれます。**どちらを通るかで必要な権限の種類が変わります。**

| 操作 | 通る面 | 必要なもの |
|---|---|---|
| ファイルシステムの作成・パスワード再設定・バックアップ | AWS の API | IAM の権限 |
| **メトリクスと容量の収集（Harvest）** | **ONTAP の管理エンドポイント** | **そのエンドポイントへのネットワーク到達性と ONTAP 側の資格情報** |

**Harvest は後者です。** ファイルシステムの管理エンドポイントはプライベートアドレスで、VPC の外からは到達できません。**IAM をどう設定してもここは開きません。**

管理面が 2 つに分かれること自体の影響は [LUN と igroup は AWS の API の外側にある](../../block-storage/notes/block-objects-are-outside-the-aws-api.md) と同じ構図です。

---

## クロスアカウントで必要になる構成要素

公式手順の構成要素です。**作り方（画面操作、テンプレート、コマンド）はここでは扱いません** — 出典と [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) にあります。

| # | 要素 | どちらのアカウントか |
|---|---|---|
| 1 | Harvest と Grafana を載せた Amazon EC2 インスタンス | 監視する側 |
| 2 | Transit Gateway の作成 | **ファイルシステムがある側**（source） |
| 3 | AWS Resource Access Manager による Transit Gateway の共有 | source → 監視する側 |
| 4 | Transit Gateway アタッチメント（VPC とサブネットの指定） | **両方**（source 側と監視側で各 1 つ） |
| 5 | Transit Gateway のルートテーブルへの静的ルート **2 本** | source 側の VPC/サブネット CIDR と監視側の VPC/サブネット CIDR |
| 6 | サブネットのルートテーブルへのルート追加 | **両方**（相手側 CIDR 宛て、ターゲットは Transit Gateway） |
| 7 | セキュリティグループでの CIDR 許可 | **両方** |
| 8 | 受信ポート 3000 と 9090 の開放 | 監視する側 |

**ルートは双方向です。** 片側だけ入れた状態は、接続の失敗として現れます。

> **セキュリティに関する補足**: 手順は CIDR 単位の許可です。監視のために開けた経路は、監視以外の通信にも使えます。**到達範囲を監視に必要な最小限へ絞る判断は、手順の外側にあります。**

---

## 拠点をまたぐと変わること

> **確度に関する補足**: **この節は設計上の推論で、検証していません。** 出典があるのはクロスアカウントの手順までです。自分の構成で成立するかは [自環境での確認手順](#自環境での確認手順) の手順 5 以降で確認してください。

Transit Gateway は AWS のリージョン内の構成要素です。オンプレミスや他のクラウドにある ONTAP の管理エンドポイントは、**共有された Transit Gateway の先にはありません。** 到達させるには拠点ごとに別の接続機構（Site-to-Site VPN、AWS Direct Connect、各クラウドの相互接続）が必要になり、**それぞれが独立した設計判断になります。**

結果として構成が変わります。

| 観点 | クロスアカウント（AWS 内） | クロスプラットフォーム（拠点をまたぐ） |
|---|---|---|
| 収集元の数 | **1 か所に集められます** | **拠点ごとに置く前提になります** |
| 接続機構 | Transit Gateway + RAM 共有で統一 | 拠点ごとに異なる機構。統一されません |
| ルート設計 | 静的ルート 2 本 + 各サブネット | 拠点数に比例。経路の重複と競合の検討が入ります |
| 資格情報 | アカウントごと | **拠点ごと。管理主体が違う場合があります** |
| 障害の切り分け | 経路が 1 系統 | **どの拠点の経路が落ちたかの切り分けが増えます** |
| メトリクスの集約点 | 監視アカウントの Prometheus | 分散した収集元からの集約設計が別途必要になります |
| 版の差 | 同一プラットフォーム | **ONTAP の版が拠点ごとに違いえます。公開メトリクスの差が出ます** |

**「アカウントを増やす」と「拠点を増やす」は同じ作業ではありません。** 前者はルートとセキュリティグループの追加ですが、後者は**収集の構成そのものを分散型に変える**判断です。段階的な広げ方は [監視経路の選択 決定木](../../../reference/decision-trees/observability-route.md) にあります。

拠点ごとの ONTAP の版が違う場合、**取れるメトリクスがそろわない**点は [オンプレのダッシュボードはそのまま移らない](on-prem-dashboards-do-not-transfer.md) と同じ論点です。

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 監視側のインスタンスから管理エンドポイントへの到達性を確認する | **IAM ではなくネットワークの問題であること** |
| 2 | 片方向のルートだけを入れた状態で収集を試す | 双方向が必要であることの実測 |
| 3 | セキュリティグループの許可 CIDR を洗い出す | **監視のために開いた範囲。監視以外にも使えます** |
| 4 | Transit Gateway のルートテーブルと各サブネットのルートテーブルを別々に確認する | 2 か所とも必要であること |
| 5 | 拠点を 1 つ追加する想定で、必要な接続機構を書き出す | **Transit Gateway で足りるかどうか** |
| 6 | 拠点ごとの ONTAP の版を並べる | 公開メトリクスがそろうか |
| 7 | 収集元を 1 か所に置いた場合の経路の本数を数える | 分散構成に切り替える判断点 |

**手順 5 を設計段階で行わないと、拠点追加の時点で構成の作り直しになります。**

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| クロスアカウント監視は IAM ロールの引き受けで済む | **接続先は ONTAP の管理エンドポイントです。** ネットワーク到達性の問題です |
| ルートは監視側だけ入れればよい | **双方向です。** 静的ルートを 2 本作る手順になっています |
| Transit Gateway は監視する側で作る | 公式手順では**ファイルシステムがある側**で作り、RAM で共有します |
| ルートテーブルは 1 か所だけ触る | Transit Gateway のルートテーブルと各サブネットのルートテーブルの**両方**です |
| セキュリティグループは監視側だけ | **両方**で CIDR を許可します |
| クロスプラットフォームはクロスアカウントの延長 | **収集元を拠点ごとに置く構成に変わります**（この判断は未検証の推論です） |
| 拠点が増えても資格情報の設計は同じ | 管理主体が違う場合があります。分離の設計が要ります |
| 拠点をまたいでもメトリクスはそろう | ONTAP の版が違えば公開メトリクスに差が出ます |

---

## 参照した一次情報

| 論点 | 出典 | 取得日 |
|---|---|---|
| クロスアカウント構成の全手順（Transit Gateway を source 側で作成、RAM による共有、両側のアタッチメント、静的ルート 2 本、両側のサブネットルートテーブル、両側のセキュリティグループでの CIDR 許可、受信ポート 3000 と 9090） | [re:Post: How can I use Harvest and Grafana to monitor my FSx for ONTAP file systems in a cross account scenario?](https://repost.aws/knowledge-center/fsx-ontap-monitor-cross-accounts) | 2026-09-05 |
| Harvest と Grafana の同一アカウント構成、ポート要件 | [AWS: Monitoring FSx for ONTAP file systems using Harvest and Grafana](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-harvest-grafana.html) | 2026-09-05 |

---

## 関連ドキュメント

- [Domain — 可観測性](../README.md) — このモジュールのハブ
- [監視経路の選択 決定木](../../../reference/decision-trees/observability-route.md) — 段階的な広げ方
- [監視経路の比較](../../../reference/comparison/observability-routes.md) — 経路別のトレードオフ
- [Harvest は remote_write を持たない](harvest-has-no-remote-write.md) — 収集基盤の運用と資格情報
- [オンプレのダッシュボードはそのまま移らない](on-prem-dashboards-do-not-transfer.md) — 版による公開メトリクスの差
- [LUN と igroup は AWS の API の外側にある](../../block-storage/notes/block-objects-are-outside-the-aws-api.md) — 管理面が 2 つに分かれる構図
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 可観測性](../README.md)
