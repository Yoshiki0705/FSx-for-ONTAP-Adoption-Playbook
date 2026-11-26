---
title: S3 Access Points で書いた 64 B の新しいファイルは NFS と SMB で数 ms 以内に読めたが、NFSv3 の新しいディレクトリでは約 28 秒、UNIX ボリュームの SMB の上書きは 120 秒たっても見えなかった
lifecycle: [design, build]
domains: [data-utilization, performance]
evidence: verified
verified_on: 2026-11-25
region: ap-northeast-1
ontap_version: 9.19.1P4D1
lang: ja
---

# S3 Access Points で書いたファイルを NFS と SMB で読むまで、プロトコルの版とクライアントのキャッシュでどれだけ違うか

## 結論

Amazon FSx for NetApp ONTAP（以下 FSx for ONTAP）のボリュームに付けた S3 Access Points へ `PutObject` したファイルを、同じボリュームを NFS でマウントした EC2 から読むまでの時間を、NFSv3、NFSv4.1、NFSv4.2 で測りました（2026-11-25、ap-northeast-1、各 30 回）。続けて、同じ EC2 から SMB 3.1.1 と SMB 3.0 でも測りました（セキュリティスタイルが UNIX のボリューム（UNIX ボリューム）と NTFS のボリューム（NTFS ボリューム）の 2 つ、各 30 回）。

- NFS では、新しいキーへ書いたファイルは、NFSv3、v4.1、v4.2 のどの版でも `stat` が p50 0.4〜3.3 ms で成功し、64 B の中身は p50 1.5〜8.0 ms で読めました。版による差より、属性キャッシュの設定（既定か `actimeo=0` か）による差の方が大きく出ました
- 既存のファイルを `PutObject` で上書きすると、NFS で新しい中身が読めるまで p50 1.5〜4.6 ms でした。既定の属性キャッシュのままでも、ファイルを開き直す読み方なら遅れは見えませんでした
- NFS では、例外が 2 件ありました。1 件目は、NFSv3 の既定のマウントで、まだ存在しないディレクトリの下に最初に書いたファイルが、見えるまで 27.9 秒かかったことです（64 B、30 回のうち 1 回）。2 件目は、所有者とモードを確かめた別の測定で、NFSv3 の既定のマウントから見たとき、別の新しいディレクトリへ最初に書いた 1 件が 30 秒以内に見えなかったことです。どちらも、存在しないという結果がクライアントのキャッシュに残ったためと考えています（未確認）
- NFS では、`PutObject` で書いたファイルの所有者は、NFSv3 で `0:1`、NFSv4.1 / 4.2 で `0:2`、モードはどれも `644` でした
- SMB でも、新しいキーへ書いたファイルは `stat` が p50 0.4〜0.8 ms で成功し、64 B の中身は p50 1.1〜1.5 ms で読めました。SMB の版（3.1.1 と 3.0）、`cache=strict`（既定）と `cache=none`（データをキャッシュしない）、UNIX ボリュームと NTFS ボリューム、64 B と 8 MiB を組み合わせた 16 通りで、タイムアウトは 0 件でした。8 MiB の中身は p50 36.4〜38.6 ms で、8 MiB の読み出しを含みます
- SMB での上書きは、NTFS ボリュームでは、既定のマウントでも 10 ms ごとの確認で p50 2.0〜2.4 ms で新しい中身が読めました
- SMB での上書きは、UNIX ボリュームでは、Linux の cifs の既定（`closetimeo=1`。`closetimeo` は、アプリがファイルを閉じてから、サーバー側のハンドルを実際に閉じるまでの待ち時間の秒数）のままだと、同じファイルを 10 ms ごとに開き直しても、120 秒以内に新しい中身が見えませんでした（4 通りのマウントすべてで 30 回中 30 回）。2 秒ごとの確認なら最初の確認（上書きの 2 秒後）で見え、`closetimeo=0` なら p50 2.3〜3.1 ms でした。原因が、クライアント側かサーバー側かは特定していません
- SMB では、NFSv3 で 27.9 秒かかった「新しいディレクトリの最初のファイル」が、`stat` で 1.0〜1.2 ms、中身で 1.8〜1.9 ms で見えました（各 1 回の観測）
- UNIX ボリュームのファイルを SMB で見ると、所有者とモードは `0:0 755` で、サーバーの値（`0:1 644`）ではなくマウントの既定値でした
- このノートの SMB の測定は、AD に参加せず SVM 上のローカルユーザーで認証する workgroup の SMB サーバーと、Linux の cifs クライアントだけです。Windows のクライアントと AD に参加した SVM は測っていません

