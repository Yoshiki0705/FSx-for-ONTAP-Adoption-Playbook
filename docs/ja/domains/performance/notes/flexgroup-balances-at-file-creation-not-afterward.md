---
title: FlexGroup は新しいファイルを作るときに分散し、置いた後は動かさない — コンスティチュエントの配置・FlexVol からの変換・上限値
lifecycle: [design, build]
domains: [performance]
evidence: documented
source: https://www.netapp.com/pdf.html?item=/media/12385-tr4571.pdf
lang: ja
---

# FlexGroup はどこで負荷を分散し、作成後に何が動かないのか？

ファイルとディレクトリを作るときに置き場所を決め、置いたファイルは動かしません。FlexVol から変換しても、既存データは再配置されません。

<!-- lang-switcher:start -->
🌐 [日本語](flexgroup-balances-at-file-creation-not-afterward.md) | [English](../../../../en/domains/performance/notes/flexgroup-balances-at-file-creation-not-afterward.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->

## このノートで学べること

- FlexGroup がファイルを 1 つのコンスティチュエントに置き、ファイルをまたいで分割しないこと
- 分散が作成時に決まり、既存ファイルへの読み書きでは置き場所が変わらないこと
- FlexVol からの変換と、コンスティチュエントの追加が既存データを動かさないこと
- TR の上限値が「強制される値」と「試験・推奨の値」に分かれていること

## このノートが答えないこと

- Amazon FSx for NetApp ONTAP での FlexGroup の性能の実測値（このリポジトリでは測定していません）
- 1 つのディレクトリに置ける名前の数（[別ノート](directory-size-is-capped-separately-from-file-count.md)が扱います）
- FlexCache の Cache としての FlexGroup の構成（[別ノート](../../data-utilization/notes/reaching-data-without-copies.md#満たすと-1-つの形に収束する-2-つの要求)が扱います）

## 前提レベル

intermediate

## 本文

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 性能](../README.md)

> **Evidence**: `documented` — ONTAP 一般の記述は NetApp の Technical Report、FSx for ONTAP についての記述は AWS のドキュメントに基づきます。このリポジトリでは測定していません。
> 主な出典は [TR-4571: NetApp ONTAP FlexGroup volumes（実装ガイド）](https://www.netapp.com/pdf.html?item=/media/12385-tr4571.pdf)（2021 年 10 月。表紙に ONTAP の版の記載はありません）と、[TR-4678: Data protection and backup — NetApp ONTAP FlexGroup volumes](https://www.netapp.com/pdf.html?item=/media/17064-tr4678.pdf)（2021 年 10 月）です。2026-10-02 に全文を確認しました。**TR の値と挙動が FSx for ONTAP で同じかは、AWS の記載を添えた箇所を除いて未確認です。**

---

### 結論

**FlexGroup は、ファイルとディレクトリを作るときに置き場所を決めます。** 1 つのファイルは 1 つのコンスティチュエント（メンバーの FlexVol）に置かれ、複数にまたがって分割されません。置いた後のファイルへの読み取りや追記では、置き場所は変わりません。

**したがって偏りを直す機会は、新しいファイルが作られるときだけです。** FlexVol から変換したボリュームも、後からコンスティチュエントを足したボリュームも、既存のデータは元の場所に残ります。AWS は FlexVol からの移行に、変換ではなく AWS DataSync で新しい FlexGroup へ移すことを推奨しています。

---

### コンスティチュエントの配置の単位

| 項目 | 記載 | 出典 |
|---|---|---|
| ファイルの置き方（ONTAP 一般） | 個々のファイルはストライプされず、1 つのメンバーボリュームに割り当てられます | TR-4571「Terminology」「FlexVol member volume layout considerations」 |
| アグリゲートの揃え方（ONTAP 一般） | 稼働中のワークロードでは、同じディスク種別・RAID グループ構成のアグリゲートだけにまたがるようにします（TR の推奨事項 4）。Table 9 の 1 ノードあたりのアグリゲート数は必須要件ではないと TR は書いています | TR-4571「Aggregate layout considerations」 |
| FSx for ONTAP の既定のコンスティチュエント数 | 既定で FlexGroup あたり HA ペアごとに 8 個。Amazon FSx API の `ConstituentsPerAggregate` は省略時 8、指定できる範囲は 1〜200 | [AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html)、[AWS API Reference: CreateAggregateConfiguration](https://docs.aws.amazon.com/fsx/latest/APIReference/API_CreateAggregateConfiguration.html) |
| FSx for ONTAP でのサイズの割り振り | 作成時の容量はコンスティチュエントに均等に割られ、サイズを変えたときも既存のコンスティチュエントに均等に配られます。データはファイル単位でコンスティチュエントに分散されます | AWS: Managing FSx for ONTAP volumes |

**FSx for ONTAP のアグリゲートは AWS が管理する構成で、TR の Table 9 をそのまま適用する対象かは未確認です。**

---

### 作成時に決まる ingest の分散

TR-4571 は次のように書いています（ONTAP 一般）。

- ONTAP は新しいファイルとディレクトリを作るときに置き場所を決めます。作成が多いほど、既存の偏りを直す機会が増えます
- 既存ファイルへの読み取りや追記が中心のワークロードでは、配置はあまり効きません。**置かれたファイルはその場所に残ります**
- 効きやすい条件は、小さいサブディレクトリが多いこと（1 ディレクトリに数十〜数百ファイル）、多数のクライアントが同時に別々の処理をすること、空き容量が十分にあること（負荷が高い間は少なくとも 10%）です
- コンスティチュエントが埋まってくると、どれか 1 つが先に満杯にならないよう、別のコンスティチュエントへの配置（remote placement）が増えます。**remote placement はメタデータ性能の低下を伴います**
- 配置の判断は ONTAP の版ごとに改善されていて、TR は最新の版を使うことを推奨しています（TR の推奨事項 1）

出典: TR-4571「Workloads and behaviors」「Ingest algorithm improvements」。**FSx for ONTAP で同じ配置判断が働くかは未確認です。**

1 つのディレクトリに大量のファイルを置くと同じコンスティチュエントに集中するという設計上の注意は、隣のリポジトリの [S3 Access Points + FlexCache / SnapMirror の設計考慮事項](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/docs/ja/s3ap-flexcache-snapmirror-considerations.md) の §1 にあります。

---

### 向くワークロードと向かないワークロードの条件

TR-4571 は両方を挙げています（ONTAP 一般）。

| 向く条件 | 向かない条件 |
|---|---|
| 新しいデータの作成（ingest）が多い | 大きいファイルを複数のノードやボリュームにまたがって分割する必要がある |
| 同時アクセスが多い | データと FlexVol の対応関係を細かく制御する必要がある |
| サブディレクトリに均等に分かれている | ファイルの改名が多い |
| — | 1 つのディレクトリに数百万ファイルがあり、頻繁に全件を走査する |
| — | シンボリックリンクが数千ある |
| — | FlexGroup で使えない機能を必要とする |

出典: TR-4571「Ideal use cases」「Nonideal cases」。TR は向く例として EDA、ソフトウェアのビルドとテスト、ログの保管、ホームディレクトリなどを挙げています。

**1 つのディレクトリに置ける名前の数そのものは、FlexGroup にしても増えません。** その上限と列挙のコストは [ディレクトリ 1 つの大きさにはファイル数と別の上限がある](directory-size-is-capped-separately-from-file-count.md) にあります。

---

### FlexVol からの変換で再配置されないデータ

| 項目 | 記載 | 出典 |
|---|---|---|
| 変換の形（ONTAP 一般） | ONTAP 9.7 以降、1 つの FlexVol をメンバー 1 つの FlexGroup にその場で変換できます。中断は 40 秒未満で、データ量やファイル数に左右されないと TR は書いています | TR-4571「FlexVol to FlexGroup volume conversion」 |
| 変換を避ける場合（ONTAP 一般） | すでに 80〜100 TB と大きく、80〜90% まで埋まっている FlexVol は、変換ではなくコピーを推奨しています。**変換後に足したメンバーに新しいデータが寄り、既存データは自動では再配置されないため**です | 同節「When not to convert a FlexVol volume」 |
| 変換を止める条件の例（ONTAP 一般） | FlexCache の Origin であること、アクティブな SnapMirror 関係にあること、クォータやストレージ効率が有効なこと（先に無効にし、変換後に戻す）など。一覧は TR の発行時点（2021 年 10 月）のものです | 同節「Things that can block a conversion」 |
| FSx for ONTAP での変換 | ONTAP CLI で変換するとコンスティチュエント 1 つの FlexGroup になります。**データを均等に分散させるには、AWS DataSync で新しい FlexGroup へ移すことを AWS は推奨しています。** CLI で変換する場合は、先に FlexVol のバックアップを削除します。変換では自動の再配置が行われません | AWS: Managing FSx for ONTAP volumes |
| FSx for ONTAP でのコンスティチュエントの追加 | 既存のコンスティチュエントがすべて最大サイズに達し容量が必要な場合に限ることを AWS は推奨しています。追加後は新しいデータが新しいコンスティチュエントへ優先して配られ、釣り合うまで偏りが残ります。**追加したコンスティチュエントは削除できません。** 既存の Snapshot は部分的なコピーになります | AWS: Managing FSx for ONTAP volumes、[AWS: Expanding FlexGroup volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/expanding-fg-volumes.html) |

**変換もコンスティチュエントの追加も、戻せない変更です。** このノートは読み取り専用の確認手順だけを載せ、変換と追加のコマンドは載せません。

---

### 上限値と値の種類

TR-4571 の表は、値ごとに「強制される値（Hard-coded/enforced）」か「試験・推奨の値（Tested/recommended）」かを区別しています。**試験・推奨の値は 10 ノードのクラスタでの試験に基づき、強制される上限ではありません**（TR の表の注記）。

| 項目（ONTAP 一般） | TR の値 | 値の種類 |
|---|---|---|
| FlexGroup のサイズ | 20 PB | 試験・推奨 |
| FlexGroup の総ファイル数 | 4,000 億（原文は 400 billion） | 試験・推奨 |
| メンバー FlexVol のサイズ | 100 TB | 強制 |
| メンバー FlexVol のファイル数 | 20 億 | 強制 |
| ファイルサイズ | 16 TB | 強制 |
| メンバー数 | 200 | 試験・推奨（TR は公式サポートを 200 と注記） |
| メンバーの最小サイズ | 100 GB | 試験・推奨 |
| SnapMirror と Snapshot のスケジュールの最短間隔 | 30 分 | 試験・推奨 |

出典: TR-4571「Maximums and minimums」の Table 5 と Table 6。

**FSx for ONTAP について AWS が記載している値は別にあります。** FlexGroup の最小は 1 コンスティチュエントあたり 100 GB、最大は 20 PiB、1 コンスティチュエントの最大は 300 TiB、1 コンスティチュエントあたりのファイル数は最大 20 億です（AWS: Managing FSx for ONTAP volumes）。**TR の値のうち AWS が記載していないものは、FSx for ONTAP では未確認です。** TR の単位（TB、PB）と AWS の単位（GB、TiB、PiB）は、それぞれの原文の表記のまま載せています。

---

### SnapMirror の宛先で揃える必要のあるメンバー数

| 項目 | 記載 | 出典 |
|---|---|---|
| メンバー数（ONTAP 一般） | 送り元と宛先でメンバー数が同じでなければなりません。宛先は送り元より大きくできますが、小さくはできません | TR-4678「FlexGroup SnapMirror guidelines」 |
| 拡張後の調整（ONTAP 一般） | ONTAP 9.3 以降、送り元を拡張すると次の SnapMirror 更新でメンバー数が調整されます | TR-4678、同節の前の「volume expand」の記述 |
| FabricPool との関係（ONTAP 一般） | FabricPool が有効なアグリゲートに FlexGroup を作るとき、メンバーを置くアグリゲートはすべて FabricPool アグリゲートである必要があります | TR-4678「Creating SnapMirror relationships when NetApp FabricPool is involved」 |
| FSx for ONTAP | 送り元と宛先の FlexGroup は同じコンスティチュエント数が必要で、そうでないと転送が失敗します。**片方を拡張したら、もう片方も手動で拡張します** | AWS: Expanding FlexGroup volumes |

**ONTAP 9.3 以降の自動調整が FSx for ONTAP でも働くかは未確認です。** AWS の記載は手動での拡張を求めています。

---

### FSx for ONTAP 側の記載と未確認の範囲

| 区分 | 内容 | 出典 |
|---|---|---|
| AWS の記載あり | 既定のコンスティチュエント数（HA ペアごとに 8、`ConstituentsPerAggregate` の省略時 8）、サイズの均等な割り振り、ファイル単位の分散 | AWS: Managing FSx for ONTAP volumes、CreateAggregateConfiguration |
| AWS の記載あり | 変換が 1 コンスティチュエントになること、再配置されないこと、AWS DataSync の推奨、変換前のバックアップ削除 | AWS: Managing FSx for ONTAP volumes |
| AWS の記載あり | 追加したコンスティチュエントを削除できないこと、SnapMirror の両側でコンスティチュエント数を揃えること | AWS: Expanding FlexGroup volumes |
| AWS の記載あり | 最小 100 GB / コンスティチュエント、最大 20 PiB、コンスティチュエントあたり最大 300 TiB と 20 億ファイル | AWS: Managing FSx for ONTAP volumes |
| 未確認 | TR の配置判断（remote placement の頻度、10% の空き容量の目安）、変換時の中断時間、変換を止める条件の現行の一覧、TR の試験・推奨の値、SnapMirror の自動調整 | AWS 側の記載を見つけていません |

探索の範囲（2026-10-02）: 上の 3 つの AWS ページと Amazon FSx API リファレンスを読みました。

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| FlexGroup は大きいファイルを全コンスティチュエントに分割する | 分割しません。1 つのファイルは 1 つのコンスティチュエントに置かれます（TR-4571） |
| FlexGroup は置いた後も負荷に応じてファイルを動かす | 動かしません。置き場所は作成時に決まり、既存ファイルは残ります（TR-4571） |
| FlexVol から変換すれば均等な FlexGroup になる | 1 コンスティチュエントのまま残ります。AWS は均等に分散させるために AWS DataSync での移行を推奨しています |
| コンスティチュエントを足せばすぐに均等になる | 新しいデータが新しいコンスティチュエントに寄り、釣り合うまで偏りが残ります。足したものは削除できません（AWS） |
| TR の上限値はすべて製品の上限 | 試験・推奨の値と強制される値が分かれています。FSx for ONTAP の値は AWS の記載を見ます |
| FlexGroup にすれば 1 ディレクトリの上限も増える | 増えません（[別ノート](directory-size-is-capped-separately-from-file-count.md#flexgroup-でも増えない-1-ディレクトリの上限)） |

---

### 参照した一次情報

| 論点 | 出典 |
|---|---|
| ファイルが 1 つのメンバーに置かれること、アグリゲートの揃え方、作成時の配置、remote placement、空き容量の目安、向く条件と向かない条件、上限値と値の種類、FlexVol からの変換と止める条件（ONTAP 一般） | [TR-4571: NetApp ONTAP FlexGroup volumes（実装ガイド）](https://www.netapp.com/pdf.html?item=/media/12385-tr4571.pdf)（2021 年 10 月）の「Terminology」「Aggregate layout considerations」「Workloads and behaviors」「Ingest algorithm improvements」「Ideal use cases」「Nonideal cases」「Maximums and minimums」「FlexVol to FlexGroup volume conversion」（2026-10-02 に確認） |
| SnapMirror でのメンバー数、9.3 以降の調整、FabricPool アグリゲートの条件（ONTAP 一般） | [TR-4678: Data protection and backup — NetApp ONTAP FlexGroup volumes](https://www.netapp.com/pdf.html?item=/media/17064-tr4678.pdf)（2021 年 10 月）の「FlexGroup SnapMirror guidelines」「Creating SnapMirror relationships when NetApp FabricPool is involved」 |
| TR の索引 | [NetApp: ONTAP technical reports — NAS containers](https://docs.netapp.com/us-en/ontap-technical-reports/nas-containers.html) |
| FSx for ONTAP の既定のコンスティチュエント数、サイズの割り振り、変換と AWS DataSync の推奨、サイズとファイル数の上限 | [AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html)（2026-10-02 に確認） |
| `ConstituentsPerAggregate` の既定値と範囲 | [AWS API Reference: CreateAggregateConfiguration](https://docs.aws.amazon.com/fsx/latest/APIReference/API_CreateAggregateConfiguration.html) |
| コンスティチュエントの追加、削除できないこと、SnapMirror の両側の数 | [AWS: Expanding FlexGroup volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/expanding-fg-volumes.html) |

---

### 関連ドキュメント

- [Domain — 性能](../README.md) — このモジュールのハブ
- [ディレクトリ 1 つの大きさにはファイル数と別の上限がある](directory-size-is-capped-separately-from-file-count.md) — 1 ディレクトリの上限と FlexGroup での remote entry
- [スループットは 1 つの設定値では決まらない](where-throughput-is-determined-and-shared.md) — FlexVol と FlexGroup の配置と共有の単位
- [コピーを増やさずにデータへ届けるには](../../data-utilization/notes/reaching-data-without-copies.md#作成経路で成否が変わること) — FlexCache の Cache としての FlexGroup と、作成経路で成否が変わること
- [階層化ポリシーの比較](../../../reference/comparison/tiering-policies.md) — FlexGroup の階層化ポリシー
- [知見の分類ポリシー](../../../evidence-policy.md)

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 性能](../README.md)

## 自環境での確認手順

すべて読み取り専用です。変換とコンスティチュエントの追加の手順は含みません。

| # | 手順 | 確認できること |
|---|---|---|
| 1 | Amazon FSx API でボリュームのスタイルと容量を読む | FlexVol か FlexGroup か |
| 2 | ONTAP CLI でコンスティチュエントごとのアグリゲート・サイズ・使用量を読む | コンスティチュエントの数と偏り |
| 3 | 2 をデータの書き込み後に再度読み、使用量の伸び方を比べる | 新しいデータがどのコンスティチュエントに寄っているか |

```bash
# Amazon FSx API: volume style and size (read-only)
aws fsx describe-volumes --volume-ids <volume-id>
```

```text
::> volume show -vserver <svm> -volume <volume>* -is-constituent true -fields aggregate,size,used
```

### 期待結果

```text
describe-volumes の OntapConfiguration.VolumeStyle が FLEXGROUP なら FlexGroup。
volume show はコンスティチュエントごとに 1 行を返し、aggregate・size・used を表示する。
FlexVol から変換したボリュームは 1 行だけになる。used が特定の行に偏っていれば、
既存データがその場所に残っている（作成後に再配置されない）ことの観察になる
```

## Read next

[ディレクトリ 1 つに置けるファイル数はどこで決まるのか？](directory-size-is-capped-separately-from-file-count.md)
