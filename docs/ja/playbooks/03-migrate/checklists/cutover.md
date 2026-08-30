---
title: 切り替え当日のチェックリスト — 停止時間を決めるのは転送ではなく、停止してから再開するまでの作業
lifecycle: [migrate]
domains: [data-protection, multiprotocol-identity, performance]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/migrating-fsx-ontap-snapmirror.html
lang: ja
---

# 切り替え当日のチェックリスト

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 03 — 移行](../README.md)

---

## このチェックリストの位置づけ

Amazon FSx for NetApp ONTAP へ切り替える当日に確認する項目です。**転送方式の選定は範囲外**で、それは [移行方式の選択](../../../reference/decision-trees/migration-method.md) と、移行元が SaaS の場合は [移行元の群を確定させる](../notes/saas-source-migration-scoping.md) にあります。

**含める基準は 2 つだけです。**

1. **飛ばすと停止時間が伸びる**か、**戻せなくなる**項目
2. **成功したように見えて失敗している**項目

「あとから直せること」は入れていません。当日に読まれないチェックリストは意味がないためです。

> **Evidence**: `documented` — コマンド・状態・制約は AWS 公式ドキュメント、AWS Storage Blog、AWS re:Post に基づきます（出典は末尾）。
> **所要時間は含みません。** 帯域とデータ量に依存するため、[自分の環境で測る](../notes/where-the-rollback-window-closes.md#自環境での確認手順)手順を参照してください。

---

## 0. 前日までに終わっていること

- [ ] **切り戻し手順を、切り替え手順と同じ精度で書いた**。書いてあるだけでなく、**テスト環境で 1 回実行した**
- [ ] **切り替え後に「戻せなくなる瞬間」を全員が把握している**。クライアントが移行先へ書き込んだ時点です。詳細は [切り戻せる時点はクライアントが書き始めた瞬間に閉じる](../notes/where-the-rollback-window-closes.md)
- [ ] **移行元を読み取り専用にする手順と、その解除手順を用意した**
- [ ] **停止時間の告知内容が、実測に基づいている**。転送時間ではなく、**停止してから再開するまでの作業時間**の実測です
- [ ] **移行先の SSD 使用率を監視する準備をした**。移行はティアリングが追いつかないうちに SSD を埋めます
- [ ] **当日の中止条件を決めた**。「どの状態を見たら切り替えをやめるか」を、判断者を含めて決めておきます

### SnapMirror を使う場合の禁止事項

**次の 4 つはいずれも「初期同期からやり直し」になります。** 当日ではなく、計画の時点で運用手順として禁止してください。

- [ ] **移行元で SnapMirror が作成した Snapshot を削除しない**。差分転送は最新の共通 Snapshot（NCS）を基点にするため、失うと差分転送ができません
- [ ] **過去の SnapMirror 関係で使った移行先ボリュームを再利用しない**。新しいボリュームを作成します
- [ ] **移行先ボリュームをオフライン・制限状態にしない**。更新できません
- [ ] **経路に NAT がないことを確認した**。**SnapMirror は NAT に対応しません**

---

## 1. 停止する前（まだ停止時間には入っていません）

**この段階の作業はすべて、クライアントを止めずに実行できます。** ここで済むことを停止後に回すと、そのぶん停止時間が伸びます。

### SnapMirror の場合

- [ ] **最終差分を転送した**（`snapmirror update`）
- [ ] **`Mirror State` が `Snapmirrored`、`Relationship Status` が `Idle` である**
- [ ] **`Last Transfer End Timestamp` が十分に新しい**。**`Idle` は「いま転送していない」という意味で、「最新である」という意味ではありません。** 移行先データの鮮度を表すのはこのタイムスタンプです

### DataSync / ホスト側コピーの場合

- [ ] **直近の差分同期が完走している**。エラーで終わったタスクを「ほぼ終わっている」と扱わないこと
- [ ] **転送されなかったファイルの一覧を確認した**。ロックされていたファイル、パスが長すぎるファイル、権限で読めなかったファイル
- [ ] **ACL が保持される設定になっている**。既定値では落ちます。詳細は [ACL 保持は権限の問題であってツールの問題ではない](../notes/preserving-acls-during-migration.md)

---

## 2. 停止中（ここが停止時間です）

**停止時間はこの区間だけです。** 転送は前段で終わっています。短縮の対象は転送ではなく、ここの作業です。

- [ ] **クライアントを停止した**（ここから停止時間）
- [ ] **移行元を読み取り専用にした**。切り替え後に移行元へ書き込まれると、どちらが正本か分からなくなります
- [ ] **SnapMirror の場合、`snapmirror quiesce` を実行し、`Relationship Status` が `Quiesced` になった**
- [ ] **SnapMirror の場合、`snapmirror break` を実行した**。ここで移行先が読み書き可能になります。**この操作は移行元に影響しません**
- [ ] **共有を再マウントした**（SMB / NFS / iSCSI）
- [ ] **DNS / 参照名を切り替えた**。クライアント設定を個別に書き換える方式にしていないか確認してください
- [ ] **クライアントを再開した**（ここまでが停止時間）

---

## 3. 切り替え後の確認

**「エラーが出ていない」は確認になりません。** 静かに失敗する項目があります。

- [ ] **一般ユーザーのアカウントで、自分のファイルを開けることを確認した**。管理者相当のアカウントは一部の権限評価を素通りします
- [ ] **ACL を移行元と比較した**。浅い階層ではなく、**継承の破れ・明示的な拒否・長いパス・実行アカウントが所有していないファイル**を選びます。手順は [自分の環境で確かめる](../notes/preserving-acls-during-migration.md#自環境での確認手順)
- [ ] **所有者が実行アカウントに置き換わっていない**
- [ ] **監査要件がある場合、SACL が残っている**。DACL だけ移して「権限は移行できた」と判断すると、失われたことに気づくのは監査の時です
- [ ] **移行元と移行先のファイル数を比較した**。容量の一致は、ファイルが揃っている証拠になりません
- [ ] **移行先の SSD 使用率を確認した**。80% を超えているとティアリングと保守処理が正常に機能しません
- [ ] **Snapshot のスケジュールが移行先で動いている**。移行先ボリュームは移行元の Snapshot ポリシーを引き継がない場合があります
- [ ] **バックアップの対象になっている**。**`DP` ボリューム（SnapMirror の複製先）はバックアップできません。** `break` 後も種別を確認してください

---

## 4. 切り戻すかどうかの判断

**「切り替え設定を戻す」という手順は存在しません。** 切り戻しは、移行先に書き込まれたデータをどう扱うかの判断です。

- [ ] **クライアントが移行先へ書き込んだかを確認した**。書き込み前なら、移行元を使い続けるだけで戻せます
- [ ] **書き込み済みの場合、その書き込みを破棄するか、複製方向を反転させるかを決めた**。`snapmirror resync` は**利用者が作成した Snapshot を複製しません**。移行先のエクスポート済み Snapshot は削除されます
- [ ] **切り戻しが「元の状態に戻る」ことではないと理解した上で判断した**。新しい状態を作る操作です

---

## 移行完了後（当日ではありませんが、忘れやすい項目）

- [ ] **移行のために発行した権限を取り消した**。SaaS からの移行でテナント全体の読み取り権限を発行した場合、**移行用のアプリケーション登録がそのまま残ります**
- [ ] **移行元の契約終了日と、履歴を残す期間を突き合わせた**。読み取り専用にしてもライセンス費用は契約終了まで発生します
- [ ] **移行に使った一時リソースを削除した**。検証用ボリュームを削除する場合、`SkipFinalBackup=true` を付けないと最終バックアップが作られ、**そのバックアップが次の削除を阻害します**

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| 切り替え手順（状態確認 → `Last Transfer End Timestamp` 確認 → `quiesce` → `break` → マウント）、移行先は `break` まで読み取り専用、タイムスタンプがデータの鮮度を表すこと | [AWS Storage Blog: Migrating on-premises file shares to FSx for ONTAP](https://aws.amazon.com/blogs/storage/migrating-on-premises-file-shares-to-amazon-fsx-for-netapp-ontap/) |
| 移行の全体手順、`snapmirror update` による差分転送 | [AWS: Migrating to FSx for ONTAP using NetApp SnapMirror](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/migrating-fsx-ontap-snapmirror.html) |
| 共通 Snapshot（NCS）への依存、移行先ボリュームの再利用非推奨、オフラインにしないこと、NAT 非対応、効率化ジョブとの同時実行を避けること | [AWS re:Post: How can I optimize SnapMirror performance?](https://repost.aws/knowledge-center/fsx-ontap-optimize-snapmirror) |
| `resync` が利用者作成 Snapshot を複製しないこと、移行先のエクスポート済み Snapshot が削除されること | [AWS re:Post: Why does the snapshot policy stop working after snapmirror resync?](https://repost.aws/knowledge-center/fsx-ontap-snapmirror-resync) |
| SSD 層 80% 推奨と、超過時にティアリング・保守処理へ及ぶ影響 | [AWS: File system storage capacity and IOPS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/storage-capacity-and-IOPS.html) |
| 移行ツールが既定で ACL を含めないこと、必要なユーザー権利 | [AWS: How DataSync handles metadata](https://docs.aws.amazon.com/datasync/latest/userguide/metadata-copied.html) |

出典は 2026-08-11 に確認しました。**手順とコマンドは変わりえます。** 当日の実行前に、自環境のバージョンで確認してください。

---

## 関連ドキュメント

- [Playbook 03 — 移行](../README.md) — このモジュールのハブ
- [切り戻せる時点はクライアントが書き始めた瞬間に閉じる](../notes/where-the-rollback-window-closes.md) — このチェックリストの根拠。差分同期が壊れる条件と切り戻しの選択肢
- [ACL 保持は権限の問題であってツールの問題ではない](../notes/preserving-acls-during-migration.md) — 切り替え後の ACL 検証手順
- [SaaS からの移行は転送方式より先に移行元の群を確定させる](../notes/saas-source-migration-scoping.md) — 移行元が SaaS / クラウドストレージの場合
- [移行方式の選択](../../../reference/decision-trees/migration-method.md) — 当日より前の判断
- [本番投入前レビュー](../../04-build/checklists/pre-production-review.md) — 不可逆な設定の確認
- [Snapshot があることと復旧できることは別](../../../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md) — 移行先が保護対象になっているか
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 03 — 移行](../README.md)
