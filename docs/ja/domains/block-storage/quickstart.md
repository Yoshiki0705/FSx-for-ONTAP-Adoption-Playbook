---
title: ブロックストレージを 30 分で動かす手順 — CloudFormation 1 本と ONTAP REST のシェル 3 本
lifecycle: [build]
domains: [block-storage]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
lang: ja
---

# ブロックストレージを 30 分で動かす手順

<!-- lang-switcher:start -->
🌐 [日本語](quickstart.md) | [English](../../../en/domains/block-storage/quickstart.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

## この手順で到達する状態

**FSx for ONTAP の LUN を 1 つ作って、Linux から iSCSI でマルチパス接続した状態**まで到達します。所要時間は待ち時間込みで約 30 分、うち 17 分はファイルシステムの作成待ちです。

置いてあるものは [`examples/block-storage/`](../../../../examples/block-storage/) にあります。

| ファイル | 役割 | どこに届くか |
|---|---|---|
| `fsxontap-iscsi-quickstart.yaml` | ファイルシステム・SVM・ボリューム・クライアント・セキュリティグループ・IAM ロール | AWS の API |
| `provision-lun.sh` | LUN・igroup・LUN マップを作る。**冪等** | ONTAP REST API |
| `connect-iscsi.sh` | ホストを iSCSI でログインさせ multipath を組む。**冪等** | ホストと ONTAP |
| `verify-block.sh` | 両側の状態を出す。何も作らない | ONTAP REST API とホスト |

> **区分**: `verified`（検証日 2026-09-05、`ap-northeast-1`、`SINGLE_AZ_2` 第 2 世代 1 HA ペア、384 MBps、ONTAP 9.18.1P5、Amazon Linux 2023 kernel 6.18.44）— 所要時間、冪等性の 5 指標、下で挙げる 4 つの躓きどころ。
> **性能値は含めません。** クライアントが `t3.medium` なので、測っても FSx for ONTAP ではなくクライアントの NIC の値になります。

---

## テンプレートとシェルが分かれている理由

**LUN・igroup・LUN マップには、Amazon FSx の API のアクションも CloudFormation のリソースタイプも存在しません。** そのため構築は AWS の制御面から ONTAP へまたぎ、**その境界はボリュームと LUN の間**にあります。この分割はパッケージングの都合ではなく、境界そのものです。詳細は [LUN と igroup は AWS の API の外側にある](notes/block-objects-are-outside-the-aws-api.md) にあります。

**ボリュームはテンプレート側で作っています。** ONTAP 側で作ったボリュームには `fsvol-` の ID が付かず、CloudWatch・AWS API でのタグ付け・AWS Backup のすべてから外れるためです（[ブロックの監視で見えるものと見えないもの](notes/what-block-monitoring-shows.md)）。

---

## 事前に必要なもの

| 要件 | 理由 |
|---|---|
| 既存の VPC とサブネット 1 つ | テンプレートはネットワークを作りません。削除時の影響範囲を VPC まで広げないためです |
| そのサブネットから Systems Manager・Secrets Manager・**Amazon FSx の API** に到達できること | 下の「躓きどころ 2」を参照。NAT ゲートウェイ、パブリックアドレス、またはインターフェース VPC エンドポイント |
| `aws` CLI と、CloudFormation・Amazon FSx・IAM・Secrets Manager の権限 | |

**クライアント側に用意するものはありません。** テンプレートが AL2023 を 1 台立て、`iscsi-initiator-utils`・`device-mapper-multipath`・`jq` を UserData で入れます。

---

## 手順

### 1. パスワードのシークレットの作成

**パスワードは CloudFormation のパラメータにも出力にも出しません。** テンプレートは `{{resolve:secretsmanager:...}}` で作成時に解決します。

```bash
aws secretsmanager create-secret --name fsxn-quickstart-fsxadmin \
  --secret-string '{"password":"<8〜50 文字>"}'
```

**長さの上限と下限は 8〜50 文字です**（`FsxAdminPassword` のパターン `^[^制御文字]{8,50}$`）。

### 2. AWS 側の作成

```bash
cd examples/block-storage
aws cloudformation create-stack --stack-name fsxn-block-quickstart \
  --template-body file://fsxontap-iscsi-quickstart.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=VpcId,ParameterValue=vpc-xxxxxxxx \
               ParameterKey=ClientSubnetId,ParameterValue=subnet-xxxxxxxx \
               ParameterKey=FsxAdminSecretName,ParameterValue=fsxn-quickstart-fsxadmin
```

**約 17 分かかります。** ほぼ全部がファイルシステムの作成待ちです。完了したら出力を取ります。

```bash
aws cloudformation describe-stacks --stack-name fsxn-block-quickstart \
  --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' --output text
```

`FileSystemId` / `SvmName` / `VolumeName` / `ClientInstanceId` が返ります。**ONTAP の管理アドレスは出力に含まれません。** `AWS::FSx::FileSystem` にその `Fn::GetAtt` が無いためです。

### 3. クライアントでの 3 本の実行

```bash
aws ssm start-session --target <ClientInstanceId>
```

スクリプトを配置したら、この順に実行します。

```bash
sudo ./provision-lun.sh --file-system-id fs-xxxxxxxx --svm <SvmName> \
  --volume <VolumeName> --secret-id fsxn-quickstart-fsxadmin

sudo ./connect-iscsi.sh --file-system-id fs-xxxxxxxx

sudo ./verify-block.sh --file-system-id fs-xxxxxxxx --svm <SvmName> \
  --volume <VolumeName> --secret-id fsxn-quickstart-fsxadmin
```

**`verify-block.sh` の出力がこの形になれば到達しています。**

```text
LUNs on the SVM              1
igroup initiators (total)    1
LUN maps                     1
iSCSI sessions (this host)   2
multipath paths (this host)  2
```

`multipath -ll` はこうなります。**優先度が 50 と 10 の 2 グループに分かれていること**が、ALUA が効いている印です。

```text
3600a0980<serial-hex> dm-0 NETAPP,LUN C-Mode
size=40G features='3 queue_if_no_path pg_init_retries 50' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| `- 0:0:0:0 sda     8:0   active ready running
`-+- policy='service-time 0' prio=10 status=enabled
  `- 1:0:0:0 sdb     8:16  active ready running
```

---

## 2 回流しても増えないこと

**AWS の接続手順は冪等ではありません。** ポータルごとのログインループを再実行するとセッションが増え、Windows では 16 パスが 24 パスになった実測があります（[パスはフェイルオーバーの仕組みそのもの](notes/paths-are-the-failover-mechanism.md)）。警告は出ません。

ここのスクリプトは実行前に現状を読み、足りないものだけを作ります。**同じ環境で 3 回連続して流し、5 指標がすべて一致しました。**

| 指標 | 1 回目 | 2 回目 | 3 回目 |
|---|---|---|---|
| SVM 上の LUN 数 | 1 | 1 | 1 |
| igroup のイニシエータ数 | 1 | 1 | 1 |
| LUN マップ数 | 1 | 1 | 1 |
| iSCSI セッション数 | 2 | 2 | 2 |
| multipath のパス数 | 2 | 2 | 2 |

2 回目以降の出力です。

```text
lun    : exists, left alone
igroup : exists, left alone
member : iqn...:xxxxxxxxxxxx already in ig_xxxxxxxxxxxx
map    : /vol/<volume>/lun1 already mapped to ig_xxxxxxxxxxxx
  <iscsi-ip-1>    1 session(s) already present, skipped
  <iscsi-ip-2>    1 session(s) already present, skipped
```

**判定を別のスクリプトに分けているのは意図的です。** 実行と判定を同じスクリプトが行うと、それは証拠になりません。

---

## 実行して初めて分かった 4 つの躓きどころ

**この 4 つはどれも `cfn-lint`・`shellcheck`・`validate-template` を通過していました。** 動かして初めて出ました。同じ構成を自分で組むときに当たる可能性が高い順に並べます。

### 1. LUN 専用ボリュームでも必須の `JunctionPath`

LUN だけを置くボリュームは SVM の名前空間にマウントする理由がありません。ところで実際に作ると失敗します。

```text
Resource handler returned message: "Parameter validation failed:
Missing required parameter in OntapConfiguration: "JunctionPath""
```

**プロパティリファレンスは `JunctionPath` を *Required: No* と書いており、同じページの本文は required と書いています。** リソースハンドラは後者に従います。テンプレートには junction path を入れてありますが、**制御面の制約であって設計判断ではありません。**

マウントされていても **LUN の中身は NFS から読めません。** 名前とサイズは見えます（[LUN の並べ方が決めているのは復旧の粒度](notes/lun-layout-decides-recovery-granularity.md)）。

### 2. Amazon FSx の API のパブリック解決

`ssm` と `secretsmanager` のインターフェースエンドポイントだけを持つプライベートサブネットでは、**`aws fsx describe-file-systems` がタイムアウトします。** Secrets Manager は 10.x のエンドポイントアドレスに解決して通るのに、`fsx.<region>.amazonaws.com` はパブリックアドレスに解決するためです。

回避策はスクリプト側に入れてあります。

```bash
# 手元の AWS CLI が届く場所で 1 回取る
aws fsx describe-file-systems --file-system-ids fs-xxxxxxxx \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]'
aws fsx describe-storage-virtual-machines \
  --query 'StorageVirtualMachines[?FileSystemId==`fs-xxxxxxxx`].Endpoints.Iscsi.IpAddresses[]'

