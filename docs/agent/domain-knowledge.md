# FSx for ONTAP domain knowledge (carry-over)

> Extracted from `AGENTS.md` so it is not loaded on every turn. Read this before writing a technical claim about AD integration, S3 Access Points, or documented constraints.
>
> `AGENTS.md` remains authoritative on any disagreement.

These are established findings from sibling repositories. Do not re-derive them; cite and link instead.

## AD integration

- AWS Managed Microsoft AD inserts an intermediate OU: `OU=Computers,OU=<ShortName>,DC=…`. Omitting it causes silent failures. Self-managed AD has no intermediate OU.
- `FileSystemAdministratorsGroup` must be `Domain Admins`. `AWS Delegated FSx Administrators` has insufficient permissions for SVM join (verified failure → `MISCONFIGURED`). <!-- allow:naming: the AD group name is a proper noun -->
- SVM NetBIOS name: ≤15 chars, must differ from the domain ShortName, unique per AD domain. Never reuse a name after a failed join — AD retains the orphaned computer account.
- Windows EC2 domain join: use a separate `AWS::SSM::Association` with the AWS-managed `AWS-JoinDirectoryServiceDomain` document. Never `SsmAssociations` on the instance, never a custom `aws:domainJoin` document.

## S3 Access Points

- IAM ARN must be access-point style: `arn:aws:s3:<region>:<account>:accesspoint/<name>` (and `/object/*`). Bucket-style ARNs do not work.
- Dual-layer authorization: AWS side (IAM + AP policy) **and** ONTAP side (file system identity) must both allow.
- `NetworkOrigin` is immutable after creation — confirmed structurally: the Amazon FSx API exposes only create, describe, and detach-and-delete for these attachments, with no update operation, so every field except the policy is fixed for the life of the attachment. <!-- allow:naming - AWS service name -->
- **An `Internet` origin access point *was* reachable through an S3 Gateway VPC Endpoint** (measured 2026-08-17, `ap-northeast-1`). This line previously stated the opposite. The request from an in-VPC EC2 instance succeeded *and* carried `aws:SourceVpce`, which is only populated when the request traverses that endpoint — so it was not falling back to the internet path. The subnet also had an IGW default route, and the S3 prefix-list route to the gateway endpoint is the more specific match for S3 destinations. The earlier claim was not reproduced; treat "unreachable" as unverified rather than established. Full record: `.private/s3ap-policy-verification/RESULTS.md`.
- Size limits are **binary** despite docs saying "GB": single `PutObject` and per-`UploadPart` 5 GiB; whole object 50 GiB. The whole-object limit is checked only at `CompleteMultipartUpload`, after the full payload transfers — validate client-side first.
- On an AD-joined SVM, **every** data operation requires AD DC reachability. `HeadBucket` succeeds even when AD is unreachable (false positive) — always verify with a data operation.

## Documented constraints

- No S3 Event Notifications → use EventBridge Scheduler polling or FPolicy.
- SnapLock / tamperproof snapshot enablement is **irreversible**. Enabling the feature is not the same as auto-locking; a retention period on the policy is what triggers locking.
- Volume names allow only alphanumerics and underscores.
