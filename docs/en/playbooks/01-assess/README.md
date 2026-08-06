# Playbook 01 — Assess

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/playbooks/01-assess/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

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
| [`notes/`](../../../ja/playbooks/01-assess/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](../../../ja/playbooks/01-assess/checklists/) | Checklists for field use |

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

- [Browse by topic](../../navigation.md#topic-axis--domains)
- [Migration Method Decision Tree](../../../ja/reference/decision-trees/migration-method.md)
- [Navigation Guide](../../navigation.md)
- [Glossary](../../../ja/reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/playbooks/01-assess/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
