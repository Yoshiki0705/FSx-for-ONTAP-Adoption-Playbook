---
title: Some SVMs cannot serve SMB. The cause is not when they were created but a deleted CIFS server, and recreating it through the ONTAP REST API restores it
lifecycle: [assess, design, build]
domains: [multiprotocol-identity]
evidence: verified
verified_on: 2026-09-02
ontap_version: 9.18.1P3D1
region: ap-northeast-1
lang: en
---

# Some SVMs cannot serve SMB. The cause is a deleted CIFS server, and the ONTAP REST API restores it

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/multiprotocol-identity/notes/smb-service-lost-on-cifs-server-delete.md) | [English](smb-service-lost-on-cifs-server-delete.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

[🏠 Repository home](../../../README.md) | [Domain — Multiprotocol identity](../README.md)

> This is the English translation. Japanese is authoritative for technical accuracy. Please report any discrepancy.

---

## Conclusion

**Some SVMs have data LIFs whose service policy does not include `data-cifs`.** In that state the SVM lists `cifs` among its allowed protocols, a CIFS server can be created, and even `Authentication Style` looks correct — but **port 445 never opens**.

```text
FsxIdEXAMPLE::> vserver cifs show -vserver <svm>
                         CIFS Server NetBIOS Name: <name>
                    NetBIOS Domain/Workgroup Name: WORKGROUP
                             Authentication Style: workgroup
                CIFS Server Administrative Status: up      ← looks healthy

(the same SVM's data LIF)
FsxIdEXAMPLE::> network interface show -vserver <svm> -lif nfs_smb_management_1 -fields services
services: data-core,data-nfs,management-ssh,management-https,data-s3-server,data-dns-server
                                        ↑ data-cifs is absent

(from a client)
<svm-data-lif>:445 closed/filtered      ← NFS on 2049 is open
```

**This note previously attributed the cause to when the SVM was created. That was wrong.**

| | Previously | Now |
|---|---|---|
| Cause | The SVM's creation date (behaviour presumed to change around 2026-06) | **A CIFS server was deleted and then recreated through the ONTAP CLI** |
| Workaround | **Create a new SVM and migrate the data — nothing else** | **Delete the CIFS server and recreate it through the ONTAP REST API. No data migration** |
| How to tell | Whether the Amazon FSx API's `Endpoints.Smb` is `null` | **Whether `services` contains `data-cifs`. `Endpoints.Smb` reflects AD membership and cannot decide this** |

**The workaround was the most harmful of the three.** It named SVM recreation and data migration as the only route for a condition that requires neither.

---

## The claim that has been withdrawn

The note stated that non-AD SVMs created before 2026-06-09 lack `data-cifs` while those created from 2026-06-24 have it regardless of AD. **The current state of one file system refutes that.**

| SVM | Created | AD-joined | `data-cifs` |
|---|---|---|---|
| A | 2026-02-10 | No | **Absent** |
| B | 2026-05-14 | Yes | Present |
| C | 2026-05-22 | No | **Absent** |
| D | 2026-05-26 | Yes | Present |
| E | 2026-06-09 | No | **Absent** |
| F | 2026-07-12 | Yes | Present |

**No date divides them.** B, from 2026-05-14, has it; C, created eight days later, does not. **What correlates across these six is not the creation date but whether a CIFS server exists** — all three with `data-cifs` have a running CIFS server, and all three without have none.

**What previously looked like a date boundary was a confound: the older an SVM is, the more chances there have been to create and delete a CIFS server on it.** The control at the time was that a non-AD SVM created that day did have `data-cifs` — but not because it was new. **It was because nothing had deleted its CIFS server yet.**

> **On the measurement**: a boundary visible in a table sorted by date was adopted as the explanation
> of the mechanism. **A boundary appearing along the axis you sorted by is not evidence that the axis
> is the cause.** The correlated second axis — here the history of CIFS server creation and deletion —
> had not been eliminated.

---

## Cause — a deleted CIFS server recreated through the CLI

**AWS Support reproduced this on the same version (ONTAP 9.18.1P3D1) and identified the mechanism** (2026-09-02).

| # | Operation | `data-cifs` | 445 |
|---|---|---|---|
| 1 | Immediately after creating an SVM | **Present** (regardless of AD membership or whether a CIFS server exists) | Closed (no CIFS server yet) |
| 2 | Create a CIFS server | Still present | **Open** |
| 3 | **Delete the CIFS server** | **Removed** | Closed |
| 4 | Recreate with the ONTAP CLI `vserver cifs create` | **Not restored** (the command succeeds and the CIFS server comes up) | **Stays closed** |
| 5 | Recreate with the ONTAP REST `POST /api/protocols/cifs/services` | **Restored** | **Open** |

At step 4 the `services` string is the following, **an exact match for the affected SVMs here**.

```text
data_core,data_nfs,management_ssh,management_https,data_s3_server,data_dns_server
```

**SVM creation was also confirmed to contain no branch on AD configuration or on the date.** No change landed in that path between 2026-06-09 and 2026-06-24.

**What makes step 4 awkward is that creating the CIFS server succeeds.** No error appears, `vserver cifs show` looks healthy, and only 445 stays closed.

**Unjoining AD through Amazon FSx also deletes the CIFS server.** So "stop using AD and switch to a workgroup" passes through step 3.

> **Evidence**: **this section reports what AWS Support found; it was not reproduced here.** The
> observed state — the contents of `services`, and 445 being closed — is `verified`, but **the causal
> chain in steps 3 to 5 and the recovery procedure have not been carried out.** Doing so requires
> deleting a CIFS server on an SVM in a shared file system, which removes SMB share definitions and
> sessions along with it, so it has not been run without a disposable SVM. **No public documentation
> describes it either** — AWS Support likewise states that no published material explaining the
> behaviour could be found.

---

## Recovery procedure

**This is the procedure AWS Support supplied. It has not been run here.** Confirm it on a test SVM before applying it.

```bash
# 1. Get the UUID of the target SVM's CIFS server
curl -X GET -u fsxadmin -k \
  "https://<management-endpoint>/api/protocols/cifs/services?svm.name=<svm-name>&fields=svm.uuid"

# 2. Delete the current CIFS server
curl -X DELETE -u fsxadmin -k \
  "https://<management-endpoint>/api/protocols/cifs/services/<UUID>"

# 3. Recreate it through REST (workgroup configuration)
curl -X POST -u fsxadmin -k -H "Content-Type: application/json" \
  -d '{"svm":{"name":"<svm-name>"},"name":"<cifs-server-name>","workgroup":"<workgroup-name>","enabled":true}' \
  "https://<management-endpoint>/api/protocols/cifs/services"
```

```text
# 4. Confirm the restoration
FsxIdEXAMPLE::> network interface show -vserver <svm> -lif nfs_smb_management_1 -fields services
```

**Step 2 deletes SMB share definitions and SMB sessions.** On an SVM where 445 is not open there is no practical impact, but record any share definitions that remain beforehand.

**The ONTAP REST API is reachable at the file system's management endpoint with `fsxadmin` credentials.** Either disable TLS verification or trust the per-region AWS CA bundle.

---

## Deciding this in your own environment

```text
# Service list on every SVM's data LIF
FsxIdEXAMPLE::> network interface show -fields vserver,lif,services -role data
```

Look for `data-cifs` in the `services` of `nfs_smb_management_1`. **Whether the SVM's `allowed-protocols` includes `cifs` decides nothing** — the affected SVMs had `cifs` there too.

| Check | `data-cifs` present | `data-cifs` absent |
|---|---|---|
| 445 on the data LIF | Opens | **Does not open** |
| 2049 (NFS) on the data LIF | Opens | Opens |
| `data-cifs` in `services` | Present | **Absent** ← **this is the test** |

**The Amazon FSx API's `Endpoints.Smb` cannot decide this.** This note previously offered whether `Endpoints.Smb` is `null` as a test that needs no ONTAP login, but **that value tracks whether the SVM is AD-joined and says nothing about `data-cifs` or about whether SMB can be served.**

AWS Support reports observing **an SVM with `data-cifs` present, a running CIFS server, and 445 open, whose `Endpoints.Smb` was `null` because it was not AD-joined**. On a workgroup SVM, `null` is the healthy value.

> **Note**: the three SVMs here with a value in `Endpoints.Smb` are the same three that have
> `data-cifs`, **but only because this file system contains no SVM that runs a CIFS server without
> AD.** The agreement is coincidental and does not make it a valid indicator.

---

## What `fsxadmin` cannot add

A lost `data-cifs` cannot be restored by editing the service policy directly.

```text
FsxIdEXAMPLE::> security login role show -role fsxadmin -fields cmddirname,access
fsxadmin "network interface service-policy" readonly
fsxadmin "network interface create"         readonly

(REST behaves the same)
PATCH /api/network/ip/service-policies/<uuid>
  → {"error":{"message":"not authorized for that command","code":"6"}}
```

**This is not insufficient privilege.** `set -privilege advanced` works over the same path (confirmed by running an advanced-only command). The role marks that command family `readonly`.

**So the recovery path is not editing the service policy but recreating the CIFS server through REST and letting ONTAP reattach it.**

> **On the error message**: running a role-restricted command in the CLI returns
> **`"<command>" is not a recognized command`** rather than anything about permissions. **It is the
> same wording as a command that does not exist, so the time goes into suspecting a typo.** This is
> ONTAP behaviour rather than specific to FSx for ONTAP; the NetApp KB
> [Command fails with "Command is not recognized command"](https://kb.netapp.com/on-prem/ontap/Ontap_OS/OS-KBs/Command_fails_with_Command_is_not_recognized_command)
> attributes it to being unable to run the command with the correct role or at the `advanced`
> privilege level (AWS Support gave the same triage, 2026-09-02). **When the spelling is right and the
> command is still not recognized, check that command family's `access` with
> `security login role show -role <role>`.**

**The list of command families that are `readonly` or `none` for `fsxadmin` is not published.** A request to document it has been filed with AWS Support, which replied that it will be considered as an improvement request (2026-09-02). **For now the only route is reading `security login role show` in your own environment.**

**Using a different role is not a way around it either.** AWS Support confirmed that `network interface service-policy` is **`readonly` under every one of** `fsxadmin`, `fsxadmin-readonly`, `vsadmin`, `vsadmin-backup`, `vsadmin-protocol`, `vsadmin-readonly`, `vsadmin-snaplock`, and `vsadmin-volume`, and that **no role available on FSx for ONTAP can change a service policy** (2026-09-02). The measurement above covers `fsxadmin` alone, but enumerating roles to find an opening is unnecessary.

> **On the difference from on-premises ONTAP**: where an administrator can edit the service policy
> directly, this symptom ends with fixing the policy. **Not having that route is specific to
> FSx for ONTAP**, which is why the recovery path is limited to recreating the CIFS server through
> REST. Factor that difference in when reading procedures written for other ONTAP environments.

---

## Impact and what to do

| Situation | Impact |
|---|---|
| Want to start using SMB on an existing SVM | **Recreate the CIFS server through REST and it works.** No SVM recreation |
| Only NFS or S3 in use on an existing SVM | No impact |
| Testing SMB in a workgroup configuration | **Time goes into working out why 445 is closed**, because creating the CIFS server succeeds |
| Unjoined AD and switched to a workgroup | **Unjoining deletes the CIFS server and `data-cifs` is lost.** Recreating through the CLI lands in this state |

> **On design**: **deleting a CIFS server is also an operation that breaks the service policy**,
> and that includes unjoining AD. In any runbook involving deletion and recreation, either
> **recreate through the ONTAP REST API** or add a step that checks `services` afterwards.

---

## A limit you meet alongside this

**Recreating SVMs is no longer the plan**, but adding SVMs for other reasons runs into the per-throughput-capacity limit.

```text
ServiceLimitExceeded: Amazon FSx does not support having more than 6 storage virtual machines
for an ONTAP file system with 128 MBps of throughput capacity.
```

Since it affects billing, confirm any decision that involves changing throughput capacity first.

---

## Not confirmed

- **The causality in steps 3 to 5, and the recovery procedure.** This is what AWS Support reported and **has not been run here.** It requires deleting a CIFS server on a shared file system, and no disposable SVM has been prepared
- **Whether a CIFS server was ever deleted on the affected SVMs here.** The current state is consistent with the mechanism, but **there is no way to review the deletion history.** A workgroup CIFS server was created and deleted on one SVM during testing, but whether `data-cifs` was lost before or after that cannot be established
- **Whether ONTAP outside FSx for ONTAP behaves the same.** AWS Support considers this ONTAP-side processing rather than specific to FSx for ONTAP, and suggests reproducing it on on-premises ONTAP and documenting it through NetApp. **Not done**
- **Why `data-cifs` is not restored when created through the ONTAP CLI.** The CLI and REST paths were shown to differ, but whether that is by design is unclear
- **What happens when AD configuration is added later to an SVM without `data-cifs`.** Joining AD through Amazon FSx creates a CIFS server, so it may be restored, but this was not measured

---

## Primary sources

- AWS: [Managing FSx for ONTAP resources using NetApp applications](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-resources-ontap-apps.html) — using the ONTAP REST API as `fsxadmin`
- AWS re:Post: [How do I use the FSx for ONTAP REST API?](https://repost.aws/knowledge-center/fsx-ontap-rest-apis)
- NetApp KB: [Command fails with "Command is not recognized command"](https://kb.netapp.com/on-prem/ontap/Ontap_OS/OS-KBs/Command_fails_with_Command_is_not_recognized_command)

**No public material explaining that `data-cifs` is lost when a CIFS server is deleted was found while writing this note.** AWS Support is still considering whether to publish it as documentation or as a knowledge article. **Filing is not publishing, so treat the behaviour as undocumented.**

---

## Related

- [SMB local users carry no last-logon attribute](../../../domains/multiprotocol-identity/notes/local-user-inventory-without-last-logon.md)
- [The AD dependency lasts a lifetime, not just the join](../../../domains/multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md)
- [Security style determines the permission evaluation model](security-style-and-permission-evaluation.md)
- [Limits and quotas](../../../../ja/reference/limits/README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/multiprotocol-identity/notes/smb-service-lost-on-cifs-server-delete.md) | [English](smb-service-lost-on-cifs-server-delete.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
