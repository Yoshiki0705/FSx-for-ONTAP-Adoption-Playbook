---
title: Which workloads do the QoS ceiling and burst help — mapping them to use cases, and choosing between QoS and other ways to cap throughput
lifecycle: [design, operate, optimize]
domains: [performance]
evidence: documented
source: https://aws.amazon.com/blogs/storage/using-quality-of-service-in-amazon-fsx-for-netapp-ontap/
lang: en
---

# Which workloads do the QoS ceiling and burst help?

A throughput ceiling (QoS ceiling) and burst are ways to isolate competing workloads and to absorb short spikes without a permanent capacity increase. This note sorts out which workloads to apply them to, and how to choose between them and other ways to cap throughput.

## What you will learn

- Which kinds of workloads, and which phase of them, the QoS ceiling and burst apply to.
- How changing the burst defaults (ONTAP 9.19.1 and later) helps per use case.
- That QoS is not the only way to cap throughput, and the angles for choosing between it and the alternatives.

## What this note does not answer

- An adoption case from a specific user's own environment as such (the use-case mapping in this note is a set of design patterns, not a sourced adoption case; the body states this distinction explicitly).
- Recommended ceiling or burst values for each workload (that is an area to measure and decide per environment).
- A quantified effect of QoS on overall application cost.

## Prerequisite level

intermediate

## Body

[🏠 Repository home](../../../README.md) | [Domain — Performance](../README.md)

---

### Conclusion

**The QoS ceiling is a way to stop one workload from crowding out the others, and burst is a buffer for absorbing short spikes without a permanent capacity increase.** Both apply when several workloads or tenants share a single file system.

**Now that the burst defaults can be changed (ONTAP 9.19.1 and later, available on Amazon FSx for NetApp ONTAP too; [verification record](qos-burst-defaults-are-user-modifiable.md)), the way the ceiling is exceeded can be tuned per use case.** Beyond the ceiling itself, you can choose the shape of the buffer — the width, duration, and absolute magnitude of the excess.

