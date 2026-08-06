# Playbook 03 — Migrate

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/playbooks/03-migrate/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Covers method selection, cutover, and rollback. A migration plan without a rollback procedure is an incomplete plan.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | Which method to choose (SnapMirror / DataSync / host-side copy) | [Choosing a migration method](../../../ja/reference/decision-trees/migration-method.md) (日本語) |
| 2 | What is required to migrate while preserving ACLs | [Preserving ACLs is a privilege problem, not a tool problem](../../../ja/playbooks/03-migrate/notes/preserving-acls-during-migration.md) (日本語) |
| 3 | How to plan initial and incremental sync | [Baseline and incremental sync](../../../ja/playbooks/03-migrate/notes/where-the-rollback-window-closes.md#初期同期と差分同期) (日本語) |
| 4 | How to minimize cutover downtime | [The cutover sequence](../../../ja/playbooks/03-migrate/notes/where-the-rollback-window-closes.md#切り替えの順序) (日本語) |
| 5 | Up to what point, and how, you can roll back | [The rollback window closes when clients start writing](../../../ja/playbooks/03-migrate/notes/where-the-rollback-window-closes.md) (日本語) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../../ja/playbooks/03-migrate/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](../../../ja/playbooks/03-migrate/checklists/) | Checklists for field use |

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
🌐 [日本語](../../../ja/playbooks/03-migrate/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
