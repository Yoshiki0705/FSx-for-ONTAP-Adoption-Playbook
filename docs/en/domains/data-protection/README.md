# Domain — Data Protection

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/data-protection/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Covers Snapshot, SnapMirror, SnapLock, backup, and ransomware readiness. "Protected" and "recoverable" are two different claims.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | How to design a Snapshot policy | [Work back from the limits and retention](../../../ja/domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md#上限と保持期間) (日本語) |
| 2 | What SnapMirror protects and what it does not | [Having snapshots is not the same as being able to recover](../../../ja/domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md#何から守れるのか) (日本語) |
| 3 | How to use WORM / SnapLock and what is irreversible | [Enabling SnapLock is not the same as locking](../../../ja/domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md) (日本語) |
| 4 | How to verify the recovery procedure | [Actually exercising a restore](../../../ja/domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md#自分の環境で確かめる) (日本語) |
| 5 | What is effective as ransomware readiness | [Ransomware readiness is layered](../../../ja/domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md#ランサムウェア対策は層で考える) (日本語) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../../ja/domains/data-protection/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](../../../ja/domains/data-protection/checklists/) | Checklists for field use |

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
🌐 [日本語](../../../ja/domains/data-protection/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
