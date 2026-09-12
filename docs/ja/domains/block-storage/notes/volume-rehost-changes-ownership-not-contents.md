---
title: '`volume rehost` が変えるのは所有 SVM だけで、中身は変わらない — 失われる設定 7 種を先に控える'
lifecycle: [design, migrate, operate]
domains: [block-storage, multiprotocol-identity]
evidence: verified
verified_on: 2026-09-12
region: ap-northeast-1
ontap_version: 9.18.1P6
source: https://docs.netapp.com/us-en/ontap/volumes/rehost-volume-another-svm-task.html
lang: ja
---

# `volume rehost` が変えるのは所有 SVM だけで、中身は変わらない

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

## 結論

**`volume rehost` は SnapMirror のコピーなしに、ボリュームを 1 つの SVM から別の SVM へ再割り当てします。** 変わるのは所有 SVM で、**ボリュームの中身は変わりません。** LUN は保持され、unmapped の状態で残ります。

**FlexClone のボリュームは rehost できません。** 前提条件が、対象がクローンでもクローンの親でもないことを求めています。**先に split する必要があり、split すると親とのブロック共有が終わって独自のストレージが割り当てられます。**

**それでも split して rehost する価値はあります。** FlexClone の利点は 2 つあり、split が失わせるのは片方だけです。容量を消費しない共有は失いますが、**親を触らないという性質は残ります。** rehost は disruptive な操作ですが、**disruptive なのはクローンに対してで、本番のボリュームは無影響です。**

**代償は容量だけではありません。rehost 後に失われて手動で再設定が必要になる設定が 7 種あり、そのうち 1 つは権限に直結します。**

**そして実測すると、7 種のうち Snapshot ポリシーは「失われる」のではなく `default` に戻りました。** 取られないつもりのボリュームが既定スケジュールを獲得する側の事故です。**セキュリティスタイルは保持され、AWS の制御面は約 14 分かけて追随しました。**

> **Evidence**: `documented` — 前提条件・非対応機能・失われる設定は、ベンダーの公式ドキュメントの記載に基づきます（2026-09-11 に確認）。
> **REST の経路、セキュリティスタイルの保持、Snapshot ポリシーの `default` への戻り、AWS 制御面の追随に要する時間の 4 点は実測です**（後述、`ap-northeast-1` / ONTAP 9.18.1P3D1 / 2026-09-11）。
> **FSx for ONTAP でサポートされた操作である根拠は見つかっていません。** AWS のドキュメントに `volume rehost` の記載がありません（同日調査）。実行できたことと、サポートされていることは別です。
> **未確定が 4 点残っています**（後述）。適用前に自環境で確認してください。

---

## rehost の前提条件

**満たしていないと実行できません。上から順に確認するのが安いです。**

| # | 条件 | 補足 |
|---|---|---|
| 1 | ボリュームが online であること | offline のままでは実行できません |
| 2 | プロトコルが SAN または NAS であること | — |
| 3 | **NAS の場合、junction path の一部でなく unmount されていること** | rehost 後に宛先 SVM の名前空間へマウントし直します |
| 4 | SnapMirror 関係がある場合は、削除して関係情報を解放するか break すること | **rehost 後に resync できます** |
| 5 | 送信元と宛先の SVM の subtype が同一であること | subtype が違う SVM 間では移せません |
| 6 | **対象がクローンでもクローンの親でもないこと** | **クローンは先に split します** |

**非対応の機能も列挙されています。** SVM DR、MetroCluster 構成、**SnapLock ボリューム**、ONTAP 9.8 より前の NetApp Volume Encryption ボリューム、FlexGroup ボリューム、クローンボリューム。

**SnapLock ボリュームが非対応であることは、別の理由でも重要です。** SnapLock は有効化が不可逆で、[人間の明示的な指示なしに有効化してはいけない機能](../../../../../AGENTS.md)です。rehost の検証で SnapLock ボリュームを作る必要はありません。

### SAN ボリュームの追加条件