sudo ./provision-lun.sh --management-ip <management-ip> --svm ... --volume ... --password-stdin
sudo ./connect-iscsi.sh --target-ips "<iscsi-ip-1> <iscsi-ip-2>"
```

**iSCSI 自体はこれを一切必要としません。** LUN は VPC の中で届きます。必要なのは管理アドレスの解決だけです。

### 3. セッション不在時に `iscsiadm -m session` が返す終了コード 21

`set -o pipefail` を付けたスクリプトでは、**セッション 0 という正常な初期状態でパイプライン全体が失敗**します。最初の 1 回目が無言で終わります。

### 4. `iscsiadm -m node -p <portal>` が出す詳細レコード

`# BEGIN RECORD` から始まる出力なので、1 行目の 2 番目のフィールドを取るとターゲット名ではなく `BEGIN` が返ります。**ディスカバリは成功し、ログインが「No records found」で失敗する**という読みにくい症状になります。ポータル指定なしの短い一覧から取るのが正解です。

---

## 既存ノートの訂正 2 件

この検証で 2 つ狭まりました。

| これまでの記述 | 実測 |
|---|---|
| `mpathconf --enable` の前に空の `/etc/multipath.conf` を置けば、そのまま残る | **残りません。** 29 バイト書かれました（空の `blacklist` と `defaults` ブロック）。ゼロから書かせた場合の 334 バイトよりは小さく、できたマップは NetApp 推奨の `service-time 0` と `queue_if_no_path` になっていました |
| 予約付き LUN はボリュームの容量を即座に食う | **REST API で作った LUN は既定で予約なしです**（`space.guarantee.requested` が `false`）。40 GiB の LUN に対してボリュームの使用量は 352,256 バイトでした。`verify-block.sh` はサイズの隣に予約の有無を出します |

