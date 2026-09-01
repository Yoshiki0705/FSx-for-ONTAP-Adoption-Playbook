---
title: SMB ログオン監査 — 4624 は記録される。ただし数えられるのはセッションであってログイン操作ではない
lifecycle: [design, build, operate]
domains: [security-governance, multiprotocol-identity]
evidence: verified
verified_on: 2026-09-01
ontap_version: 9.18.1P3D1
region: ap-northeast-1
lang: ja
---

# SMB ログオン監査 — 4624 は記録される。ただし数えられるのはセッションであってログイン操作ではない

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — セキュリティ・ガバナンス](../README.md)

---

## 結論

**`cifs-logon-logoff` を有効にすると、SMB ログオン成功 4624 とログオン失敗 4625 が EVTX に記録されます。** AD 参加 SVM でも、ワークグループ SVM のローカルユーザーでも記録されました。

**AWS のドキュメントの SMB イベント表には、この行がありません。** 表に載っているのはファイルアクセス系だけです。ただし**同じページの本文は `cifs-logon-logoff` を既定カテゴリとして説明しています。** 表だけを読むと、実現できる要件を実現不可能と判断します。

そして **4624 は「ログイン操作の回数」ではありません。** SMB セッションの確立ごとに 1 件です。実測では、Windows から同じ共有を `net use` / `net use /delete` で 3 回繰り返しても **4624 は 1 件**でした。`net use /delete` は共有のマッピング解除であってセッション終了ではなく、Windows は認証済みセッションを保持し続けます。

| イベント | 記録 | 単位 |
|---|---|---|
| 4624（ログオン成功） | **される** | SMB セッションの確立 |
| 4625（ログオン失敗） | **される** | 認証試行 |
| 4634（ログオフ） | **される。ただし条件付き** | クライアントが正規のログオフを送った場合のみ |

**4634 をセッション終了の信号として使えません。** 通信断でも、管理者による強制切断でも記録されませんでした。

> **Evidence**: `verified`（2026-09-01、`ap-northeast-1`、ONTAP `9.18.1P3D1`）。
> 2 つのファイルシステム上の 2 つの SVM で測定しました。1 つは AD 参加 SVM に作ったローカルユーザーを
> Linux の `smbclient` から、もう 1 つは**ワークグループ構成の SVM**（`Authentication Style: workgroup`）の
> ローカルユーザーを **Windows Server の `net use`** から使っています。ログは `vserver audit rotate-log`
> で確定させたうえで ONTAP REST のファイル API で回収し、`python-evtx` でパースしました。
> **実 IP・実アカウント ID・実ファイルシステム ID はプレースホルダに置き換えています。**

---

## ドキュメント間の記載差

