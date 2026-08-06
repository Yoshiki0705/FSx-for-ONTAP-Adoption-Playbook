# Playbook 02 — Design

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/playbooks/02-design/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Turn assessment output into a target configuration. Capacity and throughput can be changed later, but some choices (security style, SnapLock enablement) are irreversible.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | How to divide file systems and SVMs | _not yet added_ |
| 2 | How to size capacity and throughput | _not yet added_ |
| 3 | How to choose volume security style | _not yet added_ |
| 4 | How to decide between Multi-AZ and Single-AZ | _not yet added_ |
| 5 | Which settings are irreversible, and when they must be decided | _not yet added_ |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../../ja/playbooks/02-design/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](../../../ja/playbooks/02-design/checklists/) | Checklists for field use |

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
- [Pre-production review](../../../ja/playbooks/04-build/checklists/pre-production-review.md) (日本語) — **irreversible choices are settled in this phase**
- [Navigation Guide](../../navigation.md)
- [Glossary](../../../ja/reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/playbooks/02-design/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
