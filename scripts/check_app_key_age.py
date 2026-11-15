"""Report how old the aggregator App's private key is, and keep one Issue in step with the answer.

The App key (the repository secret `SUPPLY_CHAIN_APP_PRIVATE_KEY`) is replaced every 90 days. The
90 days is this repository's policy and nothing enforces it: GitHub private keys have no expiry
date ("Private keys do not expire and instead need to be manually revoked"). So the age has to be
measured, and the one place that records it is the secret's own `updated_at`.

What GitHub documents, and what this script relies on
-----------------------------------------------------
* A private key cannot be created, listed or deleted through the REST API. The App's REST reference
  has no endpoint for keys. A person creates and deletes keys in the App's settings
  (Credentials -> Key pairs). https://docs.github.com/en/rest/apps/apps and
  https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps
* `GET /repos/{owner}/{repo}/actions/secrets/{secret_name}` returns `name`, `created_at` and
  `updated_at`, never the value. https://docs.github.com/en/rest/actions/secrets
* An App installation token reads it with the repository permission `Secrets` (read).
  https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps
* A workflow's `GITHUB_TOKEN` has no `secrets` permission
  (https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), so the
  read uses the App's own token (`APP_TOKEN`) and the Issue is written with the job's token
  (`ISSUE_TOKEN`). The two are never swapped.

Verdicts
--------
    ok          age < WARN_DAYS                 close the open Issue, if any
    due         WARN_DAYS <= age < MAX_DAYS     open one Issue; leave an open one alone
    overdue     MAX_DAYS <= age                 open or rewrite the Issue once; exit 1
    unreadable  the age could not be read       write no Issue; exit 1

An Issue is the open one whose body starts with MARKER. Its title is not used to find it, a pull
request is never counted, and no label is involved.

Unconfirmed against the live API: the exact shape of the answers (this was written from the
documentation), the answer when the App lacks `Secrets: Read-only`, and whether the repository
name given to the App-token step is accepted in this form.

Environment: GH_REPO (`owner/name`), SECRET_NAME, APP_TOKEN, ISSUE_TOKEN, TOKEN_STEP_OUTCOME,
WARN_DAYS, MAX_DAYS, and GITHUB_STEP_SUMMARY when the runner provides it. No arguments.
Neither a token nor the body of an answer is ever printed.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, NamedTuple

API = "https://api.github.com"
API_VERSION = "2022-11-28"
TIMEOUT_SECONDS = 30
PAGE_SIZE = 100
MAX_PAGES = 30

MARKER = "<!-- supply-chain-key-rotation:v1 -->"
STATE_MARKER = "<!-- supply-chain-key-rotation:state={state} -->"
TITLE = "[supply-chain] App の秘密鍵の入れ替え"
APP_SLUG = "sc-aggregator-yoshiki0705"
APP_SETTINGS_URL = f"https://github.com/settings/apps/{APP_SLUG}"

DEFAULT_SECRET = "SUPPLY_CHAIN_APP_PRIVATE_KEY"
DEFAULT_WARN_DAYS = 80
DEFAULT_MAX_DAYS = 90

REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SECRET_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
KNOWN_OUTCOMES = frozenset({"success", "failure", "skipped", "cancelled"})


class Response(NamedTuple):
    """An answer: the HTTP status (0 when none arrived) and the decoded JSON, or None."""

    status: int
    data: Any


Send = Callable[[str, str, str, "dict[str, Any] | None"], Response]


class ConfigError(Exception):
    """The environment cannot be used. The message never repeats a value."""


class ApiError(Exception):
    """A call that must succeed did not. The message holds a status, never a body."""


class Verdict(NamedTuple):
    state: str
    days: int | None


@dataclass(frozen=True)
class Config:
    repo: str
    secret_name: str
    app_token: str
    issue_token: str
    token_outcome: str
    warn_days: int
    max_days: int


def _whole_days(env: Mapping[str, str], name: str, default: int) -> int:
    raw = (env.get(name) or "").strip()
    if not raw:
        return default
    if not raw.isdigit():
        raise ConfigError(f"{name} must be a whole number of days")
    return int(raw)


def load_config(env: Mapping[str, str]) -> Config:
    repo = (env.get("GH_REPO") or "").strip()
    if not REPO_PATTERN.match(repo):
        raise ConfigError("GH_REPO must be owner/name")
    secret_name = (env.get("SECRET_NAME") or "").strip() or DEFAULT_SECRET
    if not SECRET_PATTERN.match(secret_name):
        raise ConfigError("SECRET_NAME is not a valid secret name")
    issue_token = env.get("ISSUE_TOKEN") or ""
    if not issue_token:
        raise ConfigError("ISSUE_TOKEN is empty, so no Issue can be read or written")
    warn_days = _whole_days(env, "WARN_DAYS", DEFAULT_WARN_DAYS)
    max_days = _whole_days(env, "MAX_DAYS", DEFAULT_MAX_DAYS)
    if warn_days > max_days:
        raise ConfigError("WARN_DAYS must not be larger than MAX_DAYS")
    return Config(
        repo=repo,
        secret_name=secret_name,
        app_token=env.get("APP_TOKEN") or "",
        issue_token=issue_token,
        token_outcome=(env.get("TOKEN_STEP_OUTCOME") or "").strip(),
        warn_days=warn_days,
        max_days=max_days,
    )


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def classify(
    updated_at: object, now: datetime, warn_days: int, max_days: int
) -> Verdict:
    """The verdict for a secret last set at `updated_at`. A pure function of its arguments.

    The age is whole days: a fraction is cut off, so 79 days 23 hours is 79 and still `ok`. A
    timestamp in the future (clock skew) counts as 0 days.
    """
    moment = _parse_timestamp(updated_at)
    if moment is None:
        return Verdict("unreadable", None)
    days = max(0, (now - moment).days)
    if days >= max_days:
        return Verdict("overdue", days)
    if days >= warn_days:
        return Verdict("due", days)
    return Verdict("ok", days)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects. The token is a header, and urllib would send it on to the new location."""

    def redirect_request(  # type: ignore[no-untyped-def]
        self, req, fp, code, msg, headers, newurl
    ):
        return None


