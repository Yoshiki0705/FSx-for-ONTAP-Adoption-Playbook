#!/usr/bin/env bash
#
# Check an AWS account and VPC against what this example needs, BEFORE spending 43 minutes on a
# deployment that will not work, and write a parameters file filled in with what was found.
#
# Every check here exists because its absence produced a failure that looked like something else.
# The list is not a general best-practice audit; it is the set of things that were actually measured
# to break this example, in the order they break it.
#
# Nothing in this script creates, modifies or deletes anything. It is read-only by construction:
# every AWS call it makes is a describe or a get.
#
# Requires: aws, jq.
set -euo pipefail

VPC_ID=""
PRIMARY_SUBNET=""
SECOND_SUBNET=""
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
DOMAIN_NAME=""
DOMAIN_SHORT=""
AD_SECRET=""
FSX_SECRET=""
NAME_PREFIX="fsxn-mp-ad"
WRITE_PARAMS=""

usage() {
  cat <<'USAGE'
Usage: preflight.sh --vpc-id vpc-... --primary-subnet subnet-... --second-subnet subnet-...
                    --domain-name corp.example.com --domain-short-name CORP
                    [--ad-secret NAME] [--fsx-secret NAME] [--name-prefix PREFIX]
                    [--region REGION] [--write-params FILE]

Read-only. Reports PASS / WARN / FAIL per check and exits non-zero if anything FAILs.

Required:
  --vpc-id          The VPC to deploy into.
  --primary-subnet  Subnet for the file system and both clients.
  --second-subnet   Subnet in a DIFFERENT Availability Zone. Used only by AWS Managed Microsoft AD,
                    which always deploys two domain controllers. The file system stays Single-AZ.
  --domain-name     The Active Directory domain to create, for example corp.example.com.
  --domain-short-name  Its NetBIOS name, for example CORP.
Optional:
  --ad-secret       Secrets Manager secret holding {"password": "..."} for the directory Admin.
  --fsx-secret      Secrets Manager secret holding {"password": "..."} for fsxadmin.
                    Both are checked for existence and shape when given.
  --name-prefix     Defaults to fsxn-mp-ad. Checked against the NetBIOS length limit.
  --write-params    Write a CloudFormation parameters JSON file here, filled in with the values
                    given and with the organizational unit derived from the domain. Read it before
                    using it; it is a starting point, not a decision.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --vpc-id) VPC_ID="$2"; shift 2 ;;
    --primary-subnet) PRIMARY_SUBNET="$2"; shift 2 ;;
    --second-subnet) SECOND_SUBNET="$2"; shift 2 ;;
    --domain-name) DOMAIN_NAME="$2"; shift 2 ;;
    --domain-short-name) DOMAIN_SHORT="$2"; shift 2 ;;
    --ad-secret) AD_SECRET="$2"; shift 2 ;;
    --fsx-secret) FSX_SECRET="$2"; shift 2 ;;
    --name-prefix) NAME_PREFIX="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --write-params) WRITE_PARAMS="$2"; shift 2 ;;
    -h | --help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "preflight: $*" >&2; exit 1; }
for tool in aws jq; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required but not installed"
done
[ -n "$VPC_ID" ] || die "--vpc-id is required"
[ -n "$PRIMARY_SUBNET" ] || die "--primary-subnet is required"
[ -n "$SECOND_SUBNET" ] || die "--second-subnet is required"
[ -n "$DOMAIN_NAME" ] || die "--domain-name is required"
[ -n "$DOMAIN_SHORT" ] || die "--domain-short-name is required"
[ -n "$REGION" ] || die "--region is required (or set AWS_REGION)"

FAILURES=0
WARNINGS=0
pass() { printf '  \033[0;32mPASS\033[0m  %s\n' "$*"; }
warn() { printf '  \033[0;33mWARN\033[0m  %s\n' "$*"; WARNINGS=$((WARNINGS + 1)); }
fail() { printf '  \033[0;31mFAIL\033[0m  %s\n' "$*"; FAILURES=$((FAILURES + 1)); }
note() { printf '        %s\n' "$*"; }
aws_q() { aws "$@" --region "$REGION"; }

