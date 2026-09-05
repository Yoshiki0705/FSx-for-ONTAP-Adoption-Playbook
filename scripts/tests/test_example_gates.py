"""The shell and CloudFormation gates must reject a broken input, not merely pass on a clean tree.

Why this exists
---------------
`examples/` is different in kind from the rest of this repository. Everything else is prose a
reader evaluates; these are artifacts a reader runs against their own AWS account. A quoting bug
in a shell script or an invalid property in a template is a defect delivered, and a template that
only fails at CreateStack time costs the reader a twenty-minute file-system creation to discover
it.

So the two gates guarding that directory are tested the same way every documentation gate here is:
break something on purpose, run the real gate, assert a non-zero exit, and confirm the tree is
clean again afterwards. Passing on a clean tree proves the gate ran. It does not prove the gate can
still detect anything.

The scan-range half is checked separately. Both gates discover their inputs with `find` and `grep`
rather than a fixed file list, because this repository has twice shipped a detector that was silent
because of where it looked rather than because the tree was clean.
"""

from __future__ import annotations

import contextlib
import subprocess
import unittest
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"

# Deliberately ordinary names. A probe called `_probe.sh` would tell us nothing if the gate skips
# files beginning with an underscore.
BAD_SCRIPT = EXAMPLES / "block-storage" / "zz-gate-probe.sh"
BAD_TEMPLATE = EXAMPLES / "block-storage" / "zz-gate-probe.yaml"

# shellcheck reports SC2086 for this: an unquoted expansion in a path passed to rm.
BROKEN_SHELL = """\
#!/usr/bin/env bash
set -euo pipefail
target=${1:-}
rm -rf $target/subdir
"""

# cfn-lint reports E3002 for a property the resource type does not have.
BROKEN_TEMPLATE = """\
AWSTemplateFormatVersion: '2010-09-09'
Description: gate probe
Resources:
  Probe:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: probe
      ThisPropertyDoesNotExist: true
"""


def make(target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", target],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@contextlib.contextmanager
def written(path: Path, body: str) -> Iterator[None]:
    path.write_text(body, encoding="utf-8")
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


class GatesRejectBrokenInput(unittest.TestCase):
    def test_shellcheck_gate_rejects_an_unquoted_expansion(self) -> None:
        with written(BAD_SCRIPT, BROKEN_SHELL):
            done = make("shell")
        self.assertNotEqual(
            done.returncode,
            0,
            "`make shell` accepted a script with an unquoted expansion in an rm path, "
            f"so the gate is not inspecting examples/:\n{done.stdout}{done.stderr}",
        )

    def test_cfn_gate_rejects_an_invalid_property(self) -> None:
        with written(BAD_TEMPLATE, BROKEN_TEMPLATE):
            done = make("cfn")
        self.assertNotEqual(
            done.returncode,
            0,
            "`make cfn` accepted a template with a property the resource type does not "
            f"have:\n{done.stdout}{done.stderr}",
        )

    def test_tree_is_clean_after_the_probes(self) -> None:
        self.assertFalse(BAD_SCRIPT.exists(), f"{BAD_SCRIPT} was left behind")
        self.assertFalse(BAD_TEMPLATE.exists(), f"{BAD_TEMPLATE} was left behind")
        for target in ("shell", "cfn"):
            done = make(target)
            self.assertEqual(
                done.returncode,
                0,
                f"`make {target}` fails on the committed tree:\n{done.stdout}{done.stderr}",
            )


class GatesCoverEveryArtifact(unittest.TestCase):
    """A gate that names its files individually stops covering the next one added."""

    def test_every_shell_script_is_reachable_by_the_gate(self) -> None:
        scripts = sorted(p for p in ROOT.rglob("*.sh") if not self._ignored(p))
        self.assertTrue(
            scripts, "no shell scripts found; this test would prove nothing"
        )
        done = make("shell")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        # The recipe prints how many it checked. A script outside SH_PATHS would make the
        # count disagree with what is on disk.
        reported = [tok for tok in done.stdout.split() if tok.isdigit()]
        self.assertTrue(reported, f"`make shell` printed no count:\n{done.stdout}")
        self.assertEqual(
            int(reported[0]),
            len(scripts),
            "`make shell` checked "
            f"{reported[0]} script(s) but {len(scripts)} are tracked outside ignored "
            "directories. Add the tree holding the difference to SH_PATHS in the Makefile.",
        )

    def test_every_template_is_reachable_by_the_gate(self) -> None:
        templates = sorted(
            p
            for p in ROOT.rglob("*.y*ml")
            if not self._ignored(p)
            and p.read_text(encoding="utf-8", errors="ignore").startswith(
                "AWSTemplateFormatVersion"
            )
        )
        self.assertTrue(templates, "no CloudFormation templates found")
        done = make("cfn")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        reported = [tok for tok in done.stdout.split() if tok.isdigit()]
        self.assertTrue(reported, f"`make cfn` printed no count:\n{done.stdout}")
        self.assertEqual(
            int(reported[0]),
            len(templates),
            f"`make cfn` checked {reported[0]} template(s) but {len(templates)} are "
            "tracked. Add the tree holding the difference to CFN_PATHS in the Makefile.",
        )

    @staticmethod
    def _ignored(path: Path) -> bool:
        parts = set(path.relative_to(ROOT).parts)
        return bool(
            parts
            & {
                ".git",
                ".github",
                ".kiro",
                ".private",
                ".venv",
                "node_modules",
                "__pycache__",
            }
        )


class AuditReachesShellScripts(unittest.TestCase):
    def test_shell_suffix_is_in_the_audit_scan_range(self) -> None:
        """The naming, neutrality and private-address rules apply to a script's comments too."""
        source = (ROOT / "tools" / "audit_public_output.py").read_text(encoding="utf-8")
        match = [
            line for line in source.splitlines() if line.startswith("SCAN_SUFFIXES")
        ]
        self.assertTrue(
            match, "SCAN_SUFFIXES not found in tools/audit_public_output.py"
        )
        self.assertIn(
            '".sh"',
            match[0],
            "examples/ ships shell scripts, so leaving .sh out of SCAN_SUFFIXES makes the "
            "audit silent about them because of its scan range, not because they are clean.",
        )


if __name__ == "__main__":
    unittest.main()
