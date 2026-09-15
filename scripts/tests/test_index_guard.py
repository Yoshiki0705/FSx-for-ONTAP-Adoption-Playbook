"""The gate must not change the git index, and the assertion must say so when it does.

Two edits once existed only in the index and never on disk — no commit, no stash, no reflog. The
writing path is still unidentified, so the invariant is asserted instead of the path being chased:
running the gate leaves the index as it found it.

Both directions matter here, and the false-positive direction is why the check is written the way
it is. Hashing `.git/index` would fire on a `stat` refresh, which is not a change of meaning; a
check that fires on ordinary work gets switched off, and then it is worth nothing when a real leak
arrives. So a refresh is tested to pass, and a stray `git add` is tested to fail.

`make` is shimmed rather than real: the point is what the wrapper does with a gate that touches the
index, not what this repository's gate does.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.tests.gitenv import owns_git_dir, scrubbed_env

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "run_gate.sh"


def run_with_make(
    shim: str, *, commit: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run the gate wrapper in a scratch repository with `make` replaced by `shim`."""
    env = scrubbed_env()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        init = subprocess.run(
            ["git", "init", "-q", "-b", "work", str(work)],
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
                "the scratch repository was not created, so every verdict below would be about "
                f"another repository — git dir resolved to {owned.stdout.strip()!r}: "
                f"{init.stderr}{owned.stderr}"
            )

        def git(*args: str) -> None:
            subprocess.run(
                ["git", *args],
                env=env,
                cwd=work,
                check=True,
                capture_output=True,
                text=True,
            )

        (work / "tracked.txt").write_text("one\n", encoding="utf-8")
        if commit:
            git("add", "tracked.txt")
            git(
                "-c",
                "user.email=t@example.com",
                "-c",
                "user.name=t",
                "commit",
                "-qm",
                "seed",
            )

        # A staged change the wrapper must treat as legitimate: inside pre-commit the index holds
        # the commit being made, so the invariant is "unchanged", not "clean".
        (work / "staged.txt").write_text("staged\n", encoding="utf-8")
        git("add", "staged.txt")

        binder = work / "shimbin"
        binder.mkdir()
        make = binder / "make"
        make.write_text(
            f"#!/usr/bin/env bash\nset -uo pipefail\n{shim}\n", encoding="utf-8"
        )
        make.chmod(0o755)

        shim_env = dict(env)
        shim_env["PATH"] = f"{binder}{os.pathsep}{env.get('PATH', '')}"
        return subprocess.run(
            ["bash", str(RUNNER), str(work / "gate.log")],
            cwd=work,
            env=shim_env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )


class TheIndexAssertion(unittest.TestCase):
    def test_a_gate_that_touches_nothing_passes(self) -> None:
        result = run_with_make("exit 0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("make all", result.stdout)

    def test_a_stray_git_add_is_refused(self) -> None:
        """The failure this exists for: a check writing to the real repository."""
        result = run_with_make("echo leaked > leaked.txt\ngit add leaked.txt\nexit 0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed the git index", result.stderr)

    def test_staging_a_modification_to_a_tracked_file_is_refused(self) -> None:
        """The shape of the incident: an edit that reaches the index and not the working tree."""
        result = run_with_make("echo two > tracked.txt\ngit add tracked.txt\nexit 0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed the git index", result.stderr)

    def test_a_stat_refresh_and_a_touch_do_not_fire(self) -> None:
        """The false-positive direction, and the reason `.git/index` is not hashed.

        A refresh rewrites that file and moves its digest with no change of meaning. A check that
        fails on ordinary work gets bypassed, and is then absent when a real leak arrives.
        """
        result = run_with_make(
            "touch tracked.txt\ngit status --porcelain >/dev/null\nexit 0"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_red_gate_is_distinguishable_from_an_index_change(self) -> None:
        """Two different failures must not report the same thing, or the recovery steps for one
        get applied to the other."""
        result = run_with_make("exit 1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("make all failed", result.stderr)
        self.assertNotIn("changed the git index", result.stderr)

    def test_the_first_commit_is_handled(self) -> None:
        """Before any commit HEAD does not resolve. The comparison has to fall back to the empty
        tree rather than error into an empty snapshot that compares equal to another error."""
        result = run_with_make("exit 0", commit=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_first_commit_still_detects_a_leak(self) -> None:
        """The fallback must not be a hole: with no HEAD, a stray add still has to be caught."""
        result = run_with_make(
            "echo leaked > leaked.txt\ngit add leaked.txt\nexit 0", commit=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed the git index", result.stderr)

    def test_the_recovery_instructions_are_present(self) -> None:
        """A verdict with no way to act on it costs the reader the same diagnosis twice — and here
        the wrong first move destroys the only copy."""
        result = run_with_make("echo leaked > leaked.txt\ngit add leaked.txt\nexit 0")
        self.assertIn("Look before unstaging", result.stderr)
        self.assertIn("git fsck", result.stderr)


if __name__ == "__main__":
    unittest.main()
