#!/usr/bin/env bash
#
# Configure the ONTAP side of the multiprotocol Active Directory example: an export policy and its
# rules, an SMB share, the UNIX identity the Active Directory test user maps to, and the two
# name-mapping rules that connect them.
#
# None of these objects has an Amazon FSx API action or a CloudFormation resource type, which is why
# this script exists alongside a template rather than inside it. The same boundary is documented for
# LUNs and igroups in examples/block-storage/provision-lun.sh, whose structure this script reuses:
# the argument handling, the Secrets Manager lookup, the curl credential escaping, the HTTP status
# tracking and the idempotence are all taken from there rather than rewritten.
#
# The script is idempotent. Every step reads the current state first and creates only what is
# missing, so a second run reports everything as already present and changes nothing.
#
# The fsxadmin password is read from AWS Secrets Manager at run time. It is never accepted as an
# argument, because arguments are visible to every user on the host through ps.
#
# Requires: curl, jq, and aws unless both --management-ip and --password-stdin are given.

set -euo pipefail

FILE_SYSTEM_ID=""
SVM=""
NTFS_VOLUME=""
NTFS_JUNCTION=""
UNIX_VOLUME=""
REHOST_VOLUME=""
EXPORT_POLICY="mpad_clients"
CLIENT_MATCH=""
SHARE_NAME="ntfsshare"
AD_USER=""
UNIX_USER=""
UNIX_UID=""
UNIX_GID="1000"
UNIX_GROUP=""
SECRET_ID=""
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
CHECK_ONLY="false"
MGMT_IP_ARG=""
PASSWORD_STDIN="false"

usage() {
  cat <<'USAGE'
Usage: provision-multiprotocol.sh (--file-system-id fs-... | --management-ip IP)
                                  --svm NAME --ntfs-volume NAME --unix-volume NAME
                                  --client-match CIDR --ad-user 'DOMAIN\user'
                                  (--secret-id NAME_OR_ARN | --password-stdin)
                                  [--rehost-volume NAME] [--export-policy NAME] [--share NAME]
                                  [--unix-user NAME] [--uid N] [--gid N] [--unix-group NAME]
                                  [--region REGION] [--check]

Required:
  --svm             SVM name. Output SourceSvmName of the stack.
  --ntfs-volume     Volume with NTFS security style. Output NtfsVolumeName.
  --unix-volume     Control volume with UNIX security style. Output UnixVolumeName.
  --client-match    Client match for the export policy rule: the CIDR of the client subnet. A rule
                    matching 0.0.0.0/0 would make the export policy stop being part of what the
                    measurement controls, so that value is refused.
  --ad-user         The Active Directory test user, as DOMAIN\user or user@domain. It must NOT be a
                    member of the group given as FileSystemAdministratorsGroup: members of that
                    group are evaluated with storage-administrator privileges and every permission
                    test against them returns a false pass.

  How to reach ONTAP, one of:
  --file-system-id  Amazon FSx file system ID. The management address is resolved through the
                    Amazon FSx API, which needs a route to it: a public address, a NAT gateway, or
                    an fsx interface VPC endpoint.
  --management-ip   The ONTAP management address directly, skipping the Amazon FSx API:
                      aws fsx describe-file-systems --file-system-ids fs-... \
                        --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]'

  How to get the password, one of:
  --secret-id       Secrets Manager secret whose SecretString JSON has a "password" key.
  --password-stdin  Read the password from standard input.

Optional:
  --rehost-volume   Volume that rehost-probe.sh will move. Given here only so it receives the same
                    export policy, which is what makes a before-and-after comparison meaningful.
  --export-policy   Export policy name. Default: mpad_clients
  --share           SMB share name on the NTFS volume. Default: ntfsshare
  --unix-user       Local UNIX user name for the mapping. Default: derived from --ad-user
  --uid             UID for that user. Default: the UID sssd reports for --ad-user on this host,
                    or 90001 if it cannot be resolved.
  --gid             Primary GID. Default: 1000
  --unix-group      Local UNIX group name. Default: mpadgrp
  --region          AWS region. Defaults to AWS_REGION or AWS_DEFAULT_REGION.
  --check           Report the current state and exit without creating anything.

