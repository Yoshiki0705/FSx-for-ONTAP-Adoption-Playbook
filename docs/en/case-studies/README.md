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

| Case study | Industry | Scale band | Primary topic |
|---|---|---|---|
| _None added yet_ | — | — | — |

---

## Related documents

- [Navigation Guide](../navigation.md)
- [Evidence Policy](../evidence-policy.md)
- [CONTRIBUTING.md](../../../CONTRIBUTING.md)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/case-studies/README.md) | [English](README.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
