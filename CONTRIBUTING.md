# CONTRIBUTING

<!-- audit-file-allow: naming,neutrality,pii -->
<!-- 執筆規約そのものを定義する文書であり、禁止パターンを引用する必要があるため監査を免除します。
     このファイル単位の宣言をコンテンツファイルにコピーしないでください。 -->

[🏠 リポジトリトップ](README.md) | [🏠 Repository home](docs/en/README.md)

---

## クイックスタート

```bash
git clone https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook.git
cd FSx-for-ONTAP-Adoption-Playbook

# 任意: Markdown lint（未インストールならスキップされます）
npm install -g markdownlint-cli2

make help          # 利用可能なターゲット
make new-note MODULE=domains/performance SLUG=my-concern
make all           # コミット前に必ず実行
```

`tools/` は Python 3.12 以降の標準ライブラリのみで動きます。追加の依存はありません。CI は 3.14 で実行しています。

---

## 知見を 1 つ追加する流れ

| # | 手順 | コマンド / 参照 |
|---|---|---|
| 1 | どのモジュールに属するか決める | [ナビゲーションガイド](docs/ja/navigation.md) |
| 2 | ノートを生成する | `make new-note MODULE=... SLUG=...` |
| 3 | 本文を書く | 下記「執筆ルール」 |
| 4 | `evidence` 区分を正しく設定する | [知見の分類ポリシー](docs/ja/evidence-policy.md) |
| 5 | モジュールの README から動線を張る | 該当 `README.md` の表に行を追加 |
| 6 | 検証する | `make all` |

**手順 5 を忘れると、書いたノートに誰もたどり着けません。** ハブから必ずリンクしてください。

---

## 執筆ルール

### 構成

| ルール | 理由 |
|---|---|
| 結論を最初に書く | 読者は全部読まない |
| 1 ファイル = 1 論点 | 検索性と更新性が上がる |
| 2 属性以上の列挙は表にする | 箇条書きは比較に向かない |
| 「よくある誤解」を入れる | 誤った前提が最も多い失敗原因 |
| 数値には測定条件を併記する | 条件のない数値は再現できない |

### 書いてはいけないもの

| 禁止 | 代わりに |
|---|---|
| 企業名・組織名・個人名 | 業種と規模帯 / 役割ベースの表記 |
| 実際の識別子（アカウント ID、IP、ホスト名） | プレースホルダー（`123456789012`、`10.0.x.x`） |
| サポートケース番号・内部チケット ID | 「ベンダーに確認済み（追跡中）」 |
| `FSxN` / 単独の `FSx` / `FSx ONTAP` | 初出 **Amazon FSx for NetApp ONTAP**、以降 **FSx for ONTAP** |
| BlueXP / NetApp Workload Factory / NetApp Console の提案 | native 等価物（CloudWatch、ONTAP REST API、FabricPool、AWS DataSync、Snapshot / FlexClone / SnapMirror） |
| ベンダー対決表現（「X は Y より優れている」「競合ツール」） | 用途別の提示（「X は A に向き、Y は B に向く」） |
| 役割名ラベルの注記（`> **AppSec lens**:`） | 中立なトピックラベル（`> **Security note**:`） |

最後の項目について: 職種名のラベルは「その役割の人がレビューした」ことを含意します。
実際にレビューが行われていない場合、読者に誤った印象を与えます。**内容は変えず、ラベルだけ
中立にしてください。**

### レビュー観点を書きたい場合

自分の分析として書くのは問題ありません。ラベルを職種名にしないでください。

```markdown
✅ > **Security note**: この構成では監査ログが…
✅ > **コストに関する補足**: ティアリングを有効にすると…
❌ > **Security Engineer lens**: この構成では監査ログが…
❌ > **FinOps エンジニアの視点**: ティアリングを有効にすると…
```

---

## 多言語対応

ドキュメントの言語は**ディレクトリ**で表します。`README.en.md` のようなサフィックスは使いません。
`docs/ja/domains/cost/README.md` の対訳は `docs/en/domains/cost/README.md` です。

同じ深さに置かれるため、**翻訳はコピーして本文を訳すだけ**です。相対リンクは 1 文字も変わりません。
翻訳中に `../` の数を数え直しているとしたら、ファイルの置き場所が間違っています。

例外はルートの `README.md` だけです。これが日本語のハブなので `docs/ja/README.md` は存在しません。

