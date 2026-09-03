---
title: SMB を提供できない SVM がある。原因は作成時期ではなく CIFS サーバーの削除で、ONTAP REST で作り直せば戻る
lifecycle: [assess, design, build]
domains: [multiprotocol-identity]
evidence: verified
verified_on: 2026-09-02
ontap_version: 9.18.1P3D1
region: ap-northeast-1
lang: ja
---

# SMB を提供できない SVM がある。原因は作成時期ではなく CIFS サーバーの削除で、ONTAP REST で作り直せば戻る

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — マルチプロトコル・ID](../README.md)

---

## 結論

**データ LIF のサービスポリシーに `data-cifs` が含まれていない SVM があります。** この状態では、SVM の許可プロトコルに `cifs` が入っていて、CIFS サーバーを作成できて、`Authentication Style` まで正常に見えても、**445 番ポートが開きません。**

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

**このノートは以前、原因を「SVM の作成時期」と書いていました。それは誤りでした。**

| | 以前の記述 | 現在 |
|---|---|---|
| 原因 | SVM の作成時期（2026-06 の前後で挙動が変わったと推定） | **CIFS サーバーを削除し、その後 ONTAP CLI で作り直したこと** |
| 回避策 | **新しい SVM を作ってデータを移行する以外にない** | **CIFS サーバーを削除して ONTAP REST で作り直す。データ移行は不要** |
| 判定指標 | Amazon FSx API の `Endpoints.Smb` が `null` かどうか | **`services` に `data-cifs` が含まれるかどうか。`Endpoints.Smb` は AD 参加の有無を示すもので、判定に使えません** |

**回避策の記述が最も害の大きい誤りでした。** SVM の再作成とデータ移行を必要としない事象に対して、それを唯一の手段として書いていました。

---

## 取り下げた主張

「2026-06-09 以前に作成された非 AD SVM は `data-cifs` を持たず、2026-06-24 以降は AD の有無に関わらず持つ」と書いていました。**同一ファイルシステム上の現在の状態が、これを否定します。**

| SVM | 作成日 | AD 参加 | `data-cifs` |
|---|---|---|---|
| A | 2026-02-10 | なし | **なし** |
| B | 2026-05-14 | あり | あり |
| C | 2026-05-22 | なし | **なし** |
| D | 2026-05-26 | あり | あり |
| E | 2026-06-09 | なし | **なし** |
| F | 2026-07-12 | あり | あり |

**日付で切れる境界がありません。** 2026-05-14 の B は持ち、その 8 日後に作られた C は持ちません。**この 6 件で相関しているのは作成日ではなく、CIFS サーバーが存在するかどうかです**（`data-cifs` を持つ 3 件はいずれも CIFS サーバーが稼働しており、持たない 3 件はいずれも CIFS サーバーがありません）。

**以前「日付の境界」に見えたものは、古い SVM ほど CIFS サーバーを作って消した機会が多い、という交絡でした。** 当時の対照は「その日に新規作成した非 AD SVM が `data-cifs` を持っていた」ことでしたが、それは新しいからではなく、**まだ CIFS サーバーを削除されていないから**です。

> **測定に関する反省**: 日付順に並べた表で境界が見えたことを、機構の説明として採用しました。
> **並べ替えた軸に境界が見えることは、その軸が原因である証拠になりません。**
> 相関する別の軸（この場合は CIFS サーバーの作成・削除の履歴）を潰していませんでした。

---

## 原因 — CIFS サーバーの削除と CLI での再作成

**AWS サポートが同一バージョン（ONTAP 9.18.1P3D1）の環境で再現し、機構を特定しました**（2026-09-02）。

