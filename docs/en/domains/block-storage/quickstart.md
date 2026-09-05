---
title: Block storage running in about thirty minutes — one CloudFormation template and three ONTAP REST scripts
lifecycle: [build]
domains: [block-storage]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
lang: en
---

# Block storage running in about thirty minutes

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/block-storage/quickstart.md) | [English](quickstart.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

## What you end up with

**One LUN on Amazon FSx for NetApp ONTAP, reached from Linux over iSCSI with multipath assembled.**
About thirty minutes including waiting, of which seventeen are the file system being created.

The artifacts are in [`examples/block-storage/`](../../../../examples/block-storage/).

| File | What it does | Reaches |
|---|---|---|
| `fsxontap-iscsi-quickstart.yaml` | File system, SVM, volume, client, security groups, IAM role | AWS API |
| `provision-lun.sh` | Creates the LUN, igroup and LUN map. **Idempotent** | ONTAP REST API |
| `connect-iscsi.sh` | Logs the host in over iSCSI and assembles multipath. **Idempotent** | Host and ONTAP |
| `verify-block.sh` | Reports state from both sides. Creates nothing | ONTAP REST API and host |

> **Tier**: `verified` (2026-09-05, `ap-northeast-1`, `SINGLE_AZ_2` second generation with one HA
> pair, 384 MBps, ONTAP 9.18.1P5, Amazon Linux 2023 kernel 6.18.44) — the timings, the five
> idempotency counts, and the four stumbling points below.
> **No performance figures.** The client is a `t3.medium`, so any number measured here would describe
> its network interface rather than FSx for ONTAP.

---

## Why the template and the scripts are separate

**A LUN, an igroup and a LUN map have no Amazon FSx API action and no CloudFormation resource type.**
Provisioning therefore crosses from the AWS control plane to ONTAP, and **the crossing falls between
the volume and the LUN.** This split is that boundary, not a packaging preference. See
[LUNs and igroups sit outside the AWS API](../../../ja/domains/block-storage/notes/block-objects-are-outside-the-aws-api.md) (日本語).

**The volume is created by the template on purpose.** A volume created on the ONTAP side receives no
`fsvol` identifier and is therefore absent from Amazon CloudWatch, from AWS API tagging and from AWS
Backup — see [What block monitoring shows](../../../ja/domains/block-storage/notes/what-block-monitoring-shows.md) (日本語).

---

## Prerequisites

| Requirement | Why |
|---|---|
| An existing VPC and one subnet | The template creates no network, so deleting it cannot reach beyond the resources it made |
| That subnet reaching Systems Manager, Secrets Manager and **the Amazon FSx API** | See stumbling point 2. A NAT gateway, a public address, or interface VPC endpoints |
| `aws` CLI with CloudFormation, Amazon FSx, IAM and Secrets Manager permissions | |

**Nothing to prepare on the client.** The template launches one Amazon Linux 2023 instance and
installs `iscsi-initiator-utils`, `device-mapper-multipath` and `jq` through user data.

---

## Steps

### 1. Create a secret for the password

**The password appears in no CloudFormation parameter, output or log.** The template resolves it at
create time with `{{resolve:secretsmanager:...}}`.

```bash
aws secretsmanager create-secret --name fsxn-quickstart-fsxadmin \
  --secret-string '{"password":"<8 to 50 characters>"}'
```

Amazon FSx accepts 8 to 50 characters for `FsxAdminPassword`.

### 2. Create the AWS side

```bash
cd examples/block-storage
aws cloudformation create-stack --stack-name fsxn-block-quickstart \
  --template-body file://fsxontap-iscsi-quickstart.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=VpcId,ParameterValue=vpc-xxxxxxxx \
               ParameterKey=ClientSubnetId,ParameterValue=subnet-xxxxxxxx \
               ParameterKey=FsxAdminSecretName,ParameterValue=fsxn-quickstart-fsxadmin
```

**Around seventeen minutes**, almost all of it the file system. Then read the outputs:

```bash
aws cloudformation describe-stacks --stack-name fsxn-block-quickstart \
  --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' --output text
```

You get `FileSystemId`, `SvmName`, `VolumeName` and `ClientInstanceId`. **The ONTAP management
address is not among them**, because `AWS::FSx::FileSystem` exposes no `Fn::GetAtt` for it.

### 3. Run the three scripts on the client

```bash
aws ssm start-session --target <ClientInstanceId>
```

Then, in this order:

```bash
sudo ./provision-lun.sh --file-system-id fs-xxxxxxxx --svm <SvmName> \
  --volume <VolumeName> --secret-id fsxn-quickstart-fsxadmin

sudo ./connect-iscsi.sh --file-system-id fs-xxxxxxxx

sudo ./verify-block.sh --file-system-id fs-xxxxxxxx --svm <SvmName> \
  --volume <VolumeName> --secret-id fsxn-quickstart-fsxadmin
```

**You have arrived when `verify-block.sh` prints this:**

```text
LUNs on the SVM              1
igroup initiators (total)    1
LUN maps                     1
iSCSI sessions (this host)   2
multipath paths (this host)  2
```

And `multipath -ll` looks like this. **Two path groups at priority 50 and 10** is the sign that ALUA
is working:

```text
3600a0980<serial-hex> dm-0 NETAPP,LUN C-Mode
size=40G features='3 queue_if_no_path pg_init_retries 50' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| `- 0:0:0:0 sda     8:0   active ready running
`-+- policy='service-time 0' prio=10 status=enabled
  `- 1:0:0:0 sdb     8:16  active ready running
```

---

## Running it twice adds nothing

**The documented connection procedure is not idempotent.** Re-running its per-portal login loop adds
sessions, and on a Windows host that took a measured 16 paths to 24 with no warning — see
[Paths are the failover mechanism](../../../ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md) (日本語).

These scripts read current state first and create only what is missing. **Three consecutive passes in
the same environment left all five counts identical.**

| Count | Pass 1 | Pass 2 | Pass 3 |
|---|---|---|---|
| LUNs on the SVM | 1 | 1 | 1 |
| igroup initiators | 1 | 1 | 1 |
| LUN maps | 1 | 1 | 1 |
| iSCSI sessions | 2 | 2 | 2 |
| multipath paths | 2 | 2 | 2 |

Output from the second pass onward:

```text
lun    : exists, left alone
igroup : exists, left alone
member : iqn...:xxxxxxxxxxxx already in ig_xxxxxxxxxxxx
map    : /vol/<volume>/lun1 already mapped to ig_xxxxxxxxxxxx
  <iscsi-ip-1>    1 session(s) already present, skipped
  <iscsi-ip-2>    1 session(s) already present, skipped
```

**Judging is a separate script deliberately.** A script that both acts and judges its own result is
not evidence.

---

## Four stumbling points that only appeared when it ran

**All four passed `cfn-lint`, `shellcheck` and `validate-template`.** They surfaced on execution,
and they are listed in the order you are most likely to hit them.

### 1. CloudFormation demands `JunctionPath` even for a LUN-only volume

A volume that holds only a LUN has no reason to be mounted in the SVM namespace. Creating one without
a junction path fails:

```text
Resource handler returned message: "Parameter validation failed:
Missing required parameter in OntapConfiguration: "JunctionPath""
```

**The property reference marks `JunctionPath` as *Required: No* while the prose on the same page says
it is required.** The resource handler follows the prose. The template supplies one, but **that is a
control-plane constraint rather than a design choice.**

Being mounted does not expose the LUN's contents over NFS. Its name and size are visible; the data is
not.

### 2. The Amazon FSx API resolves to public addresses

In a private subnet carrying only the `ssm` and `secretsmanager` interface endpoints,
**`aws fsx describe-file-systems` times out.** Secrets Manager resolves to a `10.x` endpoint address
and works; `fsx.<region>.amazonaws.com` resolves to public addresses and does not.

The scripts take a bypass:

```bash
# Get these once from wherever your AWS CLI has reach.
aws fsx describe-file-systems --file-system-ids fs-xxxxxxxx \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]'
aws fsx describe-storage-virtual-machines \
  --query 'StorageVirtualMachines[?FileSystemId==`fs-xxxxxxxx`].Endpoints.Iscsi.IpAddresses[]'

