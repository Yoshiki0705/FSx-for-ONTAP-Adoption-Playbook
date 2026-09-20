---
title: ボリュームの操作時間メトリクスから p99 は出せない — ベンチマークはクレジット残高込みで設計する
lifecycle: [optimize, operate]
domains: [performance, cost]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-metrics.html
lang: ja
---

# Amazon FSx for NetApp ONTAP の CloudWatch メトリクスから p99 を読めるか？

ボリュームの操作時間と回数から得られるのは平均で、p99 は別の分布計測が必要です。

<!-- lang-switcher:start -->
🌐 [日本語](what-you-cannot-read-from-cloudwatch.md) | [English](../../../../en/domains/performance/notes/what-you-cannot-read-from-cloudwatch.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->

## このノートで学べること

- operation-time と operation-count の Sum から得られるのが期間平均であり、p99 ではないこと。
- クレジット残高、キャッシュ、共有帯域、統計と次元をベンチマーク条件に含める理由。

## このノートが答えないこと

- CloudWatch 全体でパーセンタイル統計を利用できるかどうか。
- 自環境の p99 または持続スループットの実測値。

## 前提レベル

intermediate

## 本文

<a id="ボリュームの操作時間メトリクスから-p99-は出せない"></a>
<a id="p99-は-cloudwatch-のメトリクスからは出せない"></a>

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 性能](../README.md)

---

### 結論

**FSx for ONTAP のボリューム操作レイテンシは、CloudWatch の operation-time/count メトリクスペアからは平均しか得られません。CloudWatch 全体にパーセンタイルがないという意味ではありません。**

`DataReadOperationTime` / `DataReadOperations`、`DataWriteOperationTime` / `DataWriteOperations`、`MetadataOperationTime` / `MetadataOperations` は、時間と回数の合計で、有効な統計はどちらも `Sum` です。

各ペアの **合計時間 ÷ 合計回数** で求められるのは、その期間の平均です。これらのペアにはリクエスト分布がなく、テール（p99）は含まれません。

**p99 が必要なら、クライアント計測やリクエスト単位の別テレメトリで分布を取得します。** 一方、FSx for ONTAP のファイルシステム・第 2 世代メトリクスには `Average` / `Minimum` / `Maximum` を利用できる系列があり、第 2 世代では `FileServer` や `Aggregate` ごとのデータポイントもあります。飽和監視には、目的に合う統計と次元を選びます。

そしてもう 1 つ。**ベンチマークはバースト用のクレジット残高に影響されます。** ファイルシステムはベースラインを下回っているときにクレジットを蓄積し、それを使ってベースラインを超える速度を出します。**同じ試験を残高が減った状態で再実行すると、違う数値が出ます。**