echo "== identity and region =="
CALLER="$(aws_q sts get-caller-identity --query 'Arn' --output text 2>&1)" ||
  die "could not call sts get-caller-identity. Check credentials for region $REGION"
# Neither the account id nor the principal name is printed. Neither is needed to read the result,
# and both end up in terminal scrollback, screenshots and pasted issue reports. Only the kind of
# principal is shown, because "am I running as the role I meant to?" is a real question.
CALLER_KIND="${CALLER##*:}"
CALLER_KIND="${CALLER_KIND%%/*}"
pass "credentials resolve, region $REGION"
note "principal type: ${CALLER_KIND:-unknown} (identifiers deliberately not printed)"

echo
echo "== VPC DNS attributes =="
# Private DNS on an interface endpoint does nothing unless both of these are on. Without them the
# instance keeps resolving the public address and keeps timing out, so the endpoint exists and
# changes nothing -- a failure that looks like a network problem rather than a VPC setting.
# The attribute name and the response key differ only in the first letter, which invites ${attr^} --
# and that is a bash 4 expansion. macOS still ships bash 3.2, so a reader running this on a Mac would
# get "bad substitution" on line 1 of the first real check. Both pairs are written out instead.
# Nothing in these scripts may use ${var^}, ${var,,} or associative arrays for the same reason.
for pair in "enableDnsSupport:EnableDnsSupport" "enableDnsHostnames:EnableDnsHostnames"; do
  attr="${pair%%:*}"
  key="${pair##*:}"
  v="$(aws_q ec2 describe-vpc-attribute --vpc-id "$VPC_ID" --attribute "$attr" \
    --query "${key}.Value" --output text 2>&1 || echo error)"
  case "$v" in
    True | true) pass "$attr is enabled" ;;
    *) fail "$attr is '$v'. Interface endpoint private DNS will not resolve" ;;
  esac
done

echo
echo "== subnets and Availability Zones =="
AZ1="$(aws_q ec2 describe-subnets --subnet-ids "$PRIMARY_SUBNET" \
  --query 'Subnets[0].AvailabilityZone' --output text 2>&1 || echo error)"
AZ2="$(aws_q ec2 describe-subnets --subnet-ids "$SECOND_SUBNET" \
  --query 'Subnets[0].AvailabilityZone' --output text 2>&1 || echo error)"
CIDR1="$(aws_q ec2 describe-subnets --subnet-ids "$PRIMARY_SUBNET" \
  --query 'Subnets[0].CidrBlock' --output text 2>&1 || echo error)"
if [ "$AZ1" = "$AZ2" ]; then
  fail "both subnets are in $AZ1. AWS Managed Microsoft AD requires two Availability Zones and
        always deploys two domain controllers; this is not reducible to one"
else
  pass "subnets span $AZ1 and $AZ2"
fi
note "client subnet CIDR $CIDR1 -- this is the value for --client-match in provision-multiprotocol.sh"

echo
echo "== egress for the two AWS APIs the instances call themselves =="
# The SVMs join Active Directory from the service side and never traverse the VPC. The INSTANCES do
# the opposite: the domain-join document and the scripts call AWS APIs from the instance. So a VPC
# that is fine for the file system can still leave both clients unjoined.
RT="$(aws_q ec2 describe-route-tables --filters "Name=association.subnet-id,Values=$PRIMARY_SUBNET" \
  --query 'RouteTables[0].RouteTableId' --output text 2>/dev/null || echo None)"
if [ "$RT" = "None" ] || [ -z "$RT" ]; then
  RT="$(aws_q ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" \
    "Name=association.main,Values=true" --query 'RouteTables[0].RouteTableId' --output text)"
  note "no explicit subnet association; using the main route table $RT"
fi
DEFAULT_TARGET="$(aws_q ec2 describe-route-tables --route-table-ids "$RT" \
  --query "RouteTables[0].Routes[?DestinationCidrBlock=='0.0.0.0/0'].[GatewayId,NatGatewayId]" \
  --output text 2>/dev/null | tr '\t' ' ' | tr -s ' ')"
