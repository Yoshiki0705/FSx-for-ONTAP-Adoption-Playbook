---
title: FlexCache CLI procedure (NFS) – simplified
lifecycle: [design, build]
domains: [performance, client-access, data-protection]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-flexcache.html
lang: en
---

# FlexCache CLI procedure (NFS) – simplified

[🏠 Repository home](../../en/README.md) | [Reference](../../ja/reference/README.md)

> **Audience and scope**
>
> This is the NFS counterpart to the existing "FlexCache CLI procedure (SMB) – simplified". It gives an operator who does not want to read the manual end to end the shortest path to build a FlexCache over NFS, with the Origin on Amazon FSx for NetApp ONTAP and the Cache on a second cluster. The SMB version's NetBIOS name, Active Directory domain join, and CIFS share steps are replaced by NFS service, export policy, and junction-path mount.
>
> **Evidence handling**
>
> This document is `documented`. The command shapes follow the AWS FlexCache guide, the NetApp public ONTAP procedures, and TR-4743 / TR-4571, but they do not assert success, performance, or state in any specific environment. Every IP, SVM name, cluster name, volume name, and size is a replaceable placeholder. Real values, run output, and performance numbers go only into a private run ledger. Verify in your own environment before production use.

## Conclusion

This procedure is the shortest path to create a Cache volume for an Origin (FSx for ONTAP) NFS volume on a second cluster's Cache SVM and reach it over NFSv3. The main line is **NFSv3 + write-around (default) + FlexGroup auto-provision**. Write-back, NFSv4.x, and SMB coexistence are kept to short supplements.

FlexCache suits read-heavy workloads that change infrequently. A change at the Origin requires the Cache to refresh, and both cache misses and writes are bound by the link to the Origin, so the effect is decided by the path and the access pattern (TR-4743). This simplified version is a creation procedure assuming reachability, export policy, and peering are already in place, and it does not skip Origin/Cache identity confirmation or recording the inverse operation.

| Verdict | Meaning in this procedure |
|---|---|
| `documented` | A prerequisite or operation shape confirmable from public sources. Does not assert success or performance in a real environment. |
| placeholder | IPs, names, and sizes are replaced per environment. Real values are not published. |
| stop | When identity, state, peer, or path does not match the ledger, stop on the spot. |

> **Authoring boundary**
>
> `cluster peer create`, `vserver peer create/accept`, and `volume flexcache create` are mutations. Run them only when both clusters' peering is `Available` / `peered`, every intercluster LIF pair reaches each other, and the Origin/Cache identity and inverse operation are in the ledger. If any of these is missing or contradictory, stop rather than run.

## Target environment (for replacement)

The SMB version's model names are generalized, and the Cache side is written as any second cluster. Real values go only into a private ledger.

| Item | Origin storage | Cache storage |
|---|---|---|
| Storage | Amazon FSx for NetApp ONTAP | `<cache-cluster-model>` (any ONTAP cluster) |
| ONTAP version | `<origin-ontap-version>` (9.7 or later assumed) | `<cache-ontap-version>` (9.7 or later assumed) |
| SVM | `<origin-svm>` | `<cache-svm>` |
| Protocol | NFS (NFSv3 main line) | NFS (NFSv3 main line) |
| Origin volume | `<origin-volume>` | — |
| Cache volume | — | `<cache-volume>` (FlexGroup) |
| NFS data LIF | `<origin-nfs-lif>` | `<cache-nfs-lif-1>` / `<cache-nfs-lif-2>` |
| Intercluster LIF | `<origin-intercluster-lif-1>` / `<origin-intercluster-lif-2>` | `<cache-intercluster-lif-1>` / `<cache-intercluster-lif-2>` |
| Gateway / NTP / DNS | Environment default | `<cache-gateway-ip>` / `<cache-ntp-ip>` / `<cache-dns-ip>` |

### Prerequisites (work already completed)

