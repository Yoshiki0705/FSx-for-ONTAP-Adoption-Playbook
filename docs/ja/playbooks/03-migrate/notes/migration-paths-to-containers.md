---
title: コンテナ / モダナイゼーションへの移行経路は 3 つに分かれ、どれで来てもデータストアの判断は同じ決定木に合流する
lifecycle: [assess, migrate]
domains: [block-storage, data-utilization, multiprotocol-identity]
evidence: documented
source: https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns
lang: ja
---

# コンテナ / モダナイゼーションへの移行経路は 3 つに分かれる

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook — 移行](../README.md)

---

## 結論

**FSx for ONTAP を使うワークロードをコンテナやモダナイズ後の環境へ移す経路は 3 つあり、どれを通っても、データを FSx for ONTAP のどの到達形態で使うかという判断は同じ決定木に合流します。**

経路は「何を入力に、どこへ動かすか」で分かれます。**入力がソースコードか、実行中の VM か、そのどちらでもない専用ツール経由かで、使えるツールと到達形態が変わります。** しかし移した先でコンテナから FSx for ONTAP をどう使うか（Trident の PV か、ホストマウントか、S3 Access Points 経由か）は経路に依存しません。

**この分担を明示するのは、経路ごとに別のリポジトリが実装と検証を持っているためです。** このノートは「どの経路で来たか」を仕分けて、合流点である決定木と、各経路の実装リポジトリへ送り出す受け口です。**各経路の詳細な手順と検証は、それぞれのリポジトリが正典**として持ちます。

> **区分**: `documented` — 経路の切り分けは AWS / NetApp 公式ドキュメントと各実装リポジトリの記載に基づきます（2026-09-23 に確認）。
> **このリポジトリではコンテナ経路を実機で確認していません。** 実測を持つのは EC2 リホスト経路（[VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP)）のみで、コンテナ / モダナイゼーション経路は各実装リポジトリの検証段階に依存します。

---

## 3 つの経路

| # | 経路 | 入力 | 動かす先 | FSx for ONTAP の到達形態 | 実装・検証の所在 |
|---|---|---|---|---|---|
| 1 | ソースコードからのモダナイゼーション | ソースコード | Amazon ECS / Amazon EKS 上のコンテナ | Trident の PV（EKS on EC2）、ホストマウント（ECS on EC2）、S3 Access Points 経由（Fargate） | [FSx-for-ONTAP-Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) |
| 2 | リホストでブロックを疎結合にする | 実行中の VM / サーバー | Amazon EC2 | ゲスト OS 内の iSCSI マウント（ブロックを EC2 から切り離して FSx for ONTAP 側に置く） | [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) と [AWS Transform の Finalize は物理容量が最大になる工程](atx-finalize-flexclone-capacity.md) |
| 3 | サードパーティの VM 変換ツール経由（NetApp Shift Toolkit v8.0 など） | 実行中の VM / 仮想ディスク | Amazon EC2 + FSx for ONTAP | OS ディスクは Amazon EBS、データディスクは FSx for ONTAP。後からコンテナが iSCSI / NFS で到達 | **EC2 対応は Early Preview（2026-09 時点）。** GA の経路 1・2 と成熟度が異なります。一般提供の条件は各実装リポジトリを参照 |

**経路 1 と経路 2 の違いは入力です。** ソースコードを入力にするモダナイゼーション（経路 1）と、実行中の VM を入力にするリホスト（経路 2）は、AWS Transform の中でも別機能です。**「コンテナ化」と「リホストでのブロック連携」は 1 つのワークフローにまとまりません。** ソースコードからコンテナ化する経路には、リホスト専用のブロックサポートは付きません。

**経路 3 は入力が VM である点で経路 2 に近いですが、変換の仕組みが AWS のマネージド移行と別**です。NetApp Shift Toolkit v8.0 などが該当し、ONTAP のストレージ効率（FlexClone / SnapMirror）を使って OS ディスクを Amazon EBS、データディスクを FSx for ONTAP へ変換します。**中立に選択肢の 1 つとして置いています。**

**ただし成熟度が経路 1・2 と異なります。** Shift Toolkit v8.0 の EC2 対応は 2026-09 時点で Early Preview です。GA の AWS Transform / MGN（経路 1・2）を前提にした設計に経路 3 を混ぜる場合、この成熟度差を明示してください。**バージョンと一般提供の条件は変動するため、正典は実装リポジトリ側**とし、ここでは確認日（2026-09）とともに存在だけを示します。詳細は各実装リポジトリを参照してください。

---

## どの経路でも合流する先

**3 経路のどれを通っても、移した先でコンテナから FSx for ONTAP を使うかどうかの判断は 1 か所に合流します。**

[コンテナから FSx for ONTAP をデータストアにできるか](../../../reference/decision-trees/container-datastore-selection.md) が、実行環境（Fargate / EC2）と到達形態（Trident の PV / ホストマウント / S3 Access Points 経由）を決めます。**経路 1 と経路 3 のコンテナ側は、ここへ合流します。**

