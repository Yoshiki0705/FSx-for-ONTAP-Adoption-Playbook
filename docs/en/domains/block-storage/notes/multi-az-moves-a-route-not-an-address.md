---
title: Multi-AZ moves a route, not an address — the block address does not move, so no Transit Gateway is needed either
lifecycle: [design, build, operate]
domains: [block-storage, performance]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
lang: en
---

# Multi-AZ moves a route, not an address

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/multi-az-moves-a-route-not-an-address.md) | [English](multi-az-moves-a-route-not-an-address.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

---

## Conclusion

**A Multi-AZ FSx for ONTAP has addresses that move and addresses that do not. The block address is on the side that does not move.**

The NFS, SMB, and management addresses are floating addresses outside the VPC CIDR, and on failover **the target ENI of the `/32` entry in the VPC route table is rewritten.** The address does not move within the subnet.

**The iSCSI and NVMe/TCP addresses are ordinary private addresses inside the VPC CIDR, one per AZ, carried directly on the ENI.** Their `failover-policy` is `disabled`; they are pinned to a node and do not move.

There are three consequences.

| Consequence | Detail |
|---|---|
| Reachable across peering | The block address is inside the VPC CIDR, so **it does not meet the condition that requires a Transit Gateway** |
| Availability is a host-side mechanism | Because the LIF does not move, **what switches is the host's multipath** |
| The optimal path is not decided by AZ | **ALUA / ANA optimized is on the side of "the node that owns the volume."** It is unrelated to the client's AZ |

> **Tier**: `verified` (verified 2026-09-05, `ap-northeast-1`, `MULTI_AZ_2` second generation, 1 HA pair, 384 MBps, ONTAP 9.18.1P5) — the placement of addresses, `failover-policy`, the route-table rewrite, and the direction of ALUA priority.
> **Performance figures are not included.**

---

## The placement of addresses

The endpoint IP address range was auto-assigned as **`198.19.174.0/24`**. The VPC CIDR is a `10.0.x.x` /16, so **this range is outside the VPC.**

| LIF | Address | Inside the VPC CIDR | `failover-policy` |
|---|---|---|---|
| `fsxadmin` (cluster management) | 198.19.174.43 | **No** | `broadcast-domain-wide` |
| `inter_1` (intercluster, node -01) | `<intercluster-1a>` | Yes | **`disabled`** |
| `inter_2` (intercluster, node -02) | `<intercluster-1c>` | Yes | **`disabled`** |
| `iscsi_1` (node -01) | `<iscsi-1a>` | Yes | **`disabled`** |
| `iscsi_2` (node -02) | `<iscsi-1c>` | Yes | **`disabled`** |
| `nfs_smb_management_1` | 198.19.174.120 | **No** | `sfo-partner-only` |

There was one ENI per AZ, **each carrying only two private addresses.**

| ENI | AZ | Addresses carried |
|---|---|---|
| `eni-081931…` | `ap-northeast-1a` (preferred) | `<intercluster-1a>` (intercluster), `<iscsi-1a>` (iSCSI) |
| `eni-0c290c…` | `ap-northeast-1c` (standby) | `<intercluster-1c>` (intercluster), `<iscsi-1c>` (iSCSI) |

**The floating addresses are on no ENI.** They exist as `/32` entries in the associated route table, with an ENI as the target.

```text
198.19.174.43/32   -> eni-081931…   (cluster management)
198.19.174.120/32  -> eni-081931…   (the SVM's NFS / SMB / management)
```

**The SVM's NFS / SMB / management LIF is a single one.** It is not one per AZ.

---

## What is rewritten on failover

This is the result of inducing a failover by changing the throughput capacity from 384 to 768 MBps and watching the route table at 5-second intervals.

| Time (UTC) | Target of `198.19.174.120/32` |
|---|---|
| 07:27:40 (change requested) | The 1a ENI |
| Between 07:28:10 → 07:28:31 | **Rewritten to the 1c ENI** |
| Between 07:39:26 → 07:39:52 | **Back to the 1a ENI** |

**During this, the two iSCSI addresses did not move from their respective ENIs.**

**This is why the discussion of client-side ARP tuning is written limited to Single-AZ.** AWS shows a `sysctl` setting that shortens failover detection from 55–60 seconds to 15–20 seconds, but **its target is a Single-AZ file system, and the content is tuning the ARP cache lifetime and neighbor discovery.** In Single-AZ the floating address moves between nodes within the same subnet, so the client must relearn the MAC address mapping. **In Multi-AZ the route table is rewritten, so this is not a situation where that tuning applies.**

**And neither applies to iSCSI.** Because the address does not move, there is nothing to relearn.

---

## The condition that requires a Transit Gateway, and why block does not meet it

AWS writes the condition that requires additional Transit Gateway configuration as **"a Multi-AZ file system whose endpoint IP address range is outside the VPC CIDR."** If it is inside the VPC CIDR, no additional configuration is needed.

**In the verification environment the endpoint range was outside the VPC** (`198.19.174.0/24`). So **NFS / SMB / management meet this condition.** Meanwhile **the iSCSI and NVMe/TCP addresses are inside the VPC CIDR, so they do not.**

AWS's client requirements table also answers "No" for iSCSI and NVMe/TCP to the question of whether a Transit Gateway is required.

**In a design that uses it from across a peering, this distinction changes the configuration.**

| Protocol used | Additional requirement across peering |
|---|---|
| iSCSI / NVMe/TCP only | **Reachable over VPC peering.** No route-table addition needed |
| Includes NFS / SMB / ONTAP management | If the endpoint range is outside the VPC, **a Transit Gateway and a route to that range are needed.** The route table of the subnet holding the Transit Gateway attachment must also be associated with the file system |

**If you use only block, the route requirement is straightforward.** But **if you also manage ONTAP over the same route, the management LIF is on the floating side, so that requirement remains.**

---

## The direction of the optimal path

**In a 1 HA pair configuration there is only one aggregate.** The verification environment's `aggr1` was owned by node -01 (the 1a side), and **all volumes were there.** Node -02 owns nothing until failover.

`lun mapping show -fields reporting-nodes` lists the two nodes, the owning node and its HA partner. So **there are two paths.**

Placing clients in the two AZs, the priorities for the same LUN were compared.

| Client AZ | Via `<iscsi-1a>` (the 1a LIF) | Via `<iscsi-1c>` (the 1c LIF) |
|---|---|---|
| `ap-northeast-1a` | **prio=50 active** | prio=10 enabled |
| `ap-northeast-1c` | **prio=50 active** | prio=10 enabled |

**For both clients, the optimized path was the 1a LIF.** Because the node that owns the volume is there.

**Placing a client in the standby AZ does not make that client's block access local.** The path on the same-AZ side becomes non-optimized, and **normal I/O crosses the AZ.** It bears on both latency and inter-AZ data transfer.

NVMe/TCP was the same direction. Even on a kernel with native multipath disabled, the ANA state can be read per controller.

```text
nvme ana-log /dev/nvme3   (traddr=<iscsi-1a>)  ->  state: optimized
nvme ana-log /dev/nvme2   (traddr=<iscsi-1c>)  ->  state: non-optimized
```

**The order of device names does not indicate whether it is optimized.** In the verification environment the non-optimized side appeared first as `/dev/nvme2n1`.

---

## The usable capacity in Multi-AZ

This is a measurement with `set -unit B`.

| Item | Bytes | Note |
|---|---|---|
| SSD provisioning | — | 1,024 GiB requested |
| Size of `aggr1` | 925,224,214,528 | **861.7 GiB** |
| Free in `aggr1` (empty) | 922,878,918,656 | |

**In the round 1 Single-AZ environment, the aggregate was 907.03 GiB from the same 1,024 GiB.** In Multi-AZ it is 861.7 GiB.

**The difference between the two environments is the deployment type, but no verification was done to isolate other factors.** It is an observation of two environments: "in Multi-AZ, the amount usable from the same provisioned capacity was smaller." **For capacity design, count in your own environment.**

---

## How to confirm in your own environment

| # | Step | What it tells you |
|---|---|---|
| 1 | `aws fsx describe-file-systems --query 'FileSystems[0].OntapConfiguration.EndpointIpAddressRange'` | **Whether that range is inside or outside the VPC CIDR. Whether a Transit Gateway is needed is decided here** |
| 2 | `aws fsx describe-storage-virtual-machines --query 'StorageVirtualMachines[].Endpoints'` | That the iSCSI address is inside the VPC CIDR. **`Nvme` returns `null`** (see below) |
| 3 | `aws ec2 describe-network-interfaces --network-interface-ids <the fs ENI>` | The distinction between addresses carried on the ENI and those not |
| 4 | Check the `/32` entries and their target ENI in the associated route table | **The implementation of floating addresses** |
| 5 | `network interface show -fields address,home-node,failover-policy` | **That iSCSI is `disabled`** |
| 6 | Connect from the two AZs and compare the `prio` in `multipath -ll` | **Which AZ the optimized side faces** |
| 7 | `storage aggregate show -fields aggregate,node` | With 1 HA pair there is one aggregate, owned by one of the nodes |
| 8 | Run `nvme ana-log /dev/nvmeN` per controller | **Telling optimized apart on a kernel with no native multipath** |

---

## Common misconceptions

| Misconception | Reality |
|---|---|
| In Multi-AZ the address moves between nodes on failover | **What moves is the target of the `/32` in the route table** |
| The iSCSI address also moves on failover | **It does not.** `failover-policy` is `disabled` |
| Using Multi-AZ across peering requires a Transit Gateway | **Only when the endpoint range is outside the VPC.** The block address is inside the VPC, so it does not apply |
| Client-side `sysctl` tuning also speeds up block failover | **That tuning is for Single-AZ NFS and speeds up ARP relearning.** There is no situation where it applies to iSCSI, whose address does not move |
| Placing a client in the standby AZ gives local access | **Optimized is on the volume-owning node side.** Normal I/O crosses the AZ |
| There are multiple iSCSI LIFs per AZ | **There was one per AZ, two per SVM in total** |
| There is an NFS LIF per AZ too | **There is one per SVM** |
| The NVMe endpoint can be obtained from the AWS API | **`Nvme` returned `null`.** You must ask the ONTAP side |
| The usable capacity in Multi-AZ is the same as Single-AZ | **From the same 1,024 GiB it was 861.7 GiB and 907.03 GiB** (an observation of two environments) |

---

## Verification environment

| Item | Value |
|---|---|
| ONTAP version | 9.18.1P5 |
| Region | `ap-northeast-1` |
| Deployment type | `MULTI_AZ_2` (second generation, 1 HA pair) |
| Throughput capacity | 384 MBps (changed to 768 MBps after measurement) |
| SSD capacity | 1,024 GiB, `AUTOMATIC` IOPS = 3,072 |
| VPC CIDR | a `10.0.x.x` /16 |
| preferred subnet | `ap-northeast-1a` (the `10.0.0.x` /20) |
| standby subnet | `ap-northeast-1c` (the `10.0.16.x` /20) |
| Endpoint IP range | `198.19.174.0/24` (auto-assigned) |
| Client | Amazon Linux 2023, kernel 6.18.44-99.149.amzn2023.x86_64, one per AZ |
| Verification date | 2026-09-05 |

> **Note**: the above is a measurement in this environment. **The endpoint IP range can be specified at creation time and can be made inside the VPC CIDR.** That the auto-assigned result was outside the VPC is a fact of this environment, not a statement that it is always so.

---

## Primary sources referenced

| Point | Source |
|---|---|
| That a Multi-AZ with an endpoint range outside the VPC CIDR needs an additional Transit Gateway route; that inside the VPC CIDR it is not needed; that the route table of the attachment's subnet must be associated | [AWS: Configure routing to access Multi-AZ file systems from on-premises](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configure-routing-maz-on-prem.html) |
| That iSCSI and NVMe/TCP do not require a Transit Gateway | [AWS: Supported clients and access methods](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-fsx-clients.html) |
| The `sysctl` tuning for Single-AZ NFS clients (`base_reachable_time_ms`, `delay_first_probe_time`, `ucast_solicit`, `tcp_syn_retries`) and that detection time goes from 55–60 seconds to 15–20 seconds | [AWS: Troubleshooting I/O errors and NFS lock reclaim failures](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/nfs-failover-issues.html) |
| That there are four failover triggers, that it usually completes in under 60 seconds, and that Multi-AZ fails back automatically when the preferred recovers | [AWS: Availability, durability, and deployment options](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/high-availability-AZ.html) |
| That failover can be tested by changing throughput capacity, and that file servers are replaced serially | [AWS: Managing throughput capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-throughput-capacity.html) |
| That Selective LUN Map narrows reporting nodes to the owning node and the HA partner | [NetApp: Selective LUN Map](https://docs.netapp.com/us-en/ontap/san-admin/selective-lun-map-concept.html) |
| That ONTAP uses ALUA for iSCSI and ANA for NVMe | [NetApp: Multipathing](https://docs.netapp.com/us-en/ontap/san-config/host-support-multipathing-concept.html) |

---

## Related documents

- [Domain — Block storage](../README.md) — this module's hub
- [Paths are the failover mechanism itself (日本語)](../../../../ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md) — the failover actually measured on top of this placement
- [The block protocol choice is narrowed first by generation and HA pair count (日本語)](../../../../ja/domains/block-storage/notes/protocol-choice-is-bounded-before-you-choose.md) — the LIF and port premises
- [What block monitoring shows and does not (日本語)](../../../../ja/domains/block-storage/notes/what-block-monitoring-shows.md) — watching the node switch in the `FileServer` dimension
- [The deployment type is decided only once](../../../playbooks/02-design/notes/deployment-type-is-decided-once.md)
- [Block storage cross resource map (日本語)](../../../../ja/reference/block-storage-resource-map.md)
- [Evidence policy](../../../evidence-policy.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/multi-az-moves-a-route-not-an-address.md) | [English](multi-az-moves-a-route-not-an-address.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
