---
title: 神経と生体の記録を置く前に決めること：ボリュームの分け方、鍵の単位、撤回に応えられる期限
lifecycle: [design, operate]
domains: [security-governance, data-protection]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-at-rest.html
lang: ja
---

# 神経と生体の記録を Amazon FSx for NetApp ONTAP に置くとき、データの側で何を決めるか？

生の記録と派生データでボリュームを分け、鍵がファイルシステム単位であることと、同意の撤回に応えられる期限をコピーごとに数えたうえで置き場所を決めます。

<!-- lang-switcher:start -->
🌐 [日本語](neural-and-biometric-recordings.md) | [English](../../../../en/domains/security-governance/notes/neural-and-biometric-recordings.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->

## このノートで学べること

- 脳波（EEG）や脳磁図（MEG）の生の記録と、そこから作る派生データを、別のボリュームに分ける理由
- FSx for ONTAP の保存時の暗号化がファイルシステム単位の鍵であり、被験者ごとの鍵には別の手段が要ること
- ファイルを削除しても、Snapshot、バックアップ、SnapMirror の宛先、クローンがそれぞれの期限までデータを持つこと
- 生の記録、匿名化したデータ、学習用のデータ、監査と同意の記録を、WORM に置く場合と置かない場合で何を失うか

## このノートが答えないこと

- 個別の組織が神経のデータを取り扱ってよいか、どの文言で同意を取るか（法務と倫理審査が決めます）
- ほかの法域の法令の動き
- NetApp Volume Encryption を FSx for ONTAP で有効にできるか（試していません）
- 被験者ごとの qtree とクォータを組み合わせた構成の実機での再現

## 前提レベル

intermediate

## 本文

<a id="神経と生体の記録を置く前に決めることボリュームの分け方鍵の単位撤回に応えられる期限"></a>

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — セキュリティ・ガバナンス](../README.md)

---

### 結論

**このノートが書くのは、保存と権限の技術的な設計です。法令上の判断でも法的助言でもありません。** 神経のデータを取り扱ってよいか、同意書にどう書くかは、利用者の組織の法務と倫理審査が決めます。

置き場所を決める前に、次の 4 点を決めておく必要があります。

| 決めること | このノートの答え |
|---|---|
| 生の記録と派生データを分けるか | 分けます。保護、保持期間、アクセスの範囲がそれぞれ違うためです |
| 鍵の単位 | FSx for ONTAP の保存時の暗号化は、ファイルシステムごとに選ぶ AWS KMS のキーです。被験者ごとに分けるなら、アプリケーション側か、ファイルシステムの分割が要ります |
| 同意の撤回に応えられる期限 | ファイルを削除しても、コピーはそれぞれの期限まで残ります。期限はコピーごとに数えます |
| WORM に置くか | 置けば期限まで誰も削除できず、置かなければランサムウェアへの備えを別の手段で補う必要があります |

> **Evidence**: 冒頭の `documented` は AWS の文書です（出典は frontmatter の `source`）。法令の動きは、読んだ法案の公開ページだけを引いており `documented` です。
> Cyber Resilience Patterns の記録から引いた観測は、そちらの環境と日付を併記し、このリポジトリでは再測定していません。
> 表の「置き場所」「鍵」の列にある組み合わせは設計上の見解で、`hypothesis` です。

---

### データの性質

脳波（EEG）や脳磁図（MEG）の生の記録は、EDF や FIF のような形式のファイルや、BIDS の形のデータセットとして置かれます。記録の時間に比例してデータが増えます。

置き場所を決めるうえで、次の 2 種類を分けて扱います。

| 種類 | 例 | 性質 |
|---|---|---|
| 生の記録 | 記録装置が書き出したファイル | 被験者と結びつく。同意の撤回の対象になりうる |
| 派生データ | 前処理済みのデータ、特徴量、学習用のデータ | 生の記録から作る。どこまで撤回の対象に含まれるかは、組織の法務と倫理審査が決める |

---

### 法の動き

読んだ一次情報の 2 件だけを書きます。ほかの法域には触れません。いずれも `documented` です。