| 条件 | 補足 |
|---|---|
| ボリュームの移動や LUN の移動が実行中でないこと | — |
| ボリュームと LUN に対する I/O が無いこと | — |
| **宛先 SVM に同名で別のイニシエータを持つ igroup が存在しないこと** | 同名なら送信元か宛先のどちらかで改名します |
| **`force-unmap-luns` を有効にしておくこと** | **既定は `false`。`true` に設定するとき、警告も確認メッセージも表示されません** |

---

## rehost で失われる設定

**ドキュメントは、rehost 後に送信元ボリュームから失われ、rehost 後のボリュームで手動で再設定する必要があるものを 7 種挙げています。**

| # | 失われるもの | 再設定を忘れたときに起きること |
|---|---|---|
| 1 | ウイルス対策ポリシー | スキャンが掛からなくなります |
| 2 | ボリューム効率化ポリシー | 重複排除・圧縮が止まり、容量が伸びます |
| 3 | QoS ポリシー | 上限が外れ、他のワークロードに影響しえます |
| 4 | **Snapshot ポリシー** | **世代が取られなくなります。** 気づくのは復旧が必要になったときです |
| 5 | ns-switch と name services の設定 | 名前解決の経路が変わります |
| 6 | export ポリシーとルール | **ルールが 0 件のポリシーはすべて拒否します** |
| 7 | **User and group IDs** | **NFS からの権限評価が rehost の前と同じになりません** |

**7 番が単独で重い。** UID / GID が失われた状態で NFS から読むと、権限は移す前と同じになりません。**「プロトコルを変えても同じデータへ到達する」という設計の「同じ」が、ここで壊れます。**

**4 番は気づくのが遅い。** Snapshot ポリシーの欠落は平常時に無症状で、復旧が必要になった時点で世代が無いことが分かります。

**LUN の再マップも忘れやすい。** rehost は LUN を保持しますが unmapped のままで、宛先 SVM で igroup を作り直して宛先の portset を使ってマップします。`auto-remap-luns` が `true` なら rehost 後に自動でマップされます。**実行前に `lun mapping show` でマップ情報を記録しておくことが、失敗時の保険になります。**

---

## FlexClone との排他と split の代償

**split は FlexClone の利点を半分だけ失わせます。この非対称が判断を決めます。**

| FlexClone の性質 | split 後 |
|---|---|
| 親とデータブロックを共有し、変更を書くまでストレージを消費しない | **失われます。** コピーに独自のストレージが割り当てられます |
| **親のボリュームを触らずに書き込み可能な複製が得られる** | **残ります** |

**残る側が目的なら、split の容量コストは対価として成立します。** 本番の LUN を触らずに、クローンだけを別の SVM へ移して試せます。

**同じ構造がこのリポジトリに 1 件あります。** AWS Transform の Finalize は FlexClone を親から分離する工程で、**そこで物理容量が最大になります**（[AWS Transform の Finalize は後片付けではなく、物理容量が最大になる工程](../../../playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md)）。**rehost は同じ代償を別の入口から要求します。** 容量の見積りは、そちらの考え方をそのまま使えます。

---

## rehost が変えないもの

**ここを取り違えると、成立しない設計になります。**