> **Evidence**: `documented` — メトリクスの有効統計、性能特性の決まり方、クレジット機構は AWS 公式ドキュメントの記載に基づきます。
> **数値の実測は含みません。** 測る手順は「[自分の環境で確かめる](#自環境での確認手順)」にあります。

---

### 性能を決めている 3 つの要素

クライアントは ENI 経由でファイルサーバーにアクセスします。**各ファイルサーバーには高速なインメモリキャッシュと NVMe キャッシュがあります。** その背後に SSD ディスクがあります。

| 性能特性 | 何が決めるか |
|---|---|
| ネットワーク I/O 性能（クライアント ↔ ファイルサーバー、合計） | **スループット容量のみ** |
| **インメモリ / NVMe キャッシュのサイズ** | **スループット容量のみ** |
| ディスク I/O 性能（ファイルサーバー ↔ ディスク） | **スループット容量と SSD IOPS の組み合わせ** |

**キャッシュサイズを直接指定する設定はありません。** キャッシュサイズはスループット容量で決まります。したがって「キャッシュを増やしたい」は「スループット容量を上げる」と同義です。

上限そのものが世代・構成・リージョンで変わる点は [スループットは 1 つの設定値では決まらない](where-throughput-is-determined-and-shared.md) にあります。

---

### キャッシュが効く条件

**キャッシュに載るのはアクティブなワーキングセットです。** したがって条件は 1 つに集約されます。

**ワーキングセットのサイズが、スループット容量で決まるキャッシュサイズに収まるかどうか。**

| ワークロード | キャッシュの効き |
|---|---|
| 同じデータに繰り返しアクセスし、その総量が小さい | 効きます |
| アクセス範囲が広く、毎回違うデータを読む | 効きません。ワーキングセットが収まりません |
| ワーキングセットがキャッシュより大きい | **スループット容量を上げるか、範囲を絞る設計が必要です** |

別ファイルシステムやリモート拠点への読み取り加速は FlexCache の領域で、条件が違います。[FlexCache が効く条件](../../data-utilization/notes/reaching-data-without-copies.md#flexcache-が効く条件) にあります。

なお **HA ペアを追加すると、新しいノードでは NVMe キャッシュが既定で有効になります。スループット重視のワークロードでは無効化が推奨されています。** 制約は [デプロイタイプは一度しか決められない](../../../playbooks/02-design/notes/deployment-type-is-decided-once.md#ha-ペアを足すときに起きること) にあります。

---

### プロトコル間での帯域の分け合い方

**プロトコルごとの割り当てはありません。**

ネットワーク I/O 性能は「クライアントとファイルサーバー間の**合計**」として定義されます。そして `NetworkThroughputUtilization` は **背景タスク（SnapMirror、階層化、バックアップ）を含む全トラフィック**を対象にします。

| 共有される単位 | 内容 |
|---|---|
| ネットワーク帯域 | **HA ペア 1 組分**。NFS・SMB・iSCSI・S3 Access Point が同じ予算を使います |
| 背景タスク | 同じ予算から使います |
| 明示的な優先度 | **クライアントトラフィックが背景タスクより優先される**、という 1 点のみです |

**つまり「SMB のせいで NFS が遅い」は起こりえます。** そして分離する設定は用意されていません。分離が必要なら、**別の HA ペアへボリュームを分けるか、別のファイルシステムにする**という設計判断になります。共有の単位は [共有される単位は HA ペア](where-throughput-is-determined-and-shared.md#共有される単位は-ha-ペア) にあります。

---

### ベンチマークを壊すバーストとクレジット

**ファイルベースのワークロードはスパイク型です。** 短時間の高い I/O と、その間の待機で構成されます。

これに合わせて、FSx for ONTAP は **24 時間 365 日維持できるベースライン速度に加えて、一定時間だけ高い速度にバーストできます。** ネットワーク I/O とディスク I/O の両方が対象です。

**バーストはネットワーク I/O クレジット機構で管理されます。** 平均利用率に基づいて配分され、**ファイルシステムはスループットと IOPS がベースラインを下回っているときにクレジットを蓄積します。**

#### ベンチマークへの影響

| 状況 | 測れる数値 |
|---|---|
| クレジットが十分に貯まった状態で短時間の試験を回す | **バースト性能。** 持続性能ではありません |
| クレジットを使い切った後に同じ試験を回す | ベースライン性能 |
| 記録に残高を含めない | **再現できません。** 同じ手順で違う数値が出ます |

**残高は `FileServerDiskThroughputBalance` と `FileServerDiskIopsBalance` で見られます。** この 2 つは他のメトリクスと違い **5 分間隔**で送信されます。粒度の一覧は [監視の粒度と保持](../../../playbooks/05-operate/notes/monitoring-fails-on-averages.md#監視の粒度と保持) にあります。

#### 段差の大きさと、落ちるまでの時間

**上の表は機構で、大きさは書いていませんでした。** 実測が [引用元](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/throughput-capacity-burst-and-baseline.md) にあります（第二世代 `SINGLE_AZ_2`、指定値 1,536 MBps、1 MiB 逐次読み、1,800 GiB のファイル）。

| 観測 | 値 |
|---|---|
| 段差 | **2.0 倍**（2,882 MB/s → 1,439 MB/s） |
| 落ちるまでの時間 | **満タンから約 27 分** |
| 満タンへの回復 | 無負荷で約 30 分 |
| 短い窓（約 2 分）の再現性 | 2 回で 0.16% 差。**再現しているのはバースト中の値** |

**指定値はどちらの値でもありません。** 1,536 の指定で 2,882 も 1,439 も出ます。**指定値を読み取りの上限として使えません。**

**低下はなだらかではなく階段です。** 段差は 10 秒の 1 区間で完了しました。**つまり試験を少し延ばしても数値は動かず、境界を越えた瞬間に別の値になります。** 段階的に延ばして「落ちる点」を探す上の手順は、この形を前提にしてください。

**5 分の測定でサイジングすると、ずれる向きは常に過大評価です。** バーストから始まるためで、採るべきは枠が尽きたあとの値です。どちらを採るかはワークロードの形で決まります。

| ワークロードの形 | 見る値 |
|---|---|
| 30 分未満の処理が、間に 30 分以上空いて走る | バースト側 |
| 連続、または間隔が 30 分未満 | ベースライン側 |
| 判断できない | **ベースライン側**（過大評価しない側） |

> **持続時間の 27 分は 1 回の観測です。** 消費と回復の傾きはそれぞれ 4 点以上で線形ですが、**持続時間そのものは 2 回測られていません。** 再現性は傾きについて言えることで、持続時間については言えません。

#### 枠が無い構成における残枠メトリクスの不在

**指定値を上げるとバースト枠そのものが無くなります。** 公開仕様のディスクバースト列は 3,072 以上で「—」になり、引用元は 6,144 で**30 分間減衰しないこと**を実測しています（1,536 で見えた段差が無い）。

**そしてこれは CloudWatch の読み方の問題になります。**

| 構成 | `FileServerDiskThroughputBalance` |
|---|---|
| 1,536（枠あり） | 99% → 0% を 27 分で |
| **6,144（枠なし）** | **データポイントが 1 つも公開されない** |

**「0 を返す」と「レコードを返さない」を読み分ける必要があります。** 残枠 0 と枠の不在は別の状態で、**枠の不在を 0 と読むと「常に枯渇している」というダッシュボードになります。** NVMe キャッシュのレコードも同じ形です。

**交換条件として書いてください。** 上位の指定値は値が安定する代わりに、**短時間の山を吸収する余地が消えます。** 引用元は 1,536 のバースト（3,125）が 3,072 のベースライン（3,072）とほぼ同じ値であることを指摘しています。**境界そのもの（3,072）は未測定です。**

---

### 再現できるベンチマークの条件

**「同じ手順」では足りません。同じ状態から始める必要があります。**

| 記録する項目 | 理由 |
|---|---|
| **クレジット残高（試験開始前）** | **バーストを測ったのか持続を測ったのかが決まります** |
| 試験の継続時間 | 短い試験はバーストを測ります |
| リージョン・世代・デプロイタイプ | 上限そのものが変わります |
| スループット容量と SSD IOPS の設定値 | 3 つの性能特性すべてに効きます |
| HA ペア数とボリュームスタイル（FlexVol / FlexGroup） | ファイルシステム全体の上限と、FlexVol が配置される 1 HA ペアの aggregate を区別します |
| 階層化ポリシーと cooling period | 読み取り元が SSD か容量プールかが変わります |
| 同時に走っていた背景タスク | 同じ帯域を使います |
| クライアント側またはリクエスト単位の測定値（**テール含む**） | ボリュームの operation-time/count ペアは平均だけなので、分布を別に取得します |
| 統計値と次元（Average / Minimum / Maximum、`FileServer` / `Aggregate`） | 平均と集約は飽和を隠すため、目的に合わせて選びます |

**最後の 2 行がこのリポジトリで繰り返し出てくる論点です。** 理由は [監視は平均値で失敗する](../../../playbooks/05-operate/notes/monitoring-fails-on-averages.md) にあります。

---

### 測定フロー

```mermaid
graph TD
    A[性能を評価したい] --> Q{何を知りたいか}

    Q -->|平均レイテンシ| AVG["DataReadOperationTime の Sum を<br/>DataReadOperations の Sum で割る"]
    Q -->|テール p99| TAIL["ボリュームの operation-time/count ペアにはない<br/>リクエスト単位の分布を別に測る"]
    Q -->|持続性能| SUS[クレジット残高を先に確認]
    Q -->|バースト性能| BURST[残高が十分な状態で短時間]

    SUS --> DEPLETE["残高を使い切ってから測る<br/>または 長時間流す"]

    A --> SHARE{プロトコル間の<br/>干渉を疑う}
    SHARE --> NOALLOC["割り当ては存在しない<br/>HA ペア単位で共有"]
    NOALLOC --> SEP["分離するなら<br/>別 HA ペアか別ファイルシステム"]

    A --> CACHE{キャッシュを効かせたい}
    CACHE --> WS{ワーキングセットが<br/>キャッシュに収まるか}
    WS -->|収まる| OK[効く]
    WS -->|収まらない| UP["スループット容量を上げる<br/>キャッシュは直接指定できない"]
```

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| CloudWatch で FSx for ONTAP の p99 が一切見られない | **ボリュームの read/write/metadata operation-time/count ペアからは平均だけを算出できます。** CloudWatch 全体や他のメトリクスの統計まで否定するものではありません |
| レイテンシのメトリクスがある | 時間の**合計**と回数の**合計**があり、割って平均を出します |
| ベンチマークは手順が同じなら再現する | **クレジット残高が違えば数値が変わります** |
| 短時間の試験で持続性能が分かる | 短い試験はバーストを測ります。**実測では 2.0 倍ずれ、ずれる向きは常に過大評価です** |
| 指定したスループット容量が読み取りの上限になる | **なりません。** 1,536 の指定で 2,882 も 1,439 も観測されています。**どちらも指定値ではありません** |
| 残枠のメトリクスが 0 なら枯渇している | **枠が無い構成ではレコードが 1 件も出ません。** 0 と不在を読み分けてください |
| キャッシュサイズを設定できる | **スループット容量で決まります。** 直接指定はできません |
| キャッシュはどのワークロードでも効く | ワーキングセットが収まる場合に効きます |
| プロトコルごとに帯域を割り当てられる | **割り当ては存在しません。** HA ペア単位で共有します |
| SMB と NFS は互いに影響しない | 同じ予算を使います。干渉は起こりえます |
| 背景タスクは別の帯域を使う | 同じ帯域です。ただしクライアントトラフィックが優先されます |
| ディスク性能は SSD IOPS だけで決まる | **スループット容量と SSD IOPS の組み合わせ**です |

---

### 参照した一次情報

| 論点 | 出典 |
|---|---|
| `DataReadOperationTime` / `DataReadOperations`、`DataWriteOperationTime` / `DataWriteOperations`、`MetadataOperationTime` / `MetadataOperations` が合計値で、有効統計が `Sum` であること | [AWS: Volume metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-metrics.html) |
| ファイルシステムメトリクスの統計とデータポイントの集約方法 | [AWS: File system metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-system-metrics.html) |
| 第 2 世代メトリクスの有効統計と `FileServer` / `Aggregate` 次元 | [AWS: Second-generation file system metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/so-file-system-metrics.html) |
| 各ファイルサーバーにインメモリキャッシュと NVMe キャッシュがあること、3 つの性能特性、ネットワーク I/O とキャッシュサイズがスループット容量のみで決まりディスク I/O はスループット容量と SSD IOPS の組み合わせで決まること、ファイルベースのワークロードがスパイク型であること、バーストとネットワーク I/O クレジット機構、ベースラインを下回るとクレジットが蓄積されること | [AWS: Amazon FSx for NetApp ONTAP performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html) |
| `NetworkThroughputUtilization` が HA ペア 1 組分に対する比率で、背景タスクを含む全トラフィックを対象にすること | [AWS: Second-generation file system metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/so-file-system-metrics.html) |
| `FileServerDiskThroughputBalance` と `FileServerDiskIopsBalance` が 5 分間隔で送信されること | [AWS: Monitoring with Amazon CloudWatch](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-cloudwatch.html) |
| クライアントトラフィックが背景タスクより優先されること | [AWS: Migrating to FSx for ONTAP using NetApp SnapMirror](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/migrating-fsx-ontap-snapmirror.html) |
| HA ペア追加時に NVMe キャッシュが既定で有効になり、スループット重視では無効化が推奨されること | [AWS: Adding high-availability (HA) pairs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/adding-HA-pairs.html) |
| **段差の大きさ（2.0 倍）、落ちるまでの約 27 分、回復の傾き、階段状の低下、6,144 で残枠メトリクスが不在になること**（**実測 / ドキュメント外**。測定条件と未測定の範囲は引用先） | [S3-Burst-on-ONTAP-Files: 指定値・バースト・ベースラインの実測](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/throughput-capacity-burst-and-baseline.md) |

---

### 関連ドキュメント

- [Domain — 性能](../README.md) — このモジュールのハブ
- [スループットは 1 つの設定値では決まらない](where-throughput-is-determined-and-shared.md) — 上限の決まり方と HA ペア単位の共有
- [監視は平均値で失敗する](../../../playbooks/05-operate/notes/monitoring-fails-on-averages.md) — 統計値の選択と粒度
- [FlexCache が効く条件](../../data-utilization/notes/reaching-data-without-copies.md#flexcache-が効く条件) — 別ファイルシステム・リモート拠点への読み取り加速
- [デプロイタイプは一度しか決められない](../../../playbooks/02-design/notes/deployment-type-is-decided-once.md) — HA ペアと NVMe キャッシュの既定
- [階層化の既定値は作成方法で違う](../../../playbooks/06-optimize/notes/tiering-defaults-differ-by-creation-method.md) — 読み取り元が変わる条件
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 性能](../README.md)

---

## 自環境での確認手順

**最初に確かめるのは、いま見ている数値が平均なのかテールなのかです。**

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `DataReadOperationTime` ÷ `DataReadOperations` で平均レイテンシを出す | **これが平均であること。** テールは含まれません |
| 2 | クライアント側またはリクエスト単位の別テレメトリでレイテンシ分布を測り、p99 を出す | **ボリュームの operation-time/count ペア平均との差。** テールの実測です |
| 3 | 試験前に `FileServerDiskThroughputBalance` と `FileServerDiskIopsBalance` を記録する | バーストを測るのか持続を測るのか |
| 4 | 同じ試験を残高が減った状態で再実行し、数値を比べる | **クレジットの影響量。** 再現性の根拠になります |
| 5 | 試験を段階的に長くし、数値が落ちる点を探す | ベースラインに落ちるまでの時間 |
| 6 | ワーキングセットのサイズを推定し、スループット容量を変えて比べる | キャッシュに収まっているか |
| 7 | 片方のプロトコルに負荷をかけ、他方のレイテンシを観測する | **プロトコル間の干渉の実測。** 分離が必要かの判断 |
| 8 | 背景タスクが走っている時間帯と走っていない時間帯で比べる | 背景タスクの影響量 |

手順 3 と 4 を飛ばしたベンチマークは、**同じ手順を踏んでも再現しません。** ここが最も見落とされます。

手順 2 は「ストレージが遅いのか、経路やクライアントが遅いのか」の切り分けにもなります。

次のローカル計算は、同一期間・同一ボリュームの operation-time Sum と operation-count Sum から期間平均だけを算出します。

```bash
python3 -c \
  'import sys; print(float(sys.argv[1]) / float(sys.argv[2]))' \
  <operation-time-sum> <operation-count-sum>
```

### 期待結果

```text
<入力メトリクスと同じ時間単位の期間平均>
```

この計算だけでは、入力メトリクスの正しさ、リクエスト分布、p99、クレジット残高、持続性能は確認できません。表の残りの手順を別に実施してください。

---

## Read next

[Domain — 性能](../README.md)
