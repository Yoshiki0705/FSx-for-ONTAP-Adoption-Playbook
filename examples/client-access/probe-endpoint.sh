#!/usr/bin/env bash
#
# Record what one endpoint can actually reach on an Amazon FSx for NetApp ONTAP file system, as a
# JSON document with an environment block. For macOS, WSL2 and native Linux; the Windows counterpart
# is probe-endpoint.ps1 and emits the same shape.
#
# The output is the deliverable, not the terminal text. Two records from two endpoints line up
# field by field, and a record from an endpoint nobody involved here owns lines up with them too.
#
# EVERY VALUE IS MASKED AS IT IS WRITTEN, not afterwards. Host names, IPv4 addresses, file system and
# SVM identifiers, account numbers and home paths are replaced before they reach the file. Masking a
# record later leaves the unmasked version in whatever it was copied into first, so this script never
# produces one.
#
# It creates nothing on the file system. It mounts only when asked, and unmounts before exiting.
#
# Requires: python3 (name resolution and TCP checks, so the answers come from the same resolver a
# mount would use). jq is NOT required.

set -euo pipefail

SVM_DNS=""
SMB_IP=""
NFS_IP=""
ISCSI_IP=""
SHARE_NAME=""
NFS_JUNCTION=""
SMB_USER=""
S3_ACCESS_POINT=""
OUT_FILE=""
TRY_MOUNT="false"
MOUNT_BASE=""

usage() {
  cat <<'USAGE'
Usage: probe-endpoint.sh [--svm-dns NAME] [--smb-ip IP] [--nfs-ip IP] [--iscsi-ip IP]
                         [--share NAME] [--nfs-junction PATH] [--smb-user NAME]
                         [--s3-access-point ALIAS] [--try-mount] [--mount-base DIR]
                         [--out FILE]

All arguments are optional. What is omitted is recorded as "not_tested" rather than as a failure,
because a missing check and a failed check are different findings and collapsing them is how a
comparison across endpoints stops meaning anything.

  --svm-dns          SVM DNS name. Resolution is checked with the system resolver, which is what a
                     mount uses -- so this answers "will the mount find it", not "does some DNS
                     server somewhere know".
  --smb-ip           SVM SMB address. TCP 445 is checked.
  --nfs-ip           SVM NFS address. TCP 2049, 111 and 635 are checked.
  --iscsi-ip         SVM iSCSI address. TCP 3260 is checked.
  --share            SMB share name, for the mount attempt.
  --nfs-junction     NFS junction path, for example /nfsvol.
  --smb-user         Local SMB user, as SERVER\user or just user.
  --s3-access-point  FSx for ONTAP S3 Access Point alias or ARN. A ListObjectsV2 is attempted with
                     the AWS CLI, which records whether the request reaches the VPC at all.
  --try-mount        Attempt the mounts, then unmount. Without it only reachability is recorded.
                     SMB on macOS prompts for the password on the terminal; on Linux and WSL2 the
                     password is read from standard input into a 0600 credentials file. Neither
                     path puts it in an argument, where every user on the host could read it.
  --mount-base       Directory to mount under. Default: a temporary directory, removed afterwards.
  --out              Write the JSON here instead of standard output.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --svm-dns) SVM_DNS="$2"; shift 2 ;;
    --smb-ip) SMB_IP="$2"; shift 2 ;;
    --nfs-ip) NFS_IP="$2"; shift 2 ;;
    --iscsi-ip) ISCSI_IP="$2"; shift 2 ;;
    --share) SHARE_NAME="$2"; shift 2 ;;
    --nfs-junction) NFS_JUNCTION="$2"; shift 2 ;;
    --smb-user) SMB_USER="$2"; shift 2 ;;
    --s3-access-point) S3_ACCESS_POINT="$2"; shift 2 ;;
    --try-mount) TRY_MOUNT="true"; shift ;;
    --mount-base) MOUNT_BASE="$2"; shift 2 ;;
    --out) OUT_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "probe-endpoint: $*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 ||
  die "python3 is required. It is used for name resolution and TCP checks so that both answers come
    from the same resolver and stack a mount would use."

# ------------------------------------------------------------------ masking

HOSTNAME_RAW="$(hostname 2>/dev/null || echo unknown)"
HOSTNAME_SHORT="${HOSTNAME_RAW%%.*}"

# The program is held in a variable and passed with -c rather than fed on standard input. With
# `python3 - <<EOF` the here-document IS the program, so stdin is already consumed by the time the
# script calls read() and every masked value comes out empty -- which looks like a masking bug rather
# than a plumbing one, because the record is still valid JSON.
MASK_PY='
import re
import sys

