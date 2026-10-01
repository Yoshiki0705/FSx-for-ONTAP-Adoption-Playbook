---
title: ディレクトリ 1 つの大きさにはファイル数と別の上限がある — maxdir-size と大きいディレクトリの列挙コスト
lifecycle: [design, operate]
domains: [performance, cost]
evidence: documented
source: https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-02-maxdirsize.html
lang: ja
---

# ディレクトリ 1 つに置けるファイル数はどこで決まるのか？

ボリュームの inode 数ではなく、ディレクトリごとの大きさの上限（maxdir-size）と、名前の長さ・文字種で決まります。

<!-- lang-switcher:start -->
🌐 [日本語](directory-size-is-capped-separately-from-file-count.md) | [English](../../../../en/domains/performance/notes/directory-size-is-capped-separately-from-file-count.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->

## このノートで学べること

- maxdir-size がボリュームの inode 上限とは別に、ディレクトリごとに効く上限であること
- 上限に達したときに失敗する操作と、失敗しない操作の範囲
- 大きいディレクトリで名前の検索と全件の列挙のコストが分かれること

## このノートが答えないこと

- Amazon FSx for NetApp ONTAP での実測値（このリポジトリでは測定していません）
- S3 API で収集したデータを origin に置き FlexCache で配布する構成での挙動（下の「この構成固有の挙動の追跡先」を参照）
- 他のストレージサービスのディレクトリ上限

## 前提レベル

intermediate

## 本文

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 性能](../README.md)

> **Evidence**: `documented` — ONTAP 一般の記述は NetApp の Technical Report（以下 TR）、FSx for ONTAP の既定値は AWS Prescriptive Guidance の記載に基づきます。このリポジトリでは測定していません。
> TR は NetApp「High-file-count NAS workloads : ONTAP Technical Reports」（docs.netapp.com、PDF 生成日 2026-09-30、版番号・改訂履歴の記載なし）です。節ごとの出典は各表と「参照した一次情報」にあります。

---

### 結論

**maxdir-size はディレクトリごとの上限で、ボリュームの inode 上限とは別に効きます。** TR は、空き inode が十分にあっても 1 つのディレクトリが maxdir-size に達しうること、その逆も起きることを書いています。

上限に達すると、空き容量と inode が残っていても、**そのディレクトリへの作成と改名だけが失敗します。** 他のディレクトリと読み取りは影響を受けません。

大きいディレクトリでは、名前を指定した検索は index で速く済みますが、**全件の列挙とワイルドカード検索は名前の数に応じて重くなります。**

