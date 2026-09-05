#!/usr/bin/env bash
#
# Create a LUN, an igroup and a LUN map on an Amazon FSx for NetApp ONTAP file system.
#
# These three objects have no Amazon FSx API action and no CloudFormation resource type, so they are
# created against the ONTAP REST API. That boundary is the reason this script exists alongside a
# CloudFormation template rather than inside it.
#
# The script is idempotent. Every step reads the current state first and creates only what is
# missing, so running it twice leaves the same LUN count, the same igroup membership and the same
# number of LUN maps. The AWS procedure for connecting iSCSI is not idempotent - re-running its
# connection loop adds sessions - which is what makes this property worth asserting and measuring.
# Verify it with verify-block.sh, which prints the five counts this script must not change on a
# second run.
#
# The fsxadmin password is read from AWS Secrets Manager at run time. It is never accepted as an
# argument, because arguments are visible to every user on the host through ps.
#
# Requires: aws, curl, jq. Run it on a host that can reach the ONTAP management endpoint on 443.

set -euo pipefail

FILE_SYSTEM_ID=""
SVM=""
VOLUME=""
LUN_NAME="lun1"
LUN_SIZE="40G"
IGROUP=""
INITIATOR=""
OS_TYPE="linux"
SECRET_ID=""
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
CHECK_ONLY="false"
MGMT_IP_ARG=""
PASSWORD_STDIN="false"

usage() {
  cat <<'USAGE'
Usage: provision-lun.sh (--file-system-id fs-... | --management-ip IP) --svm NAME --volume NAME
                        (--secret-id NAME_OR_ARN | --password-stdin)
                        [--lun-name NAME] [--lun-size SIZE] [--igroup NAME]
                        [--initiator IQN] [--os-type TYPE] [--region REGION] [--check]

Required:
  --svm             SVM name. Output SvmName of the quickstart stack.
  --volume          Volume that will hold the LUN. Output VolumeName of the quickstart stack.

  How to reach ONTAP, one of:
  --file-system-id  Amazon FSx file system ID. The management address is resolved through the
                    Amazon FSx API, which needs a route to it: a public address, a NAT gateway, or
                    an fsx interface VPC endpoint. A private subnet that only has ssm and
                    secretsmanager endpoints resolves fsx.<region>.amazonaws.com to public
                    addresses and the call times out.
  --management-ip   The ONTAP management address directly, skipping the Amazon FSx API. Get it once
                    from wherever your AWS CLI has reach:
                      aws fsx describe-file-systems --file-system-ids fs-... \
                        --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]'

  How to get the password, one of:
  --secret-id       Secrets Manager secret whose SecretString JSON has a "password" key.
  --password-stdin  Read the password from standard input. Use when the host cannot reach
                    Secrets Manager. Never pass a password as an argument: arguments are visible
                    to every user on the host through ps.

Optional:
  --lun-name        LUN name inside the volume. Default: lun1
  --lun-size        LUN size accepted by the ONTAP REST API, for example 40G. Default: 40G
  --igroup          igroup name. Default: ig_<trailing component of the initiator IQN>. Derived
                    from the IQN and not from the hostname, which on many images contains the
                    host's private address.
  --initiator       Initiator IQN to place in the igroup. Default: this host's IQN from
                    /etc/iscsi/initiatorname.iscsi
  --os-type         LUN and igroup os_type. Default: linux. Windows of any version is windows_2008;
                    windows_2022 does not exist.
  --region          AWS region. Defaults to AWS_REGION or AWS_DEFAULT_REGION.
  --check           Report the current state and exit without creating anything.

The script prints what it created and what already existed, so a second run is visibly a no-op.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --file-system-id) FILE_SYSTEM_ID="$2"; shift 2 ;;
    --svm) SVM="$2"; shift 2 ;;
    --volume) VOLUME="$2"; shift 2 ;;
    --lun-name) LUN_NAME="$2"; shift 2 ;;
    --lun-size) LUN_SIZE="$2"; shift 2 ;;
    --igroup) IGROUP="$2"; shift 2 ;;
    --initiator) INITIATOR="$2"; shift 2 ;;
    --os-type) OS_TYPE="$2"; shift 2 ;;
    --secret-id) SECRET_ID="$2"; shift 2 ;;
    --management-ip) MGMT_IP_ARG="$2"; shift 2 ;;
    --password-stdin) PASSWORD_STDIN="true"; shift ;;
    --region) REGION="$2"; shift 2 ;;
    --check) CHECK_ONLY="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "provision-lun: $*" >&2; exit 1; }

for tool in curl jq; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required but not installed"
done

