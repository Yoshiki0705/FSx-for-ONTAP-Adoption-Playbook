# Playbook 04 — 構築 (Build)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/playbooks/04-build/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

手作業で作った環境は再現できません。IaC と自動化で、構築を検証可能・再現可能にします。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | IaC で何を管理し、何を管理しないか | [IaC の境界は API の表面で決まる](notes/what-iac-cannot-reach.md) |
| 2 | Active Directory 連携をどう自動化するか | [Active Directory 連携の自動化](notes/what-iac-cannot-reach.md#active-directory-連携の自動化) |
| 3 | シークレットをどう扱うか | [シークレットの扱い](notes/what-iac-cannot-reach.md#シークレットの扱い) |
| 4 | 構築後の検証をどう自動化するか | [構築後の検証を自動化する](notes/what-iac-cannot-reach.md#構築後の検証を自動化する) |
| 5 | 環境の複製（開発・検証）をどう作るか | [開発・検証環境の複製](notes/what-iac-cannot-reach.md#開発検証環境の複製) |

---

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`notes/`](notes/) | 知見の最小単位。1 ファイル = 1 論点。frontmatter に `evidence` 区分を持ちます |
| [`checklists/`](checklists/) | 現場で使うチェックリスト。→ [本番投入前レビュー](checklists/pre-production-review.md) |

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
🌐 [日本語](README.md) | [English](../../../en/playbooks/04-build/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
