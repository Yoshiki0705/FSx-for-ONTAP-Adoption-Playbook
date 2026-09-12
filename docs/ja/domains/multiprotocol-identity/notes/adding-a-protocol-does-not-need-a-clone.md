---
title: SMB で運用中のボリュームに NFS を足すのに複製は要らない — 届かない原因はセキュリティスタイルの外側にある
lifecycle: [design, migrate, operate]
domains: [multiprotocol-identity]
evidence: documented
source: https://docs.netapp.com/us-en/ontap/nfs-admin/security-styles-their-effects-concept.html
lang: ja
---

# SMB で運用中のボリュームに NFS を足すのに複製は要らない

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — マルチプロトコル・ID](../README.md)

---

## 結論

**ONTAP に「SMB のみ対応のボリューム」という状態はありません。** したがって NFS を足すために、FlexClone でボリュームを複製する必要も、`volume rehost` で別の SVM へ移す必要もありません。

ベンダーのドキュメントは、セキュリティスタイルが**クライアント種別のアクセス可否を決めるものではない**と明記しています。決めるのは権限評価に使う権限の種類と、**その権限を変更できるクライアント種別**の 2 つだけです。同じページの表で、UNIX / NTFS / mixed の**どのスタイルでも「ファイルにアクセスできるクライアント」は NFS と SMB の両方**になっています。

**NFS から届かないなら、原因はセキュリティスタイルの外側にあります。** 候補は 4 つで、いずれもボリュームを複製せずに直せます。

> **Evidence**: `documented` — ベンダーおよび AWS の公式ドキュメントの記載に基づきます（2026-09-11 に確認）。
> **数値・所要時間・自環境での再現結果は含みません。** 適用前に「自環境での確認手順」を通してください。

---

## 前提の取り違えが生む遠回り

この取り違えは、次の形で現れます。

> SMB 用に作ったボリュームだから、NFS で使うには作り直すか複製するしかない

そう考えると、FlexClone でクローンを作り、NAS が有効な別の SVM へ `volume rehost` する、という手順に行き着きます。**この手順は成立しません。** `volume rehost` は前提条件として、対象がクローンでもクローンの親でもないことを求めており、**先に split しなければ実行できません**（[`volume rehost` が変えるものと変えないもの](../../block-storage/notes/volume-rehost-changes-ownership-not-contents.md)）。

**そして split すれば、複製が本来避けたかった容量コストが戻ってきます。** クローンは親とブロックを共有しますが、split すると独自のストレージが割り当てられます。

**避けたい回り道は「複製 → split → rehost」で、正しい経路は「原因を 1 つ特定して直す」です。**

---

## NFS から届かない 4 つの原因

**順に確認します。上から下に向かって、確認のコストが上がります。**

