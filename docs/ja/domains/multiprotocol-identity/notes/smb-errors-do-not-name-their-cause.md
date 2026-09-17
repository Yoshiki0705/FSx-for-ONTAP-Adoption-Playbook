---
title: SMB のエラー文字列は原因を名指さない。資格情報の誤りに見えるものがアカウント不在である
lifecycle: [build, operate]
domains: [multiprotocol-identity]
evidence: documented
source: https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/limits/smb-share-and-identifier-reading.md
lang: ja
---

# SMB のエラー文字列は原因を名指さない

<!-- lang-switcher:start -->
🌐 [日本語](smb-errors-do-not-name-their-cause.md) | [English](../../../../en/domains/multiprotocol-identity/notes/smb-errors-do-not-name-their-cause.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — マルチプロトコル・ID](../README.md)

---

## 結論

**SMB クライアントが返す文字列は、原因を一意に指しません。** 3 つの汎用的なメッセージが、それぞれ別の層の欠落として現れます。

| クライアント側のエラー | 実際の原因 | 読む場所 |
|---|---|---|
| `The specified network password is not correct.` | **アカウントがドメインに存在しません。パスワードは合っています** | ディレクトリ側のアカウント一覧 |
| `The network name cannot be found.` | **共有が存在しません。** パスもアカウントも関係ありません | `GET /api/protocols/cifs/shares` の一覧 |
| `System error 53`（`net use`） | UNC のバックスラッシュが多段のシェルを通る間に壊れています | `New-SmbMapping` に置き換える（パラメータ渡しなので入れ子の引用符が要りません） |

**1 行目がいちばん危険です。** アカウント不在がパスワード誤りとして現れるので、シークレットの値を疑って時間を使うことになります。**シークレットの存在はアカウントの存在ではありません** — ディレクトリはアカウントの入れ物で、シークレットは値の入れ物です。新しく作ったディレクトリでは、シークレットが残っていてもアカウントはありません。

**区分**: `documented` — 隣のリポジトリが 2026-09-06 に 9 台すべてのマウント失敗として観測した記録の転記です。**このリポジトリでは再現していません。**

---

## SMB で到達できるのは共有だけ

**ボリュームの junction path は共有名ではありません。** NFS はエクスポートされたパスを直接マウントできますが、SMB クライアントが指定するのは共有（CIFS share）で、これは ONTAP 上の別のオブジェクトです。

| | NFS | SMB |
|---|---|---|
| クライアントが指定するもの | junction path | **共有名** |
| ボリューム作成で使えるようになるか | なります（export policy 次第） | **なりません。共有の作成が別に必要です** |
| 作る手段 | — | `vserver cifs share create`、または REST `POST /api/protocols/cifs/shares` |

**共有を作るまで、そのボリュームに SMB で到達する名前は存在しません。** 共有の `-path` はボリューム内に存在するパスでなければならないので、**junction path は共有の指す先として使うもので、共有名として使うものではありません。**

> **新しく作った共有の既定 ACL は Everyone / Full Control です。** 疎通確認には足りますが、**権限を測る目的には使えません。** 権限の挙動を確認するなら ACL を明示して記録してください。

---

## 既定で存在する共有を「共有あり」と数えないこと

CIFS サーバーを作ると管理用の共有が自動で作られます。**データ用の共有は作られません。**

| 共有 | 用途 | 使えるか |
|---|---|---|
| `ipc$` | 名前付きパイプ。ONTAP が使います | **使えません。** 設定・プロパティ・ACL を変更できず、削除も改名もできません |
| `admin$` | SVM のリモート管理 | 使えません。**ONTAP 9.8 以降は既定で作られません** |
| `c$` | SVM ルートボリュームへの管理アクセス | **推奨しません。** 下記 |

**`c$` は動きますが、測定と検証の代表性を落とします。** 既定 ACL が `BUILTIN\administrator` の Full Control で、パスは常に SVM ルートで変更できません。SVM 管理者は `c$` から junction を越えて名前空間の残りに到達できるので `\\<svm>\c$\<volume>` の形は通ります。**ただし管理者アカウントでマップすると権限評価の一部を迂回するので、マップに使ったアカウントが結果の一部になります。**

**非特権のドメインアカウントと専用の共有を使ってください。** あとから条件を説明できます。

