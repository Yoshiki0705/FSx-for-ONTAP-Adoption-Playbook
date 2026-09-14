#!/usr/bin/env bash
#
# Make an Amazon FSx for NetApp ONTAP file system serve SMB, NFS and iSCSI to a physical endpoint.
#
# Everything this script creates sits outside the Amazon FSx API: an SMB server in a workgroup, a
# local SMB user, an SMB share, an NFS export policy and rule, a LUN, an igroup and a LUN map. None
# of them has a CloudFormation resource type either, which is why this example is a template plus a
# script rather than one artifact.
#
# RUN IT FROM THE ENDPOINT, over the same route the data will use. That is deliberate: reaching the
# ONTAP REST API on 443 proves the route before any mount is attempted, and the failure it produces
# when the route is wrong is legible ("connection timed out") instead of arriving later as a mount
# that hangs.
#
# The script is idempotent. Every step reads current state first and creates only what is missing.
#
# NO ACTIVE DIRECTORY. The SMB server is created in a workgroup, which AWS documents as an option
# for FSx for ONTAP. Workgroup mode gives up SMB3 Witness, continuously-available shares, SQL over
# SMB, folder redirection, roaming profiles, Group Policy and Volume Shadow Copy Service. If any of
# those matter, this is the wrong example - see examples/multiprotocol-ad/, which joins a domain.
#
# Passwords are read from AWS Secrets Manager or from standard input, never from an argument, because
# arguments are visible to every user on the host through ps.
#
# Requires: curl, jq. Also aws, unless both --management-ip and --password-stdin are used.

set -euo pipefail

FILE_SYSTEM_ID=""
MGMT_IP_ARG=""
SVM=""
SMB_VOLUME=""
NFS_VOLUME=""
LUN_VOLUME=""
CLIENT_CIDR=""
SECRET_ID=""
PASSWORD_STDIN="false"
SMB_SECRET_ID=""
SMB_PASSWORD_STDIN="false"
SMB_USER="clientuser"
WORKGROUP="WORKGROUP"
SMB_SERVER_NAME=""
SHARE_NAME="clientshare"
LUN_NAME="lun1"
LUN_SIZE="5G"
LUN_OS_TYPE="linux"
IGROUP=""
INITIATOR=""
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
CHECK_ONLY="false"
SKIP_BLOCK="false"

usage() {
  cat <<'USAGE'
Usage: provision-client-access.sh (--file-system-id fs-... | --management-ip IP)
         --svm NAME --smb-volume NAME --nfs-volume NAME --lun-volume NAME
         --client-cidr CIDR
         (--secret-id NAME | --password-stdin)
         (--smb-secret-id NAME | --smb-password-stdin)
         [--smb-user NAME] [--workgroup NAME] [--smb-server-name NAME] [--share-name NAME]
         [--lun-name NAME] [--lun-size SIZE] [--lun-os-type TYPE] [--igroup NAME]
         [--initiator IQN] [--skip-block] [--region REGION] [--check]

Required:
  --svm            SVM name. Output SvmName of the base stack.
  --smb-volume     NTFS-style volume for the SMB share. Output SmbVolumeName.
  --nfs-volume     UNIX-style volume for NFS. Output NfsVolumeName.
  --lun-volume     Volume that will hold the LUN. Output LunVolumeName.
  --client-cidr    CIDR the endpoint connects from. For AWS Client VPN this is the endpoint's client
                   CIDR block, not your home or office network. It becomes the NFS export rule's
                   client match, so a value copied from the wrong place produces an access denial
                   that looks like a permissions problem.

  How to reach ONTAP, one of:
  --file-system-id Resolved through the Amazon FSx API, which the endpoint needs a route to. Over a
                   split-tunnel VPN it usually has one, because the API resolves to public addresses
                   and split tunnel leaves that traffic on the endpoint's own network.
  --management-ip  The ONTAP management address directly. Get it once from wherever your AWS CLI has
                   reach:
                     aws fsx describe-file-systems --file-system-ids fs-... \
                       --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]'

  The fsxadmin password, one of:
  --secret-id      Secrets Manager secret whose SecretString JSON has a "password" key.
  --password-stdin Read it from standard input, first line.

  The local SMB user password, one of:
  --smb-secret-id     Secrets Manager secret whose SecretString JSON has a "password" key. Use a
                      DIFFERENT secret from the fsxadmin one: this password goes to whoever mounts
                      the share, and fsxadmin administers the whole file system.
  --smb-password-stdin Read it from standard input, second line. With --password-stdin as well, feed
                      both on standard input in that order.

