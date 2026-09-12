#!/usr/bin/env bash
#
# Measure what `volume rehost` changes and what it leaves alone, by recording the volume on both
# sides of the move.
#
# Two questions are open in the public documentation and this script exists to close them:
#
#   1. Does the volume keep its security style when it moves into an SVM whose root volume has a
#      different one? The documentation lists seven categories of configuration that are lost and
#      does not mention the security style. That silence is not evidence either way, so it has to be
#      measured rather than inferred.
#
#   2. Does the AWS control plane follow the ownership change? The Amazon FSx API ties a volume to an
#      SVM through StorageVirtualMachineId. If that field does not move, the two control planes now
#      disagree about the same volume, and a volume in that state may become undeletable from one
#      side. The same asymmetry has already been observed for volumes that carried an S3 access
#      point, where ONTAP refuses the delete and the Amazon FSx API accepts it.
#
# rehost is DISRUPTIVE to data access and to volume management, and it is not undone by running it
# backwards: the seven lost configuration categories do not come back. So the default mode of this
# script is to record and report only. It changes nothing unless both --apply and
# --i-understand-this-is-disruptive are given.
#
# Structure, credential handling and the ONTAP helpers are taken from
# examples/block-storage/provision-lun.sh rather than rewritten.
#
# Requires: curl, jq, aws.

set -euo pipefail

FILE_SYSTEM_ID=""
SOURCE_SVM=""
DEST_SVM=""
VOLUME=""
SECRET_ID=""
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
MGMT_IP_ARG=""
PASSWORD_STDIN="false"
APPLY="false"
ACKNOWLEDGED="false"
OUT=""

usage() {
  cat <<'USAGE'
Usage: rehost-probe.sh (--file-system-id fs-... | --management-ip IP)
                       --source-svm NAME --destination-svm NAME --volume NAME
                       (--secret-id NAME_OR_ARN | --password-stdin)
                       [--region REGION] [--out FILE]
                       [--apply --i-understand-this-is-disruptive]

Without --apply this records the current state, prints what the move would do, and exits. That mode
is safe to run as often as you like and is worth running first: it also tells you whether the
preconditions are met.

Required:
  --source-svm      SVM that owns the volume now. Output SourceSvmName of the stack.
  --destination-svm SVM to move it to. Output DestinationSvmName.
  --volume          Volume to move. Output RehostVolumeName. Do NOT point this at the volume that
                    carries the permission measurement: rehost loses the user and group IDs, which
                    would destroy the record you are trying to compare against.
  --secret-id / --password-stdin, and --file-system-id / --management-ip: as in the other scripts.

Optional:
  --out             Write the JSON record here instead of stdout.

Before you use --apply, read this:

  The CloudFormation stack records this volume as belonging to the source SVM. After a successful
  rehost that record is stale, and question 2 above is precisely whether the AWS side notices. If it
  does not, `cloudformation delete-stack` may fail on this volume. The manual path is printed by
  this script before it changes anything, so you have it even if the stack becomes unusable.

  Nothing here touches SnapLock or snapshot locking, and nothing here becomes permanently
  undeletable. The risk is a stuck stack and a volume that has to be removed by hand, not a resource
  that cannot be removed at all.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --file-system-id) FILE_SYSTEM_ID="$2"; shift 2 ;;
    --source-svm) SOURCE_SVM="$2"; shift 2 ;;
    --destination-svm) DEST_SVM="$2"; shift 2 ;;
    --volume) VOLUME="$2"; shift 2 ;;
    --secret-id) SECRET_ID="$2"; shift 2 ;;
    --management-ip) MGMT_IP_ARG="$2"; shift 2 ;;
    --password-stdin) PASSWORD_STDIN="true"; shift ;;
    --region) REGION="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --apply) APPLY="true"; shift ;;
    --i-understand-this-is-disruptive) ACKNOWLEDGED="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "rehost-probe: $*" >&2; exit 1; }

for tool in curl jq aws; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required but not installed"
done

