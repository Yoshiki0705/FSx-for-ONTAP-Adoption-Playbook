#!/usr/bin/env bash
#
# Tear down the multiprotocol AD example, in the order that was measured to work, and prove
# afterwards that nothing is left behind.
#
# WHY THIS IS A SCRIPT AND NOT A LIST OF COMMANDS IN A README
#
# The first teardown of this example failed. Not on the interesting resources -- the file system, the
# directory and the SVMs all went -- but on a security group, 21 minutes in, with:
#   DsEndpointSecurityGroup  resource sg-... has a dependent object (Service: Ec2, Status Code: 400)
# The dependent object was an interface VPC endpoint that had been created OUTSIDE the stack and
# pointed at the stack's own security group. The error names the security group, never the thing
# holding it, so the message sends you to the resource that is fine. Deleting the endpoint and
# retrying took 27 seconds.
#
# That failure is not specific to this example: anything attached to a stack-owned security group
# will strand the stack, and the message will not say what. So this script looks for dependents
# BEFORE it deletes anything, which turns a 21-minute failure into an upfront answer.
#
# Measured on 2026-09-12 in ap-northeast-1, tearing down the stack this example creates:
#   delete-volume (by id, both control planes agreed) : 247 s
#   delete-stack, first attempt                      : 1277 s, then DELETE_FAILED
#   delete-stack, retry after the dependent was gone :   27 s
#
# Requires: aws, jq. ONTAP access (curl + credentials) only when --purge-recovery-queue is used.
#
# Nothing here touches SnapLock, snapshot locking, Object Lock or any other write-once feature, and
# nothing it deletes becomes permanently undeletable.
set -euo pipefail

STACK_NAME=""
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
SECRET_IDS=""
APPLY="false"
CONFIRMED="false"
PURGE_QUEUE="false"
MGMT_IP=""
FSX_SECRET_ID=""

usage() {
  cat <<'USAGE'
Usage: teardown.sh --stack-name NAME [--region REGION]
                   [--secret-ids 'a,b'] [--purge-recovery-queue --management-ip IP --secret-id NAME]
                   [--apply --i-understand-this-deletes-data]

Without --apply this reports what it would delete, in order, and what would block it. That mode
changes nothing and is the point of running it first: the blockers are what cost time.

Required:
  --stack-name    The CloudFormation stack to remove.
Optional:
  --region        Defaults to AWS_REGION / AWS_DEFAULT_REGION.
  --secret-ids    Comma-separated secrets to delete after the stack. They are NOT stack resources,
                  so delete-stack leaves them, and they keep costing until removed.
  --purge-recovery-queue
                  Also check, and with --apply purge, the ONTAP volume recovery queue. Needs
                  --management-ip and --secret-id. A queued volume blocks its SVM for at least
                  12 hours, so skipping this can strand the file system long after the stack is gone.
  --management-ip ONTAP management endpoint, for the recovery queue only.
  --secret-id     Secret holding the fsxadmin password, for the recovery queue only.

What it does, in this order, and why the order is not arbitrary:
  1. Report volumes whose owning SVM no longer matches what the stack recorded. A rehosted volume is
     the case that matters: CloudFormation's dependency points at the source SVM while the volume
     lives under the destination, and nothing guarantees the volume is removed before the SVM it now
     belongs to. Deleting it by id first removes the race.
  2. Report anything OUTSIDE the stack that holds a security group INSIDE it. This is the check that
     exists because its absence cost 21 minutes.
  3. Delete the out-of-scope volumes, then the stack, then the secrets.
  4. Prove the result by naming each resource and showing it is gone, rather than trusting
     DELETE_COMPLETE.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --stack-name) STACK_NAME="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --secret-ids) SECRET_IDS="$2"; shift 2 ;;
    --purge-recovery-queue) PURGE_QUEUE="true"; shift ;;
    --management-ip) MGMT_IP="$2"; shift 2 ;;
    --secret-id) FSX_SECRET_ID="$2"; shift 2 ;;
    --apply) APPLY="true"; shift ;;
    --i-understand-this-deletes-data) CONFIRMED="true"; shift ;;
    -h | --help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "teardown: $*" >&2; exit 1; }
