#!/usr/bin/env bash
# Run the gate, and assert it did not change the git index, config, or HEAD.
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
# index, the local config, or HEAD.** Any leak is caught regardless of which one it is. Two of those
# three — config and HEAD — were added after a sibling repository's leak rewrote `.git/config`
# (`user.*`, `core.bare`) and pushed commits onto a branch, neither of which an index diff sees.
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
# The snapshot is not exhaustive. It watches the state a leak has actually moved here and in a
# sibling — index, local config, HEAD — not every path git can write (refs other than HEAD, the
# stash, hooks installed at runtime). It is a floor that grows when a new path is observed, not a
# proof that no other path exists. The GIT_* strip on `make all` below is the complementary half:
# the snapshot catches a leak after the fact, the strip removes the inherited handle a leak needs.
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
#
# The index is not the only thing a leaked git operation can move. A sibling repository hit the same
# GIT_DIR leak and, besides the index, it rewrote `.git/config` (`user.*`, `core.bare`) and added
# commits to a branch. So three things are snapshotted before and after, not one:
#
#   index   — git diff-index --cached
#   config  — git config --local --list         (user.*, core.bare, core.hookspath, …)
#   HEAD    — git rev-parse HEAD + symbolic-ref  (a stray commit or a moved branch)
#
# Every read is guarded the same way and for the same reason: **an unreadable snapshot is not an
# unchanged one.** A read that fails and returns an empty string compares equal to another failed
# read, turning two errors into a pass. `symbolic-ref -q` exits non-zero on a detached HEAD, which
# is a legitimate state, not a read failure — so its empty output is captured with `|| true` and
# only a genuine command-substitution failure trips the guard.
snapshot() {
    # Echo the three facts as one blob. Any read failure returns non-zero to the caller.
    git diff-index --cached "$base" || return 1
    git config --local --list || return 1
    # Before the first commit HEAD does not resolve, and that is a defined state, not a read
    # failure — the same distinction the `$base` fallback above makes. Emit a stable marker so
    # "no commit yet" reads identically before and after the gate, while a HEAD that moves from a
    # real SHA to another (a stray commit) still shows as a change.
    if git rev-parse --verify --quiet HEAD >/dev/null; then
        git rev-parse HEAD || return 1
    else
        printf 'HEAD:unborn\n'
    fi
    # `symbolic-ref -q` exits non-zero on a detached HEAD, a legitimate state — so its empty output
    # is kept and only a crash (which `|| true` cannot mask, since it is the substitution that
    # would fail) matters. A branch that moves changes the rev-parse line above regardless.
    git symbolic-ref -q HEAD || true
}

if ! before="$(snapshot)"; then
    fail "cannot read the git state before the gate — refusing to report the gate as clean"
fi

printf '▶  make all (SKIP_GATE=1 to bypass)\n'
# Strip inherited GIT_* for this one invocation. When a hook runs under a linked worktree git
# exports GIT_DIR (and friends), and a gate check that shells out to git would then read or write
# whichever repository that points at rather than this one — the leak this whole file exists to
# contain, closed at the entrance for any path not yet identified. This is safe because no target
# in `make all` reads the staged index: the only readers of the index are the snapshots above and
# the test fixtures, which set GIT_INDEX_FILE explicitly on their own subprocesses. The snapshots
# stay outside this wrap deliberately — they *need* to see the real repository.
if ! env -u GIT_DIR -u GIT_INDEX_FILE -u GIT_WORK_TREE -u GIT_OBJECT_DIRECTORY -u GIT_COMMON_DIR \
    make all >"$log" 2>&1; then
    tail -n 25 "$log" >&2
    fail "make all failed — full log: $log"
fi

if ! after="$(snapshot)"; then
    fail "cannot read the git state after the gate — refusing to report the gate as clean"
fi

if [ "$before" != "$after" ]; then
    printf '\n\033[31mthe gate changed the git state (index, config, or HEAD)\033[0m\n' >&2
    printf '\n--- git state before the gate ---\n%s\n' "$before" >&2
    printf '\n--- git state after the gate ---\n%s\n' "$after" >&2
    fail "a check wrote to the real repository during 'make all'.

  This is the failure that once left two edits in the index and nowhere else.
  Look before unstaging — unstaging discards the only copy.

  Inspect:   git status --porcelain      (M or A whose file matches HEAD is index-only)
  Recover:   git fsck --unreachable | awk '\$2 == \"blob\" { print \$3 }'
             git cat-file -p <blob>      (then redirect it to the path)

  git fsck finds it only until the next gc."
fi

printf '\033[32m✅ make all\033[0m\n'
