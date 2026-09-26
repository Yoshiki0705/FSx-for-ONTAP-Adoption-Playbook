---
title: The point where EBS stops being the cheaper answer is not the instance count but the number of copies of the same data — throughput capacity is 80% of the minimum monthly cost
lifecycle: [assess, design, optimize]
domains: [block-storage, cost]
evidence: documented
source: https://aws.amazon.com/fsx/netapp-ontap/pricing/
lang: en
---

# Is the point where EBS stops being cheaper the instance count?

No, it is the number of copies of the same data. The floor of the minimum configuration is 80% throughput capacity.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/when-ebs-stops-being-the-cheaper-answer.md) | [English](when-ebs-stops-being-the-cheaper-answer.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That FSx for ONTAP is not cheaper than EBS on a per-GB rate, and that what decides the crossover is the number of copies of the same data
- That 83% of the minimum monthly cost is throughput capacity, and that the total flips once the copy count exceeds a point that depends on dataset size

## What this note does not answer

- Current rates or the monthly cost in your own region (prices are revised; re-fetch before designing)
- The deduplication / compression reduction rate (data-dependent and not guaranteed), or a monetary conversion of the differences not in the rate table

## Prerequisite level

intermediate

## Body

<a id="is-the-point-where-ebs-stops-being-cheaper-the-instance-count"></a>

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

---

### Conclusion

**FSx for ONTAP is not cheaper than Amazon EBS on a per-GB basis.** At the Tokyo region's public rates, SSD is $0.150/GB-month against `gp3`'s $0.096/GB-month. And FSx for ONTAP adds a separate monthly charge for throughput capacity. **There is no reason to bring it in as "storage cheaper than EBS."**

**Nor is the crossover the instance count.** Even if you launch 50 EC2 instances, if each of the 50 holds different data, staying on EBS is straightforward.

**What bears on it is how many copies of the same byte sequence you hold.** On EBS, one copy is one billed volume, whereas on FSx for ONTAP FlexClone does not copy data and a Snapshot is not a separate billing line. **So as the number of copies of the same data grows, at some point the total flips.**

At the Tokyo region's minimum configuration, **around the point where the copies of a 1 TB dataset exceed about 9** is the rough crossover. The larger the dataset, the smaller this number.

> **Tier**: `documented` — the rates are public values obtained from the AWS Price List API (Tokyo region; FSx for ONTAP effective 2026-07-01 / obtained 2026-09-05, EBS effective 2026-09-01 / obtained 2026-09-05). **The calculation below is arithmetic using public rates, not a measurement.**
> **Prices are revised.** Re-fetch the current rates for your own region before deciding. The steps are in [Verify it in your environment](#verify-it-in-your-environment).

---

### The rates obtained

Tokyo region (`ap-northeast-1`). **They differ in other regions.**

| Item | Rate |
|---|---|
| FSx for ONTAP SSD (Single-AZ) | **$0.150** / GB-month |
| FSx for ONTAP SSD (Multi-AZ) | **$0.300** / GB-month |
| FSx for ONTAP throughput capacity (Single-AZ 2nd generation) | **$2.013** / MBps-month |
| FSx for ONTAP throughput capacity (Multi-AZ 2nd generation) | **$3.148** / MBps-month |
| FSx for ONTAP throughput capacity (Single-AZ 1st generation) | $0.906 / MBps-month |
| FSx for ONTAP capacity pool (Standard, Single-AZ) | $0.0238 / GB-month |
| FSx for ONTAP backup | $0.050 / GB-month |
| EBS `gp3` storage | **$0.096** / GB-month |
| EBS `gp3` extra IOPS (above 3,000) | $0.006 / IOPS-month |
| EBS `gp3` extra throughput (above 125 MB/s) | $0.048 / MBps-month |
| EBS `io2` storage | $0.142 / GB-month |
| EBS Snapshot (standard) | $0.050 / GB-month |
| EBS Snapshot (archive) | $0.0125 / GB-month |

**Note that the 2nd-generation throughput capacity rate is higher than the 1st generation's** ($2.013 vs $0.906 for Single-AZ). It is in exchange for features available only on the 2nd generation (NVMe/TCP, multiple Single-AZ HA pairs).

> **A note on unit notation**: the Price List API's `gp3` extra-throughput entry returns a unit of `GiBps-mo` with a price of $49.152. The description reads "per provisioned MiBps-month $0.048" (49.152 ÷ 1024 = 0.048). **Because the API's `unit` and `description` differ, pulling out `pricePerUnit` alone is off by a factor of 1,024.** FSx for ONTAP throughput is the same: `unit` is `MiBps-Mo`, the description is MBps.
> **Do not use `pricePerUnit` on its own; always reconcile `unit` with `description` before calculating.** The two items above had mismatched units in the 2026-09-05 response, and skipping the reconciliation is off by 1,024×.

---

### The floor of the minimum configuration

**FSx for ONTAP has a lower bound.** For a 2nd-generation 1 HA pair it is SSD 1,024 GiB and throughput capacity 384 MBps. You pay for it even unused.

| Breakdown | Calculation | Monthly |
|---|---|---|
| SSD 1,024 GiB | 1,024 × $0.150 | $153.60 |
| Throughput capacity 384 MBps | 384 × $2.013 | **$772.99** |
| **Total (the Single-AZ 2nd-generation floor)** | | **$926.59** |

**83% of the floor is throughput capacity.** Not capacity. **What bears on "starting small" is the throughput-capacity lower bound, not the SSD lower bound.**

The same configuration on Multi-AZ 2nd generation is $1,516.03/month (1,024 × $0.300 + 384 × $3.148). **About 1.6× for the same capacity and same throughput.**

---

### The crossover calculation

**There is one model.** Holding a D GB dataset as C copies.

```text
EBS               = $0.096 × D × C
FSx for ONTAP     = the SSD monthly cost (the minimum provisioning that satisfies D) + $772.99
```

On the FSx for ONTAP side, the added cost per copy is calculated as 0 (on the premise that FlexClone's actual data does not grow; in practice only the delta grows).

| Dataset D | FSx for ONTAP monthly | Crossover copy count C |
|---|---|---|
| 512 GB | $926.59 (SSD floor is 1,024 GiB) | **about 19** |
| 1,024 GB | $926.59 | **about 9.4** |
| 2,048 GB | $1,080.19 | **about 5.5** |
| 5,120 GB | $1,540.99 | **about 3.1** |
| 10,240 GB | $2,308.99 | **about 2.3** |

**Read it as "once the copies exceed C, FSx for ONTAP becomes cheaper."** The larger the dataset, the smaller C. At the 10 TB class it crosses over at three copies.

**If you also hold Snapshots on the EBS side, C shrinks further.** EBS Snapshots are a separate $0.050/GB-month charge, whereas FSx for ONTAP Snapshots only consume already-provisioned SSD and are not a separate billing line.

**Conversely, if there is one copy, FSx for ONTAP stays expensive.** This does not change whatever you provision.

---

### Replacing the instance-count question with the copy question

**"Launch N EC2 instances" alone decides nothing.** What decides is the following branch.

| How the N instances use the data | Copies needed on EBS | Judgment |
|---|---|---|
| Each holds **different** data (boot disks of web servers, etc.) | N (but different data, so not copies) | **EBS.** There is nothing to share |
| Each reads the **same** dataset (training data, a reference DB, build artifacts) | **N** (because EBS cannot share a volume) | Copies = N. Judge the crossover with the table above |
| Each holds a **writable working copy** from the same data (dev, verification environments) | **N** | Same as above. The typical case where FlexClone helps |
| Several **write the same block device simultaneously** (a cluster) | 1 | A matter of function, not rate. See the [comparison table (日本語)](../../../../ja/reference/comparison/block-storage-options.md) |
| Both block and **a file share** are needed | — | A matter of configuration, not rate. Both can be served from one file system |

**The second and third rows are where instance count turns into copy count.** EBS can attach one volume to only one instance (except `io2` Multi-Attach), so **the moment you want N instances to read the same data, N copies are needed.**

---

### The differences that do not appear in the rate

**The crossover calculation looks only at the storage bill.** The following are not converted into money. **The reason they are not is that the amount depends on the environment, not that they can be ignored.**

| Not in the rate table | Which side it bears on |
|---|---|
| The time to make a copy | FlexClone does not copy actual data. Creating a volume from an EBS Snapshot involves a copy |
| Deduplication / compression | FSx for ONTAP can enable it per volume and reduce the GB provisioned. **The reduction rate depends on the data and is not guaranteed** |
| Building and operating host-side multipath | **A burden on the FSx for ONTAP side.** Unnecessary for a single EBS attachment |
| Two control planes | LUNs and igroups are outside the AWS API ([the note](block-objects-are-outside-the-aws-api.md)) |
| Boot disk | **An FSx for ONTAP LUN cannot boot.** EBS is required |
| Inter-AZ data transfer | There are Multi-AZ configurations where the optimal path faces another AZ ([the note](multi-az-moves-a-route-not-an-address.md)) |
| The ceiling of 6 HA pairs | Block goes up to 6 pairs |
| Free-capacity operation | The difference between provisioned and consumed is in [Provisioned capacity versus consumed capacity](../../cost/notes/provisioned-versus-consumed.md) |

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| FSx for ONTAP is storage cheaper than EBS | **The per-GB rate is higher** ($0.150 vs $0.096). And throughput capacity is added on top |
| More EC2 instances make FSx for ONTAP favorable | **Not the instance count, but the number of copies of the same data.** If each instance holds different data, the count is irrelevant |
| The minimum monthly cost is decided by capacity | **83% of the floor is throughput capacity** |
| The 2nd generation is cheaper | **The throughput-capacity rate is higher than the 1st generation's** ($2.013 vs $0.906 for Single-AZ) |
| Multi-AZ is only a little more | It was **about 1.6×** for the same configuration |
| Snapshots are a separate charge on both | **EBS is a separate charge ($0.050/GB-month); FSx for ONTAP consumes already-provisioned SSD** |
| Deduplication reliably makes it cheaper | **The reduction rate depends on the data and is not guaranteed.** Also state the amount without it |
| Knowing the rate is enough to decide | **The no-boot-disk, multipath operation, two control planes, and the 6 HA pair ceiling do not appear in the amount** |
| The Price List API's `pricePerUnit` can be used as-is | **There are items where `unit` is `GiBps-mo` and the description is MiBps.** It is off by 1,024× |

---

### Primary sources referenced

| Point | Source |
|---|---|
| FSx for ONTAP's billing items (SSD, throughput capacity, capacity pool, backup) and the structure of the rates | [AWS: Amazon FSx for NetApp ONTAP pricing](https://aws.amazon.com/fsx/netapp-ontap/pricing/) |
| EBS rates per volume type, and the 3,000 IOPS / 125 MB/s included in `gp3` | [AWS: Amazon EBS pricing](https://aws.amazon.com/ebs/pricing/) |
| Where the rates were obtained | AWS Price List API (`AmazonFSx` / `AmazonEC2`, `ap-northeast-1`, obtained 2026-09-05) |
| That the Price List API endpoints are limited to `us-east-1` and `ap-south-1` | [AWS: Using the AWS Price List Query API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html) |
| The SSD and throughput-capacity lower bounds for a 2nd-generation 1 HA pair | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) |
| The conditions for attaching an EBS volume to multiple instances | [AWS: Attach a volume to multiple instances](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volumes-multi.html) |
| That FlexClone makes a writable copy without copying actual data | [NetApp: FlexClone volumes](https://docs.netapp.com/us-en/ontap/volumes/create-flexclone-task.html) |

---

### Related documents

- [Domain — Block storage](../README.md) — this module's hub
- [Comparison of block storage options (日本語)](../../../../ja/reference/comparison/block-storage-options.md) — the symmetric trade-offs on the feature side
- [When shared block changes the design (日本語)](when-shared-block-changes-the-design.md) — the part that changes by structure, not rate
- [The 30-minute block storage quickstart](../quickstart.md) — build the floor configuration as-is and check it
- [Provisioned capacity versus consumed capacity](../../cost/notes/provisioned-versus-consumed.md) — the difference between provisioned and consumed
- [Capacity is counted in three places](capacity-is-counted-in-three-places.md) — how much of the provisioned GB can be placed
- [Evidence policy](../../../evidence-policy.md)

## Verify it in your environment

**Rates are revised. Do not bring the numbers in this table into a design.**

| # | Step | What you get |
|---|---|---|
| 1 | Fetch the SSD and throughput-capacity rates for your region with `aws pricing get-products --service-code AmazonFSx --region us-east-1 --filters ...` | The two rates needed for the floor calculation. **The Price List API endpoints are only `us-east-1` and `ap-south-1`** |
| 2 | Fetch `AmazonEC2` Storage for `volumeApiName=gp3` the same way | The rate to compare against |
| 3 | Check whether the units of `unit` and `description` match | **There are items that are off by 1,024× if you look at `pricePerUnit` alone** |
| 4 | Count your dataset size D and copy count C | The two values to put in the formula above |
| 5 | Add the GB of Snapshots held on the EBS side | The actual EBS-side monthly cost |
| 6 | If you count on deduplication / compression, **also state the amount without it** | The upper bound when no reduction materializes |
| 7 | If there is one copy, stop there | **In that configuration the rate does not flip** |

The rate in step 1 is re-fetched with this read-only command (the Price List API endpoints are `us-east-1` / `ap-south-1` only).

```bash
aws pricing get-products --region us-east-1 --service-code AmazonFSx \
  --filters "Type=TERM_MATCH,Field=regionCode,Value=<your-region>" --max-results 20
```

### Expected output

```text
The SSD and throughput-capacity rates are returned. Reconcile the unit (e.g. MiBps-Mo) with the
description before calculating (there are items off by 1,024x if you read pricePerUnit alone).
83% of the floor is throughput capacity.
```

This command only reads a public rate; it changes nothing on billing or resources. Because the numbers are revised, re-fetch them at every decision point.

## Read next

[Do the contents of a LUN surface to file protocols?](lun-contents-do-not-reach-file-protocols.md)