経路 2（EC2 リホスト）は、コンテナではなくゲスト OS の中で iSCSI をマウントする形なので合流しません。**ブロックを EC2 から疎結合にする判断は** [ブロックプロトコルとレイアウトの選択](../../../reference/decision-trees/block-protocol-and-layout.md) と、容量計画は [AWS Transform の Finalize は物理容量が最大になる工程](atx-finalize-flexclone-capacity.md) が扱います。

---

## マルチプロトコルが経路の選択に効く位置

**FSx for ONTAP のマルチプロトコル対応は、モダナイズ後に共有データをどのプロトコルで出すかの自由度として効きます。** 同じデータを NFS と SMB の両方で出せるため、モダナイズ前は SMB で使っていた共有を、モダナイズ後のコンテナからは NFS の PV（Trident `ontap-nas`）で読む、といった移行途中の混在が成立します。

**ただし到達形態ごとに制約が分かれます。** SMB の PV は Windows ノードのみ、S3 Access Points 経由はオブジェクト API へのアプリ改修が要ります。プロトコルをまたぐ権限の評価は [ボリュームのセキュリティスタイルが権限モデルを決める](../../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) が扱います。

---

## このノートが答えないこと

| 問い | 置き場所 |
|---|---|
| コンテナで FSx for ONTAP をどの到達形態で使うか | [コンテナから FSx for ONTAP をデータストアにできるか](../../../reference/decision-trees/container-datastore-selection.md) |
| Trident のドライバ選択とボリューム上限 | [Kubernetes のブロック PV はボリューム数の上限に当たる](../../../domains/block-storage/notes/kubernetes-block-volumes-and-the-volume-limit.md) |
| EC2 リホスト時のブロックのレイアウト | [ブロックプロトコルとレイアウトの選択](../../../reference/decision-trees/block-protocol-and-layout.md) |
| Finalize の容量ピークと不可逆性 | [AWS Transform の Finalize は物理容量が最大になる工程](atx-finalize-flexclone-capacity.md) |
| どの移行方式（SnapMirror / DataSync / ホストコピー）を選ぶか | [移行方式の選択](../../../reference/decision-trees/migration-method.md) |
| **経路 1・3 の詳細な手順と実機検証** | **各実装リポジトリが正典です。** このノートは受け口で、経路の中身は持ちません |
| **AWS Transform のモダナイゼーションの対応言語・スコープ** | 実装リポジトリ [FSx-for-ONTAP-Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) |

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| コンテナ化とリホストのブロック連携は 1 つの移行で両取りできる | **別機能です。** ソースコードからのコンテナ化（経路 1）には、リホスト専用のブロックサポート（経路 2）は付きません |
| 経路が違えばコンテナでの FSx for ONTAP の使い方も変わる | **合流します。** 経路 1・3 のコンテナ側は、同じ決定木で到達形態を決めます |
| EC2 リホスト（経路 2）もコンテナの決定木で判断する | **しません。** 経路 2 はゲスト OS 内の iSCSI マウントで、コンテナの PV とは別の到達形態です |
| サードパーティツール（Shift Toolkit v8.0 など）は GA の経路と同列に扱える | **成熟度が異なります。** EC2 対応は 2026-09 時点で Early Preview で、GA の経路 1・2 とは前提が違います。中立な選択肢ですが、成熟度差を明示してください |
| マルチプロトコルだからプロトコルを気にせず移せる | **到達形態ごとに制約があります。** SMB PV は Windows ノードのみ、S3 Access Points 経由はアプリ改修が要ります |

---

## 関連ドキュメント

- [Playbook — 移行](../README.md) — このモジュールのハブ
- [コンテナから FSx for ONTAP をデータストアにできるか](../../../reference/decision-trees/container-datastore-selection.md) — 経路 1・3 が合流する決定木
- [AWS Transform の Finalize は物理容量が最大になる工程](atx-finalize-flexclone-capacity.md) — 経路 2 の容量計画
- [ブロックプロトコルとレイアウトの選択](../../../reference/decision-trees/block-protocol-and-layout.md) — 経路 2 のブロックのレイアウト
- [Kubernetes のブロック PV はボリューム数の上限に当たる](../../../domains/block-storage/notes/kubernetes-block-volumes-and-the-volume-limit.md) — Trident のドライバ選択
- [移行方式の選択](../../../reference/decision-trees/migration-method.md) — データそのものの移行方式
- [FSx-for-ONTAP-Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) — 経路 1 の実装（5 構成の CloudFormation テンプレート）
- [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) — 経路 2 の実装と実測
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook — 移行](../README.md)

<!-- lang-switcher:start -->
🌐 [日本語](migration-paths-to-containers.md) | [English](../../../../en/playbooks/03-migrate/notes/migration-paths-to-containers.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->
