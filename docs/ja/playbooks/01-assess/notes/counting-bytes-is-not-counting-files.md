---
title: 容量が余っていても書けなくなる — 棚卸しでファイル数を数える理由
lifecycle: [assess, design]
domains: [performance, cost]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html
lang: ja
---

# 容量が余っていても書けなくなる

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 01 — 現状把握](../README.md)

---

## 結論

**バイト数だけを棚卸しすると、容量が余っているのに書き込めない状態になります。**

ボリュームはファイル・ディレクトリ・Snapshot コピーを inode（ファイルポインタ）で数えます。**inode を使い切ると、空き容量があってもそのボリュームには書き込めません。**

問題は既定値の増え方です。**inode の既定値は 32 KiB あたり 1 個ですが、これは 648 GiB までです。** 648 GiB 以上のボリュームは、サイズに関係なくすべて **21,251,126 個**で同じになります。

つまり **10 TiB のボリュームも 648 GiB のボリュームも、既定の inode 数は同じです。** 小さいファイルが多い環境では、容量よりはるかに早く inode が尽きます。

> **Evidence**: `documented` — inode の既定値・上限・挙動は AWS 公式ドキュメントの記載に基づきます。
> 後述の平均ファイルサイズは**公開されている既定値からの算術**であり、実測値ではありません。
> 自環境の値を測る手順は「[自分の環境で確かめる](#自分の環境で確かめる)」にあります。

---

## どのくらいの平均ファイルサイズで詰まるのか

既定の 21,251,126 個を、ボリュームサイズで割ると分岐点が出ます。**この平均ファイルサイズを下回ると、容量より先に inode が尽きます。**

| ボリュームサイズ | 既定の inode 数 | 分岐点となる平均ファイルサイズ |
|---|---|---|
| 648 GiB | 21,251,126 | 約 32 KiB |
| 1 TiB | 21,251,126 | 約 50 KiB |
| 10 TiB | 21,251,126 | 約 505 KiB |
| 50 TiB | 21,251,126 | 約 2.5 MiB |
| 100 TiB | 21,251,126 | 約 4.9 MiB |

**50 TiB のボリュームで平均ファイルサイズが 2.5 MiB を下回るなら、既定値では足りません。** ドキュメントやホームディレクトリの用途では珍しくない水準です。

inode は手動で増やせますが、上限があります。

| 項目 | 値 |
|---|---|
| 既定の比率 | 32 KiB あたり 1 個（648 GiB まで） |
| 引き上げ可能な比率 | **4 KiB あたり 1 個** |
| 1 ボリュームの上限 | **20 億個** |

**20 億個は絶対上限です。** 50 TiB のボリュームで 20 億個まで引き上げても、平均ファイルサイズ約 27 KiB が分岐点になります。それを下回るならボリュームの分割が必要です。

引き上げは ONTAP CLI の `volume modify` で行います。常に最大値を使う設定（`-files-set-maximum true`）は advanced モードが必要です。**作成時の既定では有効になっていません。**

---

## Snapshot も inode を消費します

inode が数えるのは**ファイル・ディレクトリ・Snapshot コピー**です。Snapshot の保持数を増やすと inode も消費します。

保持設計を容量だけで決めていると、この分が見落とされます。保持数の上限と容量の関係は [Snapshot があることと復旧できることは別](../../../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md#上限と保持期間) にあります。

**ディレクトリあたりのファイル数にも上限があります。** 1 つのディレクトリに大量のファイルを置く構成では、inode とは別にこの上限に当たります。移行ツールがここで失敗することがあります。

---

## 棚卸し項目は「後で戻せない判断」から逆算する

**棚卸しは項目を増やすことではありません。** 後の工程で値によって判断が変わるものだけが、測る価値のある項目です。

逆に言えば、**測らなかった項目が不可逆な設定として現れます。**

| 棚卸し項目 | これが決める判断 | 参照 |
|---|---|---|
| ファイル数と平均ファイルサイズ | inode の既定値で足りるか、ボリュームを分割するか | 本ノート上記 |
| 1 ディレクトリあたりのファイル数 | 移行ツールが完走するか | 本ノート上記 |
| 実際に使われているプロトコル | **ボリュームのセキュリティスタイル。** 権限評価の仕組みが変わります | [セキュリティスタイルと権限評価](../../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) |
| 移行アカウントが ACL を読めるか | ACL が欠けたまま「成功」で終わらないか | [ACL 保持は権限の問題](../../03-migrate/notes/preserving-acls-during-migration.md#必要な特権) |
| 移行元の ONTAP バージョン | SnapMirror が使えるか、先にアップグレードが必要か | [移行方式の決定木](../../../reference/decision-trees/migration-method.md#バージョン互換性の確認移行元が-ontap-の場合) |
| リージョンと世代 | **スループットと IOPS の上限そのもの。** 第 1 世代は 4 つのリージョン以外で半分になります | [スループットは 1 つの値で決まらない](../../../domains/performance/notes/where-throughput-is-determined-and-shared.md#上限は世代と構成とリージョンで変わる) |
| メタデータの量 | SSD 容量。階層化ポリシーに関係なく SSD に残ります | [監視は平均値で失敗する](../../05-operate/notes/monitoring-fails-on-averages.md#階層化ポリシーを-all-にしても-ssd-は使われます) |
| 単一名前空間で必要なスループット | FlexVol で足りるか FlexGroup が必要か | [共有される単位は HA ペア](../../../domains/performance/notes/where-throughput-is-determined-and-shared.md#共有される単位は-ha-ペア) |
| Active Directory の依存 | SVM の参加要件。ドメイン名・DNS・OU・管理者グループ | [本番投入前レビュー](../../04-build/checklists/pre-production-review.md) |
| 性能のベースライン | 移行後の「遅くなった」を検証可能にする | 本ノート下記 |

---

## 「設定されている」と「使われている」は違う

**プロトコルの棚卸しを設定情報から作ると外れます。** 有効になっているが誰も使っていない共有、逆に設定台帳に載っていない経路の両方が出ます。

セキュリティスタイルの選択は実際のアクセス経路で決まります。**両方のプロトコルから同じデータに触るかどうか**が判断の分かれ目であり、これは設定ではなく実際のアクセスを見ないと分かりません。

---

## 性能のベースラインは比較可能な形で取る

移行後に「遅くなった」と言われたとき、**比較対象がなければ検証できません。** ベースラインは次の形で残します。

| 記録する項目 | 理由 |
|---|---|
| 平均ではなく最大値 | 平均は飽和を隠します。理由は [監視は平均値で失敗する](../../05-operate/notes/monitoring-fails-on-averages.md) にあります |
| ピーク時間帯の値と、その時刻 | 平均値だけでは再現条件が分かりません |
| 共有単位・ボリューム単位の内訳 | 全体値では原因のボリュームが特定できません |
| 測定時のリージョンと世代 | 上限そのものが変わるため、条件を書かない数値は比較に使えません |
| 測定日 | 構成変更との対応を取るため |

**「条件を書かない数値は比較に使えない」がこのリポジトリ全体の方針です。** 詳細は [知見の分類ポリシー](../../../evidence-policy.md) にあります。

---

## 棚卸しの流れ

```mermaid
graph TD
    A[棚卸しを始める] --> B[バイト数を数える]
    B --> C[ファイル数と平均サイズを数える]
    C --> D{分岐点を下回るか}
    D -->|下回る| E[inode 引き上げ<br/>または ボリューム分割]
    D -->|上回る| F[既定値で足りる]

    A --> G[実際のアクセスを観測する]
    G --> H[プロトコルの実使用]
    H --> I[セキュリティスタイルの判断へ]

    A --> J[移行元の条件を記録する]
    J --> K[ONTAP バージョン]
    J --> L[ACL を読める権限があるか]
    K --> M[移行方式の決定木へ]

    A --> N[ベースラインを測る]
    N --> O[最大値・ピーク時刻・<br/>共有単位・リージョン・世代・測定日]
```

---

## 自分の環境で確かめる

**最初に測るべきは平均ファイルサイズです。** 分岐点との比較だけで、ボリューム設計が変わるかどうかが決まります。

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 移行元の総バイト数と総ファイル数を数え、割る | 平均ファイルサイズ。**上の表と比べるだけで判断できます** |
| 2 | 最もファイル数が多いディレクトリを 1 つ特定する | ディレクトリあたりの上限に近いか |
| 3 | 移行先で `FilesCapacity` と `FilesUsed` を見る | 実際の inode 消費。コンソールの「Available files (inodes)」でも見られます |
| 4 | 一定期間アクセスを観測し、プロトコル別に集計する | **設定ではなく実使用。** セキュリティスタイルの判断材料 |
| 5 | 移行アカウントで ACL が読めるかを試す | 「エラーなし」で ACL が欠ける事故を防げます |
| 6 | ピーク時間帯のスループットと IOPS を最大値で記録する | 移行後の比較基準 |
| 7 | リージョンと世代を記録する | 上限そのものが変わります |

手順 1 と 2 は移行元で完結し、FSx for ONTAP を作る前に実行できます。**この 2 つだけでも、後戻りの大きい設計判断を先に潰せます。**

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| 容量を見積もれば棚卸しは足りる | inode を使い切ると、**空き容量があっても書けません** |
| ボリュームを大きくすれば inode も増える | 増えるのは 648 GiB までです。**それ以上はサイズに関係なく 21,251,126 個で同じです** |
| inode は後からいくらでも増やせる | 4 KiB あたり 1 個が上限、1 ボリューム **20 億個**が絶対上限です |
| inode はファイルの数 | ファイル・ディレクトリ・**Snapshot コピー**を数えます |
| 常に最大 inode を使う設定が既定 | 既定ではありません。ONTAP CLI で明示的に設定します（advanced モード） |
| プロトコルの棚卸しは設定情報で足りる | 有効だが未使用の共有と、台帳にない経路の両方が出ます |
| 階層化ポリシーを `All` にすれば SSD の見積もりは不要 | メタデータは常に SSD に残ります |
| ベースラインは平均値で十分 | 平均は飽和を隠します。最大値とピーク時刻が必要です |
| 数値だけ記録すれば比較できる | リージョン・世代・測定日がないと比較に使えません |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| inode の定義、32 KiB あたり 1 個の既定値、648 GiB 以上で 21,251,126 個に固定、4 KiB あたり 1 個までの引き上げ、20 億個の上限、Snapshot コピーも数えること | [AWS: Volume storage capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html) |
| inode を使い切ると書き込めないこと、既定値の確認と手動引き上げが必要な条件 | [AWS: Your volume has insufficient storage capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/low-volume-capacity.html) |
| `volume modify` による引き上げ手順、`-files-set-maximum` が advanced モードであること | [AWS: Updating the maximum number of files on a volume](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/increase-volume-max-files.html) |
| `FilesCapacity` / `FilesUsed` メトリクスとコンソールでの確認方法 | [AWS: Monitoring a volume's file capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/view-volume-file-capacity.html) |
| ディレクトリあたりのファイル数上限に移行ツールが当たること | [AWS: Troubleshooting issues with DataSync tasks](https://docs.aws.amazon.com/datasync/latest/userguide/troubleshooting-tasks.html) |
| メタデータが階層化ポリシーに関係なく SSD に残ること | [AWS: Migrating to FSx for ONTAP using NetApp SnapMirror](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/migrating-fsx-ontap-snapmirror.html) |

---

## 関連ドキュメント

- [Playbook 01 — 現状把握](../README.md) — このモジュールのハブ
- [移行方式の決定木](../../../reference/decision-trees/migration-method.md) — 棚卸しの結果から方式を選ぶ
- [セキュリティスタイルと権限評価](../../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) — プロトコルの実使用から決まる判断
- [ACL 保持は権限の問題であってツールの問題ではない](../../03-migrate/notes/preserving-acls-during-migration.md) — 移行前に確認する権限
- [スループットは 1 つの値で決まらない](../../../domains/performance/notes/where-throughput-is-determined-and-shared.md) — リージョンと世代が上限を変える
- [監視は平均値で失敗する](../../05-operate/notes/monitoring-fails-on-averages.md) — ベースラインを最大値で取る理由
- [上限値・クォータ](../../../reference/limits/) — 出典と検証日付きの上限値
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 01 — 現状把握](../README.md)
