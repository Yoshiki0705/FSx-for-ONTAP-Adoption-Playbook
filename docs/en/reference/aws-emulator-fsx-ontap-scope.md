---
title: AWS Emulator covers FSx for ONTAP file system create and update only; SVMs, volumes, S3 Access Points, and ONTAP itself are out of scope
lifecycle: [design, build]
domains: [client-access, data-utilization]
evidence: field-observation
source: https://aws.amazon.com/blogs/aws/test-your-applications-against-aws-locally-with-aws-emulator/
lang: en
---

# AWS Emulator and FSx for ONTAP

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md)

---

## Conclusion

**AWS Emulator can be used to test, locally and without an AWS account, the AWS API calls that create, update, and describe Amazon FSx for NetApp ONTAP file systems. It does not run ONTAP.** From one run of v1.0.322 from the public repository on 2026-11-12:

| What you want to try | Result |
|---|---|
| Create, update, and describe a file system; tags; the error for a nonexistent ID | Works. A created file system becomes `AVAILABLE` within seconds |
| CloudFormation stack containing only the file system | Works |
| Create and describe SVMs, volumes, and snapshots | Not implemented. HTTP 501 |
| Create and describe FSx for ONTAP S3 Access Points | Not implemented. HTTP 501 |
| CloudFormation `AWS::FSx::StorageVirtualMachine` and `AWS::FSx::Volume` | The resource types are not recognized and the template is rejected before a stack is created |
| ONTAP REST API, NFS, SMB, iSCSI, SnapMirror, SnapLock | Out of scope. The emulator serves only AWS API endpoints |
| IAM policy evaluation | Not performed (per the vendor). The two-layer authorization of S3 Access Points cannot be tried |

**These results are one observation in one environment and were not reproduced.** The release number had already reached v1.0.322, so updates appear frequent. "Not implemented" in the table is a snapshot of this date and version.

---

## Tier and measurement conditions

| Item | Detail |
|---|---|
| Tier | `field-observation`. The run results are a single observation. The vendor specification and fidelity-score figures are transcribed from AWS documentation and the release asset |
| Target | `aws/aws-emulator` v1.0.322 (commit `7753983`), released 2026-11-11 |
| Environment | macOS (arm64), Docker 29.5.3, installed from the aarch64 RPM on a minimal Amazon Linux 2023 image. AWS CLI 2.38.3 |
| Settings | Region setting `us-east-1`, the emulator's all-zero dummy account, `--telemetry off` |
| Run date | 2026-11-12 |
| Comparison with real AWS | Not done. "Works" here means the emulator returned success; it does not show the result matches real AWS |

The response excerpts and the run procedure are kept only in a private record.

---

## What was checked

### Operations that worked

- `create-file-system` (`FileSystemType=ONTAP`, `MULTI_AZ_1`, `HAPairs=1`) succeeded and returned `Lifecycle` as `CREATING`. A `describe-file-systems` a few seconds later showed `AVAILABLE`.
- `update-file-system` with a throughput change returned `UPDATING`.
- `list-tags-for-resource` and `describe-backups` succeeded. `describe-file-systems` with a nonexistent file system ID returned `FileSystemNotFound` with a message that includes the ID.
- The subnets passed at creation had to be created first in the emulator's own EC2. The IDs are synthetic values such as `vpc-0000…`.
- A CloudFormation template containing only `AWS::FSx::FileSystem` (ONTAP) reached `CREATE_COMPLETE`.

### Operations that did not work

- `create-storage-virtual-machine`, `describe-storage-virtual-machines`, `create-volume`, `create-snapshot`, `create-and-attach-s3-access-point`, and `describe-s3-access-point-attachments` returned `NotImplemented` (HTTP 501). The message said "scaffolded but not implemented".
- Templates containing `AWS::FSx::StorageVirtualMachine` or `AWS::FSx::Volume` were rejected with a `ValidationError` ("Unrecognized resource types") before any stack was created.
- The result of `describe-file-systems` did not include the ONTAP management endpoint (`Endpoints.Management`). Code that extracts an ONTAP REST target cannot be tried as it stands.
- `s3control create-access-point` failed to connect to a host name that includes the account ID. Whether the cause is the emulator or the client configuration was not isolated.

### Agreement with the implementation status in the public repository

Reading the source, the `fsx` service crate has 48 operations: 33 not implemented (marked `SCAFFOLDED, NOT IMPLEMENTED` at the top of the file) and 15 implemented. Every operation that did not work above is on the not-implemented side. `describe-volumes` is on the implemented side and returned an empty list.

---

## Vendor specification and limits

