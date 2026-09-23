---
title: The migration path to containers or a modernized runtime splits three ways, and all of them converge on the same datastore decision
lifecycle: [assess, migrate]
domains: [block-storage, data-utilization, multiprotocol-identity]
evidence: documented
source: https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns
lang: en
---

# The migration path to containers or a modernized runtime splits three ways

[🏠 Repository home](../../../README.md) | [Playbook 03 — Migration](../README.md)

---

## Conclusion

**There are three paths for moving a workload that uses FSx for ONTAP into containers or a modernized runtime, and whichever one you take, the decision of how the data is reached on FSx for ONTAP converges on the same decision tree.**

The paths split on "what is the input, and where does it move to." **Whether the input is source code, a running VM, or neither (a dedicated tool) changes the usable tools and the reachability form.** But how a container uses FSx for ONTAP once moved — a Trident PV, a host mount, or object access via S3 Access Points — does not depend on the path.

**This split is stated explicitly because a different repository holds the implementation and verification for each path.** This note sorts "which path you came from" and hands off to the convergence point — the decision tree — and to each path's implementation repository. **The detailed procedure and verification for each path are held as authoritative by their respective repositories.**

> **Tier**: `documented` — the path split is based on AWS / NetApp official documentation and each implementation repository's material (confirmed 2026-09-23).
> **This repository has not confirmed the container path on real hardware.** The measurements belong to the EC2 rehost path ([VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP)) only; the container / modernization paths depend on the verification stage of each implementation repository.

---

## The three paths