| # | 確認するもの | 直し方 | ボリュームの複製 |
|---|---|---|---|
| 1 | **SVM で NFS プロトコルが有効か** | SVM にプロトコルを追加します。SMB についても同じ構造で、有効化は SVM レベルの設定です | 不要 |
| 2 | **ボリュームに junction path があるか** | SVM の名前空間にマウントします。**junction path がないボリュームは NFS の名前空間に現れません** | 不要 |
| 3 | **export policy が対象クライアントを許可しているか** | ルールを追加します。**既定のポリシーはルールを持たないことがあり、その場合はすべて拒否になります** | 不要 |
| 4 | **name-mapping が成立しているか** | マッピングを設定します。**NTFS スタイルのボリュームでは、権限評価に NTFS ACL を使うため win→unix マッピングが参照されません**（[セキュリティスタイルと権限評価の対応](security-style-and-permission-evaluation.md#セキュリティスタイルと権限評価の対応)） | 不要 |

**セキュリティスタイルはこの 4 つのどこにも現れません。** スタイルが決めているのは、届いた後に「どちらの権限モデルで評価するか」です。

---

## セキュリティスタイルの変更経路

**変えたい場合も、既存のボリュームに対して直接変更できます。**

ベンダーのドキュメントは、ボリュームが既に存在する場合は `volume modify` に `-security-style` を指定すると述べています。指定できる値は `unix` / `ntfs` / `mixed` の 3 つです。

| 状態 | 使うもの |
|---|---|
| ボリュームがまだ存在しない | `volume create` に `-security-style` |
| **ボリュームが既に存在する** | **`volume modify` に `-security-style`** |
| 作成時に指定しなかった場合 | ルートボリュームのスタイルを継承します |

**ただし変更は挙動を変えます。** 遮断手段としてマッピング拒否を使っている場合、スタイルを NTFS に変えるとその手段が効かなくなります。**変更の前に何が効かなくなるかを確認してください**（[止められるものと止められないもの](security-style-and-permission-evaluation.md#止められるものと止められないもの)）。

**mixed は選ばないでください。** AWS のドキュメントは mixed が**マルチプロトコルアクセスに必須ではなく、上級者にのみ推奨される**と述べています。挙動は「最後に権限を設定したプロトコル側のモデルで評価する」もので、運用中に評価モデルが切り替わります。

### SVM のルートボリュームは例外

**SVM のルートボリュームのセキュリティスタイルは、CloudFormation では更新に置き換えを伴います。** テンプレートで管理している場合、後から変えるとリソースが作り直されます（[設定がどちらの面にあるかの決定木](../../../reference/decision-trees/where-a-setting-is-created.md)）。**先に決める項目です。**

---

## FlexClone が解決するものとしないもの

**FlexClone は不要という結論は、FlexClone が無用という意味ではありません。** 用途が違います。

ベンダーのドキュメントは FlexClone を、Snapshot のメタデータを参照して**書き込み可能な point-in-time のコピー**を作る仕組みと説明しています。コピーは親とデータブロックを共有し、**変更を書くまでメタデータ分以外のストレージを消費しません。**

| 目的 | FlexClone が要るか |
|---|---|
| SMB で運用中のボリュームを NFS からも使えるようにする | **要りません。** 上の 4 つを直します |
| **本番のセキュリティスタイルを変える前に、挙動を確かめる** | **有効です。** 親を触らずに、クローン側でスタイルを変えて試せます |
| 本番を止めずに検証環境を作る | 有効です |
| ブロックのデータをファイルとして読む | **解決しません**（[LUN の中身はファイルプロトコルに現れない](../../block-storage/notes/lun-contents-do-not-reach-file-protocols.md)） |

**2 行目がこのノートと組み合わせて効きます。** スタイルの変更が本番の遮断手段を壊すかを、本番で試さずに確かめられます。手順は次節に置いてあります。

---

## 自環境での確認手順

### 1. SVM のプロトコル設定の確認

ONTAP CLI:

```text
vserver show -vserver <svm> -fields allowed-protocols
```

ONTAP REST API:

```http
GET /api/svm/svms?fields=name,nfs.enabled,cifs.enabled
```

**NFS が有効でないなら、ここが原因です。** ボリューム側を触る前に直します。

### 2. junction path の確認

```text
volume show -vserver <svm> -volume <volume> -fields volume,junction-path,security-style
```

`junction-path` が空なら NFS の名前空間に現れません。**同じ出力で `security-style` も確認できます。**

### 3. export policy のルールの確認

```text
export-policy rule show -vserver <svm> -policyname <policy>
```

**ルールが 0 件のポリシーはすべて拒否します。** 「ポリシーが割り当てられている」と「許可されている」は別です。

### 4. クローンでのスタイル変更の試行

**本番のスタイルを変える前に、この順で試します。**

| # | 操作 | 確認できること |
|---|---|---|
| 1 | `volume clone create` で対象ボリュームのクローンを作る | 親を触らずに複製が得られること |
| 2 | クローンを SVM の名前空間にマウントし、export policy を付ける | NFS から到達できること |
| 3 | クローン側で `volume modify -security-style` を実行する | 変更が通ること |
| 4 | **管理者グループに属さない**一般ユーザーで、NFS と SMB の両方から読み書きする | 変更後の権限評価の実際 |
| 5 | クローンを削除する | 親が無影響であること |

**手順 4 を管理者アカウントで試した結果は使えません。** `FileSystemAdministratorsGroup` のメンバーはこの種の評価の影響を受けません（[もう 1 つの例外](security-style-and-permission-evaluation.md#もう-1-つの例外)）。

**手順 5 の後に親を削除しようとすると、削除できないことがあります。** 削除したボリュームは recovery queue に既定で 12 時間以上留まり、その間 FlexClone の関係が残るためです（[用語集の Volume recovery queue の項](../../../reference/glossary/README.md)）。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| SMB 用に作ったボリュームは NFS から使えない | **そういう状態はありません。** セキュリティスタイルはアクセス可否を決めません |
| NFS を足すには FlexClone で複製する | 不要です。届かない原因は 4 つのいずれかで、どれも複製せずに直せます |
| クローンを NAS 有効な SVM へ `volume rehost` すればよい | **クローンは rehost できません。** split が必要で、split すると容量共有が終わります |
| セキュリティスタイルは作成時にしか決められない | `volume modify -security-style` で変更できます。**ただし SVM のルートボリュームは CloudFormation では置き換えです** |
| mixed にすれば NFS と SMB の両方で権限を管理できる | AWS は mixed を**マルチプロトコルアクセスに必須ではなく上級者向け**と記載しています。評価モデルが運用中に切り替わります |
| export policy が割り当てられていれば許可されている | **ルールが 0 件のポリシーはすべて拒否します** |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| セキュリティスタイルはクライアント種別のアクセス可否を決めないこと、UNIX / NTFS / mixed のいずれでも NFS と SMB がアクセスできること | [NetApp: Learn about ONTAP NAS security styles](https://docs.netapp.com/us-en/ontap/nfs-admin/security-styles-their-effects-concept.html) |
| 既存ボリュームのスタイルを `volume modify -security-style` で変更できること、指定できる値が `unix` / `ntfs` / `mixed` であること、未指定時はルートボリュームを継承すること | [NetApp: Configure security styles on ONTAP NFS FlexVol volumes](https://docs.netapp.com/us-en/ontap/nfs-admin/configure-security-styles-task.html) |
| mixed がマルチプロトコルアクセスに必須ではなく、上級者にのみ推奨されること | [AWS: Updating volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/updating-volumes.html) |
| FlexClone が書き込み可能な point-in-time コピーであり、変更を書くまでストレージを消費しないこと | [NetApp: Learn about ONTAP FlexClone volumes, files, and LUNs](https://docs.netapp.com/us-en/ontap/concepts/flexclone-volumes-files-luns-concept.html) |
| クライアントが NFS と SMB の両方で同じファイルにアクセスできること | [NetApp: Learn about ONTAP client protocols](https://docs.netapp.com/us-en/ontap/concepts/client-protocols-concept.html) |

---

## 関連ドキュメント

- [Domain — マルチプロトコル・ID](../README.md) — このモジュールのハブ
- [`examples/multiprotocol-ad/`](../../../../../examples/multiprotocol-ad/) — **この 4 つを自分の環境で確かめる最小構成**。CloudFormation 1 本と ONTAP REST のスクリプト
- [セキュリティスタイルが権限評価のモデルを決める](security-style-and-permission-evaluation.md) — スタイルが決めている中身
- [`volume rehost` が変えるものと変えないもの](../../block-storage/notes/volume-rehost-changes-ownership-not-contents.md) — クローンとの排他、split の代償
- [LUN の中身はファイルプロトコルに現れない](../../block-storage/notes/lun-contents-do-not-reach-file-protocols.md) — プロトコルの追加で越えられない境界
- [ブロックからファイルへ運ぶ経路の比較](../../../reference/comparison/block-to-file-routes.md) — 境界を越える必要がある場合
- [設定がどちらの面にあるかの決定木](../../../reference/decision-trees/where-a-setting-is-created.md) — ルートボリュームのスタイルが置き換えである理由
- [移行時の ACL 保持](../../../playbooks/03-migrate/notes/preserving-acls-during-migration.md) — 権限を保ったまま運ぶ場合
- [用語集](../../../reference/glossary/) — セキュリティスタイル / `volume rehost` / FlexClone の定義
- [知見の分類ポリシー](../../../evidence-policy.md) — `documented` の扱い

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — マルチプロトコル・ID](../README.md)
