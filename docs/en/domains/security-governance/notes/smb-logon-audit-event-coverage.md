---
title: SMB logon auditing — 4624 is recorded, but what it counts is sessions rather than login actions
lifecycle: [design, build, operate]
domains: [security-governance, multiprotocol-identity]
evidence: verified
verified_on: 2026-09-01
ontap_version: 9.18.1P3D1
region: ap-northeast-1
lang: en
---

# SMB logon auditing — 4624 is recorded, but what it counts is sessions rather than login actions

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/security-governance/notes/smb-logon-audit-event-coverage.md) | [English](smb-logon-audit-event-coverage.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

[🏠 Repository home](../../../README.md) | [Domain — Security and governance](../README.md)

> This is the English translation. Japanese is authoritative for technical accuracy. Please report any discrepancy.

---

## Conclusion

**With `cifs-logon-logoff` enabled, SMB logon success 4624 and logon failure 4625 are written to the EVTX file.** Both were recorded on an AD-joined SVM and for a local user on a workgroup SVM.

**The SMB event table in the AWS documentation does not list them.** The table covers only the file access events. **The prose on the same page, however, describes `cifs-logon-logoff` as a default category.** Reading only the table leads to declaring a requirement unachievable when it is not.

And **4624 is not a count of login actions.** It is one record per SMB session establishment. In the measurement, mapping and unmapping the same share three times from Windows with `net use` and `net use /delete` produced **a single 4624**. `net use /delete` removes the share mapping rather than ending the session, and Windows keeps the authenticated session alive.

| Event | Recorded | Unit |
|---|---|---|
| 4624 (logon success) | **Yes** | SMB session establishment |
| 4625 (logon failure) | **Yes** | Authentication attempt |
| 4634 (logoff) | **Yes, conditionally** | Only when the client sends a proper logoff |

**4634 cannot be used as a signal that a session ended.** It was recorded neither on a network break nor on an administrative disconnect.

> **Evidence**: `verified` (2026-09-01, `ap-northeast-1`, ONTAP `9.18.1P3D1`).
> Measured on two SVMs across two file systems. One used a local user on an AD-joined SVM from
> `smbclient` on Linux; the other used a local user on a **workgroup SVM**
> (`Authentication Style: workgroup`) from **`net use` on Windows Server**. Logs were sealed with
> `vserver audit rotate-log`, retrieved through the ONTAP REST file API, and parsed with `python-evtx`.
> **Real IPs, account IDs, and file system IDs are replaced with placeholders.**

---

## Where the documents disagree

| Source | Logon / logoff coverage |
|---|---|
| The SMB event table in AWS [Auditing file access](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-access-auditing.html) | **Absent.** Only 560/4656, 563/4659, 564/4660, 567/4663, 4664, 9999, 9998 |
| The prose on the same page | **Present.** States that the default categories include file access, CIFS logon / logoff, and authorization policy change |
| NetApp: [SMB events that ONTAP can audit](https://docs.netapp.com/us-en/ontap/nas-audit/smb-events-audit-concept.html) | **Present.** 540/4624, 529–539/4625, 538/4634 |

The measurement agrees with the NetApp material. **The AWS table is incomplete and contradicts the prose on its own page.**

---

## Events emitted per category

The same sequence of operations — a successful logon, one wrong password, then creating and reading a file — was run with only the audit category changed. The SACL was identical in both measurements.

| `-events` setting | EventIDs emitted |
|---|---|
| `file-ops` | `{4656, 4663}`. **No logon events at all** |
| `file-ops,cifs-logon-logoff` | `{4624, 4625, 4656, 4663}` |
| `file-ops,cifs-logon-logoff,file-share` | `{4624, 4634}` plus `{5142, 5144}` on a share definition change |

**`file-ops` alone does not even retain failed logons.** Naming `cifs-logon-logoff` explicitly is required whenever account inventory or logon monitoring is a requirement.

Specifying only `-events file-ops` still adds `audit-policy-change` to the configuration automatically.

```text
FsxIdEXAMPLE::> vserver audit show -vserver <svm> -instance
                    Auditing State: true
              Log Destination Path: /audit_log
     Categories of Events to Audit: file-ops, audit-policy-change
                        Log Format: evtx
```

---

## What 4624 and 4625 contain

A 4624 recorded for a local user on the workgroup SVM:

```xml
<Provider Name="NetApp-Security-Auditing" Guid="{3CB2A168-FE19-4A4E-BDAD-DCF422F13473}"/>
<EventID>4624</EventID>
<EventName>Logon Attempt</EventName>
<Source>CIFS</Source>
<Result>Audit Success</Result>
<TimeCreated SystemTime="2026-09-01 05:57:51.494787+00:00"/>
<Computer>FsxIdEXAMPLE/<svm></Computer>
<EventData>
  <Data Name="IpAddress" IPVersion="4">10.0.x.x</Data>
  <Data Name="IpPort">65155</Data>
  <Data Name="TargetUserSID">S-1-5-21-…-1000</Data>
  <Data Name="TargetUserName">wgaudit</Data>
  <Data Name="TargetUserIsLocal">true</Data>
  <Data Name="TargetDomainName"><cifs-server-name></Data>
  <Data Name="AuthenticationPackageName">NTLM_V2</Data>
  <Data Name="LogonType">3</Data>
</EventData>
```

A 4625 adds `Status`, `FailureReason`, and `FailureReasonString` (for example, wording indicating a wrong password); its `AuthenticationPackageName` is `NONE` and `TargetUserSID` is `S-1-0-0`. `TargetUserIsLocal` is not present.

**The field name differs by category.**

| Event kind | Field holding the user name |
|---|---|
| Logon events (4624 / 4625 / 4634) | `TargetUserName` |
| File access events (4656 / 4663) | `SubjectUserName` |
| Share definition changes (5142 / 5144) | `SubjectUserName` |

**Extracting on one of them alone silently returns zero rows.** Where both are correlated, as in an inventory, the extraction has to separate them explicitly.

---

## When 4634 appears and when it does not

Seven ways of ending a session were measured, changing nothing else. **What decides it is not whether the share mapping was removed but whether the SMB session itself was destroyed.**

| How it ended | 4634 | Server-side session |
|---|---|---|
| Client destroys the SMB session (`Restart-Service LanmanWorkstation`) | **Recorded** | Disappears |
| Client process / logon session ends | **Recorded** (about 3 seconds after the script exits) | Disappears |
| Share mapping removed (`net use /delete`) | **Not recorded at that point** | **Remains** |
| Share mapping removed (`Remove-SmbMapping`) | **Not recorded at that point** | **Remains** |
| Network break (445 blocked client-side) → reclaimed naturally server-side | **Not recorded** | **Gone in about 3 minutes** |
| Administrator disconnects with `vserver cifs session close` | **Not recorded** | Disappears |
| **Left idle (with the connection alive)** | **Not recorded** | **Does not disappear** (below) |

**`net use /delete` and `Remove-SmbMapping` do not end the session.** Only the share mapping comes off; the authenticated session remains. **So 4634 does not appear at that moment — one appears later, when the session itself is destroyed.**

**A session orphaned by a network break was reclaimed server-side in about 3 minutes** (orphaned at `14:30:42`, gone from `vserver cifs session show` by `14:33:25`). **No 4634 is emitted when it is reclaimed.** An earlier measurement had not waited for the reclamation to complete, so "this might be a timing artifact" could not be ruled out; here the absence in the audit log was confirmed after observing the session disappear.

**A session left idle did not end, so no 4634 appeared either.**

With `Client Session Timeout` in `vserver cifs options` lowered from the default 900 seconds to **60 seconds**, a mapping was made with `net use`, one file was written, and nothing was touched afterwards.

```text
FsxIdEXAMPLE::> vserver cifs options show -vserver <svm> -instance
  Client Session Timeout : 60          ← the only session timeout setting exposed on this SVM

FsxIdEXAMPLE::> vserver cifs session show -vserver <svm> -fields session-id,idle-time
node                      vserver  session-id          idle-time
------------------------- -------- ------------------- ---------
FsxIdEXAMPLE-01           <svm>    1197676025903841353 17m 30s   ← survived over 17x the setting
```

| What was checked | Result |
|---|---|
| `Client Session Timeout` as configured | **60 seconds** |
| How long the session survived while idle | **Over 17 minutes 30 seconds** (exceeding the 900-second default as well) |
| How `idle-time` moved | **Monotonically increasing**, corroborating that no SMB request arrived from the client |
| 4634 records during that period | **Zero** |
| All records in the same period | 6 (`4624` ×1, `4656` ×2, `4663` ×3 — the connection and marker-file operations only) |

**`Client Session Timeout` did not reclaim the idle session.** It is the only session-related timeout setting exposed on this SVM. **So the assumption that 4634 appears once something has gone unused for a while does not hold.**

> **On the measurement**: the first attempt ran `net use * /delete /y` for an unrelated check, which
> destroyed the session and **made it indistinguishable from a timeout expiry** (at 9 minutes 17
> seconds). **While an idle test is running, do not let anything else on the same client touch SMB.**
> The values above come from a second run with the other operations stopped.

The absence of 4634 with `smbclient` has the same explanation. A file-system-side difference was suspected at first; the cause was whether the client took a path that destroys the session.

> **On measurement procedure**: **4634 appears when the session is destroyed, not immediately after
> the client's action.** With destruction by process exit it lagged about 3 seconds. **Rotating and
> collecting immediately after the client action loses that record.** It was in fact lost once, and
> misread as "`Remove-SmbMapping` produces no 4634". The correct reading is that it produces none *at
> that point*, and one appears when the session is destroyed. **Leave the collection window well
> after the client action.**

A recorded 4634 carries the same `IpPort` as its 4624, so **records can be correlated to one session.**

```text
EventID=4624  SystemTime=… 05:57:51  IpPort=65155
EventID=4634  SystemTime=… 05:58:10  IpPort=65155
```

> **On audit design**: do not build session duration, concurrent connection counts, or "who is
> connected right now" out of 4634. **Five of the seven paths measured are silent** — the two mapping
> removals emit nothing at that point, and natural reclamation after a network break, an
> administrative disconnect, and an idle session emit nothing at all. **For current connections,
> `vserver cifs session show` is the correct source.**

---

## What follows from it being per session

Repeating `net use` and `net use /delete` three times from Windows produced this:

| Expected | Measured |
|---|---|
| Three 4624 records | **One** |
| Three 4634 records | **One**, and not at the third unmapping — at the point a later authentication failure forced the session to be re-established |

What `net use /delete` removes is the share mapping; the authenticated session remains. **That property skews an inventory decision in both directions.**

| Usage pattern | How 4624 accumulates | Direction of the error |
|---|---|---|
| Connect once and hold it | **Does not accumulate** | In use, but judged "no activity" |
| Unstable network, reconnecting repeatedly | Accumulates heavily | Overstates the usage |

**As an indicator of real use, `file-ops` 4656 / 4663 are more direct.** Per-object access is recorded with `SubjectUserName`, unaffected by session reuse. For an inventory, take the later of "the last 4624" and "the last 4656 / 4663" rather than the 4624 timestamp alone.

That decision design is covered in
[The only information available for a local user inventory is in the audit log](../../multiprotocol-identity/notes/local-user-inventory-without-last-logon.md).

---

## The SACL `file-ops` requires, and the DACL it replaces

**On an NTFS security style volume, no file access event is emitted without a SACL.** These are the results with the audit configuration held identical and only the SACL changed.

| SACL | Output |
|---|---|
| None | **Zero events** (only `4719`, the audit configuration change) |
| `AUDIT-Everyone-0x1f01ff-OI\|CI\|SA\|FA` | `{4656: 14, 4663: 12}` |

**This is the most common cause of "auditing is enabled but the log is empty".** The AWS documentation gives the procedure for configuring audit policies, but does not state the causal link that events drop to zero without one.

> **On how this is classified**: asked to state this in the documentation, AWS Support replied that
> configuring a SACL is **already mandatory under the current wording — "You need to configure audit
> policies on the files and folders that you want audited" — and that the specific behaviour when a
> mandatory setting is missing is not committed to as specified behaviour** (2026-09-02).
>
> **So the zero above is measured behaviour, not guaranteed behaviour.**
> Do not build audit logic that reads "zero events" as "there was no access".
> **Zero is equally consistent with no access, no SACL, and no category.**
> AWS Support will feed back to the responsible team whether a troubleshooting entry can be added
> pointing at a missing SACL when records do not appear as expected, and a warning that configuring a
> SACL through the CLI replaces the DACL.

**And applying a security descriptor through the ONTAP CLI replaces the DACL along with the SACL.**

```text
FsxIdEXAMPLE::> vserver security file-directory apply -vserver <svm> -policy-name auditpol
(after applying, for a user who had access until then)
NT_STATUS_ACCESS_DENIED listing \*
```

Reapplying with allow ACEs included in the descriptor restored it. **Adding auditing to an existing share can therefore cause an access outage.** Either include the existing DACL in the descriptor being applied, or add the SACL from the Windows side.

---

## What the `file-share` category actually covers

**`file-share` records *changes to* share definitions, not access *to* a share.**

| Operation | Recorded |
|---|---|
| Connecting to a share (`net use`) | **Nothing** |
| `vserver cifs share create` | `5142` (Share Object Added) |
| `vserver cifs share delete` | `5144` (Share Object Deleted) |

A 5142 carries `ShareName`, `SharePath`, `ShareProperties`, `SD` (the share ACL), and the `SubjectUserName` / `SubjectIP` of the administrator who made the change. **Useful as a change history for share definitions; not usable as a record of user access.**

---

## Confirming this in your own environment

| # | Step | What it establishes |
|---|---|---|
| 1 | Read `Categories of Events to Audit` from `vserver audit show -instance` | Whether `cifs-logon-logoff` is present. With `file-ops` alone, logons are not retained |
| 2 | With auditing on, log on over SMB once and run `vserver audit rotate-log` | **Without rotating you are reading a file still being written** |
| 3 | Inspect the resulting EVTX and look at `TargetUserName` in the 4624 | Whether the expected user name is there |
| 4 | **Log on three times as the same user and count the 4624 records** | Whether session reuse collapses them into one. **This decides the premise of an inventory design** |
| 5 | Log off properly from the client and see whether a 4634 appears | Whether the client you use sends a proper logoff |
| 6 | When expecting `file-ops` on an NTFS volume, configure the SACL before measuring | Distinguishes zero-because-no-category from zero-because-no-SACL |

The rotated file name carries the **rotation time**, and its `modified_time` is earlier than that. Looking only at the newest file loses records that straddle the boundary. **Collect several files by period before counting.**

---

## Not confirmed

- **Differences between ONTAP versions.** Both file systems measured were on `9.18.1P3D1`. No comparison with another version or with on-premises ONTAP
- **Differences between client implementations.** Windows (`net use` / `Remove-SmbMapping` / restarting `LanmanWorkstation` / process exit) and `smbclient` on Linux were measured. **macOS, NAS appliances, and the various SMB libraries were not.** The result depends on whether the client takes a path that destroys the session, so **confirm with the client you use**
- **Whether an idle session eventually ends.** With `Client Session Timeout` at 60 seconds it survived 17 minutes 30 seconds with no 4634. **Whether it ends when left longer was not measured.** At minimum, neither the configured value nor the default acts as a reclamation threshold
- **Variance in the time to reclamation.** The roughly 3 minutes is a single observation. It is neither a threshold nor a setting

---

## Primary sources

- AWS: [Auditing file access](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-access-auditing.html) — for SACLs, [Configuring file and folder audit policies](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-access-auditing.html#file-audit-policies)
- NetApp: [SMB events that ONTAP can audit](https://docs.netapp.com/us-en/ontap/nas-audit/smb-events-audit-concept.html)
- NetApp: [ONTAP Auditing Schema Reference (PDF)](https://docs.netapp.com/p/ontap/9x/Auditing-Schema-Reference.pdf) — the mapping between `-events` categories and event IDs. **The AWS documentation has no such table, and AWS Support is considering adding a pointer to this PDF** (2026-09-02)

---

## Related

- [Audit log capacity exhaustion stops client access](audit-log-space-and-client-access.md)
- [The only information available for a local user inventory is in the audit log](../../multiprotocol-identity/notes/local-user-inventory-without-last-logon.md)
- [S3 Access Point authorization design — evaluation order and the two layers that narrow access](access-point-authorization-layers.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/security-governance/notes/smb-logon-audit-event-coverage.md) | [English](smb-logon-audit-event-coverage.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
