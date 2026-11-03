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
| 1 | Confirm direction and targets | GCP / AWS operators | Source/destination recorded values | Stop when direction differs |
| 2 | Establish provider interface | GCP / AWS operators | Official API/CLI specification | Mark open if interface is unknown |
| 3 | Verify peering bilaterally | GCP / AWS operators | Fresh reads from both sides | Stop on one-sided state |
| 4 | Verify replication state | Storage operators | Source/destination/role/state | Stop on contradictory state |
| 5 | Validate sample data | GCP Linux operator | Private run record | Keep open if evidence is incomplete |

Durations are planning guidance, not measured provider timings or production estimates.

## Target topology

| Role | Provider | Resource | Direction | Status |
|---|---|---|---|---|
| Cluster source | FSx for ONTAP or GCNV | `<source-cluster>` | source | Must be resolved in the private record |
| SVM source | FSx for ONTAP or GCNV | `<source-svm>` | source | Must be resolved in the private record |
| SnapMirror source volume | FSx for ONTAP | `<snapmirror-source-volume>` | FSx for ONTAP to GCNV | Candidate role |
| GCNV destination volume | GCNV | `<gcnv-destination-volume>` | destination | Provider API check required |
| Reverse destination | FSx for ONTAP | `<reverse-destination-volume>` | GCNV to FSx for ONTAP | DP/read-only check required |
| FlexCache origin volume | `<provider>` | `<origin-svm>:<origin-volume>` | origin | Resolve the direction and volume type in the private record. GCNV can be an origin only in ONTAP-mode |
| FlexCache cache volume | `<provider>` | `<cache-svm>:<cache-volume>` | cache | GCNV's creation interface is documented; resolve identity and owner in the private record |

Do not fill these values by guessing from existing resource names. Confirm them with the private record and provider read-only responses.

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

