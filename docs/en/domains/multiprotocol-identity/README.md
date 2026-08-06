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
| 1 | How security style changes permission evaluation | [Security style determines the permission model](../../../ja/domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) (日本語) |
| 2 | What Active Directory integration presupposes | _not yet added_ |
| 3 | When win-unix / unix-win mapping is consulted | [same note](../../../ja/domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) (日本語) |
| 4 | What it takes to share the same data over NFS and SMB | _not yet added_ |
| 5 | What breaks when AD becomes unreachable | _not yet added_ |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../../ja/domains/multiprotocol-identity/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
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