| # | 操作 | `data-cifs` | 445 |
|---|---|---|---|
| 1 | SVM を新規作成した直後 | **付与されている**（AD 参加の有無、CIFS サーバーの有無に関わらず） | 閉（CIFS サーバーが無いため） |
| 2 | CIFS サーバーを作成 | 付与されたまま | **開** |
| 3 | **CIFS サーバーを削除** | **削除される** | 閉 |
| 4 | ONTAP CLI `vserver cifs create` で再作成 | **復元されない**（コマンドは成功し、CIFS サーバーは稼働状態になる） | **閉のまま** |
| 5 | ONTAP REST `POST /api/protocols/cifs/services` で再作成 | **復元される** | **開** |

段階 4 の `services` は次のとおりで、**当方の該当 SVM と完全に一致します。**

```text
data_core,data_nfs,management_ssh,management_https,data_s3_server,data_dns_server
```

**SVM の作成処理には、AD の構成状況や作成時期で分岐する箇所が無いことも確認されています。** 2026-06-09〜06-24 の期間に当該処理への変更は入っていません。

**段階 4 が厄介なのは、CIFS サーバーの作成が成功してしまうことです。** エラーは出ず、`vserver cifs show` は正常に見え、445 だけが開きません。

**Amazon FSx 側で AD 構成を解除した場合も CIFS サーバーの削除が行われます。** つまり「AD をやめてワークグループに切り替える」という操作が、段階 3 を経由します。

> **Evidence**: **この節は AWS サポートの回答内容で、当方では再現していません。** 観測している
> 状態（`services` の内容、445 が閉じていること）は `verified` ですが、**段階 3〜5 の因果関係と
> 復旧手順は未実施です。** 共有ファイルシステム上の SVM で CIFS サーバーを削除する必要があり、
> 削除に伴って SMB 共有定義とセッションが消えるため、使い捨ての SVM を用意せずに実行していません。
> **公開ドキュメントにも記載がありません**（AWS サポートも「当該挙動を説明した公開情報は確認できて
> いない」と述べています）。

---

## 復旧手順

**AWS サポートから提示された手順です。当方では実行していません。** 実施前に検証用 SVM で確認してください。

```bash
# 1. 対象 SVM の CIFS サーバーの UUID を取得する
curl -X GET -u fsxadmin -k \
  "https://<管理エンドポイント>/api/protocols/cifs/services?svm.name=<SVM名>&fields=svm.uuid"

# 2. 現在の CIFS サーバーを削除する
curl -X DELETE -u fsxadmin -k \
  "https://<管理エンドポイント>/api/protocols/cifs/services/<UUID>"

# 3. REST で作り直す（ワークグループ構成の場合）
curl -X POST -u fsxadmin -k -H "Content-Type: application/json" \
  -d '{"svm":{"name":"<SVM名>"},"name":"<CIFSサーバー名>","workgroup":"<ワークグループ名>","enabled":true}' \
  "https://<管理エンドポイント>/api/protocols/cifs/services"
```

```text
# 4. 復元を確認する
FsxIdEXAMPLE::> network interface show -vserver <svm> -lif nfs_smb_management_1 -fields services
```

**手順 2 で SMB 共有の定義と SMB セッションが削除されます。** 445 が開いていない SVM であれば実質的な影響はありませんが、共有定義が残っている場合は事前に控えてください。

**ONTAP REST は `fsxadmin` の資格情報でファイルシステムの管理エンドポイントに対して使えます。** TLS 検証を無効にするか、リージョンごとの AWS CA バンドルを信頼させます。

---

## 自環境での判定

```text
# 全 SVM のデータ LIF のサービス一覧
FsxIdEXAMPLE::> network interface show -fields vserver,lif,services -role data
```

`nfs_smb_management_1` の `services` に `data-cifs` があるかどうかを見ます。**SVM の `allowed-protocols` に `cifs` が入っているかは判定になりません。** 該当した SVM でも `cifs` は入っていました。

| 確認 | `data-cifs` あり | `data-cifs` なし |
|---|---|---|
| データ LIF の 445 | 開く | **開かない** |
| データ LIF の 2049（NFS） | 開く | 開く |
| `services` に `data-cifs` | ある | **ない** ← **これが判定** |