| ティア | 対象 | 必要言語 |
|---|---|---|
| 1 | ルート `README.md` と `docs/<lang>/README.md`、`docs/i18n-manifest.txt` に登録されたガイド | manifest の指定に従う（既定は 8 言語） |
| 2 | `docs/<lang>/{playbooks,domains}/` 各モジュールの `README.md` | 日本語 + English |
| 3 | `notes/`、`checklists/`、`reference/` | 日本語（English は任意） |

### 8 言語にするもの / しないもの

Tier 1 は**初手の材料だけ**です。自分の言語で辿り着いた読者が必要なのは「どこへ行けばよいか」と「どこまで信頼できるか」で、それ以上ではありません。

| 8 言語にする | ja + en または ja に留める |
|---|---|
| ハブ、ナビゲーション、証跡区分の読み方 | 数値・上限・閾値を含むもの |
| 行動の前に読者が理解すべき匿名化・執筆ポリシー | 不可逆な操作を説明するもの |
| 経路を選ぶ前に読者が目にするラベルや文言 | ノート、チェックリスト、決定ツリー、比較マトリクス |

境界線は**結果の重さ**です。初手の材料の誤訳は読者を違うページに送るだけで、読者はそれに気づきます。**設計判断の誤訳は誤りだと分からないまま実行されます。** そのため深い技術内容は、訳しやすい場合でも意図的に昇格させません。

昇格は安定性でも判断します。変更が続いている文書を訳すと、以降の修正がすべて 8 倍になります。**書いた時点ではなく、内容が落ち着いた時点で昇格**してください。

### 正典の明記

Tier 1 の各文書は、どの版が正典かを対称に明記します。

- 日本語版は、自身が技術的な正典であることを述べる
- 他言語版は、日本語版が正典であること、齟齬は報告してほしいことを述べる

見出しではなく本文の段落なので、セクションパリティには影響しません。この記載がある理由は、ここの翻訳が機械支援で作られ、公開前にネイティブレビューを受けていないためです。**記述に従って行動するかを決める読者には、それを知る権利があります。**

### 運用は「公開してから指摘で直す」

ネイティブレビューを待つと、日本語と English 以外は永久に公開されません。そこで**制約を明記し、報告経路を 1 クリックに置き、翻訳の修正を通常の修正として扱う**方針を取ります。

この取引が成立するのは、**注意書きが見える場所にあり、対象範囲が狭いあいだ**だけです。だから初手の材料が上限であって、そこから広げていく出発点ではありません。

翻訳の誤りは [Correction テンプレート](.github/ISSUE_TEMPLATE/correction.yml) で受け付けます。言語を選ぶ欄があり、置き換え案がなくても該当箇所を示すだけで有効な報告です。

`docs/ja/reference/` は現在、日本語と English を同一ファイルに併記する形式です。言語ごとに分割していないため、
追記するときも既存の併記スタイルに合わせてください（`docs/en/reference/` を部分的に作らないこと）。

### 言語スイッチャーは手で書かない

各ドキュメント冒頭と末尾のスイッチャーは**生成物**です。手で編集しないでください。

```bash
make switcher-write   # 実在する翻訳だけを並べて再生成
make switcher-check   # 生成結果と実ファイルの一致を検査（make all に含まれます）
```

存在しない翻訳はリンクに現れません。翻訳を追加したら `make switcher-write` を実行するだけです。
マーカー（`<!-- lang-switcher:start -->` / `<!-- lang-switcher:end -->`）の挿入位置だけは人が決めます。
新規ファイルでは H1 直後と末尾に一度だけ書いてください。

`make switcher-check` は同時に、**自言語に対訳があるのに他言語へリンクしていないか**も検査します。
これは `make links` では見つかりません（リンク自体は解決するため）。

Tier 1 は**セクション構成と数が言語間で一致**していることを CI が検査します。
新しいガイドはまず ja + en で追加し、`docs/i18n-manifest.txt` に `name.md: ja,en` として登録します。
翻訳が揃ったら manifest に言語を追加してください。

翻訳しないもの: ファイルパス、コマンド、バッジ URL、アンカー ID、製品名・技術用語
（ONTAP、SnapMirror、FlexCache、SnapLock、FabricPool、S3 Access Point、SVM、LIF）。

---

## 検証