raw, short, home = sys.argv[1], sys.argv[2], sys.argv[3]
text = sys.stdin.read()

for name in sorted({raw, short}, key=len, reverse=True):
    if name and name != "unknown":
        text = text.replace(name, "<client-hostname>")
if home and home not in ("/", ""):
    text = text.replace(home, "<home>")

# Addresses keep their first two octets so two records from different networks stay distinguishable,
# and lose the rest so neither identifies a host. A literal 0.0.0.0 or 127.0.0.1 carries no
# information about anyone, so it is left alone.
def hide_ip(match: re.Match[str]) -> str:
    addr = match.group(0)
    if addr in ("0.0.0.0", "127.0.0.1", "255.255.255.255"):
        return addr
    a, b, _, _ = addr.split(".")
    return f"{a}.{b}.x.x"

text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", hide_ip, text)
text = re.sub(r"\bfs-[0-9a-f]{8,}\b", "fs-0123456789abcdef0", text)
text = re.sub(r"\bsvm-[0-9a-f]{8,}\b", "svm-0123456789abcdef0", text)
text = re.sub(r"\bFSxId[0-9a-f]{8,}\b", "FSxId0123456789abc", text)
# A 12-digit run is an AWS account ID everywhere it appears in these outputs.
text = re.sub(r"\b\d{12}\b", "123456789012", text)
# The trailing component of an IQN is the machine name on Windows and Linux alike.
text = re.sub(r"(iqn\.[0-9]{4}-[0-9]{2}\.[^:\s]+):\S+", r"\1:<client-hostname>", text)
sys.stdout.write(text)
'

# Applied to every string that reaches the record. The order matters: the host name is replaced before
# addresses, because on several images the host name contains one.
mask() {
  python3 -c "$MASK_PY" "$HOSTNAME_RAW" "$HOSTNAME_SHORT" "${HOME:-/home/unknown}"
}

json_string() {
  # Emits a JSON string literal for stdin, masked. Escaping is done by python3 rather than by hand
  # because a stray backslash in a mount error message is exactly the input that breaks hand-rolled
  # escaping, and mount error messages are the point of this script.
  mask | python3 -c 'import json,sys; sys.stdout.write(json.dumps(sys.stdin.read().rstrip("\n")))'
}

str_of() { printf '%s' "$1" | json_string; }

# ------------------------------------------------------------------ probes

tcp_check() {
  # $1 host, $2 port. Prints open, refused, timeout, unresolved or error.
  python3 - "$1" "$2" <<'PY'
import socket
import sys

host, port = sys.argv[1], int(sys.argv[2])
try:
    infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
except socket.gaierror:
    print("unresolved")
    sys.exit()
family, socktype, proto, _, sockaddr = infos[0]
sock = socket.socket(family, socktype, proto)
sock.settimeout(4)
try:
    sock.connect(sockaddr)
    print("open")
except socket.timeout:
    print("timeout")
except ConnectionRefusedError:
    print("refused")
except OSError as exc:
    print(f"error:{exc.errno}")
finally:
    sock.close()
PY
}

resolve_check() {
  # $1 name. Prints "resolved:<addr>" or "unresolved:<reason>". Uses the system resolver on purpose:
  # a dig against a nameserver the client does not actually use answers a different question.
  python3 - "$1" <<'PY'
import socket
import sys

name = sys.argv[1]
try:
    print("resolved:" + socket.getaddrinfo(name, None, family=socket.AF_INET)[0][4][0])
except socket.gaierror as exc:
    print(f"unresolved:{exc.strerror or exc}")
PY
}

OS_NAME="$(uname -s)"
KERNEL="$(uname -r)"
ARCH="$(uname -m)"

IS_WSL="false"
WSL_MODE="not_applicable"
WSL_VERSION="not_applicable"
if [ -r /proc/sys/kernel/osrelease ] &&
    grep -qiE 'microsoft|wsl' /proc/sys/kernel/osrelease 2>/dev/null; then
  IS_WSL="true"
  # Mirrored mode is what makes WSL2 share the Windows host's interfaces, including a VPN one. It is
  # opt-in through /etc/wsl.conf or .wslconfig on the Windows side, and this only sees the former --
  # so "nat_or_unset" means exactly that, not "NAT confirmed".
  if [ -r /etc/wsl.conf ] && grep -qE '^[[:space:]]*networkingMode[[:space:]]*=' /etc/wsl.conf 2>/dev/null; then
    WSL_MODE="$(sed -n 's/^[[:space:]]*networkingMode[[:space:]]*=[[:space:]]*//p' /etc/wsl.conf | head -1)"
  else
    WSL_MODE="nat_or_unset"
  fi
  if command -v wsl.exe >/dev/null 2>&1; then
    WSL_VERSION="$(wsl.exe --version 2>/dev/null | tr -d '\r' | head -1 || echo unknown)"
  else
    WSL_VERSION="wsl.exe_not_on_path"
  fi
