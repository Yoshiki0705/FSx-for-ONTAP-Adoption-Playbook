#!/usr/bin/env bash
#
# Report the state of an Amazon FSx for NetApp ONTAP block-storage setup from both sides.
#
# The five counts under "idempotency observables" are the ones provision-lun.sh and connect-iscsi.sh
# must not change on a second run. Capture them, run both scripts again, capture them again, and
# compare. That is the whole test, and it is the reason this script exists separately from the two it
# checks: a script that both acts and judges its own result is not evidence.
#
# It also prints the three places capacity is counted and whether the kernel can do NVMe multipath,
# because both are routine surprises rather than exceptional ones.
#
# Read-only. It creates nothing and changes nothing.
#
# Requires: aws, curl, jq for the storage side; iscsiadm and multipath for the host side. Run as root
# to see the host side.

set -euo pipefail

FILE_SYSTEM_ID=""
SVM=""
VOLUME=""
SECRET_ID=""
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
MGMT_IP_ARG=""
PASSWORD_STDIN="false"

usage() {
  cat <<'USAGE'
Usage: verify-block.sh (--file-system-id fs-... | --management-ip IP) --svm NAME
                       (--secret-id NAME_OR_ARN | --password-stdin)
                       [--volume NAME] [--region REGION]

Required:
  --svm             SVM name.

  How to reach ONTAP, one of:
  --file-system-id  Amazon FSx file system ID. Needs a route to the Amazon FSx API.
  --management-ip   The ONTAP management address directly, skipping that API.

  How to get the password, one of:
  --secret-id       Secrets Manager secret whose SecretString JSON has a "password" key.
  --password-stdin  Read it from standard input.

Optional:
  --volume          Volume to report capacity for. Omit to skip the capacity section.
  --region          AWS region. Defaults to AWS_REGION or AWS_DEFAULT_REGION.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --file-system-id) FILE_SYSTEM_ID="$2"; shift 2 ;;
    --svm) SVM="$2"; shift 2 ;;
    --volume) VOLUME="$2"; shift 2 ;;
    --secret-id) SECRET_ID="$2"; shift 2 ;;
    --management-ip) MGMT_IP_ARG="$2"; shift 2 ;;
    --password-stdin) PASSWORD_STDIN="true"; shift ;;
    --region) REGION="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "verify-block: $*" >&2; exit 1; }

[ -n "$SVM" ] || die "--svm is required"
[ -n "$FILE_SYSTEM_ID" ] || [ -n "$MGMT_IP_ARG" ] ||
  die "one of --file-system-id or --management-ip is required"
[ -n "$SECRET_ID" ] || [ "$PASSWORD_STDIN" = "true" ] ||
  die "one of --secret-id or --password-stdin is required"
for tool in curl jq; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required but not installed"
done

if [ -n "$MGMT_IP_ARG" ]; then
  MGMT_IP="$MGMT_IP_ARG"
else
  [ -n "$REGION" ] || die "--region is required (or set AWS_REGION)"
  MGMT_IP="$(aws fsx describe-file-systems --file-system-ids "$FILE_SYSTEM_ID" --region "$REGION" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
    --output text 2>/dev/null || true)"
  [ -n "$MGMT_IP" ] && [ "$MGMT_IP" != "None" ] ||
    die "could not resolve the management address. If the call timed out, this host has no route to
      the Amazon FSx API; pass --management-ip instead"
fi

if [ "$PASSWORD_STDIN" = "true" ]; then
  IFS= read -r PASSWORD || true
  [ -n "$PASSWORD" ] || die "no password on standard input"
else
  [ -n "$REGION" ] || die "--region is required (or set AWS_REGION)"
  PASSWORD="$(aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --region "$REGION" \
    --query SecretString --output text 2>/dev/null | jq -r '.password // empty')"
  [ -n "$PASSWORD" ] || die "secret $SECRET_ID has no \"password\" key"
fi

# See provision-lun.sh for why --insecure is used against this endpoint.
ontap() {
  curl --silent --show-error --insecure --max-time 60 \
    --user-agent 'fsxn-adoption-playbook/examples-block-storage' \
    --config /dev/fd/3 "https://${MGMT_IP}/api$1" 3<<<"user = \"fsxadmin:${PASSWORD}\""
}

num() { printf '%s' "$1" | jq -r '.num_records // 0'; }

# ---------------------------------------------------------------- idempotency observables

luns="$(ontap "/storage/luns?svm.name=${SVM}&fields=name,space.size,space.guarantee.requested,os_type,serial_number_hex")"
igroups="$(ontap "/protocols/san/igroups?svm.name=${SVM}&fields=name,initiators,os_type,protocol")"
maps="$(ontap "/protocols/san/lun-maps?svm.name=${SVM}&fields=lun.name,igroup.name,logical_unit_number")"

