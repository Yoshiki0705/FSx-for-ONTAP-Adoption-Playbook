# Domain — Data Protection

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/data-protection/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Covers Snapshot, SnapMirror, SnapLock, backup, and ransomware readiness. "Protected" and "recoverable" are two different claims.

---

## Read first

**This turns what you already have in hand into the next single page to read.** The table below it is
the table of contents; this is the entry point.

| What you have | Read first | What it settles |
|---|---|---|
| **Snapshots are already being taken** | [What each mechanism protects against](notes/snapshots-are-not-a-recovery-plan.md#what-each-mechanism-protects-against) | **a Snapshot is lost with the volume it lives on** |
| **A copy is needed in another region or account** | [A backup copy holds no file system until it is restored](../../../ja/domains/data-protection/notes/backup-copies-across-regions-and-accounts.md) (日本語) | what exists at the destination and what does not, and how it differs from SnapMirror |
| **Ransomware protection has been asked for** | [Enabling SnapLock and locking are separate](../../../ja/domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md) (日本語) | **three irreversible steps.** Privileged delete is unavailable once retention expires |

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | How to design a Snapshot policy | [Work back from the limits and retention](notes/snapshots-are-not-a-recovery-plan.md#limits-and-retention-periods) (日本語) |
| 2 | What SnapMirror protects and what it does not | [Having snapshots is not the same as being able to recover](notes/snapshots-are-not-a-recovery-plan.md#what-each-mechanism-protects-against) (日本語) |
| 3 | How to use WORM / SnapLock and what is irreversible | [Enabling SnapLock is not the same as locking](../../../ja/domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md) (日本語) |
| 4 | How to verify the recovery procedure | [Actually exercising a restore](notes/snapshots-are-not-a-recovery-plan.md#verify-in-your-own-environment) (日本語) |
| 5 | What is effective as ransomware readiness | [Ransomware readiness is layered](../../../ja/domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md#層で考えるランサムウェア対策) (日本語) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |

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