MAP_PUBLIC="$(aws_q ec2 describe-subnets --subnet-ids "$PRIMARY_SUBNET" \
  --query 'Subnets[0].MapPublicIpOnLaunch' --output text)"
HAS_NAT="no"
case "$DEFAULT_TARGET" in *nat-*) HAS_NAT="yes" ;; esac
ENDPOINTS="$(aws_q ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'VpcEndpoints[].ServiceName' --output text 2>/dev/null || true)"
have_endpoint() { grep -q "\.${1}\$\|\.${1}[[:space:]]" <<<"$ENDPOINTS "; }

note "default route target: ${DEFAULT_TARGET:-none}; MapPublicIpOnLaunch=$MAP_PUBLIC"
if [ "$HAS_NAT" = "yes" ]; then
  pass "a NAT gateway serves the default route; the instances can reach any AWS API"
  note "you may set CreateClientVpcEndpoints=false"
else
  for svc in ds fsx ssm ssmmessages ec2messages secretsmanager; do
    if have_endpoint "$svc"; then
      pass "interface endpoint present for $svc"
    else
      case "$svc" in
        # ds and fsx are WARN, not FAIL, because this template creates both when
        # CreateClientVpcEndpoints is true, which is the default. Reporting them as FAIL would block
        # a deployment that is about to succeed -- a check that cries wolf gets switched off, and
        # then it is not there for the reader who really has set the parameter to false.
        ds) warn "no route to the Directory Service API today: no NAT gateway and no ds endpoint.
        Harmless if you leave CreateClientVpcEndpoints=true, which creates it. If you set it to
        false, both clients WILL fail the domain join: 'Connect timeout on endpoint URL
        https://ds.${REGION}.amazonaws.com' on Linux, a ConnectFailure WebException on Windows,
        while Systems Manager and package installs keep working -- so every other signal will say
        the hosts are healthy" ;;
        fsx) warn "no route to the Amazon FSx API today. Also created by
        CreateClientVpcEndpoints=true. Without it the scripts still work via --management-ip, but the
        rehost probe cannot measure how long the AWS control plane takes to notice" ;;
        # These four are FAIL because the template does NOT create them. Nothing downstream will
        # fix them for you.
        ssm | ssmmessages | ec2messages) fail "no route to $svc, and this template does not create
        it. Session Manager will not connect, and the domain join runs through Systems Manager" ;;
        secretsmanager) fail "no route to Secrets Manager, and this template does not create it. The
        scripts read the fsxadmin and Admin passwords from it, and the alternative is passing
        passwords on a command line, which this example refuses to document" ;;
      esac
    fi
  done
  if [ "$MAP_PUBLIC" = "False" ] || [ "$MAP_PUBLIC" = "false" ]; then
    case "$DEFAULT_TARGET" in
      *igw-*) note "the default route is an internet gateway but instances get no public IP, so
        there is no egress despite the route. This is the exact shape that made the domain join fail
        while everything else looked healthy" ;;
    esac
  fi
fi

echo
echo "== AWS Managed Microsoft AD =="
LIMITS="$(aws_q ds get-directory-limits --output json 2>&1 || echo '{}')"
CUR="$(jq -r '.DirectoryLimits.CloudOnlyMicrosoftADCurrentCount // "unknown"' <<<"$LIMITS")"
MAX="$(jq -r '.DirectoryLimits.CloudOnlyMicrosoftADLimit // "unknown"' <<<"$LIMITS")"
if [ "$CUR" != "unknown" ] && [ "$MAX" != "unknown" ]; then
  if [ "$CUR" -lt "$MAX" ]; then
    pass "directory quota $CUR/$MAX in use"
  else
    fail "directory quota $CUR/$MAX is exhausted; the stack will fail after the file system is built"
  fi
else
  warn "could not read the directory quota; check ds:GetDirectoryLimits permission"
