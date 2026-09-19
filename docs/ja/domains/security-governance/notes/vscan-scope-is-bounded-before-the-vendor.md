---
title: ウイルス対策の選択はベンダーより前に決まる — プロトコル・ID・可用性・除外条件の 4 つが候補を狭める
lifecycle: [design, build, operate]
domains: [security-governance, multiprotocol-identity]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-vscan.html
lang: ja
---

# ウイルス対策の選択はベンダーより前に決まる

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — セキュリティ・ガバナンス](../README.md)

---

## 結論

**Amazon FSx for NetApp ONTAP のウイルス対策を検討すると、最初に出てくる資料は「対応ベンダーの一覧」です。しかし選ぶ順序としては最後に来ます。**

AWS のユーザーガイドは 6 社（Deep Instinct / SentinelOne / Symantec / Trellix / Trend Micro / OPSWAT）を列挙しますが、**そのページには制約が書かれていません。** 制約は ONTAP の Vscan 側にあり、ベンダーを選ぶ前に次の 4 つが候補と構成を狭めます。

1. **プロトコル** — on-access スキャンは SMB に対するもので、NFS エクスポートは on-demand の対象になります
2. **ID** — Vscan サーバーが SVM に接続するための privileged user は**ドメインユーザーアカウント**です
3. **可用性** — `scan-mandatory` が `on` のとき、Vscan サーバーが応答しないとクライアントのファイルアクセスが**拒否されます**
4. **除外条件** — `scan-mandatory` が `on` でも、除外条件に合致するファイルはスキャンされません。**既定の除外サイズは 2 GB です**

**4 番目が最も誤解を生みます。** 「必須スキャンを有効にした」ことは「すべてのファイルがスキャンされる」ことを意味しません。