[ -n "$SOURCE_SVM" ] || die "--source-svm is required"
[ -n "$DEST_SVM" ] || die "--destination-svm is required"
[ -n "$VOLUME" ] || die "--volume is required"
[ "$SOURCE_SVM" != "$DEST_SVM" ] || die "source and destination SVM are the same"
[ -n "$FILE_SYSTEM_ID" ] || [ -n "$MGMT_IP_ARG" ] ||
  die "one of --file-system-id or --management-ip is required"
[ -n "$SECRET_ID" ] || [ "$PASSWORD_STDIN" = "true" ] ||
  die "one of --secret-id or --password-stdin is required"
[ -n "$REGION" ] || die "--region is required (or set AWS_REGION): the AWS side of the record needs it"

if [ "$APPLY" = "true" ] && [ "$ACKNOWLEDGED" != "true" ]; then
  die "--apply also requires --i-understand-this-is-disruptive. rehost interrupts data access and
      loses seven categories of volume configuration that running it backwards does not restore"
fi

# ---------------------------------------------------------------- endpoint and credentials

if [ -n "$MGMT_IP_ARG" ]; then
  MGMT_IP="$MGMT_IP_ARG"
else
  [ -n "$FILE_SYSTEM_ID" ] || die "--file-system-id is required to resolve the management address"
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
    --query SecretString --output text 2>/dev/null |
    jq -r '.password // empty')"
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
  # ONTAP returns job messages containing unescaped control characters. Passed straight to jq they
  # produce "Invalid string: control characters from U+0000 through U+001F must be escaped", and
  # under `set -o pipefail` that kills the script with an error about JSON rather than about the
  # operation. Measured on ONTAP 9.18.1P3D1, 2026-09-11.
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

VOL_FIELDS='uuid,name,svm.name,nas.security_style,nas.path,nas.export_policy.name,snapshot_policy.name,clone.is_flexclone,clone.parent_volume.name,state,type,efficiency.compression,qos.policy.name'

