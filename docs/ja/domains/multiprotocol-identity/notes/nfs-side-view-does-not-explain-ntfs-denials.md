---
title: NTFS スタイルのボリュームでは、NFS 側から見える権限表現が実際の可否と一致しない — Deny も主体名も現れない
lifecycle: [design, migrate, operate]
domains: [multiprotocol-identity, security-governance]
evidence: verified
verified_on: 2026-09-12
region: ap-northeast-1
ontap_version: 9.18.1P6
lang: ja
---
# NTFS スタイルのボリュームでは、NFS 側から見える権限表現が実際の可否と一致しない
<!-- lang-switcher:start -->
🌐 [日本語](nfs-side-view-does-not-explain-ntfs-denials.md) | [English](../../../../en/domains/multiprotocol-identity/notes/nfs-side-view-does-not-explain-ntfs-denials.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — マルチプロトコル・ID](../README.md)

---

## 結論

**同じデータに NFS から到達できることと、NFS 側から権限を説明できることは別です。** NTFS
セキュリティスタイルのボリュームでは、`nfs4_getfacl` が返すのは合成された 3 エントリ
（`OWNER@` / `GROUP@` / `EVERYONE@`）だけで、**Deny ACE も、ACE を付けた主体名も、継承フラグも
現れません**。

実測では、その表現が実際の可否と**矛盾**しました。NFSv4 ACL は `OWNER@` に書き込みを許可すると
表示し、ONTAP はそのディレクトリの owner を当のテストユーザーだと報告し、それでもそのユーザーの
書き込みは拒否されました。

さらに悪いことに、**NTFS スタイルの拒否されるディレクトリと、UNIX スタイルの書き込めるディレク
トリが、mode bits も NFSv4 ACL も完全に同一でした**。NFS 側の表現だけでは、この 2 つを区別でき
ません。

### 使える答えの所在

**ONTAP の `effective-permissions` は、実測した全ケースで実際の可否と一致しました。** 拒否された
ディレクトリでは返る一覧から `write` / `append` / `write_ea` / `write_attributes` が落ち、許可された
ディレクトリでは含まれていました。**「NFS 側から答えられない」は「答えがない」ではありません。**
確認の経路をストレージ側に移せば、両ベンダーが文書化している API で答えられます。

ただし**その経路には ONTAP の資格情報が必要です。** いま `ls -l` で確認している担当者が、そのまま
移行後の確認を続けられるとは限りません。**誰がその資格情報を持つかを移行前に決めてください。**

判定の順序は [プロトコルを変えたあと「誰がこのファイルにアクセスできるか」をどこで確認するか](../../../reference/decision-trees/verifying-permissions-after-a-protocol-change.md)
にまとめてあります。

### 明日から変えること

| # | 対象 | 理由 |
|---|---|---|
| 1 | 権限確認の手続きに `ls -l` や `nfs4_getfacl` が**手段名で**書かれている箇所 | 移行後はその手段が答えになりません |
| 2 | NFS 側しか見えない担当者が権限変更を承認する経路 | 表現に Deny が現れないため、承認の根拠が得られません |
| 3 | mode bits を読んで判定している自動化 | **エラーを出さずに動き続け、答えだけが変わります。** 最も見つけにくい項目です |

> **Evidence**: `verified` — 下記「検証環境」の 1 環境での実測です。**一般的なサービス上限や、
> 他バージョン・他構成での再現を保証しません。** 判断に使う前に「自環境での確認手順」を実行して
> ください。
>
> **本ノートの測定は使い捨ての検証環境で、合成データに対して行いました。** 本番データ、実在の利用者、
> 実在の組織情報は含みません。規制対象のワークロードに適用する場合、ここにあるのは技術的な挙動の
> 記録であり、**法務・コンプライアンス・プライバシーの評価を代替しません。**

## 背景

モダナイゼーションでプロトコルを SMB から NFS へ変えたあと、運用は Linux 側から権限を確認しよう
とします。`ls -l` と `nfs4_getfacl` が使える以上、それで説明がつくと考えるのが自然です。

その前提が成り立ちません。NTFS スタイルのボリュームでは権限評価に使われるのは Windows の ACL で
あり、NFS クライアントに見える mode bits と NFSv4 ACL は **ONTAP が合成した射影**です。射影は
Deny を表現できず、主体を名前で持ちません。

