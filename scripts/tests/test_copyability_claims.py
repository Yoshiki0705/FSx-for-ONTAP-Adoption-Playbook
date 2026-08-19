"""Every claim that a tool can be copied into another repository, checked.

`AGENTS.md` tells the reader that `guard_irreversible_ops.py` is stdlib-only and project-agnostic and
invites them to copy it. Two other tools were described the same way in correspondence with a sibling
repository. Those are promises, and a promise breaks silently: the moment a copyable file reaches for
a project path or a sibling helper it stops being copyable, and every other test still passes.

The pattern is borrowed from that sibling repository, which wraps its own copyable block in a test
that executes it in an isolated namespace. Applying it here found a defect immediately: the
instruction given for `check_anchor_contract.py` named one helper to copy alongside it, and that was
not enough - the helper has a dependency of its own, so following the instruction produced an
ImportError.

Each test copies files into a temporary directory outside the repository and works there, because
that is what a reader actually does. Import success inside this tree proves nothing: `sys.path` and
the working directory are both wrong for the question being asked.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The documented copy set for each tool: the files a reader has to take for it to import and run.
# Keep this in step with what AGENTS.md tells them to copy.
COPY_SETS = {
    "guard_irreversible_ops.py": ("scripts/guard_irreversible_ops.py",),
    "check_i18n_parity.py": ("tools/check_i18n_parity.py",),
    "check_anchor_contract.py": (
        "tools/check_anchor_contract.py",
        "tools/check_links.py",
        "tools/frontmatter.py",
    ),
}


def run_in(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=cwd,
        check=False,
    )


def stage(target: Path, relatives: tuple[str, ...]) -> None:
    for relative in relatives:
        shutil.copy(ROOT / relative, target / Path(relative).name)


class CopyabilityClaims(unittest.TestCase):
    def test_guard_is_project_agnostic_outside_the_repository(self) -> None:
        """AGENTS.md invites a reader to copy this file; its selftest must pass where they put it."""
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            stage(target, COPY_SETS["guard_irreversible_ops.py"])
            result = run_in(target, "guard_irreversible_ops.py", "--selftest")
            self.assertEqual(
                result.returncode,
                0,
                f"the guard does not run outside this repository:\n"
                f"{result.stdout}{result.stderr}",
            )

    def test_documented_copy_set_is_sufficient(self) -> None:
        """Following the instruction must produce a module that imports."""
        for tool, files in COPY_SETS.items():
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as name:
                target = Path(name)
                stage(target, files)
                result = run_in(target, "-c", f"import {Path(tool).stem}")
                self.assertEqual(
                    result.returncode,
                    0,
                    f"{tool}: the documented copy set does not import:\n{result.stderr}",
                )

    def test_documented_copy_set_is_minimal(self) -> None:
        """Dropping any dependency must break the import, so the list records a real need.

        Without this the copy set silently grows: a file that is no longer required stays on the
        list, the next reader copies more than they have to, and the list stops being believed.
        """
        for tool, files in COPY_SETS.items():
            for dropped in files[1:]:
                kept = tuple(f for f in files if f != dropped)
                with (
                    self.subTest(tool=tool, without=dropped),
                    tempfile.TemporaryDirectory() as name,
                ):
                    target = Path(name)
                    stage(target, kept)
                    result = run_in(target, "-c", f"import {Path(tool).stem}")
                    self.assertNotEqual(
                        result.returncode,
                        0,
                        f"{tool}: imports without {dropped}, so the copy set over-states "
                        f"its dependencies",
                    )


if __name__ == "__main__":
    unittest.main()
