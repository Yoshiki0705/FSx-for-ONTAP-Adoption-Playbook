---
title: IaC の境界は好みではなく API の表面で決まる — テンプレートが成功しても構成は完成しない
lifecycle: [build, design]
domains: [security-governance, performance]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/administering-file-systems.html
lang: ja
---

# IaC の境界は好みではなく API の表面で決まる

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 04 — 構築](../README.md)

---

## 結論

**「何を IaC で管理するか」は方針で決める前に、API で届くかどうかで決まっています。**

ファイルシステム、SVM、ボリューム、バックアップ、タグは Amazon FSx の API とテンプレートで作成・更新・削除できます。 <!-- allow:naming - AWS の API 名 -->

**一方で ONTAP レベルの設定は ONTAP CLI または ONTAP REST API でしか届きません。** 例を挙げます。

| 設定 | 届く経路 |
|---|---|
| SMB 暗号化の強制 | **ONTAP CLI のみ**（`vserver cifs security modify`） |
| ボリュームの inode 上限 | **ONTAP CLI のみ**（`volume modify -files`） |
| FlexVol から FlexGroup への変換 | **ONTAP CLI のみ** |
| **ONTAP ボリュームの Snapshot 作成** | **ONTAP CLI / REST のみ。** 実測で確認しました（下記） |
| **SnapLock 監査ログボリュームの指定解除** | **ONTAP レベルのみ。** 実測で確認しました（下記）。**解除できても削除はできません** |
| **ボリューム削除が失敗した理由の取得** | **ONTAP レベルのみ。** AWS API は理由を返しません（下記） |

したがって **テンプレートが成功しても構成は完成していません。** 「IaC で全部管理する」という方針は、この境界を越えられません。設計すべきは境界の位置ではなく、**境界の向こう側をどう再現可能にするか**です。

