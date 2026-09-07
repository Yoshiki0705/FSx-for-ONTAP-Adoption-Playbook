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


class HeadComparisonIsScoped(unittest.TestCase):
    def test_comparison_is_skipped_when_the_branch_differs(self) -> None:
        """Reading someone else's pull request from another branch must still work.

        Asserted on the source rather than by running the command, because running it
        needs the network and a pull request in a particular state. What matters is
        that the SHA is only fetched under the branch-name condition.
        """
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            'local = git_head() if branch and branch == pr.get("headRefName") else ""',
            source,
            "the head comparison is no longer scoped to the pull request's own branch, so it "
            "refuses every run from main and against anyone else's pull request",
        )

    def test_a_mismatch_is_a_failure_and_not_a_warning(self) -> None:
        """A stale answer must stop the merge, not annotate it.

        `pr-verify` is read for a go/no-go, so a warning printed above a "safe to
        merge" line is the same as no check at all.
        """
        source = SCRIPT.read_text(encoding="utf-8")
        marker = "if local and local != head:"
        self.assertIn(marker, source)
        after = source[source.index(marker) : source.index(marker) + 800]
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
