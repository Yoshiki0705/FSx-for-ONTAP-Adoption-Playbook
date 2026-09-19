---
title: An SMB error string does not name its cause. What looks like a wrong credential is an absent account
lifecycle: [build, operate]
domains: [multiprotocol-identity]
evidence: documented
source: https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/limits/smb-share-and-identifier-reading.md
lang: en
---

# An SMB error string does not name its cause

[🏠 Repository home](../../../README.md) | [Domain — Multiprotocol and identity](../README.md)

---

## Conclusion

**The strings an SMB client returns do not point at a single cause.** Three generic messages each surface as a missing piece in a different layer.

| Client-side error | Actual cause | Where to look |
|---|---|---|
| `The specified network password is not correct.` | **The account does not exist in the domain. The password is fine** | The directory's account list |
| `The network name cannot be found.` | **The share does not exist.** Neither the path nor the account is involved | The list from `GET /api/protocols/cifs/shares` |
| `System error 53` (`net use`) | The UNC backslashes are mangled passing through several layers of shell | Replace it with `New-SmbMapping`, which takes parameters and needs no nested quoting |

**The first row is the dangerous one.** An absent account presents as a wrong password, so the time goes into doubting the secret's value. **A secret existing is not an account existing** — a directory holds accounts and a secret holds a value. In a newly created directory the secret can survive while no account is there.

**Tier**: `documented` — transcribed from a sibling repository's record of all nine hosts failing to mount on 2026-09-06. **Not reproduced here.**

---

## SMB reaches shares and nothing else

**A volume's junction path is not a share name.** NFS can mount an exported path directly, but what an SMB client names is a share (a CIFS share), which is a separate object in ONTAP.

| | NFS | SMB |
|---|---|---|
| What the client names | The junction path | **The share name** |
| Does creating a volume make it usable | Yes, subject to the export policy | **No. Creating a share is a separate step** |
| How to create it | — | `vserver cifs share create`, or REST `POST /api/protocols/cifs/shares` |

**Until a share exists, no name reaches that volume over SMB.** A share's `-path` has to be a path that exists inside the volume, so **the junction path is what a share points at, not what a share is called.**

> **A newly created share defaults to Everyone / Full Control.** That is enough to prove connectivity and **useless for measuring permissions.** Set the ACL explicitly and record it when the permission behaviour is what you are checking.

---

## Do not count the default administrative shares as "a share exists"

Creating a CIFS server creates administrative shares automatically. **It does not create a data share.**

| Share | Purpose | Usable |
|---|---|---|
| `ipc$` | Named pipes, used by ONTAP | **No.** Its settings, properties and ACL cannot be changed, and it cannot be deleted or renamed |
| `admin$` | Remote administration of the SVM | No. **Not created by default from ONTAP 9.8 onward** |
| `c$` | Administrative access to the SVM root volume | **Not recommended.** See below |

**`c$` works, and it costs you the representativeness of the check.** Its default ACL is Full Control for `BUILTIN\administrator`, and its path is always the SVM root and cannot be changed. An SVM administrator can cross junctions from `c$` into the rest of the namespace, so `\\<svm>\c$\<volume>` does resolve. **But mapping as an administrator bypasses part of the permission evaluation, which makes the account used for the mapping part of the result.**

**Use an unprivileged domain account and a dedicated share.** Then the conditions can be explained afterwards.

**Shares ending in `$` are hidden and do not appear in Explorer.** Do not read "absent from the listing" as "does not exist".

---

## Read identifiers; do not derive them from a neighbouring name

**Read resource, share, account and SVM names from the API that owns them.** Do not derive them from a naming convention even when it looks derivable. **Separator characters routinely differ within one environment** — in the cited environment the SVM name used hyphens and the volume name used underscores, so deriving either from the other was wrong.

| What you need | The API to read |
|---|---|
| SVM name | `aws fsx describe-storage-virtual-machines` (`Name`) |
| A volume's junction path | `aws fsx describe-volumes` (`OntapConfiguration.JunctionPath`) |
| A share's name and path | ONTAP REST `GET /api/protocols/cifs/shares?fields=name,path,svm.name` |
| SMB endpoint | `describe-storage-virtual-machines` (`Endpoints.Smb.DNSName`), or the NetBIOS name |

**Having an ID is not knowing a name.** A stack output returning an `svm-...` ID carries no name.

---

## Verify in your own environment

**Read the state before attempting a mount.** It replaces guessing a cause from a generic error string.

| # | What to confirm | If it does not hold |
|---|---|---|
| 1 | The SVM exists and has joined AD (read `Lifecycle` and the NetBIOS name) | [AD dependency lasts the lifetime](ad-dependency-lasts-the-lifetime.md) |
| 2 | **A data CIFS share exists.** Do not count `c$` and `ipc$` as "a share exists" | Create the share |
| 3 | The share's `path` matches the junction path of a volume that exists | One of the two is wrong |
| 4 | The domain account used for the mapping resolves in the directory (**a secret existing is not a substitute**) | Create the account |
| 5 | The data LIF's service policy includes `data-cifs` | [Some SVMs cannot serve SMB](smb-service-lost-on-cifs-server-delete.md) |

**Those four holding is what justifies attempting the mount.** Attempting it with any one of them missing means reading one of the generic errors in the table above.

---

## Common misconceptions

| Misconception | Reality |
|---|---|
| `network password is not correct` is a password problem | **An absent account produces the same string.** Read the directory first |
| If the secret is there, the account is too | **They are separate.** In a new directory only the secret survives |
| Creating a volume makes it visible over SMB | **Creating a share is a separate step.** A junction path is not a share name |
| If administrative shares exist, they can be used for a connectivity check | `ipc$` cannot be used, and `c$` bypasses part of the permission evaluation |
| A share absent from the listing does not exist | **Shares ending in `$` are hidden** |
| An SVM name can be derived from the naming convention | **Separators are mixed within one environment.** Read it from the API |

---

## Outside the scope of this record

| Question | State |
|---|---|
| Whether the same error strings arise from other causes | **Unconfirmed.** Only the three correspondences above were observed |
| Differences across Windows versions | The cited source does not record them |
| Whether `New-SmbMapping` is always more reliable than `net use` | **The replacement is for avoiding multi-layer backslash escaping.** No other difference was measured |

---

## Related documents

- [Some SVMs cannot serve SMB](smb-service-lost-on-cifs-server-delete.md) — the cause on the side where port 445 never opens
- [AD dependency lasts the lifetime](ad-dependency-lasts-the-lifetime.md) — the account and domain-side prerequisites
- [What NFS shows about permissions does not explain an NTFS denial](nfs-side-view-does-not-explain-ntfs-denials.md) — a rule that reports success while only name resolution fails
- [Domain — Multiprotocol and identity](../README.md)
- [Evidence policy](../../../evidence-policy.md)

---

[🏠 Repository home](../../../README.md) | [Domain — Multiprotocol and identity](../README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/multiprotocol-identity/notes/smb-errors-do-not-name-their-cause.md) | [English](smb-errors-do-not-name-their-cause.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
