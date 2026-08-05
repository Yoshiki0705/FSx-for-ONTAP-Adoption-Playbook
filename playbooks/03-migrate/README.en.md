# Playbook 03 — Migrate

[日本語](README.md) | [🏠 Repository home](../../README.en.md)

---

Covers method selection, cutover, and rollback. A migration plan without a rollback procedure is an incomplete plan.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | Which method to choose (SnapMirror / DataSync / host-side copy) | _not yet added_ |
| 2 | What is required to migrate while preserving ACLs | _not yet added_ |
| 3 | How to plan initial and incremental sync | _not yet added_ |
| 4 | How to minimize cutover downtime | _not yet added_ |
| 5 | Up to what point, and how, you can roll back | _not yet added_ |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](checklists/) | Checklists for field use |

---

## How to read this

Always check the `evidence` field in each note's frontmatter.

| Tier | Meaning |
|---|---|
| `verified` | Reproduced by the author in the stated environment. `verified_on` gives the date |
| `documented` | Stated in vendor / AWS documentation. `source` gives the reference |
| `field-observation` | Observed once in the field, not reproduced. Do not generalize |
| `hypothesis` | Reasoned expectation, untested |

See the [Evidence Policy](../../docs/en/evidence-policy.md) for the full criteria.

---

## Related

- [Browse by topic](../../docs/en/navigation.md#topic-axis--domains)
- [Migration Method Decision Tree](../../reference/decision-trees/migration-method.md)
- [Navigation Guide](../../docs/en/navigation.md)
- [Glossary](../../reference/glossary/)

---

[日本語](README.md) | [🏠 Repository home](../../README.en.md)
