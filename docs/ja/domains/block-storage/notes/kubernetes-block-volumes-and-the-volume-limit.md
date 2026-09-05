---
title: Kubernetes のブロック PV はボリューム数の上限に当たる — ドライバの選択がその天井を決める
lifecycle: [design, build, operate]
domains: [block-storage, data-utilization, performance]
evidence: documented
source: https://docs.netapp.com/us-en/trident/trident-use/ontap-san.html
lang: ja
---

# Kubernetes のブロック PV はボリューム数の上限に当たる

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

## 結論

**FSx for ONTAP をブロックの永続ボリュームとして使うと、詰まるのは容量ではなくボリューム数です。**

Trident の `ontap-san` ドライバは **PV 1 つごとに FlexVol を 1 つ作り、その中に LUN を 1 つ置きます。** つまり **PV の数がボリューム数の上限に直接当たります。** FSx for ONTAP のボリューム数の上限は、第 2 世代 1 HA ペアで **500**、2 組以上で **1,000**、第 1 世代で **500** です。

**この天井を外すためのドライバが `ontap-san-economy` です。** 共有した FlexVol の中に多数の LUN を詰めるため、PV 数がボリューム数に縛られません。**NetApp は、想定 PV 数が ONTAP のボリューム上限を超える場合にのみこちらを使うよう記載しています。**

**選択は先にしてください。** ドライバは StorageClass に紐づくため、後から変えると新しい StorageClass での再作成になります。