Why the UNIX identity and the name mappings are created here at all:

  NFSv4.1 with sec=sys carries numeric UIDs. For ONTAP to evaluate "the same Active Directory user"
  on the NFS side it has to turn that number into a name and then into a Windows identity. Two
  paths exist: an ONTAP LDAP client reading POSIX attributes from Active Directory, or explicit
  local entries. This script creates the explicit local entries for one user, because they work
  whether or not the directory publishes POSIX attributes and because a single explicit mapping is
  easier to reason about when a result is unexpected.

  If you want the LDAP path instead, configure it before running the measurement and say so in the
  record: the two paths can produce different UIDs for the same user, and a figure that does not
  name which one was in use cannot be compared with anything.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --file-system-id) FILE_SYSTEM_ID="$2"; shift 2 ;;
    --svm) SVM="$2"; shift 2 ;;
    --ntfs-volume) NTFS_VOLUME="$2"; shift 2 ;;
    --unix-volume) UNIX_VOLUME="$2"; shift 2 ;;
    --rehost-volume) REHOST_VOLUME="$2"; shift 2 ;;
    --export-policy) EXPORT_POLICY="$2"; shift 2 ;;
    --client-match) CLIENT_MATCH="$2"; shift 2 ;;
    --share) SHARE_NAME="$2"; shift 2 ;;
    --ad-user) AD_USER="$2"; shift 2 ;;
    --unix-user) UNIX_USER="$2"; shift 2 ;;
    --uid) UNIX_UID="$2"; shift 2 ;;
    --gid) UNIX_GID="$2"; shift 2 ;;
    --unix-group) UNIX_GROUP="$2"; shift 2 ;;
    --secret-id) SECRET_ID="$2"; shift 2 ;;
    --management-ip) MGMT_IP_ARG="$2"; shift 2 ;;
    --password-stdin) PASSWORD_STDIN="true"; shift ;;
    --region) REGION="$2"; shift 2 ;;
    --check) CHECK_ONLY="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "provision-multiprotocol: $*" >&2; exit 1; }

for tool in curl jq; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required but not installed"
done

[ -n "$SVM" ] || die "--svm is required"
[ -n "$NTFS_VOLUME" ] || die "--ntfs-volume is required"
[ -n "$UNIX_VOLUME" ] || die "--unix-volume is required"
[ -n "$CLIENT_MATCH" ] || die "--client-match is required"
[ -n "$AD_USER" ] || die "--ad-user is required"
[ -n "$FILE_SYSTEM_ID" ] || [ -n "$MGMT_IP_ARG" ] ||
  die "one of --file-system-id or --management-ip is required"
[ -n "$SECRET_ID" ] || [ "$PASSWORD_STDIN" = "true" ] ||
  die "one of --secret-id or --password-stdin is required"

if [ "$CLIENT_MATCH" = "0.0.0.0/0" ]; then
  die "--client-match 0.0.0.0/0 removes the export policy from what this measurement controls.
      Give the client subnet CIDR"
fi

if [ -z "$MGMT_IP_ARG" ] || { [ -n "$SECRET_ID" ] && [ "$PASSWORD_STDIN" != "true" ]; }; then
  command -v aws >/dev/null 2>&1 ||
    die "aws is required unless both --management-ip and --password-stdin are given"
  [ -n "$REGION" ] || die "--region is required (or set AWS_REGION)"
fi

# DOMAIN\user and user@domain both reduce to the same short name for the local UNIX account.
AD_SHORT_NAME="${AD_USER##*\\}"
AD_SHORT_NAME="${AD_SHORT_NAME%%@*}"
[ -n "$UNIX_USER" ] || UNIX_USER="$(printf '%s' "$AD_SHORT_NAME" | tr '[:upper:]' '[:lower:]' | tr -c '[:alnum:]_' '_')"
[ -n "$UNIX_GROUP" ] || UNIX_GROUP="mpadgrp"

