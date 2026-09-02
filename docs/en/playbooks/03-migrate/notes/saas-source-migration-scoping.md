---
title: Migrating from SaaS starts with classifying the source and mapping permissions, not with choosing a transfer method
lifecycle: [assess, migrate]
domains: [multiprotocol-identity, security-governance, cost]
evidence: documented
source: https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/en/saas-to-fsx-ontap-migration.md
lang: en
---

# Migrating From SaaS Starts With Classifying the Source

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/playbooks/03-migrate/notes/saas-source-migration-scoping.md) | [English](saas-source-migration-scoping.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

[🏠 Repository Top](../../../README.md) | [Playbook 03 — Migration](../README.md)

> This is the English translation. Japanese is authoritative for technical accuracy. Please report any discrepancy.

---

## Scope of this note

**The technical mechanisms are not here.** AWS DataSync location types, how each SaaS admin API is called, and the FSx for ONTAP S3 AP size limits all live in the primary source.

> Primary source: [Migration and data integration from SaaS / cloud storage to FSx for ONTAP](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/en/saas-to-fsx-ontap-migration.md) ([日本語](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/ja/saas-to-fsx-ontap-migration.md))

What belongs here is **where in the plan each thing has to be settled**: what to establish about the source, what to measure during Assess, and where to conclude that the work is a redesign rather than a migration.

---

## Conclusion

**Settle three things before evaluating transfer methods.**

1. **Whether the source exposes a storage endpoint.** This is where the path forks. "Cloud storage" covers two different categories: services exposing an S3-compatible API, and collaboration SaaS
2. **Whether the permissions have anywhere to map to.** How many sharing forms have no counterpart (external link sharing, anonymous links, time-limited shares). When that share of usage is large, the work becomes a **permission redesign**, not a migration
3. **Whether the largest file exceeds 50 GiB.** If it does, that file cannot be written through an S3 AP. This forks the write path

**And do not fix a downtime figure until API rate limits have been measured.** When migrating from collaboration SaaS, rate limits govern how long an incremental sync takes. A published catalog value does not let you estimate it.

> **Evidence**: `documented` — the factual claims (which sources can be handled, which services offer tenant-wide admin authorization, how a primary-storage configuration behaves) rest on the AWS and vendor documentation cited by the primary source.
> **The order of the checks and the Go/No-Go thresholds are practical judgment, not verification results.** Unconfirmed items are listed under "[What has not been confirmed](#what-has-not-been-confirmed)".

---

## 1. Classify the source

**These three points largely determine the path.** The order matters; each narrows the candidates.

| # | What to establish | What the result means |
|---|---|---|
| 1 | **Does the service expose an S3-compatible API (or Blob / NFS / SMB)?** | Yes → group A. It can be used as a DataSync location. No → go to 2 |
| 2 | **Is it self-hosted open source (Nextcloud / ownCloud / Seafile)?** | Yes → go to 3. No (collaboration SaaS) → group B. DataSync cannot handle it; the path is an admin API plus a purpose-built worker |
| 3 | **Is the object storage the primary storage, or an external storage mount?** | External storage → treat as group A. **Primary storage → the path changes** (below) |

### Point 3 matters most

**With primary storage, copying the bucket directly does not restore anything.** File names and directory structure live only in the database; the bucket holds bodies keyed by an identifier (`urn:oid:<id>` form).

**And this failure does not surface as a failure.** The transfer succeeds. Identifier-named files appear on FSx for ONTAP, and it emerges later that users cannot open their own files.

This is the class of problem discovered after the migration has been judged complete, so **settle the classification during Assess.** The method for checking it is in the primary source.

### Do not decide point 1 from a service name

Judge by whether an S3-compatible API exists, **not by the service name.** Similar names can belong to different services — Google Cloud Storage is among the DataSync sources; Google Drive is not.

DataSync source coverage and Bedrock connector coverage **move in the direction of additions.** Before settling an approach on the basis of a statement that something is unsupported, pull the documentation again as of that day.

---

## 2. For group B: can tenant admin authorization be provisioned for the migration window?

**This is the precondition for central execution.**

The five main collaboration SaaS products (Microsoft 365 / Google Workspace / Box / Dropbox Business / Egnyte) provide **tenant-wide admin authorization that does not require per-user OAuth consent.** The migration can therefore be run centrally by the operating team. The assumption that each user must configure something does not apply to these services.

What has to be established is not technical feasibility but **whether the organization can issue that authorization.**

| What to establish | What happens if you skip it |
|---|---|
| Whether a credential that can read the whole tenant can be issued for the migration window | If it cannot, the premise for central execution collapses and the plan is rebuilt |
| Whether a procedure exists to revoke it after migration | Tenant-wide permission persists. A migration app registration is a high-value target |
| Whether the read volume the migration generates will trip normal audit alert thresholds | A stop request arrives from the security side mid-migration |
| How impersonated execution is recorded in audit logs | A large volume of access is recorded with "who ran this" left ambiguous |

**Design for the permission to be enabled only for the migration window and revoked afterwards.** Make that revocation an explicit final task in the migration plan.

---

## 3. Numbers to collect during Assess

**The decisions in 03-migrate cannot start without these.** Add them to the 01-assess inventory.

| # | Number to collect | Which decision it feeds |
|---|---|---|
| 1 | Total capacity | Total cost of each path. Which is cheaper — a staged path or a direct one — flips with capacity |
| 2 | File count | With many small files, metadata operations govern throughput. Determines whether split parallel transfer is needed |
| 3 | **Largest file size** | **Whether it exceeds 50 GiB forks the write path.** Above that, the file cannot be written through an S3 AP |
| 4 | Share of SaaS-native formats | The scope requiring conversion. Conversion is irreversible, so this drives how many "what is the system of record" decisions are outstanding |
| 5 | Count of external shares | The size of the un-mappable part of the permission model. This is Go/No-Go material |
| 6 | Whether version history migrates | Migrating full history multiplies total capacity. It changes the capacity estimate |

**Items 3 and 5 are the easiest to overlook, and discovering them late means rebuilding the plan.**

The pitfalls of counting itself — counting bytes is not counting files — are in [Free space does not mean you can still write](../../../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md).

---

## 4. Go/No-Go material

**The question is not "can this be migrated" but "does this hold together as a migration".**

### Stop condition 1 — many sharing forms have no counterpart

External link sharing, anonymous links, and time-limited shares have no mapping into NFS / SMB ACLs. The alternatives (expiring URLs, distribution through Transfer Family, a sharing feature implemented in a portal) become **separate design work.**

| Scale of the count | Nature of the work |
|---|---|
| Few, used as exceptions | A migration. Alternatives can be assigned case by case |
| Many, a primary way the business works | **A redesign, not a migration.** Re-examining the sharing requirements precedes any evaluation of transfer |

**The threshold cannot be expressed as a number.** What decides it is whether that sharing form is a primary way the business works or an exception. **Fix the permission mapping in a pilot (one department is enough) before the main migration.** Moving data first leaves every file accessible only to administrators immediately after cutover.

### Stop condition 2 — rate limits have not been measured

**Do not fix a downtime figure until they have.** In group B, API rate limits determine how long an incremental sync takes. It cannot be calculated from bandwidth.

| State | What can be stated |
|---|---|
| Pilot not yet run | "The path is decided. Duration will be measured in the pilot" |
| Pilot complete | An estimate based on measurements, stated with its premises (scope, capacity, timing) |

A pilot of one department and a few hundred GB is enough. Its purpose is not to complete a transfer but to **measure rate limits and throughput.**

### Stop condition 3 — the system of record is undecided

Converting SaaS-native formats loses collaborative editing, comments, and revision history. **Conversion is irreversible.** Until one of "convert and move", "leave native content in place and move the rest", or "move nothing and provide cross-source search only" has been chosen, transfer must not begin.

---

## 5. Confirm that migration is the requirement at all

**There is an option that provides cross-source search without moving any bytes.**

The Amazon Bedrock Knowledge Bases managed connectors cover OneDrive / Google Drive / SharePoint and apply per-document ACL filtering at retrieval time. Registering FSx for ONTAP as an S3 data source through an S3 AP puts both in the same knowledge base, so cross-source search works without a migration.

This is a choice about fit, not about one option being better.

| Objective | Migration | Integration only |
|---|---|---|
| Cross-source natural language search | Excessive; integration suffices | Suits this |
| Access from existing applications over NFS / SMB | Suits this | Does not meet it |
| Ending the SaaS contract | Suits this | Does not meet it |
| Applying WORM retention and ransomware controls on the FSx for ONTAP side | Suits this | Does not meet it |
| Showing a result quickly | Takes longer | Starts sooner |

**The constraints on the integration side are stated symmetrically.** Content is still passed to Bedrock to generate embeddings. "We are not migrating, so data does not move" does not hold. Evaluate Region scope and data processing boundaries by the same standard you would apply to a migration. **Per-connector GA / preview status has to be confirmed before production adoption.**

If the objective is only search, confirm this before evaluating a migration.

---

## Common misconceptions

| Misconception | Reality |
|---|---|
| Anything called cloud storage can be moved with DataSync | It depends on whether a storage endpoint is exposed. Services with an S3-compatible API can be handled; collaboration SaaS cannot |
| Support can be judged from the service name | Similarly named but different services exist. The criterion is whether an S3-compatible API exists |
| With no bulk migration tool, users have to do it themselves | The five main services offer tenant-wide admin authorization and can be run centrally. What is missing is not bulk access on the SaaS side |
| For self-hosted open source, copying the bucket is enough | Not with a primary-storage configuration. **And because the transfer succeeds, it does not surface as a failure** |
| Migration effort is determined by transfer time | Most of it is mapping the permission model, native formats, and associated data |
| If the files moved, the business moved | Version history, comments, share links, and trash each need a separate decision |
| Downtime can be calculated from bandwidth | In group B, rate limits govern it. Measurement is the premise |
| Data can move first and permissions be sorted out later | Every file ends up accessible only to administrators right after cutover. Fix the mapping in a pilot |
| Files above 50 GiB can be written with multipart upload | Not through an S3 AP. Use NFS / SMB |
| Not migrating means the data does not move | Even with integration, content is passed out to generate embeddings |

---

## What has not been confirmed

**Items the primary source marks as unconfirmed are treated as unconfirmed here too.**

- **The completeness of the Amazon AppFlow connector list** has not been checked. The judgment that it is out of scope — record-oriented, with no FSx for ONTAP destination — is unchanged, but no claim is made that a specific connector does not exist
- **Per-connector GA / preview status for Amazon Bedrock Knowledge Bases** must be checked individually
- **Whether Citrix ShareFile supports tenant-wide impersonation** could not be confirmed
- **A business administrator content API for iCloud Drive** could not be found. No claim is made that none exists
- **No commercial migration service has been evaluated as a product.** Only structural feasibility is stated
- The DataSync location table and Bedrock connector list in the primary source are a **snapshot as of 2026-08**

**Region availability and connector coverage move.** If a plan or document states coverage, pull the documentation again at the time of writing.

---

## Related Documents

- [Migration and data integration from SaaS / cloud storage to FSx for ONTAP](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/en/saas-to-fsx-ontap-migration.md) — **Primary source.** Source classification flow, DataSync location types, admin APIs, S3 AP size limits
- [Playbook 03 — Migration](../README.md) — Module hub
- [Migration Method Decision Tree](../../../../ja/reference/decision-trees/migration-method.md) (日本語) — Method selection when the source is ONTAP or an on-premises NAS
- [ACL preservation is a permissions problem, not a tooling problem](../../../../ja/playbooks/03-migrate/notes/preserving-acls-during-migration.md) (日本語) — From an on-premises NAS, ACLs can be carried. From SaaS, they have to be created
- [The rollback window closes the moment a client writes](where-the-rollback-window-closes.md) — Cutover and rollback design
- [Free space does not mean you can still write](../../../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) — Pitfalls of counting
- [FSx for ONTAP S3 access points are not "S3 you can use as S3"](../../../../ja/domains/data-utilization/notes/s3-access-point-constraints.md) (日本語) — Constraints when choosing it as the write path
- [Evidence Classification Policy](../../../evidence-policy.md)

---

[🏠 Repository Top](../../../README.md) | [Playbook 03 — Migration](../README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/playbooks/03-migrate/notes/saas-source-migration-scoping.md) | [English](saas-source-migration-scoping.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
