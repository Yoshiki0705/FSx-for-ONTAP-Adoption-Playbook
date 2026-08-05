# モジュールテンプレート / Module Template

[🏠 リポジトリトップ](../../README.md)

---

新しいモジュールを追加するときは、このディレクトリをコピーしてください。
`playbooks/` と `domains/` は同じ内部構造を持ちます。

Copy this directory to add a new module. `playbooks/` and `domains/` share the same internal shape.

---

## 手順 / Steps

```bash
# 1. コピー / Copy
cp -r playbooks/_template domains/my-new-domain

# 2. README.md / README.en.md を書く（セクション構成を一致させる）
#    Write both READMEs, keeping the section structure identical

# 3. 語彙を追加 / Register the vocabulary
#    tools/validate_frontmatter.py  -> LIFECYCLE or DOMAINS
#    tools/new_note.py              -> LIFECYCLE_BY_DIR or VALID_DOMAINS

# 4. ルート README の 2 軸ナビゲーション表に追記（8 言語すべて）
#    Add a row to the two-axis navigation table in the root README (all 8 languages)

# 5. 検証 / Verify
make lint i18n-check links
```

手順 3 を飛ばすと `make lint` が「未知の値」で失敗します。これは意図した動作です。
モジュール追加とフロントマターの語彙は同時に更新されるべきものです。

Skipping step 3 makes `make lint` fail with "unknown value". That is intended: a new module and
the frontmatter vocabulary should always be updated together.

---

## 構造 / Structure

| パス / Path | 内容 / Contents |
|---|---|
| `README.md` / `README.en.md` | モジュールのハブ。Tier 2（ja + en）/ Module hub. Tier 2 (ja + en) |
| `notes/` | 知見の最小単位。1 ファイル = 1 論点 / Smallest unit of knowledge. One file = one concern |
| `checklists/` | 現場で使うチェックリスト / Checklists for field use |

---

## ノートの追加 / Adding a note

```bash
make new-note MODULE=domains/my-new-domain SLUG=my-concern
```

frontmatter は `evidence: hypothesis` で生成されます。**検証してから昇格してください。**
Notes are scaffolded at `evidence: hypothesis`. **Verify before promoting.**

詳細 / Details: [知見の分類ポリシー](../../docs/ja/evidence-policy.md) / [Evidence Policy](../../docs/en/evidence-policy.md)

---

[🏠 リポジトリトップ](../../README.md)
