---
title: FlexCache の書き込みが通らないとき、原因は Origin の NFS 権限か、無認証ピアの解除不能という設計上の制約にある
lifecycle: [design, build, operate]
domains: [performance, client-access, data-protection]
evidence: documented
source: https://docs.netapp.com/us-en/ontap/nfs-admin/ontap-secures-file-directory-access-concept.html
ontap_version: 9.18.1P6
lang: ja
---

# FlexCache で「読めるのに書けない」ときに最初に見るところ

Origin 側（Amazon FSx for NetApp ONTAP）の NFS 権限を見ます。export-policy が書き込みを許していても、ボリュームの UNIX パーミッションと所有者が合っていなければ、一般ユーザーの書き込みは拒否されます。

## このノートで学べること

- Cache から読めるのに書けないとき、Origin 側のどの設定を順に確認するか。
- export-policy の `RW Access Rule` と、ボリュームの UNIX パーミッション・所有者が、別々に効くこと。
- cluster peering を無認証モード（`-no-authentication true`）で張ると、無認証ピアが残る間はクラスタ全体のポリシーを認証必須へ戻せない、という設計上の制約。
- FSx for ONTAP では IPspace が `Default` のみで、`cluster peer create` の `-ipspace` に指定する値が `Default` であること。
- ピアのクラスタ名を取る引数の綴りが、コマンドによって違うこと（`cluster peer delete` は `-cluster`、`vserver peer permission create` は `-peer-cluster`）。

## このノートが答えないこと

- FlexCache 越しの書き込み性能や、Origin 更新時のキャッシュ整合の数値。整合の仕組み自体は NetApp のドキュメントにあり、本文で出典を示します。
- 無認証ピアそのもののセキュリティ評価を、特定環境のリスク受容として判断すること。
- SMB / NFSv4.x ACL でのアクセス制御（本ノートは NFSv3 + UNIX セキュリティスタイルが対象）。

## 前提レベル

intermediate

## 本文

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 性能](../README.md)

---

### 結論

**FlexCache の Cache からデータを読めるのに書き込みだけが失敗するとき、Origin 側の NFS 権限を疑います。** FlexCache の Cache ボリュームは読み書き可能で、write-around（既定）では書き込みが Origin に転送されて確定します（[AWS: Replicating your data with FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html)）。したがって「Cache が読み取り専用だから書けない」という構図ではなく、Origin 側のアクセス制御が書き込みを拒否しているか、クライアント側のマウントが読み取り専用か、のどちらかです。

切り分けの要点は、**export-policy が書き込みを許していても、ボリュームの UNIX パーミッションと所有者が合っていなければ一般ユーザーは書けない**ことです。この 2 つは別々に効きます。

