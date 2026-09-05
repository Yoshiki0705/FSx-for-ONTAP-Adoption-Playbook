#!/usr/bin/env bash
#
# Connect this Linux host to the LUNs of an Amazon FSx for NetApp ONTAP SVM over iSCSI.
#
# Why this exists rather than the documented command sequence: the AWS procedure logs in with
# "iscsiadm -m node -L all" after a loop of per-portal discoveries, and running that loop a second
# time adds sessions instead of recognising the ones already present. On a Windows host the same
# pattern took a measured 16 paths to 24 with no warning. This script logs in only to portals that
# have no session yet, so a second run is a no-op.
#
# What it deliberately does not do:
#   - It does not create more than one session per portal. The AWS guidance of eight sessions per
#     node comes from a first-generation bandwidth calculation, and NetApp separately states that a
#     single LUN needs no more than four paths. Pick a number for your own bandwidth requirement and
#     pass --sessions-per-portal; the default of 1 keeps the path count at the number of LIFs.
#   - It does not write /etc/multipath.conf if one already exists. "mpathconf --enable" produced a
#     334-byte file in a measured environment while NetApp recommends an empty file, and overwriting
#     whatever the host already has is not this script's decision to make.
#
# Requires: iscsiadm, multipath, aws, jq. Run as root.

set -euo pipefail

FILE_SYSTEM_ID=""
SVM_ID=""
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
SESSIONS_PER_PORTAL=1
REPLACEMENT_TIMEOUT=""
TARGET_IPS=""

usage() {
  cat <<'USAGE'
Usage: connect-iscsi.sh --file-system-id fs-... [--svm-id svm-...] [--region REGION]
                        [--target-ips "IP IP"] [--sessions-per-portal N]
                        [--replacement-timeout SECONDS]

Required (one of):
  --file-system-id  Amazon FSx file system ID. The iSCSI addresses are read from its SVMs.
  --target-ips      Space-separated iSCSI addresses, if you would rather not call the AWS API.

Optional:
  --svm-id          Restrict to one SVM when the file system has several.
  --region          AWS region. Defaults to AWS_REGION or AWS_DEFAULT_REGION.
  --sessions-per-portal
                    Sessions to establish per portal. Default 1. Raising it raises the path count
                    proportionally; see the note above before doing so.
  --replacement-timeout
                    Set node.session.timeo.replacement_timeout on the node records. The Linux
                    default is 120 seconds, and the AWS procedure asks for 5. Left untouched unless
                    given, so the value you chose is the value that stays.

Idempotent: portals that already have a session are skipped.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --file-system-id) FILE_SYSTEM_ID="$2"; shift 2 ;;
    --svm-id) SVM_ID="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --target-ips) TARGET_IPS="$2"; shift 2 ;;
    --sessions-per-portal) SESSIONS_PER_PORTAL="$2"; shift 2 ;;
    --replacement-timeout) REPLACEMENT_TIMEOUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "connect-iscsi: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root"
for tool in iscsiadm multipath; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required but not installed"
done

if [ -z "$TARGET_IPS" ]; then
  [ -n "$FILE_SYSTEM_ID" ] || die "--file-system-id or --target-ips is required"
  [ -n "$REGION" ] || die "--region is required (or set AWS_REGION)"
  for tool in aws jq; do
    command -v "$tool" >/dev/null 2>&1 || die "$tool is required to resolve addresses from the AWS API"
  done
  query='StorageVirtualMachines[?FileSystemId==`'"$FILE_SYSTEM_ID"'`]'
  [ -n "$SVM_ID" ] && query='StorageVirtualMachines[?StorageVirtualMachineId==`'"$SVM_ID"'`]'
  TARGET_IPS="$(aws fsx describe-storage-virtual-machines --region "$REGION" \
    --query "${query}.Endpoints.Iscsi.IpAddresses[]" --output text 2>/dev/null | tr '\t' ' ')"
  [ -n "$TARGET_IPS" ] ||
    die "no iSCSI addresses found. If the call timed out rather than returning nothing, this host has
      no route to the Amazon FSx API - a private subnet with only ssm and secretsmanager interface
      endpoints resolves fsx.<region>.amazonaws.com to public addresses. Pass --target-ips instead.
      Note also that the AWS API reports Nvme as null even where NVMe/TCP works"
fi

echo "== target portals =="
for ip in $TARGET_IPS; do echo "  $ip"; done

