---
title: The contents of a LUN do not surface to file protocols — analyzing them through S3 Access Points always passes through one host
lifecycle: [assess, design, migrate]
domains: [block-storage, data-utilization]
evidence: documented
source: https://docs.netapp.com/us-en/ontap/concepts/client-protocols-concept.html
lang: en
---

# Do the contents of a LUN surface to file protocols?

No. The host interprets a LUN, and analyzing it with S3 requires passing through one host.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/lun-contents-do-not-reach-file-protocols.md) | [English](lun-contents-do-not-reach-file-protocols.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That files inside a LUN cannot be read from NFS / SMB / S3 Access Points, and that neither FlexClone nor rehost moves this boundary
- That analyzing block data through the S3 API passes through four stages and produces one copy

## What this note does not answer

- Public primary sources stating explicitly that "the contents of a LUN cannot be read from file protocols" (none found; `open`; can be confirmed by measurement)
- Whether a copy from a crash-consistent clone may be used for audit or reconciliation

## Prerequisite level

intermediate

## Body

<a id="the-contents-of-a-lun-do-not-surface-to-file-protocols"></a>

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

---

### Conclusion

**What interprets the filesystem inside a LUN is the host, not the storage.** So the files inside a LUN cannot be read from NFS / SMB, nor from Amazon S3 Access Points.

**Neither making a clone with FlexClone nor moving to a NAS-enabled SVM with `volume rehost` shifts this boundary.** A clone replicates the contents as they are, and rehost only changes the owning SVM, keeping a LUN a LUN.

**If you want to analyze block data through the S3 API, the path is four stages.** The stages do not shrink, and **one copy of the data is produced.** It is not "analyze without adding a copy."

> **Evidence**: `documented` — the protocol correspondence and what S3 Access Points target are based on vendor and AWS official documentation (confirmed 2026-09-11).
> **However, no explicit statement that "the contents of a LUN cannot be read from file protocols" could be found** (see below, `open`).
> The steps to confirm in your own environment are in [Verify it in your environment](#verify-it-in-your-environment).

---

### What the documentation states and what it does not

**Put this distinction first. The conclusion is the same, but the strength of the basis differs.**

| Point | State of the documentation |
|---|---|
| A LUN is a virtual disk, and one or more LUNs are stored in an ONTAP volume | **Stated** |
| **The same LUN can be accessed from FC / FCoE / iSCSI** | **Stated. File protocols do not appear in the list** |
| An NVMe namespace can be accessed **only through the NVMe protocol** | **Stated** (the exclusivity is explicit) |
| **That the contents of a LUN cannot be read from file protocols** | **No explicit statement could be found** (2026-09-11 search) |
| That what S3 Access Points target is the **file data** stored in an Amazon FSx file system | **Stated. There is no mention of LUNs** |

**The namespace has an explicit exclusivity statement, but the LUN does not.** The conclusion is drawn from the enumeration of protocol support, not based on a statement of prohibition.

**[The absence of documentation is not a tier](../../../evidence-policy.md).** This is an item that can be checked by measurement, so it is worth treating as a verification item. The steps are in [Verify it in your environment](#verify-it-in-your-environment).

---

### The four stages to analyzing through S3 Access Points

**This is the shortest path that satisfies the requirement of analyzing block data without affecting the production environment.**

| Stage | What you do | Does FlexClone help |
|---|---|---|
| 1 | Make a FlexClone of the volume containing the production LUN | **Yes.** This is FlexClone's very purpose |
| 2 | Map the clone's LUN to an analysis host and mount it | Irrelevant. **A host is required** |
| 3 | Have that host write the files inside out to a NAS volume | Irrelevant. **One copy is produced here** |
| 4 | Attach S3 Access Points to that NAS volume and analyze | Irrelevant |

**FlexClone solves only stage 1.** It solves the "do not affect production" part, and does not solve the "turn block into file" part.

**There are options for how to carry stage 3.** A file copy on the host, AWS DataSync, or transfer middleware with code conversion — three, with two axes for choosing ([Comparison of routes to carry block to file (日本語)](../../../../ja/reference/comparison/block-to-file-routes.md)).

#### The consistency constraint brought in at stage 2

**Because FlexClone derives from a Snapshot, the filesystem in the LUN inside is crash-consistent.**

`fsck` or `chkdsk` may run at the moment the clone is mounted, and **files copied from there have not received the application-side consistency guarantee** ([A snapshot of a LUN is crash-consistent by default](a-snapshot-of-a-lun-is-crash-consistent.md)).

| Use | Acceptable |
|---|---|
| Trend analysis, machine-learning training data | Acceptable in many cases |
| **An audit, reconciliation, or accounting trail** | **Make the judgment to accept it explicitly.** There is the option of switching to an application-side export (a dump, for a database) |

---

### Why FlexClone and rehost do not move the boundary

**Both are operations that change "where it is," not operations that change "what it is."**

| Operation | What it changes | What happens to the LUN |
|---|---|---|
| `volume modify -security-style` | The model used for permission evaluation | **Stays a LUN** |
| FlexClone | Getting a replica without touching the parent | **Is replicated, still a LUN** |
| `volume rehost` | Which SVM owns the volume | **Kept, and becomes unmapped** ([What `volume rehost` changes and does not](volume-rehost-changes-ownership-not-contents.md)) |
| **Mapping the clone LUN to another host and writing it out** | **From block to file** | This is the only place that crosses the boundary |

**"Move to a NAS-enabled SVM and it will be visible as a file" does not hold.** An SVM's protocol setting addresses one of the four causes of NFS not arriving ([Adding NFS to a volume already serving SMB needs no clone](../../multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md#the-four-reasons-nfs-cannot-reach-it)). **The block-file boundary is outside those four.**

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| It is multiprotocol, so the contents of a LUN can also be read from NFS | **They cannot.** Multiprotocol is a property that holds among NFS, SMB, and S3, not between them and block |
| Attach S3 Access Points and block data can be read through the S3 API too | The target is **file data**. There is no mention of LUNs |
| FlexClone makes it readable as a file | A clone replicates the contents as they are. **A LUN is a LUN even as a clone** |
| `volume rehost` to a NAS-enabled SVM makes it readable | **The LUN is kept and merely becomes unmapped.** The contents do not change even when the owning SVM does |
| Block data can be analyzed without making a copy | **A copy is produced because it passes through a host.** What FlexClone saves is the impact on production, not the copy itself |
| The documentation says "cannot be read" | **It does not** (2026-09-11 search). It is a conclusion drawn from the enumeration of protocol support |
| Data copied from a clone can be used for reconciliation as-is | **It is crash-consistent.** It has not received the application-side consistency guarantee |

---

### Primary sources referenced

| Point | Source |
|---|---|
| That a LUN is a virtual disk stored in an ONTAP volume, that the same LUN can be accessed from FC / FCoE / iSCSI, and that an NVMe namespace can be accessed only through NVMe | [NetApp: Learn about ONTAP client protocols](https://docs.netapp.com/us-en/ontap/concepts/client-protocols-concept.html) |
| That what S3 Access Points target is the file data stored in an Amazon FSx file system, and that it can be used alongside NFS / SMB | [AWS: Accessing your data via Amazon S3 access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html) |
| That FlexClone is a writable copy that shares data blocks with the parent | [NetApp: Learn about ONTAP FlexClone volumes, files, and LUNs](https://docs.netapp.com/us-en/ontap/concepts/flexclone-volumes-files-luns-concept.html) |
| That a volume is a container for files, directories, and iSCSI LUNs | [AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |
| That mixing SAN LUNs and NAS shares in the same FlexVol is not recommended | [NetApp: SAN volumes](https://docs.netapp.com/us-en/ontap/volumes/san-volumes-concept.html) |

---

### Related documents

- [Domain — Block storage](../README.md) — this module's hub
- [`examples/multiprotocol-ad/`](../../../../../examples/multiprotocol-ad/) — **a minimal setup to run the "how to confirm in your own environment" steps**. It includes the NFS-side recording script with the control
- [What `volume rehost` changes and does not](volume-rehost-changes-ownership-not-contents.md) — why moving the owning SVM does not move the boundary
- [Comparison of routes to carry block to file (日本語)](../../../../ja/reference/comparison/block-to-file-routes.md) — options for stage 3
- [A snapshot of a LUN is crash-consistent by default](a-snapshot-of-a-lun-is-crash-consistent.md) — consistency at stage 2
- [LUNs and igroups are outside the AWS API](block-objects-are-outside-the-aws-api.md) — the two control planes
- [Prerequisites for FSx for ONTAP S3 Access Points (日本語)](../../../../ja/domains/data-utilization/notes/s3-access-point-constraints.md) — constraints at stage 4
- [Adding NFS to a volume already serving SMB needs no clone](../../multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md) — the four causes on the NAS side
- [Evidence policy](../../../evidence-policy.md) — the treatment of `documented` and `open`

## Verify it in your environment

**Because the public documentation has no explicit statement that "the contents of a LUN are not visible from file protocols," it can be checked by measurement.** If you check it, you can raise it to `verified`.

| # | Step | What it tells you |
|---|---|---|
| 1 | Attach a junction path to the volume containing the LUN and mount it over NFS | That the volume itself is reachable |
| 2 | List the mounted directory | **Whether the LUN appears as a file. If it does, whether its contents can be read** |
| 3 | Attach S3 Access Points to the same volume and run `ListObjectsV2` | **Whether the LUN is enumerated as an object** |
| 4 | **As a control**, place one ordinary file on the same volume over NFS and re-run steps 2 and 3 | Separates **whether seeing nothing in steps 2 and 3 is a property of the LUN or a missing route configuration** |
| 5 | Map the LUN to a host over iSCSI, mount it, and list the files inside | That the same data can be read through the block path |

**If you skip step 4, you cannot tell whether the result of seeing nothing is "invisible because it is a LUN" or "the export policy and access point are configured wrong."** This is because [a failure with no control can record an error of procedure rather than a property of the target](../../../evidence-policy.md). Items to record are the ONTAP version, the volume's security style and `os_type`, and that the control in step 4 succeeded.

The listing in step 2 runs this read-only command at the NFS mount of the volume containing the LUN.

```bash
ls -la /mnt/<vol>/
```

### Expected output

```text
The LUN does not appear as a file (the ordinary file placed as a control does appear).
Only when the control file is visible through the same route can the absence be called a
property of the LUN.
```

This command only lists the mount point; it changes nothing on the LUN or the volume. The same data can only be read through the block path (an iSCSI mount).

## Read next

[Is the block protocol choice narrowed first by generation?](protocol-choice-is-bounded-before-you-choose.md)
