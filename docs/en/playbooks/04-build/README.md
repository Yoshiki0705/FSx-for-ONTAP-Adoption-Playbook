# Playbook 04 — Build

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/playbooks/04-build/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

A hand-built environment cannot be reproduced. Infrastructure as code and automation make the build verifiable and repeatable.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | What to manage in IaC and what to leave out | [The IaC boundary is set by the API surface](../../../ja/playbooks/04-build/notes/what-iac-cannot-reach.md) (日本語) |
| 2 | How to automate Active Directory integration | [Automating Active Directory integration](../../../ja/playbooks/04-build/notes/what-iac-cannot-reach.md#active-directory-連携の自動化) (日本語) |
| 3 | How to handle secrets | [Handling secrets](../../../ja/playbooks/04-build/notes/what-iac-cannot-reach.md#シークレットの扱い) (日本語) |
| 4 | How to automate post-build verification | [Verifying in two layers](../../../ja/playbooks/04-build/notes/what-iac-cannot-reach.md#構築後検証の自動化) (日本語) |
| 5 | How to clone environments for dev and test | [Cloning environments](../../../ja/playbooks/04-build/notes/what-iac-cannot-reach.md#開発検証環境の複製) (日本語) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../../ja/playbooks/04-build/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](../../../ja/playbooks/04-build/checklists/) | Checklists for field use. → [Pre-production review](../../../ja/playbooks/04-build/checklists/pre-production-review.md) (日本語) |

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

- [Browse by topic](../../navigation.md#topic-axis--domains)
- [Migration Method Decision Tree](../../../ja/reference/decision-trees/migration-method.md)
- [Navigation Guide](../../navigation.md)
- [Glossary](../../../ja/reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/playbooks/04-build/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
