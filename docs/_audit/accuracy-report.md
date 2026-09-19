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
| FSx for ONTAP S3 Access Points prerequisites and authorization | NOT YET AUDITED | Locate each prerequisite and authorization claim, then check every policy and infrastructure layer against public primary sources. |
| Amazon CloudWatch percentile availability | NOT YET AUDITED | Locate each percentile claim, then check metric type, statistic support, and public primary source. |
| Billing components | NOT YET AUDITED | Locate each billing-component claim, then check the named charge dimensions and public primary source without producing a cost estimate. |

The first five areas above were audited against the full current primary pages. The remaining three areas have not yet been reviewed claim by claim for this report.

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

## Missing verified metadata

Reproduce this inventory from the repository root:

```bash
make frontmatter-report
```

The current report lists 34 verified documents with future metadata gaps. Thirty-two documents are missing `deployment_type`; two documents are missing both `ontap_version` and `deployment_type`. These entries identify absent metadata only. They do not establish which value applies.

### Missing `deployment_type`

#### English documents

- `docs/en/domains/block-storage/quickstart.md`
- `docs/en/domains/multiprotocol-identity/notes/local-user-inventory-without-last-logon.md`
- `docs/en/domains/multiprotocol-identity/notes/nfs-side-view-does-not-explain-ntfs-denials.md`
- `docs/en/domains/multiprotocol-identity/notes/smb-service-lost-on-cifs-server-delete.md`
- `docs/en/domains/security-governance/notes/access-point-authorization-layers.md`
- `docs/en/domains/security-governance/notes/audit-log-space-and-client-access.md`
- `docs/en/domains/security-governance/notes/smb-logon-audit-event-coverage.md`

#### Japanese documents

- `docs/ja/domains/block-storage/checklists/iscsi-cutover.md`
- `docs/ja/domains/block-storage/notes/a-database-on-luns-recovers-without-quiescing.md`
- `docs/ja/domains/block-storage/notes/block-objects-are-outside-the-aws-api.md`
- `docs/ja/domains/block-storage/notes/capacity-is-counted-in-three-places.md`
- `docs/ja/domains/block-storage/notes/igroups-are-not-the-only-access-control.md`
- `docs/ja/domains/block-storage/notes/lun-layout-decides-recovery-granularity.md`
- `docs/ja/domains/block-storage/notes/multi-az-moves-a-route-not-an-address.md`
- `docs/ja/domains/block-storage/notes/nvme-tcp-is-thin-on-the-aws-side.md`
- `docs/ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md`
- `docs/ja/domains/block-storage/notes/protocol-choice-is-bounded-before-you-choose.md`
- `docs/ja/domains/block-storage/notes/volume-rehost-changes-ownership-not-contents.md`
- `docs/ja/domains/block-storage/notes/what-block-monitoring-shows.md`
- `docs/ja/domains/block-storage/quickstart.md`
- `docs/ja/domains/data-protection/notes/backup-copies-across-regions-and-accounts.md`
- `docs/ja/domains/multiprotocol-identity/notes/local-user-inventory-without-last-logon.md`
- `docs/ja/domains/multiprotocol-identity/notes/nfs-side-view-does-not-explain-ntfs-denials.md`
- `docs/ja/domains/multiprotocol-identity/notes/smb-service-lost-on-cifs-server-delete.md`
- `docs/ja/domains/security-governance/notes/access-point-authorization-layers.md`
- `docs/ja/domains/security-governance/notes/audit-log-space-and-client-access.md`
- `docs/ja/domains/security-governance/notes/irreversible-operations-need-separate-approval.md`
- `docs/ja/domains/security-governance/notes/smb-logon-audit-event-coverage.md`
- `docs/ja/playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md`
- `docs/ja/playbooks/05-operate/notes/admin-account-lockout-and-recovery.md`
- `docs/ja/reference/comparison/ontap-configuration-routes.md`
- `docs/ja/reference/decision-trees/where-a-setting-is-created.md`

### Missing `ontap_version` and `deployment_type`

- `docs/ja/workshop-studio/eda-s3-access-points-90min/facilitation-risks.md`
- `docs/ja/workshop-studio/eda-s3-access-points-90min/measured-timings.md`

## Pending audit scope

The remaining three priority areas require a complete claim-by-claim audit. Later work must inspect each claim in context, record its file and line, compare it with an existing public primary source, and classify the result without treating this inventory as evidence. Numeric values, defaults, service behavior, timing, limits, availability, and billing statements in those three areas remain in scope.
