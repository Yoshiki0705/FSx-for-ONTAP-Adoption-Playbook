# Domain — Block Storage

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/block-storage/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Covers designing, building, and operating LUNs and NVMe namespaces served over iSCSI and NVMe/TCP. Unlike a file share, **consistency and path management stay on the host side.** Where that boundary falls is what this module is about.

**To get something running first, start with [Block storage running in about thirty minutes](quickstart.md).** One CloudFormation template and three ONTAP REST scripts take you to a LUN reached over iSCSI with multipath assembled ([`examples/block-storage/`](../../../../examples/block-storage/)).

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | Whether to use iSCSI or NVMe/TCP, and what narrows the choice first | [The block protocol choice is narrowed before you make it](../../../ja/domains/block-storage/notes/protocol-choice-is-bounded-before-you-choose.md) (日本語) |
| 2 | How to lay LUNs out across volumes, and whether one LUN per volume is right | [LUN layout decides recovery granularity](../../../ja/domains/block-storage/notes/lun-layout-decides-recovery-granularity.md) (日本語) |
| 3 | How much of a block deployment infrastructure as code can reach | [LUNs and igroups sit outside the AWS API](../../../ja/domains/block-storage/notes/block-objects-are-outside-the-aws-api.md) (日本語) |
| 4 | Where capacity is counted more than once, and what happens when writes stop | [Capacity is counted in three places](../../../ja/domains/block-storage/notes/capacity-is-counted-in-three-places.md) (日本語) |
| 5 | How many paths are needed, and who is responsible for them | [Paths are the failover mechanism](../../../ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md) (日本語) |
| 6 | How far back a snapshot of a LUN can actually recover | [A snapshot of a LUN is crash-consistent by default](../../../ja/domains/block-storage/notes/a-snapshot-of-a-lun-is-crash-consistent.md) (日本語) |
| 7 | Where Amazon EBS is sufficient and where shared block changes the design | [When shared block changes the design](../../../ja/domains/block-storage/notes/when-shared-block-changes-the-design.md) (日本語) |
| 8 | What constrains block persistent volumes on Kubernetes | [Kubernetes block volumes meet the volume limit](../../../ja/domains/block-storage/notes/kubernetes-block-volumes-and-the-volume-limit.md) (日本語) |
| 9 | How to read and how to measure block performance figures | [Reading a published benchmark](../../../ja/domains/block-storage/notes/when-shared-block-changes-the-design.md#公開ベンチマークの読み方) (日本語) |
| 10 | What changes on Multi-AZ, and whether block reaches across a peering | [Multi-AZ moves a route, not an address](../../../ja/domains/block-storage/notes/multi-az-moves-a-route-not-an-address.md) (日本語) |
| 11 | Whether I/O stops during a failover, and whether iSCSI and NVMe/TCP differ | [The measured failover](../../../ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md#実測したフェイルオーバー) (日本語) |
| 12 | Whether there is access control beyond igroups | [igroups are not the only access control](../../../ja/domains/block-storage/notes/igroups-are-not-the-only-access-control.md) (日本語) |
| 13 | Whether a database spanning several LUNs can be backed up without quiescing it | [A database on LUNs recovers without quiescing](../../../ja/domains/block-storage/notes/a-database-on-luns-recovers-without-quiescing.md) (日本語) |
| 14 | What block monitoring shows, and whether per-LUN visibility exists | [What block monitoring shows](../../../ja/domains/block-storage/notes/what-block-monitoring-shows.md) (日本語) |
| 15 | Whether Fibre Channel can be used | _not yet written_ (the [glossary FC entry](../../../ja/reference/glossary/README.md) states what is documented) |
| 16 | How to just run it and see | [Block storage running in about thirty minutes](quickstart.md) |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../../ja/domains/block-storage/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |
| [`quickstart.md`](quickstart.md) | Walkthrough for the smallest configuration. The runnable artifacts are in [`examples/block-storage/`](../../../../examples/block-storage/) |
| [`checklists/`](../../../ja/domains/block-storage/checklists/) | Checklists for field use |

---

## How to read this

Always check the `evidence` field in each note's frontmatter.

| Tier | Meaning |
|---|---|
| `verified` | Reproduced by the author in the stated environment. `verified_on` gives the date |
| `documented` | Stated in vendor / AWS documentation. `source` gives the reference |
| `field-observation` | Observed once in the field, not reproduced. Do not generalize |
| `hypothesis` | Reasoned expectation, untested |

See the [Evidence Policy](../../evidence-policy.md) for the full criteria.

**A `verified` tier in this module means observed behavior, not a performance figure.** The verification ran on minimum 384 MBps configurations — one Single-AZ and one Multi-AZ — and recorded no throughput or IOPS numbers. How to read published performance figures is covered in [Reading a published benchmark](../../../ja/domains/block-storage/notes/when-shared-block-changes-the-design.md#公開ベンチマークの読み方) (日本語).

**Failover timings are the one exception.** Those describe availability behaviour rather than performance, so they were measured; the conditions are stated in full inside [the measured failover](../../../ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md#実測したフェイルオーバー) (日本語).

---

## Related

- [Block storage resource map](../../../ja/reference/block-storage-resource-map.md) — index of AWS and NetApp primary sources and public infrastructure as code
- [Decision tree: block protocol and layout](../../../ja/reference/decision-trees/block-protocol-and-layout.md)
- [Comparison: block storage options](../../../ja/reference/comparison/block-storage-options.md)
- [Browse by lifecycle](../../navigation.md#lifecycle-axis--playbooks)
- [Navigation Guide](../../navigation.md)
- [Glossary](../../../ja/reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/block-storage/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
