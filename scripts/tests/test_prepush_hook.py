"""The tracked pre-push hook gates the commits pre-commit never saw.

Why this exists
---------------
`git commit` is not the only way a commit appears. Measured on git 2.54.0, with a pre-commit hook
wired and a commit demonstrably created in each case:

    git merge --no-ff        commit created, pre-commit did NOT run
    git cherry-pick          commit created, pre-commit did NOT run
    git revert               commit created, pre-commit did NOT run
    git rebase (conflict)    commit created, pre-commit did NOT run
    git commit  (control)    commit created, pre-commit ran

The control matters: without it, four zeros could equally mean the probe never wired the hook.

The rebase path is not hypothetical here. The CHANGELOG's top entry conflicts on every merge to
`main`, so every pull request gets rebased at least once, and resolving that conflict is an edit no
hook saw. Reported by a sibling repository, which enumerated the four paths after hitting that one.

Push is the choke point downstream of all four. As with pre-commit, git reads the hook's own exit
status, so no pipe upstream can hide a failing gate.

**Both directions are tested.** A hook that only ever blocks gets switched off, so the cases that
must be allowed — a branch deletion, a no-op push, the documented override — carry as much weight as
the refusal. Each runs the hook in a throwaway repository; the one thing that must not happen is a
test pushing from this one.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.tests.gitenv import owns_git_dir, scrubbed_env

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / ".githooks" / "pre-push"

ZERO = "0" * 40
REAL = "a" * 40


def run_hook(
    *, stdin: str, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the tracked hook in a scratch repository, feeding it a ref list on stdin.

    `GIT_*` is scrubbed before anything runs, `git init` included. Git exports `GIT_DIR` to a hook,
    and an inherited one makes `git init <path>` re-initialise the *outer* repository instead of
    creating the scratch one — so the scratch directory is not a repository at all and every verdict
    below would be about this repository. That is not hypothetical: a sibling test file in this
    repository hit it, and the first fix stripped the variables for the hook alone, leaving
    `git init` to inherit them.
    """
    env = scrubbed_env(env_extra)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        init = subprocess.run(
            ["git", "init", "-q", "-b", "feat/x", str(work)],
            env=env,
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
        )
        owned = subprocess.run(
            ["git", "rev-parse", "--absolute-git-dir"],
            env=env,
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
        )
        if init.returncode != 0 or not owns_git_dir(work, owned.stdout):
            raise AssertionError(
                "the scratch repository was not created, so every verdict would be about another "
                f"repository — git dir resolved to {owned.stdout.strip()!r}: "
                f"{init.stderr}{owned.stderr}"
            )
        return subprocess.run(
            ["bash", str(HOOK), "origin", "https://example.com/repo.git"],
            cwd=work,
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )


class TrackedHookIsWired(unittest.TestCase):
    def test_hook_is_tracked_and_executable(self) -> None:
        self.assertTrue(HOOK.is_file(), f"{HOOK} is missing")
        self.assertTrue(os.access(HOOK, os.X_OK), f"{HOOK} is not executable")

    def test_hook_still_targets_what_it_claims_to(self) -> None:
        """A hook can be gutted by an edit and still look present.

        The behaviour cases below cover what it does. This covers what it aims at: without it, an
        edit removing the `make all` call leaves every other test in this file passing, because a
        hook that does nothing exits 0 and the allow cases are satisfied.
        """
        body = HOOK.read_text(encoding="utf-8")
        self.assertIn("make all", body, "the hook no longer runs the gate")
        self.assertIn("SKIP_GATE", body, "the documented override is gone")

    def test_the_override_is_the_same_name_as_pre_commit(self) -> None:
        """Two names for one decision is a way to have the override not work when it matters."""
        self.assertIn(
            "SKIP_GATE",
            (REPO / ".githooks" / "pre-commit").read_text(encoding="utf-8"),
        )


class TrackedHookBlocks(unittest.TestCase):
    def test_a_push_of_new_commits_on_a_red_gate_is_refused(self) -> None:
        """A scratch repository has no Makefile, so `make all` fails there.

        That is the condition under test: the hook propagates a failing gate rather than reporting
        success, which is what a gate read off a pipe does.
        """
        result = run_hook(stdin=f"refs/heads/feat/x {REAL} refs/heads/feat/x {ZERO}\n")
        self.assertNotEqual(
            result.returncode, 0, "the hook allowed a push on a failing gate"
        )
        self.assertIn("make all failed", result.stderr)

    def test_one_real_ref_among_deletions_is_still_gated(self) -> None:
        """A mixed push arrives, so it is gated.

        Written because the obvious loop shape — decide from the last line read — passes the
        single-ref cases either way and lets a real ref through behind a deletion.
        """
        result = run_hook(
            stdin=(
                f"(delete) {ZERO} refs/heads/old {REAL}\n"
                f"refs/heads/feat/x {REAL} refs/heads/feat/x {ZERO}\n"
                f"(delete) {ZERO} refs/heads/older {REAL}\n"
            )
        )
        self.assertNotEqual(
            result.returncode, 0, "a real ref behind a deletion was not gated"
        )


class TrackedHookAllows(unittest.TestCase):
    def test_a_deletion_only_push_is_not_gated(self) -> None:
        """Deleting a merged branch brings no content, so a gate verdict says nothing about it.

        No SKIP_GATE here on purpose: if this needed the override, cleaning up branches would mean
        either a wait or a habit of bypassing the hook.
        """
        result = run_hook(stdin=f"(delete) {ZERO} refs/heads/merged {REAL}\n")
        self.assertEqual(
            result.returncode,
            0,
            f"the hook blocked a branch deletion:\n{result.stdout}{result.stderr}",
        )

    def test_an_empty_ref_list_is_not_gated(self) -> None:
        """git calls the hook with no lines when it finds nothing to push."""
        result = run_hook(stdin="")
        self.assertEqual(
            result.returncode,
            0,
            f"the hook blocked a no-op push:\n{result.stdout}{result.stderr}",
        )

    def test_the_override_is_honoured(self) -> None:
        """An escape hatch that does not work is a reason to delete the hook."""
        result = run_hook(
            stdin=f"refs/heads/feat/x {REAL} refs/heads/feat/x {ZERO}\n",
            env_extra={"SKIP_GATE": "1"},
        )
        self.assertEqual(
            result.returncode,
            0,
            f"the documented override did not work:\n{result.stdout}{result.stderr}",
        )

    def test_a_sha256_zero_id_is_recognised_as_a_deletion(self) -> None:
        """The zero id is 40 characters under SHA-1 and 64 under SHA-256.

        Matching the SHA-1 literal would keep passing every test above while silently gating every
        branch deletion in a repository that migrated to SHA-256.
        """
        result = run_hook(stdin=f"(delete) {'0' * 64} refs/heads/merged {'b' * 64}\n")
        self.assertEqual(
            result.returncode,
            0,
            f"a SHA-256 deletion was gated:\n{result.stdout}{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
