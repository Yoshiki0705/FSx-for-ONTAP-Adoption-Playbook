---
title: 端末から S3 Access Points に届く条件 — ゲートウェイエンドポイントでは VPN 経由の流入がルーティングされない
lifecycle: [design, build]
domains: [client-access, data-utilization, security-governance]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html
lang: ja
---

# 端末から S3 Access Points に届く条件

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — クライアントアクセス](../README.md)

---

## 結論

**端末から FSx for ONTAP S3 Access Points を使うには、VPC 内のインターフェースエンドポイントが要ります。**
ゲートウェイエンドポイントでは届きません。VPN / Direct Connect / Transit Gateway / ピアリング経由で
VPC に入るトラフィックをルーティングしないためです。

**条件は 4 つあり、上から順に狭まります。**

| # | 条件 | 満たしていないと |
|---|---|---|
| 1 | ONTAP 9.17.1 以降 | Access Point を作れません。アップグレードの検討から始まります |
| 2 | ファイルシステムと Access Point が同一アカウント・同一リージョン | **作成できません。** アカウント分離を前提にした設計は成立しません |
| 3 | 端末のリクエストが VPC に入り、**インターフェースエンドポイント**に届くこと | 名前は解決しても接続できません |
| 4 | IAM の権限と、Access Point に紐づくファイルシステムユーザーの権限が**両方**許可すること | 片方だけでは拒否されます |

**3 が端末固有の条件です。** 1・2・4 は EC2 から使う場合と同じで、既存のノートに書かれています。

> **区分**: `documented` — 前提条件は AWS 公式ドキュメント、ゲートウェイエンドポイントの制約は
> このリポジトリの `verified` なノートに基づきます（2026-09-13 に確認）。
> **端末からの到達は当方では未測定です。** `examples/client-access/probe-endpoint.sh` の
> `--s3-access-point` が `ListObjectsV2` の結果をそのまま記録するので、測定後にここへ実測を足します。

---

## 3 番目の条件が端末固有である理由

**S3 のリクエストは、端末から見ると「インターネット上の API」です。** split-tunnel の VPN では、
その通信は VPN に入らず端末のネットワークからそのまま出ていきます。**それでは VPC に入らないため、
Access Point に届きません。**

| 構成 | 結果 |
|---|---|
| split-tunnel、S3 のエンドポイントなし | **届きません。** リクエストは VPC を通りません |
| split-tunnel、**ゲートウェイ**エンドポイントあり | **届きません。** VPN 経由の流入をルーティングしません |
| split-tunnel、**インターフェース**エンドポイントあり + 名前がそこに解決する | **届きます** |
| full-tunnel、インターフェースエンドポイントあり | 届きます。**端末の全通信が VPN を通ります** |

**3 行目の「名前がそこに解決する」が抜けやすいです。** インターフェースエンドポイントを作っても、
端末が公開の S3 の名前を引いていれば公開のアドレスに向かいます。
**エンドポイント固有の DNS 名を使うか、Private DNS を有効にするかの判断になります。**

**`examples/client-access/` は Private DNS を無効にしています。** 有効にすると VPC 内のすべての
S3 リクエストの名前解決が変わるため、**この検証のためだけに VPC 全体の挙動を変えないという判断です。**

---

## 端末に置く AWS 資格情報

**Access Point へのリクエストは SigV4 で署名されます。** 署名に使う資格情報が端末に必要です。

| 方式 | 端末に残るもの | 失効 |
|---|---|---|
| IAM Identity Center の短期資格情報 | 期限付きのセッション | **放置で失効します** |
| IAM ユーザーの長期アクセスキー | `~/.aws/credentials` に無期限のキー | **明示的に無効化するまで有効です** |

**推奨は短期資格情報です。** ただし引き換えに、サインインの手順が増え、期限切れのたびに再取得が要ります。
端末に残る秘密の全体像は [端末側の資格情報の置き場所](where-endpoint-credentials-live.md) にあります。

---

## AD 参加 SVM の場合に増える条件

**AD に参加した SVM では、S3 Access Points 経由の全データ操作にドメインコントローラへの到達性が
必要です。** そして **`HeadBucket` は AD が到達不能でも成功します。**

**したがって `HeadBucket` を疎通確認に使うと偽陽性になります。** `ListObjectsV2` や `GetObject` で
確認してください。詳細は
[AD への依存は参加時ではなく生涯続く](../../multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) にあります。

