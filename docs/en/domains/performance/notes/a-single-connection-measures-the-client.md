---
title: A figure measured over a single connection is not the storage's performance — similar numbers can be hitting different ceilings
lifecycle: [assess, design, optimize]
domains: [performance, cost]
evidence: documented
source: https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md
lang: en
---

# A figure measured over a single connection is not the storage's performance

[🏠 Repository home](../../../README.md) | [Domain — Performance](../README.md)

---

## Conclusion

**A figure measured over one mount is not the storage's performance.** What it hits is some other ceiling, on the client or on the service, and **which ceiling differs per product.**

In a sibling project's measurements, **three configurations across different products and different protocols all landed between 499.79 and 591.62 MB/s over a single connection.** The numbers are close; **the ceilings they hit were not the same.**

| Single-connection measurement | The ceiling being hit |
|---|---|
| FSx for ONTAP NFS 591.62 MB/s (4.7 Gbps) | **EC2's 5 Gbps full-duplex per network flow** |
| FSx for ONTAP SMB 574.24 MB/s (4.6 Gbps) | The same |
| Amazon EFS, plain mount, 499.79 MB/s | **EFS's 500 MiBps per-client throughput quota** |

**The cited source initially explained all three rows as "EC2's per-flow ceiling" and has since corrected the EFS one.** 499.79 MB/s matches 500 MiBps, not 5 Gbps (625 MB/s). **Bundling close numbers as one cause leads to the wrong remedy.** EC2's per-flow ceiling is passed by adding connections; a service-side per-client quota is not.

**Adding connections splits the ceiling into two stages.** If the data being read returns from the file server's cache, the network ceiling binds; if it is not in cache, the disk ceiling does. **Which one binds is decided by the working set against the cache, not by the product, the generation, or the protocol.**

**Because the ceilings differ, the 1.18x between two products over a single connection is a ratio between two different ceilings.** It is not a ratio of product speed.

**And the same configuration varied by 45% under the same conditions.** The same settings, the same parameter file and the same tool, measured twice: 3,551.18 and 5,148.56 MB/s. The only difference was what remained in cache.

**One conclusion follows. This file system's throughput cannot be written as a single number.** Writing it means stating the connection count, whether data is shared, and how warm the cache was.

> **Tier**: `documented` — the figures are cited from [the per-protocol measurement results in S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md). **They were not re-measured in this repository.** The division of labour is in [the cross-repository citation index](../../../../ja/reference/cross-repo-index.md) (日本語).
> **The cited source's test environment has been deleted.** The procedure for rebuilding it remains there.

---

## Measurement conditions

**A figure without its conditions is unusable.** The following is what the cited source records, transcribed.

| Item | Value |
|---|---|
| Measured | 2026-09-05 |
| Region | `ap-northeast-1`, single AZ, **every target and every client in the same subnet** |
| ONTAP | 9.18.1P5 |
| FSx for ONTAP | Second generation `SINGLE_AZ_2`, **6,144 MBps × 1 HA pair**, 4,096 GiB SSD, 200,000 provisioned IOPS |
| NVMe read cache | **Disabled** (confirmed on both nodes) |
| `tcp-max-xfer-size` | **Raised to 1,048,576. Left at the default 65,536, `rsize` is cut back to 64 KiB** |
| Volumes | 900 GiB / UNIX for NFS, 900 GiB / NTFS for SMB. No tiering, no inline efficiency |
| Test data | Uncompressed. 600 GiB for FSx for ONTAP, 300 GiB for Amazon EFS |
| Clients | `c5n.9xlarge` (the same type for both Linux and Windows). Its 50 Gbps network is a guaranteed figure |
| Tool | VDBENCH 5.04.07, 512 threads of parallelism |

**The SSD is 4,096 GiB for the IOPS, not for the capacity.** Reduce it and what is being measured changes.

---

## The numbers that converge over a single connection

1 MiB sequential reads.

| Configuration | Connections | Throughput | Response time |
|---|---|---|---|
| FSx for ONTAP NFSv4.1, `nconnect=16` | 16 | **3,551–5,149 MB/s** | 144.18 / 99.44 ms |
| FSx for ONTAP SMB 3.1.1, Multichannel enabled | 4 | 2,227.61 MB/s | 229.78 ms |
| Amazon EFS, through the mount helper | 1 + proxy | 1,495.82 MB/s | 342.28 ms |
| FSx for ONTAP NFSv4.1, no `nconnect` | 1 | 591.62 MB/s | 865.40 ms |
| FSx for ONTAP SMB 3.1.1, Multichannel disabled | 1 | 574.24 MB/s | 891.60 ms |
| Amazon EFS, plain `mount -t nfs` | 1 | 499.79 MB/s | 1,024.41 ms |
| Amazon EFS, `nconnect=16` | — | **I/O stalled; not measurable** | — |

