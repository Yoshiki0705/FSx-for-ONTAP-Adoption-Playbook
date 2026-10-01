---
title: A single directory has its own size cap, separate from the file count — maxdir-size and the cost of listing a large directory
lifecycle: [design, operate]
domains: [performance, cost]
evidence: documented
source: https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-02-maxdirsize.html
lang: en
---

# What limits how many files fit in one directory?

Not the volume's inode count: a per-directory size cap (maxdir-size), together with name length and character set.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/performance/notes/directory-size-is-capped-separately-from-file-count.md) | [English](directory-size-is-capped-separately-from-file-count.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That maxdir-size is a per-directory cap that applies separately from the volume's inode ceiling.
- Which operations fail at the cap, and which do not.
- Why looking up a name and listing every name in a large directory cost different amounts.

## What this note does not answer

- Measured values on Amazon FSx for NetApp ONTAP (this repository has not measured them).
- The behavior of a configuration that collects data through the S3 API into an origin and distributes it with FlexCache (see "Where the configuration-specific behavior is tracked" below).
- Directory limits of other storage services.

## Prerequisite level

intermediate

## Body

[🏠 Repository home](../../../README.md) | [Domain — Performance](../README.md)

This is the English translation. Japanese is authoritative for technical accuracy.

> **Evidence**: `documented` — statements about ONTAP in general come from a NetApp Technical Report (the TR below); the FSx for ONTAP default comes from AWS Prescriptive Guidance. This repository has not measured them.
> The TR is NetApp, "High-file-count NAS workloads : ONTAP Technical Reports" (docs.netapp.com; PDF generated 2026-09-30; no version number or revision history). Per-section sources are under each table and in "Primary sources".

---

### Conclusion

**maxdir-size is a per-directory cap, and it applies separately from the volume's inode ceiling.** The TR states that one directory can reach maxdir-size while the volume still has ample free inodes, and that the reverse also happens.

At the cap, **only creates and renames into that directory fail**, even with capacity and inodes left. Other directories and reads are unaffected.

In a large directory, a lookup by name is served quickly through the index, but **full enumeration and wildcard search grow more expensive with the number of names.**

AWS documents the 320 MB default for FSx for ONTAP. The other values and behaviors are not verified on FSx for ONTAP (scope in "[What AWS documents, and what is not verified on FSx for ONTAP](#what-aws-documents-and-what-is-not-verified-on-fsx-for-ontap)").

---

### maxfiles and maxdir-size are separate limits

