---
title: 本番投入前レビュー — 後から変えられない項目と、上限に当たる項目を先に確定する
lifecycle: [design, build, operate]
domains: [security-governance, performance, data-protection]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/storage-capacity-and-IOPS.html
lang: ja
---

# 本番投入前レビュー

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 04 — 構築](../README.md)

---

## このチェックリストの位置づけ

Amazon FSx for NetApp ONTAP を本番に入れる直前に確認する項目です。**目的は 2 つだけです。**

1. **後から変えられない項目**を、変えられるうちに確定する
2. **上限や閾値に当たる項目**を、当たる前に把握する

それ以外の「あとで調整できること」は意図的に含めていません。チェックリストが長いほど実行されなくなるためです。

> **Evidence**: `documented` — 閾値と挙動は AWS / ベンダーの公式ドキュメントに基づきます。
> **自環境の実測値は含みません。** 数値が判断に効く項目は、必ず自環境で測ってから確定してください。
> 手順は [本番に取り入れる前の確認](../../../evidence-policy.md#本番に取り入れる前の確認) にあります。

---

## 1. 後から変えられない項目

**ここを飛ばすと、作り直し以外の選択肢がなくなります。** 最優先で確認してください。

- [ ] **SnapLock を使うかどうかを決めた**。有効化は不可逆です。「機能を有効にする」ことと「実際にロックがかかる」ことは別で、ロックを発生させるのは保持期間の設定です
- [ ] **S3 Access Point の `NetworkOrigin`（`Internet` / `VPC`）を決めた**。作成後に変更できません。`Internet` オリジンは S3 Gateway VPC エンドポイント経由では到達しません
- [ ] **ボリュームのセキュリティスタイル（UNIX / MIXED / NTFS）を決めた**。これは「保存できるプロトコル」ではなく「権限評価に使うモデル」を決めます。詳細は [セキュリティスタイルが権限評価のモデルを決める](../../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md)
- [ ] **ボリューム名の命名規則を決めた**。使えるのは英数字とアンダースコアのみです。ハイフンを含む命名規則を全社標準にしている場合、ここで衝突します
- [ ] **SVM の NetBIOS 名を決めた**。15 文字以内、AD ドメインの短縮名とは別の名前、同一 AD 内で一意。AD 参加に失敗した名前は再利用しないでください（AD 側に計算機アカウントが残ります）

---

## 2. 容量とスループット

- [ ] **SSD 層の使用率が 80% を超えない計画になっている**。AWS は 80% 以下を推奨しています。超えるとデータのティアリング、スループットのスケーリング、その他の保守処理が正常に機能しなくなります
- [ ] **SSD 層が 98% に達するとティアリングが完全に停止することを把握した**。使用率に応じて挙動が段階的に変わります。50% 以下では All ポリシー以外はティアリングせず、90% 以上では容量プールから SSD への読み戻しが止まり、**98% 以上でティアリング機能そのものが停止**します
- [ ] **容量プール層に置くデータのレイテンシ要件を確認した**。SSD 層はサブミリ秒、容量プール層は数十ミリ秒の水準です。レイテンシに敏感なデータをティアリング対象にしていないか確認してください
- [ ] **スループットと IOPS のプロビジョニング値を、実測に基づいて決めた**。ドキュメントの上限値ではなく、自環境のワークロードで測った値が根拠になります
- [ ] **バックグラウンド処理が遅くなる前提を織り込んだ**。FSx for ONTAP はクライアントトラフィックをバックグラウンドタスク（ティアリング、ストレージ効率化、バックアップ）より優先します。ピーク時にバックアップが想定どおり終わらない可能性を検討してください
- [ ] **上限値に当たらないことを確認した**。[上限値・クォータ](../../../reference/limits/) の各項目は検証日付きです。日付が古い項目は再確認してください

---

## 3. ID とアクセス（Active Directory を使う場合）

- [ ] **AD 参加に必要なポートが、SVM の ENI から DC へ開いている**。DNS 53、Kerberos 88 / 464、LDAP 389 / 636、SMB 445、RPC 135 と動的ポート、グローバルカタログ 3268、AD Web Services 9389、NTP 123
- [ ] **`FileSystemAdministratorsGroup` に指定するグループを決めた**。権限が不足すると SVM の AD 参加が失敗し、`MISCONFIGURED` 状態になります
- [ ] **OU のパスを実際の AD 構成で確認した**。AWS Managed Microsoft AD はドメイン短縮名の中間 OU を作ります。中間 OU を省いたパスは、エラーにならず静かに失敗する形で現れます
- [ ] **AD が到達不能になったときの影響範囲を把握した**。AD 参加済み SVM では、AD DC への到達性が失われるとアクセスが成立しなくなります。単なる認証遅延では済みません
- [ ] **管理者グループに属さない一般ユーザーでアクセス制御を検証した**。管理者相当のアカウントは一部の制御を素通りします

---

## 4. データ保護

- [ ] **Snapshot のスケジュールと保持期間が、復旧目標（RPO / RTO）から導かれている**。既定値をそのまま使っていないか確認してください
- [ ] **復元を実際に試した**。Snapshot が取れていることと、復元できることは別の確認項目です
- [ ] **Snapshot が消費する容量を容量計画に含めた**
- [ ] **複製（SnapMirror）を使う場合、切り替えと切り戻しの手順を文書化した**

---

## 5. 監視

- [ ] **Amazon CloudWatch のメトリクスとアラームを設定した**。少なくとも SSD 使用率、スループット、IOPS、レイテンシ
- [ ] **SSD 使用率 80% に対するアラームがある**。到達してから気づく設計になっていないか確認してください
- [ ] **性能が出ないときの切り分け手順を決めた**。プロビジョニング値に張り付いている場合はスロットリングが起きています
- [ ] **S3 Access Point を使う場合、イベント駆動の方式を決めた**。S3 Event Notifications は使えません。Amazon EventBridge Scheduler によるポーリングか FPolicy を選択します

---

## 6. 移行・切り替え（該当する場合）

- [ ] **移行方式を決定ツリーで確定した**。[移行方式 決定ツリー](../../../reference/decision-trees/migration-method.md)
- [ ] **切り戻し手順を、切り替え手順と同じ精度で用意した**
- [ ] **移行中の SSD 使用率を監視する準備をした**。移行はティアリングが追いつかないうちに SSD を埋めます
- [ ] **ACL / 権限の保持を、移行後にサンプル検証する手順を決めた**

---

## 不可逆な項目の一覧

**この表の項目は、決め直しに作り直しが伴います。** 設計レビューで明示的に承認を取ってください。

| 項目 | 変更できるか | 変更したい場合 |
|---|---|---|
| SnapLock の有効化 | 不可 | 新しいボリュームを作成してデータを移す |
| S3 Access Point の `NetworkOrigin` | 不可 | Access Point を作り直す |
| ボリューム名 | 不可 | 新しいボリュームを作成してデータを移す |
| ボリュームのセキュリティスタイル | 可（ただし権限評価が変わる） | 影響範囲を確認してから変更する |
| SVM の NetBIOS 名 | 可（ただし AD 側に痕跡が残る） | 新しい名前を使う。失敗した名前は再利用しない |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| SSD 層 80% 推奨、ティアリングと保守処理への影響 | [AWS: File system storage capacity and IOPS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/storage-capacity-and-IOPS.html) |
| 使用率ごとのティアリング挙動（50% / 90% / 98%） | [AWS re:Post: Modify storage data tiering policies](https://repost.aws/knowledge-center/fsx-ontap-modify-data-tiering) |
| 層ごとのレイテンシ水準（サブミリ秒 / 数十ミリ秒） | [AWS Storage Blog: How to size an FSx for ONTAP file system](https://aws.amazon.com/blogs/storage/how-to-size-an-amazon-fsx-for-netapp-ontap-file-system/) |
| クライアントトラフィックがバックグラウンドタスクより優先される | [AWS: Migrating to FSx for ONTAP using SnapMirror](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/migrating-fsx-ontap-snapmirror.html) |
| 移行中にティアリングが追いつかない場合の挙動 | [AWS Storage Blog: Cloud Write mode for petabyte-scale migrations](https://aws.amazon.com/blogs/storage/streamline-petabyte-scale-data-migrations-with-cloud-write-mode-on-amazon-fsx-for-netapp-ontap/) |
| ティアリングポリシーと容量の動的割り当て | [AWS: Managing storage capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-storage-capacity.html) |
| 性能警告と推奨事項 | [AWS: Performance warnings and recommendations](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance-insights-FSxN.html) — AWS 側の URL に由来する表記です <!-- allow:naming --> |
| スループット / IOPS スロットリングの切り分け | [AWS re:Post: Troubleshoot slow performance](https://repost.aws/knowledge-center/fsx-ontap-fix-slow-performance) |

---

## 関連ドキュメント

- [Playbook 04 — 構築](../README.md) — このモジュールのハブ
- [Playbook 02 — 設計](../../02-design/) — 不可逆項目はここで確定させる
- [Playbook 05 — 運用](../../05-operate/) — 監視とインシデント対応
- [監視は平均値で失敗する](../../05-operate/notes/monitoring-fails-on-averages.md) — 監視を入れる前に統計値を決める
- [Snapshot があることと復旧できることは別](../../../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md#自分の環境で確かめる) — 復元を実際に試す手順
- [上限値・クォータ](../../../reference/limits/) — 出典と検証日付きの上限値
- [知見の分類ポリシー](../../../evidence-policy.md) — `documented` の扱いと本番投入前の確認
- [ナビゲーションガイド](../../../navigation.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 04 — 構築](../README.md)
