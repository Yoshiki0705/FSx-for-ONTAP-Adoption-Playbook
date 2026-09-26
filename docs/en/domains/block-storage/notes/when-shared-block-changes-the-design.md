---
title: When shared block changes the design — if a single attachment is enough, there is no reason to bring it in
lifecycle: [assess, design]
domains: [block-storage, cost, performance]
evidence: documented
source: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volumes-multi.html
lang: en
---

# Under what conditions does shared block change the design?

None, if a single attachment is enough. It matters under four conditions where structure is required.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/when-shared-block-changes-the-design.md) | [English](when-shared-block-changes-the-design.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That the reason to choose FSx for ONTAP for block is structure, not speed, and that Amazon EBS is the straightforward choice for a single attachment
- The four conditions where structure matters (file coexistence, generation-unlimited Snapshot, cross-region replication, copy-free replicas), placed alongside FSx for ONTAP's own symmetric trade-offs

## What this note does not answer

- A performance comparison between FSx for ONTAP and Amazon EBS (only how to read a published benchmark; no figures held here)
- This repository's own verification of the products that carry write arbitration (a record of where support is stated, not a verification)

## Prerequisite level

intermediate

## Body

<a id="under-what-conditions-does-shared-block-change-the-design"></a>

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

---

### Conclusion

**The reason to choose FSx for ONTAP as block storage is structure, not speed.** And for requirements where structure does not matter, Amazon EBS is the straightforward choice.

**There is no reason to assign FSx for ONTAP to a disk used by a single EC2 instance alone.** Even the minimum configuration provisions 1,024 GiB of SSD and 384 MBps of throughput capacity, coming to about $927 a month on-demand in the Tokyo region. That does not balance against a data area of a few dozen GiB. **This is a judgment about storage unit price, and its conclusion is limited to the band from a few dozen GiB to a few TiB of data.** As required throughput capacity increases, the cost of Amazon EBS's replication and standby side accumulates, so at larger capacity bands the unit-price ranking can flip (see [the recalculation procedure by capacity band in a sibling project](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP/blob/main/docs/ja/tco-comparison.md)).

**Structure matters when your requirements include the following five.**

1. Serving the same data **also as a file share**
2. Wanting to keep Snapshots **without worrying about generation count**
3. Wanting to **replicate data containing a LUN to a different region**
4. Wanting to create a production replica **without copying the actual data**
5. **Needing to keep data across an AZ failure, without wanting to build the replication and failover mechanism yourself**

And FSx for ONTAP's own trade-offs are placed with the same weight. **There is a 6-HA-pair ceiling, host-side multipath and write consistency remain the user's responsibility, and there are two control planes: AWS and ONTAP.**

> **Tier**: `documented` — the constraints and limits of each service are based on AWS / NetApp official documentation (confirmed 2026-09-05). Minimum-configuration cost was obtained from the Price List API on the same day. The [Products that carry the host-side clustering function](#products-that-carry-the-host-side-clustering-function) section is based on vendor announcements and an AWS blog, **added 2026-09-15**.
> **No performance comparison is included.** How to read published figures is in [Reading a published benchmark](#reading-a-published-benchmark).
> The steps to confirm in your own environment are in [Verify it in your environment](#verify-it-in-your-environment).

---

### Deciding when a single attachment is enough

**"Block storage is needed" is not the same as "shared block is needed."** Considering FSx for ONTAP without separating these produces an over-built configuration relative to the requirement.

| Requirement | Straightforward choice | Reason |
|---|---|---|
| Boot disk | Amazon EBS | **An FSx for ONTAP LUN cannot be a boot disk.** The block protocol is established only after the guest OS boots |
| A data area dedicated to one instance | Amazon EBS | No shared arbitration and no file share are needed, and the control plane is EC2 alone |
| Temporary scratch space | Instance store | Fastest if persistence is not required, with no added cost |
| A same-AZ 2-node cluster where Snapshot can be host-side | Amazon EBS Multi-Attach | The EC2 control plane alone suffices. `io2` supports I/O fencing via NVMe reservations |
| A single EC2 instance, but data must survive an AZ failure | Decided by capacity band and whether you carry the four items below yourself | **Amazon EBS has no native cross-AZ block replication.** Meeting this requirement on EBS means building everything yourself: a volume attached in two or more AZs, replication software, and a failover mechanism. **FSx for ONTAP Multi-AZ provides two things as an AWS managed service: synchronous replication of writes across AZs, and automatic failover when one AZ becomes unavailable.** Replication is real-time (synchronous), and no self-managed cross-AZ data-transfer fee is incurred on the EBS side either (it is included in the throughput-capacity price). **An AZ failure is explicitly documented as one of the conditions that triggers Multi-AZ's automatic failover, and failover, as well as failback, normally completes in under 60 seconds.** Which is cheaper per unit depends on required throughput capacity and is not fixed by a constant |

The four items that fall to the self-managed side are: the running cost of a standby EC2 instance, replication-software licensing plus build and operations, a failover mechanism (Amazon EBS's SLA carries an exclusion clause for not switching to the recovery volume), and, if replication is asynchronous, the resulting RPO. Because these do not scale with capacity, at smaller data volumes the judgment that EBS has the lower unit price coexists with the separate cost of carrying the mechanism yourself.

**When migrating block storage with AWS Transform, too, the boot volume stays on EBS and the data volume connects over iSCSI.** This division remains unchanged after migration. Details are in [Recent updates and their design impact (日本語)](../../../../ja/reference/recent-updates.md).

---

### The four conditions where structure matters

#### File and block being served from the same storage

**NFS, SMB, iSCSI, NVMe/TCP, and S3 Access Points can all be served simultaneously from the same file system and SVM.** A configuration where the same dataset is presented to an analytics platform over NFS and to a database over a LUN can be built on one box.

**But at volume granularity the picture changes.** NetApp **does not recommend mixing SAN LUNs and NAS shares in the same FlexVol.** Not because it is technically impossible, but because capacity accounting and Snapshot handling differ between the two. **"One box can serve both" is correct; "serving both from one volume is normal" is not.**

#### Snapshot consuming already-provisioned capacity

FSx for ONTAP's Snapshot **consumes SSD capacity you have already provisioned. It is not a separate billing line.** Amazon EBS's Snapshot is billed separately per GB-month.

**In a design keeping many generations, this difference accumulates.** On the other hand, **the fact that it consumes capacity does not go away.** A different failure path appears when the SSD fills up and a LUN drops to read-only, which is covered in [Capacity is counted in three places](capacity-is-counted-in-three-places.md).

#### SnapMirror operating per volume

**A volume containing a LUN can be replicated to a different file system as-is.** Because it bypasses the host, the application does not need to be stopped for replication.

**The LUN is not usable as-is on the destination.** After making the destination volume writable, you need to **map the LUN into an igroup, establish an iSCSI session from the host, and rescan.** **The igroup mapping does not travel with the data.**

#### FlexClone not copying actual data

**A writable replica of a production LUN can be created without copying the actual data.** On Amazon EBS you would create a new volume from a Snapshot, which does involve a copy.

AWS states, in the context of SQL Server, that **cloning a 1 TB database's iSCSI LUN typically completes within 5 minutes.** This figure depends on configuration, though.

---

### FSx for ONTAP's own trade-offs

**Placed with the same weight as the four above.** If none of these requirements applies to you, they are costs you do not need to pay.

| Trade-off | Content | Escape route |
|---|---|---|
| **The 6-HA-pair ceiling** | Only file systems with 6 or fewer HA pairs support iSCSI, and NVMe/TCP additionally requires second generation. **The transition behaviour when adding a 7th pair is not documented** | Design with 6 pairs as the ceiling. An added HA pair cannot be deleted. Details in [The deployment type is decided only once (日本語)](../../../playbooks/02-design/notes/deployment-type-is-decided-once.md) |
| **Host-side multipath responsibility** | Configuring paths, tuning timeouts, and confirming failover are host-side work | The procedure is documented. [Paths are the failover mechanism itself](paths-are-the-failover-mechanism.md) |
| **Write-consistency responsibility** | When multiple hosts write to the same LUN, arbitration is done by a host-side clustering function | The same is true of Amazon EBS Multi-Attach. **A property common to shared block.** Options for who carries this are in [Products that carry the host-side clustering function](#products-that-carry-the-host-side-clustering-function) |
| **Two control planes** | The LUN, igroup, and NVMe subsystem do not exist in the AWS API | [LUNs and igroups are outside the AWS API](block-objects-are-outside-the-aws-api.md) |
| **The default Snapshot is crash-consistent** | A mechanism to quiesce the application is needed separately | [A snapshot of a LUN is crash-consistent by default](a-snapshot-of-a-lun-is-crash-consistent.md) |
| **The minimum configuration's cost** | 1,024 GiB of SSD + 384 MBps of throughput is the floor | Use Amazon EBS for smaller requirements |
| **NVMe/TCP is second generation only** | On first generation there is no path but a rebuild. **NVMe/TCP with Windows Server is unsupported on the ONTAP side** | [The block protocol choice is narrowed first by generation and HA pair count](protocol-choice-is-bounded-before-you-choose.md) |
| **The deployment type cannot be changed after creation** | Both Quick create and Standard create default to Multi-AZ 2 (second generation) in the Tokyo region. Generation and AZ topology are separate axes; Single-AZ 2 is also second generation | [The deployment type is decided only once (日本語)](../../../playbooks/02-design/notes/deployment-type-is-decided-once.md) |
| **Throughput is shared per HA pair** | It shares the same bandwidth pool with NFS, SMB, and S3 Access Points | [Throughput is not decided by a single setting](../../performance/notes/where-throughput-is-determined-and-shared.md) |

---

### Products that carry the host-side clustering function

**The "write-consistency responsibility" row above states where the responsibility sits, not who carries it.** Designing with that cell left blank leaves you having chosen shared block without having decided who implements the arbitration.

There are three kinds of carrier. **Whichever you choose, arbitration remaining host-side does not change.**

| Carrier | Content |
|---|---|
| A mechanism bundled with the OS | Windows Server Failover Clustering, Linux's Pacemaker, and similar |
| A cluster filesystem | Needed when multiple hosts use it simultaneously as a filesystem |
| Third-party clustering software | Takes on monitoring, switchover, and resource-dependency definitions as well |

**Among the third kind, one has published support for the combination with FSx for ONTAP.**

For SIOS LifeKeeper, the vendor has announced **providing support starting 2024-11-28**, with the stated scope being **iSCSI and NFS for the Linux version, iSCSI for the Windows version** (LifeKeeper for Linux ver.9.9.0 / LifeKeeper for Windows ver.8.10.1). AWS also has a Prescriptive Guidance blog post on the AWS side.

**This statement is about where support is published; it is not a verification result from this repository.** Confirm the vendor's current information for the version combination and supported protocols at the time of selection.

**For other candidates, there is a range this side has not been able to reach.** Among products that come to mind for the same problem area from a Japan-based environment, **for some this side has not reached an FSx-for-ONTAP-specific statement of support** (searched 2026-09-15). Not being able to reach one does not mean it is unsupported. The investigation state is recorded in [ISV / SaaS options map by issue](../../../reference/isv-solution-map.md#candidates-that-did-not-meet-the-bar).

---

### Reading a published benchmark

**The most frequently cited figure about FSx for ONTAP's block performance is "one million IOPS." This figure is not for a single file system.**

The AWS Storage Blog post [SAN: A million IOPs in AWS from Amazon FSx NetApp ONTAP](https://aws.amazon.com/blogs/storage/san-a-million-iops-in-aws-from-amazon-fsx-netapp-ontap/) is dated 2022-09-08, and its measurement conditions are as follows. <!-- allow:naming - exact article title -->

| Item | Content |
|---|---|
| Number of file systems | **10** (Single-AZ), used in parallel |
| Configuration per unit | About 5.3 TB of SSD, **80,000 provisioned SSD IOPS**, 2 GB/s throughput |
| Tiering policy | Snapshot Only. **All block I/O served from SSD** |
| Client side | 10 iSCSI LUNs **bundled into a single logical volume with LVM and used from a single client** |
| Instance | i3 / m6 / X2 families, RHEL-family AMIs (documented as designed around an RHEL 8.2 base) |
| Load generation | FIO (random read / write / mixed / throughput) |
| Results stated | Sub-millisecond average latency for small-block random I/O, large-block read using 100% of the client's network, large-block write of about 7.5 GB/s |

**The article itself states four caveats.**

| Caveat | Content |
|---|---|
| Single-unit ceiling | At the time, a single file system's ceiling was "several hundred thousand IOPS" and 2 GB/s |
| Cache effect | If the workload fits in cache, **measured IOPS can exceed the provisioned IOPS** |
| SSD sizing | **Deliberately sized so the entire 2 TB volume plus room for Snapshots fits on SSD** |
| Snapshot consistency | **Snapshotting across 10 units requires a coordination script**, and application consistency needs host-side involvement |

**And the figures themselves are now dated.** The article's [Japanese version](https://aws.amazon.com/jp/blogs/news/san-a-million-iops-in-aws-from-amazon-fsx-netapp-ontap/) carries a translator's note stating that by the time of translation, a single file system's ceiling had risen to **160,000 IOPS / 4 GB/s**. See [Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) for the current ceiling.

**What should be drawn from this article is method, not the figure.**

| Transferable method | Content |
|---|---|
| Land it on SSD | Set tiering to Snapshot Only, and fix whether the measurement target is served from the cache tier or the capacity pool |
| State how units were bundled | If multiple file systems were bundled with LVM, that is not one unit's performance |
| Isolate the cache effect | A value exceeding provisioned IOPS is a cache-hit contribution |
| Count consistency separately | In a bundled configuration, Snapshot consistency appears as a separate problem |

**This repository's note holds no performance figures.** Verification was limited to confirming behaviour on a minimum 384 MBps configuration; throughput and IOPS were not measured. If you need figures, measure in your own environment matching the conditions above. Benchmark design itself is in [What a reproducible benchmark requires](../../performance/notes/what-you-cannot-read-from-cloudwatch.md#what-a-reproducible-benchmark-requires).

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| Needing block storage means needing shared block | These are separate requirements. **Amazon EBS is the straightforward choice for a single attachment** |
| An FSx for ONTAP LUN can be a boot disk | **It cannot.** The block protocol is established only after the guest OS boots |
| The million-IOPS figure came from a single file system | It is **10 units bundled with LVM**; the single-unit ceiling at the time was 80,000 IOPS |
| A published benchmark's figure can be used as-is as a design value | It will not reproduce unless the tiering policy, SSD sizing, instance, and block size all match |
| Snapshot not being separately billed means capacity does not need attention | **It consumes provisioned SSD.** A full SSD drops the LUN to read-only |
| Replicating with SnapMirror makes the LUN usable as-is on the destination | **A LUN map, an iSCSI session, and a rescan are needed on the destination.** The igroup does not travel |
| Mixing file and block in one volume is normal | Both can be served from the same file system and SVM. **Mixing them in the same FlexVol is not recommended** |
| Choosing shared block lets multiple hosts write safely | **Arbitration is the host's responsibility.** The same is true of Amazon EBS Multi-Attach |

---

### Primary sources referenced

| Point | Source |
|---|---|
| Multi-Attach's 16-instance limit, same-AZ requirement, Nitro requirement, boot-disk exclusion, cluster-filesystem requirement, and `io2`'s I/O fencing | [AWS: Attach an EBS volume to multiple EC2 instances using Multi-Attach](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volumes-multi.html) |
| The million-IOPS measurement conditions (10 file systems, 80,000 IOPS / 2 GB/s per unit, LVM, FIO, Snapshot Only tiering) and its four caveats | [AWS Storage Blog: SAN: A million IOPs in AWS from Amazon FSx NetApp ONTAP](https://aws.amazon.com/blogs/storage/san-a-million-iops-in-aws-from-amazon-fsx-netapp-ontap/) <!-- allow:naming - exact article title --> |
| That by the time of translation the single-file-system ceiling had risen to 160,000 IOPS / 4 GB/s | [The same article's Japanese version](https://aws.amazon.com/jp/blogs/news/san-a-million-iops-in-aws-from-amazon-fsx-netapp-ontap/) |
| Second generation 1-HA-pair minimum throughput of 384 MBps and minimum SSD of 1,024 GiB, and current IOPS / throughput ceilings | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) |
| Volumes being thin provisioned, and capacity returning when data inside a LUN is deleted | [AWS: How FSx for ONTAP works](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/how-it-works-fsx-ontap.html) |
| Mixing SAN LUNs and NAS shares in the same FlexVol not being recommended | [NetApp: SAN volumes](https://docs.netapp.com/us-en/ontap/volumes/san-volumes-concept.html) |
| SnapMirror destinations needing a LUN map, an iSCSI session, and a rescan | [NetApp: Destination volume data access](https://docs.netapp.com/us-en/ontap/data-protection/configure-destination-volume-data-access-concept.html) |
| A 1 TB database's iSCSI LUN clone typically completing within 5 minutes | [AWS: Using SnapCenter to protect SQL Server workloads](https://aws.amazon.com/blogs/storage/using-netapp-snapcenter-with-amazon-fsx-for-netapp-ontap-to-protect-your-sql-server-workloads) |
| iSCSI being supported up to 6 HA pairs, NVMe/TCP up to 6 pairs on second generation | [AWS: Accessing your FSx for ONTAP data](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-fsx-clients.html) |
| Published support for a third-party clustering software combination (starting 2024-11-28, Linux version iSCSI and NFS, Windows version iSCSI) | [Vendor announcement](https://sios.jp/news/info/2024/20241128_lk-fsx.html) · [AWS Prescriptive Guidance blog](https://aws.amazon.com/jp/blogs/psa/high-availability-solution-with-sios-lifekeeper-and-amazon-fsx-for-netapp-ontap/) (both confirmed 2026-09-15) |
| The unit-price comparison of a 2-AZ EBS configuration and FSx for ONTAP Multi-AZ for an AZ-failure requirement, and the crossover point depending on required throughput capacity rather than being a constant | [The recalculation procedure by capacity band in a sibling project](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP/blob/main/docs/ja/tco-comparison.md) — the figures there are that sample configuration's list-price calculation, not a production estimate |
| Multi-AZ's standby being placed in a separate AZ from the active side with writes synchronously replicated across AZs, an AZ failure being one of the conditions triggering automatic failover, and failover / failback normally completing in under 60 seconds | [AWS: Availability, durability, and deployment options](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/high-availability-AZ.html) |
| Cross-AZ replication transfer fees for a Multi-AZ file system being included in the throughput-capacity price | [AWS: Amazon FSx for NetApp ONTAP Pricing](https://aws.amazon.com/fsx/netapp-ontap/pricing/) |

---

### Related documents

- [Domain — Block storage](../README.md) — this module's hub
- [Comparison: block storage options (日本語)](../../../../ja/reference/comparison/block-storage-options.md) — the comparison-table version of this decision
- [Decision tree: block protocol and layout (日本語)](../../../../ja/reference/decision-trees/block-protocol-and-layout.md) — the decision after this one
- [The block protocol choice is narrowed first by generation and HA pair count](protocol-choice-is-bounded-before-you-choose.md) — the generation and HA-pair constraints
- [Capacity is counted in three places](capacity-is-counted-in-three-places.md) — how a Snapshot consumes capacity
- [Throughput is not decided by a single setting](../../performance/notes/where-throughput-is-determined-and-shared.md) — sharing per HA pair
- [What a reproducible benchmark requires](../../performance/notes/what-you-cannot-read-from-cloudwatch.md#what-a-reproducible-benchmark-requires) — measurement design
- [Block storage cross resource map (日本語)](../../../../ja/reference/block-storage-resource-map.md) — index of primary sources
- [ISV / SaaS options map by issue](../../../reference/isv-solution-map.md) — the index of products carrying arbitration, and the range this side has not reached
- [Evidence policy](../../../evidence-policy.md)

---

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

## Verify it in your environment

| # | Step | What it tells you |
|---|---|---|
| 1 | Count the hosts that will use a block device simultaneously | 1 means Amazon EBS suffices |
| 2 | Confirm whether there is a requirement to also serve the same data as a file share | Whether structure condition 1 applies |
| 3 | Estimate the number of Snapshot generations you want to keep and the change volume per generation | The effect of structure condition 2, and the impact on SSD capacity |
| 4 | Confirm the replication requirement to a different region and the RPO | Whether structure condition 3 applies |
| 5 | Confirm whether you need to cross AZs | **Amazon EBS Multi-Attach is same-AZ only,** so crossing removes it from consideration |
| 6 | Confirm whether there is a plan to grow to 7 or more HA pairs | **If there is, block cannot be used** |
| 7 | Estimate the minimum configuration's monthly cost on the current pricing page and compare it against your data volume | Whether you are over-building |

The current HA pair count in step 6 can be confirmed with this read-only command.

```bash
aws fsx describe-file-systems --file-system-ids <fs-id> \
  --query 'FileSystems[0].OntapConfiguration.HAPairs'
```

### Expected output

```text
Returns the current HA pair count. If it is at 6, that is the support ceiling for iSCSI /
NVMe-TCP, and if there is a plan to add a 7th pair, block cannot be used (an added HA pair
cannot be deleted).
```

This command only reads the file system's configuration; it changes nothing on the HA pairs or the volumes.

## Read next

[Where does EBS stop being the cheaper answer?](when-ebs-stops-being-the-cheaper-answer.md)
