# Domain — クライアントアクセス (Client Access)

---

手元の端末 — Windows、WSL2 の Linux、Mac — から Amazon FSx for NetApp ONTAP のデータに届くまでの知見です。
**EC2 インスタンスからのアクセスは扱いません。** 他のモジュールが既に扱っており、端末側で踏む問題とは別物です。

**このモジュールが存在する理由は 1 行で書けます。** FSx for ONTAP はパブリックインターネットからのアクセスをサポートしておらず、
ファイルシステムの ENI に付いた Elastic IP は Amazon FSx が自動的に外します。
**つまり端末からの利用は必ず到達経路の設計を伴い、「マウントコマンドを配る」では終わりません。**

---

## 最初に読むもの

**手元にある材料から、次に読む 1 ページを決めます。** 下の「扱う問い」は目次で、これは入口です。

| 手元にあるもの | 最初に読むもの | そこで分かること |
|---|---|---|
| **端末の種類が決まっている**（Windows / WSL2 / Mac のどれか） | [端末別にできることの比較](../../reference/comparison/client-endpoint-capabilities.md) | **その端末で使えるストレージ形態が先に狭まっています。** Mac にはブロックの選択肢がありません |
| **到達経路が決まっていない**（VPN も Direct Connect もまだ無い） | [端末の到達経路の比較](../../reference/comparison/endpoint-reachability-options.md) | 経路ごとの費用と、端末に何をインストールする必要があるか |
| **マウントが失敗している** | [端末からデータに届く経路の決定木](../../reference/decision-trees/client-access-route.md) | 症状から、到達経路・プロトコル・認証のどこで落ちたかの逆引き |

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | 端末を直接インターネット経由で繋げないのはなぜか | [パブリックインターネットからの経路は存在しない](notes/no-route-from-the-public-internet.md) |
| 2 | 端末の種類で使えるストレージ形態がどう変わるか | [端末の種類がプロトコルを先に狭める](notes/the-endpoint-narrows-the-protocol.md) |
| 3 | WSL2 の Linux は Windows ホストと同じ経路を使えるのか | [WSL2 のネットワーク境界](notes/wsl2-network-boundary.md) |
| 4 | 端末側に何の資格情報が残るのか | [端末側の資格情報の置き場所](notes/where-endpoint-credentials-live.md) |
| 5 | SMB マウントの失敗が端末ごとに違う症状で出るのはなぜか | [SMB の落ち方は端末ごとに違う](notes/how-smb-fails-per-endpoint.md) |
| 6 | 端末から S3 Access Points に届くには何が要るか | [端末から S3 Access Points に届く条件](notes/what-an-endpoint-needs-to-reach-s3-access-points.md) |
| 7 | ブラウザで見せる経路にはどの選択肢があるか | [エンドユーザーがデータに届く経路は 4 つある](../../playbooks/02-design/notes/how-end-users-reach-the-data.md) |

---

## 接続が検討される端末

**このモジュールが今どこまで書けているかの一覧です。** 空欄を隠さずに並べているので、
**必要な行が「未検証」や「要望受付中」であれば、それはまだ判断材料になりません。**

要望は [Knowledge request](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/new?template=knowledge-request.yml) に
`client-access` ドメインを選んで出してください。**行が動くのは要望が来たときです。**