def urllib_send(
    method: str, path: str, token: str, payload: dict[str, Any] | None
) -> Response:
    """One call to the GitHub REST API. A transport failure is status 0, never an exception."""
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(API + path, data=body, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", API_VERSION)
    request.add_header("User-Agent", "supply-chain-key-rotation")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as reply:
            status, raw = reply.status, reply.read()
    except urllib.error.HTTPError as err:
        status = err.code
        try:
            raw = err.read()
        except OSError:
            raw = b""
    except (urllib.error.URLError, TimeoutError, OSError):
        return Response(0, None)
    try:
        data = json.loads(raw) if raw else None
    except ValueError:
        data = None
    return Response(status, data)


class Reading(NamedTuple):
    """What reading the secret produced: the verdict, the `updated_at` text, and a reason if unreadable."""

    verdict: Verdict
    updated_at: str
    reason: str


def _unreadable(reason: str) -> Reading:
    return Reading(Verdict("unreadable", None), "", reason)


def read_secret_age(config: Config, now: datetime, send: Send) -> Reading:
    """Read the secret's `updated_at` with the App token and classify it."""
    if not config.app_token:
        return _unreadable("APP_TOKEN is empty")
    if config.token_outcome != "success":
        outcome = (
            config.token_outcome
            if config.token_outcome in KNOWN_OUTCOMES
            else "unknown"
        )
        return _unreadable(
            f"the step that creates the App token ended with '{outcome}'. The private key may be "
            "invalid, or the App may lack the repository permission Secrets: Read-only, or the "
            "installation may not have approved it"
        )
    path = f"/repos/{config.repo}/actions/secrets/{config.secret_name}"
    reply = send("GET", path, config.app_token, None)
    if reply.status in (403, 404):
        return _unreadable(
            f"HTTP {reply.status} reading the secret. The App may lack the repository permission "
            "Secrets: Read-only, or the installation has not approved it, or the secret name is wrong"
        )
    if reply.status == 0:
        return _unreadable("no answer from the GitHub API")
    if reply.status != 200:
        return _unreadable(f"HTTP {reply.status} reading the secret")
    updated_at = reply.data.get("updated_at") if isinstance(reply.data, dict) else None
    verdict = classify(updated_at, now, config.warn_days, config.max_days)
    if verdict.state == "unreadable":
        return _unreadable("the answer had no readable updated_at")
    return Reading(verdict, str(updated_at), "")


def render_body(
    state: str,
    updated_at: str,
    days: int,
    warn_days: int = DEFAULT_WARN_DAYS,
    max_days: int = DEFAULT_MAX_DAYS,
) -> str:
    """The Issue body. Line 1 is MARKER; line 2 records which version this is (due or overdue)."""
    if state == "overdue":
        lead = (
            f"期限の {max_days} 日を超えています。秘密鍵に有効期限はないので集約ジョブは動き続けますが、"
            "運用方針の期限を過ぎました。入れ替えるまで、毎日の確認は失敗します。"
        )
    else:
        lead = (
            f"入れ替えの時期です。{warn_days} 日で Issue を起票し、{max_days} 日を超えると"
            "毎日の確認を失敗にします。"
        )
    return "\n".join(
        [
            MARKER,
            STATE_MARKER.format(state=state),
            f"App `{APP_SLUG}` の秘密鍵について。{lead}",
            "",
            "## 現在の状態",
            "",
            "| 項目 | 値 |",
            "|---|---|",
            f"| シークレット | `{DEFAULT_SECRET}` |",
            f"| 最後に設定した日時（updated_at） | {updated_at} |",
            f"| 経過日数 | {days} 日 |",
            f"| Issue を起票する日数 | {warn_days} 日 |",
            f"| 確認を失敗にする日数 | {max_days} 日 |",
            "",
            f"{max_days} 日はこのリポジトリの運用方針です。GitHub が強制する期限ではありません。",
            "",
            "## 入れ替えの手順",
            "",
            (
                f"- [ ] `{APP_SETTINGS_URL}` の Credentials → Key pairs で"
                "「Generate a private key」を押し、PEM を保存する"
            ),
            (
                "- [ ] `bash scripts/rotate_app_key.sh <PEM のパス>` を実行する"
                "（新しい鍵の検証、シークレットの登録、workflow の実行、PEM の削除まで行う）"
            ),
            "- [ ] 設定画面で、スクリプトが表示した指紋と違う古い鍵を Delete する",
            "- [ ] この Issue は、入れ替え後の次の workflow の実行で自動で閉じる（操作は不要）",
            "",
        ]
    )


def is_overdue_body(body: str | None) -> bool:
    """Whether a body is the overdue version. The version is compared, not the text, because the
    text names the elapsed days and so differs every day."""
    return STATE_MARKER.format(state="overdue") in (body or "")


def _issue_pages(send: Send, repo: str, token: str) -> Iterator[list[dict[str, Any]]]:
    for page in range(1, MAX_PAGES + 1):
        path = f"/repos/{repo}/issues?state=open&per_page={PAGE_SIZE}&page={page}"
        reply = send("GET", path, token, None)
        if reply.status != 200 or not isinstance(reply.data, list):
            raise ApiError(f"listing Issues returned HTTP {reply.status}")
        yield [row for row in reply.data if isinstance(row, dict)]
        if len(reply.data) < PAGE_SIZE:
            return
    raise ApiError(f"more than {MAX_PAGES * PAGE_SIZE} open Issues and pull requests")


def find_existing(send: Send, repo: str, token: str) -> dict[str, Any] | None:
    """The open Issue whose body starts with MARKER. A pull request is never one."""
    for rows in _issue_pages(send, repo, token):
        for row in rows:
            if "pull_request" in row:
                continue
            lines = str(row.get("body") or "").splitlines()
            if lines and lines[0].strip() == MARKER:
                return row
    return None


def _write(
    send: Send, method: str, path: str, token: str, payload: dict[str, Any]
) -> None:
    reply = send(method, path, token, payload)
    if reply.status // 100 != 2:
        raise ApiError(f"{method} {path.split('?')[0]} returned HTTP {reply.status}")


def sync_issue(config: Config, verdict: Verdict, updated_at: str, send: Send) -> str:
    """Bring the one Issue in step with the verdict. Returns a short note of what was done."""
    token, repo = config.issue_token, config.repo
    existing = find_existing(send, repo, token)
    issues = f"/repos/{repo}/issues"
    days = verdict.days or 0
    if verdict.state == "ok":
        if existing is None:
            return "no Issue to close"
        number = existing["number"]
        note = (
            f"秘密鍵の入れ替えを確認しました。シークレットの updated_at は {updated_at}"
            f"（経過 {days} 日）です。この Issue を閉じます。"
        )
        _write(send, "POST", f"{issues}/{number}/comments", token, {"body": note})
        _write(
            send,
            "PATCH",
            f"{issues}/{number}",
            token,
            {"state": "closed", "state_reason": "completed"},
        )
        return f"closed Issue #{number}"
    body = render_body(
        verdict.state, updated_at, days, config.warn_days, config.max_days
    )
    if existing is None:
        _write(send, "POST", issues, token, {"title": TITLE, "body": body})
        return "opened an Issue"
    if verdict.state == "overdue" and not is_overdue_body(existing.get("body")):
        _write(send, "PATCH", f"{issues}/{existing['number']}", token, {"body": body})
        return f"rewrote Issue #{existing['number']} as overdue"
    return f"left Issue #{existing['number']} as it was"


def write_summary(path: str | None, verdict: Verdict, updated_at: str) -> None:
    if not path:
        return
    days = "-" if verdict.days is None else str(verdict.days)
    shown = updated_at or "-"
    text = (
        "## supply-chain-key-rotation\n\n"
        "| 判定 | updated_at | 経過日数 |\n"
        "|---|---|---|\n"
        f"| {verdict.state} | {shown} | {days} |\n"
    )
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)


