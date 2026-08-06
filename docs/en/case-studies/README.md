# Case Studies

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/case-studies/README.md) | [English](README.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->

---

Findings from field technical-support work, organized as **generalized lessons**.

---

## Anonymization policy (absolute requirement)

This directory contains **no non-public information whatsoever**. When in doubt, leave it out.

| Not included | Written instead |
|---|---|
| Company, organization, department, or product names | Industry and scale band (e.g. manufacturing / several hundred TB) |
| Individual or reviewer names | Role-based references (e.g. "from a storage operations perspective") |
| Hostnames, IPs, account IDs, file system IDs | Placeholders (`10.0.x.x`, `123456789012`, `fs-0123456789abcdef0`) <!-- gitleaks:allow --> |
| Verbatim architecture diagrams or screenshots | Configuration abstracted to the level the point requires |
| Support case numbers, internal ticket IDs | "Confirmed with the vendor (tracked)" |
| Scale, region, and timing combinations that identify an organization | Reduce granularity ("H1 2026" → "recently") |

**Watch for identification by combination.** Writing industry, scale, region, and timing all precisely can identify an organization even when each individual item is anonymous.

Pre-publication checks are automated via `make audit`. But automated checks only see string patterns. **Whether "anyone who knows this configuration will recognize it" is a human judgment.**

---

## How to write one

Copy [`_template/case-study.md`](../../ja/case-studies/_template/case-study.md).

| Section | Contents |
|---|---|
| Situation | Industry and scale band only |
| Problem | What was going wrong |
| Options considered | Alternatives not chosen, and why (trade-offs stated symmetrically) |
| Decision | What was chosen and on what reasoning |
| Outcome | What actually happened. **Include where it did not match expectations** |
| Generalizable lesson | The part that transfers to other environments |
| Applicability limits | Conditions under which this lesson does not hold |

A collection of success stories is worth less than it looks. **The points where reality diverged from the plan, and where work had to be redone, are what readers can use.**

---

## Index

### How to find one

**Search by your industry, or by your workload.** Both axes reach the same material.

| Route | Where to look |
|---|---|
| **By industry** | [Public case studies — by industry](../../ja/case-studies/public-case-studies.md#業種から探す) (日本語) — energy, semiconductor/EDA, financial services, healthcare, medical devices, telecom, public health and education, media, IT |
| **By workload** | [Public case studies — by workload](../../ja/case-studies/public-case-studies.md#ワークロードから探す) (日本語) — NAS migration, SQL Server, EDA, SaaS tenancy, hybrid and branch caching, media production, multi-Region |
| **Industry-specific design material** | [Design material by industry](../../ja/case-studies/public-case-studies.md#業種固有の設計資料) (日本語) — EDA, financial services, EHR |
| **Learn from a judgement that went wrong** | The table below (this repository's own cases) |

**A matching workload is often more useful than a matching industry**, and the reverse holds too.

---

### Three kinds are kept apart

| Kind | Contents | Tier |
|---|---|---|
| Public case study | Published by AWS or NetApp. **Organized as a linked index** | Location of the published account only |
| Field case | A lesson from technical-support work, generalized | `field-observation` |
| Verification case | An observation in **this repository's own verification environment** — not a customer engagement | `field-observation` |

**They are separated so a reader cannot mistake whose environment is being described.**

A public case study is the fact that **an organization published that account**. Most do not state the ONTAP version, Region, configuration or measurement method, so **treat the figures in them as something to measure in your own environment, not as a design basis.** How to read them is in [what to check while reading](../../ja/case-studies/public-case-studies.md#読むときに確認すること) (日本語).

Field and verification cases are both single-environment observations, and neither guarantees reproduction elsewhere.

---

### This repository's own cases

| Case study | Kind | Scale band | Primary topic |
|---|---|---|---|
| [A documented default did not reproduce, and the guidance derived from it was wrong](../../ja/case-studies/documented-default-did-not-reproduce.md) (日本語) | Verification | Several TB | A citation is not a measurement; keep both values when they disagree |

**For cases and primary sources already published elsewhere**, see [Public references and how to weigh them](../../ja/case-studies/public-references.md) (日本語). It maps where the AWS and NetApp documentation, blogs, Q&A sites, and community material actually live, and how much weight each kind of source carries.

---

## Related documents

- [Navigation Guide](../navigation.md)
- [Evidence Policy](../evidence-policy.md)
- [CONTRIBUTING.md](../../../CONTRIBUTING.md)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/case-studies/README.md) | [English](README.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
