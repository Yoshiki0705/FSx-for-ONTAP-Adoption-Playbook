# Playbook 04 — Build

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/playbooks/04-build/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

A hand-built environment cannot be reproduced. Infrastructure as code and automation make the build verifiable and repeatable.

---

## Read first

**This turns what you already have in hand into the next single page to read.** The table below it is
the table of contents; this is the entry point.

| What you have | Read first | What it settles |
|---|---|---|
| **The template succeeded and the setup is still incomplete** | [The IaC boundary is the API surface](notes/what-iac-cannot-reach.md) | **a successful deployment does not reach the ONTAP-side settings.** This says where the boundary is |
| **Active Directory integration still to automate** | [Automating Active Directory integration](notes/what-iac-cannot-reach.md#automating-active-directory-integration) | what can be automated, and what is left to do by hand |
| **A pending decision on what to rehearse before production** | [Pre-production review](../../../ja/playbooks/04-build/checklists/pre-production-review.md) (日本語) | **the irreversible settings, and the items worth exercising first** |

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | What to manage in IaC and what to leave out | [The IaC boundary is set by the API surface](../../playbooks/04-build/notes/what-iac-cannot-reach.md) |
| 2 | How to automate Active Directory integration | [Automating Active Directory integration](../../playbooks/04-build/notes/what-iac-cannot-reach.md#automating-active-directory-integration) |
| 3 | How to handle secrets | [Handling secrets](../../playbooks/04-build/notes/what-iac-cannot-reach.md#handling-secrets) |
| 4 | How to automate post-build verification | [Verifying in two layers](../../playbooks/04-build/notes/what-iac-cannot-reach.md#automating-post-build-verification) |
| 5 | How to clone environments for dev and test | [Cloning environments](../../playbooks/04-build/notes/what-iac-cannot-reach.md#cloning-development-and-test-environments) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../playbooks/04-build/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
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