| コマンド | 検査内容 |
|---|---|
| `make lint` | frontmatter スキーマ + Markdown lint |
| `make i18n-check` | Tier 1 の言語間パリティ |
| `make switcher-check` | 言語スイッチャーの整合 + 誤った言語へのリンク |
| `make audit` | 命名 / 中立性 / 個人情報 / 内部 ID / シークレット |
| `make links` | 内部リンクの解決（`llms.txt` を含む） |
| `make links-external` | 外部 URL も含む（ネットワーク必要） |
| `make secrets` | gitleaks によるワークツリーの秘密スキャン（未インストール時は失敗します） |
| `make drift` | AGENTS.md のサイズ予算 / steering ローダーの薄さ / 索引の到達性と追跡状態 |
| `make test` | ガードレールのテスト（block/ask/allow 契約、.PHONY、各ゲートの壊し検出） |
| `make all` | 上記すべて。**コミット前の必須ゲート** |

`make audit` の誤検知は行末のコメントで抑止できます。使う場合は理由が一目で分かる箇所に限定してください。

```markdown
外部記事タイトルに FSxN が含まれる場合   <!-- allow:naming -->
| `name@example.com` | 「(internal reviewer)」 |   <!-- allow:pii -->
```

---

## 自己レビュー（4 軸）

`make all` の前に確認してください。自動チェックは構文しか見ません。

| # | 軸 | 確認内容 |
|---|---|---|
| 1 | 実装漏れ | ノートをモジュール README からリンクしたか。Tier 1 を 1 言語だけ更新していないか。翻訳を追加したら `make switcher-write` を実行したか |
| 2 | 違和感 | プレースホルダーの残り。`evidence: verified` に `verified_on` や `region` がない。見出しと本文の不一致 |
| 3 | 磨き込み | 同じファイルに触れる小さな改善を「範囲外」として見送っていないか |
| 4 | 退行リスク | リンク先を移動していないか。他のドキュメントが引用している数値を変えていないか |

---

## Pull Request

| 項目 | 規約 |
|---|---|
| ブランチ | `<type>/<what>`、kebab-case、40 文字以内。例: `docs/lang-directory-layout` |
| コミット件名 | Conventional Commits（`docs:` / `feat:` / `fix:` / `chore:` / `ci:`）、72 文字以内、命令形、句点なし |
| コミット本文 | 72 桁で折り返し。**なぜ**を先に書く（何をしたかは差分が示します） |
| PR タイトル | `<type>: <description>`、70 文字以内。CI が検査。**squash merge の件名になります** |
| PR 本文 | [テンプレート](.github/PULL_REQUEST_TEMPLATE.md) に従う |
| マージ方式 | squash merge。`main` を線形に保ち、詳細は PR 本文に残します |

### ブランチ名とコミットメッセージも公開物です

検索インデックスに載り、実質的に永続します。形式だけでなく中身にも規約があります。

| ルール | 理由 |
|---|---|
| **追加・変更する内容**を名前にする。以前が何を欠いていたかは書かない | ブランチ名は PR ページに永久に残り、過去の成果への評定として読まれます。`docs/readme-honest-coverage` は過去を裁いており、`docs/module-status-accuracy` は変更を説明しています |
| 文ではなく名詞句 | `docs/lang-directory-layout`（○）/ `docs/move-all-docs-under-lang`（×） |
| 1 ブランチ 1 論点 | 名前が中身を説明しなくなったら**分割**します。曖昧な名前に変えて済ませないでください |
| 日付・チケット ID・個人名・ツールやセッションへの言及を入れない | `docs/phase3-20260806` や `docs/agent-session-2` は経緯を漏らし、すぐ陳腐化します |
| 件名は活動ではなく効果を書く | `docs: add environment-first entry`（○）/ `docs: update navigation.md`（×） |

**ブランチ名・件名・本文・PR 本文に書かないもの**: 個人名、レビュー回数や観点数、企業・組織名、サポートケース番号、ベンダー内部 ID、実アカウント ID や IP、個人のパス、ベンダー対決表現。プロセスメタデータを禁じる理由は公開ドキュメントと同じで、読者にとって雑音であり、作業時期に縛られるためです。

マージ前のゲート:

1. CI が通っている
2. 未解決のレビューコメントがない
3. 4 軸自己レビューが完了している

---

## 関連ドキュメント

- [知見の分類ポリシー](docs/ja/evidence-policy.md) — `evidence` 区分の判断基準
- [ナビゲーションガイド](docs/ja/navigation.md) — リポジトリの歩き方
- [AGENTS.md](AGENTS.md) — AI エージェント向けの規約（人間が読んでも有用）
- [case-studies/README.md](docs/ja/case-studies/README.md) — 事例の匿名化ポリシー

---

[🏠 リポジトリトップ](README.md) | [🏠 Repository home](docs/en/README.md)
