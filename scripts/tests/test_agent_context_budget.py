"""The context-budget check must fail on each arrangement it exists to prevent.

Why this exists
---------------
This is the guard against two opposite mistakes: letting always-loaded context
grow without limit, and "fixing" that by moving prose into gitignored `.kiro/`,
which deletes it from the published repository while the agent still sees it.

Both are invisible in normal use. Nothing errors when `AGENTS.md` gains a
section, and nothing errors when a steering file quietly becomes the only copy
of a rule. A previous version of the checker guarded its loader tests with
`if STEERING.exists()`, so in CI — where `.kiro/` is absent by design — those
tests did nothing at all and still printed "healthy".

Each case below builds a throwaway repository, breaks one property, and runs the
real script against it. Running it in a temp tree rather than the live one keeps
the tests from depending on the repository's current size, so a legitimate edit
to `AGENTS.md` does not make them fail for the wrong reason.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.tests.gitenv import owns_git_dir, scrubbed_env

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_agent_context_budget.py"

AGENTS_STUB = """\
# AGENTS.md

This file is committed and travels with the repo.

## Task-specific references

| Document | Read it when |
|---|---|
| [`docs/agent/thing.md`](docs/agent/thing.md) | doing the thing |
"""

LOADER_STUB = """\
---
inclusion: auto
name: thing
description: Read docs/agent/thing.md when doing the thing.
---
Body: [`docs/agent/thing.md`](../../docs/agent/thing.md). Authority: AGENTS.md.
"""


class Fixture:
    """A minimal repository shaped like the real one."""

    def __init__(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="ctx-budget-"))
        (self.dir / "scripts").mkdir()
        shutil.copy2(SCRIPT, self.dir / "scripts" / SCRIPT.name)
        (self.dir / "docs" / "agent").mkdir(parents=True)
        (self.dir / ".kiro" / "steering").mkdir(parents=True)
        (self.dir / "AGENTS.md").write_text(AGENTS_STUB, encoding="utf-8")
        (self.dir / "docs" / "agent" / "thing.md").write_text(
            "# Thing\n", encoding="utf-8"
        )
        (self.dir / ".kiro" / "steering" / "thing.md").write_text(
            LOADER_STUB, encoding="utf-8"
        )
        self._git("init", "-q")
        self._assert_owns_its_git_dir()
        self.track("docs/agent/thing.md")

    def _git(self, *args: str) -> None:
        # `env` is not optional here. Without it this call inherits GIT_DIR and GIT_INDEX_FILE
        # from a pre-commit hook and operates on the real repository — which is how
        # `docs/agent/orphan.md` became a committed file that was never on disk. See
        # scripts/tests/gitenv.py for the full diagnosis.
        subprocess.run(
            ["git", *args],
            cwd=self.dir,
            env=scrubbed_env(),
            check=True,
            capture_output=True,
        )

    def _assert_owns_its_git_dir(self) -> None:
        """Confirm the scratch repository is the one every later call will hit."""
        reported = subprocess.run(
            ["git", "rev-parse", "--absolute-git-dir"],
            cwd=self.dir,
            env=scrubbed_env(),
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        if not owns_git_dir(self.dir, reported):
            raise AssertionError(
                "the fixture does not own its git dir, so every git call below would act on "
                f"another repository — got {reported.strip()!r}, expected {self.dir}/.git"
            )

    def track(self, relative: str) -> None:
        self._git("add", relative)

    def run(self) -> subprocess.CompletedProcess[str]:
        # Scrubbed for the same reason `_git` is, and this half was missed first: the script
        # under test runs `git ls-files` itself, so an inherited GIT_DIR makes it answer about
        # the caller's repository while `track()` writes to the fixture's. Before either half
        # was scrubbed both read the caller's repository and the suite passed by agreeing on the
        # wrong tree — **fixing one half is what made the disagreement visible.**
        return subprocess.run(
            [sys.executable, str(self.dir / "scripts" / SCRIPT.name)],
            capture_output=True,
            text=True,
            cwd=self.dir,
            env=scrubbed_env(),
            check=False,
        )

    def cleanup(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


class ContextBudget(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Fixture()
        self.addCleanup(self.repo.cleanup)

    def assert_fails(self, expect: str) -> None:
        result = self.repo.run()
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, f"expected a failure, got:\n{output}")
        self.assertIn(expect, output)

    def test_healthy_fixture_passes(self) -> None:
        """Without this, every test below could pass for the wrong reason."""
        result = self.repo.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("healthy", result.stdout)

    def test_oversized_agents_md_fails(self) -> None:
        path = self.repo.dir / "AGENTS.md"
        path.write_text(AGENTS_STUB + "\nfiller line\n" * 4000, encoding="utf-8")
        self.assert_fails("loaded on every turn")

    def test_fat_steering_loader_fails(self) -> None:
        """A loader this size is holding content, and .kiro/ is not published."""
        path = self.repo.dir / ".kiro" / "steering" / "thing.md"
        path.write_text(LOADER_STUB + "\nprose\n" * 500, encoding="utf-8")
        self.assert_fails("not published")

    def test_untracked_indexed_document_fails(self) -> None:
        """The failure mode that deletes public documentation without saying so."""
        self.repo._git("rm", "--cached", "-q", "docs/agent/thing.md")
        self.assert_fails("not tracked by git")

    def test_missing_indexed_document_fails(self) -> None:
        (self.repo.dir / "docs" / "agent" / "thing.md").unlink()
        self.assert_fails("does not exist")

    def test_auto_inclusion_without_name_and_description_fails(self) -> None:
        """Kiro registers nothing and reports nothing, so the file never loads."""
        path = self.repo.dir / ".kiro" / "steering" / "thing.md"
        path.write_text(
            "---\ninclusion: auto\n---\nBody: AGENTS.md\n",
            encoding="utf-8",
        )
        self.assert_fails("never loaded and never errors")

    def test_unindexed_agent_doc_fails(self) -> None:
        extra = self.repo.dir / "docs" / "agent" / "orphan.md"
        extra.write_text("# Orphan\n", encoding="utf-8")
        self.repo.track("docs/agent/orphan.md")
        self.assert_fails("does not index it")

    def test_absent_kiro_is_reported_rather_than_skipped(self) -> None:
        """CI has no .kiro/. A green run must not imply the loaders were checked."""
        shutil.rmtree(self.repo.dir / ".kiro")
        result = self.repo.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("NOT checked", result.stdout)


class LiveRepository(unittest.TestCase):
    def test_this_repository_is_within_budget(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
