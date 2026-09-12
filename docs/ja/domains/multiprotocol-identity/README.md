# Domain — マルチプロトコル・ID (Multiprotocol & Identity)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/multiprotocol-identity/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

NFS と SMB の共存、Active Directory 連携、ID マッピングを扱います。多くの「権限がおかしい」問題は、ID マッピングの理解不足に起因します。

---

## 最初に読むもの

**手元にある材料から、次に読む 1 ページを決めます。** 下の「扱う問い」は目次で、これは入口です。

| 手元にあるもの | 最初に読むもの | そこで分かること |
|---|---|---|
| **NFS と SMB で同じデータを出したい** | [セキュリティスタイルが権限評価のモデルを決める](notes/security-style-and-permission-evaluation.md) | **先にスタイルを決めます。** 後から変えると権限評価のモデルが変わります |
| **AD 連携がこれから / すでに参加済み** | [AD への依存は参加時ではなく生涯続く](notes/ad-dependency-lasts-the-lifetime.md) | **資格情報の失効は平常時に無症状で、次のメンテナンスで顕在化します** |
| **SMB につながらない** | [SMB を提供できない SVM がある](notes/smb-service-lost-on-cifs-server-delete.md) | **原因は作成時期ではなく CIFS サーバーの削除です。** REST で作り直せば戻ります |
| **SMB で運用中のボリュームを NFS からも使いたい** | [SMB で運用中のボリュームに NFS を足すのに複製は要らない](notes/adding-a-protocol-does-not-need-a-clone.md) | **複製も SVM の移動も要りません。** 届かない原因は 4 つで、どれも複製せずに直せます |
| **NFS 側で権限を確認したい / 拒否の理由を知りたい** | [NFS 側から見える権限表現が実際の可否と一致しない](notes/nfs-side-view-does-not-explain-ntfs-denials.md) | **Deny も主体名も NFS 側には現れません。** NTFS の拒否と UNIX の許可が同一表現になった実測付き |
| **移行後も今の確認手段が使えるか知りたい** | [プロトコルを変えたあと「誰がこのファイルにアクセスできるか」をどこで確認するか](../../reference/decision-trees/verifying-permissions-after-a-protocol-change.md) | **製品名ではなく仕組みで入ります。** 手続き書に手段名が書かれていないかの確認項目付き |
| **name-mapping を作ったのにアクセスが通らない** | [NFS 側から見える権限表現が実際の可否と一致しない](notes/nfs-side-view-does-not-explain-ntfs-denials.md#name-mapping-の-replacement-でバックスラッシュが消えること) | **`DOMAIN\user` の `\` はエスケープとして消費されます。** 規則は「成功」を報告し、名前解決だけが失敗します |

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | セキュリティスタイルが権限評価をどう変えるか | [セキュリティスタイルが権限評価のモデルを決める](notes/security-style-and-permission-evaluation.md) |
| 2 | Active Directory 連携で何が前提になるか | [サービスアカウントに必要な委任権限](notes/ad-dependency-lasts-the-lifetime.md#サービスアカウントに必要な委任権限) |
| 3 | win-unix / unix-win マッピングはいつ参照されるか | [同上](notes/security-style-and-permission-evaluation.md#セキュリティスタイルと権限評価の対応) |
| 4 | 同一データを NFS と SMB で共有する条件は何か | [共有する条件は 3 層あります](notes/ad-dependency-lasts-the-lifetime.md#同一データを-nfs-と-smb-で共有する条件) |
| 5 | AD が到達不能になると何が壊れるか | [AD への依存は参加時ではなく生涯続く](notes/ad-dependency-lasts-the-lifetime.md) |
| 6 | ブラウザ経由で見せると認可の層はいくつになるか | [認可が 3 層になる](../../playbooks/02-design/notes/how-end-users-reach-the-data.md#ブラウザ経路--3-層になる認可) |
| 7 | ローカルユーザーの棚卸しを自動化できるか | [最終ログオン属性は無い。監査ログから起こすしかない](notes/local-user-inventory-without-last-logon.md) |
| 8 | CIFS サーバーは作れたのに SMB に接続できないのはなぜか | [SMB を提供できない SVM がある](notes/smb-service-lost-on-cifs-server-delete.md) |
| 9 | SMB で運用中のボリュームに NFS を足すには何が必要か | [SMB で運用中のボリュームに NFS を足すのに複製は要らない](notes/adding-a-protocol-does-not-need-a-clone.md) |
| 10 | セキュリティスタイルは後から変えられるか。変えるなら何を先に確かめるか | [セキュリティスタイルの変更経路](notes/adding-a-protocol-does-not-need-a-clone.md#セキュリティスタイルの変更経路) |
| 11 | NTFS スタイルのボリュームで、NFS 側から権限を確認できるか | **表現は読めても可否は説明できません**（[NFS 側から見える権限表現が実際の可否と一致しない](notes/nfs-side-view-does-not-explain-ntfs-denials.md)） |
| 12 | SVM ルートボリュームのセキュリティスタイルは NFS 到達性に影響するか | **します。** NTFS ルートでは NFS が名前空間を辿れません（[同ノートの再現環境](../../../../examples/multiprotocol-ad/README.md)） |
| 13 | ブロックのデータをファイルプロトコルから読めるか | **読めません。** マルチプロトコルは NFS / SMB / S3 の間で成立する性質です（[LUN の中身はファイルプロトコルに現れない](../block-storage/notes/lun-contents-do-not-reach-file-protocols.md)） |

---

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`notes/`](notes/) | 知見の最小単位。1 ファイル = 1 論点。frontmatter に `evidence` 区分を持ちます |

---

## 自環境での確認に使える最小構成

**このモジュールの中心的な問い（SMB で設定した権限が NFS からどう見えるか）を実際に動かせる最小構成が [`examples/multiprotocol-ad/`](../../../../examples/multiprotocol-ad/) にあります。**

| 何が入っているか | 何を作らないか |
|---|---|
| CloudFormation 1 本（第 1 世代 Single-AZ + AWS Managed Microsoft AD + AD 参加済み SVM 2 つ + NTFS ボリューム + **UNIX の対照ボリューム** + Windows / Linux クライアント） | SMB 共有、export policy のルール、NTFS の ACE、name-mapping、FlexClone、`volume rehost`。**いずれも Amazon FSx の API に操作が存在しません** |
| ONTAP REST のスクリプト 3 本と PowerShell 1 本 | — |

**記録は 3 点セットで揃って初めて使えます。** 設定した ACE、NFS 側の表現、実際の成否。`stat` のモード bit だけを読むと Deny ACE が存在しないように見えるので、そこが 3 点にしている理由です。

**費用は時間あたり約 $0.72、EC2 を止めても約 $0.52 です**（`ap-northeast-1`、Price List API、2026-09-11 取得）。ファイルシステムとディレクトリは停止できず、削除するまで課金されます。撤収の期日を先に決めてください。

---

## 読み方

各ノートの frontmatter にある `evidence` を必ず確認してください。

| 区分 | 意味 |
|---|---|
| `verified` | 記載環境で著者が再現済み。`verified_on` に検証日 |
| `documented` | ベンダー / AWS 公式ドキュメントに記載あり。`source` に出典 |
| `field-observation` | 現場で一度観測。再現確認は未実施。一般化しないこと |
| `hypothesis` | 未検証の推論 |

判断基準の詳細は [知見の分類ポリシー](../../evidence-policy.md) を参照してください。

---

## 関連

- [ライフサイクル軸で探す](../../navigation.md#ライフサイクル軸--playbooks)
- [比較マトリクス](../../reference/comparison/)
- [ナビゲーションガイド](../../navigation.md)
- [用語集](../../reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/multiprotocol-identity/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
