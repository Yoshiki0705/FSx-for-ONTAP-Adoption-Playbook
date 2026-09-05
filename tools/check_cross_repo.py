#!/usr/bin/env python3
"""Verify that citations of sibling repositories are registered, and still say what we claim.

Why this exists
---------------
This repository does not re-measure what a sibling project has already measured. It cites. That
keeps one number in one place, which is the right call — and it introduces a failure mode with no
symptom: the cited file gets moved, or the claim gets retracted, and the sentence here goes on
saying what it always said.

Two checks, split by whether they need the network, following the same division as
`check_links.py`:

Offline (in `make all`)
    Every link into a sibling repository that appears in tracked prose has a row in
    `docs/ja/reference/cross-repo-index.md`, and every row of that table names a file in this
    repository that exists and actually contains the link. A citation nobody makes and a claim
    nobody registered are both defects.

External (opt-in)
    Each cited path is fetched and must still contain the recorded probe string. The probe is
    supposed to name the claim, not the heading, so that a retraction fails the gate rather than
    passing it.

The table is the single source. A separate machine-readable copy would be a second file to keep in
step, which is the failure this repository has already documented elsewhere.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "ja" / "reference" / "cross-repo-index.md"
OWNER = "Yoshiki0705"
THIS_REPO = "FSx-for-ONTAP-Adoption-Playbook"

TABLE_START = "<!-- cross-repo-table:start -->"
TABLE_END = "<!-- cross-repo-table:end -->"

# A citation is a blob link into a sibling repository. Tree and bare-repository links are
# navigation, not citation, so they are out of scope here — check_links.py already resolves them.
BLOB_LINK = re.compile(
    rf"https://github\.com/{OWNER}/(?P<repo>[A-Za-z0-9._-]+)/blob/(?P<ref>[^/\s)]+)/(?P<path>[^\s)\"'#]+)"
)

# Files whose prose can carry citations. Code and templates are excluded: a citation belongs next to
# the claim it supports, and neither of those states claims.
PROSE_GLOBS = ("docs/**/*.md", "*.md", "llms.txt")
SKIP_PARTS = {".private", ".kiro", ".venv", "node_modules", "_template"}


@dataclass(frozen=True)
class Row:
    citing: str
    repo: str
    path: str
    probe: str
    what: str
    line: int


def strip_code(text: str) -> str:
    """Blank out fenced blocks so an example link inside one is not read as a citation."""
    out, fenced = [], False
    for line in text.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else line)
    return "\n".join(out)


def prose_files() -> list[Path]:
    seen: dict[Path, None] = {}
    for pattern in PROSE_GLOBS:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            if SKIP_PARTS & set(path.relative_to(ROOT).parts):
                continue
            seen[path] = None
    return sorted(seen)


def parse_table() -> tuple[list[Row], list[str]]:
    problems: list[str] = []
    if not INDEX.exists():
        return [], [f"{INDEX.relative_to(ROOT)} is missing"]

    lines = INDEX.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if TABLE_START in line)
        end = next(i for i, line in enumerate(lines) if TABLE_END in line)
    except StopIteration:
        return [], [
            (
                f"{INDEX.relative_to(ROOT)}: the table markers "
                f"{TABLE_START} / {TABLE_END} must both be present"
            )
        ]

    rows: list[Row] = []
    for offset, raw in enumerate(lines[start + 1 : end], start=start + 2):
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 5:
            problems.append(
                f"{INDEX.relative_to(ROOT)}:{offset}: expected 5 columns, found {len(cells)}. "
                "The gate reads this table, so a changed shape is a broken gate."
            )
            continue
        if cells[0].startswith("---") or cells[0] in {"引用元"}:
            continue
        citing, repo, path, probe, what = (c.strip("`") for c in cells)
        if not all((citing, repo, path, probe)):
            problems.append(
                f"{INDEX.relative_to(ROOT)}:{offset}: a required cell is empty"
            )
            continue
        rows.append(Row(citing, repo, path, probe, what, offset))
    return rows, problems


def check_offline(rows: list[Row]) -> list[str]:
    problems: list[str] = []

    # Registered rows must point at a real citing file that really carries the link.
    for row in rows:
        citing = ROOT / row.citing
        if not citing.exists():
            problems.append(
                f"{INDEX.relative_to(ROOT)}:{row.line}: citing file {row.citing} does not exist"
            )
            continue
        body = strip_code(citing.read_text(encoding="utf-8"))
        wanted = f"https://github.com/{OWNER}/{row.repo}/blob/"
        if wanted not in body or row.path not in body:
            problems.append(
                f"{INDEX.relative_to(ROOT)}:{row.line}: {row.citing} does not link to "
                f"{row.repo}/{row.path}. A registered citation that nobody makes is a stale row."
            )

    # Every citation in prose must be registered, per citing file. Keying on the cited path
    # alone would let a second document cite the same claim unrecorded — and when a probe does
    # fail, what you need is every file that has to be revisited, not one of them.
    registered = {(r.citing, r.repo, r.path) for r in rows}
    for path in prose_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == INDEX.relative_to(ROOT).as_posix():
            continue
        body = strip_code(path.read_text(encoding="utf-8"))
        for match in BLOB_LINK.finditer(body):
            repo, cited = match.group("repo"), match.group("path")
            if repo == THIS_REPO:
                continue  # A link into our own repository is not a cross-repo citation.
            if (rel, repo, cited) not in registered:
                problems.append(
                    f"{rel}: cites {repo}/{cited} with no row for this file in "
                    f"{INDEX.relative_to(ROOT)}. Add one, with a probe string naming the claim. "
                    "Another file citing the same path does not cover this one."
                )
    return problems


def check_external(rows: list[Row]) -> list[str]:
    problems: list[str] = []
    cache: dict[tuple[str, str], str | None] = {}
    for row in rows:
        key = (row.repo, row.path)
        if key not in cache:
            url = (
                f"https://raw.githubusercontent.com/{OWNER}/{row.repo}/main/{row.path}"
            )
            request = urllib.request.Request(
                url, headers={"User-Agent": "cross-repo-check"}
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    cache[key] = response.read().decode("utf-8", "replace")
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
                cache[key] = None
                problems.append(f"{row.repo}/{row.path}: cannot fetch ({exc})")
        body = cache[key]
        if body is None:
            continue
        if row.probe not in body:
            problems.append(
                f"{row.repo}/{row.path}: the probe {row.probe!r} is gone. Either the claim moved "
                f"or it was retracted — check before adjusting {row.citing}."
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--external",
        action="store_true",
        help="Fetch each cited file and confirm the probe string is still present.",
    )
    args = parser.parse_args()

    rows, problems = parse_table()
    problems += check_offline(rows)
    if args.external and not problems:
        problems += check_external(rows)

    if problems:
        print(f"cross-repo check failed ({len(problems)} issue(s)):")
        for problem in problems:
            print(f"  {problem}")
        return 1

    scope = "and every probe still present" if args.external else "registered"
    print(f"cross-repo: {len(rows)} citation(s) {scope}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
