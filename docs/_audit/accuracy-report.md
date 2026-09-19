# Current accuracy audit inventory

This is an English, nonlocalized current-state report for Amazon FSx for NetApp ONTAP documentation. It records audit targets and missing evidence metadata; it does not verify, correct, or extend any source claim.

## Priority accuracy areas

| Priority area | Status | Current scope |
|---|---|---|
| Inode defaults | NOT YET AUDITED | Locate each default-value claim, then compare it with a public primary source and its stated applicability. |
| Deployment-type immutability | NOT YET AUDITED | Locate each immutability claim, then check scope, lifecycle boundary, and public primary source. |
| HA-pair scale limits | NOT YET AUDITED | Locate each scale-limit claim, then check deployment type, region or version scope, and public primary source. |
| Maintenance deferral windows | NOT YET AUDITED | Locate each timing claim, then check the documented window, conditions, and public primary source. |
| Encryption defaults | NOT YET AUDITED | Locate each at-rest and in-transit default claim, then check protocol and configuration scope against public primary sources. |
| FSx for ONTAP S3 Access Points prerequisites and authorization | NOT YET AUDITED | Locate each prerequisite and authorization claim, then check every policy and infrastructure layer against public primary sources. |
| Amazon CloudWatch percentile availability | NOT YET AUDITED | Locate each percentile claim, then check metric type, statistic support, and public primary source. |
| Billing components | NOT YET AUDITED | Locate each billing-component claim, then check the named charge dimensions and public primary source without producing a cost estimate. |

No area above has been reviewed claim by claim for this report. There are therefore no entries classified as audited and unresolved.

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

A complete claim-by-claim audit is pending. Later work must inspect each claim in context, record its file and line, compare it with an existing public primary source, and classify the result without treating this inventory as evidence. Numeric values, defaults, service behavior, timing, limits, availability, and billing statements remain in scope for that audit.
