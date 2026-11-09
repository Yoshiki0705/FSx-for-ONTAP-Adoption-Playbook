---
title: 外部情報ソースの追跡 — Tokenomics / FOCUS / クラウド各社の一次情報を最新に保つ
lifecycle: [assess, design, optimize]
domains: [cost, data-utilization]
evidence: documented
source: https://www.linuxfoundation.org/news/linux-foundation-launches-tokenomics-foundation
lang: ja
---

# 外部情報ソースの追跡

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

---

## 結論

**このリポジトリは、FinOps for AI と Tokenomics に関する一次情報を、継続的に最新へ取り込みます。** そのために「追跡すべき一次情報の URL・最終確認日・確認スコープ」を 1 つの表で管理し、ゲートで古さを検出します。

分担は [引用索引](cross-repo-index.md) と同じ思想です。あちらは **sibling repository の主張**がまだ生きているかを追い、こちらは **外部の一次情報**（業界標準・仕様・クラウド各社の公式ガイダンス）がいつ確認されたかを追います。

**なぜ必要か**: Tokenomics は 2026-08 設立で策定中、FOCUS は版が上がり、AWS の料金は随時変わります。記憶や古い確認日のまま断定すると、読者が誤った設計判断をします。**揮発性の高い事実（版・価格・提供状況）は、確認日を持たせて管理し、古くなったら確認する**のが運用です。

> **Evidence**: `documented` — 下の表の各行は公式の一次情報を指します。**内容そのものはここに転記せず、確認日と確認スコープだけを管理します。** 取り込んだ知見は各ノートの本文に出典 URL 付きで置きます。

---

## 追跡する一次情報とゲート

| ゲート | 何を検証するか | ネットワーク |
|---|---|---|
| `make source-freshness` | 下の表の各行の `last_checked` が `review_interval_days` を超えて古くないか（ローカル・オフライン） | 不要 |
| `make source-freshness-external` | 上に加え、各 URL が今も到達可能か（HTTP で確認） | 必要 |

**ローカルの古さチェックは commit ゲート（`make all`）に含みます。** オフラインで動くためです。到達確認（`--external`）は手動のみで、`cross-repo-external` と同じく CI を外部ネットワークに出さない方針に従います。

---

## 追跡対象の範囲

**追跡表に載せるのは一次情報だけです。** 版・価格・提供状況が変わる source of truth（業界標準団体・仕様・クラウド各社の公式ガイダンス）に絞ります。

**二次情報（ベンダーブログ・カンファレンス登壇・ユーザー企業事例）は追跡表に載せません。** URL が消えやすく、無関係な改変で古さ警告が誤発火して保守負荷が増えるためです。事例・ベストプラクティスは「取り込んだ知見」として各ノートの本文に出典 URL 付きで `documented` で書きます（[参考リンク集](#参考リンク集二次情報)）。

**中立性**: 特定クラウドだけでなく、複数ベンダーの公式ガイダンスを対等に扱います。

---

## 追跡表

**この表の形式はゲートが読みます。** 列を増やす・順序を変える・行を表の外に書くと `make source-freshness` が失敗します。

- **id** — 短い識別子。英数字とハイフン
- **url** — 一次情報の URL
- **last_checked** — 最後に内容を確認した日（YYYY-MM-DD）
- **review_interval_days** — 再確認までの日数。既定 90、料金ページなど変動が速いものは 30
- **scope** — この行で何を確認するか（確認時に何を見るかの指針）

<!-- markdownlint-disable MD034 -->
<!-- URL はゲートが読むセルなのでリンク装飾せず裸で置きます。MD034 はこの表に限り無効化します。 -->
<!-- source-freshness:start -->

| id | url | last_checked | review_interval_days | scope |
|---|---|---|---|---|
| tokenomics-foundation | https://www.linuxfoundation.org/news/linux-foundation-launches-tokenomics-foundation | 2026-11-09 | 90 | Tokenomics の定義・ロードマップ・技術推進委員会の進捗。Big-T / 認定プログラムの公開状況 |
| focus-spec | https://focus.finops.org/ | 2026-11-09 | 90 | FOCUS の現行版。トークンコストのテレメトリ（v1.5+）が追加されたか |
| finops-framework | https://www.finops.org/framework/ | 2026-11-09 | 90 | FinOps Framework の能力・ドメイン。AI コストに関する更新 |
| aws-fsx-ontap-pricing | https://aws.amazon.com/fsx/netapp-ontap/pricing/ | 2026-11-09 | 30 | FSx for ONTAP の課金次元。容量プールのリクエスト課金・S3 Access Points の課金の記載 |
| aws-cost-optimization-pillar | https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html | 2026-11-09 | 90 | AWS Well-Architected のコスト最適化の原則。確保量課金リソースの扱い |
| aws-bedrock-kb-datasource | https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-ds.html | 2026-11-09 | 90 | Bedrock Knowledge Bases のデータソース要件。S3 以外の経路が追加されたか |
| azure-finops | https://learn.microsoft.com/azure/cost-management-billing/finops/ | 2026-11-09 | 90 | Microsoft の FinOps ガイダンス（中立性のための対等な一次情報） |
| google-cloud-finops | https://cloud.google.com/architecture/framework/cost-optimization | 2026-11-09 | 90 | Google Cloud のコスト最適化ガイダンス（中立性のための対等な一次情報） |

<!-- source-freshness:end -->
<!-- markdownlint-enable MD034 -->

---

## 更新の手順

**ゲートが古い行を報告したら、その URL を開いて内容を確認し、`last_checked` を今日の日付に更新します。**

1. `make source-freshness` が `<id>` を古いと報告する
2. その行の `url` を開き、`scope` に書かれた点が変わっていないか確認する
3. 変わっていれば、該当するノート（[adjacent cost](../domains/cost/notes/finops-for-ai-adjacent-cost.md) など）の本文を更新する
4. `last_checked` を確認日（今日）に更新する
5. 新しい一次情報が増えたら、表に行を足す

**確認日を更新するだけで内容を見ないのは意味がありません。** `scope` の点を実際に確認してから日付を進めます。

---

## 参考リンク集（二次情報）

**追跡表には載せませんが、取り込んだ知見の出典として置きます。** URL が変わりうるため、古さゲートの対象にはしません。

| 出典 | 種別 | 取り込んだ知見 |
|---|---|---|
| [Linux Foundation: Tokenomics Foundation 設立](https://www.linuxfoundation.org/news/linux-foundation-launches-tokenomics-foundation) | 業界標準団体の発表 | AI コストの大半は隣接コスト。cost per call で BOM 全体を測る |
| [FinOps Foundation: FOCUS](https://focus.finops.org/) | 仕様 | プロバイダ横断の課金データ仕様 |

事例・ベストプラクティスは今後も追加します。

---

## 関連ドキュメント

- [AI のコストはトークンだけではない](../domains/cost/notes/finops-for-ai-adjacent-cost.md) — トークン隣接コストと Tokenomics の骨子
- [AI のアクセス経路の選び方](comparison/finops-for-ai-access-paths.md) — reference 側の比較マトリクス
- [プロジェクト間の引用索引](cross-repo-index.md) — sibling repository の主張の追跡（こちらは外部一次情報の追跡）
- [直近のアップデート](recent-updates.md) — 四半期ごとのアップデートと設計への影響
- [知見の分類ポリシー](../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)