[ -n "$SVM" ] || die "--svm is required"
[ -n "$VOLUME" ] || die "--volume is required"
[ -n "$FILE_SYSTEM_ID" ] || [ -n "$MGMT_IP_ARG" ] ||
  die "one of --file-system-id or --management-ip is required"
[ -n "$SECRET_ID" ] || [ "$PASSWORD_STDIN" = "true" ] ||
  die "one of --secret-id or --password-stdin is required"

if [ -z "$MGMT_IP_ARG" ] || { [ -n "$SECRET_ID" ] && [ "$PASSWORD_STDIN" != "true" ]; }; then
  command -v aws >/dev/null 2>&1 ||
    die "aws is required unless both --management-ip and --password-stdin are given"
  [ -n "$REGION" ] || die "--region is required (or set AWS_REGION)"
fi

if [ -z "$INITIATOR" ]; then
  [ -r /etc/iscsi/initiatorname.iscsi ] ||
    die "cannot read /etc/iscsi/initiatorname.iscsi; pass --initiator explicitly"
  INITIATOR="$(sed -n 's/^InitiatorName=//p' /etc/iscsi/initiatorname.iscsi | head -1)"
  [ -n "$INITIATOR" ] || die "no InitiatorName found; pass --initiator explicitly"
fi

if [ -z "$IGROUP" ]; then
  # Derived from the trailing component of the IQN rather than from the hostname. On many images the
  # hostname contains the host's private address, which would then be embedded in an ONTAP object
  # name and in every output that lists it.
  IGROUP="ig_$(printf '%s' "${INITIATOR##*:}" | tr -c '[:alnum:]' '_')"
fi

# ---------------------------------------------------------------- endpoint and credentials

# AWS::FSx::FileSystem exposes no Fn::GetAtt for the management endpoint, so it cannot be a
# CloudFormation output and has to be resolved here - or supplied with --management-ip when the host
# has no route to the Amazon FSx API.
if [ -n "$MGMT_IP_ARG" ]; then
  MGMT_IP="$MGMT_IP_ARG"
else
  MGMT_IP="$(aws fsx describe-file-systems \
    --file-system-ids "$FILE_SYSTEM_ID" --region "$REGION" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
    --output text 2>/dev/null || true)"
  [ -n "$MGMT_IP" ] && [ "$MGMT_IP" != "None" ] ||
    die "could not resolve the management address for $FILE_SYSTEM_ID. If the call timed out, this
      host has no route to the Amazon FSx API; pass --management-ip instead"
fi

if [ "$PASSWORD_STDIN" = "true" ]; then
  IFS= read -r PASSWORD || true
  [ -n "$PASSWORD" ] || die "no password on standard input"
else
  PASSWORD="$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_ID" --region "$REGION" \
    --query SecretString --output text 2>/dev/null |
    jq -r '.password // empty')"
  [ -n "$PASSWORD" ] || die "secret $SECRET_ID has no \"password\" key in its SecretString"
fi

# curl reads the credential from a file descriptor so it never appears in the process list.
#
# --insecure is required here: the ONTAP management endpoint of an FSx for ONTAP file system presents
# a self-signed certificate, and Amazon FSx does not publish a CA to pin it against. The connection
# is to a private address inside the VPC, reachable only from the security group attached to this
# host. If that is not acceptable in your environment, install your own certificate on the SVM with
# the ONTAP "security certificate" commands and drop this flag.
ontap() {
  local method="$1" path="$2" body="${3:-}"
  local -a args=(--silent --show-error --insecure --max-time 60
    --user-agent 'fsxn-adoption-playbook/examples-block-storage'
    --request "$method" "https://${MGMT_IP}/api${path}"
    --header 'content-type: application/json'
    --config /dev/fd/3)
  [ -n "$body" ] && args+=(--data "$body")
  curl "${args[@]}" 3<<<"user = \"fsxadmin:${PASSWORD}\""
}

ontap_ok() {
  # Fails loudly on an ONTAP error payload instead of letting a later step misread it.
  local out="$1" what="$2"
  if printf '%s' "$out" | jq -e 'has("error")' >/dev/null 2>&1; then
    local msg
    msg="$(printf '%s' "$out" | jq -r '.error.message // "unknown error"')"
    die "$what failed: $msg"
  fi
}

# ---------------------------------------------------------------- current state

LUN_PATH="/vol/${VOLUME}/${LUN_NAME}"

lun_json="$(ontap GET "/storage/luns?svm.name=${SVM}&name=${LUN_PATH}&fields=uuid,space.size,os_type,serial_number_hex")"
ontap_ok "$lun_json" "reading LUNs"
lun_count="$(printf '%s' "$lun_json" | jq -r '.num_records // 0')"