if [ -z "$UNIX_UID" ]; then
  # Prefer the UID this host already resolves for the Active Directory user, so the mapping ONTAP
  # holds and the number the NFS client sends agree. Falling back to a fixed number is fine for the
  # measurement as long as the record says which of the two happened.
  UNIX_UID="$(id -u "$AD_USER" 2>/dev/null || true)"
  if [ -z "$UNIX_UID" ]; then
    UNIX_UID="$(id -u "$AD_SHORT_NAME" 2>/dev/null || true)"
  fi
  if [ -z "$UNIX_UID" ]; then
    UNIX_UID="90001"
    UID_SOURCE="fallback (this host does not resolve $AD_USER; record this)"
  else
    UID_SOURCE="resolved on this host with id(1)"
  fi
else
  UID_SOURCE="given with --uid"
fi

# ---------------------------------------------------------------- endpoint and credentials

if [ -n "$MGMT_IP_ARG" ]; then
  MGMT_IP="$MGMT_IP_ARG"
else
  MGMT_IP="$(aws fsx describe-file-systems \
    --file-system-ids "$FILE_SYSTEM_ID" --region "$REGION" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
    --output text 2>/dev/null || true)"
  if [ -z "$MGMT_IP" ] || [ "$MGMT_IP" = "None" ]; then
    die "could not resolve the management address for $FILE_SYSTEM_ID. If the call timed out, this
      host has no route to the Amazon FSx API; pass --management-ip instead"
  fi
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
# --insecure is required: the ONTAP management endpoint presents a self-signed certificate and
# Amazon FSx publishes no CA to pin against. The connection is to a private address inside the VPC.
#
# The password is escaped before it reaches curl's config parser, which ends a double-quoted value
# at the first unescaped quote and drops a lone backslash, both silently. Amazon FSx accepts both
# characters in an fsxadmin password, so the caller cannot be asked to avoid them.
curl_credential() {
  local escaped=${PASSWORD//\\/\\\\}
  escaped=${escaped//\"/\\\"}
  printf 'user = "fsxadmin:%s"' "$escaped"
}

# The HTTP status of the last ONTAP call. It is kept in a file, not in a variable, and that is
# not incidental: every call site captures the body with out="$(ontap ...)", and a command
# substitution runs the function in a SUBSHELL, so an assignment made inside ontap() never reaches
# the caller. Measured on 2026-09-12: the status arrived empty, the case fell through to the
# catch-all, and a response that was in fact HTTP 200 was reported as `failed: HTTP ` with no code.
# A status that silently reads as empty is worse than no status at all, because every check that
# consults it then reports the wrong cause.
ONTAP_STATUS_FILE="$(mktemp "${TMPDIR:-/tmp}/ontap-status-XXXXXX")"
trap 'rm -f "$ONTAP_STATUS_FILE"' EXIT

ontap_status() { cat "$ONTAP_STATUS_FILE" 2>/dev/null || true; }

# True when the last call returned 2xx.
ontap_2xx() { case "$(ontap_status)" in 2*) return 0 ;; *) return 1 ;; esac; }

ontap() {
  local method="$1" path="$2" body="${3:-}"
  local -a args=(--silent --show-error --insecure --max-time 60
    --user-agent 'fsxn-adoption-playbook/examples-multiprotocol-ad'
    --request "$method" "https://${MGMT_IP}/api${path}"
    --header 'content-type: application/json'
    --write-out '\n%{http_code}'
    --config /dev/fd/3)
  [ -n "$body" ] && args+=(--data "$body")
  local raw
  raw="$(curl "${args[@]}" 3<<<"$(curl_credential)")" || raw=$'\n000'
  printf '%s' "${raw##*$'\n'}" >"$ONTAP_STATUS_FILE"
  printf '%s' "${raw%$'\n'*}"
}

