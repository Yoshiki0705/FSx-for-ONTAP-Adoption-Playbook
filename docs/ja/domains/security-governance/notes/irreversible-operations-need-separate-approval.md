---
title: 不可逆な操作の承認は作業の承認とは別に取る — 128 MiB がファイルシステムを 6 か月固定した
lifecycle: [design, build, operate]
domains: [security-governance, data-protection]
evidence: verified
verified_on: 2026-08-06
ontap_version: 9.17.1P7D1
region: ap-northeast-1
lang: ja
---

# 不可逆な操作の承認は作業の承認とは別に取る

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — セキュリティ・ガバナンス](../README.md)

---

## 結論

**「削除できなくする」ことが目的の機能は、実行者の判断で有効にしてはいけません。** 保持期間の値を
含めて、明示的な指示を受けてから実行する対象です。

この結論は一般論ではなく、**このリポジトリの検証作業で実際に踏んだ失敗**から来ています。128 MiB の
SnapLock 監査ログボリュームを 1 本作成した結果、**ボリューム・SVM・ファイルシステムの 3 つが 6 か月間
削除できなくなりました。**

**機能は仕様どおりに動作しています。** SnapLock は「削除できないこと」を保証する機能なので、
削除できないのは正常です。**問題は機能ではなく、承認を取らずに実行した手順の側にあります。**

