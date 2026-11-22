#!/usr/bin/env bash
# Replace the aggregator App's private key (the repository secret SUPPLY_CHAIN_APP_PRIVATE_KEY).
# A maintainer runs this on a local machine, once every 90 days, after generating a new key in the
# App's settings. It never shows the key.
#
#   bash scripts/rotate_app_key.sh <PEM のパス> [--repo owner/name]
#
# What it does, in this order, and stops at the first failure:
#   1. checks that gh, openssl and curl exist, that the PEM is an RSA private key, and that gh is
#      logged in
#   2. reads the App's client ID from the repository variable SUPPLY_CHAIN_APP_CLIENT_ID
#   3. proves the NEW key is accepted by the App, BEFORE the secret is touched: it signs a JWT
#      (RS256; iss = the client ID, iat = now - 60 s, exp = now + 540 s) and calls GET /app.
#      Anything other than HTTP 200 stops the script with the secret unchanged.
#      https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app
#   4. prints the new key's SHA-256 fingerprint, which the App's settings page shows for each key
#   5. sets the secret from the PEM, read on standard input
#   6. starts the supply-chain-key-rotation workflow and waits for that run. If it fails, the old key
#      is NOT to be deleted (it is still valid): the script says how to go back and stops
#   7. on success, tells the person to delete the old key in the settings page. A key can be created
#      and deleted only there; the REST API has no endpoint for it.
#      https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps
#   8. on every exit after the PEM was accepted as a file, deletes the PEM and says so
#
# The key is never printed, never put on a command line, never read into a variable. The JWT goes
# to curl on standard input (`--config -`), so it is on no command line either.
#
# Not run against the real GitHub when this was written: the behaviour of `gh` and of `GET /app`
# below follows their documentation, and the tests use stand-ins for both.
set -euo pipefail

DEFAULT_REPO="Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook"
SECRET_NAME="SUPPLY_CHAIN_APP_PRIVATE_KEY"
CLIENT_ID_VARIABLE="SUPPLY_CHAIN_APP_CLIENT_ID"
WORKFLOW="supply-chain-key-rotation.yml"
DEFAULT_SLUG="sc-aggregator-yoshiki0705"
POLL_SECONDS="${ROTATE_POLL_SECONDS:-3}"
POLL_TRIES=20

pem=""
pem_armed=""
response=""

usage() {
  printf '使い方: bash scripts/rotate_app_key.sh <PEM のパス> [--repo owner/name]\n'
  printf '  既定のリポジトリ: %s\n' "$DEFAULT_REPO"
}

usage_error() {
  printf 'エラー: %s\n' "$1" >&2
  usage >&2
  exit 2
}

die() {
  printf 'エラー: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  local status=$?
  trap - EXIT
  if [ -n "$response" ]; then
    rm -f -- "$response" || true
  fi
  if [ -n "$pem_armed" ]; then
    if ! rm -f -- "$pem" || [ -e "$pem" ]; then
      printf '警告: 鍵の PEM を削除できませんでした。手で削除してください: %s\n' "$pem" >&2
    else
      printf '鍵の PEM を削除しました: %s\n' "$pem"
    fi
  fi
  exit "$status"
}

b64url() {
  openssl base64 -A | tr '+/' '-_' | tr -d '='
}

max_id() {
  local best=0 id
  while IFS= read -r id; do
    if [[ "$id" =~ ^[0-9]+$ ]] && [ "$id" -gt "$best" ]; then
      best="$id"
    fi
  done
  printf '%s\n' "$best"
}

list_run_ids() {
  gh run list --repo "$repo" --workflow "$WORKFLOW" --limit 20 --json databaseId \
    --jq '.[].databaseId'
}

