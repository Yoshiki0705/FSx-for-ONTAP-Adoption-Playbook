# Block storage on Amazon FSx for NetApp ONTAP — smallest runnable example

Reference for the files in this directory. The walkthrough, with the reasoning behind each step,
is the quickstart in the documentation tree:
[日本語](../../docs/ja/domains/block-storage/quickstart.md) ·
[English](../../docs/en/domains/block-storage/quickstart.md).

## Why a template and scripts rather than one artifact

A LUN, an igroup and a LUN map have no Amazon FSx API action and no CloudFormation resource type.
Provisioning block storage therefore crosses from the AWS control plane to ONTAP, and the crossing
falls between the volume and the LUN. The split here is that boundary, not a packaging preference.

The volume is created by the template rather than by the scripts on purpose. A volume created on the
ONTAP side receives no `fsvol` identifier, and is therefore absent from Amazon CloudWatch, from AWS
API tagging and from AWS Backup.

## Files

| File | What it does | Reaches |
|---|---|---|
| `fsxontap-iscsi-quickstart.yaml` | Single-AZ second-generation file system with one HA pair, one SVM, one volume for a LUN, one Amazon Linux 2023 client, two security groups, one IAM role | AWS API |
| `provision-lun.sh` | Creates the LUN, the igroup and the LUN map. Idempotent | ONTAP REST API |
| `connect-iscsi.sh` | Logs the host in over iSCSI and assembles the multipath map. Idempotent | Host, ONTAP iSCSI |
| `verify-block.sh` | Reports state from both sides. Creates nothing | ONTAP REST API, host |

## Template parameters

| Parameter | Default | Notes |
|---|---|---|
| `NamePrefix` | `fsxn-block-quickstart` | Lower-case. The SVM and volume names derive from it with hyphens removed, because ONTAP rejects them |
| `VpcId` | — | Existing VPC. No network is created |
| `ClientSubnetId` | — | Existing subnet for both the file system and the client |
| `FsxAdminSecretName` | — | Name or ARN of an existing Secrets Manager secret whose `SecretString` is JSON with a `password` key. Resolved at create time, so the password appears in no parameter, output or log. Amazon FSx accepts 8 to 50 characters |
| `StorageCapacityGiB` | `1024` | Documented minimum for one HA pair |
| `ThroughputCapacity` | `384` | Documented minimum for one HA pair |
| `VolumeSizeBytes` | 64 GiB | After the 5 percent snapshot reserve, about 60.8 GiB — the default 40 GiB LUN plus room for snapshots |
| `ClientInstanceType` | `t3.medium` | Chosen for cost. It cannot sustain 384 MBps |
| `ClientAmiId` | SSM public parameter | Resolved at deploy time, so no AMI ID is pinned |

Outputs give `FileSystemId`, `SvmName`, `VolumeName`, `ClientInstanceId` and the secret name. The
ONTAP management address is **not** an output, because `AWS::FSx::FileSystem` exposes no
`Fn::GetAtt` for it.

## Order

```bash
# 1. A secret for the fsxadmin password, if you do not already have one.
aws secretsmanager create-secret --name fsxn-quickstart-fsxadmin \
  --secret-string '{"password":"<8-50 characters>"}'

# 2. The AWS side. Around 17 minutes, almost all of it the file system.
aws cloudformation create-stack --stack-name fsxn-block-quickstart \
  --template-body file://fsxontap-iscsi-quickstart.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=VpcId,ParameterValue=vpc-... \
               ParameterKey=ClientSubnetId,ParameterValue=subnet-... \
               ParameterKey=FsxAdminSecretName,ParameterValue=fsxn-quickstart-fsxadmin

# 3. On the client, reached with: aws ssm start-session --target <ClientInstanceId>
sudo ./provision-lun.sh --file-system-id fs-... --svm <SvmName> \
  --volume <VolumeName> --secret-id fsxn-quickstart-fsxadmin
sudo ./connect-iscsi.sh --file-system-id fs-...
sudo ./verify-block.sh --file-system-id fs-... --svm <SvmName> \
  --volume <VolumeName> --secret-id fsxn-quickstart-fsxadmin
```

## What the client needs to reach

Systems Manager to log in, Secrets Manager to read the password, and the Amazon FSx API to resolve
the ONTAP management address. Give it a NAT gateway, a public address, or interface VPC endpoints for
`ssm`, `ssmmessages`, `ec2messages`, `secretsmanager` and `fsx`.

A subnet carrying only the Systems Manager and Secrets Manager endpoints leaves the Amazon FSx API
unreachable, because `fsx.<region>.amazonaws.com` resolves to public addresses. Both scripts then
need the AWS API bypassed:

```bash
# Get these once from wherever your AWS CLI has reach.
aws fsx describe-file-systems --file-system-ids fs-... \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]'
aws fsx describe-storage-virtual-machines \
  --query 'StorageVirtualMachines[?FileSystemId==`fs-...`].Endpoints.Iscsi.IpAddresses[]'

sudo ./provision-lun.sh --management-ip <management-ip> --svm ... --volume ... --password-stdin
sudo ./connect-iscsi.sh --target-ips "<iscsi-ip-1> <iscsi-ip-2>"
```

Nothing about iSCSI itself needs any of this. The LUN is reached inside the VPC.

## Idempotency

`provision-lun.sh` and `connect-iscsi.sh` read current state before acting, so a second run changes
nothing. `verify-block.sh` prints the five counts that must stay fixed:

```text
LUNs on the SVM              1
igroup initiators (total)    1
LUN maps                     1
iSCSI sessions (this host)   2
multipath paths (this host)  2
```

Measured over three consecutive passes on `SINGLE_AZ_2` / ONTAP 9.18.1P5 / `ap-northeast-1` /
Amazon Linux 2023 kernel 6.18.44 on 2026-09-05: identical every time. This property is worth
asserting because the documented connection procedure does not have it — re-running its per-portal
login loop adds sessions, and on a Windows host that took a measured 16 paths to 24 without a
warning.

## Teardown

```bash
# The scripts create nothing that CloudFormation knows about, so remove the ONTAP objects first.
sudo ./verify-block.sh ...            # note what exists
sudo iscsiadm -m node -U all && sudo iscsiadm -m node -o delete
# then delete the LUN map, igroup and LUN through the ONTAP REST API or CLI, and finally:
aws cloudformation delete-stack --stack-name fsxn-block-quickstart
```

A deleted ONTAP volume waits in the recovery queue for at least 12 hours under a changed name. If a
FlexClone relationship survives there it blocks the parent volume, its SVM and the whole file system
from being deleted. Purge the queue before deleting a stack that had clones in it.

## Deliberately out of scope

NVMe/TCP, Windows, Multi-AZ, more than one HA pair, and any throughput measurement. The client
instance type cannot sustain the provisioned rate, so a number measured here would describe its
network interface. For NVMe/TCP, check `CONFIG_NVME_MULTIPATH` in your kernel first —
`verify-block.sh` reports it, and it is not set on Amazon Linux 2023.