Optional:
  --smb-user        Local SMB user to create. Default: clientuser
  --workgroup       Workgroup name. Default: WORKGROUP
  --smb-server-name SMB server NetBIOS name. Default: derived from the SVM name, upper-cased and
                    truncated to 15 characters, which is the ONTAP limit.
  --share-name      SMB share name. Default: clientshare
  --lun-name        LUN name. Default: lun1
  --lun-size        LUN size the ONTAP REST API accepts, for example 5G. Default: 5G
  --lun-os-type     LUN and igroup os_type. Default: linux. For a Windows endpoint pass
                    windows_2008 -- that is the value for Windows of any version; windows_2022 does
                    not exist.
  --igroup          igroup name. Default: ig_<trailing component of the initiator IQN>.
  --initiator       Initiator IQN to place in the igroup. Read from the endpoint if not given:
                    /etc/iscsi/initiatorname.iscsi on Linux and WSL2. On Windows get it with
                    (Get-InitiatorPort).NodeAddress and pass it here. On macOS there is no
                    initiator at all, so use --skip-block.
  --skip-block      Skip the LUN, igroup and LUN map. Use this from a Mac: macOS ships no iSCSI
                    initiator, so there is nothing to map a LUN to.
  --region          AWS region. Defaults to AWS_REGION or AWS_DEFAULT_REGION.
  --check           Report current state and exit without creating anything.

The script prints what it created and what already existed, so a second run is visibly a no-op.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --file-system-id) FILE_SYSTEM_ID="$2"; shift 2 ;;
    --management-ip) MGMT_IP_ARG="$2"; shift 2 ;;
    --svm) SVM="$2"; shift 2 ;;
    --smb-volume) SMB_VOLUME="$2"; shift 2 ;;
    --nfs-volume) NFS_VOLUME="$2"; shift 2 ;;
    --lun-volume) LUN_VOLUME="$2"; shift 2 ;;
    --client-cidr) CLIENT_CIDR="$2"; shift 2 ;;
    --secret-id) SECRET_ID="$2"; shift 2 ;;
    --password-stdin) PASSWORD_STDIN="true"; shift ;;
    --smb-secret-id) SMB_SECRET_ID="$2"; shift 2 ;;
    --smb-password-stdin) SMB_PASSWORD_STDIN="true"; shift ;;
    --smb-user) SMB_USER="$2"; shift 2 ;;
    --workgroup) WORKGROUP="$2"; shift 2 ;;
    --smb-server-name) SMB_SERVER_NAME="$2"; shift 2 ;;
    --share-name) SHARE_NAME="$2"; shift 2 ;;
    --lun-name) LUN_NAME="$2"; shift 2 ;;
    --lun-size) LUN_SIZE="$2"; shift 2 ;;
    --lun-os-type) LUN_OS_TYPE="$2"; shift 2 ;;
    --igroup) IGROUP="$2"; shift 2 ;;
    --initiator) INITIATOR="$2"; shift 2 ;;
    --skip-block) SKIP_BLOCK="true"; shift ;;
    --region) REGION="$2"; shift 2 ;;
    --check) CHECK_ONLY="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "provision-client-access: $*" >&2; exit 1; }

for tool in curl jq; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required but not installed"
done