ig_json="$(ontap GET "/protocols/san/igroups?svm.name=${SVM}&name=${IGROUP}&fields=uuid,initiators,os_type,protocol")"
ontap_ok "$ig_json" "reading igroups"
ig_count="$(printf '%s' "$ig_json" | jq -r '.num_records // 0')"

echo "== current state =="
printf 'management endpoint : %s\n' "$MGMT_IP"
printf 'LUN %-18s: %s\n' "$LUN_PATH" "$([ "$lun_count" -gt 0 ] && echo present || echo absent)"
printf 'igroup %-15s: %s\n' "$IGROUP" "$([ "$ig_count" -gt 0 ] && echo present || echo absent)"
printf 'initiator           : %s\n' "$INITIATOR"

if [ "$CHECK_ONLY" = "true" ]; then
  echo "(--check given, nothing created)"
  exit 0
fi

echo
echo "== reconciling =="

# ---------------------------------------------------------------- LUN

if [ "$lun_count" -gt 0 ]; then
  echo "lun    : exists, left alone"
else
  out="$(ontap POST /storage/luns "$(jq -nc \
    --arg svm "$SVM" --arg name "$LUN_PATH" --arg os "$OS_TYPE" --arg size "$LUN_SIZE" \
    '{svm:{name:$svm}, name:$name, os_type:$os, space:{size:$size}}')")"
  ontap_ok "$out" "creating LUN $LUN_PATH"
  echo "lun    : created $LUN_PATH ($LUN_SIZE, os_type=$OS_TYPE)"
fi

# ---------------------------------------------------------------- igroup

if [ "$ig_count" -gt 0 ]; then
  ig_uuid="$(printf '%s' "$ig_json" | jq -r '.records[0].uuid')"
  echo "igroup : exists, left alone"
  if printf '%s' "$ig_json" | jq -e --arg i "$INITIATOR" \
      '.records[0].initiators // [] | map(.name) | index($i) != null' >/dev/null; then
    echo "member : $INITIATOR already in $IGROUP"
  else
    out="$(ontap POST "/protocols/san/igroups/${ig_uuid}/initiators" \
      "$(jq -nc --arg i "$INITIATOR" '{records:[{name:$i}]}')")"
    ontap_ok "$out" "adding $INITIATOR to $IGROUP"
    echo "member : added $INITIATOR to $IGROUP"
  fi
else
  out="$(ontap POST /protocols/san/igroups "$(jq -nc \
    --arg svm "$SVM" --arg name "$IGROUP" --arg os "$OS_TYPE" --arg i "$INITIATOR" \
    '{svm:{name:$svm}, name:$name, os_type:$os, protocol:"iscsi", initiators:[{name:$i}]}')")"
  ontap_ok "$out" "creating igroup $IGROUP"
  echo "igroup : created $IGROUP with $INITIATOR"
fi

# ---------------------------------------------------------------- LUN map

map_json="$(ontap GET "/protocols/san/lun-maps?svm.name=${SVM}&lun.name=${LUN_PATH}&igroup.name=${IGROUP}&fields=logical_unit_number")"
ontap_ok "$map_json" "reading LUN maps"
map_count="$(printf '%s' "$map_json" | jq -r '.num_records // 0')"

if [ "$map_count" -gt 0 ]; then
  echo "map    : $LUN_PATH already mapped to $IGROUP"
else
  out="$(ontap POST /protocols/san/lun-maps "$(jq -nc \
    --arg svm "$SVM" --arg lun "$LUN_PATH" --arg ig "$IGROUP" \
    '{svm:{name:$svm}, lun:{name:$lun}, igroup:{name:$ig}}')")"
  ontap_ok "$out" "mapping $LUN_PATH to $IGROUP"
  echo "map    : mapped $LUN_PATH to $IGROUP"
fi

# ---------------------------------------------------------------- result

final="$(ontap GET "/storage/luns?svm.name=${SVM}&name=${LUN_PATH}&fields=serial_number_hex,space.size,os_type,status.state")"
ontap_ok "$final" "reading the finished LUN"

echo
echo "== result =="
printf '%s' "$final" | jq -r '.records[0] |
  "path        : \(.name)",
  "size        : \(.space.size) bytes",
  "os_type     : \(.os_type)",
  "state       : \(.status.state)",
  "serial hex  : \(.serial_number_hex // "not reported by this ONTAP version")"'

serial="$(printf '%s' "$final" | jq -r '.records[0].serial_number_hex // empty')"
if [ -n "$serial" ]; then
  # The host sees the LUN under this identifier. Documented by AWS as 3600a0980 plus the serial hex.
  printf 'expected wwid: 3600a0980%s\n' "$serial"
fi

echo
echo "Next: run connect-iscsi.sh on this host, then verify-block.sh."
