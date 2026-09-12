"""The operator scripts under `examples/multiprotocol-ad/` must refuse bad input before touching AWS.

Why this exists
---------------
`preflight.sh` and `teardown.sh` are gates a reader runs against their own account, and both were
verified once by hand. A hand verification leaves no artifact, so the next edit to either script has
nothing protecting it -- which is the same gap this repository has already shipped twice with
detectors that were silent for the wrong reason.

Two properties are worth locking down, and neither needs an AWS account:

1. **Refusal.** A missing required argument, and `--apply` without its second acknowledgement flag,
   must exit non-zero with a message that names what is missing. A destructive script whose guard
   is one flag deep is a script that gets run by shell history.

2. **Refusal happens BEFORE any AWS call.** This is the part a reading of the source does not
   settle: argument parsing sits above the first `aws` invocation in the file, but a `die` that
   interpolates a command substitution, or a default computed from `aws sts`, would still reach the
   API. So these tests put a fake `aws` first on PATH that records being called, and assert the
   recording did not happen. An arguments check that quietly makes a billing-adjacent API call is
   not an arguments check.

The fakes also cover `jq` and `curl`, because the scripts probe for them with `command -v` before
doing anything else and a machine without them would otherwise fail these tests for an unrelated
reason.

`--help` is asserted to exit 0 separately: a usage screen that exits non-zero trains readers to
ignore exit codes from these scripts.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "multiprotocol-ad"

# A fake that records that it ran, then fails. Failing is deliberate: if a script does reach it, the
# script should not then proceed as though the call succeeded.
FAKE_TOOL = """\
#!/bin/sh
echo "$0 $*" >> "$MARKER_FILE"
exit 1
"""


class OperatorScriptRefusals(unittest.TestCase):
    """Every case here runs the real script with a fake AWS CLI first on PATH."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.bindir = Path(self._tmp.name) / "bin"
        self.bindir.mkdir(parents=True)
        self.marker = Path(self._tmp.name) / "called.txt"
        for tool in ("aws", "jq", "curl"):
            path = self.bindir / tool
            path.write_text(FAKE_TOOL)
            path.chmod(0o755)
        self.addCleanup(self._tmp.cleanup)

    def run_script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PATH"] = f"{self.bindir}:{env.get('PATH', '')}"
        env["MARKER_FILE"] = str(self.marker)
        # A region is supplied so that a missing region is never the reason a case fails. The cases
        # are about the arguments under test, not about the environment.
        env["AWS_REGION"] = "ap-northeast-1"
        return subprocess.run(
            ["bash", str(EXAMPLE / name), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
            check=False,
        )

    def assert_no_aws_call(self, label: str) -> None:
        if self.marker.exists():
            self.fail(
                f"{label}: the script invoked an external tool before refusing. "
                f"Calls recorded:\n{self.marker.read_text()}"
            )

    # ------------------------------------------------------------------ preflight.sh

    def test_preflight_requires_vpc_id_and_makes_no_call(self) -> None:
        result = self.run_script("preflight.sh")
        self.assertNotEqual(
            0, result.returncode, "preflight.sh accepted no arguments at all"
        )
        self.assertIn("--vpc-id", result.stderr)
        self.assert_no_aws_call("preflight.sh with no arguments")

    def test_preflight_names_each_missing_argument_in_turn(self) -> None:
        # Supplying them one at a time proves the checks are individual rather than one combined
        # message that happens to mention the first flag.
        expectations = [
            (["--vpc-id", "vpc-0"], "--primary-subnet"),
            (["--vpc-id", "vpc-0", "--primary-subnet", "subnet-0"], "--second-subnet"),
            (
                [
                    "--vpc-id",
                    "vpc-0",
                    "--primary-subnet",
                    "subnet-0",
                    "--second-subnet",
                    "subnet-1",
                ],
                "--domain-name",
            ),
        ]
        for args, expected in expectations:
            with self.subTest(missing=expected):
                result = self.run_script("preflight.sh", *args)
                self.assertNotEqual(0, result.returncode)
                self.assertIn(expected, result.stderr)

    def test_preflight_rejects_unknown_argument(self) -> None:
        result = self.run_script("preflight.sh", "--not-a-flag")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("unknown argument", result.stderr)
        self.assert_no_aws_call("preflight.sh with an unknown flag")

    def test_preflight_help_exits_zero(self) -> None:
        result = self.run_script("preflight.sh", "--help")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--write-params", result.stdout)

    # ------------------------------------------------------------------ teardown.sh

    def test_teardown_requires_stack_name(self) -> None:
        result = self.run_script("teardown.sh")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--stack-name", result.stderr)
        self.assert_no_aws_call("teardown.sh with no arguments")

    def test_teardown_apply_needs_the_second_flag(self) -> None:
        """The whole point of the two-flag design: one flag must not be enough."""
        result = self.run_script("teardown.sh", "--stack-name", "any-stack", "--apply")
        self.assertNotEqual(
            0, result.returncode, "teardown.sh accepted --apply on its own"
        )
        self.assertIn("--i-understand-this-deletes-data", result.stderr)
        self.assert_no_aws_call("teardown.sh with --apply and no acknowledgement")

    def test_teardown_recovery_queue_needs_its_inputs(self) -> None:
        result = self.run_script(
            "teardown.sh", "--stack-name", "any-stack", "--purge-recovery-queue"
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--management-ip", result.stderr)
        self.assert_no_aws_call("teardown.sh with an incomplete recovery-queue request")

    def test_teardown_help_exits_zero(self) -> None:
        result = self.run_script("teardown.sh", "--help")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--i-understand-this-deletes-data", result.stdout)

    # ------------------------------------------------------------------ the disruptive probes

    def test_rehost_probe_apply_needs_the_second_flag(self) -> None:
        result = self.run_script(
            "rehost-probe.sh",
            "--management-ip",
            "127.0.0.1",
            "--source-svm",
            "a",
            "--destination-svm",
            "b",
            "--volume",
            "v",
            "--password-stdin",
            "--apply",
        )
        self.assertNotEqual(
            0, result.returncode, "rehost-probe.sh accepted --apply on its own"
        )
        self.assertIn("--i-understand-this-is-disruptive", result.stderr)

    def test_set_test_acls_requires_a_target(self) -> None:
        result = self.run_script("set-test-acls.sh", "--management-ip", "127.0.0.1")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--svm", result.stderr)

    def test_read_effective_permissions_requires_a_target(self) -> None:
        result = self.run_script("read-effective-permissions.sh")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--nfs-endpoint", result.stderr)

    # ------------------------------------------------------------------ the positive path

    # Everything above asserts refusal. On their own those tests are satisfied by a script that
    # refuses EVERYTHING -- an edit that made a required check unsatisfiable would keep them all
    # green. These two prove the opposite direction: a fully-specified invocation gets past argument
    # parsing and reaches the first AWS call. The fake `aws` fails, so the script still exits
    # non-zero; what is asserted is that it got that far, which is what the marker records.

    def test_preflight_with_all_required_arguments_reaches_aws(self) -> None:
        self.run_script(
            "preflight.sh",
            "--vpc-id",
            "vpc-0",
            "--primary-subnet",
            "subnet-0",
            "--second-subnet",
            "subnet-1",
            "--domain-name",
            "corp.example.com",
            "--domain-short-name",
            "CORP",
        )
        self.assertTrue(
            self.marker.exists(),
            "preflight.sh refused a complete invocation before making any call. Argument "
            "validation has become unsatisfiable, which every refusal test above would still pass.",
        )

    def test_teardown_with_stack_name_reaches_aws(self) -> None:
        self.run_script("teardown.sh", "--stack-name", "any-stack")
        self.assertTrue(
            self.marker.exists(),
            "teardown.sh refused a complete invocation before making any call.",
        )


class OperatorScriptPortability(unittest.TestCase):
    """No script may use a bash 4 expansion.

    macOS still ships bash 3.2, and `${var^}` there fails with "bad substitution" on the line it
    appears -- which for a preflight check means the first real check dies and every later check is
    skipped silently. That happened once during development; this keeps it from returning.
    """

    FORBIDDEN = (
        ("${var^}", r"\$\{[A-Za-z_][A-Za-z0-9_]*\^"),
        ("${var,,}", r"\$\{[A-Za-z_][A-Za-z0-9_]*,,"),
        ("declare -A", r"declare\s+-A\b"),
        ("readarray/mapfile", r"\b(readarray|mapfile)\b"),
    )

    def _scan(self, scripts: list[Path]) -> list[str]:
        """The scan itself, extracted so the check and its own test share one implementation.

        Asserting that the regex matches a synthetic string tests the regex. It does not test the
        scan, and the scan is where the interesting failure lives: one that skips the wrong lines,
        or globs the wrong files, reports clean for a reason unrelated to the tree. This repository
        has shipped that twice.

        Comment lines are skipped deliberately: the scripts name these constructs in order to forbid
        them, and a construct inside a comment cannot execute -- the same reason `AGENTS.md` may
        quote the phrasing it bans.
        """
        import re

        offenders: list[str] = []
        for script in scripts:
            for lineno, line in enumerate(script.read_text().split("\n"), start=1):
                if line.lstrip().startswith("#"):
                    continue
                for label, pattern in self.FORBIDDEN:
                    if re.search(pattern, line):
                        offenders.append(f"{script.name}:{lineno} uses {label}")
        return offenders

    def test_no_bash4_only_constructs(self) -> None:
        offenders = self._scan(sorted(EXAMPLE.glob("*.sh")))
        self.assertEqual(
            [], offenders, "bash 4 only constructs found:\n" + "\n".join(offenders)
        )

    def test_the_scan_detects_an_active_use_and_ignores_a_commented_one(self) -> None:
        """Run the real scan over real files, in both directions."""
        with tempfile.TemporaryDirectory() as tmp:
            active = Path(tmp) / "active.sh"
            active.write_text('#!/usr/bin/env bash\npair=a:b\nkey="${pair^}"\n')
            commented = Path(tmp) / "commented.sh"
            commented.write_text(
                "#!/usr/bin/env bash\n# never use ${pair^} here\necho ok\n"
            )

            self.assertEqual(
                ["active.sh:3 uses ${var^}"],
                self._scan([active]),
                "the scan no longer detects an active bash 4 expansion",
            )
            self.assertEqual(
                [],
                self._scan([commented]),
                "the scan flagged a construct inside a comment, which cannot execute",
            )


if __name__ == "__main__":
    unittest.main()