for tool in aws jq; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required but not installed"
done
[ -n "$STACK_NAME" ] || die "--stack-name is required"
[ -n "$REGION" ] || die "--region is required (or set AWS_REGION)"
if [ "$APPLY" = "true" ] && [ "$CONFIRMED" != "true" ]; then
  die "--apply also needs --i-understand-this-deletes-data. Two flags, because one is easy to
      leave in a shell history and re-run against the wrong stack"
fi
if [ "$PURGE_QUEUE" = "true" ]; then
  [ -n "$MGMT_IP" ] || die "--purge-recovery-queue needs --management-ip"
  [ -n "$FSX_SECRET_ID" ] || die "--purge-recovery-queue needs --secret-id"
  command -v curl >/dev/null 2>&1 || die "curl is required for --purge-recovery-queue"
fi

aws_q() { aws "$@" --region "$REGION"; }

echo "== stack =="
STACK_STATUS="$(aws_q cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo ABSENT)"
printf 'stack   : %s (%s)\n' "$STACK_NAME" "$STACK_STATUS"
[ "$STACK_STATUS" = "ABSENT" ] && echo "        nothing to do for the stack itself; still checking secrets below"

RESOURCES="[]"
if [ "$STACK_STATUS" != "ABSENT" ]; then
  RESOURCES="$(aws_q cloudformation describe-stack-resources --stack-name "$STACK_NAME" \
    --query 'StackResources[].{L:LogicalResourceId,T:ResourceType,P:PhysicalResourceId}' --output json)"
fi

# ------------------------------------------------------------------ 1. displaced volumes

echo
echo "== volumes whose owning SVM no longer matches the stack =="
DISPLACED=""
STACK_SVM_IDS="$(jq -r '[.[] | select(.T=="AWS::FSx::StorageVirtualMachine") | .P] | join(" ")' <<<"$RESOURCES")"
for vol in $(jq -r '.[] | select(.T=="AWS::FSx::Volume") | .P' <<<"$RESOURCES"); do
  info="$(aws_q fsx describe-volumes --volume-ids "$vol" \
    --query 'Volumes[0].[Name,OntapConfiguration.StorageVirtualMachineId,OntapConfiguration.JunctionPath]' \
    --output text 2>/dev/null || true)"
  [ -n "$info" ] || { printf '  %-24s already gone\n' "$vol"; continue; }
  name="$(awk '{print $1}' <<<"$info")"
  svm="$(awk '{print $2}' <<<"$info")"
  printf '  %-24s %-22s svm=%s\n' "$vol" "$name" "$svm"
  # A volume is "displaced" only when its SVM is not the one the stack's own dependency implies.
  # Comparing against every SVM in the stack would call a rehost between two stack SVMs normal,
  # which is exactly the case that strands the deletion, so the destination counts as displaced too.
  first_svm="$(awk '{print $1}' <<<"$STACK_SVM_IDS")"
  if [ -n "$first_svm" ] && [ "$svm" != "$first_svm" ]; then
    DISPLACED="$DISPLACED $vol"
    echo "        ^ not on the stack's first SVM. Delete this by id BEFORE the stack"
  fi
done
[ -n "$DISPLACED" ] || echo "  none"

# ------------------------------------------------------------------ 2. outside holders of inside SGs

echo
echo "== resources outside the stack holding a security group inside it =="
STACK_SGS="$(jq -r '[.[] | select(.T=="AWS::EC2::SecurityGroup") | .P] | join(" ")' <<<"$RESOURCES")"
BLOCKERS=""
if [ -z "$STACK_SGS" ]; then
  echo "  the stack owns no security groups"
