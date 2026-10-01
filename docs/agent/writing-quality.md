# 文書品質の判定基準

> この文書は [`AGENTS.md`](../../AGENTS.md) の索引から読みます。食い違いがあれば `AGENTS.md` を優先します。
> 書き方そのものは [執筆ガイド](../style-guide.ja.md)（[English](../style-guide.en.md)）にあります。
> この文書が扱うのは、書かれた文書をどう判定するかです。

## 適用範囲

Hub とすべての Spoke のドキュメントに適用します。
対象外は 2 つあります。
本人名義で公開する一人称のブログ記事は、署名としての締めや箇条書き中心の構成が本人の文体として認められている領域なので、外します。
upstream の規約に従う fork も外します。
第 2 段階までは日本語と英語の本文だけを走査し、他の言語は対象にしません。

## 判定の考え方

主判定は、リポジトリごとに抜き出した 5 本の目視です。
3 本は検出件数の多い順に選び、2 本はランダムに選びます。
件数の多い順だけでは、検出器が拾わない種類の悪文を確かめられないからです。

検出件数は副指標で、兆候にすぎません。
英語版 Wikipedia の編集者向けガイド [S1] は、AI が書いた文の兆候を列挙したうえで、兆候だけを消しても問題は残り、見つけにくくなるだけだと注意しています。
そのため、規則には 1 つずつ、それが示唆する実体の欠陥を対にして書きます。
件数が減っても目視の判定が良くなっていなければ、改善とはみなしません。

## 機械で検出する規則

検出器は [`tools/ai_style_rules.py`](../../tools/ai_style_rules.py) です。
パターンの正確な定義と、規則ごとの陽性・陰性の例はこのファイルにあります。
下の表の「示唆する実体の欠陥」はファイル側の定義と同じ文で、一致しないとテストが落ちます。

| ID | 検出するもの | 段階 | 言語 | 示唆する実体の欠陥 | 目視観点 |
|---|---|---|---|---|---|
| D1 | 描画後にアスタリスクのまま残る `**`（例: `は**「X」**で`） | fail 予定 | ja, en | 強調のつもりの箇所がアスタリスクのまま表示され、読者には壊れた文書に見える。 | H7 |
| D2 | 決め台詞（`が核心です`、`この点に尽きる`、`結局のところ`） | fail 予定 | ja | 決め台詞が主張の代わりになっていて、何がどうなるかが書かれていない。 | H1, H2 |
| D3 | 否定で持ち上げる対比（`単なる…ではない`） | warning | ja | 否定で持ち上げる対比構文で、言いたい内容そのものが後回しになっている。 | H2 |
| D4 | `実は` | warning | ja | 意外性を演出する副詞で、前提との差分が明示されていない。 | H1 |
| D5 | 会話の締め（`ご不明な点`、`お役に立てれば`、`I hope this helps`） | fail 予定 | ja, en | 会話の定型の締めが残っていて、文書が読者ではなく対話相手に向いている。 | H5 |
| D6 | `not just X but Y` | warning | en | 対比構文で持ち上げていて、言いたい内容そのものが後回しになっている。 | H2 |
| D7 | `serves as`、`plays a key role` | warning | en | 意義を語る言い回しが、具体的な役割や挙動の説明に置き換わっていない。 | H2 |
| D9 | 要約の予告（`In summary`、`まとめると`、`please note`） | warning | ja, en | 要約の予告や注意喚起の前置きがあり、直前の内容を繰り返している。 | H5 |
| D10 | 番号付き手順の中の `simply`、`簡単に` | warning | ja, en | 手順を簡単だと形容していて、失敗する条件が書かれていない。 | H12 |
| D11 | 出典のない一般論（`多くの企業`、`studies show`）。同じ行に URL があれば対象外 | warning | ja, en | 出典のない一般論で、誰がどこで述べたかを読者が確かめられない。 | H1 |
| D12 | ラベル付きリスト（`- **X**: …`、`- **X** — …`） | warning | ja | ラベル付きリストで、属性が 2 つ以上なら表、そうでなければ地の文で書ける内容になっている。 | H6 |
| D13 | リスト項目と見出しの先頭の絵文字 | warning | ja, en | 絵文字が見出しや箇条の装飾として使われ、意味を運んでいない。 | H7 |
| D14 | 見出しの中の `**` | fail 予定 | ja, en | 見出しの中の太字で、見出しの階層と強調が二重になり、目次やアンカーにも記号が残る。 | H6 |
| D15 | 1,000 字あたり 5 個を超える太字（2,000 字以上の文書）、文全体が太字の行 | warning | ja, en | 太字が多すぎるか文全体が太字で、本当に見落とすと壊れる条件が埋もれている。 | H7 |
| D17 | 1 項目だけのリスト、本文を持たず下位見出しだけを包む見出し | warning | ja, en | 構造が中身に釣り合っておらず、1 項目のリストや本文のない見出しが並んでいる。 | H6 |
| D18 | em ダッシュ（U+2014）を含む行 | warning | ja, en | em ダッシュで節をつないでいて、文の関係（理由・例・言い換え）が明示されていない。 | H2 |
| D19 | `実行します:` のように述語とコロンで止め、直後にコードやリストを置く行 | warning | ja | コードや表の直前を「〜します:」で止めていて、何が得られるかが書かれていない。 | H11 |
| D20 | 冗長な言い回し（`することができ`、`まず最初に`） | warning | ja | 冗長な言い回しで、短く言える動詞が名詞化されている。 | H11 |
| D23 | 推量の重ね掛け（`可能性があると考えられ`） | warning | ja | 推量が二重になっていて、確認済みか未確認かが読み取れない。 | H1 |
| D24 | 程度の形容（`飛躍的に`、`blazing`） | warning | ja, en | 程度を形容詞で語っていて、数値と測定環境が示されていない。 | H1, H2 |

