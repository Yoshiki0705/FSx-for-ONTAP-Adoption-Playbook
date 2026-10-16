---
title: 性能実測の所在マップ — プロトコル・論点ごとに、どの Spoke のどの文書に結果があるかの索引
lifecycle: [assess, design, optimize]
domains: [performance, block-storage, data-utilization, multiprotocol-identity]
evidence: documented
source: https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md
lang: ja
---

# 性能実測の所在マップ

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md) | [Domain — 性能](../domains/performance/README.md)

---

## 結論

**Amazon FSx for NetApp ONTAP の性能実測は、論点ごとに別の Spoke リポジトリへ散らばっています。** NFS とブロックは S3-Burst-on-ONTAP-Files、S3 Access Points のレイテンシは複数の Spoke、ListObjectsV2 は Lakehouse-Integrations、というように、1 つの論点の結果が 1 か所にあるとは限りません。

**この索引は、プロトコルと論点を縦に並べ、結果文書の所在・Spoke 側の段階表記・測定環境の種別だけを 1 枚にしたものです。** [ファイルプロトコル横断リソースマップ](file-protocol-resource-map.md) と [ブロックストレージ横断リソースマップ](block-storage-resource-map.md) が一次情報を索引するのに対し、こちらは**実測の記録**を索引します。

**この索引に性能値は書きません。** MB/s・IOPS・比・p99 などの数値は、測定環境と切り離すと誤読されます。数値は各行のリンク先が、測定条件とともに持っています。

> **区分**: `documented` — 各行は、リンク先の Spoke 文書が何を記録しているかの所在を記載しています。実測を持たない行（理論的推定値、計測器のみ、結果文書なし）は、その旨を行の中に書いています。**このリポジトリでは、この表のどの値も再測定していません。** Spoke 文書には Hub の `evidence` tier を示す frontmatter がないため、「Spoke 側の段階表記」の列は各 Spoke が付けている語（「検証済み」「サイジングの参考値」「ドラフト」「hypothesis」など）の転記であって、Hub の tier への対応づけではありません。分担の原則は [プロジェクト間の引用索引](cross-repo-index.md) にあります。

---

## この索引を読むときの前提

**測定条件が違う値を並べて順位をつけないでください。** 下の表の行は、世代・配置・指定スループット・クライアント・測定器・並列度・接続数・origin 種別・オブジェクトサイズのどれかが互いに違います。たとえば S3 Access Points の書き込みは S3-Burst-on-ONTAP-Files に（同一リージョンの EC2 `c5n`、boto3 または `aws s3 cp`）、読み取りレイテンシは Observability-integrations と S3AccessPoints-Serverless-Patterns に（VPC 外の Lambda やローカル端末）あります。世代（第 1 世代）や origin（Internet）が揃う記録もありますが、操作・クライアントの置き場所・測定器・オブジェクトサイズが違うので、**同じ土俵の値ではありません。**

- **標本値と本番見積りは別です。** リンク先の多くは「1 構成でのサンプル実行」「サイジングの参考値」と自ら明記しています。サービスレベル保証でも本番の見積りでもありません。
- **特定環境の結果と一般のサービス上限は別です。** ここにある数値は特定の世代・リージョン・指定値での実測で、サービスの一般的な上限として読めません。
- **このマップは、この表のどの値も再測定していません。** 所在を指すだけです。

---

## プロトコル・論点別の所在

**列の意味**は次のとおりです。

- **プロトコル・論点** — 1 行 1 論点
- **結果文書** — Spoke の相対パスへの GitHub blob リンク。結果文書が見つかっていない行は、その旨をこの列に書きます
- **Spoke 側の段階表記** — Spoke が自分の文書または主張に付けている段階の語の転記。Hub の tier ではありません。語の出どころは括弧で示します
  - 「索引の段階列」: S3-Burst-on-ONTAP-Files の [測定記録の索引（verification/README.md）](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/README.md) の「段階」列。文書単位の語です
  - 「検証状況」: 同リポジトリの [検証状況](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification-status.md) の表。主張単位の語で、「検証済み」は実環境で再現したことを指します
  - 「本文」: その文書自身の本文や冒頭の注記
  - 段階の語を持たない文書は「段階語なし」と書き、文書が書いている限定を写します