# The ONTAP view and the AWS view of the same volume, captured together. Capturing them separately
# is how a disagreement between the two gets attributed to timing instead of to the move.
snapshot_state() {
  local ontap_json aws_json
  ontap_json="$(ontap GET "/storage/volumes?name=${VOLUME}&fields=${VOL_FIELDS}")"
  ontap_ok "$ontap_json" "reading volume $VOLUME from ONTAP"

  aws_json="$(aws fsx describe-volumes --region "$REGION" \
    --query "Volumes[?Name=='${VOLUME}'].{VolumeId:VolumeId,Lifecycle:Lifecycle,SvmId:OntapConfiguration.StorageVirtualMachineId,SecurityStyle:OntapConfiguration.SecurityStyle,JunctionPath:OntapConfiguration.JunctionPath}" \
    --output json 2>/dev/null || echo '[]')"

  jq -n --argjson o "$ontap_json" --argjson a "$aws_json" \
    --arg when "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{
       at_utc: $when,
       ontap: ($o.records[0] // null),
       aws: ($a[0] // null)
     }'
}

CLUSTER="$(ontap GET "/cluster?fields=version.full,name")"
ontap_ok "$CLUSTER" "reading the cluster version"
ONTAP_VERSION="$(printf '%s' "$CLUSTER" | jq -r '.version.full // "unknown"')"

BEFORE="$(snapshot_state)"

VOL_UUID="$(jq -r '.ontap.uuid // empty' <<<"$BEFORE")"
[ -n "$VOL_UUID" ] || die "volume $VOLUME not found on this file system"
CUR_SVM="$(jq -r '.ontap.svm.name // "unknown"' <<<"$BEFORE")"
IS_CLONE="$(jq -r '.ontap.clone.is_flexclone // false' <<<"$BEFORE")"
JUNCTION="$(jq -r '.ontap.nas.path // ""' <<<"$BEFORE")"
STYLE_BEFORE="$(jq -r '.ontap.nas.security_style // "unknown"' <<<"$BEFORE")"
AWS_SVM_BEFORE="$(jq -r '.aws.SvmId // "not reported"' <<<"$BEFORE")"

echo "== before =="
printf 'ONTAP version        : %s\n' "$ONTAP_VERSION"
printf 'volume               : %s (uuid %s)\n' "$VOLUME" "$VOL_UUID"
printf 'owning SVM (ONTAP)   : %s\n' "$CUR_SVM"
printf 'owning SVM (AWS API) : %s\n' "$AWS_SVM_BEFORE"
printf 'security style       : %s\n' "$STYLE_BEFORE"
printf 'junction path        : %s\n' "${JUNCTION:-unmounted}"
printf 'is a FlexClone       : %s\n' "$IS_CLONE"

# ---------------------------------------------------------------- preconditions

echo
echo "== preconditions =="

BLOCKERS=""
note() { printf '  %s\n' "$1"; }

if [ "$CUR_SVM" != "$SOURCE_SVM" ]; then
  BLOCKERS="${BLOCKERS}volume is on '$CUR_SVM', not on the given --source-svm '$SOURCE_SVM'. "
  note "FAIL owning SVM does not match --source-svm"
else
  note "ok   owned by $SOURCE_SVM"
fi

# A clone or a clone parent is refused outright. Splitting first is possible but it ends the block
# sharing and allocates the copy its own storage, so it is a decision rather than a workaround and
# this script will not make it silently.
if [ "$IS_CLONE" = "true" ]; then
  BLOCKERS="${BLOCKERS}volume is a FlexClone; rehost refuses clones and clone parents. "
  note "FAIL this volume is a FlexClone. Split it first with volume clone split start -- which"
  note "     ends the sharing with the parent and allocates full capacity. That cost is the"
  note "     decision; the script will not take it for you"
else
  note "ok   not a FlexClone"
fi

CLONE_CHILDREN="$(ontap GET "/storage/volumes?clone.parent_volume.name=${VOLUME}&fields=name")"
ontap_ok "$CLONE_CHILDREN" "checking for clones of $VOLUME"
CHILD_COUNT="$(jq -r '.num_records // 0' <<<"$CLONE_CHILDREN")"
if [ "$CHILD_COUNT" -gt 0 ]; then
  BLOCKERS="${BLOCKERS}volume is the parent of $CHILD_COUNT clone(s). "
  note "FAIL $CHILD_COUNT clone(s) have this volume as parent; rehost refuses a clone parent"
else
  note "ok   no clones depend on it"
fi

SM_JSON="$(ontap GET "/snapmirror/relationships?destination.path=${SOURCE_SVM}:${VOLUME}&fields=uuid,state")"
ontap_ok "$SM_JSON" "checking SnapMirror relationships"
if [ "$(jq -r '.num_records // 0' <<<"$SM_JSON")" -gt 0 ]; then
  BLOCKERS="${BLOCKERS}a SnapMirror relationship targets this volume. "
  note "FAIL a SnapMirror relationship exists; delete, release or break it first"
else
  note "ok   no SnapMirror relationship targets it"
fi

if [ -n "$JUNCTION" ]; then
  note "note mounted at $JUNCTION. A NAS volume must be unmounted and outside any junction path;"
  note "     --apply will unmount it. The CloudFormation stack still records the junction path,"
  note "     because the resource handler requires one even for a volume that has no reason to be"
  note "     in the namespace"
else
  note "ok   already unmounted"
fi

DEST_JSON="$(ontap GET "/svm/svms?name=${DEST_SVM}&fields=uuid,name,subtype,nfs.enabled,cifs.enabled")"
ontap_ok "$DEST_JSON" "reading the destination SVM"
if [ "$(jq -r '.num_records // 0' <<<"$DEST_JSON")" -eq 0 ]; then
  BLOCKERS="${BLOCKERS}destination SVM $DEST_SVM not found. "
  note "FAIL destination SVM $DEST_SVM not found"
else
  SRC_SUBTYPE="$(ontap GET "/svm/svms?name=${SOURCE_SVM}&fields=subtype")"
  ontap_ok "$SRC_SUBTYPE" "reading the source SVM subtype"
  s_sub="$(jq -r '.records[0].subtype // "unknown"' <<<"$SRC_SUBTYPE")"
  d_sub="$(jq -r '.records[0].subtype // "unknown"' <<<"$DEST_JSON")"
  if [ "$s_sub" != "$d_sub" ]; then
    BLOCKERS="${BLOCKERS}SVM subtypes differ ($s_sub vs $d_sub). "
    note "FAIL subtypes differ: $s_sub vs $d_sub. Volumes only move between SVMs of the same subtype"
  else
    note "ok   both SVMs are subtype $s_sub"
  fi
fi

echo
echo "== what the move will cost =="
cat <<'COST'
  Lost from the volume and needing manual reconfiguration afterwards, per the vendor documentation
  for rehosting a SAN volume:

    antivirus policy, volume efficiency policy, QoS policy, snapshot policy,
    ns-switch and name services configuration, export policy and rules,
    user and group IDs

  Two of those matter more than the others here. The snapshot policy failing silently is only
  noticed when a restore is needed. The user and group IDs are what NFS evaluates, so losing them
  changes the answer to the question the rest of this example is measuring - which is why the volume
  under test and the volume moved here are deliberately different volumes.
COST

echo
echo "== manual teardown, in case the stack becomes unable to delete this volume =="
cat <<TEARDOWN
  # ONTAP side, if the volume ends up on the destination SVM and CloudFormation still expects it on
  # the source. Run these before deleting the stack.
  #   PATCH /api/storage/volumes/${VOL_UUID}   {"state":"offline"}
  #   DELETE /api/storage/volumes/${VOL_UUID}
  #
  # If ONTAP refuses the delete, the Amazon FSx API has been observed to succeed where ONTAP does
  # not, for volumes whose two control-plane views disagree:
  #   aws fsx delete-volume --region ${REGION} --volume-id <VolumeId from the record below>
  #
  # A deleted volume sits in the recovery queue for at least twelve hours by default and blocks its
  # parent while it is there. It is renamed to <name>_<dataset id> and hidden from the volume list,
  # and it lands on the DESTINATION SVM after a rehost, not the source (measured 2026-09-11). List
  # and purge it over REST:
  #   GET  /api/private/cli/volume/recovery-queue?fields=vserver,volume
  #   POST /api/private/cli/volume/recovery-queue/purge  {"vserver":"...","volume":"..._1200"}
  # DELETE on the collection returns HTTP 405 "invalid operation"; the purge is a POST to the
  # subcommand path. ONTAP CLI equivalent: volume recovery-queue purge -vserver X -volume Y
TEARDOWN

if [ -n "$BLOCKERS" ]; then
  echo
  echo "== not proceeding =="
  echo "$BLOCKERS"
  RECORD="$(jq -n --argjson before "$BEFORE" --arg v "$ONTAP_VERSION" --arg b "$BLOCKERS" \
    --arg src "$SOURCE_SVM" --arg dst "$DEST_SVM" --arg region "$REGION" \
    '{probe:"volume-rehost", ontap_version:$v, region:$region,
      source_svm:$src, destination_svm:$dst,
      before:$before, after:null, applied:false, blocked_by:$b}')"
  if [ -n "$OUT" ]; then printf '%s\n' "$RECORD" >"$OUT"; else printf '%s\n' "$RECORD"; fi
  exit 1
