# Reaching FSx for ONTAP from a physical endpoint — smallest runnable example

Reference for the files in this directory. This environment exists to answer one question:

> What can a Windows machine, the Linux inside WSL2, and a Mac each actually reach on an Amazon FSx
> for NetApp ONTAP file system — as file storage, as block storage, and as object storage — and where
> does each of them stop?

**The endpoint is your own machine, not an EC2 instance.** That is the whole point, and it is why this
directory has a second template for the network route: FSx for ONTAP does not support access from the
public internet, and Amazon FSx detaches any Elastic IP attached to a file system's network interface.
There is no configuration that makes a laptop reach it directly.

The design notes this environment reproduces live in
[Domain — クライアントアクセス](../../docs/ja/domains/client-access/README.md), with the ordering in
[端末からデータに届く経路の決定木](../../docs/ja/reference/decision-trees/client-access-route.md).

## If this is your first time here, read in this order

This file is a reference, not a tutorial, so it is not ordered for a first read. This is:

1. **[Cost](#cost)** and **[The two things that keep billing](#the-two-things-that-keep-billing)** —
   the file system cannot be stopped, and the Client VPN charge is keyed on something other than what
   you would guess. Decide the teardown date first.
2. **[What this deliberately does not do](#what-this-deliberately-does-not-do)** — Active Directory in
   particular. If you need it, a different example already has it.
3. **[Files](#files)** and **[Order](#order)** — the runbook.
4. **[The six failures worth knowing before you hit them](#the-six-failures-worth-knowing-before-you-hit-them)**
5. **[Teardown](#teardown)** — read it before you deploy, not after.

**If you only want the findings and not the environment**, read the module hub linked above and stop
there. Nothing here needs to run for those to be usable.

## Provenance

Nothing here was written from a blank file.

| Borrowed | From |
|---|---|
| Secret handling, ingress rules as separate resources outside the group, ONTAP name derivation, the `ontap()` / `ontap_ok()` helpers, idempotence by reading state first, the teardown-first ordering | [`examples/block-storage/`](../block-storage/) and [`examples/multiprotocol-ad/`](../multiprotocol-ad/) in this repository |
| The shape of a Client VPN endpoint used to mount a file share on a client device | [aws-samples/access-amazon-fsx-through-clientvpn](https://github.com/aws-samples/access-amazon-fsx-through-clientvpn) (AWS-published; its target is FSx for Windows File Server) |
| An SMB server in a workgroup being a documented option for FSx for ONTAP, and `vserver cifs create -workgroup` being the command | [AWS: Creating an SMB server in a workgroup](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-smb-server-workgroup.html) |
| What workgroup mode gives up, and that local users must be created afterwards | [NetApp: Create SMB servers on the ONTAP SVM with specified workgroups](https://docs.netapp.com/us-en/ontap/smb-config/create-server-workgroup-task.html) |
| The REST form of a workgroup CIFS server: `svm`, `name` (15 characters), `workgroup` | [NetApp: Create a CIFS server](https://docs.netapp.com/us-en/ontap-restapi/ontap/post-protocols-cifs-services.html) |
| Windows iSCSI: `Start-Service MSiSCSI`, `(Get-InitiatorPort).NodeAddress`, MPIO, 8 sessions per portal at 625 MBps each, `InitiatorPortalAddress` taking the host's own address | [AWS: Provisioning iSCSI for Windows](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-windows.html) |
| macOS mounting with `mount -t smbfs`, `C$` as the default share, SMB being the recommended protocol for a Mac | [AWS: Mounting volumes on macOS clients](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-mac-client.html) |
| SMB on Windows needing Active Directory **or a workgroup** | [AWS: Mounting volumes on Microsoft Windows clients](https://docs.aws.amazon.com/us_en/fsx/latest/ONTAPGuide/attach-windows-client.html) |
| A Client VPN endpoint with no DNS server falling back to the client's own resolver | [AWS: How DNS works with an AWS Client VPN endpoint](https://aws.amazon.com/premiumsupport/knowledge-center/client-vpn-how-dns-works-with-endpoint/) |
| WSL2 having a virtualized network interface, and mirrored mode being opt-in | [Microsoft: Accessing network applications with WSL](https://learn.microsoft.com/en-us/windows/wsl/networking) |
| A gateway VPC endpoint not routing traffic that enters the VPC over VPN, Direct Connect, Transit Gateway or peering | [S3 Access Point の権限設計](../../docs/ja/domains/security-governance/notes/access-point-authorization-layers.md) in this repository (`verified`) |

## What this deliberately does not do

| Not here | Why, and where it is |
|---|---|
| **Active Directory** | The SMB server is created in a workgroup. Joining a domain adds about 40 minutes and $106.58 a month for two domain controllers, and none of the endpoint-side failures this example is for depend on it. Domain membership, identity mapping and NTFS permission evaluation are measured in [`examples/multiprotocol-ad/`](../multiprotocol-ad/) |
| **NVMe/TCP** | ONTAP does not support it with Windows Server, and macOS has no initiator of any kind, so there is no endpoint in scope that could use it |
| **Throughput measurement** | Over a VPN the number describes the tunnel, the endpoint's own network and the distance to the Region. The reasoning is in [この決定木で帯域を測らない理由](../../docs/ja/reference/decision-trees/client-access-route.md#この決定木で帯域を測らない理由) |
| **Multi-AZ** | Single-AZ keeps the endpoints inside one subnet, which removes a routing question that has nothing to do with the endpoint. Multi-AZ from outside the VPC is covered in [Multi-AZ が動かすのはアドレスではなくルート](../../docs/ja/domains/block-storage/notes/multi-az-moves-a-route-not-an-address.md) |
| **An EC2 client** | There is none. The client is your endpoint. An EC2 instance would answer a question other modules already answer |
| **A revocation list for the client certificates** | Mutual certificate authentication with no revocation list means possession of the client key is the authorization. Acceptable for a disposable verification, and stated rather than hidden |

**What workgroup mode gives up, from the NetApp documentation**: SMB3 Witness protocol, SMB3
continuously-available shares, SQL over SMB, folder redirection, roaming profiles, Group Policy
Objects, and Volume Shadow Copy Service. That is a real list. If any of it matters, this example is
the wrong shape and the Active Directory one is the right one.

## Files

| File | What it does | Reaches |
|---|---|---|
| `fsxontap-client-access.yaml` | First-generation Single-AZ file system, one SVM with no Active Directory, three volumes (NTFS for SMB, UNIX for NFS, one to hold a LUN), per-protocol ingress rules keyed on a client CIDR, and an optional Amazon S3 interface endpoint | AWS API |
| `make-client-vpn-certs.sh` | Generates a CA, a server certificate and a client certificate with openssl, and imports the server certificate into ACM | Local disk, ACM |
| `fsxontap-client-vpn.yaml` | Client VPN endpoint, mutual certificate authentication, split tunnel, the VPC resolver as DNS server, and a subnet association that can be turned off without deleting anything | AWS API |
| `provision-client-access.sh` | SMB server in a workgroup, local SMB user, SMB share, NFS service and export policy, LUN, igroup, LUN map. Idempotent. **Run it from the endpoint** | ONTAP REST API |
| `probe-endpoint.sh` | Records what one endpoint can reach, as masked JSON. macOS, WSL2, native Linux | Endpoint, DNS, TCP, optional mounts |
| `probe-endpoint.ps1` | The same record from Windows, same JSON shape | Endpoint, DNS, TCP, optional mount |
| `teardown.sh` | Ordered removal, billing first. Reports only unless `--apply` | AWS API, ONTAP REST API |

The file-system resource intentionally omits `KmsKeyId`. At-rest encryption remains automatic, and
CloudFormation then uses the Amazon FSx-managed KMS key for the account. A KMS key that you manage can
be selected by adding `KmsKeyId` before creation; changing it replaces the file system.

## Cost

At the defaults: 1,024 GiB SSD and 128 MBps of throughput capacity on a first-generation Single-AZ
file system, plus a Client VPN endpoint with one subnet association and one connected client.

| Line | Rate | Monthly (730 h) | Hourly |
|---|---|---|---|
| FSx for ONTAP SSD, 1,024 GiB | $0.150 / GB-month | $153.60 | $0.2104 |
| FSx for ONTAP throughput, 128 MBps | $0.906 / MBps-month | $115.97 | $0.1588 |
| Client VPN subnet association | $0.15 / hour | $109.50 | $0.1500 |
| Client VPN connection, one client | $0.05 / hour | $36.50 | $0.0500 |
| Amazon S3 interface endpoint, 1 AZ (optional) | $0.014 / AZ-hour | $10.22 | $0.0140 |
| **Total** | | **$425.79** | **$0.5832** |

Rates from the AWS Price List API, On-Demand, `ap-northeast-1`, retrieved 2026-09-13
(`APN1-Storage.SAZ_2N:SSD`, `APN1-ThroughputCapacity.SAZ_2N`, `APN1-ClientVPN-EndpointHours`,
`APN1-ClientVPN-ConnectionHours`, `APN1-VpcEndpoint-Hours`). The monthly figures are arithmetic on
the defaults, not amounts read off a bill.

**Built and torn down in one afternoon this is about $2.** A four-hour window with the VPN associated
for three of them and the S3 endpoint on comes to roughly $2.14. The reason to write the monthly
column anyway is the failure mode: forgetting.

### The two things that keep billing

| What | How it stops |
|---|---|
| **The file system** | Only deletion. It cannot be stopped, and $0.3693 per hour continues whether anything is mounted or not — about $8.86 a day |
| **The Client VPN subnet association** | Deleting the association, which is **not** the same as deleting the endpoint. The charge is per association hour, so an endpoint with zero associations costs nothing per hour while keeping its certificates and its client profile |

Update the VPN stack with `AssociateSubnet=false` to pause overnight. The correct check for "stopped"
is a count of zero from `aws ec2 describe-client-vpn-target-networks`, not the absence of the
endpoint.

**Fix a teardown date before you start. Read [Teardown](#teardown) first.**

## Order

```bash
# 0. Two secrets. One administers the file system, one is handed to whoever mounts the share.
#    They must be different: the fsxadmin password is cluster-wide.
aws secretsmanager create-secret --name fsxn-ca-fsxadmin \
  --secret-string '{"password":"<8-50 chars>"}'
aws secretsmanager create-secret --name fsxn-ca-smbuser \
  --secret-string '{"password":"<a different one>"}'

# 1. The file system side. Measured 18 minutes 32 seconds in ap-northeast-1 on 2026-09-13, almost
#    all of it the file system. The meter starts when the file system appears, not when the stack
#    completes.
#    ClientCidr must match ClientCidrBlock in step 3 -- it is what the security group admits, and a
#    mismatch produces a mount that hangs rather than an error that names the cause.
aws cloudformation create-stack --stack-name fsxn-client-access \
  --template-body file://fsxontap-client-access.yaml \
  --parameters ParameterKey=VpcId,ParameterValue=vpc-... \
               ParameterKey=FileSystemSubnetId,ParameterValue=subnet-... \
               ParameterKey=ClientCidr,ParameterValue=<client-cidr> \
               ParameterKey=FsxAdminSecretName,ParameterValue=fsxn-ca-fsxadmin

# 2. Certificates. Prints the one ACM ARN that goes into both parameters of step 3.
#    They land in $HOME/.fsxn-client-access/pki, OUTSIDE this repository: a gitignored private key is
#    still a private key in the worktree, and the secret scan reads the worktree rather than the
#    index. Do not point --out-dir back inside the tree.
./make-client-vpn-certs.sh --region ap-northeast-1

# 3. The route. Measured 7 minutes 39 seconds on 2026-09-13; the subnet association is most of it.
#    DnsServerIp is the VPC CIDR base address plus two: for a /16 whose base is a.b.0.0, that is
#    a.b.0.2. Neither CIDR has a default, because the two below have to agree.
#    LEAVING IT WRONG IS THE MOST COMMON FAILURE HERE: the tunnel comes up, and the SVM DNS name
#    does not resolve because the client is still using its own resolver.
aws cloudformation create-stack --stack-name fsxn-client-access-vpn \
  --template-body file://fsxontap-client-vpn.yaml \
  --parameters ParameterKey=VpcId,ParameterValue=vpc-... \
               ParameterKey=TargetSubnetId,ParameterValue=subnet-... \
               ParameterKey=TargetNetworkCidr,ParameterValue=<vpc-cidr> \
               ParameterKey=DnsServerIp,ParameterValue=<vpc-resolver-ip> \
               ParameterKey=ClientCidrBlock,ParameterValue=<client-cidr> \
               ParameterKey=ServerCertificateArn,ParameterValue=arn:aws:acm:... \
               ParameterKey=ClientRootCertificateChainArn,ParameterValue=arn:aws:acm:...

# 4. Build the profile and connect. The exported configuration carries NO client certificate; the
#    two appended blocks are what make the handshake succeed.
#
#    CONNECTING NEEDS ROOT on the endpoint, whichever client you use: bringing up the tunnel creates
#    a utun interface. Neither openvpn nor the AWS VPN Client is present on a stock macOS install,
#    so this step is the one that cannot be automated from a shell without an interactive password.
PKI="$HOME/.fsxn-client-access/pki"
PROFILE="$HOME/.fsxn-client-access/client-config.ovpn"
aws ec2 export-client-vpn-client-configuration \
  --client-vpn-endpoint-id cvpn-endpoint-... --output text > "$PROFILE"
{ printf '\n<cert>\n'; cat "$PKI/client.crt"; printf '</cert>\n<key>\n'; cat "$PKI/client.key"
  printf '</key>\n'; } >> "$PROFILE"
chmod 600 "$PROFILE"
#    Then open it in the AWS VPN Client, or: sudo openvpn --config "$PROFILE"
#    Neither is present on a stock macOS install: brew install openvpn, or install the AWS VPN Client.

# 5. CONFIRM NAME RESOLUTION BEFORE ANYTHING ELSE. Get the SVM DNS name and addresses from the AWS
#    CLI, then resolve the name from the endpoint.
aws fsx describe-storage-virtual-machines \
  --query 'StorageVirtualMachines[0].Endpoints' --output json
nslookup <svm-dns-name>
#    Failing here with the tunnel up means DnsServerIp is wrong or unset. Mounting by IP still works
#    in that state, which is what makes it easy to record as a routing problem.

# 6. Record the starting state of the endpoint, before provisioning. This is the baseline.
./probe-endpoint.sh --svm-dns <svm-dns-name> --smb-ip <smb-ip> --nfs-ip <nfs-ip> \
  --iscsi-ip <iscsi-ip> --out before-provision.json

# 7. Provision the ONTAP side FROM THE ENDPOINT, over the route the data will use. Reaching the REST
#    API on 443 proves the route before any mount is attempted.
#    On a Mac add --skip-block: there is no iSCSI initiator to map a LUN to.
./provision-client-access.sh --file-system-id fs-... --svm <SvmName> \
  --smb-volume <SmbVolumeName> --nfs-volume <NfsVolumeName> --lun-volume <LunVolumeName> \
  --client-cidr <client-cidr> \
  --secret-id fsxn-ca-fsxadmin --smb-secret-id fsxn-ca-smbuser

# 8. Record again, with the mounts this time.
./probe-endpoint.sh --svm-dns <svm-dns-name> --smb-ip <smb-ip> --nfs-ip <nfs-ip> \
  --iscsi-ip <iscsi-ip> --share clientshare --nfs-junction /nfsvol \
  --smb-user '<SMB_SERVER>\clientuser' --try-mount --out after-provision.json

# 9. On Windows, from an elevated PowerShell:
#      .\probe-endpoint.ps1 -SvmDnsName <svm-dns-name> -SmbIpAddress <smb-ip> `
#        -NfsIpAddress <nfs-ip> -IscsiIpAddress <iscsi-ip> -OutFile windows-probe.json
#    In WSL2 on the same machine, probe-endpoint.sh. Run BOTH: whether they agree is the finding.
```

## What a finished run looks like

Check against this rather than against "the scripts exited 0". Each row is a value you should be able
to point at.

| # | Done when | Where it is |
|---|---|---|
| 1 | The SVM DNS name resolves **from the endpoint** with the tunnel up | `name_resolution.result` begins `resolved:` |
| 2 | TCP 445, 2049, 111, 635 report `open` from every endpoint you tested | `reachability.*` |
| 3 | TCP 3260 reports `open` from Windows and from WSL2 | `reachability.iscsi_3260` |
| 4 | The Mac record shows **no initiator at all** | `block.initiator_tool` is `absent` and `initiator_name` is `none` |
| 5 | The Windows record says whether `Install-WindowsFeature` exists on that machine | `windows_specific.install_windowsfeature_available` |
| 6 | The WSL2 record carries a networking mode and an `iscsi_tcp` verdict | `environment.wsl_networking_mode`, `block.iscsi_tcp_module` |
| 7 | An SMB mount either succeeded or failed **with its error text kept** | `mounts.smb` |
| 8 | Every record is masked: no host name, no full address, no account number | grep the files for your own host name |
| 9 | `teardown.sh` reports zero Client VPN associations and no stacks | its step 1 and step 5 |

**Row 7 is the one that decides whether you measured anything.** A record whose mounts are all
`not_tested` describes reachability only, which is a narrower finding than it looks like.

## The six failures worth knowing before you hit them

The first two were hit while building this example on 2026-09-13, **after cfn-lint reported the
templates clean**. Both roll the stack back, and the first one does so while the file system it
depends on is already creating and already billing.

| Failure | What it looks like | What it is |
|---|---|---|
| **An apostrophe in a security group RULE description** | `Invalid rule description. Valid descriptions are strings less than 256 characters from the following set: a-zA-Z0-9. _-:/()#,@[]+=&;{}!$*` and a rollback | EC2 restricts the character set on a rule description. **cfn-lint checks `GroupDescription` (E3031) and does not check the per-rule `Description`**, so the template lints clean and fails at CreateStack. The word that did it here was `system's` |
| **A server certificate with a bare common name** | `Certificate <arn> does not have a domain` on the `AWS::EC2::ClientVpnEndpoint`, after ACM accepted the import without complaint | The Client VPN endpoint wants a domain-shaped name and a `subjectAltName`. **The AWS procedure uses easy-rsa, which adds the SAN by itself, so the requirement never appears in the instructions.** `make-client-vpn-certs.sh` now issues `server.fsxn-client-access.internal` with a matching `DNS:` SAN |
| **DNS server not set on the Client VPN endpoint** | The tunnel is up, `ping` to the SVM address works, `nslookup <svm-dns-name>` fails, and mounting by IP succeeds | With no DNS server configured the client keeps using its own resolver. Split tunnel means nothing else redirects it. Set `DnsServerIp` to the VPC CIDR base plus two |
| **Client CIDR mismatch between the two stacks** | The mount hangs and eventually times out. Nothing logs a denial | The security group admits `ClientCidr`; the client's address comes from `ClientCidrBlock`. Different values means the packets arrive and are dropped |
| **`Install-WindowsFeature` on a Windows client SKU** | `The term 'Install-WindowsFeature' is not recognized` | It belongs to the `ServerManager` module, which ships on Windows Server. The AWS iSCSI procedure assumes an EC2 Windows Server 2019 instance. Use `Enable-WindowsOptionalFeature -Online -FeatureName MultiPathIO` instead, and confirm with `probe-endpoint.ps1` first |
| **A hard-coded `InitiatorPortalAddress`** | The AWS iSCSI script works once and fails on the next connection | It takes the host's own address, which over a VPN is assigned when the tunnel comes up. Read it at run time; `probe-endpoint.ps1` records every local IPv4 address with its interface so you can see which one moved |

## Teardown

The order matters, and the first step is the only one that stops money quickly.

```bash
# Report first. This answers "is anything still costing money", which is not the same question as
# "did I delete the stack".
./teardown.sh --region ap-northeast-1

# Then act. Step 1 removes the Client VPN association -- the $0.15/hour line -- before anything else.
./teardown.sh --region ap-northeast-1 --apply \
  --svm <SvmName> --file-system-id fs-... --secret-id fsxn-ca-fsxadmin

# The profile installed INSIDE the VPN application is not covered by any of the above. Remove it
# there as well: teardown.sh deletes the .ovpn file, not the copy the application imported.
#   AWS VPN Client: delete the profile in the application
#   openvpn: nothing further, the file was the profile
```

**Read step 2 and step 5 carefully rather than skimming them.** Both were changed after the first real
teardown run showed they could mislead:

- Step 2 prints `UNREACHABLE (not asked -- this is not the same as none)` when it cannot reach ONTAP.
  It used to print a blank, which reads as zero — so a teardown run with the tunnel already down
  looked like an SVM with nothing on it. A teardown is exactly when the route is most likely gone,
  including because step 1 of this same script just removed the association.
- Step 5 lists **every** file system in the region and marks which one this example created. Pass
  `--file-system-id` to get the marker. Without it, an operator who has just watched the stack delete
  sees another `AVAILABLE` file system on the next line and reads the teardown as having failed.

`teardown.sh` reports the ONTAP objects rather than sweeping them. That is deliberate: the same script
pointed at a shared SVM would delete someone else's share, and deleting the volumes with the stack
removes the LUN and the share along with them anyway. The script prints the DELETE calls for the cases
where the volumes are staying.

A deleted ONTAP volume waits in the recovery queue for at least 12 hours under a changed name. If a
FlexClone relationship survives there it blocks the parent volume, its SVM and the whole file system
from being deleted.

## Deliberately out of scope

Active Directory, NVMe/TCP, Multi-AZ, more than one HA pair, any throughput measurement, EC2 Mac
instances, and a certificate revocation list. The first four have their own homes listed above. EC2 Mac
is excluded on cost: AWS's own macOS procedure is written around one, which is worth knowing and is
recorded in the comparison matrix, but a Dedicated Host does not pay for itself against a Mac that is
already on the desk.
