---
title: "Reproduce a research dataset handed to an agent from a snapshot UUID: attach S3 Access Points to a per-experiment clone"
lifecycle: [design, build, operate]
domains: [data-utilization, data-protection]
evidence: documented
source: https://aws.amazon.com/about-aws/whats-new/2026/11/amazon-fsx-for-netapp-ontap-additional-resources/
lang: en
---

# How do you reproduce the research data an agent read, with the same input later?

Take a snapshot per dataset version and record its name and UUID. Let the agent read only through the alias of S3 Access Points attached to a per-experiment clone.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/data-utilization/notes/reproducible-research-datasets-for-agents.md) | [English](reproducible-research-datasets-for-agents.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That three pieces fix the input an agent receives: a snapshot per version, a FlexClone per experiment, and S3 Access Points attached to the clone
- Which identifiers to keep in the experiment record (the snapshot UUID, the clone name, the access point ARN and others)
- That clone creation takes longer on datasets with many small files, which affects how many experiments you run in parallel
- The order of cleanup, and the condition under which the parent volume cannot be deleted after you delete a clone

## What this note does not answer

- Attaching an access point to an NTFS-style clone (not measured, `open`)
- Which resource CloudTrail records for operations through a clone's access point (not measured, `open`)
- Whether you may handle research subjects' or personal data. What is written here is technical behavior, not a legal judgment or legal advice
- Version rotation of datasets, the volume-count limit, and the console creation route. These are in [Dataset versions and experiment branches](../../../../ja/domains/data-utilization/notes/dataset-versions-and-experiment-branches.md) (日本語) and [A console clone attaches S3 Access Points in minutes](../../../../ja/domains/data-utilization/notes/a-console-clone-attaches-s3-access-points-in-minutes.md) (日本語)

## Prerequisite level

advanced

## Body

<a id="reproduce-a-research-dataset-from-a-snapshot-uuid"></a>

[🏠 Repository Top](../../../README.md) | [Domain — Data Utilization](../README.md)

> This is the English translation. Japanese is authoritative for technical accuracy. Please report any discrepancy.

---

### Conclusion

**When you hand research data to an agent, take a snapshot for each dataset version and record its name and UUID, create a FlexClone for each experiment, and let the agent read only through the alias of the S3 Access Points attached to the clone.** If the experiment record keeps the identifiers, the same input can be rebuilt from the same snapshot.

This note takes the reproducibility theme in the AWS CTO's article [Tech predictions for 2027 and beyond](https://www.allthingsdistributed.com/2026/11/tech-predictions-for-2027-and-beyond.html) (2026-11-24), on researchers and agents working together, and sets out the decisions it implies on the data side of Amazon FSx for NetApp ONTAP. It does not reproduce the article, and it adds no new measurement. It is built from links to records that already exist.

> **Evidence**: `documented`. Each step in the flow cites a measurement (`verified`) or documentation (`documented`) at the link. This repository did not measure them again.
> The environment and date of each measurement are written at the step. Ranges that were not measured are marked `open`.

---

### The Reproduction Flow

1. Take a snapshot for each version, and record the snapshot name and UUID
2. Create a FlexClone for each experiment. From here on, the volume a clone is made from is called the parent volume
3. Attach S3 Access Points to the clone
4. The agent reads only through the alias of that access point
5. In the experiment record, keep the parent volume UUID, the snapshot UUID, the clone name, the access point ARN, the IAM principal and the CloudTrail event IDs
6. To reproduce, rebuild from the same snapshot
7. For cleanup, detach the access point and then delete the clone

#### Step 3: S3 Access Points on a clone

S3-Burst on ONTAP Files measured this in its [S3 Access Points interoperability record](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/en/reference/limits/s3ap-interoperability.md).

| Item | Detail |
|---|---|
| Date and environment | 2026-08-26, ap-northeast-1, ONTAP 9.18.1P3D1, UNIX style |
| Tier | `verified` |

The results were as follows.

- A FlexClone of a volume that had an access point attached could be created
- An access point could be attached to the clone
- LIST and GET through the clone's access point succeeded
- The sha256 of a 256 MiB file matched the parent volume

The same record shows that a PUT to the clone is not visible on the parent volume. Output an experiment writes to the clone is not visible from the parent volume.

#### Step 2: Declaring it in a template

In the [What's New](https://aws.amazon.com/about-aws/whats-new/2026/11/amazon-fsx-for-netapp-ontap-additional-resources/) of 2026-11-23, clones became creatable from the Amazon FSx API and AWS CloudFormation. You specify `CloneConfiguration` in the `OntapConfiguration` of `CreateVolume`. Step 2 can be declared in a template. The console route is in [A console clone attaches S3 Access Points in minutes](../../../../ja/domains/data-utilization/notes/a-console-clone-attaches-s3-access-points-in-minutes.md) (日本語).

#### Step 7: Cleanup

S3 Access Points Serverless Patterns records the following in [Volume lifecycle pitfalls](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/agent/pitfalls-volume-lifecycle.md) (a record measured on 2026-08-15).

- When you create a clone with the ONTAP REST API, `clone.is_flexclone: true` is required
- When you delete a clone that has not been split, the deleted clone stays in the recovery queue. The default is 12 hours. During that time the parent volume cannot be deleted

Detach the access point, then delete the clone. If you plan to delete the parent volume, order the steps with the recovery queue residue in mind.

---

### How Many Experiments to Run in Parallel

Cyber Resilience Patterns gives clone creation times in its [recovery measurement results](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/en/recovery-measurement-results.md).

| Dataset | Median clone creation time |
|---|---|
| Large file, 1 GiB | 1.5 seconds |
| Large file, 10 GiB | 2.5 seconds |
| Large file, 50 GiB | 4.0 seconds |
| About 80,000 small files (10 GiB) | 193 seconds |

Each is the median of four runs. They were measured on 2026-11-18 and 2026-11-19 on a verification file system in Tokyo. They are a sample run, not a production estimate.

**With many small files, clone creation is slower even at the same 10 GiB.** The reason is inference (`hypothesis`) in that record as well. Decide how many experiments to run in parallel from clone creation measured on your own dataset.

---

### Auditing

An operation through S3 Access Points does not leave the requesting principal in the ONTAP file access audit log. Cyber Resilience Patterns records this as E-018 in its [grounds register](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/agent/evidence-ledger.json) (`verified`).

Keep who read the data with CloudTrail data events. That is why the experiment record includes CloudTrail event IDs. Which resource CloudTrail records for operations through a clone's access point has not been measured (`open`).

---

### Reading Old Versions

Through a clone's access point as well, you may be able to read the contents of a snapshot with `.snapshot/<snapshot name>/<path>`. The measurement on the original volume is in Cyber Resilience Patterns' [Deletion requests and retained copies](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md) (2026-11-24, `verified`). There, a `GetObject` on the `.snapshot/<snapshot name>/<path>` key could read the file.

**It has not been measured on a clone (`open`).** If the agent must not read another version, deny `s3:GetObject` on `<access point ARN>/object/.snapshot/*` in the access point policy. How to write it is in [Which of the two layers narrows an S3 Access Point?](../../security-governance/notes/access-point-authorization-layers.md)

```json
{
  "Sid": "DenySnapshotDirectoryReads",
  "Effect": "Deny",
  "Principal": "*",
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:ap-northeast-1:123456789012:accesspoint/<access-point-name>/object/.snapshot/*"
}
```

---

### The Boundary with AWS HealthOmics

The inputs and outputs of a HealthOmics run are Amazon S3 URIs, and S3 Access Points of FSx for ONTAP cannot be specified. S3 Access Points Serverless Patterns records this as E-009 in its [grounds register](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/agent/evidence-ledger.json) (`documented`).

No documentation describes a way to mount your own file system into a run's tasks. That is E-014 in the same register (`open`). Where genomics and HPC pipeline data lives is covered in [Genomics pipeline data lives in three places](../../../../ja/domains/data-utilization/notes/where-genomics-pipeline-data-lives.md) (日本語).

---

### Collaboration Across Institutions

S3 Access Points can be attached only to volumes in the same account and the same Region. The conditions are in [FSx for ONTAP S3 AP is not simply "S3"](../../../../ja/domains/data-utilization/notes/s3-access-point-constraints.md) (日本語).

For another institution's data, receive it with SnapMirror, and then attach the access point to the receiving volume or to a clone of it.

---

### The Per-Researcher Clone Pattern

Pattern 4 (branching a research dataset) in S3 Access Points Serverless Patterns' [FlexClone serverless patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/guides/flexclone-serverless-patterns-en.md) covers creating a FlexClone per researcher so the shared data stays as one copy.

---

### What Has Not Been Measured

| Item | Tier |
|---|---|
| Attaching an access point to an NTFS-style clone | `open` |
| Which resource CloudTrail records for operations through a clone's access point | `open` |
| Whether the contents of `.snapshot` are readable through a clone's access point | `open` |

---

## Verify it in your environment

These steps are read-only.

```bash
aws fsx describe-snapshots --filters Name=volume-id,Values=<volume-id>
```

```bash
curl -sk -u <admin-user> "https://<management-endpoint>/api/storage/volumes?clone.is_flexclone=true&fields=clone.parent_snapshot"
```

```bash
aws fsx describe-s3-access-point-attachments
```

```bash
aws s3control get-access-point-policy --account-id <account-id> --name <access-point-name> --query Policy --output text
```

### Expected output

```text
{ "Snapshots": [ { "SnapshotId": "<snapshot-id>", "Name": "<snapshot-name>", ... } ] }
{ "records": [ { "name": "<clone-name>", "uuid": "<clone-uuid>", "clone": { "parent_snapshot": { "name": "<snapshot-name>", "uuid": "<snapshot-uuid>" } } } ] }
{ "S3AccessPointAttachments": [ { "Name": "<access-point-name>", ... } ] }
{ "Statement": [ ... ] }
```

What you learn: the snapshot ID and name for each version, the snapshot each clone came from, the access point attached to the clone, and whether the access point policy denies `.snapshot/*`.

What you do not learn: whether the contents of `.snapshot` are actually readable through the clone's access point, how long clone creation takes, and which resource CloudTrail records.

---

### Primary Sources

| Topic | Source |
|---|---|
| Creating clones from CloudFormation and the Amazon FSx API | [What's New 2026-11-23](https://aws.amazon.com/about-aws/whats-new/2026/11/amazon-fsx-for-netapp-ontap-additional-resources/) |
| Reading through S3 Access Points on a clone, and matching content | [S3-Burst on ONTAP Files: S3 Access Points interoperability](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/en/reference/limits/s3ap-interoperability.md) |
| Clone cleanup and the recovery queue | [S3 Access Points Serverless Patterns: Volume lifecycle pitfalls](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/agent/pitfalls-volume-lifecycle.md) |
| Clone creation times | [Cyber Resilience Patterns: Recovery measurement results](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/en/recovery-measurement-results.md) |
| The requesting principal not appearing in the audit log | [Cyber Resilience Patterns: grounds register](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/agent/evidence-ledger.json) |
| Reading old versions | [Cyber Resilience Patterns: Deletion requests and retained copies](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md) |
| HealthOmics inputs and outputs | [S3 Access Points Serverless Patterns: grounds register](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/agent/evidence-ledger.json) |
| Per-researcher clones | [S3 Access Points Serverless Patterns: FlexClone serverless patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/guides/flexclone-serverless-patterns-en.md) |

---

### Related Documents

- [Domain — Data Utilization](../README.md)
- [Can a dataset version go on a scheduled snapshot?](../../../../ja/domains/data-utilization/notes/dataset-versions-and-experiment-branches.md) (日本語)
- [Does the wait to attach S3 Access Points to a clone change with how you create it?](../../../../ja/domains/data-utilization/notes/a-console-clone-attaches-s3-access-points-in-minutes.md) (日本語)
- [Evidence policy](../../../evidence-policy.md)

---

## Read next

[Can a dataset version go on a scheduled snapshot?](../../../../ja/domains/data-utilization/notes/dataset-versions-and-experiment-branches.md) (日本語)
