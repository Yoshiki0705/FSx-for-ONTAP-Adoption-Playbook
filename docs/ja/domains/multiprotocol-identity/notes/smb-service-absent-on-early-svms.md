---
title: SMB を提供できない SVM がある。data-cifs は作成時期で決まり、あとから追加する経路が無い
lifecycle: [assess, design, build]
domains: [multiprotocol-identity]
evidence: verified
verified_on: 2026-09-01
ontap_version: 9.18.1P3D1
region: ap-northeast-1
lang: ja
---

# SMB を提供できない SVM がある。data-cifs は作成時期で決まり、あとから追加する経路が無い

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — マルチプロトコル・ID](../README.md)

---

## 結論

**一部の既存 SVM は SMB を提供できません。そして利用者側では直せません。**

データ LIF のサービスポリシーに `data-cifs` が含まれていない SVM があります。この状態では、SVM の許可プロトコルに `cifs` が入っていて、CIFS サーバーを作成できて、`Authentication Style` まで正常に見えても、**445 番ポートが開きません。**

```text
FsxIdEXAMPLE::> vserver cifs show -vserver <svm>
                         CIFS Server NetBIOS Name: <name>
                    NetBIOS Domain/Workgroup Name: WORKGROUP
                             Authentication Style: workgroup
                CIFS Server Administrative Status: up      ← 正常に見える

（同じ SVM のデータ LIF）
FsxIdEXAMPLE::> network interface show -vserver <svm> -lif nfs_smb_management_1 -fields services
services: data-core,data-nfs,management-ssh,management-https,data-s3-server,data-dns-server
                                        ↑ data-cifs が無い

（クライアントから）
<svm-data-lif>:445 closed/filtered      ← NFS の 2049 は開いている
```

**`fsxadmin` では追加できません。** ロール定義で読み取り専用に固定されています。

```text
FsxIdEXAMPLE::> security login role show -role fsxadmin -fields cmddirname,access
fsxadmin "network interface service-policy" readonly
fsxadmin "network interface create"         readonly

（REST も同じ）
PATCH /api/network/ip/service-policies/<uuid>
  → {"error":{"message":"not authorized for that command","code":"6"}}
```

**特権不足ではありません。** 同じ経路で `set -privilege advanced` は機能します（advanced 専用コマンドが通ることを確認済み）。ロールが当該コマンドファミリを `readonly` にしているためです。

