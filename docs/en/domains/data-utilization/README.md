# Domain — Data Utilization

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/data-utilization/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

How to use NAS-resident data from analytics, AI, and applications without multiplying copies of it.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | What is and is not possible over the S3 API | [FSx for ONTAP S3 AP is not "S3 you can use as S3"](../../../ja/domains/data-utilization/notes/s3-access-point-constraints.md) (日本語) |
| 2 | How to connect an analytics platform | [Connecting an analytics platform](../../../ja/domains/data-utilization/notes/reaching-data-without-copies.md#分析基盤への接続) (日本語) |
| 3 | How to handle permissions in AI / RAG | [What flattened permissions mean](../../../ja/domains/data-utilization/notes/reaching-data-without-copies.md#権限が平坦化されることの意味) (日本語) |
| 4 | What a copy-minimizing design looks like | [Three ways to reach data without copying](../../../ja/domains/data-utilization/notes/reaching-data-without-copies.md#コピーを増やさない-3-つの手段) (日本語) |
| 5 | Where read acceleration is worth applying | [When FlexCache helps](../../../ja/domains/data-utilization/notes/reaching-data-without-copies.md#flexcache-が効く条件) (日本語) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../../ja/domains/data-utilization/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](../../../ja/domains/data-utilization/checklists/) | Checklists for field use |

---

## How to read this

Always check the `evidence` field in each note's frontmatter.

| Tier | Meaning |
|---|---|
| `verified` | Reproduced by the author in the stated environment. `verified_on` gives the date |
| `documented` | Stated in vendor / AWS documentation. `source` gives the reference |
| `field-observation` | Observed once in the field, not reproduced. Do not generalize |
| `hypothesis` | Reasoned expectation, untested |

See the [Evidence Policy](../../evidence-policy.md) for the full criteria.

---

## Related

- [Browse by lifecycle](../../navigation.md#lifecycle-axis--playbooks)
- [Comparison Matrices](../../../ja/reference/comparison/)
- [Navigation Guide](../../navigation.md)
- [Glossary](../../../ja/reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/data-utilization/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
