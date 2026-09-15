#!/usr/bin/env bash
# Run the gate, and assert it did not change the git index.
#
# Why this exists
# ---------------
# Two edits to `examples/client-access/teardown.sh` and its README once existed **only in the git
# index and never on disk** — in no commit, no stash and no reflog entry. Unstaging them destroyed
# the only copy; they were recovered from loose objects.
#
# The mechanism is documented in `scripts/tests/gitenv.py`: git exports `GIT_DIR` and
# `GIT_INDEX_FILE` to a hook, the tracked hooks run `make all`, and `make all` runs the test suite —
# so a test shelling out to git operates on the **real** repository. That known path is closed and
# asserted. This was a different path, and it is still unidentified.
#
# So this does not chase paths. It asserts the invariant: **running the gate does not change the
# index.** Any leak is caught regardless of which one it is.
#
# Why `git diff-index --cached` and not a hash of `.git/index`
# -----------------------------------------------------------
# The digest of `.git/index` moves on a `stat` refresh with no change of meaning, so it would report
# changes that are not changes — and a check that cries wolf gets bypassed. `diff-index --cached` is
# semantic: a refresh and a `touch` on a tracked file leave it identical, while one stray `git add`
# moves it.
#
# **Before and after, not against empty.** Inside `pre-commit` the index legitimately holds the
# commit being made, so the invariant is "unchanged", not "clean".
#
# **An unreadable snapshot is not an unchanged one.** Reading the index is checked separately from
# comparing it, because a failed read that returns an empty string compares equal to another failed
# read — two errors reported as a pass. This repository has produced that shape twice from a
# different cause: a command whose failure was read as an absent string.
#
# What this does not cover
# ------------------------
# A bare `make all` is unguarded. Wrapping the target from inside itself is not possible — a recipe
# runs after its prerequisites, so it cannot observe the state before they ran — and CI runs the
# leaf targets individually, where nothing is staged and no commit follows. The exposure this closes
# is the commit and push path, which is where the incident did its damage. `make gate` runs the
# guarded form by hand.
#
# Usage:  scripts/run_gate.sh <logfile>

set -uo pipefail

log="${1:?usage: run_gate.sh <logfile>}"

fail() { printf '\n\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

# What to diff the index against. Before the first commit HEAD does not resolve, so use the empty
# tree rather than letting the comparison fail.
if git rev-parse --verify --quiet HEAD >/dev/null; then
    base=HEAD
elif ! base="$(git hash-object -t tree /dev/null)"; then
    fail "cannot compute the empty tree — refusing to report the gate as clean"
fi

# Assignment carries the command's exit status, so a failed read is distinguishable from an empty
# diff. Calling a `fail` helper inside `$(...)` would not be: `exit` there leaves the subshell only,
# and the caller would continue with an empty snapshot.
if ! before="$(git diff-index --cached "$base")"; then
    fail "cannot read the index before the gate — refusing to report the gate as clean"
fi

printf '▶  make all (SKIP_GATE=1 to bypass)\n'
if ! make all >"$log" 2>&1; then
    tail -n 25 "$log" >&2
    fail "make all failed — full log: $log"
fi

if ! after="$(git diff-index --cached "$base")"; then
    fail "cannot read the index after the gate — refusing to report the gate as clean"
fi

if [ "$before" != "$after" ]; then
    printf '\n\033[31mthe gate changed the git index\033[0m\n' >&2
    printf '\n--- staged before the gate ---\n%s\n' "$before" >&2
    printf '\n--- staged after the gate ---\n%s\n' "$after" >&2
    fail "a check wrote to the real repository during 'make all'.

  This is the failure that once left two edits in the index and nowhere else.
  Look before unstaging — unstaging discards the only copy.

  Inspect:   git status --porcelain      (M or A whose file matches HEAD is index-only)
  Recover:   git fsck --unreachable | awk '\$2 == \"blob\" { print \$3 }'
             git cat-file -p <blob>      (then redirect it to the path)

  git fsck finds it only until the next gc."
fi

printf '\033[32m✅ make all\033[0m\n'
