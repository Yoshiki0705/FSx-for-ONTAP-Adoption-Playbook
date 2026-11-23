---
title: AWS Backup の論理エアギャップボールトは、アカウント侵害に備える隔離方式の 1 つ — 前提のキーと不可逆な設定が先に決まる
lifecycle: [design, operate]
domains: [data-protection, security-governance]
evidence: documented
source: https://docs.aws.amazon.com/aws-backup/latest/devguide/logicallyairgappedvault.html
lang: ja

---

# AWS Backup の論理エアギャップボールトは、Amazon FSx for NetApp ONTAP の隔離方式としてどう選ぶか？

論理エアギャップボールトは、バックアップを AWS Backup のサービス所有アカウントに置く隔離方式です。使う前に決まる 2 つのキーと、戻せないロックを承認の対象にします。

## このノートで学べること

- SnapLock、Tamperproof Snapshot、別アカウントへの SnapVault と並べた、論理エアギャップボールトの置き場所と制約
- 元のファイルシステムの暗号化キーと、ボールトの暗号化キーが別物で、決まる時点も違うこと
- ボールトで戻せなくなる設定と、承認の前に言語化しておく値

## このノートが答えないこと

- 論理エアギャップボールトの構成手順、AWS RAM による共有、マルチパーティ承認（MPA）の設定。実装は [サイバーレジリエンス パターンの実装ガイド](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/aws-backup-logically-air-gapped-vault.md) にあります
- 実環境での動作確認。このノートは AWS の公開文書だけに基づきます（`documented`）
- 法令・規制への適合性の判断

## 前提レベル

intermediate

## 本文

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — データ保護](../README.md)

---

### 結論

