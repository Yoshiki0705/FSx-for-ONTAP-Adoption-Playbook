---
title: AWS Transform の Finalize は後片付けではなく、物理容量が最大になる工程
lifecycle: [migrate]
domains: [block-storage, cost]
evidence: verified
verified_on: 2026-09-04
ontap_version: 9.18.1P3D1
region: ap-northeast-1
lang: ja
---

# AWS Transform の Finalize は後片付けではなく、物理容量が最大になる工程

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook — 移行](../README.md)

> **Evidence**: `verified`。ap-northeast-1、ONTAP 9.18.1P3D1、2026-09-04。Amazon EC2（Amazon Linux 2023）をソースに、
> ブート 8 GiB + データ 4 GiB × 2 で AWS Transform for migrations のレプリケーションから Finalize までを実行した際の実測です。
> **1 構成 1 回の測定であり、所要時間と容量はデータ量と構成で変わります。**

---

## 結論

**Finalize は移行の後片付けではありません。物理容量の使用量がこの工程で最大になります。** アグリゲートの空き容量を Finalize 前の数値で見積もると、移行データ 1 本分だけ足りません。

| 時点 | ステージング FlexVol（物理） | ターゲット FlexVol（物理） | 合計 |
|---|---|---|---|
| Finalize 前 | 8.03 GiB | **35.5 MiB** | 約 8.06 GiB |
| スプリット完了直後 | 8.03 GiB | 8.57 GiB | **約 16.6 GiB** |
| ステージング削除後 | — | 8.57 GiB | 8.57 GiB |

理由は 2 つの数字の差です。**ターゲットボリュームは Finalize までは FlexClone なので、論理 7.91 GiB に対して物理消費は 35.5 MiB しかありません。** Finalize がこのクローンをスプリットして実体化するため、物理消費が親と同じ水準まで増えます。そして**スプリット完了からステージングボリューム削除までに約 9 分の間隔があり、その間は両方が物理容量を占めます。**

**容量計画では論理値ではなく物理値を見てください。** 論理値だけを見ていると、Finalize の前後で何も変わらないように読めます。

---

## AWS Transform のフェーズ名と ONTAP の操作の対応

ジョブログのフェーズ名がどの ONTAP 操作を指すのかを、時刻の一致で確定しました。

| AWS Transform のフェーズ | 対応する ONTAP の操作 | 実測 |
|---|---|---|
| SNAPSHOT | ステージング FlexVol の**ボリューム Snapshot** 作成 | 12:05:05 UTC。SNAPSHOT_START〜END の区間内。8 GiB に対して 44 秒 |
| LAUNCH | その Snapshot からの **FlexClone 作成** | ターゲット FlexVol の作成時刻 12:10:41 UTC |
| Finalize | FlexClone の**スプリット**とステージングの削除 | スプリット開始が約 3 分後、完了が約 4 分後、ステージング削除が約 13 分後 |

ターゲットボリュームは `is_flexclone: true` で、`parent_snapshot` が SNAPSHOT フェーズで作られた Snapshot、`parent_volume` がステージングボリュームでした。`split_estimate` は 8,517,623,808 バイトで、スプリット後の実際の増加分とおおむね一致します。

**含意が 1 つあります。SNAPSHOT フェーズはコピーではなくメタデータ操作です。** 8 GiB に対して 44 秒でした。ただし**データ量を変えたときの伸び方は測っていません。** 1 点の測定から一般化しないでください。

---

## 容量以外に効く 3 点

| 事象 | 実測 | 設計への影響 |
|---|---|---|
| Finalize はジョブを作成しない | `describe-jobs` に現れず、`describe-job-log-items` でフェーズを追えない | 進捗はリソースの状態を直接ポーリングして判定するしかありません |
| クリーンアップは段階的 | 約 33 分かけて完了。ステージング FlexVol が約 13 分、EBS ボリュームが約 13 / 23 / 33 分の 3 回に分かれて削除 | **「残骸が残った」と判定する前に観測窓の長さを決めてください。** 16 分の観測では削除済みのものを残骸と読み違えます |
| スプリットは無停止 | マウント維持、sha256 一致、I/O エラーとパスダウンと SCSI abort はいずれも 0 件 | **Finalize は容量のリスクであって可用性のリスクではありません**（この規模と負荷条件での観測） |

不可逆性も確認しました。Finalize 後に `change-server-life-cycle-state` を呼ぶと `ConflictException` で拒否され、メッセージはレプリケーションエージェントの再導入を指示します。**戻す手段はレプリケーションのやり直しだけです。**

---

## 検証環境

| 項目 | 値 |
|---|---|
| リージョン | ap-northeast-1 |
| ONTAP バージョン | 9.18.1P3D1 |
| ソース | Amazon EC2、t3.small、Amazon Linux 2023。ブート 8 GiB + データ 4 GiB × 2 |
| ステージング種別 | ブート `AUTO`（Amazon EBS）、データ `FSX_ONTAP` |

> **注意**: 上の数値は 16 GiB / 3 ディスクという小さい構成での 1 回の実測です。**アグリゲートの空き容量が
> 移行データ量を下回る状態で Finalize したときの挙動は測っていません。** エラーで停止するのか、
> アグリゲートを使い切るまで進むのかは未確認です。

---

## 自環境での確認手順

| 確認したいこと | 方法 |
|---|---|
| Finalize 前のターゲットボリュームの物理消費 | ONTAP REST の `/api/storage/volumes` で `space.physical_used` と `space.used` の両方を取得し、差を見ます。論理値だけでは判断できません |
| スプリットに必要な容量 | 同じレスポンスの `clone.split_estimate`。これがスプリットで増える物理容量の目安になります |
| クリーンアップの完了 | Finalize 発行後、ステージング FlexVol と EBS ボリュームが消えるまで 33 分程度ポーリングします。途中の状態を最終状態と読まないでください |

判断に取り入れる前の確認については [エビデンス方針](../../../evidence-policy.md#本番に取り入れる前の確認) を参照してください。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| Finalize は後片付けなので容量は減る一方 | **増えます。** スプリットで移行データ 1 本分の物理容量が一時的に必要になります |
| ターゲットボリュームの `space.used` を見れば必要な容量が分かる | FlexClone のうちは論理値です。物理値は 2 桁以上小さいことがあります |
| Finalize の進捗はジョブで追える | **ジョブは作られません。** リソースの状態をポーリングします |
| クリーンアップ直後に残っているものは残骸 | 段階的に削除されます。16 分の観測で残骸と判定するのは早すぎます |

---

## 関連ドキュメント

- [切り戻せる時点はクライアントが書き始めた瞬間に閉じる](where-the-rollback-window-closes.md) — Finalize の不可逆性と切り戻しの関係
- [最近の更新](../../../reference/recent-updates.md) — AWS Transform が FSx for ONTAP をサポートした範囲と、移行時に見積もる制約
- 実測の全文と再現手順: [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP)

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook — 移行](../README.md)
