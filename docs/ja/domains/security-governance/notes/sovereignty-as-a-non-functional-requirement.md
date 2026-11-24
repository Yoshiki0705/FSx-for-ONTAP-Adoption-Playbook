---
title: 主権はワークロードごとに非機能要件として決める：隔離と制御は別のもの
lifecycle: [design, operate]
domains: [security-governance, data-protection]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copy-backups.html
lang: ja
---

# Amazon FSx for NetApp ONTAP のデータの主権は、何をワークロードごとに決めるか？

主権は非機能要件としてワークロードごとに決め、コスト、性能、復旧力と引き換えにします。隔離と制御は別のものです。

<!-- lang-switcher:start -->
🌐 [日本語](sovereignty-as-a-non-functional-requirement.md) | [English](../../../../en/domains/security-governance/notes/sovereignty-as-a-non-functional-requirement.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->

## このノートで学べること

- 主権を、データの所在、鍵の管理、レプリカとバックアップの宛先、管理面へのアクセス、モデルと推論の所在、デプロイごとの証拠、移動の訓練の 7 軸に分けて決めること
- 隔離（データを別の場所に置くこと）と制御（誰が鍵、コピー、管理面を持つかを決められること）が別のものであること
- 7 軸それぞれについて、この Hub と、Cyber Resilience Patterns などの他のリポジトリにある既存の記録がどこにあり、どの区分（`documented`、`verified`、`hypothesis`、`open`）かということ

## このノートが答えないこと

- 法令、コンプライアンス、規制上の判断
- AWS European Sovereign Cloud での Amazon FSx API の呼び出し結果（そのパーティションのアカウントが要るため行っていません）
- FSx for ONTAP で外部キーストアのキーを使えるかどうか
- 東京から大阪への SnapMirror や、別アカウントへのコピーなど、測っていない移動の所要時間

## 前提レベル

advanced

## 本文

<a id="主権はワークロードごとに非機能要件として決める隔離と制御は別のもの"></a>

[🏠 リポジトリトップ](../../../../../README.md) | [Domain セキュリティ・ガバナンス](../README.md)

---

### 結論

**主権は、ワークロードごとに非機能要件として決めます。** 所在を限り、鍵を自分で持ち、コピーの宛先を絞るほど、費用が増え、使えるリージョンと機能が減り、運用の手間が増えるからです。

AWS CTO のブログ記事 [Tech predictions for 2027 and beyond](https://www.allthingsdistributed.com/2026/11/tech-predictions-for-2027-and-beyond.html)（2026-11-24）は、主権が非機能要件になると予測しています。このノートはその前提を受けて、FSx for ONTAP のデータについて何を決めるかを 7 軸に分けます。**新しい測定は足しません。** 既にある記録へのリンクで判断を組み立てます。

**隔離と制御は別のものです。** 隔離は、データを別のリージョンやパーティションに置くことです。制御は、誰が鍵、コピー、管理面を持つかを決められることです。リージョンを限っても、鍵の種類はファイルシステムの作成時に別に決まり、後から変えられません（下の 2 行目）。

**機微でないデータを過剰に隔離すると、費用がかかり、使える機能が減ります。** 隔離の強さは、データの区分に合わせて決めます。

> **ガバナンスに関する補足**
>
> このノートに書くのは、ガバナンスの考え方と技術的な挙動です。法令やコンプライアンスの判断ではありません。個別の要件への適合は、法務やコンプライアンスの担当者が判断します。

---

### 決めることと既存の記録

区分の語は、[知見の分類ポリシー](../../../evidence-policy.md)の定義に従います。

| 軸 | 決めること | 既存の記録（リンク、区分、日付） |
|---|---|---|
| データの所在 | リージョンとパーティション（商用のパーティションか、AWS European Sovereign Cloud か） | FSx for ONTAP について、AWS のリージョン別提供状況のデータは eusc-de-east-1 を提供ありとしており、SDK のエンドポイントデータは aws-eusc パーティションに fsx、backup、kms を持つ（2026-11-24 に確認、`documented`）。そのパーティションでの API 呼び出しは、そのパーティションのアカウントが要るため行っていない（`open`）。`CopyBackup` はパーティションの中でだけコピーできる（[AWS: Copying backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copy-backups.html)、`documented`） |
| 鍵の管理 | AWS マネージドキーかカスタマーマネージドキーか。外部キーストア（XKS）のキーを使うか。キーはファイルシステムの作成時に決まり、後から変えられない | CloudFormation の `AWS::FSx::FileSystem` の `KmsKeyId` は「Update requires: Replacement」（[AWS: AWS::FSx::FileSystem](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-fsx-filesystem.html)、`documented`）。`update-file-system` にキーを変える引数がないことは、Hub のノート [別アカウントコピーに必要な CMK](../../data-protection/notes/backup-copies-across-regions-and-accounts.md#別アカウントコピーに必要な-cmk--判断はファイルシステム作成前) が AWS CLI で確かめている。AWS マネージドキーで暗号化したファイルシステムのバックアップは、論理エアギャップボールトへコピーされない（`documented`）。手動のコピージョブは `KMS_KEY_ERROR` で失敗した（2026-11-22、ap-northeast-1、1 回、`verified`）。記録は Cyber Resilience Patterns の [論理エアギャップボールトのガイド](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/aws-backup-logically-air-gapped-vault.md)。外部キーストア（XKS）: AWS KMS の文書は、対称のカスタマーマネージドキーに対応するサービスは外部キーストアのキーにも対応すると書く（[AWS KMS: External key stores](https://docs.aws.amazon.com/kms/latest/developerguide/keystore-external.html)、`documented`）。FSx for ONTAP で外部キーストアのキーを使うことは測っていない（`hypothesis`）。トレードオフ: 外部キーマネージャーが使えない間は、そのキーで守るデータを復号できない（同じ KMS の文書、`documented`） |
| レプリカとバックアップの宛先 | コピーとレプリケーションをどのリージョン、どのアカウントへ送るか。宛先を限定するガードを置くか | Hub のノート [バックアップコピーはリストアするまでファイルシステムを持たない](../../data-protection/notes/backup-copies-across-regions-and-accounts.md)（`CopyBackup` と AWS Backup による東京から大阪へのコピーとリストア、2026-08-28〜29、`verified`）。Cyber Resilience Patterns の [論理エアギャップボールトのガイド](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/aws-backup-logically-air-gapped-vault.md)（同じ組織の 2 アカウントの間で AWS RAM によるボールトの共有と復元を各 1 回、2026-10-12、`verified`）。Lakehouse Integrations の [SnapMirror の調査記録](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/integrations/snapmirror-flexcache-multicloud/docs/ja/research.md)（東京から us-west-2 への SnapMirror を break し、宛先に S3 Access Points をつなぎ直すまで約 3 分、2026-07-22、SM-VAL-008〜011、`verified`）。ガード: `fsx:CopyBackup` に `aws:RequestedRegion` の条件を付けて宛先リージョンを限定する。条件の中身は Hub のノートの [意図しないリージョンへコピーさせないガード](../../data-protection/notes/backup-copies-across-regions-and-accounts.md#意図しないリージョンへコピーさせないガード) にある |
| 管理面へのアクセス | `fsxadmin` の認証情報を入れたシークレットとそのレプリカのリージョン。管理エンドポイントに到達できるネットワーク | Hub のノート [管理アカウントのロックアウトと復旧](../../../playbooks/05-operate/notes/admin-account-lockout-and-recovery.md)（日本語だけのページ。ロックの挙動と復旧の記録、2026-09-02、ap-northeast-1、`verified`） |
| モデルと推論の所在 | Amazon Bedrock の推論プロファイルの地理的範囲（`global.`、`apac.` などの地域、`jp.` などの国内）。RAG のベクトルストアの置き場所 | S3 Access Points Serverless Patterns の [推論プロファイルの文書](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/bedrock-inference-profiles.md)。そのリポジトリの CI ゲートはモデル ID の直書きを拒否するが、推論プロファイルの地理的範囲までは強制しない。ベクトルストアは、Agentic Access-Aware RAG の [Managed Knowledge Base への移行評価](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG/blob/main/docs/en/managed-kb-migration-evaluation.md) の 3.2 節が、ベクトルデータの置き場所を明示的に管理する必要があるなら現在の構成を残すと述べる |
| デプロイごとの証拠 | 作ったファイルシステムが、決めたとおりの所在と鍵になっていることを、何で示すか | Cyber Resilience Patterns の [読み取り専用の設定プローブ](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/adversarial-configuration-probe.md) が、出力の `residency` に、リージョン、キーの管理者と Origin、このリージョンにあるバックアップのコピー元リージョン、SnapMirror の送信先、クラスタのピアをまとめる。同じリポジトリの [テンプレートの検査](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/tests/test_fsx_kms_customer_key.py) は、テンプレートが作るファイルシステムがすべてカスタマーマネージドキーで暗号化されることを確かめる。AWS Config のサポート対象のリソースタイプに `AWS::FSx::*` はない（[AWS Config: Supported resource types](https://docs.aws.amazon.com/config/latest/developerguide/resource-config-reference.html)、2026-11-24 に確認、`documented`）ので、FSx for ONTAP 側の証拠はスクリプトか IaC から取る。2026-11-23 に、FSx for ONTAP の Snapshot、クローン、SnapMirror を Amazon FSx のコンソール、API、AWS CloudFormation から管理できるようになったと告知された（[What's New](https://aws.amazon.com/about-aws/whats-new/2026/11/amazon-fsx-for-netapp-ontap-additional-resources/)）ので、レプリケーションの宛先をテンプレートで宣言してレビューできる |
| 移動の訓練 | 別のリージョン、パーティション、推論プロファイルへ実際に移せることを、事前に訓練するか | 測ったものは 3 行目の記録。測っていないもの（`open`）: 東京から大阪への SnapMirror の初回転送、break、逆方向の再同期と戻し。増分コピー。請求された転送料。別アカウントへのコピー。RAG の推論プロファイルを切り替える訓練。追跡は [Issue #440](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/440) |

---

### 選び方

区分は例です。自組織のデータ分類に読み替えてください。どの区分でも、厳しくする側は費用と運用の手間を、緩める側は後から変えられない選択の制約を、それぞれ引き受けます。

| 区分 | 所在 | 鍵 | コピーの宛先 | 代わりに失うもの |
|---|---|---|---|---|
| 公開・機微でない | 商用のパーティション。リージョンは提供状況と費用で選ぶ | AWS マネージドキーでもよい | 同じリージョン、または別リージョン | 緩める側の制約: AWS マネージドキーを選ぶと、後からキーを変えられず、論理エアギャップボールトへのコピーも使えない（2 行目）。厳しくしない分、費用と手間は最も少ない |
| 社内 | 商用のパーティション。使うリージョンを組織の方針で決める | カスタマーマネージドキー。作成前に決める | 別リージョン、別アカウント。別アカウントへ送るなら、キーの判断を作成前に済ませる | キーの運用の手間。作成後にキーを変えられないので、決め直しはファイルシステムの作り直しになる |
| 規制対象の個人データ | データを置くリージョンを要件で限る。必要ならパーティションも限る | カスタマーマネージドキー | 許可したリージョンだけ。`fsx:CopyBackup` に `aws:RequestedRegion` の条件を付ける | 使えるリージョンと復旧先の選択肢が減る。ガードの維持と、宛先ごとの訓練（7 行目）の手間が増える |
| 特別な類型のデータ（健康、生体など） | パーティションまで限る（例: AWS European Sovereign Cloud）。そのパーティションで使えるサービスだけを使う | カスタマーマネージドキー。外部キーストアのキーは候補だが、FSx for ONTAP での動作は未測定（`hypothesis`） | そのパーティションの中だけ。`CopyBackup` はパーティションをまたげない | 外部キーマネージャーが使えない間は、そのキーで守るデータを復号できない（`documented`）。パーティションをまたぐ復旧ができない。使えるサービスが減る。fsx、backup、kms の提供は確認したが、ほかのサービスは未確認で、API 呼び出しも未実施（`open`） |

最も厳しい区分には、鍵の可用性が外部のキーマネージャーに依存すること、パーティションをまたげないこと、使えるサービスが減ることの 3 つの制約があります。**この区分を選ぶのは、その制約を引き受けても守りたいデータがあるときだけにします。**

モデルと推論の所在（5 行目）はこの表の列に入りません。区分ごとに、推論プロファイルの地理的範囲とベクトルストアの置き場所を別に決めます。

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| 隔離すれば制御できる | 隔離は場所の話です。鍵と管理面を誰が持つかは別に決めます。リージョンを限っても、キーの種類は作成時に決まり、後から変えられません（2 行目） |
| 別アカウントにコピーすれば削除に耐える | 隔離が成立する条件を満たさないと、元のアカウントの管理者がコピーを消せます。条件は Hub のノートの [隔離が成立する条件](../../data-protection/notes/backup-copies-across-regions-and-accounts.md#隔離が成立する条件) にあります |
| キーはあとからカスタマーマネージドキーに替えられる | `KmsKeyId` の更新は置き換えを要します（2 行目、`documented`）。キーの選択はファイルシステムの作成前に決めます |

---

### 参照した一次情報

| 論点 | 出典 |
|---|---|
| ブログ記事の題名と公開日（内容は写していません） | [AWS CTO のブログ記事: Tech predictions for 2027 and beyond](https://www.allthingsdistributed.com/2026/11/tech-predictions-for-2027-and-beyond.html)（2026-11-24） |
| `CopyBackup` がパーティションの中でだけコピーできること | [AWS: Copying backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copy-backups.html) |
| `KmsKeyId` が置き換えを要する更新であること | [AWS: AWS::FSx::FileSystem](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-fsx-filesystem.html) |
| 外部キーストアのキーの対応範囲と、外部キーマネージャーが使えない間の制約 | [AWS KMS: External key stores](https://docs.aws.amazon.com/kms/latest/developerguide/keystore-external.html) |
| キーの管理者と Origin を返す API | [AWS KMS: KeyMetadata](https://docs.aws.amazon.com/kms/latest/APIReference/API_KeyMetadata.html) |
| AWS Config のサポート対象のリソースタイプ | [AWS Config: Supported resource types](https://docs.aws.amazon.com/config/latest/developerguide/resource-config-reference.html) |
| Snapshot、クローン、SnapMirror の管理面の追加 | [What's New](https://aws.amazon.com/about-aws/whats-new/2026/11/amazon-fsx-for-netapp-ontap-additional-resources/) |
| 論理エアギャップボールトへのコピーの失敗と共有の記録 | [Cyber Resilience Patterns の論理エアギャップボールトのガイド](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/aws-backup-logically-air-gapped-vault.md) |
| デプロイごとの所在の出力と、鍵の検査 | [読み取り専用の設定プローブ](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/adversarial-configuration-probe.md)、[テンプレートの検査](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/tests/test_fsx_kms_customer_key.py) |
| 別リージョンの SnapMirror 宛先を break して S3 Access Points をつなぎ直すまでの時間 | [SnapMirror の調査記録](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/integrations/snapmirror-flexcache-multicloud/docs/ja/research.md) |
| 推論プロファイルの接頭辞が表す地理的範囲 | [推論プロファイルの文書](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/bedrock-inference-profiles.md) |
| ベクトルデータの置き場所を管理する要件があるときの判断 | [Managed Knowledge Base への移行評価](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG/blob/main/docs/en/managed-kb-migration-evaluation.md) |

---

### 関連ドキュメント

- [Domain セキュリティ・ガバナンス](../README.md)：このモジュールのハブ
- [バックアップコピーはリストアするまでファイルシステムを持たない](../../data-protection/notes/backup-copies-across-regions-and-accounts.md)：コピーの宛先、キーの判断、隔離が成立する条件
- [管理アカウントのロックアウトと復旧](../../../playbooks/05-operate/notes/admin-account-lockout-and-recovery.md)：管理面の認証情報
- [知見の分類ポリシー](../../../evidence-policy.md)

---

## 自環境での確認手順

読み取りだけの手順です。値は `<...>` のプレースホルダに置き換えてください。

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `aws fsx describe-file-systems --file-system-ids <file-system-id> --query "FileSystems[0].KmsKeyId"` でキーの ARN を見る | ファイルシステムがどのキーで暗号化されているか |
| 2 | `aws kms describe-key --key-id <key-arn> --query "KeyMetadata.[KeyManager,Origin]"` で管理者と Origin を見る | キーを AWS が管理しているか自分が管理しているか。鍵素材がどこに由来するか |
| 3 | `aws fsx describe-backups --query "Backups[].[BackupId,SourceBackupRegion]"` で、各バックアップのコピー元リージョンを見る | このリージョンのバックアップが、どのリージョンからのコピーか |
| 4 | `aws iam get-policy-version --policy-arn <policy-arn> --version-id <version-id> --query PolicyVersion.Document` で、`fsx:CopyBackup` に `aws:RequestedRegion` の条件があるかを読む | コピーの宛先リージョンを限るガードの有無 |

### 期待結果

```text
"arn:aws:kms:<region>:<account-id>:key/<key-id>"
["CUSTOMER","AWS_KMS"]
[["<backup-id>","<source-region-or-null>"]]
```

1 行目はキーの ARN、2 行目は `[KeyManager, Origin]` の組です。`CUSTOMER` はカスタマーマネージドキー、`AWS` は AWS マネージドキーを示します。外部キーストアのキーは、Origin が `EXTERNAL_KEY_STORE` で表れます（[AWS KMS: KeyMetadata](https://docs.aws.amazon.com/kms/latest/APIReference/API_KeyMetadata.html)）。3 行目はバックアップごとのコピー元で、コピーでないバックアップは `null` です。

この手順で分かるのは、AWS 側に記録された鍵、コピー元、IAM ポリシーの内容です。ONTAP の中にだけある SnapMirror の送信先やクラスタのピアは分かりません。それらは設定プローブの出力で確認します。また、手順 4 は条件が書かれていることを示すだけで、その条件が実際にコピーを拒否することは示しません。

## Read next

[不可逆な操作の承認は作業の承認とは別に取る](irreversible-operations-need-separate-approval.md)