- **FSx for ONTAP (Origin)**: file system created, SVM created, volume created (UNIX security style), NFS service enabled, export policy permitting access, NFS data LIF.
- **Cache cluster**: initial setup, data aggregate created, SVM created, FlexCache intercluster LIF created, NFS data LIF created.
- **Network**: TCP 11104 / 11105 reachability between both clusters' intercluster LIFs, a route from the Cache SVM to the Origin, and a TCP 2049 path from the NFS client to the Cache.

FlexCache requirements (TR-4743, ONTAP manual): both Origin and Cache must be ONTAP 9.5 or later. The Origin volume may be a FlexVol or a FlexGroup (9.7 or later). **The Cache volume is always a FlexGroup.** The Origin can serve NFSv3 / NFSv4 / SMB, but access to the Cache is NFSv3 only before 9.7, and **NFSv4 is supported from 9.10.1**. An SMB Cache is 9.8 or later.

## 1. Origin (FSx for ONTAP) pre-checks

Confirm the current state read-only. SSH to the cluster management endpoint as `fsxadmin` and move to advanced privilege.

```text
::> set advanced

# 1.1 volume list
::*> volume show -vserver *

# 1.2 security style of the target volume (NFS assumes unix)
::*> volume show -vserver <origin-svm> -volume <origin-volume> -fields security-style

# 1.3 NFS service state
::*> vserver nfs show -vserver <origin-svm>

# 1.4 DNS settings
::*> dns show -vserver *

# 1.5 ONTAP version
::*> version

# 1.6 export policy and rules (which clients are permitted)
::*> vserver export-policy show -vserver <origin-svm>
::*> vserver export-policy rule show -vserver <origin-svm> -policyname *

# 1.7 routing
::*> route show -vserver *

# 1.8 FlexCache intercluster LIFs
::*> network interface show -role intercluster
```

If the security style is not unix, the NFS service is disabled, the export policy does not permit access from the Cache SVM, or the intercluster LIF does not exist, stop and return it to each owner. The Origin volume's security style is inherited by the Cache and **cannot be changed on the Cache side**. On the NFS main line, provision the Origin as unix.

## 2. Cache cluster setup

### 2.1 Confirm settings

```text
::*> route show -vserver *
::*> dns show -vserver *
::*> export-policy rule show -vserver *
::*> cluster time-service ntp server show
```

If the export policy has no rule, add one scoped to the NFS client range. `0.0.0.0/0` is for validation only; in production, scope it to the client CIDR.

```text
::*> export-policy rule create -vserver <cache-svm> -policyname default \
  -clientmatch <nfs-client-cidr> -rorule sys -rwrule sys -superuser sys -protocol nfs
```

The Admin SVM name is the one whose `type` column is `admin` in `vserver show -vserver *`.

### 2.2 Gateway, NTP, DNS

```text
# 2.2.1 gateway
::*> route add -vserver <admin-svm> -destination 0.0.0.0/0 -gateway <cache-gateway-ip>
::*> route show -vserver *

# 2.2.2 NTP (time sync takes a few minutes)
::*> cluster time-service ntp server create -server <cache-ntp-ip>
::*> cluster time-service ntp server show
::*> cluster date show

# 2.2.3 DNS
::*> dns create -vserver <admin-svm> -domains <dns-domain> -name-servers <cache-dns-ip>
::*> dns create -vserver <cache-svm> -domains <dns-domain> -name-servers <cache-dns-ip>
::*> dns show -vserver *
```

### 2.3 Reachability between intercluster LIFs

From the Cache's two intercluster LIFs, reach the Origin's two intercluster LIFs in every combination.

```text
::*> network ping -lif <cache-intercluster-lif-1> -vserver <admin-svm> -destination <origin-intercluster-lif-1>
::*> network ping -lif <cache-intercluster-lif-1> -vserver <admin-svm> -destination <origin-intercluster-lif-2>
::*> network ping -lif <cache-intercluster-lif-2> -vserver <admin-svm> -destination <origin-intercluster-lif-1>
::*> network ping -lif <cache-intercluster-lif-2> -vserver <admin-svm> -destination <origin-intercluster-lif-2>
```

