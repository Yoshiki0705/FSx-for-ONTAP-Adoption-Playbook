---
title: An exhausted audit destination stops client access — not at the moment it fills, but when an unobservable buffer has absorbed all it can, and not one record is lost
lifecycle: [design, build, operate]
domains: [security-governance]
evidence: verified
verified_on: 2026-09-01
ontap_version: 9.18.1P3D1
region: ap-northeast-1
lang: en
---

# An exhausted audit destination stops client access, but not at the moment it fills, and not one record is lost

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/security-governance/notes/audit-log-space-and-client-access.md) | [English](audit-log-space-and-client-access.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

[🏠 Repository home](../../../README.md) | [Domain — Security and governance](../README.md)

> This is the English translation. Japanese is authoritative for technical accuracy. Please report any discrepancy.

---

## Conclusion

**When the audit destination volume filled, SMB access to the audited volume eventually stopped.** It stops with `{Audit Failed} An attempt to generate a security audit failed.` (Windows system error 606), and **not only file writes fail — establishing a session with `net use` fails too.**

**But it does not stop at the moment the destination fills.** Between exhaustion and the stop, client operations keep succeeding while their audit records never reach the destination, accumulating somewhere that cannot be observed. **The stop comes when that accumulation has been absorbed as far as it can be.**

**And not one of the accumulated records was lost.** Once free space was restored at the destination, every record was written out with its original timestamps and ordering.

| Stage | Client | Destination EVTX | Measured, first run |
|---|---|---|---|
| 1. Destination has space | Succeeds | Recorded immediately | About 6.2 records per file operation |
| 2. Destination full, consolidation halted | **Keeps succeeding** | **Not recorded** | 757 operations over about 16 seconds |
| 3. Buffer absorbs all it can | **Fails** (`{Audit Failed}`) | Not recorded | After 4,538 records accumulated |
| 4. The stop persists | Fails (session establishment too) | Not recorded | Over 8 minutes, no self-recovery |
| 5. Free space restored | Back to succeeding | **All accumulated records arrive** | Consolidation resumed in about 1 second, zero loss |

**The values in stages 2 and 3 do not reproduce.** A second run on the same configuration stopped after 56 operations, where the first took 794. **The order of the stages reproduces; the length of each cannot be used as a design premise.**

**This structure is what decides the monitoring design.** Right up to the stop the client is healthy and nothing is written to the destination EVTX. **So there is a period in which "no records in the audit log" and "access is healthy" hold at the same time, and the end of that period is the outage.** The only signal that warns of it is the destination volume's utilization.

And the defaults lean towards exhaustion.

```text
FsxIdEXAMPLE::> vserver audit show -vserver <svm> -instance
                    Auditing State: true
      Strict Guarantee of Auditing: true      ← guarantee auditing; fail access if it cannot be written
          Log Files Rotation Limit: 0         ← no limit on the number of files
            Log Retention Duration: 0s        ← no deletion by age either
```

**With no retention limit the destination is certain to fill.** `-strict-guarantee true` is the default, and **left at that default, running out of capacity leads to an access outage.**

> **Evidence**: `verified` (2026-09-01, `ap-northeast-1`, ONTAP `9.18.1P3D1`).
> Measured on **a disposable SVM created specifically so nothing else was affected.** A 100 MB audit
> destination volume, a 2 GB audited volume, `-strict-guarantee` at its default `true`, `-rotate-size`
> 5 MB, and a SACL (`Everyone` / `0x1f01ff` / `OI|CI|SA`) on the audited side. The destination was
> filled with random data so neither compression nor deduplication applied (**writing identical
> content collapses under deduplication and never fills it**). The client is a Windows EC2 instance in
> the same VPC, connecting as a local user on a workgroup CIFS server.

---

## Measured up to the stop — load is what decides it

**With the destination in the same exhausted state, changing the load changes the outcome.** What decides whether access stops is not the free space at the destination but **the volume of operations that occur while it is exhausted.**

| Load | Destination state | Client | Arrival at the destination |
|---|---|---|---|
| 5 SMB operations | 8–12 KB free | **All 5 succeeded** | All 13 records after space was restored |
| 10,000 file create + read (first run) | 8 KB free. Cannot extend by 1 MB | **794 succeeded → the 795th failed** | All 4,960 records after space was restored |
| 5,000 file create + read (second run) | 16 KB free. Cannot extend by 1 MB | **56 succeeded → the 57th failed** | All records for the 56 after space was restored |

**Five operations did not stop it.** In the same exhausted state, they stayed within what the buffer could absorb. **Reading that difference as "because there were 8 KB free at the destination" leads to a wrong design.** What decides it is the accumulated volume.

**And the number that keeps succeeding does not reproduce.** The same configuration and workload gave 794 and 56. **The grace period before a stop cannot be estimated in operations or in time.** It depends on how much of the buffer prior audit activity had consumed, and that remainder cannot be observed.

### The moment of the stop

Times from the 10,000-operation workload (all UTC, 2026-09-01).

| Time | Event |
|---|---|
| `19:41:06` | EMS `wafl.vol.full` — auditing **requested 1.01 MB with only 752 KB available** |
| `19:41:17` | EMS `monitor.volume.full` — destination at 99% |
| `19:42:04.98` | Workload starts. Create and read files on the audited volume |
| `19:42:05.63` | **The last record to reach the destination** (through the 37th of 794 files, 422 records) |
| `19:42:05.65`–`19:42:21.98` | **4,538 records occur. None reach the destination. The client keeps succeeding** (files 38–794) |
| `19:42:22` | **Client stops** — `{Audit Failed} An attempt to generate a security audit failed.` |
| `19:50:05` | **Still stopped.** `net use` fails with Windows system error 606; no self-recovery |
| `19:51:22` | Free space restored (38 random files deleted through REST, 97 MB free) |
| `19:51:23` | **Consolidation resumes.** A 5,246,976-byte EVTX is rotated out |
| `19:53:30` | **Client recovery confirmed** (5 file create + read succeeded) |

**From the destination being judged full to the client stopping was about 65 seconds, of which about 16 seconds had the client succeeding with nothing recorded.** But this is **a value that depends on this workload's operation rate** — it is decided by operation volume rather than time. In the second run that grace was **19 seconds**.

The exact moment of recovery was not bracketed. **Consolidation resumed about 1 second after space was restored** (from the rotated file's timestamp), and **client recovery held by 19:53:30** — it may have been earlier.

---

## The records that were not lost

Every record accumulated up to the stop was written to the destination once space was restored.

```text
tag              : bl
records parsed   : 6533
EventID counts   : {'4719': 1, '4624': 5, '4656': 2806, '4663': 3719, '4634': 2}
distinct files   : 794
index range      : 1..794
gaps in range    : 0
```

| What was checked | Result |
|---|---|
| Files the client created | **794** |
| Files appearing in the audit log | **794** (sequence 1–794, **zero gaps**) |
| Reached the destination before the stop | 422 records (files 1–37) |
| Accumulated and arrived later | **4,538 records** (files 38–794) |
| Timestamps | **The real time of occurrence is preserved** (`19:42:05.654` to `19:42:21.984`), not the consolidation time |
| Ordering | Preserved |

**This is not "access went through but records were dropped".** `-strict-guarantee true` behaves exactly as designed: it stops the client rather than dropping records. **From an audit requirement's point of view, the behaviour sacrifices availability rather than completeness.**

> **Implication for audit requirements**: during the exhausted period, **the audit log looks as though
> it has a hole in it.** Before treating "there is no access record for this time" as a loss, check the
> destination volume's free space history. Restoring space fills it in.

### Blast radius — only the audited paths

**What stopped was only operations that require an audit record. Volumes in the same SVM that are not audited were unaffected.**

A volume `plain` with no SACL was added to the same SVM and exercised alongside the audited volume through the same CIFS server, the same data LIF, and the same local user.

| Volume | SACL | Result while exhausted |
|---|---|---|
| `work` (audited) | `Everyone` / `0x1f01ff` / `OI\|CI\|SA` | **`{Audit Failed}` on the 57th operation** |
| `plain` (not audited) | None | **All 5,000 operations succeeded** |

Immediately after `work` was refused, `plain` was connected and 5,000 file create + read operations all went through. **The audit log contains not one record for those 5,000 operations** — with no SACL, they are not audited.

| What was checked | Result |
|---|---|
| A new SMB connection to the non-audited volume while exhausted | **Succeeded** |
| 5,000 operations against the non-audited volume | **All succeeded** |
| Audit records for those 5,000 operations | **Zero** (not audited, so not recorded) |
| Operations against the audited volume at the same time | **Refused** |

**So the blast radius is not the whole SVM but the paths carrying a SACL.** On an SVM with auditing enabled, shares that were not made audit targets keep working.

> **Design implication**: where a share whose availability comes first and a share that must be audited
> sit on the same SVM, **only the one with a SACL suffers the outage when capacity runs out.** That
> leaves room for a separation design, but **it also means the audited side is the side that stops.**
> A workload that must be audited is, by definition, placed on the side most exposed to capacity
> exhaustion.

**Conversely, once the buffer is completely full, establishing a new session also fails.** In the first run, `net use` failed with Windows system error 606 at `19:50:05`, because establishing a session requires writing a `4624`. **The reason the connection to `plain` went through in the second run is that the connection to `work` had already established an authenticated session, so no new `4624` was needed.**

### The absorption ceiling, unestablished

The absorbed volume observed was **4,538 records**. The EVTX emitted on recovery was 5,246,976 bytes, **close to the 5 MB `-rotate-size`.**

**Whether that agreement relates to the threshold for stopping was not isolated.** NetApp documentation states that a staging volume reserves 2 GB per aggregate, but **the stop here came after absorbing the equivalent of 5 MB, nowhere near 2 GB.** That was initially treated as grounds for "staging exhaustion cannot explain this", but **as below, the cause was never staging — it was the destination filling.** What could be measured is only the externally visible behaviour.

- The staging volume `MDV_AUD_*` cannot be read from `fsxadmin`, so its occupancy cannot be checked directly
- No test was run to separate accumulated volume, elapsed time, and rotation size as the threshold

**And the cause of the stop was the destination filling, not staging.** AWS Support confirmed that **besides staging volume exhaustion, client access failure can also occur when the audit log destination volume fills** (2026-09-03). What was filled in this measurement is the destination volume. The NetApp KB [CIFS share not serving data because the Audit Log Destination is full](https://kb.netapp.com/on-prem/ontap/da/NAS/NAS-KBs/CIFS_share_not_serving_data_because_the_Audit_Log_Destination_is_full) covers the same symptom. **So "it stopped nowhere near the 2 GB of staging" is not a contradiction. Staging was not involved.**

An EMS event reporting this directly is also defined: `adt.dest.directory.full` (severity `EMERGENCY`), whose description states it **can lead to denial of service on objects carrying a SACL**. This measurement used a SACL on the SMB path, matching the observed symptom.

### Not arguing from the absence of an unobservable event

**This note originally made a bad inference here.** It offered the fact that `adt.stgvol.nospace` had zero hits across both runs as evidence that staging exhaustion was not the cause.

```text
FsxIdEXAMPLE::> event log show -message-name adt.stgvol*
There are no entries matching your query.

FsxIdEXAMPLE::> event log show -message-name adt.*
There are no entries matching your query.
```

**Those zeros are evidence of nothing.** AWS Support confirmed that **neither `adt.stgvol.nospace` nor `adt.dest.directory.full` is visible to customers by design** (2026-09-03; the former retracts the same case's earlier suggestion that it could be used for monitoring). **The event cannot fire, so its absence is unrelated to whether exhaustion occurred.** The conclusion — that staging was not involved — is corroborated by AWS's answer through a different route, but **the argument that supported it at the time did not hold.**

Meanwhile, `monitor.volume.full` and `monitor.volume.nearlyFull` targeting `MDV_aud_*` are described as **expected to be visible to customers**. Those were also zero across both runs. **But "visible" is AWS's expectation and was not confirmed here** (there is no way to fill staging deliberately). **So those zeros cannot be read as "staging had not reached 95%" either.**

> **On detection patterns**: the first search used only
> `event log show -message-name *audit*`. **`adt.stgvol.*` does not match that pattern.** The
> conclusion "there is no audit-related EMS" was really "there is no event matching `*audit*`". The
> zeros above were re-taken with `adt.*` and `*stgvol*`.
> **What you searched is part of the result.**

---

## The signals you can observe

**Across both stops, what was recorded is the destination volume's capacity events. The event reporting the write failure itself is defined but not visible to customers** (below).

```text
FsxIdEXAMPLE::> event log show -message-name *wafl.vol.full*
ALERT  wafl.vol.full: Insufficient space on volume auddest@vserver:... to perform
       operation. 1.01MB was requested but only 752KB was available.

FsxIdEXAMPLE::> event log show -message-name *volume.full*
ALERT  monitor.volume.full: Volume "auddest@vserver:..." is full
       (using or reserving 99% of space and 4% of inodes).
```

Reviewing every EMS record over the interval containing the stop, the only other entries were **`secd.nfsAuth.noNameMap` from an unrelated workload, at roughly 5.5-minute intervals**. Nothing about auditing, staging, or the refusal.

**That does not mean audit-related EMS events do not exist. They are defined, and the two that matter are not visible to customers.**

| Event | Severity | Meaning | Visible to customers |
|---|---|---|---|
| `adt.dest.directory.full` | `EMERGENCY` | The destination directory is full and audit logs cannot be written. **Can lead to denial of service on objects carrying a SACL** | **No** (AWS confirmed, 2026-09-03) |
| `adt.stgvol.nospace` | `EMERGENCY` | The staging volume has no space and a file or directory for audit logs cannot be created | **No** (same) |
| `monitor.volume.full` / `monitor.volume.nearlyFull` (targeting `MDV_aud_*`) | `ALERT` / `ERROR` | The staging volume reached 98% / 95% | **Expected** yes (per AWS; not confirmed here) |
| `monitor.volume.full` / `monitor.volume.nearlyFull` / `wafl.vol.full` (targeting the destination) | `ALERT` / `ERROR` | The destination reached 98% / 95%, or extension failed | **Yes** (measured) |

**Neither of the two events that report the write failure directly is reachable, by design.** Where this note says there is no way to ask whether auditing is still writing, that is not because none was found but **because it is built that way.** What remains are capacity-side proxies.

**And `vserver audit show` kept returning `Auditing State: true` throughout the stop.** Auditing is not disabled automatically, and **there is no field indicating that it has stopped.**

| What to monitor | What it tells you |
|---|---|
| Destination volume utilization (the 95% / 99% EMS events, CloudWatch volume metrics) | **The warning signal for an access outage — but the grace is 19 to 65 seconds** (below) |
| The `wafl.vol.full` EMS event | The moment auditing failed to extend the EVTX |
| The `adt.dest.directory.full` / `adt.stgvol.nospace` EMS events | The events reporting the write failure directly. **Neither is visible to customers** (AWS confirmed). They cannot be monitored |
| The `monitor.volume.*` EMS events targeting `MDV_aud_*` | Staging pressure. **Expected to be visible but not confirmed here**, since there is no way to fill staging deliberately |
| Aggregate free space | The headroom staging has to draw on |
| `Auditing State` in `vserver audit show` | **`true` even while stopped.** Not usable as a health signal |
| An EMS event for the client refusal | **Not visible to customers.** The event reporting the refusal is defined (`adt.dest.directory.full`) but has no path to reach it |

**There is no way to ask directly whether auditing is writing.** Destination volume utilization becomes the proxy for both audit health and access availability.

**And the length of the warning does not reproduce either.**

| | Full EMS | Client stop | Grace |
|---|---|---|---|
| First run | `04:41:17` (JST) | `04:42:22` | **About 65 seconds** |
| Second run | `05:20:27` | `05:20:46` | **About 19 seconds** |

In the second run `monitor.volume.nearlyFull` (95%), `wafl.vol.full`, and `monitor.volume.full` (99%) were **all recorded in the same second**, and the stop came 19 seconds later. **There is not necessarily time for a person to act between 95% and 99%.** What is needed is a design that does not fill — explicit retention, autosizing, a generous initial size — rather than one that detects and reacts.

---

## The invisibility of the staging volume

```text
FsxIdEXAMPLE::> volume show -volume MDV_AUD* -fields vserver,volume,aggregate,size,state
There are no entries matching your query.

FsxIdEXAMPLE::> volume show -volume *MDV*
There are no entries matching your query.

FsxIdEXAMPLE::> vserver show -type admin
There are no entries matching your query.
```

Zero rows, with an SVM that has auditing enabled. It does not appear in a full `volume show` either. The admin vserver itself cannot be read, so there is no route through it.

**Staging volumes are created per aggregate.** A NetApp KB states that creating an audit configuration fails outright without 2 GB free on the aggregate, so **aggregate free space becomes an indirect proxy** — but **how much is accumulated right now cannot be measured.**

---

## Retention — the two methods are mutually exclusive

```text
FsxIdEXAMPLE::> vserver audit modify -vserver <svm> -rotate-limit 10 -retention-duration 90d
Error: Field "-retention-duration" cannot be used with field "-rotate-limit".
```

| Method | Parameter | Value accepted |
|---|---|---|
| Retain by period | `-retention-duration` | `90d` → `90d 0h 0m 0s` |
| Retain by count | `-rotate-limit` | `10` |

**They cannot be set together.** Specifying only a period leaves the file count unbounded, so **the capacity ceiling cannot be pinned down at design time.** Specifying only a count shortens the retention period during any interval of heavier access.

**This exclusivity is ONTAP's internal implementation rather than CLI argument parsing.** AWS Support tested REST on the same version and confirmed that both `POST /api/protocols/audit` and `PATCH /api/protocols/audit` return **400 Bad Request** when `retention.count` and `retention.duration` are given together (2026-09-02), and replied that **lifting the constraint on the Amazon FSx side would be difficult**. The NetApp CLI reference likewise lists the two as alternatives inside braces separated by a vertical bar.

> **On changing the setting**: **specifying only `retention.count` while `retention.duration` is set
> resets `retention.duration` to `PT0S`** (verified by AWS Support, 2026-09-02).
> `PT0S` means no deletion by age. **Setting one disables the other.**
> When switching methods, read both values with `vserver audit show -instance` afterwards.

### The ceiling each method fixes, and how to detect the other

**Whichever you choose, the side you did not choose has to be covered by monitoring.** This is the guidance AWS Support supplied.

| Criterion for choosing | Setting | What it fixes | Covering what it does not |
|---|---|---|---|
| The retention period is fixed by policy | `-retention-duration` | The retention period | **The capacity ceiling** → destination volume size and utilization monitoring |
| You want the capacity ceiling fixed at design time | `-rotate-limit` + `-rotate-size` | **`-rotate-size` × `-rotate-limit` plus the one being written** | **The retention period** → monitor the timestamp of the oldest log file |

**The default `-rotate-size` is 100 MB.** Audit logs rotate by size by default.

Having chosen `-rotate-limit`, **you can detect the retention period falling below the requirement.** Read the timestamp of the oldest log file in the destination directory and check that the interval from there to now still meets the requirement. Falling below it is the trigger to consider raising `-rotate-limit` or expanding the destination volume.

Having chosen `-retention-duration`, the capacity side is covered — **provided the destination is a dedicated volume** — by setting an alarm on Amazon CloudWatch volume metrics (`StorageUsed` / `StorageCapacityUtilization`, with `FileSystemId` and `VolumeId` dimensions) to detect it before it fills. NetApp documentation likewise assumes a dedicated volume or qtree as the destination.

**But as above, the grace from 99% to the stop was 19 to 65 seconds when measured.** Make detection effective while it is still filling, at 95% or below. Detecting it immediately before the stop is too late.

Where a period is set by policy — a three-month inventory requirement, for instance — `-retention-duration 90d` matches the requirement.

---

## What to decide at design time

| Item | Recommended | Reason |
|---|---|---|
| Destination volume | **One dedicated to auditing.** Not shared with anything else | If it fills from someone else's writes, **access to the audited volume stops** |
| A SACL on the destination volume | **Do not** | Auditing the destination itself makes audit writes generate audit records. **The measurement recorded zero records for writes to the destination; it is not audited by default** |
| SACL scope | **Only the paths that need auditing** | **Only paths with a SACL stop.** The wider you apply it, the wider the outage when capacity runs out |
| Retention | **Explicitly** set `-retention-duration` or `-rotate-limit` to match the requirement | Both defaults are unlimited, and **left alone they lead to an access outage** |
| `-rotate-size` | Around 100 MB | Keeps a single file from growing unwieldy for collection and parsing |
| Destination utilization alarm | **At 95%, at the same time you enable auditing** | It is the only warning signal, and **99% to the stop was 19 to 65 seconds when measured** |
| Autosizing (ONTAP CLI `volume autosize`) | Consider alongside | **Nineteen seconds is too short for a person or for alarm-driven automation.** It expands the volume automatically on a utilization threshold (available on FlexVol, the default on FSx for ONTAP; confirmed with AWS Support, 2026-09-02) |
| Aggregate free space | Monitor alongside | The proxy for staging headroom |
| `-strict-guarantee` | Start from **the default `true`** | See below |

Setting `-strict-guarantee false` keeps access working when capacity runs out, but **it means accepting gaps in the audit log.** If auditing exists for compliance, a gap undermines the premise of auditing itself. Which to take depends on the nature of the audit requirement. **What this measurement shows is that at `true`, a capacity management failure becomes an access outage directly.** Where availability comes first, `false` is an option — and in that case, state in the design document that audit logs can have gaps.

---

## Retrieving the audit log

The EVTX files sit on the destination volume. **Syslog forwarding is not available** (per AWS). These routes were measured.

| Route | Result |
|---|---|
| The ONTAP REST file API | Works. No mount needed. `byte_offset` and `length` must be given explicitly |
| Through an S3 Access Point (`ListObjectsV2` → `GetObject`) | Works, **with conditions** (below) |
| Mount over SMB / NFS and copy | The common approach |

> **On retrieval**: reading the 5,246,976-byte EVTX in one call through the REST file API with the
> full length in `length` **truncated the multipart response partway and produced a file that could
> not be parsed.** Reading in 1 MiB steps by advancing `byte_offset` and concatenating gave a matching
> total length that parsed correctly. **No error is returned; you get a corrupt file.** Verify the size
> after retrieval.

Using an S3 Access Point has two conditions.

1. **The destination volume's security style and the identity fixed on the access point have to be consistent.** Attaching a UNIX-identity access point to an NTFS-style volume produced `AccessDenied` even for a caller with administrative privilege. Changing the security style to `unix` with the same access point in place let `ListObjectsV2` and `GetObject` through.

   > **Correction to the attribution**: this note previously attributed the cause to a missing name
   > mapping. **That is withdrawn.** AWS Support tried it in their own environment and reported that
   > **with an explicit name-mapping present and the mapped user permitted by the NTFS ACL, access
   > through an S3 Access Point to an NTFS security style volume still failed when
   > `FileSystemIdentity` was `UNIX`** (2026-09-02). **So "add a mapping and it works" cannot be
   > claimed.** AWS is confirming whether that combination is a supported configuration at all, and
   > will document either that it is not, or the settings required if it is. **For now, choosing a
   > consistent combination is the reliable workaround.**
   >
   > Separately, the AWS documentation already states the pairing under
   > [File system user identity and authorization](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html#fsxn-file-system-user-identity):
   > use a UNIX identity with UNIX security style volumes and a Windows identity with NTFS security
   > style volumes. **The guidance on combinations exists.** What is undocumented is what happens when
   > you choose an inconsistent one.

   **The S3-side error does not reveal the cause.** `event log show` on the same cluster did contain a name mapping failure, but **the following lines belong to a different workload. It was not identified as the one record corresponding to these calls, and as above it is not accepted as the explanation either.** Reading ONTAP's EMS is worth doing when triaging `AccessDenied`, but **do not conclude from this record that adding a mapping fixes it.**

   ```text
   ERROR secd.nfsAuth.noNameMap: vserver (<svm>) Cannot map UNIX name to CIFS name.
     Error: Get user credentials procedure failed
     [ 0 ms] Determined UNIX id 0 is UNIX user 'root'
     [    0] Trying to map 'root' to Windows user 'root' using implicit mapping
     [    0] Could not find Windows name 'root'
     [    0] Unable to map 'root'. No default Windows user defined.
   **[    0] FAILURE: Name mapping for UNIX user 'root' failed. No mapping found
   ```

2. **An access point cannot be created while an ONTAP object store server exists on the same SVM.** Creation ends in `FAILED` and asks for the existing server to be removed

How the layers work is in
[S3 Access Point authorization design — evaluation order and the two layers that narrow access](access-point-authorization-layers.md).

> **On operations**: after access point creation ends in `FAILED`, deleting the attachment still leaves
> an FSx for ONTAP managed object store association on the volume, and **the volume can no longer be
> deleted from ONTAP.** `aws fsx delete-volume` does delete it. Any practice of recreating the audit
> volume gets stuck here. The mechanism and AWS Support's reproduction are in
> [FSx for ONTAP S3 AP is not "S3 that you can use"](../../../../ja/domains/data-utilization/notes/s3-access-point-constraints.md#aws-サポートによる再現確認と機構) (日本語).

---

## Recovery procedure

Recovering from the stopped state took **nothing more than freeing space on the destination volume.** No audit configuration change and no SVM restart.

| # | Step | Measured |
|---|---|---|
| 1 | Check free space on the destination (`volume show -fields space.available`) | At the stop it could not satisfy the 1 MB needed to extend |
| 2 | Archive and delete old EVTX files, or expand with `volume size` | Deleting 38 random files recovered 97 MB |
| 3 | Confirm consolidation resumes (a new EVTX appears at the destination) | **About 1 second after space was restored** |
| 4 | Confirm client access | **Held by 19:53:30 against recovery at 19:51:22** |
| 5 | Confirm the accumulated records arrived, by checking the sequence for gaps | **Zero gaps** (794/794) |

**Archive the EVTX files before freeing space.** The accumulated records need somewhere to be written, so deleting too much exhausts it again. Here the destination was 100 MB against 5 MB of accumulation.

> **On teardown**: **an audit configuration cannot be deleted immediately after auditing is disabled.**
> Attempting to delete it after `vserver audit disable` failed with:
>
> ```text
> Cannot delete audit configuration for SVM "<svm>".
> Reason: Final consolidation is in progress. Retry after sometime.
> ```
>
> It is waiting for the final consolidation. In the measurement it became deletable about 2 minutes
> after disabling. **The destination volume cannot be deleted while the audit configuration remains,
> so any practice of recreating the whole SVM waits here.** Retrying resolves it, so do not read the
> failure as permanent.

---

## Confirming this in your own environment

| # | Step | What it establishes |
|---|---|---|
| 1 | Read the four defaults from `vserver audit show -instance` | The current `Auditing State` / `Strict Guarantee` / `Rotation Limit` / `Retention Duration` |
| 2 | Run `volume show -volume *MDV*` | That the staging volume is invisible. **Invisible is correct** |
| 3 | Measure destination usage over several days and derive the growth rate | The capacity the retention period needs. **An estimate made before enabling is not enough** |
| 4 | Put a utilization alarm on the destination at 95% | **Noticing while it fills rather than immediately before the stop. 95% and 99% can arrive in the same second** |
| 5 | Set the retention method explicitly and confirm it applied with `show` | That you have left the unlimited default |
| 6 | On a disposable SVM, fill the destination and then apply load | **How long your own operation rate keeps succeeding with nothing recorded** |

---

## Not confirmed

- **The internal threshold that leads to the stop.** AWS Support's confirmation established that the cause is destination volume exhaustion (2026-09-03, above). **What triggers the stop, however** — accumulated record count, elapsed time, `-rotate-size`, or another internal queue — **was not isolated.** The stop came after absorbing 4,538 records, but there is no evidence that figure is a threshold
- **The absorption ceiling.** The 4,538 records absorbed here are an observation for this configuration at this point in time. **It cannot be generalized as a limit**
- **Whether records start dropping under longer accumulation.** Space was restored after about 10 minutes and everything was collected. **Behaviour under longer accumulation was not measured**
- **The exact time to client recovery.** Success was confirmed 2 minutes 8 seconds after space was restored, without ruling out that it happened earlier
- **The staging volume's real size and growth rate.** Not measurable, since it cannot be read
- **How records are lost with `-strict-guarantee false`.** Which records drop, and whether the loss is detectable, were not measured
- **Whether NFS behaves the same.** The stop and recovery were measured over SMB only. **NFS `file-ops` auditing requires NFSv4 audit ACEs, so the same conditions as the SACL-bearing SMB path could not be created.** Measuring "NFS did not stop" could not separate a path difference from simply not being audited, so it was not attempted
- **That volumes in the same SVM outside the audit scope are unaffected was measured** (above). But **whether establishing a new session to a non-audited volume works while the buffer is completely full** was not isolated. The second run reused an existing authenticated session

---

## Primary sources

- AWS: [Auditing file access](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-access-auditing.html)
- NetApp: [Troubleshoot ONTAP auditing and staging volume space issues](https://docs.netapp.com/us-en/ontap/nas-audit/troubleshoot-auditing-staging-volume-concept.html)
- NetApp KB: [What happens if the destination volume or staging volume is out of space in NAS auditing](https://kb.netapp.com/onprem/ontap/da/NAS/What_happens_if_the_destination_volume_or_staging_volume_is_out_of_space_in_NAS_auditing)
- NetApp EMS: [`adt.stgvol` events](https://docs.netapp.com/us-en/ontap-ems/adt-stgvol-events.html) — the definition of `adt.stgvol.nospace`
- NetApp EMS: [`adt.dest` events](https://docs.netapp.com/us-en/ontap-ems/adt-dest-events.html) — the definition of `adt.dest.directory.full`, stating it **can lead to denial of service on objects carrying a SACL**
- NetApp KB: [CIFS share not serving data because the Audit Log Destination is full](https://kb.netapp.com/on-prem/ontap/da/NAS/NAS-KBs/CIFS_share_not_serving_data_because_the_Audit_Log_Destination_is_full) — the share stopping from destination exhaustion
- NetApp EMS: [`monitor.volume` events](https://docs.netapp.com/us-en/ontap-ems/monitor-volume-events.html) — `full` is around 98%, `nearlyFull` around 95%
- NetApp: [ONTAP Auditing Schema Reference (PDF)](https://docs.netapp.com/p/ontap/9x/Auditing-Schema-Reference.pdf) — the mapping between `-events` categories and event IDs
- NetApp: [`vserver audit modify`](https://docs.netapp.com/us-en/ontap-cli/vserver-audit-modify.html) — states that `-rotate-limit` and `-retention-duration` are alternatives
- NetApp: [Plan the auditing configuration](https://docs.netapp.com/us-en/ontap/nas-audit/plan-auditing-config-concept.html) — the 100 MB default log size, and a dedicated volume or qtree as the destination
- AWS: [FSx for ONTAP volume metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-metrics.html) — `StorageUsed` / `StorageCapacityUtilization`
- AWS: [Enabling volume autosizing](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/enable-volume-autosizing.html) — `volume autosize` (FlexVol) expanding on a utilization threshold

---

## Related

- [SMB logon auditing — 4624 is recorded](smb-logon-audit-event-coverage.md)
- [The only information available for a local user inventory is in the audit log](../../multiprotocol-identity/notes/local-user-inventory-without-last-logon.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/security-governance/notes/audit-log-space-and-client-access.md) | [English](audit-log-space-and-client-access.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
