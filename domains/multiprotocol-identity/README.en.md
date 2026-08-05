# Domain — Multiprotocol & Identity

[日本語](README.md) | [🏠 Repository home](../../README.en.md)

---

Covers NFS and SMB coexistence, Active Directory integration, and ID mapping. Most "permissions are wrong" problems trace back to ID mapping.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | How security style changes permission evaluation | _not yet added_ |
| 2 | What Active Directory integration presupposes | _not yet added_ |
| 3 | When win-unix / unix-win mapping is consulted | _not yet added_ |
| 4 | What it takes to share the same data over NFS and SMB | _not yet added_ |
| 5 | What breaks when AD becomes unreachable | _not yet added_ |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](checklists/) | Checklists for field use |

---

## How to read this

Always check the `evidence` field in each note's frontmatter.

| Tier | Meaning |
|---|---|
| `verified` | Reproduced by the author in the stated environment. `verified_on` gives the date |
| `documented` | Stated in vendor / AWS documentation. `source` gives the reference |
| `field-observation` | Observed once in the field, not reproduced. Do not generalize |
| `hypothesis` | Reasoned expectation, untested |

See the [Evidence Policy](../../docs/en/evidence-policy.md) for the full criteria.

---

## Related

- [Browse by lifecycle](../../docs/en/navigation.md#lifecycle-axis--playbooks)
- [Comparison Matrices](../../reference/comparison/)
- [Navigation Guide](../../docs/en/navigation.md)
- [Glossary](../../reference/glossary/)

---

[日本語](README.md) | [🏠 Repository home](../../README.en.md)
