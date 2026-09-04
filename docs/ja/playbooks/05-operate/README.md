# Playbook 05 — 運用 (Operate)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/playbooks/05-operate/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

監視・容量管理・障害対応・変更管理を扱います。「動いている」ことの確認と「壊れたときにどうするか」の両方が必要です。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | 何を監視し、どこに閾値を置くか | [監視は平均値で失敗する](notes/monitoring-fails-on-averages.md) |
| 2 | 容量の枯渇をどう予兆検知するか | [SSD 利用率の帯域と各点で変わること](notes/monitoring-fails-on-averages.md#ssd-利用率の帯域と各点で変わること) |
| 3 | 性能劣化の切り分け手順はどうなるか | [切り分け順](notes/monitoring-fails-on-averages.md#性能劣化の切り分け順) |
| 4 | ONTAP のバージョン更新をどう扱うか | [メンテナンスは 14 日を超えて延期できない](notes/maintenance-cannot-be-deferred.md) |
| 5 | インシデント時の初動をどう定義するか | [インシデント時の初動](notes/maintenance-cannot-be-deferred.md#インシデント時の初動) |
| 6 | 管理者アカウントで認証できなくなったとき何を疑うか | [fsxadmin はロックされる。REST では原因が判別できない](notes/admin-account-lockout-and-recovery.md) |
| 7 | 稼働中の SVM が SMB を提供できなくなったとき何を見るか | [SMB を提供できない SVM がある](../../domains/multiprotocol-identity/notes/smb-service-lost-on-cifs-server-delete.md) |
| 8 | 監査を有効化したまま運用すると可用性に何が起きるか | [監査宛先の枯渇はアクセスを止める](../../domains/security-governance/notes/audit-log-space-and-client-access.md) |
| 9 | ローカルユーザーの棚卸しをどう回すか | [最終ログオン属性は無い。監査ログから起こすしかない](../../domains/multiprotocol-identity/notes/local-user-inventory-without-last-logon.md) |

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

- [テーマ軸で探す](../../navigation.md#テーマ軸--domains)
- [移行方式 決定ツリー](../../reference/decision-trees/migration-method.md)
- [ナビゲーションガイド](../../navigation.md)
- [用語集](../../reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/playbooks/05-operate/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