**`$` で終わる共有は隠し共有なので、エクスプローラーには出ません。** 「一覧に出ない」を「存在しない」と読まないでください。

---

## 識別子の出どころと、導出が外れる理由

**リソース名・共有名・アカウント名・SVM 名は、権威のある API から読んでください。** 命名規約から導けそうに見えても導かないことです。**同じ環境の中で区切り文字が混在することは普通にあります** — 引用元の環境では SVM 名がハイフン区切り、ボリューム名が下線区切りで、片方から他方を導くと外れました。

| 欲しいもの | 読む API |
|---|---|
| SVM 名 | `aws fsx describe-storage-virtual-machines`（`Name`） |
| ボリュームの junction path | `aws fsx describe-volumes`（`OntapConfiguration.JunctionPath`） |
| 共有の名前とパス | ONTAP REST `GET /api/protocols/cifs/shares?fields=name,path,svm.name` |
| SMB エンドポイント | `describe-storage-virtual-machines`（`Endpoints.Smb.DNSName`）または NetBIOS 名 |

**ID があることは名前を知っていることではありません。** スタックの出力が `svm-...` の ID を返していても、そこに名前はありません。

---

## 自環境での確認手順

**マウントを試す前に、状態を読んでください。** 汎用のエラー文字列から原因を推測する代わりになります。

| # | 確認すること | 満たされない場合 |
|---|---|---|
| 1 | SVM が存在し、AD に参加していること（`Lifecycle` と NetBIOS 名を読む） | [AD への依存は参加時ではなく生涯続く](ad-dependency-lasts-the-lifetime.md) |
| 2 | **データ用の CIFS 共有が存在すること。** `c$` と `ipc$` しかない状態を「共有あり」と数えない | 共有を作成する |
| 3 | 共有の `path` が、実在するボリュームの junction path と一致すること | どちらかが誤っている |
| 4 | マップに使うドメインアカウントがディレクトリで解決できること（**シークレットの存在では代用しない**） | アカウントを作成する |
| 5 | データ LIF のサービスポリシーに `data-cifs` が含まれること | [SMB を提供できない SVM がある](smb-service-lost-on-cifs-server-delete.md) |

**4 つ揃ったことが、マウントしてよいという判断の根拠になります。** どれか 1 つでも欠けている状態でマウントを試すと、上の表の汎用エラーのどれかを読むことになります。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| `network password is not correct` はパスワードの問題 | **アカウント不在でも同じ文字列が出ます。** 先にディレクトリ側を読んでください |
| シークレットがあるならアカウントもある | **別物です。** 新しいディレクトリではシークレットだけが残ります |
| ボリュームを作れば SMB で見える | **共有の作成が別に必要です。** junction path は共有名ではありません |
| 管理用共有があるなら疎通確認に使える | `ipc$` は使えず、`c$` は権限評価の一部を迂回します |
| 共有が一覧に出ないなら存在しない | **`$` で終わる共有は隠し共有です** |
| 命名規約から SVM 名を導ける | **同一環境で区切り文字が混在します。** API から読んでください |

---

## この記録の範囲外

| 問い | 状態 |
|---|---|
| 同じエラー文字列が別の原因でも出るか | **未確認。** 観測されたのは上の 3 通りの対応だけです |
| Windows のバージョン差 | 引用元は記録していません |
| `New-SmbMapping` が `net use` より常に安定か | **バックスラッシュの多段エスケープを避けられるという理由での置き換えです。** それ以外の差は測られていません |

---

## 関連ドキュメント

- [SMB を提供できない SVM がある](smb-service-lost-on-cifs-server-delete.md) — 445 番ポートが開かない側の原因
- [AD への依存は参加時ではなく生涯続く](ad-dependency-lasts-the-lifetime.md) — アカウントとドメイン側の前提
- [NFS 側から見える権限表現が実際の可否と一致しない](nfs-side-view-does-not-explain-ntfs-denials.md) — 「成功」を報告する規則が名前解決だけ失敗する形
- [Domain — マルチプロトコル・ID](../README.md)
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — マルチプロトコル・ID](../README.md)

<!-- lang-switcher:start -->
🌐 [日本語](smb-errors-do-not-name-their-cause.md) | [English](../../../../en/domains/multiprotocol-identity/notes/smb-errors-do-not-name-their-cause.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->