ontap_ok() {
  local out="$1" what="$2"
  case "$(ontap_status)" in
    2*) : ;;
    000) die "$what failed: no HTTP response from ${MGMT_IP} (check reachability on 443)" ;;
    401 | 403)
      die "$what failed: HTTP $(ontap_status) from ONTAP -- the fsxadmin credential was rejected"
      ;;
    *) die "$what failed: HTTP $(ontap_status) from ONTAP: $(printf '%s' "$out" | head -c 200)" ;;
  esac
  if printf '%s' "$out" | jq -e 'has("error")' >/dev/null 2>&1; then
    local msg
    msg="$(printf '%s' "$out" | jq -r '.error.message // "unknown error"')"
    die "$what failed: $msg"
  fi
}

count_of() { printf '%s' "$1" | jq -r '.num_records // 0'; }

# ---------------------------------------------------------------- preflight: is the SVM joined

# A CIFS server that is absent or disabled means the Active Directory join did not take, and every
# result after that point would be about the join rather than about the security style. The AWS API
# reports the same condition as a MISCONFIGURED lifecycle state, which the stack does not surface:
# CREATE_COMPLETE is reached either way.
cifs_json="$(ontap GET "/protocols/cifs/services?svm.name=${SVM}&fields=enabled,ad_domain.fqdn,name")"
ontap_ok "$cifs_json" "reading the CIFS server on $SVM"
if [ "$(count_of "$cifs_json")" -eq 0 ]; then
  die "no CIFS server on SVM $SVM. The Active Directory join did not complete. Check:
      aws fsx describe-storage-virtual-machines --query \
        'StorageVirtualMachines[].[Name,Lifecycle,LifecycleTransitionReason.Message]' --output table
      The two usual causes are an OrganizationalUnitDistinguishedName without the intermediate
      OU=Computers,OU=<ShortName> that AWS Managed Microsoft AD inserts, and a
      FileSystemAdministratorsGroup other than Domain Admins"
fi
cifs_enabled="$(printf '%s' "$cifs_json" | jq -r '.records[0].enabled // false')"
cifs_domain="$(printf '%s' "$cifs_json" | jq -r '.records[0].ad_domain.fqdn // "unknown"')"
cifs_netbios="$(printf '%s' "$cifs_json" | jq -r '.records[0].name // "unknown"')"

nfs_json="$(ontap GET "/protocols/nfs/services?svm.name=${SVM}\
&fields=enabled,protocol.v41_enabled,protocol.v41_features.acl_enabled,protocol.v4_id_domain,svm.uuid")"
ontap_ok "$nfs_json" "reading the NFS server on $SVM"
nfs_enabled="$(printf '%s' "$nfs_json" | jq -r '.records[0].enabled // false')"
nfs_v41="$(printf '%s' "$nfs_json" | jq -r '.records[0].protocol.v41_enabled // false')"
NFS_UUID="$(printf '%s' "$nfs_json" | jq -r '.records[0].svm.uuid // empty')"
nfs_v41_acl="$(printf '%s' "$nfs_json" | jq -r '.records[0].protocol.v41_features.acl_enabled // false')"
nfs_id_domain="$(printf '%s' "$nfs_json" | jq -r '.records[0].protocol.v4_id_domain // "-"')"

# ---------------------------------------------------------------- current state

policy_json="$(ontap GET "/protocols/nfs/export-policies?svm.name=${SVM}&name=${EXPORT_POLICY}&fields=id,name")"
ontap_ok "$policy_json" "reading export policies"
policy_count="$(count_of "$policy_json")"

share_json="$(ontap GET "/protocols/cifs/shares?svm.name=${SVM}&name=${SHARE_NAME}&fields=name,path")"
ontap_ok "$share_json" "reading SMB shares"
share_count="$(count_of "$share_json")"

group_json="$(ontap GET "/name-services/unix-groups?svm.name=${SVM}&name=${UNIX_GROUP}&fields=id,name")"
ontap_ok "$group_json" "reading UNIX groups"
group_count="$(count_of "$group_json")"

user_json="$(ontap GET "/name-services/unix-users?svm.name=${SVM}&name=${UNIX_USER}&fields=id,name,primary_gid")"
ontap_ok "$user_json" "reading UNIX users"
user_count="$(count_of "$user_json")"

