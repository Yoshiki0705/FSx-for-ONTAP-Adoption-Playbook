# 観点表の行（`analysis-appendix.md` 貼り込み用）

[🏠 リポジトリトップ](../../../../../README.md) | [補助パック](README.md)

---

この表は貼り込み用の生片で、frontmatter を持ちません。貼り込み先の AIMF Playbook の `00-analysis/analysis-appendix.md` の観点表に、下の行をそのまま追記してください。番号は貼り込み先の無印 `MP-N` と衝突しないよう `MP-FSXN-N` を使います（AIMF の `DP-<project>-N` 方式に倣った prefix）。

**種類**は AIMF の観点分類に合わせます。② は「ビルドは通るが実行時 / 本番で黙って壊れる」、③ は「誤った方向へ誘導する」です。**検出コマンドは書きますが、実行結果・件数は書きません。** 実機・実ソースに当てて回していないためです。各行の否定テスト手順と「正しいと言える観測」は [検証スニペット](verify-snippets-fragment.md) にあります。

> **検出器自身が偽陰性になる罠**: `MP-FSXN-1` の大文字小文字の検出は、`test -e` でファイルの実在を判定してはいけません。作業ホスト（macOS）のファイルシステムが大文字小文字を区別しないため、検出器自身が同じ影響を受けて取りこぼします。`git ls-files` が返す実名と `grep -F -x` で厳密に文字列比較します。これは上流 .NET Playbook の `MP-9` / `CP-12` が実測で記録した罠で、FSx for ONTAP の NFS / SMB 差にそのまま効きます。

---

## 貼り込む行

| ID | 観点 | 種類 | 検出コマンド | 参照 |
|----|------|------|------------|------|
| MP-FSXN-1 | 同じ NTFS ボリュームでも、SMB（Windows / cifs）は大文字小文字を区別せず、NFS と FSx for ONTAP S3 Access Points は区別する。パス参照の綴り違いは SMB 経由では露見せず、別経路に移した瞬間に 404 / FileNotFound になる（`field-observation`。SMB / NFS は stage-1、S3 Access Points は stage-3 の、それぞれ各 1 観測・陽性対照つき） | ② | 参照されるパス文字列を抽出し、`git ls-files` の実名と `grep -F -x` で厳密比較する（`test -e` で実在判定しない） | Hub: [SMB の識別と監査の決定木](../../../reference/decision-trees/smb-identity-and-audit.md)、[クライアント到達経路の決定木](../../../reference/decision-trees/client-access-route.md)。出典: App-Mod [stage-1-multiprotocol.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/ja/stage-1-multiprotocol.md)（SMB は区別せず・NFS は区別する）と [stage-3-s3-access-points.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/ja/stage-3-s3-access-points.md)（S3 Access Points は区別する） |
| MP-FSXN-2 | 物理保存パスと返却 URL が別管理で、ストレージをローカル / S3（FSx for ONTAP S3 Access Points）でモード切替する実装は、片方のモードでしか露見しない綴り不一致を持つ。保存は成功し例外も出ず、表示時だけ 404 になる（`hypothesis`。上流 .NET Playbook `MP-10` の類推で、FSx for ONTAP S3 経路での発火は実測していない） | ② | 保存側の `Path.Combine` 等と返却 URL を 1 件ずつ突合する。実体名は `git ls-files` で確認する（ファイルシステムに問い合わせない） | Hub: [S3 Access Points は「S3 として使える」わけではない](../../../domains/data-utilization/notes/s3-access-point-constraints.md) |
| MP-FSXN-3 | FSx for ONTAP S3 Access Points は S3 と同一ではない。非対応 API（条件付き書き込み・Versioning・Lifecycle・Object Lock・Event Notifications）・単一 ID 認可・元 ACL 非継承が、S3 前提のアプリ移行でサイレント障害になる。ビルドは通り、該当 API を叩いた実行時に初めて壊れる（`documented`。AWS 公式） | ② | 使う予定の S3 API を[対応表](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)と突合する。`If-None-Match` / `If-Match` の使用箇所を列挙する（対応表は partial list なので「非対応の網羅」としては引かない） | Hub: [S3 Access Points は「S3 として使える」わけではない](../../../domains/data-utilization/notes/s3-access-point-constraints.md)、[コピーを作らずにデータへ到達する](../../../domains/data-utilization/notes/reaching-data-without-copies.md) |
| MP-FSXN-4 | 書き込みが反対プロトコルで見えるまでの時間は方向で非対称（Linux が書き Windows が読む方向で約 8 秒、逆方向で 100 ms 未満の構成がある）。書き込み完了とオブジェクト / ファイルの出現を同時と仮定した移行コードは、遅い方向で間欠的に空読みする（`field-observation`。各組 1 回の計測。値は構成依存で一般化しない） | ② | 書き込み直後に読む同期処理を列挙し、retry / 待機の有無を突合する。値を一般化しない（構成・プロトコル依存） | Hub: [書き込みが反対プロトコルで見えるまで](../../../domains/data-utilization/notes/how-long-until-a-write-is-visible.md)。出典: App-Mod [stage-1-multiprotocol.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/ja/stage-1-multiprotocol.md)「2 台のクライアントによる挙動」 |
| MP-FSXN-5 | NFS / SMB をまたぐ排他ロックは両方向で効く（contender が open 成功・読み取りロック違反・排他 open 共有違反、解放後に成功）。片プロトコル前提でロックを無視する移行コードは、別プロトコルの保持者が居るとき拒否される（`field-observation`。組ごと 1 観測。`FileShare.None` / `fcntl` を取った場合のみの計測で、ロックを取らない書き手が止まるかは未測定） | ②/③ | ロック取得なしに書く経路と、`FileShare.None` / `fcntl` を取る経路を列挙し、クロスプロトコルで共有する対象かを突合する | Hub: [マルチプロトコルと ID](../../../domains/multiprotocol-identity/README.md)、[セキュリティスタイルが権限モデルを決める](../../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md)。出典: App-Mod [stage-1-multiprotocol.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/ja/stage-1-multiprotocol.md)（排他ロックの組の所見） |
| MP-FSXN-6 | FSx for ONTAP S3 Access Points をアタッチした / しようとしたボリュームは ONTAP CLI から削除できず、`aws fsx delete-volume` でしか消せない。verify ゲートや teardown が ONTAP `volume delete` を前提にすると、検証環境の撤去で詰まる（`verified`。Hub 自身の実測、2026-09、`ap-northeast-1`） | ② | teardown スクリプトと runbook で ONTAP CLI の `volume delete` を使っている箇所を検出し、S3 Access Points を触るボリュームなら `aws fsx delete-volume` に寄せる | Hub: [S3 Access Points は「S3 として使える」わけではない — 撤去時の停滞](../../../domains/data-utilization/notes/s3-access-point-constraints.md#撤去時の停滞--aws-側からしか消せなくなるボリューム)。[ガードレール配線メモ](guardrail-wiring.md) とも接続する |

---

## 番号衝突と帰属の注意

- **`MP-FSXN-N` は貼り込み先の無印 `MP-N` と別系列です。** 貼り込み先 Playbook の作者が持つ `MP-N` の番号を振り直さないでください。
- **`MP-FSXN-6` だけは Hub 自身の実測（`verified`）です。** 出典は Hub ノートです。他の 5 行の測定主体は App-Modernization-Patterns で、Hub は引用します。
- **`MP-FSXN-2` は未検証（`hypothesis`）です。** FSx for ONTAP 上での発火を実測していないので、採用するなら未検証として扱ってください。

---

[🏠 リポジトリトップ](../../../../../README.md) | [補助パック](README.md)
