---
title: SMB local users carry no last-logon attribute. An inventory has to be built from audit logs, and automating deletion is a separate judgment
lifecycle: [operate, optimize]
domains: [multiprotocol-identity, security-governance]
evidence: verified
verified_on: 2026-09-01
ontap_version: 9.18.1P3D1
region: ap-northeast-1
lang: en
---

# Do SMB local users have a last-logon attribute?

No. An inventory must come from audit logs, and "no activity" is not "unneeded".

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/multiprotocol-identity/notes/local-user-inventory-without-last-logon.md) | [English](local-user-inventory-without-last-logon.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That SMB local users carry no last-logon timestamp, so an inventory can only be built from file-access audit logs
- That "no activity" from audit logs is not "unneeded", and automating deletion is not advisable

## What this note does not answer

- How a logon attempt against a disabled account is distinguished in 4625 (unconfirmed)
- Behaviour with a large number of local users

## Prerequisite level

intermediate

## Body

<a id="smb-local-users-carry-no-last-logon-attribute-an-inventory-has-to-be-built-from-audit-logs-and-automating-deletion-is-a-separate-judgment"></a>

[🏠 Repository home](../../../README.md) | [Domain — Multiprotocol identity](../README.md)

> This is the English translation. Japanese is authoritative for technical accuracy. Please report any discrepancy.

---

### Conclusion

**An SMB local user object does not carry a last logon time.** Both the CLI and REST return only these fields:

```text
FsxIdEXAMPLE::> vserver cifs users-and-groups local-user show -vserver <svm> -instance
                                   Vserver: <svm>
                               Domain Name: <cifs-server-name>
                                 User Name: <cifs-server-name>\wgaudit
                                 Full Name: Workgroup Audit Test
                               Description: -
                       Is Account Disabled: false
```

REST returns only `svm`, `sid`, `name`, `full_name`, and `account_disabled`.

**So the only route to "which accounts have gone unused for N months" is the file access audit log.** That is a clear difference from an AD-joined configuration, where `lastLogonTimestamp` removes the need to build any of this.

And when building the inventory, **"no activity in the audit log" is not the same as "not needed".** The nature of the events available for the decision produces false positives structurally. **Automating deletion is not recommended.**

> **Evidence**: `verified` (2026-09-01, `ap-northeast-1`, ONTAP `9.18.1P3D1`).
> Local users were created on a workgroup SVM (`Authentication Style: workgroup`), logons, logoffs,
> and authentication failures were generated over SMB from Windows Server, and the EVTX files were
> collected and parsed with `python-evtx`. **The operational design parts are not measurements but
> judgments drawn from the measurements.** Each section says which it is.

---

### The events available, and what they are

| Purpose | Event | Field holding the user name | Nature |
|---|---|---|---|
| Logon activity | 4624 | `TargetUserName` | **Per SMB session, not a count of login actions** |
| Actual access | 4656 / 4663 | `SubjectUserName` | Per object. **Requires a SACL on NTFS** |
| Confirming an account is still live after disabling | 4625 | `TargetUserName` | Per authentication attempt |
| Current connections | — | — | `vserver cifs session show`, not the audit log |

**The field name differs between the logon events and the file access events.** Extracting on one name alone silently returns zero rows.

Recording conditions and measured values are in
[SMB logon auditing — 4624 is recorded](../../../domains/security-governance/notes/smb-logon-audit-event-coverage.md).

---

### False positives from deciding on 4624 alone

**Mapping and unmapping the same share three times from Windows with `net use` and `net use /delete` produced a single 4624.** What `net use /delete` removes is the share mapping; the authenticated session remains.

That property skews the decision in both directions.

| Usage pattern | How 4624 accumulates | Error in the inventory |
|---|---|---|
| Connect once and hold the session | **Does not accumulate** | Judged "no activity" despite daily use |
| Unstable network, reconnecting repeatedly | Accumulates heavily | Looks busier than the actual usage |
| A business account used only at quarter end | Zero within the window | "No activity" over a three-month window |
| A user on extended or parental leave | Zero within the window | A deletion candidate while still employed |

**The first two rows are properties established by measurement; the last two are consequences drawn from them.**

The remedy is to change the expression.

```text
last used = max(
    latest SystemTime per TargetUserName in 4624,
    latest SystemTime per SubjectUserName in 4656 / 4663
)
```

**4656 and 4663 are the more direct indicator of real use.** They are unaffected by session reuse. But on an NTFS volume nothing is emitted without a SACL, so **configuring SACLs becomes a precondition for the decision.**

---

### Disabling before deleting

**This is a design judgment, not a measurement.** Two reasons:

1. As above, the absence of 4624 is not the same as being unused
2. Deleting a local user cannot be undone. If a batch job, script, or scheduled task was using that account, the deletion is not an inventory step but an incident

```text
No access for N days      → disable the account (-is-account-disabled true) + notify the owning team
   ↓ objection period
N+M days with no objection → add to the inventory list and delete after approval
```

**Disabling also serves as detection.** A logon attempt against a disabled account is recorded as 4625, so **you can actively confirm whether it really is unused.** That becomes an automatic recovery loop for false positives, and evidence for the deletion decision.

Disabling is `-is-account-disabled true`, reflected in `Is Account Disabled` in `local-user show`. **That field is one of the few the object has, and the only place the inventory's state can be held on the SVM itself.**

---

### The register that keeps accounts out of scope

**A design judgment.** Some accounts cannot be distinguished from audit logs alone.

| Kind | Why no access activity appears |
|---|---|
| The built-in `Administrator` | Unused in normal operation, yet cannot be deleted |
| Service accounts | 4624 does not accumulate when an application holds a session permanently |
| Backup accounts | The run interval can be longer than the decision window |
| Machine accounts | They mix in with human accounts |

**The user name visible from the client and the one ONTAP records do not match.** In the measurement, Windows `Get-SmbConnection` showed a machine account while ONTAP's 4624 recorded the local user name used for the connection. **Exclude machine accounts explicitly when extracting.**

Recording purpose, owner, and expected usage frequency in a register when an account is issued fills the part audit logs cannot decide. **An audit log can show evidence of use; it cannot show that something has stopped being needed.**

---

### Choosing between a workgroup and AD membership

**A design judgment.** This note assumes a workgroup configuration with local users, but how much has to be built for the inventory can itself inform the choice.

| Aspect | Workgroup + local users | AD membership |
|---|---|---|
| Reading a last logon time | **Requires enabling, retaining, and parsing audit logs** | AD's `lastLogonTimestamp` |
| Dependency on AD availability | None | Lasts a lifetime ([detail](ad-dependency-lasts-the-lifetime.md)) |
| Coordination with AD operators | Not needed | Needed |
| Central user management | **Independent per SVM.** Accounts cannot be reused | Per domain |
| Responsibility for audit log capacity | Taken on for the inventory | Not needed for inventory purposes |

**Which fits depends on account count and how often it changes.** Dozens of local users with frequent movement point to AD membership; a small, stable set points to a workgroup with a register. **Enabling auditing permanently for the sake of an inventory brings [the risk of an access outage from capacity exhaustion](../../../domains/security-governance/notes/audit-log-space-and-client-access.md) into operations.** That cost is what gets weighed against operating AD.

> **On availability**: when the audit destination filled, what stopped was **only the paths carrying a
> SACL**. Volumes in the same SVM that were not audited were unaffected (measured: 5,000 operations
> succeeded against a non-audited volume while the audited one was refusing). **So the very share you
> gave a SACL for the inventory is the first to stop when capacity runs out.** The wider the inventory
> scope, the wider the outage — keep SACLs to the paths the inventory needs.

---

### A staged rollout

**A design judgment.**

| # | Stage | What it tells you |
|---|---|---|
| 1 | Enable `cifs-logon-logoff,file-ops` on a test SVM and collect logs for one to two weeks | How 4624 actually accumulates under real usage patterns |
| 2 | Build "user × last access time" and compare it against what the teams believe | **The actual rate of false positives from session reuse** |
| 3 | Measure the destination volume's growth rate and size for the retention period | Capacity design. **An estimate made before enabling is not enough** |
| 4 | Enable on the production SVM, with the utilization alarm in place **first** | — |
| 5 | Automate through disabling on the first pass; keep deletion manual | The false positive rate. Widen the automation once it is acceptable |

**Do not skip stage 2.** The false positive rate depends on usage patterns and cannot be estimated in advance.

---

### Not confirmed

- **How a logon attempt against a disabled account is distinguished in 4625's `FailureReason`.** The wrong-password case was measured; failure due to a disabled account (ONTAP's internal equivalent of 531) was not
- **The volume of 4656 / 4663 after SACLs are configured.** Whether enough granularity survives depends on real usage patterns, and only a small number of operations were generated here
- **How `local-user show` responds in an environment with many local users.** The test environment has two