| 端末 | ファイル (NFS / SMB) | ブロック (iSCSI) | オブジェクト (S3 Access Points) | このモジュールの扱い |
|---|---|---|---|---|
| **Windows 端末** | 標準機能 | 標準機能（iSCSI イニシエータ + MPIO） | AWS CLI / SDK | **対象** |
| **WSL2 の Linux** | ディストリビューションのクライアント | **カーネルに依存** | AWS CLI / SDK | **対象** |
| **Mac 端末** | 標準機能（Finder / `mount_smbfs` / `mount_nfs`） | **同梱されていません** | AWS CLI / SDK | **対象** |
| ネイティブ Linux 端末 | ディストリビューションのクライアント | `open-iscsi` + `multipath-tools` | AWS CLI / SDK | **未検証。** 経路は WSL2 と同じで、境界の問題だけが消えます |
| Amazon WorkSpaces / AppStream 2.0 | VDI 内から。端末側には何も入りません | VDI のイメージ次第 | VDI 内から | **未検証。** AWS に [WorkSpaces との併用手順](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-workspaces.html) があります |
| Chromebook / iPad / Android | **不可**（マウントの仕組みがありません） | **不可** | ブラウザ経由のみ | **ブラウザ経路として対象。** 実装は姉妹リポジトリを参照 |
| EC2 Mac インスタンス | 標準機能 | 同梱されていません | AWS CLI / SDK | **対象外。** AWS の macOS 手順はこちらを前提にしています（[出典](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-mac-client.html)）。Dedicated Host の費用が実機での検証と釣り合いません |
| シンクライアント（VDI 専用端末） | VDI 内から | VDI 内から | VDI 内から | **要望受付中。** WorkSpaces の行と同じ構図になる見込みですが未確認です |
| オンプレミスの Windows Server | 標準機能 | 標準機能 | AWS CLI / SDK | **要望受付中。** 端末ではなくサーバーなので、経路の設計が Site-to-Site VPN / Direct Connect に寄ります |
| Kubernetes ノード / CI ランナー | — | — | — | **対象外。** 端末ではなくワークロードです。判断は [コンテナから FSx for ONTAP をデータストアにできるか](../../reference/decision-trees/container-datastore-selection.md)、実装は [FSx-for-ONTAP-Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) を参照 |

> **オブジェクト側の補足**: この表の「オブジェクト」列は **FSx for ONTAP S3 Access Points** を指します。
> マウント系の手段（rclone、Mountpoint for Amazon S3）は端末からの選択肢として挙がりますが、
> **Mountpoint は Linux のみで、既存ファイルの更新もディレクトリ削除もできません。**
> どちらもこのモジュールでは未検証で、要望受付中です。

---

## 動く実装

| 置き場所 | 何ができるか |
|---|---|
| [`examples/client-access/`](../../../../examples/client-access/) | 端末から届く最小構成。workgroup モードの SMB と iSCSI を出す CloudFormation、AWS Client VPN を足す別テンプレート、3 端末で同じ形の JSON を吐くプローブスクリプト |
| [ファイルポータル UI (Amplify Gen2)](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/amplify-portal) | **端末に何もインストールせずに済む唯一の経路。** ブラウザだけで届くため、Chromebook や iPad が対象に入ります。引き換えに、ブロックとファイルのマウントは選択肢から消えます |

**ポータルの実装をこのリポジトリで再実装しません。** 分担の原則は [プロジェクト間の引用索引](../../reference/cross-repo-index.md) にあります。
こちらで書くのは端末側の観点だけです。

---

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`notes/`](notes/) | 知見の最小単位。1 ファイル = 1 論点。frontmatter に `evidence` 区分を持ちます |

---

## 読み方

各ノートの frontmatter にある `evidence` を必ず確認してください。

| 区分 | 意味 |
|---|---|
| `verified` | 記載環境で著者が再現済み。`verified_on` に検証日 |
| `documented` | ベンダー / AWS 公式ドキュメントに記載あり。`source` に出典 |
| `field-observation` | 現場で一度観測。再現確認は未実施。一般化しないこと |
| `hypothesis` | 未検証の推論 |

**このモジュールでは端末の実機で測った項目と、公式ドキュメントの記載だけに基づく項目が混在します。**
どの端末で測ったかは各ノートの検証環境の表に書いてあります。判断基準の詳細は
[知見の分類ポリシー](../../evidence-policy.md) を参照してください。

---

## 関連

- [ライフサイクル軸で探す](../../navigation.md#ライフサイクル軸--playbooks)
- [Domain — ブロックストレージ](../block-storage/README.md) — LUN 側の設計と、EC2 からの iSCSI の手順
- [Domain — マルチプロトコルと ID](../multiprotocol-identity/README.md) — Active Directory を挟む場合の権限評価
- [Domain — データ活用](../data-utilization/README.md) — S3 Access Points で何ができるか
- [比較マトリクス](../../reference/comparison/) — 選択肢の比較
- [用語集](../../reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/client-access/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
