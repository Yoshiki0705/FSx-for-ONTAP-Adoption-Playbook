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
| 1 | What to consider so that adding an HA pair later can actually be used | [What happens when you add an HA pair](../../../ja/playbooks/02-design/notes/deployment-type-is-decided-once.md#ha-ペアを足すときに起きること) (日本語) |
| 2 | Whether one HA pair is enough, or scale-out is required | [The ceiling of a single HA pair](../../../ja/playbooks/02-design/notes/deployment-type-is-decided-once.md#単一-ha-ペアの天井) (日本語) |
| 3 | How to choose volume security style | [Volume security style decides the permission model](../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) |
| 4 | How to decide between Multi-AZ and Single-AZ | [Choosing between Multi-AZ and Single-AZ](../../../ja/playbooks/02-design/notes/deployment-type-is-decided-once.md#multi-az-と-single-az-の判断) (日本語) |
| 5 | Which settings are irreversible, and when they must be decided | [Deployment type is decided once](../../../ja/playbooks/02-design/notes/deployment-type-is-decided-once.md) (日本語) |
| 6 | How end users actually reach the data | [Four paths end users take to the data](../../../ja/playbooks/02-design/notes/how-end-users-reach-the-data.md) (日本語) |
| 7 | At what granularity to divide file systems and SVMs | _未追加_ |
| 8 | How to size the initial capacity and throughput | _未追加_ |

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