fi

OS_VERSION="unknown"
case "$OS_NAME" in
  Darwin) OS_VERSION="$(sw_vers -productVersion 2>/dev/null || echo unknown)" ;;
  Linux)
    if [ -r /etc/os-release ]; then
      OS_VERSION="$(sed -n 's/^PRETTY_NAME="\{0,1\}//p' /etc/os-release | tr -d '"' | head -1)"
    fi
    ;;
esac

# --- iSCSI. The interesting answer here is an absence.
ISCSI_TOOL="absent"
ISCSI_INITIATOR="none"
ISCSI_MODULE="not_tested"
if command -v iscsiadm >/dev/null 2>&1; then
  ISCSI_TOOL="iscsiadm"
elif command -v iscsictl >/dev/null 2>&1; then
  ISCSI_TOOL="iscsictl"
fi
if [ -r /etc/iscsi/initiatorname.iscsi ]; then
  ISCSI_INITIATOR="$(sed -n 's/^InitiatorName=//p' /etc/iscsi/initiatorname.iscsi | head -1)"
  [ -n "$ISCSI_INITIATOR" ] || ISCSI_INITIATOR="file_present_but_empty"
fi
if [ "$OS_NAME" = "Linux" ]; then
  if lsmod 2>/dev/null | grep -q '^iscsi_tcp'; then
    ISCSI_MODULE="loaded"
  elif modprobe -n iscsi_tcp >/dev/null 2>&1; then
    ISCSI_MODULE="loadable"
  else
    ISCSI_MODULE="unavailable"
  fi
fi

# --- name resolution and reachability
DNS_RESULT="not_tested"
[ -n "$SVM_DNS" ] && DNS_RESULT="$(resolve_check "$SVM_DNS")"

port_result() {
  # $1 host (may be empty), $2 port
  if [ -z "$1" ]; then printf 'not_tested'; else tcp_check "$1" "$2"; fi
}

SMB_445="$(port_result "$SMB_IP" 445)"
NFS_2049="$(port_result "$NFS_IP" 2049)"
NFS_111="$(port_result "$NFS_IP" 111)"
NFS_635="$(port_result "$NFS_IP" 635)"
ISCSI_3260="$(port_result "$ISCSI_IP" 3260)"

# --- S3 Access Point
S3_RESULT="not_tested"
if [ -n "$S3_ACCESS_POINT" ]; then
  if command -v aws >/dev/null 2>&1; then
    if S3_OUT="$(aws s3api list-objects-v2 --bucket "$S3_ACCESS_POINT" --max-items 1 2>&1)"; then
      S3_RESULT="ok"
    else
      # The whole message is kept, masked. Which error it is decides the diagnosis: an endpoint
      # problem, an authorization problem and a name-resolution problem all read as a failed list.
      S3_RESULT="failed: $(printf '%s' "$S3_OUT" | tr '\n' ' ' | cut -c1-400)"
    fi
  else
    S3_RESULT="aws_cli_absent"
  fi
fi

# --- mounts
NFS_MOUNT="not_tested"
SMB_MOUNT="not_tested"
CLEANUP_DIRS=""

cleanup() {
  for d in $CLEANUP_DIRS; do
    if mount | grep -q " $d "; then umount "$d" >/dev/null 2>&1 || true; fi
    rmdir "$d" >/dev/null 2>&1 || true
  done
  if [ -n "${CRED_FILE:-}" ]; then rm -f "$CRED_FILE"; fi
  # An explicit success. A trap on EXIT whose last command fails sets the script's exit status, so
  # the earlier `[ -n "$CRED_FILE" ] && rm` here made every clean run exit 1 while printing a
  # perfectly valid record -- a failure signal with nothing failing behind it.
  return 0
}
trap cleanup EXIT