## 詳細

### 3 点セットの記録

権限の結果は 3 つ揃って初めて使えます。設定した ACE / NFS 側の表現 / 実際の成否です。

**Part 1 — ONTAP REST で設定した ACE**（`POST /protocols/file-security/permissions/`）

| パス | ACE |
|---|---|
| `allow/` | `access_allow` `MPAD\mpadtest` = modify 相当、`apply_to` = this_folder |
| `deny/` | `access_deny` `MPAD\mpadtest` = write 系 4 ビット + `access_allow` = read 系 |
| `inherited/` | `access_allow` `MPAD\mpadtest`、`apply_to` = this_folder + sub_folders + files |
| `inherited/child` | 上記が `inherited: true` で到達（**継承は成立した**） |

3 つすべてに、ボリュームルートから継承された `Everyone` full control が併存していました。後述の
とおりこれは `allow/` の識別力を失わせますが、`deny/` の結果は失わせません。

**Part 2 / Part 3 — NFS 側の表現と実際の可否**（NFSv4.1、`sec=sys`、AD ユーザーで実行）

NTFS スタイル `/ntfsvol`:

| パス | mode bits | NFSv4 ACL | read | write |
|---|---|---|---|---|
| `allow/` | 777 | `A::OWNER@:rwaDxtTnNcCy` / `A:g:GROUP@:rwaDxtTnNcy` / `A::EVERYONE@:rwaDxtTnNcy` | ok | ok |
| `deny/` | **755** | `A::OWNER@:rwaDxtTnNcCy` / `A:g:GROUP@:rxtncy` / `A::EVERYONE@:rxtncy` | ok | **拒否** |
| `inherited/child` | 777 | `allow/` と同一 | ok | ok |

UNIX スタイル `/unixvol`（対照群、Windows ACE は一切設定していない）:

| パス | mode bits | NFSv4 ACL | read | write |
|---|---|---|---|---|
| `allow/` | 755 | `A::OWNER@:rwaDxtTnNcCy` / `A:g:GROUP@:rxtncy` / `A::EVERYONE@:rxtncy` | ok | ok |
| `deny/` | 755 | 同上 | ok | **ok** |
| `inherited/child` | 755 | 同上 | ok | ok |

### 表現が可否を説明しない 3 つの形

1. **Deny が現れない。** NFSv4 ACL は `A:`（allow）3 件のみで、`D:`（deny）エントリは 1 件も
   ありません。書き込みを止めているのは Windows の Deny ACE です。
2. **主体名が現れない。** ACE を付けた相手は `MPAD\mpadtest` ですが、NFS 側には `OWNER@` /
   `GROUP@` / `EVERYONE@` しかありません。誰に対する権限なのかを NFS 側から知る方法がありません。
3. **NTFS の拒否と UNIX の許可が同一表現になる。** NTFS `deny/` と UNIX `deny/` は mode bits
   （どちらも 755）も NFSv4 ACL も一致し、結果は拒否と成功に分かれました。**表現が同じで結果が
   違うのだから、表現は判断材料になりません。**

### owner 表示が `nobody` になる別の落とし穴

クライアントは owner を `nobody(65534)` と表示しました。ONTAP は owner を `MPAD\mpadtest` と報告
しています。原因は NFSv4 の ID ドメイン不一致で、SVM の `v4_id_domain` は既定で
`<region>.compute.internal`（実測値 `ap-northeast-1.compute.internal`）であり、AD ドメイン名とは
一致しません。

これが 755 の解釈を壊します。`755` は「owner は書ける」と読めますが、owner が誰なのかをクライア
ントは解決できていません。**owner を解決できない状態の mode bits は、可否の説明として使えません。**

### name-mapping の replacement でバックスラッシュが消えること

