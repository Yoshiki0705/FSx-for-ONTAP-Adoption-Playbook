# Domain — Multiprotocol & Identity

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/multiprotocol-identity/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Covers NFS and SMB coexistence, Active Directory integration, and ID mapping. Most "permissions are wrong" problems trace back to ID mapping.

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

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](../../../ja/domains/multiprotocol-identity/checklists/) | Checklists for field use |

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
