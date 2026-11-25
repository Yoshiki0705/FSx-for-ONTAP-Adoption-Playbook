---
title: "Split agent memory into three tiers: forgetting has to reach snapshots, backups and clones, not only the original files"
lifecycle: [design, operate]
domains: [data-utilization, data-protection, cost]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html
lang: en
---

# Where should agent memory live, and how do you make it forget?

Split it into short-term, long-term and source-of-truth tiers, and make forgetting reach snapshots, backups and clones.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/data-utilization/notes/agent-memory-tiers-and-forgetting.md) | [English](agent-memory-tiers-and-forgetting.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- How to split agent memory into short-term events, long-term records and a source of truth. For the source-of-truth tier on FSx for ONTAP, the volume tiering policy decides what sits on SSD and what sits in the capacity pool
- That "forgetting" does not end with deleting the original file. While a snapshot holds the file, a measurement shows the deleted file was still readable through S3 Access Points
- How the mechanisms that reduce stored bytes (deduplication, compression, compaction) behave once data has moved to the capacity pool

## What this note does not answer

- The slowness and cost of reading from the capacity pool, as measurements. This note uses only what AWS documents and has not measured it (`open`)
- Whether a given personal-data deletion duty is met. What is written here is technical behavior, not a legal judgment or legal advice
- What AgentCore Memory actually does when a retention period expires. Only the API reference is cited
- Power or energy savings. Only the reduction in stored bytes is covered

## Prerequisite level

intermediate

## Body

<a id="split-agent-memory-into-three-tiers"></a>

[🏠 Repository Top](../../../README.md) | [Domain — Data Utilization](../README.md)

> This is the English translation. Japanese is authoritative for technical accuracy. Please report any discrepancy.

---

### Conclusion

**What goes on Amazon FSx for NetApp ONTAP is the source-of-truth tier of agent memory.** Short-term events (conversation and session records) and long-term records (extracted and consolidated memories) usually live on the agent platform side, and you treat them as derived data that can be rebuilt from the original. For the original tier, the volume tiering policy decides what sits on SSD and what sits in the capacity pool.

**"Forgetting" means deleting records, and deleting the original alone is not enough.** After you delete the original file, a path to read it stays open for as long as a snapshot that contains it remains. Count backups and clones on the same footing.

This note takes the memory and forgetting theme in the AWS CTO's article [Tech predictions for 2027 and beyond](https://www.allthingsdistributed.com/2026/11/tech-predictions-for-2027-and-beyond.html) (2026-11-24) and sets out the decisions it implies on the data side of FSx for ONTAP. It does not reproduce the article, and it adds no new measurement. It is built from links to records that already exist.

> **Evidence**: `documented`. Tiering policies and storage efficiency come from AWS documentation, and the AgentCore Memory retention period comes from the API reference.
> That a deleted file was readable from a snapshot is quoted from a Cyber Resilience Patterns measurement (`verified`, 2026-11-24); this repository did not measure it again.

---

### The Three Tiers of Memory

| Tier | Contents | Where to put it | What deleting has to reach |
|---|---|---|---|
| Short-term events | Conversation and session records | The agent platform's memory service, which has a retention period | Expiry of the retention period, or deletion per user |
| Long-term records | Memories and vectors extracted and consolidated from short-term events | The agent platform's memory service, a vector index | They can be rebuilt from the original, so whether to delete them is decided on the original's side |
| Source of truth | The original files and data | A volume on FSx for ONTAP | The original, snapshots, backups and clones |

**If the original remains, deleting a long-term record does not stop the same memory from being rebuilt.** If forgetting is the intent, delete on the original's side first and do not rebuild the derived data. For designs that handle edge data, the premise of keeping memory, vectors and the source of truth separate is written in section 4 (memory, vectors, the distinction from the source of truth) of ONTAP Edge to Cloud AI's [Agentic AI on AWS](https://github.com/Yoshiki0705/ONTAP-Edge-to-Cloud-AI/blob/main/docs/en/agentic-ai-on-aws.md). Items not confirmed or not implemented are in section 7.

---

### Four Tiering Policy Choices

A volume's tiering policy decides whether data sits on SSD or moves to the capacity pool.

| Policy | Where the data sits |
|---|---|
| `Auto` | Moves cold user data and cold snapshot data to the capacity pool. The default when you create a volume in the Amazon FSx console |
| `Snapshot Only` | Moves only snapshot data to the capacity pool. The default when you create a volume with the AWS CLI, the Amazon FSx API or the ONTAP CLI |
| `All` | Treats all data as cold. Writes land on SSD first and move to the capacity pool in the background |
| `None` | Keeps data on SSD |

The default cooling period is 31 days for `Auto` and 2 days for `Snapshot Only`. You can set the cooling period from 2 to 183 days, and data is tiered 24 to 48 hours after the period passes. File metadata always stays on SSD.

SSD utilization changes the behavior.

| SSD utilization | Tiering behavior |
|---|---|
| 50 % or lower | Only `All` tiers data |
| 90 % or higher | Data read from the capacity pool is not written back to SSD |
| 98 % or higher | Tiering stops |

---

### Mapping Memory Tiers to Policies

The table below is an example mapping limited to the original tier kept on FSx for ONTAP. The right choice depends on your situation, so each row lists what you gain and what you give up.

| What you place | A policy that may fit | What you gain | What you give up |
|---|---|---|---|
| Original data of the source of truth that is read often | `Auto` | Only cold data moves to the capacity pool, and frequently read data stays on SSD | Data past the cooling period is read from the capacity pool, so reads are slower and carry a read cost |
| Old versions and low-frequency history | `Snapshot Only` or `All` | History is kept without using SSD capacity | Re-reading history becomes a read from the capacity pool. With `All`, reading the original also comes from the capacity pool |
| Data that always needs low latency | `None` | Reads are served from SSD | You pay for SSD capacity and cost for the whole data set |

For every row, the slowness and cost of reading data that has moved to the capacity pool are not measured in this note. If you measure it in your own environment, check that you are not putting frequently read data on `All`.

---

### Reducing Stored Bytes

Deduplication, compression and compaction run inline and as background processing on SSD.

- Background processing does not run on data that has moved to the capacity pool. The savings obtained while the data was on SSD are kept
- Storage efficiency cannot be enabled on a DP volume. The savings obtained on the original RW volume are kept at the replication destination
- There is no deduplication across volumes

What can be said here is only the reduction in stored bytes. This note does not state power or energy figures.

---

### How Far Forgetting Has to Reach

**After the original file was deleted, the deleted file was still readable for as long as a snapshot containing it remained.** Cyber Resilience Patterns measured this in [Deletion requests and retained copies](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md).

| Item | Detail |
|---|---|
| Date and environment | 2026-11-24, ap-northeast-1, first generation SINGLE_AZ_1, ONTAP 9.19.1P4 |
| Volume and user | UNIX-style volume, the file system user was root |
| Number of runs | Three reads, and one run of each way of closing the path |
| Tier | `verified` |

The results were as follows.

1. After the file was deleted, a `GetObject` through S3 Access Points on the key `.snapshot/<snapshot name>/<path>` returned the deleted file for as long as a snapshot containing it existed
2. `ListObjectsV2` did not show that key. Because the listing omits it, you cannot conclude the file is gone by looking at a listing
3. Any of these closed the path: deleting the snapshot, setting `snapshot_directory_access_enabled=false` on the volume, or denying `s3:GetObject` on `<access point ARN>/object/.snapshot/*` in the access point policy

**For the access point that an agent's role uses, we recommend placing this deny unless there is a reason to read old versions.** How to write the deny, and why a narrower `Allow` does not restrict access, are in [Which of the two layers narrows an S3 Access Point?](../../security-governance/notes/access-point-authorization-layers.md)

For backups and clones, follow the linked record for how copies other than snapshots are handled. This note adds no new measurement.

What has not been measured (`open`):

- NTFS-style volumes
- Users other than root
- FlexGroup
- Other ONTAP versions

---

### Retention in the Memory Service

AgentCore Memory's `CreateMemory` has `eventExpiryDuration`, in days. The Valid Range in [CreateMemory](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateMemory.html) is 3 to 3650 (checked 2026-11-24, `documented`).

**The description on the same page says "between 7 and 3650 days", which disagrees with the range field.** This note states the value in the range field. Resolving the disagreement waits on AWS updating its documentation. If you use the retention period as a design input, create a memory in your own environment and check whether the boundary value is accepted.

An implementation that lists and deletes records inside a per-user namespace is in Agentic Access-Aware RAG's [episodic memory implementation](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG/blob/main/docker/nextjs/src/lib/agentcore/episodic-memory.ts). The location of `deleteEpisode` is there.

---

### Design Steps

1. For each memory tier, decide where the original lives. Keep derived data in a state where it can be rebuilt from the original
2. For each original volume, decide the tiering policy, and check the cooling period and the SSD utilization thresholds
3. If there is a forgetting requirement, count snapshots, backups and clones among the things to delete
4. On the access point that the agent's role uses, place a deny on `s3:GetObject` for `.snapshot/*`
5. For a memory service that has a retention period, create one in your own environment and check the value

---

## Verify it in your environment

These steps are read-only.

```bash
aws fsx describe-volumes --volume-ids <volume-id> --query "Volumes[0].OntapConfiguration.[TieringPolicy,SnapshotPolicy]"
```

```bash
curl -sk -u <admin-user> "https://<management-endpoint>/api/storage/volumes/<volume-uuid>?fields=snapshot_directory_access_enabled"
```

```bash
aws s3control get-access-point-policy --account-id <account-id> --name <access-point-name> --query Policy --output text
```

```bash
aws fsx describe-backups --filters Name=volume-id,Values=<volume-id>
```

### Expected output

```text
[ { "Name": "AUTO", "CoolingPeriod": 31 }, "<snapshot-policy>" ]
{ "snapshot_directory_access_enabled": true }
{ "Statement": [ ... "Resource": "<access-point-arn>/object/.snapshot/*" ... ] }
{ "Backups": [ ... ] }
```

What you learn: the volume's tiering policy and cooling period, whether access to the snapshot directory is enabled, whether the access point policy denies `.snapshot/*`, and whether there are backups to count among the things to delete.

What you do not learn: the slowness and cost of reading from the capacity pool, whether a deleted file has actually become unreadable, and the behavior on NTFS-style volumes. To confirm that a file cannot be read after deletion, call `GetObject` on the deleted key.

---

### Primary Sources

| Topic | Source |
|---|---|
| Tiering policies, cooling period, SSD utilization thresholds | [AWS: Volume storage capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html) |
| Deduplication, compression, compaction | [AWS: Managing storage efficiencies](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/manage-vol-SE.html) |
| AgentCore Memory retention | [AWS: CreateMemory](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateMemory.html) |
| Measurement of copies that outlive deletion | [Cyber Resilience Patterns: Deletion requests and retained copies](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md) |
| Implementation of episodic memory deletion | [Agentic Access-Aware RAG: episodic-memory.ts](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG/blob/main/docker/nextjs/src/lib/agentcore/episodic-memory.ts) |
| Memory, vectors and the source of truth kept apart | [ONTAP Edge to Cloud AI: Agentic AI on AWS](https://github.com/Yoshiki0705/ONTAP-Edge-to-Cloud-AI/blob/main/docs/en/agentic-ai-on-aws.md) |

---

### Related Documents

- [Domain — Data Utilization](../README.md)
- [Which of the two layers narrows an S3 Access Point?](../../security-governance/notes/access-point-authorization-layers.md)
- [Evidence policy](../../../evidence-policy.md)

---

## Read next

[Research datasets handed to agents are reproduced from a snapshot UUID](reproducible-research-datasets-for-agents.md)
