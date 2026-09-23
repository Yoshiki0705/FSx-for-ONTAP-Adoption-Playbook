---
title: 保存時の暗号化は自動、転送時は方式ごとに条件が異なる — 監査ログには記録されない読み取りがある
lifecycle: [design, operate]
domains: [security-governance, multiprotocol-identity]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/data-protection.html
lang: ja
---

# 暗号化は「有効/無効」で語れるか？

保存時は自動で有効、転送時は方式ごとに条件が異なります。まとめて有効とは言えません。

## このノートで学べること

- 保存時の暗号化・KMS キー選択・転送時の方式と経路を、分けて確認する必要があること
- SMB のアクセス監査が 1 オブジェクトにつき最初の読み取りと書き込みしか記録しないこと

## このノートが答えないこと

- 規制・法令への適合性の判断
- LDAP 参加時のプロトコル別の転送時暗号化の適用範囲

## 前提レベル

basic

## 本文

<a id="保存時の暗号化は自動転送時は方式ごとに条件が異なる"></a>

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — セキュリティ / ガバナンス](../README.md)

---

### 結論

**保存時の暗号化は無効化できません。** ファイルシステム作成時に自動で有効になり、データとメタデータの両方が AES-256 で暗号化されます。バックアップも同様です。一方、**使用する AWS KMS キーは設計項目です。** `KmsKeyId` を指定しなければアカウントの Amazon FSx 管理キーが使われ、カスタマーマネージド KMS キーを指定することもできます。CloudFormation では `KmsKeyId` の変更に置換が必要です。

**転送時の暗号化に共通の既定値は置けません。** 方式ごとに条件と設定主体が異なります。

- **Nitro ベースの暗号化**は、対応する Amazon EC2 インスタンスタイプとネットワーク経路の条件を満たすと自動で有効になります。
- **SMB 暗号化の必須化**は SVM 作成時点では無効です。共有単位または SVM 単位で設定します。
- **NFS の Kerberos 暗号化**は NFSv3 / NFSv4 が対象で、詳細ページは Microsoft Active Directory に参加した SVM の子ボリュームを対象として説明しています。
- **IPsec**は SVM とクライアントの両方で有効化と設定が必要です。

そして監査には文書化された穴があります。**SMB のアクセス監査は、1 つのオブジェクトについて最初の読み取りと最初の書き込みしか記録しません。**

