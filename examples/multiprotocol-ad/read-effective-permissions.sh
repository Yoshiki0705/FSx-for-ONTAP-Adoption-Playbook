#!/usr/bin/env bash
#
# Record what the NFS side of an Amazon FSx for NetApp ONTAP volume shows for permissions that were
# set over SMB, and whether the access those permissions describe actually succeeds.
#
# This is the second half of a three-part record. set-test-acls.sh writes the first half - the ACE
# as it was set, at the storage layer through the ONTAP REST API. This script writes the other two: the representation the NFS
# side shows, and the outcome of a real read and a real write. A result missing any of the three is
# not usable, because the three answer different questions:
#
#   the ACE as set          - what was asked for
#   the NFS representation  - what survived the translation
#   the outcome             - whether the translation is what governs the decision
#
# The output is JSON on stdout, or to --out. It carries the environment alongside the results,
# because a permission result without the ONTAP version, the region and the security style cannot be
# compared with anything.
#
# Run it as the Active Directory test user. It refuses to run as root, and it refuses to run when the
# caller is in the group that was given as FileSystemAdministratorsGroup: both produce a pass that
# says nothing about the permissions being tested.
#
# Requires: mount.nfs4 (nfs-utils), nfs4_getfacl (nfs4-acl-tools), jq, id, stat.

set -euo pipefail

NFS_ENDPOINT=""
JUNCTION=""
STYLE=""
MOUNTPOINT=""
SUBPATHS=""
OUT=""
ADMIN_GROUP="Domain Admins"
ONTAP_VERSION=""
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
KEEP_MOUNTED="false"

usage() {
  cat <<'USAGE'
Usage: read-effective-permissions.sh --nfs-endpoint HOST_OR_IP --junction /path --style STYLE
                                    [--subpaths 'a,b,c'] [--mountpoint DIR] [--out FILE]
                                    [--ontap-version V] [--region REGION]
                                    [--admin-group 'NAME'] [--keep-mounted]

Required:
  --nfs-endpoint    The SVM's NFS endpoint. From the stack:
                      aws fsx describe-storage-virtual-machines --storage-virtual-machine-ids svm-... \
                        --query 'StorageVirtualMachines[0].Endpoints.Nfs.IpAddresses[0]'
  --junction        Junction path of the volume, for example /ntfsvol.
  --style           The volume's security style, as ONTAP reports it: ntfs or unix. This is recorded,
                    not detected, so that the record states what the operator believed - and a
                    mismatch with the ONTAP side becomes visible rather than silently assumed away.

Optional:
  --subpaths        Comma-separated paths under the junction to examine. Default:
                    allow,deny,inherited/child
                    These are the three directories set-test-acls.sh applies descriptors to.
  --mountpoint      Where to mount. Default: a directory under /tmp, removed afterwards.
  --out             Write the JSON record here instead of stdout.
  --ontap-version   ONTAP version string, recorded as given. Read it once from the ONTAP REST API:
                      GET /api/cluster?fields=version.full
  --region          Recorded in the output. Defaults to AWS_REGION or AWS_DEFAULT_REGION.
  --admin-group     Group whose members invalidate the test. Default: Domain Admins
  --keep-mounted    Leave the mount in place for manual inspection.

What each field of the output means:

  mode_bits          What stat(1) reports. On an NTFS-style volume these are synthesised by ONTAP
                     from the NTFS ACL; they are a lossy view and a Deny ACE has no representation
                     in them at all. Reading only this field is the mistake this script exists to
                     prevent.
  nfsv4_acl          What nfs4_getfacl reports. This can carry a deny entry, so it is where a Deny
                     ACE would appear if it survived.
  nfsv4_acl_status   Whether the call worked. "unsupported" is a real answer and does not mean the
                     ACL is empty.
  read / write       The outcome. If the representation says one thing and the outcome says another,
                     the outcome is the finding and the representation is the explanation to chase.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --nfs-endpoint) NFS_ENDPOINT="$2"; shift 2 ;;
    --junction) JUNCTION="$2"; shift 2 ;;
    --style) STYLE="$2"; shift 2 ;;
    --subpaths) SUBPATHS="$2"; shift 2 ;;
    --mountpoint) MOUNTPOINT="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --ontap-version) ONTAP_VERSION="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --admin-group) ADMIN_GROUP="$2"; shift 2 ;;
    --keep-mounted) KEEP_MOUNTED="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "read-effective-permissions: $*" >&2; exit 1; }

command -v jq >/dev/null 2>&1 || die "jq is required but not installed"
command -v mount.nfs4 >/dev/null 2>&1 || command -v mount >/dev/null 2>&1 ||
  die "nfs-utils is required but not installed"