fi

if [ "$APPLY" != "true" ]; then
  echo
  echo "== recorded only =="
  echo "Preconditions are met. Nothing was changed. To perform the move:"
  echo "  $0 ... --apply --i-understand-this-is-disruptive"
  RECORD="$(jq -n --argjson before "$BEFORE" --arg v "$ONTAP_VERSION" \
    --arg src "$SOURCE_SVM" --arg dst "$DEST_SVM" --arg region "$REGION" \
    '{probe:"volume-rehost", ontap_version:$v, region:$region,
      source_svm:$src, destination_svm:$dst,
      before:$before, after:null, applied:false, blocked_by:null}')"
  if [ -n "$OUT" ]; then printf '%s\n' "$RECORD" >"$OUT"; else printf '%s\n' "$RECORD"; fi
  exit 0
fi

# ---------------------------------------------------------------- apply

echo
echo "== applying =="

if [ -n "$JUNCTION" ]; then
  out="$(ontap PATCH "/storage/volumes/${VOL_UUID}" '{"nas":{"path":""}}')"
  ontap_ok "$out" "unmounting $VOLUME"
  echo "unmount : $VOLUME removed from the namespace (was $JUNCTION)"
fi

# rehost has no resource endpoint. Rewriting the volume's owning SVM is refused outright:
#
#   PATCH /api/storage/volumes/{uuid}  {"svm":{"name":"<destination>"}}
#   -> HTTP 400  code 262196  Field "svm.name" cannot be set in this operation
#
# (measured on ONTAP 9.18.1P3D1, 2026-09-11 - this script previously used that shape and could not
# have worked). The operation is reachable only through the private CLI passthrough, which is the
# documented escape hatch for CLI-only commands. The CLI equivalent is:
#   volume rehost -vserver <source> -volume <name> -destination-vserver <destination>
out="$(ontap POST "/private/cli/volume/rehost" "$(jq -nc \
  --arg s "$SOURCE_SVM" --arg v "$VOLUME" --arg d "$DEST_SVM" \
  '{vserver:$s, volume:$v, "destination-vserver":$d}')")"
