"""`make pr-verify` must judge on the newest run per workflow, not on every run at the SHA.

One head SHA can carry several runs of the same workflow. Editing a pull request title re-runs
`pr-title-check` against an unchanged head, so an earlier failure and a later success both sit under
that SHA. Counting every run made the failure permanent — the title was fixed, the new run passed, and
the gate still refused the merge with no way to clear it short of pushing a commit.

The other direction matters just as much: taking the newest run must not let a *different* commit's
result answer for this one. That separation lives in the head-SHA filter, so the tests below hold the
SHA fixed and only vary the runs within it.
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "verify_pr_checks.py"


def load():
    spec = importlib.util.spec_from_file_location("verify_pr_checks", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(name: str, conclusion: str, created: str, sha: str = "abc123") -> dict:
    return {
        "headSha": sha,
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "createdAt": created,
    }


class LatestPerWorkflow(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load()

    def test_a_later_success_supersedes_an_earlier_failure(self) -> None:
        """The exact case that blocked PR #85: title edited, re-run passed, old failure lingered."""
        runs = [
            run("pr-title-check", "success", "2026-09-01T05:00:00Z"),
            run("pr-title-check", "failure", "2026-09-01T04:00:00Z"),
        ]
        kept, superseded = self.mod.latest_per_workflow(runs)
        self.assertEqual([r["conclusion"] for r in kept], ["success"])
        self.assertEqual([r["conclusion"] for r in superseded], ["failure"])

    def test_a_later_failure_supersedes_an_earlier_success(self) -> None:
        """The gate must not be softened: a re-run that fails is the verdict."""
        runs = [
            run("ci", "failure", "2026-09-01T05:00:00Z"),
            run("ci", "success", "2026-09-01T04:00:00Z"),
        ]
        kept, superseded = self.mod.latest_per_workflow(runs)
        self.assertEqual([r["conclusion"] for r in kept], ["failure"])
        self.assertEqual([r["conclusion"] for r in superseded], ["success"])

    def test_distinct_workflows_are_all_kept(self) -> None:
        runs = [
            run("ci", "success", "2026-09-01T04:00:00Z"),
            run("gitleaks", "success", "2026-09-01T04:00:01Z"),
            run("pr-title-check", "success", "2026-09-01T04:00:02Z"),
        ]
        kept, superseded = self.mod.latest_per_workflow(runs)
        self.assertEqual(
            sorted(r["name"] for r in kept), ["ci", "gitleaks", "pr-title-check"]
        )
        self.assertEqual(superseded, [])

    def test_an_unfinished_later_run_still_wins(self) -> None:
        """A re-run in flight must not be answered by the previous run's success."""
        pending = {
            "headSha": "abc123",
            "name": "ci",
            "status": "in_progress",
            "conclusion": None,
            "createdAt": "2026-09-01T05:00:00Z",
        }
        runs = [pending, run("ci", "success", "2026-09-01T04:00:00Z")]
        kept, _ = self.mod.latest_per_workflow(runs)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["status"], "in_progress")
        self.assertIsNone(kept[0]["conclusion"])

    def test_required_workflows_are_still_declared(self) -> None:
        """Selection must not quietly drop a workflow from the required set."""
        self.assertEqual(
            sorted(self.mod.REQUIRED), ["ci", "gitleaks", "pr-title-check"]
        )

    def test_created_at_is_requested_from_gh(self) -> None:
        """The selection is only correct if the timestamp is actually fetched."""
        source = SCRIPT.read_text()
        self.assertIn("createdAt", source)
        self.assertIn("headSha,name,status,conclusion,createdAt", source)

    def test_the_head_sha_filter_is_still_present(self) -> None:
        """Latest-per-workflow must not replace the SHA keying that prevents a stale read."""
        source = SCRIPT.read_text()
        self.assertIn('r["headSha"] == head', source)


if __name__ == "__main__":
    unittest.main()
