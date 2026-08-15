---
title: エンドユーザーがデータに届く経路は 4 つあり、ブラウザだけがマネージドで埋まっていない
lifecycle: [assess, design, build]
domains: [data-utilization, multiprotocol-identity, security-governance]
evidence: documented
source: https://docs.aws.amazon.com/transfer/latest/userguide/fsx-s3-access-points.html
lang: ja
---

# エンドユーザーがデータに届く経路は 4 つある

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 02 — 設計](../README.md)

---

## 結論

**「誰がどうやってこのファイルを開くのか」を、ボリューム設計と同時に決めてください。**
FSx for ONTAP のデータにエンドユーザーが届く経路は 4 つあり、**マネージドサービスで埋まっている
範囲がそれぞれ違います。** ブラウザ経路だけは、FSx for ONTAP を対象にした場合に自分で組む必要が
あります。

| 経路 | エンドユーザーが使うもの | AWS 側の実体 | 組む量 |
|---|---|---|---|
| **ファイル共有プロトコル** | エクスプローラ / Finder / マウント | FSx for ONTAP の NFS / SMB。追加サービス不要 | なし |
| **ファイル転送プロトコル** | SFTP / FTPS / FTP クライアント | AWS Transfer Family + FSx for ONTAP S3 AP | 設定のみ |
| **ブラウザ（FSx for ONTAP 上のデータ）** | Web ブラウザ | **該当するマネージドサービスは確認できていません** | 自分で組む |
| **ブラウザ（S3 バケット上のデータ）** | Web ブラウザ | Transfer Family web apps（IAM Identity Center + S3 Access Grants） | 設定のみ |

