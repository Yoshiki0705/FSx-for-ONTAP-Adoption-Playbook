#!/usr/bin/env bash
#
# Set the three kinds of NTFS ACE the multiprotocol measurement needs, at the storage layer, and
# record them. This writes the first of the three parts of the record; read-effective-permissions.sh
# writes the other two.
#
# WHY THIS IS NOT A WINDOWS SCRIPT
#
# The first version of this example set the ACEs from a domain-joined Windows client over SMB. That
# was an assumption, not a requirement. NetApp documents the opposite: the ONTAP REST API can manage
# NTFS file security "without the need of a client. It works similar to what you could do with a
# cacls in windows client".
#   https://docs.netapp.com/us-en/ontap-restapi-991/manage_file_security_permissions_and_audit_policies.html
#
# AWS documents the same mechanism as the recommended way to manage NTFS permissions on
# FSx for ONTAP, describing it as operating "at the storage layer rather than through client-side
# tools", with the client-side approach called out as slow over SMB and error-prone at scale:
#   https://aws.amazon.com/blogs/storage/manage-ntfs-permissions-at-scale-on-amazon-fsx-for-netapp-ontap/
#
# NetApp also publishes the REST-to-CLI mapping, which is why one call here replaces six CLI commands
# (ntfs create, dacl add, sacl add, policy create, policy task add, apply):
#   https://docs.netapp.com/us-en/ontap-automation/workflows/wf_nas_fs_prepare.html
#
# For this measurement the storage-layer path is also the more honest one: it sets the DACL mask
# explicitly, so the record says exactly which rights were requested rather than whatever an SMB
# client chose to translate "Modify" into.
#
# WHAT IS STILL A WINDOWS JOB
#
# Creating the Active Directory test user. AWS documents no API for it - the documented path is the
# Active Directory Administration Tools and PowerShell on a domain-joined instance:
#   https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_manage_users_groups_create_user.html
# So the Windows client in this example exists for that, and for the optional comparison run where an
# SMB client sets the same ACEs. It is not on the critical path for the ACEs themselves.
#
# Requires: curl, jq, and aws unless both --management-ip and --password-stdin are given.
# ONTAP 9.9.1 or later: that is when the REST API gained SACL and DACL management.

set -euo pipefail

FILE_SYSTEM_ID=""
SVM=""
VOLUME=""
AD_USER=""
SECRET_ID=""
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
MGMT_IP_ARG=""
PASSWORD_STDIN="false"
OUT=""
CHECK_ONLY="false"
ADMIN_GROUP="Domain Admins"

usage() {
  cat <<'USAGE'
Usage: set-test-acls.sh (--file-system-id fs-... | --management-ip IP)
                        --svm NAME --volume NAME --ad-user 'DOMAIN\user'
                        (--secret-id NAME_OR_ARN | --password-stdin)
                        [--region REGION] [--out FILE] [--check]

Required:
  --svm         SVM owning the volume. Output SourceSvmName of the stack.
  --volume      The NTFS-security-style volume. Output NtfsVolumeName. The junction path is read
                from ONTAP rather than assumed, so a volume mounted somewhere else still works.
  --ad-user     The Active Directory test user the ACEs apply to, as DOMAIN\user. It must NOT be a
                member of the file system administrators group: members of that group bypass the
                evaluation being measured, and every access then succeeds.

Optional:
  --out         Write the JSON record here instead of stdout.
  --check       Read and report the current DACLs. Creates and changes nothing.
  --admin-group Group whose membership would invalidate the test. Default: Domain Admins

What gets created, and why each one:

  allow/            One Allow ACE, not inheritable. Mode bits can express this, so it is the
                    baseline that is expected to survive translation to NFS.
  deny/             Allow read-and-execute AND an explicit Deny write, on the same directory. POSIX
                    mode bits cannot express a deny at all; an NFSv4 ACL can. Pairing them is what
                    makes a loss visible - if the NFS side shows the read but not the denial, the
                    denial did not survive.
  inherited/        One Allow ACE with apply_to = this_folder + sub_folders + files. That is the
                    REST spelling of the OI|CI inheritance flags AWS documents. The child directory
                    is created afterwards so its ACE arrives by inheritance rather than by being set.

A gotcha this script checks for, from the AWS post above: ONTAP adds four default Windows security
groups to a new security descriptor - BUILTIN\Administrators, BUILTIN\Users, CREATOR OWNER and
NT AUTHORITY\SYSTEM. BUILTIN\Users granting read would make every read succeed regardless of the
ACEs under test, which is a false pass. The script reports whichever of them it finds after
applying, so the record shows what else was in the DACL. It does not remove them: AWS documents for
FSx for Windows File Server that SYSTEM needs full control and that removing it can make a share
inaccessible and backups unusable, and that warning is not worth testing here.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --file-system-id) FILE_SYSTEM_ID="$2"; shift 2 ;;
    --svm) SVM="$2"; shift 2 ;;
    --volume) VOLUME="$2"; shift 2 ;;
    --ad-user) AD_USER="$2"; shift 2 ;;
    --secret-id) SECRET_ID="$2"; shift 2 ;;
    --management-ip) MGMT_IP_ARG="$2"; shift 2 ;;
    --password-stdin) PASSWORD_STDIN="true"; shift ;;
    --region) REGION="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --admin-group) ADMIN_GROUP="$2"; shift 2 ;;
    --check) CHECK_ONLY="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "set-test-acls: $*" >&2; exit 1; }