[ -n "$NFS_ENDPOINT" ] || die "--nfs-endpoint is required"
[ -n "$JUNCTION" ] || die "--junction is required"
[ -n "$STYLE" ] || die "--style is required (ntfs or unix)"
[ -n "$SUBPATHS" ] || SUBPATHS="allow,deny,inherited/child"

case "$STYLE" in
  ntfs | unix) : ;;
  *) die "--style must be ntfs or unix, got '$STYLE'" ;;
esac

# ---------------------------------------------------------------- who is running this

WHOAMI="$(id -un)"
WHOAMI_UID="$(id -u)"

if [ "$WHOAMI_UID" -eq 0 ]; then
  die "refusing to run as root. Root is squashed or privileged depending on the export rule's
      superuser setting, and neither case measures what an ordinary user can do. Run as the Active
      Directory test user"
fi

# The membership check is the one that has silently invalidated this kind of test before: members of
# the file system administrators group are evaluated with storage-administrator privileges, so every
# access succeeds and the run looks like a pass.
if id -nG 2>/dev/null | tr ' ' '\n' | grep -Fxq "$ADMIN_GROUP"; then
  die "$WHOAMI is a member of '$ADMIN_GROUP'. Members of that group bypass the evaluation being
      measured, so the result would be a false pass. Use an ordinary Active Directory user"
fi

# ---------------------------------------------------------------- mount

CLEANUP_MOUNT=""
cleanup() {
  if [ -n "$CLEANUP_MOUNT" ] && [ "$KEEP_MOUNTED" != "true" ]; then
    sudo umount "$CLEANUP_MOUNT" 2>/dev/null || true
    rmdir "$CLEANUP_MOUNT" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [ -z "$MOUNTPOINT" ]; then
  MOUNTPOINT="$(mktemp -d /tmp/mpad-XXXXXX)"
  CLEANUP_MOUNT="$MOUNTPOINT"
else
  mkdir -p "$MOUNTPOINT"
fi

# vers=4.1 is explicit. Without it the client negotiates, and a mount that silently landed on NFSv3
# would be measuring a different translation path - v3 carries mode bits only and has no ACL call at
# all, so the nfsv4_acl field would come back empty for a reason unrelated to the security style.
MOUNT_OPTS="vers=4.1,sec=sys,hard"
if ! mountpoint -q "$MOUNTPOINT" 2>/dev/null; then
  sudo mount -t nfs4 -o "$MOUNT_OPTS" "${NFS_ENDPOINT}:${JUNCTION}" "$MOUNTPOINT" ||
    die "mount failed. Check the export policy rule matches this host's address, that ports 111,
        635, 2049 and 4045-4046 are open, and that NFSv4.1 is enabled on the SVM"
fi

ACTUAL_VERS="$(findmnt -n -o OPTIONS --target "$MOUNTPOINT" 2>/dev/null |
  tr ',' '\n' | sed -n 's/^vers=//p' | head -1)"
[ -n "$ACTUAL_VERS" ] || ACTUAL_VERS="unknown"
if [ "$ACTUAL_VERS" != "4.1" ]; then
  die "mounted as NFS $ACTUAL_VERS, not 4.1. The record would not be about the path being measured"
fi

# ---------------------------------------------------------------- probe each path