## 背景

S3 API でデータを受け入れ、ファイルとして読む構成には、正本の置き場所で 2 つの形があります。正本を FSx for ONTAP のボリュームに置いて S3 Access Points で受け入れる形と、正本を S3 のバケットに置いて Amazon S3 Files で読む形です。後者の反映の待ちは、S3 API で書いてファイルで読めるまで p50 約 1.5 秒でした（[S3 Files の実測記録](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/s3files-measured.md)、2026-09-01）。前者は NFSv3 で p50 3 ms の記録があり（[書いた側と読む側が違うと、見えるまでの時間は方向で決まる](how-long-until-a-write-is-visible.md)）、NFSv4.x は測っていませんでした。SMB は、別の環境（AD に参加した SVM の FlexCache ボリューム）の記録が 1 件あるだけでした。このノートは、前者を NFS の版ごと、SMB の版ごとに測った記録です。S3 Files のユーザーガイドが対応する版として挙げているのは NFSv4.1 と 4.2 で、SMB は挙がっていません（[Unsupported features, limits, and quotas](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-files-quotas.html)）。

![図 1: A は、EC2 が S3 Access Points 経由で FSx for ONTAP のボリュームへ PutObject で書き、同じ EC2 が NFS（v3、v4.1、v4.2）か SMB（3.0、3.1.1）で、新しいファイルを数 ms 以内に読む。B は、EC2 が汎用バケットへ書き、S3 Files が約 1.5 秒（p50）で取り込み、同じ EC2 が NFSv4.1 / 4.2 で読む](../../../../_assets/images/s3api-in-files-out-ab.svg)

図の内容は本文の表と同じです（[暗い背景の版](../../../../_assets/images/s3api-in-files-out-ab-dark.svg)、[English](../../../../_assets/images/s3api-in-files-out-ab-en.svg)）。

## 詳細

「新しいキーへの `PutObject` から NFS で読めるまで」から「所有者とモード（NFS）」までの 3 節は NFS の測定です。SMB の測定は、その後の 4 節（「新しいキーへの `PutObject` から SMB で読めるまで」から「新しいディレクトリの最初のファイル（SMB）」まで）にあります。

### 新しいキーへの `PutObject` から NFS で読めるまで

時間は `PutObject` の API 完了から、同じ EC2 で読めるまでです。10 ms ごとに確かめました。「stat」は `stat` が成功するまで、「中身」は読んだファイルの SHA-256 が書いた内容と一致するまでです。p50 と p90 は、30 回の値を小さい順に並べて 15 番目と 27 番目です。30 秒のタイムアウトは 0 件でした。単位は ms です。

| NFS | 属性キャッシュ | 大きさ | stat（p50 / p90 / max） | 中身（p50 / p90 / max） |
|---|---|---|---|---|
| v3 | 既定 | 64 B | 0.4 / 0.4 / 27,915.4 | 1.6 / 1.7 / 27,916.4 |
| v3 | 既定 | 8 MiB | 0.4 / 0.5 / 1.1 | 38.1 / 39.5 / 46.9 |
| v3 | `actimeo=0` | 64 B | 3.2 / 3.4 / 4.6 | 7.5 / 7.9 / 18.2 |
| v3 | `actimeo=0` | 8 MiB | 3.2 / 3.5 / 4.2 | 44.3 / 45.4 / 46.7 |
| v4.1 | 既定 | 64 B | 0.4 / 0.5 / 2.7 | 1.5 / 1.6 / 4.2 |
| v4.1 | 既定 | 8 MiB | 0.4 / 0.5 / 1.0 | 38.0 / 38.8 / 41.5 |
| v4.1 | `actimeo=0` | 64 B | 3.2 / 3.3 / 3.4 | 7.8 / 8.1 / 8.2 |
| v4.1 | `actimeo=0` | 8 MiB | 3.2 / 3.4 / 3.9 | 43.8 / 44.7 / 44.9 |
| v4.2 | 既定 | 64 B | 0.4 / 0.5 / 2.9 | 1.5 / 1.6 / 4.0 |
| v4.2 | 既定 | 8 MiB | 0.4 / 0.5 / 0.9 | 37.9 / 38.8 / 40.1 |
| v4.2 | `actimeo=0` | 64 B | 3.3 / 3.4 / 3.5 | 8.0 / 8.2 / 8.5 |
| v4.2 | `actimeo=0` | 8 MiB | 3.3 / 3.4 / 3.7 | 44.5 / 45.2 / 46.5 |