- **測定環境の要約** — 世代・配置・origin 種別・クライアント種別・測定日などの**測定条件のみ**。構成値（指定スループット・SSD 容量など）は測定条件であって測定値ではありません。各 Spoke の条件表から転記し、読み取れない項目は「文書内の条件表を参照」、文書に書かれていない項目は「記載がない」と書きます。条件表を持たない文書は、その旨を書きます
- **Hub の転記ノート** — Hub 側に転記している digest があればそのリンク
- **文書自身が挙げる未測定** — その文書が未測定・未確認・対象外としている範囲の**抜粋**です。全項目の転記ではなく、その行の論点に直接関わる項目を選んでいます。文書の一覧は更新が追いつかず、後の節で測った項目が残っていることがあるため、一覧の項目が今も未測定とは限りません（食い違いを見つけた行には注記しています）。文書が挙げていない項目は書きません。マップ側の観察は「マップ側の観察（日付）」と明記します

### Spoke 側の入口ページ

| プロトコル・論点 | 結果文書 | Spoke 側の段階表記 | 測定環境の要約 | Hub の転記ノート | 文書自身が挙げる未測定 |
|---|---|---|---|---|---|
| 測らずに読む期待値の要約（層ごとの期待値、移植できない値、未解明の項目） | [performance-expectations.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/performance-expectations.md) | 段階語なし（本文）。冒頭は、数値がすべて S3-Burst-on-ONTAP-Files の実測だと書き、「記録の側が正で、ここは索引」と注記 | 収集側と配布側の表に「条件」の列があり、世代・指定値・SSD IOPS・転送サイズ・並列度などを行ごとに書く。持続書き込み・ブロック・比較対象の表に「条件」の列はなく、条件は「構成」「注意」の列や表の外の文に置かれている。測定日は各行の出典の記録側。列の構成は文書内の各表を参照 | — | 「未解明のまま残しているもの」の表と「移植できない値」の表。NFS の値を SMB に当てはめた値は測っていない。SMB の窓長（300 秒と 900 秒）の差は、「未解明」の表では 4 チャネル側が未測定、同じ文書の持続書き込みの表では再現しないとあり、文書内で食い違う |
| 測定記録の索引（実測の記録と、まだ測っていないものの計画の区別） | [verification/README.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/README.md) | 各記録に「検証済み」「手順」「計画」などを付ける。この索引自身の段階語はなし | 索引のため条件表なし。引用時に運ぶ項目（リージョン・ONTAP の版・世代と指定値・オブジェクトサイズ・並列度・何を測ったか）は文書が列挙している | — | 「まだ測っていないものの計画」の表（4 件、段階は「計画」または「計画（未実施）」）。主経路として掲げる Cache をオンプレミス ONTAP に置く形は未検証（「未検証の範囲」の節） |

### ファイルプロトコル（NFS / SMB）

| プロトコル・論点 | 結果文書 | Spoke 側の段階表記 | 測定環境の要約 | Hub の転記ノート | 文書自身が挙げる未測定 |
|---|---|---|---|---|---|
| NFS（v3 / v4.0 / v4.1 / v4.2、`nconnect`、台数、キャッシュ） | [perf-matrix-results.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md) | 検証済み（索引の段階列）。文書の冒頭は「測定中の記録」と書く（本文） | 共通条件表の環境は、第 2 世代 `SINGLE_AZ_2`、同一サブネット、`c5n.9xlarge`、2026-09-05。台数試験は `c5n.2xlarge` で、条件は文書内の該当節を参照 | [単一接続で測った値はストレージの性能ではない](../domains/performance/notes/a-single-connection-measures-the-client.md) | 世代差（第 1 世代対第 2 世代、NFSv4.1 固定）、S3 API と NFS の同一データ比較（未完）、重ならない領域での 1 台と 6 台 |
| NFS / S3 API 経路の IOPS・並列度・コールドリード | [throughput-iops-concurrency.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/throughput-iops-concurrency.md) | 検証済み（索引の段階列） | 測定環境の表は、`SINGLE_AZ_1`、128 MBps と 2,048 MBps、S3 Access Points は VPC origin（S3 ゲートウェイエンドポイント経由）、`c5n.9xlarge`、2026-09-01。後半の再測定の節は別日・別構成で、各節の冒頭を参照 | — | SMB でのファイル読み取り（この記録の測定はすべて NFS）、128 MBps 構成の読み取りを止めているものの特定、ランダム IO・ブロックサイズの掃引・曲線の膝、時間帯差。この一覧は 2026-09-02 の洗い替えで、その後の節（ランダム読みの天井の節など）には、一覧のあとに測った項目がある |
| SMB（Multichannel、台数試験、15 分書き込み） | [perf-matrix-results.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md) | 検証済み（索引の段階列）。文書の冒頭は「測定中の記録」と書く（本文） | 共通条件表の環境は、第 2 世代 `SINGLE_AZ_2`、同一サブネット、`c5n.9xlarge`（Windows）、2026-09-05。台数試験（`c5n.2xlarge`）、窓長の振り（作り直した別環境、2026-09-18）、指定値の違う環境（1,536 MBps）での確認は別条件で、文書内の該当節を参照 | — | チャネル数を 4 より増やす条件（NIC 増設・設定値の引き上げは未実施）、SMB のキャッシュ制御下 7 シナリオ表、台数試験の 2 台と 6 台。「SMB の 300 秒と 900 秒で値が違う理由」は、この文書の表では「値そのものは未解明」、検証状況の表では「閉じた（再現しない）」とあり、Spoke 内で食い違う |