**測定を始める前に、この 1 文字で全アクセスが拒否されました。** NTFS スタイルのボリュームでは
UNIX の UID を Windows のアカウントへ対応付ける必要があり、その規則の replacement に
`DOMAIN\user` を保存すると、**ONTAP は `\` をエスケープ文字として扱うため `DOMAINuser` になります。**

拒否のされ方が問題です。ONTAP のイベントログは次のように出しました。

```text
Determined UNIX id 675401149 is UNIX user 'mpadtest'
Mapping Successful for Unix-user 'mpadtest' to Windows user 'MPADmpadtest' at position 1
Could not find Windows name 'MPADmpadtest'
FAILURE: Name mapping for UNIX user 'mpadtest' failed
```

**規則自体は「成功」を報告し、その結果の名前の解決だけが失敗します。** そのためエラーは Active
Directory を指し、規則の書き方の問題だとは読めません。クライアント側の症状は `EACCES` で、
`opendir` も通らないため **`ls` すら失敗します**。この形は export policy の問題に見えますが、
export policy は正しい状態でした。

**GET による読み返しも助けになりません。** 保存された 1 個のバックスラッシュがそのまま返るため、
意図した値と区別できません。正しい保存値は**バックスラッシュ 2 個**で、ONTAP はそれを 1 個として
解釈します。

| | 送る値 | ONTAP の解釈 |
|---|---|---|
| 誤り | `MPAD\mpadtest` | `MPADmpadtest`（区切りが消える） |
| 正しい | `MPAD\\mpadtest` | `MPAD\mpadtest` |

**成立したかどうかは、規則を読み返すのではなく解決結果で判定してください。** 読み返しは誤った値でも
正しく見えます。判定に使える経路は 2 つです。

| 経路 | 見るもの |
|---|---|
| `GET /api/support/ems/events` を `secd` で絞る | `noNameMap` が出ていないこと。出ている場合、本文に ONTAP が試した名前が入っています |
| `GET /protocols/file-security/effective-permissions/{svm.uuid}/{path}?user=DOMAIN\user` | 権限一覧が返ること。**マッピングが成立していなければこの呼び出し自体が答えを返しません** |

2 つ目は測定にそのまま使う経路なので、**マッピングの確認を別途行う必要がありません。** 先にこれを
1 回叩けば、この節の失敗は測定前に検出できます。

### NFSv4 ACL は既定で無効

そもそも `nfs4_getfacl` は最初「Operation to request attribute not supported」を返しました。SVM の
NFS 設定で `v40_features.acl_enabled` と `v41_features.acl_enabled` が**どちらも既定で false**
だったためです。セキュリティスタイルとは無関係で、UNIX スタイルのボリュームでも同じでした。

有効化しても、**既存のマウントはネゴシエート済みの機能を持ち続けます。** 再マウントするまで属性は
`not supported` のままです。

なお `nfs4_getfacl` は「not supported」を出力しながら**終了ステータス 0 を返します**。`$?` だけを
見る記録は、読めていない表現を「読めた」と記録します。

## 検証環境

| 項目 | 値 |
|---|---|
| ONTAP バージョン | NetApp Release 9.18.1P6 |
| リージョン | ap-northeast-1 |
| 構成 | Single-AZ 第 1 世代、1,024 GiB SSD、128 MBps、AWS Managed Microsoft AD (Standard) |
| SVM ルートボリューム | UNIX セキュリティスタイル |
| 測定対象ボリューム | NTFS スタイル（`/ntfsvol`）／対照群は UNIX スタイル（`/unixvol`）|
| クライアント | Amazon Linux 2023、sssd で AD 参加、NFSv4.1 `sec=sys` |
| テストユーザー | AD ユーザー 1 名。`Domain Admins` **非メンバー**（primary group は `Domain Users` のみ）|
| 検証日 | 2026-09-12 |

> **注意**: 上記はこの環境での実測であり、一般的なサービス上限や本番環境での再現を保証するもの
> ではありません。

### 結果の限界（測定前に固定した判定に対して）

- `allow/` は識別力がありません。ボリュームルートから継承された `Everyone` full control が
  すでに書き込みを許可しているため、成功が ACE の効果だとは言えません。
- `deny/` は識別力があります。NTFS の評価順序で明示 Deny は Allow に優先するため、`Everyone`
  full control が併存していても拒否が観測できます。ONTAP の
  `effective-permissions` も `deny/` から `write` / `append` / `write_ea` / `write_attributes`
  を落として返しました。
- したがって本ノートの結論は `deny/` と対照群の比較に依拠しており、`allow/` には依拠していません。

## 未確定の項目

**測っていないことを列挙します。** 本ノートの結論はユーザー 1 名の ACE に対する実測で、以下は
いずれも同じ挙動になると推測できるだけで、確認していません。

| # | 未確定 | なぜ重要か |
|---|---|---|
| 1 | **グループに対する ACE**（1 つだけ測るならこれ） | 実運用の ACL はグループ単位です。グループの解決はユーザーの解決とは別経路で、入れ子グループやトークンサイズという固有の失敗面を持ちます。**本ノートはユーザー ACE のみの実測です** |
| 2 | サービスアカウントやコンテナの実行主体からのアクセス | ドメインユーザーではない主体が name-mapping をどう通るか未確認です。モダナイゼーションの現実的な経路なので、優先度は高いと考えています |
| 3 | 移行で持ち込んだボリューム | 実測は空のボリュームに作ったディレクトリに対するものです。既存 ACL を持つボリュームを移行した場合を測っていません |
| 4 | NFSv4 ACL を有効化した際の性能影響 | 有効化は本ノートの測定に必要でしたが、**性能への影響は測っていません。** 無償と仮定しないでください |
| 5 | ボリュームルートの継承 `Everyone` を外した場合 | 実測では `allow/` の識別力がこれで失われました。除去した状態での再測は未実施です |

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `GET /api/protocols/nfs/services/{svm.uuid}?fields=**` で `v41_features.acl_enabled` と `v4_id_domain` を読む | ACL が無効なら NFS 側の表現はそもそも読めない。ID ドメインが AD と違えば owner は `nobody` になる |
| 2 | NTFS スタイルのボリュームに、対象ユーザーへの明示 Deny ACE を `POST /protocols/file-security/permissions/{svm.uuid}/{path}` で付ける | 設定できたこと（Part 1） |
| 3 | NFS クライアントで `stat` と `nfs4_getfacl` を実行し、出力が `# file:` で始まることを確認する | 表現が読めたこと。終了ステータス 0 は根拠にならない |
| 4 | 同じユーザーで実際に書き込む | 可否（Part 3）。表現と食い違えば、食い違いが所見 |
| 5 | UNIX スタイルの対照ボリュームで 3 と 4 を繰り返す | 差が出なければ、それは環境についての所見であってスタイルについての所見ではない |