すべての規則は、コードフェンス、インラインコード、HTML コメント、URL、frontmatter、言語スイッチャーの中を対象にしません。
D1 は CommonMark の太字の規則で判定します。
括弧の外側に日本語の助詞が接する `**「X」**` は、区切りが開きも閉じもしない位置にあり、GitHub でも markdown-it でも太字になりません。
エディタ上では正しく見えるため、描画器と同じ規則で機械的に判定します。
Python の実装は、markdown-it が生成した期待値とテストで照合しています。

現在はすべての規則が件数の報告だけで、どの規則も CI を止めません。
fail 予定の 4 規則は、Hub の既存文書の該当箇所を直す pull request で `REPORT_ONLY_CATEGORIES` から `ai-style` を外し、fail に上げます。
D2 の `尽きる` は、`こと` `点` `これ` `それ` が前に来る形だけを拾います。
これがないと `容量が先に尽きます` のような文字どおりの記述も検出するためです。

### 見送った規則

| ID | 検出しようとしたもの | 見送った理由 |
|---|---|---|
| D8 | 英語の AI 語彙（`delve`、`tapestry` など） | 単語 1 つでは技術用法と区別できず、複数語の共起で判断する必要があるため |
| D16 | 英語見出しの Title Case | 製品名などの固有名詞の辞書が要るため |
| D21 | 環境を併記していない測定値 | 仕様値と実測値を字面で区別できないため |
| D22 | 敬体と常体の混在 | 表、箇条書き、引用を除いた文末判定の精度を確かめていないため |

### 実行方法

`make audit` は件数の要約を 1 行出し、終了コードには影響させません。
所見の一覧は `make ai-style-report` で出ます。
Spoke では検出器を単体で使い、`python3 ai_style_rules.py docs/ --summary` で件数表を出します。
`--fail` を付けると fail 予定の規則に所見があるときだけ終了コード 1 を返します。

## 目視でしか判定できない観点

目視は次の 12 観点で行います。
記録は「問題あり / なし / 判断できない」の 3 値で残し、「判断できない」には理由を書きます。

| 観点 | 問い | 対応する検出規則 |
|---|---|---|
| H1 主張と根拠 | 断定した文ごとに、出典、環境付きの実測、「未確認」の明示のどれかがあるか | D2, D4, D11, D23, D24 |
| H2 具体性 | 一般論を、この環境の値やこの操作の結果に置き換えられる箇所が残っていないか | D2, D3, D6, D7, D18, D24 |
| H3 文書の種類 | 手順書に長い解説が入っていないか、リファレンスに意見が混ざっていないか | なし |
| H4 読者の前提 | 想定読者が冒頭で分かり、前提知識の説明が過不足ないか | なし |
| H5 結論の位置 | 最初の画面で、何が分かり何を決められるかが読めるか | D5, D9 |
| H6 見出しの連なり | 見出しだけを順に読んで論旨が追えるか | D12, D14, D17 |
| H7 強調の意味 | 太字が、逆説、禁止、見落とすと壊れる条件に限られているか | D1, D13, D15 |
| H8 対称性 | 比較で、推奨する選択肢の制約も同じ粒度で書いているか | なし（`neutrality` が一部を拾う） |
| H9 説明可能性 | 書き手か承認者が、各主張の正しさを口頭で説明できるか | なし |
| H10 図と本文 | 図の主張が本文か表にも書かれているか | なし |
| H11 翻訳の自然さ | 英語版が日本語の構文をなぞっていないか、日本語版に直訳調が残っていないか | D19, D20 |
| H12 失敗と限界 | うまくいかなかった試行や、測っていない範囲が書かれているか | D10 |

