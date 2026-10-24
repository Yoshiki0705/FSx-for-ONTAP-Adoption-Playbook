---
title: Safely check GCP reachability and sample data on Amazon FSx for NetApp ONTAP
lifecycle: [assess, build, operate]
domains: [data-protection, client-access, security-governance]
evidence: documented
source: https://cloud.google.com/netapp/volumes/docs/migrate/ontap/prerequisites-ontap-netapp-volumes
lang: en
---

# Safely checking GCP reachability and sample data on Amazon FSx for NetApp ONTAP

[🏠 Repository home](../../en/README.md) | [Reference](../../ja/reference/README.md)

## Conclusion

This procedure checks existing network paths and a dedicated verification volume before using NFS from a Linux client in GCP. It covers network preflight, safe mounting, a deterministic 48-file fixture, SHA-256 comparison, and DP read-only validation. Cluster peering, SVM peering, SnapMirror creation, break, and Reverse Resync are not executable steps in this document. They are covered as open items in [the separate reference](gcp-to-fsx-ontap-peering-and-replication-open-items.md).

| Status | Meaning |
|---|---|
| `documented` | Procedure or prerequisite based on a public source |
| `verified` | An observation with environment, date, and run ID recorded |
| `field-observation` | Observed once and not reproduced by this document |
| `open` | Evidence or an execution interface is missing; not a confirmed public procedure |

