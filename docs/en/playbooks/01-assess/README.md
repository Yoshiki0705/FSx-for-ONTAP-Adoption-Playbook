# Playbook 01 — Assess

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/playbooks/01-assess/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Before migrating, establish what exists on the current NAS and what will constrain the move. Gaps here translate directly into rework cost in later phases.

---

## Read first

**This turns what you already have in hand into the next single page to read.** The table below it is
the table of contents; this is the entry point.

| What you have | Read first | What it settles |
|---|---|---|
| **A number from the source** (capacity, file count) | [Free capacity does not mean you can still write](notes/counting-bytes-is-not-counting-files.md) | why counting bytes is not enough. **The inode default does not grow with capacity** |
| **An existing setup** whose actual use is unknown | [Configured is not the same as used](notes/counting-bytes-is-not-counting-files.md#the-difference-between-configured-and-in-use) | why a configuration listing is not evidence of use |
| **A migration method still to be chosen** | [Migration method decision tree](../../../ja/reference/decision-trees/migration-method.md) (日本語) | **working back from the decisions that cannot be undone** tells you what to collect now |

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | How to inventory capacity, file counts, and directory structure | [Free space does not mean you can still write](../../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) |
| 2 | Which protocols are actually in use | ["Configured" is not "in use"](../../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md#the-difference-between-configured-and-in-use) |
| 3 | The current state of permissions, ACLs, and ID mapping | [Inventory items worked back from the decisions](../../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md#working-back-from-decisions-you-cannot-undo) |
| 4 | Which feature dependencies could block the migration | [Migration method decision tree](../../../ja/reference/decision-trees/migration-method.md) (日本語) |
| 5 | How to measure a baseline for performance requirements | [Record it so it stays comparable](../../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md#capturing-a-performance-baseline-in-comparable-form) |
| 6 | What additional numbers to collect when the source is SaaS / cloud storage | [Numbers to collect during Assess](../03-migrate/notes/saas-source-migration-scoping.md#3-numbers-to-collect-during-assess) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../playbooks/01-assess/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](../../../ja/playbooks/01-assess/checklists/) | Checklists for field use. [Inventory checklist](../../../ja/playbooks/01-assess/checklists/inventory.md) (日本語) |

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