- 8 MiB の「中身」の約 38〜45 ms は、8 MiB を NFS で読み出して SHA-256 を計算する時間を含みます
- `actimeo=0` では、`stat` のたびにクライアントがサーバーへ属性を問い合わせるので、`stat` が約 3 ms 長くなったと考えています（未確認）
- NFSv3 の既定のマウントで 64 B の max が 27,915.4 ms になったのは、30 回のうち最初の 1 回だけです。この 1 回は、まだ存在しないディレクトリ（`s3fa/`）の下に書いた最初のファイルでした。2 回目以降の p90 は 0.4 ms です。2 件目の例外は、別のディレクトリに最初に書いたファイルで、30 秒以内に見えず、下の所有者の表で値を取れませんでした

### 既存のファイルの上書き（NFS）

既存のファイル（64 B）を NFS で一度読んでから、同じキーへ `PutObject` で上書きし、NFS で新しい中身が読めるまでを測りました（各 30 回、タイムアウト 120 秒、タイムアウトは 0 件）。単位は ms です。

| マウント | p50 / p90 / max |
|---|---|
| v3 既定 | 1.7 / 2.0 / 2.0 |
| v3 `actimeo=0` | 4.3 / 4.5 / 5.6 |
| v4.1 既定 | 1.5 / 1.6 / 1.7 |
| v4.1 `actimeo=0` | 4.5 / 4.6 / 5.2 |
| v4.2 既定 | 1.5 / 1.6 / 1.6 |
| v4.2 `actimeo=0` | 4.6 / 5.0 / 6.3 |

測定は読むたびにファイルを開き直しました。NFS のクライアントは、ファイルを開くときに属性を確かめ直す（close-to-open の一貫性）ので、既定の属性キャッシュでも遅れが見えなかったと考えています（未確認）。ファイルを開いたまま読み続けるアプリでは、属性キャッシュの期間だけ古い中身が見える可能性があります。測っていません。

### 所有者とモード（NFS）

| マウント | `stat` の所有者とモード |
|---|---|
| v3 既定 | 30 秒以内に見えず取得できなかった。別の 1 件で `0:1 644` |
| v3 `actimeo=0` | `0:1 644` |
| v4.1 既定、v4.1 `actimeo=0` | `0:2 644` |
| v4.2 既定、v4.2 `actimeo=0` | `0:2 644` |

Access Point のファイルシステムユーザーは UNIX の root です。所有者は root（0）になり、グループは NFSv3 で 1、NFSv4.x で 2 に見えました。同じファイルを版の違うマウントで見たときにグループが違う理由は、確かめていません。グループで権限を分けるアプリは、版ごとに実機で確かめてください。

### 新しいキーへの `PutObject` から SMB で読めるまで

測り方は NFS と同じです。時間は `PutObject` の API 完了から、同じ EC2 で読めるまでで、10 ms ごとに確かめました。タイムアウトは 30 秒です。SMB 3.1.1 と SMB 3.0、`cache=strict`（既定）と `cache=none` の 4 通りのマウントを、UNIX ボリュームと NTFS ボリュームの 2 つに付けました（2 つのボリューム × 4 通りのマウント × 64 B と 8 MiB の 2 つの大きさで計 16 通り、各 30 回）。表の範囲は、4 通りのマウントの最小〜最大です。単位は ms で、タイムアウトはどの行も 0 件でした。

| ボリューム | 大きさ | stat（p50 / p90 / max、ms） | 中身（p50 / p90 / max、ms） |
|---|---|---|---|
| UNIX | 64 B | 0.4〜0.5 / 1.1〜1.4 / 1.2〜7.0 | 1.1〜1.4 / 1.8〜2.3 / 1.9〜8.8 |
| UNIX | 8 MiB | 0.5〜0.8 / 1.1〜1.5 / 1.1〜2.9 | 36.4〜38.6 / 37.6〜39.8 / 38.3〜40.5 |
| NTFS | 64 B | 0.5 / 1.1〜1.4 / 1.3〜1.6 | 1.2〜1.5 / 1.8〜2.4 / 2.0〜2.7 |
| NTFS | 8 MiB | 0.5〜0.8 / 1.1〜1.5 / 1.2〜7.9 | 36.6〜38.5 / 37.8〜39.8 / 40.2〜46.4 |