for tool in curl jq; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required but not installed"
done

[ -n "$SVM" ] || die "--svm is required"
[ -n "$VOLUME" ] || die "--volume is required"
[ -n "$AD_USER" ] || die "--ad-user is required"
[ -n "$FILE_SYSTEM_ID" ] || [ -n "$MGMT_IP_ARG" ] ||
  die "one of --file-system-id or --management-ip is required"
[ -n "$SECRET_ID" ] || [ "$PASSWORD_STDIN" = "true" ] ||
  die "one of --secret-id or --password-stdin is required"

if [ -z "$MGMT_IP_ARG" ] || { [ -n "$SECRET_ID" ] && [ "$PASSWORD_STDIN" != "true" ]; }; then
  command -v aws >/dev/null 2>&1 ||
    die "aws is required unless both --management-ip and --password-stdin are given"
  [ -n "$REGION" ] || die "--region is required (or set AWS_REGION)"
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
    die "could not resolve the management address for $FILE_SYSTEM_ID; pass --management-ip instead"
  fi
fi

if [ "$PASSWORD_STDIN" = "true" ]; then
  IFS= read -r PASSWORD || true
  [ -n "$PASSWORD" ] || die "no password on standard input"
else
  PASSWORD="$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_ID" --region "$REGION" \
    --query SecretString --output text 2>/dev/null | jq -r '.password // empty')"
  [ -n "$PASSWORD" ] || die "secret $SECRET_ID has no \"password\" key in its SecretString"
fi

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
  local -a args=(--silent --show-error --insecure --max-time 120
    --user-agent 'fsxn-adoption-playbook/examples-multiprotocol-ad'
    --request "$method" "https://${MGMT_IP}/api${path}"
    --header 'content-type: application/json'
    --write-out '\n%{http_code}'
    --config /dev/fd/3)
  [ -n "$body" ] && args+=(--data "$body")
  local raw
  raw="$(curl "${args[@]}" 3<<<"$(curl_credential)")" || raw=$'\n000'
  printf '%s' "${raw##*$'\n'}" >"$ONTAP_STATUS_FILE"
  # ONTAP job messages carry unescaped control characters; jq rejects them and the failure then looks
  # like a JSON problem rather than an operation problem.
  printf '%s' "${raw%$'\n'*}" | tr -d '\000-\010\013\014\016-\037'
}

ontap_ok() {
  local out="$1" what="$2"
  case "$(ontap_status)" in
    2*) : ;;
    000) die "$what failed: no HTTP response from ${MGMT_IP} (check reachability on 443)" ;;
    401 | 403) die "$what failed: HTTP $(ontap_status) -- the fsxadmin credential was rejected" ;;
    *) die "$what failed: HTTP $(ontap_status): $(printf '%s' "$out" | head -c 300)" ;;
  esac
  if printf '%s' "$out" | jq -e 'has("error")' >/dev/null 2>&1; then
    die "$what failed: $(printf '%s' "$out" | jq -r '.error.message // "unknown error"')"
  fi
}

wait_job() {
  local job="$1" what="$2"
  [ -n "$job" ] || return 0
  for _ in $(seq 1 40); do
    local j js
    j="$(ontap GET "/cluster/jobs/${job}?fields=state,message")"
    ontap_ok "$j" "reading job $job"
    js="$(jq -r '.state // "unknown"' <<<"$j")"
    case "$js" in
      success) return 0 ;;
      failure) die "$what failed: $(jq -r '.message // "no message"' <<<"$j")" ;;
    esac
    sleep 5
  done
  die "$what did not finish within 200 seconds"
}

# ---------------------------------------------------------------- preflight

