---
title: 端末側の資格情報の置き場所 — 端末を配った瞬間に、回収できない秘密が 4 種類増える
lifecycle: [design, build, operate]
domains: [client-access, security-governance]
evidence: documented
source: https://docs.aws.amazon.com/vpn/latest/clientvpn-admin/what-is.html
lang: ja
---

# 端末側の資格情報の置き場所

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — クライアントアクセス](../README.md)

---

## 結論

**端末からアクセスさせると、秘密が端末側に残ります。** サーバー側の設定と違い、**回収も棚卸しも
こちらからはできません。**

| 何が残るか | どこに | 失効させる手段 |
|---|---|---|
| **VPN の証明書と秘密鍵** | 端末のファイル、または VPN クライアントのプロファイル | **証明書失効リストか、CA の作り直し** |
| **SMB の資格情報** | Windows の資格情報マネージャー / macOS のキーチェーン / Linux の `credentials=` ファイル | パスワードの変更 |
| **iSCSI の CHAP シークレット** | ホストの設定ファイル。**平文で残ります** | シークレットの変更 |
| **AWS の資格情報** | `~/.aws/credentials`、または IAM Identity Center の短期資格情報 | 長期キーなら無効化、短期なら**放置で失効します** |

**4 行目だけが「放置すれば安全側に倒れる」性質を持っています。** 残りの 3 つは、
**こちらが動かないと有効なままです。**

> **区分**: `documented` — 各仕組みの保管場所と失効手段は AWS / Microsoft / Apple / NetApp の
> ドキュメントに基づきます（2026-09-13 に確認）。
> **これはセキュリティやコンプライアンスの判断ではありません。** 設計上どこに秘密が置かれるかの整理です。
> 監査要件への適合は、組織の基準で別に判断してください。

---

## 相互認証の Client VPN で起きること

**証明書認証には、ユーザーもグループもありません。** 認可の主体は証明書そのものです。

| 帰結 | 実務上の意味 |
|---|---|
| **クライアント鍵を持っていることが認可** | 鍵が渡った先は、認可された CIDR に届きます |
| 端末ごとに証明書を作らないと区別できない | 1 枚を共有すると、失効は全員に効きます |
| 失効リストを運用しないと個別に止められない | **端末を紛失したとき、止める手段が CA の作り直しだけになります** |
| `.ovpn` プロファイルは鍵を埋め込む形が一般的 | **プロファイルのファイル 1 つが完全な資格情報です** |

**`examples/client-access/` は失効リストを作りません。** 使い捨ての検証を前提にしているためで、
**そのことを README に書いてあります。** 常用するなら、証明書認証ではなく IdP 認証（SAML）を
検討する判断になります。

---

## 端末ごとの保管場所

| 端末 | SMB | iSCSI | AWS |
|---|---|---|---|
| **Windows** | 資格情報マネージャー。`net use /savecred` で永続化されます | iSCSI イニシエータの設定に CHAP シークレット | `%USERPROFILE%\.aws\credentials` |
| **WSL2 の Linux** | `credentials=` ファイル。**モードを 600 にしないと同一ホストの他ユーザーが読めます** | 同上（カーネルが対応する場合） | `~/.aws/credentials`。**Windows 側とは別のファイルです** |
| **Mac** | キーチェーン | **該当しません**（イニシエータが同梱されていません） | `~/.aws/credentials` |

**WSL2 の行の 3 列目が見落とされます。** Windows 側と WSL2 側で `~/.aws/credentials` が別に存在し、
**片方だけを更新した状態が普通に起きます。** どちらで `aws` を叩いたかで結果が変わります。

---

## 減らすための 3 つの手立て

**「秘密を安全に置く」より「置かない」ほうが確実です。**

| 手立て | 何が消えるか | 引き換えに負うもの |
|---|---|---|
| **AWS の長期アクセスキーを使わず、IAM Identity Center の短期資格情報にする** | 端末に残る AWS の秘密が期限付きになります | サインインの手順が増えます |
| **端末に何も入れないブラウザ経路にする** | VPN 証明書・SMB 資格情報・CHAP シークレットのすべて | **ブロックとファイルのマウントが選択肢から消えます** |
| **VDI 経由にする** | 端末側の 4 種類すべて。秘密は VDI の中に移ります | VDI の費用と運用。**秘密は消えず、場所が変わります** |

