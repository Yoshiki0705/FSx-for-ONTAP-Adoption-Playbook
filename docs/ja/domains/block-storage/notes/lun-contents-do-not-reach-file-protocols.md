---
title: LUN の中身はファイルプロトコルに現れない — S3 Access Points で分析するには必ずホストを 1 台経由する
lifecycle: [assess, design, migrate]
domains: [block-storage, data-utilization]
evidence: documented
source: https://docs.netapp.com/us-en/ontap/concepts/client-protocols-concept.html
lang: ja
---

# LUN の中身はファイルプロトコルに現れない

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

## 結論

**LUN の中にあるファイルシステムを解釈するのはホストで、ストレージではありません。** したがって LUN の中のファイルは、NFS / SMB からも Amazon S3 Access Points からも読めません。

**FlexClone でクローンを作っても、`volume rehost` で NAS が有効な SVM へ移しても、この境界は動きません。** クローンは中身をそのまま複製し、rehost は所有 SVM を変えるだけで LUN を LUN のまま保持します。

**ブロックのデータを S3 API で分析したい場合、経路は 4 段になります。** 段が減ることはなく、**データのコピーが 1 本発生します。** 「コピーを増やさずに分析する」ではありません。

> **Evidence**: `documented` — プロトコルの対応関係と S3 Access Points の対象は、ベンダーおよび AWS の公式ドキュメントの記載に基づきます（2026-09-11 に確認）。
> **ただし「LUN の中身はファイルプロトコルから読めない」と明示した記述は見つけられませんでした**（後述、`open`）。
> 自環境での確認手順を末尾に置いてあります。

---

## ドキュメントが述べていることと述べていないこと

**この区別を先に置きます。結論は同じでも、根拠の強さが違います。**

| 論点 | ドキュメントの状態 |
|---|---|
| LUN は仮想ディスクであり、1 つ以上の LUN が ONTAP のボリュームに格納される | **明記あり** |
| **同じ LUN は FC / FCoE / iSCSI からアクセスできる** | **明記あり。ファイルプロトコルは列挙に現れません** |
| NVMe の namespace は **NVMe プロトコル経由でのみ**アクセスできる | **明記あり**（排他が明示されている） |
| **LUN の中身がファイルプロトコルから読めないこと** | **明示された記述を見つけられませんでした**（2026-09-11 調査） |
| S3 Access Points が対象とするのは Amazon FSx のファイルシステムに保存された**ファイルデータ**であること | **明記あり。LUN への言及はありません** |

**namespace には排他の明示があるのに、LUN にはありません。** 結論はプロトコル対応の列挙から導いたもので、禁止の記述を根拠にしたものではありません。

**[ドキュメントの不在は区分ではありません](../../../evidence-policy.md)。** ここは実測で確かめられる項目なので、検証項目として扱う価値があります。手順は末尾にあります。

---

## S3 Access Points で分析するまでの 4 段

**本番環境に影響を与えずにブロックのデータを分析したい、という要件を満たす最短の経路です。**

| 段 | 何をするか | FlexClone が効くか |
|---|---|---|
| 1 | 本番 LUN を含むボリュームの FlexClone を作る | **効きます。** これが FlexClone の用途そのものです |
| 2 | クローンの LUN を分析用ホストにマップしてマウントする | 関係ありません。**ホストが必要です** |
| 3 | そのホストが中のファイルを NAS ボリュームへ書き出す | 関係ありません。**ここでコピーが 1 本発生します** |
| 4 | その NAS ボリュームに S3 Access Points を付けて分析する | 関係ありません |

**FlexClone が解決するのは段 1 だけです。** 「本番に影響を与えない」という部分を解決し、「ブロックをファイルにする」部分は解決しません。

**段 3 の運び方には選択肢があります。** ホスト上のファイルコピー、AWS DataSync、コード変換を持つ転送ミドルウェアの 3 つで、選ぶ軸が 2 段あります（[ブロックからファイルへ運ぶ経路の比較](../../../reference/comparison/block-to-file-routes.md)）。

### 段 2 で持ち込まれる整合性の制約

**FlexClone は Snapshot 由来なので、中の LUN のファイルシステムは crash-consistent です。**

クローンをマウントした時点で `fsck` や `chkdsk` が走る可能性があり、**そこからコピーしたファイルはアプリケーション側の整合性保証を受けていません**（[LUN の Snapshot は既定で crash-consistent](a-snapshot-of-a-lun-is-crash-consistent.md)）。

| 用途 | 許容できるか |
|---|---|
| 傾向の分析、機械学習の学習データ | 多くの場合許容できます |
| **監査・照合・会計の証跡** | **許容するという判断を明示的にしてください。** アプリケーション側のエクスポート（データベースなら dump）に切り替える選択肢があります |

---

## FlexClone と rehost が境界を動かさない理由

**2 つとも「どこにあるか」を変える操作で、「何であるか」を変える操作ではありません。**

| 操作 | 変えるもの | LUN はどうなるか |
|---|---|---|
| `volume modify -security-style` | 権限評価に使うモデル | **LUN のまま** |
| FlexClone | 親を触らずに複製を得ること | **LUN のまま複製されます** |
| `volume rehost` | どの SVM がボリュームを所有するか | **保持され、unmapped になります**（[`volume rehost` が変えるものと変えないもの](volume-rehost-changes-ownership-not-contents.md)） |
| **クローン LUN を別ホストにマップして書き出す** | **ブロックからファイルへ** | ここだけが境界を越えます |

