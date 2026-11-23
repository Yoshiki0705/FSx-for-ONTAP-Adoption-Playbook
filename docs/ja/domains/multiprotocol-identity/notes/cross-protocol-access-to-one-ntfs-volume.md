---
title: NTFS ボリュームを SMB と NFS で同時に使うと、名前の文字、ロック、読めるまでの時間がプロトコルごとに違う
lifecycle: [design, migrate]
domains: [multiprotocol-identity]
evidence: documented
source: https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/ja/stage-1-multiprotocol.md
lang: ja
---
# NTFS ボリュームを SMB と NFS で同時に使うと、何が違うか？

名前に使える文字、ロックが他方のプロトコルの操作を止めるかどうか、他方のクライアントが読めるまでの時間が違います。Windows が読み手のときだけ約 8 秒の遅れが出ました（FSx-for-ONTAP-App-Modernization-Patterns リポジトリでの 1 回の計測）。
<!-- lang-switcher:start -->
🌐 [日本語](cross-protocol-access-to-one-ntfs-volume.md) | [English](../../../../en/domains/multiprotocol-identity/notes/cross-protocol-access-to-one-ntfs-volume.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->
## このノートで学べること

- `\` を含むファイル名が、Linux の SMB では拒否され、NFS では作成できること
- Windows の `FileShare.None` が NFS の open も拒否し、Linux の排他ロックが Windows の読み取りを止めたこと
- 保存してから他方が読めるまでの時間が、読み手が Windows のときだけ約 8 秒だったこと

## このノートが答えないこと

- 同じ値の再現性（各組 1 回の計測です）
- 約 8 秒の遅れの原因（未検証）
- ロックを取らずに書く側が止められるか
- security style が `unix` / `mixed` のボリューム、他の ONTAP の版、Multi-AZ

## 前提レベル

intermediate

## 本文

<a id="ntfs-ボリュームを-smb-と-nfs-で同時に使うと何が違うか"></a>
[🏠 リポジトリトップ](../../../../../README.md) | [Domain — マルチプロトコル・ID](../README.md)

---

### 結論

**NTFS スタイルのボリュームを SMB と NFS の両方から使うアプリは、次の 3 点をプロトコルごとに確かめてください。** どれも別リポジトリで、各組 1 回だけ計測した値です。

| 観点 | 観測 |
|---|---|
| 名前に使える文字 | `\` を含む名前は、Linux の SMB（cifs）では `errno=22` で拒否された。NFS では作成でき、`\` は名前の一部になった。Windows からは 8.3 形式の短い名前（`SEPCHE~1.TXT`）で見え、読めた |
| ロック | Windows の `FileShare.None` は、NFS からの open も拒否した（`errno=13`）。Linux の `fcntl` 排他ロックは、Windows の読み取りをロック違反として止めた。ロックを取った側が解放したあとは、他方も取得できた |
| 保存してから読めるまで | Windows が読み手のとき約 8 秒、Linux が読み手のとき約 0.1 秒だった |

> **Evidence**: `documented`。出典は FSx-for-ONTAP-App-Modernization-Patterns の [段階 1（ja）](https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/ja/stage-1-multiprotocol.md) で、出典側では `verified` です。この文書の著者がこの環境を再実行したわけではないので、`verified` には上げません。**各組 1 回の計測で、再現は確かめていません。性能の主張ではありません。**

---

### 背景

NTFS スタイルのボリュームでも、NFS クライアントはマウントして読み書きできます（[セキュリティスタイルが権限評価のモデルを決める](security-style-and-permission-evaluation.md)）。同じファイルを両方のプロトコルから開くと、ファイル名の規則、ロックの意味、変更の見え方は、クライアントの実装に依存します。ストレージ側の設定では揃いません

---

### ロックの組み合わせ

2 台のクライアントが同じファイルを同時に操作し、一方が保持している間に他方が open を試みました。2 台の同期は、検証対象のボリュームではなく別の S3 バケット経由で取りました。

| 保持側 | 保持の方法 | 保持中の競合側 | 解放後 |
|---|---|---|---|
| Windows（SMB） | `FileShare.None` | Linux の SMB は読み取りと書き込みの open が拒否（`errno=16`）。Linux の NFS も拒否（`errno=13`） | 取得できた |
| Linux（SMB） | `fcntl` の排他ロック | Windows は open に成功し、読み取りがロック違反、排他 open が共有違反 | 取得できた |
| Linux（NFS） | `fcntl` の排他ロック | 同上 | 取得できた |

測ったのは、一方がロックを取り、他方がその間に open を試みた場合だけです。ロックを取らずに書く側が止められるかは測っていません。

---

### 保存してから読めるまでの時間

読み手は 100 ms 間隔で一覧と読み取りを繰り返したので、値の分解能は約 100 ms です。

| 書き手 | 読み手 | 保存完了から読めるまで |
|---|---|---|
| Windows（SMB） | Linux（SMB） | 99 ms |
| Windows（SMB） | Linux（NFS） | 88 ms |
| Linux（SMB） | Windows（SMB） | 7,849 ms |
| Linux（NFS） | Windows（SMB） | 8,085 ms |

- 書き手が SMB でも NFS でも、Windows が読み手のときは約 8 秒でした。遅れは書き手のプロトコルではなく、読み手が Windows であることに伴って現れました。
- 出典は、同じ形が別の 3 つの run（2026-10-11 と 2026-10-12 を含む）でも現れたと書いています。
- **遅れの原因は未検証です。** 出典は、Windows の SMB クライアントがディレクトリの内容や「ファイルがない」という結果をキャッシュするためと推測していますが、クライアントの設定値は確かめていません。この文書も、この推測を `hypothesis` として扱います。
- 読者が取る行動: Windows クライアントが Linux の書いたファイルを読む処理には、読めるまでの遅れを許す待機やリトライを置く。逆向きの遅れが小さいことを根拠に、遅れのない設計にしない。ここで測った秒数は 1 つの構成での値で、他の構成の遅れを示すものではない。

---

### 検証環境

| 項目 | 値 |
|---|---|
| ONTAP バージョン | 9.19.1P2（作成時に版を指定せず、1 回の作成で得た値） |
| リージョン | ap-northeast-1 |
| 構成 | 第 1 世代 `SINGLE_AZ_1`、1,024 GiB、128 MBps。NTFS ボリューム 1 本。AWS Managed Microsoft AD（Standard）に参加した SVM |
| クライアント | Windows Server 2022（SMB 3）と Amazon Linux 2023（SMB は `cifs`・`sec=ntlmssp`、NFS は `vers=4.1`・`sec=sys`） |
| 計測日 | 2026-10-07 |
| 計測回数 | 各組 1 回 |
| 時計 | Amazon Time Sync Service に対するオフセットが Windows で 1.5〜2.1 ms、Linux で 0.01 ms 未満 |

> **注意**: 上記はこの環境での実測であり、一般的なサービス上限や本番環境での再現を保証するものではありません。

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| 同じボリュームなら、どのクライアントからも同じ名前が作れる | `\` を含む名前は NFS では作成でき、Linux の SMB では拒否されました |
| SMB のロックは NFS クライアントに関係しない | Windows の `FileShare.None` は NFS の open を拒否しました |
| 保存が済んだファイルは、すぐ他方から読める | Windows が読み手のときは約 8 秒かかりました。逆向きは約 0.1 秒でした |

---

### 関連ドキュメント

- [セキュリティスタイルが権限評価のモデルを決める](security-style-and-permission-evaluation.md)
- [NFS 側から見える権限表現が実際の可否と一致しない](nfs-side-view-does-not-explain-ntfs-denials.md)
- [性能の実測の所在地図](../../../reference/performance-evidence-map.md): 2 台のクライアントによる記録の所在
- [エビデンス方針](../../../evidence-policy.md)

## 自環境での確認手順

**確認の前に、NFS 側のマウントと 2 台のクライアントの時計の同期（Amazon Time Sync Service）を揃えてください。**

| # | 手順 | 確認できること |
|---|---|---|
| 1 | NFS のクライアントで、`\` を含む名前のファイルを専用ディレクトリの下に作る。Linux の cifs マウントでも同じ名前を作る | 名前の規則がプロトコルで違うか。作る場所は専用ディレクトリに限る |
| 2 | Windows で `FileShare.None` を指定して開いたまま、NFS のクライアントから同じファイルを open する | 排他が NFS に及ぶか |
| 3 | Linux で `fcntl` の排他ロックを取ったまま、Windows から読み取る | ロック違反になるか |
| 4 | 書き手が保存した時刻と、読み手が初めて読めた時刻を、100 ms 以下の間隔で両側から記録する | 読めるまでの遅れ。複数回測り、1 回の値で判断しない |

### 期待結果

```text
名前の規則、ロックの及ぶ範囲、読めるまでの遅れが、プロトコルの組ごとに記録される
```

この確認は検証用のボリュームで行ってください。専用ディレクトリの外にファイルを作らず、本番のボリュームには適用しないでください。

## Read next

[NFS 側から見える権限表現が実際の可否と一致しない](nfs-side-view-does-not-explain-ntfs-denials.md)