### ブロックプロトコル（iSCSI / NVMe/TCP）

| プロトコル・論点 | 結果文書 | Spoke 側の段階表記 | 測定環境の要約 | Hub の転記ノート | 文書自身が挙げる未測定 |
|---|---|---|---|---|---|
| iSCSI（セッション数、ANA 経路、配置、指定 IOPS 比例） | [perf-matrix-results.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md) | 検証済み（検証状況の iSCSI のスループットの行。主張単位）。文書の冒頭は「測定中の記録」と書く（本文） | 第 2 世代 `SINGLE_AZ_2`、6,144 MBps、raw device（ファイルシステムなし）、`c5n.9xlarge`、2026-09-12。同一ファイルシステムでの再測定は 2026-09-14〜15 | [パスはフェイルオーバーの仕組みそのもの](../domains/block-storage/notes/paths-are-the-failover-mechanism.md) | ファイルシステムを載せた構成の値、`iorate=max` 以外の曲線 / カットオフ、ベースライン（測定窓は 300 秒） |
| NVMe/TCP（キュー数、ANA マルチパス、デプロイ間の再現性） | [perf-matrix-results.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md) | 検証済み（検証状況の NVMe/TCP のスループットの行。主張単位）。同じ表は、同じ構成の逐次読みの再現性を「run 内は再現、環境間は再現しない」とする | 第 2 世代 `SINGLE_AZ_2`、6,144 MBps（F-11 の節は 1,536 MBps）、raw device / namespace、`c5n.9xlarge`、2026-09-13〜17。クライアント OS は測定ごとに違う（Amazon Linux 2023、Rocky Linux 9.7、RHEL 9.7） | [パスはフェイルオーバーの仕組みそのもの](../domains/block-storage/notes/paths-are-the-failover-mechanism.md) | Amazon Linux 2023 での ANA マルチパス（`CONFIG_NVME_MULTIPATH` が無効のため測定不能）、ファイルシステムを載せた構成の値、`iorate=max` 以外の曲線 / カットオフ |

### S3 Access Points