適用手順の全体像は [本番に取り入れる前の確認](../../../evidence-policy.md#本番に取り入れる前の確認)
を参照してください。

再現用の最小環境とスクリプトは
[`examples/multiprotocol-ad/`](../../../../../examples/multiprotocol-ad/README.md) にあります。

## よくある誤解

| 誤解 | 実際 |
|---|---|
| NFS から見えないなら権限が失われている | 失われていません。評価は Windows ACL で行われ、拒否は実際に効いています。見えないのは表現だけです |
| `nfs4_getfacl` が空なら ACL がない | 既定で ACL 属性自体が無効です。有効化し、さらに再マウントするまで読めません |
| `nfs4_getfacl` が終了コード 0 なら読めた | 「not supported」を出力しながら 0 を返します。出力が `# file:` で始まるかで判定してください |
| mode bits 755 なら owner は書ける | owner を解決できていない場合（`nobody` 表示）その読み方は成立しません。実測では owner 本人の書き込みが拒否されました |
| セキュリティスタイルを揃えれば表現も揃う | mode bits と NFSv4 ACL は NTFS 拒否と UNIX 許可で同一になりました。揃っているのは表現であって挙動ではありません |

## 関連ドキュメント

- [プロトコルを変えたあと「誰がこのファイルにアクセスできるか」をどこで確認するか](../../../reference/decision-trees/verifying-permissions-after-a-protocol-change.md) — **移行元の構成からの読み替え**。いまの確認手段が移行後も使えるかを判定します
- [ボリュームのセキュリティスタイルが権限評価のモデルを決める](security-style-and-permission-evaluation.md)
- [SMB で運用中のボリュームに NFS を足すのに複製は要らない](adding-a-protocol-does-not-need-a-clone.md)
- [`examples/multiprotocol-ad/`](../../../../../examples/multiprotocol-ad/README.md) — 再現環境
- [エビデンス方針](../../../evidence-policy.md)

<!-- lang-switcher:start -->
🌐 [日本語](nfs-side-view-does-not-explain-ntfs-denials.md) | [English](../../../../en/domains/multiprotocol-identity/notes/nfs-side-view-does-not-explain-ntfs-denials.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->