> **区分**: `documented` — 各経路の対応範囲と制約を AWS 公式ドキュメントで確認しています。3 行目は
> 「無い」ことの出典を示せないため、**確認できていない**という書き方にしています。後述の
> [この記述の限界](#この記述の限界) を必ず読んでください。

---

## なぜ設計時に決める必要があるか

アクセス経路は、後から足せる場合と、ボリューム設計まで戻る場合に分かれます。

| 経路を後から足すとき | 戻る範囲 |
|---|---|
| NFS / SMB を追加する | SVM の設定。ボリュームはそのまま |
| Transfer Family を追加する | S3 AP の新規作成。**S3 AP には ONTAP 9.17.1 以降が必要** |
| ブラウザ経路を追加する | 認可の設計。ID ドメインが 1 つ増えます（後述） |

S3 AP を前提にする経路（Transfer Family とブラウザ経路の両方）は、**ONTAP のバージョン要件が
先に来ます。** 9.17.1 より前のファイルシステムでは、まずアップグレードの検討からになります。
詳細は [FSx for ONTAP S3 AP は「S3 として使える」わけではない](../../../domains/data-utilization/notes/s3-access-point-constraints.md) を参照してください。

---

## Transfer Family 経路の制約 — クライアント側で先に詰まる

SFTP / FTPS / FTP は「設定だけ」で済みますが、**ファイル操作の一部が使えません。** これは
サーバー側の設定ミスではなく、S3 AP 経由であることに由来します。

| 制約 | 影響 |
|---|---|
| **rename が非対応** | 一時ファイル名でアップロードして最後に rename するクライアントは失敗します |
| **append が非対応** | 追記でログを送る運用は成立しません |
| **アップロードは 5 GB まで** | これを超えるファイルは別経路が必要です |
| ファイルシステムと S3 AP が同一リージョン・同一アカウント | クロスアカウント構成は取れません |

**最も踏みやすいのは rename です。** WinSCP は既定で一時ファイル名を使うため、AWS のドキュメントは
`Disable transfer resume/transfer to temporary filename` を無効化する手順を明記しています。
つまり **「クライアントの既定設定では失敗する」** 経路であり、利用者への案内文にこの 1 行を
含めるかどうかで問い合わせ件数が変わります。

> S3 AP を直接 S3 API で叩く場合のサイズ上限は、Transfer Family 経由の 5 GB とは別の値です
> （単一 `PutObject` と `UploadPart` が 5 GiB、オブジェクト全体が 50 GiB）。**同じ「5」でも
> 単位と適用箇所が違うため、どちらの経路の話かを常に明示してください。**
> 出典: [S3 AP の制約ノート](../../../domains/data-utilization/notes/s3-access-point-constraints.md)

なお、**S3 AP を後から付けても NFS / SMB の挙動は変わりません。** 既存のファイルプロトコル
アクセスはそのまま動き続けます。段階的に経路を増やせるのは、この性質があるためです。

---

## ブラウザ経路 — 認可が 3 層になる

ブラウザから見せる場合、認可の層が 1 つ増えます。ここを設計時に写像として決めていないと、
「特定のユーザーだけ見えない」を後から追いかけることになります。

| 層 | 何が主体か | 決めること |
|---|---|---|
| 1. ブラウザの認証 | IdP のユーザー / グループ（IAM Identity Center、Cognito、SAML / OIDC） | 誰がサインインできるか |
| 2. AWS の認可 | IAM ロールと S3 AP ポリシー | どの AP のどのプレフィックスに触れるか |
| 3. ファイルシステムの認可 | **S3 AP に紐づくファイルシステムユーザー** | ボリューム上で実際に何ができるか |

3 層目が見落とされがちです。AWS のドキュメントは、S3 AP が **dual-layer authorization model**
（AWS の IAM 権限とファイルシステムレベルの権限の組み合わせ）であり、**両方が許可しないと
リクエストは成功しない**と明記しています。さらに、アクセスポイントに紐づくファイルシステム
ユーザーが読み取り専用なら、**IAM 側が書き込みを許可していても書き込みは拒否されます。**

ここから 2 つの設計上の含意が出ます。

1. **IdP のグループを増やしても、3 層目は増えません。** 1 つの S3 AP は 1 つのファイルシステム
   ユーザー identity に紐づきます。ユーザーごとに実効権限を変えたいなら、AP を分ける設計か、
   アプリケーション層で絞る設計かを選ぶことになります。
2. **読み取り専用を保証したいなら、3 層目で担保するのが最も硬いです。** IAM だけで担保すると、
   ポリシー変更ひとつで書き込み可能になります。

> **セキュリティに関する補足**: AD 参加済み SVM では、S3 AP 経由の**すべてのデータ操作**に
> AD ドメインコントローラへの到達性が必要です。`HeadBucket` は AD が到達不能でも成功するため、
> 疎通確認に使うと偽陽性になります。詳細は
> [AD への依存は参加時ではなく生涯続く](../../../domains/multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) を参照してください。

---

## ブラウザ経路を自分で組む場合の選択肢

FSx for ONTAP 上のデータをブラウザで見せる実装は、姉妹リポジトリに動くものがあります。

| 選択肢 | 向く状況 | 引き換えに負うもの |
|---|---|---|
| [Amplify Gen2 ポータル](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/amplify-portal) | サーバーレスで完結させたい。AI 処理や検索を同じ画面に載せたい | フロントエンドのコードを保守する |
| OSS のファイル共有製品 | 既製の UI と同期クライアントが要る | 実行基盤（EC2 / ECS）の運用が増える |
| 独自実装（CDK + 任意のフレームワーク） | 既存の社内ポータルに組み込みたい | 認証・認可を含めて全部自分で持つ |

**どれが優れているという話ではありません。** チームが既に持っているスキル、運用の好み、
コンプライアンス要件で決まります。3 者の比較と選び方は
[File Portal UI Options（姉妹リポジトリ）](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/file-portal-amplify-gen2.md)
にまとまっています。

既存の SaaS ファイル共有（Box / SharePoint / Google Drive など）を置き換える話でもありません。
併用も、NAS 側だけをブラウザに出す構成も成立します。**置き換えを前提に検討を始めると、
移行コストで止まります。**

---

## この記述の限界

- **「ブラウザ × FSx for ONTAP にマネージドサービスが無い」は、無いことの証明ではありません。**
  Transfer Family web apps は Amazon S3 バケットを対象としており、IAM Identity Center と
  S3 Access Grants に統合されています。FSx for ONTAP の S3 AP を対象にできるという記述は、
  本ノート作成時点の公式ドキュメントでは確認できませんでした。**サービスは追加されます。**
  設計を始める前に現行のドキュメントを確認してください。
- Transfer Family 経由の制約（rename / append / 5 GB）は公式ドキュメントの記述です。
  自環境での再現確認は行っていません。**採用を決める前に、実際のクライアントで 1 度試して
  ください。** 特に rename は、クライアントの既定設定に依存します。
- 4 経路の分類は、読者が選択肢を漏らさないための整理です。分類自体に出典はありません。

---

## 出典

| 内容 | 出典 |
|---|---|
| Transfer Family と FSx for ONTAP の統合、dual-layer authorization、rename / append 非対応、5 GB 上限、WinSCP の設定 | [Access your FSx for NetApp ONTAP file systems with Transfer Family](https://docs.aws.amazon.com/transfer/latest/userguide/fsx-s3-access-points.html) |
| S3 AP の認可モデルとファイルシステムユーザー identity | [Managing access point access](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html) |
| Transfer Family web apps の対象と構成 | [Transfer Family web apps](https://docs.aws.amazon.com/transfer/latest/userguide/web-app.html) |

---

## 関連

- [FSx for ONTAP S3 AP は「S3 として使える」わけではない](../../../domains/data-utilization/notes/s3-access-point-constraints.md) — S3 AP 側の前提条件
- [AD への依存は参加時ではなく生涯続く](../../../domains/multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) — 3 層目が壊れる条件
- [セキュリティスタイルが権限評価のモデルを決める](../../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) — ボリューム側の権限評価
- [デプロイタイプは一度しか決められない](deployment-type-is-decided-once.md) — 同じ設計フェーズの不可逆な判断
- [業種別リソースマップ](../../../reference/industry-resource-map.md) — 業種ごとの実装パターン

---

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook 02 — 設計](../README.md)