sudo ./provision-lun.sh --management-ip <management-ip> --svm ... --volume ... --password-stdin
sudo ./connect-iscsi.sh --target-ips "<iscsi-ip-1> <iscsi-ip-2>"
```

**iSCSI itself needs none of this.** The LUN is reached inside the VPC. Only resolving the management
address needs the AWS API.

### 3. `iscsiadm -m session` exits 21 when there are no sessions

Under `set -o pipefail`, **zero sessions — the normal starting state — fails the whole pipeline**, so
the first run ends silently.

### 4. `iscsiadm -m node -p <portal>` prints a full record dump

It begins with `# BEGIN RECORD`, so taking field 2 of line 1 yields `BEGIN` instead of the target
name. **Discovery succeeds and the login then fails with "No records found"**, which reads like a
different problem. Parse the short listing, without `-p`, instead.

---

## Two corrections to earlier notes

| Recorded earlier | Measured |
|---|---|
| Creating an empty `/etc/multipath.conf` before `mpathconf --enable` leaves it alone | **It does not.** 29 bytes were written — empty `blacklist` and `defaults` blocks — against 334 when it writes from scratch. The resulting map still used NetApp's recommended `service-time 0` and `queue_if_no_path` |
| A space-reserved LUN consumes volume capacity immediately | **A LUN created through the REST API is not reserved by default** (`space.guarantee.requested` is `false`). The volume showed 352,256 bytes used against a 40 GiB LUN. `verify-block.sh` now prints the reservation flag next to the size |