**論理エアギャップボールトは、AWS アカウント全体の侵害を想定するときに検討する隔離方式です。** 2026 年 9 月に FSx for ONTAP のボリュームバックアップが対象になりました（`documented`、[What's New](https://aws.amazon.com/about-aws/whats-new/2026/09/aws-backup-air-gapped-vault-fsx-ontap/)）。ボールトはバックアップを AWS Backup のサービス所有アカウントに保存し、Vault Lock のコンプライアンスモードを備えます（`documented`）。

**採用の前に決めることが 2 つあります。どちらも、あとから直す手段が見つかっていません。**

1. **元のファイルシステムの暗号化キー。** AWS Backup が完全に管理しないリソースタイプは、カスタマー管理キー（CMK）で暗号化されていないとボールトへコピーされません。FSx for ONTAP の既定のキーは AWS マネージドキーです。キーはファイルシステムの作成時に指定します。
2. **ボールトの暗号化キーと保持期間の範囲。** ボールトのキーは作成時にしか選べず、あとで変更も移行もできません（`documented`）。コンプライアンスモードのロックがかかった復旧ポイントは、保持期間が終わるまで削除できません。

この 2 つは [不可逆な操作の承認は作業の承認とは別に取る](../../security-governance/notes/irreversible-operations-need-separate-approval.md) の対象です。承認の取り方は [ボールトで承認前に提示する値](#ボールトで承認前に提示する値) にあります。

> **区分**: `documented`（確認日 2026-11-23）。AWS Backup 開発者ガイドと FSx for ONTAP の公開文書を読んだ結果で、ボールトの作成・コピー・復元は **このリポジトリでは実行していません**。文書に見つからなかった点は [文書で確認できなかった点](#文書で確認できなかった点) に分けて書きます。

---

### 4 つの隔離方式の置き場所と制約

**順位は付けません。** 想定する侵害が ONTAP 管理者までか、AWS アカウント全体かで選びます。方式は組み合わせられます。

| 方式 | 復旧点の置き場所 | 運用するもの | 主な制約 | 戻せない点 |
|---|---|---|---|---|
| SnapLock | 同じファイルシステムの SnapLock ボリューム | SnapLock ボリュームと容量計画 | 保持期間中は削除できず、容量計画が保持期間で決まる | 有効化、保持モード、特権削除の無効化。監査ログボリュームはファイルシステム全体を 6 か月固定する |
| Tamperproof Snapshot（Snapshot locking） | 同じボリューム | Snapshot ポリシーとボリュームの設定 | ONTAP 9.12.1 以降。AWS API にパラメーターがなく、ONTAP の資格情報で設定できる | ロック済み Snapshot の失効まで無効化できない |
| 別アカウントの FSx for ONTAP への SnapVault / SnapMirror | 別アカウントの別ファイルシステム | 二次ファイルシステム、ネットワーク、IAM | 宛先ファイルシステムを平常時から動かす費用がかかる | 宛先でロックを使うなら、宛先側のロックの期限 |
| 論理エアギャップボールト | AWS Backup のサービス所有アカウント | AWS Backup のプランとボールト。隔離側のファイルシステムは要らない | 元のファイルシステムの CMK、RW ボリュームのみ、同時コピー数の上限 | ボールトのロック（コンプライアンスモード）とボールトの暗号化キー |

SnapLock と Tamperproof Snapshot の詳細は [SnapLock は有効化とロックが別](snaplock-and-layered-ransomware-readiness.md)、バックアップコピーと SnapMirror の違いは [SnapMirror との選び分け](backup-copies-across-regions-and-accounts.md#snapmirror-との選び分け) にあります。この表では繰り返しません。

**どの方式も守るのは復旧点の可用性と完全性です。** 読み出されたデータの機密性は、アクセス制御・暗号化・監査という別の制御で守ります。

| 問い | 向く方式の傾向 |
|---|---|
| 侵害が ONTAP 管理者の資格情報までと想定する | SnapLock、Tamperproof Snapshot、ボールトのいずれも候補になる |
| AWS アカウント全体の侵害を想定する | ボールトと、別アカウントへの SnapVault が候補。SnapLock と Tamperproof Snapshot はこの想定での挙動を、このノートでは確認していない |
| 隔離側のファイルシステムを運用したくない | ボールト（復元時には復元先のファイルシステムと SVM が要る） |

> **補足**: 「確認していない」は、SnapLock と Tamperproof Snapshot の保護が弱いという主張ではありません。アカウント侵害時の挙動を、AWS の文書で確認していないという意味です。

---

### 元のファイルシステムとボールトの 2 つのキー

**2 つのキーは別物で、決まる時点が違います。**

| 項目 | 内容 | 決まる時点 | 出典 |
|---|---|---|---|
| 元のファイルシステムのキー | FSx for ONTAP は、既定では AWS マネージドキーを使い、CMK も選べる。ボールトへコピーするには、AWS Backup が完全に管理しないリソースでは CMK が要る | ファイルシステムの作成時（`CreateFileSystem` の `KmsKeyId`） | [暗号化](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-at-rest.html)、[ボールト](https://docs.aws.amazon.com/aws-backup/latest/devguide/logicallyairgappedvault.html)、[API](https://docs.aws.amazon.com/fsx/latest/APIReference/API_CreateFileSystem.html) |
| ボールトのキー | AWS 所有キーが既定で、CMK も選べる。AWS Backup は AWS 所有キーを推奨している。CMK を選ぶ場合は、別アカウントのキーを推奨し、同じアカウントのキーはテスト用途に限るとしている | ボールトの作成時。変更も移行もできない | [ボールト](https://docs.aws.amazon.com/aws-backup/latest/devguide/logicallyairgappedvault.html) |

**FSx for ONTAP が「完全に管理しないリソース」であることの根拠。** AWS Backup の [Primary backups to logically air-gapped vaults](https://docs.aws.amazon.com/aws-backup/latest/devguide/lag-vault-primary-backup.html) は、Amazon FSx を、ボールトへ直接バックアップできず、標準ボールトに一時的な復旧ポイントを作ってからコピーするリソースの例に挙げています。同じページは、AWS マネージドキーで暗号化されたこの種のリソースを、ボールトへコピーできないと書いています。この場合、バックアップジョブは失敗せず「Completed with issues」で完了し、バックアップは標準ボールトにだけ残ります。

**この設計判断が難しい理由。** 既存のファイルシステムのキーを後から CMK に変える手順は、確認した文書に見つかりませんでした（[文書で確認できなかった点](#文書で確認できなかった点)）。ボールトを使う計画があるなら、ファイルシステムを作る時点で CMK を選ぶのが確実です。既に AWS マネージドキーで作ったファイルシステムでは、CMK のファイルシステムを新しく作ってデータを移す選択肢を含めて検討します。

**一時的な復旧ポイントは費用に出ます。** FSx for ONTAP のバックアップは、標準ボールトの一時的な復旧ポイントを経由してボールトへコピーされ、一時的な復旧ポイントも保持期間中は課金されます（`documented`、同ページ）。バックアップコピーの課金の全体は [バックアップコピーの課金](backup-copies-across-regions-and-accounts.md) にあります。

---

### ボールトで承認前に提示する値

**ボールトは「削除できなくするために作る」ものなので、作る前に値を提示して承認を取ります。** [不可逆な操作の承認ゲート](../../security-governance/notes/irreversible-operations-need-separate-approval.md#承認ゲート) の 6 項目を、このボールトに当てはめると次の表になります。

| ゲートの項目 | このボールトでの内容 | 出典 |
|---|---|---|
| 保持期間の値 | ボールトの作成時に最小保持期間（7 日以上）と最大保持期間を決める。範囲の外の保持期間を持つバックアップは、ボールトにコピーされない。バックアッププランの保持期間をこの範囲に収める | [ボールト](https://docs.aws.amazon.com/aws-backup/latest/devguide/logicallyairgappedvault.html)、[Primary backups](https://docs.aws.amazon.com/aws-backup/latest/devguide/lag-vault-primary-backup.html) |
| 縛るパラメーター | ボールトのロックは常にコンプライアンスモード。ボールトの暗号化キーは作成時に固定される | [ボールト](https://docs.aws.amazon.com/aws-backup/latest/devguide/logicallyairgappedvault.html) |
| 最も広い影響範囲 | ボールトと、その中の復旧ポイント。コンプライアンスモードのロックがかかったボールトは、猶予期間が過ぎると誰も（AWS も）設定を変えられず、復旧ポイントがある限り削除できない | [Vault Lock](https://docs.aws.amazon.com/aws-backup/latest/devguide/vault-lock.html) |
| 期間いっぱい保持するコスト | 復旧ポイントは保持期間が終わるまで削除できず、保管料金が続く。料金は [AWS Backup の料金](https://aws.amazon.com/backup/pricing/) | 同上 |
| 早期解除の経路 | 文書に見つかっていない。Vault Lock のページは、猶予期間の後は誰も変えられないと書く | [Vault Lock](https://docs.aws.amazon.com/aws-backup/latest/devguide/vault-lock.html) |
| 削除手順の確認 | ボールトの削除は、復旧ポイントが残っている間はできない。**有効化の前に、この制約を読む** | [ボールト](https://docs.aws.amazon.com/aws-backup/latest/devguide/logicallyairgappedvault.html) |

**SnapLock の監査ログボリュームと違い、FSx for ONTAP のファイルシステムの削除可否に及ぶかは書かれていません。** ボールトの復旧点は AWS Backup のサービス所有アカウントにあり、元のファイルシステムとは別の保管先です。ただし、ロック済みの復旧ポイントが元のボリュームやファイルシステムの削除に影響するかを、確認した文書は述べていません。影響しないと決めつけず、承認の前に試験用のファイルシステムで確かめます（[自環境での確認手順](#自環境での確認手順)）。

**承認の対象は、ボールトの作成だけではありません。** 次の 2 つも承認の対象です。

- バックアッププランに「ボールトを宛先に加える」変更。加えた時点で、以降のバックアップがロック付きのボールトに積み上がる
- ボールトに CMK を指定する変更。作成時にしか決められない

---

### SnapLock ベースの cyber vault とは別の概念

**同じ「論理エアギャップ」という語でも、指すものが違います。**

| 項目 | SnapLock ベースの cyber vault | AWS Backup の論理エアギャップボールト |
|---|---|---|
| 構成要素 | SnapVault と、宛先の SnapLock Compliance ボリューム | AWS Backup のボールト |
| 置き場所 | ONTAP のファイルシステム上の SnapLock ボリューム | AWS Backup のサービス所有アカウント |
| ロックの機構 | SnapLock の保持期間 | AWS Backup Vault Lock のコンプライアンスモード |
| 運用するもの | 宛先のファイルシステム、SnapLock ボリューム | バックアッププランとボールト |
| 参照元 | ONTAP の技術レポート（[該当節](snaplock-and-layered-ransomware-readiness.md#論理エアギャップcyber-vaultという不変性層の置き方)） | AWS Backup の文書 |

**前者は NetApp が示す参照アーキテクチャで、後者は AWS Backup の機能です。** 片方の文書の制約（SnapLock の保持モードが変えられない、など）を、もう片方に当てはめません。

---

### 文書で確認できなかった点

| 点 | 確認した範囲 | このノートの扱い |
|---|---|---|
| 既存の FSx for ONTAP ファイルシステムの暗号化キーを後から変えられないこと | `CreateFileSystem` は `KmsKeyId` を受け付ける。`UpdateFileSystem` の要求にキーを変えるパラメーターは見当たらない。「変更できない」と明記した文を、確認した Amazon FSx の文書に見つけていない | 「変更手順が見つからない」と書き、「変更できない」と断定しない |
| 論理エアギャップボールトのロックに、コンプライアンスモードの猶予期間があるか | Vault Lock のページは、コンプライアンスモードに 3 日以上の猶予期間を置くと書く。論理エアギャップボールトのページには、猶予期間の記載が見つからない | 猶予期間はないものとして承認を取る |
| ロック済みの復旧ポイントが、元のボリューム・ファイルシステムの削除に影響するか | 記載なし | 試験用のファイルシステムで確かめるまで、影響しないと書かない |
| AWS マネージドキーのファイルシステムからのコピーが、プランのコピー規則と手動のコピーで同じ結果になるか | 文書はプランの経路で「Completed with issues」になると書く。手動のコピーの結果は書かれていない。別リポジトリの実装ガイドは、手動のコピーが失敗した 1 回の観測を記録している | このノートは文書の記述だけを使う。観測は実装ガイドを参照 |

---

### 利用できるリージョンと対象

- **FSx for ONTAP は論理エアギャップボールトの対象リソースです。** 2026-11-23 時点の [AWS Backup の機能提供状況](https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-feature-availability.html) の表で、FSx for ONTAP の行に論理エアギャップボールトの印があります。
- **東京（ap-northeast-1）と大阪（ap-northeast-3）の行にも、論理エアギャップボールトの印があります**（同じ表、2026-11-23）。リージョンの提供状況は変わるため、使う前に表を読み直します。
- 対象は RW ボリュームです。ボールトへのコピーでは、DP、LSM、FlexCache、SnapMirror の宛先ボリューム、SnapLock FlexGroup ボリュームは対象外です（`documented`、[FSx for ONTAP のバックアップ](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-backups.html)）。
- Amazon FSx からボールトへの同時コピーは 5 件で、バックアップの頻度がコピーの完了より速いと、コピージョブが滞留して失敗しうると文書にあります（[Primary backups](https://docs.aws.amazon.com/aws-backup/latest/devguide/lag-vault-primary-backup.html)）。上限の値は [AWS Backup のクォータ](https://docs.aws.amazon.com/aws-backup/latest/devguide/aws-backup-limits.html) で確認します。

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| FSx for ONTAP はボールトへ直接バックアップできる | **できません。** 標準ボールトの一時的な復旧ポイントを経由してコピーされ、一時的な復旧ポイントも課金される |
| 既定の設定のファイルシステムのバックアップが、そのままボールトに入る | **AWS マネージドキーのファイルシステムは、ボールトへコピーされません。** バックアップは標準ボールトにだけ残る |
| ボールトのキーは、あとで CMK に変えられる | **作成時にしか選べません。** 変更も移行もできません |
| 論理エアギャップボールトは SnapLock の cyber vault と同じ | **別の機構です。** 構成要素も、ロックの機構も違う |
| ボールトは、読み出されたデータの漏えいも防ぐ | **守るのは復旧点の可用性と完全性です。** 機密性は別の制御で守る |

---

### 参照した一次情報

| 主張 | 出典 | 確認日 |
|---|---|---|
| FSx for ONTAP のボリュームバックアップが論理エアギャップボールトの対象になったこと。プライマリターゲットまたはコピー先に指定できること。RAM と MPA に対応すること | [What's New (2026-09)](https://aws.amazon.com/about-aws/whats-new/2026/09/aws-backup-air-gapped-vault-fsx-ontap/) | 2026-11-23 |
| ボールトがサービス所有アカウントに保存すること。コンプライアンスモードの Vault Lock を備えること。ボールトのキーの既定と変更不可。最小保持期間 7 日。AWS マネージドキーの制約。ボールトの削除条件 | [Logically air-gapped vault](https://docs.aws.amazon.com/aws-backup/latest/devguide/logicallyairgappedvault.html) | 2026-11-23 |
| FSx for ONTAP が完全管理でないリソースであること。一時的な復旧ポイントと課金。AWS マネージドキーでは「Completed with issues」になること。同時コピー数 | [Primary backups to logically air-gapped vaults](https://docs.aws.amazon.com/aws-backup/latest/devguide/lag-vault-primary-backup.html) | 2026-11-23 |
| コンプライアンスモードのロックが、猶予期間の後は誰にも変えられないこと | [AWS Backup Vault Lock](https://docs.aws.amazon.com/aws-backup/latest/devguide/vault-lock.html) | 2026-11-23 |
| FSx for ONTAP と東京・大阪で、論理エアギャップボールトの印があること | [Feature availability](https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-feature-availability.html) | 2026-11-23 |
| FSx for ONTAP の既定のキーが AWS マネージドキーであること。`KmsKeyId` が作成時のパラメーターであること | [Encryption of data at rest](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-at-rest.html)、[CreateFileSystem](https://docs.aws.amazon.com/fsx/latest/APIReference/API_CreateFileSystem.html) | 2026-11-23 |

---

### 関連ドキュメント

- [Domain — データ保護](../README.md) — このモジュールのハブ
- [不可逆な操作の承認は作業の承認とは別に取る](../../security-governance/notes/irreversible-operations-need-separate-approval.md) — 承認ゲートと対象の操作
- [SnapLock は有効化とロックが別](snaplock-and-layered-ransomware-readiness.md) — SnapLock と Tamperproof Snapshot の不可逆性
- [バックアップコピーはリストアするまでファイルシステムを持たない](backup-copies-across-regions-and-accounts.md) — 別リージョン・別アカウントへのコピーと復元の制約
- [サイバーレジリエンス機能マップ](../../../reference/cyber-resilience-capability-map.md) — 機能とリポジトリの対応
- [実装ガイド（FSx-for-ONTAP-Cyber-Resilience-Patterns）](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/aws-backup-logically-air-gapped-vault.md) — 構成、RAM 共有、MPA、復元の手順
- [知見の分類ポリシー](../../../evidence-policy.md)

---

## 自環境での確認手順

次のコマンドは読み取りだけで、ボールトもロックも作りません。

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `aws fsx describe-file-systems --file-system-ids <file-system-id> --query 'FileSystems[].KmsKeyId'` で得たキーを、`aws kms describe-key --key-id <key-arn> --query 'KeyMetadata.KeyManager'` に渡す | `AWS` なら AWS マネージドキーで、ボールトにはコピーされない。`CUSTOMER` なら CMK |
| 2 | `aws backup list-backup-vaults --query 'BackupVaultList[].[BackupVaultName,VaultType,Locked]'` | 既存のボールトの種別とロックの状態。**ボールトの作成はしない** |
| 3 | 試験用のアカウントで、プランのコピー先にボールトを加える前に、保持期間の範囲を提示して承認を取る | [ボールトで承認前に提示する値](#ボールトで承認前に提示する値)の各項目に値が入っているか |

### 期待結果

手順 1 で `KeyManager` が `AWS` を返すなら、そのファイルシステムのバックアップは標準ボールトにだけ残ります。手順 2 の `VaultType` が論理エアギャップボールトを示し、`Locked` が `true` なら、そのボールトにある復旧ポイントは保持期間が終わるまで削除できません。

**確認できる範囲には境界があります。** この手順は、ボールトへのコピーが成功すること、ロック済みの復旧ポイントが元のファイルシステムの削除に影響しないこと、復元できることを確かめません。それらを試す場合は、使い捨てのアカウントと使い捨てのファイルシステムを使い、保持期間の最小値と最大値を先に承認してもらいます。
