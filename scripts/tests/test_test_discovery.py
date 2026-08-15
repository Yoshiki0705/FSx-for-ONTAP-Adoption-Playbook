"""Every test directory must be reachable, and no gate may force its own success.

Why this exists
---------------
Tests that exist but are enumerated nowhere run nowhere. They are not in the
Makefile, not in CI, and execute only when somebody remembers a command from a
README — which means a regression they would have caught ships anyway. In a
sibling project 422 tests sat in exactly that state.

The second half is the mirror image: a CI step ending in `|| true`, or a scan
whose findings are piped to nothing, reports success unconditionally. Both leave
a green check mark standing in for verification that never happened.

`TEST_DIRS` in the Makefile is the single list, and CI runs `make test`, so this
test only has to compare the filesystem against that one variable.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
WORKFLOWS = ROOT / ".github" / "workflows"

IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".ruff_cache"}

# `cmd || true` and `cmd 2>/dev/null` at the end of a step both discard the verdict.
FORCED_SUCCESS = re.compile(r"\|\|\s*true\b|;\s*true\s*$|\bexit\s+0\s*$")


def declared_test_dirs() -> set[str]:
    source = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(r"^TEST_DIRS\s*:?=\s*(.*)$", source, re.MULTILINE)
    if not match:
        return set()
    return set(match.group(1).split())


def existing_test_dirs() -> set[str]:
    found: set[str] = set()
    for path in ROOT.rglob("tests"):
        if not path.is_dir():
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if not any(path.glob("test_*.py")):
            continue
        found.add(path.relative_to(ROOT).as_posix())
    return found


class TestDiscovery(unittest.TestCase):
    def test_every_test_directory_is_declared(self) -> None:
        undeclared = sorted(existing_test_dirs() - declared_test_dirs())
        self.assertEqual(
            undeclared,
            [],
            "these directories hold test_*.py files but are not in the Makefile's "
            f"TEST_DIRS, so nothing runs them: {undeclared}",
        )

    def test_declared_directories_exist(self) -> None:
        missing = sorted(d for d in declared_test_dirs() if not (ROOT / d).is_dir())
        self.assertEqual(
            missing, [], f"TEST_DIRS names directories that do not exist: {missing}"
        )

    def test_test_dirs_is_not_empty(self) -> None:
        """An empty list would make `make test` a successful no-op."""
        self.assertTrue(declared_test_dirs())

    def test_ci_runs_the_make_test_target(self) -> None:
        """Declaring the list is pointless if CI never invokes it."""
        joined = "\n".join(
            p.read_text(encoding="utf-8") for p in WORKFLOWS.glob("*.yml")
        )
        self.assertIn(
            "make test",
            joined,
            "no workflow runs `make test`, so the guardrail tests would only ever "
            "run on a developer's machine",
        )

    def test_no_workflow_step_forces_its_own_success(self) -> None:
        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            for number, line in enumerate(
                workflow.read_text(encoding="utf-8").splitlines(), start=1
            ):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                with self.subTest(workflow=workflow.name, line=number):
                    self.assertIsNone(
                        FORCED_SUCCESS.search(stripped),
                        f"{workflow.name}:{number} discards the exit status, so this "
                        f"step can never fail: {stripped}",
                    )


if __name__ == "__main__":
    unittest.main()
