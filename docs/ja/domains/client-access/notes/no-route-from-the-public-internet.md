---
title: パブリックインターネットからの経路は存在しない — 設定の問題ではなく、Elastic IP は自動的に外される
lifecycle: [assess, design, build]
domains: [client-access, security-governance]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-clients-fsx.html
lang: ja
---

# 端末を直接インターネット経由で繋げるか？

繋げません。パブリックアクセスは非対応で、Elastic IP を付けても自動的に外されます。

## このノートで学べること

- 端末を FSx for ONTAP に直接インターネット経由で繋ぐ経路が提供されていないこと（設定の問題ではない）
- 端末利用は必ず到達経路の設計を伴い、AWS API の成功はデータ経路の到達性を証明しないこと

## このノートが答えないこと

- Elastic IP が自動的に外されるまでの時間や、その間の到達性（未測定）
- どの到達経路（Client VPN / Direct Connect / VDI / ブラウザ）が要件に合うかの選定判断

## 前提レベル

basic

## 本文

<a id="パブリックインターネットからの経路は存在しない"></a>

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — クライアントアクセス](../README.md)

---

### 結論

**手元の端末を FSx for ONTAP に直接インターネット経由で繋ぐ方法はありません。** セキュリティグループの
設定でもルートテーブルでもなく、経路そのものが提供されていません。

AWS のドキュメントは 2 つのことを書いています。

| 記述 | 意味 |
|---|---|
| Amazon FSx はパブリックインターネットからのファイルシステムへのアクセスをサポートしない | 「非推奨」ではなく非対応です |
| ファイルシステムの ENI に付いた Elastic IP は **Amazon FSx が自動的に切り離す** | 手で付け直しても外されます。回避策ではありません |

**したがって端末からの利用は、必ず到達経路の設計を伴います。** 「マウントコマンドを利用者に配る」で
終わる作業ではありません。経路の選択肢と費用は
[端末の到達経路の比較](../../../reference/comparison/endpoint-reachability-options.md) にあります。

> **区分**: `documented` — AWS 公式ドキュメントの記載に基づきます（2026-09-13 に確認）。
> **自環境での再現は行っていません。** Elastic IP を付けて外されるまでの時間や、その間の到達性は
> 測っていません。**確認するなら検証用のファイルシステムで行ってください。**

---

### この制約が設計に効く 3 か所

**「あとで VPN を足せばよい」で済まない場合があります。**

| 場面 | 効き方 |
|---|---|
| **在宅勤務の利用者にファイル共有を出す** | 端末ごとの経路（Client VPN）か、端末に何も入れない経路（VDI・ブラウザ）かを、利用者数が確定する前に決めることになります。**証明書配布の運用は人数に比例します** |
| **社外の協力会社にデータを渡す** | 相手の端末に VPN プロファイルを入れる話になります。**入れられない場合、ファイル共有プロトコルは選択肢から消えます** |
| **検証・PoC を短期間でやる** | Direct Connect は回線の手配が週単位なので選べません。**Client VPN は分単位で作れて、サブネットの関連付けを外せば課金が止まります** |

**3 行目が最も見落とされます。** 「まず繋いで試す」ができる経路が 1 つしかないため、
検証の設計が到達経路の選択に先に縛られます。

---

### 「非対応」の範囲

**インターネットから届かないのは、ファイルシステムのデータ経路です。** 混ぜないでください。

| 対象 | パブリックインターネットから届くか |
|---|---|
| NFS / SMB / iSCSI のデータ経路 | **届きません** |
| ONTAP の管理エンドポイント（REST / SSH） | **届きません。** 同じ VPC の中にあります |
| Amazon FSx の AWS API（`fsx.<region>.amazonaws.com`） | 公開リージョナルエンドポイントを使う場合はパブリックアドレスに解決されます。Amazon FSx インターフェイス VPC エンドポイントで Private DNS を有効にした場合は、同じ名前がエンドポイントのプライベートアドレスに解決されます |
| S3 Access Points 経由のデータ | `Internet` origin はポリシーが許可すれば公開 S3 エンドポイントから到達できます。VPC 内で発生した通信はゲートウェイエンドポイントを使えます。VPN 等で VPC に入る通信を私設経路に限定する場合はインターフェイスエンドポイントが必要です（[詳細](what-an-endpoint-needs-to-reach-s3-access-points.md)） |

