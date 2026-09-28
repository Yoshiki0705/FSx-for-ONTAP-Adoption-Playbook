---
title: Modernization journey map — migration as the entry, and which module, decision tree, and pattern to read at each stage
lifecycle: [assess, design, migrate, operate]
domains: [block-storage, data-protection, data-utilization, security-governance, observability, cost]
evidence: documented
source: https://aws.amazon.com/fsx/netapp-ontap/
lang: en
---
# Modernization journey map

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md)

---

## Conclusion

**This map lays out what comes after a migration, along a timeline. There are two ways in.**

- **To proceed in order** → [the journey stage table](#the-journey-stage-table). Migration is the entry, then containerization, data utilization, DR, and operational optimization
- **To enter from a specific stage** → [the stage-by-stage index](#the-stage-by-stage-index), which lists the spoke, decision tree, and design notes for each stage

**This map does not answer selection questions. It answers ordering.** Which path to take, which protocol to serve over, which datastore to use — those branches live in the existing [decision trees](../../ja/reference/decision-trees/). This map only covers "where am I in the journey, and what do I read next," and hands selection itself off to the decision trees.

**To enter from an industry, use a different map.** The same set of spokes arranged by industry is the [industry resource map](../../ja/reference/industry-resource-map.md); problem-first ISV and SaaS options are the [ISV / SaaS solution map](isv-solution-map.md). This map rearranges those same spokes along the stages of modernization.

**There is one center to the arc.** With the migration from VMware to EC2 + Amazon FSx for NetApp ONTAP as the entry, the journey proceeds through containerization, going serverless, analytics / AI, DR / resilience, and operational optimization, keeping FSx for ONTAP as the core of the data foundation throughout. It pairs with a sibling blog series; Part 1 and Part 2 are published. Part 3 and Part 4 are not yet published ([related blog posts](#related-blog-posts)).

> **Tier**: `documented` — records where each spoke repository link and each in-repository module lives. The "where decisions concentrate" column for each stage summarizes the concern the linked note covers; it is not a result verified in this map.
---

## The journey stage table

**There are six stages, 0 through 5.** Migration is the entry (stage 1), with assessment before it (stage 0) and the stages of modernization laid out after it.

**One caveat first: the stages do not force you to pass through all of them in order.** Some paths reach serverless without containerizing; some design DR alongside the migration itself. This table draws one representative arc. Skip the stages your path does not include, and read only the ones you need.

| Stage | What you do | Read first (in this repo) | Implementation pattern (spoke) | Where decisions concentrate at this stage |
|---|---|---|---|---|
| 0. Assess | Inventory the migration targets and their shape | [Assess](../playbooks/01-assess/) | — | Counting files. You can run out of write capacity even with capacity to spare |
| 1. Migrate (entry) | VMware → EC2 + FSx for ONTAP | [Migrate](../playbooks/03-migrate/) / [migration-method decision tree](../../ja/reference/decision-trees/migration-method.md) | [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) | When the rollback window closes. Boot is always on Amazon EBS |
| 2. Containerize | Replatform to ECS / EKS, keep the data layer | [datastore-selection decision tree](decision-trees/container-datastore-selection.md) / [block storage](../domains/block-storage/) | [Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) | The runtime (EC2 / Fargate) decides how you reach the data. The Trident PV volume-count limit |
| 3. Serverless / analytics / AI | Use the data via S3 Access Points | [client-access-route decision tree](../../ja/reference/decision-trees/client-access-route.md) / [data utilization](../domains/data-utilization/) | [Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) / [Lakehouse-Integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) / [S3-Burst](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) / [Agentic-RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | S3 Access Points do not behave like a full S3 bucket. The original ACLs do not carry over |
| 4. DR / resilience | Replication, Snapshot, ransomware readiness | [data protection](../domains/data-protection/) / [security governance](../domains/security-governance/) | [Cyber-Resilience-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns) | Enabling and locking are separate. Three irreversible choices |
| 5. Operate / observability / optimize | Monitoring, capacity, tiering, cost | [Operate](../playbooks/05-operate/) / [Optimize](../playbooks/06-optimize/) / [cost-higher-than-expected decision tree](../../ja/reference/decision-trees/cost-higher-than-expected.md) | [Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) | Monitoring fails on averages. Billing splits between provisioned and consumed |

Some things you **run through first**, at every stage. Give them priority over the stage rows.

| Run through first | Why at every stage |
|---|---|
| [Pre-production review](../../ja/playbooks/04-build/checklists/pre-production-review.md) (日本語) | **Items you cannot change later** are stage-independent: SnapLock, Snapshot locking, security style, `NetworkOrigin` |
| [Evidence policy](../evidence-policy.md) | The tiers that keep a case-study or benchmark number from becoming a design basis unexamined |
| [Limits and quotas](../../ja/reference/limits/) | Whether you hit a limit is decided by configuration, not by stage |

---

## The stage-by-stage index

For each stage, this lists the implementation pattern (spoke), the in-repository decision tree, and the design notes. Individual note links reuse ones already confirmed to exist in the [industry resource map](../../ja/reference/industry-resource-map.md). Where an English page does not yet exist, the link points to the Japanese page.

### 0. Assess

| Type | Resource | Point |
|------|----------|------|
| Decision tree | [File storage selection](../../ja/reference/decision-trees/file-storage-selection.md) | What to serve, over which protocol, decided at the entry |
| Note | [Counting bytes is not counting files](../playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) | Inventory the file count |

### 1. Migrate (entry)

| Type | Resource | Point |
|------|----------|------|
| Pattern | [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) | Both VMware → EC2 + FSx for ONTAP paths, verified hands-on |
| Decision tree | [Migration method selection](../../ja/reference/decision-trees/migration-method.md) | Which migration method to choose |
| Note | [Where the rollback window closes](../playbooks/03-migrate/notes/where-the-rollback-window-closes.md) | The cutover decision |
| Note | [Preserving ACLs during migration](../../ja/playbooks/03-migrate/notes/preserving-acls-during-migration.md) (日本語) | Permission preservation during migration |

### 2. Containerize

| Type | Resource | Point |
|------|----------|------|
| Pattern | [Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) | Datastores for ECS / EKS |
| Decision tree | [Container datastore selection](decision-trees/container-datastore-selection.md) | The runtime decides how you reach the data |
| Note | [Kubernetes block volumes and the volume limit](../domains/block-storage/notes/kubernetes-block-volumes-and-the-volume-limit.md) | The split between `ontap-san` and `ontap-san-economy`. What you run out of is not capacity |

### 3. Serverless / analytics / AI

| Type | Resource | Point |
|------|----------|------|
| Pattern | [Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | Industry use cases via S3 Access Points |
| Pattern | [Lakehouse-Integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) | Athena / Glue / Spark integration |
| Pattern | [S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) | Collect via S3 → serve as NFS / SMB through FlexCache |
| Pattern | [Agentic-Access-Aware-RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | Access-control-aware Agentic RAG |
| Decision tree | [Client access route selection](../../ja/reference/decision-trees/client-access-route.md) | Which route reaches the data |
| Note | [S3 Access Points do not behave like a full S3 bucket](../../ja/domains/data-utilization/notes/s3-access-point-constraints.md) (日本語) | Same-account, same-region and other constraints |
| Note | [S3 Access Points authorize every request as one identity](../../ja/domains/data-utilization/notes/reaching-data-without-copies.md) (日本語) | The original ACLs do not carry over into the AI pipeline |

### 4. DR / resilience

| Type | Resource | Point |
|------|----------|------|
| Pattern | [Cyber-Resilience-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns) | Defense in depth with ARP + File Security + FPolicy |
| Note | [SnapLock separates enabling from locking](../../ja/domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md) (日本語) | Three irreversible choices |
| Note | [Having a Snapshot is not the same as being able to recover](../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md) | Data protection design |

### 5. Operate / observability / optimize

| Type | Resource | Point |
|------|----------|------|
| Pattern | [Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) | Forward audit logs to Datadog / Splunk and others |
| Decision tree | [When the bill is higher than expected](../../ja/reference/decision-trees/cost-higher-than-expected.md) | Provisioned or consumed. The lever differs by which one |
| Note | [Monitoring fails on averages](../playbooks/05-operate/notes/monitoring-fails-on-averages.md) | Standby nodes pull the average down |
| Note | [Billing splits between provisioned and consumed](../domains/cost/notes/provisioned-versus-consumed.md) | The structure of TCO |

---

## Related blog posts

The correspondence between each stage and a blog post. **Part 1 and Part 2 are published and linked in the table below. Part 3 and Part 4 are not yet published.** Links to Part 3 and Part 4 will be added after publication. The English post is the primary link, with the Japanese post alongside it.

| Stage | Blog post |
|---|---|
| 1. Migrate | [Part 1 (designing the entry)](https://dev.to/aws-builders/designing-aws-modernization-with-vmware-migration-as-the-entry-point-why-fsx-for-ontap-as-the-3k24) ([日本語](https://hakobiya.hatenablog.com/entry/fsxn-vmware-migration-options-ec2)) / [Part 2 (AWS Transform, hands-on)](https://dev.to/aws-builders/aws-transform-now-supports-block-storage-migration-to-fsx-for-ontap-benefits-and-pitfalls-from-a-1hhe) ([日本語](https://hakobiya.hatenablog.com/entry/fsxn-aws-transform-mgn-migration-target)) |
| 2-4. Modernization | Part 3 (containerization, S3 Access Points, DR) — not yet published |
| 1. Migrate (existing assets) | Part 4 (Shift Toolkit) — not yet published |

---

## How to read this

1. **Find the stage you are at** — from the stage table. **The stages are not a promise that you pass through all of them in order.** Skip the stages your path does not include
2. **What you read first are the in-repository modules** — playbooks (lifecycle axis) and domains (topic axis). Selection branches are handed to the decision trees
3. **Implementation patterns are the spoke repositories** — runnable templates including SAM / CDK / CFn
4. **"Where decisions concentrate" is the concern the linked note covers** — it is this map's summary; if you use it as a design basis, check the linked page and the note's tier
5. **Before the stage rows, run through the three shared items** — at the end of [the stage table](#the-journey-stage-table). **Items you cannot change later are stage-independent**

---

## Sibling repositories

| Repository | Contents | Format |
|---|---|---|
| [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) | The migration entry. Both paths verified hands-on | CFn |
| [FSx-for-ONTAP-Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) | Datastores for ECS / EKS | Implementation patterns |
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | Industry use cases + OPS + GenAI + file portal UI | SAM + Amplify Gen2 |
| [FSx-for-ONTAP-Lakehouse-Integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) | Athena / Glue / Spark integration | S3 Access Points |
| [S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) | Collect via S3 → serve as NFS / SMB through FlexCache | CFn + SAM |
| [FSx-for-ONTAP-Agentic-Access-Aware-RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | Access-control-aware Agentic RAG | CDK |
| [FSx-for-ONTAP-Cyber-Resilience-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns) | Defense in depth with ARP + File Security + FPolicy | Implementation patterns |
| [FSx-for-ONTAP-Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) | Audit logs → Datadog / Splunk and others | Lambda + S3 Access Points |

---
[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md)
<!-- lang-switcher:start -->
🌐 [日本語](../../ja/reference/modernization-journey-map.md) | [English](modernization-journey-map.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
