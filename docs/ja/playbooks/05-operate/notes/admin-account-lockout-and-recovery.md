---
title: fsxadmin はロックされる。REST では原因が判別できず、復旧はパスワード再設定に限られる
lifecycle: [operate]
domains: [security-governance]
evidence: verified
verified_on: 2026-09-01
ontap_version: 9.18.1P3D1
region: ap-northeast-1
lang: ja
---

# fsxadmin はロックされる。REST では原因が判別できず、復旧はパスワード再設定に限られる

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 05 — 運用](../README.md)

---

## 結論

**`fsxadmin` は失敗ログインの蓄積でロックされます。** そして **ロックとパスワード誤りは、REST から見ると同じ `401` です。**

```text
（SSH — 区別できる）
fsxadmin@<management-ip>'s password:
Error: Account currently locked. Contact the storage administrator to unlock it.

（REST — 区別できない）
GET /api/cluster
→ HTTP 401  {"error":{"code":"6691623","message":"User is not authorized."}}
```

**認証情報が正しいのに `401` が返ります。** REST だけで運用していると、格納しているパスワードが古いのか、アカウントがロックされているのかが判定できません。**先に SSH を 1 回試してメッセージを読むのが最短の切り分けです。**

**復旧は Amazon FSx API のパスワード再設定だけです。** ONTAP の `security login unlock` は管理者ログインを要するため循環します。そして **再設定はロックも解除しました**（実測）。

> **Evidence**: `verified`（2026-09-01、`ap-northeast-1`、ONTAP `9.18.1P3D1`）。
> ロック状態の 1 ファイルシステムで、SSH と REST の両方の応答を確認し、`UpdateFileSystem` による
> パスワード再設定の前後で SSH ログインの成否を測りました。**ロックに至る失敗回数の閾値と、
> 時間経過による自動解除の有無は測っていません**（後述）。

---

## ロックに至る経路と、複数ファイルシステム運用の危険

**`fsxadmin` はファイルシステムごとに独立したアカウントですが、ユーザー名は共通です。** 複数のファイルシステムを 1 つのアカウントで運用している場合、**認証情報を取り違えると、別のファイルシステムの実アカウントに失敗ログインが記録されます。**

SSH はログイン時に累積回数を表示します。

```text
FsxIdEXAMPLE::> version
Unsuccessful login attempts since last login: 7
NetApp Release 9.18.1P3D1: ...
```

**この行が出ていたら、誰かが（あるいは何かの自動化が）失敗し続けています。** 放置するとロックに至ります。

| 対策 | 内容 |
|---|---|
| シークレットに対象を書く | どのファイルシステム専用かを説明欄に明記する。ユーザー名が同じなので、値だけでは判別できません |
| 総当たりを避ける | 「どちらのシークレットか分からないので両方試す」は、片方に必ず失敗ログインを積みます |
| 失敗回数を確認する | SSH ログイン時の `Unsuccessful login attempts` を読む。REST では表示されません |

> **運用に関する補足**: 認証情報が分からない状態で試行を重ねるのは、**調査ではなく障害の作成**です。
> 1 回失敗したら、次の 1 回を投げる前に「どのファイルシステム用の値か」を確定させてください。

---

## 復旧手順

```bash
# 1. 新しいパスワードを再設定する（ロック解除も兼ねる）
aws fsx update-file-system --file-system-id <fs-id> \
  --ontap-configuration FsxAdminPassword=<new-password>

# 2. 保管先も同じ値に更新する（順序を逆にしないこと）
aws secretsmanager put-secret-value --secret-id <secret> \
  --secret-string '{"username":"fsxadmin","password":"<new-password>"}'

# 3. SSH で 1 回ログインして解除を確認する
```

**手順 1 と 2 は必ずこの順序で、かつ両方成功したことを確認してください。** 検証中に、シークレット更新だけが成功してファイルシステム側の再設定がコマンドエラーで失敗した瞬間がありました。**この状態は「格納値と実際が食い違っている」ため、次に読んだ自動化が失敗ログインを積みます。** 片方だけ成功した場合は、成功した側に合わせて即座に是正してください。

パスワードは ONTAP のロール設定に従う必要があります。要件は `security login role config show -role fsxadmin` で確認できます。

> **セキュリティに関する補足**: 再設定は共有リソースの認証情報の変更です。**同じシークレットを読む
> 他の自動化がある場合、シークレットを更新するまでその自動化は失敗します。** 実行前に参照元を
> 洗い出してください。Secrets Manager の `LastAccessedDate` が手がかりになります。

---

## 事前に決めておくこと

| 項目 | 理由 |
|---|---|
| SSH 経路の確保 | REST だけではロックを判別できません。管理 LIF の 22 番に到達できる経路を用意しておく |
| シークレットの命名と説明 | ユーザー名が共通なので、対象ファイルシステムが値から分かりません |
| 再設定の承認経路 | 共有ファイルシステムの認証情報変更にあたるため、実行者の判断だけで進めない構成にする |
| `vsadmin` の準備 | SVM 単位の作業に `fsxadmin` を使わなければ、失敗ログインの機会自体が減ります（[管理者の分離](../../../domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md#権限設計--管理者の分離)） |

---

## 未確認

- **ロックに至る失敗回数の閾値。** 観測できたのは「7 回の失敗が記録された状態でログインできた」ことと、別のファイルシステムがロック済みだったことだけです。閾値は測っていません
- **時間経過による自動解除の有無。** ロック状態を放置して再試行する検証はしていません
- **`vsadmin` が同じ挙動をするか。** 測っていません。`vsadmin` のパスワード再設定は `UpdateStorageVirtualMachine` で可能ですが、ロック解除を兼ねるかは未確認です
- **ロック解除がパスワード再設定の副作用か、明示的な仕様か。** AWS / NetApp のドキュメントに記載を見つけられていません。**再設定でロックが解除されたのは 1 回の観測です**

---

## 参照した一次情報

- AWS: [Updating the fsxadmin account password](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/updating-admin-password.html)

---

## 関連

- [権限設計 — 管理者の分離](../../../domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md#権限設計--管理者の分離)
- [IaC の境界は API の表面で決まる](../../04-build/notes/what-iac-cannot-reach.md)
- [不可逆な操作の承認は作業の承認とは別に取る](../../../domains/security-governance/notes/irreversible-operations-need-separate-approval.md)
