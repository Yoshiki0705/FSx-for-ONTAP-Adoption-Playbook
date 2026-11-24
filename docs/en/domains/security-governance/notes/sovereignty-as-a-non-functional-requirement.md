---
title: "Sovereignty is a per-workload non-functional requirement: isolation and control are different things"
lifecycle: [design, operate]
domains: [security-governance, data-protection]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copy-backups.html
lang: en
---

# What does Amazon FSx for NetApp ONTAP data sovereignty ask you to decide per workload?

Decide sovereignty per workload as a non-functional requirement, and pay for it in cost, performance, and recoverability. Isolation and control are different things.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/security-governance/notes/sovereignty-as-a-non-functional-requirement.md) | [English](sovereignty-as-a-non-functional-requirement.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That sovereignty splits into seven axes to decide: data location, key management, replica and backup destinations, management-plane access, model and inference location, per-deployment evidence, and movement drills
- That isolation (placing data somewhere else) and control (being able to decide who holds the keys, the copies, and the management plane) are different things
- Where the existing records in this Hub and in other repositories such as Cyber Resilience Patterns sit for each of the seven axes, and which tier (`documented`, `verified`, `hypothesis`, `open`) each one has

## What this note does not answer

- Legal, compliance, or regulatory judgments
- The result of calling the Amazon FSx API in the AWS European Sovereign Cloud (not done, because it needs an account in that partition)
- Whether FSx for ONTAP can use a key from an external key store
- How long moves take that have not been measured, such as SnapMirror from Tokyo to Osaka or a copy to another account

## Prerequisite level

advanced

## Body

<a id="sovereignty-is-a-per-workload-non-functional-requirement-isolation-and-control-are-different-things"></a>

[🏠 Repository Top](../../../README.md) | [Domain Security & Governance](../README.md)

> This is the English translation. Japanese is authoritative for technical accuracy. Please report any discrepancy.

---

### Conclusion

**Decide sovereignty per workload, as a non-functional requirement.** The more you restrict location, hold your own keys, and narrow copy destinations, the more it costs, the fewer Regions and features you can use, and the more operating effort it takes.

The AWS CTO's blog post [Tech predictions for 2027 and beyond](https://www.allthingsdistributed.com/2026/11/tech-predictions-for-2027-and-beyond.html) (2026-11-24) predicts that sovereignty becomes a non-functional requirement. This note takes that as its premise and splits what to decide for FSx for ONTAP data into seven axes. **It adds no new measurement.** It builds the decision from links to records that already exist.

**Isolation and control are different things.** Isolation is placing data in another Region or partition. Control is being able to decide who holds the keys, the copies, and the management plane. Even if you restrict the Region, the key type is decided separately at file system creation and cannot be changed afterwards (row 2 below).

**Over-isolating data that is not sensitive costs money and removes features.** Set the strength of isolation to match the class of the data.

> **Governance note**
>
> This note describes governance thinking and technical behavior. It is not a legal or compliance judgment. Whether a specific requirement is met is for legal and compliance staff to decide.

---

### What to decide and the existing records

The tier terms follow the definitions in the [evidence policy](../../../evidence-policy.md).

| Axis | What to decide | Existing records (link, tier, date) |
|---|---|---|
| Data location | Region and partition (the commercial partition, or the AWS European Sovereign Cloud) | For FSx for ONTAP, the AWS Regional availability data lists eusc-de-east-1 as available, and the SDK endpoint data has fsx, backup, and kms in the aws-eusc partition (checked 2026-11-24, `documented`). API calls in that partition were not made, because they need an account in that partition (`open`). `CopyBackup` copies only within a partition ([AWS: Copying backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copy-backups.html), `documented`) |
| Key management | AWS managed key or a CMK (a KMS key you manage). Whether to use a key from an external key store (XKS). The key is decided at file system creation and cannot be changed afterwards | `KmsKeyId` of CloudFormation `AWS::FSx::FileSystem` is "Update requires: Replacement" ([AWS: AWS::FSx::FileSystem](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-fsx-filesystem.html), `documented`). That `update-file-system` has no argument to change the key is confirmed with the AWS CLI in the Hub note [The CMK a cross-account copy needs](../../../../ja/domains/data-protection/notes/backup-copies-across-regions-and-accounts.md#別アカウントコピーに必要な-cmk--判断はファイルシステム作成前) (日本語). A backup of a file system encrypted with an AWS managed key is not copied to a logically air-gapped vault (`documented`). A manual copy job failed with `KMS_KEY_ERROR` (2026-11-22, ap-northeast-1, once, `verified`). The record is in the Cyber Resilience Patterns [logically air-gapped vault guide](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/aws-backup-logically-air-gapped-vault.md). External key store (XKS): the AWS KMS documentation says a service that supports symmetric CMKs also supports keys in an external key store ([AWS KMS: External key stores](https://docs.aws.amazon.com/kms/latest/developerguide/keystore-external.html), `documented`). Using an external key store key with FSx for ONTAP has not been measured (`hypothesis`). Trade-off: while the external key manager is unavailable, data protected by that key cannot be decrypted (same KMS documentation, `documented`) |
| Replica and backup destinations | Which Regions and accounts copies and replication go to. Whether to place a guard that limits destinations | Hub note [A backup copy has no file system until you restore it](../../../../ja/domains/data-protection/notes/backup-copies-across-regions-and-accounts.md) (日本語) (copy and restore from Tokyo to Osaka with `CopyBackup` and AWS Backup, 2026-08-28 to 29, `verified`). Cyber Resilience Patterns [logically air-gapped vault guide](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/aws-backup-logically-air-gapped-vault.md) (vault sharing through AWS RAM and a restore, once each, between two accounts of the same organization, 2026-10-12, `verified`). Lakehouse Integrations [SnapMirror research record](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/integrations/snapmirror-flexcache-multicloud/docs/ja/research.md) (about 3 minutes to break a SnapMirror from Tokyo to us-west-2 and reattach S3 Access Points to the destination, 2026-07-22, SM-VAL-008 to 011, `verified`). Guard: add an `aws:RequestedRegion` condition to `fsx:CopyBackup` to limit the destination Region. The condition itself is in [the guard against copies to unintended Regions](../../../../ja/domains/data-protection/notes/backup-copies-across-regions-and-accounts.md#意図しないリージョンへコピーさせないガード) (日本語) in the Hub note |
| Management-plane access | The secret holding the `fsxadmin` credentials and the Regions of its replicas. The network that can reach the management endpoint | Hub note [Admin account lockout and recovery](../../../../ja/playbooks/05-operate/notes/admin-account-lockout-and-recovery.md) (日本語) (Japanese-only page. Record of the lockout behavior and recovery, 2026-09-02, ap-northeast-1, `verified`) |
| Model and inference location | The geographic scope of the Amazon Bedrock inference profile (regional such as `global.` or `apac.`, or national such as `jp.`). Where the RAG vector store sits | S3 Access Points Serverless Patterns [inference profile document](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/bedrock-inference-profiles.md). The CI gate in that repository rejects hard-coded model IDs but does not enforce the geographic scope of an inference profile. For the vector store, section 3.2 of the Agentic Access-Aware RAG [Managed Knowledge Base migration evaluation](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG/blob/main/docs/en/managed-kb-migration-evaluation.md) says to keep the current architecture if you need to manage explicitly where vector data is stored |
| Per-deployment evidence | What shows that the file system you built has the location and key you decided on | The Cyber Resilience Patterns [read-only configuration probe](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/adversarial-configuration-probe.md) collects, in the `residency` field of its output, the Region, the key's manager and Origin, the source Region of backups in this Region, SnapMirror destinations, and cluster peers. The [template check](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/tests/test_fsx_kms_customer_key.py) in the same repository confirms that every file system a template creates is encrypted with a CMK. `AWS::FSx::*` is not among the resource types AWS Config supports ([AWS Config: Supported resource types](https://docs.aws.amazon.com/config/latest/developerguide/resource-config-reference.html), checked 2026-11-24, `documented`), so take FSx for ONTAP evidence from scripts or IaC. On 2026-11-23, managing FSx for ONTAP Snapshots, clones, and SnapMirror from the Amazon FSx console, API, and AWS CloudFormation was announced ([What's New](https://aws.amazon.com/about-aws/whats-new/2026/11/amazon-fsx-for-netapp-ontap-additional-resources/)), so a replication destination can be declared in a template and reviewed |
| Movement drills | Whether to drill moving to another Region, partition, or inference profile ahead of time | What was measured is the records in row 3. Not measured (`open`): the first transfer of SnapMirror from Tokyo to Osaka, break, and reverse resync and fail back. Incremental copies. The transfer fee actually billed. Copies to another account. A drill that switches the RAG inference profile. Tracked in [Issue #440](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/440) |

---

### How to choose

The classes are examples. Read them as your organization's data classification. In every class, the stricter side takes on cost and operating effort, and the looser side takes on the constraints of choices that cannot be changed later.

| Class | Location | Key | Copy destination | What you give up |
|---|---|---|---|---|
| Public, not sensitive | The commercial partition. Choose the Region by availability and cost | An AWS managed key is acceptable | The same Region, or another Region | Constraint of the looser side: with an AWS managed key you cannot change the key later, and copies to a logically air-gapped vault are not available (row 2). In exchange, cost and effort are lowest |
| Internal | The commercial partition. Choose the Regions your organization's policy allows | A CMK, decided before creation | Another Region, another account. If you send copies to another account, settle the key decision before creation | The effort of operating the key. The key cannot be changed after creation, so deciding again means rebuilding the file system |
| Regulated personal data | Restrict the Regions where data sits by requirement. Restrict the partition too if needed | A CMK | Only the allowed Regions. Add an `aws:RequestedRegion` condition to `fsx:CopyBackup` | Fewer Regions and recovery destinations to choose from. More effort to maintain the guard and to run drills per destination (row 7) |
| Special categories of data (health, biometrics, and so on) | Restrict down to the partition (for example, the AWS European Sovereign Cloud). Use only the services available in that partition | A CMK. A key from an external key store is a candidate, but its behavior with FSx for ONTAP is not measured (`hypothesis`) | Only inside that partition. `CopyBackup` cannot cross partitions | While the external key manager is unavailable, data protected by that key cannot be decrypted (`documented`). You cannot recover across partitions. Fewer services are available. Availability of fsx, backup, and kms was checked, other services were not, and no API call was made (`open`) |

The strictest class has three constraints: key availability depends on an external key manager, you cannot cross partitions, and fewer services are available. **Choose this class only when the data is worth those constraints.**

Model and inference location (row 5) does not fit a column of this table. Decide the geographic scope of the inference profile and where the vector store sits separately for each class.

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| Isolating means you control | Isolation is about place. Who holds the keys and the management plane is decided separately. Even if you restrict the Region, the key type is decided at creation and cannot be changed afterwards (row 2) |
| Copying to another account survives deletion | If the conditions for isolation are not met, an administrator of the original account can delete the copy. The conditions are in [the conditions under which isolation holds](../../../../ja/domains/data-protection/notes/backup-copies-across-regions-and-accounts.md#隔離が成立する条件) (日本語) in the Hub note |
| You can switch to a CMK later | Updating `KmsKeyId` requires replacement (row 2, `documented`). Decide the key before you create the file system |

---

### Primary sources

| Topic | Source |
|---|---|
| Title and publication date of the blog post (its content is not reproduced) | [The AWS CTO's blog post: Tech predictions for 2027 and beyond](https://www.allthingsdistributed.com/2026/11/tech-predictions-for-2027-and-beyond.html) (2026-11-24) |
| `CopyBackup` copying only within a partition | [AWS: Copying backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copy-backups.html) |
| `KmsKeyId` being an update that requires replacement | [AWS: AWS::FSx::FileSystem](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-fsx-filesystem.html) |
| Scope of support for external key store keys, and the constraint while the external key manager is unavailable | [AWS KMS: External key stores](https://docs.aws.amazon.com/kms/latest/developerguide/keystore-external.html) |
| The API that returns a key's manager and Origin | [AWS KMS: KeyMetadata](https://docs.aws.amazon.com/kms/latest/APIReference/API_KeyMetadata.html) |
| Resource types AWS Config supports | [AWS Config: Supported resource types](https://docs.aws.amazon.com/config/latest/developerguide/resource-config-reference.html) |
| Management-plane additions for Snapshots, clones, and SnapMirror | [What's New](https://aws.amazon.com/about-aws/whats-new/2026/11/amazon-fsx-for-netapp-ontap-additional-resources/) |
| The failed copy to a logically air-gapped vault, and the sharing record | [Cyber Resilience Patterns logically air-gapped vault guide](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/aws-backup-logically-air-gapped-vault.md) |
| Per-deployment location output, and the key check | [Read-only configuration probe](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/adversarial-configuration-probe.md), [template check](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/tests/test_fsx_kms_customer_key.py) |
| Time to break a SnapMirror destination in another Region and reattach S3 Access Points | [SnapMirror research record](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/integrations/snapmirror-flexcache-multicloud/docs/ja/research.md) |
| The geographic scope that inference profile prefixes express | [Inference profile document](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/bedrock-inference-profiles.md) |
| The decision when you must manage where vector data is stored | [Managed Knowledge Base migration evaluation](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG/blob/main/docs/en/managed-kb-migration-evaluation.md) |

---

### Related documents

- [Domain Security & Governance](../README.md): the hub for this module
- [A backup copy has no file system until you restore it](../../../../ja/domains/data-protection/notes/backup-copies-across-regions-and-accounts.md) (日本語): copy destinations, the key decision, and the conditions under which isolation holds
- [Admin account lockout and recovery](../../../../ja/playbooks/05-operate/notes/admin-account-lockout-and-recovery.md) (日本語): management-plane credentials
- [Evidence policy](../../../evidence-policy.md)

---

## Verify it in your environment

These steps are read-only. Replace each value with the `<...>` placeholder for your environment.

| # | Step | What it establishes |
|---|---|---|
| 1 | Read the key ARN with `aws fsx describe-file-systems --file-system-ids <file-system-id> --query "FileSystems[0].KmsKeyId"` | Which key encrypts the file system |
| 2 | Read the manager and Origin with `aws kms describe-key --key-id <key-arn> --query "KeyMetadata.[KeyManager,Origin]"` | Whether AWS or you manages the key, and where the key material comes from |
| 3 | Read the source Region of each backup with `aws fsx describe-backups --query "Backups[].[BackupId,SourceBackupRegion]"` | Which Region each backup in this Region was copied from |
| 4 | Read the IAM policy with `aws iam get-policy-version --policy-arn <policy-arn> --version-id <version-id> --query PolicyVersion.Document` and look for an `aws:RequestedRegion` condition on `fsx:CopyBackup` | Whether a guard limiting the copy destination Region exists |

### Expected output

```text
"arn:aws:kms:<region>:<account-id>:key/<key-id>"
["CUSTOMER","AWS_KMS"]
[["<backup-id>","<source-region-or-null>"]]
```

The first line is the key ARN and the second is the `[KeyManager, Origin]` pair. `CUSTOMER` means a CMK and `AWS` means an AWS managed key. A key from an external key store shows an Origin of `EXTERNAL_KEY_STORE` ([AWS KMS: KeyMetadata](https://docs.aws.amazon.com/kms/latest/APIReference/API_KeyMetadata.html)). The third line is the source of each backup, and is `null` for a backup that is not a copy.

These steps show only what AWS records about the key, the copy source, and the IAM policy. They do not show SnapMirror destinations or cluster peers, which exist only inside ONTAP. Use the output of the configuration probe for those. Step 4 shows that a condition is written, not that the condition actually refuses a copy.

## Read next

[Approval for an irreversible operation is separate from approval for the work](../../../../ja/domains/security-governance/notes/irreversible-operations-need-separate-approval.md) (日本語)
