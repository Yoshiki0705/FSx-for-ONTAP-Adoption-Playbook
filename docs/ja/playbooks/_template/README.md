# モジュールテンプレート / Module Template

[🏠 リポジトリトップ](../../../../README.md)

---

新しいモジュールを追加するときは、このディレクトリをコピーしてください。
`playbooks/` と `domains/` は同じ内部構造を持ちます。
ドキュメントの言語はディレクトリで表します（`docs/<lang>/…`）。`README.en.md` のようなサフィックスは使いません。

Copy this directory to add a new module. `playbooks/` and `domains/` share the same internal shape.
A document's language is its directory (`docs/<lang>/…`); there is no `README.<lang>.md` suffix.

---

## 手順 / Steps

```bash
# 1. コピー / Copy
cp -r docs/ja/playbooks/_template docs/ja/playbooks/07-my-new-phase

# 2. 言語ごとに README.md を書く（セクション構成を一致させる）
#    docs/ja/playbooks/07-my-new-phase/README.md
#    docs/en/playbooks/07-my-new-phase/README.md
#    One README.md per language directory, keeping the section structure identical

# 3. 語彙を追加 / Register the vocabulary
#    tools/validate_frontmatter.py  -> LIFECYCLE or DOMAINS
#    tools/new_note.py              -> LIFECYCLE_BY_DIR or VALID_DOMAINS

# 4. ルート README の 2 軸ナビゲーション表に追記（8 言語すべて）
#    Add a row to the two-axis navigation table in the root README (all 8 languages)

# 5. スイッチャーを生成 / Generate the language switcher
#    H1 直後と末尾に <!-- lang-switcher:start --> / <!-- lang-switcher:end --> を置いてから実行
#    Place the marker pair after the H1 and at the end of the file, then run:
make switcher-write

# 6. 検証 / Verify
make all
```

手順 3 を飛ばすと `make lint` が「未知の値」で失敗します。これは意図した動作です。
モジュール追加とフロントマターの語彙は同時に更新されるべきものです。

Skipping step 3 makes `make lint` fail with "unknown value". That is intended: a new module and
the frontmatter vocabulary should always be updated together.

---

## 構造 / Structure

| パス / Path | 内容 / Contents |
|---|---|
| `README.md` | モジュールのハブ。`docs/<lang>/` 配下に言語ごとに 1 つ。Tier 2（ja + en）/ Module hub, one per language directory. Tier 2 (ja + en) |
| `notes/` | 知見の最小単位。1 ファイル = 1 論点 / Smallest unit of knowledge. One file = one concern |
| `checklists/` | 現場で使うチェックリスト / Checklists for field use |

---

## ノートの追加 / Adding a note

```bash
make new-note MODULE=playbooks/07-my-new-phase SLUG=my-concern
```

frontmatter は `evidence: hypothesis` で生成されます。**検証してから昇格してください。**
Notes are scaffolded at `evidence: hypothesis`. **Verify before promoting.**

詳細 / Details: [知見の分類ポリシー](../../evidence-policy.md) / [Evidence Policy](../../../en/evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../README.md)
