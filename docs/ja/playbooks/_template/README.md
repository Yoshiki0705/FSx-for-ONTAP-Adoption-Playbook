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
| `checklists/` | 現場で使うチェックリスト。**中身ができてから作ってください。**空のディレクトリへのリンクは、読者に無い期待を持たせます / Checklists for field use. **Create this directory once a checklist exists** — a link to an empty directory promises something that is not there |

---

## ノートの追加 / Adding a note

```bash
make new-note MODULE=playbooks/07-my-new-phase SLUG=my-concern
```

frontmatter は `evidence: hypothesis` で生成されます。**検証してから昇格してください。**
Notes are scaffolded at `evidence: hypothesis`. **Verify before promoting.**

詳細 / Details: [知見の分類ポリシー](../../evidence-policy.md) / [Evidence Policy](../../../en/evidence-policy.md)

---

## モジュールの完成条件 / What makes a module done

**ノートが増えただけではモジュールは使えません。** 読者は「自分の状況がどれに当たるか」を先に決める必要があります。
**下の 4 点が揃って初めて、モジュールとして読める状態になります。**

A pile of notes is not a usable module. A reader has to work out which situation is theirs before
the notes help. **The first four are required; a module without them is a collection, not a module.**

| # | 要素 / Element | 置き場所 / Where | 必須か / Required |
|---|---|---|---|
| 1 | **入口** — 「ここから読む」。読者の状況を 3 段以内で分岐させ、2〜4 へ送る / **Entry point** routing the reader in three steps or fewer | `README.md` の冒頭 / top of `README.md` | **必須 / Required** |
| 2 | **ノート** — 1 ファイル = 1 論点 / **Notes**, one concern per file | `notes/` | **必須 / Required** |
| 3 | **決定木** — 選択肢を狭める順序。可否と粒度の判断 / **Decision tree** giving the order in which the choice narrows | `docs/ja/reference/decision-trees/` | **必須 / Required** |
| 4 | **比較** — トレードオフを対称に。「選び方」を必ず含める / **Comparison** with symmetric trade-offs and a "how to choose" section | `docs/ja/reference/comparison/` | **必須 / Required** |
| 5 | **動く例** — 最小構成を実際に流せるもの / **A runnable example** | `examples/<module>/` | 対象を絞る / Only where it pays |
| 6 | **リソースマップ** — 一次情報と公開 IaC の索引、資料間の食い違い / **Resource map** indexing primary sources and where they disagree | `docs/ja/reference/<module>-resource-map.md` | 対象を絞る / Only where it pays |

**5 と 6 を全モジュールに用意しようとすると費用と時間が合いません。** 検証環境が要る側（5）と、一次情報が散っている側（6）に絞ってください。
**足りない部分を他のプロジェクトが持っている場合は、自前で作らずに引用します。**
分担と引用の登録は [プロジェクト間の引用索引](../../reference/cross-repo-index.md) にあります。

Attempting 5 and 6 for every module does not pay for itself. Reserve them for modules that need a
test environment, and for modules whose primary sources contradict each other. **When a sibling
project already holds what is missing, cite it rather than rebuild it** — see the cross-repository
citation index above.

---

## 入口の書き方 / Writing the entry point

**入口は目次ではありません。** 「このモジュールが扱う問い」の表は目次で、入口とは別に必要です。

**入口が答えるのは 1 つだけです。読者が今持っている材料から、次に読む 1 ページを決めること。**

The entry point is not a table of contents. Its only job is to turn what the reader already has in
hand into the next single page to read.

| 読者が持っているもの / What the reader arrives with | 入口が示すこと / What the entry point resolves |
|---|---|
| 数字（遅い、高い、足りない） / A number | その数字が何を測ったのか / what that number actually measured |
| 既存の構成（今こう組んでいる） / An existing setup | 前提が崩れる条件 / the condition under which its premise breaks |
| 決めなければならない選択 / A pending decision | 先に狭まっている制約 / the constraint that has already narrowed it |

**3 行以内の表にしてください。** 長い入口は読まれません。

---

## 検証記録の形式 / Recording a verification

**数値を書くなら、条件を同じ場所に書いてください。** 条件を外した数値は設計に使えません。

`evidence: verified` のノートは frontmatter に `verified_on` と `region` を持ちます。
**それだけでは足りません。** 本文に測定条件の表を置いてください。

A `verified` note carries `verified_on` and `region` in its frontmatter. **That is not sufficient.**
Put a conditions table in the body.

| 記録する項目 / Item | なぜ / Why |
|---|---|
| 世代・デプロイタイプ / Generation and deployment type | 世代で使える機能が違います / features differ by generation |
| スループット容量・SSD 容量・プロビジョンド IOPS / Throughput capacity, SSD capacity, provisioned IOPS | どの上限に当たるかが変わります / they decide which ceiling you hit |
| ONTAP のバージョン / ONTAP version | 挙動が版で変わります / behavior changes between releases |
| クライアントの型と、その帯域が保証値かバーストか / Client instance type, and whether its network figure is guaranteed or burst | バースト型では測定対象がクライアントになります / on a burst type you are measuring the client |
| 並列度・ブロックサイズ・接続数 / Concurrency, block size, connection count | 1 接続と複数接続で別の上限を測ります / one connection and many measure different ceilings |
| キャッシュの状態 / Cache state | 同一構成で結果が振れます / the same setup returns different numbers |
| 測定環境が現存するか / Whether the environment still exists | 撤去済みなら再現手順の所在を書きます / if torn down, say where the rebuild steps are |

**測定環境を撤去したら、そのことを書いてください。** 「再現できます」と「再現手順があります」は別です。

**予算の目安**: 1 モジュールあたり実測に $50 以内、実測項目 4 件以上。

**超えた場合に選ぶ区分は、測れなかった理由では決まりません。出どころで決まります。**
一次資料があれば `documented`、測定環境を持つ別プロジェクトの記録があれば `documented`（条件の転記が必要）、
どちらも無く推論で書くなら **`hypothesis`** です。**「予算を超えたから `documented`」は誤りです。**
区分の選び方は [知見の分類ポリシー](../../evidence-policy.md) にあります。

**Budget**: up to $50 of measurement per module, four measured items or more. **When that is
exceeded, the tier is decided by provenance, not by why the measurement did not happen** — vendor
documentation or a sibling project's record makes it `documented`, and reasoning with neither behind
it is `hypothesis`. See the evidence policy.

---

[🏠 リポジトリトップ](../../../../README.md)
