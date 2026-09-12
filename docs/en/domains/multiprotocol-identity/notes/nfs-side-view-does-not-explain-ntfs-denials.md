---
title: On an NTFS-style volume the permission view available from NFS does not match the enforced outcome — neither the Deny nor the principal appears
lifecycle: [design, migrate, operate]
domains: [multiprotocol-identity, security-governance]
evidence: verified
verified_on: 2026-09-12
region: ap-northeast-1
ontap_version: 9.18.1P6
lang: en
---
# On an NTFS-style volume the permission view available from NFS does not match the enforced outcome
<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/multiprotocol-identity/notes/nfs-side-view-does-not-explain-ntfs-denials.md) | [English](nfs-side-view-does-not-explain-ntfs-denials.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

[🏠 Repository Top](../../../README.md) | [Domain — Multiprotocol & Identity](../README.md)

---

## Conclusion

**Reaching the same data over NFS and being able to explain its permissions from NFS are two
different things.** On a volume with the NTFS security style, `nfs4_getfacl` returns three
synthesised entries and nothing else (`OWNER@` / `GROUP@` / `EVERYONE@`): **no Deny ACE, no name of
the principal the ACE was set for, and no inheritance flags.**

Measured, that representation **contradicted** the enforced outcome. The NFSv4 ACL showed `OWNER@`
as permitted to write, ONTAP reported the owner of that directory as the test user, and the write by
that user was refused.

Worse, **the NTFS-style directory that refused the write and the UNIX-style directory that allowed it
had identical mode bits and identical NFSv4 ACLs.** From the NFS side alone the two cannot be told
apart.

### Where the usable answer is

**ONTAP's `effective-permissions` agreed with the enforced outcome in every case measured.** On the
refused directory, `write` / `append` / `write_ea` / `write_attributes` were absent from the list it
returned; on the permitted directory they were present. **"Not answerable from NFS" is not "not
answerable".** Move the verification path to the storage side and the question is answered by an API
both vendors document.

That path needs an ONTAP credential, though. **The person verifying with `ls -l` today may not be
able to keep verifying after the move. Decide who holds that credential before the migration, not
after.**

The order of the decision is in
[Where to verify who can access a file after a protocol change](../../../../ja/reference/decision-trees/verifying-permissions-after-a-protocol-change.md) (日本語).

### What to change tomorrow

| # | Target | Reason |
|---|---|---|
| 1 | Any procedure that names `ls -l` or `nfs4_getfacl` **as the mechanism** for checking permissions | After the move that mechanism no longer answers the question |
| 2 | Any approval path where a reviewer who sees only the NFS side signs off a permission change | The representation contains no Deny, so there is nothing to base the approval on |
| 3 | Any automation that decides by reading mode bits | **It keeps running without error and only the answer changes.** This is the hardest one to find |

> **Evidence**: `verified` — measured in the single environment described under "Test environment".
> **It does not guarantee a general service limit, nor reproduction on another version or
> configuration.** Run "Verifying in your own environment" before using it in a decision.
>
> **The measurement was made in a disposable verification environment against synthetic data.** It
> contains no production data, no real users and no real organisational information. For a regulated
> workload, what is recorded here is technical behaviour and **it does not replace a legal,
> compliance or privacy assessment.**

## Background

After a modernization changes the protocol from SMB to NFS, operations reach for the Linux side to
check permissions. Given that `ls -l` and `nfs4_getfacl` are available, expecting them to explain the
result is the natural assumption.

That assumption does not hold. On an NTFS-style volume the permission evaluation uses the Windows
ACL, and the mode bits and NFSv4 ACL visible to an NFS client are **a projection ONTAP synthesises**.
A projection cannot express a Deny and does not carry principals by name.

## Detail

### The record has three parts

A permission result is usable only when all three are present: the ACE that was set, the
representation on the NFS side, and whether the access actually succeeded.

**Part 1 — the ACE as set through the ONTAP REST API** (`POST /protocols/file-security/permissions/`)

| Path | ACE |
|---|---|
| `allow/` | `access_allow` for the test user, modify-equivalent, `apply_to` = this_folder |
| `deny/` | `access_deny` for the test user on the four write bits, plus `access_allow` on the read bits |
| `inherited/` | `access_allow` for the test user, `apply_to` = this_folder + sub_folders + files |
| `inherited/child` | The above arrived with `inherited: true` (**inheritance did work**) |

All three also carried an `Everyone` full control ACE inherited from the volume root. As noted below
this removes the discriminating power of `allow/`, but not that of `deny/`.

**Part 2 / Part 3 — the NFS-side representation and the enforced outcome** (NFSv4.1, `sec=sys`, run
as the Active Directory user)

NTFS style, `/ntfsvol`:

| Path | mode bits | NFSv4 ACL | read | write |
|---|---|---|---|---|
| `allow/` | 777 | `A::OWNER@:rwaDxtTnNcCy` / `A:g:GROUP@:rwaDxtTnNcy` / `A::EVERYONE@:rwaDxtTnNcy` | ok | ok |
| `deny/` | **755** | `A::OWNER@:rwaDxtTnNcCy` / `A:g:GROUP@:rxtncy` / `A::EVERYONE@:rxtncy` | ok | **refused** |
| `inherited/child` | 777 | identical to `allow/` | ok | ok |

UNIX style, `/unixvol` (the control volume; no Windows ACE was set on it at all):

| Path | mode bits | NFSv4 ACL | read | write |
|---|---|---|---|---|
| `allow/` | 755 | `A::OWNER@:rwaDxtTnNcCy` / `A:g:GROUP@:rxtncy` / `A::EVERYONE@:rxtncy` | ok | ok |
| `deny/` | 755 | as above | ok | **ok** |
| `inherited/child` | 755 | as above | ok | ok |

### Three ways the representation fails to explain the outcome

1. **The Deny does not appear.** The NFSv4 ACL carries three `A:` (allow) entries and not one `D:`
   (deny) entry. What stops the write is the Windows Deny ACE.
2. **The principal does not appear.** The ACE was set for a named Active Directory user, but the NFS
   side has only `OWNER@` / `GROUP@` / `EVERYONE@`. There is no way to learn from NFS who the
   permission applies to.
3. **An NTFS refusal and a UNIX permit produce the same representation.** NTFS `deny/` and UNIX
   `deny/` matched on mode bits (755 in both cases) and on the NFSv4 ACL, and the outcomes diverged
   into refused and succeeded. **Identical representation with different outcomes means the
   representation is not evidence.**

### A separate trap: the owner displayed as `nobody`

The client displayed the owner as `nobody(65534)`. ONTAP reports the owner as the test user. The
cause is an NFSv4 ID domain mismatch: the SVM's `v4_id_domain` defaults to
`<region>.compute.internal` (measured: `ap-northeast-1.compute.internal`), which does not match the
Active Directory domain name.

That breaks the reading of `755`. It can be read as "the owner may write", but the client has not
resolved who the owner is. **Mode bits whose owner cannot be resolved are not usable as an
explanation of the outcome.**

### The backslash disappearing from a name-mapping replacement

**Before the measurement could start, this one character refused every access.** On an NTFS-style
volume the UNIX UID has to be mapped to a Windows account, and storing `DOMAIN\user` as that rule's
replacement produces `DOMAINuser`, **because ONTAP treats `\` as an escape character.**

The way it refuses is the problem. The ONTAP event log reported:

```text
Determined UNIX id 675401149 is UNIX user 'mpadtest'
Mapping Successful for Unix-user 'mpadtest' to Windows user 'MPADmpadtest' at position 1
Could not find Windows name 'MPADmpadtest'
FAILURE: Name mapping for UNIX user 'mpadtest' failed
```

**The rule itself reports success, and only the resolution of the resulting name fails.** So the
error points at Active Directory and does not read as a problem with how the rule was written. The
client-side symptom is `EACCES`, and because `opendir` is refused too, **even `ls` fails**. That shape
looks like an export policy problem; the export policy was correct.

**Reading the value back does not help either.** The single stored backslash is returned as stored,
so it cannot be distinguished from the intended value. The correct stored value carries **two
backslashes**, which ONTAP interprets as one.

| | Value sent | ONTAP's interpretation |
|---|---|---|
| Wrong | `MPAD\mpadtest` | `MPADmpadtest` (the separator disappears) |
| Correct | `MPAD\\mpadtest` | `MPAD\mpadtest` |

**Judge whether it worked from the resolution result, not by reading the rule back.** A read-back
looks correct even for a wrong value. Two routes can decide it:

| Route | What to look at |
|---|---|
| `GET /api/support/ems/events` filtered on `secd` | That no `noNameMap` appears. If one does, its body carries the name ONTAP tried |
| `GET /protocols/file-security/effective-permissions/{svm.uuid}/{path}?user=DOMAIN\user` | That a permission list comes back. **If the mapping did not resolve, this call itself returns no answer** |

The second is the same call the measurement uses, so **verifying the mapping needs no separate
step.** Making it once up front detects this section's failure before the measurement begins.

### NFSv4 ACLs are disabled by default

`nfs4_getfacl` initially returned "Operation to request attribute not supported" at all, because the
SVM's NFS configuration had `v40_features.acl_enabled` and `v41_features.acl_enabled` **both false by
default**. This is unrelated to the security style — the UNIX-style volume behaved the same way.

Enabling it is not sufficient on its own: **an existing mount keeps the capability set it
negotiated.** The attribute stays `not supported` on that mount until it is remounted.

Note also that `nfs4_getfacl` prints "not supported" while **exiting with status 0**. A record that
consults only `$?` will record a representation it never read as having been read.

## Test environment

| Item | Value |
|---|---|
| ONTAP version | NetApp Release 9.18.1P6 |
| Region | ap-northeast-1 |
| Configuration | Single-AZ first generation, 1,024 GiB SSD, 128 MBps, AWS Managed Microsoft AD (Standard) |
| SVM root volume | UNIX security style |
| Measured volume | NTFS style (`/ntfsvol`); the control is UNIX style (`/unixvol`) |
| Client | Amazon Linux 2023, joined to AD with sssd, NFSv4.1 `sec=sys` |
| Test user | One Active Directory user, **not a member** of `Domain Admins` (primary group `Domain Users` only) |
| Measured on | 2026-09-12 |

> **Note**: the above is a measurement in this environment. It does not guarantee a general service
> limit, nor reproduction in a production environment.

### Limits of the result, against the criteria fixed before measuring

- `allow/` has no discriminating power. The `Everyone` full control inherited from the volume root
  already permits the write, so success cannot be attributed to the ACE.
- `deny/` does have discriminating power. In the NTFS evaluation order an explicit Deny takes
  precedence over an Allow, so the refusal is observable even with `Everyone` full control alongside
  it. ONTAP's `effective-permissions` likewise returned `deny/` with `write` / `append` /
  `write_ea` / `write_attributes` dropped.
- The conclusion of this note therefore rests on the comparison between `deny/` and the control
  volume, and not on `allow/`.

## Open questions

**What was not measured, listed.** The conclusion rests on a measurement of ACEs for a single user;
each of the following can only be expected to behave the same way, and was not confirmed.

| # | Open | Why it matters |
|---|---|---|
| 1 | **An ACE granted to a group** (measure this one first if you measure only one) | Real ACLs are group-based. Group resolution is a separate path from user resolution, with failure surfaces of its own such as nested groups and token size. **This note measured user ACEs only** |
| 2 | Access from a service account or a container's runtime identity | How a principal that is not a domain user passes through name mapping is unconfirmed. It is the realistic modernization path, so the priority is high |
| 3 | A volume brought in by a migration | The measurement used directories created on an empty volume. A volume migrated in with existing ACLs was not measured |
| 4 | The performance effect of enabling NFSv4 ACLs | Enabling it was required for this measurement, but **the effect on performance was not measured.** Do not assume it is free |
| 5 | Removing the inherited `Everyone` from the volume root | It is what removed the discriminating power of `allow/`. A re-measurement without it has not been done |

## Verifying in your own environment

| # | Step | What it establishes |
|---|---|---|
| 1 | Read `v41_features.acl_enabled` and `v4_id_domain` with `GET /api/protocols/nfs/services/{svm.uuid}?fields=**` | If ACLs are disabled the NFS-side representation cannot be read at all. If the ID domain differs from AD, the owner will display as `nobody` |
| 2 | Set an explicit Deny ACE for the target user on an NTFS-style volume with `POST /protocols/file-security/permissions/{svm.uuid}/{path}` | That it could be set (Part 1) |
| 3 | Run `stat` and `nfs4_getfacl` on the NFS client, and confirm the output begins with `# file:` | That the representation was read. Exit status 0 is not evidence |
| 4 | Write as the same user | The outcome (Part 3). If it disagrees with the representation, the disagreement is the finding |
| 5 | Repeat 3 and 4 on the UNIX-style control volume | If no difference appears, that is a finding about the environment and not about the security style |

For the full procedure see [Before adopting into production](../../../evidence-policy.md#before-adopting-into-production).

The smallest environment that reproduces this, with scripts, is
[`examples/multiprotocol-ad/`](../../../../../examples/multiprotocol-ad/README.md).

## Common misconceptions

| Misconception | Actually |
|---|---|
| If it is not visible from NFS, the permission has been lost | It has not. Evaluation happens against the Windows ACL and the refusal is in force. Only the representation is missing |
| An empty `nfs4_getfacl` means there is no ACL | The ACL attribute itself is disabled by default. It cannot be read until it is enabled and the client remounted |
| `nfs4_getfacl` exiting 0 means the ACL was read | It returns 0 while printing "not supported". Decide on whether the output begins with `# file:` |
| Mode bits of 755 mean the owner may write | Not when the owner cannot be resolved (displayed as `nobody`). Measured, the owner's own write was refused |
| Aligning the security style aligns the representation | The mode bits and NFSv4 ACL were identical between an NTFS refusal and a UNIX permit. What matches is the representation, not the behaviour |

## Related documents

- [Where to verify who can access a file after a protocol change](../../../../ja/reference/decision-trees/verifying-permissions-after-a-protocol-change.md) (日本語) — **mapping from the configuration you are moving from.** Decides whether your current verification mechanism still works after the move
- [A volume's security style determines the permission model](security-style-and-permission-evaluation.md)
- [Adding NFS to a volume already serving SMB needs no clone](../../../../ja/domains/multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md) (日本語)
- [`examples/multiprotocol-ad/`](../../../../../examples/multiprotocol-ad/README.md) — the reproduction environment
- [Evidence classification policy](../../../evidence-policy.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/multiprotocol-identity/notes/nfs-side-view-does-not-explain-ntfs-denials.md) | [English](nfs-side-view-does-not-explain-ntfs-denials.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