| 期待 | 実際 |
|---|---|
| NAS が有効な SVM へ移せば、LUN の中身が NFS から読める | **読めません。** LUN は保持され unmapped になるだけです（[LUN の中身はファイルプロトコルに現れない](lun-contents-do-not-reach-file-protocols.md)） |
| 移せばマルチプロトコルになる | **セキュリティスタイルはもともとアクセス可否を決めません。** NFS から届かない原因は 4 つあり、rehost はそのうち 1 つにしか対応しません（[SMB で運用中のボリュームに NFS を足すのに複製は要らない](../../multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md#nfs-から届かない-4-つの原因)） |
| ボリュームの中のデータ構造が変わる | 変わりません。**ブロックはブロックのままです** |

---

## 実測で確定した 4 点

**ここはドキュメントの記載ではなく当方の実測です。** ノートの `documented` 区分の外にあります。

検証環境 / Environment: `ap-northeast-1`、ONTAP 9.18.1P3D1、`SINGLE_AZ_1`（第 1 世代）、SSD 1,024 GiB、スループット 128 MBps、2026-09-11。送信元 `subtype: default` / NFS 有効・CIFS 無効・ルートボリューム UNIX、宛先も同じ。**対象ボリュームは 1 GiB、セキュリティスタイルを明示的に `NTFS` で作成**（つまり宛先 SVM のルートのスタイルとは異なる状態で移した）。

### 1. REST の経路は private CLI パススルー

**ボリュームの `svm` を書き換える形は拒否されます。**

```text
PATCH /api/storage/volumes/{uuid}   {"svm":{"name":"<destination>"}}
→ HTTP 400  code 262196
  Field "svm.name" cannot be set in this operation
```

**通るのはこちらです。**

```text
POST /api/private/cli/volume/rehost
  {"vserver":"<source>","volume":"<name>","destination-vserver":"<destination>"}
→ HTTP 202 + job
  cli_output: "[Job NNNN] Job is queued: Volume rehost operation on volume ... by administrator "fsxadmin"."
```

**ジョブは非同期です。** 完了後のジョブメッセージはベンダー自身の指示を含みます — 「対象 Vserver 側で export policy と QoS policy などの望ましい構成を設定してください」。

> **ONTAP のジョブレスポンスは制御文字をエスケープせずに返します。** `jq` に直接渡すと
> `Invalid string: control characters from U+0000 through U+001F must be escaped` で失敗します。
> スクリプトを書くなら `tr -d '\000-\010\013\014\016-\037'` を挟んでください。

### 2. セキュリティスタイルの保持

**`ntfs` のまま移りました。** 宛先 SVM のルートボリュームは UNIX なので、**スタイルはボリュームの属性で、宛先のルートに引きずられません。** 失われる 7 種にセキュリティスタイルが含まれていないという記述の沈黙は、この環境では保持を意味していました。

### 3. Snapshot ポリシーの `default` への復帰 — 喪失ではないこと

**これが 7 種の記述より鋭い所見です。**

| 項目 | 移動前 | 移動後 |
|---|---|---|
| `snapshot_policy.name` | **`none`**（意図的に無効化していた） | **`default`** |

**「失われる」は不在を思わせますが、実際に起きたのは既定スケジュールの獲得です。** リスクの向きが逆で、**取られないつもりのボリュームに、頼んでいない Snapshot が取られ始めます。** そしてベンダーのジョブメッセージは export policy と QoS policy を名指しますが、**実際に変わった Snapshot ポリシーには触れていません。**

**1 回目の環境で観測できたのは Snapshot ポリシーだけでした。** export policy は移動前から `default` だったため差が出ず、QoS は未設定、ウイルス対策・効率化・ns-switch は構成していませんでした。

**2 回目（下記「2 回目の実測」）で export policy の喪失も観測できました。** 移動前に非既定の
export policy を割り当てておいたためです。**1 回目で「差が出なかった」のは、失われなかったからでは
なく、失われても見えない状態で測ったからです。** 残り 5 種は未観測で、ドキュメントの記述のままです。

### 4. AWS 制御面の追随と、それに要する時間

| 時刻（UTC） | ONTAP | AWS API |
|---|---|---|
| 02:31:01 | rehost ジョブ `success` | — |
| 02:33:29 〜 02:43:12 | `svm_dest` | **`verification-svm`（古い）。** `JunctionPath` と `SnapshotPolicy` も古いまま |
| 02:44:43 | `svm_dest` | **`svm_dest`。** 3 フィールドが同時に更新 |

**ジョブ完了から約 13 分 42 秒後**に、`StorageVirtualMachineId`・`JunctionPath`・`SnapshotPolicy` が一斉に追いつきました。**AWS のドキュメントが言う「数分」より長いことは、待ち時間の設計に直接効きます。**

**3 分の観測で打ち切ると逆の結論が出ます。** 当初このリポジトリのプローブスクリプトはポーリング窓を 10 分にしていて、**13 分 42 秒には届かず「AWS は追随しない」と断定して終わる実装でした。** 修正済みです。**観測窓が短い測定は、沈黙を否定と読み替えます。**

**両制御面が一致した状態では、撤去は `aws fsx delete-volume` で通りました。** S3 Access Points を付けたボリュームで観測された非対称（[撤去時の停滞](../../data-utilization/notes/s3-access-point-constraints.md#撤去時の停滞--aws-側からしか消せなくなるボリューム)）は、この経路では再現していません。**ただし追随前の 14 分間に削除を試した場合の挙動は測っていません。**

## 2 回目の実測 — 追随時間は 13 分 42 秒より延び、export policy の喪失も観測

別のファイルシステムで、より新しい ONTAP で再測しました。**セキュリティスタイルの保持と Snapshot
ポリシーの `default` 復帰は再現しました。** 一方で 2 点が 1 回目と違いました。

検証環境 / Environment: `ap-northeast-1`、**ONTAP 9.18.1P6**、`SINGLE_AZ_1`（第 1 世代）、SSD 1,024 GiB、
スループット 128 MBps、2026-09-12。送信元・宛先とも `subtype: default`、**両 SVM のルートボリュームは
UNIX**。対象ボリュームはセキュリティスタイルを明示的に `NTFS` で作成し、非既定の export policy
（`mpad_clients`）を割り当てた状態で移動。

| 項目 | 移動前 | 移動後 | 判定 |
|---|---|---|---|
| セキュリティスタイル | `ntfs` | `ntfs` | **保持**（宛先ルートは UNIX。1 回目と同じ結論） |
| ONTAP の所有 SVM | `fsxnmpadsrc` | `fsxnmpaddst` | 即時 |
| AWS の `SvmId` | 送信元 | 宛先 | **追随した**（下記の所要時間） |
| Snapshot ポリシー | `none` | `default` | **変化**（1 回目と同じ。既定の獲得） |
| **export policy** | `mpad_clients` | `default` | **喪失を初観測。** 再設定が必要 |

### Snapshot ポリシーの変化はデータ保護の設計変更として扱うこと

`none` から `default` への変化を「既定を獲得した」と書くと軽く見えますが、**データ保護の観点では
どちらの方向も設計変更です。**

| 変化の方向 | 起きること |
|---|---|
| `none` → `default` | **予定していないスケジュールで Snapshot が取られ始めます。** 容量の消費と、保持世代の管理対象が増えます |
| 何らかのポリシー → `default` | **元のスケジュールが失われます。** 復旧手順書が「1 時間ごとの Snapshot がある」前提で書かれていれば、その前提が静かに崩れます |

**どちらも成功として報告され、次に復旧が必要になるまで気づきません。** rehost を運用手順に入れる
場合、Snapshot ポリシーの再設定を手順の一部にしてください。export policy と同じ扱いです。
| AWS の `JunctionPath` | `/rehostvol` | `null` | 名前空間から外れた |

### 追随時間は環境ごとに変わる — 13 分 42 秒を規則として扱わないこと

2 回目の追随は **19 分 01 秒以上、24 分 05 秒以下**でした。上下限で書くのは、ONTAP ジョブの完了時刻を
記録していなかったためです。観測できたのは「01:40:47 の時点で ONTAP はすでに宛先を示していた」と
「01:59:48 に AWS が切り替わった」の 2 点で、移動前スナップショットは 01:35:43 です。

**1 回目の 13 分 42 秒より明確に長く、同じ操作で 1.4 倍以上の差が出ました。** したがって
13 分 42 秒は上限ではなく 1 標本です。**待ち時間を設計するときは、実測値そのものではなく「数分では
終わらない」という性質だけを前提にしてください。** プローブスクリプトのポーリング窓は 25 分です。

> **注意**: 2 回とも 1 環境・1 回の観測です。上下限は再現された範囲ではなく、この 1 回の
> 観測精度の限界を示しています。

---

## 残っている未確定

| # | 未確定 | なぜ未確定か | 影響 |
|---|---|---|---|
| 1 | **失われる 7 種のうち 5 種** | 観測できたのは Snapshot ポリシー（1 回目・2 回目）と export policy（2 回目）です。QoS・ウイルス対策・効率化・ns-switch・user/group ID は構成していないか未確認です | 再設定リストの網羅性 |
| 2 | **追随前の 14 分間に削除した場合** | 両制御面が食い違っている窓での削除を試していません | 手順書がこの窓に入ると挙動が読めません |
| 3 | split の所要時間と容量のピーク | ボリュームサイズに比例するはずですが、公開された算定式を見つけていません | 実行中に SSD が満杯になると LUN が read-only に落ちます（[容量は 3 か所で数えられる](capacity-is-counted-in-three-places.md)） |
| 4 | FSx for ONTAP の公開ドキュメントへの記載 | AWS のドキュメントに `volume rehost` の記載を見つけられませんでした（2026-09-11 調査）。**上記は `fsxadmin` で実行できた実測ですが、サポートされた操作である根拠にはなりません** | 公式にサポートされない操作を手順書の前提にする risk |

**委任管理者で実行できる範囲の一覧は、姉妹プロジェクトが持っています**（[`fsxadmin-limitations.md`](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/fsxadmin-limitations.md)）。**このリポジトリでは一覧を再掲しません。**

---

## 自環境での確認手順

**rehost は disruptive です。本番相当のデータを置いたボリュームでは試さないでください。**

### 実行前

| # | 手順 | 理由 |
|---|---|---|
| 1 | `lun mapping show -volume <volume> -vserver <source_svm>` の出力を保存する | **失敗時にマップ情報を失わないための保険。** ドキュメントが手順として挙げています |
| 2 | `volume show -volume <volume> -instance` の出力を保存する | **セキュリティスタイルを含む現状の記録。** 未確定 1 の判定に使います |
| 3 | `aws fsx describe-volumes` の出力を保存する | **AWS 側から見た所有 SVM の記録。** 未確定 2 の判定に使います |
| 4 | export ポリシーと Snapshot ポリシーの現状を保存する | 失われる 7 種のうち再設定が必要なもの |

### 実行後に判定する項目

| # | 確認 | 何が分かるか |
|---|---|---|
| 1 | `volume show -volume <volume> -instance` でセキュリティスタイルを比較する | 当環境では**保持**されました。宛先のルートと異なるスタイルで試すこと |
| 2 | `aws fsx describe-volumes` の `StorageVirtualMachineId` を比較する。**15 分以上待つこと** | 当環境では**ジョブ完了から 13 分 42 秒後**に追随しました。10 分で打ち切ると逆の結論が出ます |
| 3 | 失われる 7 種を 1 つずつ確認する。**Snapshot ポリシーは `none` にしてから移すこと** | 再設定リストの網羅性。`default` に戻る挙動は、移動前が `default` だと観測できません |
| 4 | LUN が unmapped であることを確認し、宛先 SVM の igroup にマップする | ドキュメントどおりの挙動か |
| 5 | **管理者グループに属さない**一般ユーザーで NFS から読み書きする | UID / GID の欠落が実際に権限へ効くか |
| 6 | **撤去を試す。** `aws fsx delete-volume` と ONTAP の `volume delete` の両方 | **未確定 2 の帰結。** 片方でしか消せないなら手順書に書く必要があります |

**手順 6 を省かないでください。** 撤去が片方の経路でしか通らないことは、導入時ではなく撤去時に分かります。**検証環境を作り直す場面ほど当たりやすい経路です。**

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| FlexClone のボリュームをそのまま rehost できる | **できません。** 前提条件が排除しており、非対応機能の一覧にも「クローンボリューム」があります |
| split すると FlexClone を使った意味がなくなる | **半分だけです。** 容量共有は失われますが、親を触らないという性質は残ります |
| rehost は本番に影響する | **クローンに対して実行するなら本番は無影響です。** disruptive なのは対象のボリュームです |
| rehost すればボリュームの中身も宛先 SVM の流儀に変わる | **変わりません。** LUN は保持され unmapped になるだけです |
| LUN は自動でマップし直される | **`auto-remap-luns` が `true` の場合だけです。** 既定の挙動を確認してください |
| `force-unmap-luns` を有効にすれば警告が出る | **出ません。** 有効化そのものが無言です |
| 失われるのは LUN のマップだけ | **7 種あります。** とくに Snapshot ポリシーと User and group IDs |
| セキュリティスタイルは失われる 7 種に入っていないので保持される | 結論は合っていますが**理由が違います。** 書かれていないことは根拠にならず、当環境での実測が根拠です |
| Snapshot ポリシーは失われるので、移動後は何も取られない | **`default` に戻ります**（実測）。取られない側ではなく、**頼んでいない既定スケジュールが付く側**の事故です |
| AWS のコンソールに反映されないなら 2 つの制御面が食い違ったままだ | **約 14 分待ってから判断してください。** 当環境では 13 分 42 秒後に追随しました。3 分の観測では逆に読めます |
| REST でボリュームの `svm` を書き換えれば移せる | **HTTP 400 で拒否されます**（`code 262196`）。`POST /api/private/cli/volume/rehost` が通る経路です |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| rehost が SnapMirror のコピーなしに SVM 間でボリュームを再割り当てすること、data access と volume management の両方に対して disruptive であること、前提条件 6 件（online / SAN か NAS / NAS は junction path 外で unmount / SnapMirror の扱い / subtype 同一 / クローンとクローン親の排除） | [NetApp: Prepare to rehost an ONTAP volume from one SVM to another SVM](https://docs.netapp.com/us-en/ontap/volumes/rehost-volume-another-svm-task.html) |
| 非対応機能（SVM DR / MetroCluster / SnapLock / ONTAP 9.8 より前の NVE / FlexGroup / クローンボリューム） | [NetApp: ONTAP features not supported with a volume rehost](https://docs.netapp.com/us-en/ontap/volumes/features-supported-volume-rehost-concept.html) |
| SAN の追加条件、失われる設定 7 種、LUN が保持され unmapped になること、`force-unmap-luns` の既定が `false` で警告が出ないこと、`auto-remap-luns`、`lun mapping show` による事前記録 | [NetApp: Rehost an ONTAP SAN volume](https://docs.netapp.com/us-en/ontap/volumes/rehost-san-task.html) |
| split で独自のストレージが割り当てられること | [NetApp: Learn about ONTAP FlexClone volumes, files, and LUNs](https://docs.netapp.com/us-en/ontap/concepts/flexclone-volumes-files-luns-concept.html) |
| NetApp のツールでの変更が AWS 側に反映されるまで数分かかること | [AWS: Managing FSx for ONTAP resources using NetApp applications](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-resources-ontap-apps.html) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [`examples/multiprotocol-ad/`](../../../../../examples/multiprotocol-ad/) — **未確定 4 点のうち 2 点を測るための最小構成**。`rehost-probe.sh` は既定では記録のみで、`--apply` を二重に指定しない限り何も変更しません
- [LUN の中身はファイルプロトコルに現れない](lun-contents-do-not-reach-file-protocols.md) — rehost でも動かない境界
- [SMB で運用中のボリュームに NFS を足すのに複製は要らない](../../multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md) — rehost が不要な場合
- [AWS Transform の Finalize は後片付けではなく、物理容量が最大になる工程](../../../playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md) — split の容量ピークが同型
- [容量は 3 か所で数えられる](capacity-is-counted-in-three-places.md) — split 中に満杯になる経路
- [LUN と igroup は AWS の API の外側にある](block-objects-are-outside-the-aws-api.md) — 2 つの制御面
- [FSx for ONTAP S3 Access Points の前提条件](../../data-utilization/notes/s3-access-point-constraints.md) — 制御面が食い違った先例
- [ブロックからファイルへ運ぶ経路の比較](../../../reference/comparison/block-to-file-routes.md) — rehost の後に残る工程
- [用語集](../../../reference/glossary/) — `volume rehost` / FlexClone の定義
- [知見の分類ポリシー](../../../evidence-policy.md) — `documented` と未確定の扱い

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)
