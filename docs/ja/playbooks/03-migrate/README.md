# Playbook 03 — 移行 (Migrate)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/playbooks/03-migrate/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

移行方式の選択、切り替え手順、そして戻す手順を扱います。ロールバック手順のない移行計画は計画として未完成です。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | どの移行方式を選ぶか（SnapMirror / DataSync / ホスト側コピー） | [移行方式の選択](../../reference/decision-trees/migration-method.md) |
| 2 | ACL を保持したまま移行するには何が必要か | [ACL 保持は権限の問題であってツールの問題ではない](notes/preserving-acls-during-migration.md) |
| 3 | 初期同期と差分同期をどう計画するか | [初期同期と差分同期](notes/where-the-rollback-window-closes.md#初期同期と差分同期) |
| 4 | 切り替え時のダウンタイムをどう最小化するか | [切り替えの順序](notes/where-the-rollback-window-closes.md#切り替えの順序) |
| 5 | どの時点まで、どうやって戻せるか | [切り戻せる時点はクライアントが書き始めた瞬間に閉じる](notes/where-the-rollback-window-closes.md) |
| 6 | 移行元が SaaS / クラウドストレージの場合、方式の前に何を確定させるか | [SaaS からの移行は転送方式より先に移行元の群を確定させる](notes/saas-source-migration-scoping.md) |
| 7 | AWS Transform で移行するとき、どの工程で容量がいくら要るか | [AWS Transform の Finalize は後片付けではなく、物理容量が最大になる工程](notes/atx-finalize-flexclone-capacity.md) |

---

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`notes/`](notes/) | 知見の最小単位。1 ファイル = 1 論点。frontmatter に `evidence` 区分を持ちます |
| [`checklists/`](checklists/) | 現場で使うチェックリスト。[切り替え当日のチェックリスト](checklists/cutover.md) |

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
🌐 [日本語](README.md) | [English](../../../en/playbooks/03-migrate/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
