"""The irreversibility guard must block, ask, and allow — proven by execution.

Why this exists
---------------
`scripts/guard_irreversible_ops.py` carries an in-file corpus and a `--selftest`
flag. That corpus only proves the *matching logic* is right. It does not prove
the script behaves correctly as a Kiro PreToolUse hook, and the hook contract is
where this class of guard usually fails:

  exit 0 + empty stdout            -> allow
  exit 0 + permissionDecision:ask  -> prompt the human first
  exit 2 + stderr                  -> block, stderr goes back to the agent
  any other non-zero               -> warning only; execution CONTINUES

A guard that signals "block" with exit 1 looks like it is working and stops
nothing. So these tests drive the real script through a subprocess with a real
JSON event on stdin and assert the exit code, stdout, and stderr separately.

The corpus is imported rather than restated. Once the guard is wired to a hook,
a matching literal typed on a command line gets the verification run itself
blocked, so the cases must never travel through a shell.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "guard_irreversible_ops.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("guard_irreversible_ops", GUARD)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


def run(command: str) -> tuple[int, str, str]:
    """Invoke the guard exactly as a PreToolUse hook does."""
    event = json.dumps({"tool_input": {"command": command}})
    done = subprocess.run(
        [sys.executable, str(GUARD)],
        input=event,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return done.returncode, done.stdout, done.stderr


def verdict_of(command: str) -> str:
    code, out, _err = run(command)
    if code == 2:
        return "block"
    if code == 0 and "permissionDecision" in out:
        return "ask"
    if code == 0:
        return "allow"
    return f"invalid(exit={code})"


class GuardContract(unittest.TestCase):
    def test_block_uses_exit_2_and_stderr(self) -> None:
        code, out, err = run(
            "aws ec2 lock-snapshot --snapshot-id snap-1 --lock-mode compliance"
        )
        self.assertEqual(code, 2, "only exit 2 blocks; any other non-zero is a warning")
        self.assertIn("BLOCKED", err)
        self.assertEqual(out, "", "a block must not also emit a permission decision")

    def test_ask_uses_exit_0_and_a_permission_decision(self) -> None:
        code, out, _err = run("aws fsx delete-file-system --file-system-id fs-0abc")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"],
            "ask",
            "asking is exit 0 plus this payload; a non-zero exit would not prompt",
        )
        self.assertTrue(
            payload["hookSpecificOutput"]["permissionDecisionReason"].strip()
        )

    def test_allow_is_silent(self) -> None:
        code, out, err = run("aws fsx describe-volumes --volume-ids fsvol-0abc")
        self.assertEqual((code, out, err), (0, "", ""))

    def test_read_only_inspection_is_never_blocked(self) -> None:
        """Refusing to let an agent look pushes it toward guessing, which is worse."""
        for command in (
            "aws s3api get-object-lock-configuration --bucket b",
            "aws fsx describe-volumes --query 'Volumes[0].LifecycleTransitionReason'",
        ):
            with self.subTest(command=command):
                self.assertEqual(verdict_of(command), "allow")

    def test_malformed_event_does_not_block_all_work(self) -> None:
        done = subprocess.run(
            [sys.executable, str(GUARD)],
            input="not json at all",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertIn(done.returncode, (0, 2))
        self.assertNotIn(
            done.returncode,
            (1,),
            "exit 1 is a warning that does not block; the guard must never use it",
        )


class GuardCorpus(unittest.TestCase):
    """Run the in-file corpus through the real process, not just the matcher."""

    def test_block_and_allow_corpus(self) -> None:
        for want, description, command in guard.SELFTEST_CASES:
            expected = "block" if want == 2 else "allow"
            with self.subTest(case=description):
                self.assertEqual(verdict_of(command), expected)

    def test_ask_corpus(self) -> None:
        for expected, description, command in guard.ASK_CASES:
            with self.subTest(case=description):
                self.assertEqual(verdict_of(command), expected)

    def test_corpus_covers_all_three_verdicts(self) -> None:
        """A corpus that lost its allow cases would let over-blocking through."""
        verdicts = {
            "block" if w == 2 else "allow" for w, _d, _c in guard.SELFTEST_CASES
        }
        verdicts |= {v for v, _d, _c in guard.ASK_CASES}
        self.assertEqual(verdicts, {"block", "ask", "allow"})

    def test_every_documented_immutability_area_has_a_block_case(self) -> None:
        """A feature area with patterns but no case is an untested claim.

        This is the check that would have caught the divergence this suite was
        written for: the pattern table listed Glacier, Backup, and EBS locks
        while the guard actually being executed by the hook covered none of them.
        """
        uncovered = []
        for area in guard.IMMUTABILITY_PATTERNS:
            hit = any(
                area in guard.find_matches(command)[0]
                for want, _d, command in guard.SELFTEST_CASES
                if want == 2
            )
            if not hit:
                uncovered.append(area)
        self.assertEqual(
            uncovered, [], f"feature areas with no block case: {uncovered}"
        )


if __name__ == "__main__":
    unittest.main()
