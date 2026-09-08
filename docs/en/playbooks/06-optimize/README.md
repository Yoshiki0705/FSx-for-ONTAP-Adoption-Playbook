# Playbook 06 — Optimize

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/playbooks/06-optimize/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Performance and cost tuning once you are in steady state. Optimization cannot begin without measurement.

---

## Read first

**This turns what you already have in hand into the next single page to read.** The table below it is
the table of contents; this is the entry point.

| What you have | Read first | What it settles |
|---|---|---|
| **The bill is higher than expected** | [When the bill came in higher than expected](../../../ja/reference/decision-trees/cost-higher-than-expected.md) (日本語) | **provisioned or consumed is the first branch.** Reducing usage does not move a provisioned charge |
| **It is slow and the cause is unclear** | [Isolating a performance regression](../05-operate/notes/monitoring-fails-on-averages.md#order-for-isolating-a-performance-regression) | **the remedy for one ceiling is a no-op for the others** |
| **A pending decision on what order to change things in** | [Order changes by whether they can be undone](../../../ja/playbooks/06-optimize/notes/tiering-defaults-differ-by-creation-method.md#戻せるかで決める変更の順序) (日本語) | **try the reversible ones first.** The tiering default depends on how the volume was created |

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | How to identify where the bottleneck is | [Triage order](../05-operate/notes/monitoring-fails-on-averages.md#order-for-isolating-a-performance-regression) |
| 2 | How to configure tiering | [Tiering defaults differ by creation method](../../../ja/playbooks/06-optimize/notes/tiering-defaults-differ-by-creation-method.md) (日本語) |
| 3 | How to measure storage efficiency gains | [How to measure the gain](../../../ja/playbooks/06-optimize/notes/tiering-defaults-differ-by-creation-method.md#ストレージ効率の効果の測り方) (日本語) |
| 4 | What to check before raising the throughput setting | [Order changes by whether they can be undone](../../../ja/playbooks/06-optimize/notes/tiering-defaults-differ-by-creation-method.md#戻せるかで決める変更の順序) (日本語) |
| 5 | How to position the cost-versus-availability trade-off | [Weighing the trade-off symmetrically](../../../en/domains/cost/notes/provisioned-versus-consumed.md#how-to-weigh-trade-offs) (日本語) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../../ja/playbooks/06-optimize/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |

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
🌐 [日本語](../../../ja/playbooks/06-optimize/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