[ -n "$SVM" ] || die "--svm is required"
[ -n "$SMB_VOLUME" ] || die "--smb-volume is required"
[ -n "$NFS_VOLUME" ] || die "--nfs-volume is required"
[ -n "$LUN_VOLUME" ] || die "--lun-volume is required"
[ -n "$CLIENT_CIDR" ] || die "--client-cidr is required"
[ -n "$FILE_SYSTEM_ID" ] || [ -n "$MGMT_IP_ARG" ] ||
  die "one of --file-system-id or --management-ip is required"
[ -n "$SECRET_ID" ] || [ "$PASSWORD_STDIN" = "true" ] ||
  die "one of --secret-id or --password-stdin is required"
if [ "$CHECK_ONLY" != "true" ]; then
  [ -n "$SMB_SECRET_ID" ] || [ "$SMB_PASSWORD_STDIN" = "true" ] ||
    die "one of --smb-secret-id or --smb-password-stdin is required (the local SMB user needs a
      password, and it must not be an argument)"
fi

if [ -z "$MGMT_IP_ARG" ] || [ -n "$SECRET_ID" ] || [ -n "$SMB_SECRET_ID" ]; then
  command -v aws >/dev/null 2>&1 ||
    die "aws is required unless --management-ip is used with both passwords on standard input"
  [ -n "$REGION" ] || die "--region is required (or set AWS_REGION)"
fi

if [ -z "$SMB_SERVER_NAME" ]; then
  # Upper-cased and cut to 15 characters because that is the ONTAP limit on a CIFS server name. A
  # longer value is refused at creation, after the file system is already billing.
  SMB_SERVER_NAME="$(printf '%s' "$SVM" | tr '[:lower:]' '[:upper:]' | tr -cd '[:alnum:]' | cut -c1-15)"
  [ -n "$SMB_SERVER_NAME" ] || die "could not derive an SMB server name; pass --smb-server-name"
fi

# ------------------------------------------------------------------ endpoint and credentials

if [ -n "$MGMT_IP_ARG" ]; then
  MGMT_IP="$MGMT_IP_ARG"
else
  MGMT_IP="$(aws fsx describe-file-systems \
    --file-system-ids "$FILE_SYSTEM_ID" --region "$REGION" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
    --output text 2>/dev/null || true)"
  if [ -z "$MGMT_IP" ] || [ "$MGMT_IP" = "None" ]; then
    die "could not resolve the management address for $FILE_SYSTEM_ID. If the call timed out, this
      endpoint has no route to the Amazon FSx API; pass --management-ip instead"
  fi
fi

read_secret() {
  aws secretsmanager get-secret-value --secret-id "$1" --region "$REGION" \
    --query SecretString --output text 2>/dev/null | jq -r '.password // empty'
}

if [ "$PASSWORD_STDIN" = "true" ]; then
  IFS= read -r PASSWORD || die "no fsxadmin password on standard input"
else
  PASSWORD="$(read_secret "$SECRET_ID")"
  [ -n "$PASSWORD" ] || die "secret '$SECRET_ID' has no 'password' key, or could not be read"
fi

SMB_PASSWORD=""
if [ "$CHECK_ONLY" != "true" ]; then
  if [ "$SMB_PASSWORD_STDIN" = "true" ]; then
    IFS= read -r SMB_PASSWORD || die "no SMB user password on standard input"
  else
    SMB_PASSWORD="$(read_secret "$SMB_SECRET_ID")"
    [ -n "$SMB_PASSWORD" ] ||
      die "secret '$SMB_SECRET_ID' has no 'password' key, or could not be read"
  fi
fi

# ------------------------------------------------------------------ ONTAP REST helpers

BASE="https://$MGMT_IP/api"

# -k is used because the file system presents a self-signed certificate that no public CA has signed.
# The connection is inside the VPC, or inside the VPN tunnel, and the address came from the AWS API.
ontap() {
  # $1 method, $2 path, $3 optional JSON body
  local method="$1" path="$2" body="${3:-}"
  if [ -n "$body" ]; then
    curl -sk -u "fsxadmin:$PASSWORD" -X "$method" -H 'Content-Type: application/json' \
      -d "$body" "$BASE$path"
  else
    curl -sk -u "fsxadmin:$PASSWORD" -X "$method" "$BASE$path"
  fi
}

