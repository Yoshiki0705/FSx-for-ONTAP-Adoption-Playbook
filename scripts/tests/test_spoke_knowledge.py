"""The mechanism that keeps Spoke work from being overlooked must run, and must stay wired in.

Why this exists
---------------
Twice, a note here called something "unverified" or "not measured" while a sibling repository (a
Spoke) had already investigated it. The writer was an agent that had no way to know, and the only
safeguard was the human who remembered. The fix is two tracked programs and the places that point
at them:

- ``tools/spoke_search.py`` searches the Spokes' committed content, and reports what is there.
- ``scripts/guard_unverified_claims.py`` blocks a write that adds an "unverified" sentence over
  material a Spoke recorded.

Each carries its own ``--selftest`` (scratch repositories, block and allow in both directions,
a refresh against a bare remote). This file does three things the selftests cannot:

1. Runs them under ``make test``, so a regression fails the commit gate rather than waiting for
   someone to remember the flag.
2. Runs them with ``GIT_DIR`` and ``GIT_INDEX_FILE`` pointing at nothing. The pre-commit hook
   exports those and then runs this suite; a tool that trusts the environment answers every
   question with the committing repository's data, silently. ``gitenv.py`` has the diagnosis.
3. Checks that the places a writer looks still point at the search. A mechanism nobody is told
   about is the failure it replaces, one level up.

What this does **not** prove: that the user-level hooks which call these programs are installed
on a given machine. ``.kiro/`` and ``~/.kiro/`` are not in the repository or in CI, so wiring
there is verified by ``test_hook_wiring.py`` where the directory exists, and by hand otherwise.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.tests.gitenv import scrubbed_env

ROOT = Path(__file__).resolve().parents[2]
SEARCH = ROOT / "tools" / "spoke_search.py"
GUARD = ROOT / "scripts" / "guard_unverified_claims.py"

#: A hook environment that points git at nothing. A tool that does not scrub ``GIT_*`` fails
#: every git call it makes, which its selftest reports.
HOOK_ENV = {"GIT_DIR": "/nonexistent/.git", "GIT_INDEX_FILE": "/nonexistent/index"}


def selftest(program: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(program), "--selftest"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        env=env,
    )


class SelfTestsRun(unittest.TestCase):
    def test_search_selftest_passes(self) -> None:
        done = selftest(SEARCH, scrubbed_env())
        self.assertEqual(done.returncode, 0, done.stderr or done.stdout)

    def test_guard_selftest_passes(self) -> None:
        done = selftest(GUARD, scrubbed_env())
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_search_survives_a_hook_environment(self) -> None:
        done = selftest(SEARCH, scrubbed_env(HOOK_ENV))
        self.assertEqual(done.returncode, 0, done.stderr or done.stdout)

    def test_guard_survives_a_hook_environment(self) -> None:
        done = selftest(GUARD, scrubbed_env(HOOK_ENV))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class StaysWired(unittest.TestCase):
    def test_make_target_exists(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertRegex(
            makefile,
            r"(?m)^spoke-search:",
            "the pointers all say `make spoke-search`; without the target they send the "
            "reader to a command that does not exist",
        )

    def test_programs_are_executable(self) -> None:
        for program in (SEARCH, GUARD):
            with self.subTest(program=program.name):
                self.assertTrue(
                    os.access(program, os.X_OK),
                    "a hook runs the script by path; ruff's EXE001 also rejects a shebang "
                    "on a file that is not executable",
                )

    def test_a_writer_is_pointed_at_the_search(self) -> None:
        """Where an agent or contributor looks before writing "unverified" must name the search."""
        for rel in (
            "docs/agent/domain-knowledge.md",
            "docs/agent/pitfalls.md",
            "tools/new_note.py",
        ):
            with self.subTest(file=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn(
                    "spoke-search",
                    text,
                    f"{rel} no longer points at the Spoke search, so the one place a writer "
                    "would learn it exists has gone",
                )


if __name__ == "__main__":
    unittest.main()
