---
title: A database on LUNs recovered without quiescing — a write-fenced snapshot in 0.52 s, and the DB does the recovery itself
lifecycle: [design, build, operate]
domains: [block-storage, data-protection]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
deployment_type: MULTI_AZ_2
lang: en
---

# Can a database on LUNs recover without quiescing?

Yes. A write-fenced snapshot took 0.52 seconds, and the DB recovered itself through WAL replay.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/a-database-on-luns-recovers-without-quiescing.md) | [English](a-database-on-luns-recovers-without-quiescing.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That a PostgreSQL with data and WAL split onto separate LUNs can be captured as one point in time with a consistency group's write-fenced snapshot, without stopping writes
- That the DB starts from a crash-consistent clone by redoing its own recovery, and no committed row is lost

## What this note does not answer

- The behavior with other DB engines or other settings (one observation with PostgreSQL 16)
- The conditions, symptoms, or upper time limit under which the write fence fails (not observed; the source for an upper-limit value could not be confirmed either)

## Prerequisite level

advanced

## Body

<a id="a-database-on-luns-recovered-without-quiescing"></a>

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

---

### Conclusion

**Against a PostgreSQL with data and WAL split onto separate LUNs, a consistency-group snapshot was taken without stopping writes, and starting from that clone, the DB replayed its own WAL and reached a consistent state.**

- **The write-fenced snapshot returned in 0.52 seconds**, and a snapshot at the **same timestamp** was created on the two volumes
- The PostgreSQL started from the clone recorded **`database system was not properly shut down; automatic recovery in progress`** and **completed redo in 0.84 seconds**
- **Every row committed immediately before the fence remained.** There are no missing numbers either
- **No operation equivalent to `pg_backup_start` was used at any point**

**It is not "crash-consistent, so unusable for a DB."** **Crash-consistent is usable for a DB insofar as the DB can bring itself up from a crash.** What matters is not the kind of snapshot but **that the order of dependent writes is not broken.** So **a fence is needed when it spans multiple LUNs.**

> **Tier**: `verified` (verified 2026-09-05, `ap-northeast-1`, `MULTI_AZ_2` second generation, 1 HA pair, ONTAP 9.18.1P5, Amazon Linux 2023, PostgreSQL 16, XFS) — the fence duration, the match of snapshot timestamps, the recovery log, the remaining row count, and whether `nouuid` was needed.
> **This is one observation with one DB engine.** Do not generalize it to other engines or other settings.

---

### The configuration

| Element | Placement |
|---|---|
| Data directory | A 40 GiB LUN (volume A) |
| WAL | A **separate** 20 GiB LUN (volume B), specified with `initdb -X` |
| Filesystem | Both XFS |
| Load | Continuous committed INSERTs (kept running throughout the verification) |

**NetApp's PostgreSQL guidance also shows a configuration splitting data and log onto separate volumes.** But that is an NFS mount example. **Here the same split was done with LUNs.**

---

### Why a write fence is needed, and its duration

**Snapshotting the two LUNs separately mixes two points in time.** The data could be newer and the WAL older, or vice versa. **The relationship the DB's recovery assumes — "the WAL is ahead of the data" — is broken.**

A consistency group treats multiple volumes as one unit and **fixes the snapshots of all volumes together while the write fence is applied.**

```text
vserver consistency-group create -vserver <svm> -consistency-group cg_pg \
                                 -volumes <data-vol>,<wal-vol>

vserver consistency-group snapshot create -vserver <svm> -consistency-group cg_pg \
                                 -snapshot cgfence1 -consistency-type crash -write-fence true
```

The measurement.

| Item | Result |
|---|---|
| Until the command returned | **0.52 seconds** |
| The snapshot creation time of the two volumes | **Identical** (`Sat Sep 05 07:24:52 2026`) |
| `max(id)` immediately before the fence | 210,000 |
| `max(id)` immediately after the fence | 213,000 |

**The fence has an upper time limit, and it fails if exceeded.** But **that value is not shown in this note** — its source could not be confirmed. **The measured value of 0.52 seconds is the only certain thing; the headroom to the limit is unknown.** It grows as the volume count and load increase. What happens when the fence fails was not observed.

**The default of `-consistency-type` is `crash`.** A scheduled snapshot is always crash.

**The `vserver consistency-group` commands were usable with `fsxadmin`.**

---

### The handoff of the clone

Cloning the volumes from the snapshot, **they were mapped to a separate host's igroup.**

```text
volume clone create -vserver <svm> -flexclone clone_pgdata \
                    -parent-volume <data-vol> -parent-snapshot cgfence1
lun map -vserver <svm> -path /vol/clone_pgdata/pgdata -igroup <the other host's igroup>
```

**The LUNs inside the clone have a serial different from the parent.** That is, the WWID differs, and the host sees them as separate disks.

| LUN | Parent serial | Clone serial |
|---|---|---|
| data | `…717a6976` | `…717a697a` |
| WAL | `…717a6977` | `…717a6a30` |

**The cloned LUN must be explicitly `lun map`ped.** The parent's mapping is not inherited.

**Mounting did not need `-o nouuid`.** This narrows the round 1 observation.

| Situation | `nouuid` |
|---|---|
| The parent filesystem is mounted on the **same host** | **Needed.** XFS refuses a double mount of a filesystem with a matching UUID |
| The parent is mounted on a **separate host** (this time) | **Not needed.** It `mount`ed as-is |

**`nouuid` is not a property of the clone but a workaround for a UUID collision on the same host.** It is not needed in an operation that hands the clone to a separate host.

---

### The content of the recovery

**The PostgreSQL on the clone side started with no preparation.** Only `postmaster.pid` was deleted.

```text
LOG:  database system was interrupted; last known up at 2026-09-05 07:24:11 UTC
LOG:  database system was not properly shut down; automatic recovery in progress
LOG:  redo starts at 0/1543818
LOG:  invalid record length at 0/5C40768: expected at least 24, got 0
LOG:  redo done at 0/5C40740 system usage: ... elapsed: 0.84 s
LOG:  checkpoint starting: end-of-recovery immediate wait
LOG:  checkpoint complete: ...
```

| Log line | How to read it |
|---|---|
| `was not properly shut down` | **It means the snapshot looks like "the power fell."** This is what crash-consistent means |
| `redo starts` → `redo done` (0.84 s) | **The DB replayed the WAL.** There was no manual operation |
| `invalid record length` | **A normal line indicating the end of the WAL. Not corruption.** Replay stopping here is correct behavior |
| `checkpoint complete` | The checkpoint after recovery |

The data check.

| Item | Result |
|---|---|
| `count(*)` | 212,000 |
| `min(id)` / `max(id)` | 1 / 212,000 |
| Missing numbers | **None** (count and max match) |

**212,000 is between the 210,000 immediately before the fence and the 213,000 immediately after.** That is, **every row committed before the fence remained, and some rows committed within the fence window also remained.** No committed row was lost.

**`pg_backup_start` / `pg_start_backup` was not used.** **The NetApp page cited shows a procedure that does not use them** — that the word does not appear anywhere in the guidance was not confirmed.

---

### What can and cannot be said

**What can be said** (measured in this environment).

- A DB spanning multiple LUNs can be captured as one point in time without stopping writes
- A DB started from that point recovers itself and does not lose committed data
- No additional operation is needed for recovery

**What cannot be said.**

| Claim | Why it cannot be said |
|---|---|
| It will be the same on all DB engines | **It was observed once with PostgreSQL 16** |
| The conditions and symptoms of the fence failing | **Not observed.** The upper-limit value's source could not be confirmed either |
| It will take 0.52 seconds on a configuration with many volumes | **It is the value with 2 volumes** |
| application-consistent is unnecessary | **It depends on the requirement.** Read the distinction below |

**The distinction between crash-consistent and application-consistent does not change in this verification.** **NetApp writes that the two flags are for recording and there is no difference from ONTAP's perspective.** What quiesces is a mechanism outside the storage. **So the judgment is not on the presence of a backup product but on the requirement side of "is recovering to that point enough."** The details are in [A snapshot of a LUN is crash-consistent by default](a-snapshot-of-a-lun-is-crash-consistent.md).

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| A crash-consistent snapshot is unusable for a DB | **Usable if the DB can bring itself up from a crash.** It recovered in 0.84 seconds by measurement |
| A snapshot is meaningless without quiescing the DB | **All committed data returned from a clone taken without quiescing** |
| For multiple LUNs, snapshotting per volume is enough | **The points in time mix.** A fence is needed |
| A write fence stops I/O for a long time | **It was 0.52 seconds in this configuration** (2 volumes) |
| It is risky unless `-consistency-type application` | **The default is `crash`, and it recovered with it.** The judgment is on the recovery-objective side |
| `pg_backup_start` is needed | **It was not used.** The page cited also shows a procedure that does not use it |
| Mounting a clone always needs `nouuid` | **Only when the parent is mounted on the same host** |
| A clone's LUN is immediately usable | **`lun map` is needed separately.** The parent's mapping is not inherited |
| A clone's LUN has the same WWID | **The serial differs, so the WWID differs too** |
| `invalid record length` is data corruption | **A normal line indicating the end of the WAL** |

---

### Verification environment

| Item | Value |
|---|---|
| ONTAP version | 9.18.1P5 |
| Region | `ap-northeast-1` |
| Deployment type | `MULTI_AZ_2` (second generation, 1 HA pair) |
| Throughput capacity | 384 MBps |
| DB | PostgreSQL 16 (the Amazon Linux 2023 package) |
| Data LUN | 40 GiB, XFS |
| WAL LUN | 20 GiB, XFS, a separate volume, `initdb -X` |
| Client | Amazon Linux 2023, kernel 6.18.44-99.149.amzn2023.x86_64. The clone was started on a separate host in a separate AZ |
| Verification date | 2026-09-05 |

> **Note**: the above is a single measurement in this environment. **The fence duration changes with the volume count and load.** Measure it with your production configuration.

---

### Primary sources referenced

| Point | Source |
|---|---|
| The syntax of `vserver consistency-group snapshot create`, that the default of `-consistency-type` is `crash`, that `-write-fence` exists, and that it is usable with admin privileges | [NetApp: vserver consistency-group snapshot create](https://docs.netapp.com/us-en/ontap-cli/vserver-consistency-group-snapshot-create.html) |
| That a consistency group applies a write fence to create a same-point-in-time image of all members | [NetApp: Manage application consistency groups](https://docs.netapp.com/us-en/ontap-restapi-9161/manage_application_consistency_groups.html) |
| That an on-demand snapshot can choose application-consistent or crash-consistent, that the default is crash, and that scheduled runs are always crash | [NetApp: Manage application consistency group snapshots](https://docs.netapp.com/us-en/ontap-restapi-9171/manage_application_consistency_group_snapshots.html) |
| The concept of consistency groups and the guarantee of protection spanning multiple volumes | [NetApp: Learn about ONTAP consistency groups](https://docs.netapp.com/us-en/ontap/consistency-groups/) |
| The configuration of splitting data and log onto separate volumes for PostgreSQL, the recovery procedure, and not using `pg_backup_start` | [NetApp: PostgreSQL with ONTAP](https://docs.netapp.com/us-en/ontap-apps-dbs/postgres/postgres-overview.html) |
| That the application-consistent and crash-consistent flags are for recording and there is no difference from ONTAP's perspective | [NetApp: Application snapshots (REST API)](https://docs.netapp.com/us-en/ontap-restapi/application_applications_application.uuid_snapshots_endpoint_overview.html) |
| Creating a FlexClone and specifying the parent snapshot | [NetApp: volume clone create](https://docs.netapp.com/us-en/ontap-cli/volume-clone-create.html) |

---

### Related documents

- [Domain — Block storage](../README.md) — this module's hub
- [A snapshot of a LUN is crash-consistent by default](a-snapshot-of-a-lun-is-crash-consistent.md) — the definition of consistency and the judgment on the requirement side
- [The LUN layout decides the recovery granularity (日本語)](../../../../ja/domains/block-storage/notes/lun-layout-decides-recovery-granularity.md) — why data and WAL are split
- [Capacity is counted in three places](capacity-is-counted-in-three-places.md) — the path by which clones and snapshots bear on capacity
- [What block monitoring shows and does not (日本語)](../../../../ja/domains/block-storage/notes/what-block-monitoring-shows.md)
- [Evidence policy](../../../evidence-policy.md)

## Verify it in your environment

| # | Step | What it tells you |
|---|---|---|
| 1 | Split the data and the WAL / redo onto LUNs on separate volumes | That the configuration is one that needs a fence |
| 2 | Check that `vserver consistency-group create` works | **That it is usable with `fsxadmin`** |
| 3 | Under load, run `snapshot create … -write-fence true` and **measure the time to return** | The fence duration in your own environment. **The gap to the limit is unknown until the limit value can be confirmed** |
| 4 | `volume snapshot show -snapshot <name> -fields volume,create-time` | **That the timestamps of all volumes match** |
| 5 | Record the maximum committed key immediately before and after | The footing to later judge the lost range |
| 6 | Map the clone to a **separate host's igroup** and start it | **That `lun map` is needed separately** |
| 7 | Check `redo starts` / `redo done` in the log after startup | **That the DB actually replayed.** Without this it is not a verification |
| 8 | Count whether all rows up to the recorded maximum key are present | **That no committed row was lost** |
| 9 | Do the same with `-write-fence false` and compare the results | **The effect of the fence** (do not do this in production) |

**Do step 9 in a test environment.** It is a procedure that creates a broken state without a fence.

The timestamp match in step 4 can be confirmed with this read-only command.

```bash
ssh <svm-management-endpoint> volume snapshot show -snapshot <name> -fields volume,create-time
```

### Expected output

```text
The create-time of every volume in the consistency group matches (the write fence fixed the same
point in time). If the timestamps mix, the order of dependent writes is broken and the DB's
recovery loses its premise.
```

This command only reads the snapshot creation time; it changes nothing on the snapshot or the DB. The fence duration changes with the volume count and load, so measure it with your production configuration.

## Read next

[What does block monitoring not show? (日本語)](../../../../ja/domains/block-storage/notes/what-block-monitoring-shows.md)
