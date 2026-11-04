---
title: Entry point for ONTAP commands, REST APIs, and permissions — treat them as something to re-take per version, and pick what to read from what you need to check
lifecycle: [operate]
domains: [security-governance, observability]
evidence: documented
source: https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/ontap-command-api-snapshot.md
lang: en
---

# Entry point for ONTAP commands, REST APIs, and permissions

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md)

---

## Conclusion

**The ONTAP CLI commands, REST APIs, and permissions an administrator can use are a record to re-take per version, not a setting to check once and fix.** ONTAP patches are applied by the service. A measurement on the same file system shows the version rising from `9.17.1P7D1` to `9.18.1P3D1` after 11 days, in [Where the ONTAP version comes from](../../ja/reference/limits/README.md#ontap-バージョンの取得経路--where-the-ontap-version-comes-from) (日本語).

**This page carries no findings of its own.** It holds links and decision guidance, starting from the question in your hand. Numbers and observations live only in the Spoke; copying them here would leave a stale value behind when only the Spoke is corrected.

> **Tier**: `documented` — an entry point that records where the Spoke's statements live. The Spoke's observations cover **one environment, one version (ONTAP 9.18.1P6), and `fsxadmin` only**. Other versions, Multi-AZ, and roles other than `fsxadmin` are not established.

---

## Choosing by what you need to check

| Your question | Read |
|---|---|
| Which ONTAP version am I running | [Where the ONTAP version comes from](../../ja/reference/limits/README.md#ontap-バージョンの取得経路--where-the-ontap-version-comes-from) (日本語) |
| Which commands can `fsxadmin` run | The CLI section of [Snapshot of ONTAP commands and REST APIs](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/ontap-command-api-snapshot.md) (日本語) |
| Which REST APIs exist in this version, and which are unavailable because of permissions | The REST section and the section on GETs that returned 403, in the same document |
| What changed when the version went up | The [snapshot Lambda](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/solutions/ontap-catalog-snapshot/README.md) (日本語), which keeps a diff against the previous record |
| How to take it in my own environment, or have an AI agent implement it | The README of the same Lambda, and the [prompts for AI agents](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/agent-prompts/ontap-catalog-snapshot.md) (日本語) |
| Can MAV (Multi-Admin Verification) be used on FSx for ONTAP | [MAV observations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/ontap-command-api-snapshot.md#mav-の観測) (日本語). Read the next section first |

For ONTAP 9.18.1P6, `fsxadmin`, read on 2026-11-04, the Spoke records 1,744 runnable CLI commands and 570 REST endpoints. Values differ on another version or in another environment.

---

## Scope of the MAV observations

**This page does not say whether MAV can or cannot be used.** The Spoke's observations are limited to the one environment, one version, and `fsxadmin` above. Whether MAV can be configured through the AWS-side management routes (console, AWS CLI, API) is not established in the Spoke either. Read the observation table and judge from it. The Hub's treatment of MAV is in [Admin-plane protection depends on several controls](../domains/security-governance/notes/admin-plane-protection-depends-on-several-controls.md).

---

## Choosing how to take the record

Every route has constraints. This table does not favour a route. The Spoke's README carries the detailed comparison.

| Route | Suits | Constraints |
|---|---|---|
| By hand with the CLI (SSH) | Once, reading the result on the spot | Needs a route to SSH into the management endpoint. Does not produce the list of all commands, and walking `?` was not done in the Spoke either. The steps are repeated by a person at every version change |
| By hand with REST (CLI passthrough) | Keeping the result in a file to compare | The management endpoint is reachable only from inside the VPC, so a bastion or a Session Manager port forward is needed. `fields=*` is not allowed on `show-rest`, so field names are listed |
| Snapshot Lambda | Taking the same content at each version change and keeping a diff | Needs a SAM deployment and VPC and secret design. GET availability is measured only for GETs without path parameters. Confirmed on a real system only for one environment, one version, and `fsxadmin`; stopping on an authentication failure and the diff at a version change were not triggered there and are covered by unit tests |

---

## Protecting the administrator account

**On any route, do not repeat authentication failures in an operation that uses the same administrator credentials many times.** Accumulated failures lock `fsxadmin`, and a REST response cannot tell a lock from a wrong password. The background and the recovery steps are in [fsxadmin gets locked, and REST cannot tell you why](../../ja/playbooks/05-operate/notes/admin-account-lockout-and-recovery.md) (日本語).

---

## What is not established

- Results on any version other than ONTAP 9.18.1P6
- Results on Multi-AZ
- The commands that roles other than `fsxadmin` (`fsxadmin-readonly`, the `vsadmin` family) can run
- Whether MAV can be configured through the AWS-side management routes

---

## Related

| Document | Relation |
|---|---|
| [Where the ONTAP version comes from](../../ja/reference/limits/README.md#ontap-バージョンの取得経路--where-the-ontap-version-comes-from) (日本語) | The measurement of a version rising in 11 days |
| [Can maintenance be deferred?](../../ja/playbooks/05-operate/notes/maintenance-cannot-be-deferred.md) (日本語) | Patching is performed by the service |
| [Operate module](../playbooks/05-operate/README.md) | The question on handling ONTAP version updates |
| [Evidence policy](../evidence-policy.md) | What tiers such as `documented` and `verified` mean |

---

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md)
<!-- lang-switcher:start -->
🌐 [日本語](../../ja/reference/ontap-commands-and-apis.md) | [English](ontap-commands-and-apis.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