| プロトコル・論点 | 結果文書 | Spoke 側の段階表記 | 測定環境の要約 | Hub の転記ノート | 文書自身が挙げる未測定 |
|---|---|---|---|---|---|
| S3 Access Points の書き込み（VPC origin、マルチパート、Internet origin との差） | [throughput-iops-concurrency.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/throughput-iops-concurrency.md) ／ [s3ap-multipart-internet-origin.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/s3ap-multipart-internet-origin.md) | 前者は検証済み。後者は検証済み（1 構成・各 1〜2 回）で、全体 50 GiB 超の判定は未観測（いずれも索引の段階列） | 前者は `SINGLE_AZ_1`、128 MBps と 2,048 MBps、VPC origin（boto3）、`c5n.9xlarge`、2026-09-01。後者は `SINGLE_AZ_1`、128 MBps、Internet origin（`aws s3 cp`）、`c5n.2xlarge`、2026-10-07 | [S3 Access Point 経由の書き込みを律速する別の上限](../domains/performance/notes/a-single-connection-measures-the-client.md#s3-access-point-経由の書き込みを律速する別の上限) | 後者の「この測定が答えていないこと」の表は、`NetworkOrigin=VPC` での値、128 MBps 以外の指定値、律速の内訳、全体 50 GiB 超の判定、読み取り |
| S3 Access Points の読み取りレイテンシ（P50 / P99、128 / 256 / 512 MBps、Lambda 対 Internet） | [s3ap-benchmark-results.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/s3ap-benchmark-results.md) | 「実測値」「sizing reference」（本文。サービスの上限値ではないと明記） | 第 1 世代 Single-AZ、Internet origin、macOS のローカルクライアントまたは VPC 外の Lambda、2026-05-22〜06-06 | — | VPC 内 Lambda（VPC origin の S3 Access Points）経由、Multi-AZ または第 2 世代（個別に検証、と記載） |
| S3 Access Points の読み取りレイテンシ（プール集計、位置、SSD 対キャパシティプール階層） | [s3ap-throughput-benchmark.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/blob/main/docs/ja/s3ap-throughput-benchmark.md) | サイジングの参考値（本文。サービス上限ではないと明記） | 第 1 世代 `SINGLE_AZ_1`、128 MBps、SSD 1,024 GiB、Internet origin、VPC 外の Lambda（256 MB）、2026-10-10〜11 | — | 第 2 世代 / Multi-AZ、同時実行数 2 以上、VPC 内の Lambda、請求の比較 |
| S3 Access Points の ListObjectsV2（〜20,000 オブジェクト） | [benchmark-result.yaml（2026-09-14-scale）](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/verification-pack/s3ap-list-latency/evidence/2026-09-14-scale/benchmark-result.yaml) | 段階語なし。`observations`（OBS-1〜5）と `conclusion.caveats`（5 項目）で適用範囲を限定 | `environment` ブロックは、`SINGLE_AZ_1`、ONTAP 9.18.1P5、Internet origin、ローカル端末からインターネット経由（VPC 外）、boto3、2026-09-14 | — | 20,000 を超えるオブジェクト数、flat レイアウトのみ（nested は今回再実施せず）、VPC 内クライアント、同時クライアント負荷（単一スレッド） |

### マルチプロトコル・デュアルプロトコル

| プロトコル・論点 | 結果文書 | Spoke 側の段階表記 | 測定環境の要約 | Hub の転記ノート | 文書自身が挙げる未測定 |
|---|---|---|---|---|---|
| マルチプロトコル（S3 API と NFS/SMB の相互可視性 — スループットではなく反映時間） | [cross-protocol-directions.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/cross-protocol-directions.md) ／ [s3ap-nfs-visibility.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/s3ap-nfs-visibility.md) | 検証済み（索引の段階列） | 前者は Origin 役と Cache 役の 2 ファイルシステム（`SINGLE_AZ_1`、128 MBps）、VPC ピアリング、Cache の VPC 内の EC2、2026-08-09。SMB の追加分は 2026-08-10、AWS Managed AD 参加。後者は 1 ファイルシステム（`SINGLE_AZ_1`、128 MBps）、Internet origin、同一 VPC の EC2、NFSv3、2026-08-09 | [書き込みが見えるまでの時間](../domains/data-utilization/notes/how-long-until-a-write-is-visible.md) | 後者の「読み取れないこと」の表は、別の指定値・世代、大量の小ファイル、SMB（後者は NFSv3 のみ）、NTFS セキュリティスタイル、ONTAP バージョン（特定できず） |
| デュアルプロトコルのスループット・IOPS（NFS と SMB を同一ボリュームで同時利用） | 結果文書を見つけられていない | — | — | — | — |
| デュアルプロトコルの挙動（NFS と SMB から同一 NTFS ボリュームへ入る 2 台のクライアントの、ロックの衝突と、書き込みから読めるまでの時間 — スループット・IOPS ではない） | [stage-1-multiprotocol.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/ja/stage-1-multiprotocol.md) | 冒頭の証拠区分で、「実測結果」「再現」の節を `verified`、「未検証の仮説」を `hypothesis` とする（本文の語の転記）。文書は秒数について「性能の主張ではない」と注記 | ONTAP 9.19.1P2（2026-10-07）、再現は ONTAP 9.19.1P3（2026-10-11、2026-10-12）、ap-northeast-1、Single-AZ（1,024 GiB / 128 MBps）、NTFS ボリューム、AWS Managed AD に参加した SVM。クライアントは Windows Server 2022 の EC2 と Amazon Linux 2023 の EC2 の 2 台（SMB と NFSv4.1）。世代は文書に記載がない | — | 文書の「未測定の範囲」の節は、security style `unix` と `mixed`、ONTAP の他の版、Multi-AZ・複数 SVM、cifs の他の mount options・Kerberos・NFS 4.1 以外、請求額。ロックを取らずに書く側が止められるかは測っていない |

**デュアルプロトコルの 2 行について。** NFS と SMB を同一ボリュームで同時に走らせたときの**スループット・IOPS の実測**は、**2026-10-13 時点で、次の範囲では見つけられませんでした。** これは探索の記述であって、存在しないという断定ではありません。見た範囲は、(1) このリポジトリで「デュアルプロトコル」の文字列を検索（このマップを書く前の状態で 0 件）、(2) S3-Burst-on-ONTAP-Files の `docs/ja/verification/README.md` の全文、(3) 同リポジトリの `perf-matrix-results.md` の見出し一覧、(4) FSx-for-ONTAP-App-Modernization-Patterns の `docs/ja/stage-1-multiprotocol.md` です。(1) の検索は日本語の文字列だけで、「dual-protocol」のような英語の語では検索していません。(4) は、NFS と SMB から同一 NTFS ボリュームへ入る 2 台のクライアントの、ロックの衝突と、書き込みから読めるまでの時間を観測した文書で、スループットと IOPS は扱っていません。文書自身が、秒数は性能の主張ではないと注記しています。この記録は上の 2 行目に載せました。これ以外の文書は読んでいません。`perf-matrix-results.md` の「指定値との差」節にある「NFS と SMB を同時に走らせると同じポートを取り合う」は、同時利用の測定結果ではなく測定順序の注意です。

### FlexCache・階層化

| プロトコル・論点 | 結果文書 | Spoke 側の段階表記 | 測定環境の要約 | Hub の転記ノート | 文書自身が挙げる未測定 |
|---|---|---|---|---|---|
| FlexCache（Origin → Cache の可視性） | [flexcache-s3ap-visibility.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/flexcache-s3ap-visibility.md) | 検証済み（FSx for ONTAP どうし。索引の段階列） | `SINGLE_AZ_1`、128 MBps、2 ファイルシステム（Origin 役と Cache 役）、VPC ピアリング、Internet origin、Cache と同じサブネットの EC2、NFSv3、2026-08-09 | [書き込みが見えるまでの時間](../domains/data-utilization/notes/how-long-until-a-write-is-visible.md) | 遠隔拠点・高レイテンシ環境、スループット（この文書の範囲外。同じ Spoke の別文書が読み取りを測っている — 次の行）、オンプレミス ONTAP を Cache にした場合、SMB / NTFS、Cache を増やした場合、`actimeo=0` 以外のマウントオプション |
| FlexCache の読み取りスループット（同一 AZ、リージョン間、Origin と Cache の指定値の組み合わせ） | [throughput-iops-concurrency.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/throughput-iops-concurrency.md)（「FlexCache 経由の読み取り」「リージョンを跨いだ FlexCache（読み手が遠い場合）」と、非圧縮で測り直した「C」の節ほか） | 検証済み（索引の段階列。文書単位）。ただし「FlexCache 経由の読み取り」の節は、冒頭の数値と結論を取り下げると本文が書き、非圧縮での測り直しの節に置き換えている（本文）。リージョン間の経路は「読み取りスループットのみ検証済み」（検証状況） | 同一 AZ・同一 VPC、FSx for ONTAP どうし、専用ファイルシステム 2 つ、両側 128 MBps、cluster peering と SVM peering。非圧縮での測り直しは 2026-09-02。リージョン間は Origin が ap-northeast-1、Cache が ap-northeast-3、両側 128 MBps、リージョン間 VPC ピアリング、読み手は大阪の `c5n.2xlarge`、2026-09-01。Origin だけ 2,048 MBps に上げた測定は 2026-09-18。条件の詳細は各節の冒頭を参照 | — | WAN を挟む構成。同一 AZ の測定は WAN を挟んだ構成の予測ではなく、リージョン間は都市間の代役で長距離 WAN や実際のオンプレミス回線とは違うと本文が書く |
| FabricPool / 階層化の読み取り（SSD 対キャパシティプール階層、直接 ALL 対 NONE からの切り替え） | [s3ap-throughput-benchmark.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/blob/main/docs/ja/s3ap-throughput-benchmark.md) ／ [s3files-throughput-measured.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/s3files-throughput-measured.md)（S-5 の節） | 前者はサイジングの参考値で、節によっては主張ごとの根拠区分（`verified` / `documented` / `hypothesis` / `open`）を持つ（本文）。後者は文書単位で検証済み（1 台 1 回のサンプル）（索引の段階列）。後者の S-5 の節自身は「1 回の測定である」と書き、cold の窓の読み取りが capacity pool に届いていなかったと書く（本文） | 前者は `SINGLE_AZ_1`、128 MBps、SSD 1,024 GiB、Internet origin、VPC 外の Lambda、2026-10-11。後者の S-5 は `SINGLE_AZ_1`、128 MBps、Internet origin、AWS 外のローカル端末、2026-10-10 | — | 前者は第 2 世代 / Multi-AZ、同時実行数 2 以上、AUTO ポリシー、請求の比較。後者の S-5 は VPC 内からの階層差、並列度を上げた階層差、capacity pool から実際に読んだ遅れ |

### 指定値・バースト・他サービスとの対照

| プロトコル・論点 | 結果文書 | Spoke 側の段階表記 | 測定環境の要約 | Hub の転記ノート | 文書自身が挙げる未測定 |
|---|---|---|---|---|---|
| 指定値・バースト・ベースライン | [throughput-capacity-burst-and-baseline.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/throughput-capacity-burst-and-baseline.md) | 検証済み（索引の段階列） | 第 2 世代 `SINGLE_AZ_2`、1,536 MBps と 6,144 MBps（6,144 MBps は別のファイルシステム）、同一サブネット、`c5n.9xlarge`、2026-09-10 | [スループットは 1 つの設定値では決まらない](../domains/performance/notes/where-throughput-is-determined-and-shared.md) | 3,072 MBps の中間点、バースト持続時間の再現性、1,536 MBps 未満（384 / 768）、64 KiB 逐次やランダムでのバースト枠の効き方 |
| Amazon EFS との対照 | [perf-matrix-results.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md) | 検証済み（索引の段階列。文書単位） | Amazon EFS Elastic（Provisioned の対照の節あり）、東京、`c5n.9xlarge`、2026-09-05 | [単一接続で測った値はストレージの性能ではない](../domains/performance/notes/a-single-connection-measures-the-client.md) | Provisioned でヘルパーの効果が出なかった機構（モードまでは切り分け済み）、`nconnect=16` は I/O が停滞して測定不能 |
| Amazon S3 との対照（S3 API 経路のスループット / IOPS / 並列度） | [throughput-iops-concurrency.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/throughput-iops-concurrency.md) | 検証済み（索引の段階列） | S3 Access Points（`SINGLE_AZ_1`、VPC origin）と Amazon S3 のバケットを同一クライアント・同一コードで測定。`c5n.9xlarge`、2026-09-01。台数試験は `c5n.2xlarge`。S3 API の経路は S3 Files を通らない（文書の記述） | — | Amazon S3 の台数を増やして比例しなくなる点。ホストごとに別プレフィックスを使ったため、プレフィックスあたりのリクエスト上限は未試験 |
| Amazon S3 Files との対照（反映時間とファイルシステム性能） | [s3files-vs-flexcache.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/s3files-vs-flexcache.md) ／ [s3files-throughput-measured.md](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/s3files-throughput-measured.md) | 前者は検証済み（両側とも実測）。後者は検証済み（1 台 1 回のサンプル）（いずれも索引の段階列。後者は文書単位） | 前者は FSx for ONTAP 側が `SINGLE_AZ_1`、128 MBps、2 ファイルシステム、VPC ピアリング、2026-08-09。S3 Files 側は `t3.small`、同一 VPC、NFSv4.2、2026-09-01。後者は S3 Files 単体（ONTAP は関与しない）、専用 VPC、`c5n.9xlarge`（台数試験は `c5n.2xlarge`）、2026-10-10。後者の S-5 の節だけは FSx for ONTAP の S3 Access Points（上の階層化の行） | — | 後者の「読み取れないこと」の表は、warm と cold の差（S-3 は一部実施で、clean な比較は方法が無効なため取れておらず、不成立のまま）、複数マウント・複数ホストの集約（複数ホストは S-4 が 1〜8 台まで実施済みで、9 台以上は未測定）、別インスタンス型での頭打ち、`nodirects3read` を付けた場合 |

### アプリ層のベンチマーク

| プロトコル・論点 | 結果文書 | Spoke 側の段階表記 | 測定環境の要約 | Hub の転記ノート | 文書自身が挙げる未測定 |
|---|---|---|---|---|---|
| サイバーレジリエンス（スキャン遅延・パイプライン・隔離応答） | [benchmarks/README.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/benchmarks/README.md) | 段階語なし（本文）。注意書きは、特定のテスト環境で実行したものであり、本番性能の保証として読んではならないと書く | 結果の条件表なし。計測器の説明の Caveats 節は、テスト環境を single-AZ・専用スキャナで、同時に走る別の負荷はないと書く | — | 文書は挙げていない。マップ側の観察（2026-10-13）: origin/main の `benchmarks/` は `README.md` と `run_benchmark.py` だけで、結果ファイルは無い |
| RAG（Retrieve API レイテンシ、サイジング） | [baseline-estimates.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG/blob/main/benchmarks/results/baseline-estimates.md) ／ [fsxn-sizing-and-performance.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG/blob/main/docs/fsxn-sizing-and-performance.md) | 前者は `[hypothesis]`（理論的推定値、この規模では未検証の外挿と明記）、後者はステータス「ドラフト」（いずれも本文） | 前者はデモ環境（2 ドキュメント、ap-northeast-1）の測定からの外挿。後者は設計指針で、作成日は 2026-05-21（測定日ではない）。FlexCache と S3 Access Point の制約を扱う節の性能特性の小節は、ap-northeast-1、128 MB/s、`SINGLE_AZ_1` のテスト環境の参考値と注記 | — | この規模での実測（前者は未検証の外挿と明記） |

---

## 掲載範囲と、載せていない文書の種別

**この索引が載せるのは、2026-10-13 に各 Spoke の `origin/main` で読んだ文書に限ります。** 載っていないことは、存在しないことを意味しません。各 Spoke のファイル一覧（`git ls-tree`）を性能系のファイル名で絞り、性能が主題の文書を選んで読みました。数値を含む文書をすべて読んだわけではありません。

載せていない主な文書は次のとおりです。存在を一覧で確認しただけで、このマップのために内容を読んでいないものを含みます。

- S3-Burst-on-ONTAP-Files: 計画の文書（`block-protocol-matrix-plan.md`、`initial-sizing-measurement-plan.md` など）、手順の文書（`reproduction-guide.md`）、S3 Files 単体の反映の記録（`s3files-measured.md`）、機能の可否の記録（`s3ap-operations.md`、`protocol-matrix-efs-vs-ontap.md`）、`docs/ja/reference/limits/smb-multichannel-enablement.md`。入口は上の「Spoke 側の入口ページ」の 2 行
- FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns: `docs/s3ap-performance-considerations.md` と、`benchmarks/data/` の生データ
- FSx-for-ONTAP-Observability-integrations: `benchmark/s3ap-throughput/results/` の生データ
- FSx-for-ONTAP-Lakehouse-Integrations: `verification-pack/` の `athena-parquet-read`、`duckdb-local`、`opensharing-sts-vending`、および `s3ap-list-latency` の `2026-08-05` の証跡
- VMware-Migration-EC2-ONTAP: `docs/agent/cross-repo-block-performance.md`。ブロック性能の実測を S3-Burst-on-ONTAP-Files から受け取るときの約束の記録で、状態表は 2026-09-15 時点

ONTAP-Edge-to-Cloud-AI、blea-fsxn-usecase、FSx-for-ONTAP-Container-Datastore-Patterns、FSx-for-ONTAP-App-Modernization-Patterns は、ファイル名に `perf`・`benchmark`・`throughput`・`iops`・`latency` を含む文書が `origin/main` に見つかりませんでした。App-Modernization-Patterns の `stage-1-multiprotocol.md` は、ファイル名にそれらの語を含みませんが、デュアルプロトコルの行で載せました。

---

## 選び方 — 値を比べる前に揃えるべき変数

**このマップは、プロトコル間やサービス間の優劣を示しません。** 2 つの値を比べてよいのは、下の変数がすべて揃っているときだけです。揃っていない値を並べると、環境差をプロトコル差やサービス差として誤読します。各変数は、上の表のリンク先が測定条件として挙げているものです。右の列は、その変数を各 Spoke の文書がどう扱っているかです。

| 揃えるべき変数 | Spoke 文書での扱い |
|---|---|
| 世代（第 1 世代 / 第 2 世代） | 指定値・バースト・ベースラインの記録は、第 2 世代 Single-AZ の AWS 公開仕様の表を引いています。同じ使用率の指標でも分母が世代で違い（第 1 世代は指定値、第 2 世代はベースライン）、どちらの世代の値も分母を確かめずに並べられないと、同記録は注記しています |
| 配置（Single-AZ / Multi-AZ、HA ペア数） | S3 Access Points の読み取りレイテンシの記録は、Multi-AZ では結果が異なりうるとして個別の検証を求めています。S3-Burst-on-ONTAP-Files のブロックの記録は、データ LIF が別ノードの別ポートに載っていることを、ファイル側の横並び表に足さない理由の 1 つに挙げています |
| 指定スループット | 第 2 世代の公開仕様の表では、ディスクのバースト枠と NVMe リードキャッシュの有無が指定値で変わります（指定値・バースト・ベースラインの記録） |
| クライアント種別とネットワーク | S3-Burst-on-ONTAP-Files の記録は、帯域が保証値の `c5n.9xlarge` か「最大」表記のインスタンスかを条件に書いています。S3 Access Points の読み取りレイテンシの記録は、ローカル端末の帯域がクライアント側で頭打ちになった条件を書いています |
| 測定器 | S3-Burst-on-ONTAP-Files の記録は、VDBENCH 直接と `auto_vdbench` の系列の行を混ぜて並べないこと、`dd` の値を VDBENCH の表と並べないことを注記しています |
| 並列度（スレッド数） | S3-Burst-on-ONTAP-Files の横並び表は 512 スレッドに固定しています。S3 Access Points の書き込みの記録は、並列度 1 / 8 / 32 を別々の点として測っています |
| 接続数（`nconnect` / SMB チャネル / iSCSI セッション） | S3-Burst-on-ONTAP-Files の記録は、指定値ではなく確立された本数（`ss` で数えた接続、数えた TCP の本数）を条件にしています |
| origin 種別（Internet / VPC） | S3 Access Points の書き込みの記録は、値が Internet origin のものであり、VPC origin は同じ手順で測っていないと書いています |
| オブジェクトサイズ | S3 API の記録は 1 MiB と 8 MiB で表を分けています。S3 Access Points の読み取りレイテンシの記録は、1 MB と 202 バイトの小ファイルを別の節にしています |

これらの変数が実測の値をどう動かしたかは、測定条件とともに [単一接続で測った値はストレージの性能ではない](../domains/performance/notes/a-single-connection-measures-the-client.md) にあります。

---

## 関連ドキュメント

- [Domain — 性能](../domains/performance/README.md) — 性能ドメインのハブ
- [ファイルプロトコル横断リソースマップ](file-protocol-resource-map.md) — ファイル側の一次情報の索引
- [ブロックストレージ横断リソースマップ](block-storage-resource-map.md) — ブロック側の一次情報の索引
- [プロジェクト間の引用索引](cross-repo-index.md) — Spoke の実測をどう引いているか、分担の原則
- [手元のスループット値は何を測ったのかを判定する](decision-trees/measured-throughput-triage.md) — 上限の切り分け
- [知見の分類ポリシー](../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md) | [Domain — 性能](../domains/performance/README.md)

<!-- lang-switcher:start -->
🌐 [日本語](performance-evidence-map.md) | [English](../../en/reference/performance-evidence-map.md) | [🏠 リポジトリトップ](../../../README.md)
<!-- lang-switcher:end -->
