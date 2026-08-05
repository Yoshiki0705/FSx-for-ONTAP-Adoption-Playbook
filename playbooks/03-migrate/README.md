# Playbook 03 — 移行 (Migrate)

[English](README.en.md) | [🏠 リポジトリトップ](../../README.md)

---

移行方式の選択、切り替え手順、そして戻す手順を扱います。ロールバック手順のない移行計画は計画として未完成です。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | どの移行方式を選ぶか（SnapMirror / DataSync / ホスト側コピー） | _未追加_ |
| 2 | ACL を保持したまま移行するには何が必要か | _未追加_ |
| 3 | 初期同期と差分同期をどう計画するか | _未追加_ |
| 4 | 切り替え時のダウンタイムをどう最小化するか | _未追加_ |
| 5 | どの時点まで、どうやって戻せるか | _未追加_ |

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

判断基準の詳細は [知見の分類ポリシー](../../docs/ja/evidence-policy.md) を参照してください。

---

## 関連

- [テーマ軸で探す](../../docs/ja/navigation.md#テーマ軸--domains)
- [移行方式 決定ツリー](../../reference/decision-trees/migration-method.md)
- [ナビゲーションガイド](../../docs/ja/navigation.md)
- [用語集](../../reference/glossary/)

---

[English](README.en.md) | [🏠 リポジトリトップ](../../README.md)
