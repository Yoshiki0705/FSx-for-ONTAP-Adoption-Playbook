---
title: igroup の外側にある 2 つの制御 — CHAP と portset は fsxadmin で使えるが AWS のドキュメントには出てこない
lifecycle: [design, build, operate]
domains: [block-storage, security-governance]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
lang: ja
---

# igroup の外側にある 2 つの制御

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

## 結論

**FSx for ONTAP のブロックアクセス制御は igroup だけではありません。** ONTAP には **CHAP**（イニシエータの認証）と **portset**（LUN を見せる LIF の制限）があり、**どちらも `fsxadmin` で操作できました。**

**そして AWS のドキュメントはどちらにも触れていません。** 未記載ですが使えます。**未記載を非対応と読み替えないでください。**

| 制御 | 何を制限するか | 既定 |
|---|---|---|
| igroup | **どのイニシエータ**が LUN を見られるか | 明示的に作る |
| CHAP | イニシエータが**名乗った IQN が本物か** | **`none`**（認証なし） |
| portset | **どの LIF 経由**で LUN が見えるか | 無し（全 reporting node の LIF） |

**igroup だけの構成では、IQN を騙れば LUN に届きます。** IQN はホスト側の設定ファイルに書かれた文字列であって、秘密ではありません。**CHAP を掛けるかどうかは、そのネットワークで IQN の詐称をどう見るかの判断です。**

> **区分**: `verified`（検証日 2026-09-05、`ap-northeast-1`、`MULTI_AZ_2` 第 2 世代 1 HA ペア、ONTAP 9.18.1P5、Amazon Linux 2023）— コマンドの可否、既定値、認証失敗時の症状、portset を掛けたときのホスト側の状態。

---

## `fsxadmin` で使えたコマンド

**FSx for ONTAP の `fsxadmin` は権限が絞られています。** ブロックの制御に関わるものを実際に叩いた結果です。

| コマンド | 結果 |
|---|---|
| `vserver iscsi security show` / `create` | **使えました** |
| `lun portset show` / `create`、`lun igroup bind` / `unbind` | **使えました** |
| `vserver consistency-group show` / `create` | **使えました** |
| `statistics lun show` | **使えました** |
| `storage failover show` | **空のテーブルが返りました** |

**`storage failover show` が「This table is currently empty」を返したのは権限エラーではありません。** **FSx for ONTAP は HA の状態を `fsxadmin` に見せていません。** 帰結として **`storage failover takeover` でフェイルオーバーを誘発する道はありません。** 誘発の手段はスループット容量の変更だけです（[パスはフェイルオーバーの仕組みそのもの](paths-are-the-failover-mechanism.md) を参照）。

---

## CHAP の既定と、掛け方

**既定は認証なしです。**

```text
Vserver      Initiator Name   Auth Type   Auth Policy   Inbound User   Outbound User
------------ ---------------- ----------- ------------- -------------- --------------
<svm>        default          none        -             -              -
```

**`default` の行が `none` である限り、igroup に載っている IQN を名乗れば誰でもログインできます。**

CHAP の設定は ONTAP の CLI にもありますが、**CLI はパスワードを対話プロンプトで受け取ります。** 自動化には REST を使いました。

```text
POST https://<management-ip>/api/protocols/san/iscsi/credentials
{
  "svm": {"name": "<svm>"},
  "initiator": "iqn.1994-05.com.redhat:xxxxxxxx",
  "authentication_type": "chap",
  "chap": {"inbound": {"user": "<chap-user>", "password": "<secret>"}}
}
```

設定後の表示です。`Auth Policy` が `local` になります。

| 項目 | 値 |
|---|---|
| Auth Type | `CHAP` |
| Auth Policy | `local` |

**単方向と相互認証の区別は inbound / outbound です。**

| 種類 | 設定するもの |
|---|---|
| 単方向（ターゲットがイニシエータを認証） | inbound のユーザーとパスワード |
| 相互（イニシエータもターゲットを認証） | inbound と outbound の両方。**同じパスワードは使えません** |

CHAP のユーザー名は 1〜128 バイトです。**イニシエータのアドレス範囲で絞る `-initiator-address-ranges` もあります。**

---

## 認証に失敗したときの症状

**CHAP をターゲット側に掛け、イニシエータ側に何も設定していない状態でログインしました。**

```text
iscsiadm: Could not login to [iface: default, target: iqn...:vs.4, portal: <iscsi-1c>,3260].
iscsiadm: initiator reported error (24 - iSCSI login failed due to authorization failure)
iscsiadm: Could not log into all portals
```

