---
title: Using one NTFS volume over SMB and NFS at once, names, locks and time-to-readable differ by protocol
lifecycle: [design, migrate]
domains: [multiprotocol-identity]
evidence: documented
source: https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/ja/stage-1-multiprotocol.md
lang: en
---
# What differs when one NTFS volume is used over SMB and NFS at once?

The characters allowed in names, whether a lock stops the other protocol's operations, and how soon the other client can read differ. A delay of about 8 seconds appeared only when Windows was the reader (one measurement, in the FSx-for-ONTAP-App-Modernization-Patterns repository).
<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/multiprotocol-identity/notes/cross-protocol-access-to-one-ntfs-volume.md) | [English](cross-protocol-access-to-one-ntfs-volume.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
## What you will learn

- That a name containing `\` was rejected over Linux SMB and could be created over NFS
- That a Windows `FileShare.None` also refused an NFS open, and a Linux exclusive lock stopped a Windows read
- That the time from save to readable was about 8 seconds only when the reader was Windows

## What this note does not answer

- Whether the same values reproduce (each pair was measured once)
- Why the delay is about 8 seconds (untested)
- Whether a writer that takes no lock can be stopped
- Volumes with security style `unix` or `mixed`, other ONTAP versions, Multi-AZ

## Prerequisite level

intermediate

## Body

<a id="what-differs-when-one-ntfs-volume-is-used-over-smb-and-nfs-at-once"></a>
[🏠 Repository home](../../../README.md) | [Domain — Multiprotocol and identity](../README.md)

---

### Conclusion

**An application that uses an NTFS-style volume over both SMB and NFS should check three things per protocol.** Each is a value measured once, in another repository.

| Aspect | Observation |
|---|---|
| Characters in names | A name containing `\` was rejected over Linux SMB (cifs) with `errno=22`. Over NFS it could be created, and `\` became part of the name. Windows showed it as an 8.3 short name (`SEPCHE~1.TXT`) and could read it |
| Locking | A Windows `FileShare.None` also refused the open from NFS (`errno=13`). A Linux `fcntl` exclusive lock stopped a Windows read as a lock violation. After the holder released, the other side could acquire it |
| Save to readable | About 8 seconds when Windows was the reader; about 0.1 seconds when Linux was the reader |

> **Evidence**: `documented`. The source is the [stage 1 document (Japanese)](https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/ja/stage-1-multiprotocol.md) of FSx-for-ONTAP-App-Modernization-Patterns, where it is recorded as `verified`. The author of this document did not rerun the environment, so the tier is not raised here. **Each pair was measured once and reproducibility is not confirmed. It is not a performance claim.**

---

### Background

On an NTFS-style volume an NFS client can still mount and read and write ([Security style determines the permission model](security-style-and-permission-evaluation.md)). When both protocols open the same file, the file-name rules, the meaning of a lock, and how a change becomes visible depend on the client implementations. Storage-side settings do not make them uniform

---

### Lock combinations

Two clients operated on the same file at the same time; while one held it, the other tried to open it. The two were synchronized through a separate S3 bucket, not through the volume under test.

| Holder | How it held | Contender while held | After release |
|---|---|---|---|
| Windows (SMB) | `FileShare.None` | Linux SMB: read and write opens refused (`errno=16`). Linux NFS: also refused (`errno=13`) | Acquired |
| Linux (SMB) | `fcntl` exclusive lock | Windows: open succeeded, read hit a lock violation, exclusive open hit a sharing violation | Acquired |
| Linux (NFS) | `fcntl` exclusive lock | Same | Acquired |

Only one side taking a lock while the other tried to open was measured. Whether a writer that takes no lock can be stopped was not measured.

---

### Time from save to readable

The reader listed and read every 100 ms, so the value resolution is about 100 ms.

| Writer | Reader | Save complete to readable |
|---|---|---|
| Windows (SMB) | Linux (SMB) | 99 ms |
| Windows (SMB) | Linux (NFS) | 88 ms |
| Linux (SMB) | Windows (SMB) | 7,849 ms |
| Linux (NFS) | Windows (SMB) | 8,085 ms |

- Whether the writer used SMB or NFS, about 8 seconds appeared when Windows was the reader. The delay followed the reader being Windows, not the writer's protocol.
- The source reports the same shape in three other runs (including 2026-10-11 and 2026-10-12).
- **The cause of the delay is untested.** The source guesses that the Windows SMB client caches directory contents or a "file not found" result, and did not check the client settings. This document also treats that guess as `hypothesis`.
- What to do: where a Windows client reads a file that Linux wrote, add a wait or retry that tolerates the delay. Do not design for no delay because the opposite direction is fast. The seconds measured are for one configuration and do not indicate the delay in another.

---

### Test environment

| Item | Value |
|---|---|
| ONTAP version | 9.19.1P2 (version not specified at creation; value from one creation) |
| Region | ap-northeast-1 |
| Configuration | Generation 1 `SINGLE_AZ_1`, 1,024 GiB, 128 MBps. One NTFS volume. An SVM joined to AWS Managed Microsoft AD (Standard) |
| Clients | Windows Server 2022 (SMB 3) and Amazon Linux 2023 (SMB with `cifs` and `sec=ntlmssp`; NFS with `vers=4.1` and `sec=sys`) |
| Measured on | 2026-10-07 |
| Runs | One per pair |
| Clocks | Offset to Amazon Time Sync Service: Windows 1.5 to 2.1 ms, Linux under 0.01 ms |

> **Note**: These are measurements in this environment, not a general service limit and not a guarantee of reproduction in production.

---

### Common misconceptions

| Misconception | Actual |
|---|---|
| The same volume allows the same names from any client | A name containing `\` could be created over NFS and was rejected over Linux SMB |
| SMB locks do not concern NFS clients | A Windows `FileShare.None` refused the NFS open |
| A saved file is immediately readable from the other side | About 8 seconds when Windows was the reader; about 0.1 seconds the other way |

---

### Related documents

- [Security style determines the permission model](security-style-and-permission-evaluation.md)
- [The NFS-side permission view does not match the enforced outcome](nfs-side-view-does-not-explain-ntfs-denials.md)
- [Evidence policy](../../../evidence-policy.md)

## Verify it in your environment

**Before checking, make sure the NFS mount is in place and both clients' clocks are synchronized (Amazon Time Sync Service).**

| # | Step | What it confirms |
|---|---|---|
| 1 | From an NFS client, create a file whose name contains `\` under a dedicated directory. Try the same name on a Linux cifs mount | Whether the name rules differ by protocol. Create only under a dedicated directory |
| 2 | On Windows, hold a file open with `FileShare.None` and open the same file from an NFS client | Whether the exclusion reaches NFS |
| 3 | On Linux, take an `fcntl` exclusive lock and read from Windows | Whether it is a lock violation |
| 4 | Record the writer's save time and the reader's first successful read at 100 ms or finer, on both sides | The delay to readable. Measure several times; do not judge from one value |

### Expected output

```text
The name rules, the reach of the locks, and the delay to readable are recorded per protocol pair
```

Do this on a test volume. Do not create files outside the dedicated directory, and do not apply it to a production volume.

## Read next

[The NFS-side permission view does not match the enforced outcome](nfs-side-view-does-not-explain-ntfs-denials.md)