CLUSTER="$(ontap GET "/cluster?fields=version.full")"
ontap_ok "$CLUSTER" "reading the cluster version"
ONTAP_VERSION="$(jq -r '.version.full // "unknown"' <<<"$CLUSTER")"

SVM_JSON="$(ontap GET "/svm/svms?name=${SVM}&fields=uuid,name,cifs.enabled")"
ontap_ok "$SVM_JSON" "reading SVM $SVM"
[ "$(jq -r '.num_records // 0' <<<"$SVM_JSON")" -gt 0 ] || die "SVM $SVM not found"
SVM_UUID="$(jq -r '.records[0].uuid' <<<"$SVM_JSON")"

# An SVM with a configured CIFS server but no discovered domain controller cannot authenticate any
# domain user, so an ACE naming one would be unresolvable. Measured on an unrelated file system in
# the same account on 2026-09-11: three SVMs reported cifs enabled=true with the domain FQDN set,
# the AWS API reported Lifecycle=CREATED, and ONTAP had discovered zero domain controllers. Three
# signals said healthy. The DC count is the one that was telling the truth.
DOM_JSON="$(ontap GET "/protocols/cifs/domains?svm.uuid=${SVM_UUID}&fields=**")"
ontap_ok "$DOM_JSON" "reading the CIFS domain state of $SVM"
DC_TOTAL="$(jq -r '[.records[]?.discovered_servers[]?] | length' <<<"$DOM_JSON")"
DC_OK="$(jq -r '[.records[]?.discovered_servers[]? | select((.state // .status // "") == "ok")] | length' <<<"$DOM_JSON")"
if [ "${DC_OK:-0}" -eq 0 ]; then
  die "SVM $SVM has $DC_TOTAL discovered domain controller(s) and none in state ok. No domain user
      can be authenticated, so an ACE naming $AD_USER would not resolve. Do not read
      cifs.enabled=true or Lifecycle=CREATED as evidence that the join works"
fi

VOL_JSON="$(ontap GET "/storage/volumes?svm.uuid=${SVM_UUID}&name=${VOLUME}&fields=uuid,name,nas.path,nas.security_style")"
ontap_ok "$VOL_JSON" "reading volume $VOLUME"
[ "$(jq -r '.num_records // 0' <<<"$VOL_JSON")" -gt 0 ] || die "volume $VOLUME not found on $SVM"
JUNCTION="$(jq -r '.records[0].nas.path // empty' <<<"$VOL_JSON")"
STYLE="$(jq -r '.records[0].nas.security_style // "unknown"' <<<"$VOL_JSON")"
[ -n "$JUNCTION" ] || die "volume $VOLUME is not mounted; the file-security API takes a path in the
      SVM namespace, so the volume needs a junction path"
[ "$STYLE" = "ntfs" ] || die "volume $VOLUME has security style '$STYLE'. This script sets NTFS
      ACEs, which only govern the access decision on an ntfs-style volume. Point it at the NTFS
      volume and use the unix one as the control"

echo "== target =="
printf 'ONTAP version : %s\n' "$ONTAP_VERSION"
printf 'SVM           : %s (%s)\n' "$SVM" "$SVM_UUID"
printf 'volume        : %s at %s, style %s\n' "$VOLUME" "$JUNCTION" "$STYLE"
printf 'domain ctrls  : %s discovered, %s in state ok\n' "$DC_TOTAL" "$DC_OK"
printf 'test user     : %s\n' "$AD_USER"
printf 'admin group   : %s (membership would invalidate the measurement)\n' "$ADMIN_GROUP"

# ---------------------------------------------------------------- helpers

# The path in the URL is relative to the SVM root volume and has to be percent-encoded.
enc() { printf '%s' "$1" | jq -sRr @uri; }

read_sd() {
  local p="$1"
  ontap GET "/protocols/file-security/permissions/${SVM_UUID}/$(enc "$p")"
}

