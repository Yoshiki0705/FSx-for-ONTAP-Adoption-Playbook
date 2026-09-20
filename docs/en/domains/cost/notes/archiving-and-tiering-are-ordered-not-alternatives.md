---
title: Archiving with an external tool and the capacity pool tier are ordered, not alternatives — and the published reduction is measured against the adopting organization's legacy environment
lifecycle: [assess, migrate, optimize]
domains: [cost, data-utilization]
evidence: documented
source: https://aws.amazon.com/blogs/storage/cost-optimized-file-storage-with-amazon-fsx-for-netapp-ontap-and-komprise/
lang: en
---

# Archiving with an external tool and the capacity pool tier are ordered, not alternatives

[🏠 Repository home](../../../README.md) | [Domain — Cost](../README.md)

---

## Conclusion

**List the mechanisms for spending less and archiving by an external data-management tool sits in the same column as the FSx for ONTAP capacity pool tier. They are not in the same place.**

In the case AWS published, **two stages act in order.** An external tool archives to S3 Glacier by last-accessed date first, and **what remains then falls to the capacity pool tier.** Neither is placed instead of the other.

**And the published reduction is measured against the adopting organization's legacy environment, not against another AWS option.** This case is unusual in **footnoting the configuration**, so it is possible to read which configuration the rate belongs to. **A different configuration does not carry the rate.**

**What to take is the ordering, and the conditions attached to the rate — not the rate.**

