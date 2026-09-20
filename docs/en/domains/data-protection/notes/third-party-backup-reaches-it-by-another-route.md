---
title: A third-party backup product reaches FSx for ONTAP by a route that is not the AWS API — and "supported" is written differently per route
lifecycle: [design, build]
domains: [data-protection, security-governance]
evidence: documented
source: https://helpcenter.veeam.com/docs/vbaws/guide/add_fsx_policy_byb.html
lang: en
---

# How Does a Third-Party Backup Product Reach Amazon FSx for NetApp ONTAP?

Check whether a product reaches it through AWS, ONTAP, or a file share.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/data-protection/notes/third-party-backup-reaches-it-by-another-route.md) | [English](third-party-backup-reaches-it-by-another-route.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- The AWS API route covers AWS Backup, the ONTAP route covers management access, and the file-share route covers NFS or SMB visibility
- Explicit non-support and absence from a supported-systems list justify different conclusions

## What this note does not answer

- Whether the third-party product actually completes a backup and restore
- Whether an unlisted ONTAP route is usable in practice

## Prerequisite level

intermediate

## Body

<a id="a-third-party-backup-product-reaches-it-by-a-route-that-is-not-the-aws-api"></a>

[🏠 Repository home](../../../README.md) | [Domain — Data protection](../README.md)

---

### Conclusion

**"We already use this backup product, so FSx for ONTAP comes in on the same operation" is something you can say only after checking the route.**

Read one product's documentation and **the route by which it reaches FSx for ONTAP differs from the route by which it reaches the rest of the Amazon FSx family.** The former is **excluded by name** from the cloud-native route that works through AWS Backup, and the reader is pointed at the file-share side instead.

**And "supported" is written differently per route.** One is a stated non-support; the other is **an absence from a list of supported systems.** **Those two carry different weight, and the second cannot be read as non-support.**

Two questions to settle.

1. **Which route does the product reach it by?** Through the AWS API, through the ONTAP management plane, or through a file share
2. **Does it say "not supported", or does it not say anything?**

> **Tier**: `documented` — based on what the vendor's public documentation states (**retrieved 2026-09-15**). **No product behaviour was verified in this repository.** Nor was it confirmed that any route works. What is here is what the material says, not an observation.
> **This is a structure read from one product's documentation.** No claim is made that other products share it. [Verify in your own environment](#verify-in-your-own-environment) below is written as questions that hold whatever the product.

---

### Three routes, and the difference in how the material is written

| Route | What it goes through | FSx for ONTAP | How the material is written |
|---|---|---|---|
| **1. AWS plug-in** (cloud-native) | The AWS Backup service | **Excluded** | States by name that creating cloud-native backups for Amazon FSx for NetApp ONTAP file systems is not supported, and points at the Backup & Replication console |
| **2. ONTAP plug-in** (Universal Storage API) | The ONTAP management plane | **Absent from the list** | The supported-systems list names FAS / AFF / ASA / ASA r2 (ONTAP 9.10.1 or later). **FSx for ONTAP is not written there** |
| **3. Unstructured Data Backup** (NAS) | A file share (NFS or SMB) | Route 1's document points here | States that FSx for ONTAP file systems can be backed up using the Backup & Replication console |

**What route 1's exclusion means is that it stops being visible from the AWS API.** Route 1 creates Amazon FSx backups and backup copies through the AWS Backup service, requiring the Amazon FSx resource type to be opted in on the AWS Backup side. **FSx for ONTAP does not sit in that shape.**

**Route 3 treats it as a file share.** So **what is in scope is what NFS and SMB expose**, not a whole volume or the volume's own configuration. **LUN contents do not reach the file protocols**, so whether data served as block is in scope for this route has to be checked separately ([LUN contents do not reach the file protocols](../../block-storage/notes/lun-contents-do-not-reach-file-protocols.md)). **The material does not address this, and we did not check it.**

---

### Telling a stated exclusion from an absence

**Routes 1 and 2 support conclusions of different strength.**

| Route | State of the material | What can be concluded | What cannot |
|---|---|---|---|
| 1 | Non-support written by name | "This route cannot create them" | — |
| 2 | Absent from the supported-systems list | "It is not on the list" | **"It is not supported"** |

**Reading an absence from an enumeration as non-support is a move this repository names as something not to be used as grounds** ([Fit conditions — what must not be used as grounds](../../../../ja/reference/fsx-ontap-fit-conditions.md) (日本語)). Lists get updated, and the reason for absence can be non-support, not-yet-evaluated, or an omission.

**The vendor was not asked.** That is the means available if route 2 needs settling.

**Route 2's other requirements were not evaluated.** The material states that a FlexClone licence is needed, gives rules for coexistence with the built-in integration, and notes that Tamperproof Snapshots require the whole cluster to be registered rather than individual SVMs — but **since FSx for ONTAP is absent from the list, whether any of it applies cannot be judged.** Do not design as if it did.

**Route 1's constraints include an example of an irreversible setting closing a route.** The same document states that cloud-native backups cannot be stored in a logically air-gapped vault or in one with AWS Backup Vault Lock enabled. **That is a route 1 constraint, so it does not bind FSx for ONTAP** — but the shape of **an irreversible setting adopted for compliance removing a tool's destination** is there in the same material as a worked example. Vault Lock falls under [Approval for an irreversible operation is separate from approval for the task](../../../../ja/domains/security-governance/notes/irreversible-operations-need-separate-approval.md) (日本語).

---

### Compared symmetrically with the AWS-native options

**Adding no third-party product is placed with the same weight.** Each commits you to something.

| Mechanism | Suits | What it commits you to |
|---|---|---|
| **FSx for ONTAP volume backups plus AWS Backup** | Completing it on the AWS control plane. Riding the existing AWS Backup operation | **It holds no file system until it is restored.** The routes to another Region or account have boundaries ([A backup copy holds no file system until it is restored](../../../../ja/domains/data-protection/notes/backup-copies-across-regions-and-accounts.md) (日本語)) |
| **ONTAP snapshots plus SnapMirror** | Deciding granularity and RPO finely. Using ONTAP's own features | **The control plane becomes the ONTAP side.** Having a snapshot is not the same as being able to recover ([Having snapshots is not the same as being able to recover](snapshots-are-not-a-recovery-plan.md)) |
| **A third-party product (through a file share)** | Consolidating into an existing backup estate. Managing it in the same catalogue as other workloads | **The route is not the AWS API.** Scope becomes what the file share exposes, and a licence and an operating owner are added |

**How to choose comes down to whether consolidation is a requirement.**

| What you have | The straightforward choice |
|---|---|
| No requirement to consolidate into an existing backup estate | **The AWS-native side.** Adding no product is the lightest to operate |
| Consolidation is required and the target is visible from a file share | The third-party product. **Check the route first** |
| Consolidation is required and the target includes block (LUNs) | **Not visible through a file share.** Consider another mechanism |
| An irreversible retention setting is planned for audit or compliance | **Confirm, before setting it, that it does not remove the product's destination** |

---

### Common misconceptions

| Misconception | Actually |
|---|---|
| We already use this backup product, so the same operation carries over | **The route can differ.** Identify it in the material |
| Supporting Amazon FSx means supporting FSx for ONTAP | **It is not per family.** There is an example of it being excluded by name from the cloud-native route |
| It is absent from the supported-systems list, so it is not supported | **That does not follow.** Non-support, not-yet-evaluated and omission are all possible |
| Through a file share, all the data inside is in scope | **What NFS and SMB expose is in scope.** LUN contents do not reach the file protocols |
| A third-party product makes the AWS-native side unnecessary | They serve different purposes. **With no consolidation requirement, adding no product is lightest** |
| An irreversible retention setting only strengthens backups | **There is an example of it removing a tool's destination.** Confirm before setting it |
| This account is a verification of product behaviour | **It is a reading of what the material states.** No behaviour was verified in this repository |

---

### Primary sources consulted

| Point | Source | Retrieved |
|---|---|---|
| That the AWS plug-in does not support cloud-native backups for FSx for ONTAP and points at the Backup & Replication console; that the route uses the AWS Backup service and requires the Amazon FSx resource type to be opted in; that cloud-native backups are limited to the same AWS account; that they cannot be stored in a logically air-gapped vault or one with AWS Backup Vault Lock enabled | [Vendor documentation: Before You Begin (backing up Amazon FSx)](https://helpcenter.veeam.com/docs/vbaws/guide/add_fsx_policy_byb.html) | 2026-09-15 |
| That the ONTAP plug-in's supported systems are FAS / AFF / ASA / ASA r2 (ONTAP 9.10.1 or later); that the plug-in does not support NAS integration (unstructured data backup) and the built-in integration is needed for it; the FlexClone licence requirement; that Tamperproof Snapshots require the whole cluster to be registered and are not supported for individual SVMs | [Vendor documentation: NetApp ONTAP plug-in release information](https://www.veeam.com/kb4904) | 2026-09-15 |

---

### Related documents

- [Domain — Data protection](../README.md) — this module's hub
- [ISV and SaaS solution map by problem](../../../reference/isv-solution-map.md#integrating-an-existing-backup-product) — the index for this problem area
- [A backup copy holds no file system until it is restored](../../../../ja/domains/data-protection/notes/backup-copies-across-regions-and-accounts.md) (日本語) — the AWS-native route and its boundaries
- [Having snapshots is not the same as being able to recover](snapshots-are-not-a-recovery-plan.md) — verification once the route is settled
- [Data protection methods compared](../../../../ja/reference/comparison/data-protection-methods.md) (日本語) — the comparison table
- [LUN contents do not reach the file protocols](../../../../ja/domains/block-storage/notes/lun-contents-do-not-reach-file-protocols.md) (日本語) — route 3's scope
- [Approval for an irreversible operation is separate from approval for the task](../../../../ja/domains/security-governance/notes/irreversible-operations-need-separate-approval.md) (日本語) — approval before enabling Vault Lock
- [Fit conditions — what must not be used as grounds](../../../../ja/reference/fsx-ontap-fit-conditions.md) (日本語) — how an absence from an enumeration is treated
- [Evidence Policy](../../../evidence-policy.md)

---

<a id="verify-in-your-own-environment"></a>

## Verify it in your environment

**Written as questions that hold whatever the product.**

| # | Step | What it establishes |
|---|---|---|
| 1 | Identify, in the material, the route by which the product reaches FSx for ONTAP | **Through the AWS API, the ONTAP management plane, or a file share** |
| 2 | Distinguish "states not supported" from "does not say" | The strength of the conclusion available |
| 3 | If the route is a file share, confirm the target data is visible over NFS or SMB | **Data served as block may be out of scope** |
| 4 | If the route is the ONTAP management plane, confirm reachability to the management endpoint and the credential requirements | Whether it meets `fsxadmin`'s permission boundary |
| 5 | If an irreversible retention setting is planned, confirm first that it does not remove the destination from scope | **There is no going back afterwards** |
| 6 | If it is merely absent from a list, ask the vendor | **An absence from an enumeration is not evidence of non-support** |
| 7 | Once the route is settled, actually exercise a restore | **Being able to back up is not being able to restore** |

**Leaving step 5 until later means the backup route closes as a result of satisfying the compliance requirement.**

### Read-only file-share visibility check

For a mounted NFS or SMB path, list entries visible to the current identity without modifying them.

```bash
ls -la -- <mounted-nfs-or-smb-path>
```

### Expected output

The output has this general shape. Owner, group, timestamp, and names vary by environment.

```text
drwxr-x---  2 <owner> <group> 4096 <timestamp> <entry>
-rw-r-----  1 <owner> <group> <size> <timestamp> <file>
```

This check proves **only current file-share visibility for the identity running the command**. It does not prove product support, backup success, restore success, ONTAP management-route usability, LUN contents, metadata protection, or vendor compatibility.

---

## Read next

Use the [Data Protection domain README](../README.md) to choose the next note for the protection scope and recovery requirement.