## 構成の規則

結論を先に置き、理由と詳細を後に続けます [S11b] [S15]。
見出しだけを順に読んで論旨が追えるようにします [S15]。
1 つの文書に、チュートリアル、手順、リファレンス、解説の 4 種類を混ぜません [S14]。
太字は、逆説、禁止、見落とすと壊れる条件だけに使います。
強調は通常、語の選び方で運びます [S11a]。

ラベル付きリストは、`- **X**: …` の形も `- **X** — …` の形も減らします。
区切り記号をコロンからダッシュに付け替えても、ラベルで内容を区切る構造は変わりません [S4]。
各項目に属性が 2 つ以上あれば表にし、そうでなければ地の文にします。
1 項目だけのリストは作りません [S11c]。

見出しやリスト項目の先頭には絵文字を置きません [S4] [S5]。
意味を持つ記号として認めるのは、状態を表す表の `✅` や `⚠️` だけです。
補足の件数に目標は置かず、その文書での判断に要る補足だけを書きます。

## 人と AI の両方に読ませる設計

人と AI エージェントの両方が読む文書は、短い入口と、詳細へのリンクで構成します。
[`llms.txt`](../../llms.txt) は H1、要約、リンク一覧という決まった形を持ち、詳細はリンク先に置きます [S17]。
[`AGENTS.md`](../../AGENTS.md) は、人には雑音になる規約や手順をエージェント向けに分けて置く場所です [S18]。
人向けの README は短く保ちます。

数値には、測定した環境と日付を添えます。
AI の関与そのものより、誰がどの範囲を検証したかが示されないことが読者の不信につながる、という知見があります [S8] [S9] [S10]。
図だけに事実を載せず、同じ内容を本文か表にも書きます。
理由は [`documentation-design.md`](documentation-design.md) にあります。
表示が崩れた `**` は、人には雑音で、クローラにはマークアップの残骸になります。
D1 を fail 予定に置いているのはこのためです。

## Hub の意図的な逸脱

Hub は、全角文字と半角英数字の間に半角スペースを入れます（`FSx for ONTAP を使う`、`128 MiB`）。
JTF 日本語標準スタイルガイドの 12 のルール [S16] はスペースを入れない側ですが、Hub は既存の文書全体の慣行を維持します。
意図的な逸脱なので、検出器には入れません。

## Spoke への導入手順と Kiro ローダの置き方

Spoke への導入は、そのリポジトリの文書を直す pull request と同じ pull request で行います。
fail 予定の規則を先にゲートへ入れると、既存の所見で CI が一斉に止まるためです。

1. Hub の `tools/ai_style_rules.py` を 1 ファイルだけコピーします。Hub の外で `--selftest` が通ることは、[`test_copyability_claims.py`](../../scripts/tests/test_copyability_claims.py) の `COPY_SETS` に登録して検査しています。
2. `python3 ai_style_rules.py docs/ --summary` で、修正前の件数を記録します。
3. 本人名義のブログ記事は、`--exclude 'blog/*'` かファイル単位の宣言 `<!-- audit-file-allow: ai-style,ai-style-warn -->` で外します。
4. 文書を直したら、同じ pull request で `--fail` を付けた実行を CI に加えます。
5. 規則をそのリポジトリの文書に書き写さず、`AGENTS.md` からこの文書の GitHub 上の URL へリンクします。規約を複数のリポジトリに複製すると、直すときに全部を追う必要があるためです。

Kiro のローダは `.kiro/` に置きますが、`.kiro/` は gitignore されているため、Hub から配れません。
各 Spoke では、`.kiro/steering/` に次の内容のファイルを 1 つ置きます。
Hub の `make drift` が Hub 自身のローダに課している上限と同じく、2,000 バイト以下に収めます。

```markdown
---
inclusion: auto
name: writing-quality
description: Read the Hub's writing-quality criteria before judging prose style, reading an ai-style finding, or choosing which documents to review by eye.
---
Body: https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/blob/main/docs/agent/writing-quality.md
Authority: AGENTS.md
```

## 出典の要約と一覧

