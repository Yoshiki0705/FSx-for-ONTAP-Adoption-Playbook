# Multiprotocol permissions with Active Directory — smallest runnable example

Reference for the files in this directory. This environment exists to answer one question:

> On an NTFS-security-style volume, what happens to a permission set over SMB when the same data is
> read over NFSv4.1 by the same Active Directory user?

Two further questions ride along, because a single `volume rehost` answers both and the file system
is already standing:

- Does a volume keep its security style when it moves to an SVM whose root volume has a different one?
- Does the AWS control plane follow the ownership change?

The design notes this environment reproduces are
[LUN の中身はファイルプロトコルに現れない](../../docs/ja/domains/block-storage/notes/lun-contents-do-not-reach-file-protocols.md),
[`volume rehost` が変えるのは所有 SVM だけ](../../docs/ja/domains/block-storage/notes/volume-rehost-changes-ownership-not-contents.md)
and
[SMB で運用中のボリュームに NFS を足すのに複製は要らない](../../docs/ja/domains/multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md).

## If this is your first time here, read in this order

This file is a reference, not a tutorial, so it is not ordered for a first read. This is:

1. **[Cost](#cost)** and **[Spending less than the table](#spending-less-than-the-table)** — the file
   system and the directory bill until deleted and cannot be stopped. Decide the teardown date first.
2. **[If you already run Active Directory](#if-you-already-run-active-directory)** — decides whether
   you deploy the whole stack or reuse a domain you already have.
3. **[Template parameters](#template-parameters)** — the "if it is wrong" column is the useful one.
   Then run `preflight.sh`, which fills the parameters in and checks the account.
4. **[Order](#order)** — the runbook.
5. **[What the first end-to-end run actually cost](#what-the-first-end-to-end-run-actually-cost)** —
   the failures, and what each one looked like before it was understood. Worth reading *before* you
   hit them.
6. **[Teardown](#teardown)** — read it before you deploy, not after.

**If you only want the finding and not the environment**, read
[NFS 側から見える権限表現が実際の可否と一致しない](../../docs/ja/domains/multiprotocol-identity/notes/nfs-side-view-does-not-explain-ntfs-denials.md)
and stop there. Nothing in this directory needs to run for that result to be usable.

## Provenance

Nothing here was written from a blank file.

| Borrowed | From |
|---|---|
| Secret handling, security group split with ingress outside the group, ONTAP name derivation, resolved AMI parameters, the `ontap()` / `ontap_ok()` helpers, curl credential escaping, idempotence | [`examples/block-storage/`](../block-storage/) in this repository |
| `AWS::SSM::Association` with `AWS-JoinDirectoryServiceDomain` targeting instance IDs, `dnsIpAddresses` passed explicitly | [`Solutions/DirectoryADClients/DIRECTORY-AD-CLIENTS.yaml`](https://github.com/aws-cloudformation/aws-cloudformation-templates/blob/main/Solutions/DirectoryADClients/DIRECTORY-AD-CLIENTS.yaml) (AWS-published) |
| `AWS::DirectoryService::MicrosoftAD` shape, `Edition`, `VpcSettings` | [AWS CloudFormation property reference](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-directoryservice-microsoftad.html) |
| `ActiveDirectoryConfiguration` having no managed-AD variant, `FileSystemAdministratorsGroup` defaulting to Domain Admins | [AWS CloudFormation property reference](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-fsx-storagevirtualmachine-activedirectoryconfiguration.html) |
| The intermediate OU, Domain Admins being what works, the NetBIOS constraints, the SSM-association form of the domain join | Carried-over findings in [`docs/agent/domain-knowledge.md`](../../docs/agent/domain-knowledge.md) |
| Minimum SSD 1,024 GiB per HA pair, first-generation throughput options starting at 128 MBps | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html), [Availability, durability, and deployment options](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/high-availability-AZ.html) |
| Ports needed for a working NFS mount and SMB locking, not port 2049 alone | [Multiprotocol access without Active Directory integration](https://www.repost.aws/articles/ARTG4-JD8UQ_igrHwSoxytOA/fsx-for-netapp-ontap-fsxn-multiprotocol-access-without-active-directory-integration) (repost.aws) |
| The directory's controllers security group accepting AD traffic from the VPC CIDR by default | [AWS Managed Microsoft AD best practices](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_best_practices.html) |
| Setting NTFS ACEs without an SMB client, the `acls[]` / `apply_to` / `propagation_mode` shape, `effective-permissions` as an independent signal, ONTAP 9.9.1 as the floor | [Manage file security permissions and audit policies](https://docs.netapp.com/us-en/ontap-restapi-991/manage_file_security_permissions_and_audit_policies.html) (NetApp ONTAP REST reference) |
| One REST call standing in for six `vserver security file-directory` commands | [Prepare a NAS file system](https://docs.netapp.com/us-en/ontap-automation/workflows/wf_nas_fs_prepare.html) (NetApp ONTAP automation) |
| The same API on FSx for ONTAP: storage-layer evaluation, SMB bypassed, `OI`/`CI` inheritance flags | [Manage NTFS permissions at scale on Amazon FSx for NetApp ONTAP](https://aws.amazon.com/blogs/storage/manage-ntfs-permissions-at-scale-on-amazon-fsx-for-netapp-ontap/) (AWS Storage Blog) |
| No API for creating a directory user; `dsa.msc` on an instance with the administration tools is the documented path | [Creating an AWS Managed Microsoft AD user](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_manage_users_groups_create_user.html) |
| `AmazonSSMManagedInstanceCore` + `AmazonSSMDirectoryServiceAccess` being the stated requirement for creating users and groups | [Installing Active Directory Administration Tools](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_install_ad_tools.html) |
| Installing the administration tools over Session Manager instead of opening RDP ingress | [Manage AWS Managed Microsoft AD resources with Session Manager port forwarding](https://aws.amazon.com/blogs/mt/manage-aws-managed-microsoft-ad-resources-with-session-manager-port-forwarding/) (AWS Cloud Operations Blog) |

## If you already run Active Directory

**The finding this example produces does not depend on which Active Directory you use.** What is
measured is how ONTAP evaluates an NTFS security descriptor and what an NFS client can see of it.
That is a property of the volume's security style and of name mapping, not of where the domain
controllers run.

The **stack** does depend on it: it creates AWS Managed Microsoft AD because that is the shortest
path to a disposable domain. If you already have a domain, you do not need that part.

| You have | What changes in this example |
|---|---|
| AWS Managed Microsoft AD already | Delete the `Directory` resource, pass the existing directory's DNS addresses to the join association, and keep everything else. The intermediate OU still applies |
| Self-managed AD on EC2, same VPC | Same as above. `ActiveDirectoryConfiguration` on the SVM takes the DNS addresses and a join account either way — there is **no managed-AD-specific variant** of it |
| Self-managed AD on premises, reached over Direct Connect or a VPN | Same again, plus: the file system's security group must reach the domain controllers across that link, and **the intermediate OU does not exist** in a self-managed domain. A value copied from this README's example will fail there — use your own OU path |
| No AD, and you want NFS only | You do not need this example. A UNIX-security-style volume evaluates mode bits and the whole question disappears. The measurement's control volume is exactly that case |

**The one thing that is genuinely managed-AD-specific is the intermediate OU** (`OU=Computers,OU=<NetBIOS>`),
and it is the most common cause of an SVM that reports healthy without being joined. In both
directions: a self-managed path copied into a managed directory fails, and a managed path copied into
a self-managed directory fails.

`preflight.sh` assumes it will create the directory, so skip its Managed Microsoft AD checks if you
are reusing one. Everything else it checks still applies.

## Why a template and scripts rather than one artifact

The SMB share, the export policy rules, the NTFS ACEs, the name mappings, any FlexClone and the
volume rehost have no Amazon FSx API action and no CloudFormation resource type. The split here is
that control-plane boundary, the same one that puts LUNs and igroups outside the template in
[`examples/block-storage/`](../block-storage/).

## Files

| File | What it does | Reaches |
|---|---|---|
| `preflight.sh` | **Run this first.** Read-only. Checks the account and VPC against every condition that was measured to break this example, and writes a filled-in parameters file | AWS API (describe/get only) |
| `fsxontap-multiprotocol-ad.yaml` | First-generation Single-AZ file system, AWS Managed Microsoft AD, two AD-joined SVMs, an NTFS volume, a UNIX control volume, a volume for the rehost probe, a Windows client, a Linux client | AWS API |
| `provision-multiprotocol.sh` | Export policy and rule, SMB share, the UNIX identity the AD user maps to, both name-mapping directions. Idempotent | ONTAP REST API |
| `set-test-acls.sh` | Sets the Allow, Deny and inherited ACEs at the storage layer and records them. **Part 1 of 3 of the record** | ONTAP REST API |
| `set-test-acls.ps1` | The same ACEs through an SMB client, for comparison. **Optional** — see [the gap section](#a-gap-found-on-first-use-and-the-wrong-fix-for-it) | Windows, SMB |
| `read-effective-permissions.sh` | Records what NFS shows and whether access succeeds. **Parts 2 and 3** | Host, NFSv4.1 |
| `rehost-probe.sh` | Records the volume before and after a `volume rehost`. Records only, unless `--apply` | ONTAP REST API, AWS API |
| `teardown.sh` | Removes everything in the order measured to work, refuses to start when something would strand the stack, and proves afterwards that each resource is gone. Reports only, unless `--apply` | AWS API, ONTAP REST API |

## What a finished run looks like

Check against this rather than against "the scripts exited 0". Each row is a file or a value you
should be able to point at.

| # | Done when | Where it is |
|---|---|---|
| 1 | Both SVMs report **discovered domain controllers**, not just `Lifecycle: CREATED` | `GET /api/protocols/cifs/domains?fields=svm.name,discovered_servers` |
| 2 | The AD test user exists and is **not** in the file system administrators group | `Get-ADUser mpadtest -Properties MemberOf` |
| 3 | Part 1 of the record exists, and every ACE shows non-empty rights | whatever `set-test-acls.sh --out` wrote: `subjects[].sd.acls[].advanced_rights` |
| 4 | Part 2 and 3 exist for **both** the NTFS volume and the UNIX control volume | the two files `read-effective-permissions.sh --out` wrote, one per volume: `results[].nfsv4_acl_status` == `ok` |
| 5 | The NFSv4 ACL was actually readable, not `unsupported` | same field. If it says `unsupported`, remount and re-run |
| 6 | The control volume produced a **different outcome** from the NTFS volume on at least one path | compare `results[].write` across those two files |
| 7 | Teardown reports every resource as gone | `teardown.sh` verification section |

**Row 6 is the one that decides whether you measured anything.** If both volumes behave identically,
the result is a statement about your environment, not about security styles, and the record should not
be quoted as the latter.

### What to hand over at the end

The three JSON files are the deliverable, not the terminal output. Each carries its own environment
block — ONTAP version, region, security style, timestamp, caller — so a reader who was not present can
tell what was measured and decide whether it transfers to their own case. Keep them together with the
teardown log; the failures are as reusable as the result.

If you are producing this for someone else, the useful summary is three sentences: what was set, what
the other protocol showed, and whether access succeeded. Anything shorter loses the part that makes it
checkable.

## Why the record has three parts

A permission result is only usable when all three are present:

| Part | Question it answers |
|---|---|
| The ACE as set | What was asked for |
| The representation NFS shows | What survived the translation |
| The outcome of a real read and write | Whether the translation is what governs the decision |

**Two out of three is not a finding.** Reading only the mode bits is the specific failure this is
built to prevent: POSIX mode bits cannot express a Deny, so a Deny ACE that did survive into the
NFSv4 ACL looks absent when only `stat` is consulted.

## The control volume is not optional

`unixvol` exists so that a result on `ntfsvol` can be attributed to the security style rather than to
the export policy, to sssd, or to the name mapping. Same clients, same policy, same user, same files
— only the style differs. **Run `read-effective-permissions.sh` against both, or the run produces an
observation about the environment rather than about the security style.**

## Template parameters

Nine parameters have no usable default because they describe **your** account. `preflight.sh
--write-params` fills all nine in and derives the one that is most often wrong. The table below is
for deciding, not for copying: it says where to find each value and what a wrong one does.

**Read the last column before the second.** Every one of these failures was observed, and most of
them do not look like a wrong parameter when they happen.

| Parameter | Default | How to choose it, in your own account | If it is wrong |
|---|---|---|---|
| `VpcId` | — | Any VPC whose subnets can reach the domain controllers. No network is created.<br>`aws ec2 describe-vpcs --query 'Vpcs[].[VpcId,CidrBlock,IsDefault]' --output table` | Private DNS on the interface endpoints silently does nothing when the VPC has `enableDnsSupport` or `enableDnsHostnames` off, and the domain join then times out with the endpoints present |
| `PrimarySubnetId` | — | Holds the file system and both clients.<br>`aws ec2 describe-subnets --filters Name=vpc-id,Values=<vpc> --query 'Subnets[].[SubnetId,AvailabilityZone,CidrBlock]' --output table`<br>Its CIDR is also the `--client-match` value for `provision-multiprotocol.sh` | A subnet with no egress and no interface endpoints leaves both clients unjoined while Systems Manager keeps working |
| `SecondAzSubnetId` | — | **A different Availability Zone** from the primary. Used only by the directory | Same AZ for both is rejected at directory creation. AWS Managed Microsoft AD always deploys two domain controllers across two AZs; this is not reducible to one, and the file system stays Single-AZ regardless |
| `DomainName` | `corp.example.com` | A name you are willing to have resolve **inside this VPC only**. It does not need to exist publicly, and using a name you own publicly is the more confusing choice | A directory with the same name already in the account fails the stack ~40 minutes in, after the file system is already billing |
| `DomainShortName` | `CORP` | The NetBIOS name, 15 characters or fewer | Must differ from the SVM NetBIOS names the template derives from `NamePrefix`. A collision is rejected at SVM creation, after the directory is built |
| `OrganizationalUnitDistinguishedName` | — | **Required on purpose.** `OU=Computers,OU=<DomainShortName>,DC=…` — see below | Omitting the intermediate OU produces **no validation error**. The stack reaches `CREATE_COMPLETE` and the SVM settles in `MISCONFIGURED` |
| `AdAdminSecretName` | — | A secret containing `{"password": "..."}` for the directory `Admin`, 8–64 characters using three of the four character classes.<br>`aws secretsmanager create-secret --name mpad-ad-admin --secret-string '{"password":"..."}'` | A secret without a `password` **key** fails at resolve time, because the template reads `{{resolve:secretsmanager:<name>:SecretString:password}}`. The key name is not optional |
| `FsxAdminSecretName` | — | Same shape, for ONTAP `fsxadmin`, 8–50 characters | As above. `preflight.sh` checks both for the key and the length |
| `NamePrefix` | `fsxn-mp-ad` | Lower-case, short. SVM and volume names derive from it with hyphens removed, because ONTAP accepts only alphanumerics and underscores | A long prefix pushes the derived SVM NetBIOS name past 15 characters. **Do not change it on an existing stack:** the SVM name derives from it, and changing an SVM name means replacing the SVM |
| `StorageCapacityGiB` | `1024` | Leave it. This is the documented minimum per HA pair | Lower values are rejected. Higher values raise the largest line in the cost table |
| `ThroughputCapacity` | `128` | Leave it. The documented minimum for the first generation | The second-generation minimum is 384 MBps at a higher per-MBps rate, so a value copied from a second-generation deployment multiplies the cost |
| `VolumeSizeBytes` | 10 GiB | Leave it. The volumes hold a handful of directories | Larger volumes do not make the measurement better and are not free |
| `WindowsInstanceType` | `t3.large` | Only creates the Active Directory test user | `t3.medium` works but leaves little headroom for the administration tools |
| `LinuxInstanceType` | `t3.medium` | Runs every script | **Cannot sustain the provisioned throughput.** Deliberate: this example measures permissions, not throughput. Do not read any bandwidth number off it |
| `CreateClientVpcEndpoints` | `true` | Creates interface endpoints for the Directory Service and Amazon FSx APIs. Set `false` **only** when the subnet already has a NAT gateway or those endpoints | With `false` and no other egress, both clients fail the domain join and the rehost probe cannot time the AWS control plane. `preflight.sh` reports which endpoints already exist |
| `WindowsAmiId` / `LinuxAmiId` | SSM public parameters | Leave them. They resolve to the current AMI at deploy time | Pinning an old AMI can predate the SSM Agent version the domain join needs |

### Permissions the operator needs

This list is derived from the calls the template and the scripts were observed to make, not from an
IAM audit, so treat it as a starting point and expect your account's guardrails to narrow it.

| Purpose | Actions |
|---|---|
| Deploy and remove the stack | `cloudformation:CreateStack`, `UpdateStack`, `DeleteStack`, `CreateChangeSet`, `DescribeChangeSet`, `ExecuteChangeSet`, `DescribeStacks`, `DescribeStackEvents`, `DescribeStackResources` |
| The resources it creates | `fsx:*` on the file system, SVMs and volumes; `ds:CreateMicrosoftAD`, `DescribeDirectories`, `DeleteDirectory`, `GetDirectoryLimits`; `ec2:*` for the security groups, endpoints and instances; `iam:CreateRole`, `PutRolePolicy`, `AttachRolePolicy`, `CreateInstanceProfile`, `PassRole` |
| Reach the hosts | `ssm:SendCommand`, `GetCommandInvocation`, `StartSession`, `DescribeInstanceInformation`, `DescribeAssociationExecutions`, `StartAssociationsOnce` |
| The secrets | `secretsmanager:CreateSecret`, `GetSecretValue`, `DeleteSecret` on the two secrets |
| `preflight.sh` only | Read-only: `ec2:Describe*`, `ds:DescribeDirectories`, `ds:GetDirectoryLimits`, `secretsmanager:GetSecretValue`, `sts:GetCallerIdentity` |

`iam:PassRole` and `CAPABILITY_IAM` are the two that most often stop a first attempt in an account
with tight guardrails. If IAM role creation is not available to you, create the two instance roles
separately and adapt the template to take their ARNs as parameters — the roles are the only IAM the
stack needs.

### Why `OrganizationalUnitDistinguishedName` has no default

AWS Managed Microsoft AD inserts an intermediate OU. The value must be

```text
OU=Computers,OU=<DomainShortName>,DC=<label>,DC=<label>,...
```

for example `OU=Computers,OU=CORP,DC=corp,DC=example,DC=com`.

**Omitting the intermediate OU produces no validation error.** The stack reaches `CREATE_COMPLETE`,
the join fails afterwards, and the SVM settles in `MISCONFIGURED`. A self-managed Active Directory
has no intermediate OU, so a value copied from a self-managed setup is the usual cause. Making the
parameter required is what puts the requirement in front of the operator instead of inside a default.

## Cost

At the defaults: 1,024 GiB SSD, 128 MBps throughput, a Standard-edition directory with two domain
controllers, a `t3.large` Windows client and a `t3.medium` Linux client.

Measured build time, ap-northeast-1, 2026-09-11: **43 minutes**, of which the directory is 40. The
meter starts when the file system and the directory appear, not when the stack completes.

| Line | Rate | Monthly (730 h) | Hourly |
|---|---|---|---|
| FSx for ONTAP SSD | $0.150 / GB-month | $153.60 | $0.2104 |
| FSx for ONTAP throughput | $0.906 / MBps-month | $115.97 | $0.1588 |
| Managed Microsoft AD Standard | $0.073 / hour / DC × 2 | $106.58 | $0.1460 |
| Windows `t3.large` | $0.1364 / hour | $99.57 | $0.1364 |
| Linux `t3.medium` | $0.0544 / hour | $39.71 | $0.0544 |
| EBS gp3, 70 GiB | $0.096 / GB-month | $6.72 | $0.0092 |
| Directory Service interface endpoint, 2 AZs | $0.014 / AZ-hour | $20.44 | $0.0280 |
| Amazon FSx interface endpoint, 2 AZs | $0.014 / AZ-hour | $20.44 | $0.0280 |
| **Total** | | **$563.03** | **$0.7713** |

Rates from the AWS Price List API, On-Demand, `ap-northeast-1`, retrieved 2026-09-11; both endpoint
lines added 2026-09-12. The monthly figures are arithmetic on the defaults, not amounts read off a
bill. Set `CreateClientVpcEndpoints=false` to drop both lines when the subnet already has a NAT
gateway or these endpoints — but read what its absence looks like before deciding, because the
symptom is a domain join that fails while everything else reports healthy.

**Only the EC2 instances can be stopped.** The file system, the directory and both endpoints bill
until they are deleted, which is **$0.5805 per hour, about $13.93 a day, with both instances
stopped**. A three-day run with the instances up eight hours a day is about $46. Forgotten for a
month with the instances stopped it is about $424, and about $563 with them left running.

Fix a teardown date before you start. **Read [Teardown](#teardown) first.**

### Spending less than the table

Three reductions, in the order they save the most for the least loss of meaning.

| Reduction | Saves | What you give up |
|---|---|---|
| **Do not deploy the Windows client at all**, if you already have a domain-joined host with the Active Directory administration tools. Creating the test user is the only thing this example needs Windows for, and it does not have to be *this* Windows | $0.1364/hour plus its EBS, from the start | Nothing for the measurement. Set `WindowsInstanceType` aside and delete the `WindowsClient`, `WindowsRole`, `WindowsInstanceProfile` and the Windows target in `JoinDomainAssociation` |
| **Stop the Windows client as soon as the test user exists**, if you did deploy it. Its only job takes minutes; it then sits idle for the rest of the run | $0.1364/hour for the remainder | Nothing, unless you want the optional SMB-side comparison. Restart it then |
| **Skip the destination SVM and the rehost volume** if you only want the permission finding | Nothing directly — they are storage inside the same file system — but it removes the rehost probe's 20-minute wait and the teardown's extra step | The rehost measurement. The permission measurement does not use either |
| Drop `CreateClientVpcEndpoints` if the subnet already has a NAT gateway | $0.056/hour | Nothing. `preflight.sh` tells you whether it applies |

```bash
# After step 4 (the AD test user exists), the Windows client is idle:
aws ec2 stop-instances --instance-ids <WindowsClientInstanceId>
```

**What cannot be reduced is the pair that dominates the bill**: the file system's SSD and provisioned
throughput are billed on what was provisioned, and the directory cannot be stopped at all. Neither
responds to using the environment less, which is why the teardown date matters more than any of the
reductions above.

## Order

```bash
# 0. Preflight. Read-only, takes seconds, and every check in it exists because its absence produced
#    a failure that presented as something else. It also writes the parameters file for you, with
#    the organizational unit derived correctly - the value most often wrong on a first attempt.
./preflight.sh --vpc-id vpc-... --primary-subnet subnet-... --second-subnet subnet-... \
  --domain-name corp.example.com --domain-short-name CORP \
  --ad-secret mpad-ad-admin --fsx-secret mpad-fsxadmin \
  --write-params params.json
#    Exit 0 means nothing blocking. Exit 1 lists what to fix first. WARN lines about the ds and fsx
#    endpoints are expected on a subnet without a NAT gateway: the template creates both.

# 1. Two secrets, if you do not already have them.
aws secretsmanager create-secret --name mpad-ad-admin \
  --secret-string '{"password":"<8-64 chars, three of the four character classes>"}'
aws secretsmanager create-secret --name mpad-fsxadmin \
  --secret-string '{"password":"<8-50 chars>"}'

# 2. The AWS side. Measured once end to end on 2026-09-11 in ap-northeast-1: 43 minutes total.
#    The directory took 40 of them and is the whole critical path; the file system finished in 17
#    minutes alongside it, the two SVM joins took about 2, and the three volumes about 1. Budget an
#    hour and do not read a long-running Directory resource as a hang.
#
#    Parameters go in a JSON file, NOT in the ParameterKey=...,ParameterValue=... shorthand. The
#    shorthand splits on commas, and a distinguished name is full of them:
#      Error parsing parameter '--parameters': Second instance of key "DC" encountered
#    That is a CLI parsing failure, not a template problem, and it happens before anything is
#    validated - so it looks like the template is wrong when it is not.
cat > params.json <<'JSON'
[
  {"ParameterKey":"VpcId","ParameterValue":"vpc-..."},
  {"ParameterKey":"PrimarySubnetId","ParameterValue":"subnet-..."},
  {"ParameterKey":"SecondAzSubnetId","ParameterValue":"subnet-..."},
  {"ParameterKey":"DomainName","ParameterValue":"corp.example.com"},
  {"ParameterKey":"DomainShortName","ParameterValue":"CORP"},
  {"ParameterKey":"AdAdminSecretName","ParameterValue":"mpad-ad-admin"},
  {"ParameterKey":"FsxAdminSecretName","ParameterValue":"mpad-fsxadmin"},
  {"ParameterKey":"OrganizationalUnitDistinguishedName","ParameterValue":"OU=Computers,OU=CORP,DC=corp,DC=example,DC=com"}
]
JSON
aws cloudformation create-stack --stack-name fsxn-mp-ad \
  --template-body file://fsxontap-multiprotocol-ad.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters file://params.json

# 3. BEFORE anything else: confirm both SVMs joined. CREATE_COMPLETE does not mean they did, and
#    neither does Lifecycle=CREATED. Measured on an unrelated file system in the same account on
#    2026-09-11: three SVMs reported Lifecycle=CREATED, ActiveDirectoryConfiguration populated, and
#    ONTAP reported cifs enabled=true with the domain FQDN set - while ONTAP had discovered ZERO
#    domain controllers. Every signal said healthy and no domain user could have authenticated.
#
#    So check the DC count, not the lifecycle:
aws fsx describe-storage-virtual-machines \
  --query 'StorageVirtualMachines[].[Name,Lifecycle,LifecycleTransitionReason.Message]' --output table
#    ... and then, through the ONTAP REST API:
#      GET /api/protocols/cifs/domains?fields=svm.name,discovered_servers
#    A populated discovered_servers list is the signal. An empty one means no domain user can be
#    authenticated regardless of what the other three fields say.
#
#    The SVMs joining says NOTHING about the CLIENTS joining: Amazon FSx joins from the service side
#    and never traverses the VPC, while the clients run the join on themselves. Both clients failed
#    on the first run here. Check the association, not just the stack:
aws ssm describe-association-executions --association-id <id> \
  --query 'AssociationExecutions[0].[Status,CreatedTime]' --output text
#    ... and on each host:
#      Windows: (Get-WmiObject Win32_ComputerSystem).PartOfDomain
#      Linux:   realm list  &&  id 'CORP\Admin'
#
#    A failed association does not retry promptly. Re-run it once the cause is fixed:
aws ssm start-associations-once --association-ids <id>
#
#    Windows then joins. LINUX WILL STILL FAIL with "***Failed: Cannot find parent directory Id"
#    unless the seamless-domain-join service account and its secret exist - see the gap section.
#    For a disposable environment the documented manual join is fewer moving parts, and the Linux
#    role can already read the AD secret, so the password never crosses the SSM parameter boundary:
#      PW=$(aws secretsmanager get-secret-value --secret-id mpad-ad-admin \
#             --query SecretString --output text | jq -r .password)
#      printf %s "$PW" | sudo realm join -U Admin corp.example.com

# 4. Create the test user in Active Directory, from the Windows client. There is no AWS API for
#    this; an instance with the administration tools is the documented path. The tools are
#    installed by the template's UserData.
#
#    It must NOT be in Domain Admins: members of the file system administrators group bypass the
#    evaluation being measured and every access succeeds.
#
#    Read the directory Admin password interactively - never as an argument, never as an SSM
#    command parameter. The Windows role can fetch it from Secrets Manager:
#      $s = (Get-SECSecretValue -SecretId mpad-ad-admin).SecretString | ConvertFrom-Json
#      New-ADUser -Name mpadtest -AccountPassword (Read-Host -AsSecureString) -Enabled $true `
#        -Credential (New-Object PSCredential('CORP\Admin', (ConvertTo-SecureString $s.password -AsPlainText -Force)))

# 5. ONTAP side, from the Linux client.
#
#    --file-system-id needs a route to the Amazon FSx API. This subnet has no NAT and no fsx
#    endpoint, so pass --management-ip instead; the script says so when the lookup times out:
#      --management-ip $(aws fsx describe-file-systems --file-system-ids fs-... \
#          --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' --output text)
sudo ./provision-multiprotocol.sh --file-system-id fs-... \
  --svm <SourceSvmName> --ntfs-volume <NtfsVolumeName> --unix-volume <UnixVolumeName> \
  --rehost-volume <RehostVolumeName> --client-match <client-subnet-cidr> \
  --ad-user 'CORP\mpadtest' --secret-id mpad-fsxadmin

# 6. Mount, and create the tree. CONFIRM THE MOUNT BEFORE WRITING: a refused mount leaves the
#    directories on local disk and `ls` looks perfectly correct. That happened here.
sudo mkdir -p /mnt/ntfsvol /mnt/unixvol
sudo mount -t nfs4 -o minorversion=1,sec=sys <nfs-ip>:/ntfsvol /mnt/ntfsvol
sudo mount -t nfs4 -o minorversion=1,sec=sys <nfs-ip>:/unixvol /mnt/unixvol
mountpoint -q /mnt/ntfsvol || { echo 'REFUSING: not mounted'; exit 1; }

#    On the NTFS volume, create the tree AS THE TEST USER. root has no unix_win mapping, so ONTAP
#    cannot evaluate it and even mkdir returns EACCES. On the UNIX control volume root is fine.
sudo su -s /bin/bash -c 'mkdir -p /mnt/ntfsvol/{allow,deny,inherited}
  for d in allow deny inherited; do echo probe > /mnt/ntfsvol/$d/probe.txt; done' 'CORP\mpadtest'

# 7. Set the ACEs. Part 1 of the record. From the LINUX client, through the ONTAP REST API - no SMB
#    client involved. The scripts must live somewhere the test user can reach (/opt/mp, mode 755);
#    /home/ec2-user is not readable by a domain user.
./set-test-acls.sh --management-ip <mgmt-ip> --svm <SourceSvmName> --volume <NtfsVolumeName> \
  --ad-user 'CORP\mpadtest' --secret-id mpad-fsxadmin --out acls-ntfs.json

#    Then the inheritance child, AFTER the inheritable ACE exists, and again as the test user.
sudo su -s /bin/bash -c 'mkdir -p /mnt/ntfsvol/inherited/child
  echo probe > /mnt/ntfsvol/inherited/child/probe.txt' 'CORP\mpadtest'
#
#    Optional, and only to compare an SMB-side path against the storage-side one:
#      .\set-test-acls.ps1 -SharePath \\CORPSRC.corp.example.com\ntfsshare -AdUser CORP\mpadtest

# 8. Remount. provision-multiprotocol.sh only just enabled NFSv4 ACLs, and an existing mount keeps
#    the capability set it negotiated. Skip this and nfs4_getfacl still answers "not supported".
sudo umount /mnt/ntfsvol /mnt/unixvol
sudo mount -t nfs4 -o minorversion=1,sec=sys <nfs-ip>:/ntfsvol /mnt/ntfsvol
sudo mount -t nfs4 -o minorversion=1,sec=sys <nfs-ip>:/unixvol /mnt/unixvol

# 9. Parts 2 and 3, twice, AS THE TEST USER and not root. The script refuses to run as root, and it
#    mounts with sudo when the target is not already a mountpoint - which a domain user cannot do.
#    So hand it the mount made above, with --keep-mounted.
./read-effective-permissions.sh --nfs-endpoint <nfs-ip> --junction /ntfsvol --style ntfs \
  --mountpoint /mnt/ntfsvol --keep-mounted --ontap-version <version> --out ntfs.json
./read-effective-permissions.sh --nfs-endpoint <nfs-ip> --junction /unixvol --style unix \
  --mountpoint /mnt/unixvol --keep-mounted --ontap-version <version> --out unix.json

# 10. Only once the record is complete: the rehost probe. Records first, applies never
#     unless told twice.
./rehost-probe.sh --file-system-id fs-... --source-svm <SourceSvmName> \
  --destination-svm <DestinationSvmName> --volume <RehostVolumeName> \
  --secret-id mpad-fsxadmin --out rehost-before.json
```

### How long the whole thing takes, and where the time actually goes

The 43-minute build is the part that is easy to plan for. It is not the part that consumed the time.

| Phase | Measured | Note |
|---|---|---|
| Stack build | 43 min | The directory is 40 of it, and runs in parallel with the file system |
| Getting both clients domain-joined | Not a fixed cost | Zero if `preflight.sh` is clean. It was the largest single delay on the first run, and the cause was a missing VPC endpoint |
| Provisioning and the permission measurement | ~30 min | Includes creating the tree, setting the ACEs, and two `read-effective-permissions.sh` runs |
| Rehost probe with `--apply` | ~25 min | Almost entirely waiting for the AWS control plane |
| Teardown | 5 min, **or 25** | 5 if nothing outside the stack holds one of its security groups. 25 if something does, because the stack spends ~21 minutes failing first. `teardown.sh` checks in advance |

**Budget half a day for a first run including reading, not the 43 minutes.** If you are running this
in a shared account or a workshop slot, the teardown row is the one that ruins a schedule, and it is
avoidable: run `teardown.sh` without `--apply` before you need the slot.

Endpoints, when you need them:

```bash
aws fsx describe-storage-virtual-machines --storage-virtual-machine-ids svm-... \
  --query 'StorageVirtualMachines[0].Endpoints.{Nfs:Nfs.IpAddresses,Smb:Smb.DNSName}'
```

The ONTAP version, for the record:

```bash
curl -sk -u "fsxadmin:$PW" "https://${MGMT_IP}/api/cluster?fields=version.full" | jq -r .version.full
```

## When the SVM does not join

`provision-multiprotocol.sh` refuses to continue when the SVM has no CIFS server, because every
result after that point would be about the join rather than about the security style. The two usual
causes, in order of frequency:

1. `OrganizationalUnitDistinguishedName` without the intermediate `OU=Computers,OU=<ShortName>`.
2. `FileSystemAdministratorsGroup` set to something other than `Domain Admins`. The group named
   `AWS Delegated FSx Administrators` has been measured to have insufficient permissions for the SVM
   join.

**Never reuse an SVM NetBIOS name after a failed join.** Active Directory keeps the orphaned computer
account and the next attempt fails on the conflict. Change `NamePrefix` or `DomainShortName`, or
delete the computer object from Active Directory first.

## The identity problem this example makes explicit

NFSv4.1 with `sec=sys` carries numeric UIDs. For ONTAP to evaluate *the same Active Directory user*
on the NFS side, it has to turn that number into a name and then into a Windows identity. Two paths
exist:

| Path | What it needs |
|---|---|
| An ONTAP LDAP client reading POSIX attributes from Active Directory | The directory must publish them |
| Explicit local `unix-user` and `name-mapping` entries | Nothing beyond ONTAP |

`provision-multiprotocol.sh` creates the explicit entries for one user, because they work either way
and because one explicit mapping is easier to reason about when a result is surprising. It derives
the UID from what the Linux host resolves for the account, and **warns when ONTAP already holds a
different number** — a mismatch there makes the result about the mismatch.

If you configure the LDAP path instead, say so in the record. The two paths can produce different
UIDs for the same user, and a figure that does not name which was in use cannot be compared with
anything.

## A gap found on first use, and the wrong fix for it

On first use the Windows client could not read the directory's `Admin` credential: the template
granted Secrets Manager access to the Linux role only. The first reading of that gap was that it
blocked **two** jobs — creating the test AD user, and authenticating to the SMB share as an account
that can change ACLs. Checking the documentation before changing the template removed the second
one entirely, and narrowed what the first one needs.

### Setting the ACEs was never a Windows problem

**Part 1 of the record is produced by the ONTAP REST API, not by an SMB client.** ONTAP 9.9.1 and
later expose `POST /protocols/file-security/permissions/{svm.uuid}/{path}`, which NetApp describes as
managing NTFS file security *without requiring a client*, as the equivalent of the `cacls` family:
[Manage file security permissions and audit policies](https://docs.netapp.com/us-en/ontap-restapi-991/manage_file_security_permissions_and_audit_policies.html).
The [REST-to-CLI mapping](https://docs.netapp.com/us-en/ontap-automation/workflows/wf_nas_fs_prepare.html)
shows that one call stands in for six `vserver security file-directory` commands, and the
[AWS Storage Blog](https://aws.amazon.com/blogs/storage/manage-ntfs-permissions-at-scale-on-amazon-fsx-for-netapp-ontap/)
covers the same API on FSx for ONTAP specifically: it operates at the storage layer, bypasses SMB,
and carries the `OI`/`CI` inheritance flags the inherited-ACE case needs.

That is what `set-test-acls.sh` does, from the Linux client, which already holds the `fsxadmin`
credential. `set-test-acls.ps1` is retained as an **optional** second path, useful only for comparing
an SMB-side result against the storage-side one. It is not on the critical path for the measurement.

One caveat this API brings with it: ONTAP adds four groups to a newly created security descriptor
(`BUILTIN\Administrators`, `BUILTIN\Users`, `CREATOR OWNER`, `NT AUTHORITY\SYSTEM`). They are
reported rather than removed — AWS documents `SYSTEM` full control as required — but a
denied-access result that is actually granted through one of them is a false positive, so the record
lists them.

### What the Windows client is still for

Creating the test AD user, because AWS Directory Service exposes no API for it. The documented
procedure is the Active Directory Users and Computers snap-in (`dsa.msc`) on an instance with the
administration tools installed:
[Creating an AWS Managed Microsoft AD user](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_manage_users_groups_create_user.html).

**The IAM permissions for that were already correct.**
[Installing Active Directory Administration Tools](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_install_ad_tools.html)
names `AmazonSSMManagedInstanceCore` and `AmazonSSMDirectoryServiceAccess` as the policies an
instance needs "to create users and groups", and the template attached both from the start. The same
page says only that "you will need the credentials for your Active Directory domain Administrator" —
it does not say where they live. In this stack they live in Secrets Manager, so **the gap was never
about the Active Directory operation; it was about credential retrieval.**

The applied fix grants `secretsmanager:GetSecretValue` on the AD admin secret alone. The `fsxadmin`
secret is deliberately still out of reach from this host.

Install the tools over Session Manager rather than opening RDP ingress — feature list and
port-forwarding approach in
[Manage AWS Managed Microsoft AD resources with Session Manager port forwarding](https://aws.amazon.com/blogs/mt/manage-aws-managed-microsoft-ad-resources-with-session-manager-port-forwarding/).

### Applying the fix taught two things about `update-stack`

Both measured on 2026-09-11 in `ap-northeast-1` while adding the policy above.

**A change set is worth creating even for a one-line IAM edit.** The same commit also touched the
Windows client's `UserData`, and the change set reported `WindowsClient` as
`Replacement: Conditional` — a replacement of a domain-joined instance, which `update-stack` would
have started without showing it first.

**`UPDATE_COMPLETE` does not mean `UserData` ran.** The update finished in about one minute and the
instance ID did not change, so CloudFormation updated the property in place and did not replace the
host. `UserData` executes at launch, so **the new script never ran** and the running instance kept
the feature set it booted with. The template and the host had diverged while every status said
success. Verify on the host, not in the stack event:

```powershell
Get-WindowsFeature RSAT-AD-Tools,RSAT-AD-PowerShell,RSAT-ADDS-Tools | Format-Table Name,InstallState
Test-Path "$env:SystemRoot\system32\dsa.msc"
```

Doing that turned an assumption into a measurement, and the assumption was wrong in the safe
direction: `Install-WindowsFeature RSAT-AD-PowerShell,RSAT-AD-Tools` reported `RSAT-ADDS-Tools` and
`RSAT-AD-AdminCenter` as `Installed` and `dsa.msc` as present — `RSAT-AD-Tools` pulls both in. The
longer feature list AWS publishes for a general-purpose AD management host was therefore not needed,
and one of its entries (`RSAT-DNS-Server`) is not a sub-feature and stayed `Available`. The template
keeps the two-feature line and records the measurement rather than the guess.

### Reading the secret on the Windows host: two traps

**The AWS CLI is not on the Windows Server AMI this template resolves.** `aws secretsmanager
get-secret-value` fails with `CommandNotFoundException`. Use the AWS Tools for PowerShell cmdlet,
which is present:

```powershell
$o = (Get-SECSecretValue -SecretId mpad-ad-admin -Region ap-northeast-1).SecretString | ConvertFrom-Json
```

That mattered more than it looks. A first attempt wrapped the CLI call in `if ($LASTEXITCODE -ne 0)`
and printed `fsxadmin correctly DENIED` — **a false pass produced by the command not existing at
all**, not by the deny working. Any check of the form "it failed, so the control held" has to
distinguish the failure it is testing for from every other failure.

Verified properly, both directions hold: the AD secret returns a 24-character password, and the
`fsxadmin` secret returns `is not authorized to perform: secretsmanager:GetSecretValue ... because no
identity-based policy allows` — the deny is real, not incidental.

**The first AWS Tools for PowerShell cmdlet in a session takes minutes.** The SSM invocation above
sat in `InProgress` for over four minutes on a `t3.large` before returning `Success`. Budget for it
and do not read a slow first call as a hung command.

### What the first end-to-end run actually cost

Everything below was measured on 2026-09-12 in `ap-northeast-1`, ONTAP 9.18.1P6, running this
example from a standing start. Each one presented as a different problem than it was — that pattern
is the reason this section exists.

| Symptom | Where it pointed | What it was |
|---|---|---|
| Domain join failed on **both** clients | The directory, or the join document | No route to the Directory Service API. `ds` has no VPC endpoint and the subnet's default route is an IGW with no public IPs, while SSM, Secrets Manager and `dnf` all kept working through their own endpoints. Now created by `CreateClientVpcEndpoints` |
| Linux join still failed: `***Failed: Cannot find parent directory Id` | A shared or cross-account directory | The Linux path needs a service account plus a secret named exactly `aws/directory-services/<id>/seamless-domain-join`. Absent, the agent falls back to a shared-directory lookup and reports **that** failure. Source: the agent's own script, in an open issue — [aws/amazon-ssm-agent#461](https://github.com/aws/amazon-ssm-agent/issues/461). Windows needs none of it, which is why only one host stayed broken |
| `mount ...:/ntfsvol` → `access denied by server` | That volume's export policy | The **SVM root volume** was NTFS style. `root` has no `unix_win` mapping, so ONTAP cannot evaluate it and denies the LOOKUP traversal needs. Diagnostic: mounting `/` succeeds and then `ls /` returns EACCES. Root is now UNIX |
| `mkdir` on the mount → `Permission denied`, for root *and* for the AD user | The NTFS ACL | A name-mapping replacement of `DOMAIN\user`. **ONTAP treats `\` as an escape**, so it became `DOMAINuser`; the mapping reported success at position 1 and the *lookup* of that name failed. `secd.nfsAuth.noNameMap` in EMS names it exactly. The GET readback shows the single backslash that was stored, which looks correct. Fixed by doubling it |
| Descriptor POST → `HTTP 400, code 262196` | A malformed body | `security_style` is returned by GET on that endpoint but cannot be sent back. Same code as a rehost PATCH carrying `svm.name`: 262196 means "readable here, not writable here" |
| `rights=-` on every ACE in the readback | ONTAP granted nothing | The readback returns `advanced_rights`, never `rights`, even when the ACE was set with `rights: "modify"` |
| Effective permissions all `-` | ONTAP granted nothing | The fields are `file_permissions` and `share_permissions` — **plural, arrays**. The singular names read as null |
| `nfs4_getfacl`: `Operation to request attribute not supported` | The security style | NFSv4 ACLs are **disabled by default** on the SVM (`v40_features.acl_enabled` and `v41_features.acl_enabled` both false). Style-independent — the UNIX volume behaved the same. Enabling is not enough: an existing mount keeps the capability it negotiated, so remount |
| `nfs4_getfacl` reported status `ok` alongside that error | The check worked | It prints the error and **exits 0**. A real ACL always opens with `# file:`, so the output shape decides, not `$?` |
| A tree created on a "mounted" path, `ls` looking correct | Success | The mount had been **refused** and the directories were created on local disk. `mountpoint -q` before writing is now a hard precondition in the scripts |
| `owner` shown as `nobody` while ONTAP reports the AD user | Broken mapping | NFSv4 ID domain mismatch: `v4_id_domain` defaults to `<region>.compute.internal`, not the AD domain. Cosmetic for access, **not** cosmetic for reading mode bits — see the note below |
| `update-stack` rolled back: `SourceSvm ... is already the name of a storage virtual machine` | A naming collision to work around | **`RootVolumeSecurityStyle` requires replacing the SVM.** Editing it and updating tries to build a second SVM and delete the first, taking its volumes. The name collision is what stopped it, not a safeguard — a template that also changed `NamePrefix` would have proceeded. Change it through ONTAP on a running SVM, and run a change set before any update touching it |
| `provision-multiprotocol.sh` could not resolve the management address | The file system | No route to the Amazon FSx API, the same shape as the `ds` gap. The Linux role is granted `fsx:Describe*` regardless, so the permission existed and the path did not. Now covered by `CreateClientVpcEndpoints`; `--management-ip` remains the fallback, but then the rehost probe cannot time the AWS control plane |

Two of these deserve emphasis because they produce a *confident wrong answer* rather than an error:
the local-disk tree, and `nfs4_getfacl` exiting 0. Both make a check report success while measuring
nothing.

The finding the run was built to produce is in
[NFS 側から見える権限表現が実際の可否と一致しない](../../docs/ja/domains/multiprotocol-identity/notes/nfs-side-view-does-not-explain-ntfs-denials.md).

### What the rehost probe found on this stack

Ran with `--apply` on 2026-09-12, ONTAP 9.18.1P6, moving the NTFS-style `rehostvol` into an SVM whose
root is UNIX. Full record and the earlier run in
[`volume rehost` が変えるのは所有 SVM だけ](../../docs/ja/domains/block-storage/notes/volume-rehost-changes-ownership-not-contents.md).

| | Before | After | |
|---|---|---|---|
| Security style | `ntfs` | `ntfs` | **Preserved**, against a UNIX-root destination — so the style is the volume's own property |
| ONTAP owning SVM | source | destination | Immediate |
| AWS `SvmId` | source | destination | Followed, but see the timing below |
| Snapshot policy | `none` | `default` | Changed. It **gained** a default rather than losing one |
| Export policy | `mpad_clients` | `default` | **Lost.** First time this repository observed it, because the first run happened to start from `default` |
| AWS `JunctionPath` | `/rehostvol` | `null` | Out of the namespace |

**The AWS control plane took between 19m01s and 24m05s to notice** — against 13m42s on the earlier
run. The bounds are wide because the ONTAP job completion time was not recorded, only that ONTAP
already showed the destination by 01:40:47 and AWS flipped at 01:59:48. Treat 13m42s as one sample,
not a ceiling: **the same operation varied by more than 1.4x between two environments.** The probe
polls for 25 minutes for this reason.

### Security positions this example takes, and where they stop being appropriate

Stated rather than left implicit, because the template is the part people copy.

| Position here | Why it is acceptable here | What to change in a production copy |
|---|---|---|
| Egress is enumerated by port, but the destination CIDR on the rules leaving the VPC is `0.0.0.0/0` | A template cannot portably discover the VPC CIDR or the S3 gateway endpoint's prefix list, and the earlier version was `IpProtocol: -1` to anywhere, which is strictly worse | Replace with the VPC CIDR on the Active Directory rules and the S3 prefix list on 443. `preflight.sh` prints the subnet CIDR |
| **Neither secret is rotated** | The environment is meant to live hours, and rotating a credential that the SVM join also uses would need the join re-run | Enable rotation. AWS publishes an Active Directory rotation template for Secrets Manager |
| The Linux role can read **both** secrets, though it needs one at a time | Splitting them adds two policies and a parameter to a disposable stack | Split per host and per purpose. The Windows role here already reads only the AD secret, which is the pattern to follow |
| The clients have no inbound rules and are reached only through Session Manager | No RDP or SSH ingress is the right default regardless of environment | Nothing. Keep it |
| `fsxadmin` is used directly by the scripts | It is the only ONTAP credential the file system starts with | Create a role-scoped ONTAP account and use that. `fsxadmin` is a break-glass credential |

### What the measurement implies for a permission-change control

This is a consequence rather than a measurement, and it follows directly from the result: **an
approver who can only see the NFS side cannot approve a permission change on an NTFS-style volume.**
The view available to them contains no Deny entry and no principal name, and it was observed to be
identical between a directory that refused a write and one that allowed it.

So if a review step exists in the form "a Linux administrator confirms the permissions look right",
that step needs to move to the storage-side API or to the Windows side. Note what this requires: the
storage-side check needs an ONTAP credential, which most platform engineers do not hold. **That is
the practical blocker** — the check exists, but the person currently doing the verification may not
be able to run it. Decide who holds it before the migration, not after.

### ONTAP error codes seen here, and what they actually mean

Collected in one place because a reader who hits one of these searches for the number, and each was
observed to mean something narrower than its message suggests.

| Code | Message shape | What it means here |
|---|---|---|
| `262196` | `Field "X" cannot be set in this operation` | X is **readable but not writable on this endpoint**. Seen for `security_style` on a file-security POST and for `svm.name` on a volume PATCH. It does not mean the field name is wrong |
| `262197` | `The value "X" is invalid for field "fields"` | One name in the `fields=` query is not valid for that endpoint. **The whole request becomes a 400**, so a projection like `jq '.records'` prints `null` and reads as an empty result |
| `655551` | `The specified path "..." does not exist in the namespace belonging to SVM "..."` | The path is wrong, commonly because it was built as `/<volume-name>` when the junction path is something else. It does not mean the volume is missing |
| `secd.nfsAuth.noNameMap` (event, not a code) | `Cannot map UNIX name to CIFS name` | Read the event body: it prints the name it tried. A doubled-up name such as `DOMAINuser` means the backslash in the mapping replacement was consumed as an escape |

Read these from the API rather than the client. The client-side symptom for all four is `EACCES` or a
generic failure, which is why the ONTAP event log is the first place to look and not the last.

### Two things to keep not doing

| Rejected | Why |
|---|---|
| Passing the password in SSM command parameters | Command parameters are retained in the command history and readable by anyone with `ssm:GetCommandInvocation` |
| Passing it as a command-line argument on the host | Arguments are visible to every user on the instance through `ps` |

---

## Teardown

```bash
# 1. Unmount on the Linux client, if a mount was left in place.
sudo umount /mnt/ntfsvol /mnt/unixvol 2>/dev/null || true

# 2. Report what would be deleted and what would block it. Changes nothing.
./teardown.sh --stack-name fsxn-mp-ad \
  --secret-ids mpad-ad-admin,mpad-fsxadmin \
  --purge-recovery-queue --management-ip <mgmt-ip> --secret-id mpad-fsxadmin

# 3. Do it. Two flags, because one is easy to leave in a shell history.
./teardown.sh --stack-name fsxn-mp-ad \
  --secret-ids mpad-ad-admin,mpad-fsxadmin \
  --purge-recovery-queue --management-ip <mgmt-ip> --secret-id mpad-fsxadmin \
  --apply --i-understand-this-deletes-data
```

The ONTAP objects the scripts created — the share, the export policy, the name mappings, the UNIX
identity — do not block anything. Removing them is tidiness, not a prerequisite; deleting the file
system takes them with it.

### The first teardown failed, and the message pointed at the wrong resource

Measured on 2026-09-12, tearing this stack down by hand:

| Step | Result |
|---|---|
| `delete-volume` on the rehosted volume, by id | 247 s, clean |
| Recovery queue purge | Queued volume found on the **destination** SVM, purged |
| `delete-stack`, first attempt | **`DELETE_FAILED` after 1,277 s** |
| `delete-stack`, retry once the real blocker was gone | 27 s |

The failure was `DsEndpointSecurityGroup: resource sg-... has a dependent object`. The dependent
object was an interface VPC endpoint created **outside** the stack that had been pointed at the
stack's own security group. **The error names the security group, never the thing holding it**, so it
sends you to the resource that is fine.

Two rules come out of that, and `teardown.sh` enforces the first before it deletes anything:

- **Anything created outside a stack must bring its own security group.** Borrowing the stack's is
  what makes the stack undeletable, and the diagnosis is not in the error message.
- **Tag out-of-band resources at creation**, because nothing else will list them for you:
  `--tag-specifications 'ResourceType=vpc-endpoint,Tags=[{Key=DeleteManually,Value=not-in-cloudformation}]'`

### An empty recovery queue and a failed query look identical

The queue must be empty before the file system can go, and it is easy to believe it already is:

```bash
# WRONG. One invalid field name makes this a 400, and jq prints null from the error object -
# indistinguishable from an empty queue.
curl ... '/api/private/cli/volume/recovery-queue?fields=vserver,volume,size' | jq '.records'
# null

# What that request actually returned:
#   HTTP 400  {"error":{"message":"The value \"size\" is invalid for field \"fields\"",
#              "code":"262197","target":"fields"}}
```

Judge on `num_records`, and only after checking the status. An empty queue is
`{"records": [], "num_records": 0}` with HTTP 200 — clearly different from an error once you stop
projecting. After a rehost the queued volume lands on the **destination** SVM, and its name gains a
dataset-id suffix that is **not a constant**: `_1200` on one run, `_1031` on another. Match on the
prefix.

### Verify by resource, not by stack status

`DELETE_COMPLETE` is a statement about the stack, not about what it billed for. `teardown.sh` ends by
naming each file system, directory, instance and security group and showing what the API says about
it now. The same sweep by hand:

```bash
aws fsx describe-file-systems --file-system-ids <fs-id>      # expect FileSystemNotFound
aws ds describe-directories --directory-ids <d-id>           # expect empty
aws ec2 describe-instances --instance-ids <i-...> --query 'Reservations[].Instances[].State.Name'
aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=<vpc-id> \
  --query 'VpcEndpoints[].[VpcEndpointId,ServiceName]' --output text
```

Two things bite here.

**A deleted ONTAP volume waits in the recovery queue for at least 12 hours** under a changed name,
and a FlexClone relationship surviving there blocks the parent volume, its SVM and the whole file
system from being deleted. If you made any clone, purge the queue rather than waiting:
`volume recovery-queue purge -vserver <svm> -volume <name>_<dataset id>`.

**The directory outlives the stack if the stack fails to delete.** It is the second-largest line in
the cost table and it cannot be stopped, only deleted. Check it explicitly:
`aws ds describe-directories --query 'DirectoryDescriptions[].[DirectoryId,Name,Stage]' --output table`.

## Deliberately out of scope

Throughput measurement of any kind — the client instance types cannot sustain the provisioned rate,
so a number measured here would describe their network interfaces. Also out of scope: Multi-AZ, the
second generation, `mixed` security style (AWS documents it as not required for multiprotocol access
and recommended only for advanced users), Kerberos NFS, S3 access points, NFSv3, case sensitivity,
and anything involving SnapLock or snapshot locking.

`mixed` and NFSv3 are both worth measuring later and are both a second run, not an extra flag on
this one: each changes what the result is about.