> **Tier**: `documented` — based on what a case study AWS published states (**retrieved 2026-09-15**). **No measurement in this repository.** The case's figures belong to the adopting organization's configuration and are not grounds for a design.
> **The stated parts do not add up to the stated total.** See [The recorded ordering, and an arithmetic that does not add up](#the-recorded-ordering-and-an-arithmetic-that-does-not-add-up). **Do not cite the rate as it stands.**

---

## The recorded ordering, and an arithmetic that does not add up

**The ordering recorded in the case is as follows.**

| Stage | What happened | Share stated |
|---|---|---|
| 1 | After migration, the first archival ran on **last-accessed date**. The external tool moved data to S3 Glacier | **about 70%** to S3 Glacier |
| 2 | What remained in FSx for ONTAP fell to the capacity pool tier **within 30 days** | **60% of the remaining 30%** |
| Result | As the article states it | "**over 90%** of the initial data optimized" |

**Those three figures do not add up to over 90%.** 70 + (30 × 0.6) is 88. **How "optimized" is counted is not stated, so the reason for the difference is unknown.** This does not contradict anything else in the article; the definition is simply absent.

**So what can be taken is the ordering, not the rate.** That archiving carried most of it away first and the capacity pool tier acted on the remainder is readable from the two stages. **The over-90% total should not be quoted until the counting is known.**

**The ordering matters because the two stages act on different billing dimensions.**

| Stage | Destination | What changes |
|---|---|---|
| Archiving by an external tool | Amazon S3 / S3 Glacier | **It leaves FSx for ONTAP.** It comes out of the file system's capacity |
| The capacity pool tier | The FSx for ONTAP capacity pool tier | **It stays inside the file system.** It only drops out of the SSD tier, **and requests are charged as well** |

**Because the capacity pool tier carries per-request charges, moving data down does not necessarily cost less.** Data read repeatedly costs more once moved down. The detail is in [Tiering does not always save money](provisioned-versus-consumed.md#tiering-does-not-always-save-money). **This case's footnote states the capacity-tier request count as a premise** (below).

---

## The basis for the reduction, and the configuration in the footnote

**The rate is over 50% against a legacy environment that had reached $1/GB/year.** It is not a comparison with another AWS file storage service. **Cases that state the basis are not common, which is the part worth citing.**

The configuration recorded in the footnote:

| Item | Stated value |
|---|---|
| FSx for ONTAP data | 768 TB |
| Backups | 768 TB |
| SSD tier share | 30% |
| Throughput | 8 GBps |
| SSD IOPS | 320,000 |
| Capacity pool tier read/write requests | 6 million |
| S3 Glacier Instant Retrieval data | 4.2 TB |
| Retrievals per month | 10 TB |
| **Costs included** | **NetApp and external-tool third-party licensing** |
| Comparison basis | A legacy environment at **$1/GB/year** |

**That third-party licensing is inside the breakdown matters.** The decision to add a tool is evaluated after licensing is subtracted from the saving. **This is not a rate with licensing excluded.**

**A different configuration does not carry the rate.** Three things in particular change the result.

| Changes the result | Why |
|---|---|
| **The SSD tier share (30%)** | Provisioned SSD capacity is charged from the moment it is provisioned. A higher share lowers the rate |
| **The capacity-tier request count (6 million)** | **Requests are charged.** In a read-heavy configuration, moving data down does not cost less |
| **The comparison basis ($1/GB/year)** | If the legacy environment was cheaper than this, the reduction is smaller |

**Do not use "50% reduction" as an estimate for your own environment.** What can be taken is that a case exists which states its basis and configuration, and the structure by which those three inputs move the rate.

**On migration speed the article states "up to 25x", without saying what it is relative to.** With no baseline, the figure is usable neither for design nor for comparison.

---

## Where the reason for the migration choice sits

**This case used an external tool for the migration because of where the source was, not because of a feature comparison.** The article names AWS Snowball and AWS DataSync as candidates and then states that the external tool was used because **most of the data was already hosted by a cloud provider.**

**So the choice of migration mechanism was settled by the source before the tool.** The same ordering as [Choosing a migration method](../../../../ja/reference/decision-trees/migration-method.md) (日本語); **entering from a product comparison reverses it.**

The tool-side reasons the article gives are resilience, that users could find their data either at the original location or in the AWS cloud during the migration, and chain-of-custody reporting for regulated parts of the business. **These are statements of capability, not something confirmed in this repository.**

**Two configuration premises.** The external tool ran on Amazon EC2 in a central Region, a **single-Region** configuration that was acceptable there. And **AWS Direct Connect is stated as a requirement for FlexCache performance**, named as the first thing to start on where it is absent, because of lead times.

---

## Compared symmetrically with the AWS-native options

**Adding no external tool is placed with the same weight.**

| Mechanism | Suits | What it commits you to |
|---|---|---|
| **The capacity pool tier alone** (an FSx for ONTAP feature) | Completing it inside the file system. Not adding tools | **Nothing leaves the file system.** Requests are charged, so a read-heavy estate does not get cheaper |
| **Archiving with an external tool** | Moving data out of the file system to S3 or Glacier. Wanting visibility into usage as well | **Licensing and an operating owner are added.** In the case it ran on Amazon EC2 |
| **Both** (the case's configuration) | Moving most of it out and dropping the remainder a tier | **Both sets of constraints.** The ordering and the thresholds have to be designed |

**How to choose comes down to whether data may leave the file system.**

| What you have | Applicable option |
|---|---|
| Data must not leave the file system | **The capacity pool tier alone.** Archiving with an external tool drops out |
| Reads are frequent | **Moving data down can cost more.** Read [Tiering does not always save money](provisioned-versus-consumed.md#tiering-does-not-always-save-money) first |
| Visibility into usage is itself the goal | The external tool. **But visibility is a separate requirement from tiering** |
| The legacy environment's unit cost is already low | **The reduction will be smaller than the case's.** The basis differs |

---

## Verify in your own environment

| # | Step | What it establishes |
|---|---|---|
| 1 | Work out the annual cost per GB of the legacy environment | **The comparison basis.** Without it, a rate says nothing |
| 2 | Check against audit requirements whether data may leave the file system | **If it may not, archiving with an external tool drops out** |
| 3 | Measure the distribution of last-accessed dates | How much stage 1 moves. **The case's 70% belongs to the case's distribution** |
| 4 | Measure how often what remains after stage 1 is read | **Whether stage 2 costs more rather than less** |
| 5 | Estimate the capacity pool tier request count | The gap between the footnote's 6 million and your own |
| 6 | Subtract third-party licensing from the saving | **The actual effect of adding the tool** |
| 7 | Settle where the migration source is | **The mechanism is decided here.** Before any tool comparison |
| 8 | If FlexCache is planned, confirm Direct Connect and its lead time | What the case names as the first thing to start on |

**Skipping step 1 leaves the phrase "reduction rate" without meaning.**

---

## Common misconceptions

| Misconception | Actually |
|---|---|
| Archiving and the capacity pool tier are a choice between two | **They are ordered.** In the case, external archiving acted first and the remainder fell to the capacity pool tier |
| The 50% reduction comes from moving to FSx for ONTAP | **The basis is the adopting organization's legacy environment at $1/GB/year.** A lower-cost legacy environment gives a smaller rate |
| The case's over-90% total can be quoted | **The stated parts add to 88.** The counting is not stated, so it cannot be quoted |
| The reduction excludes the tool's cost | **It includes it.** The footnote states third-party licensing is included |
| Tiering always costs less | **Requests are charged.** A read-heavy estate costs more |
| A migration tool is chosen on capability | **The case's stated reason is where the source was.** Settled before any comparison |
| "Up to 25x" is a usable figure for transfer speed | **It does not say what it is relative to.** With no baseline it cannot be used |
| The case's configuration can be used as an estimate directly | **The SSD share, the request count and the comparison basis all move the rate** |

---

## Primary sources consulted

| Point | Source | Retrieved |
|---|---|---|
| The two-stage ordering (about 70% archived to S3 Glacier on last-accessed date, 60% of the remaining 30% to the capacity pool tier within 30 days, stated in the article as over 90% of the initial data). 3 PB migrated with no downtime and 2 PB consolidated. That the legacy environment had reached $1/GB/year. The reduction of over 50%. The footnoted configuration (768 TB data / 768 TB backups / 30% SSD / 8 GBps / 320k SSD IOPS / 6 million capacity-tier requests / 4.2 TB in S3 Glacier IR / 10 TB retrieved per month / third-party licensing included). That the migration mechanism was chosen because of where the source was. That Snowball and DataSync were named as candidates. That the external tool ran on Amazon EC2 in a central Region as a single-Region configuration. That Direct Connect is stated as a requirement for FlexCache performance, with lead time named. That the "up to 25x" migration speed carries no stated baseline | [AWS Storage Blog: Cost-optimized file storage with Amazon FSx for NetApp ONTAP and Komprise](https://aws.amazon.com/blogs/storage/cost-optimized-file-storage-with-amazon-fsx-for-netapp-ontap-and-komprise/) | 2026-09-15 |

---

## Related documents

- [Domain — Cost](../README.md) — this module's hub
- [ISV and SaaS solution map by problem](../../../reference/isv-solution-map.md#nas-migration-and-data-visibility) — the index for this problem area
- [Billing splits into "provisioned" and "consumed"](provisioned-versus-consumed.md) — the billing model itself
- [Tiering does not always save money](provisioned-versus-consumed.md#tiering-does-not-always-save-money) — stage 2's per-request charge
- [When the bill is higher than expected](../../../../ja/reference/decision-trees/cost-higher-than-expected.md) (日本語) — whether a line item is billed on provisioned or consumed
- [Choosing a migration method](../../../../ja/reference/decision-trees/migration-method.md) (日本語) — the ordering by which the source settles the mechanism
- [Tiering policies compared](../../../../ja/reference/comparison/tiering-policies.md) (日本語) — stage 2's options
- [Industry resource map — manufacturing](../../../../ja/reference/industry-resource-map.md#製造) (日本語) — the same case from another entry point
- [Evidence Policy](../../../evidence-policy.md)

---

[🏠 Repository home](../../../README.md) | [Domain — Cost](../README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/cost/notes/archiving-and-tiering-are-ordered-not-alternatives.md) | [English](archiving-and-tiering-are-ordered-not-alternatives.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