> **区分**: `documented` — NetApp の ONTAP ドキュメントは、ONTAP が最大 3 層（export／share、Storage-Level Access Guard、ファイル／ディレクトリ自身の権限）を評価し、有効な権限は 3 層の評価結果で決まると定めています。ファイル自身の権限は、SMB と NFS のどちらで届いても有効です。（出典: [NetApp: Learn about file-based restrictions for ONTAP NAS SVMs](https://docs.netapp.com/us-en/ontap/nfs-admin/ontap-secures-file-directory-access-concept.html)、2025-05-28 更新の版を2026-11-03 に読みました。このノートの「次のような組み合わせ」は、この定めから導いた説明です。実機で再現した記録は、このノートの根拠にしていません。）

---

### 書き込みが拒否される 2 つの面

NFS の書き込み可否は、次の 2 つが**両方**成立して初めて通ります。片方だけでは書けません。

| 面 | 確認するもの | 書けないときの典型 |
|---|---|---|
| export-policy | Origin volume に適用された export-policy の `RW Access Rule` が、クライアントの範囲に対し許可（`any` など）か | `RW Access Rule` が `never` のポリシー（SVM ルートボリューム用の既定ポリシーなど）が付いている |
| UNIX パーミッション / 所有者 | ボリュームと配下ディレクトリの `unix-permissions`・`user`・`group` | 所有者が `root`、モードが `755` で、書き込むのが一般ユーザー。その他ユーザーには書き込みビットがない |

たとえば、Origin volume に付いた export-policy が `RW Access Rule: any`（`0.0.0.0/0`）で書き込みを許可していても、ボリュームと配下の所有者が `root`、モードが `755` なら、一般ユーザーの書き込みは UNIX パーミッションで拒否されます。`755` で書けるのは所有者だけで、その他のユーザーは読み取りと実行しかできないためです。Cache を一般ユーザーでマウントして書いても、同じ理由で拒否されます。export-policy を見ただけでは原因にたどり着けません。

> **設計上の補足**: Origin volume のセキュリティスタイル（NFS 本線では unix）は Cache 側に引き継がれ、Cache 側では変更できません。アクセス制御は Origin 側で設計します。

---

### 確認の順序

Cache から読めるのに書けないとき、Origin 側（FSx for ONTAP）を次の順で読み取り確認します。いずれも read-only です。

```console
# 1. Origin volume の種別・セキュリティスタイル・所有者・モード・適用 export-policy
volume show -vserver <origin-svm> -volume <origin-volume> \
  -fields policy,security-style,unix-permissions,user,group,type,junction-path

# 2. SVM の export-policy 一覧
vserver export-policy show -vserver <origin-svm>

# 3. 各 export-policy rule の RO/RW Access Rule とクライアント範囲
vserver export-policy rule show -vserver <origin-svm> -instance
```

判定:

- 手順 1 の `policy` が指す export-policy の `RW Access Rule`（手順 3）が、クライアント範囲に対し許可か。`never` なら export-policy 側で拒否。
- 手順 1 の `unix-permissions` と `user`/`group` が、書き込むユーザーに書き込みを許すか。`755` + `root` 所有で一般ユーザーが書くなら、ここで拒否。
- クライアント側（Cache をマウントするホスト）のマウントが `ro` でないか。これは Origin 側ではなく、マウントオプションの問題。

---

### 権限の直し方

**どの面が原因かで直す場所が変わります。** UNIX パーミッションが原因なら Origin 側で直します。Cache に書いた内容は write-around で Origin に反映されるため、所有権・モードは Origin volume の真実として設計します。

| 原因 | 直す場所 | 例 |
|---|---|---|
| マウントが `ro` | クライアント（Cache 側ホスト） | `rw` でマウントし直す。Origin は無関係 |
| UNIX パーミッション / 所有者 | Origin volume | 書き込ませたいユーザーの UID/GID に合わせる、または対象ディレクトリにグループ書き込みを付ける |
| export-policy の `RW Access Rule` | Origin（または Cache）の export-policy | クライアント範囲に RW を許可する rule を、範囲を絞って追加 |

UNIX 所有者を特定ユーザーに合わせる場合、ONTAP は所有者を名前ではなく UID/GID の数値で持ちます。クライアント側で `id <user>` の `uid`/`gid` を確認し、その数値で設定します。名前解決には SVM 側の LDAP / NIS / ローカル UNIX ユーザー設定が要るため、数値指定が設定に依存せず確実です。

> **セキュリティに関する補足**: ボリューム全体を誰でも書ける状態（`777`）にするのは切り分けには有効ですが、恒久設定には向きません。実運用では、書き込ませたいユーザーの所有に絞り、モードを `755` など必要最小に戻します。`0.0.0.0/0` を RW に開く export-policy も検証限定で、本番ではクライアント CIDR に絞ります。

---

### cluster peering を無認証で張るときの設計上の制約

FlexCache の前提となる cluster peering は、通常はパスフレーズで相互認証します。相手側がパスフレーズの対話入力を扱えない環境では、無認証モード（`-no-authentication true`）で張ることがあります。このとき、**解除できなくなる設計上の制約**があります。

> **区分**: `field-observation` — 1 回観測、再現は未確認です。2026-10-29、ONTAP 9.18.1P6 の FSx for ONTAP で、無認証ピアが存在する状態で `cluster peer policy modify -is-unauthenticated-access-permitted false` を実行したところ、ONTAP が拒否しました。エラー文は逐語ではなく趣旨を記録しています。拒否された理由は、次の `documented` の記述と一致します。

`cluster peer policy modify -is-unauthenticated-access-permitted false` は、無認証の関係が 1 つでも残っていると ONTAP が拒否します。これは NetApp のコマンドリファレンスにも記載があります。

> **区分**: `documented` — NetApp ONTAP コマンドリファレンス `cluster peer policy modify`（2026-10-06 版）に次の記載があります。逐語引用（30 語未満）: "Setting the value to false is not possible if the cluster currently is in any unauthenticated relationships."（出典: <https://docs.netapp.com/us-en/ontap-cli/cluster-peer-policy-modify.html>）

設計上の含意は 3 つです。

- **このポリシーはクラスタ全体の設定**で、特定ピア単位ではありません。無認証ピアを 1 つ作ると、そのクラスタのポリシーは無認証許可のままになります。
- **戻すには、先に無認証ピアを削除**する必要があります。認証必須へ戻すのは、無認証の関係がゼロになった後です。
- 既存の認証付きピアを無認証へ切り替える方向は容易でも、**逆方向（無認証 → 認証必須のポリシー）は、無認証ピアが残る限り不可**です。認証付きに戻すには `cluster peer modify -auth-status-admin use-authentication` でパスフレーズ交換をやり直す必要があり、両クラスタでの操作が要ります（[NetApp: cluster peer modify](https://docs.netapp.com/us-en/ontap-cli/cluster-peer-modify.html)）。

> **セキュリティに関する補足**: 無認証ピアではクラスタピア間の認証がなく、ピア間暗号化も `none` になります。到達範囲はセキュリティグループと intercluster LIF（TCP 11104-11105）で絞られますが、認証の欠如そのものは残ります。無認証で張る場合は、利用終了時にピアを削除してポリシーを戻す撤去手順を設計に含めます。

---

### ピアのクラスタ名を取る引数の綴りの、コマンド間の差

無認証でピアを作り直すとき、相手から渡された手順の `cluster peer delete -peer-cluster <name>` が通りませんでした。

> **区分**: `field-observation` — 1 回観測、再現は未確認です。2026-10-29、ONTAP 9.18.1P6 の FSx for ONTAP で、`cluster peer delete -peer-cluster <name>` は引数エラー（`invalid argument`）になり、`cluster peer delete -cluster <name>` で削除できました。

原因は、ピアのクラスタ名を取る引数の綴りがコマンドごとに違うことです。NetApp のコマンドリファレンスが、この違いを定めています。

> **区分**: `documented` — `cluster peer delete` の引数は `-cluster <text>` です（[NetApp: cluster peer delete](https://docs.netapp.com/us-en/ontap-cli/cluster-peer-delete.html)、2026-10-06 版）。一方、`vserver peer permission create` の引数は `-peer-cluster <text>` です（[NetApp: vserver peer permission create](https://docs.netapp.com/us-en/ontap-cli/vserver-peer-permission-create.html)、同版）。2026-11-03 に両ページを全文で読みました。

| コマンド | ピアのクラスタ名を取る引数 |
|---|---|
| `cluster peer delete` | `-cluster <name>` |
| `vserver peer permission create` | `-peer-cluster <name>` |

`-peer-cluster` を `cluster peer delete` に渡したことが原因と読めますが、他のバージョンで通るかどうかは確認していません。手順書を書き写すときは、コマンドごとに引数の綴りをリファレンスと突き合わせます。

ピアを削除すると、そのピアに紐づく `vserver peer permission` も消えます。無認証で張り直した後は、`vserver peer permission create -vserver <svm> -peer-cluster <name> -applications flexcache` を再作成します。

---

### cluster peer create の -ipspace に Default を指定して成功した例

`cluster peer create` の `-ipspace` に何を指定すべきか迷う場合の、1 件の事例です。

> **区分**: `field-observation` — 1 回観測、再現は未確認です。2026-10-29、ONTAP 9.18.1P6 の FSx for ONTAP で、`cluster peer create -peer-addrs <相手の intercluster LIF 2 つ> -ipspace Default` を実行し、ピアが `Available` になりました。同じ FSx for ONTAP の intercluster LIF の属性表示にも `IPspace Name: Default` がありました。

このノートが言えるのは、ここまでです。次の 2 点は確認していないので、書きません。

- この FSx for ONTAP に `Default` 以外の IPspace が存在するかどうか（`network ipspace show` の出力を保管していません）。
- すべての SVM と intercluster LIF が `Default` に属するかどうか。

`-ipspace` に指定する値は、自分の環境で `network interface show -by-ipspace` を実行し、intercluster LIF がどの IPspace に属するかを見てから決めます（[NetApp: network interface show](https://docs.netapp.com/us-en/ontap-cli/network-interface-show.html)、2026-10-06 版は `-by-ipspace` を「IPspace と Vserver で並べて表示する」と定めています）。

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| Cache が読み取り専用だから書けない | **Cache は読み書き可能。** write-around で書き込みは Origin に転送されて確定する（[AWS FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html)） |
| export-policy で RW が許可されていれば書ける | **UNIX パーミッションと所有者も合う必要がある。** `755` + `root` 所有だと一般ユーザーは書けない |
| 書き込み権限は Cache 側で直す | **Origin 側で直す。** セキュリティスタイルと所有権は Origin から Cache に引き継がれ、Cache 側では変えられない |
| 無認証ピアは特定ピアだけの設定 | **クラスタ全体のポリシー。** 無認証ピアが 1 つ残ると認証必須へ戻せない |
| 無認証許可はいつでも false に戻せる | **無認証ピアを削除してからでないと戻せない。** ONTAP が拒否する（[cluster peer policy modify](https://docs.netapp.com/us-en/ontap-cli/cluster-peer-policy-modify.html)） |
| `-ipspace` には既定の値があり、確かめなくてよい | **intercluster LIF が属する IPspace を `network interface show -by-ipspace` で確かめてから指定する。** 1 件の事例では `Default` で成功した（上の `field-observation`）が、すべての環境に当てはまるとは確認していない |

---

### 参照した一次情報

| 論点 | 出典 |
|---|---|
| FlexCache の write-around / write-back、Cache が読み書き可能であること、write-back は 9.15.1 以降 | [AWS: Replicating your data with FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html) |
| 無認証ピアが存在する間は認証必須ポリシーへ戻せない旨 | [NetApp: cluster peer policy modify](https://docs.netapp.com/us-en/ontap-cli/cluster-peer-policy-modify.html) |
| 認証付きへ戻す手順（`-auth-status-admin use-authentication`）と両クラスタでの反映 | [NetApp: cluster peer modify](https://docs.netapp.com/us-en/ontap-cli/cluster-peer-modify.html) |
| FlexCache の作成手順（LIF 収集・cluster peering・SVM peering・Cache 作成） | [AWS: Creating a FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-flexcache.html) |
| FSx for ONTAP の export-policy 設計 | [AWS Storage Blog: Restrict access using export policies](https://aws.amazon.com/blogs/storage/restrict-access-to-your-amazon-fsx-for-netapp-ontap-volumes-using-export-policies) |

---

### 関連ドキュメント

- [Domain — 性能](../README.md) — このモジュールのハブ
- [FlexCache CLI 手順 (NFS編) – 簡易版](../../../reference/flexcache-cli-nfs-simplified.md) — 作成手順の最短経路
- [FlexCache とストレージチューニングの NetApp 一次資料マップ](../../../reference/netapp-primary-sources-map.md) — 設計・運用時に読む TR / ベストプラクティスへの導線
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 性能](../README.md)