| # | Path | Input | Moves to | FSx for ONTAP reachability | Where implementation and verification live |
|---|---|---|---|---|---|
| 1 | Modernization from source code | Source code | Containers on Amazon ECS / Amazon EKS | Trident PV (EKS on EC2), host mount (ECS on EC2), object access via S3 Access Points (Fargate) | [FSx-for-ONTAP-Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) |
| 2 | Rehost, decoupling block from EC2 | A running VM / server | Amazon EC2 | iSCSI mount inside the guest OS (block detached from EC2 and placed on FSx for ONTAP) | [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) and [AWS Transform's Finalize is where physical capacity peaks (日本語)](../../../../ja/playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md) |
| 3 | Via a third-party VM conversion tool (NetApp Shift Toolkit v8.0 and the like) | A running VM / virtual disk | Amazon EC2 + FSx for ONTAP | OS disk to Amazon EBS, data disk to FSx for ONTAP; a container reaches it afterward over iSCSI / NFS | **EC2 support is Early Preview (as of 2026-09).** Its maturity differs from the GA paths 1 and 2. See the respective implementation repositories for the general-availability conditions |

**The difference between path 1 and path 2 is the input.** Modernization that takes source code as input (path 1) and rehost that takes a running VM as input (path 2) are separate features even within AWS Transform. **"Containerization" and "block integration on rehost" do not combine into one workflow.** The path that containerizes from source code does not come with the rehost-only block support.

**Path 3 is close to path 2 in that its input is a VM, but its conversion mechanism differs from AWS's managed migration.** NetApp Shift Toolkit v8.0 and the like are examples, converting the OS disk to Amazon EBS and the data disk to FSx for ONTAP using ONTAP's storage efficiency (FlexClone / SnapMirror). **It is placed neutrally as one option.**

**But its maturity differs from paths 1 and 2.** Shift Toolkit v8.0's EC2 support is Early Preview as of 2026-09. When mixing path 3 into a design premised on the GA AWS Transform / MGN (paths 1 and 2), state that maturity gap explicitly. **The version and the general-availability conditions change, so the implementation repository is authoritative**; here it is noted only as existing, with the date it was confirmed (2026-09). See the respective implementation repositories for details.

---

## Where every path converges

**Whichever of the three paths you take, the decision of whether a container uses FSx for ONTAP once moved converges to one place.**

[Whether a container can use FSx for ONTAP as a datastore](../../../reference/decision-trees/container-datastore-selection.md) decides the runtime (Fargate / EC2) and the reachability form (Trident PV / host mount / object access via S3 Access Points). **The container side of paths 1 and 3 converges here.**

Path 2 (EC2 rehost) does not converge, because it mounts iSCSI inside the guest OS rather than in a container. **The decision to decouple block from EC2 is covered by** [Choosing a block protocol and layout (日本語)](../../../../ja/reference/decision-trees/block-protocol-and-layout.md), and its capacity planning by [AWS Transform's Finalize is where physical capacity peaks (日本語)](../../../../ja/playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md).

---

## Where multiprotocol support bears on the path choice

**FSx for ONTAP's multiprotocol support bears on the path choice as freedom in which protocol serves the shared data after modernization.** Because the same data can be served over both NFS and SMB, a share used over SMB before modernization can be read from a modernized container as an NFS PV (Trident `ontap-nas`) — a mid-migration coexistence that holds.

**But the constraints differ per reachability form.** The SMB PV is Windows nodes only, and object access via S3 Access Points requires an app change to the object API. Cross-protocol permission evaluation is covered by [The volume security style decides the permission model](../../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md).

---

## What this note does not answer

| Question | Where it lives |
|---|---|
| Which reachability form a container uses for FSx for ONTAP | [Whether a container can use FSx for ONTAP as a datastore](../../../reference/decision-trees/container-datastore-selection.md) |
| Trident driver choice and the volume limit | [Kubernetes block volumes meet the volume limit (日本語)](../../../../ja/domains/block-storage/notes/kubernetes-block-volumes-and-the-volume-limit.md) |
| The block layout on EC2 rehost | [Choosing a block protocol and layout (日本語)](../../../../ja/reference/decision-trees/block-protocol-and-layout.md) |
| Finalize's capacity peak and irreversibility | [AWS Transform's Finalize is where physical capacity peaks (日本語)](../../../../ja/playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md) |
| Which migration method (SnapMirror / DataSync / host copy) to choose | [Choosing a migration method (日本語)](../../../../ja/reference/decision-trees/migration-method.md) |
| **The detailed procedure and real-hardware verification for paths 1 and 3** | **The respective implementation repositories are authoritative.** This note is a landing point and does not hold the path internals |
| **AWS Transform modernization's supported languages and scope** | The implementation repository [FSx-for-ONTAP-Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) |

---

## Common misconceptions

| Misconception | Reality |
|---|---|
| Containerization and rehost block integration can be had together in one migration | **They are separate features.** Containerizing from source code (path 1) does not come with the rehost-only block support (path 2) |
| A different path changes how a container uses FSx for ONTAP | **They converge.** The container side of paths 1 and 3 decides the reachability form with the same decision tree |
| EC2 rehost (path 2) is also judged by the container decision tree | **It is not.** Path 2 mounts iSCSI inside the guest OS, a different reachability form from a container PV |
| Third-party tools (Shift Toolkit v8.0 and the like) can be treated on par with the GA paths | **Their maturity differs.** EC2 support is Early Preview as of 2026-09, a different premise from the GA paths 1 and 2. A neutral option, but state the maturity gap |
| Multiprotocol means you can move without regard to protocol | **The constraints differ per reachability form.** The SMB PV is Windows nodes only, and object access via S3 Access Points requires an app change |

---

## Related documents

- [Playbook 03 — Migration](../README.md) — this module's hub
- [Whether a container can use FSx for ONTAP as a datastore](../../../reference/decision-trees/container-datastore-selection.md) — the decision tree paths 1 and 3 converge on
- [AWS Transform's Finalize is where physical capacity peaks (日本語)](../../../../ja/playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md) — capacity planning for path 2
- [Choosing a block protocol and layout (日本語)](../../../../ja/reference/decision-trees/block-protocol-and-layout.md) — the block layout for path 2
- [Kubernetes block volumes meet the volume limit (日本語)](../../../../ja/domains/block-storage/notes/kubernetes-block-volumes-and-the-volume-limit.md) — Trident driver choice
- [Choosing a migration method (日本語)](../../../../ja/reference/decision-trees/migration-method.md) — the migration method for the data itself
- [FSx-for-ONTAP-Container-Datastore-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Container-Datastore-Patterns) — path 1 implementation (five configurations as CloudFormation templates)
- [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) — path 2 implementation and measurements
- [Evidence Policy](../../../evidence-policy.md)

---

[🏠 Repository home](../../../README.md) | [Playbook 03 — Migration](../README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/playbooks/03-migrate/notes/migration-paths-to-containers.md) | [English](migration-paths-to-containers.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