> **エラー文言に関する補足**: ロールで制限されたコマンドを CLI で叩くと、権限の話ではなく
> **`"<command>" is not a recognized command`** が返ります。**存在しないコマンドを打ったときと
> 同じ文言なので、綴りを疑って時間を使うことになります。** これは FSx for ONTAP 固有ではなく
> ONTAP の挙動で、NetApp KB
> [Command fails with "Command is not recognized command"](https://kb-ja.netapp.com/on-prem/ontap/Ontap_OS/OS-KBs/Command_fails_with_Command_is_not_recognized_command)
> が原因を「正しいロールまたは権限レベル `advanced` でコマンドを実行できなかった」と説明しています
> （AWS サポートからも同じ切り分けの案内あり、2026-09-02）。**綴りが正しいのに認識されないときは、
> `security login role show -role <role>` で当該コマンドファミリの `access` を確認してください。**

**なお `fsxadmin` で `readonly` / `none` になるコマンドファミリの一覧は公開されていません。** AWS サポートに一覧の掲載を要望済みで、改善要望として検討する旨の回答を得ています（2026-09-02）。**現時点では上記のとおり自環境で `security login role show` を読むしかありません。**

**FSx for ONTAP の API / コンソールにも、既存 SVM の SMB を有効化する操作がありません。** 回避策は**新しい SVM を作ってデータを移行する**ことだけです。

> **Evidence**: `verified`（2026-09-01、`ap-northeast-1`、ONTAP `9.18.1P3D1`）。
> 2 つのファイルシステム上の 9 SVM について `network interface show -fields services` を確認し、
> 本日新規作成した SVM で対照を取りました。**変更が入った時期の特定は観測からの推定で、
> AWS の告知は確認していません。**

---

## 決めているのは AD の有無ではなく作成時期

当初は「AD 参加 SVM だけが `data-cifs` を持つ」と考えましたが、**反例があります。**

| SVM | 作成日 | AD 参加 | `data-cifs` |
|---|---|---|---|
| A | 2026-02-10 | なし | **なし** |
| B | 2026-05-14 | あり | あり |
| C | 2026-05-22 | なし | **なし** |
| D | 2026-05-26 | あり | あり |
| E | 2026-06-09 | なし | **なし** |
| F | 2026-06-24 | あり | あり |
| G | 2026-06-30 | **なし** | **あり** ← 反例 |
| H | 2026-07-12 | あり | あり |
| I（本日新規作成） | 2026-09-01 | **なし** | **あり** ← 対照 |

**G と I が「AD の有無で決まる」を否定します。** 一方で C と E は非 AD で `data-cifs` を持ちません。

全観測と整合する読み方はこうです。

| 時期 | 挙動 |
|---|---|
| 2026-06-09 以前に作成 | AD 設定ありのときだけ `data-cifs` が付く |
| 2026-06-24 以降に作成 | **AD の有無に関わらず付く** |

**そして既に作られた SVM には遡って付きません。** I を作った時点でも C や E は変わっていません。

> **注意**: 上表の日付は 1 アカウント内の観測です。**変更時期はアカウントやリージョンで異なる
> 可能性があります。** 自環境では日付ではなく、次節の判定を使ってください。

---

## 自環境での判定

```text
# 全 SVM のデータ LIF のサービス一覧
FsxIdEXAMPLE::> network interface show -fields vserver,lif,services -role data
```

`nfs_smb_management_1` の `services` に `data-cifs` があるかどうかを見ます。**SVM の `allowed-protocols` に `cifs` が入っているかは判定になりません。** 該当した SVM でも `cifs` は入っていました。

クライアント側からの確認も併せて行うと確実です。

| 確認 | `data-cifs` あり | `data-cifs` なし |
|---|---|---|
| データ LIF の 445 | 開く | **開かない** |
| データ LIF の 2049（NFS） | 開く | 開く |
| Amazon FSx API の SVM の SMB エンドポイント | 値がある | **`null`** |

**Amazon FSx API の `Endpoints.Smb` が `null` かどうかが、ONTAP にログインせずに判定できる指標です。**

```bash
aws fsx describe-storage-virtual-machines \
  --query 'StorageVirtualMachines[].{Name:Name,SMB:Endpoints.Smb.IpAddresses}'
```

---

## 影響と回避

| 状況 | 影響 |
|---|---|
| 既存 SVM で SMB を新たに使いたい | **できません。** SVM の新規作成とデータ移行が必要です |
| 既存 SVM で NFS / S3 だけを使っている | 影響なし |
| ワークグループ構成で SMB を検証したい | **該当 SVM では検証そのものができません。** CIFS サーバーは作れるので、445 が開かない理由に気づくまで時間を取られます |

移行の手段はデータ量と停止許容時間で決まります。同一ファイルシステム内であれば SnapMirror や FlexClone、ボリューム移動が候補になります。**この比較は本ノートでは扱いません。**

> **設計に関する補足**: SVM を長期に使い回す設計では、**プロトコルを後から足せない可能性**を
> 前提に入れてください。今回の事例は `data-cifs` ですが、同じ形の制約が他のサービスでも
> 起こり得ます。**新しいプロトコルを使い始める前に、対象 SVM のデータ LIF のサービス一覧を
> 確認する**のが安全側の手順です。

---

## 併せて当たる上限

SVM を作り直す方針を採る場合、**スループット容量あたりの SVM 数の上限**に当たります。

```text
ServiceLimitExceeded: Amazon FSx does not support having more than 6 storage virtual machines
for an ONTAP file system with 128 MBps of throughput capacity.
```

既存 SVM を消せない状況で新規作成もできない場合、**スループット容量の変更が前提になります。** 課金に影響するため、移行計画の中で先に確認してください。

---

## 未確認

- **変更が入った正確な時期と、AWS 側の告知の有無**。観測から 2026-06-09 と 2026-06-24 の間と推定しただけです
- **リージョンやアカウントによる差**。1 アカウント 2 ファイルシステムの観測です
- **`data-cifs` が無い SVM に AD 設定を後から追加した場合の挙動**。Amazon FSx が `data-cifs` を追加するかは測っていません。AD 資格情報を要し、失敗時に SVM が不整合な状態になる可能性があるため実施しませんでした
- **移行手段ごとの所要時間と停止時間**

---

## 関連

- [SMB ローカルユーザーに最終ログオン属性は無い](local-user-inventory-without-last-logon.md)
- [AD への依存は参加時ではなく生涯続く](ad-dependency-lasts-the-lifetime.md)
- [セキュリティスタイルが権限評価のモデルを決める](security-style-and-permission-evaluation.md)
- [上限値・クォータ](../../../reference/limits/README.md)
