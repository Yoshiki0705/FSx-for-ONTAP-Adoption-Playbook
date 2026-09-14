#!/usr/bin/env bash
#
# Remove everything this example creates, in the order that works, and prove afterwards that each
# piece is gone.
#
# Reports only unless --apply is given.
#
# THE FIRST STEP IS THE BILLING ONE. An AWS Client VPN endpoint is charged per subnet association
# hour, not per endpoint, so removing the association is what stops the meter - $0.15 per hour in
# ap-northeast-1. Everything after that is cleanup. If you have to stop reading partway through,
# stop after step 1.
#
# The ONTAP objects go before the CloudFormation stacks because the Amazon FSx API did not create
# them and does not know they exist, so a stack deletion neither removes them nor waits for them.
#
# Requires: aws, curl, jq.

set -euo pipefail

BASE_STACK="fsxn-client-access"
VPN_STACK="fsxn-client-access-vpn"
SVM=""
MGMT_IP_ARG=""
FILE_SYSTEM_ID=""
SECRET_ID=""
PASSWORD_STDIN="false"
CERT_ARN=""
# Matches the default in make-client-vpn-certs.sh, which keeps private keys out of the repository.
PKI_DIR="${HOME}/.fsxn-client-access/pki"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
APPLY="false"

usage() {
  cat <<'USAGE'
Usage: teardown.sh [--base-stack NAME] [--vpn-stack NAME] [--svm NAME]
                   [--file-system-id fs-... | --management-ip IP]
                   [--secret-id NAME | --password-stdin]
                   [--certificate-arn ARN] [--pki-dir DIR] [--region REGION] [--apply]

Without --apply nothing is removed. The report alone is worth running: it answers "is anything still
costing money", which is a different question from "did I delete the stack".

Optional:
  --base-stack       CloudFormation stack from fsxontap-client-access.yaml. Default: fsxn-client-access
  --vpn-stack        Stack from fsxontap-client-vpn.yaml. Default: fsxn-client-access-vpn
  --svm              SVM name. Needed to remove the ONTAP objects. Without it, those steps are
                     skipped and reported as skipped rather than as done.
  --file-system-id   Used to resolve the ONTAP management address, and to mark which file system in
                     step 5 belongs to this example.
  --management-ip    The management address directly.
  --secret-id        Secrets Manager secret holding the fsxadmin password.
  --password-stdin   Read the fsxadmin password from standard input instead.
  --certificate-arn  ACM certificate imported by make-client-vpn-certs.sh. Read from
                     <pki-dir>/server-certificate-arn.txt when not given.
  --pki-dir          Directory holding the generated keys.
                     Default: $HOME/.fsxn-client-access/pki, outside the repository
  --region           AWS region. Defaults to AWS_REGION or AWS_DEFAULT_REGION.
  --apply            Actually remove things.

What is NOT removed, deliberately:
  - the two Secrets Manager secrets. They cost almost nothing, they are reusable, and a scheduled
    secret deletion is a seven-day window during which the name cannot be reused - which turns a
    later rebuild into a puzzle.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --base-stack) BASE_STACK="$2"; shift 2 ;;
    --vpn-stack) VPN_STACK="$2"; shift 2 ;;
    --svm) SVM="$2"; shift 2 ;;
    --file-system-id) FILE_SYSTEM_ID="$2"; shift 2 ;;
    --management-ip) MGMT_IP_ARG="$2"; shift 2 ;;
    --secret-id) SECRET_ID="$2"; shift 2 ;;
    --password-stdin) PASSWORD_STDIN="true"; shift ;;
    --certificate-arn) CERT_ARN="$2"; shift 2 ;;
    --pki-dir) PKI_DIR="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --apply) APPLY="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "teardown: $*" >&2; exit 1; }
step() { echo; echo "=== $* ==="; }
note() { echo "    $*"; }

for tool in aws jq; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required but not installed"
done
[ -n "$REGION" ] || die "--region is required (or set AWS_REGION)"

if [ "$APPLY" != "true" ]; then
  echo "REPORT ONLY. Nothing will be removed. Add --apply to act."
fi

if [ -z "$CERT_ARN" ] && [ -r "$PKI_DIR/server-certificate-arn.txt" ]; then
  CERT_ARN="$(head -1 "$PKI_DIR/server-certificate-arn.txt")"
fi

# ------------------------------------------------------------------ 1. the billing one

step "1. Client VPN subnet associations (this is what costs \$0.15 per hour)"

VPN_ENDPOINTS="$(aws ec2 describe-client-vpn-endpoints --region "$REGION" \
  --query 'ClientVpnEndpoints[].[ClientVpnEndpointId,Status.Code]' --output text 2>/dev/null || true)"
if [ -z "$VPN_ENDPOINTS" ]; then
  note "no Client VPN endpoints in $REGION"