> **Evidence: documented**
>
> Communication between GCP and an external ONTAP system requires the GCP route, AWS return route, firewalls, and NFS export policy to align. See [Google Cloud: prerequisites for ONTAP to Google Cloud NetApp Volumes communication](https://cloud.google.com/netapp/volumes/docs/migrate/ontap/prerequisites-ontap-netapp-volumes).

## Get started

| Phase | Purpose | Primary actor | Required access | Output and stop condition |
|---|---|---|---|---|
| 1 | Confirm targets and ownership | AWS / GCP operators | AWS/GCP read access | Stop on any target mismatch |
| 2 | Check routes and NFS reachability | Network operator | Read access to VPC, VPN, and Cloud Router | Stop on missing return route or blocked TCP 2049 |
| 3 | Validate the NFS mount safely | GCP Linux operator | GCP Compute Engine access | Stop on a local filesystem or wrong export |
| 4 | Verify the sample data | GCP Linux operator | Write access to a dedicated fixture directory | Stop on count or manifest mismatch |
| 5 | Validate the DP volume is read-only | AWS / GCP operators | AWS/GCP read access | Stop if a write succeeds |
| 6 | Clean up | Run owner | Ownership of run-created resources | Leave shared resources and request review |

Durations are planning guidance. They are not measured service timings, production forecasts, or service limits.

## Prerequisites and actors

### Run ledger

Record these values in a private run ledger before execution. Do not publish real values.

| Item | Value format | Owner |
|---|---|---|
| GCP project / region | `<gcp-project-id>` / `<gcp-region>` | GCP operator |
| GCP VPC / Cloud VPN / Cloud Router | `<gcp-vpc>` / `<vpn-name>` / `<router-name>` | GCP network operator |
| AWS account / region / VPC | `<aws-account>` / `<aws-region>` / `<aws-vpc-id>` | AWS operator |
| AWS VGW / VPN | `<vgw-id>` / `<vpn-id>` | AWS network operator |
| FSx for ONTAP file system / SVM | `<file-system-id>` / `<fsx-svm-name>` | AWS storage operator |
| NFS endpoint / export | `<nfs-endpoint>` / `<export-path>` | AWS storage operator |
| GCP Linux client | `<gce-instance>` | GCP operator |

### Stop conditions

Stop when the owner, region, SVM, volume, endpoint, or run ID does not match the ledger. Do not delete or change a shared VPN, Cloud Router, VGW, route table, or security rule unless the ledger proves that this run created it and the owner approves the change.

> **Evidence: documented**
>
> The procedure reads target state before changes and does not infer ownership from names. A successful mutation response does not prove the resulting state.

## Network reachability and return routes

### GCP checks

The GCP operator checks Cloud VPN tunnels and Cloud Router BGP state.

```bash
set -euo pipefail
GCP_PROJECT_ID="<gcp-project-id>"
GCP_REGION="<gcp-region>"
VPN_NAME="<vpn-name>"
ROUTER_NAME="<cloud-router-name>"
AWS_PREFIX="<aws-vpc-cidr>"

gcloud config set project "$GCP_PROJECT_ID"
gcloud compute vpn-tunnels list \
  --regions "$GCP_REGION" \
  --filter="name:$VPN_NAME" \
  --format='table(name,status,router,peerIp)'
gcloud compute routers get-status "$ROUTER_NAME" \
  --region "$GCP_REGION" \
  --format=json
```

The required tunnel/BGP state is `ESTABLISHED` / `UP`, and the AWS VPC CIDR must be present as a learned route. A test from Cloud Shell or another host outside the GCP VPC is not evidence for a VPC client.

### AWS checks

The AWS operator checks the VGW, VPN, and route table associated with the FSx for ONTAP NFS subnet.

```bash
set -euo pipefail
AWS_REGION="<aws-region>"
NFS_SUBNET_ID="<nfs-subnet-id>"
GCP_CIDR="<gcp-client-cidr>"

aws ec2 describe-vpn-connections \
  --region "$AWS_REGION" \
  --vpn-connection-ids "<vpn-id>" \
  --query 'VpnConnections[].VgwTelemetry'
aws ec2 describe-route-tables \
  --region "$AWS_REGION" \
  --filters "Name=association.subnet-id,Values=$NFS_SUBNET_ID" \
  --query 'RouteTables[].{RouteTable:RouteTableId,Routes:Routes}'
```

The return route must use the GCP client CIDR as its destination and a VGW, VPN, or pre-approved VPC peering/TGW as next hop. A learned route on the GCP side does not prove the AWS return path.

### Security and NFS path

Check that the NFS endpoint's security group, NACL, and export policy permit TCP 2049 from the GCP client CIDR. If a change is required, record the target, owner, current value, creator, and rollback in the ledger and obtain approval first. Export-policy state is an ONTAP management-plane item; if it cannot be checked without an approved management interface, stop and mark this procedure open.

```bash
set -euo pipefail
NFS_ENDPOINT="<nfs-endpoint>"
timeout 5 bash -c "</dev/tcp/$NFS_ENDPOINT/2049"
```

Do not mount or write if this probe fails.

## NFS sample data and hash verification

### Safe mount

On the GCP Linux client, validate the mount root before creating a fixture directory.

```bash
set -euo pipefail
SAMPLE_MOUNT="/mnt/gcp-fsx-sample"
NFS_ENDPOINT="<nfs-endpoint>"
EXPORT_PATH="<export-path>"

mountpoint -q "$SAMPLE_MOUNT"
findmnt -T "$SAMPLE_MOUNT" -o TARGET,SOURCE,FSTYPE,OPTIONS
SOURCE="$(findmnt -n -T "$SAMPLE_MOUNT" -o SOURCE)"
FSTYPE="$(findmnt -n -T "$SAMPLE_MOUNT" -o FSTYPE)"
test "$FSTYPE" = nfs || test "$FSTYPE" = nfs4
test "$SOURCE" = "$NFS_ENDPOINT:$EXPORT_PATH"
```

Stop if `mountpoint` fails, the filesystem is local, the source differs from the ledger, or a run directory or marker already exists.

### Fixture and manifest

The new fixture below is not evidence that the earlier 48-file observation used the same method. To publish the earlier observation as `verified`, recover its run ID, environment, date, original manifest, and read-only result from a retained run record. If that record is unavailable, keep the earlier result `open` and treat this as a reproducibility procedure.

Create the 48 files with the Python standard library:

```bash
set -euo pipefail
RUN_ID="<run-id>"
FIXTURE_ROOT="$SAMPLE_MOUNT/gcp-fsx-ontap-$RUN_ID"
python3 - "$FIXTURE_ROOT" <<'PY'
from pathlib import Path
import hashlib
import sys

root = Path(sys.argv[1])
if root.exists():
    raise SystemExit(f"refusing existing fixture: {root}")
root.mkdir(parents=True)
manifest = []
for index in range(1, 49):
    name = f"sample-{index:03d}.txt"
    seed = f"gcp-fsx-ontap-sample-{index:03d}"
    payload = hashlib.sha256(seed.encode("ascii")).hexdigest().encode("ascii") + b"\n"
    path = root / name
    path.write_bytes(payload)
    manifest.append((hashlib.sha256(payload).hexdigest(), name))
(root / "manifest.sha256").write_text(
    "".join(f"{digest}\t{name}\n" for digest, name in sorted(manifest)),
    encoding="ascii",
)
PY

test "$(find "$FIXTURE_ROOT" -type f -name 'sample-*.txt' -printf '%f\n' | wc -l)" -eq 48
```

### DP-volume validation

Compare the manifest on the DP/read-only mount only after the mount source and volume role match the ledger.

```bash
set -euo pipefail
FIXTURE_ROOT="<verified-dp-mount>/gcp-fsx-ontap-<run-id>"
MANIFEST="$FIXTURE_ROOT/manifest.sha256"

ACTUAL="$(find "$FIXTURE_ROOT" -type f -name 'sample-*.txt' -printf '%f\n' | sort)"
EXPECTED="$(printf 'sample-%03d.txt\n' $(seq 1 48) | sort)"
test "$ACTUAL" = "$EXPECTED"
( cd "$FIXTURE_ROOT" && sha256sum -c <(awk -F '\t' '{print $1 "  " $2}' "$MANIFEST") )
touch "$FIXTURE_ROOT/.write-test" 2>&1 && exit 1 || true
```

If the `touch` failure is not `Read-only file system`, do not accept it as proof of DP read-only state. Record the 48-file hash count, failed, missing, extra, and read-only results in the private run ledger. Do not publish real IDs, paths, or individual hashes.

## Cleanup and stop conditions

The run owner cleans up in this order:

1. Remove the fixture directory and unmount only the run-created mount. Do not remove an existing mount.
2. Stop/delete a temporary client only when the ledger proves this run created it.
3. Revert a run-created security rule, route, or BGP advertisement only after a fresh read confirms its definition and ownership.
4. Leave shared or pre-existing VPN, Cloud Router, VGW, peering, route tables, SVMs, and volumes in place and request owner review.
5. Stop if an active transfer, incomplete relationship, or dependency remains. Relationship break/delete requires a fresh target/owner/state confirmation.

This document authoring workflow performs none of these mutations.

## Related documents

- [Evidence policy](../evidence-policy.md)
- [Localization workflow](../../agent/localization.md)
- [FSx for ONTAP S3 Access Points constraints](../../ja/domains/data-utilization/notes/s3-access-point-constraints.md) (日本語)
- [Data protection](../domains/data-protection/)
- [Client access](../domains/client-access/)
- [GCP-to-FSx for ONTAP peering and replication open items](gcp-to-fsx-ontap-peering-and-replication-open-items.md)

## Evidence and open items

> **Evidence: documented**
>
> The ordering of VPN, Cloud Router, VGW, route, security-group, export-policy, and NFS checks follows public provider guidance and repository procedure conventions. It does not prove the state of a particular environment.

> **Status: open**
>
> The conversation's 48-file SHA-256 result is not backed here by a retained public or private run record with all required fields. It remains open until the run ID, environment, date, 48/48 result, zero failures, zero missing files, and DP read-only observation are available.

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/reference/gcp-to-fsx-ontap-preflight-and-sample-validation.md) | [English](gcp-to-fsx-ontap-preflight-and-sample-validation.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