# Fails loudly on an ONTAP error object instead of letting a later step misread an empty result as
# "nothing exists yet". ONTAP answers with HTTP 2xx and an "error" member for several classes of
# failure, so checking the status code alone is not enough.
ontap_ok() {
  local out
  out="$(ontap "$@")" || die "curl failed calling $2"
  if printf '%s' "$out" | jq -e 'has("error")' >/dev/null 2>&1; then
    die "ONTAP refused $1 $2: $(printf '%s' "$out" | jq -c '.error')"
  fi
  printf '%s' "$out"
}

count_records() { printf '%s' "$1" | jq -r '.num_records // 0'; }

echo "==> ONTAP $MGMT_IP, SVM $SVM"

# Reachability is checked before the first REST call so the failure names its cause. Without this the
# first call fails with "curl failed calling /cluster?fields=version", which says a request did not
# complete and nothing about why -- and "why" is almost always the route, since this script is meant
# to run from an endpoint whose tunnel may not be up. Diagnosing that from the thin message is the
# cost this whole module exists to remove, so it should not be paid inside the module's own tooling.
if ! curl -sk --connect-timeout 8 -o /dev/null "https://$MGMT_IP/api/cluster" 2>/dev/null; then
  die "cannot reach the ONTAP management endpoint at $MGMT_IP on 443.

      This script is meant to run from the endpoint, over the same route the data will use, so a
      failure here is almost certainly the route rather than the credentials. In order:

        1. Is the VPN connected?  The tunnel has to be up before this can work.
        2. Does the client address fall inside the CIDR the security group admits? Compare
           ClientCidr on the file-system stack with ClientCidrBlock on the VPN stack -- a mismatch
           drops the packets silently.
        3. Is there an authorization rule for the target network? A route without one times out.
        4. From inside the VPC the same call should succeed. If it does, the difference is the route."
fi

VERSION="$(ontap_ok GET '/cluster?fields=version' | jq -r '.version.full // "unknown"')"
echo "    $VERSION"

# ------------------------------------------------------------------ current state

CIFS_STATE="$(ontap_ok GET "/protocols/cifs/services?svm.name=$SVM&fields=name,workgroup,enabled")"
NFS_STATE="$(ontap_ok GET "/protocols/nfs/services?svm.name=$SVM&fields=enabled,protocol")"
SHARE_STATE="$(ontap_ok GET "/protocols/cifs/shares?svm.name=$SVM&name=$SHARE_NAME")"
USER_STATE="$(ontap_ok GET "/protocols/cifs/local-users?svm.name=$SVM&name=*$SMB_USER")"
POLICY_NAME="ep_$(printf '%s' "$SVM" | tr -cd '[:alnum:]')"
POLICY_STATE="$(ontap_ok GET "/protocols/nfs/export-policies?svm.name=$SVM&name=$POLICY_NAME")"
ISCSI_STATE="$(ontap_ok GET "/protocols/san/iscsi/services?svm.name=$SVM&fields=enabled")"
LUN_STATE="$(ontap_ok GET "/storage/luns?svm.name=$SVM&name=/vol/$LUN_VOLUME/$LUN_NAME")"

report_state() {
  cat <<STATE
    SMB server        $(count_records "$CIFS_STATE") (want 1, workgroup $WORKGROUP)
    local SMB user    $(count_records "$USER_STATE") (want 1: $SMB_USER)
    SMB share         $(count_records "$SHARE_STATE") (want 1: $SHARE_NAME)
    NFS service       $(count_records "$NFS_STATE") (want 1, enabled)
    export policy     $(count_records "$POLICY_STATE") (want 1: $POLICY_NAME)
    iSCSI service     $(count_records "$ISCSI_STATE") (want 1, enabled)
    LUN               $(count_records "$LUN_STATE") (want 1 unless --skip-block)
STATE
}

echo "==> Current state"
report_state

