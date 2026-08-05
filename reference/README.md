# Reference

<!-- audit-file-allow: neutrality -->
<!-- 中立性ルールを説明するために禁止表現を引用します / Quotes forbidden phrasing to define the rule. -->

[🏠 リポジトリトップ](../README.md) | [🏠 Repository home](../README.en.md)

---

ライフサイクル・テーマの両軸から参照される横断リファレンスです。
Cross-cutting reference material, referenced from both the lifecycle and topic axes.

---

## 構成 / Structure

| ディレクトリ / Directory | 内容 / Contents |
|---|---|
| [`decision-trees/`](decision-trees/) | 選択フローチャート。複数の選択肢からどれを選ぶか / Selection flowcharts |
| [`comparison/`](comparison/) | 比較マトリクス。トレードオフを対称に記載 / Comparison matrices with symmetric trade-offs |
| [`limits/`](limits/) | 上限値・クォータ。出典と検証日付き / Limits and quotas, with source and verification date |
| [`glossary/`](glossary/) | ONTAP / AWS 用語集 / Terminology |

---

## 執筆時のルール / Authoring rules

### 比較マトリクス / Comparison matrices

推奨する選択肢の制約も必ず書きます。ベンダー対決の枠組み（「X は Y より優れている」）は使いません。
用途に応じた選択（「X は A に向き、Y は B に向く」）として提示し、「選び方」セクションを必ず添えます。

Always state the recommended option's own constraints. Do not use vendor-versus framing
("X is better than Y"). Present options as suited to different contexts ("X suits A; Y suits B")
and always include a "how to choose" section.

### 上限値 / Limits

各値には出典と検証日を付けます。ドキュメント記載値と実測値が異なる場合は**両方**を書き、
差分の理由が分かっていればそれも書きます。

Every value carries a source and a verification date. Where the documented value and the measured
value differ, record **both**, and the reason for the difference when it is known.

---

[🏠 リポジトリトップ](../README.md) | [🏠 Repository home](../README.en.md)