else
  printf '%s\n' "$VPN_ENDPOINTS" | while read -r ep_id ep_state; do
    [ -n "$ep_id" ] || continue
    assoc="$(aws ec2 describe-client-vpn-target-networks --region "$REGION" \
      --client-vpn-endpoint-id "$ep_id" \
      --query 'ClientVpnTargetNetworks[].AssociationId' --output text 2>/dev/null || true)"
    if [ -z "$assoc" ] || [ "$assoc" = "None" ]; then
      note "$ep_id ($ep_state): no associations. No hourly association charge."
    else
      note "$ep_id ($ep_state): associations $assoc -- BILLING"
      if [ "$APPLY" = "true" ]; then
        for a in $assoc; do
          note "  disassociating $a"
          aws ec2 disassociate-client-vpn-target-network --region "$REGION" \
            --client-vpn-endpoint-id "$ep_id" --association-id "$a" >/dev/null
        done
      fi
    fi
  done
fi
note "The count of associations, not the existence of the endpoint, is the check for 'stopped'."

# ------------------------------------------------------------------ 2. ONTAP objects

step "2. ONTAP objects (invisible to CloudFormation)"

if [ -z "$SVM" ]; then
  note "skipped: --svm not given. The SMB server, share, local user, export policy, LUN, igroup and"
  note "LUN map are NOT removed by the stack deletion below, so they are still there."
else
  if [ -n "$MGMT_IP_ARG" ]; then
    MGMT_IP="$MGMT_IP_ARG"
  elif [ -n "$FILE_SYSTEM_ID" ]; then
    MGMT_IP="$(aws fsx describe-file-systems --file-system-ids "$FILE_SYSTEM_ID" \
      --region "$REGION" \
      --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
      --output text 2>/dev/null || true)"
  else
    MGMT_IP=""
  fi

  if [ -z "$MGMT_IP" ] || [ "$MGMT_IP" = "None" ]; then
    note "skipped: could not resolve the ONTAP management address."
    note "Pass --management-ip, or --file-system-id from somewhere with a route to the Amazon FSx API."
  else
    command -v curl >/dev/null 2>&1 || die "curl is required to reach the ONTAP REST API"
    if [ "$PASSWORD_STDIN" = "true" ]; then
      IFS= read -r PASSWORD || die "no password on standard input"
    elif [ -n "$SECRET_ID" ]; then
      PASSWORD="$(aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --region "$REGION" \
        --query SecretString --output text 2>/dev/null | jq -r '.password // empty')"
      [ -n "$PASSWORD" ] || die "secret '$SECRET_ID' has no 'password' key, or could not be read"
    else
      die "one of --secret-id or --password-stdin is required to remove the ONTAP objects"
    fi

    BASE="https://$MGMT_IP/api"
    # --connect-timeout and --max-time are not optional here. A teardown is frequently run when the
    # route is already gone -- the VPN is down, or the association was removed in step 1 of this very
    # script -- and without them curl waits on a dead address indefinitely. A report that hangs is
    # worse than one that says UNREACHABLE, because the operator cannot tell it apart from slowness
    # and leaves it running while the file system keeps billing.
    ontap() {
      local method="$1" path="$2"
      curl -sk --connect-timeout 8 --max-time 20 -u "fsxadmin:$PASSWORD" -X "$method" "$BASE$path"
    }

    # Order: LUN maps before igroups and LUNs, because a mapped LUN and a mapped igroup both refuse
    # deletion. The share and the local user before the SMB server, for the same reason.
    for query in \
      "lun-maps:/protocols/san/lun-maps?svm.name=$SVM&fields=lun.uuid,igroup.uuid" \
      "luns:/storage/luns?svm.name=$SVM&fields=uuid,name" \
      "igroups:/protocols/san/igroups?svm.name=$SVM&fields=uuid,name" \
      "shares:/protocols/cifs/shares?svm.name=$SVM&fields=name" \
      "local-users:/protocols/cifs/local-users?svm.name=$SVM&fields=name,sid" \
      "cifs-server:/protocols/cifs/services?svm.name=$SVM&fields=name" \
      "export-policies:/protocols/nfs/export-policies?svm.name=$SVM&fields=id,name"
    do
      label="${query%%:*}"
      path="${query#*:}"
      # "could not ask" and "asked, found none" must not print the same thing. The first version
      # printed an empty string for both, because a failed curl produces no body, jq turns that into
      # nothing, and the `|| echo 0` never fires since the pipeline itself succeeded. A blank next to
      # "lun-maps:" reads as zero, so a teardown run with no route to ONTAP looked like a clean SVM.
      if ! body="$(ontap GET "$path")" || [ -z "$body" ]; then
        note "$label: UNREACHABLE (not asked -- this is not the same as none)"
        continue
      fi
      count="$(printf '%s' "$body" | jq -r '.num_records // "unparseable"' 2>/dev/null || echo unparseable)"
      note "$label: $count"
    done

    if [ "$APPLY" = "true" ]; then
      note "Removing the ONTAP objects is left as explicit DELETE calls rather than automated here."
      note "Deleting the volumes with the stack removes the LUN and the share along with them, and"
      note "an automated sweep over an SVM is the wrong habit to encode in an example: the same"
      note "script pointed at a shared SVM would remove someone else's share. Delete by name:"
      note "  curl -sk -u fsxadmin:\$PW -X DELETE $BASE/protocols/cifs/shares/<svm-uuid>/<share>"
      note "  curl -sk -u fsxadmin:\$PW -X DELETE $BASE/protocols/san/lun-maps/<lun-uuid>/<igroup-uuid>"
    fi
  fi