| Aspect | maxfiles (the volume's inode count) | maxdir-size (the size of a directory) |
|---|---|---|
| What it bounds | How many files and directories the whole volume can hold | How many names one directory can hold |
| Unit | The volume (a FlexGroup sets it on the whole, with a ceiling per constituent) | A per-volume setting that applies to each directory individually |
| Default (ONTAP in general, TR) | About one per 32 KiB | 320 MB |
| Ceiling (ONTAP in general, TR) | 2,040,109,451 on a FlexVol | 4 GB (minimum 4 KiB). The same value on a FlexGroup, not multiplied by constituents |
| Symptom when exhausted | Creates fail with an error worded like a capacity shortage | Creates and renames into that directory fail |

Source: TR, page "[NetApp ONTAP High File Count Workloads for NAS volumes](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-01-overview.html)", section "Maxfiles compared with maxdir-size". The TR says to confirm the supported maximum for the release and platform before raising it. The inode side is in [You can run out of writes with capacity to spare](../../../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md).

> "A volume can have ample free inodes and still reach maxdir-size in one directory."
> — TR, same page and section

---

### How many names fit in one directory

A directory file grows in 4 KiB blocks; 320 MB is 81,920 blocks. How many names fit in a block depends on name length and character set, so the same 320 MB holds a different number of names.

| Name shape (the TR's examples) | Per block | Names at 320 MB |
|---|---|---|
| ASCII names up to 32 characters | About 53 | 4,341,758 |
| 48-character ASCII names | About 40 | 3,276,798 |
| 32-character names with non-ASCII characters (FlexGroup entries are similar) | About 26 | 2,129,918 |
| As above, also carrying an NFS alternate name | About 22 | 1,802,238 |
| 32-character Japanese names under `ja.UTF-8` | 26 | 2,129,918 (about 49% of the ASCII default) |
| All names 255 characters | — | About 737,000 |

Source: TR, page "[Maxdir-size and large ONTAP directories](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-02-maxdirsize.html)", sections "How directory blocks are constructed" and "Estimating the number of names per directory file". The Japanese-name row is from page "[Volume considerations](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-06-maxdirsize-volume-types.html)", section "Volume language".

**These are planning figures, not guarantees.** The TR presents them as such. Whether FSx for ONTAP holds the same numbers is not verified.

---

### What happens at the cap

The TR states the following (ONTAP in general).

- Operations that add a name to that directory (creates and renames) are rejected. Clients see `ENOSPC`, `file too large`, NFS error 27, `STATUS_CANNOT_MAKE`, or similar
- Operations on other directories, and reads of existing files, are unaffected
- The volume may still have capacity and inodes

Source: TR, page "[Impact of maxdir-size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-05-maxdirsize-impact.html)", section "What happens when maxdir-size is exceeded?".

On the FSx for ONTAP side, the AWS DataSync troubleshooting page states that a transfer task to FSx for ONTAP fails with `Input/Output error` when a directory reaches its per-directory maximum ([AWS: Troubleshooting issues with DataSync tasks](https://docs.aws.amazon.com/datasync/latest/userguide/troubleshooting-tasks.html)). As with inode exhaustion, the symptom can read like a capacity shortage.

---

### Listing cost grows with the directory

| Operation | What the TR states (ONTAP in general) |
|---|---|
| Lookup by name (opening a known file) | From ONTAP 9.2, an index is created when a directory file reaches about 2 MiB and helps name lookups. Opening stays fast |
| Full enumeration (`ls`, `find`, READDIR) and wildcard search | Every name is walked even with the index. It can run for a long time, appear hung, or hit a client or application timeout |
| Loading a directory not in cache; operations concentrating on one directory | Keep getting more expensive with the number of names |
| `wafl.dir.size.warning` (about 90% of the cap) | A size warning, not a latency threshold |

The TR states there is no directory size at which ONTAP declares a performance failure. What keeps getting more expensive is full enumeration, wildcard search, cold-cache loads, and serialization of operations against that directory.

> "Wildcard scans and READDIR still process the entire directory namespace."
> — TR, page "Directory indexing in ONTAP", section "What indexing does not change"

A single hot directory on a FlexVol gains no parallelism from additional nodes.

Source: TR, page "[Directory indexing in ONTAP](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-04-maxdirsize-indexing.html)", sections "Why directory indexing exists" and "What indexing does not change"; page "[Impact of maxdir-size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-05-maxdirsize-impact.html)", section "Performance impact"; page "[Volume considerations](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-06-maxdirsize-volume-types.html)", section "FlexVol volumes".

> **Performance note**: the TR states that sequential bandwidth tests do not predict this behavior. To measure it, test create, lookup, stat, rename, unlink, and enumeration separately, with a cold and a warm cache (the TR's recommendations page, section "Test metadata operations, not only throughput").

---

### A directory file does not shrink after deletes

The TR states the following (ONTAP in general).

- maxdir-size is a cap, not a reservation. Setting 320 MB does not set aside 320 MB in advance; but if a directory file does grow to 320 MB, it uses that much volume capacity
- Once a directory file grows, it stays at its high-water size even after entries are removed
- From ONTAP 9.5, indexed directories can reclaim 4 KiB blocks that become completely empty (hole punching). The reported size still does not normally shrink
- After many deletes, READDIR can traverse empty blocks. Copying the remaining entries into a new directory compacts it; lowering maxdir-size does not

Source: TR, page "[Maxdir-size and large ONTAP directories](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-02-maxdirsize.html)", section "How the maxdir-size cap behaves"; page "[Directory indexing in ONTAP](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-04-maxdirsize-indexing.html)", section "Sparse directories and hole punching".

---

### FlexGroup does not raise the per-directory cap

FSx for ONTAP offers both FlexVol and FlexGroup volumes ([AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html)).

According to the TR (ONTAP in general), a FlexGroup's maxdir-size is set on the FlexGroup and is not multiplied by the number of constituents. One directory's file lives on one constituent, and entries placed on another constituent (remote entries) take more space. For large, flat directories, plan for up to about 2×, which puts the 320 MB default at about 2 to 2.6 million ordinary names, fewer than the about 4.3 million on a FlexVol.

> "lowers the practical ceiling to about 2 to 2.6 million ordinary names at the 320 MB default"
> — TR, page "Volume considerations", section "FlexGroup volumes"

Source: TR, page "[Volume considerations](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-06-maxdirsize-volume-types.html)", section "FlexGroup volumes". Whether a FlexGroup on FSx for ONTAP shows this ratio is not verified.

---

### Raising the cap, and where the two documents differ

The two documents word differently whether the cap can be lowered after raising it.

| Point | TR (ONTAP in general) | AWS Prescriptive Guidance (FSx for ONTAP) |
|---|---|---|
| Raising policy | Raise only for a demonstrated single-directory need, in steps of about 2% | States that NetApp recommends keeping the default; validate any custom value by testing |
| Can it be lowered | It can be lowered later, but not below the largest directory file's high-water mark | Once increased, it cannot be decreased without recreating the directory |
| Size and performance | See "Listing cost grows with the directory" above | Directories are loaded into memory, so size trades against performance |

Source: TR, page "[Impact of maxdir-size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-05-maxdirsize-impact.html)", section "What happens when maxdir-size is exceeded?". AWS Prescriptive Guidance, "[Deploying Amazon FSx for NetApp ONTAP in an enterprise environment](https://docs.aws.amazon.com/pdfs/prescriptive-guidance/latest/fsx-ontap-enterprise-deployment/fsx-ontap-enterprise-deployment.pdf)" (PDF; document history initial publication 2023-08-29), the maximum directory size section (p.15).

> "After the value has been increased, it cannot be decreased without recreating the directory."
> — AWS Prescriptive Guidance, same section

**This repository has not tested which statement applies on FSx for ONTAP.** Treat raising the cap as a change that may not be reversible, and decide only after measuring the need. This note carries read-only inspection steps only, with no command that changes the value.

---

### What AWS documents, and what is not verified on FSx for ONTAP

| Status | Content | Source |
|---|---|---|
| Documented by AWS | maxdir-size is a per-volume setting shared by every directory; the 320 MB default allows about 4,300,000 files per directory (the source says 4.3 million) | AWS Prescriptive Guidance, maximum directory size section (p.15) |
| Documented by AWS | A DataSync task fails with `Input/Output error` when a directory reaches its per-directory maximum | AWS DataSync troubleshooting page |
| Documented by AWS | Both FlexVol and FlexGroup volumes are available | AWS: Managing FSx for ONTAP volumes |
| Not verified | The 4 GB ceiling, the about 2 MiB index threshold, enumeration-cost behavior, the about 2× FlexGroup ratio, Japanese-name packing, EMS events, the condition for lowering it | No AWS statement found |

Search scope (2026-10-01): AWS documentation searched for "maxdir-size" and "maximum directory size". **No page in the FSx for ONTAP User Guide documenting maxdir-size was found.** The only AWS statements found were the Prescriptive Guidance PDF and the DataSync page. The DataSync page links to a section of the HTML version of the Prescriptive Guidance, and that link returned HTTP 404 on 2026-10-01. The PDF of the same guide was retrievable, and it is what this note cites.

---

### Where the configuration-specific behavior is tracked

This note does not cover metadata operations and enumeration in a configuration that collects data through the S3 API into an origin and distributes it with FlexCache. That is tracked as a not-yet-measured item in [S3-Burst-on-ONTAP-Files issue #235](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/issues/235).

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| The per-directory limit follows from the volume's file-count ceiling | It is a separate limit. One directory reaches maxdir-size even with inodes left (TR) |
| Raising maxdir-size reserves capacity | It is a cap, not a reservation. Capacity is used only as the directory file actually grows (TR) |
| With an index, a large directory lists quickly too | The index helps lookups by name. Full enumeration walks every name (TR) |
| On a FlexGroup the per-directory cap grows with the number of constituents | It does not. Remote entries can make it hold fewer names than a FlexVol (TR) |
| Deleting files makes the directory smaller | It stays at its high-water size. To compact it, copy into a new directory (TR) |
| Hitting the cap means a capacity shortage | Capacity and inodes can remain; only creates and renames into that directory fail (TR) |

---

### Primary sources

Every TR row refers to NetApp, "High-file-count NAS workloads : ONTAP Technical Reports" (docs.netapp.com; PDF generated 2026-09-30; no version number or revision history).

| Point | Source |
|---|---|
| maxdir-size default 320 MB, minimum 4 KiB, ceiling 4 GB; the same ceiling on a FlexGroup; that it applies separately from inodes; confirming the supported maximum per release before raising it | TR, page "[NetApp ONTAP High File Count Workloads for NAS volumes](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-01-overview.html)", section "Maxfiles compared with maxdir-size" |
| 4 KiB blocks; 320 MB = 81,920 blocks; names per name shape | TR, page "[Maxdir-size and large ONTAP directories](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-02-maxdirsize.html)", sections "How directory blocks are constructed" and "Estimating the number of names per directory file" |
| A cap, not a reservation; the high-water mark; hole punching | Same page, section "How the maxdir-size cap behaves" |
| How to read the cap and the directory-file size; 320 MB appearing as 335,544,320 bytes | TR, page "[View maxdir-size and current directory size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-03-maxdirsize-view.html)", sections "View the configured cap" and "View the directory file from an NFS client" |
| The index at about 2 MiB; what indexing does not change; empty blocks and compaction | TR, page "[Directory indexing in ONTAP](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-04-maxdirsize-indexing.html)", sections "Why directory indexing exists", "What indexing does not change", and "Sparse directories and hole punching" |
| Enumeration cost; `wafl.dir.size.warning`; behavior at the cap; raising in about 2% steps and the condition for lowering | TR, page "[Impact of maxdir-size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-05-maxdirsize-impact.html)", sections "Performance impact" and "What happens when maxdir-size is exceeded?" |
| No parallelism for one FlexVol directory; the about 2× FlexGroup figure; Japanese-name packing | TR, page "[Volume considerations](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-06-maxdirsize-volume-types.html)", sections "FlexVol volumes", "FlexGroup volumes", and "Volume language" |
| The 320 MB default from ONTAP 9.14.1, indexing from 9.2, sparse directories from 9.5 | TR, page "[Features, EMS, and monitoring for maxdir-size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-07-maxdirsize-features-ems.html)", the features-by-release table |
| Measuring metadata operations, including enumeration | The TR's recommendations page ([high-file-count-workloads-14](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-14-best-practices.html)), section "Test metadata operations, not only throughput" |
| The FSx for ONTAP 320 MB default, about 4,300,000 files, per-volume scope, the condition for lowering, the recommendation to keep the default | [AWS Prescriptive Guidance: Deploying Amazon FSx for NetApp ONTAP in an enterprise environment](https://docs.aws.amazon.com/pdfs/prescriptive-guidance/latest/fsx-ontap-enterprise-deployment/fsx-ontap-enterprise-deployment.pdf) (PDF; initial publication 2023-08-29), maximum directory size section (p.15). The HTML version of that section returned HTTP 404 on 2026-10-01 |
| A DataSync task failing at the per-directory maximum | [AWS: Troubleshooting issues with DataSync tasks](https://docs.aws.amazon.com/datasync/latest/userguide/troubleshooting-tasks.html) |
| FlexVol and FlexGroup available on FSx for ONTAP | [AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |

---

### Related documents

- [Domain — Performance](../README.md) — this module's hub
- [You can run out of writes with capacity to spare](../../../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) — the volume-wide inode ceiling
- [Does FSx for ONTAP suit a high-file-count workload?](../../../playbooks/01-assess/notes/file-count-fit-depends-on-namespace-shape.md) — an adoption decision that uses the limits in this note
- [Throughput is not set by one value](where-throughput-is-determined-and-shared.md) — FlexVol and FlexGroup placement and the unit of sharing
- [Evidence classification policy](../../../evidence-policy.md)

[🏠 Repository home](../../../README.md) | [Domain — Performance](../README.md)

## Verify it in your environment

Every step is read-only. No step changes maxdir-size.

| # | Step | What it tells you |
|---|---|---|
| 1 | At the source, find the directories with the largest directory files | Whether the largest directory fits the target's cap |
| 2 | For those directories, count the names and note their length and character set | Which row of the names table above applies |
| 3 | Read maxdir-size on the target volume | The actual cap |

On an NFS client, read the directory-file size with the following (not `du`).

```bash
# On an NFS client: directory-file size of one directory (not du)
stat -c '%n %s bytes' /mount/path/directory
# The 10 largest leaf directories under a mount point, skipping Snapshot copies
find /mountpoint -name .snapshot -prune -o -type d -ls -links 2 -prune | sort -rn -k 7 | head
```

On the target, read maxdir-size through the ONTAP CLI.

```text
::> set -privilege advanced
::*> volume show -vserver <svm> -volume <volume> -fields maxdir-size
```

These checks follow the TR page "[View maxdir-size and current directory size](https://docs.netapp.com/us-en/ontap-technical-reports/high-file-count-workloads/high-file-count-workloads-03-maxdirsize-view.html)", sections "View the configured cap" and "View the directory file from an NFS client" (page URL and title confirmed on 2026-10-01). The TR states that ONTAP has no command reporting an individual directory's size, so it is read from a client. `set -privilege advanced` only changes the CLI privilege level, and `volume show` is a read. The procedure on [AWS: Updating the maximum number of files on a volume](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/increase-volume-max-files.html) shows that `fsxadmin` can use advanced mode on FSx for ONTAP, but whether it can read this field is not verified.

### Expected output

`stat` returns the directory file's size in bytes; per the TR, a directory at the 320 MB default shows 335,544,320 bytes. `volume show` returns the volume's cap. Compare the largest directory's size against the cap, and its name count against the table above. If it is near about 90% of the cap, consider splitting the directory before migrating.

## Read next

[Does FSx for ONTAP suit a high-file-count workload?](../../../playbooks/01-assess/notes/file-count-fit-depends-on-namespace-shape.md)
