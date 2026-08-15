"""A validator must not walk into a directory nobody here wrote.

Why this exists
---------------
Creating a project-local virtual environment made `make audit` fail — not on
anything in this repository, but on an SBOM shipped inside an installed package,
where an absolute build path looked like leaked PII. The finding was real by the
rule and meaningless in substance, and the only ways out were to delete the venv
or to stop trusting the gate. Both are worse than the problem.

The general shape: every directory a validator should skip is already gitignored,
because that is the same statement — "this is not our content". So the test is
not "is `.venv` in the list" but "does the list cover everything git ignores".
That way the next tool needing a cache directory is already handled, instead of
being discovered the same way this one was.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from frontmatter import IGNORED_DIRS, iter_markdown


def gitignored_directories() -> set[str]:
    """Top-level directories that exist on disk and are ignored by git."""
    found: set[str] = set()
    for child in ROOT.iterdir():
        if not child.is_dir():
            continue
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", child.name],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        if ignored.returncode == 0:
            found.add(child.name)
    return found


class IgnoredDirectories(unittest.TestCase):
    def test_every_gitignored_directory_is_skipped(self) -> None:
        uncovered = sorted(gitignored_directories() - set(IGNORED_DIRS))
        self.assertEqual(
            uncovered,
            [],
            "these directories exist, are gitignored, and are not in "
            f"tools/frontmatter.py IGNORED_DIRS, so validators walk into them "
            f"and report findings about files that are not ours: {uncovered}",
        )

    def test_git_itself_is_skipped(self) -> None:
        """`.git` is ignored implicitly rather than by a .gitignore rule, so the
        check above would not catch its absence."""
        self.assertIn(".git", IGNORED_DIRS)

    def test_the_audit_shares_the_same_list(self) -> None:
        """Two lists drift; the audit adds to the shared one instead of copying it."""
        sys.path.insert(0, str(ROOT / "tools"))
        import audit_public_output

        self.assertTrue(
            set(IGNORED_DIRS).issubset(set(audit_public_output.SKIP_DIRS)),
            "audit_public_output.SKIP_DIRS no longer contains the shared list",
        )

    def test_walker_does_not_enter_an_ignored_directory(self) -> None:
        """Checked by walking, not by reading the constant."""
        probe_dir = ROOT / ".venv" / "probe"
        created = not (ROOT / ".venv").exists()
        probe_dir.mkdir(parents=True, exist_ok=True)
        probe = probe_dir / "should-not-be-scanned.md"
        probe.write_text("# probe\n", encoding="utf-8")
        try:
            found = [p for p in iter_markdown(ROOT) if probe.name in p.name]
            self.assertEqual(found, [], f"iter_markdown walked into {probe_dir}")
        finally:
            probe.unlink(missing_ok=True)
            probe_dir.rmdir()
            if created:
                (ROOT / ".venv").rmdir()


if __name__ == "__main__":
    unittest.main()
