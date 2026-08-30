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
| 1 | How to inventory capacity, file counts, and directory structure | [Free space does not mean you can still write](../../../ja/playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) (日本語) |
| 2 | Which protocols are actually in use | ["Configured" is not "in use"](../../../ja/playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md#設定されていると使われているの違い) (日本語) |
| 3 | The current state of permissions, ACLs, and ID mapping | [Inventory items worked back from the decisions](../../../ja/playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md#後で戻せない判断から逆算する棚卸し項目) (日本語) |
| 4 | Which feature dependencies could block the migration | [Migration method decision tree](../../../ja/reference/decision-trees/migration-method.md) (日本語) |
| 5 | How to measure a baseline for performance requirements | [Record it so it stays comparable](../../../ja/playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md#比較可能な形での性能ベースラインの取得) (日本語) |
| 6 | What additional numbers to collect when the source is SaaS / cloud storage | [Numbers to collect during Assess](../03-migrate/notes/saas-source-migration-scoping.md#3-numbers-to-collect-during-assess) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../../ja/playbooks/01-assess/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
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
