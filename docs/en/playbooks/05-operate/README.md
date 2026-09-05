# Playbook 05 — Operate

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/playbooks/05-operate/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Covers monitoring, capacity management, incident response, and change management. You need both confirmation that things work and a plan for when they break.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | What to monitor and where to set thresholds | [Monitoring fails on averages](notes/monitoring-fails-on-averages.md) |
| 2 | How to detect impending capacity exhaustion | [The SSD utilization bands and what changes at each](notes/monitoring-fails-on-averages.md#the-ssd-utilisation-bands-and-what-changes-at-each-point) |
| 3 | How to triage performance degradation | [Triage order](notes/monitoring-fails-on-averages.md#order-for-isolating-a-performance-regression) |
| 4 | How to handle ONTAP version updates | [Maintenance cannot be deferred past 14 days](../../../ja/playbooks/05-operate/notes/maintenance-cannot-be-deferred.md) (日本語) |
| 5 | How to define first-response actions during an incident | [First response during an incident](../../../ja/playbooks/05-operate/notes/maintenance-cannot-be-deferred.md#インシデント時の初動) (日本語) |
| 6 | What to suspect when the admin account can no longer authenticate | [fsxadmin gets locked, and REST cannot tell you why](../../../ja/playbooks/05-operate/notes/admin-account-lockout-and-recovery.md) (日本語) |
| 7 | What to look at when a running SVM stops serving SMB | [An SVM that cannot serve SMB](../../domains/multiprotocol-identity/notes/smb-service-lost-on-cifs-server-delete.md) |
| 8 | What happens to availability when auditing runs continuously | [Destination exhaustion stops access](../../domains/security-governance/notes/audit-log-space-and-client-access.md) |
| 9 | How to run an inventory of local users | [No last-logon attribute exists; the inventory has to come from audit logs](../../domains/multiprotocol-identity/notes/local-user-inventory-without-last-logon.md) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`checklists/`](../../../ja/playbooks/05-operate/checklists/) | Checklists for field use |

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
🌐 [日本語](../../../ja/playbooks/05-operate/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