**Amazon FSx API の `Endpoints.Smb` は判定に使えません。** 以前このノートは「ONTAP にログインせずに判定できる指標」として `Endpoints.Smb` が `null` かどうかを挙げていましたが、**これは SVM が AD に参加しているかどうかに連動する値で、`data-cifs` の有無や SMB を提供できるかどうかを示しません。**

AWS サポートは、**`data-cifs` が付与され CIFS サーバーも稼働し 445 も開いている SVM が、AD 未参加であるために `Endpoints.Smb` が `null` になる状態**を確認したと報告しています。ワークグループ構成の SVM では、正常でも `null` になります。

> **注意**: 当方の観測では `Endpoints.Smb` が値を持つ 3 件と `data-cifs` を持つ 3 件が一致して
> いますが、**それはこのファイルシステムに「非 AD で CIFS サーバーが稼働している SVM」が
> 存在しないためです。** 一致は偶然で、指標としての妥当性を示しません。

---

## fsxadmin では追加できないこと

`data-cifs` が失われた状態を、サービスポリシーを直接編集して直すことはできません。

```text
FsxIdEXAMPLE::> security login role show -role fsxadmin -fields cmddirname,access
fsxadmin "network interface service-policy" readonly
fsxadmin "network interface create"         readonly

（REST も同じ）
PATCH /api/network/ip/service-policies/<uuid>
  → {"error":{"message":"not authorized for that command","code":"6"}}
```

**特権不足ではありません。** 同じ経路で `set -privilege advanced` は機能します（advanced 専用コマンドが通ることを確認済み）。ロールが当該コマンドファミリを `readonly` にしているためです。

**したがって復旧経路は、サービスポリシーを編集することではなく、CIFS サーバーを REST で作り直して ONTAP に付け直させることになります。**