| 論点 | 内容 |
|---|---|
| 実行したこと | SnapLock 監査ログボリュームの作成（128 MiB） |
| 想定していた影響範囲 | そのボリューム 1 本 |
| 実際の影響範囲 | **ボリューム + SVM + ファイルシステム** |
| 期間 | **最低 6 か月**（Enterprise モードでも例外なし） |
| 早期解除の経路 | **ありません。** ドキュメントの読みに加え、[ベンダーサポートの回答としても確定](#ベンダーサポートに確認した結果2026-08)しました |
| 得られた知見 | **なし。** 当該検証は「帰属できない」で終了しました |

> **Evidence**: `verified`（検証日 2026-08-06、`ap-northeast-1`、`SINGLE_AZ_1`（第 1 世代）、
> ONTAP `9.17.1P7D1`）。影響範囲が SVM とファイルシステムに及ぶことは `documented`（出典は
> [参照した一次情報](#参照した一次情報)）。**本ノートの承認ゲートは推奨であり、実測ではありません。**
> 技術的な全記録は [上限値・クォータ](../../../reference/limits/) にあります。

---

## 起きたこと

作業の目的は、既存ノートの記載を自環境で検証することでした。**「未実測項目の検証」について承認は
得ていました。** しかし以下について、確認も報告もしていません。

| 実行した不可逆操作 | 確認を取ったか |
|---|---|
| SnapLock `ENTERPRISE` ボリュームの作成 | いいえ |
| `PrivilegedDelete=PERMANENTLY_DISABLED` の設定（終端状態） | いいえ |
| SnapLock 監査ログボリュームの作成 | いいえ |
| 保持期間の値（既定の 6 か月が適用された） | **いいえ。値を提示していません** |

そして**削除できないことを、削除に失敗してから知りました。** 該当する警告は「機能を有効にする方法」の
ページではなく、**「削除する方法」のページ**に書かれていました。

### 順序による退路の狭まり

`PrivilegedDelete` を先に `PERMANENTLY_DISABLED` にしていたため、監査ログの WORM ファイルを特権削除で
消す経路も残っていませんでした。**不可逆な操作を 2 つ重ねると、片方だけなら残っていた出口が閉じます。**

| 試したこと | 結果 |
|---|---|
| AWS API での削除（`BypassSnaplockEnterpriseRetention=true` 併用） | 失敗。エラーを返さず元の状態に復帰 |
| ONTAP REST で SVM 側の監査ログ指定を解除 | **成功。ただし削除できるようにはならない** |
| ボリューム側の `is_audit_log` を解除 | **拒否。読み取り専用フィールド** |
| ボリュームをオフラインにして削除 | 失敗（保持期間が未満了） |
| WORM ログファイルの特権削除 | **経路なし**（恒久無効化済み） |

### ベンダーサポートに確認した結果（2026-08）

**早期解除の経路が無いことは、ドキュメントの読みではなく回答として確定しました。** 以下は
2026-08 のサポートケースで得た内容です（`verified`。ケース識別子は本ノートに含めません）。

| 論点 | 回答 |
|---|---|
| 保持期間満了前の削除 / ロック解除 | **不可。満了を待つ以外の経路はありません** |
| 請求面の相談 | **対象リソースの削除完了後**に「アカウントおよび請求サポート」窓口へ改めて起票する順序。配慮が可能であることは約束されません |
| `AuditLogVolume: false` でも削除できない理由 | ブロックしているのは**指定ではなく、監査ログファイルに適用済みの保持期間**。指定を解除しても残ります |
| `snaplock.is_audit_log` が `true` のまま残る理由 | **「過去に一度でも指定された」ことを示す履歴マーク**で、現在の指定を表しません。現在の指定は AWS の `AuditLogVolume` で判断します |
| 削除可否の判断に使うフィールド | `DescribeVolumes` の `LifecycleTransitionReason.Message`（`Cannot delete the volume because it contains unexpired log files.`） |
| 満了日時の確認方法 | 管理エンドポイントへ SSH し `volume snaplock show -vserver <svm> -volume <volume> -instance` の `Expiry Time`。**ONTAP REST の `GET /api/storage/volumes/{uuid}?fields=snaplock` でも `expiry_time` として読めます**（実測 2026-08-17） |
| ドキュメント改善の要望 | 担当部署へフィードバック。反映と時期は約束されません |
| 長期案件のケース運用 | 半年オープンのままにはできないため、**満了後の削除実施時に、前のケース ID を添えて新規ケースを起票**する運用 |

> **ドキュメント改善は「提出済み」であって「反映済み」ではありません。** 公開されるまでは未反映として
> 扱ってください。

**保持期間の設定値は、削除できない理由を説明しません。** 実測したボリュームは
`retention` が `{default: P0Y, minimum: P0Y, maximum: P30Y}` のまま 6 か月削除できませんでした。
削除可能になる日時は `expiry_time` の側にあります。

### コンソールの警告は、実際に起きることより範囲が狭い

**「コンソールなら警告が出るので事故らない」は成り立ちません。** 作成画面には確かに警告がありますが、
削除に関する記述は「SnapLock ボリュームを削除できなくなります」までで、**SVM とファイルシステムには
触れません。** 承知チェックボックスは `SnapLock 設定` を有効化したことに対するもので、
**`監査ログボリューム` に専用の確認はありません。** さらに `監査ログボリューム` の直下に並ぶ保持期間の
3 欄（デフォルト / 最小 / 最大）はすべて**ボリューム上の WORM ファイル用**で、監査ログの保持期間を
指定する欄は画面上に存在しません。

実際の画面 3 枚と、詰まった後に読むべきフィールドは
[監査ログボリューム — コンソールでの操作ポイント](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/ja/snaplock-audit-log-console-guardrails.md)
にあります。

---

## 知識があっても防げなかった理由

**知識は不足していませんでした。** このリポジトリには、同じ作業中に書かれた
[SnapLock は有効化とロックが別](../../data-protection/notes/snaplock-and-layered-ransomware-readiness.md)
というノートがあり、不可逆性を主題にしています。**その不可逆性を、そのノートを書いている最中に踏みました。**

ここから取り出せる論点は 3 つあります。

| 論点 | 内容 |
|---|---|
| **危険を文書化することは、危険を尊重することと同じではありません** | ノートに書いた不可逆性は、実行判断には反映されませんでした |
| **作業の承認は、結果を永続化する承認を含みません** | 「検証してよい」は「取り消せない状態を作ってよい」ではありません。**操作の結果がタスクより長く残るなら、同意の範囲を取り直す必要があります** |
| **可逆性は「入口」ではなく「出口」の性質です** | 有効化手順のページには書かれていません。**削除手順のページを先に読む必要があります** |

---

## 対象となる操作（AWS 横断）

**SnapLock 固有の話ではありません。** 「削除する能力を取り除くこと」が目的の機能は共通の性質を持ちます。

| サービス | 操作・パラメータ |
|---|---|
| FSx for ONTAP — SnapLock | `SnaplockConfiguration`、`SnaplockType`、`AuditLogVolume`、`PrivilegedDelete`、`RetentionPeriod`、`VolumeAppendModeEnabled`、ONTAP の `snaplock` / `audit-logs` エンドポイント |
| FSx for ONTAP — **Snapshot locking**（Tamperproof Snapshot） | `-snapshot-locking-enabled`、`-snaplock-expiry-time`、`volume snapshot modify-snaplock-expiry-time`、`volume snapshot policy create -retention-period`、`snapmirror policy add-rule -retention-period` |
| Amazon S3 | Object Lock の構成、`put-object-retention`、`put-object-legal-hold` |
| S3 Glacier | `initiate-vault-lock`、`complete-vault-lock` |
| AWS Backup | Vault Lock（`put-backup-vault-lock-configuration`）、compliance モード |
| Amazon EBS | `lock-snapshot` |
| 全般 | `PERMANENTLY_DISABLED` / `COMPLIANCE` など、終端状態を表す値 |

**これらは「設定ミス」が復旧不能になる唯一の種類の機能です。** ほかの設定は作り直せますが、この分類は
作り直しもできません。

### 「SnapLock を使っていない」の、保護としての不成立

**Snapshot locking（Tamperproof Snapshot）は、非 SnapLock ボリュームでも有効にできます。**
SnapLock を採用していない環境でも、同じ削除ロックが発生しえます。

| 項目 | 内容 |
|---|---|
| 対象 | **非 SnapLock ボリュームでも可**（ONTAP 9.12.1 以降） |
| 無効化 | **全ロック済み Snapshot の失効まで不可** |
| ボリュームの削除 | **未期限のロック済み Snapshot があると不可** |
| ボリュームの `expiry_time` | ロック済み Snapshot の**最大失効時刻**が入ります |
| 保持期間 | **時間単位まで短く設定できます**（Hours 0–24 / Days 0–36500 など） |
| **AWS API のパラメータ** | **存在しません。** ONTAP CLI / REST 専用です |

**AWS API にパラメータがないことは、AWS 側のガードレールも効かないことを意味します。** IAM の条件キーや
コンソールの警告で止められません。**ONTAP に到達できる資格情報が、そのまま削除ロックを作れる権限です。**

そして監査ログボリュームとは失敗の形が逆です。

| | 監査ログボリューム | Snapshot locking |
|---|---|---|
| 保持期間の下限 | **6 か月**（下限自体が許容できない） | **時間単位から選べる** |
| 失敗の形 | 「選べなかった」 | **「選べたのに選ばなかった」** |

詳細と 1,023 上限との複合的な問題は [上限値・クォータ](../../../reference/limits/) にあります。

> **この節は `documented` です。** 有効化すると同種の削除ロックを新たに作るため、**本リポジトリでは
> 検証していません。** 自分の環境で試す場合も、使い捨てのファイルシステムを使ってください。

---

## 承認ゲート

実行前に、以下を**すべて**満たしてください。自動化や AI エージェントに実行させる場合も同じです。

| # | 項目 | 理由 |
|---|---|---|
| 1 | **保持期間の値を推測しない。既定値を黙って受け入れない** | 本件は既定の 6 か月が適用されました。値を提示していれば止まっていました |
| 2 | **どのパラメータが期間を縛るのかを特定する。使う API に指定手段があるかまで確認する** | 本件はここを外しました。下表参照 |
| 3 | **最も広い影響範囲を明示する**（ボリューム / SVM / ファイルシステム / バケット / ボールト / アカウント） | 呼び出しで指定したリソースより広いのが通例です |
| 4 | **その範囲を期間いっぱい保持するコストを提示する** | 削除できないことは課金が続くことです |
| 5 | **早期解除の documented な経路があるかを明言する** | 監査ログボリュームには、アカウント閉鎖以外ありません |
| 6 | **削除手順のドキュメントを、有効化手順より先に読む** | 可逆性は出口側に書かれています |

### 「保持期間を最小にする」の不成立 — 縛るパラメータが別であるため

**SnapLock には保持期間を表すパラメータが複数あり、ロックの原因になるものは 1 つです。** 本件で
「最小値を設定する」実践は、**設定した側では既に最小（0 年）**でした。ロックしたのは別のパラメータです。

| パラメータ | 設定できる値 | 何を縛るか | 本件の値 |
|---|---|---|---|
| ボリュームの `RetentionPeriod` | 秒〜年。**0 も可** | ボリューム上の WORM ファイル | Default **0 YEARS** / Minimum **0 YEARS** |
| **監査ログ設定の `retention-period`** | ドキュメント上の下限 **6 か月** | 監査ログファイル → ボリュームの `expiry_time` | **P6M**（既定値が適用） |

そして決定的な点として、**AWS API 側に監査ログの保持期間を指定するパラメータが存在しません。**

| API | 監査ログ保持期間の指定 |
|---|---|
| Amazon FSx `CreateSnaplockConfiguration` | **不可。** フィールドは `SnaplockType` / `AuditLogVolume` / `AutocommitPeriod` / `PrivilegedDelete` / `RetentionPeriod` / `VolumeAppendModeEnabled` の 6 つで、`RetentionPeriod` は**ボリュームの WORM ファイル用**です <!-- allow:naming - AWS の API 名 --> |
| ONTAP `snaplock log create -retention-period` | 可 |

**つまり「短い期間を選べなかった」のではなく、「指定できる経路を使わなかった」のが実態です。**
`AuditLogVolume=true` を AWS API で渡すと既定値が適用されます。値を制御したいなら ONTAP 側で作成する
必要があります。

> **ここは `documented` です。** 監査ログの下限が 6 か月という記載は
> [参照した一次情報](#参照した一次情報) のとおりですが、**それより短い値が実際に拒否されるかは試していません。**
> 試すには監査ログボリュームをもう 1 本作る必要があり、失敗すれば同じロックが増えます。

**教訓は「最小値を選ぶ」ではありません。** 期間を縛るパラメータを特定し、**自分が使う API にその指定手段が
あるかまで確認する**ことです。手段がなければ、既定値が適用されるという事実そのものが承認事項です。

### 例外にならない検証

**本件は検証作業でした。** 検証だからこそ、次を先に決めてください。

- **使い捨ての専用ファイルシステム、または専用アカウントを使う**
- **不可逆操作を重ねる場合は、そのたびに承認を取り直す**（順序が出口を閉じます）
- **その検証が失敗したときに何が残るかを、先に書き出す**

---

## 仕組みによる防止

**手順の合意だけでは再発を防げません。** 本件では合意も知識もあったうえで発生しました。

このリポジトリでは `scripts/guard_irreversible_ops.py` が、上表のパターンに一致する**変更操作を
ブロック**し、**読み取りは許可**します。読み取りを止めると、状態を確認できない実行者が推測で動くため、
かえって危険になります。

| 実装上の判断 | 理由 |
|---|---|
| 確認プロンプトではなく**ブロック** | プロンプトは流れで承認されます。ブロックなら会話で説明せざるを得ません |
| 読み取り操作は通す | 調査を止めると推測が増えます |
| 標準ライブラリのみ、プロジェクト非依存 | 他のリポジトリへ複製して使えます |

過検知は無効化を招くため、**誤ってブロックしない**ことも要件です。実装では
`get-object-lock-configuration`（読み取り）が `lock-` に一致してブロックされる不具合を、動詞をコマンド
位置に固定することで修正しました。

---

## 自環境での確認手順

**不可逆な操作なので、本番でも共用の検証環境でも試さないでください。**

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 使い捨てのファイルシステムを作る | 失敗しても捨てられる状態を先に用意する |
| 2 | 削除手順のドキュメントを読み、削除できない条件を書き出す | **有効化前に出口を確認する習慣** |
| 3 | 監査ログボリュームを作らずに、SnapLock の保持期間だけを検証する | 監査ログなしでも確認できる範囲 |
| 4 | 特権削除を使う設計かどうかを先に決める | **使わないなら監査ログボリュームが不要で、6 か月ロックも発生しません** |
| 5 | 不可逆操作を検出する仕組みを CI / フックに入れる | 手順の合意だけでは止まらないこと |

**手順 4 が最も効きます。** 特権削除を使わない判断をすれば、この問題自体が発生しません。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| 影響は指定したリソースだけに及ぶ | **SVM とファイルシステムにも及びます。** 呼び出しでは指定していません |
| コンソールから操作すれば警告で止まる | **警告の範囲が狭いです。** 削除に関する記述はボリュームまでで、SVM とファイルシステムには触れません。`監査ログボリューム` に専用の承知チェックもありません |
| サポートに依頼すれば早期に解除できる | **できません。** 回答として確定しています。請求面の相談も、リソースの削除完了後に別窓口へ起票する順序です |
| SnapLock を使っていなければこの問題は起きない | **Snapshot locking は非 SnapLock ボリュームでも有効にできます** |
| AWS API に無い機能なら誤って有効化されない | **逆です。** AWS API にパラメータがないため、IAM 条件キーやコンソール警告で止められません |
| Enterprise モードなら管理者が消せる | **監査ログボリュームには例外がありません** |
| ONTAP レベルの権限があれば解除できる | SVM 側の指定は解除できますが、**削除できるようにはなりません** |
| 保持期間を最小にしておけば安全 | **縛るパラメータが別です。** ボリュームの `RetentionPeriod` は 0 年でしたが、監査ログ設定の保持期間がロックしました |
| SnapLock の保持期間は短くできないのか | **できます。** 秒単位まで設定可能です。ただし**監査ログ設定の保持期間は AWS API に指定手段がなく**、既定が適用されます |
| Enterprise なら管理者が消せるので安全 | **監査ログボリュームには Enterprise の例外が適用されません。** ドキュメントが「Enterprise モードでも同様」と明記しています |
| 検証環境なら試してよい | **使い捨てでなければ同じ損害です。** 他の検証ごと 6 か月固定されます |
| 削除に失敗すれば API がエラーを返す | **応答にはエラーが含まれず、`CREATED` に戻ります。** 理由は `DescribeVolumes` の `LifecycleTransitionReason` を**読み直して**取得します |
| 手順を文書化すれば再発しない | 本件は文書化しながら発生しました。**仕組みで止める必要があります** |
| 機能側の問題である | **仕様どおりの動作です。** 問題は承認を取らずに実行した手順の側です |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| 監査ログボリュームの保持期間が満了するまで、ボリューム・SVM・当該 SVM が属するファイルシステムのいずれも削除できないこと（Enterprise モードでも同じ）、Enterprise ボリュームの削除に `fsx:BypassSnapLockEnterpriseRetention` 権限が必要であること | [AWS: Deleting SnapLock volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snaplock-delete-volume.html) |
| 監査ログの最小保持期間が 6 か月であること、SVM あたり 1 つであること | [NetApp KB: What is the minimum retention of SnapLock audit log?](https://kb.netapp.com/Advice_and_Troubleshooting/Data_Protection_and_Security/SnapLock/What_is_the_minimum_retention_of_SnapLock_audit_log%3F) |
| `CreateSnaplockConfiguration` のフィールドが 6 つであること、`RetentionPeriod` がボリュームの保持期間であること、`AuditLogVolume=true` で監査ログボリュームになり最小保持期間が 6 か月であること | [AWS API Reference: CreateSnaplockConfiguration](https://docs.aws.amazon.com/fsx/latest/APIReference/API_CreateSnaplockConfiguration.html) |
| 監査ログの保持期間を `snaplock log create -retention-period` で指定すること、既定・最小が 6 か月であること、削除ファイルの保持期間が長い場合はログ側が延長されること | [NetApp Docs: Create an ONTAP SnapLock-protected audit log](https://docs.netapp.com/us-en/ontap/snaplock/create-audit-log-task.html) |
| 保持期間満了まで監査ログを削除できないこと、満了後も変更できないこと（Compliance / Enterprise 共通） | [NetApp Docs: Create an ONTAP SnapLock-protected audit log](https://docs.netapp.com/us-en/ontap/snaplock/create-audit-log-task.html) |
| 監査ログ指定の解除 API（アクティブなログを閉じ、SnapLock ロギング対象外にする） | [NetApp Docs: Disassociate SnapLock audit logs](https://docs.netapp.com/us-en/ontap-restapi/delete-storage-snaplock-audit-logs-.html) |
| 満了した WORM ファイルには特権削除を実行できないこと | [AWS: Understanding SnapLock Enterprise](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snaplock-enterprise.html) |
| 恒久無効化後はファイルの削除が満了後のみになること | [NetApp KB: Can I delete snaplock files after privileged delete is set to permanently disabled](https://kb.netapp.com/on-prem/ontap/DP/SnapLock/SnapLock-KBs/Can_I_delete_snaplock_files_after_privileged_delete_is_set_to_permanently_disabled) |

---

## 関連ドキュメント

- [Domain — セキュリティ・ガバナンス](../README.md) — このモジュールのハブ
- [SnapLock は有効化とロックが別](../../data-protection/notes/snaplock-and-layered-ransomware-readiness.md#監査ログボリュームによるファイルシステム全体の-6-か月固定) — 機能側の詳細と全エラー
- [IaC の境界は API の表面で決まる](../../../playbooks/04-build/notes/what-iac-cannot-reach.md) — AWS API が届かない操作の一覧
- [本番投入前レビュー](../../../playbooks/04-build/checklists/pre-production-review.md#不可逆な項目の一覧) — 不可逆項目の一覧
- [上限値・クォータ](../../../reference/limits/) — エラーコードを含む全記録
- [知見の分類ポリシー](../../../evidence-policy.md)
- [監査ログボリューム — コンソールでの操作ポイント](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/ja/snaplock-audit-log-console-guardrails.md) — 実画面 3 枚。作成画面の警告の範囲、保持期間の 3 欄の意味、詰まった後に読むフィールド

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — セキュリティ・ガバナンス](../README.md)
