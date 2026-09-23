---
title: '`volume rehost` changes only the owning SVM, not the contents — note the seven settings that are lost first'
lifecycle: [design, migrate, operate]
domains: [block-storage, multiprotocol-identity]
evidence: verified
verified_on: 2026-09-12
region: ap-northeast-1
ontap_version: 9.18.1P6
source: https://docs.netapp.com/us-en/ontap/volumes/rehost-volume-another-svm-task.html
lang: en
---

# `volume rehost` changes only the owning SVM, not the contents

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/volume-rehost-changes-ownership-not-contents.md) | [English](volume-rehost-changes-ownership-not-contents.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

---

## Conclusion

**`volume rehost` reassigns a volume from one SVM to another without a SnapMirror copy.** What changes is the owning SVM, and **the volume's contents do not change.** The LUN is kept, left in an unmapped state.

**A FlexClone volume cannot be rehosted.** The prerequisites require the target to be neither a clone nor a clone's parent. **You must split first, and splitting ends the block sharing with the parent and allocates its own storage.**

**It is still worth splitting and rehosting.** FlexClone has two benefits, and split loses only one of them. It loses the capacity-free sharing, but **the property of not touching the parent remains.** rehost is a disruptive operation, but **the disruptive part is to the clone, and the production volume is unaffected.**

**The price is not capacity alone. There are seven settings lost after rehost that need to be reconfigured manually, and one of them bears directly on permissions.**

**And measured, of the seven, the snapshot policy was not "lost" but reverted to `default`.** It is the accident on the side where a volume that was meant not to be snapshotted acquires the default schedule. **The security style was kept, and the AWS control plane caught up over about 14 minutes.**

> **Evidence**: `documented` — the prerequisites, unsupported features, and lost settings are based on the vendor's official documentation (confirmed 2026-09-11).
> **The REST path, the security-style retention, the snapshot policy reverting to `default`, and the time for the AWS control plane to catch up — these four are measured** (below, `ap-northeast-1` / ONTAP 9.18.1P3D1 / 2026-09-11).
> **No basis that it is a supported operation on FSx for ONTAP has been found.** AWS's documentation has no mention of `volume rehost` (searched the same day). Being able to run it and it being supported are different.
> **Four items remain undetermined** (below). Confirm in your own environment before applying.

---

## The prerequisites for rehost

**It cannot run unless they are met. Checking from the top down is cheapest.**

| # | Condition | Note |
|---|---|---|
| 1 | The volume is online | It cannot run while offline |
| 2 | The protocol is SAN or NAS | — |
| 3 | **For NAS, it is unmounted and not part of a junction path** | Remount it into the destination SVM's namespace after rehost |
| 4 | If there is a SnapMirror relationship, delete it and release the relationship info, or break it | **It can be resynced after rehost** |
| 5 | The source and destination SVM subtypes are identical | It cannot move between SVMs of differing subtype |
| 6 | **The target is neither a clone nor a clone's parent** | **Split a clone first** |

**The unsupported features are also enumerated.** SVM DR, MetroCluster configurations, **SnapLock volumes**, NetApp Volume Encryption volumes prior to ONTAP 9.8, FlexGroup volumes, and clone volumes.

**That SnapLock volumes are unsupported matters for another reason too.** SnapLock is irreversible to enable, a [feature that must not be enabled without an explicit human instruction](../../../../../AGENTS.md). There is no need to create a SnapLock volume for rehost verification.

### Additional conditions for SAN volumes

| Condition | Note |
|---|---|
| No volume move or LUN move is running | — |
| No I/O to the volume and LUN | — |
| **No igroup of the same name with different initiators exists on the destination SVM** | If the name matches, rename on either the source or the destination |
| **`force-unmap-luns` is enabled beforehand** | **The default is `false`. When set to `true`, no warning or confirmation message is shown** |

---

## The settings lost on rehost

**The documentation lists seven that are lost from the source volume after rehost and need to be reconfigured manually on the rehosted volume.**

| # | What is lost | What happens if you forget to reconfigure |
|---|---|---|
| 1 | Antivirus policy | Scanning stops being applied |
| 2 | Volume efficiency policy | Deduplication/compression stops and capacity grows |
| 3 | QoS policy | The cap comes off and can affect other workloads |
| 4 | **Snapshot policy** | **Generations stop being taken.** You notice when recovery becomes necessary |
| 5 | ns-switch and name services config | The name-resolution path changes |
| 6 | Export policy and rules | **A policy with 0 rules denies everything** |
| 7 | **User and group IDs** | **NFS permission evaluation is not the same as before rehost** |

**Number 7 is heavy on its own.** Reading from NFS with the UID / GID lost, permissions are not the same as before the move. **The "same" in the design "reach the same data even if you change protocol" breaks here.**

**Number 4 is slow to notice.** A missing snapshot policy is asymptomatic in normal times, and you learn the generations are gone when recovery becomes necessary.

**The LUN remap is also easy to forget.** rehost keeps the LUN but leaves it unmapped, and you recreate the igroup on the destination SVM and map it using the destination's portset. If `auto-remap-luns` is `true`, it is mapped automatically after rehost. **Recording the mapping info with `lun mapping show` before running is insurance against failure.**

---

## The exclusivity with FlexClone and the price of split

**Split loses only half of FlexClone's benefits. This asymmetry decides the judgment.**

| FlexClone property | After split |
|---|---|
| Shares data blocks with the parent and consumes no storage until a change is written | **Lost.** The copy gets its own storage allocated |
| **Obtains a writable copy without touching the parent volume** | **Remains** |

**If the remaining side is the goal, the capacity cost of split holds as its consideration.** You can move only the clone to another SVM and test it without touching the production LUN.

**There is one instance of the same structure in this repository.** AWS Transform's Finalize is the step that separates a FlexClone from its parent, and **physical capacity peaks there** ([AWS Transform's Finalize is where physical capacity peaks (日本語)](../../../../ja/playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md)). **rehost demands the same price from a different entrance.** The capacity estimate can use that way of thinking as-is.