show_dacl() {
  local label="$1" p="$2" sd
  sd="$(read_sd "$p")"
  if ! ontap_2xx; then
    printf '  %-22s (no security descriptor: HTTP %s)\n' "$label" "$(ontap_status)"
    return
  fi
  printf '  %-22s owner=%s\n' "$label" "$(jq -r '.owner // "-"' <<<"$sd")"
  # The readback reports advanced_rights, never rights, even when the ACE was SET with
  # rights: "modify". ONTAP expands the shorthand into the individual bits and returns only the
  # expanded form, so a projection that reads .rights prints an empty column and the record then
  # says nothing about what was granted. Measured on ONTAP 9.18.1P6, 2026-09-12.
  jq -r '.acls[]? |
    "      \(.access)  \(.user)  rights=" +
    ((.rights // (.advanced_rights | if . == null then null else
        (if .full_control then ["full_control"] else
          [to_entries[] | select(.value == true) | .key] end | join(","))
      end)) // "-") + "  " +
    "apply_to=" + ([(if .apply_to.this_folder then "this_folder" else empty end),
                    (if .apply_to.sub_folders then "sub_folders" else empty end),
                    (if .apply_to.files then "files" else empty end)] | join("+") // "-") +
    (if .inherited then "  (inherited)" else "" end)' <<<"$sd"
}

if [ "$CHECK_ONLY" = "true" ]; then
  echo
  echo "== current DACLs (--check, nothing changed) =="
  for sub in "" /allow /deny /inherited /inherited/child; do
    show_dacl "${JUNCTION}${sub}" "${JUNCTION}${sub}"
  done
  exit 0
fi

# ---------------------------------------------------------------- create the tree
#
# Directories are created over NFS, not by this script: the file-security API applies a descriptor to
# an existing path and does not create one. The stack's Linux client has the volume exported, so
# create them there first. Kept as an explicit instruction rather than a silent dependency.

for sub in /allow /deny /inherited; do
  sd="$(read_sd "${JUNCTION}${sub}")"
  if ! ontap_2xx; then
    die "path ${JUNCTION}${sub} does not exist yet (HTTP $(ontap_status)). Create the tree first from
        a client that has the volume mounted, for example on the Linux client:
          sudo mkdir -p /mnt/ntfsvol/{allow,deny,inherited}
          sudo sh -c 'for d in allow deny inherited; do
            echo probe > /mnt/ntfsvol/\$d/probe.txt; done'
        The file-security API applies a descriptor to an existing path; it does not create paths"
  fi
done

echo
echo "== applying security descriptors =="

apply_sd() {
  local label="$1" p="$2" body="$3" out job
  out="$(ontap POST "/protocols/file-security/permissions/${SVM_UUID}/$(enc "$p")" "$body")"
  ontap_ok "$out" "applying the descriptor for $label"
  job="$(jq -r '.job.uuid // empty' <<<"$out")"
  wait_job "$job" "the apply job for $label"
  printf '  %-22s applied\n' "$label"
}

# The POST body carries no security_style. The GET response for this same endpoint DOES return
# security_style and effective_style, which makes it look like a field of the resource; sending it
# back is rejected with
#   HTTP 400, code 262196: Field "security_style" cannot be set in this operation
# Measured on ONTAP 9.18.1P6, 2026-09-12. Same code as a rehost PATCH that carries svm.name, so
# 262196 means "this field is readable but not writable here", not "this field is wrong".
# 1. allow -- a plain Allow ACE, not inheritable. apply_to is this_folder only.
apply_sd "allow" "${JUNCTION}/allow" "$(jq -nc --arg u "$AD_USER" '{
  access_control: "file_directory",
  acls: [
    {access: "access_allow", user: $u, rights: "modify",
     apply_to: {this_folder: true, sub_folders: false, files: false}}
  ]
}')"

# 2. deny -- Allow read-and-execute plus an explicit Deny write, on the same directory. A bare Deny
#    would be indistinguishable from no ACE at all when read as mode bits, so the pairing is what
#    makes the loss visible.
apply_sd "deny" "${JUNCTION}/deny" "$(jq -nc --arg u "$AD_USER" '{
  access_control: "file_directory",
  acls: [
    {access: "access_allow", user: $u, rights: "read",
     apply_to: {this_folder: true, sub_folders: false, files: false}},
    {access: "access_deny", user: $u, rights: "write",
     apply_to: {this_folder: true, sub_folders: false, files: false}}
  ]
}')"

# 3. inherited -- this_folder + sub_folders + files is the REST spelling of OI|CI. propagation_mode
#    propagate pushes inheritable permissions down; replace would overwrite what is already there,
#    which is a different operation and not what is being measured.
apply_sd "inherited" "${JUNCTION}/inherited" "$(jq -nc --arg u "$AD_USER" '{
  access_control: "file_directory",
  propagation_mode: "propagate",
  acls: [
    {access: "access_allow", user: $u, rights: "modify",
     apply_to: {this_folder: true, sub_folders: true, files: true}}
  ]
}')"

echo
echo "  Now create ${JUNCTION}/inherited/child from a client, AFTER this point, so its ACE arrives"
echo "  by inheritance rather than by being set:  sudo mkdir /mnt/ntfsvol/inherited/child"

