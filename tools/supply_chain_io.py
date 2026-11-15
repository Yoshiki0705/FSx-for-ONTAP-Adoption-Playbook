"""Thin HTTP and GitHub API clients for the supply-chain Aggregator.

Everything here fetches or sends; nothing here decides. The decisions (what to open, update or
close, how long to wait before a retry, whether a failure notice is due) are made by the pure core
in tools/supply_chain/. This module only turns them into requests and turns responses back into
the plain values the core takes.

Standard library only. All network access goes through a ``Transport``, so tests pass a fake that
records every call and never touches the network.

Two properties are deliberate:

* A redirect is never followed by the transport. GitHub answers an artifact download with a 302 to
  a storage host, and ``urllib`` copies the Authorization header onto the redirected request. The
  client follows the redirect itself and sends the second request without a token.
* A write is not retried after a server error or a dropped connection when it might have been
  applied (POST). It is retried after 429 and a rate-limit 403, where the request was refused.
"""

from __future__ import annotations

import base64
import csv
import gzip
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

from supply_chain import run_record
from supply_chain.models import KevEntry

API_ROOT = "https://api.github.com"
USER_AGENT = "fsx-ontap-adoption-playbook-supply-chain-aggregator"
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_URL = "https://epss.empiricalsecurity.com/epss_scores-current.csv.gz"
OSV_ROOT = "https://api.osv.dev"
REQUEST_TIMEOUT_SECONDS = 60
# A wait longer than this is not served: the run stops and records which repositories were left.
MAX_SERVED_WAIT_SECONDS = 120.0
# Conservative. The documented upper bound of a batch was not confirmed, so this is not claimed to be it.
OSV_BATCH_SIZE = 100
OSV_MAX_PAGE_ROUNDS = 20
MAX_PAGES = 100
PER_PAGE = 100


class TransportError(OSError):
    """The request did not produce an HTTP response (DNS, TLS, reset, timeout)."""


class HttpError(Exception):
    """A response that the caller treats as a failure."""

    def __init__(self, method: str, url: str, status: int, excerpt: str = "") -> None:
        self.method, self.url, self.status, self.excerpt = method, url, status, excerpt
        super().__init__(f"{method} {_redact(url)} -> HTTP {status} {excerpt}".strip())


class RateLimited(Exception):
    """A rate limit was hit and the wait is longer than the run will serve (or retries ran out)."""


