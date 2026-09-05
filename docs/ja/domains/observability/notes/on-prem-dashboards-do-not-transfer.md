---
title: オンプレのダッシュボードはそのまま移らない — 公開されるメトリクスセットが違う
lifecycle: [assess, design]
domains: [observability, performance]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-harvest-grafana.html
lang: ja
---

# オンプレのダッシュボードはそのまま移らない

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 可観測性](../README.md)

---

## 結論

**Amazon FSx for NetApp ONTAP は、オンプレミスの NetApp ONTAP とは異なるメトリクスセットを公開します。**

そのため NetApp Harvest の既製ダッシュボードは全部が使えるわけではありません。AWS 公式ドキュメントは 3 つに分類しています。

| 分類 | 数 |
|---|---|
| サポート対象（`fsx` タグ付き） | 19 |
| サポート対象だが Harvest の既定では無効 | 8 |
| **非サポート** | **10** |

**「オンプレと同じ Grafana ダッシュボードがそのまま使える」という期待は外れます。** サポート対象のダッシュボードでも、**一部のパネルは情報が欠けることがある**と明記されています。

> **Evidence**: `documented` — 分類とダッシュボード名は AWS 公式ドキュメントの記載に基づきます（**取得日 2026-09-05**）。**著者による実測は含みません。** ダッシュボードの構成は Harvest の版で変わるため、[自環境での確認手順](#自環境での確認手順) で自分の版を確認してください。

---

## サポート状況の 3 分類

### 非サポート（10 種）

```text
ONTAP: Disk
ONTAP: External Service Operation
ONTAP: File Systems Analytics (FSA)
ONTAP: Headroom
ONTAP: Health
ONTAP: MAV Request
ONTAP: MetroCluster
ONTAP: Power
ONTAP: Shelf
ONTAP: S3 Object Stores
```

### サポート対象だが既定で無効（8 種）

```text
ONTAP: FlexCache
ONTAP: FlexGroup
ONTAP: NFS Clients
ONTAP: NFSv4 Storepool Monitors
ONTAP: NFS Troubleshooting
ONTAP: NVMe Namespaces
ONTAP: SMB
ONTAP: Workload
```

**この 8 種は「無い」のではなく「有効化していないだけ」です。** SMB と NFS のトラブルシューティング、FlexCache、ワークロード別の可視化はここに含まれます。**移行計画でこれらを前提にしているなら、有効化が必要だと認識しておく必要があります。**

### サポート対象（19 種）

Aggregate / cDOT / Cluster / Compliance / Datacenter / Data Protection / LUN / Network / Node / Qtree / Security / SnapMirror（+ Destinations / Sources）/ SVM / Volume（+ by SVM / Deep Dive）、および Harvest: Metadata。

---

## 運用設計に影響する不在 — Health と Headroom

非サポート 10 種のうち、**運用設計を変えるのは Health と Headroom の 2 つ**です。

| ダッシュボード | 無いことの意味 |
|---|---|
| **Health** | **「システム全体が健全か」を 1 画面で見る入口がありません。** 健全性の判断は、個別メトリクスの組み合わせと Amazon CloudWatch のアラーム、および FSx for ONTAP 側が出す警告に置き換える設計になります |
| **Headroom** | **性能の余裕をどれだけ残しているかの指標が出ません。** 「あと何割まで負荷を上げられるか」の判断材料を、スループット容量とクレジット残高の側から自分で作ることになります |

Headroom の代替として何を見るかは [監視は平均値で失敗する](../../../playbooks/05-operate/notes/monitoring-fails-on-averages.md) と [p99 は CloudWatch のメトリクスからは出せない](../../performance/notes/what-you-cannot-read-from-cloudwatch.md) にあります。**クレジット残高が性能の余裕そのものを左右する**ため、Headroom の不在はベンチマークの設計にも波及します。

> **設計に関する補足**: Health ダッシュボードの代替を「アラームを増やす」で埋めると、平常時に無症状の劣化を見落とします。閾値の置き方は運用側のノートを先に読んでください。

---

## マネージドサービスとして筋が通る不在

残る 8 種の不在は、責任分界点の結果です。**これらを探す必要はありません。**

| ダッシュボード | 不在の理由 |
|---|---|
| Disk / Shelf / Power | 物理層は AWS の管理範囲です。利用者に露出しません |
| MetroCluster | FSx for ONTAP のデプロイタイプに存在しない構成です |
| File Systems Analytics (FSA) | ファイルシステム解析の機能面が公開メトリクスに含まれません |
| S3 Object Stores | ONTAP の S3 オブジェクトストア機能に対応するダッシュボードで、FSx for ONTAP S3 AP の監視とは別物です |
| External Service Operation / MAV Request | 対応する機能面が公開メトリクスに含まれません |

**Disk と Shelf と Power が無いことは、想定どおりの挙動です。** 一方で Health と Headroom の不在は、上の節のとおり設計の変更を要求します。**同じ「非サポート」の中でも影響の質が違います。**

---

## 自環境での確認手順

**ダッシュボードの一覧は Harvest の版で変わります。** 公式ドキュメントの分類と自分の版の実物を突き合わせてください。

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 導入予定の Harvest の版を確定させる | 分類の前提。版が違えばダッシュボードの構成も変わります |
| 2 | Grafana で `fsx` タグの付いたダッシュボードを一覧する | サポート対象として認識されているもの |
| 3 | 既定で無効な 8 種のうち、自分の要件に必要なものを洗い出す | 有効化の作業量 |
| 4 | オンプレで日常的に見ているダッシュボードを列挙し、上の 3 分類に振り分ける | **移行後に失うものの実数** |
| 5 | 手順 4 で非サポートに落ちたものについて、代替の指標を決める | 運用設計の変更点 |
| 6 | サポート対象のダッシュボードを開き、空欄のパネルを記録する | パネル単位の欠損。**分類だけでは分かりません** |

**手順 4 と 6 が最も見落とされます。** 手順 4 を飛ばすと移行後に「見ていた画面が無い」と気づき、手順 6 を飛ばすと「ダッシュボードはあるのに数値が出ない」に当たります。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| Harvest を入れればオンプレと同じ画面になる | **10 種が非サポート、8 種が既定で無効です** |
| サポート対象なら全パネルが埋まる | **一部のパネルは情報が欠けることがある**と明記されています |
| 既定で無効な 8 種は使えない | 使えます。有効化が必要なだけです |
| 非サポートはすべて同じ扱いでよい | **Health と Headroom の不在は運用設計を変えます。** Disk / Shelf / Power とは影響の質が違います |
| Power が無いのは制限である | 物理層は AWS の管理範囲です。責任分界点の結果です |
| `ONTAP: S3 Object Stores` が FSx for ONTAP S3 AP の監視に使える | ONTAP の S3 オブジェクトストア機能向けで、別物です |
| ダッシュボードの一覧は固定である | Harvest の版で変わります。自分の版で確認してください |

---

## 参照した一次情報

| 論点 | 出典 | 取得日 |
|---|---|---|
| FSx for ONTAP がオンプレミスの ONTAP と異なるメトリクスセットを公開すること、`fsx` タグ付きの 19 種のみがサポート対象であること、一部パネルの情報が欠けうること、既定で無効な 8 種、非サポートの 10 種 | [AWS: Monitoring FSx for ONTAP file systems using Harvest and Grafana](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-harvest-grafana.html) | 2026-09-05 |

---

## 関連ドキュメント

- [Domain — 可観測性](../README.md) — このモジュールのハブ
- [監視経路の選択 決定木](../../../reference/decision-trees/observability-route.md) — どの経路を選ぶか
- [監視経路の比較](../../../reference/comparison/observability-routes.md) — 経路別のトレードオフ
- [Harvest は remote_write を持たない](harvest-has-no-remote-write.md) — Harvest を選んだ後に来る運用
- [監視は平均値で失敗する](../../../playbooks/05-operate/notes/monitoring-fails-on-averages.md) — 何を監視し閾値をどこに置くか
- [p99 は CloudWatch のメトリクスからは出せない](../../performance/notes/what-you-cannot-read-from-cloudwatch.md) — Headroom の代替に使う指標
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 可観測性](../README.md)