- 8 MiB の「中身」の p50 の 36.4〜38.6 ms は、8 MiB を SMB で読み出して SHA-256 を計算する時間を含みます
- SMB の版、`cache=` の値、ボリュームのスタイルによる差は、ms の範囲でした。NFS の既定のマウントの値（`stat` p50 0.4 ms、64 B の中身 p50 1.5〜1.6 ms）と同じ桁です
- AD に参加した SVM の記録が、別に 2 件あります。S3-Burst-on-ONTAP-Files の[全方向の可視性比較](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/cross-protocol-directions.md)にある測定です
  - 2026-08-09（UTC）: `PutObject` から、元のボリュームを NFSv3（`actimeo=0`）で直接読むまでが p50 3 ms でした
  - 2026-08-10（UTC）: AD に参加した SVM（AWS Managed Microsoft AD）の FlexCache ボリューム（別のボリュームのデータをキャッシュとして持つボリューム）を通して、`PutObject` から SMB（3.0、`cache=none`）で読めるまでが p50 7 ms、p90 8 ms、max 9 ms（30 回）でした。並行して測った NFS（`actimeo=0`）は p50 7 ms でした
  - このノートの測定は AD に参加した SVM を使っていません。S3-Burst の 2 件は AD に参加した SVM での測定で、1 件目は元のボリュームを NFSv3 で直接読み、2 件目は FlexCache ボリュームを通して SMB で読んでいます。環境と測り方が違うので、値は比べません

### SMB での既存のファイルの上書き

既存のファイル（64 B）を SMB で一度読んでから、同じキーへ `PutObject` で上書きし、新しい中身が読めるまでを測りました（各 30 回、タイムアウト 120 秒）。読むたびにファイルを開き直しました。4 通りのマウント（SMB 3.1.1 / 3.0 × `cache=strict` / `none`）の結果は、どれも同じ傾向だったので、範囲で示します。

| ボリューム | マウントと確認の間隔 | p50 | max | タイムアウト（30 回中） |
|---|---|---|---|---|
| NTFS | 既定（`closetimeo=1`）、10 ms | 2.0〜2.4 ms | 3.5〜6.7 ms | 0 |
| NTFS | `closetimeo=0`、10 ms | 2.2〜3.3 ms | 10.1〜14.9 ms | 0 |
| UNIX | 既定（`closetimeo=1`）、10 ms | 取得できず | 取得できず | 30（4 通りとも） |
| UNIX | 既定（`closetimeo=1`）、2 秒 | 2.00 秒（最初の確認） | 2.00〜2.01 秒 | 0 |
| UNIX | `closetimeo=0`、10 ms | 2.3〜3.1 ms | 7.2〜11.0 ms | 0 |

- UNIX ボリュームの既定のマウントで、同じファイルを 10 ms ごとに開き直し続けると、120 秒たっても新しい中身が見えませんでした。`cache=none` のマウントは I/O エラー（EIO、errno 5。Linux のシステムコールが返すエラー）を返し、`cache=strict` のマウントは古い中身を返しました
- 2 秒ごとの確認では、最初の確認（上書きの 2 秒後）で新しい中身が読めました。表の p50 の 2.00 秒は、確認の間隔と同じ値です。間隔を 2 秒にした測定でしか見えていないので、新しい中身がいつから読めたかは、2 秒より細かくは分かりません
- `closetimeo=0` にすると、10 ms ごとの確認でも読めました。既定の `closetimeo=1` では、アプリがファイルを閉じても、cifs はサーバー側のハンドルを 1 秒間閉じません。1 秒より短い間隔で開き直し続けると、cifs が閉じていないそのハンドルを使い続け、その結果、上書き前の中身（`cache=strict`）か I/O エラー（`cache=none`）が返ると考えています。これはクライアント側の仮説で、サーバー側の要因は切り分けていません。カーネルのコードや trace は見ていないので、機構は未確認です
- NTFS ボリュームで同じ現象が出なかった理由は、確かめていません。ボリュームのスタイルで、上書きの扱い（ファイルの置き換えか、その場の更新か）が違う可能性を考えていますが、未確認です
- 原因が、クライアント側かサーバー側かは特定していません。FSx for ONTAP の制約と示す測定も、ありません。Windows のクライアントと AD に参加した SVM は測っていません