**The bottom three rows are close in value and hit different ceilings.** The mapping is in the table under [Conclusion](#conclusion). **The two FSx for ONTAP rows hit EC2's per-flow ceiling; the Amazon EFS row hits EFS's per-client quota.**

**Three cautions on reading the table.**

1. **The top three rows and the bottom three have different connection counts, so this is not a table from which to read product superiority.**
2. **The range on the top row is a difference in cache state, not measurement error** (below).
3. **The mount-helper row is not a single-flow measurement.** It goes through a local proxy, so the connection count is "1 + proxy". **The cited source records that this 3x appears only in EFS Elastic mode and was 1.00x in Provisioned mode.** Being mode-dependent, it cannot be placed alongside single-connection comparisons.

On Amazon EFS's `nconnect=16` being unmeasurable, **the cited source reproduced the behaviour and records it as a property cached per server on the client side.** It is a mount-option combination, not a statement about the product's bandwidth. Read the cited source for the detail.

---

## The two-stage ceiling

**After connections are added there are two ceilings, and both are explained when checked against the published figures.**

| Path | Published figure (this configuration) | Measured | Achieved |
|---|---|---|---|
| Network (reads returning from cache) | 12,500 MBps (baseline, no burst) | 12,763 MBps | **102%** |
| Disk (reads not in cache) | 3,072 MBps | 2,411 MBps | 78% |

**The 12,763 MBps on the network side is the figure from ONTAP's port counters.** With 8 clients and 128 connections the cited source records 11,916.29 MB/s totalled on the client side against 12,173.0 MiB/s measured at the port, **and 12,763 is that converted to MB/s.** Why it exceeds the published baseline by 2% is not explained there either. **A client-side total and a port-side total are different figures; do not mix them up when reconciling.**

**What deserves attention is that this configuration's throughput capacity is 6,144 MBps.** The network baseline is 12,500 MBps, **a different number from the throughput capacity setting.** What the throughput capacity setting does determine is in [Throughput is not set by one value](where-throughput-is-determined-and-shared.md).

**Which ceiling binds changed with whether the data was shared.** Measured with 8 clients and 128 connections.

| 8 clients, 128 connections | Total | Ratio |
|---|---|---|
| Every client reads the same file | 11,916.29 MB/s | — |
| Each client reads a non-overlapping region | 2,173.37 MB/s | **0.18x** |

**The only difference is whether the data is shared.** Shared, one disk read satisfies every client. AWS also states that **SSD IOPS are consumed only when accessing data that is not in the file server's memory or NVMe cache.**

**The same file system, the same workload shape and the same connection count differ by 5.5x.** A performance requirement written only in MB/s does not say which of those two it means.

---

## What the 45% range actually is

**The same settings, the same parameter file and the same tool, measured twice: 3,551.18 and 5,148.56 MB/s.** The only difference was what remained in cache.

**This is not a benchmark reproducibility problem; it is a property of this storage.** Whether a read returns from cache changes which ceiling stage binds, so **the order of measurement and what was read immediately before decide the result.**

| Countermeasure | Detail |
|---|---|
| Measure with the cache out of the way | **Disable the NVMe read cache.** The cited source does. **AWS also recommends disabling it at high throughput** |
| Make the working set larger than the cache | Total test data scales with the number of servers. It is decided by both the client count and the file size |
| Record the state before measuring | Without recording what was read immediately before, the second run cannot be compared with the first |
| Report a range | **Reporting a single point is indistinguishable from having picked the convenient side** |
| **Use incompressible test data** | **Reading a file written from `/dev/zero` never reaches disk.** The measurement above used incompressible data; with compressible data, something that looks like a cache difference comes from another cause (below) |

**That last row comes from a case where figures explained as a cache difference were withdrawn.** A sibling repository recorded a file-path read as warm 1,164.1 / cold 751.0 MB/s — a ratio of 1.55 — and **later retracted both** ([S3 Files compared with this architecture](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/s3files-vs-flexcache.md) (日本語)). Both were reads of files written from `/dev/zero`, and **ONTAP returns zero blocks without going to disk.** With the same configuration and the same intervening volume, changing only the data to incompressible produced **warm 297.8 against cold 297.2, a ratio of 1.00: no warm-versus-cold difference existed.**

**The surviving conclusion is that the figure is not this file system's read performance — but the reason changed places.** Not "a warm cache was being measured" but **"read performance was not being measured at all."** **Confirm the test data is incompressible before attributing a difference to cache warmth.** With compressible data, the two runs may not be taking the same path.

---

## How to write a performance requirement

**A requirement stating only MB/s cannot be settled once these measurements are in view.** These are the items to decide.

| To decide | What happens if you do not |
|---|---|
| The connection count (`nconnect`, or the SMB Multichannel channel count) | **On FSx for ONTAP a single connection stops at around 5 Gbps.** Change product and the ceiling changes too |
| Whether data is shared, or each host reads its own region | **5.5x under the same conditions** |
| The working set against the cache | It changes which ceiling stage binds |
| Block size and parallelism | The cited source measured at 1 MiB with 512 threads |
| The client instance type | **`c5n.9xlarge`'s 50 Gbps is a guaranteed figure.** On a burstable type, what is being measured is the client |
| `tcp-max-xfer-size` | **Left at the default, `rsize` is cut back to 64 KiB** |

**The first thing to raise is the connection count.** It moved from 591.62 MB/s with no `nconnect` to 3,551–5,149 MB/s with `nconnect=16`. **It was the single setting that moved the figure most.**

---

## What the cited source records as unmeasured

**A citation can take only the convenient part.** What the cited source lists as unmeasured, transcribed.

| Case | State |
|---|---|
| Re-measurement with cache state equalised | **Unmeasured. Named there as the most valuable thing for collapsing the 45% range above** |
| The generational difference between first and second (NFSv4.1 held constant) | Unmeasured |
| Comparing the same data over the S3 API and over NFS | Unmeasured |
| One and six clients in the non-overlapping-region client-count test | Unmeasured (2, 4 and 8 were measured) |
| The conditions for raising the SMB Multichannel channel count above 4 | Unmeasured (it was still 4 with `max_connections_per_session=32`) |
| Why 64 KiB sequential reads are slower than 64 KiB random reads | Unmeasured |

**The test environment has been deleted.** The procedure for rebuilding it is in the cited repository.

---

## What a block figure would need before it joins this table

**The block protocol figures (iSCSI, NVMe/TCP) have since been measured.** At a multiplicity of one, iSCSI reached 1,135.19 MB/s and NVMe/TCP 1,135.88 MB/s ([Paths are the failover mechanism](../../../../ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md#ブロックが同じ位置に来なかったこと) (日本語)). **They are still not placed in the table above.** Placing one there requires **two conditions to travel with it,** and both work in block's favour, so **dropping them invites the difference being misread as a protocol difference.**

| Condition | In the file-side measurement | What to expect for block |
|---|---|---|
| **The number of paths** | Every byte went through one port (the other measured zero) | Both nodes' LIFs are used, so **it spreads across two nodes by default** |
| **Whether a file system layer is present** | It goes through the page cache and the metadata path | A raw device with `o_direct` goes through **neither** |

**So reading it as "block is faster" includes the effect of twice the paths and no file system layer.** That is not a protocol difference.

**A comparison between iSCSI and NVMe/TCP, on the other hand, holds cleanly.** The same host, the same OS, the same `openflag` and the same LIF leave a single parameter line as the difference.

**The measurement did not land where that expectation put it.** 1,135 MB/s is roughly 1.8× the EC2 single-flow ceiling of 625 MB/s, so **it does not belong in a comparison premised on landing in the same place.** The table above therefore still has three rows, and **the position that the protocol choice is settled by generation and HA pair count before performance enters is unchanged.**

**The decision not to add a row was made before the measurement ran.** The cited source split the possible outcomes for a single flow four ways and tabulated, **in advance,** how the table above would be rewritten in each case ([Block protocol measurement plan](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/block-protocol-matrix-plan.md) (日本語)). **Deciding after measuring allows the wording to be chosen to suit whatever number came out.**

> **Do not treat landing in the same range as evidence of the same cause.** The point of the table above is not the range but that similar values arise from different ceilings. **The cited source got this wrong once, for EFS, and corrected it** ([Conclusion](#conclusion)). If a block figure lands in the same range, whether the EC2 single-flow ceiling is the cause has to be confirmed separately.

## Verify in your own environment

**Do not target the cited source's numbers.** A different configuration hits a different ceiling.

| # | Step | What it establishes |
|---|---|---|
| 1 | Count the mount's connections (the `nconnect` value; for SMB, `Get-SmbMultichannelConnection`) | **On FSx for ONTAP a single connection stops at around 5 Gbps.** On other services a service-side quota can bind first |
| 2 | `nfs show -vserver <svm> -fields tcp-max-xfer-size` | **At the default 65,536, `rsize` is cut back** |
| 3 | Compare the working set size against the file server's cache | Which ceiling binds |
| 4 | Run the same measurement twice back to back and look at the difference | **The range from cache warmth. One run does not show it** |
| 5 | Measure with one client and with several, and reconcile against ONTAP's physical port counters | **A client-side total is not evidence** |
| 6 | Measure the case where every client reads the same data separately from the case where they read non-overlapping regions | Which side of the 5.5x you are on |
| 7 | Check whether the client's network figure is guaranteed or burstable | **On a burstable type, what is being measured is the client** |

Step 5 is what the cited source does. **A client-side total alone cannot isolate where the constraint is.**

---

## Common misconceptions

| Misconception | Actually |
|---|---|
| Measuring over one mount shows the storage's performance | **It measures some other ceiling, on the client or the service.** Which one differs per product |
| Close numbers mean the same cause | **Three configurations landed between 499.79 and 591.62 MB/s, but the two FSx for ONTAP figures hit EC2's per-flow ceiling and the EFS one hit a 500 MiBps per-client quota.** The cited source bundled them wrongly and later corrected it |
| The protocol choice decides performance | **The connection count moved it more** (591.62 to 3,551–5,149 MB/s) |
| The 1.18x between products is a product difference | **It is a ratio between two different ceilings** |
| The throughput capacity setting is the ceiling reachable | **In this configuration, 6,144 MBps was set and the network baseline was 12,500 MBps.** Different numbers |
| The benchmark varying by 45% was a measurement mistake | **It is a difference in what remained in cache.** A property of this storage |
| Adding clients scales linearly | **Whether the data is shared changes it by 5.5x** |
| Performance can be written as one number | **It cannot.** State the connection count, whether data is shared, and the cache state |
| The same configuration as the cited source yields the same number | **Not without matching the cache warmth as well** |

---

## Primary sources referenced

| Point | Source |
|---|---|
| That the three single-connection configurations were hitting different ceilings (FSx for ONTAP EC2's per-flow ceiling, EFS a 500 MiBps per-client quota), the two-stage ceiling, the 45% range, the 0.18x with 8 clients, and every measurement condition | [S3-Burst-on-ONTAP-Files: per-protocol measurement results](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md) |
| The tool used (`auto_vdbench`) and the constraint that parameters cannot be passed on the command line | [S3-Burst-on-ONTAP-Files: per-protocol throughput measurement plan](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/throughput-protocol-matrix-plan.md) |
| EC2's 5 Gbps full-duplex ceiling per network flow, and that it is passed by using multiple flows through `nconnect` or SMB Multichannel. That SSD IOPS are consumed only when accessing data not in cache | [AWS: Amazon FSx for NetApp ONTAP performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html) |
| Throughput capacity and the network baseline per generation and configuration | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) |
| The default `tcp-max-xfer-size` and how it bears on `rsize` and `wsize` | [NetApp: nfs modify](https://docs.netapp.com/us-en/ontap-cli/vserver-nfs-modify.html) |

---

## Related documents

- [Domain — Performance](../README.md) — this module's hub
- [Throughput is not set by one value](where-throughput-is-determined-and-shared.md) — what the throughput capacity setting determines, and sharing per HA pair
- [p99 is not available from volume operation-time metric pairs](what-you-cannot-read-from-cloudwatch.md) — the measuring instrument's limits, and burst credits
- [Cross-repository citation index](../../../../ja/reference/cross-repo-index.md) (日本語) — where these figures are cited from, and the division of labour
- [Reading a published benchmark](../../../../ja/domains/block-storage/notes/when-shared-block-changes-the-design.md#公開ベンチマークの読み方) (日本語) — checking the conditions behind a published figure
- [Evidence Policy](../../../evidence-policy.md)

---

[🏠 Repository home](../../../README.md) | [Domain — Performance](../README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/performance/notes/a-single-connection-measures-the-client.md) | [English](a-single-connection-measures-the-client.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