# The secret already holds the new key when this is called. The old key is still valid, so nothing
# is lost; what must not happen is the old key being deleted on the strength of a failed check.
fail_after_secret() {
  printf 'エラー: %s\n' "$1" >&2
  {
    printf '\n新しい鍵はすでにシークレットに入っています。手順 3 で検証済みなので、鍵としては有効です。\n'
    printf '古い鍵もまだ有効です。どちらの鍵も設定画面に残し、古い鍵は消さないでください。\n'
    printf 'workflow が失敗した原因は、鍵ではないことがあります。たとえば App に Secrets: Read-only がない、\n'
    printf 'インストール側でその権限を承認していない、などです。run のログを読んで原因を直し、\n'
    printf '次のコマンドで確認し直してください。\n'
    printf '  gh workflow run %s --repo %s\n' "$WORKFLOW" "$repo"
    printf 'シークレットを古い鍵に戻すには、古い PEM を持っている場合に限り、次を実行します。\n'
    printf '  gh secret set %s --repo %s < <古い PEM のパス>\n' "$SECRET_NAME" "$repo"
  } >&2
  exit 1
}

# --- arguments -------------------------------------------------------------------------------
repo="$DEFAULT_REPO"
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)
      [ $# -ge 2 ] || usage_error "--repo には owner/name を渡してください"
      repo="$2"
      shift 2
      ;;
    --repo=*)
      repo="${1#--repo=}"
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    -*)
      usage_error "知らないオプションです: $1"
      ;;
    *)
      [ -z "$pem" ] || usage_error "PEM のパスは 1 つだけ渡してください"
      pem="$1"
      shift
      ;;
  esac
done