### SMB で見える所有者とモード（UNIX と NTFS のボリューム）

`PutObject` で書いたファイルを、SMB（3.1.1 と 3.0 で同じ）で見た値です。

| ボリューム | SMB の `stat -c '%u:%g %a'` | NFSv3 | ONTAP から見た値 |
|---|---|---|---|
| UNIX（ファイルシステムユーザーは UNIX の root） | `0:0 755` | `0:1 644` | ユーザー 0、グループ 1、モード 644 |
| NTFS（ファイルシステムユーザーは Windows のローカルユーザー） | `0:0 755` | EC2 の root で `stat` すると Permission denied | 所有者は Access Point に指定した Windows ユーザー。継承された ACE（ACL の 1 行）が 1 本（Everyone、フルコントロール） |

- UNIX ボリュームで SMB が示す `0:0 755` は、サーバーの値ではなく、マウントの既定値（`uid=0`、`gid=0`、`file_mode=0755`、`nounix`）です。ONTAP と NFSv3 は `0:1 644` でした
- NTFS ボリュームの所有者は、ONTAP REST で Access Point の Windows ユーザーでした。Linux の `getcifsacl`（cifs-utils の、ACL を表示するコマンド）は、DACL（アクセスを許可する相手と権限の一覧。ここでは Everyone、継承、フルコントロール）を示しましたが、所有者とグループは、解釈できない SID（Windows のユーザーやグループの識別子）として表示しました。この表示は解釈できていません
- NTFS ボリュームを NFSv3 でマウントして EC2 の root で読むと、Permission denied でした。UNIX のユーザーを Windows のユーザーへ対応づける向き（`unix-win`）のネームマッピングを作っていないためと考えていますが、作った場合は測っていません
- UNIX ボリュームを SMB で読むためのネームマッピング（ONTAP で、あるプロトコルのユーザーを別のプロトコルのユーザーへ対応づける規則。ここでは `win-unix` の向きで、Windows ユーザーを UNIX の root へ対応づけた）は 1 件作りました

### 新しいディレクトリの最初のファイル（SMB）

S3 API だけで作ったプレフィックスの下に、最初のファイル（64 B）を書き、SMB 3.1.1（`cache=strict`）で読むまでを、ボリュームごとに 1 回測りました。

| ボリューム | stat | 中身 |
|---|---|---|
| UNIX | 1.2 ms | 1.9 ms |
| NTFS | 1.0 ms | 1.8 ms |

NFSv3 の既定のマウントで 27.9 秒かかった型は、SMB では出ませんでした。各 1 回の観測なので、再現は確かめていません。

### 設計への含意

| 気にすること | 対処 |
|---|---|
| 新しいディレクトリへ S3 API で書き始めた直後に、ファイルが見えない | 読む側のマウントの属性キャッシュが、存在しないという結果を持っている可能性があります。ディレクトリを先に作っておくか、読む側で `actimeo=0` や `lookupcache=positive` を検討します（`lookupcache` は測っていません） |
| 上書きを確実に読みたい | NFS では、ファイルを開き直して読みます。開いたまま読み続ける場合は、属性キャッシュの期間を短くします（SMB は次の行） |
| `actimeo=0` の費用 | `stat` が約 3 ms 長くなり、サーバーへの問い合わせが増えます。全部のマウントに付けず、反映を待つ必要のある読み手だけに付けます |
| UNIX ボリュームを Linux の cifs で読み、上書きを短い間隔の開き直しで待つ | 既定のマウントでは見えませんでした。確認の間隔を 2 秒にするか、`closetimeo=0` を付けると読めました（測った間隔は 10 ms と 2 秒だけで、`closetimeo=0` の副作用は測っていません）。NTFS ボリュームでは既定のマウントで読めました |
| SMB で読む側が、所有者やモードで権限を判断する | UNIX ボリュームでは、Linux の cifs が示す値はマウントの既定値です。サーバーの値は ONTAP か NFS で確かめます |
| SMB の認証 | workgroup の SMB サーバーは NTLM だけで、Kerberos を使えません（[ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/smb-server-workgroup-setup.html)） |
| Windows のクライアント | Linux の cifs の結果を Windows に当てはめないでください |

> **区分**: 時間と所有者は、下の環境で 2026-11-25 に測った値です。性能の測定ではなく、本番の値を保証するものではありません。

