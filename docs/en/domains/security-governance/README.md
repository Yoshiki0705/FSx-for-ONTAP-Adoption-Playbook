# Domain — Security & Governance

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/security-governance/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Covers encryption, audit, permission design, and considerations for regulated workloads. What is written here are design considerations, not legal or compliance judgments.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | The encryption options and where their boundaries lie | [At rest is automatic, in transit is off by default](../../../ja/domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md#プラットフォームが提供するものと自分に残るもの) (日本語) |
| 2 | How to record who did what | [Two audit planes, one with a documented gap](../../../ja/domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md#監査は-2-つの面に分かれ片方に穴があります) (日本語) |
| 3 | How to move permission design toward least privilege | [Separate the administrators](../../../ja/domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md#権限設計管理者を分ける) (日本語) |
| 4 | Which points come up for regulated workloads | [What gets asked, and what can be answered as fact](../../../ja/domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md#規制ワークロードで問われる論点) (日本語) |
| 5 | Considerations when crossing the OT / IT boundary | [Mechanisms for crossing a segmented boundary, and their limits](../../../ja/domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md#分離された境界をまたぐときに使える仕組みとその限界) (日本語) |
| 6 | How to govern operations that cannot be undone | [Approval for an irreversible operation is separate from approval for the task](../../../ja/domains/security-governance/notes/irreversible-operations-need-separate-approval.md) (日本語) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../../ja/domains/security-governance/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](../../../ja/domains/security-governance/checklists/) | Checklists for field use |

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
🌐 [日本語](../../../ja/domains/security-governance/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
