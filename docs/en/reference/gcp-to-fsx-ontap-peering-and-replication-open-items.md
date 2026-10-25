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
| FlexCache origin volume | `<provider>` | `<origin-svm>:<origin-volume>` | origin | Topology unresolved, open |
| FlexCache cache volume | `<provider>` | `<cache-svm>:<cache-volume>` | cache | Provider interface unresolved, open |

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

### Verified read-only state

> **Evidence: verified** (2026-09-28, `ap-northeast-1`, ONTAP 9.18.1P6)
>
> The target SVM was `running`. The SVM peer was `peered` with `snapmirror, flexcache` applications. The corresponding cluster peer was `Unavailable`. An existing SnapMirror relationship reported `Snapmirrored`, `Idle`, and `Healthy true`.

This confirms that an SVM peer and a SnapMirror relationship exist. The `Unavailable` cluster-peer state means that this read-only check does not establish end-to-end replication or Reverse Resync readiness. Do not create a new relationship, break, resync, or create a FlexCache relationship based on this observation.

## FlexCache

> **Status: open**
>
> In this conversation, a separate FlexCache-origin volume was prepared on FSx for ONTAP and the SVM-peering application list included `flexcache`. The GCNV cache-volume creation interface, cache owner, exact origin/cache resource identities, post-create cache state, and read/write mode were not established. The conversation also did not verify that GCNV created the cache volume or that the FlexCache state was healthy.

Resolve this ledger before creating a FlexCache relationship.

| Item | Required value |
|---|---|
| Origin provider / cluster / SVM / volume | `<origin-provider>` / `<origin-cluster>` / `<origin-svm>` / `<origin-volume>` |
| Cache provider / cluster / SVM / volume | `<cache-provider>` / `<cache-cluster>` / `<cache-svm>` / `<cache-volume>` |
| Origin/cache direction | `<origin-to-cache-direction>` |
| Volume type and security style | `<origin-volume-type>` / `<cache-volume-type>` / `<security-style>` |
| Client protocol | `<nfs-or-smb>` |
| Creation interface | `<documented-gcnv-or-ontap-interface>` |
| Post-state query | `<documented-cache-state-query>` |

After creation, verify origin and cache identity, cache state, SVM peer state, and content reads as separate results. Do not create, modify, or delete a cache when the ledger lacks the creator, target resource, current state, dependencies, or inverse operation. FlexCache is not the S3 Access Point path; validate the NFS/SMB path to the cache volume separately.

### Direction-specific FlexCache diagrams

- [FlexCache: FSx for ONTAP origin to GCNV cache](../../_assets/images/gcp-fsx-ontap-flexcache-fsx-origin-to-gcnv-cache-en.svg) ([dark theme](../../_assets/images/gcp-fsx-ontap-flexcache-fsx-origin-to-gcnv-cache-en-dark.svg))
- [FlexCache: GCNV origin to FSx for ONTAP cache](../../_assets/images/gcp-fsx-ontap-flexcache-gcnv-origin-to-fsx-cache-en.svg) ([dark theme](../../_assets/images/gcp-fsx-ontap-flexcache-gcnv-origin-to-fsx-cache-en-dark.svg))

The Open label means that the cache-creation interface and post-create state have not been verified. Including `flexcache` in the SVM peering applications is not evidence that cache creation succeeded.

## SnapMirror and Reverse Resync

> **Status: open**
>
> The control-plane ownership for FSx for ONTAP to GCNV create/initialize, GCNV stop/break, and GCNV to FSx for ONTAP Reverse Resync has not been established as a public, executable contract. This document therefore does not publish an unverified `snapmirror resync` or equivalent command as an execution step.

### Direction-specific SnapMirror diagrams