if [ "$CHECK_ONLY" = "true" ]; then
  echo "==> --check given, nothing created"
  exit 0
fi

# ------------------------------------------------------------------ SMB in a workgroup

if [ "$(count_records "$CIFS_STATE")" = "0" ]; then
  echo "==> Creating SMB server $SMB_SERVER_NAME in workgroup $WORKGROUP"
  ontap_ok POST /protocols/cifs/services "$(jq -nc \
    --arg svm "$SVM" --arg name "$SMB_SERVER_NAME" --arg wg "$WORKGROUP" \
    '{svm:{name:$svm}, name:$name, workgroup:$wg, enabled:true}')" >/dev/null
else
  echo "==> SMB server exists: $(printf '%s' "$CIFS_STATE" | jq -r '.records[0].name')"
fi

if [ "$(count_records "$USER_STATE")" = "0" ]; then
  echo "==> Creating local SMB user $SMB_USER"
  ontap_ok POST /protocols/cifs/local-users "$(jq -nc \
    --arg svm "$SVM" --arg name "$SMB_USER" --arg pw "$SMB_PASSWORD" \
    '{svm:{name:$svm}, name:$name, password:$pw, account_disabled:false}')" >/dev/null

  # Added to BUILTIN\Administrators so the mount succeeds without this example also having to set
  # NTFS ACEs on the volume. That is a deliberate narrowing of scope, not a recommendation: a member
  # of the administrators group bypasses the evaluation that examples/multiprotocol-ad/ exists to
  # measure. Keep this user out of anything that is not a disposable verification.
  #
  # The members endpoint is keyed on the SVM UUID and the group SID, not on their names, so both are
  # looked up first. A failure here is reported and not fatal: the share is still there, and the
  # alternative is setting share and NTFS permissions by hand, which is a legitimate way to finish.
  echo "==> Adding $SMB_USER to BUILTIN\\Administrators (scope narrowing -- see the comment)"
  SVM_UUID="$(ontap_ok GET "/svm/svms?name=$SVM&fields=uuid" | jq -r '.records[0].uuid // empty')"
  GROUP_SID="$(ontap_ok GET "/protocols/cifs/local-groups?svm.name=$SVM&name=BUILTIN%5CAdministrators&fields=sid" \
    | jq -r '.records[0].sid // empty')"
  if [ -n "$SVM_UUID" ] && [ -n "$GROUP_SID" ]; then
    if ontap_ok POST "/protocols/cifs/local-groups/$SVM_UUID/$GROUP_SID/members" \
        "$(jq -nc --arg n "$SMB_SERVER_NAME\\\\$SMB_USER" '{name:$n}')" >/dev/null 2>&1; then
      echo "    added"
    else
      echo "    could not add it; grant the share and NTFS permissions by hand instead"
    fi
  else
    echo "    BUILTIN\\Administrators or the SVM UUID could not be resolved; set permissions by hand"
  fi
else
  echo "==> Local SMB user exists: $SMB_USER"
fi

if [ "$(count_records "$SHARE_STATE")" = "0" ]; then
  echo "==> Creating SMB share $SHARE_NAME on /$SMB_VOLUME"
  ontap_ok POST /protocols/cifs/shares "$(jq -nc \
    --arg svm "$SVM" --arg name "$SHARE_NAME" --arg path "/$SMB_VOLUME" \
    '{svm:{name:$svm}, name:$name, path:$path,
      acls:[{permission:"full_control", type:"windows", user_or_group:"Everyone"}]}')" >/dev/null
  echo "    share ACL is Everyone / full_control. The NTFS ACL on the volume still applies, so this"
  echo "    is not open access -- it is one fewer layer to debug while checking reachability."
else
  echo "==> SMB share exists: $SHARE_NAME"
fi

# ------------------------------------------------------------------ NFS

if [ "$(count_records "$NFS_STATE")" = "0" ]; then
  echo "==> Enabling NFS with v3 and v4.1"
  ontap_ok POST /protocols/nfs/services "$(jq -nc --arg svm "$SVM" \
    '{svm:{name:$svm}, enabled:true,
      protocol:{v3_enabled:true, v40_enabled:false, v41_enabled:true}}')" >/dev/null