**All four pairs must reach each other.** If any one IP is down, FlexCache creation fails (the same constraint as the SMB version). If any one fails, stop.

### 2.4 Enable the NFS service (Cache SVM)

The SMB version's CIFS server creation and AD domain join are not needed in the NFS version. Instead, enable NFS on the Cache SVM.

```text
::*> vserver nfs create -vserver <cache-svm> -v3 enabled -access true
::*> vserver nfs show -vserver <cache-svm>
```

To also use NFSv4.x, see the supplement. The main line is v3.

## 3. FlexCache setup

The prompt name indicates which ONTAP runs the command (Cache side is `Cache::*>`, Origin side is `FSx-for-ONTAP::*>`).

### 3.1 Create the cluster peer

```text
Cache::*> cluster peer create -address-family ipv4 \
  -peer-addrs <origin-intercluster-lif-1>,<origin-intercluster-lif-2> -applications flexcache
  Enter the passphrase:
  Confirm the passphrase:
  # Enter the same passphrase in the next step. It is a one-time value for establishing the peer.

FSx-for-ONTAP::*> cluster peer create -address-family ipv4 \
  -peer-addrs <cache-intercluster-lif-1>,<cache-intercluster-lif-2> -applications flexcache
  Enter the passphrase:
  Confirm the passphrase:

Cache::*> cluster peer show
FSx-for-ONTAP::*> cluster peer show
```

Hand the passphrase over a private channel and keep it out of shell history, stdout, logs, and public output. If `cluster peer show` does not reach `Available` on both sides, stop.

### 3.2 Create the SVM peer

```text
Cache::*> vserver peer create -vserver <cache-svm> -peer-vserver <origin-svm> \
  -applications flexcache -peer-cluster <origin-cluster-name>

FSx-for-ONTAP::*> vserver peer accept -vserver <origin-svm> -peer-vserver <cache-svm>

Cache::*> vserver peer show
FSx-for-ONTAP::*> vserver peer show
```

Confirm that the peer state is `peered` on both sides and that `applications` includes `flexcache`. If only one side is `peered`, applications are missing, or identity does not match, stop.

### 3.3 Create the FlexCache volume

AWS requires the FlexCache volume to be a FlexGroup, so use `-auto-provision-as flexgroup`. Instead of the SMB version's explicit `-aggr-list`, the main line on FSx for ONTAP does not name aggregates and relies on auto-provision.

```text
Cache::*> volume flexcache create \
  -vserver <cache-svm> \
  -volume <cache-volume> \
  -auto-provision-as flexgroup \
  -size <cache-size> \
  -origin-vserver <origin-svm> \
  -origin-volume <origin-volume> \
  -junction-path /<cache-volume> \
  -space-guarantee none

Cache::*> volume flexcache show
Cache::*> volume flexcache show -vserver <cache-svm> -volume <cache-volume> -instance
```

Meaning: on Cache SVM `<cache-svm>`, create a Cache volume `<cache-volume>` (FlexGroup) for `<origin-volume>` on Origin SVM `<origin-svm>`, thin-provisioned at `<cache-size>`, mounted at `/<cache-volume>`. The security style is inherited from the Origin (unix) and cannot be set or changed on the Cache side. Do not proceed until `volume flexcache show` lists the Cache and the Origin/Cache identity matches the ledger.

## 4. Other tasks

### 4.1 NFS export and mount

Instead of the SMB version's CIFS share creation, NFS publishes the junction path through the export policy and the client mounts it.

```text
# Apply the export policy to the Cache volume (use the policy created in 2.1)
Cache::*> volume modify -vserver <cache-svm> -volume <cache-volume> -policy default
Cache::*> volume show -vserver <cache-svm> -volume <cache-volume> -fields policy,junction-path
```

