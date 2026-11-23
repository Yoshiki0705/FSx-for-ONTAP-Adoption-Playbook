---
title: 第 1 世代では broadcast domain の MTU を REST と CLI のどちらでも変更でき、ONTAP 9.18.1P6 と 9.19.1P4 で結果は同じだった
lifecycle: [build, operate]
domains: [performance]
evidence: verified
verified_on: 2026-11-23
region: ap-northeast-1
ontap_version: 9.19.1P4
deployment_type: SINGLE_AZ_1
lang: ja
---
# 第 1 世代の FSx for ONTAP で、broadcast domain の MTU は変更できるか？

変更できます。ONTAP 9.19.1P4 の第 1 世代（`SINGLE_AZ_1`）で、REST と CLI（private CLI の REST 経由）のどちらでも、MTU を 1500、1300、1200 に変えて読み取りで確認し、9001 に戻しました。第 2 世代と第 3 世代は試していません。

## このノートで学べること

- broadcast domain の名前は `Default` ではなく `Fsx` で、`Default` は IPspace の名前であること
- 存在しない名前を CLI で指定すると、エラーにならず「対象 0 件」で HTTP 200 が返ること
- REST の変更は HTTP 200 と空の本文を返すだけなので、読み取りで確かめる必要があること
- 第 1 世代で ONTAP の版が 9.18.1P6 から 9.19.1P4 に上がっても、結果が変わらなかったこと

## このノートが答えないこと

- 第 2 世代と第 3 世代で MTU を変更できるか。試していません
- MTU を変更している間に、その broadcast domain に載る NFS、SMB、iSCSI の通信がどうなるか。測っていません
- 9001 以外の MTU が、スループットや遅延に与える影響

## 前提レベル

intermediate

## 本文

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 性能](../README.md)

---

### 結論

**第 1 世代のファイルシステムでは、MTU の値 1200 そのものも、ONTAP 9.18.1P6 から 9.19.1P4 への版の違いも、変更を拒否しませんでした。** 変更できない場合の原因として、この 2 つは外れます。世代による違いは、第 2 世代と第 3 世代で同じ手順を試すまで判断できません。

> **区分**: `verified` — 検証日 2026-11-23、`ap-northeast-1`、第 1 世代 `SINGLE_AZ_1`（HA ペア 1 組、2 ノード）、ONTAP 9.19.1P4。VPC 内の Windows インスタンスを経由した AWS Systems Manager のポートフォワードで、手元から管理 LIF の REST に接続しました。ONTAP 9.18.1P6 の結果は、削除済みの別の第 1 世代ファイルシステムで 2026-09 に同じ操作を行ったもので、その環境は今は再確認できません。

---

### 名前の取り違えの起点

| 項目 | 値 |
|---|---|
| broadcast domain の数 | 1 つ。名前は `Fsx` |
| IPspace の名前 | `Default` |
| 変更前の MTU | broadcast domain も、2 ノードのポート `e0e` も 9001 |

`broadcast-domain modify -broadcast-domain Default` のように IPspace の名前を指定しても、対象の broadcast domain は見つかりません。**FSx for ONTAP の broadcast domain を指定するときは、`Fsx` を使います。** 名前は推測せず、先に一覧を読み取ってください。

---

### 実測した操作と結果

| 経路 | 指定 | 結果 |
|---|---|---|
| REST（`PATCH /api/network/ethernet/broadcast-domains/{uuid}`） | MTU 1500 | HTTP 200、本文は空。読み取りで broadcast domain と 2 ノードのポートが 1500 |
| REST（同上） | MTU 1200 | HTTP 200、本文は空。読み取りで broadcast domain が 1200 |
| CLI（`PATCH /api/private/cli/network/port/broadcast-domain?broadcast_domain=Default`） | 存在しない名前 `Default`、MTU 1200 | HTTP 200、`num_records` が 0。何も変更されない |
| CLI（同上、`broadcast_domain=Fsx`） | MTU 1300 | HTTP 200、`num_records` が 1。読み取りで 1300 |
| CLI（同上） | MTU 9001 | HTTP 200、`num_records` が 1。読み取りで broadcast domain と 2 ノードのポートが 9001 |

**HTTP 200 は変更の成功を意味しません。** 存在しない名前を指定した CLI の呼び出しは HTTP 200 で返ります。成功の判定には、`num_records` と、変更後の読み取りの両方を使ってください。REST の PATCH も、新しい値を本文に返しません。

---

### 呼び出しの罠

| 症状 | 原因と対処 |
|---|---|
| `/api/private/cli/broadcast-domain` が 404 `API not found` | CLI のコマンド階層が違います。`network port broadcast-domain` に当たる `/api/private/cli/network/port/broadcast-domain` を使います |
| `fields=*` が HTTP 400 | CLI 型の REST は `fields=*` を受け付けません。フィールド名を列挙します |

---

### 試していないことと、報告された失敗との関係

第 2 世代のファイルシステムで `broadcast-domain modify -vserver <svm> -broadcast-domain Default -mtu 1200` が失敗した、という報告があります。エラーの全文は入手できていません。**この報告は、世代差の根拠として使えません。** 指定した名前が `Default` だったため、世代とは別に、対象が見つからなかっただけの可能性があるからです。
確かめる手順は、[ファイルシステムを作り直すたびの世代と版の確認](../../../playbooks/04-build/checklists/rebuild-version-and-generation-checks.md)にあります。第 2 世代と第 3 世代で同じ手順を行い、失敗した場合はエラーの全文を残してください。

---

### 関連

| ドキュメント | 関係 |
|---|---|
| [第 3 世代は確認した 7 リージョンのうち米国の 3 リージョンだけで作れた](third-generation-file-systems-and-where-the-sources-disagree.md) | 第 3 世代を作れるリージョン。東京では 2026-11-22 時点で作れなかった |
| [ONTAP のコマンド・REST API・権限の入口](../../../reference/ontap-commands-and-apis.md) | 管理者が使えるコマンドを版ごとに取り直す記録 |