> **区分**: `documented` — ドライバの動作は NetApp のドキュメント、ボリューム上限は AWS のドキュメントの記載に基づきます（2026-09-05 に確認）。
> **PV 数の実測は含めません。** 上限に到達させる検証は行っていません。
> 自環境での確認手順は [自環境での確認手順](#自環境での確認手順) にあります。

---

## 2 つのドライバの違い

| 観点 | `ontap-san` | `ontap-san-economy` |
|---|---|---|
| **PV 1 つが消費するもの** | **FlexVol 1 つ + その中の LUN 1 つ** | 共有 FlexVol の中の **LUN 1 つ** |
| **PV 数の上限を決めるもの** | **ボリューム数の上限**（500 / 1,000） | 共有 FlexVol の数と、そこに入る LUN の数 |
| **ボリューム単位の操作の効き方** | **PV ごとに独立**。Snapshot・SnapMirror・QoS を PV 単位で掛けられます | **共有 FlexVol 単位**。1 つの PV だけを対象にできません |
| **NetApp の推奨** | 既定の選択 | **想定 PV 数がボリューム上限を超える場合のみ** |
| **NVMe/TCP** | `ontap-san` 側で対応。**REST 経由のみ**（ONTAPI / ZAPI では非対応） | 記載なし |

**トレードオフは対称です。** `ontap-san` は PV ごとの独立性を得る代わりにボリューム上限を天井として受け入れます。`ontap-san-economy` は PV 数の自由度を得る代わりに、ボリューム単位の操作を PV 単位で掛けられなくなります。

**「多いほうを選べばよい」ではありません。** Snapshot や SnapMirror を PV 単位で運用する設計なら、`ontap-san-economy` はその運用を成立させません。

---

## ボリューム数の上限が効いてくる位置

| 構成 | ボリューム数の上限 | `ontap-san` での PV 数の目安 |
|---|---|---|
| 第 1 世代 | 500 | 500 から、SVM のルートボリュームなどを引いた数 |
| 第 2 世代・1 HA ペア | 500 | 同上 |
| 第 2 世代・2 組以上 | **1,000（全 HA ペア合計）** | HA ペアを増やしても 1,000 が上限です |

**HA ペアを増やしてもボリューム数の上限は 1,000 で止まります。** そして **7 組目からブロックプロトコルが使えなくなる**ため、ブロック PV を使う構成では 6 組が上限です。詳細は [デプロイタイプは一度しか決められない](../../../playbooks/02-design/notes/deployment-type-is-decided-once.md) にあります。

**FlexGroup の構成ボリュームもこの数に含まれます。** ファイル用の FlexGroup を同じファイルシステムに置いている場合、ブロック PV に使える枠はその分減ります。

---

## アクセスモードの読み方

Trident の SAN ドライバは **RWO / ROX / RWX / RWOP** に対応しています。**ただし RWX をブロックで使う意味は、ファイル共有の RWX とは違います。**

| モード | ブロックでの意味 |
|---|---|
| RWO | 1 ノードから読み書き。**ブロックの標準的な使い方です** |
| RWOP | 1 Pod から読み書き |
| ROX | 複数ノードから読み取り専用 |
| RWX | **複数ノードから raw block device として同時に見えます。** ファイルシステムを載せるなら、調停はクラスタファイルシステム側の責任です |

**RWX を選んでも、2 つの Pod が同じブロックに同時に書くことを止める仕組みは付いてきません。** ここは Amazon EBS Multi-Attach と同じ性質です。[共有ブロックが設計を変える条件](when-shared-block-changes-the-design.md) を参照してください。

---

## iSCSI の LIF を指定しないこと

**`ontap-san` では `dataLIF` を指定しません。** Trident は **Selective LUN Map を使って multipath セッションに必要な iSCSI LIF を自分で見つけます。** 明示的に `dataLIF` を書くと警告が出ます。

**これは Selective LUN Map が新しい LUN マップで既定で有効であることの帰結です。** SLM は LUN を所有するノードとその HA パートナー上のパスに限ってアクセスを許すため、Trident はそこから使えるパスを導出できます。SLM 自体の挙動は [LUN の並べ方が決めているのは復旧の粒度](lun-layout-decides-recovery-granularity.md) にあります。

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 想定する PV の最大数を見積もる | `ontap-san` で足りるか、`ontap-san-economy` が必要か |
| 2 | `volume show -vserver <svm>` でボリューム数を数え、ファイル用途で使っている数を差し引く | ブロック PV に使える実際の枠 |
| 3 | `aws fsx describe-file-systems --query 'FileSystems[].OntapConfiguration.[DeploymentType,HAPairs]'` | ボリューム上限が 500 か 1,000 か |
| 4 | Snapshot や SnapMirror を PV 単位で運用する要件があるかを確認する | **要件があるなら `ontap-san-economy` は選べません** |
| 5 | StorageClass を 2 つ作り、片方を `ontap-san`、片方を `ontap-san-economy` にして PVC を 1 つずつ作る | ボリュームが増えるかどうかを `volume show` の差分で確認する |
| 6 | NVMe/TCP を使う場合、backend の設定が REST 経由になっているかを確認する | **ONTAPI / ZAPI では NVMe/TCP が使えません** |
| 7 | HA ペアを 7 組以上に増やす計画があるかを確認する | **計画があるならブロック PV は使えません** |

手順 5 は**検証環境で行ってください。** 作成した PV を消し忘れると、ボリューム数の枠を消費し続けます。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| PV の数はストレージ容量で決まる | **`ontap-san` ではボリューム数の上限で決まります。** 容量が余っていても PV を作れなくなります |
| HA ペアを増やせば PV をいくらでも増やせる | **全 HA ペア合計で 1,000 が上限**で、しかも 7 組目からブロックが使えなくなります |
| `ontap-san-economy` のほうが常に良い | ボリューム単位の Snapshot・SnapMirror・QoS を **PV 単位で掛けられなくなります** |
| ドライバは後から変えられる | StorageClass に紐づくため、**新しい StorageClass での再作成**になります |
| RWX にすれば複数 Pod から安全に書ける | **raw block device が複数ノードに見えるだけです。** 調停はクラスタファイルシステムの責任です |
| iSCSI の LIF を `dataLIF` に書いたほうが確実 | **書くと警告が出ます。** Trident は Selective LUN Map からパスを導出します |
| NVMe/TCP は Trident のどの設定でも使える | **REST 経由の backend のみです。** ONTAPI / ZAPI では使えません |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| `ontap-san` が PV ごとに FlexVol + LUN を作ること、`ontap-san-economy` が共有 FlexVol に LUN を詰めること、後者はボリューム上限を超える見込みのときのみ使うこと、対応アクセスモード、NVMe/TCP が REST 経由のみであること | [NetApp: ONTAP SAN driver overview](https://docs.netapp.com/us-en/trident/trident-use/ontap-san.html) |
| `ontap-san` で `dataLIF` を指定せず、Trident が Selective LUN Map から iSCSI LIF を見つけること | [NetApp: FSx for ONTAP configuration options and examples](https://docs.netapp.com/us-en/trident/trident-use/trident-fsx-examples.html) |
| Trident と FSx for ONTAP の連携でブロックとファイルの永続ボリュームを供給できること | [NetApp: Use Trident with Amazon FSx for NetApp ONTAP](https://docs.netapp.com/us-en/trident/trident-use/trident-fsx.html) |
| ボリューム数の上限が第 2 世代 1 HA ペア 500、2 組以上で合計 1,000、第 1 世代 500 であること。FlexGroup の構成ボリュームが数に含まれること | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) |
| ボリュームが LUN の入れ物であること | [AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |
| 7 組目からブロックプロトコルが使えなくなること | [AWS: Adding HA pairs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/adding-HA-pairs.html) |
| Selective LUN Map が新しい LUN マップで既定で有効であること | [NetApp: Selective LUN Map](https://docs.netapp.com/us-en/ontap/san-admin/selective-lun-map-concept.html) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [共有ブロックが設計を変える条件](when-shared-block-changes-the-design.md) — RWX と書き込み調停の責任
- [LUN の並べ方が決めているのは復旧の粒度](lun-layout-decides-recovery-granularity.md) — Selective LUN Map の挙動
- [LUN と igroup は AWS の API の外側にある](block-objects-are-outside-the-aws-api.md) — Trident が使う制御面
- [デプロイタイプは一度しか決められない](../../../playbooks/02-design/notes/deployment-type-is-decided-once.md) — HA ペア 6 組の天井
- [上限値・クォータ](../../../reference/limits/) — 出典と検証日付きの上限値
- [ブロックストレージ横断リソースマップ](../../../reference/block-storage-resource-map.md) — Trident 関連の公開 IaC
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)