## 検証環境

| 項目 | 値 |
|---|---|
| ONTAP バージョン | 9.19.1P4D1 |
| リージョン | ap-northeast-1 |
| 構成 | FSx for ONTAP 第 1 世代 `SINGLE_AZ_1`、128 MBps。NFS の測定は UNIX ボリューム、SMB の測定は UNIX ボリュームと NTFS ボリュームの 2 つ（下の行）。どれにも S3 Access Points を付けた。ネットワークオリジンはインターネット。ファイルシステムユーザーは、UNIX ボリュームでは UNIX の root、NTFS ボリュームでは SMB サーバーのローカルの Windows ユーザー。SVM の NFS は v3、v4.0、v4.1、v4.2 が有効 |
| クライアント | EC2（ap-northeast-1a）、Amazon Linux 2023、カーネル 6.18.62、nfs-utils 2.5.4、boto3 1.40.31。`PutObject` と NFS の読み取りは同じ EC2 で、同じ時計を使った |
| マウント（NFS） | NFSv3、NFSv4.1、NFSv4.2 を、既定のオプションと `actimeo=0` の 6 通り。共通の実効値は `rsize=65536,wsize=65536,hard,proto=tcp,timeo=600,retrans=2,sec=sys` |
| SMB サーバー | 同じ SVM に、AD に参加しない workgroup の SMB サーバー（ONTAP の CIFS サーバー）を作成。今回の測定用に作ったローカルユーザー 1 つ。共有の ACL は既定（Everyone、フルコントロール）。UNIX ボリュームには、このユーザーを UNIX の root へ対応づけるネームマッピングを 1 件作成 |
| NTFS ボリューム（SMB の測定用） | NTFS セキュリティスタイル、1 GiB。S3 Access Points を付け、ファイルシステムユーザーは WINDOWS タイプで、上のローカルユーザー。ネットワークオリジンはインターネット |
| SMB クライアント | 同じ EC2。Linux の cifs（カーネル 6.18.62）、cifs-utils 7.7-145。`PutObject`（boto3 1.40.31）と SMB の読み取りは同じ EC2 で、NFS と同じ時計を使った |
| マウント（SMB） | `vers=3.1.1` と `vers=3.0`、`cache=strict`（既定）と `cache=none` の 4 通りを、2 つのボリュームに付けた。実効値は `actimeo=1,closetimeo=1,rsize=1048576,wsize=1048576,soft,nounix,serverino,mapposix,uid=0,gid=0,file_mode=0755,dir_mode=0755`。cifs の既定は、`cache=none` でも `actimeo=1`、`closetimeo=1` のままだった。上書きの切り分けには、`closetimeo=0` を足したマウントを使った |
| 測定の条件（SMB） | 新しいキーは 10 ms ごとの確認、タイムアウト 30 秒、各 30 回。上書きは 10 ms または 2 秒ごとの確認、タイムアウト 120 秒、各 30 回 |
| 検証日 | 2026-11-25 |

> **注意**: 上記はこの環境での実測であり、一般的なサービス上限や本番環境での再現を
> 保証するものではありません。

## 自環境での確認手順

手順 5〜8 の前提として、`<Access Point のエイリアス>` を付けた UNIX ボリュームに対して、次の 4 つを作っておきます。

