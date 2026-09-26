---
title: Block monitoring has no LUN dimension and no protocol dimension — one LUN per volume becomes the monitoring design decision
lifecycle: [design, operate]
domains: [block-storage, performance]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
deployment_type: MULTI_AZ_2
lang: en
---

# What is invisible to block monitoring?

Neither a LUN dimension nor a protocol dimension. That is why one LUN per volume becomes a monitoring design decision.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/what-block-monitoring-shows.md) | [English](what-block-monitoring-shows.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That `AWS/FSx` in CloudWatch has neither a LUN dimension nor a protocol dimension, and that with one LUN per volume, the volume dimension substitutes for the LUN dimension
- That a volume created on the ONTAP side appears in neither CloudWatch nor AWS Backup

## What this note does not answer

- How the `FileServer` dimension behaves during a failover (not measured)
- Whether p99 can be derived from the volume operation-time metrics (average only; see a separate note)

## Prerequisite level

intermediate

## Body

<a id="what-is-invisible-to-block-monitoring"></a>

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

---

### Conclusion

**The `AWS/FSx` namespace in CloudWatch has no dimension pointing at a LUN. It has no dimension that separates protocols either.** iSCSI I/O, NVMe/TCP I/O, and NFS I/O all mix within the same metrics.

**Volume-level I/O metrics do exist, however.** So **in a configuration placing 1 LUN per volume, the volume dimension effectively becomes the LUN dimension.** This is a **monitoring-granularity reason for 1:1**, separate from the recovery-granularity argument.

**But only granularity is substituted; the kind of statistic is not.** A volume's `DataReadOperationTime` / `DataReadOperations`, `DataWriteOperationTime` / `DataWriteOperations`, and `MetadataOperationTime` / `MetadataOperations` are cumulative, and the valid statistic is `Sum`. **The latency derivable from each pair is an average; the tail cannot be obtained** (see [p99 cannot be derived from the volume operation-time metrics](../../performance/notes/what-you-cannot-read-from-cloudwatch.md)). Other volume-capacity metrics do take `Average` or `Maximum`, so we do not treat every volume metric as `Sum`-only.

**If a per-LUN figure is needed, you go to the ONTAP side.** `statistics lun show` and `lun show -fields size-used` are there.

And **a volume created on the ONTAP side does not appear in CloudWatch at all.**

> **Tier**: `verified` (verified 2026-09-05, `ap-northeast-1`, `MULTI_AZ_2` second generation, 1 HA pair, ONTAP 9.18.1P5) — the list of metrics and dimensions, the absence of ONTAP-created volumes, and the value of the `FileServer` dimension.
> **The metric list is as of the measurement point.** It can grow. Run `list-metrics` in your own environment before relying on this.

---

### Measured dimensions and metrics

`aws cloudwatch list-metrics --namespace AWS/FSx --dimensions Name=FileSystemId,Value=<fs-id>` returned **129 entries.** Organized by dimension combination:

| Dimension | Metrics |
|---|---|
| `FileSystemId` | `CPUUtilization`, `DataReadBytes` / `DataWriteBytes`, `DataReadOperations` / `DataWriteOperations`, `DataReadOperationTime` / `DataWriteOperationTime`, `DiskReadBytes` / `DiskWriteBytes`, `DiskReadOperations` / `DiskWriteOperations`, `DiskIopsUtilization`, `FileServerCacheHitRatio`, `FileServerDiskIopsBalance` / `FileServerDiskThroughputBalance`, `FileServerDiskIopsUtilization` / `FileServerDiskThroughputUtilization`, `NetworkReceivedBytes` / `NetworkSentBytes`, `NetworkThroughputUtilization`, `LogicalDataStored`, `MetadataOperations`, `MetadataOperationTime`, `StorageEfficiencySavings`, `StorageUsed`, `CapacityPoolRead*` / `CapacityPoolWrite*` |
| **`FileSystemId,FileServer`** | `CPUUtilization`, `FileServerCacheHitRatio`, `FileServerDiskIopsBalance` / `FileServerDiskThroughputBalance`, `FileServerDiskIopsUtilization` / `FileServerDiskThroughputUtilization`, `NetworkReceivedBytes` / `NetworkSentBytes`, `NetworkThroughputUtilization` |
| **`FileSystemId,VolumeId`** | `DataReadBytes` / `DataWriteBytes`, `DataReadOperations` / `DataWriteOperations`, `DataReadOperationTime` / `DataWriteOperationTime`, `MetadataOperations`, `MetadataOperationTime`, `StorageCapacity`, `StorageUsed`, `StorageCapacityUtilization`, `FilesCapacity`, `FilesUsed`, `CapacityPoolRead*` / `CapacityPoolWrite*` |
| `FileSystemId,Aggregate` | `DiskReadBytes` / `DiskWriteBytes`, `DiskReadOperations` / `DiskWriteOperations`, `DiskIopsUtilization` |
| `FileSystemId,DataType,StorageTier` (`+VolumeId` / `+Aggregate`) | `StorageCapacity`, `StorageUsed`, `StorageCapacityUtilization` |

**A `LUN` dimension does not exist.** **A dimension equivalent to `Protocol` does not exist either.**

---

### That the `FileServer` dimension points at a node

The `FileServer` dimension's values were **the node names themselves.**

```text
FileServer = FsxIdEXAMPLE-01
FileServer = FsxIdEXAMPLE-02
```

**This is the only place a per-node view is obtainable.** What was confirmed is only that this dimension's value is the node name; **how it behaves during a failover was not measured.** [The measured failover](paths-are-the-failover-mechanism.md#the-measured-failover) was observed via `nvme ana-log`, multipath, and the route table, not recorded on the CloudWatch side.

Which node I/O leans toward under normal conditions was also not measured. **How to read a utilization skewed toward one node is explained from the preferred / standby design in [Monitoring fails on averages (日本語)](../../../playbooks/05-operate/notes/monitoring-fails-on-averages.md).**

---

### How to count when a per-LUN figure is needed

**Because volume-level I/O metrics exist, with 1 volume per LUN you can see per-LUN I/O through CloudWatch.**

| Configuration | What is visible in CloudWatch |
|---|---|
| 1 volume, 1 LUN | **That LUN's I/O and capacity** (as the volume dimension) |
| Multiple LUNs in 1 volume | **Only the total.** Which LUN is using it is unknown |

**Separately from the recovery-granularity argument for 1:1, here is the monitoring-granularity reason.** Write down in the design document which reason drove your choice of 1:1. The recovery-granularity argument is in [LUN layout decides recovery granularity](lun-layout-decides-recovery-granularity.md).

If you need per-LUN figures in a configuration placing multiple LUNs in one volume, they are on the ONTAP side.

| What you want to see | Command |
|---|---|
| Per-LUN I/O counters | `statistics lun show -vserver <svm>` |
| LUN usage and reservation | `lun show -vserver <svm> -fields path,size,size-used,space-reserve` |
| iSCSI sessions | `vserver iscsi session show -vserver <svm> -fields lif,initiator-name,tpgroup` |
| NVMe controllers | `vserver nvme subsystem controller show` |
| **NVMe/TCP bytes by path** | **The `nvmf_tcp_port` counter.** Not obtainable from `nvmf_lif` or `lif` (below) |

**None of these flow to CloudWatch.** A separate path connecting to ONTAP is needed to pull them. **Look at the [Observability](../../observability/) route comparison before building your own** — NetApp Harvest's supported dashboards include one for LUNs, and NVMe Namespaces is simply disabled by default (see [On-prem dashboards do not transfer as-is (日本語)](../../../../ja/domains/observability/notes/on-prem-dashboards-do-not-transfer.md)). Building your own is a choice for when only a handful of values are needed.

---

### That only one table carries NVMe/TCP's bytes by path (cited)

**This is not our own verification.** The following is transcribed from a sibling repository's measurement.

**When confirming on the ONTAP side whether a second path is actually carrying traffic, the two you would naturally try first both return nothing.**

| Table | Behaviour against NVMe/TCP traffic |
|---|---|
| `nvmf_lif` | **Returns 0 rows.** Empty even after writing 600 GiB |
| `lif` | Reports the two LIFs at **0 bytes** (does not count NVMe-oF) |
| **`nvmf_tcp_port`** | **Carries real data.** Read and write byte counts and ops, per path |

**Both kinds of empty look identical to "there is no traffic."** The cited source, from `nvmf_tcp_port`'s delta, attributes about 1,012 GiB of reads and 730 GiB of writes to the optimized side, and **±0 bytes to the non-optimized side** ([the cited source's measurement results](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md)).

