---
title: Open items for GCP and Amazon FSx for NetApp ONTAP peering and replication
lifecycle: [design, migrate, build]
domains: [data-protection, security-governance]
evidence: documented
source: https://cloud.google.com/netapp/volumes/docs/protect-data/replicate-ontap/overview
lang: en
---

# Open items for GCP and Amazon FSx for NetApp ONTAP peering and replication

[🏠 Repository home](../../en/README.md) | [Reference](../../ja/reference/README.md)

## Conclusion

This document records the items that are not yet established as a public procedure for cluster peering, SVM peering, SnapMirror, Break, and Reverse Resync between Google Cloud NetApp Volumes and Amazon FSx for NetApp ONTAP. The operations below must not be treated as runnable commands until the primary provider interface and evidence are available.

## Get started

| Phase | Purpose | Primary actor | Required evidence | Stop condition |
|---|---|---|---|---|
| 1 | Confirm direction and targets | GCP / AWS operators | Source/destination ledger | Stop when direction differs |
| 2 | Establish provider interface | GCP / AWS operators | Official API/CLI specification | Mark open if interface is unknown |
| 3 | Verify peering bilaterally | GCP / AWS operators | Fresh reads from both sides | Stop on one-sided state |
| 4 | Verify replication state | Storage operators | Source/destination/role/state | Stop on contradictory state |
| 5 | Validate sample data | GCP Linux operator | Private run record | Keep open if evidence is incomplete |

Durations are planning guidance, not measured provider timings or production estimates.

## Target topology

| Role | Provider | Resource | Direction | Status |
|---|---|---|---|---|
| Cluster source | FSx for ONTAP or GCNV | `<source-cluster>` | source | Must be resolved in the ledger |
| SVM source | FSx for ONTAP or GCNV | `<source-svm>` | source | Must be resolved in the ledger |
| SnapMirror source volume | FSx for ONTAP | `<snapmirror-source-volume>` | FSx for ONTAP to GCNV | Candidate role |
| GCNV destination volume | GCNV | `<gcnv-destination-volume>` | destination | Provider API check required |
| Reverse destination | FSx for ONTAP | `<reverse-destination-volume>` | GCNV to FSx for ONTAP | DP/read-only check required |
| FlexCache origin | `<provider>` | `<origin-svm>:<origin-volume>` | origin | Topology unresolved, open |

Do not fill these values by guessing from existing resource names. Confirm them with the run ledger and provider read-only responses.

## Cluster peering

> **Status: open**
>
> The public procedure has not established the GCNV initiation interface, the FSx for ONTAP acceptance interface, the generated ONTAP command, passphrase handoff, or expiry predicate. Resolution requires the current Google Cloud NetApp Volumes API/CLI contract, FSx for ONTAP ONTAP CLI/REST documentation, and an actual response record.

Required resolution inputs:

- Full GCNV replication resource name.
- API method, request body, and asynchronous operation completion predicate.
- Hybrid peering response fields.
- Exact generated command syntax and passphrase prompt.
- FSx for ONTAP actor, target selector, pre-state, and post-state.
- Bilateral checks for peer identity, intercluster addresses, availability, and authentication.

The following is a **non-runnable input inventory**, not a command:

```text
GCNV replication resource: <resource-name>
GCNV method: <documented-method>
FSx for ONTAP acceptance interface: <documented-cli-or-rest-interface>
Peer cluster identity: <peer-cluster>
Peer intercluster addresses: <peer-addresses>
Passphrase handoff: <approved-private-channel>
Expiry predicate: <documented-expiry-field-and-condition>
```

## SVM peering

> **Status: open**
>
> The official interface for accepting a GCNV-initiated SVM peer request on FSx for ONTAP, exact SVM selectors, application list, and bilateral post-state are not established in this public procedure.

Do not accept a one-sided `peered` result. Both sides must read and record the following under one run ID:

- local SVM identity
- peer SVM identity
- peer cluster identity
- applications such as SnapMirror or FlexCache
- peering state
- dedicated-role and ownership match

Stop before replication when either read is unavailable, identities differ, or requested applications are missing.

## SnapMirror and Reverse Resync

> **Status: open**
>
> The control-plane ownership for FSx for ONTAP to GCNV create/initialize, GCNV stop/break, and GCNV to FSx for ONTAP Reverse Resync has not been established as a public, executable contract. This document therefore does not publish an unverified `snapmirror resync` or equivalent command as an execution step.

Minimum state mapping to resolve:

| Phase | Source | Destination | Required check |
|---|---|---|---|
| initialized | `<source-system>:<source-volume>` | `<destination-system>:<destination-volume>` | source/destination, role, mirror state, relationship status, health |
| synchronized | same | same | Actual ONTAP output mapped to predicates such as `Snapmirrored` and `Idle` |
| broken | GCNV destination | GCNV destination | Post-break write-enabled/read-only and provider state |
| reverse resync | GCNV | FSx for ONTAP | Authoritative operation, direction, post-state, and content evidence |
| final | Ledger identities | Ledger identities | Relationship state and file content must pass separately |

Names such as `healthy`, `transfer-state`, and `mirrorState` may be used only after mapping them to actual provider response fields. Do not accept a healthy result from another relationship as evidence for the target.

## Handling the 48-file result

> **Status: open**
>
> The conversation contains an observation of 48 files, 48/48 SHA-256 matches, zero failures, zero missing files, and DP read-only behavior. A retained record containing its run ID, environment, date, fixture method, and original manifest is not available to this public document. The result is therefore not promoted to `verified` here.

The following fields are required before promotion:

- `sample_run_id`
- GCP client, region, protocol, and NFS source/export
- AWS file system, SVM, volume, and region
- measurement date
- total files = 48
- successful hashes = 48
- failed = 0
- missing = 0
- extra = 0
- DP/read-only result
- original manifest or reproducible fixture specification

## Cleanup boundary

This document does not execute deletion of peerings, replication relationships, volumes, SVMs, VPNs, Cloud Routers, VGWs, routes, or security rules. Cleanup requires:

1. A fresh read of owner and exact resource identity from the run ledger.
2. Leave shared and pre-existing resources in place.
3. Stop when active transfer, dependencies, or peer relationships remain.
4. Obtain separate confirmation immediately before each destructive operation.
5. Record the provider inverse operation and post-state.

## Related documents

- [GCP / FSx for ONTAP preflight and sample validation](gcp-to-fsx-ontap-preflight-and-sample-validation.md)
- [Evidence policy](../evidence-policy.md)
- [Localization workflow](../../agent/localization.md)
- [Data protection](../domains/data-protection/)
- [FSx for ONTAP S3 Access Points constraints](../../ja/domains/data-utilization/notes/s3-access-point-constraints.md) (日本語)
- [Google Cloud: external replication overview](https://cloud.google.com/netapp/volumes/docs/protect-data/replicate-ontap/overview)
- [Google Cloud: ONTAP communication prerequisites](https://cloud.google.com/netapp/volumes/docs/migrate/ontap/prerequisites-ontap-netapp-volumes)

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/reference/gcp-to-fsx-ontap-peering-and-replication-open-items.md) | [English](gcp-to-fsx-ontap-peering-and-replication-open-items.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