fi
EXISTING="$(aws_q ds describe-directories \
  --query "DirectoryDescriptions[?Name=='${DOMAIN_NAME}'].DirectoryId" --output text 2>/dev/null || true)"
if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
  fail "a directory for $DOMAIN_NAME already exists ($EXISTING). Choose another domain name or reuse it"
else
  pass "no existing directory named $DOMAIN_NAME"
fi

echo
echo "== leftovers from a previous run of this example =="
# A previous run that was torn down incompletely is a different problem from a fresh account, and it
# fails later and less clearly: a surviving security group blocks nothing until deletion, a surviving
# endpoint bills quietly, and a surviving stack in a ROLLBACK state cannot be updated.
LEFTOVER_STACK="$(aws_q cloudformation describe-stacks --stack-name "$NAME_PREFIX" \
  --query 'Stacks[0].StackStatus' --output text 2>/dev/null || true)"
if [ -n "$LEFTOVER_STACK" ] && [ "$LEFTOVER_STACK" != "None" ]; then
  case "$LEFTOVER_STACK" in
    *ROLLBACK_COMPLETE | *FAILED)
      fail "a stack named $NAME_PREFIX exists in $LEFTOVER_STACK. It cannot be updated from that
        state; delete it first" ;;
    *) fail "a stack named $NAME_PREFIX already exists ($LEFTOVER_STACK). Choose another
        --name-prefix or remove it" ;;
  esac
else
  pass "no stack named $NAME_PREFIX"
fi
LEFTOVER_SG="$(aws_q ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" \
  "Name=tag:Name,Values=${NAME_PREFIX}-*" --query 'SecurityGroups[].GroupId' --output text 2>/dev/null || true)"
if [ -n "$LEFTOVER_SG" ]; then
  warn "security groups tagged ${NAME_PREFIX}-* still exist: $LEFTOVER_SG"
  note "usually the residue of a teardown that failed on a group something else was holding"
else
  pass "no leftover security groups tagged ${NAME_PREFIX}-*"
fi
LEFTOVER_EP="$(aws_q ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:DeleteManually,Values=not-in-cloudformation" \
  --query 'VpcEndpoints[].[VpcEndpointId,ServiceName]' --output text 2>/dev/null || true)"
if [ -n "$LEFTOVER_EP" ]; then
  warn "interface endpoints tagged as manually managed still exist, and bill hourly:"
  printf '        %s\n' "$LEFTOVER_EP"
else
  pass "no endpoints tagged DeleteManually"
fi

echo
echo "== names and NetBIOS limits =="
if [ "${#DOMAIN_SHORT}" -le 15 ]; then
  pass "domain NetBIOS name '$DOMAIN_SHORT' is ${#DOMAIN_SHORT} characters"
else
  fail "domain NetBIOS name '$DOMAIN_SHORT' is ${#DOMAIN_SHORT} characters; the limit is 15"
fi
# The template derives each SVM's NetBIOS name from the prefix. A NetBIOS name that collides with the
# domain's own NetBIOS name is rejected at SVM creation, and the derived names must also fit in 15.
for suffix in src dst; do
  derived="$(tr -d '-' <<<"${NAME_PREFIX}${suffix}" | tr '[:lower:]' '[:upper:]')"
  if [ "${#derived}" -gt 15 ]; then
    fail "derived SVM NetBIOS name '$derived' is ${#derived} characters; shorten --name-prefix"
  elif [ "$derived" = "$DOMAIN_SHORT" ]; then
    fail "derived SVM NetBIOS name '$derived' equals the domain NetBIOS name; they must differ"
  else
    pass "derived SVM NetBIOS name '$derived' is usable"
  fi
done

echo
echo "== organizational unit path =="
# AWS Managed Microsoft AD inserts an intermediate OU named after the NetBIOS name. Omitting it is
# the single most common reason an SVM reports CREATED while no domain user can authenticate.
DC_PART="$(sed 's/^/DC=/; s/\./,DC=/g' <<<"$DOMAIN_NAME")"
OU_SUGGESTED="OU=Computers,OU=${DOMAIN_SHORT},${DC_PART}"
note "use exactly: $OU_SUGGESTED"
note "omitting the intermediate OU=${DOMAIN_SHORT} is the usual cause of an SVM that looks joined"
note "and is not. Verify the join by the discovered domain controller count, never by Lifecycle."