| 出典 | Logon / Logoff の記載 |
|---|---|
| AWS: [Auditing file access](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-access-auditing.html) の SMB イベント表 | **なし**。560/4656、563/4659、564/4660、567/4663、4664、9999、9998 のみ |
| 同じページの本文 | **あり**。既定カテゴリにファイルアクセス、CIFS ログオン / ログオフ、認可ポリシー変更が含まれると記載 |
| NetApp: [SMB events that ONTAP can audit](https://docs.netapp.com/us-en/ontap/nas-audit/smb-events-audit-concept.html) | **あり**。540/4624、529〜539/4625、538/4634 |

実測は NetApp 側の記載と一致しました。**AWS の表は不足しており、同一ページ内で本文と矛盾しています。**

---

## カテゴリ別の出力イベント

同一の操作列（成功ログオン、誤パスワード 1 回、ファイル作成と読み出し）を、監査カテゴリだけ変えて実行しました。SACL は両方の測定で同一です。

| `-events` の指定 | 出力された EventID |
|---|---|
| `file-ops` | `{4656, 4663}`。**ログオン系は 0 件** |
| `file-ops,cifs-logon-logoff` | `{4624, 4625, 4656, 4663}` |
| `file-ops,cifs-logon-logoff,file-share` | `{4624, 4634}` + 共有定義の変更で `{5142, 5144}` |

**`file-ops` だけでは失敗ログオンも残りません。** アカウント棚卸しやログオン監視を要件にする場合、`cifs-logon-logoff` の明示が必要です。

`-events file-ops` だけを指定しても、設定には `audit-policy-change` が自動で加わります。

```text
FsxIdEXAMPLE::> vserver audit show -vserver <svm> -instance
                    Auditing State: true
              Log Destination Path: /audit_log
     Categories of Events to Audit: file-ops, audit-policy-change
                        Log Format: evtx
```

---

## 4624 と 4625 の記録内容

ワークグループ SVM のローカルユーザーで記録された 4624 です。

```xml
<Provider Name="NetApp-Security-Auditing" Guid="{3CB2A168-FE19-4A4E-BDAD-DCF422F13473}"/>
<EventID>4624</EventID>
<EventName>Logon Attempt</EventName>
<Source>CIFS</Source>
<Result>Audit Success</Result>
<TimeCreated SystemTime="2026-09-01 05:57:51.494787+00:00"/>
<Computer>FsxIdEXAMPLE/<svm></Computer>
<EventData>
  <Data Name="IpAddress" IPVersion="4">10.0.x.x</Data>
  <Data Name="IpPort">65155</Data>
  <Data Name="TargetUserSID">S-1-5-21-…-1000</Data>
  <Data Name="TargetUserName">wgaudit</Data>
  <Data Name="TargetUserIsLocal">true</Data>
  <Data Name="TargetDomainName"><cifs-server-name></Data>
  <Data Name="AuthenticationPackageName">NTLM_V2</Data>
  <Data Name="LogonType">3</Data>
</EventData>
```

4625 は上記に加えて `Status`、`FailureReason`、`FailureReasonString`（例: パスワード誤りを示す文言）を持ち、`AuthenticationPackageName` は `NONE`、`TargetUserSID` は `S-1-0-0` になります。`TargetUserIsLocal` は付きません。

**フィールド名がカテゴリで異なります。**

| イベント種別 | ユーザー名のフィールド |
|---|---|
| ログオン系（4624 / 4625 / 4634） | `TargetUserName` |
| ファイルアクセス系（4656 / 4663） | `SubjectUserName` |
| 共有定義の変更（5142 / 5144） | `SubjectUserName` |

**片方だけで抽出すると、無言で 0 件になります。** 棚卸しのように両方を突き合わせる用途では、抽出側で明示的に分ける必要があります。

---

## 4634 が出る条件と出ない条件

同一の SVM・同一のクライアントで、セッションの終わらせ方だけを変えて 3 通り測りました。

| 終了方法 | 4634 | サーバー側のセッション |
|---|---|---|
| クライアントが正規のログオフを送る | **記録された** | 消える |
| 通信が突然切れる（クライアント側で 445 を遮断） | **記録されない** | **残る**（`Idle Time` が進み、オープンファイルも保持） |
| 管理者が `vserver cifs session close` で切る | **記録されない** | 消える |

**この 3 行が同一ファイルシステム内の比較です。** 別のファイルシステムで `smbclient` を使ったときにも 4634 は出ませんでした。当初はファイルシステム側の差を疑いましたが、上表の 2 行目でクライアント側の切断方法が原因だと切り分けられました。

記録された 4634 は 4624 と同じ `IpPort` を持つため、**同一セッションの対応付けはできます。**

```text
EventID=4624  SystemTime=… 05:57:51  IpPort=65155
EventID=4634  SystemTime=… 05:58:10  IpPort=65155
```

> **監査設計に関する補足**: セッションの継続時間、同時接続数、「現在誰が接続しているか」を
> 4634 から組み立てないでください。通信断のケースでは、サーバーにセッションが残ったまま
> ログオフイベントが出ません。**現在の接続状況は `vserver cifs session show` が正解です。**

---

## セッション単位であることの帰結

Windows から `net use` と `net use /delete` を 3 回繰り返した結果です。

| 期待 | 実測 |
|---|---|
| 4624 が 3 件 | **1 件** |
| 4634 が 3 件 | **1 件**（3 回目の解除時ではなく、後続の認証失敗がセッション再確立を強制した時点） |

`net use /delete` が解除するのは共有のマッピングで、認証済みセッションは残ります。**この性質は棚卸しの判定を両方向に歪めます。**

| 利用パターン | 4624 の増え方 | 誤判定の向き |
|---|---|---|
| 一度接続して張り続ける | **増えない** | 使っているのに「実績なし」 |
| 通信が不安定で再接続を繰り返す | 大量に増える | 利用量を過大に見せる |

**実利用の指標としては `file-ops` の 4656 / 4663 のほうが素直です。** オブジェクト単位のアクセスが `SubjectUserName` 付きで残るため、セッション再利用に影響されません。棚卸しに使うなら「4624 の最終時刻」ではなく「4624 と 4656 / 4663 の最終時刻のうち新しい方」を採ってください。

この判定設計は
[ローカルユーザーの棚卸しに使える情報は監査ログにしかない](../../multiprotocol-identity/notes/local-user-inventory-without-last-logon.md)
で扱います。

---

## file-ops に必要な SACL と、適用時の DACL 置換

**NTFS セキュリティスタイルのボリュームでは、SACL が無いとファイルアクセスイベントが 1 件も出ません。** 同一の監査設定で SACL の有無だけを変えた結果です。

| SACL | 出力 |
|---|---|
| なし | **0 件**（`4719` の監査設定変更のみ） |
| `AUDIT-Everyone-0x1f01ff-OI\|CI\|SA\|FA` | `{4656: 14, 4663: 12}` |

**「監査を有効にしたのにログが空」の最も多い原因はここです。** AWS のドキュメントには監査ポリシー設定の手順がありますが、設定しない場合にイベントが 0 件になるという因果は明示されていません。

**そして ONTAP CLI でセキュリティ記述子を適用すると、SACL だけでなく DACL も置き換わります。**

```text
FsxIdEXAMPLE::> vserver security file-directory apply -vserver <svm> -policy-name auditpol
（適用後、それまでアクセスできていたユーザーが）
NT_STATUS_ACCESS_DENIED listing \*
```

適用した記述子に許可 ACE を含めて再適用すると復旧しました。**既存共有に後から監査を足す作業は、アクセス断を伴い得ます。** 適用する記述子に既存の DACL を含めるか、Windows 側から SACL のみを追加してください。

---

## file-share カテゴリの実際の対象

**`file-share` は共有への「アクセス」ではなく、共有定義の「変更」を記録します。**

| 操作 | 記録 |
|---|---|
| 共有への接続（`net use`） | **何も出ない** |
| `vserver cifs share create` | `5142`（Share Object Added） |
| `vserver cifs share delete` | `5144`（Share Object Deleted） |

5142 は `ShareName`、`SharePath`、`ShareProperties`、`SD`（共有 ACL）と、変更した管理者の `SubjectUserName` / `SubjectIP` を持ちます。**共有定義の変更履歴には使えますが、利用者のアクセス記録には使えません。**

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `vserver audit show -instance` で `Categories of Events to Audit` を読む | `cifs-logon-logoff` が入っているか。`file-ops` だけならログオンは残りません |
| 2 | 監査を有効にしたまま SMB で 1 回ログオンし、`vserver audit rotate-log` を実行する | **ローテーションしないと書きかけのファイルを読むことになります** |
| 3 | 出力された EVTX を確認し、4624 の `TargetUserName` を見る | 期待したユーザー名が入っているか |
| 4 | **同じユーザーで 3 回ログオンし直して 4624 の件数を数える** | セッション再利用で 1 件にまとまらないか。**これが棚卸し設計の前提を決めます** |
| 5 | クライアントから正規にログオフし、4634 が出るか見る | 使っているクライアントが正規のログオフを送るか |
| 6 | NTFS ボリュームで `file-ops` を期待する場合、SACL を設定してから測る | 0 件がカテゴリ未設定なのか SACL 未設定なのかを切り分けられます |

ローテーション後のファイル名には**ローテーション時刻**が入り、`modified_time` はそれより前になります。最新の 1 ファイルだけを見ると、境界をまたいだレコードを取りこぼします。**期間で複数ファイルを回収してから数えてください。**

---

## 未確認

- **ONTAP バージョン間の差**。測定した 2 つのファイルシステムはいずれも `9.18.1P3D1` でした。別バージョンやオンプレミス ONTAP との比較はしていません
- **クライアント種別ごとの正規ログオフ送信の有無**。Windows の `net use /delete` と Linux の `smbclient` の 2 つだけを見ています。macOS やアプライアンス、各種 SMB ライブラリの挙動は測っていません
- **セッションのアイドルタイムアウトによる終了で 4634 が出るか**。観測窓を超えるため測っていません

---

## 参照した一次情報

- AWS: [Auditing file access](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-access-auditing.html)
- NetApp: [SMB events that ONTAP can audit](https://docs.netapp.com/us-en/ontap/nas-audit/smb-events-audit-concept.html)

---

## 関連

- [監査ログの空き容量不足はクライアントアクセスを止める](audit-log-space-denies-client-access.md)
- [ローカルユーザーの棚卸しに使える情報は監査ログにしかない](../../multiprotocol-identity/notes/local-user-inventory-without-last-logon.md)
- [S3 Access Point の権限設計 — 評価順序と、絞り込みを担う 2 つの層](access-point-authorization-layers.md)