> **エラー文言に関する補足**: ロールで制限されたコマンドを CLI で叩くと、権限の話ではなく
> **`"<command>" is not a recognized command`** が返ります。**存在しないコマンドを打ったときと
> 同じ文言なので、綴りを疑って時間を使うことになります。** これは FSx for ONTAP 固有ではなく
> ONTAP の挙動で、NetApp KB
> [Command fails with "Command is not recognized command"](https://kb-ja.netapp.com/on-prem/ontap/Ontap_OS/OS-KBs/Command_fails_with_Command_is_not_recognized_command)
> が原因を「正しいロールまたは権限レベル `advanced` でコマンドを実行できなかった」と説明しています
> （AWS サポートからも同じ切り分けの案内あり、2026-09-02）。**綴りが正しいのに認識されないときは、
> `security login role show -role <role>` で当該コマンドファミリの `access` を確認してください。**

**なお `fsxadmin` で `readonly` / `none` になるコマンドファミリの一覧は公開されていません。** AWS サポートに一覧の掲載を要望済みで、改善要望として検討する旨の回答を得ています（2026-09-02）。**現時点では自環境で `security login role show` を読むしかありません。**

**別のロールを使えば直せる、という抜け道もありません。** AWS サポートが確認したところ、`network interface service-policy` は `fsxadmin`、`fsxadmin-readonly`、`vsadmin`、`vsadmin-backup`、`vsadmin-protocol`、`vsadmin-readonly`、`vsadmin-snaplock`、`vsadmin-volume` の**いずれのロールでも `readonly`** で、**FSx for ONTAP で使えるロールにサービスポリシーを変更できるものは存在しません**（2026-09-02）。上の実測は `fsxadmin` だけを見たものですが、ロールを変えて回避する試みは不要です。

> **オンプレミス ONTAP との差分に関する補足**: 管理者がサービスポリシーを直接編集できる環境では、
> この症状はポリシーを直せば終わります。**その手順が使えないのは FSx for ONTAP 固有の制約**で、
> だからこそ復旧経路が「CIFS サーバーを REST で作り直す」に限られます。他の ONTAP 環境向けの
> 手順を読むときは、この差分を織り込んでください。

---

## 影響と回避

| 状況 | 影響 |
|---|---|
| 既存 SVM で SMB を新たに使いたい | **CIFS サーバーを REST で作り直せば使えます。** SVM の再作成は不要です |
| 既存 SVM で NFS / S3 だけを使っている | 影響なし |
| ワークグループ構成で SMB を検証したい | **445 が開かない理由に気づくまで時間を取られます。** CIFS サーバーの作成は成功するためです |
| AD 構成を解除してワークグループへ切り替えた | **解除時に CIFS サーバーが削除され、`data-cifs` が失われます。** CLI で作り直すとこの状態に入ります |

> **設計に関する補足**: **CIFS サーバーを削除する操作は、サービスポリシーを壊す操作でもあります。**
> AD 構成の解除も含みます。削除と再作成を伴う手順書では、**再作成を ONTAP REST で行う**か、
> 完了後に `services` を確認する手順を入れてください。

---

## 併せて当たる上限

**SVM を作り直す方針は不要になりましたが**、他の理由で SVM を増やす場合はスループット容量あたりの上限に当たります。

```text
ServiceLimitExceeded: Amazon FSx does not support having more than 6 storage virtual machines
for an ONTAP file system with 128 MBps of throughput capacity.
```

課金に影響するため、スループット容量の変更を伴う判断は先に確認してください。

---

## 未確認

- **段階 3〜5 の因果と復旧手順**。AWS サポートの回答内容で、**当方では実行していません。** 共有ファイルシステム上で CIFS サーバーを削除する必要があるため、使い捨ての SVM を用意していません
- **当方の該当 SVM で過去に CIFS サーバーの削除が行われたか**。現在の状態は機構と整合しますが、**削除の履歴を確認する手段がありません。** 検証中に 1 件の SVM でワークグループ CIFS サーバーを作成・削除した記録はありますが、`data-cifs` が失われたのがその前か後かを特定できていません
- **FSx for ONTAP 以外の ONTAP で同じ挙動になるか**。AWS サポートは「ONTAP 側の処理であり FSx for ONTAP 固有ではない」との見解で、オンプレミス ONTAP での再現確認と NetApp 側でのナレッジ化を提案しています。**未実施です**
- **ONTAP CLI で作成した場合に `data-cifs` が復元されない理由**。CLI と REST で処理経路が異なることは示されていますが、設計上の意図かは分かりません
- **`data-cifs` が無い SVM に AD 設定を後から追加した場合の挙動**。Amazon FSx 経由の AD 参加が CIFS サーバーを作成するため復元される可能性がありますが、測っていません

---

## 参照した一次情報

- AWS: [NetApp アプリケーションを使用した FSx for ONTAP リソースの管理](https://docs.aws.amazon.com/ja_jp/fsx/latest/ONTAPGuide/managing-resources-ontap-apps.html) — `fsxadmin` での ONTAP REST 利用
- AWS re:Post: [FSx for ONTAP REST API を使用するにはどうすればよいですか?](https://repost.aws/ja/knowledge-center/fsx-ontap-rest-apis)
- NetApp KB: [Command fails with "Command is not recognized command"](https://kb-ja.netapp.com/on-prem/ontap/Ontap_OS/OS-KBs/Command_fails_with_Command_is_not_recognized_command)

**`data-cifs` が CIFS サーバーの削除で失われることを説明した公開情報は、本ノート作成時点で見つかっていません。** AWS サポートもドキュメントまたはナレッジとしての公開を検討中の段階です。**提出は公開ではないため、未記載の挙動として扱ってください。**

---

## 関連

- [SMB ローカルユーザーに最終ログオン属性は無い](local-user-inventory-without-last-logon.md)
- [AD への依存は参加時ではなく生涯続く](ad-dependency-lasts-the-lifetime.md)
- [セキュリティスタイルが権限評価のモデルを決める](security-style-and-permission-evaluation.md)
- [上限値・クォータ](../../../reference/limits/README.md)