> **Tier**: The role of QoS in this section (isolating noisy neighbors, keeping a workload below a set amount even when there is no contention) is `documented`. The source is [AWS: Using Quality of Service in Amazon FSx for NetApp ONTAP](https://aws.amazon.com/blogs/storage/using-quality-of-service-in-amazon-fsx-for-netapp-ontap/). Much of the mapping to use cases (which workload it helps and how) is `hypothesis` (a design-level expectation, untested), stated explicitly as such throughout the body.

![AWS integration where the QoS ceiling and burst apply: Oracle / SAP / SQL Server on Amazon EC2 connect to Amazon FSx for NetApp ONTAP over NFS / iSCSI / SMB, Amazon EventBridge and AWS Lambda configure QoS automatically via ONTAP REST, and Amazon CloudWatch monitors throughput](../../../../_assets/images/qos-ceiling-use-cases.svg)

Figure 1: The AWS integration patterns where the QoS ceiling and burst apply (the integrations include design-level expectations)

---

### Where the ceiling and burst take effect

**The QoS ceiling takes effect where several workloads share a single file system.** `documented`: AWS lists that QoS lets you build a multi-workload / multi-tenant file system while avoiding noisy neighbors, and that it can keep a workload from exceeding a set amount even when there is no contention (source above).

**Burst takes effect for workloads that stay within the ceiling in steady state but spike at the moment of startup or switchover.** `documented`: NetApp explains that absorbing a temporary spike such as a database startup or the boot of many VMs, without a permanent capacity increase, is the role of burst ([ONTAP QoS throughput guarantee](https://docs.netapp.com/us-en/ontap/performance-admin/guarantee-throughput-qos-task.html)).

**For multi-tenant setups, nested QoS allocates ceilings hierarchically.** `documented`: Since ONTAP 9.18.1, a policy can be assigned to both an SVM and the volumes / qtrees beneath it, and the most restrictive one applies ([QoS policy group assignment restrictions](https://docs.netapp.com/us-en/ontap/performance-admin/policy-group-assignment-restrictions.html)). It can be used in a design that subdivides an SVM-wide ceiling down to a tenant's volumes. Wherever burst is set in the hierarchy, the effective excess is bounded by the tightest ceiling.

---

### Mapping to use cases

**The following table is a set of design patterns, not a sourced adoption case.** It separates whether a workload is listed as a target for FSx for ONTAP (`documented`) from how burst is applied to it (`hypothesis`).

| Workload | Applying the ceiling and burst | Workload tier | Mapping tier |
|---|---|---|---|
| Oracle / SQL Server / SAP (on Amazon EC2, over NFS / iSCSI / SMB) | Cap batch and reporting work, leaving bandwidth for OLTP. Absorb the DB-startup spike with burst | documented (target workload) | hypothesis (mapping) |
| VMware datastore (on Amazon EC2) | Absorb the boot-storm spike with burst, isolate per cluster with a ceiling | hypothesis | hypothesis |
| VDI (platform on Amazon EC2) | Burst for the login storm, a per-pool ceiling for fairness | hypothesis | hypothesis |
| EDA (semiconductor design) grid | A ceiling per project team on a shared file system, burst for the compile-time spike | documented (target workload) | hypothesis (mapping) |
| SaaS multi-tenant (one file system, separated by SVM / qtree) | Layer the ceilings with nested QoS, varying the burst shape per tenant to express SLA tiers | documented (SaaS use + nested QoS) | hypothesis (burst tiering) |

**What changing the burst defaults helps with is the tuning range of this "mapping".** To bring the ceiling closer to a hard wall (strict metering / chargeback), lower burst-percent; to allow a longer startup spike (a latency-sensitive burst type), extend burst-duration — these adjustments are possible on ONTAP 9.19.1 and later ([verification record](qos-burst-defaults-are-user-modifiable.md)). These are `hypothesis` (design-level expectations).

---

### AWS services that integrate

**The ceiling and burst are operated in combination with surrounding AWS services.** The following are all combinations that work as mechanisms (`hypothesis`, though the role of each service itself is `documented`).

| Integration | Role |
|---|---|
| Amazon CloudWatch (FSx for ONTAP metrics) | Monitor the throughput time series and see whether the ceiling is being hit. There is no burst-specific metric, however, so it is read from the throughput time series |
| ONTAP REST API automation (AWS Lambda / Amazon EventBridge) | Configure per-tenant ceilings and bursts automatically at provisioning time. The configuration route is ONTAP REST ([verification record](qos-burst-defaults-are-user-modifiable.md)) |
| Data ingestion via AWS DataSync / SnapMirror | Cap ingestion / replication so it does not crowd out production reads, relaxing it with burst only during the catch-up window |

**Native CloudWatch metrics have no dimension that names a QoS policy group.** When you want to monitor QoS per policy group or per workload, the route is the counter-manager → Lambda → CloudWatch custom-metric collector that [FSx-for-ONTAP-Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/blob/main/docs/en/monitoring-design.md#per-policy-group-qos-monitoring) provides. It polls the ONTAP counter manager and publishes per-workload `FSxONTAP/QoS` metrics. The implementation detail (which counters are collected, how a rate is derived from cumulative raw values) lives on the Spoke side. This note holds who-it-helps and when-it-matters; it cites the Spoke for the implementation.

> **Monitoring note**: There is no burst-specific counter in ONTAP, so what is collected is effective throughput / IOPS. "Pinned at the ceiling" is visible, but "currently bursting" is inferred from the time series, not measured directly (Spoke live verification, ONTAP 9.19.1P2).

![Two-plane management of QoS burst: the AWS Management Console / FSx for ONTAP AWS API have no burst configuration parameter, and the burst of Amazon FSx for NetApp ONTAP can be set only from Amazon EC2 (a client inside the VPC) via ONTAP REST / CLI](../../../../_assets/images/qos-burst-two-plane.svg)

Figure 2: The two-plane management of burst configuration (the AWS management plane has no corresponding parameter; it is set from the ONTAP management plane)

---

### Choosing between QoS and other ways to cap throughput

**QoS is not the only way to isolate a workload and cap throughput.** Each has its strengths and weaknesses, and you choose by use case. No single one is always superior.

| Means | Where it fits | Trade-off (this means' constraint) |
|---|---|---|
| QoS policy group (ceiling / burst) | Isolating at the storage layer while still sharing a single file system | A storage-layer control that does not see the meaning of the application's requests. Configured on the ONTAP management plane |
| Application-layer rate limiting | Fine-grained control by request type or priority | Requires implementation per application. Does not prevent storage contention itself |
| Separate file systems | Full physical isolation between tenants | More fixed cost and more to operate. Loses the benefits of data sharing and cloning |
| Separate throughput-capacity allocation | Securing guaranteed bandwidth | Can be divided only at the granularity of the capacity setting, coarser than per-workload. Raises cost |

**How to choose**: First, split on "is the storage layer enough, or do you need to see the meaning of the requests?" If you want to control by request type, choose the application layer; if you only want to suppress storage contention, choose QoS. If full isolation is a requirement, consider separate file systems; if guaranteed bandwidth is a requirement, consider separate capacity. QoS is not mutually exclusive with these — they can be combined. Note that a file system with only one workload and no contention does not need a ceiling at all.

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| A QoS ceiling makes a workload faster | **It does not make it faster.** It is a way to hold a workload down with a ceiling so it does not crowd out others. To guarantee bandwidth, there is a separate floor |
| Burst is spare bandwidth available at any time | **It is a buffer that lets you temporarily exceed the ceiling, within the range of accumulated credit.** The default is +50% for 1 second |
| The burst defaults cannot be changed | **They can be changed on ONTAP 9.19.1 and later.** Available on FSx for ONTAP too ([verification record](qos-burst-defaults-are-user-modifiable.md)). Not possible on 9.18.1 and earlier |
| The use cases listed here are adoption cases | **They are design patterns.** The target workloads are listed officially, but the burst mapping is an expectation (hypothesis) |
| QoS is the only choice for capping | **Application-layer rate limiting, separate file systems, and separate capacity are also means.** Choose by use case |

---

### Primary sources referenced

| Point | Source |
|---|---|
| That QoS achieves multi-workload / multi-tenant use while avoiding noisy neighbors, and the use of keeping a workload below a set amount even without contention | [AWS: Using Quality of Service in Amazon FSx for NetApp ONTAP](https://aws.amazon.com/blogs/storage/using-quality-of-service-in-amazon-fsx-for-netapp-ontap/) |
| The role of burst in absorbing DB-startup and VM-boot spikes without a permanent capacity increase, and that the defaults can be changed on 9.19.1 and later | [NetApp: ONTAP QoS throughput guarantee](https://docs.netapp.com/us-en/ontap/performance-admin/guarantee-throughput-qos-task.html) |
| Nested QoS (9.18.1 and later, hierarchical assignment across SVM / volume / qtree, most restrictive applies) | [NetApp: QoS policy group assignment restrictions](https://docs.netapp.com/us-en/ontap/performance-admin/policy-group-assignment-restrictions.html) |
| The target workloads for FSx for ONTAP (Oracle / SAP / VMware / SQL Server, EDA and others) | [AWS: FSI Services Spotlight — FSx for ONTAP](https://aws.amazon.com/blogs/industries/fsi-services-spotlight-featuring-amazon-fsx-for-netapp-ontap) |
| Confirmation on a live system that the burst defaults are user-modifiable on FSx for ONTAP | [The QoS burst defaults are user-modifiable](qos-burst-defaults-are-user-modifiable.md) |

---

### Related documents

- [Domain — Performance](../README.md) — the hub for this module
- [The QoS burst defaults are user-modifiable](qos-burst-defaults-are-user-modifiable.md) — the live-system verification record of whether the feature works (the prerequisite for this note)
- [Evidence Policy](../../../evidence-policy.md)

---

[🏠 Repository home](../../../README.md) | [Domain — Performance](../README.md)

---

## Verify it in your environment

**Before mapping to use cases, first confirm on your own file system whether contention is actually occurring.**

| # | Step | What it confirms |
|---|---|---|
| 1 | Look at the throughput time series per volume in Amazon CloudWatch | Which workload spikes when. Whether the ceiling is being hit |
| 2 | Take stock of whether contending workloads share a single file system | Whether there is a target that should be isolated with QoS |
| 3 | Create a verification QoS policy group with a ceiling and confirm the behavior on a non-target volume | How the ceiling and burst behave ([the steps in the verification record](qos-burst-defaults-are-user-modifiable.md#confirming-this-in-your-own-environment)) |
| 4 | Compare against other ways to cap throughput (application layer / separation) and choose the one that fits the requirement | Whether the storage layer is enough, or you need to see the meaning of the requests |

Step 3 is the same procedure as the [verification record](qos-burst-defaults-are-user-modifiable.md). **Directly changing the policy of a production volume changes its I/O behavior immediately, so run the verification on a non-target volume.**

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/performance/notes/qos-ceiling-burst-use-cases.md) | [English](qos-ceiling-burst-use-cases.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
