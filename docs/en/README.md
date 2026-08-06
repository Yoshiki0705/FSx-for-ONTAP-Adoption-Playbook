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
| Learn how to read the confidence levels | [Evidence Policy](evidence-policy.md) | 5 min |
| Add knowledge (authoring) | [CONTRIBUTING.md](../../CONTRIBUTING.md) | 10 min |

> **Coverage**: the 6 lifecycle modules and 6 domain modules currently define the questions they will
> answer and the structure to answer them in — `notes/` is not yet populated. Each module README lists
> the questions it is scoped to cover.
> The table above therefore lists **only material that has content today**, rather than spending a
> reader's time on an empty entry point. For the full module map, see the two-axis navigation below.

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
| [`decision-trees/`](../ja/reference/decision-trees/) | Selection flowcharts (migration method, protection scheme, protocol) |
| [`comparison/`](../ja/reference/comparison/) | Option comparison matrices (trade-offs stated symmetrically) |
| [`limits/`](../ja/reference/limits/) | Limits and quotas, with sources and verification dates |
| [`glossary/`](../ja/reference/glossary/) | ONTAP / AWS terminology and definitions |

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
