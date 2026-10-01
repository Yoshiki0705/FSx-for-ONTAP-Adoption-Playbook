---
title: A FlexGroup balances when files are created, not afterward — constituent placement, FlexVol conversion, and limits
lifecycle: [design, build]
domains: [performance]
evidence: documented
source: https://www.netapp.com/pdf.html?item=/media/12385-tr4571.pdf
lang: en
---

# Where does a FlexGroup spread load, and what stays put after creation?

It chooses a location when files and directories are created, and does not move files once placed. Converting from a FlexVol does not redistribute existing data either.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/performance/notes/flexgroup-balances-at-file-creation-not-afterward.md) | [English](flexgroup-balances-at-file-creation-not-afterward.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That a FlexGroup places each file on one constituent and does not split a file across constituents.
- That balancing is decided at creation time, and reads or writes to existing files do not change where they live.
- That converting from a FlexVol, and adding constituents, leave existing data where it is.
- That the TR's limits split into enforced values and tested/recommended values.

## What this note does not answer

- Measured FlexGroup performance on Amazon FSx for NetApp ONTAP (this repository has not measured it).
- How many names fit in one directory ([another note](directory-size-is-capped-separately-from-file-count.md) covers that).
- Configuring a FlexGroup as a FlexCache cache ([a Japanese-only note](../../../../ja/domains/data-utilization/notes/reaching-data-without-copies.md#満たすと-1-つの形に収束する-2-つの要求) (日本語) covers that).

## Prerequisite level

intermediate

## Body

[🏠 Repository home](../../../README.md) | [Domain — Performance](../README.md)

This is the English translation. Japanese is authoritative for technical accuracy.

> **Evidence**: `documented` — statements about ONTAP in general come from NetApp Technical Reports; statements about FSx for ONTAP come from AWS documentation. This repository has not measured them.
> The main sources are [TR-4571: NetApp ONTAP FlexGroup volumes (implementation guide)](https://www.netapp.com/pdf.html?item=/media/12385-tr4571.pdf) (October 2021; the cover names no ONTAP version) and [TR-4678: Data protection and backup — NetApp ONTAP FlexGroup volumes](https://www.netapp.com/pdf.html?item=/media/17064-tr4678.pdf) (October 2021), both read in full on 2026-10-02. **Whether the TR values and behavior hold on FSx for ONTAP is not verified, except where an AWS statement is given.**

---

### Conclusion

**A FlexGroup decides where a file or directory goes when it is created.** Each file is placed on one constituent (a member FlexVol) and is not split across several. Reads of, or appends to, a file after placement do not move it.

**So the only chance to correct an imbalance is when new files are created.** In a volume converted from a FlexVol, or one that had constituents added later, existing data stays where it was. For moving off a FlexVol, AWS recommends copying into a new FlexGroup with AWS DataSync rather than converting.

---

### Where constituents are placed

| Item | Statement | Source |
|---|---|---|
| How files are placed (ONTAP general) | Individual files are not striped; each is allocated to one member volume | TR-4571 "Terminology", "FlexVol member volume layout considerations" |
| Matching aggregates (ONTAP general) | For active workloads, span only aggregates with the same disk type and RAID group configuration (the TR's numbered recommendation 4). The TR says the per-node aggregate counts in Table 9 are not hard requirements | TR-4571 "Aggregate layout considerations" |
| Default constituent count on FSx for ONTAP | Eight constituents per HA pair by default. The Amazon FSx API's `ConstituentsPerAggregate` defaults to 8 when omitted, with a valid range of 1–200 | [AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html), [AWS API Reference: CreateAggregateConfiguration](https://docs.aws.amazon.com/fsx/latest/APIReference/API_CreateAggregateConfiguration.html) |
| Size allocation on FSx for ONTAP | The size at creation is divided evenly among constituents, and a resize is spread evenly across the existing ones. Data is distributed across constituents at the file level | AWS: Managing FSx for ONTAP volumes |

**FSx for ONTAP aggregates are an AWS-managed layout; whether TR Table 9 applies to them as written is not verified.**

---

### Ingest balancing happens at creation time

TR-4571 states the following (ONTAP general).

- ONTAP makes placement decisions as new files and directories are created; the more creation there is, the more chances it has to correct an existing imbalance.
- For workloads that mostly read or append to existing files, placement matters less. **Placed files stay where they landed.**
- Conditions that help: many small subdirectories (dozens to hundreds of files each), many clients doing different things at once, and ample free space (at least 10% while under heavy load).
- As constituents fill, remote placement to other constituents increases so that none fills before its peers. **Remote placement carries a metadata performance penalty.**
- Placement decisions improve with each ONTAP release, and the TR recommends running the latest release (the TR's numbered recommendation 1).

Source: TR-4571 "Workloads and behaviors", "Ingest algorithm improvements". **Whether the same placement logic applies on FSx for ONTAP is not verified.**

The design caution that putting a very large number of files in one directory concentrates them on one constituent is in §1 of the sibling repository's [S3 Access Points + FlexCache / SnapMirror design considerations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/docs/ja/s3ap-flexcache-snapmirror-considerations.md) (日本語).

---

### Conditions that suit and do not suit

TR-4571 lists both (ONTAP general).

| Suits | Does not suit |
|---|---|
| Heavy creation of new data (ingest) | Large files that must be striped across nodes or volumes |
| High concurrency | A need to control the mapping of data to FlexVol volumes precisely |
| Even distribution across subdirectories | Many file renames |
| — | Millions of files in one directory that are frequently scanned in full |
| — | Thousands of symbolic links |
| — | Features not available on FlexGroup volumes |

Source: TR-4571 "Ideal use cases", "Nonideal cases". The TR's examples of suitable workloads include EDA, software build and test, log repositories, and home directories.

**The number of names that fit in one directory does not grow with a FlexGroup.** That cap and the cost of listing are in [A single directory has its own size cap, separate from the file count](directory-size-is-capped-separately-from-file-count.md).

---

### Converting from FlexVol does not redistribute data

| Item | Statement | Source |
|---|---|---|
| Form of conversion (ONTAP general) | From ONTAP 9.7, a single FlexVol can be converted in place to a FlexGroup with one member. The TR states the disruption is under 40 seconds regardless of data size or file count | TR-4571 "FlexVol to FlexGroup volume conversion" |
| When to avoid converting (ONTAP general) | For a FlexVol that is already very large (80–100 TB) and very full (80–90%), the TR recommends copying instead, **because new data gravitates to members added after conversion and existing data is not rebalanced automatically** | Same section, "When not to convert a FlexVol volume" |
| Examples of blocking conditions (ONTAP general) | The volume is a FlexCache origin, is in an active SnapMirror relationship, or has quotas or storage efficiency enabled (disable first, re-enable after), among others. The list is as of the TR's publication (October 2021) | Same section, "Things that can block a conversion" |
| Conversion on FSx for ONTAP | Converting with the ONTAP CLI yields a FlexGroup with one constituent. **For even distribution, AWS recommends moving data into a new FlexGroup with AWS DataSync.** When converting with the CLI, delete backups of the FlexVol first. Conversion does not rebalance automatically | AWS: Managing FSx for ONTAP volumes |
| Adding constituents on FSx for ONTAP | AWS recommends doing so only when all constituents are at maximum size and capacity is needed. New data is then prioritized to the new constituents, and the imbalance remains until they even out. **Added constituents cannot be removed.** Existing snapshots become partial copies | AWS: Managing FSx for ONTAP volumes, [AWS: Expanding FlexGroup volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/expanding-fg-volumes.html) |

**Both conversion and adding constituents are changes you cannot undo.** This note includes read-only checks only, not the conversion or expansion commands.

---

### Limits and what kind of limit each is

TR-4571's tables mark each value as hard-coded/enforced or tested/recommended. **Tested/recommended values come from testing on a 10-node cluster and are not enforced limits** (the note under the TR's tables).

| Item (ONTAP general) | TR value | Value type |
|---|---|---|
| FlexGroup size | 20 PB | Tested/recommended |
| FlexGroup total file count | 400 billion | Tested/recommended |
| Member FlexVol size | 100 TB | Enforced |
| Member FlexVol file count | 2 billion | Enforced |
| File size | 16 TB | Enforced |
| Member count | 200 | Tested/recommended (the TR notes official support is 200) |
| Minimum member size | 100 GB | Tested/recommended |
| Shortest SnapMirror and Snapshot schedule interval | 30 minutes | Tested/recommended |

Source: TR-4571 "Maximums and minimums", Tables 5 and 6.

**AWS states separate values for FSx for ONTAP.** The FlexGroup minimum is 100 GB per constituent and the maximum is 20 PiB; one constituent is at most 300 TiB and holds at most two billion files (AWS: Managing FSx for ONTAP volumes). **TR values that AWS does not state are not verified on FSx for ONTAP.** Units are kept as each source writes them (TB and PB in the TR; GB, TiB, and PiB at AWS).

---

### Member count a SnapMirror destination must match

| Item | Statement | Source |
|---|---|---|
| Member count (ONTAP general) | Source and destination must have the same number of members. The destination can be larger than the source but not smaller | TR-4678 "FlexGroup SnapMirror guidelines" |
| Adjustment after expansion (ONTAP general) | From ONTAP 9.3, expanding the source adjusts the member count at the next SnapMirror update | TR-4678, the "volume expand" passage just before that section |
| FabricPool (ONTAP general) | When a FlexGroup is created on FabricPool-enabled aggregates, every aggregate that holds a member must be a FabricPool aggregate | TR-4678 "Creating SnapMirror relationships when NetApp FabricPool is involved" |
| FSx for ONTAP | Source and destination FlexGroups need the same number of constituents, or transfers fail. **If you expand one, expand the other manually** | AWS: Expanding FlexGroup volumes |

**Whether the ONTAP 9.3+ automatic adjustment works on FSx for ONTAP is not verified.** The AWS statement calls for manual expansion.

---

### What AWS states and what is unverified

| Category | Content | Source |
|---|---|---|
| Stated by AWS | Default constituent count (eight per HA pair; `ConstituentsPerAggregate` defaults to 8), even size allocation, file-level distribution | AWS: Managing FSx for ONTAP volumes, CreateAggregateConfiguration |
| Stated by AWS | Conversion yields one constituent, no rebalancing, AWS DataSync recommended, delete backups before converting | AWS: Managing FSx for ONTAP volumes |
| Stated by AWS | Added constituents cannot be removed; constituent counts must match on both sides of SnapMirror | AWS: Expanding FlexGroup volumes |
| Stated by AWS | Minimum 100 GB per constituent, maximum 20 PiB, at most 300 TiB and two billion files per constituent | AWS: Managing FSx for ONTAP volumes |
| Not verified | The TR's placement logic (remote placement frequency, the 10% free-space guide), disruption time during conversion, the current list of blocking conditions, the TR's tested/recommended values, SnapMirror auto-adjustment | No AWS statement found |

Search scope (2026-10-02): the three AWS pages above and the Amazon FSx API Reference.

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| A FlexGroup splits a large file across all constituents | It does not. One file lives on one constituent (TR-4571) |
| A FlexGroup moves files after placement according to load | It does not. Placement is decided at creation and existing files stay (TR-4571) |
| Converting from a FlexVol produces an evenly balanced FlexGroup | It stays at one constituent. AWS recommends migrating with AWS DataSync for even distribution |
| Adding constituents balances immediately | New data gravitates to the new constituents and an imbalance remains until they even out. Added ones cannot be removed (AWS) |
| All TR limits are product limits | Tested/recommended values and enforced values are separate. For FSx for ONTAP, read the AWS values |
| A FlexGroup also raises the cap for one directory | It does not ([another note](directory-size-is-capped-separately-from-file-count.md#flexgroup-does-not-raise-the-per-directory-cap)) |

---

### Primary sources

| Topic | Source |
|---|---|
| One file per member, aggregate matching, placement at creation, remote placement, free-space guide, suitable and unsuitable conditions, limits and value types, FlexVol conversion and blocking conditions (ONTAP general) | [TR-4571: NetApp ONTAP FlexGroup volumes (implementation guide)](https://www.netapp.com/pdf.html?item=/media/12385-tr4571.pdf) (October 2021), "Terminology", "Aggregate layout considerations", "Workloads and behaviors", "Ingest algorithm improvements", "Ideal use cases", "Nonideal cases", "Maximums and minimums", "FlexVol to FlexGroup volume conversion" (checked 2026-10-02) |
| SnapMirror member count, 9.3+ adjustment, FabricPool aggregate condition (ONTAP general) | [TR-4678: Data protection and backup — NetApp ONTAP FlexGroup volumes](https://www.netapp.com/pdf.html?item=/media/17064-tr4678.pdf) (October 2021), "FlexGroup SnapMirror guidelines", "Creating SnapMirror relationships when NetApp FabricPool is involved" |
| TR index | [NetApp: ONTAP technical reports — NAS containers](https://docs.netapp.com/us-en/ontap-technical-reports/nas-containers.html) |
| FSx for ONTAP default constituent count, size allocation, conversion and the AWS DataSync recommendation, size and file-count limits | [AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) (checked 2026-10-02) |
| `ConstituentsPerAggregate` default and range | [AWS API Reference: CreateAggregateConfiguration](https://docs.aws.amazon.com/fsx/latest/APIReference/API_CreateAggregateConfiguration.html) |
| Adding constituents, that they cannot be removed, member count on both sides of SnapMirror | [AWS: Expanding FlexGroup volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/expanding-fg-volumes.html) |

---

### Related documents

- [Domain — Performance](../README.md) — this module's hub
- [A single directory has its own size cap, separate from the file count](directory-size-is-capped-separately-from-file-count.md) — the per-directory cap and remote entries in a FlexGroup
- [Reaching data without making copies](../../../../ja/domains/data-utilization/notes/reaching-data-without-copies.md#作成経路で成否が変わること) (日本語) — a FlexGroup as a FlexCache cache, and how the creation path changes the outcome
- [Tiering policy comparison](../../../../ja/reference/comparison/tiering-policies.md) (日本語) — tiering policy for a FlexGroup
- [Evidence policy](../../../evidence-policy.md)

[🏠 Repository home](../../../README.md) | [Domain — Performance](../README.md)

## Verify it in your environment

All steps are read-only. Conversion and adding constituents are not included.

| # | Step | What it shows |
|---|---|---|
| 1 | Read the volume style and size through the Amazon FSx API | Whether it is a FlexVol or a FlexGroup |
| 2 | Read each constituent's aggregate, size, and used space through the ONTAP CLI | How many constituents there are, and any imbalance |
| 3 | Repeat step 2 after writing data and compare how used space grew | Which constituents new data is going to |

```bash
# Amazon FSx API: volume style and size (read-only)
aws fsx describe-volumes --volume-ids <volume-id>
```

```text
::> volume show -vserver <svm> -volume <volume>* -is-constituent true -fields aggregate,size,used
```

### Expected output

```text
If OntapConfiguration.VolumeStyle in describe-volumes is FLEXGROUP, the volume is a FlexGroup.
volume show returns one row per constituent with aggregate, size, and used.
A volume converted from a FlexVol shows a single row. If used is skewed toward particular rows,
that is an observation that existing data stayed where it was placed (no redistribution after creation)
```

## Read next

[What limits how many files fit in one directory?](directory-size-is-capped-separately-from-file-count.md)
