# Domain — Cost

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/cost/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Covers capacity, tiering, and the gap between estimates and measurements. Estimates usually miss because of assumptions, not unit prices.

---

## Read first

**This turns what you already have in hand into the next single page to read.** The table below it is
the table of contents; this is the entry point.

| What you have | Read first | What it settles |
|---|---|---|
| **A bill** that came in higher than expected | [When the bill came in higher than expected](../../../ja/reference/decision-trees/cost-higher-than-expected.md) (日本語) | **provisioned or consumed is the first branch.** Reducing usage does not move a provisioned charge |
| **An estimate** for something not built yet | [Assumptions that make an estimate wrong](notes/provisioned-versus-consumed.md#items-commonly-mistaken-as-not-billed) | **deduplication and compression do not reduce the SSD bill** |
| **A cut already chosen** | [What is billed](notes/provisioned-versus-consumed.md#what-is-billed) | what the cut trades away. **If a requirement fixed the provisioned amount, there is nothing to cut** |

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | What is billed and what is not | [What is billed](notes/provisioned-versus-consumed.md#what-is-billed) (日本語) |
| 2 | How far tiering actually brings cost down | [Tiering does not always cost less](notes/provisioned-versus-consumed.md#tiering-does-not-always-save-money) (日本語) |
| 3 | Which assumptions typically break an estimate | [The assumptions that break an estimate](notes/provisioned-versus-consumed.md#typical-estimation-assumptions-that-break) (日本語) |
| 4 | How to account for Snapshot capacity impact | [Snapshots show up as capacity](notes/provisioned-versus-consumed.md#snapshots-consume-capacity) (日本語) |
| 5 | How to weigh the cost-availability-performance trade-off | [Weighing the trade-off symmetrically](notes/provisioned-versus-consumed.md#how-to-weigh-trade-offs) (日本語) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |

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
🌐 [日本語](../../../ja/domains/cost/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
