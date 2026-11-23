# FSx for ONTAP domain knowledge (carry-over)

> Extracted from `AGENTS.md` so it is not loaded on every turn. Read this before writing a technical claim about AD integration, S3 Access Points, or documented constraints.
>
> `AGENTS.md` remains authoritative on any disagreement.

These are established findings from sibling repositories. Do not re-derive them; cite and link instead.

## Before you write "unverified"

Three checks come first, in this order, and all are cheap. A label such as `hypothesis`, `未確認`, or
"not measured" is a statement that you looked and the answer was not there.

1. **Search what the Spokes have already done.** Run `make spoke-search Q='<product or feature name>'`
   (a phrase needs quotes inside the single quotes). It reads the other repositories' *committed* content,
   after fetching any ref gone stale, and lists their evidence-ledger entries with the tier each recorded,
   their feature requests, limits and verification records, and the Kiro memory scope to read for each
   repository. A hit does not mean your claim is wrong. It means someone investigated, and you read it
   before saying otherwise. An empty result is also an answer: write down what you searched. Do not grep
   `~/Projects/*` instead; that reads whatever each checkout happens to hold, and `.private/` holds vendor
   correspondence that must not become the basis of a published claim.
2. **A measurement may be indexed already.** The file-protocol (NFS / SMB), block (iSCSI / NVMe/TCP) and S3
   Access Points performance tests were run in the Spokes. Their locations, with the measurement
   environment, are in [`performance-evidence-map.md`](../ja/reference/performance-evidence-map.md); the
   claims this repository cites are in [`cross-repo-index.md`](../ja/reference/cross-repo-index.md). Cite
   those; do not re-measure and do not call them unmeasured.
3. **Then ask whether a few hours would settle it.** A file system for FSx for ONTAP is kept running in
   `ap-northeast-1` for verification, and AWS access on this machine is IAM Identity Center (SSO). If the
   claim can be tested there within a few hours, test it and record the result with its environment
   (`verified_on`, `region`, ONTAP version) instead of writing "unverified".

Two programs make the first check run without anyone remembering it. Both are tracked here and are meant
to be called from user-level Kiro hooks, so they apply in every repository of the family and in session
worktrees, where the gitignored `.kiro/` of the main tree does not exist.

| Program | Hook | What it does |
|---|---|---|
| `tools/spoke_search.py --digest` | Prompt submitted | Picks the product and feature names out of the prompt and prints where the Spokes hold records on them. Silent when nothing matches |
| `scripts/guard_unverified_claims.py` | Before `fs_write`, `str_replace`, `fs_append` | Blocks a Markdown write that **adds** a "not verified / not measured" sentence over material a Spoke recorded, unless that paragraph names the Spoke. A measurement claim about performance must name the evidence map or a Spoke |

The guard names product-shaped terms (CamelCase, digit-bearing, capitalised mid-sentence) found in a
record of a conclusion in a Spoke: an evidence ledger, a feature request, a limits or pitfalls page, a
decision. Terms found in many files (FlexCache, SnapMirror, S3 Access Points) name no topic and are not
matched; the search above is how those are covered. When it blocks, change the text: link the Spoke
file in the same paragraph with the tier it records, or, if the Spoke covers a neighbouring thing and
you have said so, add `<!-- spoke-checked: <term> -->`. `git grep spoke-checked` lists every override.

What is established, and what you must still check each time:

| Item | State |
|---|---|
| A verification FSx for ONTAP file system exists in `ap-northeast-1` | Kept running. Confirm the file system ID and its lifecycle with `aws fsx describe-file-systems` before relying on it |
| AWS authentication | SSO only, valid for about 24 hours from `aws sso login`. The agent cannot log in: ask the user and wait. Never create or use long-term access keys |
| A Linux host that can reach the ONTAP management endpoint | **Not standing.** Discover one, or start a short-lived SSM-managed instance in the file system's VPC and stop it afterwards |
| Anything that cannot be undone, or holds a parent resource for a long time | Do not run unprompted. See the immutability rules in `AGENTS.md` |

What a few hours cannot settle: anything that needs a second environment you do not control (for example a
non-AWS ONTAP service as a FlexCache Origin). Say so, name the missing environment, and keep the label.

## Generation and ONTAP version

What a first-generation file system on ONTAP 9.19.1P4 does is not what a second- or third-generation one
does, and the ONTAP patch level changes under a file system without notice. Before you write that a
feature works, is missing, or can be changed on FSx for ONTAP:

