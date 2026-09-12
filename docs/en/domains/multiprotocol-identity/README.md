# Domain — Multiprotocol & Identity

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/multiprotocol-identity/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Covers NFS and SMB coexistence, Active Directory integration, and ID mapping. Most "permissions are wrong" problems trace back to ID mapping.

---

## Read first

**This turns what you already have in hand into the next single page to read.** The table below it is
the table of contents; this is the entry point.

| What you have | Read first | What it settles |
|---|---|---|
| **Serving the same data over NFS and SMB** | [Security style decides the permission model](notes/security-style-and-permission-evaluation.md) | **decide the style first.** Changing it later changes how permissions are evaluated |
| **AD integration, planned or already joined** | [The AD dependency lasts the lifetime, not the join](notes/ad-dependency-lasts-the-lifetime.md) | **an expired credential is asymptomatic until the next maintenance window** |
| **SMB will not connect** | [Some SVMs cannot serve SMB](notes/smb-service-lost-on-cifs-server-delete.md) | **the cause is a deleted CIFS server, not when the SVM was created** |
| **Checking permissions from NFS, or explaining a denial** | [The NFS-side permission view does not match the enforced outcome](notes/nfs-side-view-does-not-explain-ntfs-denials.md) | **neither the Deny nor the principal appears on the NFS side.** Measured: an NTFS refusal and a UNIX permit produced identical representations |
| **Access is refused after the name mapping was created** | [The backslash disappearing from a name-mapping replacement](notes/nfs-side-view-does-not-explain-ntfs-denials.md#the-backslash-disappearing-from-a-name-mapping-replacement) | **`\` in `DOMAIN\user` is consumed as an escape.** The rule reports success and only the name resolution fails |

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | How security style changes permission evaluation | [Security style determines the permission model](notes/security-style-and-permission-evaluation.md) |
| 2 | What Active Directory integration presupposes | [The delegated permissions the service account needs](notes/ad-dependency-lasts-the-lifetime.md#delegated-permissions-the-service-account-needs) |
| 3 | When win-unix / unix-win mapping is consulted | [same note](notes/security-style-and-permission-evaluation.md) |
| 4 | What it takes to share the same data over NFS and SMB | [Three layers of conditions](notes/ad-dependency-lasts-the-lifetime.md#conditions-for-serving-the-same-data-over-nfs-and-smb) |
| 5 | What breaks when AD becomes unreachable | [The AD dependency lasts the lifetime, not just the join](notes/ad-dependency-lasts-the-lifetime.md) |
| 6 | How many authorization layers a browser path introduces | [Authorization becomes three layers](../../../ja/playbooks/02-design/notes/how-end-users-reach-the-data.md#ブラウザ経路--3-層になる認可) (日本語) |
| 7 | Whether a local user inventory can be automated | [No last-logon attribute exists; it has to come from audit logs](notes/local-user-inventory-without-last-logon.md) |
| 8 | Why SMB will not connect even though the CIFS server was created | [Some SVMs cannot serve SMB](notes/smb-service-lost-on-cifs-server-delete.md) |
| 9 | Whether permissions on an NTFS-style volume can be verified from NFS | **the representation is readable but does not explain the outcome** ([The NFS-side permission view does not match the enforced outcome](notes/nfs-side-view-does-not-explain-ntfs-denials.md)) |
| 10 | Which check does answer it, and who can run it | [ONTAP's effective-permissions agreed with the outcome in every case](notes/nfs-side-view-does-not-explain-ntfs-denials.md#where-the-usable-answer-is) — and it needs an ONTAP credential |
| 11 | Whether the verification mechanism in use today survives the move | [Where to verify who can access a file after a protocol change](../../../ja/reference/decision-trees/verifying-permissions-after-a-protocol-change.md) (日本語) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |

---

## The smallest runnable environment for checking this yourself

**The central question of this module — what happens to a permission set over SMB when the same data is read over NFS — has a runnable environment in [`examples/multiprotocol-ad/`](../../../../examples/multiprotocol-ad/).**

| What it creates | What it deliberately does not |
|---|---|
| One CloudFormation template: a first-generation Single-AZ file system, an AWS Managed Microsoft AD directory, two AD-joined SVMs, an NTFS volume, **a UNIX control volume**, and Windows and Linux clients | The SMB share, the export policy rules, the NTFS ACEs, the name mappings, any FlexClone, the `volume rehost`. **The Amazon FSx API has no action for any of them** |
| Three ONTAP REST scripts and one PowerShell script | — |

**A result is only usable when all three parts of the record are present**: the ACE that was set, the representation the NFS side showed, and whether the access succeeded. Reading only the mode bits from `stat` is what makes a Deny ACE look absent, which is why the record has three parts rather than one.

**Cost is about $0.72 per hour, and about $0.52 per hour with both instances stopped** (`ap-northeast-1`, AWS Price List API, retrieved 2026-09-11). The file system and the directory cannot be stopped, only deleted. Fix a teardown date before starting.

---

## How to read this

Always check the `evidence` field in each note's frontmatter.

| Tier | Meaning |
|---|---|
| `verified` | Reproduced by the author in the stated environment. `verified_on` gives the date |
| `documented` | Stated in vendor / AWS documentation. `source` gives the reference |
| `field-observation` | Observed once in the field, not reproduced. Do not generalize |
| `hypothesis` | Reasoned expectation, untested |

See the [Evidence Policy](../../evidence-policy.md) for the full criteria.

---

## Related

- [Browse by lifecycle](../../navigation.md#lifecycle-axis--playbooks)
- [Comparison Matrices](../../../ja/reference/comparison/)
- [Navigation Guide](../../navigation.md)
- [Glossary](../../../ja/reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/multiprotocol-identity/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