- [SnapMirror: FSx for ONTAP to GCNV](../../_assets/images/gcp-fsx-ontap-snapmirror-fsx-to-gcnv-en.svg) ([dark theme](../../_assets/images/gcp-fsx-ontap-snapmirror-fsx-to-gcnv-en-dark.svg))
- [Reverse Resync: GCNV to FSx for ONTAP](../../_assets/images/gcp-fsx-ontap-reverse-resync-gcnv-to-fsx-en.svg) ([dark theme](../../_assets/images/gcp-fsx-ontap-reverse-resync-gcnv-to-fsx-en-dark.svg))

The arrows show the data or relationship direction. Before execution, map the source, destination, operator, and post-state to the run ledger and fresh provider reads.

Minimum state mapping to resolve:

| Phase | Source | Destination | Required check |
|---|---|---|---|
| initialized | `<source-system>:<source-volume>` | `<destination-system>:<destination-volume>` | source/destination, role, mirror state, relationship status, health |
| synchronized | same | same | Actual ONTAP output mapped to predicates such as `Snapmirrored` and `Idle` |
| broken | GCNV destination | GCNV destination | Post-break write-enabled/read-only and provider state |
| reverse resync | GCNV | FSx for ONTAP | Authoritative operation, direction, post-state, and content evidence |
| final | Ledger identities | Ledger identities | Relationship state and file content must pass separately |

Names such as `healthy`, `transfer-state`, and `mirrorState` may be used only after mapping them to actual provider response fields. Do not accept a healthy result from another relationship as evidence for the target.

## Mutation approval procedure

This section is executed only after a separate approval and a passing read-only state check. These mutations were not run during this authoring session because the cluster peer was `Unavailable`.

### Create and initialize a SnapMirror relationship

Prerequisites are source and destination cluster and SVM peering, a `DP` destination volume, ledger-matched source and destination paths, an approved policy and schedule, an owner, a rollback, and a transfer window. NetApp's procedure also requires cluster and SVM peering before relationship creation and verification with `snapmirror show` ([Create an ONTAP SnapMirror replication relationship](https://docs.netapp.com/us-en/ontap/data-protection/create-replication-relationship-task.html)).

```text
# Run on the destination cluster. Replace values from the ledger.
snapmirror create \
  -source-path <source-svm>:<source-volume> \
  -destination-path <destination-svm>:<destination-volume> \
  -type XDP \
  -schedule <approved-schedule> \
  -policy <approved-policy>

snapmirror show -destination-path <destination-svm>:<destination-volume>

# Initialize only after the relationship and roles match the ledger.
snapmirror initialize \
  -source-path <source-svm>:<source-volume> \
  -destination-path <destination-svm>:<destination-volume>
```

Map predicates such as `Snapmirrored`, `Idle`, and `Healthy true` to the actual output for the target relationship. STOP when the cluster peer is `Unavailable`, an identity differs, the destination is not `DP`, or an active transfer exists.

### Stop, resume, and reverse external replication