英語圏の議論 [S1] [S2] は、意義の誇張、コピュラの回避、否定の並列、太字ラベル付きのリスト、会話文の混入などを AI 生成文の兆候として挙げています。
同時に、人による判別の精度には限界があり、兆候は規則ではないとしています。
日本語圏では、textlint の公開ルール [S4] [S7] と個人やコミュニティの議論 [S5] [S6] [S20] が、太字ラベル、文頭の絵文字、述語とコロンで止める書き方、冗長表現を挙げています。
[S5]、[S6]、[S20] は個人の記事や SNS の議論です。
[S20] からは構造の規則だけを参照し、トーンの推奨は採りません。
読者の信頼については [S8] [S9] [S10]、可読性と構成については [S11a] から [S16] のスタイルガイド、人と AI の両方に読ませる設計については [S17] [S18]、D1 の判定規則については [S19] を参照しています。

確認日はすべて 2026-10-02 です。

| ID | タイトル | 発行者 | 公開日 / 更新日 |
|---|---|---|---|
| S1 | [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) | Wikipedia 編集者コミュニティ | 記載なし（2026-08、2026-09 付の保守注記あり） |
| S2 | [Delving into LLM-assisted writing in biomedical publications through excess vocabulary](https://arxiv.org/abs/2406.07016) | arXiv / Science Advances 11(27) | 2024-06-11（v1）、2025-07-02（誌面） |
| S4 | [textlint-rule-preset-ai-writing](https://github.com/textlint-ja/textlint-rule-preset-ai-writing) | textlint-ja | 記載なし |
| S5 | [`急にAI感出る文体『これ、実は**あるあるです。**』`](https://togetter.com/li/2650083) | Togetter（SNS 投稿のまとめ） | 2026-01-10 |
| S6 | [AI執筆ブログを進化させた話 〜textlintとZenn GitHub連携編〜](https://zenn.dev/modokkin/articles/zenn-2025-09-04-tech-ai-blog-writing-evolution) | Zenn（個人） | 2025-09（日は記載なし） |
| S7 | [textlint-rule-preset-ja-technical-writing](https://github.com/textlint-ja/textlint-rule-preset-ja-technical-writing) | textlint-ja | 記載なし |
| S8 | [Understanding Reader Perception Shifts upon Disclosure of AI Authorship](https://arxiv.org/abs/2510.24011) | arXiv | 2025-10-28（v1）、2026-01-22（v2） |
| S9 | [When news is "written by artificial intelligence": a systematic review of provenance and disclosure cues in journalism](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1815243/full) | Frontiers in Artificial Intelligence | 2026-05-05 |
| S10 | [NN/G's Generative-AI Content Policy](https://www.nngroup.com/contents/ai-content-policy/) | Nielsen Norman Group | 2026-09-14 |
| S11a | [Text-formatting summary](https://developers.google.com/style/text-formatting) | Google developer documentation style guide | 記載なし |
| S11b | [Voice and tone](https://developers.google.com/style/tone) | Google developer documentation style guide | 記載なし |
| S11c | [Lists](https://developers.google.com/style/lists) | Google developer documentation style guide | 記載なし |
| S12a | [Top 10 tips for Microsoft style and voice](https://learn.microsoft.com/en-us/style-guide/top-10-tips-style-voice) | Microsoft Writing Style Guide | 記載なし |
| S12b | [Scannable content](https://learn.microsoft.com/en-us/style-guide/scannable-content/) | Microsoft Writing Style Guide | 記載なし |
| S13 | [A to Z style guide](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/style-guides/a-to-z-style-guide/) | GOV.UK | 記載なし |
| S14 | [Diátaxis](https://diataxis.fr/)、[Start here](https://diataxis.fr/start-here/) | Diátaxis | 記載なし |
| S15 | [公用文作成の考え方（建議）](https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/93650001_01.html) | 文化審議会（文化庁） | 2022-01-07 |
| S16 | [JTF日本語標準スタイルガイド（翻訳用）／12 のルール](https://www.jtf.jp/tips/styleguide) | 日本翻訳連盟 | 4.0 版 2026-07-25 |
| S17 | [The /llms.txt file](https://llmstxt.org/) | llms-txt | 記載なし（v2） |
| S18 | [AGENTS.md](https://agents.md/) | Agentic AI Foundation（Linux Foundation） | 記載なし |
| S19 | [CommonMark Spec 0.31.2](https://spec.commonmark.org/0.31.2/) | CommonMark | 記載なし |
| S20 | [自然な日本語文章を生成するためのライティングガイドライン](https://gist.github.com/YSRKEN/c10b25539c73007df4d0dbd887d84b14) | GitHub Gist（個人） | 記載なし |

S5 のタイトルはアスタリスクを文字として含むため、太字として描画されないようコードとして載せています。