| Question | Read |
|---|---|
| Does a feature in an ONTAP 9.17.1 to 9.20.1 release note exist on FSx for ONTAP? | [`ontap-release-features-and-fsx-for-ontap.md`](../ja/reference/ontap-release-features-and-fsx-for-ontap.md). A release-note entry is not evidence; the status column says what was confirmed, in which environment |
| Can the broadcast domain MTU be changed? Does the generation matter? | [the MTU note](../ja/domains/performance/notes/broadcast-domain-mtu-can-be-changed-on-first-generation.md). First generation only; the broadcast domain is `Fsx` and `Default` is the IPspace |
| A rebuilt file system, or an ONTAP update: what to re-take | [`rebuild-version-and-generation-checks.md`](../ja/playbooks/04-build/checklists/rebuild-version-and-generation-checks.md) |

Three rules come from the work behind those pages. A REST or CLI call that returns HTTP 200 may have
changed nothing (`num_records: 0`), so read the value back. A file system tagged `Teardown` or
`MeasurementId` belongs to another project's measurement: do not reset its password or change it. Record
the generation, the full ONTAP version and the date with every result, or the result cannot be compared.

## AD integration

- AWS Managed Microsoft AD inserts an intermediate OU: `OU=Computers,OU=<ShortName>,DC=…`. Omitting it causes silent failures. Self-managed AD has no intermediate OU.
- The same OU tree applies to users. AWS documents the `<ShortName>` OU as owned by AWS, with Full Control granted to the directory administrator and two default child OUs, `Computers` and `Users` ([AWS: What gets created](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_getting_started_what_gets_created.html), `documented`). That page does not say what happens when a delegated administrator writes outside that OU. One observation covers it: the delegated administrator could not create a user in the domain-root `CN=Users` (Access is denied) and could in `OU=Users,OU=APPMOD`, the delegated tree. Generalizing that value to `OU=Users,OU=<ShortName>` rests only on the intermediate-OU statement above, not on a second observation. `documented`, one observation (ap-northeast-1, 2026-10-07, AWS Managed Microsoft AD Standard, created from a Windows Server 2022 EC2): [App-Modernization-Patterns, Gaps found after creation](https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/en/environment.md#gaps-found-after-creation).
- `FileSystemAdministratorsGroup` must be `Domain Admins`. `AWS Delegated FSx Administrators` has insufficient permissions for SVM join (verified failure → `MISCONFIGURED`).
- SVM NetBIOS name: ≤15 chars, must differ from the domain ShortName, unique per AD domain. Never reuse a name after a failed join — AD retains the orphaned computer account.
- Windows EC2 domain join: use a separate `AWS::SSM::Association` with the AWS-managed `AWS-JoinDirectoryServiceDomain` document. Never `SsmAssociations` on the instance, never a custom `aws:domainJoin` document.
- **Domain-controller discovery on a joined SVM** can be read from ONTAP REST `GET /api/protocols/cifs/domains/{svm.uuid}?fields=discovered_servers`: an `ms_dc` entry in `state=ok`. `GET /api/protocols/active-directory` returned 0 records on the same joined SVM, so an empty result there does not mean the join failed. Use this as a complement to the SVM lifecycle-state check, not a replacement. The source never saw lifecycle state alone give a wrong answer; its criterion is stricter, not proven necessary. `documented`, one SVM (ap-northeast-1, 2026-10-07, Gen1 `SINGLE_AZ_1`, ONTAP 9.19.1P2, AWS Managed Microsoft AD Standard): [stage 0 measured results](https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/en/stage-0-smb-ntfs.md#measured-results-verified), [environment](https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/en/environment.md#measured-ontap-version). What `active-directory` returns on other configurations is untested.
- **Port 9389 has two paths.** The SVM-ENI-to-DC path (the port list in the pre-production checklist) is separate from a Windows host's path to AD Web Services. One domain-joined Windows Server 2022 EC2 could not reach TCP 9389 while LDAP 389 and LDAPS 636 worked; the cause was not recorded (security group, ADWS service state and name resolution are all unchecked). Do not read this as "ADWS is unavailable on AWS Managed Microsoft AD" or as a reason to change the SVM-side port list. AWS's default DC security-group inbound list does not include 9389, which is context, not a diagnosis. `documented`, one observation (same environment as above): [Gaps found after creation](https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/en/environment.md#gaps-found-after-creation).

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
