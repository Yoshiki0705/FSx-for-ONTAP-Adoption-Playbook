---
title: EBS が安くなくなる境目は台数ではなく同じデータの複製の数 — 最小構成の月額はスループット容量が 8 割
lifecycle: [assess, design, optimize]
domains: [block-storage, cost]
evidence: documented
source: https://aws.amazon.com/fsx/netapp-ontap/pricing/
lang: ja
---

# EBS が安くなくなる境目は台数ではなく同じデータの複製の数

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

## 結論

**FSx for ONTAP は 1 GB あたりの単価では Amazon EBS より安くなりません。** 東京リージョンの公開単価で、SSD が $0.150/GB-月に対し `gp3` が $0.096/GB-月です。しかも FSx for ONTAP にはスループット容量の月額が別に乗ります。**「EBS より安いストレージ」として持ち込む理由はありません。**

**分岐点は台数でもありません。** EC2 を 50 台起動しても、50 台がそれぞれ別のデータを持つなら EBS のままが素直です。

**効いてくるのは、同じバイト列の複製をいくつ持っているかです。** EBS では複製 1 つが課金対象の 1 ボリュームですが、FSx for ONTAP では FlexClone がデータをコピーせず、Snapshot も別建ての課金項目になりません。**だから同じデータの複製数が増えると、ある点で総額が入れ替わります。**

東京リージョンの最小構成では、**1 TB のデータセットに対して複製が約 9 個を超えたあたり**が入れ替わりの目安になります。データセットが大きいほどこの数は小さくなります。