`iscsid` 側です。

```text
iscsid: Login failed to authenticate with target iqn...
iscsid: session 3 login rejected: Initiator failed authentication with target
```

| 観測 | 値 |
|---|---|
| `iscsiadm -m node -L all` の終了コード | **24** |
| できたセッション | **0** |

**症状は明確です。** 「見えない」ではなく「認証で拒否された」と出ます。**LUN が見えないという症状で調べ始めたときに、igroup を疑う前にここを見れば切り分けが済みます。**

イニシエータ側に設定して再度ログインすると通りました。

```bash
iscsiadm -m node --op=update -n node.session.auth.authmethod -v CHAP
iscsiadm -m node --op=update -n node.session.auth.username   -v <chap-user>
iscsiadm -m node --op=update -n node.session.auth.password   -v <secret>
iscsiadm -m node -L all      # 終了コード 0、セッションが復帰
```

**ノードレコードの更新は `-T` / `-p` で絞らずに実行してください。** 検証環境ではポータルを指定した形が `No records found` を返しました。絞らない形は通りました。

---

## portset がパス数を実際に減らすこと、そして残骸

**portset は「この igroup には、この LIF 経由でしか見せない」という制限です。** Selective LUN Map の上に載る追加の絞り込みです。

```text
lun portset create -vserver <svm> -portset ps_1a_only -protocol iscsi -port-name iscsi_1
lun igroup bind   -vserver <svm> -igroup <igroup> -portset ps_1a_only
```

**`-protocol` は `mixed`（既定）/ `fcp` / `iscsi` です。** portset の名前は 1〜96 文字で**大文字小文字を区別**します。**空の portset に bind はできません。**

**効果はホスト側に出ました。** ただし **除外したパスは消えません。**

`iscsiadm -m session --rescan` と `multipath -r` の後の状態です。

```text
`-+- policy='service-time 0' prio=0 status=enabled
  `- 0:0:0:0 sda     8:0   active faulty running
```

| 観測 | 内容 |
|---|---|
| 除外した LIF 経由のパス | **`faulty`、`prio=0`** |
| `lsblk` のサイズ | **0B** |
| マップの `hwhandler` | **`'1 alua'` から `'0'` に落ちました** |

**LUN が報告されなくなっただけで、SCSI デバイスはホストに残ります。** 片付けが要ります。

```bash
multipath -f <wwid>
echo 1 > /sys/block/sda/device/delete
multipath -r
```

**これで単一パスの正常なマップになり、`hwhandler='1 alua'` も戻りました。**

**portset を運用に入れるなら、ホスト側のデバイス削除まで手順に含めてください。** そうしないと **`faulty` なパスが残ったままの構成が正常だと思われます。**

解除の注意点が 2 つあります。

| 操作 | 注意 |
|---|---|
| `lun igroup unbind` | **`-portset` 引数を取りません。** igroup だけを指定します |
| `lun portset delete` | **igroup が bind されている間は削除できません。** unbind が先です |

**NetApp は portset を非推奨としていません。** ONTAP 9.12.1 以降、最初の portset は CLI で作る必要があります。

---

## どれを使うかの判断

**3 つは重ねて使えます。目的が別です。**

| 目的 | 使うもの |
|---|---|
| どのホストにどの LUN を見せるか | **igroup**（必須） |
| IQN の詐称を防ぐ | **CHAP** |
| パス数を減らす、経路を限定する | **portset** |
| ホストのパス数の上限に収める | **portset**（または LIF 側の設計） |

**CHAP を掛けるかどうかは、そのサブネットに誰が入れるかで決まります。** ブロックのアドレスは VPC CIDR 内の普通のアドレスなので（[Multi-AZ が動かすのはアドレスではなくルート](multi-az-moves-a-route-not-an-address.md)）、**セキュリティグループで届く範囲を絞るのが第一の制御です。** CHAP はその上の層です。**どちらか一方ではありません。**

**portset は、パスが多すぎる問題に対する ONTAP 側の答えです。** ホスト側のセッション数で調整する方法もあり、**どちらで絞ったかを記録しておかないと、後から見て理由が分かりません。** パス数の指針が資料間で食い違っている点は [パスはフェイルオーバーの仕組みそのもの](paths-are-the-failover-mechanism.md) にあります。

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `vserver iscsi security show -vserver <svm>` | **`default` が `none` かどうか。認証なしで運用しているかがここで分かります** |
| 2 | `vserver iscsi security create` か REST の `credentials` が通るか | **`fsxadmin` で CHAP が設定できること** |
| 3 | イニシエータ側を未設定のままログインし、終了コードと `journalctl -u iscsid` を記録する | **認証失敗の症状**（切り分けの足場） |
| 4 | `lun portset create` と `lun igroup bind` が通るか | **`fsxadmin` で portset が使えること** |
| 5 | bind 後に `multipath -ll` でパス数と `faulty` の有無を確認する | **絞り込みが効いたこと、そして残骸** |
| 6 | 残骸を `echo 1 > /sys/block/<dev>/device/delete` で消し、`hwhandler` が戻るか確認する | **片付けの手順** |
| 7 | `storage failover show` を叩く | **空テーブルなら HA 状態は見えません** |

