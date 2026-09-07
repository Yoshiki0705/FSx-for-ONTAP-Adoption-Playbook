"""The tracked pre-commit hook refuses a trunk commit and refuses a red gate.

Two failures in this repository's history are the reason this hook exists, and both were
failures of *remembering* rather than of knowing:

- a commit landed on `main` because HEAD had moved back after a branch was created;
- a commit was made on a red gate twice, because `make all | tail` returns tail's exit
  status and the skimmed output did not show the failure.

A hook is only worth having if it fails when it should. Proving it blocks is also not
enough on its own — a hook that blocks ordinary work gets switched off, so the allow
direction is tested too. Each case runs the hook in a throwaway repository, because the
one thing that must not happen is a test that commits to this one.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / ".githooks" / "pre-commit"


def run_hook(
    *, branch: str, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the tracked hook inside a scratch repository on the named branch."""
    # Strip every GIT_* variable inherited from the caller, and build the environment BEFORE
    # anything runs, because `git init` needs it too.
    #
    # Git exports GIT_DIR and GIT_INDEX_FILE to a pre-commit hook. When the hook runs this
    # suite, an inherited GIT_DIR does two things, and the second is why the first was hard to
    # see: `git symbolic-ref` inside the scratch repository answers for the *outer* repository,
    # and `git init <path>` **re-initialises the outer repository instead of creating the scratch
    # one** — `warning: re-init: ignored --initial-branch` is that happening. The scratch
    # directory is then not a repository at all, HEAD resolves to `detached`, no trunk branch is
    # ever seen, and the trunk cases pass by reporting on an environment they did not set.
    #
    # Found by the hook running this suite during a commit. The first fix stripped the variables
    # only for the hook invocation, which left `git init` inheriting them — **the same defect with
    # a narrower blast radius**, and it still wrote to the real repository.
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        **(env_extra or {}),
    }
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        init = subprocess.run(
            ["git", "init", "-q", "-b", branch, str(work)],
            env=env,
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
        )
        if init.returncode != 0 or "re-init" in init.stderr:
            raise AssertionError(
                "the scratch repository was not created cleanly, so any verdict below would be "
                f"about the wrong repository: {init.stdout}{init.stderr}"
            )
        (work / "seed.txt").write_text("seed\n", encoding="utf-8")
        return subprocess.run(
            ["bash", str(HOOK)],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )


class TrackedHookIsWired(unittest.TestCase):
    def test_hook_is_tracked_and_executable(self) -> None:
        """A hook under ~/.config or .git/hooks is invisible to every other clone.

        AGENTS.md already says this about the irreversible-ops guard. The repository
        was nonetheless in that state: the only pre-commit hook lived in a global
        hooksPath, so it existed on exactly one machine and drifted unobserved.
        """
        self.assertTrue(HOOK.is_file(), f"{HOOK} is missing")
        self.assertTrue(os.access(HOOK, os.X_OK), f"{HOOK} is not executable")

    def test_wiring_instruction_is_documented(self) -> None:
        """core.hooksPath is per-clone, so the hook does nothing until it is set."""
        needle = "core.hooksPath .githooks"
        found = [
            p.name
            for p in (REPO / "AGENTS.md", REPO / "CONTRIBUTING.md")
            if p.is_file() and needle in p.read_text(encoding="utf-8")
        ]
        self.assertTrue(
            found, f"no tracked document tells a contributor to set {needle!r}"
        )


class TrackedHookBlocks(unittest.TestCase):
    def test_commit_on_main_is_refused(self) -> None:
        result = run_hook(branch="main", env_extra={"SKIP_GATE": "1"})
        self.assertNotEqual(result.returncode, 0, "the hook allowed a commit on main")
        self.assertIn("main", result.stderr)

    def test_commit_on_master_is_refused(self) -> None:
        result = run_hook(branch="master", env_extra={"SKIP_GATE": "1"})
        self.assertNotEqual(result.returncode, 0, "the hook allowed a commit on master")

    def test_trunk_refusal_survives_an_inherited_git_dir(self) -> None:
        """The regression guard for the leak that made the two cases above lie.

        Git exports `GIT_DIR` and `GIT_INDEX_FILE` to a pre-commit hook, so when the
        hook runs this suite those variables reach the scratch repository and
        `git symbolic-ref` answers for the *outer* repository instead. The trunk
        cases then pass regardless of the branch they set up.

        Injecting `GIT_DIR` deliberately reproduces that condition. If the stripping
        in `run_hook` is ever removed, this fails and the two cases above stop
        being evidence of anything.
        """
        leaked = {
            "GIT_DIR": str(REPO / ".git"),
            "GIT_INDEX_FILE": str(REPO / ".git" / "index"),
        }
        # Patching os.environ is the point: the leak arrives through inheritance, not
        # through an argument, so passing these via env_extra would test the opposite
        # thing — env_extra is applied after the stripping, by design, because a caller
        # asking for a variable should get it.
        with unittest.mock.patch.dict(os.environ, leaked):
            result = run_hook(branch="main", env_extra={"SKIP_GATE": "1"})
        self.assertNotEqual(
            result.returncode,
            0,
            "an inherited GIT_DIR let a commit on main through — the suite is not hermetic",
        )

    def test_red_gate_is_refused(self) -> None:
        """The hook must run the gate itself rather than trust that it was run.

        A scratch repository has no Makefile, so `make all` fails there — which is
        the condition being checked: the hook propagates a failing gate instead of
        reporting success.
        """
        result = run_hook(branch="feat/x")
        self.assertNotEqual(
            result.returncode, 0, "the hook allowed a commit on a failing gate"
        )
        self.assertIn("make all failed", result.stderr)


class TrackedHookAllows(unittest.TestCase):
    def test_feature_branch_with_gate_skipped_is_allowed(self) -> None:
        result = run_hook(branch="feat/x", env_extra={"SKIP_GATE": "1"})
        self.assertEqual(
            result.returncode,
            0,
            f"the hook blocked ordinary work:\n{result.stdout}{result.stderr}",
        )

    def test_trunk_override_is_honoured(self) -> None:
        """An escape hatch that does not work is a reason to delete the hook."""
        result = run_hook(
            branch="main",
            env_extra={"SKIP_GATE": "1", "ALLOW_TRUNK_COMMIT": "1"},
        )
        self.assertEqual(
            result.returncode,
            0,
            f"the documented override did not work:\n{result.stdout}{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