def main(
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
    send: Send | None = None,
) -> int:
    environment = os.environ if env is None else env
    moment = now or datetime.now(timezone.utc)
    transport = send or urllib_send
    try:
        config = load_config(environment)
    except ConfigError as err:
        print(f"::error::{err}")
        return 1
    verdict, updated_at, reason = read_secret_age(config, moment, transport)
    write_summary(environment.get("GITHUB_STEP_SUMMARY"), verdict, updated_at)
    if verdict.state == "unreadable":
        print(f"key age: unreadable ({reason})")
        print(
            "::error::The age of the App private key could not be read: "
            f"{reason}. No Issue was changed."
        )
        return 1
    print(f"key age: {verdict.state}, {verdict.days} day(s), updated_at {updated_at}")
    try:
        done = sync_issue(config, verdict, updated_at, transport)
    except ApiError as err:
        print(f"::error::Could not bring the Issue in step: {err}")
        return 1
    print(f"issue: {done}")
    if verdict.state == "overdue":
        print(
            f"::error::The App private key is {verdict.days} days old, past the "
            f"{config.max_days}-day limit (overdue). See the open Issue."
        )
        return 1
    if verdict.state == "due":
        print(
            f"::warning::The App private key is {verdict.days} days old; "
            f"replace it before day {config.max_days}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
