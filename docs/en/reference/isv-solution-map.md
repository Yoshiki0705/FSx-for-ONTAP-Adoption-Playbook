---
title: ISV and SaaS solution map by problem — options whose combination is published, and those still unconfirmed
lifecycle: [assess, design, build]
domains: [security-governance, data-protection, data-utilization, observability, block-storage]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-vscan.html
lang: en
---

# ISV and SaaS solution map by problem

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md)

---

## Conclusion

**This index does not answer which product is better. It answers two things.**

- **Whether the problem has an option whose combination with Amazon FSx for NetApp ONTAP is published**
- **Whether this repository holds a design note to read before choosing that combination**

**The second is a column because a reader has to be able to tell what kind of entry each row is.** A row with a design note has had its primary sources read and its constraints written down here. A row without one **works only as a list of links.** Mixed into one table with no marking, a reader cannot tell how far the index has actually been checked.

**The delivery form is not decided by the problem.** The same problem draws software you host on Amazon EC2, SaaS, and AWS-managed services. So the form is one column rather than the grouping.

> **Tier**: `documented` — each row records where the combination is published. **The only product behaviour verified in this repository is what the design-note column points at.**
> **Every row in this table and in [Candidates that did not meet the bar](#candidates-that-did-not-meet-the-bar) was searched on 2026-09-15.** A row added later carries its own search date. **The date is not repeated per row because the same value in eleven places is a value that gets updated in ten.**

---

## Inclusion criteria

**A row is listed when either holds.**

1. AWS or NetApp published material recording the combination with FSx for ONTAP
2. The vendor itself announced FSx for ONTAP support

**What does not qualify goes to [Candidates that did not meet the bar](#candidates-that-did-not-meet-the-bar).** Being there does not mean "not supported". **It records our own search state: no statement naming FSx for ONTAP was reached.**

Personal blogs and community articles are outside the criteria. **Not because they are wrong, but because citing one as the source would misstate the strength of the evidence behind a `documented` tier.**

---

## Index by problem

| Problem | Options | Design note | Section |
|---|---|---|---|
| Malware and virus scanning | 6 | **yes** | [Malware and virus scanning](#malware-and-virus-scanning) |
| Removing a single point of failure in an application | 1 | yes (principle only) | [Removing a single point of failure in an application](#removing-a-single-point-of-failure-in-an-application) |
| NAS migration and data visibility | 2 | **yes** | [NAS migration and data visibility](#nas-migration-and-data-visibility) |
| Server migration including block | 1 | no | [Server migration including block](#server-migration-including-block) |
| Integrating an existing backup product | 1 | **yes** | [Integrating an existing backup product](#integrating-an-existing-backup-product) |
| Monitoring and log aggregation | 3 | **yes** | [Monitoring and log aggregation](#monitoring-and-log-aggregation) |
| File transfer and data integration | 0 | no | [File transfer and data integration](#file-transfer-and-data-integration) |
| VMware workload migration and protection | 2 | no | [VMware workload migration and protection](#vmware-workload-migration-and-protection) |

---

### Malware and virus scanning

**This problem has a dedicated page in the AWS user guide.** It is the only row in this table where AWS documentation enumerates ISV names.

| Option | Form | Source |
|---|---|---|
| Deep Instinct / SentinelOne / Symantec / Trellix / Trend Micro / OPSWAT (through ONTAP Vscan) | Software hosted on Amazon EC2 (a Vscan server) | [AWS: Use NetApp ONTAP Vscan with FSx for ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-vscan.html) · [NetApp: Vscan partner solutions](https://docs.netapp.com/us-en/ontap/antivirus/vscan-partner-solutions.html) · [AWS Storage Blog](https://aws.amazon.com/blogs/storage/securing-your-amazon-fsx-for-ontap-windows-share-smb-against-viruses/) |

**Four things are settled before the vendor is chosen.** Whether the SVM is joined to Active Directory, which protocols are in scope, the `scan-mandatory` setting, and the default exclusions. **The differences between the six only matter after those four.**

**And what can be refused in real time depends on where a write lands.** A write arriving through an S3 access point cannot be refused at the moment it lands (recording and detection still work). **Reading this index row alone, as "pick one of six", never reaches that constraint.**

- Design note: [The antivirus choice is settled before the vendor](../domains/security-governance/notes/vscan-scope-is-bounded-before-the-vendor.md)
- Decision tree: [How far antivirus scanning applies](decision-trees/vscan-antivirus-scope.md)

---

### Removing a single point of failure in an application

| Option | Form | Source |
|---|---|---|
| SIOS LifeKeeper | Software hosted on Amazon EC2 | [AWS Prescriptive Guidance blog](https://aws.amazon.com/blogs/psa/high-availability-solution-with-sios-lifekeeper-and-amazon-fsx-for-netapp-ontap/) · [Vendor announcement (2024-11-28)](https://sios.jp/news/info/2024/20241128_lk-fsx.html) |

**The scope stated in the vendor announcement** is iSCSI and NFS on Linux and iSCSI on Windows (LifeKeeper for Linux ver.9.9.0 / LifeKeeper for Windows ver.8.10.1, available from 2024-11-28).

**The design note is not about the product.** The principle comes first — when several hosts write to the same LUN, arbitration is the host's responsibility — and this product is one implementation that takes it on. **Read the principle before looking at the product.**

- Design note: [When shared block changes the design — the write-arbitration responsibility](../../ja/domains/block-storage/notes/when-shared-block-changes-the-design.md#ホスト側のクラスタ機能を担う製品) (日本語)
- Decision tree: [Block protocol and layout](../../ja/reference/decision-trees/block-protocol-and-layout.md) (日本語)

---

### NAS migration and data visibility

| Option | Form | Source |
|---|---|---|
| Komprise | SaaS (control plane) plus migration workers | [AWS Storage Blog: Cost-optimized file storage with FSx for ONTAP and Komprise](https://aws.amazon.com/blogs/storage/cost-optimized-file-storage-with-amazon-fsx-for-netapp-ontap-and-komprise/) · [Vendor announcement](https://www.komprise.com/blog/komprise-and-aws-fsx-for-netapp-ontap/) |
| Datadobi StorageMAP | Software | [Vendor announcement](https://datadobi.com/post_news/organizations-can-now-accelerate-journey-to-the-cloud-with-amazon-fsx-for-netapp-ontap-and-datadobis-storagemap/) |

**AWS-native options sit beside these for the same problem.** AWS DataSync, and NetApp SnapMirror when the source is ONTAP. **The method is sometimes already settled before any product is considered.**

**And for the goal of spending less, external archiving and the FSx for ONTAP capacity pool tier read as one column and are in fact ordered.** That the published reduction rate is measured against the adopting organization's legacy environment also needs checking before the figure is used.

- Design note: [Archiving and the capacity pool tier are ordered, not alternatives](../domains/cost/notes/archiving-and-tiering-are-ordered-not-alternatives.md)
- Decision tree: [Choosing a migration method](../../ja/reference/decision-trees/migration-method.md) (日本語)
- Design note: [Preserving ACLs is a permissions problem, not a tooling problem](../../ja/playbooks/03-migrate/notes/preserving-acls-during-migration.md) (日本語)
- See also: the manufacturing case (3 PB migrated) is in the [industry resource map](../../ja/reference/industry-resource-map.md#製造) (日本語)

**Datadobi StorageMAP has only a vendor announcement, so no design note was written.** It meets the inclusion criteria, but no primary source was reached from which constraints could be set out.

---

### Server migration including block

| Option | Form | Source |
|---|---|---|
| Cirrus Data Migrate Cloud | Software (installed on the host) | [NetApp: Migrate VMs to Amazon EC2 using FSx for ONTAP](https://docs.netapp.com/us-en/netapp-solutions-virtualization/migration/migrate-vms-to-ec2-fsxn-deploy.html) · [Vendor page](https://cirrusdata.com/cloud-migration-amazon-fsxn) |

**This repository holds no design note here.** Block migration methods are covered, but nothing is set out that presumes this product. **The procedure is in the primary source.**

---

### Integrating an existing backup product

| Option | Form | Source |
|---|---|---|
| Veeam Backup & Replication | Software | [Vendor user guide](https://helpcenter.veeam.com/docs/vbaws/guide/add_fsx_policy_byb.html) · [NetApp ONTAP plug-in release information](https://www.veeam.com/kb4904) |

**Constraints settle this row first.** There are three routes, and the cloud-native one that works **through AWS Backup excludes FSx for ONTAP by name**, pointing at the file-share side instead. **This is where "we already use this backup product, so the same operation carries over" breaks.**

**And "supported" is written differently per route.** One is a stated exclusion; the other is an absence from a supported-systems list, and **the second cannot be read as non-support.**

**AWS-native options sit beside it.** FSx for ONTAP volume backups with AWS Backup, and ONTAP snapshots with SnapMirror.

- Design note: [A third-party backup product reaches it by a route that is not the AWS API](../domains/data-protection/notes/third-party-backup-reaches-it-by-another-route.md)
- Design note: [Having a snapshot is not the same as being able to recover](../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md)
- Design note: [A backup copy holds no file system until it is restored](../../ja/domains/data-protection/notes/backup-copies-across-regions-and-accounts.md) (日本語)

---

### Monitoring and log aggregation

**This problem already has a dedicated module. It is not duplicated here.**

| Option | Form | Where it is covered |
|---|---|---|
| Datadog / Splunk / Elastic and others | SaaS | [Domain — Observability, route 3](../domains/observability/README.md) |

**Choosing the SaaS route brings seven questions about where the data sits.** Granularity can be added later; data that has left cannot be made not to have left.

- Decision tree: [Choosing a monitoring route](../../ja/reference/decision-trees/observability-route.md) (日本語)
- Comparison: [Monitoring routes compared](../../ja/reference/comparison/observability-routes.md) (日本語)
- Design note: [The route is narrowed first by access and authentication](../../ja/domains/observability/notes/route-choice-is-bounded-by-access-and-auth.md) (日本語)

---

### File transfer and data integration

**No option meets the inclusion criteria.** The detail is in [Candidates that did not meet the bar](#candidates-that-did-not-meet-the-bar).

**AWS-native options do exist.** AWS Storage Blog records an SFTP sharing configuration combining AWS Transfer Family with FSx for ONTAP and S3 Access Points ([source](https://aws.amazon.com/blogs/storage/secure-sftp-file-sharing-with-aws-transfer-family-amazon-fsx-for-netapp-ontap-and-s3-access-points/)).

---

### VMware workload migration and protection

| Option | Form | Source |
|---|---|---|
| VMware HCX (migration) | Software | [NetApp: Migrate workloads to an FSx for ONTAP datastore using VMware HCX](https://docs.netapp.com/us-en/netapp-solutions-cloud/vmware/vmw-aws-vmc-migrate-hcx.html) |
| Veeam Backup & Replication (protecting VMs on an NFS datastore) | Software | [NetApp: Veeam backup and restore in VMware Cloud with FSx for ONTAP](https://docs.netapp.com/us-en/netapp-solutions-cloud/vmware/vmw-aws-vmc-backup-restore-veeam.html) |

**There is no design note.** The VMware side is outside this repository's scope, and the implementation lives in the **sibling repository** [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP).

---

## Candidates that did not meet the bar

**Being here does not mean "not supported".** It records our own search state: no statement naming FSx for ONTAP was reached.

| Candidate | Problem | What was confirmed | What was not reached |
|---|---|---|---|
| NEC CLUSTERPRO X | Removing a single point of failure in an application | AWS HA cluster deployment guides (Linux and Windows, several versions) and a verified-software list are published. There is also an article on making HULFT redundant on AWS | **A statement naming FSx for ONTAP.** Not found anywhere in the material above |
| HULFT | File transfer and data integration | That HULFT10 for Container Services supports Amazon ECS, AWS Fargate and Amazon S3. That vendor engineers have published several articles on AWS integration | **Material recording a combination with FSx for ONTAP.** Zero results |

**These two rows are kept rather than dropped** because they are the products a reader in Japan will think of for these problems. **Without a row, a reader cannot tell "not investigated" from "not supported".**

**The vendors were not asked.** The table above is search results from public material only.

---

## Verification planned

**For HULFT there is no public material, so the plan is to measure it here.** It is not listed in the table above even as a `hypothesis` (**mixing untested reasoning into the index would empty the inclusion criteria of meaning**).

| # | What will be measured | Why this |
|---|---|---|
| 1 | Whether transfer to and from an FSx for ONTAP NFS volume succeeds, and whether the result is intact | The smallest question of whether the combination holds at all |
| 2 | How a transfer behaves during a file system failover (continues / retries / fails) | **The interaction between a managed failover and file-transfer middleware.** No public material covers it, and it bears on a design decision |

**Throughput will not be measured.** The figure would be governed by the client instance type and placement rather than by the product. The same reasoning is in [Reading a published benchmark](../../ja/domains/block-storage/notes/when-shared-block-changes-the-design.md#公開ベンチマークの読み方) (日本語).

**The verification environment will be deleted within 24 hours.** No irreversible retention setting (SnapLock, snapshot locking) will be used.

---

## How to choose

**Not "which is better", but what is already settled.**

| What you have | How to use the index |
|---|---|
| The problem is settled, the product is not | **Start from the rows where the design-note column says yes.** What gets settled before the product is written down there |
| A product is already in place and you want to combine it | Read the sources on that product's row. **If there is no row, check [Candidates that did not meet the bar](#candidates-that-did-not-meet-the-bar)** |
| You want to judge whether AWS-native features are enough | Read each section's "AWS-native options" first. **Adding no product is the lightest to operate** |
| You want products compared side by side | **This index is not a comparison matrix.** Options for one problem differ in form and in where responsibility sits, so the symmetric trade-offs are in each design note |

**Some premises apply to every row.**

| Premise | Detail |
|---|---|
| **The date on the source** | Support status changes. **This table was searched on 2026-09-15** (a row with its own date carries it). Confirm the current state at selection time |
| **The version combination** | A statement of support means a specific combination of versions. The vendor's interoperability information is where to confirm it |
| **The support boundary** | The AWS support scope and the vendor support scope are separate. **Settle in the contract which side owns triage for the combined configuration** |

---

## Out of scope for this repository

| Not covered | Why |
|---|---|
| Product installation procedures | They live in the primary source and change with the version. **The same procedure in two places means one of them stops being updated** |
| Procedures that go through a vendor-specific management tool | This repository writes against native mechanisms (ONTAP REST API, SnapMirror, FabricPool, Amazon CloudWatch). **What cannot be restated that way is left to the primary source** |
| Product pricing and licence terms | They vary by contract |
| Which product is better | It depends on the use and the premises. **This index shows where the options are and what gets settled before choosing** |
| The internals of a VMware, EDR or backup product | Outside the subject |

---

## Related documents

- [Reference](../../ja/reference/README.md) — the cross-cutting reference hub
- [Industry resource map](../../ja/reference/industry-resource-map.md) (日本語) — reading order when entering from an industry, plus the case-study index
- [Cross-repository citation index](../../ja/reference/cross-repo-index.md) (日本語) — where implementations belong
- [The antivirus choice is settled before the vendor](../domains/security-governance/notes/vscan-scope-is-bounded-before-the-vendor.md) — an example of a problem with a design note
- [Choosing a migration method](../../ja/reference/decision-trees/migration-method.md) (日本語) — the method that is settled before the product
- [Evidence Policy](../evidence-policy.md) — how the inclusion criteria relate to the `evidence` tiers

---

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/reference/isv-solution-map.md) | [English](isv-solution-map.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