---

## What rehost does not change

**Mistaking this leads to a design that does not hold.**

| Expectation | Reality |
|---|---|
| Move to a NAS-enabled SVM and the LUN's contents are readable from NFS | **They are not.** The LUN is kept and merely becomes unmapped ([The contents of a LUN do not surface to file protocols](lun-contents-do-not-reach-file-protocols.md)) |
| Moving makes it multiprotocol | **The security style does not decide access in the first place.** There are four causes of NFS not arriving, and rehost addresses only one ([Adding NFS to a volume already serving SMB needs no clone](../../multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md#the-four-reasons-nfs-cannot-reach-it)) |
| The data structure inside the volume changes | It does not. **Block stays block** |

---

## The four points confirmed by measurement

**This is our measurement, not the documentation's statement.** It is outside the note's `documented` tier.

Environment: `ap-northeast-1`, ONTAP 9.18.1P3D1, `SINGLE_AZ_1` (first generation), SSD 1,024 GiB, throughput 128 MBps, 2026-09-11. Source `subtype: default` / NFS enabled, CIFS disabled, root volume UNIX; destination the same. **The target volume was 1 GiB, created with an explicit security style of `NTFS`** (i.e. moved in a state differing from the destination SVM root's style).

### 1. The REST path is a private CLI passthrough

**The form of rewriting the volume's `svm` is refused.**

```text
PATCH /api/storage/volumes/{uuid}   {"svm":{"name":"<destination>"}}
→ HTTP 400  code 262196
  Field "svm.name" cannot be set in this operation
```

**What works is this.**

```text
POST /api/private/cli/volume/rehost
  {"vserver":"<source>","volume":"<name>","destination-vserver":"<destination>"}
→ HTTP 202 + job
  cli_output: "[Job NNNN] Job is queued: Volume rehost operation on volume ... by administrator "fsxadmin"."
```

**The job is asynchronous.** The job message after completion includes the vendor's own instruction — "configure the desired settings such as export policy and QoS policy on the target Vserver side."

> **ONTAP's job response returns control characters without escaping them.** Passing it directly to `jq` fails with
> `Invalid string: control characters from U+0000 through U+001F must be escaped`.
> If you script it, interpose `tr -d '\000-\010\013\014\016-\037'`.

### 2. Security-style retention

**It moved staying `ntfs`.** The destination SVM's root volume is UNIX, so **the style is a volume attribute and is not dragged to the destination root.** The silence in the statement that the security style is not among the seven lost meant retention in this environment.

### 3. The snapshot policy reverting to `default` — not a loss

**This is a sharper observation than the statement of the seven.**

| Item | Before the move | After the move |
|---|---|---|
| `snapshot_policy.name` | **`none`** (deliberately disabled) | **`default`** |

**"Lost" suggests absence, but what actually happened is the acquisition of the default schedule.** The direction of risk is reversed: **a volume meant not to be snapshotted starts having snapshots taken that were not requested.** And the vendor's job message names export policy and QoS policy, but **does not touch the snapshot policy that actually changed.**

**What could be observed in the first environment was only the snapshot policy.** The export policy was `default` before the move so no difference showed, QoS was unconfigured, and antivirus / efficiency / ns-switch were not configured.

**The second run (below, "The second measurement") could observe the export policy loss too.** Because a non-default export policy had been assigned before the move. **That "no difference showed" in the first run was not because nothing was lost, but because it was measured in a state where even a loss was invisible.** The remaining five are unobserved and stand as the documentation states.

### 4. The AWS control plane catch-up, and the time it takes

| Time (UTC) | ONTAP | AWS API |
|---|---|---|
| 02:31:01 | rehost job `success` | — |
| 02:33:29 – 02:43:12 | `svm_dest` | **`verification-svm` (old).** `JunctionPath` and `SnapshotPolicy` also still old |
| 02:44:43 | `svm_dest` | **`svm_dest`.** Three fields updated at once |

**About 13 minutes 42 seconds after the job completed**, `StorageVirtualMachineId`, `JunctionPath`, and `SnapshotPolicy` caught up all at once. **That it is longer than the "a few minutes" AWS's documentation says bears directly on designing the wait time.**

**Cutting off the observation at 3 minutes gives the opposite conclusion.** This repository's probe script originally had a 10-minute polling window, and **it was an implementation that would not reach 13 minutes 42 seconds and would conclude "AWS does not catch up."** Fixed. **A measurement with a short observation window reads silence as denial.**

**With both control planes agreeing, teardown worked with `aws fsx delete-volume`.** The asymmetry observed on a volume with S3 Access Points attached ([Stalling at teardown (日本語)](../../../../ja/domains/data-utilization/notes/s3-access-point-constraints.md#撤去時の停滞--aws-側からしか消せなくなるボリューム)) did not reproduce on this path. **But the behavior of trying to delete during the 14 minutes before catch-up was not measured.**

## The second measurement — the catch-up time extends beyond 13 minutes 42 seconds, and the export policy loss is observed

Re-measured on a different file system, with a newer ONTAP. **The security-style retention and the snapshot policy reverting to `default` reproduced.** Meanwhile two points differed from the first run.

Environment: `ap-northeast-1`, **ONTAP 9.18.1P6**, `SINGLE_AZ_1` (first generation), SSD 1,024 GiB, throughput 128 MBps, 2026-09-12. Both source and destination `subtype: default`, **both SVM root volumes UNIX**. The target volume was created with an explicit security style of `NTFS` and moved with a non-default export policy (`mpad_clients`) assigned.

| Item | Before the move | After the move | Verdict |
|---|---|---|---|
| Security style | `ntfs` | `ntfs` | **Kept** (destination root is UNIX; same conclusion as the first run) |
| ONTAP owning SVM | `fsxnmpadsrc` | `fsxnmpaddst` | Immediate |
| AWS `SvmId` | source | destination | **Caught up** (time below) |
| Snapshot policy | `none` | `default` | **Changed** (same as the first run; acquiring the default) |
| **Export policy** | `mpad_clients` | `default` | **Loss observed for the first time.** Reconfiguration needed |

### Treat the snapshot policy change as a data-protection design change

Writing the change from `none` to `default` as "acquired the default" makes it look light, but **from a data-protection viewpoint either direction is a design change.**

| Direction of change | What happens |
|---|---|
| `none` → `default` | **Snapshots start being taken on an unplanned schedule.** Capacity consumption and the set of retained generations to manage grow |
| Some policy → `default` | **The original schedule is lost.** If the recovery runbook is written on the premise "there is an hourly snapshot," that premise quietly collapses |

**Both are reported as a success and go unnoticed until recovery is next needed.** If you put rehost into an operational procedure, make reconfiguring the snapshot policy part of the procedure. Treat it the same as the export policy.

The AWS `JunctionPath` went from `/rehostvol` to `null`, off the namespace.

### The catch-up time varies by environment — do not treat 13 minutes 42 seconds as a rule

The second catch-up was **19 minutes 01 seconds or more, 24 minutes 05 seconds or less**. It is written as a range because the ONTAP job's completion time was not recorded. What could be observed was the two points "at 01:40:47 ONTAP already showed the destination" and "at 01:59:48 AWS switched over," with the pre-move snapshot at 01:35:43.

**Clearly longer than the first run's 13 minutes 42 seconds — the same operation gave a difference of 1.4× or more.** So 13 minutes 42 seconds is not an upper bound but one sample. **When designing the wait time, make the premise not the measured value itself but only the property "it does not finish in a few minutes."** The probe script's polling window is 25 minutes.

> **Note**: both are single observations of one environment. The range does not show a reproduced range but the observation-precision limit of this one run.

---

## The undetermined that remain

| # | Undetermined | Why undetermined | Impact |
|---|---|---|---|
| 1 | **Five of the seven lost** | What could be observed is the snapshot policy (first and second runs) and the export policy (second run). QoS / antivirus / efficiency / ns-switch / user-group ID were unconfigured or unconfirmed | The completeness of the reconfiguration list |
| 2 | **Deleting during the 14 minutes before catch-up** | Deletion in the window where the two control planes disagree was not tried | If a runbook enters this window, the behavior is unreadable |
| 3 | The split time and capacity peak | It should be proportional to the volume size, but no published formula was found | If SSD fills up mid-run, the LUN drops to read-only ([Capacity is counted in three places](capacity-is-counted-in-three-places.md)) |
| 4 | Presence in FSx for ONTAP's public documentation | No mention of `volume rehost` could be found in AWS's documentation (searched 2026-09-11). **The above is a measurement that ran with `fsxadmin`, but is not a basis that it is a supported operation** | The risk of making an officially unsupported operation a runbook premise |

**The list of what a delegated administrator can run is held by a sibling project** ([`fsxadmin-limitations.md`](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/fsxadmin-limitations.md)). **This repository does not reproduce the list.**

---

## How to confirm in your own environment

**rehost is disruptive. Do not try it on a volume holding production-equivalent data.**

### Before running

| # | Step | Reason |
|---|---|---|
| 1 | Save the output of `lun mapping show -volume <volume> -vserver <source_svm>` | **Insurance against losing the mapping info on failure.** The documentation lists it as a step |
| 2 | Save the output of `volume show -volume <volume> -instance` | **A record of the current state including the security style.** Used to judge undetermined 1 |
| 3 | Save the output of `aws fsx describe-volumes` | **A record of the owning SVM as seen from the AWS side.** Used to judge undetermined 2 |
| 4 | Save the current export policy and snapshot policy | Of the seven lost, the ones needing reconfiguration |

### Items to judge after running

| # | Confirmation | What it tells you |
|---|---|---|
| 1 | Compare the security style with `volume show -volume <volume> -instance` | It was **kept** in this environment. Try it with a style differing from the destination root |
| 2 | Compare `StorageVirtualMachineId` from `aws fsx describe-volumes`. **Wait 15+ minutes** | In this environment it caught up **13 minutes 42 seconds after job completion**. Cutting off at 10 minutes gives the opposite conclusion |
| 3 | Confirm the seven lost one by one. **Set the snapshot policy to `none` before moving** | The completeness of the reconfiguration list. The revert-to-`default` behavior cannot be observed if it was `default` before the move |
| 4 | Confirm the LUN is unmapped, and map it to the destination SVM's igroup | Whether the behavior matches the documentation |
| 5 | Read/write from NFS as a general user **not in the admin group** | Whether the UID / GID loss actually bears on permissions |
| 6 | **Try teardown.** Both `aws fsx delete-volume` and ONTAP's `volume delete` | **The consequence of undetermined 2.** If it can be deleted on only one path, the runbook needs to say so |

**Do not skip step 6.** That teardown works on only one path is learned at teardown, not at deployment. **It is a path you hit most when rebuilding a test environment.**

---

## Common misconceptions

| Misconception | Reality |
|---|---|
| A FlexClone volume can be rehosted as-is | **It cannot.** The prerequisites exclude it, and "clone volume" is on the unsupported-features list |
| Splitting defeats the purpose of using FlexClone | **Only half.** The capacity sharing is lost, but the property of not touching the parent remains |
| rehost affects production | **If run against a clone, production is unaffected.** The disruptive part is the target volume |
| rehost makes the volume's contents follow the destination SVM's style | **They do not.** The LUN is kept and merely becomes unmapped |
| The LUN is automatically remapped | **Only if `auto-remap-luns` is `true`.** Confirm the default behavior |
| Enabling `force-unmap-luns` shows a warning | **It does not.** The enabling itself is silent |
| Only the LUN map is lost | **There are seven.** Especially the snapshot policy and User and group IDs |
| The security style is kept because it is not among the seven lost | The conclusion is right but **the reason differs.** What is not written is not a basis; the basis is the measurement in this environment |
| The snapshot policy is lost, so nothing is taken after the move | **It reverts to `default`** (measured). Not the side where nothing is taken, but **the side where an unrequested default schedule is attached** |
| If it is not reflected in the AWS console, the two control planes still disagree | **Judge after waiting about 14 minutes.** In this environment it caught up after 13 minutes 42 seconds. A 3-minute observation reads it the opposite way |
| Rewriting the volume's `svm` over REST moves it | **It is refused with HTTP 400** (`code 262196`). `POST /api/private/cli/volume/rehost` is the path that works |

---

## Primary sources referenced

| Point | Source |
|---|---|
| That rehost reassigns a volume between SVMs without a SnapMirror copy, that it is disruptive to both data access and volume management, and the six prerequisites (online / SAN or NAS / NAS unmounted outside a junction path / SnapMirror handling / same subtype / clone and clone-parent exclusion) | [NetApp: Prepare to rehost an ONTAP volume from one SVM to another SVM](https://docs.netapp.com/us-en/ontap/volumes/rehost-volume-another-svm-task.html) |
| The unsupported features (SVM DR / MetroCluster / SnapLock / NVE before ONTAP 9.8 / FlexGroup / clone volumes) | [NetApp: ONTAP features not supported with a volume rehost](https://docs.netapp.com/us-en/ontap/volumes/features-supported-volume-rehost-concept.html) |
| The SAN additional conditions, the seven lost settings, that the LUN is kept and becomes unmapped, that `force-unmap-luns` defaults to `false` with no warning, `auto-remap-luns`, and pre-recording with `lun mapping show` | [NetApp: Rehost an ONTAP SAN volume](https://docs.netapp.com/us-en/ontap/volumes/rehost-san-task.html) |
| That split allocates its own storage | [NetApp: Learn about ONTAP FlexClone volumes, files, and LUNs](https://docs.netapp.com/us-en/ontap/concepts/flexclone-volumes-files-luns-concept.html) |
| That changes made with NetApp tools take a few minutes to reflect on the AWS side | [AWS: Managing FSx for ONTAP resources using NetApp applications](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-resources-ontap-apps.html) |

---

## Related documents

- [Domain — Block storage](../README.md) — this module's hub
- [`examples/multiprotocol-ad/`](../../../../../examples/multiprotocol-ad/) — **a minimal setup to measure two of the four undetermined**. `rehost-probe.sh` records only by default and changes nothing unless `--apply` is given twice
- [The contents of a LUN do not surface to file protocols](lun-contents-do-not-reach-file-protocols.md) — the boundary rehost also does not move
- [Adding NFS to a volume already serving SMB needs no clone (日本語)](../../multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md) — the case where rehost is unnecessary
- [AWS Transform's Finalize is where physical capacity peaks (日本語)](../../../../ja/playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md) — the split capacity peak of the same shape
- [Capacity is counted in three places](capacity-is-counted-in-three-places.md) — the path to filling up mid-split
- [LUNs and igroups are outside the AWS API](block-objects-are-outside-the-aws-api.md) — the two control planes
- [Prerequisites for FSx for ONTAP S3 Access Points (日本語)](../../../../ja/domains/data-utilization/notes/s3-access-point-constraints.md) — a precedent of disagreeing control planes
- [Comparison of routes to carry block to file (日本語)](../../../../ja/reference/comparison/block-to-file-routes.md) — the steps remaining after rehost
- [Glossary (日本語)](../../../../ja/reference/glossary/) — the definitions of `volume rehost` / FlexClone
- [Evidence policy](../../../evidence-policy.md) — the treatment of `documented` and the undetermined

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/volume-rehost-changes-ownership-not-contents.md) | [English](volume-rehost-changes-ownership-not-contents.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