> **区分**: `documented` — 単価は AWS Price List API から取得した公開値です（東京リージョン、FSx for ONTAP は effective 2026-07-01 / 取得 2026-09-05、EBS は effective 2026-09-01 / 取得 2026-09-05）。**下の計算は公開単価を使った算術であって、実測ではありません。**
> **価格は改定されます。** 判断の前に自分のリージョンの現行単価を引き直してください。手順は [自環境での確認手順](#自環境での確認手順) にあります。

---

## 取得した単価

東京リージョン（`ap-northeast-1`）です。**他のリージョンでは違います。**

| 項目 | 単価 |
|---|---|
| FSx for ONTAP SSD（Single-AZ） | **$0.150** / GB-月 |
| FSx for ONTAP SSD（Multi-AZ） | **$0.300** / GB-月 |
| FSx for ONTAP スループット容量（Single-AZ 第 2 世代） | **$2.013** / MBps-月 |
| FSx for ONTAP スループット容量（Multi-AZ 第 2 世代） | **$3.148** / MBps-月 |
| FSx for ONTAP スループット容量（Single-AZ 第 1 世代） | $0.906 / MBps-月 |
| FSx for ONTAP キャパシティプール（Standard、Single-AZ） | $0.0238 / GB-月 |
| FSx for ONTAP バックアップ | $0.050 / GB-月 |
| EBS `gp3` ストレージ | **$0.096** / GB-月 |
| EBS `gp3` 追加 IOPS（3,000 を超える分） | $0.006 / IOPS-月 |
| EBS `gp3` 追加スループット（125 MB/s を超える分） | $0.048 / MBps-月 |
| EBS `io2` ストレージ | $0.142 / GB-月 |
| EBS Snapshot（標準） | $0.050 / GB-月 |
| EBS Snapshot（アーカイブ） | $0.0125 / GB-月 |

**第 2 世代のスループット容量は第 1 世代より単価が高いことに注意してください**（Single-AZ で $2.013 対 $0.906）。第 2 世代でしか使えない機能（NVMe/TCP、Single-AZ の HA ペア複数）と引き換えです。

> **単位表記の注意**: Price List API の `gp3` 追加スループットのエントリは、単位が `GiBps-mo` で価格が $49.152 と返ります。説明文は「per provisioned MiBps-month $0.048」です（49.152 ÷ 1024 = 0.048）。**API の `unit` と `description` で単位が違うので、`pricePerUnit` だけを引き抜くと 1,024 倍ずれます。** FSx for ONTAP のスループットも同様に `unit` が `MiBps-Mo`、説明文は MBps です。
> **`pricePerUnit` を単体で使わず、必ず `unit` と `description` を突き合わせてから計算してください。** 上の 2 項目は 2026-09-05 の応答で単位が食い違っており、突き合わせを飛ばすと 1,024 倍ずれます。

---

## 最小構成の床

**FSx for ONTAP には下限があります。** 第 2 世代 1 HA ペアで SSD 1,024 GiB とスループット容量 384 MBps です。使わなくても払います。

| 内訳 | 計算 | 月額 |
|---|---|---|
| SSD 1,024 GiB | 1,024 × $0.150 | $153.60 |
| スループット容量 384 MBps | 384 × $2.013 | **$772.99** |
| **合計（Single-AZ 第 2 世代の床）** | | **$926.59** |

**床の 83% はスループット容量です。** 容量ではありません。**「小さく始める」ときに効くのはスループット容量の下限で、SSD の下限ではない**ということです。

Multi-AZ 第 2 世代の同構成は $1,516.03/月になります（1,024 × $0.300 + 384 × $3.148）。**同じ容量・同じスループットで約 1.6 倍です。**

---

## 入れ替わる点の計算

**モデルは 1 つです。** D GB のデータセットを C 個の複製として持つ場合。

```text
EBS               = $0.096 × D × C
FSx for ONTAP     = SSD の月額（D を満たす最小provisioning）+ $772.99
```

FSx for ONTAP 側で複製の追加コストを 0 として計算します（FlexClone の実データが増えない前提。実際には差分だけ増えます）。

| データセット D | FSx for ONTAP の月額 | 入れ替わる複製数 C |
|---|---|---|
| 512 GB | $926.59（SSD は 1,024 GiB が下限） | **約 19** |
| 1,024 GB | $926.59 | **約 9.4** |
| 2,048 GB | $1,080.19 | **約 5.5** |
| 5,120 GB | $1,540.99 | **約 3.1** |
| 10,240 GB | $2,308.99 | **約 2.3** |

**読み方は「複製が C 個を超えると FSx for ONTAP のほうが安くなる」です。** データセットが大きいほど C は小さくなります。10 TB 級では複製 3 つで入れ替わります。

**EBS 側で Snapshot も保持しているなら、その分 C はさらに小さくなります。** EBS の Snapshot は $0.050/GB-月の別課金で、FSx for ONTAP の Snapshot は確保済み SSD を消費するだけで別建ての請求項目になりません。

**逆に、複製が 1 つなら FSx for ONTAP は高いままです。** これは何を確保しても変わりません。

---

## 台数の問いから複製の問いへの置き換え

**「EC2 を N 台起動する」だけでは何も決まりません。** 決まるのは次の分岐です。

| N 台がデータをどう使うか | EBS で必要な複製数 | 判断 |
|---|---|---|
| 各台が**別の**データを持つ（Web サーバーの起動ディスクなど） | N（ただし別データなので複製ではない） | **EBS。** 共有する対象がありません |
| 各台が**同じ**データセットを読む（学習データ、参照 DB、ビルド成果物） | **N**（EBS はボリュームを共有できないため） | 複製数 = N。上の表で入れ替わりを判定 |
| 各台が同じデータから**書き込み可能な作業コピー**を持つ（開発環境、検証環境） | **N** | 同上。FlexClone が効く典型 |
| 数台が**同時に同じブロックデバイス**を書く（クラスタ） | 1 | 単価ではなく機能の話。[比較表](../../../reference/comparison/block-storage-options.md) を参照 |
| ブロックと**ファイル共有の両方**が要る | — | 単価ではなく構成の話。1 つのファイルシステムから両方出せます |

**2 行目と 3 行目が、台数が複製数に化ける場所です。** EBS は 1 ボリュームを 1 インスタンスにしか付けられないので（`io2` の Multi-Attach を除く）、**同じデータを N 台に読ませたい時点で N 個の複製が必要になります。**

---

## 単価に現れない差

**入れ替わり点の計算はストレージの請求額だけを見ています。** 以下は金額に換算していません。**換算していない理由は、金額が環境に依るからで、無視してよいという意味ではありません。**

| 単価表に出ないもの | どちらに効くか |
|---|---|
| 複製を作る時間 | FlexClone は実データをコピーしません。EBS の Snapshot からのボリューム作成はコピーを伴います |
| 重複排除・圧縮 | FSx for ONTAP はボリューム単位で有効化でき、確保する GB を減らせます。**削減率はデータ依存で、保証されません** |
| ホスト側 multipath の構築と運用 | **FSx for ONTAP 側の負担です。** EBS の単独接続には不要です |
| 2 つの制御面 | LUN と igroup は AWS の API の外側にあります（[該当ノート](block-objects-are-outside-the-aws-api.md)） |
| 起動ディスク | **FSx for ONTAP の LUN はブートできません。** EBS が必要です |
| AZ 間のデータ転送 | Multi-AZ で最適パスが別 AZ を向く構成があります（[該当ノート](multi-az-moves-a-route-not-an-address.md)） |
| HA ペア 6 組の天井 | ブロックは 6 組までです |
| 空き容量の運用 | 確保と消費の差は [確保した容量と消費した容量](../../cost/notes/provisioned-versus-consumed.md) にあります |

---

## 自環境での確認手順

**単価は改定されます。この表の数字を設計に持ち込まないでください。**

| # | 手順 | 得られるもの |
|---|---|---|
| 1 | `aws pricing get-products --service-code AmazonFSx --region us-east-1 --filters ...` で自リージョンの SSD とスループット容量の単価を引く | 床の計算に必要な 2 つの単価。**Price List API のエンドポイントは `us-east-1` と `ap-south-1` だけです** |
| 2 | 同じ手順で `AmazonEC2` の `volumeApiName=gp3` の Storage を引く | 比較対象の単価 |
| 3 | `unit` と `description` の単位が一致しているかを確認する | **`pricePerUnit` だけを見ると 1,024 倍ずれる項目があります** |
| 4 | 自分のデータセットサイズ D と複製数 C を数える | 上の式に入れる 2 つの値 |
| 5 | EBS 側で保持している Snapshot の GB を足す | EBS 側の実際の月額 |
| 6 | 重複排除・圧縮を見込むなら、**見込まない場合の額も併記する** | 削減率が出なかったときの上限 |
| 7 | 複製が 1 つなら、そこで打ち切る | **その構成では単価で逆転しません** |

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| FSx for ONTAP は EBS より安いストレージ | **GB 単価は高いです**（$0.150 対 $0.096）。さらにスループット容量が別に乗ります |
| EC2 の台数が増えれば FSx for ONTAP が有利になる | **台数ではなく、同じデータの複製数です。** 各台が別データなら台数は関係ありません |
| 最小構成の月額は容量で決まる | **床の 83% はスループット容量です** |
| 第 2 世代のほうが安い | **スループット容量の単価は第 1 世代より高いです**（Single-AZ で $2.013 対 $0.906） |
| Multi-AZ は少し高いだけ | 同構成で**約 1.6 倍**でした |
| Snapshot はどちらも別課金 | **EBS は別課金（$0.050/GB-月）、FSx for ONTAP は確保済み SSD を消費します** |
| 重複排除で確実に安くなる | **削減率はデータ依存で保証されません。** 見込まない額も併記してください |
| 単価が分かれば判断できる | **起動ディスク不可、multipath の運用、制御面が 2 つ、HA ペア 6 組の天井は金額に出ません** |
| Price List API の `pricePerUnit` をそのまま使える | **`unit` が `GiBps-mo` で説明が MiBps の項目があります。** 1,024 倍ずれます |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| FSx for ONTAP の課金項目（SSD、スループット容量、キャパシティプール、バックアップ）と単価の構造 | [AWS: Amazon FSx for NetApp ONTAP pricing](https://aws.amazon.com/fsx/netapp-ontap/pricing/) |
| EBS のボリューム種別ごとの単価と、`gp3` に含まれる 3,000 IOPS / 125 MB/s | [AWS: Amazon EBS pricing](https://aws.amazon.com/ebs/pricing/) |
| 単価の取得元 | AWS Price List API（`AmazonFSx` / `AmazonEC2`、`ap-northeast-1`、2026-09-05 取得） |
| Price List API のエンドポイントが `us-east-1` と `ap-south-1` に限られること | [AWS: Using the AWS Price List Query API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html) |
| 第 2 世代 1 HA ペアの SSD とスループット容量の下限 | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) |
| EBS ボリュームを複数インスタンスに接続できる条件 | [AWS: Attach a volume to multiple instances](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volumes-multi.html) |
| FlexClone が実データをコピーせずに書き込み可能な複製を作ること | [NetApp: FlexClone volumes](https://docs.netapp.com/us-en/ontap/volumes/create-flexclone-task.html) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [ブロックストレージの選択肢の比較](../../../reference/comparison/block-storage-options.md) — 機能面の対称なトレードオフ
- [共有ブロックが設計を変える条件](when-shared-block-changes-the-design.md) — 単価ではなく構造で変わる部分
- [ブロックストレージを 30 分で動かす手順](../quickstart.md) — 床の構成をそのまま作って確かめる
- [確保した容量と消費した容量](../../cost/notes/provisioned-versus-consumed.md) — 確保と消費の差
- [容量は 3 か所で数えられる](capacity-is-counted-in-three-places.md) — 確保した GB のうち置ける量
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)
