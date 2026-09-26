---
title: Kubernetes block persistent volumes hit the volume-count limit — the driver choice decides that ceiling
lifecycle: [design, build, operate]
domains: [block-storage, data-utilization, performance]
evidence: documented
source: https://docs.netapp.com/us-en/trident/trident-use/ontap-san.html
lang: en
---

# What limit do Kubernetes block PVs hit?

Volume count, not capacity. The Trident driver choice decides that ceiling.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/kubernetes-block-volumes-and-the-volume-limit.md) | [English](kubernetes-block-volumes-and-the-volume-limit.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That `ontap-san` consumes one FlexVol per PV, so what runs out is volume count (500 / 1,000), not capacity
- That `ontap-san-economy`, which removes that ceiling, does not support per-PV Snapshot / SnapMirror / QoS

## What this note does not answer

- A measurement of PV count actually reaching the limit (not verified)
- How multiple Pods' writes on a block RWX are arbitrated (the cluster filesystem's responsibility)

## Prerequisite level

intermediate

## Body

<a id="kubernetes-block-persistent-volumes-hit-the-volume-count-limit"></a>

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

---

### Conclusion

**Using FSx for ONTAP as a block persistent volume, what runs out is volume count, not capacity.**

Trident's `ontap-san` driver **creates one FlexVol per PV and places one LUN inside it.** So **the PV count maps directly onto the volume-count limit.** FSx for ONTAP's volume-count limit is **500** for second generation with 1 HA pair, **1,000** for 2 or more pairs, and **500** for first generation.

**The driver that removes this ceiling is `ontap-san-economy`.** It packs many LUNs into a shared FlexVol, so PV count is not bound by volume count. **NetApp states this should be used only when the expected PV count exceeds ONTAP's volume limit.**

**Decide up front.** The driver is tied to the StorageClass, so changing it later means re-creating PVs under a new StorageClass.

