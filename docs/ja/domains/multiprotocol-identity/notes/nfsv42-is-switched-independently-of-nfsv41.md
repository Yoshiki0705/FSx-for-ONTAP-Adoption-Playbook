---
title: ONTAP 9.19.1P4 の第 1 世代では、SVM ごとに NFSv4.2 を NFSv4.1 と独立に切り替えられた
lifecycle: [design, build]
domains: [multiprotocol-identity]
evidence: verified
verified_on: 2026-11-23
region: ap-northeast-1
ontap_version: 9.19.1P4
deployment_type: SINGLE_AZ_1
lang: ja
---
# FSx for ONTAP で、SVM ごとに NFSv4.2 だけを無効にできるか？

できました。ONTAP 9.19.1P4 の第 1 世代で、使い捨ての SVM の NFSv4.2 だけを無効にしても NFSv4.1 は有効のままで、NFSv4.1 を無効にして NFSv4.2 を有効にすることもできました。クライアントのマウントで何が交渉されるかは試していません。

## このノートで学べること

- NFS サービスの設定に、`v42_enabled` が `v41_enabled` とは別の項目としてあること
- 新しく作った SVM では、NFSv4.0、4.1、4.2 がすべて有効であること
- NFSv4.2 の切り替えと、NFSv4.1 の切り替えが互いに影響しなかったこと

## このノートが答えないこと

- NFSv4.2 を無効にした SVM に、クライアントが `vers=4` でマウントしたときに交渉される版
- 9.18.1 以前で、NFSv4.2 だけを切り替えられなかったかどうか。比較していません
- NFSv4.2 を無効にした SVM での、既存のマウントの挙動

## 前提レベル

intermediate

## 本文

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — マルチプロトコルと ID](../README.md)

---

### 結論

**9.19.1P4 では、`vserver nfs` の設定で NFSv4.1 と NFSv4.2 を別々に切り替えられます。** 操作に必要な権限は `fsxadmin` が持っています（`vserver nfs` は `all`）。

> **区分**: `verified` — 検証日 2026-11-23、`ap-northeast-1`、第 1 世代 `SINGLE_AZ_1`、ONTAP 9.19.1P4。FSx for ONTAP の API で作った使い捨ての SVM に対し、REST で変更し、読み取りで確認しました。操作後に SVM を削除しています。
> NetApp のリリースノートは、9.19.1 で NFSv4.2 の管理が NFSv4.1 と独立になり、新しい NFS サービスでは既定で NFSv4.2 が有効だと記載しています（`documented`、[What's new in ONTAP 9.19.1](https://docs.netapp.com/us-en/ontap/release-notes/whats-new-9191.html)）。

---

### 実測した操作と結果

| 順 | 操作（REST、`PATCH /api/protocols/nfs/services/{svm の uuid}`） | 読み取りの結果（v4.0 / v4.1 / v4.2） |
|---|---|---|
| 0 | 新規 SVM の初期値 | 有効 / 有効 / 有効 |
| 1 | `v42_enabled` を `false` にする | 有効 / 有効 / 無効 |
| 2 | `v41_enabled` を `false`、`v42_enabled` を `true` にする | 有効 / 無効 / 有効 |
| 3 | 両方を `true` に戻す | 有効 / 有効 / 有効 |

すべて HTTP 200 で、読み取りで反映を確認しました。既存の SVM でも、`v42_enabled` の項目は読み取れました（確認した SVM では `true`）。

---

### 設計への含み

サーバー側で NFSv4.2 だけを止められるなら、NFSv4.2 を前提にできないクライアントやツールがある環境で、クライアント側の設定を変えずに済む可能性があります。**ただし、これは試していません。** NFSv4.2 を無効にした SVM に、`vers=4` を指定したクライアントが接続したときに NFSv4.1 へ下がるかは、別に確かめる必要があります。
S3 Access Points の Spoke は、`mount -o vers=4` が NFSv4.2 を交渉する環境で `vers=4.1` を明示するよう記録しています。同じ Spoke は、FPolicy が NFSv4.2 に対応しない前提で EVENT_DRIVEN モードの条件を書いています。NetApp のリリースノートによると、9.20.1 は FPolicy の NFSv4.2 対応を加えます。FSx for ONTAP が 9.20.1 を提供するか、提供した場合に FPolicy が NFSv4.2 で動くかは、確認していません。

---

### 関連

| ドキュメント | 関係 |
|---|---|
| [ファイルシステムを作り直すたびの世代と版の確認](../../../playbooks/04-build/checklists/rebuild-version-and-generation-checks.md) | 版が変わるたびに、この切り替えを取り直す手順 |
| [ONTAP 9.17.1 から 9.20.1 の新機能と FSx for ONTAP での確認状況](../../../reference/ontap-release-features-and-fsx-for-ontap.md) | 同じ版の他の機能の確認状況 |