else
  # Ownership is decided by comparing identifiers, not by searching for one inside a description.
  #
  # The first version matched a stack resource id as a substring of the interface's description
  # field. That is the kind of check that reports "in the stack" for the wrong reason and hands back
  # the 21-minute failure it exists to prevent: descriptions are free text, AWS owns their format,
  # and an endpoint's description contains the endpoint id rather than anything the stack knows.
  #
  # Instead: an interface belongs to the stack when the thing it is attached to is a stack resource.
  # Instances are compared by instance id, and VPC endpoints by endpoint id looked up from the
  # endpoints that actually use this security group. Anything left over is a blocker.
  STACK_PHYSICAL_IDS="$(jq -r '[.[] | .P] | join(" ")' <<<"$RESOURCES")"
  for sg in $STACK_SGS; do
    # Endpoints using this group, by id. Endpoint interfaces are the common blocker because the
    # endpoint owns them, so the stack has no resource that names them.
    ep_ids="$(aws_q ec2 describe-vpc-endpoints \
      --query "VpcEndpoints[?contains(to_string(Groups),'${sg}')].VpcEndpointId" \
      --output text 2>/dev/null || true)"
    enis="$(aws_q ec2 describe-network-interfaces --filters "Name=group-id,Values=$sg" \
      --query 'NetworkInterfaces[].{Id:NetworkInterfaceId,Desc:Description,Owner:Attachment.InstanceId,Type:InterfaceType}' \
      --output json 2>/dev/null || echo '[]')"
    printf '  %-22s %s interface(s)\n' "$sg" "$(jq 'length' <<<"$enis")"
    for ep in $ep_ids; do
      in_stack="no"
      for p in $STACK_PHYSICAL_IDS; do
        [ "$ep" = "$p" ] && in_stack="yes"
      done
      if [ "$in_stack" = "yes" ]; then
        printf '      %-24s VPC endpoint, in the stack\n' "$ep"
      else
        printf '      %-24s VPC endpoint, OUTSIDE the stack\n' "$ep"
        BLOCKERS="$BLOCKERS $ep"
      fi
    done
    # Instance-attached interfaces, compared by instance id.
    while IFS= read -r row; do
      [ -n "$row" ] || continue
      eid="$(jq -r '.Id' <<<"$row")"
      owner="$(jq -r '.Owner // ""' <<<"$row")"
      itype="$(jq -r '.Type // ""' <<<"$row")"
      [ "$itype" = "vpc_endpoint" ] && continue # already accounted for above, by endpoint id
      if [ -z "$owner" ]; then
        # Unattributable is treated as a blocker rather than as "probably fine", because the failure
        # this check exists to prevent came from an interface nothing in the stack knew about. Say
        # how to resolve it instead of leaving the reader with a verdict and no next step.
        printf '      %-24s attached to nothing this script can identify (type %s)\n' "$eid" "${itype:-unknown}"
        printf '      %-24s resolve with: aws ec2 describe-network-interfaces --network-interface-ids %s \\\n' "" "$eid"
        printf '      %-24s   --region %s --query "NetworkInterfaces[0].{Desc:Description,Req:RequesterId,Att:Attachment}"\n' "" "$REGION"
        BLOCKERS="$BLOCKERS $eid"
        continue
      fi
      in_stack="no"
      for p in $STACK_PHYSICAL_IDS; do
        [ "$owner" = "$p" ] && in_stack="yes"
      done
      if [ "$in_stack" = "yes" ]; then
        printf '      %-24s instance %s, in the stack\n' "$eid" "$owner"
      else
        printf '      %-24s instance %s, OUTSIDE the stack\n' "$eid" "$owner"
        BLOCKERS="$BLOCKERS $eid"
      fi
    done < <(jq -c '.[]' <<<"$enis")
  done
fi
if [ -z "$STACK_SGS" ]; then
  : # already reported that there are no groups to hold; a second "none" reads as a separate finding
elif [ -n "$BLOCKERS" ]; then
  cat <<'WARN'

  ^ These will make delete-stack fail on the security group, with a message that names the security
    group and not them. Remove them first. For an interface VPC endpoint:
      aws ec2 describe-vpc-endpoints --query \
        'VpcEndpoints[?contains(to_string(Groups),`<sg-id>`)].[VpcEndpointId,ServiceName]' --output text
      aws ec2 delete-vpc-endpoints --vpc-endpoint-ids <vpce-...>
    The lesson generalizes: anything created outside a stack should bring its own security group.