probe_one() {
  local sub="$1"
  local full="$MOUNTPOINT/$sub"

  if [ ! -e "$full" ]; then
    jq -nc --arg p "$sub" '{path:$p, present:false,
      note:"not found. Create the tree over NFS and run set-test-acls.sh first"}'
    return
  fi

  local mode owner group
  mode="$(stat -c '%A %a' "$full" 2>/dev/null || echo 'unreadable')"
  owner="$(stat -c '%U(%u)' "$full" 2>/dev/null || echo 'unreadable')"
  group="$(stat -c '%G(%g)' "$full" 2>/dev/null || echo 'unreadable')"

  local acl acl_status
  if command -v nfs4_getfacl >/dev/null 2>&1; then
    if acl="$(nfs4_getfacl "$full" 2>&1)"; then
      # Exit status 0 is not the verdict. Measured on 2026-09-12: with NFSv4 ACLs disabled on the
      # SVM, nfs4_getfacl printed "Operation to request attribute not supported" and still exited
      # 0, so a status taken from $? alone recorded "ok" next to an error string -- the record then
      # claimed a representation had been read when none had. A real ACL always opens with a
      # "# file:" header, so the shape of the output is what decides.
      if printf '%s' "$acl" | grep -q '^# file:'; then
        acl_status="ok"
      else
        # The usual cause is acl_enabled being false on the SVM, which is the DEFAULT on
        # FSx for ONTAP for both v4.0 and v4.1:
        #   GET  /api/protocols/nfs/services/{svm.uuid}?fields=**
        #        .protocol.v41_features.acl_enabled
        #   PATCH the same path with {"protocol":{"v41_features":{"acl_enabled":true}}}
        # An existing mount keeps the capability it negotiated, so remount afterwards or the
        # attribute stays unsupported on that mount.
        acl_status="unsupported: $(printf '%s' "$acl" | head -1)"
        acl=""
      fi
    else
      # A failure here is informative and must not be reported as an empty ACL.
      acl_status="failed: $(printf '%s' "$acl" | head -1)"
      acl=""
    fi
  else
    acl_status="unsupported: nfs4_getfacl not installed (dnf install nfs4-acl-tools)"
    acl=""
  fi

  # A read and a write, each reported with the errno text rather than as a bare boolean, because
  # EACCES and EPERM come from different layers and the distinction is the first thing to look at
  # when the outcome disagrees with the representation.
  local read_result write_result probe_file
  if [ -d "$full" ]; then
    # find rather than ls: the point is whether the directory can be read at all, and find reports
    # the errno on the directory itself instead of on the first awkward filename inside it.
    if find "$full" -maxdepth 1 >/dev/null 2>&1; then
      read_result="ok"
    else
      read_result="denied: $(find "$full" -maxdepth 1 2>&1 >/dev/null | head -1)"
    fi
    probe_file="$full/.mpad-write-probe.$$"
    if : >"$probe_file" 2>/dev/null; then
      write_result="ok"
      rm -f "$probe_file" 2>/dev/null || true
    else
      write_result="denied: $(: >"$probe_file" 2>&1 | head -1)"
    fi
  else
    if head -c 1 "$full" >/dev/null 2>&1; then read_result="ok"; else read_result="denied: $(head -c 1 "$full" 2>&1 | head -1)"; fi
    if printf '' >>"$full" 2>/dev/null; then write_result="ok"; else write_result="denied: $(printf '' >>"$full" 2>&1 | head -1)"; fi
  fi

  jq -nc --arg p "$sub" --arg m "$mode" --arg o "$owner" --arg g "$group" \
    --arg acl "$acl" --arg as "$acl_status" --arg r "$read_result" --arg w "$write_result" \
    '{path:$p, present:true, mode_bits:$m, owner:$o, group:$g,
      nfsv4_acl:$acl, nfsv4_acl_status:$as, read:$r, write:$w}'
}

RESULTS="[]"
IFS=',' read -r -a SUBLIST <<<"$SUBPATHS"
for sub in "${SUBLIST[@]}"; do
  one="$(probe_one "$sub")"
  RESULTS="$(jq -c --argjson o "$one" '. + [$o]' <<<"$RESULTS")"
done

# ---------------------------------------------------------------- emit

INCOMPLETE=""
[ -n "$ONTAP_VERSION" ] || INCOMPLETE="ontap_version not given; the record cannot be promoted beyond field-observation without it"
[ -n "$REGION" ] || INCOMPLETE="${INCOMPLETE:+$INCOMPLETE; }region not given"

RECORD="$(jq -n \
  --arg endpoint "$NFS_ENDPOINT" \
  --arg junction "$JUNCTION" \
  --arg style "$STYLE" \
  --arg vers "$ACTUAL_VERS" \
  --arg opts "$MOUNT_OPTS" \
  --arg user "$WHOAMI" \
  --arg uid "$WHOAMI_UID" \
  --arg groups "$(id -nG 2>/dev/null || echo unknown)" \
  --arg ontap "${ONTAP_VERSION:-not recorded}" \
  --arg region "${REGION:-not recorded}" \
  --arg when "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg incomplete "${INCOMPLETE:-}" \
  --argjson results "$RESULTS" \
  '{
     environment: {
       nfs_endpoint: $endpoint, junction: $junction, security_style: $style,
       nfs_version: $vers, mount_options: $opts,
       ontap_version: $ontap, region: $region, recorded_at_utc: $when
     },
     caller: { user: $user, uid: $uid, groups: $groups },
     results: $results,
     record_is_incomplete: (if $incomplete == "" then null else $incomplete end),
     reminder: "This is two of the three parts. Pair it with the ACE that set-test-acls.sh recorded before drawing any conclusion."
   }')"

if [ -n "$OUT" ]; then
  printf '%s\n' "$RECORD" >"$OUT"
  echo "written to $OUT"
else
  printf '%s\n' "$RECORD"
fi

if [ -n "$INCOMPLETE" ]; then
  echo "read-effective-permissions: $INCOMPLETE" >&2
fi