lun_count="$(num "$luns")"
igroup_initiators="$(printf '%s' "$igroups" | jq -r '[.records[]?.initiators // [] | length] | add // 0')"
map_count="$(num "$maps")"

if command -v iscsiadm >/dev/null 2>&1; then
  session_count="$(iscsiadm -m session 2>/dev/null | grep -c '^tcp' || true)"
else
  session_count="n/a"
fi

if command -v multipath >/dev/null 2>&1; then
  path_count="$(multipath -ll 2>/dev/null | grep -cE '^[[:space:]]*[|`].*[0-9]+:[0-9]+:[0-9]+:[0-9]+' || true)"
else
  path_count="n/a"
fi

echo "== idempotency observables =="
echo "These five must be identical before and after a second run of provision-lun.sh and"
echo "connect-iscsi.sh. Any change means a step is not idempotent."
echo
printf '%-28s %s\n' 'LUNs on the SVM'            "$lun_count"
printf '%-28s %s\n' 'igroup initiators (total)'  "$igroup_initiators"
printf '%-28s %s\n' 'LUN maps'                   "$map_count"
printf '%-28s %s\n' 'iSCSI sessions (this host)' "$session_count"
printf '%-28s %s\n' 'multipath paths (this host)' "$path_count"

# ---------------------------------------------------------------- detail

echo
echo "== LUNs =="
if [ "$lun_count" -eq 0 ]; then
  echo "(none)"
else
  printf '%s' "$luns" | jq -r '.records[] |
    "\(.name)  size=\(.space.size)  reserved=\(.space.guarantee.requested)  os_type=\(.os_type)  wwid=3600a0980\(.serial_number_hex // "?")"'
fi

echo
echo "== igroups =="
if [ "$(num "$igroups")" -eq 0 ]; then
  echo "(none)"
else
  printf '%s' "$igroups" | jq -r '.records[] |
    "\(.name)  protocol=\(.protocol)  os_type=\(.os_type)  initiators=\((.initiators // []) | map(.name) | join(","))"'
fi

echo
echo "== LUN maps =="
if [ "$map_count" -eq 0 ]; then
  echo "(none)"
else
  printf '%s' "$maps" | jq -r '.records[] | "\(.lun.name) -> \(.igroup.name)  lun_id=\(.logical_unit_number)"'
fi

# ---------------------------------------------------------------- capacity, three places

if [ -n "$VOLUME" ]; then
  echo
  echo "== capacity, counted in three places =="
  aggr="$(ontap '/storage/aggregates?fields=name,space.block_storage.size,space.block_storage.available')"
  printf '%s' "$aggr" | jq -r '.records[]? |
    "aggregate \(.name): size=\(.space.block_storage.size) available=\(.space.block_storage.available)"'

  vol="$(ontap "/storage/volumes?svm.name=${SVM}&name=${VOLUME}&fields=space.size,space.available,space.used,space.snapshot.reserve_percent")"
  printf '%s' "$vol" | jq -r '.records[]? |
    "volume \(.name): size=\(.space.size) used=\(.space.used) available=\(.space.available) snapshot_reserve=\(.space.snapshot.reserve_percent)%"'

  echo "Read the volume figures against the LUN's reserved flag above. A LUN created through the"
  echo "REST API has space.guarantee.requested false by default, so the volume shows almost nothing"
  echo "used until data is written. Turning reservation on makes the volume account for the LUN's"
  echo "full size immediately, with nothing written. Either way these figures can lag a change by"
  echo "up to about 30 seconds, so a reading taken straight after a change shows the old value."
fi

# ---------------------------------------------------------------- host side

echo
echo "== host =="
if [ "$path_count" != "n/a" ]; then
  multipath -ll 2>/dev/null || echo "(no maps)"
  echo
  printf 'replacement_timeout in iscsid.conf : %s\n' \
    "$(sed -n 's/^node.session.timeo.replacement_timeout *= *//p' /etc/iscsi/iscsid.conf 2>/dev/null | head -1)"
  printf '/etc/multipath.conf size           : %s bytes\n' "$(wc -c </etc/multipath.conf 2>/dev/null || echo absent)"
else
  echo "(host tooling not present; storage side only)"
fi

kcfg="/boot/config-$(uname -r 2>/dev/null || true)"
echo
echo "== NVMe multipath in this kernel =="
if [ -r "$kcfg" ]; then
  if grep -q '^CONFIG_NVME_MULTIPATH=y' "$kcfg"; then
    echo "CONFIG_NVME_MULTIPATH=y - a namespace would present as one device and fail over on ANA"
  else
    echo "CONFIG_NVME_MULTIPATH is not set - one namespace would present as two devices with the"
    echo "same wwid, and an application bound to one of them has no path to fail over to. This is"
    echo "the state measured on Amazon Linux 2023. It does not affect iSCSI."
  fi
else
  echo "cannot read $kcfg; check CONFIG_NVME_MULTIPATH another way before choosing NVMe/TCP"
fi