WARN
else
  echo "  none"
fi

# ------------------------------------------------------------------ 3. recovery queue

if [ "$PURGE_QUEUE" = "true" ]; then
  echo
  echo "== ONTAP volume recovery queue =="
  PW=""
  PW="$(aws_q secretsmanager get-secret-value --secret-id "$FSX_SECRET_ID" \
    --query SecretString --output text | jq -r '.password // empty')"
  [ -n "$PW" ] || die "could not read a password field from secret $FSX_SECRET_ID"
  rq_raw="$(curl -sk -u "fsxadmin:${PW}" \
    "https://${MGMT_IP}/api/private/cli/volume/recovery-queue?fields=vserver,volume" \
    -w '\n%{http_code}' || true)"
  rq_status="${rq_raw##*$'\n'}"
  rq_body="${rq_raw%$'\n'*}"
  # DO NOT judge this by whether .records is empty.
  #
  # One invalid field name makes the whole request a 400, and `jq '.records'` on the error object
  # prints `null` -- which reads exactly like an empty queue. Measured 2026-09-12: adding a "size"
  # field returned
  #   HTTP 400  {"error":{"message":"The value \"size\" is invalid for field \"fields\"",
  #              "code":"262197","target":"fields"}}
  # and the projection printed null. Acting on that would mean deleting the stack while a queued
  # volume still blocked its SVM. num_records is the field to trust, and only on a 2xx.
  if [ "${rq_status:0:1}" != "2" ]; then
    die "reading the recovery queue failed: HTTP $rq_status $(head -c 300 <<<"$rq_body").
      A non-2xx here is NOT an empty queue"
  fi
  n="$(jq -r '.num_records // "absent"' <<<"$rq_body")"
  [ "$n" != "absent" ] || die "the response carried no num_records, so the queue state is unknown.
      Treat this as unknown, never as empty"
  echo "  num_records: $n"
  jq -r '.records[]? | "    \(.vserver)  \(.volume)"' <<<"$rq_body"
  if [ "$n" != "0" ]; then
    echo "  A queued volume blocks its SVM for at least 12 hours. After a rehost it lands on the"
    echo "  DESTINATION SVM, and its name gains a dataset-id suffix that is not a constant"
    echo "  (measured _1200 on one run and _1031 on another), so match on the prefix, not a literal."
  fi
fi

# ------------------------------------------------------------------ apply

if [ "$APPLY" != "true" ]; then
  echo
  echo "== reported only =="
  echo "Nothing was deleted. To proceed:"
  echo "  ./teardown.sh --stack-name $STACK_NAME --apply --i-understand-this-deletes-data ..."
  [ -n "$BLOCKERS" ] && echo "Remove the blockers listed above first, or the stack will strand."
  exit 0
fi

if [ -n "$BLOCKERS" ]; then
  die "refusing to delete the stack while something outside it holds one of its security groups.
      Remove the interfaces listed above first. Proceeding would fail after roughly 20 minutes with
      an error naming the security group instead of the holder"
fi

echo
echo "== deleting =="
if [ -n "$PURGE_QUEUE" ] && [ "$PURGE_QUEUE" = "true" ] && [ -n "${n:-}" ] && [ "${n:-0}" != "0" ]; then
  while IFS= read -r row; do
    [ -n "$row" ] || continue
    vs="$(jq -r '.vserver' <<<"$row")"; vn="$(jq -r '.volume' <<<"$row")"
    echo "queue  : purging ${vs}/${vn}"
    out="$(curl -sk -u "fsxadmin:${PW}" -X POST -H 'content-type: application/json' \
      -d "$(jq -nc --arg v "$vs" --arg n "$vn" '{vserver:$v, volume:$n}')" \
      "https://${MGMT_IP}/api/private/cli/volume/recovery-queue/purge" -w '\n%{http_code}' || true)"
    st="${out##*$'\n'}"
    [ "${st:0:1}" = "2" ] || die "purge of ${vs}/${vn} failed: HTTP $st"
  done < <(jq -c '.records[]?' <<<"$rq_body")