**2 行目と 3 行目の違いを混ぜないでください。** ブラウザ経路は秘密を減らし、VDI は移動させます。
経路の比較は [端末の到達経路の比較](../../../reference/comparison/endpoint-reachability-options.md) にあります。

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | Windows: `cmdkey /list` | 資格情報マネージャーに残っている SMB の資格情報 |
| 2 | macOS: `security find-internet-password -s <smb-host>` | キーチェーンに残っている資格情報 |
| 3 | Linux / WSL2: `ls -l /etc/*cred* ~/.smbcredentials 2>/dev/null` と `stat -c '%a %n'` でモードを見る | `credentials=` ファイルの存在と、**600 になっているか** |
| 4 | 各端末で `ls -l ~/.aws/credentials` と `aws sts get-caller-identity` | AWS の秘密の所在。**WSL2 と Windows で別々に実行してください** |
| 5 | `aws ec2 describe-client-vpn-endpoints --query 'ClientVpnEndpoints[].[ClientVpnEndpointId,ClientConnectOptions,AuthenticationOptions]'` | 認証方式。証明書認証なら失効リストの運用が必要です |
| 6 | 端末で VPN プロファイルのファイルを探し、`<key>` ブロックが含まれるか見る | **プロファイル 1 つが資格情報かどうか** |

**手順 6 が最も効きます。** 鍵が埋め込まれたプロファイルは、コピーされた時点で複製された資格情報です。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| VPN の証明書はサーバー側で管理されている | **秘密鍵は端末にあります。** こちらから消せません |
| 証明書認証はユーザー単位で止められる | **失効リストを運用していない場合、止める手段は CA の作り直しです** |
| CHAP シークレットはハッシュで保存される | **ホストの設定ファイルに平文で残ります** |
| `~/.aws/credentials` は端末に 1 つ | **WSL2 と Windows では別のファイルです。** 片方だけ更新された状態が普通に起きます |
| VDI にすれば秘密が消える | **VDI の中に移るだけです。** 消えるのは端末側の保管です |
| ブラウザ経路も結局セッションが残る | セッションは期限付きです。**証明書と CHAP シークレットは期限がありません** |
| 端末を回収すれば済む | **コピーされていないことは証明できません。** 失効の手段を先に決めてください |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| Client VPN が OpenVPN ベースのクライアントで、相互認証では証明書が認証手段になること | [AWS: What is AWS Client VPN?](https://docs.aws.amazon.com/vpn/latest/clientvpn-admin/what-is.html) |
| Client VPN の DNS の動作、およびエンドポイント設定の項目 | [AWS: Client VPN endpoint での DNS の動作](https://aws.amazon.com/premiumsupport/knowledge-center/client-vpn-how-dns-works-with-endpoint/) |
| Windows の iSCSI で CHAP を含む設定がホスト側のレジストリと設定に置かれること、NetApp Windows Host Utilities が推奨値を設定すること | [AWS: Provisioning iSCSI for Windows](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-windows.html) |
| igroup の外側に CHAP と portset があること | [igroup の外側にある 2 つの制御](../../block-storage/notes/igroups-are-not-the-only-access-control.md)（`verified`） |
| S3 Access Point 経由の認可が 2 層で、ファイルシステム側のユーザーが最終的に効くこと | [S3 Access Point の権限設計](../../security-governance/notes/access-point-authorization-layers.md)（`verified`） |

---

## 関連ドキュメント

- [Domain — クライアントアクセス](../README.md) — このモジュールのハブ
- [端末の到達経路の比較](../../../reference/comparison/endpoint-reachability-options.md) — 経路ごとに端末へ入るもの
- [端末から S3 Access Points に届く条件](what-an-endpoint-needs-to-reach-s3-access-points.md) — AWS 資格情報の使われ方
- [SMB の落ち方は端末ごとに違う](how-smb-fails-per-endpoint.md) — 資格情報の失敗がどう見えるか
- [igroup の外側にある 2 つの制御](../../block-storage/notes/igroups-are-not-the-only-access-control.md) — CHAP の位置
- [保存時の暗号化は自動、転送時は既定で無効](../../security-governance/notes/what-the-platform-gives-and-what-stays-yours.md) — プラットフォームが担う範囲
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — クライアントアクセス](../README.md)