# ---------------------------------------------------------------- read back

echo
echo "== DACLs as ONTAP now reports them =="
for sub in /allow /deny /inherited /inherited/child; do
  show_dacl "${JUNCTION}${sub}" "${JUNCTION}${sub}"
done

# The four groups ONTAP adds by default. BUILTIN\Users granting read would make every read succeed
# regardless of the ACEs under test, which is a false pass, so the record has to name whichever are
# present. They are reported, not removed: AWS documents that removing SYSTEM's full control can make
# a share inaccessible and backups unusable.
echo
echo "== other principals in the DACLs (a false-pass risk, reported not removed) =="
for sub in /allow /deny /inherited; do
  sd="$(read_sd "${JUNCTION}${sub}")"
  others="$(jq -r --arg u "$AD_USER" '[.acls[]? | select(.user != $u) | .user] | unique | join(", ")' <<<"$sd" 2>/dev/null || true)"
  printf '  %-22s %s\n' "${JUNCTION}${sub}" "${others:-none}"
done

# ---------------------------------------------------------------- ONTAP's own verdict

# A third signal, independent of both the DACL text and of what the NFS client sees:
# GET /protocols/file-security/effective-permissions/ reports what ONTAP would actually grant the
# named user. It accepts a Windows or a UNIX user.
echo
echo "== ONTAP's effective permissions for the test user =="
EFF="[]"
for sub in /allow /deny /inherited /inherited/child; do
  e="$(ontap GET "/protocols/file-security/effective-permissions/${SVM_UUID}/$(enc "${JUNCTION}${sub}")?user=$(enc "$AD_USER")")"
  if ontap_2xx; then
    # file_permissions and share_permissions are ARRAYS and both names are plural. The singular
    # forms read as null and print "-", which looks like "ONTAP granted nothing" rather than like a
    # wrong field name -- the most misleading way for this signal to fail. Measured 2026-09-12.
    printf '  %-22s %s\n' "${JUNCTION}${sub}" \
      "$(jq -c '{file: (.file_permissions // ["-"]), share: (.share_permissions // ["-"])}' <<<"$e")"
    EFF="$(jq -c --arg p "${JUNCTION}${sub}" --argjson e "$e" '. + [{path:$p, effective:$e}]' <<<"$EFF")"
  else
    printf '  %-22s (HTTP %s)\n' "${JUNCTION}${sub}" "$(ontap_status)"
    EFF="$(jq -c --arg p "${JUNCTION}${sub}" --arg s "$(ontap_status)" '. + [{path:$p, error:("HTTP "+$s)}]' <<<"$EFF")"
  fi
done

# ---------------------------------------------------------------- record

SUBJECTS="[]"
for sub in /allow /deny /inherited /inherited/child; do
  sd="$(read_sd "${JUNCTION}${sub}")"
  if ontap_2xx; then
    SUBJECTS="$(jq -c --arg p "${JUNCTION}${sub}" --argjson sd "$sd" '. + [{path:$p, sd:$sd}]' <<<"$SUBJECTS")"
  else
    SUBJECTS="$(jq -c --arg p "${JUNCTION}${sub}" --arg s "$(ontap_status)" '. + [{path:$p, error:("HTTP "+$s)}]' <<<"$SUBJECTS")"
  fi
done

RECORD="$(jq -n \
  --arg part "ace-as-set" \
  --arg how "ONTAP REST POST /protocols/file-security/permissions (storage layer, no SMB client)" \
  --arg svm "$SVM" --arg vol "$VOLUME" --arg junction "$JUNCTION" --arg style "$STYLE" \
  --arg user "$AD_USER" --arg ontap "$ONTAP_VERSION" --arg region "${REGION:-not recorded}" \
  --arg when "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg dcs "$DC_OK" \
  --argjson subjects "$SUBJECTS" --argjson effective "$EFF" \
  '{part:$part, set_via:$how,
    environment:{svm:$svm, volume:$vol, junction:$junction, security_style:$style,
                 ontap_version:$ontap, region:$region, recorded_at_utc:$when,
                 domain_controllers_ok:($dcs|tonumber)},
    ad_user:$user,
    subjects:$subjects,
    ontap_effective_permissions:$effective,
    reminder:"One of three parts. Pair it with the NFS-side record from read-effective-permissions.sh, run as an ordinary Active Directory user."}')"

if [ -n "$OUT" ]; then
  printf '%s\n' "$RECORD" >"$OUT"
  echo
  echo "record written to $OUT"
else
  echo
  printf '%s\n' "$RECORD"
fi
