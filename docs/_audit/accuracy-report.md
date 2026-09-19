# Current accuracy audit inventory

This is an English, nonlocalized current-state report for Amazon FSx for NetApp ONTAP documentation. It records audit targets, completed claim audits, and missing evidence metadata. It does not replace the linked primary sources.

## Priority accuracy areas

| Priority area | Status | Current scope |
|---|---|---|
| Inode defaults | AUDITED | AWS documents one inode per 32 KiB through 648 GiB and a cap of 21,251,126. A contrary 2026-08-06 observation is retained beside every summary. |
| Deployment-type immutability | AUDITED | AWS explicitly states that deployment type cannot change after creation and directs migration to a new file system. |
| HA-pair scale limits | AUDITED WITH OPEN TRANSITION | Second-generation Single-AZ supports up to 12 HA pairs; block protocols are supported only with 6 or fewer; each FlexVol has one aggregate entry belonging to one HA pair. |
| Maintenance deferral windows | AUDITED | Patching is typically once every several weeks. The 14-day condition applies only after a patch release when no maintenance window occurs in that period. |
| Encryption defaults | AUDITED WITH OPEN SOURCE DIFFERENCES | At-rest encryption is automatic, while KMS key selection remains a creation-time choice. In-transit behavior is recorded separately for Nitro, SMB, NFS Kerberos, and IPsec. |
| FSx for ONTAP S3 Access Points prerequisites and authorization | AUDITED WITH OPEN AD DATA-PATH CLAIM | Creation ownership is separate from cross-account use; endpoint choice depends on `NetworkOrigin`, caller location, and whether the design requires a private path; the controlled in-VPC gateway-endpoint measurement is retained. |
| Amazon CloudWatch percentile availability | AUDITED | The p99 limitation is scoped to volume read/write/metadata operation-time/count pairs whose valid statistic is `Sum`; other metrics retain their documented statistics and dimensions. |
| Billing components | AUDITED WITH OPEN TRANSFER CLAIMS | Charge dimensions now follow the current pricing and billing pages without fixed component counts or price quotes. Native `CopyBackup` transfer billing and the AWS Backup cross-account transfer payer remain open. |

All eight areas above were audited against the full current primary pages.

## Capacity and scaling audit