Sources: the [AWS announcement](https://aws.amazon.com/about-aws/whats-new/2026/11/aws-emulator-now-available/), the [AWS News Blog](https://aws.amazon.com/blogs/aws/test-your-applications-against-aws-locally-with-aws-emulator/), and the [repository README](https://github.com/aws/aws-emulator).

| Item | Vendor statement |
|---|---|
| Delivery | RPM and Debian packages on Linux. On macOS and Windows, you build an image yourself from a short Dockerfile. No prebuilt image is published |
| Cost and license | No additional service fee. Source under CC0 1.0 |
| State | In memory only; lost when the emulator stops |
| Account and Region | One account. No cross-account or cross-Region behavior |
| Signing | SigV4 is required, and credentials other than those the emulator generates at each start are rejected |
| IAM | IAM and resource-based policies are not evaluated the way AWS does; a request AWS would deny may succeed. The vendor states it must not be used to test security |
| Unimplemented operations | Return HTTP 501 |
| Telemetry | On by default; can be turned off with `--telemetry off` or an environment variable |
| How fidelity is measured | Tests verified against real AWS are compared on the response (status, body, error code and message) and on the resources created. Per-service pass counts are attached to each release |

### Transcribed fidelity scores

Figures tallied from the `scores.json.gz` attached to v1.0.322. They are transcriptions and were not re-measured in this repository. The vendor notes that a score can go down when tests are added.

| Scope | Pass | Fail | Skipped |
|---|---|---|---|
| Overall (42,937 tests) | 24,243 | 18,614 | 80 |
| `fsx` service (16 tests) | 5 | 11 | 0 |
| S3 (2,814 tests) | 1,763 | 1,035 | 16 |
| S3 Control (77 tests) | 37 | 40 | 0 |
| DataSync (29 tests) | 4 | 25 | 0 |

The main cause of the `fsx` failures is the unimplemented operations confirmed above (501). The passes were file system creation validation, tagging, restore from backup, the lower bound on a storage capacity update, and data repository association validation.

---

## Expected uses

This section is a **hypothesis** and is untested.

- **Testing code that operates FSx for ONTAP**: code that calls file system creation and waits for `AVAILABLE`, or waits for an update transition, may be runnable repeatedly, locally and in CI.
- **Testing error handling**: whether the error shape for a nonexistent ID matches real AWS is covered by the scored tests, so tests for this class of error path may be easier to write.
- **Coding-agent iteration**: because AWS APIs can be tried without a deployment, an agent could validate a draft script that includes FSx for ONTAP. SVM and volume calls return 501, so anything beyond that is confirmed on real AWS.
- **Testing the S3 side**: the S3 calls of an application that uses FSx for ONTAP S3 Access Points could be tested by substituting a regular bucket. Whether behavior is preserved by the substitution has not been checked.

---

## Where it does not fit

- Checking ONTAP internals (volumes, qtrees, snapshot policies, SnapMirror, SnapLock, ARP, FlexCache). The emulator targets AWS APIs; ONTAP is not running.
- SVM and Active Directory integration, NFS and SMB access checks, iSCSI connection checks.
- Checking IAM, resource policies, or the two-layer authorization of S3 Access Points. The vendor states they are not evaluated.
- Estimating performance, cost, or availability. This is in-memory emulation and says nothing about the characteristics of real hardware.
- Final checks before production. The vendor also states that security settings and the whole application should be confirmed on AWS.

---

## Deciding whether to use it

| What you want to check | Where it fits |
|---|---|
| Branching and state waits in code that calls FSx for ONTAP create and update | AWS Emulator |
| IaC or scripts that create SVMs and volumes | Real AWS. The emulator returns 501 or rejects the template |
| ONTAP configuration or behavior | Real FSx for ONTAP |
| Authorization behavior | Real AWS |

The constraint on the AWS Emulator side is shown in the table. The constraint on the real AWS side is cost and creation time, which make repeated runs a poor fit.

---

## Common misconceptions

- **"All of AWS runs locally, so I can make an FSx for ONTAP demo environment locally"**: the file system creation call works, but what is created is a record at the API level. No mountable ONTAP starts.
- **"The service count is large, so FSx for ONTAP's main operations work"**: the number of services and the implementation rate of a service's operations are different things. The `fsx` service had 15 of 48 operations implemented.
- **"If a test passes on the emulator, it passes on AWS"**: the vendor states that how closely behavior matches varies by service and feature. "Works" in this document was not compared with real AWS.

---

## Re-checking in your own environment

1. Build the image as in the vendor's [Getting started with Docker](https://docs.aws.amazon.com/emulator/latest/userguide/getting-started-docker.html), and start it with `--telemetry off`.
2. Point your AWS CLI at the configuration file and endpoint the emulator writes at startup. Unset the environment variables that carry real AWS credentials.
3. Run the FSx for ONTAP operations you want to try one at a time, and see whether `NotImplemented` is returned.
4. For implementation status, run `grep -rl '^//! SCAFFOLDED, NOT IMPLEMENTED:' services/service-com-amazonaws-fsx-*/src/ops/` in the repository and count. Take the `fsx` service fidelity from the `scores.json.gz` attached to the release you use.
5. To clean up, stop the container and delete `~/.aws/emulator`.

---

## Related documents

- [Reference index](../../ja/reference/README.md)
- [Evidence policy](../evidence-policy.md)
- [FSx for ONTAP fit conditions](../../ja/reference/fsx-ontap-fit-conditions.md) (日本語)
- [Entry point for ONTAP commands, REST APIs, and permissions](ontap-commands-and-apis.md)

---

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/reference/aws-emulator-fsx-ontap-scope.md) | [English](aws-emulator-fsx-ontap-scope.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
