# Domain — Performance

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/performance/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Covers throughput design, latency, caching, and shared-bandwidth behavior. Always read a number together with the environment it was measured in.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | Where throughput is determined and where it is shared | [Throughput is not set by one value](notes/where-throughput-is-determined-and-shared.md) (日本語) |
| 2 | How bandwidth is shared across protocols | [How bandwidth is shared across protocols](../../../ja/domains/performance/notes/what-you-cannot-read-from-cloudwatch.md#プロトコル間で帯域はどう分け合われるか) (日本語) |
| 3 | How to look at latency tails (p99) | [p99 cannot be read from the CloudWatch metrics](../../../ja/domains/performance/notes/what-you-cannot-read-from-cloudwatch.md) (日本語) |
| 4 | What makes a workload benefit from caching | [When caching helps](../../../ja/domains/performance/notes/what-you-cannot-read-from-cloudwatch.md#キャッシュが効く条件) (日本語) |
| 5 | How to design a benchmark that reproduces | [What a reproducible benchmark records](../../../ja/domains/performance/notes/what-you-cannot-read-from-cloudwatch.md#再現できるベンチマークの条件) (日本語) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](../../../ja/domains/performance/checklists/) | Checklists for field use |

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
🌐 [日本語](../../../ja/domains/performance/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
