#!/usr/bin/env bash
#
# Generate the mutual-authentication material an AWS Client VPN endpoint needs, and import the server
# certificate into AWS Certificate Manager.
#
# Mutual certificate authentication is used here because it has the fewest prerequisites: no identity
# provider, no directory, nothing to stand up before the endpoint works. The cost of that choice is
# that POSSESSION OF THE CLIENT KEY IS THE AUTHORIZATION. There is no group, no user and no
# revocation list in this example, so anyone holding the file below can reach the authorized CIDR.
# Treat the output directory as a credential store and delete it when the verification is over.
#
# openssl is used rather than easy-rsa, which the AWS documentation uses, because openssl is already
# present on macOS, on WSL2 and on every Linux distribution this example targets. The certificates it
# produces are the same shape.
#
# Requires: openssl, aws. Writes into ./pki, which .gitignore excludes as a whole.

set -euo pipefail

# OUTSIDE THE REPOSITORY ON PURPOSE. This used to default to ./pki, which .gitignore excluded --
# and a gitignored private key is still a private key in the worktree: `make secrets` runs gitleaks
# with --no-git precisely so it sees files before they are staged, so it reported four keys and the
# commit gate stopped. Ignoring them in .gitleaks.toml would have been the wrong fix: it would teach
# the scanner to stay quiet about private keys under examples/. Not putting them there is the fix.
OUT_DIR="${HOME}/.fsxn-client-access/pki"
CA_CN="fsxn-client-access-ca"
# Domain-shaped, and carried into a subjectAltName below. A bare CN like "server" imports into ACM
# without complaint and is then refused by the Client VPN endpoint with "Certificate <arn> does not
# have a domain" -- after the stack has begun creating. The AWS procedure uses easy-rsa, which adds
# the SAN on its own, so the requirement is invisible when following it and surfaces only here.
SERVER_CN="server.fsxn-client-access.internal"
CLIENT_CN="client1"
DAYS="90"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
IMPORT="true"
FORCE="false"

usage() {
  cat <<'USAGE'
Usage: make-client-vpn-certs.sh [--out-dir DIR] [--server-cn NAME] [--client-cn NAME] [--days N]
                                [--region REGION] [--no-import] [--force]

Optional:
  --out-dir     Directory for the generated material.
                Default: $HOME/.fsxn-client-access/pki -- OUTSIDE THE REPOSITORY.
                Overriding this to a path inside the repository puts private keys in the worktree,
                where the secret scan will find them even though .gitignore excludes them.
  --server-cn   Common name for the server certificate, also used as its subjectAltName.
                Default: server.fsxn-client-access.internal
                MUST BE DOMAIN-SHAPED. A bare name like "server" imports into ACM successfully and
                is then refused by the Client VPN endpoint with "does not have a domain", which
                surfaces only once the stack is creating.
  --client-cn   Common name for the client certificate. Default: client1
                One per person or per device, so a lost device can be reasoned about even though
                this example sets up no revocation list.
  --days        Validity in days. Default: 90. Short on purpose: this material exists for a
                verification, and a certificate that outlives the file system is a credential
                nobody is watching.
  --region      AWS region for the ACM import. Defaults to AWS_REGION or AWS_DEFAULT_REGION.
  --no-import   Generate the files and skip the ACM import. Use when the import will happen from
                somewhere else, or to inspect what would be uploaded first.
  --force       Overwrite an existing output directory. Without it, an existing directory is left
                alone -- re-running by accident would otherwise invalidate a profile already
                installed on an endpoint.

What it prints at the end:
  - the ACM ARN to pass as BOTH ServerCertificateArn and ClientRootCertificateChainArn
  - the two commands that turn the endpoint configuration into a working .ovpn profile

Teardown, when the verification is done:
  aws acm delete-certificate --certificate-arn <arn>
  rm -rf "$HOME/.fsxn-client-access"   <this removes the only copy of the client key>
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --server-cn) SERVER_CN="$2"; shift 2 ;;
    --client-cn) CLIENT_CN="$2"; shift 2 ;;
    --days) DAYS="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --no-import) IMPORT="false"; shift ;;
    --force) FORCE="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "make-client-vpn-certs: $*" >&2; exit 1; }

command -v openssl >/dev/null 2>&1 || die "openssl is required but not installed"
if [ "$IMPORT" = "true" ]; then
  command -v aws >/dev/null 2>&1 || die "aws is required unless --no-import is given"
  [ -n "$REGION" ] || die "--region is required (or set AWS_REGION) unless --no-import is given"
fi

case "$DAYS" in
  ''|*[!0-9]*) die "--days must be a positive integer, got '$DAYS'" ;;
esac

if [ -d "$OUT_DIR" ] && [ "$FORCE" != "true" ]; then
  die "$OUT_DIR already exists. A profile generated from it may already be installed on an
    endpoint, and regenerating invalidates it. Pass --force to overwrite deliberately."
fi

mkdir -p "$OUT_DIR"
# The private keys land here. 0700 is not a substitute for deleting the directory afterwards, but it
# keeps another account on the same machine from reading them in the meantime.
chmod 700 "$OUT_DIR"