**3 行目は、公開リージョナルエンドポイントを使い、Private DNS で上書きしていない場合の挙動です。**
split-tunnel の VPN でも `aws fsx describe-file-systems` は端末側のインターネット経路から動きます。
Amazon FSx インターフェイス VPC エンドポイントを使う構成では、端末の DNS と経路がそのエンドポイントへ
向いていることを別に確認します。どちらの場合も、AWS API の成功は NFS / SMB / iSCSI のデータ経路の
到達性を証明しません。

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| セキュリティグループで 0.0.0.0/0 を許可すればインターネットから届く | **経路がありません。** 許可する対象が到達しません |
| Elastic IP を付ければ公開できる | **Amazon FSx が自動的に切り離します** |
| `aws fsx describe-file-systems` が端末から通ったので経路はある | **AWS API はパブリックアドレスです。** データ経路とは別です |
| VPN を後から足せばよいので設計時は考えなくてよい | **利用者数と端末の種類で経路が変わります。** 証明書配布の運用は人数に比例し、端末に何も入れられない層はブラウザ経路しかありません |
| Multi-AZ にすれば外から届く | デプロイタイプは可用性の設定で、到達経路とは無関係です |

---

### 参照した一次情報

| 論点 | 出典 |
|---|---|
| パブリックインターネットからのアクセスが非対応であること、ENI に付いた Elastic IP が自動的に切り離されること、対応する NFS / SMB / iSCSI のバージョン | [AWS: Supported clients](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-clients-fsx.html) |
| 別 VPC・別アカウント・別リージョン・オンプレミスからは Transit Gateway / Direct Connect / VPN が前提であること | [AWS: Mounting volumes on macOS clients](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-mac-client.html) |

---

### 関連ドキュメント

- [Domain — クライアントアクセス](../README.md) — このモジュールのハブ
- [端末の到達経路の比較](../../../reference/comparison/endpoint-reachability-options.md) — 経路 5 つの費用と引き換え
- [端末からデータに届く経路の決定木](../../../reference/decision-trees/client-access-route.md) — 判断の順序
- [端末から S3 Access Points に届く条件](what-an-endpoint-needs-to-reach-s3-access-points.md) — オブジェクト側の経路
- [エンドユーザーがデータに届く経路は 4 つある](../../../playbooks/02-design/notes/how-end-users-reach-the-data.md) — ブラウザ経路と SFTP 経路
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — クライアントアクセス](../README.md)

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `aws fsx describe-file-systems --query 'FileSystems[].OntapConfiguration.Endpoints'` を**端末から**実行する | AWS API には届くこと。**ここが通ることは経路の証明になりません** |
| 2 | 返ってきた NFS / SMB のアドレスに対し、端末から到達性を試す | データ経路の到達性。VPN 未接続なら失敗します |
| 3 | ファイルシステムの ENI に Elastic IP が付いていないことを確認する | 付け直しても自動的に外されること |

**手順 1 と 2 を分けて実行してください。** 1 だけで判断すると、経路があると誤認します。

手順 2 のデータ経路の到達性は、次の読み取り専用コマンドを端末から実行して確認できます。

```bash
nc -vz <data-lif-ip> 445
```

### 期待結果

```text
VPN や専用線で VPC に入っていなければ接続は失敗する（データ経路はインターネットから届かない）。
同じ端末から AWS API 呼び出しが成功しても、それはデータ経路の到達性を意味しない
```

このコマンドはポートへの到達性を試すだけで、ファイルシステムにも経路設定にも変更を加えません。

## Read next

[端末の種類はプロトコルを先に狭めるか？](the-endpoint-narrows-the-protocol.md)
