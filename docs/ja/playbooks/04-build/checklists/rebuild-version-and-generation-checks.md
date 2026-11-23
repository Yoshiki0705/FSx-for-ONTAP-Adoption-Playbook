---
title: ファイルシステムを作り直すたびの世代と版の確認 — 世代、ONTAP の版、MTU、管理者の権限、新機能を同じ手順で取り直す
lifecycle: [build, operate]
domains: [performance, security-governance]
evidence: documented
source: https://docs.netapp.com/us-en/ontap/release-notes/index.html
lang: ja
---
# ファイルシステムを作り直すたびの世代と版の確認

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 04 — 構築](../README.md)

---

## このチェックリストの位置づけ

Amazon FSx for NetApp ONTAP のファイルシステムを作り直したとき、または ONTAP の版が上がったときに、同じ項目を同じ手順で取り直すためのものです。**世代（第 1、第 2、第 3）と ONTAP の版は、ユーザーが選べない、または途中で変わる条件です。** 一度確かめた結果は、別の世代や別の版では成り立たない場合があります。

> **区分**: `documented` — 項目の出典は NetApp のリリースノートと、このリポジトリのノートです。各項目の結果は、リンク先のノートの区分（`verified` など）に従います。
> **この手順が確認するのは、第 1 世代の ONTAP 9.18.1P6 と 9.19.1P4 までです。** 第 2 世代と第 3 世代の結果は、まだありません。結果が増えたら、この手順の出力を表に追記します。

---

## 1. 環境の記録

**結果の表の先頭に置く列です。** これがない結果は、別の環境の結果と比べられません。

- [ ] リージョン、デプロイタイプ（`SINGLE_AZ_1`、`SINGLE_AZ_2`、`SINGLE_AZ_3` など）、HA ペア数、スループット容量を記録した
- [ ] ONTAP の完全な版（パッチを含む）を、ONTAP 側で読み取って記録した（`GET /api/cluster?fields=name,version`）。AWS の API の `OntapVersion` は null で返ることがあります
- [ ] 取得した日付を記録した。ONTAP のパッチはサービス側で適用されるため、同じファイルシステムでも日が変われば版が変わりえます（[ONTAP のコマンド・REST API・権限の入口](../../../reference/ontap-commands-and-apis.md)）
- [ ] 他のプロジェクトのタグ（`Teardown`、`MeasurementId` など）が付いたファイルシステムを見つけたら、触らなかった。パスワードの再設定も、設定変更もしない

---

## 2. MTU の変更の確認

**使い捨てのファイルシステム、または持ち主が変更を承認した環境でだけ行います。** MTU の変更中は、その broadcast domain に載る通信に影響しえます。手順と結果は [第 1 世代の MTU のノート](../../../domains/performance/notes/broadcast-domain-mtu-can-be-changed-on-first-generation.md)にあります。

- [ ] broadcast domain の名前、MTU、配下のポートの MTU を読み取って記録した。名前を推測していない（`Default` は IPspace の名前）
- [ ] 現在値とは別の値（例: 9001 から 1500）を、REST で指定した。HTTP の状態と、読み取った MTU の両方を記録した
- [ ] 同じ変更を、CLI（`/api/private/cli/network/port/broadcast-domain`）でも行った。`num_records` が 1 であることを確認した。0 なら、何も変更されていない
- [ ] 元の値に戻し、読み取りで確認した
- [ ] 失敗した場合は、エラーの全文と HTTP の状態を、そのまま残した。「対象なし」「権限なし」「未対応」を区別できる形にする
- [ ] 世代と版の組ごとに結果を並べた。世代と版が同時に変わった比較で、どちらの影響かを判断していない

---

## 3. 管理者が使えるコマンドの取り直し

- [ ] `GET /api/security/roles?name=fsxadmin&fields=privileges,owner.name` で、`fsxadmin` の権限の一覧を取り、版と日付を付けて保存した
- [ ] 前回の一覧と比べ、増減したコマンドを記録した。比較の基準は、Cyber Resilience の Spoke が公開している 9.18.1P6 の表と、その差分を残す Lambda（[ONTAP のコマンド・REST API・権限の入口](../../../reference/ontap-commands-and-apis.md)から読めます）
- [ ] 機能の表の「`fsxadmin` から使えるか」の行を、この一覧で更新した。たとえば `vserver nfs tls` は、9.19.1P4 で `none`（使えない）でした

---

## 4. ONTAP の新機能の確認

- [ ] [ONTAP 9.17.1 から 9.20.1 の新機能と FSx for ONTAP での確認状況](../../../reference/ontap-release-features-and-fsx-for-ontap.md)の、読み取りだけで確かめられる行を更新した
- [ ] 設定の変更を伴う行は、使い捨ての SVM とボリュームで行った（FSx for ONTAP の API で作り、確認後に削除する）。既存の SVM とボリュームを使っていない
- [ ] 新しい版が出ていたら、NetApp の What's new を全文で読み、表に行を足した。索引ページの先頭だけで「記載なし」と判断していない
- [ ] 結果が新しい論点になるときは、`notes/` に 1 論点 1 ファイルで追加した。表の状態の欄には、そのノートへのリンクを置いた

---

## 5. 触る前に止まる項目

- [ ] **削除できなくなる機能は、人が保持期間を指定するまで実行していない。** タンパープルーフスナップショット、SnapLock、保持期間つきの S3 バケット削除が該当する（[不可逆な操作の承認は作業の承認とは別に取る](../../../domains/security-governance/notes/irreversible-operations-need-separate-approval.md)）
- [ ] 認証が 401 で失敗したら、その環境への再試行を止めた。失敗の繰り返しで `fsxadmin` がロックされる（[fsxadmin はロックされる](../../05-operate/notes/admin-account-lockout-and-recovery.md)）
- [ ] 管理エンドポイントへの接続は、AWS Systems Manager のポートフォワードで手元から行い、パスワードを SSM のコマンドやログに載せていない

---

## 6. 後始末

- [ ] 変更した設定を元に戻し、読み取りで確認した
- [ ] 作った SVM とボリュームを削除し、一覧に残っていないことを確認した
- [ ] ポートフォワードを閉じ、一時的に付けた IAM の権限を外した

---

## 結果の置き場所

| 結果の種類 | 置く場所 |
|---|---|
| 新機能の確認状況（1 行ごと） | [新機能の確認状況の表](../../../reference/ontap-release-features-and-fsx-for-ontap.md)の状態の欄 |
| 1 つの論点として独立する結果 | 該当モジュールの `notes/`。環境の記録（本チェックリストの 1）を区分の欄に書く |
| 世代と版の組ごとの MTU の結果 | [第 1 世代の MTU のノート](../../../domains/performance/notes/broadcast-domain-mtu-can-be-changed-on-first-generation.md)の表に、組を足す |
| Spoke が持つべき記録（権限の一覧、版ごとの差分） | その Spoke。Hub には入口のリンクだけを置く |

---

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 04 — 構築](../README.md)
