# Domain — Performance

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/performance/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Covers throughput design, latency, caching, and shared-bandwidth behavior. Always read a number together with the environment it was measured in.

---

## Reading order

**If you have arrived with a figure that is lower than expected, the first step is isolating what it measured, not tuning.**

| Order | Read | What it settles |
|---|---|---|
| 1 | [Working out what a measured throughput figure actually measured](../../../ja/reference/decision-trees/measured-throughput-triage.md) (日本語) | Which of four ceilings the figure hit. **The remedy for one is a no-op for the others** |
| 2 | [Levers for raising throughput](../../../ja/reference/comparison/throughput-levers.md) (日本語) | Six levers against the ceiling each one moves. **The two that moved the measured figure most carry no additional charge** |
| 3 | [A figure from a single connection measures the client, not the storage](../../../ja/domains/performance/notes/a-single-connection-measures-the-client.md) (日本語) | The measured figures and every condition behind them |

**If you are about to write a throughput requirement, read 3 first.** A requirement stated only in MB/s does not settle anything.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | Where throughput is determined and where it is shared | [Throughput is not set by one value](notes/where-throughput-is-determined-and-shared.md) (日本語) |
| 2 | How bandwidth is shared across protocols | [How bandwidth is shared across protocols](../../../ja/domains/performance/notes/what-you-cannot-read-from-cloudwatch.md#プロトコル間での帯域の分け合い方) (日本語) |
| 3 | How to look at latency tails (p99) | [p99 cannot be read from the CloudWatch metrics](../../../ja/domains/performance/notes/what-you-cannot-read-from-cloudwatch.md) (日本語) |
| 4 | What makes a workload benefit from caching | [When caching helps](../../../ja/domains/performance/notes/what-you-cannot-read-from-cloudwatch.md#キャッシュが効く条件) (日本語) |
| 5 | How to design a benchmark that reproduces | [What a reproducible benchmark records](../../../ja/domains/performance/notes/what-you-cannot-read-from-cloudwatch.md#再現できるベンチマークの条件) (日本語) |
| 6 | What a figure measured here is actually measuring | [A figure from a single connection measures the client, not the storage](../../../ja/domains/performance/notes/a-single-connection-measures-the-client.md) (日本語) |
| 7 | Why the same configuration returns different numbers | [Where the 45% spread comes from](../../../ja/domains/performance/notes/a-single-connection-measures-the-client.md#45-の幅の正体) (日本語) |
| 8 | Which lever to try first | [Levers for raising throughput](../../../ja/reference/comparison/throughput-levers.md) (日本語) |

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
🌐 [日本語](../../../ja/domains/performance/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
