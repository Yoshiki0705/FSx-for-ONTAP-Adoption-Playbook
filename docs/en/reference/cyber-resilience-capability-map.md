---
title: Cyber resilience capability map — a one-page view of which Spoke covers which NIST CSF 2.0 function
lifecycle: [assess, design]
domains: [security-governance, data-protection, observability]
evidence: documented
source: https://www.nist.gov/cyberframework
lang: en
---
# Cyber resilience capability map

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md)

---

## Conclusion

This page is a one-page index for seeing end-to-end cyber resilience at a glance. For each of the six NIST CSF 2.0 functions (Govern / Identify / Protect / Detect / Respond / Recover), it shows which sibling repository (Spoke) carries that slice, and sends you to that Spoke's documentation for the detail.

Each Spoke is assigned only its own slice of a function. No single Spoke holds the whole chain. This avoids the two-places-one-truth problem, where the same content lives in two places and only one gets updated while the stale copy remains.

This page carries no findings of its own. Each cell links to a Spoke's documentation, and implementation detail, measured values, and versions live only there.

> **Tier**: `documented` — records where each linked document lives. The CSF 2.0 function definitions follow the [NIST Cybersecurity Framework 2.0](https://www.nist.gov/cyberframework). A row in this map does not mean the function has been verified on FSx for ONTAP; read each linked document's tier for its verification state.

---

## How to read this map

There are three Spokes, and their slices are divided by function.

- Cyber resilience implementation patterns (the "cyber repository" below) — storage-native protection, inline scanning, event-driven response, and recovery options
- Observability integrations (the "observability repository" below) — ONTAP event ingestion, dashboards, SIEM integration, and verified recovery points
- The Amplify-based file portal (the "portal" below) — access through S3 Access Points from a Cognito-authenticated screen, with a human approval step on operations

The Hub (this repository) holds no implementation; it holds only the function-to-Spoke mapping. Govern is an organisational responsibility, and every Spoke supplies evidence artifacts only.

---

## NIST CSF 2.0 to Spoke mapping

For each function, one row shows which Spoke carries the slice. The detail is behind the links.

| CSF 2.0 function | cyber repository | observability repository | portal | Hub's slice |
|---|---|---|---|---|
| Govern (GV) | supplies evidence artifacts | supplies evidence artifacts | supplies evidence artifacts | organisational responsibility (no Spoke holds the implementation) |
| Identify (ID) | `DataClassification` tags | content / PII classification | — | function-to-Spoke mapping |
| Protect (PR) | SnapLock, Tamperproof Snapshot, MAV, inline scan, logically air-gapped vault (documentation only) | — | S3 Access Points two-layer policy | function-to-Spoke mapping |
| Detect (DE) | ARP / FPolicy | EMS / FPolicy pipeline, SIEM ML | — | function-to-Spoke mapping |
| Respond (RS) | approval-based quarantine with Step Functions | Lambda direct block | — | function-to-Spoke mapping |
| Recover (RC) | logically air-gapped vault recovery-account restore (Option D) | verified-clean recovery-point pre-filter | approval-gated restore | function-to-Spoke mapping |

The Detect row's ARP / FPolicy appears in both the cyber repository and the observability repository. The cyber repository holds the detection configuration, and the observability repository holds the ingestion and SIEM integration. The two are not written into one cell; they are divided by slice.

---

## Per-function slices

### Govern (GV)

An organisational responsibility. Risk strategy, roles, and oversight are organisational decisions. No Spoke holds the implementation; each supplies evidence artifacts such as audit trails and compliance evidence only.

### Identify (ID)

The observability repository carries content / PII classification, and the cyber repository carries volume `DataClassification` tags. Office / PDF extraction is outside the observability repository's current scope.

### Protect (PR)

The cyber repository carries SnapLock, Tamperproof Snapshot, MAV, inline scan, and the logically air-gapped vault (documentation only). The portal carries the S3 Access Points two-layer policy (the IAM access point policy and the file system user). These protect the availability and integrity of recovery points and files; exfiltration through authorised reads is handled under a different function.

### Detect (DE)

ARP / FPolicy involves both the cyber repository and the observability repository. The cyber repository holds the ARP / FPolicy detection configuration, and the observability repository holds the EMS / FPolicy pipeline and SIEM ML. FPolicy involves NFS / SMB only.

### Respond (RS)

The cyber repository carries approval-based quarantine with Step Functions, and the observability repository carries the Lambda direct block. Either can be triggered from any detection source.

### Recover (RC)

The cyber repository carries the logically air-gapped vault recovery-account restore (Option D), the observability repository carries the verified-clean recovery-point pre-filter, and the portal carries the approval-gated restore.

---

## Where the detail lives

Per-function implementation detail lives in the following places. This page does not restate it.

- The per-function detail is in the cyber repository's single mapping ([docs/en/cyber-resilience-framework-mapping.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/en/cyber-resilience-framework-mapping.md)). It includes the encryption/destruction vs exfiltration scenarios, the management-plane compromise, and the evidence types.
- The full six-function implementation-level detail is in the observability repository's existing capability map ([docs/en/cyber-resilience-capability-map.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/blob/main/docs/en/cyber-resilience-capability-map.md)). This page points to it and does not restate its content.

---

## The logically air-gapped vault's placement

The logically air-gapped vault appears above under Protect (documentation only) and Recover (Option D restore). The work of adding this vault as one isolation option in the data-protection domain is handled in a separate Issue ([#316](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/316)). The trade-offs beside SnapLock, Tamperproof Snapshot, and SnapVault to a separate account, and the approval path for the irreversible settings such as Vault Lock compliance mode being always on, are deferred to #316. This page does not restate them.

This map is a reference for seeing the function-to-Spoke mapping, and #316 is the isolation-option content in the data-protection domain. The two are distinct slices and do not overlap.

---

## Related documents

- [Index of cross-repository citations](../../ja/reference/cross-repo-index.md) — which claim is cited from which Spoke, and the division of labour
- [Reference](../../ja/reference/README.md) — the list of cross-cutting reference material

---

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/reference/cyber-resilience-capability-map.md) | [English](cyber-resilience-capability-map.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
