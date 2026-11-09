#!/usr/bin/env python3
"""Keep the external primary sources this repository tracks from going stale unnoticed.

Why this exists
---------------
FinOps for AI and Tokenomics rest on facts with a short shelf life: an industry standard that was
set up in 2026-08 and is still being written, a FOCUS specification whose version keeps moving, and
cloud pricing that changes whenever a provider decides. A claim written from memory, or from a
confirmation made months ago and never revisited, reads to a reader as current. The silent failure
is a number or a "not yet supported" that was true once and is quoted as if it still is.

So the tracked primary sources carry a `last_checked` date and a `review_interval_days`, and this
gate fails when a row is older than its interval. It is the freshness analogue of
`check_cross_repo.py`: that one asks whether a sibling repository's claim still holds; this one asks
whether an external source was confirmed recently enough to keep citing.

Two checks, split by whether they need the network, following the same division as
`check_links.py` and `check_cross_repo.py`:

Offline (in `make all`)
    Every row of the tracking table in `docs/ja/reference/external-sources.md` parses, has a valid
    `last_checked` date that is not in the future, a positive `review_interval_days`, and is not
    older than that interval. This runs in the commit gate because it needs no network.

External (opt-in)
    Each tracked URL is fetched and must still resolve. A source that has moved or been taken down
    cannot be the thing a reader is sent to. This stays out of the commit gate for the same reason
    `cross-repo-external` does: CI is not sent onto the public network.

The table is the single source. A second hand-maintained copy of its contents is not kept, for the
reason stated at length in `check_cross_repo.py`: a copy nothing compares drifts.

Usage:
    python3 tools/check_source_freshness.py             # offline freshness check (a gate)
    python3 tools/check_source_freshness.py --external  # also confirm each URL resolves (network)
    python3 tools/check_source_freshness.py --selftest  # verdict truth table, no filesystem
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE_FILE = ROOT / "docs" / "ja" / "reference" / "external-sources.md"

TABLE_START = "<!-- source-freshness:start -->"
TABLE_END = "<!-- source-freshness:end -->"

# The columns the table must have, in this order. Changing the order or adding a column is a
# parse failure rather than a silent misread: a row read into the wrong field would validate a
# date against a URL and pass.
COLUMNS = ("id", "url", "last_checked", "review_interval_days", "scope")

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class Source:
    id: str
    url: str
    last_checked: str
    review_interval_days: str
    scope: str
    line: int


def _split_row(line: str) -> list[str] | None:
    """Split a Markdown table row into trimmed cells, or None if it is not a table row."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    # Drop the leading and trailing pipe, then split. A separator row (---|---) returns cells
    # that are all dashes, which the caller skips.
    inner = stripped.strip("|")
    return [cell.strip() for cell in inner.split("|")]


def parse_table(text: str) -> tuple[list[Source], list[str]]:
    """Parse the fenced tracking table. Returns (sources, structural errors)."""
    errors: list[str] = []
    if TABLE_START not in text or TABLE_END not in text:
        return [], [f"tracking markers {TABLE_START} / {TABLE_END} not found"]

    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if TABLE_START in ln)
    end = next(i for i, ln in enumerate(lines) if TABLE_END in ln)
    if end < start:
        return [], ["source-freshness:end appears before source-freshness:start"]

    sources: list[Source] = []
    header_seen = False
    for offset, raw in enumerate(lines[start + 1 : end], start=start + 2):
        cells = _split_row(raw)
        if cells is None:
            continue
        if all(set(cell) <= {"-", ":"} and cell for cell in cells):
            continue  # separator row
        if not header_seen:
            header_seen = True
            if tuple(cells) != COLUMNS:
                errors.append(f"table header is {tuple(cells)}, expected {COLUMNS}")
            continue
        if len(cells) != len(COLUMNS):
            errors.append(
                f"line {offset}: row has {len(cells)} cells, expected {len(COLUMNS)}"
            )
            continue
        sources.append(Source(*cells, line=offset))

    if not header_seen:
        errors.append("tracking table has no header row")
    return sources, errors


