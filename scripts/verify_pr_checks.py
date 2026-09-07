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
import os
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


def _git(*args: str) -> str:
    """Run git with GIT_* scrubbed and return stdout, or "" on any failure.

    Empty rather than raising: these two helpers guard against a stale API answer, and a guard that
    cannot run must not stop the check it guards. GIT_* is scrubbed because an inherited GIT_DIR
    would make this report another repository's HEAD, inventing a mismatch that refuses every run.
    The same inheritance already fabricated a committed file in this repository.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, env=env, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def git_head() -> str:
    return _git("rev-parse", "HEAD")


def git_branch() -> str:
    return _git("symbolic-ref", "--quiet", "--short", "HEAD")


def head_verdict(*, branch: str, pr_branch: str, local: str, head: str) -> str:
    """Whether the API's head can be trusted for this invocation: "answer" or "stale".

    Extracted from `main` on a sibling repository's argument, and it is a better argument than the
    one it replaces. **A prohibition written in a comment is only enforceable if the code enforcing
    it can be reached by a test.** This decision lived inside `main`, so the only tests possible were
    assertions that the source *contained* certain strings — which cannot distinguish a behaviour
    from its spelling, and which a mutation kills trivially without saying anything.

    The rule, as a truth table rather than as prose:

    | branch | equals the PR's branch | SHAs equal | verdict |
    |---|---|---|---|
    | absent (detached) | — | — | `answer` — nothing to compare against |
    | present | no | — | `answer` — another branch, or someone else's pull request |
    | present | yes | yes | `answer` |
    | present | yes | **no** | **`stale`** |

    The third row is the one that matters and the reason the comparison is scoped: comparing
    unconditionally refuses every run from `main` and against anyone else's pull request, and **a
    check that refuses ordinary use gets worked around**, which is the failure this command exists to
    prevent.
    """
    if not branch or branch != pr_branch:
        return "answer"
    if local and local != head:
        return "stale"
    return "answer"


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print("usage: verify_pr_checks.py <pr-number>", file=sys.stderr)
        return 2
    number = sys.argv[1]

    pr = gh_json("pr", "view", number, "--json", "headRefOid,headRefName,state,title")
    assert isinstance(pr, dict)
    head = pr["headRefOid"]
    print(f"PR #{number} head {head[:8]} ({pr['state']}): {pr['title']}")

    # This command exists because `gh pr checks` answers about the latest run rather than the
    # current head — and it had the same defect one layer up. Called straight after a push, the API
    # still reports the previous head, so every lookup below keys on a SHA that is correct and
    # stale. That happened four times in one session. Twice the old SHA had failed, so the answer
    # was "not safe to merge" and the wrong reason went unnoticed; had the old SHA passed, this
    # would have cleared a merge for a commit it never examined.
    #
    # A stale answer is not a verdict, so it fails rather than passes.
    #
    # Compared only when the checked-out branch *is* the pull request's branch. Comparing
    # unconditionally refuses every run from main and against anyone else's pull request, which is
    # over-blocking — and a check that refuses ordinary use gets worked around, which is the
    # failure this command exists to prevent. The first version of this guard did exactly that.
    branch = git_branch()
    local = git_head() if branch else ""
    if (
        head_verdict(
            branch=branch,
            pr_branch=str(pr.get("headRefName", "")),
            local=local,
            head=head,
        )
        == "stale"
    ):
        print(
            f"\nrefusing to answer: {branch} is at {local[:8]} but the API reports {head[:8]}.\n"
            "  After a push the API serves the previous head for a while, so every verdict below\n"
            "  would be correct about the wrong commit. Wait and re-run.\n"
            "  If it is not a lag, the last commit was never pushed.",
            file=sys.stderr,
        )
        return 1

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