| 法域と文書 | 内容 |
|---|---|
| 米国コロラド州 [HB24-1058](https://leg.colorado.gov/bills/hb24-1058) | Colorado Privacy Act の「sensitive data」に、神経のデータを含む生体のデータ（biological data）を加えました。対象は、識別の目的で使う、または使うことを意図したデータです。2024-04-17 に知事が承認し、2024-08-07 に施行されました |
| 米国カリフォルニア州 [SB 1223](https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB1223) | 法案の本文が、Civil Code 1798.140 の機微な個人情報（sensitive personal information）に「neural data」を加えています。このノートは法案の本文だけを読んでおり、成立の状況は確認していません |

どちらも、神経や生体のデータを、通常の個人データより厳しく扱う区分へ入れる方向の動きです。自組織のデータにこれらの法令が当たるかは、法務が判断します。

---

### ボリュームの分け方とアクセスの 2 層

生の記録、匿名化したデータ、学習用のデータは、別のボリュームに置きます。保護の方式、保持期間、アクセスの範囲がそれぞれ違うためです。

生の記録のボリュームでは、被験者ごとに qtree を切り、クォータを付ける構成が考えられます。この組み合わせは設計上の見解（`hypothesis`）で、このノートでは実機で試していません。

被験者ごとのアクセスは、2 層で絞ります。

| 層 | 絞る手段 |
|---|---|
| S3 Access Points の認可 | アクセスポイントポリシーの明示的な拒否 |
| ファイルシステム | アクセスポイントに固定した ID の mode bits と ACL |

アクセスポイントポリシーの `Allow` を狭く書いても、同一アカウントでは絞り込みになりません。明示的な拒否の書き方と、ファイルシステム側の権限との独立性は
[S3 Access Point の認可は 2 層のどちらで絞るか？](access-point-authorization-layers.md)にあります。

---

### 保存時暗号化の鍵の単位

FSx for ONTAP は保存時のデータを、ファイルシステムごとに選ぶ AWS KMS のキーで暗号化します（[AWS: Encryption at rest](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-at-rest.html)、`documented`）。

鍵の単位がファイルシステムなので、被験者ごとに鍵を分けるには、アプリケーション側のエンベロープ暗号化か、ファイルシステムの分割が要ります。

ONTAP のボリューム暗号化については、Cyber Resilience Patterns の[読み取り専用の設定プローブ](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/adversarial-configuration-probe.md)が、次を読み取っています（`verified`。そちらの記録の値で、このリポジトリでは再測定していません）。

| 項目 | 値 |
|---|---|
| 対象 | 検証用のファイルシステム |
| ONTAP のバージョン | 9.19.1P4 |
| 測定日 | 2026-11-24 |
| 読み取った内容 | 26 の読み書きボリュームすべてで `encryption.enabled=false`。ONTAP のキーマネージャーはない |

`encryption.enabled=false` は、ONTAP のボリューム暗号化が使われていないことを示します。ファイルシステム単位の KMS による保存時の暗号化が無効であることは示しません。

NetApp Volume Encryption を FSx for ONTAP で有効にできるかは試していません（`open`）。

---

### 同意の撤回と残るコピー

同意の撤回に応えるときは、ファイルを削除するだけでは足りません。Cyber Resilience Patterns の[削除の依頼と削除後も残るコピー](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md)が、次を記録しています。

- ファイルを削除しても、Snapshot、バックアップ、SnapMirror の宛先、クローンが、それぞれの期限までデータを持つ
- 削除したファイルが、Snapshot が残っている間、S3 Access Points から `.snapshot/<Snapshot 名>/<パス>` で読めた（2026-11-24、ap-northeast-1、ONTAP 9.19.1P4、UNIX スタイルのボリューム、`verified`。そちらの記録の値で、このリポジトリでは再測定していません）

SnapLock Compliance のボリュームと、論理エアギャップボールトのコピーは、期限まで誰も削除できません。撤回の対象になりうる生の記録は、そこに置きません。置く場合は、その保持期間を同意書に書きます。WORM の有効化は取り消せないので、保持期間の値を人が名指しする運用が要ります（[不可逆な操作には別の承認が要る](irreversible-operations-need-separate-approval.md)）。

---

### エッジでの取得と write-back

記録装置に近いエッジで取得する場合は、ONTAP Edge to Cloud AI の[AWS IoT と FlexCache の連携シナリオ](https://github.com/Yoshiki0705/ONTAP-Edge-to-Cloud-AI/blob/main/docs/ja/iot-greengrass-flexcache-integration.md)が出発点になります。

そこに記録されているとおり、FlexCache の write-back では、データはまずエッジ側のキャッシュに書かれます。このため、エッジに記録が残る期間を設計で決める必要があります。撤回の依頼を受けたとき、Origin 側のコピーだけを消してもエッジ側に残りうる、というのは設計上の見解（`hypothesis`）で、このノートでは試していません。

---

### 選び方

行は、置くデータの種類です。「WORM に置くか」の列は、置く場合と置かない場合の両方で、失うものを書きます。

| データ | 置き場所 | 鍵 | WORM（SnapLock、論理エアギャップボールト）に置くか | 代わりに失うもの |
|---|---|---|---|---|
| 生の記録（撤回の対象） | 専用のボリューム。被験者ごとの qtree とクォータ | ファイルシステムの KMS キー。被験者ごとに分けるならアプリケーション側のエンベロープ暗号化か、ファイルシステムの分割 | 置かない構成を基本にします | 置かない場合は、ランサムウェアへの備えを別のボリュームや別の保護で補います。ただし、そのコピーも撤回の期限を数える対象です。置く場合は、削除の依頼に期限まで応えられません |
| 匿名化したデータ | 生の記録とは別のボリューム | 同上 | 撤回の対象から外れると組織が判断したときに限り、置く選択肢があります | 置かない場合は、改ざんやランサムウェアへの備えを別の保護で補います。置く場合は、匿名化の判断が後で覆っても、期限まで削除できません |
| 学習用のデータ | 別のボリューム | 同上 | 置かない構成を基本にします | 置かない場合は、学習の再現のためにデータを固定する手段を別に用意します。置く場合は、元の被験者の撤回に期限まで応えられません |
| 監査と同意の記録 | 別のボリューム。被験者を直接識別する内容を含めない設計にします | 同上 | 置く選択肢があります | 置く場合は、期限まで訂正と削除ができません。置かない場合は、記録の改ざんを防ぐ別の手段が要ります |

匿名化したデータが撤回の対象から外れるか、学習用のデータが生の記録の撤回に連動するかは、このノートでは決めません。組織の法務と倫理審査が決めます。

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| ファイルを消せば撤回に応じたことになる | Snapshot、バックアップ、SnapMirror の宛先、クローンが、それぞれの期限までデータを持ちます。削除したファイルが、Snapshot がある間は S3 Access Points から読めた記録があります |
| 保存時暗号化で被験者ごとに鍵が分かれる | 鍵はファイルシステム単位です。被験者ごとに分けるには、アプリケーション側のエンベロープ暗号化か、ファイルシステムの分割が要ります |
| アクセスポイントポリシーに `Allow` を書けば、書いた被験者だけに絞れる | 同一アカウントでは、`Allow` を狭く書いても絞り込みになりません。明示的な拒否とファイルシステムの権限の 2 層で絞ります |
| WORM に置けば、撤回にも安全に応えられる | 期限まで誰も削除できないため、撤回に応えられない期間ができます |

---

### この記述の限界

- 法令の動きは 2 件だけで、読んだのはコロラド州の法案の公開ページとカリフォルニア州の法案の本文です。成立や施行の状況の全体は追っていません。
- 被験者ごとの qtree とクォータの構成は、設計上の見解で、実機では試していません。
- Cyber Resilience Patterns の観測値は、そちらの環境（ONTAP 9.19.1P4、2026-11-24）のものです。このリポジトリでは再測定していません。
- NetApp Volume Encryption を FSx for ONTAP で有効にできるかは、試していません。
- エッジ側のキャッシュに残る期間の挙動は、試していません。

---

### 参照した一次情報

| 論点 | 出典 |
|---|---|
| 保存時の暗号化がファイルシステムごとに選ぶ AWS KMS のキーであること | [AWS: Encryption at rest](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-at-rest.html) |
| 神経のデータを含む生体のデータを sensitive data に加えたこと（2024-04-17 承認、2024-08-07 施行） | [Colorado HB24-1058](https://leg.colorado.gov/bills/hb24-1058) |
| 「neural data」を機微な個人情報に加える法案の本文 | [California SB 1223](https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB1223) |
| ONTAP のボリューム暗号化が使われていなかった読み取りの結果 | [読み取り専用の設定プローブ](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/adversarial-configuration-probe.md) |
| 削除後も残るコピーと、Snapshot から読めた実測 | [削除の依頼と削除後も残るコピー](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md) |
| FlexCache の write-back でデータがまずエッジ側に書かれること | [AWS IoT と FlexCache の連携シナリオ](https://github.com/Yoshiki0705/ONTAP-Edge-to-Cloud-AI/blob/main/docs/ja/iot-greengrass-flexcache-integration.md) |

AWS CTO のブログ記事 [Tech predictions for 2027 and beyond](https://www.allthingsdistributed.com/2026/11/tech-predictions-for-2027-and-beyond.html)（2026-11-24）は、「The mind becomes readable」という予測を示しており、このノートを書くきっかけになりました。記事の内容はここに写していません。

---

### 関連ドキュメント

- [S3 Access Point の認可は 2 層のどちらで絞るか？](access-point-authorization-layers.md)：アクセスポイントポリシーとファイルシステムの権限
- [不可逆な操作には別の承認が要る](irreversible-operations-need-separate-approval.md)：WORM の有効化と保持期間
- [Domain — セキュリティ・ガバナンス](../README.md)：このモジュールのハブ
- [知見の分類ポリシー](../../../evidence-policy.md)

---

## 自環境での確認手順

読み取りだけの手順です。変更は行いません。

| # | 手順 | 確認できること |
|---|---|---|
| 1 | ONTAP REST の `GET /api/storage/qtrees?fields=name,volume.name` | 被験者ごとの qtree がどのボリュームにあるか |
| 2 | ONTAP REST の `GET /api/storage/quota/rules` | qtree にクォータが付いているか |
| 3 | ONTAP REST の `GET /api/storage/volumes?fields=encryption.enabled` | ONTAP のボリューム暗号化が使われているか |
| 4 | `aws fsx describe-file-systems` の `KmsKeyId` | ファイルシステムの保存時の暗号化に使われている KMS キー |
| 5 | ONTAP REST の `GET /api/storage/volumes/<volume-uuid>/snapshots?fields=name,create_time,expiry_time` | 削除後もデータを持つ Snapshot と、その期限 |

```bash
aws fsx describe-file-systems --file-system-ids <file-system-id> --query "FileSystems[0].KmsKeyId"
curl -sk -u <admin-user> "https://<management-ip>/api/storage/qtrees?fields=name,volume.name"
curl -sk -u <admin-user> "https://<management-ip>/api/storage/quota/rules"
curl -sk -u <admin-user> "https://<management-ip>/api/storage/volumes?fields=encryption.enabled"
curl -sk -u <admin-user> "https://<management-ip>/api/storage/volumes/<volume-uuid>/snapshots?fields=name,create_time,expiry_time"
```

### 期待結果

```text
<kms-key-arn>
{"records":[{"name":"<qtree-name>","volume":{"name":"<volume-name>"}}],"num_records":<n>}
{"records":[{"qtree":{"name":"<qtree-name>"},"volume":{"name":"<volume-name>"},"space":{"hard_limit":<bytes>}}],"num_records":<n>}
{"records":[{"name":"<volume-name>","encryption":{"enabled":<true-or-false>}}],"num_records":<n>}
{"records":[{"name":"<snapshot-name>","create_time":"<timestamp>","expiry_time":"<timestamp-or-absent>"}],"num_records":<n>}
```

分かること:

- 被験者ごとの qtree とクォータの有無と、ボリュームの対応
- ファイルシステムの保存時の暗号化に使われている KMS キーの 1 つの値
- ONTAP のボリューム暗号化の有無。`enabled` が `false` でも、ファイルシステム単位の KMS による暗号化が無効であるとは読めません
- Snapshot が残っている間は、削除したファイルのコピーが残ること

分からないこと:

- バックアップ、SnapMirror の宛先、クローンに残るコピーの有無と期限（別の API で調べます）
- 削除したファイルが S3 Access Points から読めるか（アクセスポイントの設定と権限に依存します）
- 組織の法務と倫理審査が、この構成を許すか

## Read next

[S3 Access Point の認可は 2 層のどちらで絞るか？](access-point-authorization-layers.md)
