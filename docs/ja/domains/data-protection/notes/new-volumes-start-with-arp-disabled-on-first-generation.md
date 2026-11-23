---
title: ONTAP 9.19.1P4 の第 1 世代では、新規ボリュームの Autonomous Ransomware Protection は既定で無効だった
lifecycle: [design, build]
domains: [data-protection, security-governance]
evidence: verified
verified_on: 2026-11-23
region: ap-northeast-1
ontap_version: 9.19.1P4
deployment_type: SINGLE_AZ_1
lang: ja
---
# FSx for ONTAP で、新しく作ったボリュームの ARP/AI は有効になっているか？

有効になっていませんでした。ONTAP 9.19.1P4 の第 1 世代で、FSx for ONTAP の API で作った新規ボリュームの `anti_ransomware.state` は `disabled` でした。ボリュームごとに有効化が必要です。

## このノートで学べること

- 第 1 世代・ONTAP 9.19.1P4 の新規ボリュームの ARP/AI の状態と、それを読み取る方法
- NetApp のリリースノートが「新規ボリュームで既定で有効」とする対象に、FSx for ONTAP が載っていないこと

## このノートが答えないこと

- 第 2 世代と第 3 世代の新規ボリュームの既定
- 有効化した後の学習期間と、検知の挙動（[SnapLock とランサムウェア対策の層のノート](snaplock-and-layered-ransomware-readiness.md)にある）
- 新規ボリュームで ARP/AI を有効にする推奨の是非

## 前提レベル

intermediate

## 本文

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — データ保護](../README.md)

---

### 結論

**ONTAP 9.19.1P4 の第 1 世代で、新規ボリュームの ARP/AI は既定で無効です。** 新しく作るボリュームの保護を ARP/AI に頼る設計では、作成後に有効化する手順が要ります。

> **区分**: `verified` — 検証日 2026-11-23、`ap-northeast-1`、第 1 世代 `SINGLE_AZ_1`、ONTAP 9.19.1P4。FSx for ONTAP の API で、使い捨ての SVM に 1,024 MB のボリュームを 1 つ作り、REST で読み取りました。ボリュームは確認後に削除しています。1 回の観測です。

---

### 実測した内容

| 項目 | 結果 |
|---|---|
| 読み取りの経路 | `GET /api/storage/volumes?name=<ボリューム>&fields=anti_ransomware.state` |
| 新規ボリューム | `anti_ransomware.state` が `disabled` |
| 同じファイルシステムの既存ボリューム（3 つを確認） | すべて `disabled` |

---

### リリースノートの記載との関係

NetApp の [What's new in ONTAP 9.18.1](https://docs.netapp.com/us-en/ontap/release-notes/whats-new-9181.html) は、クラスターの作成または 9.18.1 への更新のあと、新規ボリュームで ARP/AI が 12 時間の猶予をおいて既定で有効になると記載しています（`documented`）。対象として挙がっているのは AFF A、AFF C、ASA、ASA r2 で、FSx for ONTAP は記載にありません。今回の結果は、この記載と矛盾しません。

---

### 関連

| ドキュメント | 関係 |
|---|---|
| [SnapLock は有効化とロックが別](snaplock-and-layered-ransomware-readiness.md) | ARP の世代と学習期間の、版とボリューム種別による違い |
| [ファイルシステムを作り直すたびの世代と版の確認](../../../playbooks/04-build/checklists/rebuild-version-and-generation-checks.md) | 版が変わるたびに、この既定を取り直す手順 |