else
  echo "==> NFS service exists (enabled=$(printf '%s' "$NFS_STATE" | jq -r '.records[0].enabled'))"
fi

if [ "$(count_records "$POLICY_STATE")" = "0" ]; then
  echo "==> Creating export policy $POLICY_NAME for $CLIENT_CIDR"
  ontap_ok POST /protocols/nfs/export-policies "$(jq -nc \
    --arg svm "$SVM" --arg name "$POLICY_NAME" --arg cidr "$CLIENT_CIDR" \
    '{svm:{name:$svm}, name:$name,
      rules:[{clients:[{match:$cidr}], protocols:["nfs"],
              ro_rule:["sys"], rw_rule:["sys"], superuser:["none"], anonymous_user:"65534"}]}')" \
    >/dev/null
  echo "    superuser is none, so root on the endpoint maps to anonymous. A write as root fails with"
  echo "    EACCES on a UNIX-style volume -- that is the rule working, not the mount being broken."
else
  echo "==> Export policy exists: $POLICY_NAME"
fi

NFS_VOL_UUID="$(ontap_ok GET "/storage/volumes?svm.name=$SVM&name=$NFS_VOLUME&fields=uuid,nas.export_policy.name" \
  | jq -r '.records[0].uuid // empty')"
if [ -n "$NFS_VOL_UUID" ]; then
  CURRENT_POLICY="$(ontap_ok GET "/storage/volumes/$NFS_VOL_UUID?fields=nas.export_policy.name" \
    | jq -r '.nas.export_policy.name // empty')"
  if [ "$CURRENT_POLICY" != "$POLICY_NAME" ]; then
    echo "==> Attaching $POLICY_NAME to volume $NFS_VOLUME (was ${CURRENT_POLICY:-none})"
    ontap_ok PATCH "/storage/volumes/$NFS_VOL_UUID" "$(jq -nc --arg p "$POLICY_NAME" \
      '{nas:{export_policy:{name:$p}}}')" >/dev/null
  else
    echo "==> Volume $NFS_VOLUME already uses $POLICY_NAME"
  fi
else
  echo "==> WARNING: volume $NFS_VOLUME not found; the export policy is not attached to anything"
fi

# ------------------------------------------------------------------ block

if [ "$SKIP_BLOCK" = "true" ]; then
  echo "==> --skip-block given, leaving the LUN, igroup and LUN map alone"