---

### Related

- [SMB logon auditing — 4624 is recorded](../../../domains/security-governance/notes/smb-logon-audit-event-coverage.md)
- [Audit log capacity exhaustion stops client access](../../../domains/security-governance/notes/audit-log-space-and-client-access.md)
- [The AD dependency lasts a lifetime, not just the join](ad-dependency-lasts-the-lifetime.md)
- [Some SVMs cannot serve SMB](smb-service-lost-on-cifs-server-delete.md)

<a id="verify-in-your-own-environment"></a>

## Verify it in your environment

| # | Step | What it establishes |
|---|---|---|
| 1 | Read the local user's attributes with `local-user show -instance` | That there is no last-logon timestamp; only a disabled flag is available |
| 2 | On a test SVM, enable `cifs-logon-logoff,file-ops` and collect logs for a few days | How 4624 / 4656 / 4663 accumulate under the real usage pattern |
| 3 | Log on three times as the same user and count the 4624 records | That session reuse collapses them into one — the premise of the inventory design |
| 4 | Build "user x last-access time" and compare it with the field's understanding | The rate of false positives from session reuse |

A local user's attributes can be read with this read-only command.

```bash
ssh <svm-management-endpoint> vserver cifs users-and-groups local-user show -vserver <svm> -instance
```

### Expected output

```text
Only Domain Name / User Name / Full Name / Description / Is Account Disabled (no last-logon timestamp)
```

This shows only the attributes a local user carries. Real usage has to be built from audit logs, and a deletion decision goes through disabling and an objection window first. It changes nothing.

## Read next

[Does the AD dependency end once the join is done?](ad-dependency-lasts-the-lifetime.md)
