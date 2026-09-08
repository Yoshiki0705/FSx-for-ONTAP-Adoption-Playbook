#!/usr/bin/env python3
"""Warn before merging a change to a workflow that no pull request runs.

A workflow triggered only by `schedule` or `workflow_dispatch` **never runs on a pull request**, so a
change to it can be merged with every check green and **its first execution observed by nobody**. The
green ticks are true and about other workflows.

A sibling repository measured the cost: it merged a workflow behind 31 passing checks, **none of which
were that workflow**, and the first manual dispatch failed. Diagnosing it took a second merge. This
repository is already in the same position - `cross-repo-external.yml` has `schedule` and
`workflow_dispatch` only - and had already recorded the symptom without naming the cause.

**The verdict is `ask`, never `block`.** Dispatching requires the branch to be pushed first, so the
sequence is push, dispatch, read the result, then merge, and a person has to drive it. There are
legitimate exceptions too: a comment-only edit, or a workflow waiting on a secret that does not exist
yet. **A block would be removed, and a removed guard protects nothing.**

Usage:
    python3 scripts/check_workflow_observability.py <file>...   # verdict for named files
    python3 scripts/check_workflow_observability.py --selftest  # parser and verdict corpus
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Triggers that cause a run a reviewer can see on the pull request.
OBSERVED = frozenset({"pull_request", "push", "pull_request_target", "merge_group"})

# `[ \t]`, never `\s`. A sibling reported this exact bug: `\s` matches a newline, the line anchor
# stops meaning anything, and every trigger after the first is lost - which silently reclassified two
# pull-request workflows as unobserved while its own selftest stayed green, because the selftest
# covered the verdict and not the parse.
TRIGGER = re.compile(r"^[ \t]{0,4}([A-Za-z_]+):", re.MULTILINE)
ON_BLOCK = re.compile(r"^on:[ \t]*(.*?)(?=^[A-Za-z_])", re.MULTILINE | re.DOTALL)

CASES = [
    ("on:\n  push:\n  pull_request:\n\njobs:\n", {"push", "pull_request"}),
    (
        "on:\n  schedule:\n    - cron: '0 0 * * 1'\n  workflow_dispatch:\n\njobs:\n",
        {"schedule", "workflow_dispatch"},
    ),
    # The row the `\s{0,4}` bug loses: everything after the first trigger.
    (
        "on:\n  push:\n    branches: [main]\n  pull_request:\n\njobs:\n",
        {"push", "pull_request"},
    ),
    ("on: [push, pull_request]\n\njobs:\n", {"push", "pull_request"}),
    ("on:\n  merge_group:\n\njobs:\n", {"merge_group"}),
    # The word appearing mid-line before the real key. Added because a mutation removing the `^`
    # anchor from ON_BLOCK survived every other case: without it the match starts inside the comment,
    # the lookahead stops at `name:`, and the body holds no triggers at all - a workflow that runs on
    # pull requests is then called unobserved.
    (
        "# runs on: a schedule\nname: x\non:\n  pull_request:\n\njobs:\n",
        {"pull_request"},
    ),
]


def triggers(text: str) -> set[str]:
    """Trigger names declared under `on:`, in both the block and inline forms."""
    match = ON_BLOCK.search(text)
    if not match:
        inline = re.search(r"^on:[ \t]*\[(.*?)\]", text, re.MULTILINE)
        return {t.strip() for t in inline.group(1).split(",")} if inline else set()
    body = match.group(1)
    inline = re.match(r"[ \t]*\[(.*?)\]", body)
    if inline:
        return {t.strip() for t in inline.group(1).split(",")}
    found = {m.group(1) for m in TRIGGER.finditer(body)}
    # Keys nested under a trigger are not triggers.
    return found & _TRIGGER_NAMES


_TRIGGER_NAMES = OBSERVED | {
    "schedule",
    "workflow_dispatch",
    "workflow_call",
    "workflow_run",
    "release",
    "issues",
    "issue_comment",
    "repository_dispatch",
    "create",
    "delete",
    "fork",
    "watch",
    "discussion",
    "label",
    "milestone",
    "page_build",
    "project",
    "public",
    "registry_package",
    "status",
    "deployment",
    "deployment_status",
    "check_run",
    "check_suite",
    "gollum",
    "member",
}


def observability(text: str) -> str:
    """Whether a pull request runs this workflow: "observed" or "unobserved"."""
    return "observed" if triggers(text) & OBSERVED else "unobserved"


def selftest() -> int:
    failures = 0
    for text, expected in CASES:
        got = triggers(text)
        if got != expected:
            print(f"FAIL: triggers() = {sorted(got)}, expected {sorted(expected)}")
            failures += 1
    for text, expected in CASES:
        want = "observed" if expected & OBSERVED else "unobserved"
        got = observability(text)
        if got != want:
            print(f"FAIL: observability() = {got!r}, expected {want!r}")
            failures += 1
    # A property, not a count. A sibling fixed a count against `*.yml` while scanning `*.y*ml`, so
    # two files sat outside the number and inside the scan. A property cannot drift from the scan.
    root = Path(__file__).resolve().parents[1] / ".github" / "workflows"
    for path in sorted(root.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        verdict = observability(text)
        found = triggers(text)
        if verdict == "observed" and not found & OBSERVED:
            print(f"FAIL: {path.name} called observed with no observing trigger")
            failures += 1
        if not found:
            print(f"FAIL: {path.name} parsed to no triggers at all")
            failures += 1
    print(
        f"selftest: {2 * len(CASES)} case(s) + every workflow parsed"
        if not failures
        else f"{failures} failure(s)"
    )
    return 1 if failures else 0


def changed_workflows(base: str = "origin/main") -> list[str]:
    """Workflow files this branch touches, relative to the base branch.

    **`cwd` is the repository root, taken from this file's own location.** Without it the guard was
    inert in the only configuration it runs in: a hook process does not start inside the repository,
    `git diff` failed there, and **the empty result read as "no unobserved workflow was touched".** It
    was tested from inside the repository and shipped - the same mistake a sibling reported after
    reading a local pass as evidence about a hosted runner.
    """
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD", "--", ".github/workflows"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            cwd=Path(__file__).resolve().parents[1],
            env={
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", ""),
            },
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [line for line in out.stdout.split() if line]


def hook() -> int:
    """PreToolUse entry point. Always exits 0; the verdict travels in the payload.

    **`ask`, never `block`.** Dispatching needs the branch pushed first, so the sequence is push,
    dispatch, read the result, then merge - a person has to drive it. Comment-only edits and
    workflows waiting on a secret that does not exist yet are legitimate exceptions. **A block would
    be removed, and a removed guard protects nothing.**
    """
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = str(payload.get("tool_input", {}).get("command", "")) or str(
        payload.get("command", "")
    )
    if "gh pr merge" not in command:
        return 0
    root = Path(__file__).resolve().parents[1]
    unobserved = [
        rel
        for rel in changed_workflows()
        if (root / rel).exists()
        and observability((root / rel).read_text(encoding="utf-8")) == "unobserved"
    ]
    if not unobserved:
        return 0
    reason = (
        "No pull request runs "
        + ", ".join(unobserved)
        + ", so the checks on this pull request say nothing about it and the first run after merging "
        "would be observed by nobody. Push the branch, dispatch the workflow, read that run, then "
        "merge."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    if "--hook" in argv:
        return hook()
    unobserved = [
        p
        for p in argv
        if Path(p).exists()
        and observability(Path(p).read_text(encoding="utf-8")) == "unobserved"
    ]
    if not unobserved:
        return 0
    print(
        "no pull request runs these workflows, so merging leaves the first run unobserved:"
    )
    for path in unobserved:
        print(f"  {path}")
    print("  Push the branch, dispatch it, read the result, then merge.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