def validate(source: Source, *, today: dt.date) -> list[str]:
    """Return freshness/schema errors for one row (offline)."""
    errors: list[str] = []
    where = f"line {source.line} ({source.id or '?'})"

    if not ID_RE.match(source.id):
        errors.append(f"{where}: id must be lowercase alphanumeric with hyphens")

    if not source.url.startswith(("http://", "https://")):
        errors.append(f"{where}: url must be an absolute http(s) URL")

    try:
        checked = dt.date.fromisoformat(source.last_checked)
    except ValueError:
        errors.append(
            f"{where}: last_checked {source.last_checked!r} is not YYYY-MM-DD"
        )
        return errors
    if checked > today:
        errors.append(f"{where}: last_checked {source.last_checked} is in the future")

    try:
        interval = int(source.review_interval_days)
    except ValueError:
        errors.append(
            f"{where}: review_interval_days {source.review_interval_days!r} is not an integer"
        )
        return errors
    if interval <= 0:
        errors.append(f"{where}: review_interval_days must be positive")
        return errors

    if not source.scope.strip():
        errors.append(f"{where}: scope must say what to confirm on review")

    age = (today - checked).days
    if age > interval:
        errors.append(
            f"{where}: last confirmed {age} days ago, exceeds review interval of "
            f"{interval} days -- open {source.url}, confirm its scope, then update last_checked"
        )
    return errors


def check_reachable(
    url: str,
    *,
    opener=urllib.request.urlopen,
) -> str | None:
    """Return an error string if the URL does not resolve, else None."""
    request = urllib.request.Request(
        url, method="HEAD", headers={"User-Agent": "source-freshness-check"}
    )
    try:
        with opener(request, timeout=30) as response:
            status = getattr(response, "status", 200)
        if status >= 400:
            return f"{url} returned HTTP {status}"
    except urllib.error.HTTPError as exc:
        # Some servers reject HEAD but serve GET. Retry once with GET before reporting.
        if exc.code in (403, 405):
            try:
                get = urllib.request.Request(
                    url, headers={"User-Agent": "source-freshness-check"}
                )
                with opener(get, timeout=30) as response:
                    status = getattr(response, "status", 200)
                if status >= 400:
                    return f"{url} returned HTTP {status}"
                return None
            except (urllib.error.URLError, TimeoutError) as retry_exc:
                return f"{url} did not resolve on GET: {retry_exc}"
        return f"{url} returned HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError) as exc:
        return f"{url} did not resolve: {exc}"
    return None


# ---- selftest ----------------------------------------------------------------------------------

# (last_checked, review_interval_days, days_ago_today_is_from_checked, expect_stale)
_SELFTEST_CASES = [
    ("2026-01-01", "90", 10, False),  # fresh: checked 10 days ago, interval 90
    ("2026-01-01", "90", 100, True),  # stale: checked 100 days ago, interval 90
    ("2026-01-01", "30", 29, False),  # fresh at the boundary minus one
    ("2026-01-01", "30", 31, True),  # stale one past the boundary
]


def _selftest() -> int:
    failures = 0
    base = dt.date(2026, 1, 1)
    for last_checked, interval, days_ago, expect_stale in _SELFTEST_CASES:
        today = base + dt.timedelta(days=days_ago)
        source = Source(
            id="x",
            url="https://example.com",
            last_checked=last_checked,
            review_interval_days=interval,
            scope="s",
            line=1,
        )
        errors = validate(source, today=today)
        is_stale = any("exceeds review interval" in e for e in errors)
        if is_stale != expect_stale:
            print(
                f"selftest FAIL: checked={last_checked} interval={interval} "
                f"days_ago={days_ago} -> stale={is_stale}, expected {expect_stale}",
                file=sys.stderr,
            )
            failures += 1

    # Structural: a mismatched header must fail to parse.
    bad = f"{TABLE_START}\n\n| id | wrong |\n|---|---|\n\n{TABLE_END}\n"
    _, bad_errors = parse_table(bad)
    if not bad_errors:
        print("selftest FAIL: a wrong header parsed cleanly", file=sys.stderr)
        failures += 1

    if failures:
        return 1
    print("check_source_freshness selftest: all cases pass")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--external",
        action="store_true",
        help="also confirm each URL resolves (network)",
    )
    parser.add_argument(
        "--selftest", action="store_true", help="run the verdict truth table and exit"
    )
    args = parser.parse_args()

    if args.selftest:
        return _selftest()

    try:
        text = TABLE_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"error: {TABLE_FILE.relative_to(ROOT)} is missing", file=sys.stderr)
        return 1

    sources, errors = parse_table(text)
    today = dt.datetime.now(dt.UTC).date()
    for source in sources:
        errors.extend(validate(source, today=today))

    if args.external:
        for source in sources:
            problem = check_reachable(source.url)
            if problem:
                errors.append(f"line {source.line} ({source.id}): {problem}")

    if errors:
        print(
            f"\nsource-freshness check failed ({len(errors)} issue(s)):",
            file=sys.stderr,
        )
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1

    scope = "offline + reachability" if args.external else "offline"
    print(
        f"source-freshness: {len(sources)} source(s) within review interval ({scope})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