ontap_ok "$out" "rehosting $VOLUME to $DEST_SVM"
REHOST_JOB="$(jq -r '.job.uuid // empty' <<<"$out")"
echo "rehost  : requested $SOURCE_SVM -> $DEST_SVM${REHOST_JOB:+ (job $REHOST_JOB)}"
printf '          %s\n' "$(jq -r '.cli_output // "no cli_output"' <<<"$out")"

# The call returns 202 with a queued job. Waiting for the job is separate from waiting for the AWS
# side, and conflating the two is how a still-running rehost gets recorded as a finished one.
if [ -n "$REHOST_JOB" ]; then
  echo "job     : waiting for the ONTAP job to finish"
  for _ in $(seq 1 40); do
    job="$(ontap GET "/cluster/jobs/${REHOST_JOB}?fields=state,message,code")"
    ontap_ok "$job" "reading job $REHOST_JOB"
    js="$(jq -r '.state // "unknown"' <<<"$job")"
    printf '          state=%s\n' "$js"
    case "$js" in
      success) break ;;
      failure) die "the rehost job failed: $(jq -r '.message // "no message"' <<<"$job")" ;;
    esac
    sleep 15
  done
fi

# The AWS side is asynchronous, and the window matters more than it looks. Amazon FSx documents that
# changes made with NetApp tooling take "several minutes" to appear in the console, the CLI and the
# API. Measured here on 2026-09-11 it took **13 minutes 42 seconds** from the ONTAP job completing,
# and all three stale fields - StorageVirtualMachineId, JunctionPath, SnapshotPolicy - moved at once.
#
# This loop used to run for 10 minutes and then declare that the AWS side had not followed. It would
# have been wrong on the first real run. 25 minutes is the window now: long enough to clear the
# measured figure with margin, and a timeout is reported as a timeout rather than as a finding.
POLL_MINUTES=25
echo "waiting : polling both control planes for up to ${POLL_MINUTES} minutes"
echo "          (measured once at 13m42s; a shorter window turns a sync delay into a false finding)"
AFTER=""
AWS_FOLLOWED="false"
for _ in $(seq 1 $((POLL_MINUTES * 4))); do
  sleep 15
  AFTER="$(snapshot_state)"
  a_svm="$(jq -r '.aws.SvmId // "not reported"' <<<"$AFTER")"
  o_svm="$(jq -r '.ontap.svm.name // "unknown"' <<<"$AFTER")"
  printf '          %s ONTAP=%s AWS=%s\n' "$(date -u +%H:%M:%S)" "$o_svm" "$a_svm"
  if [ "$a_svm" != "$AWS_SVM_BEFORE" ]; then
    AWS_FOLLOWED="true"
    break
  fi
done
[ -n "$AFTER" ] || AFTER="$(snapshot_state)"

STYLE_AFTER="$(jq -r '.ontap.nas.security_style // "unknown"' <<<"$AFTER")"
AWS_SVM_AFTER="$(jq -r '.aws.SvmId // "not reported"' <<<"$AFTER")"
ONTAP_SVM_AFTER="$(jq -r '.ontap.svm.name // "unknown"' <<<"$AFTER")"

