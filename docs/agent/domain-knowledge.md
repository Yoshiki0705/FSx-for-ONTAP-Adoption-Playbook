# FSx for ONTAP domain knowledge (carry-over)

> Extracted from `AGENTS.md` so it is not loaded on every turn. Read this before writing a technical claim about AD integration, S3 Access Points, or documented constraints.
>
> `AGENTS.md` remains authoritative on any disagreement.

These are established findings from sibling repositories. Do not re-derive them; cite and link instead.

## Before you write "unverified"

Two checks come first, in this order, and both are cheap. A label such as `hypothesis`, `未確認`, or
"not measured" is a statement that you looked and the answer was not there.

1. **A Spoke may have measured it already.** The file-protocol (NFS / SMB), block (iSCSI / NVMe/TCP) and S3
   Access Points performance tests were run in the Spokes. Their locations, with the measurement
   environment, are in [`performance-evidence-map.md`](../ja/reference/performance-evidence-map.md); the
   claims this repository cites are in [`cross-repo-index.md`](../ja/reference/cross-repo-index.md). Cite
   those; do not re-measure and do not call them unmeasured.
2. **Then ask whether a few hours would settle it.** A file system for FSx for ONTAP is kept running in
   `ap-northeast-1` for verification, and AWS access on this machine is IAM Identity Center (SSO). If the
   claim can be tested there within a few hours, test it and record the result with its environment
   (`verified_on`, `region`, ONTAP version) instead of writing "unverified".

What is established, and what you must still check each time:

| Item | State |
|---|---|
| A verification FSx for ONTAP file system exists in `ap-northeast-1` | Kept running. Confirm the file system ID and its lifecycle with `aws fsx describe-file-systems` before relying on it |
| AWS authentication | SSO only, valid for about 24 hours from `aws sso login`. The agent cannot log in: ask the user and wait. Never create or use long-term access keys |
| A Linux host that can reach the ONTAP management endpoint | **Not standing.** Discover one, or start a short-lived SSM-managed instance in the file system's VPC and stop it afterwards |
| Anything that cannot be undone, or holds a parent resource for a long time | Do not run unprompted. See the immutability rules in `AGENTS.md` |

What a few hours cannot settle: anything that needs a second environment you do not control (for example a
non-AWS ONTAP service as a FlexCache Origin). Say so, name the missing environment, and keep the label.

## AD integration

- AWS Managed Microsoft AD inserts an intermediate OU: `OU=Computers,OU=<ShortName>,DC=…`. Omitting it causes silent failures. Self-managed AD has no intermediate OU.
- `FileSystemAdministratorsGroup` must be `Domain Admins`. `AWS Delegated FSx Administrators` has insufficient permissions for SVM join (verified failure → `MISCONFIGURED`).
- SVM NetBIOS name: ≤15 chars, must differ from the domain ShortName, unique per AD domain. Never reuse a name after a failed join — AD retains the orphaned computer account.
- Windows EC2 domain join: use a separate `AWS::SSM::Association` with the AWS-managed `AWS-JoinDirectoryServiceDomain` document. Never `SsmAssociations` on the instance, never a custom `aws:domainJoin` document.

## S3 Access Points

- IAM ARN must be access-point style: `arn:aws:s3:<region>:<account>:accesspoint/<name>` (and `/object/*`). Bucket-style ARNs do not work. **Primary source found 2026-08-18**: [AWS: Troubleshooting S3 access point issues](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/troubleshooting-access-points-for-fsxn.html) documents this as a named failure mode — automatically created service roles may reference the alias as `arn:aws:s3:::<alias>`, and the fix is to use the access point ARN. The ARN grammar itself is in [Referencing access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/referencing-access-points-for-fsxn.html). This may be cited as `documented`.
- Dual-layer authorization: AWS side (IAM + AP policy) **and** ONTAP side (file system identity) must both allow. **The AWS side is itself layered** — network origin check (before any policy), VPC endpoint policy, access point policy, identity policy, SCP — and an explicit deny in any of them takes precedence: [AWS: Configuring network access for Amazon S3 access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html). **The VPC endpoint policy is the layer most often forgotten** because its default allows everything.
- `NetworkOrigin` is immutable after creation — confirmed structurally: the Amazon FSx API exposes only create, describe, and detach-and-delete for these attachments, with no update operation, so every field except the policy is fixed for the life of the attachment.
- **An `Internet` origin access point *was* reachable through an S3 Gateway VPC Endpoint** (measured 2026-08-17, `ap-northeast-1`). This line previously stated the opposite. The request from an in-VPC EC2 instance succeeded *and* carried `aws:SourceVpce`, which is only populated when the request traverses that endpoint — so it was not falling back to the internet path. The subnet also had an IGW default route, and the S3 prefix-list route to the gateway endpoint is the more specific match for S3 destinations. The earlier claim was not reproduced; treat "unreachable" as unverified rather than established. **Reproduced 2026-08-18 with the missing control**: changing only the condition value to a non-existent endpoint ID denied the same EC2 instance, which is what distinguishes "the value matched" from "the condition is not evaluated on an Internet-origin access point". Now published with the control in [the access point authorization note](../ja/domains/security-governance/notes/access-point-authorization-layers.md); cite that rather than this file. **Caveat AWS documents and this measurement does not cover**: gateway endpoints do not route traffic entering the VPC from VPN, Direct Connect, Transit Gateway or peering — callers on those paths need an Interface endpoint when the design requires a private path, which is the likely explanation for timeouts observed from outside a VPC.
- Size limits are **binary** despite docs saying "GB": single `PutObject` and per-`UploadPart` 5 GiB; whole object 50 GiB. The whole-object limit is checked only at `CompleteMultipartUpload`, after the full payload transfers — validate client-side first.
- **Open claim:** an existing carry-over says that every data operation on an AD-joined SVM requires domain-controller reachability and that `HeadBucket` can succeed while the domain is unreachable. The tracked record does not contain the full environment, procedure, and controls needed to publish this as verified, and the current AWS pages document identity resolution and name-service reachability without establishing that universal runtime behavior. Use a data operation for end-to-end verification, but do not attribute a failure to Active Directory from `HeadBucket` alone.

## Documented constraints

- No S3 Event Notifications, and **FPolicy is not a substitute for them**: measured 2026-08-26 on ONTAP 9.18.1P3D1, data operations arriving through an access point raise no FPolicy notification, and are not blocked even by a `mandatory` synchronous policy, while the same volume over NFS or SMB is. An FPolicy event accepts only `cifs` / `nfsv3` / `nfsv4` as its protocol; there is no value for the S3 path. Use EventBridge Scheduler polling, or the ONTAP native audit log, which **does** record these operations as `Source=HTTP` (objects) and `Source=S3` (LIST) — without the requester identity. ARP also sees this path. See [the access point authorization note](../ja/domains/security-governance/notes/access-point-authorization-layers.md) and the measurement record in the observability repository.
- SnapLock / tamperproof snapshot enablement is **irreversible**. Enabling the feature is not the same as auto-locking; a retention period on the policy is what triggers locking.
- Volume names allow only alphanumerics and underscores.
