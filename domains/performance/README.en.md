# Domain — Performance

[日本語](README.md) | [🏠 Repository home](../../README.en.md)

---

Covers throughput design, latency, caching, and shared-bandwidth behavior. Always read a number together with the environment it was measured in.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | Where throughput is determined and where it is shared | _not yet added_ |
| 2 | How bandwidth is shared across protocols | _not yet added_ |
| 3 | How to look at latency tails (p99) | _not yet added_ |
| 4 | What makes a workload benefit from caching | _not yet added_ |
| 5 | How to design a benchmark that reproduces | _not yet added_ |

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

- [Browse by lifecycle](../../docs/en/navigation.md#lifecycle-axis--playbooks)
- [Comparison Matrices](../../reference/comparison/)
- [Navigation Guide](../../docs/en/navigation.md)
- [Glossary](../../reference/glossary/)

---

[日本語](README.md) | [🏠 Repository home](../../README.en.md)