fi

for vol in $DISPLACED; do
  echo "volume : deleting $vol by id, before the stack"
  aws_q fsx delete-volume --volume-id "$vol" --query 'Lifecycle' --output text || true
done
for vol in $DISPLACED; do
  for _ in $(seq 1 40); do
    st="$(aws_q fsx describe-volumes --volume-ids "$vol" --query 'Volumes[0].Lifecycle' \
      --output text 2>/dev/null || echo GONE)"
    [ "$st" = "GONE" ] && break
    sleep 15
  done
  echo "volume : $vol -> ${st:-GONE}"
done

if [ "$STACK_STATUS" != "ABSENT" ]; then
  echo "stack  : delete-stack"
  aws_q cloudformation delete-stack --stack-name "$STACK_NAME"
  for _ in $(seq 1 80); do
    s="$(aws_q cloudformation describe-stacks --stack-name "$STACK_NAME" \
      --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo GONE)"
    case "$s" in
      GONE | DELETE_COMPLETE) echo "stack  : deleted"; break ;;
      DELETE_FAILED)
        echo "stack  : DELETE_FAILED. What actually failed:" >&2
        aws_q cloudformation describe-stack-events --stack-name "$STACK_NAME" \
          --query "StackEvents[?ResourceStatus=='DELETE_FAILED'].[LogicalResourceId,ResourceStatusReason]" \
          --output text >&2
        die "read the reason above. A security group named here is usually held by something else"
        ;;
    esac
    sleep 25
  done
fi

for s in ${SECRET_IDS//,/ }; do
  echo "secret : $s"
  aws_q secretsmanager delete-secret --secret-id "$s" --force-delete-without-recovery \
    --query 'Name' --output text || true
done

# ------------------------------------------------------------------ prove it

echo
echo "== verification =="
echo "Each line names a resource the stack owned and what the API says about it now. DELETE_COMPLETE"
echo "on the stack is not evidence about the resources; this is."
for p in $(jq -r '.[] | select(.T=="AWS::FSx::FileSystem") | .P' <<<"$RESOURCES"); do
  r="$(aws_q fsx describe-file-systems --file-system-ids "$p" --query 'FileSystems[0].Lifecycle' \
    --output text 2>&1 || true)"
  case "$r" in *NotFound* | *does\ not\ exist*) r="gone" ;; esac
  printf '  file system %-24s %s\n' "$p" "$r"
done
for p in $(jq -r '.[] | select(.T=="AWS::DirectoryService::MicrosoftAD") | .P' <<<"$RESOURCES"); do
  r="$(aws_q ds describe-directories --directory-ids "$p" --query 'DirectoryDescriptions[0].Stage' \
    --output text 2>&1 || true)"
  case "$r" in "" | None | *EntityDoesNotExist*) r="gone" ;; esac
  printf '  directory   %-24s %s\n' "$p" "$r"
done
for p in $(jq -r '.[] | select(.T=="AWS::EC2::Instance") | .P' <<<"$RESOURCES"); do
  r="$(aws_q ec2 describe-instances --instance-ids "$p" \
    --query 'Reservations[].Instances[].State.Name' --output text 2>&1 || true)"
  printf '  instance    %-24s %s\n' "$p" "${r:-gone}"
done
for p in $STACK_SGS; do
  r="$(aws_q ec2 describe-security-groups --group-ids "$p" --query 'SecurityGroups[0].GroupId' \
    --output text 2>&1 || true)"
  case "$r" in *NotFound*) r="gone" ;; esac
  printf '  sec group   %-24s %s\n' "$p" "$r"
done
echo
echo "Anything above that is not 'gone' or 'terminated' is still costing money."
echo "Resources created outside the stack are not listed here, because the stack never knew about"
echo "them. Tag them at creation and look them up by tag."
