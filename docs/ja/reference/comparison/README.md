# 比較マトリクス / Comparison Matrices

<!-- audit-file-allow: neutrality -->
<!-- 中立性ルールを説明するために禁止表現を引用します / Quotes forbidden phrasing to define the rule. -->

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md)

---

選択肢を比較する資料を置きます。目的は「どれが優れているか」を決めることではなく、
**どの状況にどれが向くか**を読者が判断できるようにすることです。

Comparison material lives here. The goal is not to decide which option is superior, but to let
readers judge **which option suits which situation**.

---

## 執筆ルール / Authoring rules

| ルール / Rule | 理由 / Reason |
|---|---|
| トレードオフは**推奨案の制約も含めて**対称に書く / State trade-offs symmetrically, **including for the recommended option** | 片方の弱点だけを列挙すると比較ではなく主張になる / Listing only one side's weaknesses turns a comparison into an argument |
| 「選び方」セクションを必ず添える / Always include a "how to choose" section | 表だけでは読者が自分の状況に当てはめられない / A table alone does not let readers map it onto their own situation |
| ベンダー対決の枠組みを使わない / Do not use vendor-versus framing | 「X は Y より優れている」ではなく「X は A に向き、Y は B に向く」/ Not "X is better than Y" but "X suits A; Y suits B" |
| 数値には測定条件を併記する / State measurement conditions alongside numbers | 条件のない数値は再現できない / A number without conditions cannot be reproduced |
| 比較時点を明記する / Record the comparison date | 機能は変わる。古い比較は誤解を招く / Capabilities change; a stale comparison misleads |

`make audit` が優劣表現・ベンダー対決表現を検出します。
`make audit` flags superiority claims and vendor-versus phrasing.

---

## テンプレート / Template

```markdown
---
title: <何と何を比較するか>
lifecycle: [design]
domains: [<該当テーマ>]
evidence: documented
source: <URL>
lang: ja
---

# <タイトル>

## 結論
<どの状況にどれが向くか、1-3 行で>

## 比較
| 観点 | 選択肢 A | 選択肢 B | 選択肢 C |
|---|---|---|---|
| 向いている状況 | | | |
| トレードオフ | | | |
| 前提条件 | | | |
| 運用負荷 | | | |
| コスト特性 | | | |

## 選び方
| # | 確認項目 | 判断への影響 |
|---|---|---|
| 1 | | |

## よくある誤解
| 誤解 | 実際 |
|---|---|
| | |

## 比較時点
YYYY-MM-DD 時点の情報です。
```

---

## 一覧 / Index

| 資料 / Document | 比較対象 / Options compared | 比較時点 / As of |
|---|---|---|
| [データ保護方式の比較](data-protection-methods.md) | Snapshot / ボリュームバックアップ / AWS Backup / SnapMirror（+ SnapLock の 2 モード） | 2026-08-06 |
| [階層化ポリシーの比較](tiering-policies.md) | `NONE` / `SNAPSHOT_ONLY` / `AUTO` / `ALL` | 2026-08-06 |
| [ブロックストレージの選択肢の比較](block-storage-options.md) | Amazon EBS / EBS Multi-Attach / FSx for ONTAP の iSCSI と NVMe/TCP | 2026-09-05 |
| [監視経路の比較](observability-routes.md) | Amazon CloudWatch / NetApp Harvest + Prometheus + Grafana / SaaS / ONTAP REST 直叩き | 2026-09-05 |
| [スループットを上げる手段の比較](throughput-levers.md) | `nconnect` / SMB Multichannel / `tcp-max-xfer-size` / 台数 / SSD と IOPS / スループット容量 | 2026-09-05 |

---

## 関連ドキュメント / Related documents

- [移行方式 決定ツリー](../decision-trees/migration-method.md) / [Migration Method Decision Tree](../decision-trees/migration-method.md)
- [知見の分類ポリシー](../../evidence-policy.md) / [Evidence Policy](../../../en/evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md)