@dataclass(frozen=True, slots=True)
class Response:
    """An HTTP response. Header names are lower case."""

    status: int
    headers: Mapping[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class Transport(Protocol):
    """Sends one request and returns the response without following redirects."""

    def request(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> Response: ...


def _redact(url: str) -> str:
    """Drop the query string: signed storage URLs carry credentials there."""
    return url.split("?", 1)[0]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class UrllibTransport:
    """The real transport. A 3xx, 4xx or 5xx comes back as a Response, never as an exception."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirect())

    def request(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> Response:
        if not url.startswith("https://"):
            raise TransportError(f"refusing a non-https URL: {_redact(url)}")
        req = urllib.request.Request(
            url, data=body, method=method, headers=dict(headers)
        )
        try:
            with self._opener.open(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                return Response(resp.status, _lower(resp.headers), resp.read())
        except urllib.error.HTTPError as exc:
            return Response(exc.code, _lower(exc.headers), exc.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise TransportError(f"{method} {_redact(url)}: {exc}") from exc


def _lower(headers: Any) -> dict[str, str]:
    return {k.lower(): v for k, v in headers.items()}


def _retry_after_seconds(headers: Mapping[str, str], now: float) -> float | None:
    """Seconds to wait from Retry-After, else from the rate-limit reset header, else None."""
    raw = headers.get("retry-after")
    if raw is not None:
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None
    if (
        headers.get("x-ratelimit-remaining") == "0"
        and headers.get("x-ratelimit-reset", "").isdigit()
    ):
        return max(0.0, float(headers["x-ratelimit-reset"]) - now)
    return None


def _is_rate_limit(resp: Response) -> bool:
    if resp.status == 429:
        return True
    return resp.status == 403 and (
        "retry-after" in resp.headers
        or resp.headers.get("x-ratelimit-remaining") == "0"
    )


class Client:
    """Sends requests with the retry policy of ``run_record.retry_wait`` (2, 4, 8, 16, 32 s)."""

    def __init__(
        self,
        transport: Transport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._transport = transport
        self._sleep = sleep
        self._clock = clock

    def send(
        self,
        method: str,
        url: str,
        *,
        token: str | None = None,
        headers: Mapping[str, str] | None = None,
        body: bytes | None = None,
    ) -> Response:
        """Send a request and return the last response.

        Retries 429 and a rate-limit 403 for every method; 5xx and dropped connections only for
        methods that cannot have been applied twice (everything but POST).

        Raises:
            RateLimited: The limit was hit and the wait exceeds MAX_SERVED_WAIT_SECONDS, or the
                retries ran out while still limited.
            TransportError: No response after the retries (non-POST) or on the first try (POST).
        """
        merged = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
        merged.update(headers or {})
        if token:
            merged["Authorization"] = f"Bearer {token}"
        attempt = 0
        while True:
            try:
                resp = self._transport.request(method, url, merged, body)
            except TransportError:
                wait = run_record.retry_wait(attempt) if method != "POST" else None
                if wait is None:
                    raise
                self._sleep(wait)
                attempt += 1
                continue
            limited = _is_rate_limit(resp)
            retryable = limited or (resp.status >= 500 and method != "POST")
            if not retryable:
                return resp
            asked = _retry_after_seconds(resp.headers, self._clock())
            if asked is not None and asked > MAX_SERVED_WAIT_SECONDS:
                raise RateLimited(
                    f"{method} {_redact(url)}: asked to wait {asked:.0f} s"
                )
            wait = run_record.retry_wait(attempt, asked)
            if wait is None:
                if limited:
                    raise RateLimited(
                        f"{method} {_redact(url)}: still limited after {attempt} retries"
                    )
                return resp
            self._sleep(wait)
            attempt += 1

    def download(self, url: str, *, token: str | None = None) -> bytes:
        """GET a URL that may redirect (an artifact). The redirect target gets no token."""
        resp = self.send("GET", url, token=token)
        hops = 0
        while resp.status in (301, 302, 303, 307, 308) and hops < 3:
            location = resp.headers.get("location")
            if not location:
                raise HttpError("GET", url, resp.status, "redirect without Location")
            url = urllib.parse.urljoin(url, location)
            resp = self.send("GET", url, headers={"Accept": "*/*"})
            hops += 1
        if not resp.ok:
            raise HttpError("GET", url, resp.status)
        return resp.body


_LINK_ENTRY = re.compile(r"<([^>]*)>([^<]*)")


def _next_link(header: str | None) -> str | None:
    """The URL of rel="next" in a Link header, or None."""
    if not header:
        return None
    for target, params in _LINK_ENTRY.findall(header):
        for rel in re.findall(r'rel\s*=\s*"?([^";,]+)"?', params):
            if "next" in rel.split():
                return target
    return None


class GitHubApi:
    """One GitHub REST token. The Aggregator holds two of these and never mixes them up."""

    def __init__(self, client: Client, token: str, api_root: str = API_ROOT) -> None:
        self._client, self._token, self._root = client, token, api_root

    def _url(self, path: str, params: Mapping[str, Any] | None = None) -> str:
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        return f"{self._root}{path}{query}"

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> Response:
        return self._client.send("GET", self._url(path, params), token=self._token)

    def get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        resp = self.get(path, params)
        if not resp.ok:
            raise HttpError("GET", self._url(path), resp.status, resp.text()[:200])
        return resp.json()

    def write(self, method: str, path: str, payload: Mapping[str, Any]) -> Response:
        """POST, PATCH or PUT a JSON body. Returns the response; the caller checks it."""
        return self._client.send(
            method,
            self._url(path),
            token=self._token,
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

    def delete(self, path: str) -> Response:
        """DELETE with no body. Returns the response; the caller checks it (a 404 may be acceptable)."""
        return self._client.send("DELETE", self._url(path), token=self._token)

    def pages(
        self, path: str, params: Mapping[str, Any] | None = None, key: str | None = None
    ) -> Iterator[Any]:
        """Yield every item of a paginated list by following the Link header's rel="next".

        No ``page`` parameter is sent: some lists (Dependabot alerts) refuse it and page by cursor.
        A next URL must be https on the same host as the API root; anything else is an error. A
        response without a next link is the last page.
        """
        root_host = urllib.parse.urlsplit(self._root).netloc.lower()
        url: str | None = self._url(path, {**(params or {}), "per_page": PER_PAGE})
        for _ in range(MAX_PAGES):
            resp = self._client.send("GET", url, token=self._token)
            if not resp.ok:
                raise HttpError("GET", url, resp.status, resp.text()[:200])
            data = resp.json()
            yield from (data[key] if key else data)
            url = _next_link(resp.headers.get("link"))
            if url is None:
                return
            parts = urllib.parse.urlsplit(url)
            if parts.scheme != "https" or parts.netloc.lower() != root_host:
                raise HttpError(
                    "GET", url, resp.status, "next link leaves the API host"
                )
        raise HttpError("GET", self._url(path), 0, f"more than {MAX_PAGES} pages")

    def download(self, url: str) -> bytes:
        return self._client.download(url, token=self._token)

    def read_file(self, repo: str, path: str, ref: str) -> str:
        """Read a text file through the Contents API. Raises HttpError when it is not readable."""
        data = self.get_json(
            f"/repos/{repo}/contents/{urllib.parse.quote(path)}", {"ref": ref}
        )
        if (
            not isinstance(data, dict)
            or data.get("type") != "file"
            or data.get("encoding") != "base64"
        ):
            raise HttpError("GET", self._url(path), 200, "not a base64 file")
        return base64.b64decode(data["content"]).decode("utf-8")


# --- feeds ---------------------------------------------------------------------------------------


def _kev_due_date(raw: object) -> date | None:
    """``dueDate`` (``YYYY-MM-DD``) of a KEV entry, or None when it is missing or not that shape."""
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _kev_forensic_triage(raw: object) -> bool | None:
    """``forensicTriage``: ``Yes`` is True, ``No`` is False, anything else (a missing field too) is None."""
    return {"Yes": True, "No": False}.get(raw) if isinstance(raw, str) else None


def _kev_released_at(raw: object) -> datetime | None:
    """The catalogue's ``dateReleased`` as UTC whole seconds, or None when it is missing or not a UTC time.

    The fraction of a second is dropped because ``FeedSnapshot`` takes whole seconds. The real value was not
    fetched when this was written; the fake in the tests has the shape ``2026-11-14T15:04:05.123Z``.
    """
    parsed = parse_osv_time(raw)
    return parsed.replace(microsecond=0) if parsed is not None else None


def fetch_kev(
    client: Client,
) -> tuple[dict[str, KevEntry], str | None, datetime | None]:
    """CISA KEV: id -> ``KevEntry``, the catalogue version, and the catalogue's ``dateReleased``.

    ``knownRansomwareCampaignUse``, ``dueDate`` and ``forensicTriage`` are shown, never used to decide. A
    missing or unreadable one of them is None for that entry and does not hide the entry's other fields.
    ``dateAdded`` stays required: an entry without it fails the whole fetch, as before.
    """
    resp = client.send("GET", KEV_URL, headers={"Accept": "application/json"})
    if not resp.ok:
        raise HttpError("GET", KEV_URL, resp.status)
    doc = resp.json()
    table: dict[str, KevEntry] = {}
    for entry in doc["vulnerabilities"]:
        flag = entry.get("knownRansomwareCampaignUse")
        table[entry["cveID"]] = KevEntry(
            date.fromisoformat(entry["dateAdded"]),
            True if flag == "Known" else None,
            _kev_due_date(entry.get("dueDate")),
            _kev_forensic_triage(entry.get("forensicTriage")),
        )
    return table, doc.get("catalogVersion"), _kev_released_at(doc.get("dateReleased"))


MAX_FEED_REDIRECTS = 3


def _get_following_same_host(
    client: Client, url: str, headers: Mapping[str, str]
) -> Response:
    """GET without a token, following at most MAX_FEED_REDIRECTS redirects to the same host over https.

    Raises:
        HttpError: A redirect without Location, to another host or scheme, or a further redirect.
    """
    origin = urllib.parse.urlsplit(url).netloc.lower()
    current = url
    resp = client.send("GET", current, headers=headers)
    hops = 0
    while resp.status in (301, 302, 303, 307, 308):
        location = resp.headers.get("location")
        if not location:
            raise HttpError("GET", current, resp.status, "redirect without Location")
        if hops >= MAX_FEED_REDIRECTS:
            raise HttpError("GET", current, resp.status, "too many redirects")
        target = urllib.parse.urljoin(current, location)
        parts = urllib.parse.urlsplit(target)
        if parts.scheme != "https" or parts.netloc.lower() != origin:
            raise HttpError(
                "GET", current, resp.status, "redirect leaves the original https host"
            )
        current = target
        resp = client.send("GET", current, headers=headers)
        hops += 1
    return resp


_EPSS_HEADER = re.compile(r"^#model_version:([^,]+),score_date:(\d{4}-\d{2}-\d{2})")


def fetch_epss(
    client: Client, wanted: Sequence[str]
) -> dict[str, tuple[str, date, str]]:
    """FIRST EPSS daily file: id -> (score, score date, model version), for the ids asked about.

    The model version and the date are read from the file's first line, not assumed.
    """
    resp = _get_following_same_host(client, EPSS_URL, {"Accept": "*/*"})
    if not resp.ok:
        raise HttpError("GET", EPSS_URL, resp.status)
    lines = io.TextIOWrapper(io.BytesIO(gzip.decompress(resp.body)), encoding="utf-8")
    header = _EPSS_HEADER.match(lines.readline())
    if header is None:
        raise HttpError("GET", EPSS_URL, resp.status, "no model_version header line")
    model, score_date = header.group(1), date.fromisoformat(header.group(2))
    wanted_set = set(wanted)
    table: dict[str, tuple[str, date, str]] = {}
    for row in csv.DictReader(lines):
        if row["cve"] in wanted_set:
            table[row["cve"]] = (row["epss"], score_date, model)
    return table


def parse_osv_time(raw: object) -> datetime | None:
    """An OSV timestamp (RFC 3339, may carry fractional seconds) as UTC, or None if unreadable."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.utcoffset() is not None else None


class Osv:
    """OSV.dev: which MAL- records mention a purl, and what one record says."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def query_purls(self, purls: Sequence[str]) -> dict[str, list[str]]:
        """purl -> ids of the vulnerabilities OSV lists for it (all kinds; the caller keeps MAL-)."""
        found: dict[str, list[str]] = {p: [] for p in purls}
        for start in range(0, len(purls), OSV_BATCH_SIZE):
            chunk = list(purls[start : start + OSV_BATCH_SIZE])
            tokens: dict[int, str | None] = dict.fromkeys(range(len(chunk)))
            pending = list(range(len(chunk)))
            for _ in range(OSV_MAX_PAGE_ROUNDS):
                queries = []
                for i in pending:
                    q: dict[str, Any] = {"package": {"purl": chunk[i]}}
                    if tokens[i]:
                        q["page_token"] = tokens[i]
                    queries.append(q)
                resp = self._client.send(
                    "POST",
                    f"{OSV_ROOT}/v1/querybatch",
                    headers={"Content-Type": "application/json"},
                    body=json.dumps({"queries": queries}).encode("utf-8"),
                )
                if not resp.ok:
                    raise HttpError("POST", f"{OSV_ROOT}/v1/querybatch", resp.status)
                results = resp.json()["results"]
                if len(results) != len(pending):
                    raise HttpError(
                        "POST",
                        f"{OSV_ROOT}/v1/querybatch",
                        resp.status,
                        "result count mismatch",
                    )
                still = []
                for i, result in zip(pending, results, strict=True):
                    found[chunk[i]].extend(v["id"] for v in result.get("vulns", []))
                    if result.get("next_page_token"):
                        tokens[i] = result["next_page_token"]
                        still.append(i)
                pending = still
                if not pending:
                    break
            else:
                raise HttpError(
                    "POST",
                    f"{OSV_ROOT}/v1/querybatch",
                    200,
                    "pagination did not finish",
                )
        return found

    def get_vuln(self, vuln_id: str) -> Response:
        return self._client.send(
            "GET", f"{OSV_ROOT}/v1/vulns/{urllib.parse.quote(vuln_id)}"
        )