- workgroup の SMB サーバーとローカルユーザー: 同じ SVM に作ります（[Setting up an SMB server in a workgroup](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/smb-server-workgroup-setup.html)、[Creating a local user account on the SMB server](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/smb-workgroup-create-local-accounts.html)）。このユーザーの名前とパスワードは、`username=`、`password=` の 2 行で資格情報ファイルに書きます
- 共有: そのボリュームのパスを、ONTAP の [`vserver cifs share create`](https://docs.netapp.com/us-en/ontap-cli/vserver-cifs-share-create.html) で共有にします
- ネームマッピング: ローカルユーザーを UNIX の root へ対応づけます（[`vserver name-mapping create`](https://docs.netapp.com/us-en/ontap-cli/vserver-name-mapping-create.html) の `-direction win-unix`）。Access Point のファイルシステムユーザーは UNIX の root にします（[Creating access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-access-points.html)）
- 中身の違うローカルファイル 2 つ: `c-old.bin` は上書き前、`c-new.bin` は上書き後の中身です。たとえば `head -c 64 /dev/urandom > c-old.bin` で作ります

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 読む側のマウントで `grep <マウントポイント> /proc/mounts` を見る | NFS の版と、属性キャッシュの実効値 |
| 2 | `aws s3api put-object --bucket <Access Point のエイリアス> --key new-dir/a.bin --body a.bin` の後、NFS のマウントで `stat new-dir/a.bin` を繰り返す | 新しいディレクトリの下に書いたファイルが見えるまでの時間 |
| 3 | 同じキーへ別の中身で `put-object` し、NFS で `sha256sum` を繰り返す | 上書きが見えるまでの時間 |
| 4 | SMB のマウントで `grep <マウントポイント> /proc/mounts` を見る | SMB の版、`cache=`、`actimeo`、`closetimeo` の実効値 |
| 5 | `sudo mkdir -p /mnt/smb /mnt/smb-c0` でマウントポイントを作り（`/mnt/smb-c0` は手順 8 の `closetimeo=0` のマウント用）、UNIX ボリュームを `sudo mount -t cifs //<SMB サーバー>/<共有名> /mnt/smb -o credentials=<資格情報ファイル>,vers=3.1.1,cache=strict` でマウントする | Linux の cifs の既定のマウント |
| 6 | `aws s3api put-object --bucket <Access Point のエイリアス> --key check/c.bin --body c-old.bin` で書き、`stat /mnt/smb/check/c.bin` が成功するまで待ってから、`sha256sum /mnt/smb/check/c.bin` で一度読む | 上書き前の中身を SMB で読んだ状態 |
| 7 | 同じキーへ `c-new.bin` を `put-object` で上書きし、`sha256sum /mnt/smb/check/c.bin` を 10 ms ごとに、`c-new.bin` のハッシュと一致するまで、120 秒を上限に繰り返す | 既定のマウントで上書きが見えるか（この測定では 120 秒たっても見えなかった） |
| 8 | 手順 6 から繰り返す。1 回目は `-o closetimeo=0` を足したマウントを別のマウントポイント（`/mnt/smb-c0`）に付け、手順 6 と 7 の `/mnt/smb` を `/mnt/smb-c0` に替える。2 回目は既定のマウントのまま確認の間隔を 2 秒にする | 見えるようになるか（この測定では、どちらも読めた） |

適用手順の全体像は [本番に取り入れる前の確認](../../../evidence-policy.md#本番に取り入れる前の確認) を参照してください。

## よくある誤解

| 誤解 | 実際 |
|---|---|
| NFSv4.x にすると、S3 API で書いたファイルが早く見える | 版による差は小さく、属性キャッシュの設定の方が大きく効きました（既定で stat p50 0.4 ms、`actimeo=0` で 3.2〜3.3 ms） |
| 既定の属性キャッシュでは、上書きが数十秒見えない | ファイルを開き直す読み方では、既定でも p50 1.5〜1.7 ms で新しい中身が読めました |
| S3 API で書いたファイルは、すぐに必ず見える | 存在しないディレクトリの下に書いた最初のファイルは、NFSv3 の既定のマウントで約 28 秒見えないことがありました。SMB では、各 1 回の観測で、`stat` が 1.0〜1.2 ms、中身が 1.8〜1.9 ms でした |
| SMB で読むと、NFS より反映が遅い | 新しいキーでは、`stat` が p50 0.4〜0.8 ms で、NFS の既定のマウントと同じ桁でした。UNIX ボリュームの上書きは、Linux の cifs の既定のマウントでは 120 秒以内に見えませんでした（下の行） |
| SMB の上書きが見えないのは、FSx for ONTAP の制約だ | FSx for ONTAP の制約と示す測定は、ありません。UNIX ボリュームの Linux の cifs の既定のマウントで観測した現象で、`closetimeo=0` か 2 秒ごとの確認では読めました。NTFS ボリュームでは既定のマウントで読めました |
| UNIX ボリュームを SMB で見た所有者とモードは、サーバーの値だ | Linux の cifs が示した `0:0 755` は、マウントの既定値でした。サーバーの値は `0:1 644` でした |

## 関連ドキュメント

- [書いた側と読む側が違うと、見えるまでの時間は方向で決まる](how-long-until-a-write-is-visible.md)
- [S3 Files のバケットと FSx for ONTAP のボリュームをサーバー側コピーでつなぐ](s3-files-and-access-points-bridged-by-copy.md)
- [FSx for ONTAP S3 Access Points は S3 として使えるか](s3-access-point-constraints.md)