Google Cloud NetApp Volumes external replication uses SnapMirror and supports create, stop, resume, reverse, and delete. When the external ONTAP side manages the relationship, the actual state must be checked with ONTAP `snapmirror show` ([External replication overview](https://docs.cloud.google.com/netapp/volumes/docs/protect-data/replicate-ontap/overview), [Manage your external replications](https://docs.cloud.google.com/netapp/volumes/docs/protect-data/replicate-ontap/manage-external-replication)).

```bash
set -euo pipefail
export GCP_PROJECT_ID="<gcp-project-id>"
export GCP_REGION="<gcp-region>"
export GCNV_VOLUME="<gcnv-volume>"
export REPLICATION_NAME="<replication-name>"

gcloud config set project "$GCP_PROJECT_ID"
gcloud netapp volumes replications list \
  --volume="$GCNV_VOLUME" --location="$GCP_REGION"
```

When `hybridReplicationUserCommands` is returned, save the ONTAP commands in the private ledger and execute those commands exactly. Do not infer or rewrite the source, destination, SVM, cluster, or direction from placeholders.

- **Stop**: request stop on the Google Cloud side. For an external ONTAP destination, verify `Snapmirrored` / `Idle` with `snapmirror show`, then run the returned `snapmirror break` command.
- **Resume**: request resume on the Google Cloud side, then run the returned `snapmirror resync` command only when its direction matches the new ledger state.
- **Reverse**: stop the replication first and start reverse on the Google Cloud side. When ONTAP becomes the new destination, run only the returned `snapmirror resync`, schedule, and modify commands.
- **Delete**: require stopped state, no outdated SnapMirror connection, and separate approval for cluster-peer cleanup when this is the last replication.

Do not run any of these operations while the current cluster peer is `Unavailable`.

### Create a FlexCache relationship

The AWS FlexCache procedure orders intercluster LIF and network checks, cluster peering, SVM peering, cache-volume creation, and `volume flexcache show`. For remote networks, confirm the route and intercluster TCP 11104 / 11105 first ([Creating a FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-flexcache.html)). The current NetApp procedure also uses cluster peering, SVM peering, `volume flexcache create`, and `volume flexcache show` ([Create ONTAP FlexCache volumes](https://docs.netapp.com/us-en/ontap/flexcache/create-volume-task.html)).

```text
# Run only after cluster peer is Available and intercluster LIFs are reachable.
cluster peer create -address-family ipv4 -peer-addrs <origin-intercluster-lif-1>,<origin-intercluster-lif-2>

# Run on the cache SVM side with the flexcache application.
vserver peer create \
  -vserver <cache-svm> \
  -peer-vserver <origin-svm> \
  -peer-cluster <origin-cluster> \
  -applications flexcache

# Accept on the origin side only after the provider actor and selector are established.
vserver peer accept \
  -vserver <origin-svm> \
  -peer-vserver <cache-svm> \
  -local-name <cache-local-name>

# Create on the cache SVM. Write-back requires a separate decision.
volume flexcache create \
  -vserver <cache-svm> \
  -volume <cache-volume> \
  -auto-provision-as flexgroup \
  -size <cache-size> \
  -origin-vserver <origin-svm> \
  -origin-volume <origin-volume>

volume flexcache show
```

STOP until `cluster peer show` reports `Available`, the SVM peer is `peered`, the application is `flexcache`, origin and cache identities match the ledger, security style is deliberate, and the inverse operation is recorded. The current cluster peer is `Unavailable`, so FlexCache creation remains Open.

### Rollback and destructive-operation boundary

Before deleting a relationship, confirm that no transfer is active, client access is stopped, the owner approved the operation, and the inverse operation and post-state are in the ledger. The published Reverse Resync procedure orders common-snapshot checks, direction changes, update, quiesce, break, delete, release, and re-sync of the original relationship ([Reactivate the original ONTAP source volume](https://docs.netapp.com/us-en/ontap/data-protection/reactivate-original-source-volume-task.html)).

- Do not run `snapmirror break`, `snapmirror delete`, or `snapmirror release` during an active transfer.
- Do not delete shared VPNs, routes, security groups, SVMs, volumes, or cluster peers unless the run created them and ownership is proven.
- Read the final state from both AWS and ONTAP after every approved mutation.

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
- [NetApp TR-4743: ONTAP FlexCache and FlexGroup technical reports](https://docs.netapp.com/us-en/ontap-technical-reports/nas-containers.html)
- [NetApp TR-4015: data protection and disaster recovery technical reports](https://docs.netapp.com/us-en/ontap-technical-reports/data-protection-disaster-recovery.html)
- [AWS Blog: scalable replication with FSx for ONTAP and SnapMirror](https://aws.amazon.com/blogs/storage/highly-scalable-solution-design-to-replicate-data-using-amazon-fsx-for-netapp-ontap-and-snapmirror/)

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/reference/gcp-to-fsx-ontap-peering-and-replication-open-items.md) | [English](gcp-to-fsx-ontap-peering-and-replication-open-items.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
