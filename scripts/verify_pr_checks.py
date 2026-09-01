#!/usr/bin/env python3
"""Confirm that CI passed for the commit a pull request will actually merge.

`gh pr checks` answers a different question than the one that matters. It reports the latest results,
not the results for the current head, so pushing one more commit and re-reading it returns the
previous commit's verdict with no indication that it is stale. That happened here: a pull request was
merged over a failing gate, the procedure "read the checks before merging" was restored in response,
and the very next pull request nearly consumed a stale result because a CHANGELOG commit was pushed
after the checks were read.

A procedure that has to be remembered at exactly one moment is more expensive than a command, so this
is a command. It resolves the pull request's head SHA and keys every lookup on it.

A workflow that has not started for that SHA is a failure here, not a pass. That is the case the
stale read produces: asking "did checks pass" without naming the commit lets another commit's success
answer for this one.

Runs skipped by a path filter are reported as filtered rather than missing, because a gate that
reports a false absence gets ignored.

One head SHA can carry several runs of the same workflow, and only the newest is the verdict. Editing
a pull request title re-runs `pr-title-check` against the unchanged head, so the earlier failure and
the later success both sit under that SHA. Counting every run made the failure permanent: the title
was fixed, the new run passed, and this command still refused the merge with no way to clear it short
of pushing a commit. Keying on the SHA is what keeps a *different* commit's result from answering, and
that is untouched here — within one SHA, the latest run per workflow is the answer.

Run:  python3 scripts/verify_pr_checks.py <pr-number>
      make pr-verify PR=<pr-number>
"""

from __future__ import annotations

import json
import subprocess
import sys

# Workflows expected on every commit. Anything outside this set is reported but not required, so a
# path-filtered workflow does not read as a missing check.
REQUIRED = ("ci", "gitleaks", "pr-title-check")


def latest_per_workflow(runs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split runs into the newest per workflow name and the ones it supersedes.

    Callers pass runs already filtered to one head SHA. `createdAt` is an ISO 8601 UTC string from
    `gh run list`, so it sorts lexicographically. Ties keep the order `gh` returned, which is
    newest-first, so the first occurrence wins.
    """
    newest: dict[str, dict] = {}
    for run in runs:
        name = str(run["name"])
        current = newest.get(name)
        if current is None or str(run.get("createdAt", "")) > str(
            current.get("createdAt", "")
        ):
            newest[name] = run
    kept = list(newest.values())
    kept_ids = {id(r) for r in kept}
    superseded = [r for r in runs if id(r) not in kept_ids]
    return kept, superseded


def gh_json(*args: str) -> object:
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=120, check=False
    )
    if result.returncode != 0:
        print(f"gh {' '.join(args)} failed: {result.stderr.strip()}", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(result.stdout or "null")


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print("usage: verify_pr_checks.py <pr-number>", file=sys.stderr)
        return 2
    number = sys.argv[1]

    pr = gh_json("pr", "view", number, "--json", "headRefOid,state,title")
    assert isinstance(pr, dict)
    head = pr["headRefOid"]
    print(f"PR #{number} head {head[:8]} ({pr['state']}): {pr['title']}")

    runs = gh_json(
        "run",
        "list",
        "--limit",
        "200",
        "--json",
        "headSha,name,status,conclusion,createdAt",
    )
    assert isinstance(runs, list)
    at_head = [r for r in runs if r["headSha"] == head]
    mine, superseded = latest_per_workflow(at_head)

    for run in sorted(superseded, key=lambda r: (str(r["name"]), str(r["createdAt"]))):
        print(
            f"  skip  {run['name']}: {run['conclusion'] or run['status']}"
            f" (superseded by a later run of the same workflow)"
        )

    problems: list[str] = []
    seen: set[str] = set()
    for run in sorted(mine, key=lambda r: str(r["name"])):
        seen.add(str(run["name"]))
        status, conclusion = run["status"], run["conclusion"]
        verdict = conclusion or status
        marker = "ok  " if conclusion == "success" else "BAD "
        print(f"  {marker}{run['name']}: {verdict}")
        if status != "completed":
            problems.append(f"{run['name']} has not finished ({status})")
        elif conclusion != "success":
            problems.append(f"{run['name']} concluded {conclusion}")

    for name in REQUIRED:
        if name not in seen:
            problems.append(
                f"{name} has no run for {head[:8]} - a workflow that has not started is not a pass"
            )
    for name in sorted(seen - set(REQUIRED)):
        print(
            f"  note  {name}: present, not required (path filters may skip it elsewhere)"
        )

    if problems:
        print(f"\nnot safe to merge #{number}:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(
        f"\nevery required workflow passed for {head[:8]}; #{number} is safe to merge"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
