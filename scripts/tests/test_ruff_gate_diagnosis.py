"""`make python` must tell a broken ruff apart from a ruff of the wrong version.

The gate read the version through a pipeline, `ruff --version | awk '{print $2}'`. A pipeline reports
the exit status of its last command, so a ruff that does not run at all produced an empty version
string, which then failed the version comparison. The gate refused - correctly - but said
`is , but CI pins 0.16.3` and pointed at the pinning instructions, which are not the fix for a binary
that cannot execute.

A sibling repository found the same masking in its own commit gate, in a worse shape: a pipeline whose
result was chained with `&&`, so it looked connected while never propagating a failure. Both cases are
the same fact - `&&` and `||` see the pipeline's status, not the interesting command's.

These tests drive the real Makefile target with `RUFF=` pointed at a stub, because the failure was in
the recipe's shell, which is the one place a Python-level test of the same logic would not reach.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BROKEN = '#!/bin/sh\necho "ruff: broken install" >&2\nexit 127\n'
WRONG_VERSION = '#!/bin/sh\necho "ruff 0.9.9"\n'


def make_python_with(stub_body: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as name:
        stub = Path(name) / "ruff-stub"
        stub.write_text(stub_body, encoding="utf-8")
        stub.chmod(0o755)
        return subprocess.run(
            ["make", "python", f"RUFF={stub}"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=ROOT,
            check=False,
            env={**os.environ, "MAKEFLAGS": ""},
        )


class RuffGateDiagnosis(unittest.TestCase):
    def test_a_ruff_that_cannot_run_is_named_as_such(self) -> None:
        result = make_python_with(BROKEN)
        output = result.stdout + result.stderr
        self.assertNotEqual(
            result.returncode, 0, f"the gate accepted a broken ruff:\n{output}"
        )
        self.assertIn("does not run", output)
        self.assertNotIn(
            "but CI pins",
            output,
            "a broken install is being reported as a version mismatch, which sends the reader "
            "to the pinning instructions instead of to the broken binary",
        )

    def test_a_wrong_version_is_still_reported_as_a_version(self) -> None:
        result = make_python_with(WRONG_VERSION)
        output = result.stdout + result.stderr
        self.assertNotEqual(
            result.returncode, 0, f"the gate accepted an unpinned ruff:\n{output}"
        )
        self.assertIn("but CI pins", output)
        self.assertNotIn("does not run", output)

    def test_the_recipe_reads_the_version_without_a_pipeline(self) -> None:
        """A pipeline here would hide the exit status again, which is how this started."""
        recipe = ROOT.joinpath("Makefile").read_text(encoding="utf-8")
        line = next(
            candidate
            for candidate in recipe.split("\n")
            if "--version" in candidate and "RUFF" in candidate
        )
        # A single `|` only. The recipe legitimately contains `||`, and a bare substring check
        # read that as a pipeline - the first version of this assertion failed on correct code,
        # which is the same shape of defect it was written to catch.
        pipeline = re.search(r"(?<!\|)\|(?!\|)", line)
        self.assertIsNone(
            pipeline,
            f"the version is being read through a pipeline again ({line.strip()}); a pipeline's "
            f"exit status is its last command's, so a ruff that fails to run reports success",
        )


if __name__ == "__main__":
    unittest.main()