[[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || usage_error "--repo は owner/name の形で渡してください"
[ -n "$pem" ] || usage_error "PEM のパスを渡してください"
if [ ! -f "$pem" ] || [ ! -r "$pem" ]; then
  usage_error "PEM が読めるファイルではありません"
fi
[[ "$POLL_SECONDS" =~ ^[0-9]+$ ]] || usage_error "ROTATE_POLL_SECONDS は整数にしてください"

# A key inside a git repository is one `git add -A` from being published. Refuse, and leave the file
# where it is: it is not this script's to delete before it has been accepted for use.
if command -v git > /dev/null 2>&1 \
  && env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE \
    git -C "$(dirname -- "$pem")" rev-parse --git-dir > /dev/null 2>&1; then
  usage_error "PEM が git のリポジトリの中にあります。リポジトリの外へ移してから、もう一度実行してください"
fi

# From here on the file is this script's to delete, on every exit.
pem_armed=1
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# --- 1. prerequisites ------------------------------------------------------------------------
for tool in gh openssl curl; do
  command -v "$tool" > /dev/null 2>&1 || die "$tool が見つかりません"
done
openssl rsa -check -noout -passin pass: -in "$pem" > /dev/null 2>&1 \
  || die "PEM が RSA の秘密鍵として読めません"
gh auth status > /dev/null 2>&1 || die "gh が未ログインです。gh auth login を実行してください"

# --- 2. the client ID ------------------------------------------------------------------------
if ! client_id="$(gh variable get "$CLIENT_ID_VARIABLE" --repo "$repo")"; then
  die "リポジトリ変数 $CLIENT_ID_VARIABLE を読めませんでした"
fi
client_id="${client_id//[[:space:]]/}"
[[ "$client_id" =~ ^[A-Za-z0-9_.-]+$ ]] \
  || die "リポジトリ変数 $CLIENT_ID_VARIABLE が空か、想定外の文字を含みます"

# --- 3. prove the new key before touching the secret -----------------------------------------
now="$(date +%s)"
issued_at=$((now - 60))
expires_at=$((now + 540))
if ! header="$(printf '%s' '{"alg":"RS256","typ":"JWT"}' | b64url)"; then
  die "JWT のヘッダを作れませんでした"
fi
if ! payload="$(printf '{"iat":%s,"exp":%s,"iss":"%s"}' "$issued_at" "$expires_at" "$client_id" | b64url)"; then
  die "JWT の本文を作れませんでした"
fi
if ! signature="$(printf '%s.%s' "$header" "$payload" | openssl dgst -sha256 -sign "$pem" -passin pass: -binary | b64url)"; then
  die "JWT に署名できませんでした"
fi
[ -n "$signature" ] || die "JWT に署名できませんでした"
jwt="$header.$payload.$signature"

response="$(mktemp)"
if ! status="$(printf 'header = "Authorization: Bearer %s"\n' "$jwt" \
  | curl --silent --show-error --max-time 30 --config - \
    --header 'Accept: application/vnd.github+json' \
    --header 'X-GitHub-Api-Version: 2022-11-28' \
    --output "$response" --write-out '%{http_code}' \
    https://api.github.com/app)"; then
  die "App への問い合わせが通信で失敗しました。シークレットには触れていません"
fi
status="${status//[^0-9]/}"
if [ "$status" != 200 ]; then
  die "新しい鍵の検証が HTTP ${status:-000} で失敗しました。鍵がこの App のものか、クライアント ID が合っているかを確かめてください。シークレットには触れていません"
fi
slug="$(tr -d '\n' < "$response" \
  | sed -n 's/.*"slug"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | tr -cd 'A-Za-z0-9-')"
[ -n "$slug" ] || slug="$DEFAULT_SLUG"
printf '新しい鍵を App が受け付けました（slug: %s）\n' "$slug"

# --- 4. the fingerprint the settings page shows ----------------------------------------------
if ! fingerprint="$(openssl rsa -in "$pem" -passin pass: -pubout -outform DER 2> /dev/null \
  | openssl dgst -sha256 -binary | openssl base64 -A)"; then
  die "指紋を計算できませんでした"
fi
printf '新しい鍵の指紋: SHA256:%s\n' "$fingerprint"

# --- 5. the secret, on standard input --------------------------------------------------------
gh secret set "$SECRET_NAME" --repo "$repo" < "$pem" \
  || die "gh secret set に失敗しました。新しい鍵は検証済みですが、シークレットは更新されていない可能性があります。設定画面の古い鍵はそのまま残してください"
printf 'シークレット %s を更新しました\n' "$SECRET_NAME"

# --- 6. run the workflow and wait for that run -----------------------------------------------
if ! before_ids="$(list_run_ids)"; then
  fail_after_secret "起動前の run の一覧を読めませんでした"
fi
before_max="$(max_id <<< "$before_ids")"
gh workflow run "$WORKFLOW" --repo "$repo" \
  || fail_after_secret "workflow を起動できませんでした。$WORKFLOW が既定ブランチにあるかを確かめてください"

run_id=""
for ((attempt = 0; attempt < POLL_TRIES; attempt++)); do
  sleep "$POLL_SECONDS"
  if after_ids="$(list_run_ids)"; then
    newest="$(max_id <<< "$after_ids")"
    if [ "$newest" -gt "$before_max" ]; then
      run_id="$newest"
      break
    fi
  fi
done
[ -n "$run_id" ] || fail_after_secret "起動した run を見つけられませんでした"

printf 'run %s の完了を待ちます\n' "$run_id"
gh run watch "$run_id" --repo "$repo" --exit-status \
  || fail_after_secret "run $run_id が失敗しました"

# --- 7. the part only a person can do --------------------------------------------------------
printf '\nworkflow が成功しました。次の操作は人が行います。\n'
printf '  1. https://github.com/settings/apps/%s を開く\n' "$slug"
printf '  2. Credentials → Key pairs で、指紋が SHA256:%s と一致しない鍵（古い鍵）を Delete する\n' "$fingerprint"
printf '  3. 鍵は 1 つの App に 25 本までです。25 本に近いときは、使っていない鍵から先に Delete してください\n'
printf '  4. 入れ替えの Issue は、次の workflow の実行で自動で閉じます\n'
