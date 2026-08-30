---
title: 棚卸しチェックリスト — 後で戻せない判断に必要な数値から逆算して採取する
lifecycle: [assess]
domains: [performance, multiprotocol-identity, cost]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html
lang: ja
---

# 棚卸しチェックリスト

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 01 — 評価](../README.md)

---

## このチェックリストの位置づけ

Amazon FSx for NetApp ONTAP へ移行する前に採取する項目です。**網羅的な現状調査の一覧ではありません。** 収録の基準は 1 つで、**後のフェーズで戻せない判断の入力になるかどうか**です。

各項目に「これが無いと何が決められないか」を併記しています。**用途の書けない項目は採取しないでください。** 集めた数値が使われないと、次回の棚卸しが省略されるようになります。

> **Evidence**: `documented` — 上限値と既定の挙動は AWS / ベンダーの公式ドキュメントに基づきます。
> **自環境の実測値は含みません。** 実測が必要な項目には「実測」と書いています。
> 本リポジトリの検証環境での実測値は [上限値・クォータ](../../../reference/limits/) にあり、**ドキュメント記載値と一致しなかった項目**も記録しています。

---

## 1. 数量の把握 — 容量だけでは不足

- [ ] **総容量**。SSD 層のプロビジョニング量と、階層化の設計に効きます
- [ ] **ファイル数**。**容量が余っていても inode を使い切ると新規作成が失敗します。** 既定は 32 KiB あたり 1 個の比率で割り当てられ、後から引き上げる操作は ONTAP CLI 側です。用途は [容量が余っていても書けなくなる](../notes/counting-bytes-is-not-counting-files.md)
- [ ] **ディレクトリ数と、1 ディレクトリあたりの最大エントリ数**。移行ツールの完走に影響します
- [ ] **最大ファイルサイズ**。**50 GiB を超えるファイルは FSx for ONTAP S3 AP 経由では投入できません。** NFS / SMB 経由にする分岐です
- [ ] **単一ボリュームに収める想定容量**。FlexVol の上限は 314,572,800 MiB（300 TiB）で、これを超えるなら FlexGroup になります。FlexGroup は構成要素（constituent）あたり 100 GiB が下限です
- [ ] **ファイルサイズの分布**。大量小ファイルはファイル単位転送のオーバーヘッドが支配的になります。**帯域から所要時間を計算できなくなる**のはこの条件です

---

## 2. 権限と ID — 移行方式への影響

- [ ] **どのセキュリティスタイルに対応する権限を持っているか**（NTFS ACL / UNIX モード / 両方）。移行先ボリュームのセキュリティスタイルの入力になります
- [ ] **コピー実行アカウントが読めない ACL があるか**（実測）。**あるならバックアップモードと対応する特権が必須**で、方式選択が変わります。**「エラーが出なかった」は読めた証拠になりません**
- [ ] **監査設定（SACL）を移行するか**。移行ツールの既定では落ちます。監査要件がある場合は明示的に決めてください
- [ ] **移行元と移行先が同一 AD ドメインか、信頼関係があるか**。無い場合、SID が解決できないため **ID 移行の設計が先に必要**です
- [ ] **ローカルアカウントで付与された権限があるか**。ドメインアカウントに寄せる作業が別途発生します
- [ ] **対応物のない共有形態の件数**（社外リンク共有、期限付き共有など）。多いと移行ではなく権限の再設計になります。移行元が SaaS の場合は [Go/No-Go の判断材料](../../03-migrate/notes/saas-source-migration-scoping.md)

---

## 3. プロトコルの実使用 — 設定ではなく使用の確認

