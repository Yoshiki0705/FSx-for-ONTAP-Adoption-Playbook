---
title: NVMe/TCP は AWS 側の面から一貫して抜けている — セキュリティグループもプロトコル列挙も API も
lifecycle: [design, build, operate]
domains: [block-storage, security-governance]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
lang: ja
---

# NVMe/TCP は AWS 側の面から一貫して抜けている

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

## 結論

**FSx for ONTAP のセキュリティグループ要件表に、NVMe/TCP のポートは載っていません。** iSCSI の TCP 3260 は載っています。したがって**要件表だけを見てセキュリティグループを設計すると、NVMe/TCP は接続できません。**

**開けるべきは 2 つです。データが TCP 4420、ディスカバリが TCP 8009。** これは自環境で実測しました。ただし**「この 2 つで網羅されている」は当方では確認していません**（否定対照を取っていないため。[検証環境](#検証環境)を参照）。

**抜けているのは表だけではありません。** 同じページの本文と、AWS API のレスポンスにも現れません。

| AWS 側の面 | iSCSI | NVMe/TCP |
|---|---|---|
| セキュリティグループ要件表のポート | TCP 3260 として記載 | **記載なし** |
| 同ページ本文のプロトコル列挙 | 記載あり（NFS / SMB / iSCSI） | **列挙に現れない** |
| `describe-storage-virtual-machines` のエンドポイント | `Iscsi` が返る | **`Nvme` は `null`。到達できる状態でも返らない** |

> **区分**: `verified`（検証日 2026-09-05、`ap-northeast-1`、`MULTI_AZ_2` 第 2 世代 1 HA ペア、ONTAP 9.18.1P5、Amazon Linux 2023 kernel 6.18.44）— ポート番号と `Nvme: null`。**ドキュメントの記載の有無は 2026-09-12 に該当ページを通読して確認しました。**

---

## 記載を探した範囲と結果

**2026-09-12 時点で、次の 3 ページを通読しました。**

| ページ | 4420 の扱い | 8009 の扱い |
|---|---|---|
| [File System Access Control with Amazon VPC](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limit-access-security-groups.html)（要件表） | 記載なし | 記載なし |
| [Provisioning NVMe/TCP for Linux](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/provision-nvme-linux.html)（手順） | **出力例の中に `trsvcid=4420` として現れるだけ**。開けるべきポートとしての記述ではない | 記載なし |
| [Use NVMe/TCP to mount FSx for ONTAP file system on Linux instance](https://www.repost.aws/knowledge-center/ec2-mount-fsx-ontap-nvme-tcp)（Knowledge Center） | **インバウンドで 4420 を許可することが前提条件として明記されている** | 記載なし |

**要件として 4420 を書いているのは 3 番目だけです。** 要件表ではなく Knowledge Center の記事で、しかも 8009 には触れていません。**設計の入口として要件表を見る読者は、ここに到達しません。**

8009 については、**上記のいずれにも記載を見つけられませんでした。** 記載が無いことと不要であることは別です。当方の実測ではディスカバリが 8009 で成立しています。

---

## セキュリティグループを設計するときに採る手順

**要件表を出発点にして、プロトコルごとの手順ページで足し込む。** 表を網羅的な一覧として扱わないことがこのノートの実務上の帰結です。

| プロトコル | ポート | 出所 |
|---|---|---|
| iSCSI | TCP 3260 | 要件表 |
| NVMe/TCP（データ） | TCP 4420 | 実測。要件表に記載なし |
| NVMe/TCP（ディスカバリ） | TCP 8009 | 実測。公開ページに記載を見つけられず |

[30 分で動かす手順](../quickstart.md)が使う CloudFormation は iSCSI だけを開けています（`fsxontap-iscsi-quickstart.yaml`）。NVMe/TCP を試す場合は同じ `SecurityGroupIngress` に 4420 と 8009 を足してください。

---

## AWS API から NVMe エンドポイントが取れないことの帰結

`describe-storage-virtual-machines` の `Endpoints` に `Nvme` は含まれず `null` が返ります。NVMe/TCP が実際に到達できている状態でも変わりません。

**つまり接続先アドレスを AWS API だけで求められません。** iSCSI と同じ 2 つのアドレスを使いますが、それを知るには `Iscsi` のエンドポイントを読むか、ONTAP 側で `network interface show` を見る必要があります。実測では `iscsi_1` / `iscsi_2` の `services` に `data-iscsi` と `data-nvme-tcp` の両方が入っており、**同じ 2 アドレスが両プロトコルを提供していました。**

これは [LUN と igroup は AWS の API の外側にある](block-objects-are-outside-the-aws-api.md) と同じ分界線の話ですが、**あちらは「AWS の API で作れない」、こちらは「AWS の API で読めない」**です。作成の話ではなく、稼働中の構成を読み取る手段の話として分けています。

---

## 検証環境

| 項目 | 値 |
|---|---|
| ONTAP バージョン | 9.18.1P5 |
| リージョン | `ap-northeast-1` |
| 構成 | `MULTI_AZ_2`（第 2 世代）、1 HA ペア、スループット容量 384 MBps、SSD 1024 GiB |
| クライアント | Amazon Linux 2023、kernel 6.18.44 |
| 検証日 | 2026-09-05 |

> **注意**: 上記はこの環境での実測であり、一般的なサービス上限や本番環境での再現を保証するものではありません。

**この検証に否定対照はありません。** 観測したのは「ディスカバリが 8009 を、データが 4420 を使った」ことだけです。**4420 と 8009 だけを開けた状態で接続が成立するか**は試していません。したがって「この 2 つで網羅」と書けるだけの根拠がありません。網羅性を自分の設計の前提に置く場合は、下の手順 3 を実行してください。

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `network interface show -vserver <svm> -lif <iscsi_lif> -fields services` | そのアドレスが `data-nvme-tcp` を提供しているか。iSCSI 用のアドレスがそのまま使えるかがここで決まります |
| 2 | クライアントで `nvme discover -t tcp -a <lif_ip> -s 8009` と `nvme connect-all -t tcp -a <lif_ip>` を実行し、`nvme list-subsys` で `trsvcid` を読む | ディスカバリとデータがそれぞれどのポートを使ったか |
| 3 | **4420 と 8009 だけを許可したセキュリティグループを新規に作り、それだけを付けた状態で手順 2 を再実行する** | **網羅性。** これが通れば「2 つで足りる」と書けます。当方は未実施です |
| 4 | `aws fsx describe-storage-virtual-machines --storage-virtual-machine-ids <id> --query 'StorageVirtualMachines[].Endpoints'` | `Nvme` が返るかどうか。自環境でも `null` なら、接続先は ONTAP 側から取る前提で手順を組みます |

適用手順の全体像は [本番に取り入れる前の確認](../../../evidence-policy.md#本番に取り入れる前の確認) を参照してください。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| セキュリティグループ要件表は必要なポートの網羅的な一覧である | **ブロックプロトコルについては網羅していません。** iSCSI の 3260 はありますが、NVMe/TCP の 4420 と 8009 はありません（2026-09-12 確認） |
| NVMe/TCP のポートは手順ページに書いてある | 手順ページに現れる `4420` は**出力例の中の `trsvcid` の値**です。開けるべきポートとしての記述ではありません |
| 4420 だけ開ければ接続できる | 当方の実測ではディスカバリが 8009 を使いました。4420 だけで足りるかは確認していません |
| NVMe/TCP 用に別のアドレスが払い出される | 実測では iSCSI と**同じ 2 アドレス**が両プロトコルを提供していました。ただし AWS API の `Nvme` は `null` を返すため、アドレスは `Iscsi` 側か ONTAP 側から取ります |
| ブロックのプロトコルが 2 つあるなら、AWS のドキュメントの扱いも同程度である | セキュリティグループ要件表、同ページのプロトコル列挙、`describe-storage-virtual-machines` の 3 か所で NVMe/TCP が抜けています |

---

## 関連ドキュメント

- [ブロックプロトコルの選択肢は世代と HA ペア数で先に狭まる](protocol-choice-is-bounded-before-you-choose.md) — どちらを選ぶかの判断
- [パスはフェイルオーバーの仕組みそのもの](paths-are-the-failover-mechanism.md) — 接続後のパス数とフェイルオーバー。**NVMe/TCP は Amazon Linux 2023 でネイティブマルチパスが構成できません**
- [LUN と igroup は AWS の API の外側にある](block-objects-are-outside-the-aws-api.md) — 作成側の分界線
- [ブロックストレージを 30 分で動かす手順](../quickstart.md) — iSCSI のみを開ける CloudFormation