**手順 3 と 5 は検証環境で行ってください。** どちらも一時的にアクセスを失わせます。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| ブロックのアクセス制御は igroup だけ | **CHAP と portset があります。** どちらも `fsxadmin` で使えました |
| AWS のドキュメントに無いから CHAP は使えない | **使えました。** 未記載であることと非対応は別です |
| igroup に載っていなければ届かないので認証は不要 | **IQN はホスト側の設定文字列で、秘密ではありません** |
| CHAP は既定で有効 | **既定は `none` です** |
| 相互認証は同じパスワードでよい | **inbound と outbound に同じパスワードは使えません** |
| CHAP の失敗は「LUN が見えない」という症状になる | **`error (24 ... authorization failure)` と明示されます。** 終了コードは 24 |
| `iscsiadm --op=update` はポータルを指定して行う | **絞らずに実行してください。** 指定した形は `No records found` を返しました |
| portset を掛ければホストのパスが消える | **消えません。** `faulty` な SCSI デバイスが残り、削除が要ります |
| `lun igroup unbind -portset …` で解除する | **`-portset` 引数はありません** |
| portset は非推奨 | **NetApp は非推奨としていません** |
| `storage failover show` が空なのは権限エラー | **エラーではありません。** FSx for ONTAP が HA 状態を見せていません |

---

## 検証環境

| 項目 | 値 |
|---|---|
| ONTAP バージョン | 9.18.1P5 |
| リージョン | `ap-northeast-1` |
| デプロイタイプ | `MULTI_AZ_2`（第 2 世代、1 HA ペア） |
| スループット容量 | 384 MBps |
| iSCSI LIF | 2 本（AZ ごとに 1 本） |
| クライアント | Amazon Linux 2023、kernel 6.18.44-99.149.amzn2023.x86_64 |
| 検証日 | 2026-09-05 |

> **注意**: 上記はこの環境での実測です。**`fsxadmin` に許されている操作は変わることがあります。** 設計に織り込む前に自環境で確認してください。

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| CHAP の設定、単方向と相互の区別、inbound / outbound、同じパスワードが使えないこと、ユーザー名の長さ、`-initiator-address-ranges` | [NetApp: vserver iscsi security create](https://docs.netapp.com/us-en/ontap-cli/vserver-iscsi-security-create.html) |
| iSCSI の認証方式の考え方 | [NetApp: iSCSI authentication](https://docs.netapp.com/us-en/ontap/san-admin/iscsi-authentication-concept.html) |
| portset の作成、`-protocol` の値と既定、名前の規則 | [NetApp: lun portset create](https://docs.netapp.com/us-en/ontap-cli/lun-portset-create.html) |
| igroup と portset の bind | [NetApp: lun igroup bind](https://docs.netapp.com/us-en/ontap-cli/lun-igroup-bind.html) |
| portset で LUN を見せる LIF を制限すること、パス数を抑える手段として portset を挙げていること | [NetApp: Multipathing](https://docs.netapp.com/us-en/ontap/san-config/host-support-multipathing-concept.html) |
| Selective LUN Map が既定で有効であること | [NetApp: Selective LUN Map](https://docs.netapp.com/us-en/ontap/san-admin/selective-lun-map-concept.html) |
| igroup による LUN の見せ方 | [AWS: Provisioning iSCSI for Linux](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-luns-linux.html) |
| セキュリティグループで iSCSI に開ける必要があるポート | [AWS: File system access control with Amazon VPC](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limit-access-security-groups.html) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [パスはフェイルオーバーの仕組みそのもの](paths-are-the-failover-mechanism.md) — portset で絞る対象になるパス
- [Multi-AZ が動かすのはアドレスではなくルート](multi-az-moves-a-route-not-an-address.md) — ブロックのアドレスが VPC 内にあること
- [LUN と igroup は AWS の API の外側にある](block-objects-are-outside-the-aws-api.md) — igroup が IaC の外にあること
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)