- [ ] **実際にアクセスがあるプロトコルを、期間を決めて観測した**（実測）。**「設定されている」と「使われている」は違います。** 用途は [設定されていると使われているは違う](../notes/counting-bytes-is-not-counting-files.md#設定されていると使われているの違い)
- [ ] **SMB のプロトコルバージョン**。**SMB 1.0 では SACL がコピーされません**
- [ ] **NFS のバージョンと、使っているマウントオプション**
- [ ] **ブロックプロトコル（iSCSI / NVMe/TCP）を使うか**。使うなら **HA ペアは 6 組が上限**です。7 組目を追加した時点で使えなくなり、**HA ペアは削除できません**

---

## 4. 機能依存 — 移行のブロッカー

- [ ] **移行元が ONTAP か**。ONTAP なら SnapMirror が候補の中心になります。判断は [移行方式の選択](../../../reference/decision-trees/migration-method.md)
- [ ] **ONTAP の場合、バージョンの組み合わせが互換性マトリクスにあるか**。**「前後 N バージョン」では判断できません。表を引いてください**
- [ ] **Snapshot 履歴を引き継ぐ必要があるか**。必要なら SnapMirror 以外では満たせません
- [ ] **保持しているバージョン履歴・世代数**。全世代を移すと総容量が数倍になります
- [ ] **移行元で使っている機能の一覧**（重複排除、圧縮、暗号化、監査、WORM 保持）。移行先で同じ設定が要るかを確認します
- [ ] **WORM / 保持要件があるか**。**該当する場合、移行先での有効化は不可逆です。** 値と影響範囲を決めるまで有効化しないでください。詳細は [不可逆な操作の承認は作業の承認とは別に取る](../../../domains/security-governance/notes/irreversible-operations-need-separate-approval.md)

---

## 5. 性能ベースライン — 比較できる形での取得

- [ ] **測定期間と統計値を先に決めた**。後から平均値と p99 を突き合わせられません。用途は [性能のベースラインは比較可能な形で取る](../notes/counting-bytes-is-not-counting-files.md#比較可能な形での性能ベースラインの取得)
- [ ] **ピーク時とオフピーク時の両方を取った**（実測）。平均値だけでは移行後の比較に使えません
- [ ] **レイテンシをクライアント側で測った**（実測）。ストレージ側のメトリクスからテールレイテンシは読めません
- [ ] **測定時の構成を記録した**。バージョン、リージョン、クライアント台数、並列度。**構成の記録がない測定値は再現できません**

---

## 6. 移行元が SaaS / クラウドストレージの場合の追加項目

移行元がオンプレミス NAS でない場合、上記に加えて必要になります。詳細は [SaaS からの移行は転送方式より先に移行元の群を確定させる](../../03-migrate/notes/saas-source-migration-scoping.md)。

- [ ] **S3 互換 API（または Blob / NFS / SMB）を公開しているか**
- [ ] **自ホスト OSS の場合、オブジェクトストレージがプライマリストレージか外部ストレージか**。**プライマリストレージではバケットを直接コピーしても復元できず、しかも転送は成功します**
- [ ] **テナント管理者権限を移行期間中に発行できるか**
- [ ] **SaaS ネイティブ形式の割合**。変換は不可逆です
- [ ] **API のレート制限**（実測）。**実測が終わるまで停止時間を確定させないでください**

---

## 採取した数値の扱い

- [ ] **各数値に採取日と採取方法を付けた**。移行の検討が数か月に及ぶ場合、初回の数値は再採取が必要です
- [ ] **実測値とドキュメント記載値を区別して記録した**。食い違った場合は**両方を残します**。片方だけを残すと、どちらの前提で設計したのかが後から分かりません
- [ ] **使われなかった項目を次回の棚卸しから外した**

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| FlexVol の最小・最大サイズ（20 MiB / 314,572,800 MiB）、FlexGroup は constituent あたり 100 GiB 下限・最大 20 PiB | [AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |
| inode の既定比率（32 KiB あたり 1 個）、引き上げ可能な比率、1 ボリュームの絶対上限 | [AWS: Volume storage capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html) |
| iSCSI は HA ペア 6 組以下、NVMe/TCP は第 2 世代かつ 6 組以下、HA ペアは追加後に削除できない | [AWS: Adding high-availability (HA) pairs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/adding-HA-pairs.html) |
| 移行ツールが既定で ACL を含めないこと、SMB 1.0 では SACL がコピーされないこと、同一 AD ドメイン要件 | [AWS: How DataSync handles metadata](https://docs.aws.amazon.com/datasync/latest/userguide/metadata-copied.html) |
| SnapMirror の互換性はマトリクス表で定義されること | [NetApp: Compatible ONTAP versions for SnapMirror relationships](https://docs.netapp.com/us-en/ontap/data-protection/compatible-ontap-versions-snapmirror-concept.html) |

出典は 2026-08-11 に確認しました。**上限値は引き上げられる側に動きます。** 設計判断に使う前に、その時点のドキュメントを引き直してください。

---

## 関連ドキュメント

- [Playbook 01 — 評価](../README.md) — このモジュールのハブ
- [容量が余っていても書けなくなる](../notes/counting-bytes-is-not-counting-files.md) — このチェックリストの根拠。棚卸し項目を「後で戻せない判断」から逆算する考え方
- [移行方式の選択](../../../reference/decision-trees/migration-method.md) — 採取した数値を使う場所
- [SaaS からの移行は転送方式より先に移行元の群を確定させる](../../03-migrate/notes/saas-source-migration-scoping.md) — 移行元が SaaS の場合の追加項目
- [切り替え当日のチェックリスト](../../03-migrate/checklists/cutover.md) — 移行フェーズの実行時
- [上限値・クォータ](../../../reference/limits/) — 出典と検証日付きの上限値、実測との食い違い
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 01 — 評価](../README.md)