**「NAS が有効な SVM へ移せばファイルとして見える」は成立しません。** SVM のプロトコル設定は、NFS から届かない 4 つの原因のうち 1 つに対応するものです（[SMB で運用中のボリュームに NFS を足すのに複製は要らない](../../multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md#nfs-から届かない-4-つの原因)）。**ブロックとファイルの境界はその 4 つの外側にあります。**

---

## 自環境での確認手順

**「LUN の中身がファイルプロトコルから見えない」ことは、公開ドキュメントに明示がないので実測で確かめられます。** 確かめれば `verified` に上げられます。

| # | 手順 | 確認できること |
|---|---|---|
| 1 | LUN を含むボリュームに junction path を付け、NFS でマウントする | ボリューム自体には到達できること |
| 2 | マウント先のディレクトリを一覧する | **LUN がファイルとして現れるか。現れる場合、その中身が読めるか** |
| 3 | 同じボリュームに S3 Access Points を付け、`ListObjectsV2` を実行する | **LUN がオブジェクトとして列挙されるか** |
| 4 | **対照として**、同じボリュームに NFS で普通のファイルを 1 つ置き、手順 2 と 3 を再実行する | **手順 2・3 で何も見えなかったのが LUN の性質か、経路の設定漏れか**を分けられます |
| 5 | LUN を iSCSI でホストにマップしてマウントし、中のファイルを一覧する | 同じデータがブロック経由では読めること |

**手順 4 を省くと、何も見えなかった結果が「LUN だから見えない」なのか「export policy とアクセスポイントの設定が間違っている」なのか分かりません。** [コントロールのない失敗は対象の性質ではなく手順の誤りを記録しうる](../../../evidence-policy.md)ためです。

**記録する項目:**

| 項目 | 理由 |
|---|---|
| ONTAP バージョン | 挙動がバージョンに依存する可能性があります |
| ボリュームのセキュリティスタイルと `os_type` | 結論がこの条件に紐づきます |
| 手順 4 の対照が成功したこと | 経路が正常であることの証拠です |

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| マルチプロトコルなので LUN の中身も NFS から読める | **読めません。** マルチプロトコルは NFS・SMB・S3 の間で成立する性質で、ブロックとの間ではありません |
| S3 Access Points を付ければブロックのデータも S3 API で読める | 対象は**ファイルデータ**です。LUN への言及はありません |
| FlexClone すればファイルとして読めるようになる | クローンは中身をそのまま複製します。**LUN はクローンでも LUN です** |
| NAS が有効な SVM に `volume rehost` すれば読めるようになる | **LUN は保持され unmapped になるだけです。** 所有 SVM が変わっても中身は変わりません |
| コピーを作らずにブロックのデータを分析できる | **ホストを経由するのでコピーが 1 本発生します。** FlexClone が省くのは本番への影響で、コピーそのものではありません |
| ドキュメントに「読めない」と書いてある | **書かれていません**（2026-09-11 調査）。プロトコル対応の列挙から導いた結論です |
| クローンからコピーしたデータはそのまま照合に使える | **crash-consistent です。** アプリケーション側の整合性保証を受けていません |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| LUN が仮想ディスクであり ONTAP のボリュームに格納されること、同じ LUN が FC / FCoE / iSCSI からアクセスできること、NVMe の namespace は NVMe 経由でのみアクセスできること | [NetApp: Learn about ONTAP client protocols](https://docs.netapp.com/us-en/ontap/concepts/client-protocols-concept.html) |
| S3 Access Points が対象とするのが Amazon FSx のファイルシステムに保存されたファイルデータであること、NFS / SMB と併用できること | [AWS: Accessing your data via Amazon S3 access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html) |
| FlexClone が親とデータブロックを共有する書き込み可能なコピーであること | [NetApp: Learn about ONTAP FlexClone volumes, files, and LUNs](https://docs.netapp.com/us-en/ontap/concepts/flexclone-volumes-files-luns-concept.html) |
| ボリュームがファイル・ディレクトリ・iSCSI の LUN のコンテナであること | [AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |
| SAN の LUN と NAS 共有を同じ FlexVol に混在させることが推奨されないこと | [NetApp: SAN volumes](https://docs.netapp.com/us-en/ontap/volumes/san-volumes-concept.html) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [`examples/multiprotocol-ad/`](../../../../../examples/multiprotocol-ad/) — **「自環境での確認手順」を動かせる最小構成**。対照を含む NFS 側の記録スクリプトが入っています
- [`volume rehost` が変えるものと変えないもの](volume-rehost-changes-ownership-not-contents.md) — 所有 SVM を変えても境界が動かない理由
- [ブロックからファイルへ運ぶ経路の比較](../../../reference/comparison/block-to-file-routes.md) — 段 3 の選択肢
- [LUN の Snapshot は既定で crash-consistent](a-snapshot-of-a-lun-is-crash-consistent.md) — 段 2 の整合性
- [LUN と igroup は AWS の API の外側にある](block-objects-are-outside-the-aws-api.md) — 2 つの制御面
- [FSx for ONTAP S3 Access Points の前提条件](../../data-utilization/notes/s3-access-point-constraints.md) — 段 4 の制約
- [SMB で運用中のボリュームに NFS を足すのに複製は要らない](../../multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md) — NAS 側の 4 つの原因
- [知見の分類ポリシー](../../../evidence-policy.md) — `documented` と `open` の扱い

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)
