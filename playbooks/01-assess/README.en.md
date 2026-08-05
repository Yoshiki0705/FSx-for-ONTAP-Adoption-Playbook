# Playbook 01 — Assess

[日本語](README.md) | [🏠 Repository home](../../README.en.md)

---

Before migrating, establish what exists on the current NAS and what will constrain the move. Gaps here translate directly into rework cost in later phases.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | How to inventory capacity, file counts, and directory structure | _not yet added_ |
| 2 | Which protocols are actually in use | _not yet added_ |
| 3 | The current state of permissions, ACLs, and ID mapping | _not yet added_ |
| 4 | Which feature dependencies could block the migration | _not yet added_ |
| 5 | How to measure a baseline for performance requirements | _not yet added_ |

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