if [ "$TRY_MOUNT" = "true" ]; then
  BASE_DIR="${MOUNT_BASE:-$(mktemp -d)}"
  mkdir -p "$BASE_DIR"

  if [ -n "$NFS_IP" ] && [ -n "$NFS_JUNCTION" ]; then
    NFS_DIR="$BASE_DIR/nfs"
    mkdir -p "$NFS_DIR"
    CLEANUP_DIRS="$CLEANUP_DIRS $NFS_DIR"
    if NFS_ERR="$(mount -t nfs -o nfsvers=4.1 "$NFS_IP:$NFS_JUNCTION" "$NFS_DIR" 2>&1)"; then
      NFS_MOUNT="mounted"
    else
      NFS_MOUNT="failed: $(printf '%s' "$NFS_ERR" | tr '\n' ' ' | cut -c1-400)"
    fi
  fi

  if [ -n "$SMB_IP" ] && [ -n "$SHARE_NAME" ] && [ -n "$SMB_USER" ]; then
    SMB_DIR="$BASE_DIR/smb"
    mkdir -p "$SMB_DIR"
    CLEANUP_DIRS="$CLEANUP_DIRS $SMB_DIR"
    if [ "$OS_NAME" = "Darwin" ]; then
      # mount_smbfs prompts on the terminal. That is the reason it is used this way: putting the
      # password in the URL would put it in the argument list, where ps shows it to every user.
      echo "probe-endpoint: mount_smbfs will prompt for the password for $SMB_USER" >&2
      if SMB_ERR="$(mount_smbfs "//${SMB_USER}@${SMB_IP}/${SHARE_NAME}" "$SMB_DIR" 2>&1)"; then
        SMB_MOUNT="mounted"
      else
        SMB_MOUNT="failed: $(printf '%s' "$SMB_ERR" | tr '\n' ' ' | cut -c1-400)"
      fi
    else
      CRED_FILE="$(mktemp)"
      chmod 600 "$CRED_FILE"
      echo "probe-endpoint: reading the SMB password from standard input" >&2
      IFS= read -r SMB_PW || SMB_PW=""
      {
        printf 'username=%s\n' "${SMB_USER##*\\}"
        printf 'password=%s\n' "$SMB_PW"
      } > "$CRED_FILE"
      unset SMB_PW
      if SMB_ERR="$(mount -t cifs -o "credentials=$CRED_FILE,vers=3.1.1" \
          "//${SMB_IP}/${SHARE_NAME}" "$SMB_DIR" 2>&1)"; then
        SMB_MOUNT="mounted"
      else
        SMB_MOUNT="failed: $(printf '%s' "$SMB_ERR" | tr '\n' ' ' | cut -c1-400)"
      fi
    fi
  fi
fi

# ------------------------------------------------------------------ record

TIMESTAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

RECORD="$(cat <<JSON
{
  "schema": "fsxn-client-access-probe/1",
  "recorded_at": $(str_of "$TIMESTAMP"),
  "environment": {
    "os": $(str_of "$OS_NAME"),
    "os_version": $(str_of "$OS_VERSION"),
    "kernel": $(str_of "$KERNEL"),
    "arch": $(str_of "$ARCH"),
    "is_wsl": $IS_WSL,
    "wsl_networking_mode": $(str_of "$WSL_MODE"),
    "wsl_version": $(str_of "$WSL_VERSION")
  },
  "name_resolution": {
    "svm_dns_queried": $(str_of "${SVM_DNS:-not_tested}"),
    "result": $(str_of "$DNS_RESULT")
  },
  "reachability": {
    "smb_445": $(str_of "$SMB_445"),
    "nfs_2049": $(str_of "$NFS_2049"),
    "nfs_111": $(str_of "$NFS_111"),
    "nfs_635": $(str_of "$NFS_635"),
    "iscsi_3260": $(str_of "$ISCSI_3260")
  },
  "block": {
    "initiator_tool": $(str_of "$ISCSI_TOOL"),
    "initiator_name": $(str_of "$ISCSI_INITIATOR"),
    "iscsi_tcp_module": $(str_of "$ISCSI_MODULE")
  },
  "object": {
    "access_point_list_objects": $(str_of "$S3_RESULT")
  },
  "mounts": {
    "nfs": $(str_of "$NFS_MOUNT"),
    "smb": $(str_of "$SMB_MOUNT")
  },
  "notes": {
    "masking": "Host names, IPv4 host octets, file system and SVM identifiers, 12-digit account numbers, IQN host parts and the home path are replaced at write time.",
    "not_tested_meaning": "A field reading not_tested was not attempted. It is not a failure.",
    "throughput": "Deliberately absent. Measured over a VPN it would describe the tunnel and this endpoint's own network rather than the file system."
  }
}
JSON
)"

if [ -n "$OUT_FILE" ]; then
  printf '%s\n' "$RECORD" > "$OUT_FILE"
  echo "probe-endpoint: wrote $OUT_FILE" >&2
else
  printf '%s\n' "$RECORD"
fi
