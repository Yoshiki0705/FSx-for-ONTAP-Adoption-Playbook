---
title: NetApp / AWS primary-source map for FlexCache and storage tuning — the discovery path for design, operation, and build
lifecycle: [design, build, operate, optimize]
domains: [performance, client-access, data-protection]
evidence: documented
source: https://docs.netapp.com/us-en/ontap/flexcache/
lang: en
---

# Primary-source map for FlexCache and storage tuning

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md) | [Domain — performance](../domains/performance/README.md)

---

## Conclusion

**When you design, operate, or build FlexCache and storage tuning on Amazon FSx for NetApp ONTAP, the primary sources are split across several AWS and NetApp documents.** The creation steps are in the AWS ONTAP guide, the cache behavior and recommended practices are in NetApp Technical Reports and docs, and FlexGroup placement is in a separate TR — the grounds for one topic are not always in one place.

**This index puts, per document, "what it answers" and "when in design / operation / build to read it" on a single page.** Where [the performance evidence map](performance-evidence-map.md) indexes the Spokes' measured records, this one indexes **the discovery path to vendor primary sources**.

**This index does not restate the documents' conclusions.** Cache behavior values and recommended settings are misread when separated from version and environment. It states only what each document covers; read the specifics at the link.

> **Tier**: `documented` — each row records the location and scope of a published AWS / NetApp primary source. **This repository has not re-measured or re-verified these documents.** The findings this repository reproduced on real hardware are in [Where to look first when FlexCache reads but will not write (日本語)](../../ja/domains/performance/notes/flexcache-origin-permissions-and-peering-constraints.md) and [FlexCache CLI procedure (NFS) – simplified](flexcache-cli-nfs-simplified.md), where the `verified` / `documented` tiers are assigned.

---

## How to read this index

- **Much of it is version-dependent.** FlexCache write-back is ONTAP 9.15.1 or later, NFSv4 access to a Cache is 9.10.1 or later — availability changes by version. When reading a document, match your own ONTAP version against the version the document assumes.
- **AWS and NetApp docs split the management plane.** FSx for ONTAP has a two-plane structure: the AWS plane (console / FSx for ONTAP API) and the ONTAP plane (REST / CLI). Much of FlexCache and QoS is governed by the ONTAP plane, and some operations have no equivalent parameter in the AWS API.
- **Some PDF sources cannot be fetched programmatically.** Items marked PDF below are listed as pointers to location and scope. The claims this repository makes are grounded in the HTML documents whose text could be confirmed.

---

## FlexCache documents

| Topic | Document | What it answers / when to read it |
|---|---|---|
| What FlexCache is, the FSx for ONTAP configurations (Origin/Cache combinations), choosing write-around / write-back | [AWS: Replicating your data with FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html) | The design entry point. That the Cache is read-writable, that write-back is 9.15.1 or later, and that you choose the mode by read-heavy vs write-heavy |
| FlexCache volume creation steps (LIF gather, cluster peering, SVM peering, Cache creation, mount) | [AWS: Creating a FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-flexcache.html) | At build time. The full shape of the procedure |
| write-back concepts and terms (dirty data, XLD/SLD, DDRS), the contrast with write-around, per-origin limits | [NetApp: Learn about ONTAP FlexCache write-back](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-overview.html) | When considering write-back. The limit difference: 100 per origin for write-around, 10 for write-back |
| Guidelines for using write-back (single-constituent recommendation and so on) | [NetApp: ONTAP FlexCache write-back guidelines](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-guidelines.html) | When designing write-back. The configuration recommendation, and the need to test when used outside the guidelines |
| Access patterns where write-back does / does not help | [NetApp: ONTAP FlexCache write-back use cases](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-use-cases.html) | When estimating the effect of write-back. The relation between writes between OPEN and CLOSE and the performance gain |
| The systematic primary source for FlexCache design and operation (TR-4743) | [NetApp Technical Report TR-4743: FlexCache in ONTAP](https://www.netapp.com/media/7336-tr4743.pdf) (PDF) | When going deeper into design. Cache invalidation, refresh, the network-bound reasoning. Listed as a location pointer, being a PDF |

---

## Storage tuning and placement documents

| Topic | Document | What it answers / when to read it |
|---|---|---|
| How FSx for ONTAP performance is determined (throughput capacity, SSD IOPS, network) | [AWS: Amazon FSx for NetApp ONTAP performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html) | At sizing time. What sets the throughput ceiling |
| Storage tiers and tiering policies (SSD / Capacity Pool) | [AWS: FSx for ONTAP best practices (Prescriptive Guidance)](https://docs.aws.amazon.com/prescriptive-guidance/latest/fsx-ontap-enterprise-deployment/best-practices.html) | When designing the cost-vs-performance trade-off <!-- allow:sales-vocabulary source page title literally contains best practices --> |
| FlexGroup composition and data placement (balanced at creation, not rebalanced afterward) | [NetApp Technical Report TR-4571: FlexGroup volumes best practices](https://www.netapp.com/media/12385-tr4571.pdf) (PDF) | Because a Cache volume is always a FlexGroup, when designing placement for high-file-count workloads. Listed as a location pointer, being a PDF <!-- allow:sales-vocabulary TR-4571 title literally contains best practices --> |
| Access control design with export policies | [AWS Storage Blog: Restrict access using export policies](https://aws.amazon.com/blogs/storage/restrict-access-to-your-amazon-fsx-for-netapp-ontap-volumes-using-export-policies) | When designing NFS access control. Rule order and the meaning of RO/RW |
| throughput ceiling / floor with QoS | [NetApp: Set a throughput ceiling with QoS](https://docs.netapp.com/us-en/ontap/performance-admin/set-throughput-ceiling-qos-task.html) | When designing per-workload ceilings and floors |
| FSx for ONTAP technical detail (Tech Deep Dive) | [NetApp: Amazon FSx for NetApp ONTAP Tech Deep Dive](https://www.netapp.com/ja/pdf.html?item=/ja/media/138603-amazon-fsx-for-netapp-ontap-tech-deep-dive.pdf) (PDF, Japanese) | For an overview in Japanese. Listed as a location pointer, being a PDF; not used as grounds for this repository's claims |

---

## Cluster peering documents

| Topic | Document | What it answers / when to read it |
|---|---|---|
| cluster peer policy (unauthenticated access, minimum passphrase length) | [NetApp: cluster peer policy modify](https://docs.netapp.com/us-en/ontap-cli/cluster-peer-policy-modify.html) | When considering an unauthenticated peer. The constraint that you cannot return to authenticated-required while an unauthenticated peer exists |
| Modifying cluster peer attributes (authentication status, encryption) | [NetApp: cluster peer modify](https://docs.netapp.com/us-en/ontap-cli/cluster-peer-modify.html) | When switching between authenticated / unauthenticated. The change must be reflected on both clusters |

---

## Related documents

- [Where to look first when FlexCache reads but will not write (日本語)](../../ja/domains/performance/notes/flexcache-origin-permissions-and-peering-constraints.md) — the triage this repository reproduced on real hardware
- [FlexCache CLI procedure (NFS) – simplified](flexcache-cli-nfs-simplified.md) — the shortest creation path
- [Performance evidence map](performance-evidence-map.md) — where the Spokes' measured records live
- [Evidence policy](../evidence-policy.md)

---

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md) | [Domain — performance](../domains/performance/README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/reference/netapp-primary-sources-map.md) | [English](netapp-primary-sources-map.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
