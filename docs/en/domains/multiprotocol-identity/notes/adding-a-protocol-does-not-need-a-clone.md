---
title: Adding NFS to a volume already serving SMB needs no clone — the reason it is unreachable lies outside the security style
lifecycle: [design, migrate, operate]
domains: [multiprotocol-identity]
evidence: documented
source: https://docs.netapp.com/us-en/ontap/nfs-admin/security-styles-their-effects-concept.html
lang: en
---

# Adding NFS to a volume already serving SMB needs no clone

[🏠 Repository home](../../../README.md) | [Domain — Multiprotocol identity](../README.md)

---

## Conclusion

**There is no such state in ONTAP as "a volume that only supports SMB".** So adding NFS requires neither cloning the volume with FlexClone nor moving it to another SVM with `volume rehost`.

The vendor's documentation states plainly that a security style **does not decide which client types can access a volume**. It decides two things only: which kind of permissions is used to evaluate access, and **which client type can change those permissions**. In the table on that same page, **"clients that can access the file" is both NFS and SMB for every style** — UNIX, NTFS and mixed alike.

**If NFS cannot reach it, the cause lies outside the security style.** There are four candidates, and every one of them is fixable without copying the volume.

> **Evidence**: `documented` — based on vendor and AWS documentation (confirmed 2026-09-11).
> **No figures, durations, or results reproduced in our own environment are included.** Run [Verify in your own environment](#verify-in-your-own-environment) before applying any of it.

---

## The detour a mistaken premise produces

The mistake arrives in this shape:

> This volume was created for SMB, so using it from NFS means rebuilding or copying it

Follow that and you arrive at a procedure: make a FlexClone, then `volume rehost` it to another SVM that has NAS enabled. **That procedure does not work.** `volume rehost` requires as a precondition that the target is neither a clone nor a clone's parent, so **it cannot run until the clone is split first** ([What `volume rehost` changes and what it does not](../../../../ja/domains/block-storage/notes/volume-rehost-changes-ownership-not-contents.md) (日本語)).

**And splitting brings back the capacity cost the copy was meant to avoid.** A clone shares blocks with its parent; splitting allocates storage of its own.

**The detour to avoid is "clone, split, rehost". The correct route is "identify one cause and fix it".**

---

## The four reasons NFS cannot reach it

**Check them in order. The cost of checking rises down the list.**

| # | What to check | How to fix it | Copy the volume |
|---|---|---|---|
| 1 | **Is the NFS protocol enabled on the SVM** | Add the protocol to the SVM. The same structure applies to SMB; enabling is an SVM-level setting | Not needed |
| 2 | **Does the volume have a junction path** | Mount it into the SVM's namespace. **A volume with no junction path does not appear in the NFS namespace** | Not needed |
| 3 | **Does the export policy permit the client** | Add a rule. **A default policy may carry no rules, and in that case it denies everything** | Not needed |
| 4 | **Does name mapping resolve** | Configure the mapping. **On an NTFS-style volume, permission evaluation uses the NTFS ACL, so a Windows-to-UNIX mapping is not consulted** ([How a security style maps to permission evaluation](security-style-and-permission-evaluation.md#security-style-and-permission-evaluation)) | Not needed |

**The security style appears in none of the four.** What the style decides is which permission model evaluates access once the request has arrived.

---

## How to change a security style

**Even when you do want to change it, an existing volume can be changed directly.**

The vendor's documentation states that where the volume already exists, `volume modify` with `-security-style` is what changes it. The values available are `unix`, `ntfs` and `mixed`.

| State | What to use |
|---|---|
| The volume does not exist yet | `volume create` with `-security-style` |
| **The volume already exists** | **`volume modify` with `-security-style`** |
| Unspecified at creation | It inherits the root volume's style |

**But changing it changes behaviour.** If a refused mapping is being used as a means of blocking access, changing the style to NTFS stops that means from working. **Confirm what stops working before you change it** ([What can be stopped and what cannot](security-style-and-permission-evaluation.md#what-can-and-cannot-be-stopped)).

**Do not choose mixed.** AWS documentation states that mixed is **not required for multiprotocol access and is recommended only for advanced users**. Its behaviour is to evaluate against the model of whichever protocol last set the permissions, which means the evaluation model changes during operation.

### The SVM root volume is the exception

**Changing the security style of an SVM root volume is a replacement in CloudFormation.** Managed from a template, changing it later rebuilds the resource ([Where a setting is created](../../../../ja/reference/decision-trees/where-a-setting-is-created.md) (日本語)). **It is something to settle first.**

---

## What FlexClone solves and what it does not

**Concluding that FlexClone is not needed does not mean FlexClone is useless.** It serves a different purpose.

The vendor's documentation describes FlexClone as a mechanism that references a snapshot's metadata to create **a writable point-in-time copy**. The copy shares data blocks with its parent and **consumes no storage beyond the metadata until a change is written.**

| Purpose | Is FlexClone needed |
|---|---|
| Making a volume already serving SMB usable from NFS as well | **No.** Fix one of the four above |
| **Confirming behaviour before changing a production security style** | **Yes, this works.** Change the style on the clone and try it without touching the parent |
| Building a test environment without stopping production | Yes |
| Reading block data as files | **It does not solve that** ([LUN contents do not reach the file protocols](../../../../ja/domains/block-storage/notes/lun-contents-do-not-reach-file-protocols.md) (日本語)) |

**The second row is what pairs with this note.** Whether changing the style breaks a means of blocking access in production can be established without trying it in production. The procedure is in the next section.

---

## Verify in your own environment

### 1. Check the SVM's protocol configuration

ONTAP CLI:

```text
vserver show -vserver <svm> -fields allowed-protocols
```

ONTAP REST API:

```http
GET /api/svm/svms?fields=name,nfs.enabled,cifs.enabled
```

**If NFS is not enabled, that is the cause.** Fix it before touching the volume.

### 2. Check the junction path

```text
volume show -vserver <svm> -volume <volume> -fields volume,junction-path,security-style
```

An empty `junction-path` means it does not appear in the NFS namespace. **The same output also shows `security-style`.**

### 3. Check the export policy's rules

```text
export-policy rule show -vserver <svm> -policyname <policy>
```

**A policy with zero rules denies everything.** "A policy is assigned" and "access is permitted" are different statements.

### 4. Try the style change on a clone

**Before changing a production style, try it in this order.**

| # | Operation | What it establishes |
|---|---|---|
| 1 | `volume clone create` against the target volume | That a copy is available without touching the parent |
| 2 | Mount the clone into the SVM namespace and attach an export policy | That NFS can reach it |
| 3 | Run `volume modify -security-style` on the clone | That the change goes through |
| 4 | Read and write from both NFS and SMB as an ordinary user **who is not in the administrators group** | What permission evaluation actually does after the change |
| 5 | Delete the clone | That the parent is unaffected |

**A result from step 4 obtained with an administrator account is not usable.** Members of `FileSystemAdministratorsGroup` are not subject to this kind of evaluation ([The other exception](security-style-and-permission-evaluation.md#one-further-exception)).

**Trying to delete the parent after step 5 may not succeed.** A deleted volume stays in the recovery queue for at least 12 hours by default, and the FlexClone relationship persists for that period ([the Volume recovery queue entry in the glossary](../../../../ja/reference/glossary/README.md)).

---

## Common misconceptions

| Misconception | Actually |
|---|---|
| A volume created for SMB cannot be used from NFS | **No such state exists.** A security style does not decide access |
| Adding NFS means copying the volume with FlexClone | Not needed. The cause is one of four, and none requires a copy |
| Just `volume rehost` the clone to an SVM with NAS enabled | **A clone cannot be rehosted.** It has to be split, and splitting ends the block sharing |
| A security style can only be set at creation | `volume modify -security-style` changes it. **But an SVM root volume is a replacement in CloudFormation** |
| mixed lets permissions be managed from both NFS and SMB | AWS documents mixed as **not required for multiprotocol access and for advanced users**. The evaluation model changes during operation |
| If an export policy is assigned, access is permitted | **A policy with zero rules denies everything** |

---

## Primary sources consulted

| Point | Source |
|---|---|
| That a security style does not decide which client types can access a volume, and that NFS and SMB can both access it under UNIX, NTFS and mixed | [NetApp: Learn about ONTAP NAS security styles](https://docs.netapp.com/us-en/ontap/nfs-admin/security-styles-their-effects-concept.html) |
| That an existing volume's style is changed with `volume modify -security-style`, that the values are `unix` / `ntfs` / `mixed`, and that it inherits the root volume when unspecified | [NetApp: Configure security styles on ONTAP NFS FlexVol volumes](https://docs.netapp.com/us-en/ontap/nfs-admin/configure-security-styles-task.html) |
| That mixed is not required for multiprotocol access and is recommended only for advanced users | [AWS: Updating volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/updating-volumes.html) |
| That FlexClone is a writable point-in-time copy consuming no storage until a change is written | [NetApp: Learn about ONTAP FlexClone volumes, files, and LUNs](https://docs.netapp.com/us-en/ontap/concepts/flexclone-volumes-files-luns-concept.html) |
| That a client can reach the same file over both NFS and SMB | [NetApp: Learn about ONTAP client protocols](https://docs.netapp.com/us-en/ontap/concepts/client-protocols-concept.html) |

---

## Related documents

- [Domain — Multiprotocol identity](../README.md) — this module's hub
- [`examples/multiprotocol-ad/`](../../../../../examples/multiprotocol-ad/) — **the smallest environment in which to check these four yourself**. One CloudFormation template and ONTAP REST scripts
- [Security style determines the permission model](security-style-and-permission-evaluation.md) — what the style actually decides
- [What `volume rehost` changes and what it does not](../../../../ja/domains/block-storage/notes/volume-rehost-changes-ownership-not-contents.md) (日本語) — the exclusion with clones, and what a split costs
- [LUN contents do not reach the file protocols](../../../../ja/domains/block-storage/notes/lun-contents-do-not-reach-file-protocols.md) (日本語) — the boundary adding a protocol does not cross
- [Routes for moving block data to files](../../../../ja/reference/comparison/block-to-file-routes.md) (日本語) — when that boundary has to be crossed
- [Where a setting is created](../../../../ja/reference/decision-trees/where-a-setting-is-created.md) (日本語) — why the root volume's style is a replacement
- [Preserving ACLs during migration](../../../../ja/playbooks/03-migrate/notes/preserving-acls-during-migration.md) (日本語) — carrying permissions across intact
- [Glossary](../../../../ja/reference/glossary/) — definitions of security style, `volume rehost` and FlexClone
- [Evidence Policy](../../../evidence-policy.md) — how `documented` is treated

---

[🏠 Repository home](../../../README.md) | [Domain — Multiprotocol identity](../README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md) | [English](adding-a-protocol-does-not-need-a-clone.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