The three-level capacity accounting itself is in
[Capacity is counted in three places](../../../ja/domains/block-storage/notes/capacity-is-counted-in-three-places.md) (日本語).
**The aggregate here reported 907.03 GiB, matching a separately created Single-AZ file system
exactly.**

---

## Teardown

**CloudFormation does not know about what the scripts created.** Remove the ONTAP objects first.

```bash
sudo ./verify-block.sh ...      # record what exists
sudo iscsiadm -m node -U all && sudo iscsiadm -m node -o delete
# then delete the LUN map, the igroup and the LUN through the ONTAP REST API or CLI
aws cloudformation delete-stack --stack-name fsxn-block-quickstart
```

Deletion took about eighteen minutes.

**If you created a FlexClone, empty the recovery queue before deleting volumes.** A deleted volume
waits there for at least twelve hours under a changed name, and a surviving FlexClone relationship
makes **the parent volume, its SVM and the entire file system undeletable.**

---

## Deliberately out of scope

| Not covered | Why, and where to go next |
|---|---|
| NVMe/TCP | It depends on the kernel, which is too much for a first pass. **`verify-block.sh` reports `CONFIG_NVME_MULTIPATH`**; it is not set on Amazon Linux 2023, and failover does not work in that state — see [the measured failover](../../../ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md#実測したフェイルオーバー) (日本語) |
| Windows and MPIO | A separate set of PowerShell steps. Host-side defaults are in [Paths are the failover mechanism](../../../ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md) (日本語) |
| Multi-AZ | Address layout and failover behaviour both change — see [Multi-AZ moves a route, not an address](../../../ja/domains/block-storage/notes/multi-az-moves-a-route-not-an-address.md) (日本語) |
| More than one HA pair | Block protocols are limited to six pairs and are disabled above that |
| Performance figures | A `t3.medium` cannot sustain 384 MBps, which is 3.07 Gbps. Methodology is in [Reading a published benchmark](../../../ja/domains/block-storage/notes/when-shared-block-changes-the-design.md#公開ベンチマークの読み方) (日本語) |
| CHAP and portsets | Authentication defaults to none. Configuration and failure symptoms are in [igroups are not the only access control](../../../ja/domains/block-storage/notes/igroups-are-not-the-only-access-control.md) (日本語) |

---

## Related documents

- [Domain — Block Storage](README.md) — the module hub
- [Decision tree: block protocol and layout](../../../ja/reference/decision-trees/block-protocol-and-layout.md) (日本語)
- [Comparison: block storage options](../../../ja/reference/comparison/block-storage-options.md) (日本語)
- [Block storage resource map](../../../ja/reference/block-storage-resource-map.md) (日本語)
- [Evidence Policy](../../evidence-policy.md)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/block-storage/quickstart.md) | [English](quickstart.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