```bash
# On the NFS client (NFSv3)
sudo mount -t nfs -o vers=3 <cache-nfs-lif-1>:/<cache-volume> /mnt/<cache-volume>
findmnt -T /mnt/<cache-volume> -o TARGET,SOURCE,FSTYPE,OPTIONS
```

Confirm the mount source and FSTYPE match what you expect. If they do not, unmount and stop.

### 4.2 Warm the cache (optional)

When you want to raise the hit rate before a batch run, use prepopulate. Give `-path-list` the directory structure inside the FlexVol directly; do not include the junction path or a share name.

```text
Cache::> set advanced
Cache::*> flexcache prepopulate start \
  -cache-volume <cache-volume> -cache-vserver <cache-svm> -path-list /<dir1>,/<dir2>
```

Caching is block-level by nature, but with `-path-list` the named files and directories are cached in full.

## Supplement

### write-back (default is write-around)

On the write-around main line, a write to the Cache is forwarded to the Origin and completes after the Origin commits it (the NFS Write behavior in TR-4743). Write-back is a write mode that commits first on the Cache side. It arrived in ONTAP 9.15.1, but **9.17.1P1 or later is strongly recommended on both Origin and Cache**, and 9.15.1 is not recommended for production. Choosing write-back adds constraints such as recommending a single constituent for the FlexGroup. Because AWS requires FlexCache to be a FlexGroup, the shape becomes a single-constituent FlexGroup. Consider write-back only under separate approval and after meeting the version prerequisites.

### NFSv4.x

NFSv4 access to the Cache is supported from ONTAP 9.10.1. To use NFSv4.x, enable `-v4.0 enabled` / `-v4.1 enabled` on the Cache SVM and mount with `vers=4.x` on the client. ACL and lock handling differ from v3, so verify it separately from the main line (v3).

### Invalidation and consistency

FlexCache keeps consistency with delegations, locks, a negative lookup cache, and disconnected mode. A change at the Origin invalidates the delegation for the affected blocks, and the Cache re-fetches on the next access. During a network disconnection, a disconnected Cache can access only already-cached data and, after reconnection, reflects the Origin's updates on a per-file basis (TR-4743). Size the Cache assuming FIFO eviction at 90%. These are conclusion notes; confirm the behavior in your specific environment.

## Stop conditions

Stop immediately on any of the following.

- The Origin volume's security style is not unix, or the NFS service is disabled.
- The export policy does not permit access from the NFS client / Cache SVM.
- Any of the four intercluster LIF pairs fails to reach each other.
- `cluster peer show` does not reach `Available` on either side.
- The SVM peer is `peered` on only one side, `applications` lacks `flexcache`, or identity does not match.
- `volume flexcache show` does not list the Cache, or the Origin/Cache identity differs from the ledger.
- A passphrase or a real value appeared in shell history, stdout, logs, or public output.

## Related documents

- [Open items for GCP and FSx for ONTAP peering and replication](../../en/reference/gcp-to-fsx-ontap-peering-and-replication-open-items.md) — the open items for the GCNV management-plane interface when applying this procedure with GCNV as the Cache side
- [GCP / FSx for ONTAP read-only preflight and sample validation](../../en/reference/gcp-to-fsx-ontap-preflight-and-sample-validation.md)
- [Evidence policy](../../en/evidence-policy.md)
- [AWS: Creating a FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-flexcache.html)
- [NetApp: Create ONTAP FlexCache volumes](https://docs.netapp.com/us-en/ontap/flexcache/create-volume-task.html)
- [NetApp: FlexCache accelerate data access concept](https://docs.netapp.com/us-en/ontap/flexcache/accelerate-data-access-concept.html)
- [NetApp TR-4743: FlexCache in ONTAP](https://docs.netapp.com/us-en/ontap-technical-reports/nas-containers.html)
- [NetApp TR-4571: ONTAP FlexGroup volumes](https://docs.netapp.com/us-en/ontap-technical-reports/flexgroup-volumes.html)

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/reference/flexcache-cli-nfs-simplified.md) | [English](flexcache-cli-nfs-simplified.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
