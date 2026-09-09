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

## Cost once the architecture is decided

**This module holds the FSx for ONTAP billing model** — what is billed on what was provisioned, what on what was consumed, and how far tiering reduces it.

**The cost structure of a particular architecture belongs to the repository that operates it.** Nothing is transcribed here: the same figure in two places goes stale in one of them.

| Decided | Where the cost structure lives | What it holds |
|---|---|---|
| **Collect through S3, consume over a file protocol** | [FinOps — S3 standard against an FSx for ONTAP S3 access point](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/comparison/finops-s3-vs-s3ap.md) (日本語) | The billing-dimension mapping and three structural differences. **Reading the same data repeatedly, or once, changes which is cheaper** |
| **About to run a performance test** | [FinOps — cost per test pattern](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/comparison/finops-performance-test-patterns.md) (日本語) | **The cost of the measurement environment itself**, what is billed by time against by usage, and what happens if it is left running |
| **Choosing a monitoring route** | [Cost model — Direct Send / Collector / Firehose](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/blob/main/docs/ja/cost-model.md) (日本語) | Monthly comparison across three routes, and **the input values an estimate needs** |
| **Monitoring is running; is the estimate right** | [Cost validation](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/blob/main/docs/ja/cost-validation.md) (日本語) | Reconciling the estimate against **actual billing data** |
| **Putting data on an analytics platform** | [Cost estimation](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/docs/adoption-guide/cost-estimation.md) | Component breakdown and **scaling formulas**. Metadata-only against full copy |
| **The S3 access point portal has been running** | [Cost measurement](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/ja/cost-measurement.md) (日本語) | **Measuring from Cost Explorer.** Not an estimate |

**A figure brought here is registered as a citation** ([citation index](../../../ja/reference/cross-repo-index.md) (日本語)). Unit prices carry a retrieval date and a region, and a figure without them cannot be compared.

**Unit prices themselves are on the [AWS pricing page](https://aws.amazon.com/fsx/netapp-ontap/pricing/).** Every figure in those repositories is as of its retrieval date and does not replace it.

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