> **区分**: `documented` — AWS および NetApp の公式ドキュメントと NetApp KB の記載に基づきます（**取得日 2026-09-15**）。**当リポジトリでの実測は含みません。** 下の [ONTAP 一般の制約と FSx for ONTAP 固有の制約の区別](#ontap-一般の制約と-fsx-for-ontap-固有の制約の区別) のとおり、**ここに挙げた制約はすべて ONTAP 一般の性質**で、FSx for ONTAP 固有の差分は確認できていません。

---

## 6 ベンダーの列挙元と、そこに書かれていないもの

**FSx for ONTAP でサードパーティのウイルス対策を使う根拠は、AWS 自身のユーザーガイドにあります。** ベンダー製品との組み合わせで、AWS のドキュメントに専用ページが存在するものは限られており、これはその 1 つです。

| 出典 | 書かれていること | 書かれていないこと |
|---|---|---|
| [AWS: Use NetApp ONTAP Vscan with FSx for ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-vscan.html) | 6 社の名前と、各社のドキュメントへのリンク | **制約が 1 つも書かれていません。** 構成手順もありません |
| [NetApp: ONTAP Vscan パートナー解決策](https://docs.netapp.com/ja-jp/ontap/antivirus/vscan-partner-solutions.html) | 同じ 6 社。相互運用性の確認先（NetApp 相互運用性マトリックスと各社サイト） | 特定の版の組み合わせ。**そこは自分で引く必要があります** |
| [NetApp: Antivirus architecture with ONTAP Vscan](https://docs.netapp.com/us-en/ontap/antivirus/architecture-concept.html) | Vscan サーバーの構成要素、scanner pool、privileged user、on-access ポリシー、ファイル操作プロファイル | FSx for ONTAP 固有の差分 |

**AWS のページが薄いことは欠落ではありません。** 6 社の製品仕様は AWS が保証する範囲の外にあり、リンク先に送るのが正確です。**ただし読者から見ると「6 社から選べばよい」に見えます。** 実際には次の 4 つが先に決まります。

---

## ベンダーより前に決まる 4 つの条件

### プロトコル — on-access は SMB のみ

**on-access ポリシーの作成コマンドが受け付けるプロトコルは `CIFS` です。**

```text
vserver vscan on-access-policy create -vserver <SVM> -policy-name <name> -protocol CIFS ...
```

NFS エクスポートに対して on-access スキャンは構成できません。**NetApp KB は on-demand スキャンの用途として「on-access を構成できないボリューム、たとえば NFS エクスポート」を明示的に挙げています。**

**そして on-demand は on-access の代わりではありません。**

| 種別 | 契機 | NFS | SMB |
|---|---|---|---|
| on-access | クライアントのファイル操作（open / close / rename / write）。**操作は結果が返るまで中断されます** | 構成できません | 対象 |
| on-demand | cron スケジュール、または `vserver vscan on-demand-task run` の手動実行 | 対象 | 対象 |

**on-demand には on-access ポリシーが必要です。** NetApp のドキュメントは「on-demand スキャンには on-access ポリシーが必要」と記載しており、on-access スキャンを避けたい場合は `-scan-files-with-no-ext false` と `-file-ext-to-exclude *` で全拡張子を除外する形を案内しています。**「NFS だけなので on-access は関係ない」という前提で構成すると、ここで詰まります。**

さらに on-demand は**既存の Vscan サーバーを使います。** 専用の実行基盤があるわけではないので、**on-demand しか使わない構成でも Vscan サーバーの運用は必要です。**

### ID — privileged user はドメインユーザー

**Vscan サーバーが SVM に接続するために使う privileged user は、ドメインユーザーアカウントです。** scanner pool の privileged user 一覧に存在する必要があります。

つまり **Vscan を使う構成は Active Directory を前提にします。** SVM をワークグループ運用にしている場合、この前提が満たせません。

**そして AD への依存は参加した時点で終わりません。** 資格情報の失効はメンテナンスの局面で顕在化します。詳細は [AD への依存は参加時ではなく生涯続く](../../multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) にあります。**ウイルス対策を足すことは、AD への依存点を 1 つ増やすことでもあります。**

### 可用性 — scan-mandatory とクライアントアクセスの結合

**`scan-mandatory` が `on` のとき、Vscan サーバーが応答しなければクライアントのアクセスは拒否されます。**

| 設定 | Vscan サーバーが応答しないとき |
|---|---|
| `scan-mandatory on` | scanner pool のタイムアウトまで再試行し、受け付けられなければ**クライアントのアクセス要求を拒否** |
| `scan-mandatory off` | Vscan サーバーが無くても**アクセスを許可** |

**これは「セキュリティを厳しくすると可用性が下がる」という一般論ではなく、設定 1 つで切り替わる具体的な結合です。** 同じ構造は監査にもあります。[監査宛先が枯渇するとクライアントアクセスは止まる](audit-log-space-and-client-access.md) と並べて読んでください。**止め方を選ぶ設定がある、という点が共通しています。**

**タイムアウトの設定には順序があります。** NetApp は **AV ソフトウェア側のタイムアウトを scanner pool のスキャン要求タイムアウトより 5 秒短く**設定するよう案内しています。逆にするとアクセスの遅延または拒否が起きます。

**冗長化の手段は scanner policy です。** `Primary` は常時有効、`Secondary` は primary の Vscan サーバーがどれも接続されていないときだけ有効、`Idle` は常時無効。**カスタムの scanner policy は作れません**（3 種はシステム定義）。

### 除外条件 — mandatory でもスキャンされないファイルの存在

**`scan-mandatory` を `on` にしても、除外条件に合致するファイルはスキャン対象として扱われません。** NetApp のドキュメントがこれを明記しています。

除外の経路は 3 つあります。

| 経路 | 内容 |
|---|---|
| `max-file-size` | 指定サイズを超えるファイル。**既定の除外サイズは 2 GB** |
| `paths-to-exclude` | 指定したパス |
| `file-ext-to-exclude` | 指定した拡張子。**`file-ext-to-include` より優先されます** |

**さらに既定でスキャンされない範囲が 3 つあります。**

| 既定でスキャンされないもの | 有効化する手段 |
|---|---|
| read-only ボリューム（既定では read-write のみ） | `scan-ro-volume` フィルタ |
| `continuously-available` を `Yes` にした SMB 共有 | **手段がありません。** この共有ではウイルススキャンが行われません |
| `vscan-fileop-profile` が `no-scan` の共有 | プロファイルを `standard` 以上にする |

**`continuously-available` の行が設計に効きます。** 継続的可用性を要求するワークロード（SMB 上のデータベースなど）でこの共有設定を使っている場合、**その共有はスキャン対象になりません。** ウイルス対策の範囲を宣言するときに、この共有を含めてはいけません。

**そして rename の扱いが profile で変わります。**

| `vscan-fileop-profile` | スキャンの契機 | 備考 |
|---|---|---|
| `no-scan` | なし | この共有ではスキャンされません |
| `standard`（既定・NetApp 推奨） | open / close / rename | |
| `strict` | open / read / close / rename | 複数クライアントが同一ファイルを同時に開く状況向け。**スキャン要求が増えるため性能に影響しえます** |
| `writes-only` | 変更されたファイルのクローズ時のみ | 要求が減り性能は上がりますが、**修復不能なファイルの削除か隔離をスキャナ側で設定する必要があります** |

**ポリシーの本数にも上限があります。** on-access ポリシーは 1 SVM あたり最大 10 本ですが、**同時に有効化できるのは 1 本だけ**です。除外パスと拡張子は 1 ポリシーで最大 100 件。**有効化できるのが 1 本なので、除外条件はすべて同じポリシーに書くことになります。**

**既定のポリシーが存在します。** ONTAP は `default_CIFS` という on-access ポリシーを作成し、クラスタの全 SVM で有効化します。**「まだ何も構成していない」状態が「ポリシーが無い」状態とは異なります。**

---

## 書き込みの着地経路による、インラインでの拒否の可否

**プロトコルの制約は、対象範囲だけでなく「いつ止められるか」も決めます。**

on-access が SMB に対するものだという事実を、**書き込みが S3 Access Point 経由で着地する構成**に当てると、**その経路には着地の瞬間に拒否する手立てが無い**という帰結になります。**ただし記録と検知は成立します。** ここを混ぜると、対策が無いという誤った結論になります。

| 手立て | NFS / SMB 経由の書き込み | S3 Access Point 経由の書き込み | 区分 |
|---|---|---|---|
| **Vscan on-access** | 対象 | **構成できません。** on-access ポリシーのプロトコルは `CIFS` です | `documented` |
| **Vscan on-demand** | 対象 | **対象。** 着地の瞬間ではなく、後から拾います | `documented` |
| **FPolicy（`mandatory`）** | 発火し、遮断されます | **通知が無く、遮断もされません。** event の protocol に `s3` は無く、HTTP 400 で拒否されます | `verified`（別ノートの測定） |
| **ONTAP 監査** | 記録されます | **記録されます** | `verified`（別ノートの測定） |
| **Autonomous Ransomware Protection** | 検知します | **検知します** | `verified`（別ノートの測定） |

**帰結は 1 行です。S3 Access Point 経由の書き込みに対して、着地の瞬間に拒否する手立てはありません。** 記録は残り、振る舞いの異常も検知されますが、**書き込み自体は成立します。** リアルタイムに止めることを要件にしている場合、この経路は要件を満たしません。

> **確度に関する補足**: **この節は 2 つの出典の合成です。** Vscan 側の行は on-access ポリシーのプロトコルが `CIFS` であるという公式ドキュメントの記載から、FPolicy / 監査 / ARP の行は [S3 Access Point 経由のアクセスを見ない FPolicy](access-point-authorization-layers.md#この経路を見ない-fpolicy) の測定から取っています。**当リポジトリで、S3 Access Point 経由の書き込みに対する Vscan の挙動を測ってはいません。** on-access ポリシーが何らかの形で介入しないことを実測で確認したわけではなく、プロトコル指定が `CIFS` であることから導いています。

**FPolicy を代替として検討する場合、適合条件は書き込みの着地経路で決まります。** 詳細は [FPolicy が適合するかは、データをどう読むかではなく、どう書くかで決まる](../../data-utilization/notes/fpolicy-fits-by-how-writes-land.md) にあります。**読む側は判定に入りません。** 同じボリュームを S3 Access Point で読んでいても、書き込みが SMB で着地していれば両方が効きます。

---

## ONTAP 一般の制約と FSx for ONTAP 固有の制約の区別

**上に挙げた制約はすべて ONTAP 一般の性質です。** FSx for ONTAP のドキュメントにも NetApp のドキュメントにも、**FSx for ONTAP 固有の Vscan 制約は見つけていません。**

| 帰属 | 内容 |
|---|---|
| **ONTAP 一般** | on-access が SMB のみ、privileged user がドメインユーザー、`scan-mandatory` の挙動、除外条件、ポリシー本数の上限、`continuously-available` 共有の非スキャン、profile の 4 種 |
| **FSx for ONTAP 固有** | **確認できていません。** 「無い」という主張ではなく、探して見つからなかったという状態です（検索日 2026-09-15） |

**未確認の項目を明示します。** 次に検証すると `verified` に昇格できる部分です。

| # | 未確認の項目 | なぜ効くか |
|---|---|---|
| 1 | `fsxadmin` の権限で `vserver vscan` 系のコマンドがどこまで実行できるか | **FSx for ONTAP の `fsxadmin` はオンプレミスのクラスタ管理者と同じ権限ではありません。** 構成できない項目があれば、それが最初の制約になります |
| 2 | ONTAP Antivirus Connector を載せた EC2 インスタンスから SVM への接続要件 | Connector は NetApp Support Site からのダウンロード（ログインが必要）で、配置と到達性の要件を自環境で確認する必要があります |
| 3 | `scan-mandatory on` で Vscan サーバーを落としたときの実際の症状 | 「拒否される」とドキュメントにありますが、**クライアントに見えるエラーの形**は確認していません |

**項目 1 は他の領域と同じ構造です。** AWS の API に無い設定が ONTAP 側にあり、そこに `fsxadmin` の権限境界がかかります。[この設定はどこから作るか](../../../reference/decision-trees/where-a-setting-is-created.md) と同じ判断です。

---

## 選択肢の対称な比較

**ウイルス対策の手立ては Vscan だけではありません。** そして Vscan を選ぶ側の制約も対称に置きます。

| 手立て | 向く状況 | 引き受ける制約 |
|---|---|---|
| **ONTAP Vscan（6 社のいずれか）** | ストレージ側でスキャンを完結させたい。クライアントの構成に依存させたくない | **AD が前提。** Vscan サーバー（Connector + AV）の運用が増える。on-access は SMB のみ。`scan-mandatory` の設定でアクセスと結合する |
| **クライアント / EDR 側でのスキャン** | すでに端末と EC2 に EDR を配っている。ストレージ側に手を入れたくない | **スキャンされるかは端末の状態に依存します。** 管理外の端末からの書き込みは通ります |
| **[FPolicy による外部制御](../../data-utilization/notes/fpolicy-fits-by-how-writes-land.md)** | 拡張子や操作の単位で拒否したい。マルウェア検知ではなく操作の制御 | **ウイルス対策ではありません。** 別の目的の仕組みで、外部サーバーの運用が要ります。**適合するかは書き込みの着地経路で決まり、S3 Access Point 経由では不発です** |
| **ONTAP の Autonomous Ransomware Protection** | 振る舞いの異常検知。既知パターンの検出ではない | **ウイルススキャンの代替ではありません。** 検知の対象が違います |

**選び方は「どれが優れているか」ではなく、決まっている前提から引きます。**

| 手元の状況 | 素直な選択 |
|---|---|
| SVM を AD 参加させておらず、参加の予定もない | Vscan は選べません。クライアント / EDR 側 |
| NFS のみで運用している | Vscan は on-demand のみ。**リアルタイム性が要件なら別の手立てを検討します** |
| 継続的可用性の共有を使っている | **その共有は Vscan の対象外です。** 範囲の宣言に含めないこと |
| 書き込みが S3 Access Point 経由で着地する | **着地の瞬間に拒否する手立てがありません。** on-demand で後から拾うか、書き込み経路を変えるかの判断になります。[詳細](#書き込みの着地経路によるインラインでの拒否の可否) |
| Vscan サーバーの運用主体が決まっていない | **決まるまで構成しないこと。** `scan-mandatory on` は運用の穴がアクセス断に直結します |
| すでに 6 社のいずれかと契約している | 相互運用性マトリックスで版の組み合わせを確認してから |

**組み合わせが成立します。** Vscan とクライアント側の EDR は排他ではありません。ただし**同じファイルを二重にスキャンする構成**になるので、除外設定を双方でそろえる必要があります。NetApp も **AV エンジン側に同じ除外セットを設定すること**を強く推奨しています。

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | SVM が AD 参加しているかを確認する | **参加していなければ Vscan は選べません。** 最初の分岐 |
| 2 | スキャン対象にしたい共有 / エクスポートをプロトコル別に数える | NFS 分は on-demand のみになります |
| 3 | `continuously-available` を `Yes` にしている SMB 共有を列挙する | **その共有はスキャンされません。** 範囲の宣言から外します |
| 4 | 既存の `default_CIFS` ポリシーの状態を確認する | 「未構成」ではなく「既定が有効」の可能性 |
| 5 | 対象データの最大ファイルサイズを測り、既定の除外サイズ 2 GB と比べる | **超えるファイルは既定でスキャンされません** |
| 5-1 | **書き込みが着地するプロトコルを経路ごとに書き出す** | **リアルタイムに拒否できる範囲。** S3 Access Point 経由の経路があるなら、そこは on-demand しか届きません |
| 6 | `fsxadmin` で `vserver vscan on-access-policy show` が実行できるか試す | **未確認の項目 1。** 権限境界の位置 |
| 7 | Vscan サーバーの運用主体・パッチ適用・監視の担当を決める | **決まる前に `scan-mandatory on` にしないこと** |
| 8 | 相互運用性マトリックスで ONTAP 版と AV 製品版の組み合わせを確認する | ベンダー選択に必要な最後の材料 |

**手順 7 を後回しにすると、`scan-mandatory on` のまま Vscan サーバーが停止したときにアクセス断になります。**

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| 6 社から選ぶのが最初の判断である | **プロトコル・ID・可用性・除外条件が先に決まります。** ベンダー選択は最後です |
| AWS のユーザーガイドに制約が書かれている | **書かれていません。** 6 社へのリンク集です。制約は ONTAP 側の資料にあります |
| NFS でもリアルタイムにスキャンできる | **on-access は SMB に対するものです。** NFS エクスポートは on-demand の対象です |
| NFS だけなら on-access ポリシーは要らない | **on-demand スキャンに on-access ポリシーが必要です** |
| on-demand なら Vscan サーバーは不要 | **on-access 用に構成した既存の Vscan サーバーを使います** |
| Vscan はストレージ側で完結するので AD は要らない | **privileged user はドメインユーザーアカウントです** |
| `scan-mandatory on` にすればすべてのファイルがスキャンされる | **除外条件に合致するファイルは対象外です。** 既定の除外サイズは 2 GB |
| ウイルス対策を足しても可用性には影響しない | **`scan-mandatory on` では Vscan サーバーが応答しないとアクセスが拒否されます** |
| 共有を作れば自動的にスキャン範囲に入る | **`continuously-available` が `Yes` の共有はスキャンされません。** `vscan-fileop-profile` が `no-scan` でも入りません |
| 除外設定はポリシーを分けて管理できる | **有効化できる on-access ポリシーは 1 SVM あたり 1 本です。** 除外はすべて同じポリシーに書きます |
| 構成していないので既定ではスキャンされない | ONTAP は `default_CIFS` を作成し全 SVM で有効化します。**状態を確認してください** |
| ウイルス対策を入れれば書き込み経路を問わず止まる | **着地経路で変わります。** S3 Access Point 経由の書き込みには、着地の瞬間に拒否する手立てがありません |
| S3 Access Point 経由の書き込みには何の対策も効かない | **記録と検知は成立します。** ONTAP 監査は記録し、ARP は検知します。無いのはインラインでの拒否です |
| FPolicy を入れれば Vscan で届かない経路を止められる | **同じ経路で不発です。** event の protocol に `s3` は無く、`mandatory` でも遮断されません |
| これらの制約は FSx for ONTAP 固有である | **すべて ONTAP 一般の性質です。** FSx for ONTAP 固有の差分は確認できていません |

---

## 参照した一次情報

| 論点 | 出典 | 取得日 |
|---|---|---|
| FSx for ONTAP で Vscan を通じてサードパーティのウイルス対策を実行できること、対応 6 社（Deep Instinct / SentinelOne / Symantec / Trellix / Trend Micro / OPSWAT） | [AWS: Use NetApp ONTAP Vscan with FSx for ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-vscan.html) | 2026-09-15 |
| パートナー 6 社の一覧と、相互運用性の確認先が NetApp 相互運用性マトリックスおよび各社サイトであること | [NetApp: ONTAP Vscan パートナー解決策](https://docs.netapp.com/ja-jp/ontap/antivirus/vscan-partner-solutions.html) | 2026-09-15 |
| ONTAP Antivirus Connector と AV ソフトを同一の Vscan サーバーに置くこと、privileged user がドメインユーザーアカウントであること、scanner policy が 3 種のシステム定義でカスタム不可であること、AV 側タイムアウトを scanner pool より 5 秒短くすること、`vscan-fileop-profile` の 4 種の挙動 | [NetApp: Antivirus architecture with ONTAP Vscan](https://docs.netapp.com/us-en/ontap/antivirus/architecture-concept.html) | 2026-09-15 |
| on-access ポリシーの `-protocol CIFS`、除外条件に合致するファイルが `scan-mandatory on` でも対象外になること、既定の除外サイズ 2 GB、既定で read-write ボリュームのみ、`continuously-available` が `Yes` の SMB 共有が非スキャン、1 SVM あたり 10 ポリシー / 同時有効 1 本、除外 100 件、`default_CIFS` の既定作成と有効化、on-demand に on-access ポリシーが必要であること | [NetApp: Create ONTAP Vscan on-access policies](https://docs.netapp.com/us-en/ontap/antivirus/create-on-access-policy-task.html) | 2026-09-15 |
| on-access が SMB のファイル操作を中断すること | [NetApp: Virus scanning with ONTAP Vscan](https://docs.netapp.com/us-en/ontap/concepts/virus-scanning-concept.html) | 2026-09-15 |
| on-demand が on-access を構成できないボリューム（NFS エクスポート等）に使えること、既存の Vscan サーバーを流用すること | [NetApp KB: How does vscan work](https://kb.netapp.com/on-prem/ontap/da/NAS/NAS-KBs/How_does_vscan_work) | 2026-09-15 |
| SMB 共有のウイルス対策構成の全体像 | [AWS Storage Blog: Securing your Amazon FSx for ONTAP Windows Share (SMB) against viruses](https://aws.amazon.com/jp/blogs/storage/securing-your-amazon-fsx-for-ontap-windows-share-smb-against-viruses/) | 2026-09-15 |

---

## 関連ドキュメント

- [Domain — セキュリティ・ガバナンス](../README.md) — このモジュールのハブ
- [ウイルス対策の適用範囲をどこまでにするか](../../../reference/decision-trees/vscan-antivirus-scope.md) — この判断の決定木版
- [課題別 ISV / SaaS ソリューションマップ](../../../reference/isv-solution-map.md) — 他の課題領域で組み合わせられる選択肢の索引
- [FPolicy が適合するかは、データをどう読むかではなく、どう書くかで決まる](../../data-utilization/notes/fpolicy-fits-by-how-writes-land.md) — 代替として検討する場合の適合条件
- [S3 Access Point 経由のアクセスを見ない FPolicy](access-point-authorization-layers.md#この経路を見ない-fpolicy) — 着地経路の表の測定元
- [監査宛先が枯渇するとクライアントアクセスは止まる](audit-log-space-and-client-access.md) — 同じ「設定でアクセスと結合する」構造
- [AD への依存は参加時ではなく生涯続く](../../multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) — privileged user の前提が持ち込む依存
- [アクセスを絞る手立ての比較](../../../reference/comparison/access-restriction-options.md) — 手立てが並ぶ層の違い
- [この設定はどこから作るか](../../../reference/decision-trees/where-a-setting-is-created.md) — `fsxadmin` の権限境界
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — セキュリティ・ガバナンス](../README.md)

<!-- lang-switcher:start -->
🌐 [日本語](vscan-scope-is-bounded-before-the-vendor.md) | [English](../../../../en/domains/security-governance/notes/vscan-scope-is-bounded-before-the-vendor.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->