FSx for ONTAP の既定値 320 MB は AWS の記載があります。それ以外の値と挙動は FSx for ONTAP では未確認です（範囲は「[FSx for ONTAP 側の記載と未確認の範囲](#fsx-for-ontap-側の記載と未確認の範囲)」）。

---

### maxfiles と maxdir-size の別

| 観点 | maxfiles（ボリュームの inode 数） | maxdir-size（ディレクトリの大きさ） |
|---|---|---|
| 守るもの | ボリューム全体で作れるファイル・ディレクトリの数 | 1 つのディレクトリに置ける名前の数 |
| 単位 | ボリューム（FlexGroup は全体で設定し、構成要素ごとに上限） | ボリューム単位の設定値が、各ディレクトリに個別に効く |
| 既定（ONTAP 一般、TR） | 約 32 KiB に 1 個 | 320 MB |
| 上限（ONTAP 一般、TR） | FlexVol で 2,040,109,451 個 | 4 GB（最小 4 KiB）。FlexGroup でも同じ値で、構成要素の数で増えない |
| 尽きたときの症状 | 作成が失敗し、容量不足と同じ文面のエラーが返る | そのディレクトリへの作成・改名が失敗する |

出典: TR、ページ「[NetApp ONTAP High File Count Workloads for NAS volumes](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-01-overview.html)」の節「Maxfiles compared with maxdir-size」。TR は、上限を上げる前にリリースとプラットフォームごとの対応上限を確認するよう書いています。inode 側の詳細は [容量が余っていても書けなくなる](../../../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) にあります。

> "A volume can have ample free inodes and still reach maxdir-size in one directory."
> — TR、同ページ同節

---

### 1 ディレクトリに入る名前の数の目安

ディレクトリファイルは 4 KiB のブロック単位で大きくなります。320 MB は 81,920 ブロックです。1 ブロックに入る名前の数は名前の長さと文字種で変わるため、同じ 320 MB でも入る名前の数が変わります。

| 名前の形（TR の例） | 1 ブロックあたり | 320 MB での名前の数 |
|---|---|---|
| 32 文字までの ASCII 名 | 約 53 | 4,341,758 |
| 48 文字の ASCII 名 | 約 40 | 3,276,798 |
| 非 ASCII 文字を含む 32 文字の名前（FlexGroup のエントリも同程度） | 約 26 | 2,129,918 |
| 上に加えて NFS の代替名を持つ名前 | 約 22 | 1,802,238 |
| `ja.UTF-8` の日本語 32 文字の名前 | 26 | 2,129,918（ASCII の既定の約 49%） |
| すべて 255 文字の名前 | — | 約 737,000 |

出典: TR、ページ「[Maxdir-size and large ONTAP directories](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-02-maxdirsize.html)」の節「How directory blocks are constructed」「Estimating the number of names per directory file」。日本語名の行はページ「[Volume considerations](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-06-maxdirsize-volume-types.html)」の節「Volume language」です。

**これは計画の目安で、保証ではありません。** TR 自身が目安として示しています。FSx for ONTAP で同じ数になるかは未確認です。

---

### 上限に達したときの挙動

TR は次のように書いています（ONTAP 一般）。

- そのディレクトリに名前を追加する操作（作成・改名）が拒否されます。クライアントには `ENOSPC`、`file too large`、NFS のエラー 27、`STATUS_CANNOT_MAKE` などが返ります
- 他のディレクトリへの操作と、既存ファイルの読み取りは影響を受けません
- ボリュームには容量と inode が残っていることがあります

出典: TR、ページ「[Impact of maxdir-size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-05-maxdirsize-impact.html)」の節「What happens when maxdir-size is exceeded?」。

FSx for ONTAP 側では、AWS DataSync のトラブルシューティングページが、ディレクトリあたりの上限に達したときに FSx for ONTAP への転送タスクが `Input/Output error` で失敗すると記載しています（[AWS: Troubleshooting issues with DataSync tasks](https://docs.aws.amazon.com/datasync/latest/userguide/troubleshooting-tasks.html)）。症状が容量不足と同じ文面になりうる点は、inode 枯渇と同じです。

---

### ディレクトリが大きくなると重くなる列挙

| 操作 | TR の記載（ONTAP 一般） |
|---|---|
| 名前を指定した検索（既知のファイルを開く） | ONTAP 9.2 以降、ディレクトリファイルが約 2 MiB に達すると index が作られ、名前の検索を助けます。開く操作は速いままです |
| 全件の列挙（`ls`、`find`、READDIR）とワイルドカード検索 | index があっても全名前を走査します。長時間かかり、止まって見えたり、クライアントやアプリケーションのタイムアウトに当たったりします |
| キャッシュにないディレクトリの読み込み、同じディレクトリへの操作の集中 | 名前の数に応じて重くなり続けます |
| `wafl.dir.size.warning`（上限の約 90%） | 大きさの警告で、レイテンシの閾値ではありません |

TR は、ONTAP が性能上の失敗を宣言する大きさは存在しないと書いています。重くなり続けるのは全件の列挙、ワイルドカード検索、キャッシュにない状態からの読み込み、そのディレクトリへの操作の直列化です。

> "Wildcard scans and READDIR still process the entire directory namespace."
> — TR、ページ「Directory indexing in ONTAP」の節「What indexing does not change」

FlexVol の 1 つのホットなディレクトリは、ノードを増やしても並列性を得ません。

出典: TR、ページ「[Directory indexing in ONTAP](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-04-maxdirsize-indexing.html)」の節「Why directory indexing exists」「What indexing does not change」、ページ「[Impact of maxdir-size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-05-maxdirsize-impact.html)」の節「Performance impact」、ページ「[Volume considerations](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-06-maxdirsize-volume-types.html)」の節「FlexVol volumes」。

> **性能に関する補足**: TR は、逐次の帯域の試験ではこの挙動を予測できないと書いています。測るなら作成・検索・stat・改名・削除・列挙を、キャッシュの冷えた状態と温まった状態で分けて測ります（TR の推奨事項のページの節「Test metadata operations, not only throughput」）。

---

### 削除しても縮まないディレクトリファイル

TR は次のように書いています（ONTAP 一般）。

- maxdir-size は上限であって予約ではありません。320 MB に設定しても、320 MB を先に確保するわけではありません。ただしディレクトリファイルが 320 MB まで育てば、その分のボリューム容量を実際に使います
- 一度大きくなったディレクトリファイルは、エントリを削除しても最高到達点の大きさのままです
- ONTAP 9.5 以降、index を持つディレクトリは完全に空になった 4 KiB ブロックを回収できます（hole punching）。それでも報告される大きさは通常は縮みません
- 大量に削除したあとのディレクトリでは、READDIR が空のブロックをたどることがあります。残ったエントリを新しいディレクトリにコピーすると詰め直せます。maxdir-size を下げても詰め直しにはなりません

出典: TR、ページ「[Maxdir-size and large ONTAP directories](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-02-maxdirsize.html)」の節「How the maxdir-size cap behaves」、ページ「[Directory indexing in ONTAP](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-04-maxdirsize-indexing.html)」の節「Sparse directories and hole punching」。

---

### FlexGroup でも増えない 1 ディレクトリの上限

FSx for ONTAP は FlexVol と FlexGroup を提供します（[AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html)）。

TR によれば（ONTAP 一般）、FlexGroup の maxdir-size は FlexGroup 単位で設定し、構成要素の数を掛けた値にはなりません。1 つのディレクトリのファイルは 1 つの構成要素にあり、別の構成要素に置かれたエントリ（remote entry）はより多くの領域を使います。大きく平坦なディレクトリでは最大で約 2 倍を見込み、320 MB の既定で通常の名前が約 200 万〜260 万個になります。FlexVol の約 430 万個より少ない値です。

> "lowers the practical ceiling to about 2 to 2.6 million ordinary names at the 320 MB default"
> — TR、ページ「Volume considerations」の節「FlexGroup volumes」

出典: TR、ページ「[Volume considerations](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-06-maxdirsize-volume-types.html)」の節「FlexGroup volumes」。FSx for ONTAP の FlexGroup でこの比率になるかは未確認です。

---

### 上限の引き上げと 2 つの記載の差

2 つの文書は、引き上げたあとに下げられるかを違う書き方で記載しています。

| 論点 | TR（ONTAP 一般） | AWS Prescriptive Guidance（FSx for ONTAP） |
|---|---|---|
| 引き上げの方針 | 1 つのディレクトリで必要性が示されたときだけ上げる。約 2% 刻み | 既定値を保つことを NetApp が推奨すると記載。独自の値は試験で確かめる |
| 下げられるか | 後で下げられる。ただし最大のディレクトリファイルの最高到達点より下には下げられない | 一度上げると、ディレクトリを作り直さない限り下げられない |
| 大きさと性能 | 上の「ディレクトリが大きくなると重くなる列挙」 | ディレクトリはメモリに読み込まれるため、大きさと性能が引き換えになる |

出典: TR、ページ「[Impact of maxdir-size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-05-maxdirsize-impact.html)」の節「What happens when maxdir-size is exceeded?」。AWS Prescriptive Guidance「[Deploying Amazon FSx for NetApp ONTAP in an enterprise environment](https://docs.aws.amazon.com/pdfs/prescriptive-guidance/latest/fsx-ontap-enterprise-deployment/fsx-ontap-enterprise-deployment.pdf)」（PDF、文書履歴の初版 2023-08-29）の maximum directory size の節（p.15）。

> "After the value has been increased, it cannot be decreased without recreating the directory."
> — AWS Prescriptive Guidance、同節

**FSx for ONTAP でどちらの記載が当てはまるかは、このリポジトリでは試していません。** 引き上げは戻せない変更として扱う前提で、必要性を測ってから判断します。このノートは読み取り専用の確認手順だけを載せ、変更コマンドは載せません。

---

### FSx for ONTAP 側の記載と未確認の範囲

| 区分 | 内容 | 出典 |
|---|---|---|
| AWS の記載あり | maxdir-size はボリューム単位の設定で、全ディレクトリに共通。既定 320 MB で 1 ディレクトリに約 4,300,000 ファイル（原文は 4.3 million） | AWS Prescriptive Guidance の maximum directory size の節（p.15） |
| AWS の記載あり | ディレクトリあたりの上限に達すると DataSync のタスクが `Input/Output error` で失敗する | AWS DataSync のトラブルシューティングページ |
| AWS の記載あり | FlexVol と FlexGroup の両方を使える | AWS: Managing FSx for ONTAP volumes |
| 未確認 | 上限 4 GB、index が作られる約 2 MiB、列挙コストの挙動、FlexGroup での約 2 倍の比率、日本語名の詰め込み、EMS イベント、下げる条件 | AWS 側の記載を見つけていません |

探索の範囲（2026-10-01）: AWS ドキュメントを "maxdir-size" と "maximum directory size" で検索しました。**FSx for ONTAP ユーザーガイドに maxdir-size を記載したページは見つかりませんでした。** 見つかった AWS の記載は Prescriptive Guidance の PDF と DataSync のページだけです。DataSync のページは Prescriptive Guidance の HTML 版の節にリンクしていますが、そのリンク先は 2026-10-01 に HTTP 404 を返しました。同じガイドの PDF は取得でき、このノートはそれを引用しています。

---

### この構成固有の挙動の追跡先

S3 API で収集したデータを origin に置き FlexCache で配布する構成での、メタデータ操作と列挙の挙動はこのノートでは扱いません。未計測の項目として [S3-Burst-on-ONTAP-Files の Issue #235](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/issues/235) で追跡されています。

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| 1 ディレクトリの上限はボリュームのファイル数上限で決まる | 別の上限です。inode が残っていても 1 つのディレクトリが maxdir-size に達します（TR） |
| maxdir-size を上げると容量を予約する | 上限であって予約ではありません。容量を使うのはディレクトリファイルが実際に育った分です（TR） |
| index があれば大きいディレクトリも速く一覧できる | index が助けるのは名前を指定した検索です。全件の列挙は全名前を走査します（TR） |
| FlexGroup なら 1 ディレクトリの上限が構成要素の数だけ増える | 増えません。remote entry の分、入る名前は FlexVol より少なくなりえます（TR） |
| ファイルを消せばディレクトリは小さくなる | 最高到達点の大きさのままです。詰め直すには新しいディレクトリにコピーします（TR） |
| 上限に達したら容量不足 | 容量と inode が残っていても、そのディレクトリへの作成と改名だけが失敗します（TR） |

---

### 参照した一次情報

TR はいずれも NetApp「High-file-count NAS workloads : ONTAP Technical Reports」（docs.netapp.com、PDF 生成日 2026-09-30、版番号・改訂履歴の記載なし）です。

| 論点 | 出典 |
|---|---|
| maxdir-size の既定 320 MB・最小 4 KiB・上限 4 GB、FlexGroup でも同じ上限、inode と別に効くこと、上限を上げる前にリリースごとの対応上限を確認すること | TR、ページ「[NetApp ONTAP High File Count Workloads for NAS volumes](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-01-overview.html)」の節「Maxfiles compared with maxdir-size」 |
| 4 KiB ブロック、320 MB = 81,920 ブロック、名前の形ごとの数 | TR、ページ「[Maxdir-size and large ONTAP directories](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-02-maxdirsize.html)」の節「How directory blocks are constructed」「Estimating the number of names per directory file」 |
| 上限であって予約ではないこと、最高到達点、hole punching | 同ページの節「How the maxdir-size cap behaves」 |
| 上限とディレクトリファイルの大きさの読み方、320 MB が 335,544,320 バイトと表示されること | TR、ページ「[View maxdir-size and current directory size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-03-maxdirsize-view.html)」の節「View the configured cap」「View the directory file from an NFS client」 |
| 約 2 MiB での index、index が変えないこと、空のブロックと詰め直し | TR、ページ「[Directory indexing in ONTAP](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-04-maxdirsize-indexing.html)」の節「Why directory indexing exists」「What indexing does not change」「Sparse directories and hole punching」 |
| 列挙コスト、`wafl.dir.size.warning`、上限に達したときの挙動、約 2% 刻みの引き上げと下げる条件 | TR、ページ「[Impact of maxdir-size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-05-maxdirsize-impact.html)」の節「Performance impact」「What happens when maxdir-size is exceeded?」 |
| FlexVol の 1 ディレクトリが並列化しないこと、FlexGroup の約 2 倍、日本語名の詰め込み | TR、ページ「[Volume considerations](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-06-maxdirsize-volume-types.html)」の節「FlexVol volumes」「FlexGroup volumes」「Volume language」 |
| 320 MB 既定が ONTAP 9.14.1 から、index が 9.2 から、sparse directory が 9.5 から | TR、ページ「[Features, EMS, and monitoring for maxdir-size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-07-maxdirsize-features-ems.html)」の機能とリリースの表 |
| 列挙を含むメタデータ操作を測ること | TR の推奨事項のページ（[high-file-count-workloads-14](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-14-best-practices.html)）の節「Test metadata operations, not only throughput」 |
| FSx for ONTAP の既定 320 MB、約 4,300,000 ファイル、ボリューム単位、下げる条件、既定を保つ推奨 | [AWS Prescriptive Guidance: Deploying Amazon FSx for NetApp ONTAP in an enterprise environment](https://docs.aws.amazon.com/pdfs/prescriptive-guidance/latest/fsx-ontap-enterprise-deployment/fsx-ontap-enterprise-deployment.pdf)（PDF、初版 2023-08-29）の maximum directory size の節（p.15）。HTML 版の該当節は 2026-10-01 に HTTP 404 |
| ディレクトリあたりの上限で DataSync のタスクが失敗すること | [AWS: Troubleshooting issues with DataSync tasks](https://docs.aws.amazon.com/datasync/latest/userguide/troubleshooting-tasks.html) |
| FSx for ONTAP で FlexVol と FlexGroup を使えること | [AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |

---

### 関連ドキュメント

- [Domain — 性能](../README.md) — このモジュールのハブ
- [容量が余っていても書けなくなる](../../../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) — ボリューム全体の inode の上限
- [高ファイル数のワークロードに FSx for ONTAP は合うか](../../../playbooks/01-assess/notes/file-count-fit-depends-on-namespace-shape.md) — このノートの上限を使った採用判断
- [スループットは 1 つの設定値では決まらない](where-throughput-is-determined-and-shared.md) — FlexVol と FlexGroup の配置と共有の単位
- [知見の分類ポリシー](../../../evidence-policy.md)

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 性能](../README.md)

## 自環境での確認手順

すべて読み取り専用です。maxdir-size を変更する手順は含みません。

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 移行元で、ディレクトリファイルの大きさが最も大きいディレクトリを探す | 最大のディレクトリが移行先の上限の目安に収まるか |
| 2 | 1 で見つけたディレクトリの名前の数と、名前の長さ・文字種を数える | 上の名前の数の表のどの行に当たるか |
| 3 | 移行先のボリュームの maxdir-size を読む | 実際の上限 |

NFS クライアントでは、次のコマンドでディレクトリファイルの大きさを読みます（`du` ではありません）。

```bash
# On an NFS client: directory-file size of one directory (not du)
stat -c '%n %s bytes' /mount/path/directory
# The 10 largest leaf directories under a mount point, skipping Snapshot copies
find /mountpoint -name .snapshot -prune -o -type d -ls -links 2 -prune | sort -rn -k 7 | head
```

移行先では、ONTAP CLI で maxdir-size を読みます。

```text
::> set -privilege advanced
::*> volume show -vserver <svm> -volume <volume> -fields maxdir-size
```

これらの確認方法は TR のページ「[View maxdir-size and current directory size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-03-maxdirsize-view.html)」の節「View the configured cap」「View the directory file from an NFS client」に基づきます（このページの URL と題名は 2026-10-01 に確認）。TR は、ONTAP には個々のディレクトリの大きさを直接報告するコマンドがなく、クライアントから読むと書いています。`set -privilege advanced` は CLI の権限レベルを変えるだけで、`volume show` は読み取りです。FSx for ONTAP の `fsxadmin` が advanced モードを使えることは [AWS: Updating the maximum number of files on a volume](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/increase-volume-max-files.html) の手順から分かりますが、この項目を読めるかは未確認です。

### 期待結果

`stat` はディレクトリファイルのバイト数を返します。TR によれば、320 MB の既定に達したディレクトリは 335,544,320 バイトと表示されます。`volume show` はボリュームの上限を返します。最大のディレクトリの大きさを上限と比べ、名前の数を上の表と比べます。上限の約 90% に近いなら、移行の前にディレクトリの分割を検討します。

## Read next

[高ファイル数のワークロードに FSx for ONTAP は合うか？](../../../playbooks/01-assess/notes/file-count-fit-depends-on-namespace-shape.md)
