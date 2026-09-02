---
title: fsxadmin はロックされる。REST では原因が判別できず、復旧はパスワード再設定に限られる
lifecycle: [operate]
domains: [security-governance]
evidence: verified
verified_on: 2026-09-02
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
> パスワード再設定の前後で SSH ログインの成否を測りました。**閾値と自動解除の有無は、ロールの
> 設定値を読み取って確認しています**（[後述](#閾値と自動解除の設定値)）— 意図的にロックさせた
> わけではありません。

---

## ロックに至る経路と、複数ファイルシステム運用の危険

**`fsxadmin` はファイルシステムごとに独立したアカウントですが、ユーザー名は共通です。** 複数のファイルシステムを 1 つのアカウントで運用している場合、**認証情報を取り違えると、別のファイルシステムの実アカウントに失敗ログインが記録されます。**

**許容される失敗は 5 回で、時間が経っても戻りません**（[設定値](#閾値と自動解除の設定値)）。SSH はログイン時に累積回数を表示します。

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

### 正しいパスワードでもロックさせられること

**上の経路は「値を取り違えた場合」ですが、正しい値を使っていてもロックできます。** 2026-09-02 に実際にやりました。

| 時刻（UTC） | 事象 |
|---|---|
| `06:00:57` | シークレットの値で認証成功。`Account Locked: no`、失敗回数の表示なし（= 0 回） |
| `06:03` 頃 | SSM ポートフォワード経由の SSH が応答せず、120 秒でタイムアウト |
| `06:07:19` | `nc` はポートが開いていると応答。直後の `ssh` は `Connection refused` |
| `06:08:27` | **`Account currently locked.`** |

**同じ窓で使ったパスワードは、直前に認証が成功した正しい値です。** 経路が不安定なまま認証を投げ直したことが、失敗回数の側に積まれたと考えるほかありません。**閾値は 5 回で自動解除は無いため、数回の再試行で到達します。**

| 誤解 | 実際 |
|---|---|
| 正しいパスワードなら失敗回数は増えない | **増え得ます。** 認証が完了せずに切れた試行が積まれます |
| `nc` でポートが開いていれば経路は使える | **なりません。** 開いている応答の直後に `Connection refused` になりました |
| ロックの調査は無害 | **調査が原因になり得ます。** ロック中のアカウントは ONTAP 側のログも読めず、切り分け手段が同時に失われます |

> **運用に関する補足**: **不安定な踏み台・ポートフォワード越しに管理者認証を繰り返さないでください。**
> トンネルを張り直したら、認証の前に**時間を空けた複数回のポート確認**で安定を確かめ、**認証は 1 回だけ**
> 投げます。失敗したら原因が経路か資格情報かを切り分けるまで次を投げないでください。
> 経路が疑わしいときは、SSH より **REST の 1 リクエスト**のほうが試行回数を制御しやすいです。

### 誰がシークレットを読んでいるかの特定

**`LastAccessedDate` は日単位なので、5 分間隔の自動化を追うには粗すぎます。** CloudTrail の `GetSecretValue` を引くと、時刻・呼び出し元・対象シークレットが揃います。

```bash
aws cloudtrail lookup-events --region <region> \
  --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue \
  --start-time <iso8601> --query 'Events[].CloudTrailEvent' --output text
```

**そして「シークレットを読んでいること」は「認証していること」ではありません。** 実測では、5 分間隔で両方の `fsxadmin` シークレットを読む Lambda が見つかりましたが、その実行ログは毎回「処理対象 0 件」で終わっており、**ONTAP へ認証した形跡はありませんでした。** 読み取り元を犯人と決める前に、その処理のログで認証まで到達しているかを確認してください。

---

## 復旧手順

```bash
# 1. 新しいパスワードを再設定する（ロック解除も兼ねる）
aws fsx update-file-system --file-system-id <fs-id> \
  --ontap-configuration FsxAdminPassword=<new-password>

# 2. 保管先も同じ値に更新する（順序を逆にしないこと）
aws secretsmanager put-secret-value --secret-id <secret> \
  --secret-string '{"username":"fsxadmin","password":"<new-password>"}'

# 3. 反映完了を待ってから、認証を 1 回だけ試す
aws fsx describe-file-systems --file-system-ids <fs-id> \
  --query 'FileSystems[0].AdministrativeActions[0].Status'   # COMPLETED になるまで待つ
```

**手順 3 で待たずに試すと、失敗ログインを 1 回消費します。** `Lifecycle` は `AVAILABLE` のまま `PENDING` → `IN_PROGRESS` → `COMPLETED` と進むため、**`AVAILABLE` を反映完了の合図として使えません。** 実測では投入から `COMPLETED` まで約 44 秒でした（`06:17:36` → `06:18:19`）。

確認は SSH でも REST でもかまいませんが、**REST なら 1 リクエストで済み、`locked` の値も同時に読めます。**

```bash
curl -sk --user fsxadmin:<new-password> \
  'https://<mgmt-lif>/api/security/accounts?name=fsxadmin&fields=locked'
# -> "locked": false
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

## 閾値と自動解除の設定値

**アカウントをロックさせずに、ロール設定から読み取れます。** advanced 特権の `-instance` 表示に含まれます。

```text
FsxIdEXAMPLE::> set -privilege advanced -confirmations off
FsxIdEXAMPLE::> security login role config show -role fsxadmin -instance
                  Maximum Number of Failed Attempts: 5
       Delay after Each Failed Login Attempt (Secs): 4
Account Lockout Duration (ISO 8601 Duration Format): -
         (DEPRECATED)-Maximum Lockout Period (Days): 0
                   Minimum Password Length Required: 8
                             Password Alpha-Numeric: enabled
                         Disallow Last 'N' Passwords: 6
                         Password Expires In (Days): unlimited
```

| 項目 | 値 | 意味 |
|---|---|---|
| `Maximum Number of Failed Attempts` | **5** | この回数の失敗でロックされます |
| `Delay after Each Failed Login Attempt` | **4 秒** | 失敗するたびに遅延が入ります。総当たりは遅くなりますが、**回数は積まれます** |
| `Account Lockout Duration` | **未設定（`-`）** | **時間経過による自動解除がありません。** 放置しても戻りません |

**5 回で止まる、そして自動では戻らない。** つまり「どのシークレットか分からないので順に試す」は、2 つのシークレットを持つ環境では容易に到達します。**そして戻す手段はパスワード再設定だけです。**

`Disallow Last 'N' Passwords: 6` があるため、再設定では直近 6 世代と同じ値を使えません。復旧手順を自動化する場合は毎回新しい値を生成してください。

> **注意**: 上記は検証環境（`ap-northeast-1`、ONTAP `9.18.1P3D1`）の値です。**設定値であって
> 仕様上の固定値ではありません。** 自環境では同じコマンドで確認してください。

---

## 未確認

- **ロックまでの回数が実際に 5 回であること。** 設定値を読み取っただけで、意図的に 5 回失敗させて確認したわけではありません（共有ファイルシステムのため実施していません）
- **`vsadmin` が同じ挙動をするか。** 測っていません。`vsadmin` のパスワード再設定は `UpdateStorageVirtualMachine` で可能ですが、ロック解除を兼ねるかは未確認です
- **ロック解除がパスワード再設定の副作用か、明示的な仕様か。** AWS / NetApp のドキュメントに記載を見つけられていません。**再設定でロックが解除されたのは 2 回の観測です**（2026-09-01、2026-09-02）。2 回とも成功していますが、仕様として保証されているかは確認できていません
- **中断された認証試行が失敗回数に積まれること。** 正しいパスワードでロックに至った経路（上記）から**そう解釈するほかない**という状態で、**ONTAP 側のカウンタが実際に何を数えているかは確認できていません。** ロック中は当該ファイルシステムのログを読めず、解除するとカウンタが 0 に戻るため、事後の確認手段がありません
- **`Account Lockout Duration` を設定した場合の挙動。** 既定が未設定であることは確認しましたが、値を入れて自動解除させる検証はしていません

---

## 参照した一次情報

- AWS: [Updating the fsxadmin account password](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/updating-admin-password.html)

---

## 関連

- [権限設計 — 管理者の分離](../../../domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md#権限設計--管理者の分離)
- [IaC の境界は API の表面で決まる](../../04-build/notes/what-iac-cannot-reach.md)
- [不可逆な操作の承認は作業の承認とは別に取る](../../../domains/security-governance/notes/irreversible-operations-need-separate-approval.md)
