"""`pr-verify` must refuse a stale API answer, and must not refuse ordinary use.

The command exists because `gh pr checks` answers about the latest run rather than the current
head. It then had the same defect one layer up: called straight after a push, the API still reports
the previous head, so every lookup keys on a SHA that is **correct and stale**.

That happened four times in one session. Twice the old SHA had failed, so the answer was "not safe
to merge" and the wrong reason went unnoticed; **had the old SHA passed, this would have cleared a
merge for a commit it never examined.**

The first version of the guard compared local `HEAD` unconditionally, which refused every run from
`main` and against anyone else's pull request. **A check that refuses ordinary use gets worked
around**, which is the failure the whole command exists to prevent — so the comparison is scoped to
the case where the checked-out branch *is* the pull request's branch, and both directions are
tested.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_pr_checks.py"

sys.path.insert(0, str(ROOT / "scripts"))

from verify_pr_checks import head_verdict


class HeadComparisonIsScoped(unittest.TestCase):
    """The decision as a truth table, exercised rather than grepped for.

    These were assertions that the source *contained* certain strings. That cannot tell a behaviour
    from its spelling: a rename of a local variable failed them, and a mutation that changed the
    behaviour while keeping the text would have passed. A sibling repository named the general
    shape — **a prohibition is only enforceable if the code enforcing it can be reached by a test**,
    and the fix is extracting a function rather than moving a comment.
    """

    def test_no_branch_means_nothing_to_compare(self) -> None:
        self.assertEqual(
            head_verdict(branch="", pr_branch="feat/x", local="aaa", head="bbb"),
            "answer",
        )

    def test_a_different_branch_is_not_compared(self) -> None:
        """Reading someone else's pull request, or reading from main, must still work.

        Comparing unconditionally refuses both, and **a check that refuses ordinary use gets
        worked around** — which is the failure this command exists to prevent.
        """
        self.assertEqual(
            head_verdict(branch="main", pr_branch="feat/x", local="aaa", head="bbb"),
            "answer",
        )

    def test_the_same_branch_at_the_same_commit_answers(self) -> None:
        self.assertEqual(
            head_verdict(branch="feat/x", pr_branch="feat/x", local="aaa", head="aaa"),
            "answer",
        )

    def test_the_same_branch_at_a_different_commit_is_stale(self) -> None:
        """The case that cost four repeats: after a push the API serves the previous head."""
        self.assertEqual(
            head_verdict(branch="feat/x", pr_branch="feat/x", local="aaa", head="bbb"),
            "stale",
        )

    def test_an_unknown_local_head_does_not_invent_a_mismatch(self) -> None:
        """`git_head` returns "" when it cannot answer, and a guard that cannot run must not
        block the check it guards."""
        self.assertEqual(
            head_verdict(branch="feat/x", pr_branch="feat/x", local="", head="bbb"),
            "answer",
        )

    def test_a_stale_verdict_still_fails_the_command(self) -> None:
        """A warning printed above "safe to merge" is the same as no check at all."""
        source = SCRIPT.read_text(encoding="utf-8")
        # Matched on the call rather than on the comparison: a formatter moves `== "stale"` onto
        # its own line, and a test that breaks when the formatter runs is testing the formatter.
        marker = "head_verdict("
        index = source.rindex(marker)
        after = source[index : index + 900]
        self.assertIn('"stale"', after, "the stale branch is no longer taken in main")
        self.assertIn("return 1", after, "a stale head no longer fails the command")
        self.assertIn("sys.stderr", after, "the refusal is not reported on stderr")

    def test_git_lookups_scrub_the_environment(self) -> None:
        """An inherited GIT_DIR would invent a mismatch and refuse every verify.

        The same inheritance already fabricated a committed file in this repository,
        so neither helper may read another repository's HEAD. Both route through one
        implementation, so this asserts the scrubbing is there **and** that both
        helpers actually use it — checking only the shared function would pass if a
        helper grew its own `subprocess.run`.
        """
        source = SCRIPT.read_text(encoding="utf-8")
        shared = source[source.index("def _git") : source.index("def git_head")]
        self.assertIn(
            'startswith("GIT_")',
            shared,
            "_git no longer scrubs GIT_* and can answer about another repository",
        )
        for helper in ("def git_head", "def git_branch"):
            body = source[source.index(helper) : source.index(helper) + 400]
            body = body[: body.index("\ndef ", 1)] if "\ndef " in body[1:] else body
            self.assertIn(
                "_git(",
                body,
                f"{helper} does not route through the scrubbing helper",
            )
            self.assertNotIn(
                "subprocess.run",
                body,
                f"{helper} calls git directly, bypassing the scrubbing helper",
            )

    def test_the_script_still_runs(self) -> None:
        """A syntax error here disables the only pre-merge gate that keys on the head."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode, 2, f"expected the usage exit: {result.stderr}"
        )
        self.assertIn("usage", result.stderr)


if __name__ == "__main__":
    unittest.main()