> **Status: open** (the interface is documented publicly; real-environment evidence is missing)
>
> GCNV's public documentation describes how to create a Cache (`--cache-parameters` of `gcloud beta netapp volumes create`), how to check it afterwards (`cacheParameters.cacheState` returned by `gcloud beta netapp volumes describe`), and what to do before deleting it (disable write-back first if it is enabled), as read on 2026-11-03 ([GCNV public interface](#gcnv-public-interface)). The private record's `Creation interface` and `Post-state query` can be filled from that source.
>
> No run record that this repository can cite exists. The S3-Burst-on-ONTAP-Files verification-status table agrees: it records whether GCNV can hold a Cache of an FSx for ONTAP origin as still unconfirmed (2026-09-20), as summarized in the [cross-cloud note](../../ja/domains/data-utilization/notes/cross-cloud-analytics-without-extra-copies.md#構成ごとの確認状況) (日本語). The record here covers only that a separate FlexCache-origin volume was prepared on FSx for ONTAP and that the SVM-peering application list included `flexcache`. The cache owner, exact origin/cache resource identities, read/write mode, and post-create cache state were not confirmed in a real environment.

Resolve the values in this table before creating a FlexCache relationship.

| Item | Required value |
|---|---|
| Origin provider / cluster / SVM / volume | `<origin-provider>` / `<origin-cluster>` / `<origin-svm>` / `<origin-volume>` |
| Cache provider / cluster / SVM / volume | `<cache-provider>` / `<cache-cluster>` / `<cache-svm>` / `<cache-volume>` |
| Origin/cache direction | `<origin-to-cache-direction>` |
| Volume type and security style | `<origin-volume-type>` / `<cache-volume-type>` / `<security-style>` |
| Client protocol | `<nfs-or-smb>` |
| Creation interface | `<documented-gcnv-or-ontap-interface>` |
| Post-state query | `<documented-cache-state-query>` |

After creation, verify origin and cache identity, cache state, SVM peer state, and content reads as separate results. Do not create, modify, or delete a cache when the private record lacks the creator, target resource, current state, dependencies, or inverse operation. FlexCache is not the S3 Access Point path; validate the NFS/SMB path to the cache volume separately.

### GCNV public interface

**This is what GCNV's public documentation says (read 2026-11-03). It is not a record of a real-environment run.**

| Direction (Origin → Cache) | Create the Cache | Check afterwards | Delete |
|---|---|---|---|
| FSx for ONTAP → GCNV | [`gcloud beta netapp volumes create`](https://docs.cloud.google.com/netapp/volumes/docs/configure-and-use/volumes/cache-ontap-volumes/create-flexcache-volume) with `--cache-parameters` carrying the origin's cluster name, SVM name, volume name, and intercluster LIF IPs | Read `cacheParameters.cacheState` from `gcloud beta netapp volumes describe`. For `PENDING_CLUSTER_PEERING`, run the returned `cluster peer create` on the origin FSx for ONTAP; for `PENDING_SVM_PEERING`, run the returned `vserver peer create`. Wait a minute and read again; `PEERED` marks the creation as complete | Delete like any other volume. If write-back is enabled, disable it first ([Manage FlexCache volumes](https://docs.cloud.google.com/netapp/volumes/docs/configure-and-use/volumes/cache-ontap-volumes/manage-flexcache-volume)) |
| GCNV (ONTAP-mode) → FSx for ONTAP | Run ONTAP `volume flexcache create` on FSx for ONTAP, after peering the clusters and SVMs with [the ONTAP-mode procedure](https://docs.cloud.google.com/netapp/volumes/docs/ontap/peer-clusters-svms) | `volume flexcache show`, `cluster peer show`, and `vserver peer show` on FSx for ONTAP | Follow ONTAP's procedure for deleting a FlexCache relationship |

GCNV states these conditions:

- Disable access-time updates on the origin volume.
- Give the cache the same security style as the origin. The cache's protocol determines it, and a cache does not support NFSv4.2.
- Create the cache at its intended size. GCNV says not to start small and grow it later.
- The communication prerequisites are shared with SnapMirror and volume migration, and a network connection and cluster peering built for migration or external replication can be reused.
- Peering times out after one hour in `PENDING_CLUSTER_PEERING` or `PENDING_SVM_PEERING`. Use `gcloud beta netapp volumes establish-peering` to correct a wrong IP and restart.
- ONTAP-mode volumes cannot be created, viewed, updated, or deleted from the Google Cloud console or the Google Cloud CLI.
- The [release notes](https://docs.cloud.google.com/netapp/volumes/docs/release-notes) call FlexCache allow-listed GA (GA that needs allow-list registration) as of 2025-09-24. Check that it is enabled in the target project first.

**Do not read this table as a run procedure.** This repository has no run record showing that the syntax GCNV returns is accepted by the ONTAP version of FSx for ONTAP, so that stays open. The `describe` output contains a passphrase; redact it when recording.

### Direction-specific FlexCache diagrams

- [FlexCache: FSx for ONTAP origin to GCNV cache](../../_assets/images/gcp-fsx-ontap-flexcache-fsx-origin-to-gcnv-cache-en.svg) ([dark theme](../../_assets/images/gcp-fsx-ontap-flexcache-fsx-origin-to-gcnv-cache-en-dark.svg))
- [FlexCache: GCNV origin to FSx for ONTAP cache](../../_assets/images/gcp-fsx-ontap-flexcache-gcnv-origin-to-fsx-cache-en.svg) ([dark theme](../../_assets/images/gcp-fsx-ontap-flexcache-gcnv-origin-to-fsx-cache-en-dark.svg))

The Open label means that cache creation and the post-create state have not been confirmed in a real environment. That the creation interface is documented is a separate matter. Including `flexcache` in the SVM peering applications is not evidence that cache creation succeeded.

## SnapMirror and Reverse Resync

> **Status: open**
>
> The control-plane ownership for FSx for ONTAP to GCNV create/initialize, GCNV stop/break, and GCNV to FSx for ONTAP Reverse Resync has not been established as a public, executable contract. This document therefore does not publish an unverified `snapmirror resync` or equivalent command as an execution step.

### Direction-specific SnapMirror diagrams

- [SnapMirror: FSx for ONTAP to GCNV](../../_assets/images/gcp-fsx-ontap-snapmirror-fsx-to-gcnv-en.svg) ([dark theme](../../_assets/images/gcp-fsx-ontap-snapmirror-fsx-to-gcnv-en-dark.svg))
- [Reverse Resync: GCNV to FSx for ONTAP](../../_assets/images/gcp-fsx-ontap-reverse-resync-gcnv-to-fsx-en.svg) ([dark theme](../../_assets/images/gcp-fsx-ontap-reverse-resync-gcnv-to-fsx-en-dark.svg))

The arrows show the data or relationship direction. Before execution, map the source, destination, operator, and post-state to the private record and fresh provider reads.

Minimum state mapping to resolve:

| Phase | Source | Destination | Required check |
|---|---|---|---|
| initialized | `<source-system>:<source-volume>` | `<destination-system>:<destination-volume>` | source/destination, role, mirror state, relationship status, health |
| synchronized | same | same | Actual ONTAP output mapped to predicates such as `Snapmirrored` and `Idle` |
| broken | GCNV destination | GCNV destination | Post-break write-enabled/read-only and provider state |
| reverse resync | GCNV | FSx for ONTAP | Authoritative operation, direction, post-state, and content evidence |
| final | Recorded identities | Recorded identities | Relationship state and file content must pass separately |

Names such as `healthy`, `transfer-state`, and `mirrorState` may be used only after mapping them to actual provider response fields. Do not accept a healthy result from another relationship as evidence for the target.

## Mutation approval procedure

This section is executed only after a separate approval and a passing read-only state check. These mutations were not run during this authoring session because the cluster peer was `Unavailable`.

### Create and initialize a SnapMirror relationship

Prerequisites are source and destination cluster and SVM peering, a `DP` destination volume, source and destination paths that match the recorded values, an approved policy and schedule, an owner, a rollback, and a transfer window. NetApp's procedure also requires cluster and SVM peering before relationship creation and verification with `snapmirror show` ([Create an ONTAP SnapMirror replication relationship](https://docs.netapp.com/us-en/ontap/data-protection/create-replication-relationship-task.html)).

```text
# Run on the destination cluster. Use the recorded values.
snapmirror create \
  -source-path <source-svm>:<source-volume> \
  -destination-path <destination-svm>:<destination-volume> \
  -type XDP \
  -schedule <approved-schedule> \
  -policy <approved-policy>

snapmirror show -destination-path <destination-svm>:<destination-volume>

# Initialize only after the relationship and roles match the recorded values.
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

When `hybridReplicationUserCommands` is returned, save the ONTAP commands in the private record and execute those commands exactly. Do not infer or rewrite the source, destination, SVM, cluster, or direction from placeholders.

- **Stop**: request stop on the Google Cloud side. For an external ONTAP destination, verify `Snapmirrored` / `Idle` with `snapmirror show`, then run the returned `snapmirror break` command.
- **Resume**: request resume on the Google Cloud side, then run the returned `snapmirror resync` command only when its direction matches the new recorded state.
- **Reverse**: stop the replication first and start reverse on the Google Cloud side. When ONTAP becomes the new destination, run only the returned `snapmirror resync`, schedule, and modify commands.
- **Delete**: require stopped state, no outdated SnapMirror connection, and separate approval for cluster-peer cleanup when this is the last replication.

Do not run any of these operations while the current cluster peer is `Unavailable`.

### Create a FlexCache relationship

The AWS FlexCache procedure orders intercluster LIF and network checks, cluster peering, SVM peering, cache-volume creation, and `volume flexcache show`. For remote networks, confirm the route and intercluster TCP 11104 / 11105 first ([Creating a FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-flexcache.html)). The current NetApp procedure also uses cluster peering, SVM peering, `volume flexcache create`, and `volume flexcache show` ([Create ONTAP FlexCache volumes](https://docs.netapp.com/us-en/ontap/flexcache/create-volume-task.html)).

The command shapes below create a Cache on FSx for ONTAP (the origin is GCNV in ONTAP-mode, or FSx for ONTAP). For a Cache on GCNV, create the cache volume with `gcloud beta netapp volumes create` ([GCNV public interface](#gcnv-public-interface)) and run only the `cluster peer create` and `vserver peer create` commands that `describe` returns, on the origin FSx for ONTAP. Do not run `volume flexcache create`.

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

STOP until `cluster peer show` reports `Available`, the SVM peer is `peered`, the application is `flexcache`, origin and cache identities match the recorded values, security style is deliberate, and the inverse operation is recorded. The current cluster peer is `Unavailable`, so FlexCache creation remains Open.

### Rollback and destructive-operation boundary

Before deleting a relationship, confirm that no transfer is active, client access is stopped, the owner approved the operation, and the inverse operation and post-state are in the private record. The published Reverse Resync procedure orders common-snapshot checks, direction changes, update, quiesce, break, delete, release, and re-sync of the original relationship ([Reactivate the original ONTAP source volume](https://docs.netapp.com/us-en/ontap/data-protection/reactivate-original-source-volume-task.html)).

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

1. A fresh read of owner and exact resource identity from the private record.
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
- [Google Cloud: Create a FlexCache volume](https://docs.cloud.google.com/netapp/volumes/docs/configure-and-use/volumes/cache-ontap-volumes/create-flexcache-volume)
- [Google Cloud: Manage FlexCache volumes](https://docs.cloud.google.com/netapp/volumes/docs/configure-and-use/volumes/cache-ontap-volumes/manage-flexcache-volume)
- [Google Cloud: Peer clusters and SVMs](https://docs.cloud.google.com/netapp/volumes/docs/ontap/peer-clusters-svms)
- [NetApp TR-4743: ONTAP FlexCache and FlexGroup technical reports](https://docs.netapp.com/us-en/ontap-technical-reports/nas-containers.html)
- [NetApp TR-4015: data protection and disaster recovery technical reports](https://docs.netapp.com/us-en/ontap-technical-reports/data-protection-disaster-recovery.html)
- [AWS Blog: scalable replication with FSx for ONTAP and SnapMirror](https://aws.amazon.com/blogs/storage/highly-scalable-solution-design-to-replicate-data-using-amazon-fsx-for-netapp-ontap-and-snapmirror/)

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/reference/gcp-to-fsx-ontap-peering-and-replication-open-items.md) | [English](gcp-to-fsx-ontap-peering-and-replication-open-items.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
