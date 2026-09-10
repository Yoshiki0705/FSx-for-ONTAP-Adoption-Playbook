# Playbook 01 — 評価 (Assess)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/playbooks/01-assess/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

移行の前に、現行 NAS に何があり、何が制約になるかを把握します。ここでの見落としが、後続フェーズのやり直しコストに直結します。

---

## 最初に読むもの

**手元にある材料から、次に読む 1 ページを決めます。** 下の「扱う問い」は目次で、これは入口です。

| 手元にあるもの | 最初に読むもの | そこで分かること |
|---|---|---|
| **移行元の数字**（容量、ファイル数） | [容量が余っていても書けなくなる](notes/counting-bytes-is-not-counting-files.md) | 容量だけ数えても足りない理由。**inode の既定値は容量に比例して増えません** |
| **既存の構成**（いま何が使われているか不明） | [「設定されている」と「使われている」は違う](notes/counting-bytes-is-not-counting-files.md#設定されていると使われているの違い) | 設定の一覧が使用実態にならない理由。プロトコルは有効なだけでは使われていません |
| **先に決めなければならない移行方式** | [移行方式の決定木](../../reference/decision-trees/migration-method.md) | **後で戻せない判断から逆算して、いま採取すべき項目**が決まります |

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | 容量・ファイル数・ディレクトリ構造をどう棚卸しするか | [容量が余っていても書けなくなる](notes/counting-bytes-is-not-counting-files.md) |
| 2 | どのプロトコルが実際に使われているか | [「設定されている」と「使われている」は違う](notes/counting-bytes-is-not-counting-files.md#設定されていると使われているの違い) |
| 3 | 権限・ACL・ID マッピングの現状はどうなっているか | [棚卸し項目の逆算表](notes/counting-bytes-is-not-counting-files.md#後で戻せない判断から逆算する棚卸し項目) |
| 4 | 移行のブロッカーになりうる機能依存は何か | [移行方式の決定木](../../reference/decision-trees/migration-method.md) |
| 5 | 性能要件のベースラインをどう測るか | [比較可能な形で取る](notes/counting-bytes-is-not-counting-files.md#比較可能な形での性能ベースラインの取得) |
| 6 | 移行元が SaaS / クラウドストレージの場合、追加で採取すべき数値は何か | [Assess フェーズで採取すべき数値](../03-migrate/notes/saas-source-migration-scoping.md#3-assess-フェーズで採取すべき数値) |
| 7 | その値をどこから取れば判断に使えるか | [棚卸しの値をどこから取るかの比較](../../reference/comparison/inventory-sources.md) |
| 8 | 評価と PoC はどう違い、どちらを今やっているのか | 本 README の[評価と PoC の別](#評価と-poc-の別) |

---

## 評価と PoC の別

**この 2 つは答える問いが違い、取り違えると片方の成果でもう片方を判断することになります。**

| | 答える問い | 終わりの条件 |
|---|---|---|
| **評価（assessment）** | **進めるか、進めないか** | 進めない理由が出るか、出ないことが確認できたとき |
| **PoC** | **動くか、動かないか** | **測定前に決めた合否基準に対して、測った結果が出たとき** |

**PoC で最も多い失敗は、測ったあとに合否を決めることです。** そうすると出た数値が合格になります。**測る前に「何を測るか」「どの値なら合格か」「誰が判断するか」を書き、測定結果と一緒に残します。** 埋まらない欄があるなら、そのフェーズはまだ始められません。

**このモジュールの棚卸し項目は評価に効きます。** PoC の合否基準はワークロードごとに違うので、ここにはありません。

| 知りたいこと | 所在 |
|---|---|
| 評価を成果物としてどう構成するか（**適用しない条件の一覧を含む**） | [Adoption Assessment Guide](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/docs/adoption-guide/adoption-assessment.md) |
| PoC の合否基準の書き方と、記録の残し方 | [PoC チェックリスト](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/poc-checklist.md) |

**どちらもそれぞれのアーキテクチャに固有です。** 汎用のテンプレートはこちらで作りません。**使われていないテンプレートは、使われているものへの参照より悪い**ためです。

---

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`notes/`](notes/) | 知見の最小単位。1 ファイル = 1 論点。frontmatter に `evidence` 区分を持ちます |
| [`checklists/`](checklists/) | 現場で使うチェックリスト。[棚卸しチェックリスト](checklists/inventory.md) |

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
🌐 [日本語](README.md) | [English](../../../en/playbooks/01-assess/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