echo
echo "== secrets =="
check_secret() {
  local id="$1" label="$2" minlen="$3" maxlen="$4"
  [ -n "$id" ] || { note "$label secret not given, skipped"; return; }
  local s
  s="$(aws_q secretsmanager get-secret-value --secret-id "$id" --query SecretString --output text 2>&1)" || {
    fail "$label secret '$id' cannot be read: $(head -c 120 <<<"$s")"
    return
  }
  local pw
  pw="$(jq -r '.password // empty' <<<"$s" 2>/dev/null || true)"
  if [ -z "$pw" ]; then
    fail "$label secret '$id' has no 'password' key. The template resolves
        {{resolve:secretsmanager:<name>:SecretString:password}}, so the key name is not optional"
    return
  fi
  if [ "${#pw}" -lt "$minlen" ] || [ "${#pw}" -gt "$maxlen" ]; then
    fail "$label password is ${#pw} characters; the accepted range is ${minlen}-${maxlen}"
  else
    pass "$label secret '$id' has a password key of ${#pw} characters"
  fi
  local classes=0
  grep -q '[a-z]' <<<"$pw" && classes=$((classes + 1))
  grep -q '[A-Z]' <<<"$pw" && classes=$((classes + 1))
  grep -q '[0-9]' <<<"$pw" && classes=$((classes + 1))
  grep -q '[^a-zA-Z0-9]' <<<"$pw" && classes=$((classes + 1))
  if [ "$label" = "directory Admin" ] && [ "$classes" -lt 3 ]; then
    fail "directory Admin password uses $classes of the four character classes; three are required"
  fi
}
check_secret "$AD_SECRET" "directory Admin" 8 64
check_secret "$FSX_SECRET" "fsxadmin" 8 50

echo
echo "== summary =="
printf '  %d FAIL, %d WARN\n' "$FAILURES" "$WARNINGS"
if [ -n "$WRITE_PARAMS" ]; then
  jq -n --arg vpc "$VPC_ID" --arg s1 "$PRIMARY_SUBNET" --arg s2 "$SECOND_SUBNET" \
    --arg dn "$DOMAIN_NAME" --arg ds "$DOMAIN_SHORT" --arg ou "$OU_SUGGESTED" \
    --arg ad "${AD_SECRET:-mpad-ad-admin}" --arg fx "${FSX_SECRET:-mpad-fsxadmin}" \
    --arg np "$NAME_PREFIX" \
    '[{ParameterKey:"VpcId",ParameterValue:$vpc},
      {ParameterKey:"PrimarySubnetId",ParameterValue:$s1},
      {ParameterKey:"SecondAzSubnetId",ParameterValue:$s2},
      {ParameterKey:"DomainName",ParameterValue:$dn},
      {ParameterKey:"DomainShortName",ParameterValue:$ds},
      {ParameterKey:"OrganizationalUnitDistinguishedName",ParameterValue:$ou},
      {ParameterKey:"AdAdminSecretName",ParameterValue:$ad},
      {ParameterKey:"FsxAdminSecretName",ParameterValue:$fx},
      {ParameterKey:"NamePrefix",ParameterValue:$np}]' >"$WRITE_PARAMS"
  echo "  wrote $WRITE_PARAMS"
  note "a parameters FILE, not the ParameterKey=...,ParameterValue=... shorthand: the shorthand"
  note "splits on commas and a distinguished name is full of them, which fails before the template"
  note "is ever validated and so reads as a template error."
fi
if [ "$FAILURES" -gt 0 ]; then
  echo "  Do not deploy yet. Each FAIL above produces a failure that presents as something else."
  exit 1
fi
echo "  No blocking findings. Read the Cost section before deploying, and fix a teardown date."