容量の 3 段の数え方そのものは [容量は 3 か所で数えられる](notes/capacity-is-counted-in-three-places.md) にあります。**この環境の aggregate は 907.03 GiB で、別に作った Single-AZ 環境と一致しました。**

---

## 撤去

**スクリプトが作ったものは CloudFormation が知りません。** ONTAP 側を先に消します。

```bash
sudo ./verify-block.sh ...      # 何があるか記録する
sudo iscsiadm -m node -U all && sudo iscsiadm -m node -o delete
# LUN マップ → igroup → LUN の順に ONTAP REST か CLI で削除
aws cloudformation delete-stack --stack-name fsxn-block-quickstart
```

削除には 18 分ほどかかりました。

**FlexClone を作った場合は、ボリュームを消す前に recovery queue を空にしてください。** 削除したボリュームは名前を変えて 12 時間以上キューに残り、そこに FlexClone の関係が生き残ると**親ボリューム・SVM・ファイルシステムのすべてが削除できなくなります。**

---

## ここに含めていないもの

| 含めていないもの | 理由と次の一歩 |
|---|---|
| NVMe/TCP | カーネル依存があるため 1 本目には入れませんでした。**`verify-block.sh` が `CONFIG_NVME_MULTIPATH` を報告します。** Amazon Linux 2023 では無効で、その状態ではフェイルオーバーが効きません（[実測したフェイルオーバー](notes/paths-are-the-failover-mechanism.md#実測したフェイルオーバー)） |
| Windows と MPIO | PowerShell 一式が別物になります。ホスト側の既定値は [パスはフェイルオーバーの仕組みそのもの](notes/paths-are-the-failover-mechanism.md) にあります |
| Multi-AZ | アドレスの配置とフェイルオーバーの挙動が変わります（[Multi-AZ が動かすのはアドレスではなくルート](notes/multi-az-moves-a-route-not-an-address.md)） |
| HA ペア複数 | ブロックは 6 組までです。それ以上ではプロトコルが無効になります |
| 性能値 | `t3.medium` は 384 MBps = 3.07 Gbps を持続できません。測定方法は [公開ベンチマークの読み方](notes/when-shared-block-changes-the-design.md#公開ベンチマークの読み方) |
| CHAP と portset | 既定は認証なしです。設定方法と失敗時の症状は [igroup の外側にある 2 つの制御](notes/igroups-are-not-the-only-access-control.md) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](README.md) — このモジュールのハブ
- [ブロックプロトコルとレイアウトの決定木](../../reference/decision-trees/block-protocol-and-layout.md) — プロトコルとレイアウトを決める
- [ブロックストレージの選択肢の比較](../../reference/comparison/block-storage-options.md) — Amazon EBS との対称なトレードオフ
- [ブロックストレージ横断リソースマップ](../../reference/block-storage-resource-map.md) — 一次情報の索引と資料間の食い違い
- [知見の分類ポリシー](../../evidence-policy.md)

---

<!-- lang-switcher:start -->
🌐 [日本語](quickstart.md) | [English](../../../en/domains/block-storage/quickstart.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