else
  if [ -z "$INITIATOR" ] && [ -r /etc/iscsi/initiatorname.iscsi ]; then
    INITIATOR="$(sed -n 's/^InitiatorName=//p' /etc/iscsi/initiatorname.iscsi | head -1)"
  fi
  if [ -z "$INITIATOR" ]; then
    die "no initiator IQN. On Linux or WSL2 install open-iscsi so
      /etc/iscsi/initiatorname.iscsi exists, on Windows pass the value of
      (Get-InitiatorPort).NodeAddress with --initiator, and on macOS pass --skip-block: macOS
      ships no iSCSI initiator, so there is nothing to map a LUN to"
  fi

  if [ -z "$IGROUP" ]; then
    # From the IQN rather than the hostname: on many machines the hostname identifies the person or
    # the private address, and it would then be embedded in an ONTAP object name.
    IGROUP="ig_$(printf '%s' "${INITIATOR##*:}" | tr -c '[:alnum:]' '_')"
  fi

  if [ "$(count_records "$ISCSI_STATE")" = "0" ]; then
    echo "==> Enabling the iSCSI service"
    ontap_ok POST /protocols/san/iscsi/services "$(jq -nc --arg svm "$SVM" \
      '{svm:{name:$svm}, enabled:true}')" >/dev/null
  else
    echo "==> iSCSI service exists (enabled=$(printf '%s' "$ISCSI_STATE" | jq -r '.records[0].enabled'))"
  fi

  IGROUP_STATE="$(ontap_ok GET "/protocols/san/igroups?svm.name=$SVM&name=$IGROUP&fields=initiators")"
  if [ "$(count_records "$IGROUP_STATE")" = "0" ]; then
    echo "==> Creating igroup $IGROUP with $INITIATOR"
    ontap_ok POST /protocols/san/igroups "$(jq -nc \
      --arg svm "$SVM" --arg name "$IGROUP" --arg iqn "$INITIATOR" --arg os "$LUN_OS_TYPE" \
      '{svm:{name:$svm}, name:$name, os_type:$os, protocol:"iscsi",
        initiators:[{name:$iqn}]}')" >/dev/null
  elif printf '%s' "$IGROUP_STATE" | jq -e --arg iqn "$INITIATOR" \
      '.records[0].initiators // [] | map(.name) | index($iqn)' >/dev/null; then
    echo "==> igroup $IGROUP already contains this initiator"
  else
    echo "==> Adding $INITIATOR to igroup $IGROUP"
    IGROUP_UUID="$(printf '%s' "$IGROUP_STATE" | jq -r '.records[0].uuid')"
    ontap_ok POST "/protocols/san/igroups/$IGROUP_UUID/initiators" \
      "$(jq -nc --arg iqn "$INITIATOR" '{name:$iqn}')" >/dev/null
  fi

  if [ "$(count_records "$LUN_STATE")" = "0" ]; then
    echo "==> Creating LUN /vol/$LUN_VOLUME/$LUN_NAME ($LUN_SIZE)"
    ontap_ok POST /storage/luns "$(jq -nc \
      --arg svm "$SVM" --arg path "/vol/$LUN_VOLUME/$LUN_NAME" \
      --arg size "$LUN_SIZE" --arg os "$LUN_OS_TYPE" \
      '{svm:{name:$svm}, name:$path, os_type:$os, space:{size:$size}}')" >/dev/null
  else
    echo "==> LUN exists: /vol/$LUN_VOLUME/$LUN_NAME"
  fi

  MAP_STATE="$(ontap_ok GET "/protocols/san/lun-maps?svm.name=$SVM&lun.name=/vol/$LUN_VOLUME/$LUN_NAME&igroup.name=$IGROUP")"
  if [ "$(count_records "$MAP_STATE")" = "0" ]; then
    echo "==> Mapping the LUN to $IGROUP"
    ontap_ok POST /protocols/san/lun-maps "$(jq -nc \
      --arg svm "$SVM" --arg lun "/vol/$LUN_VOLUME/$LUN_NAME" --arg ig "$IGROUP" \
      '{svm:{name:$svm}, lun:{name:$lun}, igroup:{name:$ig}}')" >/dev/null
  else
    echo "==> LUN map exists"
  fi
fi

# ------------------------------------------------------------------ what to mount

SVM_IPS="$(ontap_ok GET "/network/ip/interfaces?svm.name=$SVM&fields=name,ip.address,services")"

cat <<REPORT

--------------------------------------------------------------------------
Addresses on SVM $SVM:
$(printf '%s' "$SVM_IPS" | jq -r '.records[] | "    \(.name)\t\(.ip.address)"')

Mount, from the endpoint, over the route this script already used:

  Windows    net use Z: \\\\<smb-ip>\\$SHARE_NAME /user:$SMB_SERVER_NAME\\$SMB_USER
  macOS      mount -t smbfs //$SMB_USER@<smb-ip>/$SHARE_NAME /Volumes/fsxn
  WSL2       sudo mount -t nfs -o nfsvers=4.1 <nfs-ip>:/$NFS_VOLUME /mnt/fsxn

Prefer the SVM DNS name over an address once name resolution works. Confirm it first:
  nslookup <svm-dns-name>
A failure there with the tunnel up means the Client VPN endpoint has no DNS server set, not that
the route is wrong. Mounting by IP succeeds in that state, which is what makes it easy to misread.

Re-run this script to confirm it is a no-op. Nothing above should be created a second time.
REPORT
