"""A workflow no pull request runs can be merged with every check green and none of them about it.

`cross-repo-external.yml` is in exactly that position here - `schedule` and `workflow_dispatch` only.
A sibling repository measured the cost of the same shape: it merged behind 31 passing checks, **none
of which were that workflow**, and the first manual dispatch failed. Diagnosing that took a second
merge.

The corpus is shared with `--selftest` so the two cannot drift, and the assertion over the real
workflows is **a property, not a count** - a sibling pinned a number counted over `*.yml` while
scanning `*.y*ml`, leaving two files outside the number and inside the scan.
"""

import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_workflow_observability as W

SCRIPT = ROOT / "scripts" / "check_workflow_observability.py"


class TheCorpusIsShared(unittest.TestCase):
    def test_every_case_parses_to_its_declared_triggers(self) -> None:
        for text, expected in W.CASES:
            with self.subTest(text=text[:40]):
                self.assertEqual(W.triggers(text), expected)

    def test_the_word_on_appearing_mid_line_does_not_truncate_the_block(self) -> None:
        """A mutation removing the `^` anchor from `ON_BLOCK` survived every other case.

        Without it the match starts inside a comment, the lookahead stops at the next top-level key,
        and a workflow that does run on pull requests is called unobserved.
        """
        text = "# runs on: a schedule\nname: x\non:\n  pull_request:\n\njobs:\n"
        self.assertEqual(W.observability(text), "observed")


class TheRealWorkflowsAreClassified(unittest.TestCase):
    def test_every_workflow_parses_to_at_least_one_trigger(self) -> None:
        """A property rather than a count, so it cannot drift from the scan."""
        for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
            with self.subTest(path.name):
                self.assertTrue(
                    W.triggers(path.read_text(encoding="utf-8")),
                    f"{path.name} parsed to no triggers, so its verdict means nothing",
                )

    def test_observed_is_never_claimed_without_an_observing_trigger(self) -> None:
        for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
            text = path.read_text(encoding="utf-8")
            if W.observability(text) == "observed":
                with self.subTest(path.name):
                    self.assertTrue(W.triggers(text) & W.OBSERVED)


class TheHookAsksAndNeverBlocks(unittest.TestCase):
    """`ask`, not `block`. Dispatching needs the branch pushed first, so a person drives the sequence.

    This was not theoretical: a first version resolved the script through `git rev-parse` in the hook
    process's working directory, which is not the repository, so **it failed on every shell command
    and blocked unrelated work.** It was removed within a minute - which is the argument against
    `block` demonstrated rather than reasoned.
    """

    def _run(self, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--hook"],
            input=json.dumps({"tool_input": {"command": command}}),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

    def test_an_unrelated_command_is_silent(self) -> None:
        result = self._run("git status")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_malformed_input_does_not_stop_the_tool(self) -> None:
        """A guard that cannot read its input must not block the work it guards."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--hook"],
            input="not json",
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0)

    def test_a_merge_never_exits_nonzero(self) -> None:
        """Exit 2 is a block in this hook contract, so the verdict must travel in the payload."""
        self.assertEqual(self._run("gh pr merge 1 --squash").returncode, 0)

    def test_the_payload_asks_and_names_the_workflow(self) -> None:
        """Driven by a stub rather than by the branch's own diff.

        Reading the real diff made this skip whenever the branch touched no unobserved workflow, and
        a test that skips on most branches is a test that does not run. The stub fixes the input so
        the payload is always exercised.
        """
        with (
            mock.patch.object(
                W,
                "changed_workflows",
                return_value=[".github/workflows/cross-repo-external.yml"],
            ),
            mock.patch.object(
                sys, "stdin", io.StringIO(json.dumps({"command": "gh pr merge 1"}))
            ),
            mock.patch("sys.stdout", new=io.StringIO()) as out,
        ):
            code = W.hook()
        self.assertEqual(code, 0, "the hook blocks instead of asking")
        emitted = json.loads(out.getvalue())["hookSpecificOutput"]
        self.assertEqual(emitted["permissionDecision"], "ask")
        self.assertIn(
            "cross-repo-external.yml",
            emitted["permissionDecisionReason"],
            "the reason does not name the workflow, so the person cannot judge it",
        )


if __name__ == "__main__":
    unittest.main()
