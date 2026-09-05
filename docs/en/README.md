# Amazon FSx for NetApp ONTAP — Adoption Playbook

![docs](https://img.shields.io/badge/docs-lint%20passing-brightgreen) ![i18n](https://img.shields.io/badge/i18n-8%20languages-blue) ![license](https://img.shields.io/badge/license-MIT-blue) ![region](https://img.shields.io/badge/verified-ap--northeast--1-blue)

<!-- lang-switcher:start -->
🌐 [日本語](../../README.md) | [English](README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [繁體中文](../zh-TW/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Español](../es/README.md)
<!-- lang-switcher:end -->

---

> A knowledge base for migrating to **Amazon FSx for NetApp ONTAP** and for the design, build, and operations work that follows.
> Two navigation axes: the lifecycle (assess → design → migrate → build → operate → optimize) and the topic (data protection, data utilization, security, performance, cost, multiprotocol identity).
>
> Findings from field technical-support work are organized here as anonymized reference material. The structure is intended to be readable by humans and by AI agents / web crawlers alike.

---

## Get Started

| What you want to do | Guide | Time |
|---|---|---|
| Learn how to navigate this repository | [Navigation Guide](navigation.md) | 3 min |
| Decide whether and how to migrate | [Migration Method Decision Tree](../ja/reference/decision-trees/migration-method.md) | 10 min |
| Check verified limits and quotas | [Limits and Quotas](../ja/reference/limits/) | 5 min |
| Compare the trade-offs between options | [Comparison Matrices](../ja/reference/comparison/) | 10 min |
| Learn how to read the confidence levels | [Evidence Policy](evidence-policy.md) | 5 min |
| Find primary sources in the public record | [Public references and how to weigh them](../ja/case-studies/public-references.md) (日本語) | 5 min |
| Find a case study for your industry or workload | [Published FSx for ONTAP case studies](../ja/case-studies/public-case-studies.md) (日本語) | 10 min |
| Learn from a judgement that went wrong | [Case studies](case-studies/README.md) | 10 min |
| Add knowledge (authoring) | [CONTRIBUTING.md](../../CONTRIBUTING.md) | 10 min |

> **Coverage**: **all 12 modules have content.**
> Each module README lists the questions it covers alongside the note that answers each one.
> **A question whose answer is not yet written is marked `_未追加_`.**

### Available today

Each note is one concern per file, and always carries **its primary sources** and **a procedure for checking it in your own environment**. The notes themselves are Japanese for now.

| Finding | What it answers |
|---|---|
| [Free space does not mean you can still write](playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) | Why an inventory has to count files, not just bytes — the default inode count stops growing past 648 GiB |
| [Deployment type is decided once](playbooks/02-design/notes/deployment-type-is-decided-once.md) | The availability choice also sets the scale-out ceiling. Multi-AZ is fixed at one HA pair |
| [ACL preservation is a privilege problem, not a tool problem](../ja/playbooks/03-migrate/notes/preserving-acls-during-migration.md) (日本語) | Run with the defaults and ACLs are dropped silently, while the job still reports success |
| [The rollback window closes when clients start writing](playbooks/03-migrate/notes/where-the-rollback-window-closes.md) (日本語) | There is no operation that undoes a cutover, and incremental sync depends on the common snapshot |
| [The IaC boundary is set by the API surface](playbooks/04-build/notes/what-iac-cannot-reach.md) | A successful template is not a complete configuration — ONTAP-level settings are out of reach |
| [Pre-production review](../ja/playbooks/04-build/checklists/pre-production-review.md) (日本語) | Checklist of the irreversible settings and what to actually exercise before going live |
| [Monitoring fails on averages](playbooks/05-operate/notes/monitoring-fails-on-averages.md) | Why the statistic is decided before the threshold — standby nodes pull the average down |
| [Maintenance cannot be deferred past 14 days](../ja/playbooks/05-operate/notes/maintenance-cannot-be-deferred.md) (日本語) | SSD above 90% and a missing route both make patching materially worse |
| [Tiering defaults differ by creation method](../ja/playbooks/06-optimize/notes/tiering-defaults-differ-by-creation-method.md) (日本語) | The console and IaC do not produce the same default policy. Order changes by whether they can be undone |
| [Having snapshots is not the same as being able to recover](domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md) (日本語) | Each mechanism covers a different failure. A snapshot is lost along with its volume |
| [Enabling SnapLock is not the same as locking](../ja/domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md) (日本語) | Three separate irreversible decisions, and privileged delete does not work after expiry |
| [FSx for ONTAP S3 AP is not "S3 you can use as S3"](../ja/domains/data-utilization/notes/s3-access-point-constraints.md) (日本語) | Same-account and same-Region prerequisites become plan-level constraints |
| [An S3 access point authorizes every request as one identity](../ja/domains/data-utilization/notes/reaching-data-without-copies.md) (日本語) | The original ACLs do not carry into an AI or RAG pipeline reading through it |
| [At rest is automatic, in transit is off by default](../ja/domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md) (日本語) | The audit trail does not record every read — only the first per object |
| [Throughput is not set by one value](domains/performance/notes/where-throughput-is-determined-and-shared.md) (日本語) | Generation, configuration and Region all move the ceiling, and a FlexVol cannot exceed one HA pair |
| [p99 cannot be read from the CloudWatch metrics](../ja/domains/performance/notes/what-you-cannot-read-from-cloudwatch.md) (日本語) | Only an average is obtainable, and benchmarks are swayed by burst credit balance |
| [Billing splits into provisioned and consumed](domains/cost/notes/provisioned-versus-consumed.md) (日本語) | Tiering carries per-request charges, and deduplication does not lower the bill |
| [Volume security style decides the permission model](domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) | Blocking ID mapping does not block SMB access on an NTFS-style volume |
| [The AD dependency lasts the lifetime, not just the join](domains/multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) | An expired service account is symptomless until the next maintenance window |
| [Some SVMs cannot serve SMB](domains/multiprotocol-identity/notes/smb-service-lost-on-cifs-server-delete.md) | The cause is a deleted CIFS server, not the creation date. The ONTAP REST API restores it |
| [An exhausted audit destination stops client access](domains/security-governance/notes/audit-log-space-and-client-access.md) | Not at the moment it fills, and the EMS event reporting the write failure is not visible to you |

---

<details>
<summary><strong>🗺️ Two-Axis Navigation (click to expand)</strong></summary>

### Lifecycle axis — `playbooks/`

Enter here when your question is "which phase am I in right now?"

| # | Module | Question it answers |
|---|---|---|
| 01 | [`01-assess/`](playbooks/01-assess/) | What exists on the current NAS, and what will constrain the migration |
| 02 | [`02-design/`](playbooks/02-design/) | Which configuration, capacity, throughput, and protection scheme to choose |
| 03 | [`03-migrate/`](playbooks/03-migrate/) | Which method to use, how to cut over, and how to roll back |
| 04 | [`04-build/`](playbooks/04-build/) | How to structure IaC, automation, and reproducible builds |
| 05 | [`05-operate/`](playbooks/05-operate/) | How to run monitoring, capacity, incident response, and change management |
| 06 | [`06-optimize/`](playbooks/06-optimize/) | How far to tune performance and cost |

### Topic axis — `domains/`

Enter here when your question is "I need to research this specific concern." These are referenced across all lifecycle phases.

| Module | Question it answers |
|---|---|
| [`data-protection/`](domains/data-protection/) | Snapshot / SnapMirror / SnapLock / backup and ransomware readiness |
| [`data-utilization/`](domains/data-utilization/) | Analytics, AI/RAG, and data access over the S3 API |
| [`security-governance/`](domains/security-governance/) | Encryption, audit, permission design, and how to think about regulated workloads |
| [`performance/`](domains/performance/) | Throughput design, latency, caching, shared bandwidth |
| [`cost/`](domains/cost/) | Capacity, tiering, and the gap between estimates and measurements |
| [`multiprotocol-identity/`](domains/multiprotocol-identity/) | NFS / SMB coexistence, Active Directory integration, ID mapping |

### Cross-cutting reference — `reference/`

| Directory | Contents |
|---|---|
| [`decision-trees/`](../ja/reference/decision-trees/README.md) | Selection flowcharts (migration method, protection scheme, protocol, SMB identity and auditing) |
| [`comparison/`](../ja/reference/comparison/) | Option comparison matrices (trade-offs stated symmetrically) |
| [`limits/`](../ja/reference/limits/) | Limits and quotas, with sources and verification dates |
| [`glossary/`](../ja/reference/glossary/) | ONTAP / AWS terminology and definitions |

### Hands-on delivery — `workshop-studio/`

| Directory | Contents |
|---|---|
| [`workshop-studio/`](../ja/workshop-studio/) | Measured timings and module selection for fitting a public AWS Workshop Studio workshop into the time an event actually has (日本語) |

</details>

<details>
<summary><strong>📁 Shared Module Structure (how to extend)</strong></summary>

Every module under `playbooks/` and `domains/` has the **same internal structure**. To add a new module, copy `_template/`.

```text
docs/<lang>/{playbooks,domains}/<module>/
├── README.md          # Module hub
├── notes/             # Smallest unit of knowledge. One file = one concern
│   └── <slug>.md      # YAML frontmatter required
└── checklists/        # Checklists for field use
    └── <slug>.md
```

Each file under `notes/` carries metadata in YAML frontmatter, so that AI agents and web crawlers can interpret it as structure rather than prose.

```yaml
---
title: Triaging low throughput during SnapMirror initial sync
lifecycle: [migrate]          # Tag on the playbooks axis
domains: [performance]        # Tag on the domains axis
evidence: verified            # verified | documented | field-observation | hypothesis
verified_on: 2026-08-06       # Required when evidence: verified
ontap_version: 9.17.1P7D1     # Version at verification time (where applicable)
region: ap-northeast-1        # Verification region (where applicable)
lang: en
---
```

The four `evidence` levels let readers judge how far a given note can be relied on. See the [Evidence Policy](evidence-policy.md) for details.

</details>

<details>
<summary><strong>📚 How Case Studies Are Handled (anonymization policy)</strong></summary>

`case-studies/` carries findings from field technical-support work, but **contains no non-public information whatsoever**.

| Not included | Written instead |
|---|---|
| Company, organization, or department names | Industry and scale band (e.g. manufacturing / several hundred TB) |
| Real hostnames, IPs, account IDs | Placeholders (`10.0.x.x`, `123456789012`) |
| Verbatim architecture diagrams | Configuration abstracted to the level the point requires |
| Individual or reviewer names | Role-based references (e.g. "from a storage operations perspective") |
| Support case numbers, internal ticket IDs | "Confirmed with the vendor (tracked)" |

Case studies are written as **generalized lessons**: what the problem was, how it was judged, and what the outcome was. The template lives in [`case-studies/_template/`](../ja/case-studies/_template/). Pre-publication checks are automated via `make audit`.

</details>

<details>
<summary><strong>🌐 Localization Policy (8 languages)</strong></summary>

To balance translation cost against freshness, content is split into **three tiers**.

| Tier | Scope | Languages |
|---|---|---|
| Tier 1 | Root `README`, primary guides under `docs/<lang>/` | All 8 languages |
| Tier 2 | Each module's `README` | Japanese + English |
| Tier 3 | Individual files under `notes/`, `checklists/` | Japanese (English optional) |

Supported: 日本語 / English / 한국어 / 简体中文 / 繁體中文 / Français / Deutsch / Español

For Tier 1, CI verifies that **section structure and count match across languages** (`make i18n-check`). Never translated: file paths, commands, badge URLs, anchor IDs, and product or technical terms (ONTAP, SnapMirror, FlexCache, SnapLock, S3 Access Point, and similar).

</details>

<details>
<summary><strong>🤖 For AI Agents and Crawlers</strong></summary>

This repository assumes both human and machine readers.

| File | Purpose |
|---|---|
| [`llms.txt`](../../llms.txt) | Repository-wide map for LLMs ([llmstxt.org](https://llmstxt.org/) convention) |
| [`AGENTS.md`](../../AGENTS.md) | Conventions, prohibitions, and verification steps for coding agents |
| frontmatter in `notes/*.md` | Machine-readable metadata (lifecycle / topic / evidence level / verification date) |
| [`reference/limits/`](../ja/reference/limits/) | Limits structured with sources and verification dates |

**Note for anyone citing this material**: notes marked `evidence: hypothesis` or `field-observation` are not verified facts. Always check the `evidence` field in the frontmatter.

</details>

<details>
<summary><strong>🔧 Contributing and Local Verification</strong></summary>

```bash
make help          # List available targets
make lint          # Markdown lint + frontmatter schema validation
make i18n-check    # Cross-language parity check for Tier 1 docs
make audit         # Pre-publication checks (naming / neutrality / PII / internal IDs)
make links         # Broken link check
make all           # All of the above
```

Issues and Pull Requests are welcome. See [CONTRIBUTING.md](../../CONTRIBUTING.md) for authoring conventions and the [Evidence Policy](evidence-policy.md) for classification criteria.

</details>

---

## Related Repositories

| Repository | Contents |
|---|---|
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | 45+ serverless processing patterns over S3 Access Points |
| [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) | Observability integrations (metrics, alerts, automated response) |
| [fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations) | Lakehouse integrations (Databricks / Snowflake / Athena / Glue / EMR) |
| [vmware-migration-ec2-ontap](https://github.com/Yoshiki0705/vmware-migration-ec2-ontap) | VMware → EC2 + FSx for ONTAP migration |

---

## Disclaimer

This repository is personal technical material and does not represent the official position of any employer.
Statements about governance or regulated workloads are **general design considerations**, not legal or compliance judgments. Benchmark figures are measurements from the stated verification environment; they do not guarantee general service limits or reproduction in a production environment.

The Japanese version of this repository is authoritative for technical accuracy. Other languages are machine-assisted translations that have not been natively reviewed before publication; where they disagree, the Japanese version prevails. Corrections are welcome as an [Issue](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues).

## License

MIT — [LICENSE](../../LICENSE)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../README.md) | [English](README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [繁體中文](../zh-TW/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Español](../es/README.md)
<!-- lang-switcher:end -->