echo
echo "== findings =="
printf 'security style     : %s -> %s  => %s\n' "$STYLE_BEFORE" "$STYLE_AFTER" \
  "$([ "$STYLE_BEFORE" = "$STYLE_AFTER" ] && echo 'PRESERVED across the move' || echo 'CHANGED by the move')"
printf 'ONTAP owning SVM   : %s -> %s\n' "$CUR_SVM" "$ONTAP_SVM_AFTER"
printf 'AWS owning SVM     : %s -> %s  => %s\n' "$AWS_SVM_BEFORE" "$AWS_SVM_AFTER" \
  "$([ "$AWS_FOLLOWED" = "true" ] && echo 'AWS followed the change' || echo "still stale after ${POLL_MINUTES}m -- NOT yet a finding, see below")"

# The snapshot policy is the one of the seven lost categories that is observable here, and what it
# does is not what "lost" suggests: measured 2026-09-11 a volume with snapshot_policy=none came out
# with snapshot_policy=default. Reported explicitly because the direction of the risk is inverted -
# a volume nobody wanted snapshots on acquires the default schedule.
SNAP_BEFORE="$(jq -r '.ontap.snapshot_policy.name // "unknown"' <<<"$BEFORE")"
SNAP_AFTER="$(jq -r '.ontap.snapshot_policy.name // "unknown"' <<<"$AFTER")"
printf 'snapshot policy    : %s -> %s  => %s\n' "$SNAP_BEFORE" "$SNAP_AFTER" \
  "$([ "$SNAP_BEFORE" = "$SNAP_AFTER" ] && echo 'unchanged' || echo 'CHANGED -- reconfigure it, and check whether it acquired a schedule rather than losing one')"

if [ "$AWS_FOLLOWED" != "true" ]; then
  cat <<DISAGREE

The AWS API still reports the old SVM after ${POLL_MINUTES} minutes. That is longer than the
13m42s measured on 2026-09-11, so it is worth taking seriously - but it is still a timeout, not a
finding. Two readings remain open and this run cannot tell them apart:

  - the synchronisation is slower in this environment than in the measured one, or
  - something about this volume keeps it from synchronising at all.

Re-read the AWS side after an hour before recording either, and treat the stack as possibly unable
to delete this volume until it agrees:

  aws fsx describe-volumes --region ${REGION} --volume-ids <VolumeId> \
    --query 'Volumes[0].OntapConfiguration.StorageVirtualMachineId'
DISAGREE
fi

RECORD="$(jq -n --argjson before "$BEFORE" --argjson after "$AFTER" \
  --arg v "$ONTAP_VERSION" --arg src "$SOURCE_SVM" --arg dst "$DEST_SVM" --arg region "$REGION" \
  --arg sb "$STYLE_BEFORE" --arg sa "$STYLE_AFTER" \
  --arg ab "$AWS_SVM_BEFORE" --arg aa "$AWS_SVM_AFTER" \
  --arg snb "$SNAP_BEFORE" --arg sna "$SNAP_AFTER" \
  --arg followed "$AWS_FOLLOWED" --arg window "$POLL_MINUTES" \
  '{probe:"volume-rehost", ontap_version:$v, region:$region,
    source_svm:$src, destination_svm:$dst,
    before:$before, after:$after, applied:true, blocked_by:null,
    findings: {
      security_style: {before:$sb, after:$sa, preserved:($sb == $sa)},
      snapshot_policy: {before:$snb, after:$sna, changed:($snb != $sna)},
      aws_control_plane: {before:$ab, after:$aa, followed:($followed == "true"),
                          polled_minutes:($window|tonumber),
                          note:"A false value means the poll timed out, not that the planes disagree permanently. Re-read after an hour."}
    },
    caveat: "The seven lost configuration categories are not captured here. Compare the before and after export policy, snapshot policy and QoS policy fields in this record before reconfiguring."}')"

if [ -n "$OUT" ]; then
  printf '%s\n' "$RECORD" >"$OUT"
  echo
  echo "record written to $OUT"
else
  echo
  printf '%s\n' "$RECORD"
fi