| Area | Primary sources read in full | Files examined | Corrections and remaining scope |
|---|---|---|---|
| Inode defaults | [Volume storage capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html) | `README.md`; `docs/en/README.md`; JA/EN Assess module READMEs and inode notes; JA/EN IaC-boundary notes; inventory checklist and comparison; limits; case study; `llms.txt`; `CHANGELOG.md` | Eight short summaries now distinguish the documented 648 GiB cap from the contrary 2026-08-06 observation. The detailed note, limits ledger, and case study already preserved both. |
| Deployment type | [Creating file systems](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/creating-file-systems.html); [Availability, durability, and deployment options](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/high-availability-AZ.html) | JA/EN design notes and module READMEs; decision and comparison references; data-protection and security notes; limits; examples; `CHANGELOG.md` | Universal immutability now rests on AWS's explicit statement, not on the absence of an update CLI parameter. |
| HA-pair scale and block scope | [Adding HA pairs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/adding-HA-pairs.html); [Managing HA pairs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/HA-pairs.html); [Accessing your data](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-fsx-clients.html); [Creating an iSCSI LUN](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-iscsi-lun.html); [Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) | JA/EN design and performance notes; block notes, quickstarts, checklist, resource map, decision tree, comparison; block example; backup note; `CHANGELOG.md` | The general 12-pair file-system ceiling, the 6-pair block-protocol support scope, and one-aggregate FlexVol placement are now separate claims. |
| FlexVol placement | [AggregateConfiguration](https://docs.aws.amazon.com/fsx/latest/APIReference/API_AggregateConfiguration.html); [Creating volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/creating-volumes.html) | JA/EN performance and CloudWatch notes; README summaries; backup note; `CHANGELOG.md` | Source links now point to the API statement that FlexVol always has one aggregate entry and each HA pair has one aggregate. |

**Unresolved claim:** the primary pages state only that iSCSI is available on file systems with 6 or fewer HA pairs and NVMe/TCP on second-generation file systems with 6 or fewer. They do not state what happens to existing LUNs, namespaces, or connections while a seventh pair is added or after it completes. The documentation therefore supports a configuration boundary, not a transition-behavior claim.

## Maintenance and encryption audit

| Area | Primary sources read in full | Files examined | Corrections and remaining scope |
|---|---|---|---|
| Maintenance deferral | [Maintenance windows](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/maintenance-windows.html) | Root and English hubs; JA/EN Operate module READMEs; maintenance note; JA/EN AD-lifecycle notes; limits and industry references; `llms.txt`; `CHANGELOG.md` | Removed wording that turned the 14-day post-patch condition into a maintenance frequency. The title, navigation, summaries, Mermaid labels, limits text, and source ledger now retain both conditions: a patch has been released, and no maintenance window occurs within 14 days. |
| At-rest encryption and KMS selection | [Data protection](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/data-protection.html); [Encryption at rest](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-at-rest.html); [Creating file systems](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/creating-file-systems.html); [AWS::FSx::FileSystem](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-fsx-filesystem.html) | All eight Tier 1 READMEs; JA/EN security and IaC module material; glossary and comparison references; three CloudFormation examples and their READMEs; `llms.txt`; `CHANGELOG.md` | Separated automatic at-rest encryption from the creation-time KMS key choice. The examples intentionally omit `KmsKeyId`; comments now state that this selects the Amazon FSx-managed key and that changing the property replaces the file system. |
| In-transit encryption | [Encryption in transit](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-in-transit.html); [Enable SMB encryption](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/enable-smb-encryption.html); [Document History](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/document-history.html); [What is FSx for ONTAP?](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/what-is-fsx-ontap.html) | All title and navigation followers; JA security note; JA/EN AD-lifecycle and IaC notes; recent updates; glossary and file-storage comparison; `llms.txt`; `CHANGELOG.md` | Removed the shared "off by default" claim. Nitro automatic application, SMB creation default, NFS Kerberos prerequisites, and IPsec configuration are now stated separately. The recent-updates entry now limits all-Region availability to second-generation file systems and retains the first-generation Region and creation-date constraints. |

**Unresolved source differences:** the data-protection page says Kerberos-based encryption over NFS and SMB is available when the SVM joins Active Directory or a domain using LDAP. The detailed in-transit page describes NFS Kerberos for child volumes of SVMs joined to Microsoft Active Directory, and its automatic-Nitro overview names Linux and Windows while its client-factor section also names Mac. The report does not infer a protocol-wide LDAP scope or one common Nitro client list from those differences.

## S3 Access Points and CloudWatch audit

| Area | Primary sources read in full | Files examined | Corrections and remaining scope |
|---|---|---|---|
| S3 Access Points restrictions, creation, identity and authorization | [Access point restrictions and limitations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-points-restrictions-limitations-naming-rules.html); [Creating access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-access-points.html); [Managing access point access](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html); [OntapFileSystemIdentity](https://docs.aws.amazon.com/fsx/latest/APIReference/API_OntapFileSystemIdentity.html); [Policy evaluation logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html) | Root and English hubs; JA prerequisite, client-access, design and workshop notes; JA/EN authorization notes; authorization and client-route decision trees; agent domain knowledge; examples; `llms.txt`; `CHANGELOG.md` | Same-account ownership is now limited to creation. Cross-account data use requires an allow on both policy sides. No example change was needed. |
| S3 Access Points network, troubleshooting and references | [Configuring network access](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html); [Troubleshooting S3 access point issues](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/troubleshooting-access-points-for-fsxn.html); [Referencing access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/referencing-access-points-for-fsxn.html); [Monitoring and logging Access Points](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-points-monitoring-logging.html) | The same reader surfaces plus `examples/client-access/` | Endpoint requirements now account for `NetworkOrigin`, caller location, and whether a private path is required. The controlled 2026-08-17/18 `ap-northeast-1` in-VPC measurement remains evidence that an Internet-origin access point can use an S3 gateway endpoint when the subnet route table selects it. CloudTrail can record requests through Access Points when S3 data-event logging is configured. |
| Volume operation latency and other CloudWatch metric families | [Volume metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-metrics.html); [File system metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-system-metrics.html); [Second-generation file system metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/so-file-system-metrics.html) | Root and English hubs; JA/EN performance notes and module hubs; JA observability hub and route note; block-monitoring note; assess and observability checklists; industry and comparison references; `llms.txt`; `CHANGELOG.md` | The p99 limitation now names all three Sum-only volume operation-time/count pairs. It no longer generalizes to all CloudWatch metrics or makes client instrumentation the only telemetry path. `Maximum` is a supported monitoring choice, with per-dimension series retained. Access Point request-level fields are separated from aggregate storage telemetry. |

**Unresolved claims:** current public pages state that the Windows file-system identity must resolve in the joined Active Directory domain and that an unreachable name service can place an access point in `MISCONFIGURED`. They do not establish that every S3 data operation on every AD-joined SVM requires live domain-controller reachability, or that `HeadBucket` succeeds specifically while that dependency is unavailable. The tracked carry-over lacks a complete reader-facing environment, procedure, result and control, so both runtime claims remain `open` and are not attributed to private correspondence. [Amazon S3 documents](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-points-monitoring-logging.html) that CloudTrail records requests through Access Points when S3 data-event logging is configured, including an `AWS::FSx::Volume` resource for Access Points attached to Amazon FSx volumes.

## Billing audit

| Area | Primary sources read in full | Files examined | Corrections and remaining scope |
|---|---|---|---|
| FSx for ONTAP charge dimensions | [Pricing](https://aws.amazon.com/fsx/netapp-ontap/pricing/); [What is FSx for ONTAP?](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/what-is-fsx-ontap.html); [AWS billing and usage reports](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/FSxONTAP-Billing.html); [Sizing blog](https://aws.amazon.com/blogs/storage/how-to-size-an-amazon-fsx-for-netapp-ontap-file-system/) | JA/EN provisioned-versus-consumed notes; root and English hubs; JA/EN Cost module hubs; JA/EN tiering notes; cost decision trees and comparisons; data-protection comparison; block-storage comparisons and shared-block note; backup-copy note; `CHANGELOG.md` | Removed conflicting fixed component counts. Capacity-pool request charges now name capacity-pool reads and writes. SnapLock usage is GB-month storage used by SnapLock volumes. S3 charges are limited to access through attached FSx for ONTAP S3 Access Points. No price quote was added or changed. |
| Backup storage and recovery points | [FSx for ONTAP pricing](https://aws.amazon.com/fsx/netapp-ontap/pricing/); [AWS Backup metering and billing](https://docs.aws.amazon.com/aws-backup/latest/devguide/metering-and-billing.html); [AWS Backup pricing](https://aws.amazon.com/backup/pricing/) | JA/EN provisioned-versus-consumed notes; data-protection comparison; backup-copy note; block-storage cost comparison | Incremental backup wording now describes changed blocks and retained recovery points rather than claiming that incremental storage prevents duplicate billing. |
| Transfer scope and payer | [FSx for ONTAP pricing](https://aws.amazon.com/fsx/netapp-ontap/pricing/); [AWS Backup metering and billing](https://docs.aws.amazon.com/aws-backup/latest/devguide/metering-and-billing.html); [AWS Backup pricing](https://aws.amazon.com/backup/pricing/); [EBS snapshot-copy transfer blog](https://aws.amazon.com/blogs/storage/effectively-track-aws-data-transfer-costs-for-cross-region-amazon-ebs-snapshot-copy/) | JA/EN provisioned-versus-consumed notes; backup-copy note; related `CHANGELOG.md` entries | Included Multi-AZ transfer is limited to service replication between Availability Zones, not client traffic, backup copies, or SnapMirror. The EBS blog establishes EBS transfer billing only. Native `CopyBackup` cross-Region transfer billing remains open. AWS Backup's guide assigns non-fully-managed resource transfer to the destination account, while its pricing page assigns transfer to the sending account; payer ownership remains open. |
| Fee wording and configuration floor | [FSx for ONTAP pricing](https://aws.amazon.com/fsx/netapp-ontap/pricing/) | JA/EN provisioned-versus-consumed notes; block-storage cost comparison and quickstarts | No service setup or minimum fee is separate from the minimum provisionable SSD and throughput configuration of a created file system. Existing dated estimates were not repriced. |

## Missing verified metadata

Reproduce this inventory from the repository root:

```bash
make frontmatter-report
```

The current worktree report lists 15 verified documents with future metadata gaps. A prior working inventory stated a total of 22, but only 19 documents had individually established values; the total of 22 was internally inconsistent. Those 19 established documents were filled. No review-round metadata is recorded here. The remaining entries are reported as absent or ambiguous without inferring values.

### Absent `deployment_type` metadata

#### English documents

- `docs/en/domains/multiprotocol-identity/notes/local-user-inventory-without-last-logon.md`
- `docs/en/domains/multiprotocol-identity/notes/smb-service-lost-on-cifs-server-delete.md`
- `docs/en/domains/security-governance/notes/access-point-authorization-layers.md`
- `docs/en/domains/security-governance/notes/audit-log-space-and-client-access.md`
- `docs/en/domains/security-governance/notes/smb-logon-audit-event-coverage.md`

#### Japanese documents

- `docs/ja/domains/multiprotocol-identity/notes/local-user-inventory-without-last-logon.md`
- `docs/ja/domains/multiprotocol-identity/notes/smb-service-lost-on-cifs-server-delete.md`
- `docs/ja/domains/security-governance/notes/access-point-authorization-layers.md`
- `docs/ja/domains/security-governance/notes/audit-log-space-and-client-access.md`
- `docs/ja/domains/security-governance/notes/smb-logon-audit-event-coverage.md`
- `docs/ja/playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md`
- `docs/ja/playbooks/05-operate/notes/admin-account-lockout-and-recovery.md`
- `docs/ja/reference/comparison/ontap-configuration-routes.md`

### Ambiguous `ontap_version` and `deployment_type` metadata

- `docs/ja/workshop-studio/eda-s3-access-points-90min/facilitation-risks.md`
- `docs/ja/workshop-studio/eda-s3-access-points-90min/measured-timings.md`

The report establishes absence for 13 documents and ambiguity for 2 documents. It does not establish the missing values.