**Client-side output does not substitute.** `nvme list-subsys` shows two paths exist, but **it does not show that both are being used.**

> **Do not report 0 rows as 0.** "The table exists but is empty" and "this version has no such table" collapse into the same appearance if you add them up. **Have the collection side fail on 0 rows.**
> This is a point about how you build monitoring, and the same applies to [Observability](../../observability/) routes.

> **Tier**: `documented` (transcription of a sibling repository's measurement, ONTAP 9.18.1, `ap-northeast-1`). **Why `nvmf_lif` is empty is unresolved even in the cited source** and remains an open question to the vendor. **Do not read this as "a per-LIF counter is not available for NVMe-oF by design."**

---

### That a volume created on the ONTAP side does not appear in monitoring

In the verification environment, 2 volumes were created via the AWS API and 2 via the ONTAP CLI.

| Counting method | Result |
|---|---|
| `aws fsx describe-volumes` | **3 entries** (the root volume + the 2 created via AWS) |
| ONTAP's `volume show` | **5 entries** |
| CloudWatch `list-metrics`'s `VolumeId` values | **3 entries** (only IDs beginning with `fsvol-`) |

**A volume created on the ONTAP side does not receive an `fsvol-` ID.** The consequences:

| Impact | Content |
|---|---|
| CloudWatch | **Does not appear on the `VolumeId` dimension.** Neither capacity nor I/O can be monitored |
| Tags | Cannot be tagged through the AWS API |
| AWS Backup | Cannot be selected |
| Cost allocation | Cannot be allocated without a tag |

**Building block requires some objects that can only be created on the ONTAP side** (LUN, igroup, namespace, subsystem). **But the volume itself can also be created through the AWS API.** If you want to run monitoring and backup on the AWS side, **the shape that fits is creating the volume through the AWS API and creating only the LUN inside it on the ONTAP side.**

The full picture of this boundary is in [LUNs and igroups are outside the AWS API](block-objects-are-outside-the-aws-api.md).

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| Per-LUN I/O is visible in CloudWatch | **There is no LUN dimension.** Only as far as the volume |
| iSCSI I/O alone can be isolated in CloudWatch | **There is no protocol dimension** |
| Only capacity is visible at the volume level | **I/O metrics exist too.** `DataReadBytes` and similar carry a `VolumeId` dimension |
| 1 volume per LUN is only about recovery granularity | **There is also a monitoring-granularity reason.** The volume dimension substitutes for the LUN dimension |
| A per-node view is unavailable | **The `FileServer` dimension exists.** Its value is the node name |
| Uneven I/O between nodes is abnormal | **With 1 HA pair, one node owns the aggregate.** Being skewed is normal |
| A volume created on the ONTAP side also appears in CloudWatch | **It does not.** Because it has no `fsvol-` ID |
| Being block means the volume must also be created on the ONTAP side | **The volume can be created through the AWS API.** Only LUN, igroup, namespace, and subsystem can be created only on the ONTAP side |
| NVMe/TCP's bytes by path are obtainable from `nvmf_lif` | **It returns 0 rows** (cited). `lif` does not count NVMe-oF. The real data is in `nvmf_tcp_port` |

---

### Verification environment

| Item | Value |
|---|---|
| ONTAP version | 9.18.1P5 |
| Region | `ap-northeast-1` |
| Deployment type | `MULTI_AZ_2` (second generation, 1 HA pair) |
| Throughput capacity | 384 MBps |
| Volumes | 2 via the AWS API, 2 via the ONTAP CLI |
| `list-metrics` count | 129 |
| Verification date | 2026-09-05 |

> **Note**: metrics and dimensions can be added. **This list is a measurement as of 2026-09-05.** Run `list-metrics` in your own environment before reusing an "it does not exist" judgment.

---

### Primary sources referenced

| Point | Source |
|---|---|
| The definition of the `AWS/FSx` namespace's metrics and dimensions | [AWS: Monitoring with Amazon CloudWatch](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-cloudwatch.html) |
| Detailed monitoring adding per-volume and per-aggregate metrics | [AWS: FSx for ONTAP metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/fsx-ontap-metrics.html) |
| ONTAP's LUN statistics | [NetApp: statistics lun show](https://docs.netapp.com/us-en/ontap-cli/statistics-lun-show.html) |
| ONTAP's LUN usage and reservation | [NetApp: lun show](https://docs.netapp.com/us-en/ontap-cli/lun-show.html) |
| Confirming iSCSI sessions | [NetApp: vserver iscsi session show](https://docs.netapp.com/us-en/ontap-cli/vserver-iscsi-session-show.html) |

---

### Related documents

- [Domain — Block storage](../README.md) — this module's hub
- [LUNs and igroups are outside the AWS API](block-objects-are-outside-the-aws-api.md) — the full picture of the control-plane boundary
- [LUN layout decides recovery granularity](lun-layout-decides-recovery-granularity.md) — the other reason for 1:1
- [Multi-AZ moves a route, not an address](multi-az-moves-a-route-not-an-address.md) — what to look at with the `FileServer` dimension
- [Paths are the failover mechanism itself](paths-are-the-failover-mechanism.md) — the switchover as seen from the host side
- [Evidence policy](../../../evidence-policy.md)

---

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

## Verify it in your environment

| # | Step | What it tells you |
|---|---|---|
| 1 | Pull the full set of `AWS/FSx` dimensions and metrics with `list-metrics` | **The full set that exists at that point. It can grow** |
| 2 | Aggregate the above result by dimension combination | Whether a LUN or protocol dimension has been added |
| 3 | Look at `CPUUtilization`'s `FileServer` value | The node name. **A foothold for watching a failover** |
| 4 | Compare the count from `aws fsx describe-volumes` against ONTAP's `volume show` count | **Whether a volume invisible from AWS exists** |
| 5 | `statistics lun show -vserver <svm>` | Per-LUN counters on the ONTAP side |
| 6 | With multiple LUNs in one volume, cross-check the `VolumeId` dimension's `DataWriteBytes` against each LUN's writes | **Confirm that only the total is visible** |

Step 4's "a volume invisible from AWS" is confirmed by comparing this read-only command's count against ONTAP's `volume show`.

```bash
aws fsx describe-volumes --query 'length(Volumes)'
```

### Expected output

```text
The count from aws fsx describe-volumes can be smaller than ONTAP's volume show.
A volume created on the ONTAP side has no fsvol- ID and appears in neither CloudWatch nor AWS
Backup.
```

This command only counts volumes; it changes nothing on the volumes or the metrics. Because a LUN or protocol dimension does not currently exist, get per-LUN figures on the ONTAP side.

## Read next

[Is NVMe/TCP thin on the AWS side?](nvme-tcp-is-thin-on-the-aws-side.md)