echo "==> Certificate authority"
openssl genrsa -out "$OUT_DIR/ca.key" 2048 2>/dev/null
chmod 600 "$OUT_DIR/ca.key"
openssl req -x509 -new -nodes -key "$OUT_DIR/ca.key" -sha256 -days "$DAYS" \
  -subj "/CN=$CA_CN" -out "$OUT_DIR/ca.crt"

issue_cert() {
  # $1 common name, $2 file stem, $3 extended key usage, $4 "san" to add a subjectAltName
  local cn="$1" stem="$2" eku="$3" want_san="${4:-}"
  openssl genrsa -out "$OUT_DIR/$stem.key" 2048 2>/dev/null
  chmod 600 "$OUT_DIR/$stem.key"
  openssl req -new -key "$OUT_DIR/$stem.key" -subj "/CN=$cn" -out "$OUT_DIR/$stem.csr"
  # extendedKeyUsage is set explicitly. A certificate without it is accepted by some TLS stacks and
  # refused by others, and the refusal surfaces as a generic handshake failure in the VPN client -
  # which reads as a server problem rather than as a missing extension.
  printf 'extendedKeyUsage = %s\nbasicConstraints = CA:FALSE\n' "$eku" > "$OUT_DIR/$stem.ext"
  if [ "$want_san" = "san" ]; then
    # Without this the Client VPN endpoint refuses the certificate with "does not have a domain".
    # ACM accepts the import either way, so the gap is only visible at CreateStack time.
    printf 'subjectAltName = DNS:%s\n' "$cn" >> "$OUT_DIR/$stem.ext"
  fi
  openssl x509 -req -in "$OUT_DIR/$stem.csr" -CA "$OUT_DIR/ca.crt" -CAkey "$OUT_DIR/ca.key" \
    -CAcreateserial -out "$OUT_DIR/$stem.crt" -days "$DAYS" -sha256 \
    -extfile "$OUT_DIR/$stem.ext"
  rm -f "$OUT_DIR/$stem.csr" "$OUT_DIR/$stem.ext"
}

echo "==> Server certificate ($SERVER_CN)"
issue_cert "$SERVER_CN" server serverAuth san

echo "==> Client certificate ($CLIENT_CN)"
issue_cert "$CLIENT_CN" client clientAuth

CERT_ARN=""
if [ "$IMPORT" = "true" ]; then
  echo "==> Importing the server certificate into ACM in $REGION"
  CERT_ARN="$(aws acm import-certificate \
    --certificate "fileb://$OUT_DIR/server.crt" \
    --private-key "fileb://$OUT_DIR/server.key" \
    --certificate-chain "fileb://$OUT_DIR/ca.crt" \
    --region "$REGION" \
    --query CertificateArn --output text)"
  [ -n "$CERT_ARN" ] || die "the ACM import returned no ARN"
  printf '%s\n' "$CERT_ARN" > "$OUT_DIR/server-certificate-arn.txt"
fi

cat <<REPORT

--------------------------------------------------------------------------
Generated in $OUT_DIR:
  ca.crt      the certificate authority -- the client profile needs this
  ca.key      CA PRIVATE KEY. Delete the directory when you are done.
  server.crt  server certificate, imported into ACM
  server.key  server PRIVATE KEY, imported into ACM
  client.crt  client certificate -- goes into the .ovpn profile
  client.key  client PRIVATE KEY -- goes into the .ovpn profile

REPORT

if [ -n "$CERT_ARN" ]; then
  cat <<REPORT
Pass this ARN as BOTH template parameters. The client certificate is signed by the same CA as the
server certificate, so one import covers both fields:

  ServerCertificateArn          = $CERT_ARN
  ClientRootCertificateChainArn = $CERT_ARN

REPORT
else
  cat <<'REPORT'
Skipped the ACM import (--no-import). Import the server certificate before deploying the endpoint:

  aws acm import-certificate --certificate fileb://pki/server.crt \
    --private-key fileb://pki/server.key --certificate-chain fileb://pki/ca.crt

REPORT
fi

cat <<REPORT
After the Client VPN stack exists, build the profile the VPN client opens. Keep it beside the keys,
outside the repository:

  PROFILE="$OUT_DIR/../client-config.ovpn"
  aws ec2 export-client-vpn-client-configuration \\
    --client-vpn-endpoint-id <ClientVpnEndpointId> --output text > "\$PROFILE"
  {
    printf '\\n<cert>\\n'; cat "$OUT_DIR/client.crt"; printf '</cert>\\n<key>\\n'
    cat "$OUT_DIR/client.key"; printf '</key>\\n'
  } >> "\$PROFILE"

The exported configuration carries no client certificate. A profile missing the two blocks above
fails at the TLS handshake, which the client reports as a connection error rather than as a missing
certificate -- so append them before the first attempt rather than after diagnosing one.

The profile CONTAINS THE CLIENT PRIVATE KEY. Connecting also needs root on the endpoint, whichever
client you use, because bringing up the tunnel creates a utun interface.
REPORT