`examples/client-access/` は AD に参加しないため、この条件は当たりません。

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `aws fsx describe-file-systems` の ONTAP バージョンを ONTAP REST の `GET /api/cluster?fields=version` で確認する | 条件 1。**AWS CLI はバージョンを `None` で返すことがあります** |
| 2 | `aws ec2 describe-vpc-endpoints --query 'VpcEndpoints[].[ServiceName,VpcEndpointType,PrivateDnsEnabled]'` | 条件 3。**`Gateway` と出ていたら端末からは届きません** |
| 3 | 端末から `nslookup s3.<region>.amazonaws.com` と、エンドポイント固有の DNS 名の両方を引く | どちらに向かうか |
| 4 | 端末から `aws s3api list-objects-v2 --bucket <access-point-alias> --max-items 1` | 条件 3 と 4 の両方。**`HeadBucket` は使わないでください** |
| 5 | 失敗した場合、エラー全文を残す | **エンドポイント・認可・名前解決のどれで落ちたかはエラーの種類で分かれます** |

**手順 5 を省かないでください。** 3 つの原因がどれも「list が失敗した」に見えます。
症状から層を逆引きする手順は
[S3 Access Point 経由のリクエストはどう判定されるか](../../../reference/decision-trees/access-point-authorization.md) にあります。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| S3 なので端末からインターネット経由で使える | **VPC に入る必要があります。** Access Point は VPC 内のエンドポイント経由です |
| ゲートウェイエンドポイントを作れば VPN からも届く | **VPN / Direct Connect / Transit Gateway / ピアリング経由の流入はルーティングされません** |
| インターフェースエンドポイントを作れば自動的に使われる | **名前解決がそこに向いている必要があります。** Private DNS かエンドポイント固有の DNS 名です |
| `HeadBucket` が通ったので疎通は正常 | **AD 参加 SVM では AD が到達不能でも成功します。** 偽陽性です |
| IAM で許可すれば書き込める | **Access Point に紐づくファイルシステムユーザーが読み取り専用なら拒否されます** |
| Access Point を足しても他に影響はない | **ファイルシステムあたりのボリューム数上限が下がります**（[詳細](../../data-utilization/notes/s3-access-point-constraints.md)） |
| Private DNS は有効にしたほうが素直 | VPC 内の**すべての** S3 リクエストの名前解決が変わります。検証のために全体を変えるかは判断です |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| ONTAP 9.17.1 以降、同一アカウント、同一リージョンという前提条件、ボリューム数上限の低下 | [AWS: Restrictions and limitations（S3 Access Points for FSx for ONTAP）](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html) |
| 認可が IAM とファイルシステムユーザーの 2 層で、両方が許可しないと成功しないこと | [AWS: Managing access point access](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html) |
| ゲートウェイエンドポイントが VPN / Direct Connect / Transit Gateway / ピアリング経由の流入をルーティングしないこと、評価順序 | [S3 Access Point の権限設計](../../security-governance/notes/access-point-authorization-layers.md)（`verified`） |
| AD 参加 SVM では全データ操作に DC 到達性が必要で、`HeadBucket` が偽陽性になること | [AD への依存は参加時ではなく生涯続く](../../multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) |
| S3 との差分、オブジェクトサイズ上限、S3 Event Notifications が使えないこと | [FSx for ONTAP S3 AP は「S3 として使える」わけではない](../../data-utilization/notes/s3-access-point-constraints.md) |

---

## 関連ドキュメント

- [Domain — クライアントアクセス](../README.md) — このモジュールのハブ
- [パブリックインターネットからの経路は存在しない](no-route-from-the-public-internet.md) — ファイル側と同じ前提
- [端末側の資格情報の置き場所](where-endpoint-credentials-live.md) — SigV4 の資格情報の置き場所
- [S3 Access Point 経由のリクエストはどう判定されるか](../../../reference/decision-trees/access-point-authorization.md) — 症状から層を逆引きする
- [FSx for ONTAP S3 AP は「S3 として使える」わけではない](../../data-utilization/notes/s3-access-point-constraints.md) — Access Point 側の制約
- [端末の到達経路の比較](../../../reference/comparison/endpoint-reachability-options.md) — 経路の選択
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — クライアントアクセス](../README.md)