# The multipath daemon has to be running before login, otherwise the first paths appear as bare SCSI
# devices and the map is assembled late.
if [ ! -e /etc/multipath.conf ]; then
  echo
  echo "== multipath =="
  echo "no /etc/multipath.conf found; enabling multipathd"
  # NetApp recommends an empty file so ONTAP's compiled-in defaults apply, while "mpathconf --enable"
  # writes its own content. Creating the empty file first does not stop it entirely: measured on
  # Amazon Linux 2023 it left a 29-byte file with empty blacklist and defaults blocks, against the
  # 334 bytes it writes from scratch. The resulting map used NetApp's recommended path selector and
  # queueing behaviour either way, but record which of the two instructions you followed.
  : > /etc/multipath.conf
  mpathconf --enable --with_multipathd y >/dev/null 2>&1 || true
else
  echo
  echo "== multipath =="
  printf 'keeping existing /etc/multipath.conf (%s bytes)\n' "$(wc -c </etc/multipath.conf)"
fi
systemctl enable --now multipathd >/dev/null 2>&1 || die "could not start multipathd"
systemctl enable --now iscsid >/dev/null 2>&1 || die "could not start iscsid"

echo
echo "== discovery and login =="

sessions_for_portal() {
  # "iscsiadm -m session" exits 21 when there are no sessions at all, which under `set -o pipefail`
  # would take the whole script down on the first portal of a fresh host. An empty session list is
  # the normal starting state, not an error.
  { iscsiadm -m session 2>/dev/null || true; } |
    awk -v ip="$1" '$3 ~ "^"ip":" {n++} END {print n+0}'
}

for ip in $TARGET_IPS; do
  iscsiadm -m discovery -t sendtargets -p "${ip}:3260" >/dev/null 2>&1 ||
    die "discovery failed against ${ip}:3260. Check that the security group allows 3260 from here"

  have="$(sessions_for_portal "$ip")"
  want="$SESSIONS_PER_PORTAL"

  if [ "$have" -ge "$want" ]; then
    printf '  %-15s %s session(s) already present, skipped\n' "$ip" "$have"
    continue
  fi

  # Parsed from the short listing. "iscsiadm -m node -p <portal>" prints a full record dump that
  # begins with "# BEGIN RECORD", so taking a field from its first line yields "BEGIN" rather than
  # the target name - a discovery that succeeds followed by a login that cannot find its record.
  target="$({ iscsiadm -m node 2>/dev/null || true; } |
    awk -v ip="${ip}:3260" '$1 == ip || index($1, ip) == 1 {print $2; exit}')"
  [ -n "$target" ] || die "no node record for ${ip}:3260 after discovery"

  if [ -n "$REPLACEMENT_TIMEOUT" ]; then
    iscsiadm -m node -T "$target" -p "${ip}:3260" --op=update \
      -n node.session.timeo.replacement_timeout -v "$REPLACEMENT_TIMEOUT" >/dev/null
  fi

  # iscsid keys a session by (target, portal, iface), so more than one session to the same portal
  # needs a distinct iface. Named after the index so a re-run finds the same ifaces.
  added=0
  while [ "$((have + added))" -lt "$want" ]; do
    idx="$((have + added))"
    if [ "$idx" -eq 0 ]; then
      iface="default"
    else
      iface="fsxn${idx}"
      iscsiadm -m iface -I "$iface" --op=new >/dev/null 2>&1 || true
    fi
    if ! login_out="$(iscsiadm -m node -T "$target" -p "${ip}:3260" -I "$iface" --login 2>&1)"; then
      # The error text matters here: an authorization failure (exit 24) means CHAP is configured on
      # the target, which is a different problem from an unreachable portal.
      die "login failed for ${ip}:3260 via iface $iface: ${login_out}"
    fi
    added="$((added + 1))"
  done
  printf '  %-15s logged in %s new session(s)\n' "$ip" "$added"
done

echo
echo "== settling =="
# Paths appear asynchronously. Waiting here rather than in the caller keeps the verify step honest.
for _ in $(seq 1 15); do
  sleep 1
  multipath -r >/dev/null 2>&1 || true
  if multipath -ll 2>/dev/null | grep -q 'NETAPP,LUN C-Mode'; then break; fi
done

if multipath -ll 2>/dev/null | grep -q 'NETAPP,LUN C-Mode'; then
  echo "multipath map present"
else
  echo "no NetApp map yet. If provision-lun.sh has not run, no LUN is mapped to this host's igroup."
fi

echo
echo "Next: run verify-block.sh to record the counts, then run this script again to confirm they do"
echo "not change."