> **Evidence**: `documented` — 暗号化の既定値・前提条件・監査イベントの仕様は AWS 公式ドキュメントの記載に基づきます。
> **このノートは規制・法令への適合を判断するものではありません。** 何が問われるかを整理するところまでが範囲で、
> 適合の判断は読者側の監査・法務プロセスに属します。確認手順は「[自分の環境で確かめる](#自環境での確認手順)」にあります。

---

### プラットフォームが提供するものと、自分に残るもの

| 項目 | 誰の作業か | 状態 |
|---|---|---|
| 保存時の暗号化（データ・メタデータ） | プラットフォーム | **自動で有効。無効化できません** |
| バックアップの暗号化 | プラットフォーム | 作成時に自動で暗号化、復元時に自動で復号 |
| KMS キーの選択 | 自分 | 未指定時は Amazon FSx 管理キー。カスタマーマネージド KMS キーも作成時に指定できます |
| Nitro ベースの転送時暗号化 | プラットフォーム | 対応する EC2 クライアント、世代・リージョン、同一またはピア接続 VPC などの条件を満たすと自動 |
| SMB 暗号化の必須化 | 自分 | SVM 作成時は無効。SVM 単位または共有単位で設定 |
| NFS Kerberos 暗号化 | 自分 | NFSv3 / NFSv4 とディレクトリ参加・Kerberos 設定が必要 |
| IPsec | 自分 | SVM とクライアントの両方で有効化・設定が必要 |
| ファイルアクセス監査 | 自分 | 有効化と保存先の設定が必要 |
| 管理 API の記録 | プラットフォーム | CloudTrail が全 API 呼び出しを記録 |
| 権限設計（最小権限） | 自分 | 管理者アカウントの使い分け |
| ウイルススキャン | 自分 | オンデマンドスキャンに対応 |

**「暗号化されているか」への答えは分けて説明する必要があります。** 保存時の有効化、保存時のキー選択、転送時の方式と経路を別々に確認します。

---

### 転送時の暗号化の前提条件

利用できる方式と条件は次のとおりです。

| 方式 | 対象と条件 | 有効化 |
|---|---|---|
| Nitro ベース | 対応する EC2 クライアント。ファイルシステムと同一リージョン、同一 VPC または直接ピア接続された VPC。仮想ネットワーク機器や Transit Gateway などを経由しないこと | 条件を満たすと自動 |
| NFS Kerberos | NFSv3 / NFSv4。詳細ページは Microsoft Active Directory に参加した SVM の子ボリュームを対象に説明 | Kerberos を設定 |
| SMB 暗号化 | SMB 3.0 以降。NTLM と Kerberos のどちらの認証でも使用可能 | SVM または共有で必須化。SVM 作成時は無効 |
| IPsec | NFS、SMB、iSCSI。PSK または証明書で認証 | SVM とクライアントの両方で設定 |

AWS のデータ保護ページは NFS と SMB の Kerberos ベース暗号化について Active Directory または LDAP ドメイン参加を挙げています。一方、転送時暗号化の詳細ページは NFS Kerberos を Microsoft Active Directory に参加した SVM の子ボリュームとして説明しています。**LDAP を使う場合のプロトコル別の適用範囲は、これらのページだけでは一致していません。**

Nitro ベースの暗号化は、第 2 世代では第 2 世代ファイルシステムを提供する全リージョンが対象です。第 1 世代は文書に列挙されたリージョンに限られ、2022 年 11 月 28 日以降に作成されたファイルシステムが対象です。どちらも、対応する EC2 クライアントと上表のネットワーク経路条件を満たしたときに自動で有効になります。

AD 参加そのものが権限評価に与える影響は [セキュリティスタイルが権限評価のモデルを決める](../../multiprotocol-identity/notes/security-style-and-permission-evaluation.md) にあります。

#### SMB 暗号化の強制による、クライアント接続の不可

SMB 暗号化は SVM 作成時点で無効です。有効化は 2 段階で選べます。

- 個別の共有に対して必須にする
- SVM に対して必須にする（その SVM の全共有に適用）

**必須にすると、暗号化に対応していない SMB クライアントはその SVM や共有に接続できなくなります。**

これは「セキュリティを上げる変更」が「接続断を起こす変更」でもあるということです。**対応状況を把握してから有効化してください。** 設定は ONTAP CLI の `vserver cifs security modify` で行い、`vserver cifs security show` で現在値を確認できます。

---

### 監査の 2 つの面と、片方の穴の存在

「誰が何をしたか」は 1 つのログでは追えません。**面が 2 つあります。**

| 面 | 記録されるもの | 仕組み |
|---|---|---|
| 管理面 | ファイルシステムやボリュームの作成・削除・タグ付けなど、**API 呼び出し** | CloudTrail |
| データ面 | エンドユーザーによるファイル・ディレクトリへのアクセス | ファイルアクセス監査 |

CloudTrail は FSx for ONTAP の**全 API 呼び出しを記録します。** ルートか IAM ユーザーか、ロールの一時的な認証情報か、他の AWS サービスからの呼び出しかまで識別できます。

#### 記録されない読み取りの存在

SMB のアクセス監査のうち**ファイルアクセスのカテゴリ**で記録できるイベントには、オブジェクトの open、削除意図付きの open、削除、read / write / 属性取得 / 属性設定、ハードリンク作成、リネーム、アンリンクがあります。

**これで全部ではありません。** ログオン成功 / 失敗 / ログオフは別のカテゴリ（`cifs-logon-logoff`）にあり、有効化すれば記録されます。**AWS のドキュメントの SMB イベント表にはこのカテゴリの行が無いため、表だけを読むと「SMB のログオンは監査できない」と読めてしまいます。** 実測した記録条件は [SMB ログオン監査 — 4624 は記録される](smb-logon-audit-event-coverage.md) にあります。

**このうち read / write のイベント（4663）は、1 つのオブジェクトについて最初の SMB 読み取りと最初の SMB 書き込みだけが記録されます。** 成功・失敗を問いません。1 クライアントが 1 ファイルを開いて連続で読み書きしたときにログが膨張するのを防ぐための仕様です。

**したがって「このユーザーはこのファイルを何回読んだか」は監査ログから答えられません。** 開いたこと、最初に読んだことは分かりますが、回数は残りません。

これは監査対応の最中に気づくと厳しい性質です。**何を答えられる必要があるのかを先に確認してください。**

---

### 権限設計 — 管理者の分離

管理エンドポイントと管理者アカウントは階層が分かれています。

| アカウント | 範囲 |
|---|---|
| `fsxadmin` | ファイルシステム（クラスタ）全体 |
| `vsadmin` | 個別の SVM |

**SVM 単位の運用担当者に `fsxadmin` を渡す必要はありません。** SVM の管理エンドポイントに `vsadmin` で接続すれば、その SVM の設定（SMB 暗号化の強制など）を変更できます。

`vsadmin` のパスワードを設定していない場合は `fsxadmin` を使うことになるため、**最小権限で運用するなら SVM 作成時に `vsadmin` のパスワードを設定してください。** 後から `fsxadmin` を配り始めると、範囲を絞り直すのが難しくなります。

---

### 分離された境界をまたぐときに使える仕組みと、その限界

**このセクションは OT セキュリティの指針ではありません。** ネットワークや管理主体が分離された環境をまたぐときに、**FSx for ONTAP 側で使える仕組みと、それぞれの限界**を整理します。境界の設計そのものは読者側の判断です。

| 仕組み | できること | 限界 |
|---|---|---|
| SnapMirror | **複製先は読み取り専用**なので、片方向の受け渡し先として使えます | **break すると書き込み可能になります。** 読み取り専用は関係が続いている間の性質です。また **NAT に対応していません** |
| S3 Access Point の `NetworkOrigin` | `VPC` を指定すると到達経路を VPC 内に限定できます | **作成後に変更できません。** VPC 内で発生した通信はゲートウェイエンドポイントを使えます。VPN / Direct Connect / Transit Gateway / ピアリング経由で VPC に入る通信を私設経路に限定する場合はインターフェイスエンドポイントが必要です |
| S3 Access Point の `FileSystemIdentity` | 公開する範囲をその ID の権限で絞れます | **全リクエストが 1 つの ID で認可されます。** 境界の向こう側で誰が読んだかは、この層では区別されません |
| デプロイタイプ・AZ・サブネット | 作成時に配置を決められます | **作成後に変更できません。** ネットワーク配置は後から動かせません |
| SVM の AD 参加 | 境界の向こうの AD を使えます | **必要なポートが開いている必要があり、サービスアカウントは生涯有効である必要があります** |

**片方向性を「設定」だと考えないでください。** SnapMirror の読み取り専用は関係の状態に由来する性質で、`break` という 1 コマンドで解除されます。片方向を保証したいなら、**誰が break を実行できるかを権限で縛る**話になります。管理者の分け方は上の [権限設計](#権限設計--管理者の分離) にあります。

**NAT 非対応は経路設計に直接効きます。** 分離された環境では NAT が入りがちなので、SnapMirror を前提にするなら経路を先に確認してください。詳細は [切り戻せる時点はクライアントが書き始めた瞬間に閉じる](../../../playbooks/03-migrate/notes/where-the-rollback-window-closes.md#転送性能に影響する条件) にあります。

**`NetworkOrigin` は作成後に変更できないので、境界設計の前に決める項目です。** 一覧は [本番投入前レビュー](../../../playbooks/04-build/checklists/pre-production-review.md#不可逆な項目の一覧) にあります。

---

### 規制ワークロードで問われる論点

**以下は「何を聞かれるか」の整理です。適合の判断ではありません。**

| 問われること | 事実として答えられること |
|---|---|
| 保存データは暗号化されているか | 自動で有効、AES-256、データとメタデータの両方。無効化できません |
| 鍵は誰が管理するか | AWS KMS。未指定時は Amazon FSx 管理キーで、カスタマーマネージド KMS キーも作成時に指定できます |
| 暗号モジュールの位置づけ | AWS の鍵管理インフラは FIPS 140-2 承認済みの暗号アルゴリズムを使用し、NIST 800-57 の推奨と整合するとされています |
| 転送中は暗号化されているか | **方式と経路ごとに確認します。** Nitro は条件を満たすと自動で有効になり、SMB 必須化・NFS Kerberos・IPsec は個別の設定と前提を確認します |
| 記録を改変・削除できないようにできるか | SnapLock の WORM に Compliance と Enterprise の保持モードがあります |
| エンドユーザーのアクセス記録は残るか | 残ります。ただし**読み取り回数は残りません**（上記の 4663 の仕様） |
| 管理操作の記録は残るか | CloudTrail が全 API 呼び出しを記録します |
| 誰が管理できるか | `fsxadmin` と `vsadmin` で範囲を分けられます |

SnapLock は**有効化が不可逆**です。「機能を有効にすること」と「実際にロックがかかること」は別で、ロックを発生させるのは保持期間の設定です。詳細は [本番投入前レビュー](../../../playbooks/04-build/checklists/pre-production-review.md#不可逆な項目の一覧) にあります。

---

### 判断フロー

```mermaid
graph TD
    A[セキュリティ要件を整理する] --> R[保存時の暗号化]
    R --> R1[暗号化は自動]
    R1 --> KMS{KMS キーを指定するか}
    KMS -->|指定しない| AK[AWS 管理キー]
    KMS -->|指定する| CK[カスタマーマネージド KMS キー]

    A --> T{転送中のデータを暗号化する<br/>方式と経路はどれか}
    T -->|Nitro 対応クライアントと経路| NITRO{Nitro のクライアントと<br/>経路条件を満たすか}
    NITRO -->|全条件を満たす| AUTO[自動で有効]
    T -->|NFS Kerberos| KRB[NFS Kerberos<br/>AD と Kerberos を設定]
    T -->|SMB 暗号化| SMBE[SMB 暗号化<br/>SVM または共有で必須化]
    T -->|IPsec| IPSEC[IPsec<br/>SVM とクライアントで設定]

    SMBE --> CLIENT[非対応クライアントは<br/>接続できなくなる<br/>対応状況を先に確認]

    A --> AUD{何を答える必要があるか}
    AUD -->|誰が資源を作ったか| CT[CloudTrail]
    AUD -->|誰がファイルに触れたか| FA[ファイルアクセス監査]
    AUD -->|何回読んだか| GAP["答えられない<br/>最初の read しか記録されない"]
```

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| 暗号化はまとめて「有効」または「無効」と言える | 保存時の有効化、KMS キー、転送時の方式と経路を分けて確認します |
| 保存時の暗号化は設計項目ではない | 暗号化自体は自動ですが、**Amazon FSx 管理キーかカスタマーマネージド KMS キーかは作成時の選択です** |
| メタデータは暗号化されない | データとメタデータの両方が暗号化されます |
| 転送時暗号化には 1 つの共通既定値がある | Nitro、NFS Kerberos、SMB 暗号化、IPsec で有効化条件が異なります |
| SMB 暗号化は既定で有効 | SVM 作成時点では無効です |
| SMB 暗号化を必須にしても影響はない | **非対応クライアントは接続できなくなります** |
| 監査ログがあれば読み取り回数が分かる | **1 オブジェクトにつき最初の読み取りだけ**が記録されます |
| CloudTrail でファイルアクセスも追える | CloudTrail は API 呼び出しです。ファイルアクセスは別の仕組みです |
| 運用担当者には `fsxadmin` が必要 | SVM 単位の作業は `vsadmin` で足ります |
| SnapLock を有効にすれば即座にロックされる | 有効化とロックは別です。ロックは保持期間の設定で発生します |

---

### 参照した一次情報

| 論点 | 出典 |
|---|---|
| 転送時暗号化の方式、ファイルアクセス監査、オンデマンドウイルススキャン、SnapLock の Compliance / Enterprise モード、責任共有モデル | [AWS: What is Amazon FSx for NetApp ONTAP?](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/what-is-fsx-ontap.html) |
| 保存時暗号化が作成時に自動で有効になること、Kerberos ベースの転送時暗号化が AD または LDAP 参加を前提とすること | [AWS: Data protection in Amazon FSx for NetApp ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/data-protection.html) |
| AES-256、データとメタデータの両方、バックアップの自動暗号化と復元時の復号、Amazon FSx 管理キーが既定でカスタマーマネージド KMS キーも選択できること、KMS 鍵管理インフラが FIPS 140-2 承認アルゴリズムを使用し NIST 800-57 と整合すること | [AWS: Encryption of data at rest](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-at-rest.html) |
| Nitro の自動適用条件、NFS Kerberos・SMB 暗号化・IPsec の対象プロトコルと設定条件 | [AWS: Encrypting data in transit](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-in-transit.html) |
| SMB 暗号化が SVM 作成時に無効であること、共有単位 / SVM 単位で必須化できること、必須化すると非対応クライアントが接続できないこと、`vsadmin` と `fsxadmin` の使い分け | [AWS: Enabling SMB encryption of data in transit](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/enable-smb-encryption.html) |
| `KmsKeyId` を省略すると Amazon FSx 管理キーが使われ、変更には置換が必要なこと | [AWS CloudFormation: AWS::FSx::FileSystem](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-fsx-filesystem.html) |
| 監査可能な SMB イベントの一覧、4663 で最初の読み取りと最初の書き込みのみが記録されること | [AWS: Auditing file access](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-access-auditing.html) |
| 全 API 呼び出しが CloudTrail に記録されること、呼び出し元の識別情報 | [AWS: Monitoring FSx for ONTAP API Calls with AWS CloudTrail](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/logging-using-cloudtrail-win.html) |

---

### 関連ドキュメント

- [Domain — セキュリティ / ガバナンス](../README.md) — このモジュールのハブ
- [セキュリティスタイルが権限評価のモデルを決める](../../multiprotocol-identity/notes/security-style-and-permission-evaluation.md) — AD 連携と権限評価
- [本番投入前レビュー](../../../playbooks/04-build/checklists/pre-production-review.md#不可逆な項目の一覧) — SnapLock ほか不可逆項目
- [Snapshot があることと復旧できることは別](../../data-protection/notes/snapshots-are-not-a-recovery-plan.md) — 復旧の守備範囲
- [デプロイタイプは一度しか決められない](../../../playbooks/02-design/notes/deployment-type-is-decided-once.md) — ファイルシステム単位の不可逆項目
- [知見の分類ポリシー](../../../evidence-policy.md)

---

## 自環境での確認手順

**転送時の暗号化と監査の範囲は、有効化しただけでは確認になりません。** 実際に確かめる手順です。

| # | 手順 | 確認できること |
|---|---|---|
| 1 | SVM の `is-smb-encryption-required` の現在値を確認する | 暗号化が強制されているか。既定は無効です |
| 2 | 暗号化に対応していないクライアントで接続を試す | **必須化したときに切れる範囲。** 本番で有効化する前に把握します |
| 3 | 選んだ転送時暗号化方式のクライアント・経路・ディレクトリ条件を確認する | Nitro の自動適用、NFS Kerberos、SMB 必須化、IPsec のどれが成立するか |
| 4 | ファイルアクセス監査を有効にし、同じファイルを 2 回読む | **2 回目が記録されないことを確認する。** 監査で答えられる範囲の実測 |
| 5 | ファイルの削除・リネームを行い、対応するイベントを確認する | どの操作が追跡できるか |
| 6 | CloudTrail でボリューム作成イベントを検索する | 管理面の記録が取れているか |
| 7 | `vsadmin` のパスワードが設定済みかを確認する | `fsxadmin` を配らずに運用できるか |

手順 4 が最も重要です。**「監査ログを有効にした」ことと「監査で問われることに答えられる」ことは別です。**

手順 2 は検証環境で行ってください。本番で必須化すると接続断が起きます。

SMB 暗号化の現在値は次の読み取り専用コマンドで確認できます。

```bash
ssh <svm-management-endpoint> vserver cifs security show
```

### 期待結果

```text
Is SMB Encryption Required の現在値（true / false）
```

この確認で分かるのは SMB 暗号化の強制状態だけです。転送時暗号化の他方式、保存時のキー選択、監査の網羅性は証明しません。

## Read next

[S3 Access Point の認可は 2 層のどちらで絞るか？](access-point-authorization-layers.md)
