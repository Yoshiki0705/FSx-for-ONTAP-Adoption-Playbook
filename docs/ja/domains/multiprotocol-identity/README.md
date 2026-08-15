# Domain — マルチプロトコル・ID (Multiprotocol & Identity)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/multiprotocol-identity/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

NFS と SMB の共存、Active Directory 連携、ID マッピングを扱います。多くの「権限がおかしい」問題は、ID マッピングの理解不足に起因します。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | セキュリティスタイルが権限評価をどう変えるか | [セキュリティスタイルが権限評価のモデルを決める](notes/security-style-and-permission-evaluation.md) |
| 2 | Active Directory 連携で何が前提になるか | [サービスアカウントに必要な委任権限](notes/ad-dependency-lasts-the-lifetime.md#サービスアカウントに必要な委任権限) |
| 3 | win-unix / unix-win マッピングはいつ参照されるか | [同上](notes/security-style-and-permission-evaluation.md#セキュリティスタイルと権限評価の対応) |
| 4 | 同一データを NFS と SMB で共有する条件は何か | [共有する条件は 3 層あります](notes/ad-dependency-lasts-the-lifetime.md#同一データを-nfs-と-smb-で共有する条件) |
| 5 | AD が到達不能になると何が壊れるか | [AD への依存は参加時ではなく生涯続く](notes/ad-dependency-lasts-the-lifetime.md) |
| 6 | ブラウザ経由で見せると認可の層はいくつになるか | [認可が 3 層になる](../../playbooks/02-design/notes/how-end-users-reach-the-data.md#ブラウザ経路--認可が-3-層になる) |

---

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`notes/`](notes/) | 知見の最小単位。1 ファイル = 1 論点。frontmatter に `evidence` 区分を持ちます |
| [`checklists/`](checklists/) | 現場で使うチェックリスト |

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