> **Evidence**: `documented` — 各操作の経路とテンプレートの更新挙動は AWS 公式ドキュメントと CloudFormation リファレンスの記載に基づきます。
> **特定のツール構成の推奨はしません。** 自環境での確認手順は
> 「[自分の環境で確かめる](#自分の環境で確かめる)」にあります。

---

## 実測で見つかった 3 つの境界

**いずれも「テンプレートや AWS CLI から届かない」ことを実際に試して確認しました。**

| 発見 | 内容 |
|---|---|
| **`CreateSnapshot` は FSx for OpenZFS 専用** | ONTAP ボリュームに対して実行すると `Unable to create a snapshot because the volume was not found` になります。**ボリュームは存在し `CREATED` です。** ONTAP の Snapshot は Snapshot ポリシーまたは ONTAP CLI / REST の領域です |
| **SnapLock 監査ログボリュームは AWS API で削除できない** | 通常の削除も `BypassSnaplockEnterpriseRetention=true` も効きません。SVM 側の指定は API に露出しておらず、**ONTAP REST でなら解除できます。ただし解除しても削除できるようにはなりません**（最低 6 か月の保持期間中は、ボリューム・SVM・ファイルシステムのいずれも削除不可）。詳細は [SnapLock は有効化とロックが別](../../../domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md#監査ログボリュームはファイルシステムごと-6-か月固定します) |
| **ボリューム削除の失敗は応答では分かりません**（理由の取得先は AWS API 内にあります） | `delete-volume` は `DELETING` に入ったのち `CREATED` に戻り、**応答にはエラーが含まれません。** `AdministrativeActions` も `null` です。ただし**理由は `DescribeVolumes` の `LifecycleTransitionReason` に入ります**。ONTAP 側は必須ではありません |
| **`UpdateVolume` は非同期で痕跡を残さない** | 反映は 30 秒では未確認、120〜180 秒で確認。**`AdministrativeActions` には記録されません**（`null`）。連続実行は `There is an update already in progress.` で拒否されます |

**3 つ目が検証の設計に効きます。** API が成功を返しても反映されたことにはならず、記録も残らないため、**`DescribeVolumes` を読み直す以外に確認手段がありません。** この検証では短い待ち時間で状態を読み、一度「無視された」と誤診しました。

> **区分**: `verified`（検証日 2026-08-06、`ap-northeast-1`、`SINGLE_AZ_1`）。
> 記録は [上限値・クォータ](../../../reference/limits/) にあります。

**構築後の検証を自動化するなら、この 3 つ目を前提に組んでください。** 「API が 200 を返したか」ではなく「読み直して意図した値になっているか」を判定条件にします。

---

## テンプレートで扱えるものと、その更新挙動

更新挙動は設計に直結します。**`Replacement` と書かれているプロパティを変更すると、リソースが作り直されます。**

| プロパティ | 更新時の挙動 | 意味 |
|---|---|---|
| SVM の `RootVolumeSecurityStyle` | **Replacement** | **変更すると SVM が作り直されます。** ボリューム単位のセキュリティスタイル変更とは別物です |
| `FsxAdminPassword` | 中断なし | ローテーションはテンプレート経由で安全に行えます |
| `SvmAdminPassword` | — | 未指定でも SVM は作れますが、後述の副作用があります |

SVM のルートボリュームのセキュリティスタイルは `UNIX` / `NTFS` / `MIXED` から選びます。**この選択を後から変えるとリソースが置き換わる**ため、[セキュリティスタイルが権限評価のモデルを決める](../../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) を先に読んで決めてください。

---

## シークレットの扱い

`FsxAdminPassword` と `SvmAdminPassword` はテンプレートのプロパティです。**つまりテンプレートに平文で書けてしまいます。**

| 方針 | 内容 |
|---|---|
| 平文で書かない | CloudFormation の**動的参照**で AWS Secrets Manager から解決します |
| リポジトリに入れない | テンプレートもパラメータファイルも公開リポジトリに入る可能性があります |
| ローテーションを想定する | `FsxAdminPassword` の更新は中断を伴いません |

`FsxAdminPassword` には制約があります。**8〜50 文字で、改行や特定の制御文字を含められません。** 自動生成のパスワードポリシーがこの範囲を外れていると、作成時に失敗します。

### `SvmAdminPassword` を省略すると最小権限が崩れます

**`SvmAdminPassword` を指定しないと、その SVM の管理は `fsxadmin` で行うことになります。**

`fsxadmin` はファイルシステム全体の管理者です。つまり SVM 1 つの運用担当者に、ファイルシステム全体の権限を渡すことになります。

**指定すれば、その SVM を `vsadmin` で ONTAP CLI / REST API から管理できます。** 最小権限で運用するなら、SVM 作成時に指定してください。権限の分け方は [管理者を分ける](../../../domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md#権限設計管理者を分ける) にあります。

---

## Active Directory 連携の自動化

SVM の AD 参加はテンプレートで指定できますが、**参加そのものは AD 側の状態に依存します。** 自動化で扱うべき対象は次のとおりです。

| 対象 | 注意 |
|---|---|
| ドメイン名と DNS のアドレス | 参加の前提です |
| 計算機オブジェクトを置く OU | 権限委譲が済んでいる場所を指定します |
| 管理者グループ | 参加に必要な権限を持つグループを指定します |
| NetBIOS 名 | **失敗した名前を再利用しないでください。** AD 側に計算機アカウントが残ります |
| サービスアカウントのパスワード | シークレットとして扱います |

**AD 参加は「テンプレートが成功したか」では判定できません。** 参加状態は SVM のライフサイクル状態で確認します。前提条件は [Domain — マルチプロトコル・ID](../../../domains/multiprotocol-identity/) にあります。

---

## 構築後の検証を自動化する

**IaC の成功は構成の完成を意味しません。** 上で見たとおり、ONTAP レベルの設定はテンプレートの外にあります。したがって検証は 2 層必要です。

| 層 | 検証すること | 経路 |
|---|---|---|
| AWS リソース層 | ファイルシステム・SVM・ボリュームが意図した設定で存在するか | Amazon FSx API <!-- allow:naming - AWS の API 名 --> |
| ONTAP 設定層 | SMB 暗号化の強制、inode 上限、export policy、階層化ポリシー | ONTAP CLI / REST API |

**特に確認すべきは、既定値に任せると環境差が出る項目です。**

| 項目 | なぜ確認するのか |
|---|---|
| 階層化ポリシーと cooling period | **作成経路によって既定が違います。** [階層化の既定値は作成方法で違う](../../06-optimize/notes/tiering-defaults-differ-by-creation-method.md) |
| inode 上限 | 既定は 648 GiB を超えると増えません。[容量が余っていても書けなくなる](../../01-assess/notes/counting-bytes-is-not-counting-files.md) |
| SMB 暗号化の強制 | SVM 作成時点では無効です |
| ボリュームスタイル | HA ペア数によって既定が FlexVol / FlexGroup と変わります |

本番投入前に通す項目は [本番投入前レビュー](../checklists/pre-production-review.md) にまとめてあります。**復元と監視は「設定した」ではなく「試した」で確認してください。**

---

## 開発・検証環境の複製

| 方法 | 特徴 |
|---|---|
| FlexClone | 元データを参照するため高速です。ディスクスループットを消費しません |
| バックアップから新しいボリュームへ復元 | Amazon FSx の API で実行できます。同一リージョン内が対象です <!-- allow:naming - AWS の API 名 --> |
| SnapMirror | 別ファイルシステム・別リージョンへ複製できます |

### FlexClone には運用上の相互作用があります

**SSD 容量の縮小操作を開始した後に FlexClone を作成すると、縮小操作が一時停止します。** ONTAP がボリューム移動時にクローン関係を分割するため、新しいディスク上でストレージが二重になるのを避けるためです。

**再開させるには、縮小操作の開始後に作られた FlexClone を削除する必要があります。** 削除すると自動的に再開します。

「検証環境をクローンで用意する」運用と「コスト削減で SSD を縮小する」運用が同時に走ると、後者が止まります。

### FlexVol と FlexGroup の変換

| 項目 | 内容 |
|---|---|
| FlexVol の既定 | HA ペアが 1 組のファイルシステム |
| FlexGroup の既定 | **第 2 世代で HA ペアが 2 組以上**のファイルシステム |
| 変換 | **ONTAP CLI のみ。** 単一構成要素の FlexGroup が作られます |
| 推奨される方法 | **AWS DataSync でデータを移すこと。** 構成要素間に均等に分散させるためです |
| 変換前の注意 | **FlexVol のバックアップを削除してください。** ONTAP は変換時に自動リバランスしません |

**変換は「できる」が「推奨されない」操作です。** HA ペアを増やす計画があるなら、最初から FlexGroup で設計するほうが安いです。関係は [デプロイタイプは一度しか決められない](../../02-design/notes/deployment-type-is-decided-once.md) にあります。

---

## 構築フロー

```mermaid
graph TD
    A[構築を設計する] --> B{その設定は<br/>どの API で届くか}
    B -->|AWS リソース層| T[テンプレートで管理]
    B -->|ONTAP 設定層| O["ONTAP CLI / REST API<br/>テンプレートでは届かない"]

    T --> REPL{Replacement か}
    REPL -->|そう| CARE["変更すると作り直し<br/>SVM の RootVolumeSecurityStyle など"]
    REPL -->|中断なし| OK[更新可]

    O --> REPRO[再現可能にする手段を決める<br/>手順書か自動化か]

    T --> SEC[シークレットは<br/>動的参照で解決]
    SEC --> VSADMIN{SvmAdminPassword を<br/>指定したか}
    VSADMIN -->|していない| ESCALATE["SVM 管理に fsxadmin が必要<br/>最小権限が崩れる"]
    VSADMIN -->|した| LEAST[vsadmin で運用できる]

    REPRO --> VERIFY[2 層で検証する]
    OK --> VERIFY
    VERIFY --> V1[AWS リソース層の設定]
    VERIFY --> V2["ONTAP 設定層<br/>既定値に任せた項目を重点的に"]
```

---

## 自分の環境で確かめる

**最初に確かめるのは、テンプレートの外にある設定がいくつあるかです。**

| # | 手順 | 確認できること |
|---|---|---|
| 1 | テンプレートで作った環境の ONTAP 設定を CLI で一覧する | **テンプレートに書いていない設定が何であるか。** 境界の実測です |
| 2 | 階層化ポリシーと cooling period を確認する | 作成経路による既定の差が出ていないか |
| 3 | SMB 暗号化の強制状態を確認する | 既定の無効のままになっていないか |
| 4 | inode 上限を確認する | 既定のままで足りるか |
| 5 | `SvmAdminPassword` を指定したかを確認する | `fsxadmin` を配らずに運用できるか |
| 6 | 検証環境で FlexClone を作り、所要時間を記録する | 環境複製の実時間 |
| 7 | SSD 縮小操作中に FlexClone を作り、縮小が止まることを確認する | **相互作用の実測。** 検証環境で行ってください |
| 8 | 同じテンプレートを 2 回適用し、差分が出ないことを確認する | 冪等性 |

手順 1 が最も価値があります。**「テンプレートに書いていない設定の一覧」がそのまま、手順書または自動化の対象です。**

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| IaC で全部管理できる | **ONTAP レベルの設定はテンプレートで届きません。** SMB 暗号化の強制、inode 上限、FlexGroup 変換などです |
| テンプレートが成功すれば構成は完成 | ONTAP 設定層が残っています。検証は 2 層必要です |
| セキュリティスタイルはいつでも変えられる | SVM の `RootVolumeSecurityStyle` は **Replacement** です。変更すると SVM が作り直されます |
| `SvmAdminPassword` は任意なので省略してよい | 省略すると SVM 管理に `fsxadmin` が必要になり、**最小権限が崩れます** |
| パスワードは自動生成に任せればよい | `FsxAdminPassword` は 8〜50 文字で改行を含められません。ポリシーが外れると作成に失敗します |
| AD 参加はテンプレートの成功で判定できる | AD 側の状態に依存します。SVM のライフサイクル状態で確認します |
| FlexClone は独立したコピー | 元データを参照します。**SSD 縮小操作を止める**相互作用があります |
| FlexVol はいつでも FlexGroup にできる | ONTAP CLI のみで、**推奨は DataSync でのデータ移動**です。変換前にバックアップの削除が必要です |
| 環境の複製はバックアップ復元だけ | FlexClone と SnapMirror も選択肢です。復元は同一リージョン内が対象です |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| コンソール・AWS CLI・ONTAP CLI / API で行える管理操作の範囲（ファイルシステム・SVM・ボリューム・バックアップ・タグの作成と更新、管理アカウントとパスワード、SMB と iSCSI、ネットワーク到達性） | [AWS: Administering FSx for ONTAP resources](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/administering-file-systems.html) |
| `SvmAdminPassword` 未指定時に `fsxadmin` で SVM を管理することになること、指定すると ONTAP CLI / REST API で管理できること、`RootVolumeSecurityStyle` の値と更新時の Replacement 挙動 | [AWS CloudFormation: AWS::FSx::StorageVirtualMachine](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-fsx-storagevirtualmachine.html) |
| `FsxAdminPassword` が ONTAP CLI と REST API 用の管理パスワードであること、8〜50 文字の制約、更新が中断を伴わないこと | [AWS CloudFormation: AWS::FSx::FileSystem OntapConfiguration](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-fsx-filesystem-ontapconfiguration.html) |
| テンプレート内でシークレットを平文にせず解決する動的参照 | [AWS CloudFormation: Dynamic references](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/dynamic-references.html) |
| FlexVol と FlexGroup の既定条件とサイズ範囲、変換が ONTAP CLI のみであること、DataSync でのデータ移動が推奨されること、変換前にバックアップを削除する必要があること、自動リバランスされないこと | [AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |
| SSD 縮小操作開始後の FlexClone 作成で縮小が一時停止すること、クローン削除で自動再開すること | [AWS: Troubleshooting SSD decrease operation issues](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/ssd-decrease-troubleshooting.html) |
| ONTAP CLI で SVM を管理する方法 | [AWS: Managing FSx for ONTAP storage virtual machines](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-svms.html) |

---

## 関連ドキュメント

- [Playbook 04 — 構築](../README.md) — このモジュールのハブ
- [本番投入前レビュー](../checklists/pre-production-review.md) — 構築後に通す項目
- [階層化の既定値は作成方法で違う](../../06-optimize/notes/tiering-defaults-differ-by-creation-method.md) — 作成経路で既定が変わる代表例
- [容量が余っていても書けなくなる](../../01-assess/notes/counting-bytes-is-not-counting-files.md) — inode 上限は ONTAP CLI で設定します
- [デプロイタイプは一度しか決められない](../../02-design/notes/deployment-type-is-decided-once.md) — FlexGroup を選ぶ判断の前提
- [保存時の暗号化は自動、転送時は既定で無効](../../../domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md) — SMB 暗号化と管理者の分離
- [セキュリティスタイルが権限評価のモデルを決める](../../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) — Replacement を伴う選択の前提
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 04 — 構築](../README.md)