> **Tier**: `documented` — the driver behaviour is per NetApp's documentation, and the volume limit is per AWS's documentation (confirmed 2026-09-05).
> **No PV-count measurement is included.** No verification was run to reach the limit.
> The steps to confirm in your own environment are in [Verify it in your environment](#verify-it-in-your-environment).

---

### The difference between the two drivers

| Point | `ontap-san` | `ontap-san-economy` |
|---|---|---|
| **What one PV consumes** | **One FlexVol + one LUN inside it** | **One LUN** inside a shared FlexVol |
| **What bounds PV count** | **The volume-count limit** (500 / 1,000) | The number of shared FlexVols and the LUNs each can hold |
| **How volume-level operations apply** | **Independent per PV.** Snapshot, SnapMirror, and QoS can be applied per PV | **Per shared FlexVol.** A single PV alone cannot be the target |
| **NetApp's recommendation** | The default choice | **Only when the expected PV count exceeds the volume limit** |
| **NVMe/TCP** | Supported on `ontap-san`. **REST only** (not supported on ONTAPI / ZAPI, confirmed in Trident's documentation 2026-09-05) | Not stated |

**The trade-off is symmetric.** `ontap-san` gains per-PV independence at the cost of accepting the volume limit as a ceiling. `ontap-san-economy` gains freedom on PV count at the cost of losing per-PV volume-level operations.

**"Pick whichever gives more" is not the right frame.** If your design operates Snapshot or SnapMirror per PV, `ontap-san-economy` does not support that operation.

---

### Where the volume-count limit bites

| Configuration | Volume-count limit | Rough PV-count ceiling on `ontap-san` |
|---|---|---|
| First generation | 500 | 500, minus the SVM's root volume and similar |
| Second generation, 1 HA pair | 500 | Same as above |
| Second generation, 2 or more pairs | **1,000 (across all HA pairs)** | Adding HA pairs still caps at 1,000 |

**Adding HA pairs still caps the volume-count limit at 1,000.** File systems using a block protocol are **supported only up to 6 HA pairs**, so a configuration using block PVs is capped at 6 pairs. Details are in [The deployment type is decided only once (日本語)](../../../playbooks/02-design/notes/deployment-type-is-decided-once.md).

**FlexGroup constituent volumes count toward this too.** If a file-serving FlexGroup shares the same file system, the headroom available for block PVs is reduced by that amount.

---

### Reading access modes

Trident's SAN driver supports **RWO / ROX / RWX / RWOP.** **But what RWX means on block differs from what RWX means on a file share.**

| Mode | Meaning on block |
|---|---|
| RWO | Read-write from one node. **The standard way to use block** |
| RWOP | Read-write from one Pod |
| ROX | Read-only from multiple nodes |
| RWX | **Visible simultaneously as a raw block device from multiple nodes.** If a filesystem is placed on it, arbitration is the cluster filesystem's responsibility |

**Choosing RWX does not come with a mechanism that stops two Pods writing to the same block at once.** This is the same property as Amazon EBS Multi-Attach. See [When shared block changes the design](when-shared-block-changes-the-design.md).

---

### Not specifying the iSCSI LIF

**`ontap-san` does not specify `dataLIF`.** Trident **finds the iSCSI LIF a multipath session needs by itself, through Selective LUN Map.** Writing `dataLIF` explicitly produces a warning.

**This follows from Selective LUN Map being enabled by default on a new LUN map.** SLM restricts access to paths on the LUN's owning node and its HA partner, so Trident can derive the usable paths from there. SLM's own behaviour is in [LUN layout decides recovery granularity (日本語)](lun-layout-decides-recovery-granularity.md).

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| PV count is decided by storage capacity | **On `ontap-san` it is decided by the volume-count limit.** You can be unable to create a PV even when capacity remains |
| Adding HA pairs lets you scale PVs without limit | **The cap is 1,000 across all HA pairs**, and only configurations of 6 pairs or fewer are supported for block |
| `ontap-san-economy` is always the better choice | **You lose the ability to apply per-PV Snapshot, SnapMirror, and QoS** |
| The driver can be changed later | It is tied to the StorageClass, so it means **re-creating PVs under a new StorageClass** |
| Setting RWX lets multiple Pods write safely | **A raw block device just becomes visible from multiple nodes.** Arbitration is the cluster filesystem's responsibility |
| Writing the iSCSI LIF into `dataLIF` makes it more certain | **Doing so produces a warning.** Trident derives the path from Selective LUN Map |
| NVMe/TCP works with any Trident backend setting | **Only a REST-based backend.** Not available on ONTAPI / ZAPI |

---

### Primary sources referenced

| Point | Source |
|---|---|
| `ontap-san` creating a FlexVol + LUN per PV, `ontap-san-economy` packing LUNs into a shared FlexVol, the latter being used only when the volume limit would be exceeded, the supported access modes, and NVMe/TCP being REST-only | [NetApp: ONTAP SAN driver overview](https://docs.netapp.com/us-en/trident/trident-use/ontap-san.html) |
| `ontap-san` not specifying `dataLIF`, Trident finding the iSCSI LIF from Selective LUN Map | [NetApp: FSx for ONTAP configuration options and examples](https://docs.netapp.com/us-en/trident/trident-use/trident-fsx-examples.html) |
| Trident and FSx for ONTAP together provisioning block and file persistent volumes | [NetApp: Use Trident with Amazon FSx for NetApp ONTAP](https://docs.netapp.com/us-en/trident/trident-use/trident-fsx.html) |
| The volume-count limit being 500 for second generation with 1 HA pair, 1,000 for 2 or more pairs, and 500 for first generation. FlexGroup constituent volumes counting toward it | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) |
| A volume being the container that holds a LUN | [AWS: Managing FSx for ONTAP volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |
| Block protocols being supported only on file systems with 6 or fewer HA pairs | [AWS: Adding HA pairs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/adding-HA-pairs.html) |
| Selective LUN Map being enabled by default on a new LUN map | [NetApp: Selective LUN Map](https://docs.netapp.com/us-en/ontap/san-admin/selective-lun-map-concept.html) |

---

### Related documents

- [Domain — Block storage](../README.md) — this module's hub
- [Can FSx for ONTAP be a container datastore?](../../../reference/decision-trees/container-datastore-selection.md) — the higher-level decision flow that includes this note's driver choice. It starts from the runtime (Fargate / EC2)
- [When shared block changes the design](when-shared-block-changes-the-design.md) — RWX and the responsibility for write arbitration
- [LUN layout decides recovery granularity](lun-layout-decides-recovery-granularity.md) — Selective LUN Map's behaviour
- [LUNs and igroups are outside the AWS API](block-objects-are-outside-the-aws-api.md) — the control plane Trident uses
- [The deployment type is decided only once](../../../playbooks/02-design/notes/deployment-type-is-decided-once.md) — the 6-HA-pair ceiling
- [Limits and quotas (日本語)](../../../../ja/reference/limits/) — limit values with source and verification date
- [Block storage cross resource map (日本語)](../../../../ja/reference/block-storage-resource-map.md) — public infrastructure as code related to Trident
- [FSx-for-ONTAP-Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) — CloudFormation templates for 5 configurations, including Trident persistent volumes on EKS on EC2. **This note holds the driver-choice and volume-limit judgment; that implementation is the division of labor on this side**
- [Evidence policy](../../../evidence-policy.md)

---

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

## Verify it in your environment

| # | Step | What it tells you |
|---|---|---|
| 1 | Estimate the maximum expected PV count | Whether `ontap-san` is enough, or `ontap-san-economy` is needed |
| 2 | Count volumes with `volume show -vserver <svm>` and subtract those already used for file | The actual headroom available for block PVs |
| 3 | Confirm the file system's generation and HA pair count | Whether the volume limit is 500 or 1,000 |
| 4 | Confirm whether there is a requirement to operate Snapshot or SnapMirror per PV | **If there is, `ontap-san-economy` cannot be chosen** |
| 5 | Create two StorageClasses, one `ontap-san` and one `ontap-san-economy`, and create one PVC against each | Confirm from the `volume show` diff whether volumes increase |
| 6 | If using NVMe/TCP, confirm the backend is configured over REST | **NVMe/TCP is not usable on ONTAPI / ZAPI** |
| 7 | Confirm whether there is a plan to grow to 7 or more HA pairs | **If there is, block PVs cannot be used** |

Do step 5 **in a test environment.** Forgetting to delete created PVs keeps consuming the volume-count headroom.

The volume count in step 2 can be counted with this read-only command.

```bash
ssh <svm-management-endpoint> volume show -vserver <svm> -fields volume
```

### Expected output

```text
Returns the current volume count. Subtracting the count already used for file from the limit
(500, or 1,000 combined) gives the actual headroom available for ontap-san PVs (because one PV
consumes one FlexVol).
```

This command only lists volumes; it changes nothing on the volumes or the PVs. Because the driver is tied to the StorageClass, decide the choice before going into operation.

## Read next

[Does Multi-AZ move an address?](multi-az-moves-a-route-not-an-address.md)