echo "== preflight =="
printf 'management endpoint : %s\n' "$MGMT_IP"
printf 'SVM                 : %s\n' "$SVM"
printf 'CIFS server         : %s (NetBIOS %s, domain %s)\n' \
  "$([ "$cifs_enabled" = "true" ] && echo enabled || echo 'present but DISABLED')" \
  "$cifs_netbios" "$cifs_domain"
printf 'NFS server          : %s, v4.1 %s\n' \
  "$([ "$nfs_enabled" = "true" ] && echo enabled || echo disabled)" \
  "$([ "$nfs_v41" = "true" ] && echo enabled || echo 'DISABLED -- enable it before measuring')"
printf 'NFSv4 ACL           : %s\n' \
  "$([ "$nfs_v41_acl" = "true" ] && echo enabled || echo 'disabled (default) -- will be enabled below')"
printf 'NFSv4 id domain     : %s\n' "$nfs_id_domain"

echo
echo "== current state =="
printf 'export policy %-14s: %s\n' "$EXPORT_POLICY" "$([ "$policy_count" -gt 0 ] && echo present || echo absent)"
printf 'SMB share %-18s: %s\n' "$SHARE_NAME" "$([ "$share_count" -gt 0 ] && echo present || echo absent)"
printf 'UNIX group %-17s: %s\n' "$UNIX_GROUP" "$([ "$group_count" -gt 0 ] && echo present || echo absent)"
printf 'UNIX user %-18s: %s\n' "$UNIX_USER" "$([ "$user_count" -gt 0 ] && echo present || echo absent)"
printf 'AD user             : %s\n' "$AD_USER"
printf 'UID                 : %s (%s)\n' "$UNIX_UID" "$UID_SOURCE"

if [ "$CHECK_ONLY" = "true" ]; then
  echo "(--check given, nothing created)"
  exit 0
fi