fi

# ------------------------------------------------------------------ 3. the stacks

step "3. CloudFormation stacks"

for stack in "$VPN_STACK" "$BASE_STACK"; do
  state="$(aws cloudformation describe-stacks --stack-name "$stack" --region "$REGION" \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo ABSENT)"
  note "$stack: $state"
  if [ "$APPLY" = "true" ] && [ "$state" != "ABSENT" ]; then
    note "  deleting $stack"
    aws cloudformation delete-stack --stack-name "$stack" --region "$REGION"
    note "  waiting"
    aws cloudformation wait stack-delete-complete --stack-name "$stack" --region "$REGION" || {
      note "  the wait failed. A volume that still holds a LUN, or a FlexClone in the volume"
      note "  recovery queue, both block deletion. Read the stack events before retrying."
    }
  fi
done

note "The VPN stack goes first: deleting it removes the association, and an association whose"
note "endpoint is gone cannot be reported on afterwards."

# ------------------------------------------------------------------ 4. certificates and keys

step "4. Certificate and private keys"

if [ -z "$CERT_ARN" ]; then
  note "no certificate ARN given and none found in $PKI_DIR/server-certificate-arn.txt"
else
  note "ACM certificate: $CERT_ARN"
  if [ "$APPLY" = "true" ]; then
    # An ACM certificate in use by a Client VPN endpoint cannot be deleted, so this runs after the
    # stack deletion above rather than alongside it.
    aws acm delete-certificate --certificate-arn "$CERT_ARN" --region "$REGION" 2>/dev/null ||
      note "  refused. It is usually still associated with the endpoint; retry once the stack is gone."
  fi
fi

if [ -d "$PKI_DIR" ]; then
  note "$PKI_DIR exists and holds the CA, server and client PRIVATE KEYS"
  if [ "$APPLY" = "true" ]; then
    rm -rf "$PKI_DIR"
    note "  removed"
  fi
else
  note "$PKI_DIR not present"
fi

# Both the directory the keys live in and the current directory, because a reader who overrode
# --out-dir to a path inside the repository has a profile here instead.
PROFILE_DIRS="$(dirname "$PKI_DIR") ."
for dir in $PROFILE_DIRS; do
  [ -d "$dir" ] || continue
  count="$(find "$dir" -maxdepth 1 -name '*.ovpn' -type f 2>/dev/null | wc -l | tr -d ' ')"
  [ "$count" != "0" ] || continue
  note "$count .ovpn profile(s) in $dir. Each EMBEDS A CLIENT PRIVATE KEY."
  if [ "$APPLY" = "true" ]; then
    find "$dir" -maxdepth 1 -name '*.ovpn' -type f -delete
    note "  removed"
  fi
done
note "Also remove the profile from the VPN client on the endpoint. Deleting the file here does not."

# ------------------------------------------------------------------ 5. what is left

step "5. Still present"

FS_LEFT="$(aws fsx describe-file-systems --region "$REGION" \
  --query 'FileSystems[].[FileSystemId,Lifecycle]' --output text 2>/dev/null || true)"
note "Amazon FSx file systems in $REGION -- EVERY ONE, not only the one this example created:"
if [ -z "$FS_LEFT" ]; then
  note "  none"
else
  # The one this example owns is marked. Without the marker a reader who has just watched the stack
  # delete sees an AVAILABLE file system on the next line and reads the teardown as having failed,
  # when what they are looking at is somebody else's environment.
  printf '%s\n' "$FS_LEFT" | while read -r fs_id fs_state; do
    if [ -n "$FILE_SYSTEM_ID" ] && [ "$fs_id" = "$FILE_SYSTEM_ID" ]; then
      note "      $fs_id $fs_state   <-- THIS EXAMPLE. Still here, so the deletion did not finish."
    else
      note "      $fs_id $fs_state   (not this example)"
    fi
  done
fi
note "Any file system listed above bills until it is deleted and cannot be stopped. Leave the ones"
note "marked 'not this example' alone -- they belong to something else in this account."
if [ -z "$FILE_SYSTEM_ID" ]; then
  note "Pass --file-system-id to have the one this example created marked in the list above."
fi

if [ "$APPLY" != "true" ]; then
  echo
  echo "REPORT ONLY. Re-run with --apply to act on the above."
fi
