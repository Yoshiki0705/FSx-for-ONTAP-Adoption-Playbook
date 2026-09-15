#!/usr/bin/env python3
"""Protect the strings other repositories pin inside this repository's files.

Why this exists
---------------
`check_cross_repo.py` guards the outbound direction: the claims this repository cites, and whether
they still exist where they were cited from. The inbound direction had nothing. Another repository
had pinned three strings inside `docs/ja/reference/comparison/block-to-file-routes.md` -- two
adjacent lines carrying all three -- and nothing here said so. Rewording that paragraph would have
broken their gate with no signal on this side, and the three were found only because that
repository mentioned the risk in passing.

Two failures, not one:

  absent      The string is gone. Their gate fails, and it reads as a retraction of a claim they
              depend on rather than as an edit here.
  duplicated  The string now occurs more than once. Their gate stays green while one copy can be
              reworded, so the probe silently stops guarding anything. This is not hypothetical:
              writing prose *about* a pinned string is the ordinary way to create the second copy,
              and the repository that reported the class did exactly that while documenting it.

So the rule for an inbound probe is stricter than "present": exactly one occurrence, in body text.
A heading-only match is rejected for the same reason it is on the outbound side -- a section keeps
its title while its content is replaced.

Coverage is partial by construction
-----------------------------------
Discovery reads each sibling's *published* contract. A sibling that publishes none is unknown, not
clean, and is recorded that way in the artifact. Nothing here can enumerate a probe nobody
published, so the artifact is a floor on what depends on this repository, never a ceiling.

Run:      python3 tools/check_inbound_probes.py            (offline; reads our own files)
Refresh:  python3 tools/check_inbound_probes.py --refresh   (network; rewrites the artifact)
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

from check_cross_repo import OWNER, REPO_REF, THIS_REPO, prose_files, strip_code

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "docs" / "agent" / "inbound-probe-contract.txt"

# Where a sibling publishes the strings it pins elsewhere. Same path this repository uses, because
# the convention travels with the tool.
SIBLING_CONTRACT = "docs/agent/cross-repo-probe-contract.txt"

UNKNOWN_MARKER = (
    "# unknown (publishes no contract; absence of a contract is not absence of probes):"
)

HEADER = """\
# Probe strings that other repositories pin inside THIS repository's files. Generated - do not
# hand-edit.
#
# Refresh with: python3 tools/check_inbound_probes.py --refresh
#
# Why this file is load-bearing: each string below is an interface. Editing the line it sits on
# breaks a gate in the repository named in the first column, and nothing in that repository can
# warn us first - the check runs there, against a tree they do not have.
#
# The gate here enforces more than presence. A string must occur EXACTLY ONCE, in body text:
#   - zero occurrences  their gate fails, and reads as a retraction rather than as our edit
#   - two or more       their gate stays green while one copy can be reworded, so it guards nothing
#   - heading only      the section keeps its title while the content is replaced
#
# Writing prose about a pinned string is the ordinary way to create a second copy. Describe it
# instead of quoting it.
#
# COVERAGE IS A FLOOR, NOT A CEILING. Discovery reads each sibling's published contract. Siblings
# that publish none are listed at the end as unknown. A probe nobody published cannot be found here.
#
# Format: <citing repo> TAB <our path> TAB <role> TAB <probe>, sorted.
"""


class Row:
    __slots__ = ("citing", "path", "probe", "role")

    def __init__(self, citing: str, path: str, role: str, probe: str) -> None:
        self.citing = citing
        self.path = path
        self.role = role
        self.probe = probe

    def key(self) -> tuple[str, str, str, str]:
        return (self.citing, self.path, self.role, self.probe)

    def line(self) -> str:
        return "\t".join(self.key())


def parse_contract() -> tuple[list[Row], list[str], list[str]]:
    """Return (rows, unknown repos, problems)."""
    if not CONTRACT.exists():
        return (
            [],
            [],
            [
                (
                    f"{CONTRACT.relative_to(ROOT)} is missing. Run "
                    "`python3 tools/check_inbound_probes.py --refresh` to create it"
                )
            ],
        )
    rows: list[Row] = []
    unknown: list[str] = []
    problems: list[str] = []
    for number, raw in enumerate(
        CONTRACT.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if raw.startswith(UNKNOWN_MARKER):
            unknown = [part for part in raw[len(UNKNOWN_MARKER) :].split() if part]
            continue
        if raw.startswith("#") or not raw.strip():
            continue
        parts = raw.split("\t")
        if len(parts) != 4:
            problems.append(
                f"{CONTRACT.relative_to(ROOT)}:{number}: expected 4 tab-separated fields, got "
                f"{len(parts)}"
            )
            continue
        rows.append(Row(*parts))
    return rows, unknown, problems


def verdict(probe: str, text: str) -> str:
    """Classify one pinned string against the document that holds it.

    Kept pure and separate so the four outcomes can be pinned as a truth table. Three of them are
    silent in normal use — a passing gate looks identical whether the rule is right or absent.
    """
    hits = [line for line in strip_code(text).splitlines() if probe in line]
    if not hits:
        return "absent"
    if all(line.lstrip().startswith("#") for line in hits):
        return "heading-only"
    if len(hits) > 1:
        return "duplicated"
    return "ok"


EXPLANATION = {
    "absent": (
        "and it is gone. Their gate will read this as a retraction of the claim, not as an edit "
        "on our side"
    ),
    "heading-only": (
        "and it now matches only a heading, so their probe survives the section being replaced. "
        "Keep the claim in body text"
    ),
    "duplicated": (
        "more than once, so one copy can be reworded with their gate still green. Describe the "
        "string instead of quoting it"
    ),
}


def check(rows: list[Row]) -> list[str]:
    """Every pinned string occurs exactly once, in body text, in the file it is pinned to."""
    problems: list[str] = []
    for row in rows:
        target = ROOT / row.path
        if not target.exists():
            problems.append(
                f"{row.path}: does not exist, but {row.citing} pins {row.probe!r} in it. "
                "Moving or deleting the file breaks their gate — tell them before doing it"
            )
            continue
        result = verdict(row.probe, target.read_text(encoding="utf-8"))
        if result != "ok":
            problems.append(
                f"{row.path}: {row.citing} pins {row.probe!r} here {EXPLANATION[result]}"
            )
    return problems


def sibling_repos() -> list[str]:
    """Sibling repositories named anywhere in tracked prose.

    Derived rather than listed: a hardcoded set is a second copy of something the documents already
    say, and it is the copy that stops being updated.
    """
    found: set[str] = set()
    for path in prose_files():
        for match in REPO_REF.finditer(strip_code(path.read_text(encoding="utf-8"))):
            repo = match.group("repo")
            if repo != THIS_REPO:
                found.add(repo)
    return sorted(found)


def fetch(repo: str, path: str) -> str | None:
    result = subprocess.run(
        ["gh", "api", f"repos/{OWNER}/{repo}/contents/{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        content = json.loads(result.stdout)["content"]
    except (json.JSONDecodeError, KeyError):
        return None
    return base64.b64decode(content).decode("utf-8", "replace")


def refresh() -> int:
    rows: list[Row] = []
    unknown: list[str] = []
    for repo in sibling_repos():
        body = fetch(repo, SIBLING_CONTRACT)
        if body is None:
            unknown.append(repo)
            continue
        for raw in body.splitlines():
            if raw.startswith("#") or not raw.strip():
                continue
            parts = raw.split("\t")
            if len(parts) == 4 and parts[0] == THIS_REPO:
                rows.append(Row(repo, parts[1], parts[2], parts[3]))

    lines = sorted({row.line() for row in rows})
    body = HEADER + "\n" + "\n".join(lines) + ("\n" if lines else "")
    body += f"\n{UNKNOWN_MARKER} " + " ".join(unknown) + "\n"

    previous = CONTRACT.read_text(encoding="utf-8") if CONTRACT.exists() else ""
    CONTRACT.write_text(body, encoding="utf-8")

    print(
        f"inbound probes: {len(lines)} pinned into this repository by "
        f"{len({row.citing for row in rows})} repositor(ies); {len(unknown)} sibling(s) publish no "
        "contract and are recorded as unknown"
    )
    if previous and previous != body:
        print("  the artifact changed — review the diff before committing")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-read each sibling's published contract and rewrite the artifact (network)",
    )
    args = parser.parse_args()

    if args.refresh:
        return refresh()

    rows, unknown, problems = parse_contract()
    problems += check(rows)

    if problems:
        print(f"inbound probes failed ({len(problems)} issue(s)):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    note = (
        f"; {len(unknown)} sibling(s) publish no contract, so coverage is a floor"
        if unknown
        else ""
    )
    print(
        f"inbound probes: {len(rows)} pinned string(s) present exactly once in body text{note}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