if [ "$nfs_v41" != "true" ]; then
  die "NFSv4.1 is not enabled on $SVM. Enable it first, otherwise the mount falls back to a version
      this measurement is not about:
        PATCH /api/protocols/nfs/services/<svm.uuid>  {\"protocol\":{\"v41_enabled\":true}}"
fi

echo
echo "== reconciling =="

# ---------------------------------------------------------------- export policy and rule

if [ "$policy_count" -gt 0 ]; then
  policy_id="$(printf '%s' "$policy_json" | jq -r '.records[0].id')"
  echo "policy : exists, left alone"
else
  out="$(ontap POST /protocols/nfs/export-policies "$(jq -nc \
    --arg svm "$SVM" --arg name "$EXPORT_POLICY" \
    '{svm:{name:$svm}, name:$name}')")"
  ontap_ok "$out" "creating export policy $EXPORT_POLICY"
  policy_json="$(ontap GET "/protocols/nfs/export-policies?svm.name=${SVM}&name=${EXPORT_POLICY}&fields=id")"
  ontap_ok "$policy_json" "re-reading export policy $EXPORT_POLICY"
  policy_id="$(printf '%s' "$policy_json" | jq -r '.records[0].id')"
  echo "policy : created $EXPORT_POLICY"
fi

rule_json="$(ontap GET "/protocols/nfs/export-policies/${policy_id}/rules?fields=index,clients,protocols,rw_rule,ro_rule,superuser")"
ontap_ok "$rule_json" "reading export policy rules"
if printf '%s' "$rule_json" | jq -e --arg m "$CLIENT_MATCH" \
    '[.records[]?.clients[]?.match] | index($m) != null' >/dev/null 2>&1; then
  echo "rule   : a rule for $CLIENT_MATCH already exists, left alone"
else
  # superuser is sys rather than none deliberately. With superuser none, root on the client is
  # squashed to anonymous, and a permission denial then cannot be told apart from root squashing.
  # The measurement is run as an ordinary Active Directory user in any case.
  out="$(ontap POST "/protocols/nfs/export-policies/${policy_id}/rules" "$(jq -nc \
    --arg m "$CLIENT_MATCH" \
    '{clients:[{match:$m}], protocols:["nfs4"], rw_rule:["sys"], ro_rule:["sys"],
      superuser:["sys"], anonymous_user:"65534"}')")"
  ontap_ok "$out" "adding an export rule for $CLIENT_MATCH"
  echo "rule   : added nfs4 rw/ro sys for $CLIENT_MATCH"
fi

# ---------------------------------------------------------------- apply the policy to the volumes

for vol in "$NTFS_VOLUME" "$UNIX_VOLUME" ${REHOST_VOLUME:+"$REHOST_VOLUME"}; do
  vol_json="$(ontap GET "/storage/volumes?svm.name=${SVM}&name=${vol}&fields=uuid,nas.export_policy.name,nas.security_style,nas.path")"
  ontap_ok "$vol_json" "reading volume $vol"
  if [ "$(count_of "$vol_json")" -eq 0 ]; then
    die "volume $vol not found on SVM $SVM"
  fi
  vol_uuid="$(printf '%s' "$vol_json" | jq -r '.records[0].uuid')"
  vol_policy="$(printf '%s' "$vol_json" | jq -r '.records[0].nas.export_policy.name // "none"')"
  vol_style="$(printf '%s' "$vol_json" | jq -r '.records[0].nas.security_style // "unknown"')"
  # The junction path is read, never derived from the volume name. They coincide often enough to
  # look like a rule and they are unrelated: measured on 2026-09-12, volume fsxnmpadntfsvol was
  # mounted at /ntfsvol, and building the share path as /<volume-name> produced
  #   HTTP 400, code 655551: The specified path "/fsxnmpadntfsvol" does not exist in the namespace
  # which reads as a missing volume rather than as a wrong assumption about its name.
  if [ "$vol" = "$NTFS_VOLUME" ]; then
    NTFS_JUNCTION="$(printf '%s' "$vol_json" | jq -r '.records[0].nas.path // ""')"
    [ -n "$NTFS_JUNCTION" ] ||
      die "volume $vol has no junction path, so it is not mounted in the namespace and neither an
      SMB share nor an NFS mount can reach it"
  fi
  if [ "$vol_policy" = "$EXPORT_POLICY" ]; then
    printf 'volume : %-24s already uses %s (style %s)\n' "$vol" "$EXPORT_POLICY" "$vol_style"
  else
    out="$(ontap PATCH "/storage/volumes/${vol_uuid}" "$(jq -nc \
      --arg p "$EXPORT_POLICY" '{nas:{export_policy:{name:$p}}}')")"
    ontap_ok "$out" "applying $EXPORT_POLICY to $vol"
    printf 'volume : %-24s now uses %s (style %s)\n' "$vol" "$EXPORT_POLICY" "$vol_style"
  fi
done

# ---------------------------------------------------------------- NFSv4 ACL visibility
#
# Without this, part 2 of the record -- what the NFS side shows -- cannot be collected at all:
# nfs4_getfacl answers "Operation to request attribute not supported". Both v4.0 and v4.1 ACL
# support are DISABLED by default on an FSx for ONTAP SVM. Measured on ONTAP 9.18.1P6, 2026-09-12,
# where acl_enabled was false on a freshly created SVM, on the UNIX-style volume as well as the
# NTFS-style one -- so it is not a property of the security style.
#
# Turning it on does not change the access decision. On an NTFS-style volume the decision is made
# from the Windows ACL either way; this only controls whether the client may READ a representation
# of it. That distinction is the whole point of the measurement, so the representation has to be
# obtainable before the measurement means anything.

if [ "$nfs_v41_acl" = "true" ]; then
  echo "nfsacl : already enabled, left alone"
elif [ -z "$NFS_UUID" ]; then
  echo "nfsacl : could not determine the NFS service UUID, left alone" >&2
else
  out="$(ontap PATCH "/protocols/nfs/services/${NFS_UUID}" \
    '{"protocol":{"v40_features":{"acl_enabled":true},"v41_features":{"acl_enabled":true}}}')"
  ontap_ok "$out" "enabling NFSv4 ACL support on $SVM"
  echo "nfsacl : enabled for v4.0 and v4.1"
  # An already-established mount keeps the capability set it negotiated, so it will keep answering
  # "not supported" until it is remounted. Saying so here is cheaper than the reader concluding the
  # PATCH did not work.
  echo "         REMOUNT any existing NFS mount, or it will still report the attribute unsupported"
fi

# ---------------------------------------------------------------- SMB share

if [ "$share_count" -gt 0 ]; then
  echo "share  : exists, left alone"
else
  out="$(ontap POST /protocols/cifs/shares "$(jq -nc \
    --arg svm "$SVM" --arg name "$SHARE_NAME" --arg path "$NTFS_JUNCTION" \
    '{svm:{name:$svm}, name:$name, path:$path}')")"
  ontap_ok "$out" "creating SMB share $SHARE_NAME"
  echo "share  : created $SHARE_NAME on $NTFS_JUNCTION"
fi

# ---------------------------------------------------------------- UNIX identity

if [ "$group_count" -gt 0 ]; then
  echo "group  : exists, left alone"
else
  out="$(ontap POST /name-services/unix-groups "$(jq -nc \
    --arg svm "$SVM" --arg name "$UNIX_GROUP" --argjson id "$UNIX_GID" \
    '{svm:{name:$svm}, name:$name, id:$id}')")"
  ontap_ok "$out" "creating UNIX group $UNIX_GROUP"
  echo "group  : created $UNIX_GROUP (gid $UNIX_GID)"
fi

if [ "$user_count" -gt 0 ]; then
  existing_uid="$(printf '%s' "$user_json" | jq -r '.records[0].id')"
  echo "user   : exists, left alone (uid $existing_uid)"
  if [ "$existing_uid" != "$UNIX_UID" ]; then
    echo "         WARNING: ONTAP holds uid $existing_uid, this run derived $UNIX_UID."
    echo "         The NFS client sends a number. If the two disagree, the mapping does not apply"
    echo "         and the result is about the mismatch, not about the security style."
  fi
else
  out="$(ontap POST /name-services/unix-users "$(jq -nc \
    --arg svm "$SVM" --arg name "$UNIX_USER" \
    --argjson id "$UNIX_UID" --argjson gid "$UNIX_GID" \
    '{svm:{name:$svm}, name:$name, id:$id, primary_gid:$gid}')")"
  ontap_ok "$out" "creating UNIX user $UNIX_USER"
  echo "user   : created $UNIX_USER (uid $UNIX_UID, gid $UNIX_GID)"
fi

# ---------------------------------------------------------------- name mappings

# Two directions, both needed for different reasons.
#
#   win_unix : consulted when a Windows identity has to be evaluated against UNIX permissions. On an
#              NTFS-style volume it is NOT consulted for the access decision, which is the finding
#              this environment exists to reproduce - it is created here so the UNIX-style control
#              volume has the mapping it does need.
#   unix_win : consulted when the numeric UID arriving over NFS has to be evaluated against an NTFS
#              ACL. This is the direction that carries the measurement on the NTFS volume.
add_mapping() {
  local direction="$1" pattern="$2" replacement="$3"
  local existing
  existing="$(ontap GET "/name-services/name-mappings?svm.name=${SVM}&direction=${direction}&fields=index,pattern,replacement")"
  ontap_ok "$existing" "reading $direction name mappings"
  if printf '%s' "$existing" | jq -e --arg r "$replacement" \
      '[.records[]?.replacement] | index($r) != null' >/dev/null 2>&1; then
    printf 'map    : %-8s -> %s already present\n' "$direction" "$replacement"
    return
  fi
  # index 1 puts the rule first. ONTAP evaluates name mappings in index order and stops at the first
  # match, so appending a rule behind an existing catch-all would leave it unreachable.
  local out
  out="$(ontap POST /name-services/name-mappings "$(jq -nc \
    --arg svm "$SVM" --arg d "$direction" --arg p "$pattern" --arg r "$replacement" \
    '{svm:{name:$svm}, direction:$d, index:1, pattern:$p, replacement:$r}')")"
  ontap_ok "$out" "creating $direction mapping $pattern -> $replacement"
  printf 'map    : %-8s -> %s created\n' "$direction" "$replacement"
}

# The pattern is anchored on the short name so it matches regardless of which form the client sends.
add_mapping win_unix "${AD_SHORT_NAME}" "$UNIX_USER"

# THE BACKSLASH IN THE REPLACEMENT MUST BE DOUBLED.
#
# ONTAP treats \ as an escape character inside a name-mapping replacement, so a replacement stored as
# DOMAIN\user is read back as DOMAINuser -- the separator is swallowed and the two names are joined.
# Nothing rejects it. The rule is created, it matches, and the mapping reports success; the *lookup*
# of the resulting name is what fails, so the error names Active Directory rather than the rule.
#
# Measured on ONTAP 9.18.1P6 in ap-northeast-1 on 2026-09-12. Sending MPAD\mpadtest produced, in
# secd.nfsAuth.noNameMap:
#     Determined UNIX id 675401149 is UNIX user 'mpadtest'
#     Mapping Successful for Unix-user 'mpadtest' to Windows user 'MPADmpadtest' at position 1
#     Could not find Windows name 'MPADmpadtest'
#     FAILURE: Name mapping for UNIX user 'mpadtest' failed
# and every NFS access to the NTFS-style volume returned EACCES -- including opendir, so even `ls`
# failed. Read from the client that looks like an export-policy problem; the export policy was fine.
# The GET readback is no help either: it returns the single backslash that was stored, which looks
# exactly like what was intended.
#
# jq --arg takes these characters literally, so the two backslashes here are what reaches ONTAP.
add_mapping unix_win "$UNIX_USER" "${AD_USER/\\/\\\\}"

# ---------------------------------------------------------------- result

echo
echo "== result =="
final_vols="$(ontap GET "/storage/volumes?svm.name=${SVM}&fields=name,nas.security_style,nas.path,nas.export_policy.name")"
ontap_ok "$final_vols" "reading the finished volumes"
printf '%s' "$final_vols" | jq -r '.records[] |
  "\(.name)\t\(.nas.security_style // "-")\t\(.nas.path // "unmounted")\t\(.nas.export_policy.name // "-")"' |
  { printf 'volume\tstyle\tjunction\texport policy\n'; cat; } |
  column -t -s "$(printf '\t')"

cat <<NEXT

Next, in this order:

  1. Mount both volumes on this host and create the tree. Confirm the mount FIRST -- a refused
     mount leaves the directories on local disk, where ls looks entirely correct:
       mountpoint -q /mnt/ntfsvol || echo REFUSING
     On the NTFS volume create it as ${AD_USER}, not as root: root has no unix_win mapping, so
     ONTAP cannot evaluate it and even mkdir fails.

  2. Set the ACEs with set-test-acls.sh, from THIS host, through the ONTAP REST API. No SMB client
     is involved. That writes the "ACE as set" part of the record.
     set-test-acls.ps1 is optional and only compares an SMB-side path against the storage-side one.

  3. Create ${NTFS_JUNCTION:-/<junction>}/inherited/child AFTER step 2, so its ACE arrives by
     inheritance rather than by being set.

  4. Run read-effective-permissions.sh for both ${NTFS_VOLUME} and ${UNIX_VOLUME}.
     It records what the NFS side sees and whether the access actually succeeded. Run it as
     ${AD_USER}, not as root and not as a member of the administrators group. Remount first if the
     NFSv4 ACL was only just enabled above.

  5. Only after the record is complete: rehost-probe.sh. It is disruptive and may leave the
     CloudFormation stack unable to delete ${REHOST_VOLUME:-the rehost volume}.

A result is only usable if all three parts of the record are present: the ACE that was set, the
representation the NFS side showed, and whether the access succeeded. Two out of three is not a
finding.
NEXT
