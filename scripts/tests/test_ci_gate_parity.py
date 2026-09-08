"""Every gate in `make all` must actually run in a workflow.

Why this exists
---------------
The gate set is written down twice: once as the prerequisites of `make all`, and once as the steps
of `.github/workflows/ci.yml`. Nothing compared the two, so one could be extended and the other
left alone — and the failure is silent in the direction that matters. A target sitting in `make all`
reads as "CI runs this". Nobody re-derives it.

That is not hypothetical here. `diagram-fonts` and `diagram-flow` were added to `make all` with a
comment saying CI therefore runs them on every change; `ci.yml` never called them, and the comment
went on looking true because no check read both files. They were added to `ci.yml` later, by hand.
Four more were in the same state when this test was written: `headings`, `ja-markers`, `anchors`
and `workflow-observability` — among them the heading convention that `AGENTS.md` documents as a
rule, and the externally-cited-anchor contract, whose whole premise is that **GitHub answers an
unknown fragment with the top of the page, so the citing side never observes the break.** A gate
that exists and does not run is worse than an absent one: it is credited in the checklist.

Two exemptions are recorded below rather than pretended away, each because a workflow covers the
same ground by a different mechanism. They are asserted to still be part of `make all`, so a rename
cannot leave a dead exemption behind that quietly excuses a real gap.

The parser is checked against a deliberately broken workflow. Comparing two sets that are both
empty reports agreement, so a regex that stopped matching would leave this test green forever —
the same shape of silence it exists to catch.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
WORKFLOWS = ROOT / ".github" / "workflows"

# `target: dep dep ## comment`, excluding `VAR := value` and `VAR ?= value`. Recipe lines start
# with a tab and are skipped, so a `make` call inside a recipe is not read as a prerequisite.
TARGET_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*)\s*:(?!=)(.*)$")

# A `make <target>` call anywhere on a non-comment line. Restricting this to `run:` lines would
# miss a call inside a `run: |` block, and those are the ones a reader is least likely to audit.
MAKE_CALL_RE = re.compile(r"\bmake\s+([a-z0-9][a-z0-9-]*)")
YAML_COMMENT_RE = re.compile(r"^\s*#")

# A gate `make all` runs that no workflow calls by name, because a workflow covers the same ground
# another way. Each value is the reason, and each key is asserted below to still exist in `make all`.
COVERED_ANOTHER_WAY = {
    "markdown": "the markdown-lint job runs markdownlint-cli2-action directly",
    "secrets": "gitleaks.yml scans the full history, which `make secrets` (worktree only) cannot",
}


def prerequisites(source: str) -> dict[str, list[str]]:
    """Map each target to its prerequisites, with the `## help` text stripped."""
    graph: dict[str, list[str]] = {}
    for line in source.splitlines():
        if line.startswith("\t"):
            continue
        match = TARGET_RE.match(line)
        if not match or match.group(1) == ".PHONY":
            continue
        deps = match.group(2).split("##", 1)[0].split()
        graph.setdefault(match.group(1), []).extend(deps)
    return graph


def leaf_gates(graph: dict[str, list[str]], root: str = "all") -> set[str]:
    """The targets reached from `root` that have no prerequisites of their own.

    `all` depends on `lint`, and `lint` depends on six targets that CI calls individually. Comparing
    the direct prerequisites of `all` would therefore report `lint` as missing from a workflow that
    runs every part of it.
    """
    leaves: set[str] = set()
    seen: set[str] = set()
    stack = [root]
    while stack:
        target = stack.pop()
        if target in seen:
            continue
        seen.add(target)
        deps = graph.get(target, [])
        if deps:
            stack.extend(deps)
        else:
            leaves.add(target)
    return leaves


def make_calls(workflow_source: str) -> set[str]:
    """The Makefile targets a workflow calls, ignoring comments.

    Comments matter: `ci.yml` carries a comment containing `make all`, and a comment naming a target
    must not be read as running it. That is the exact confusion this test exists to end.
    """
    return {
        match.group(1)
        for line in workflow_source.splitlines()
        if not YAML_COMMENT_RE.match(line)
        for match in MAKE_CALL_RE.finditer(line)
    }


def calls_in_all_workflows() -> set[str]:
    called: set[str] = set()
    for path in sorted(WORKFLOWS.glob("*.yml")):
        called |= make_calls(path.read_text(encoding="utf-8"))
    return called


class GateSetParity(unittest.TestCase):
    def test_every_gate_in_make_all_runs_in_a_workflow(self) -> None:
        gates = leaf_gates(prerequisites(MAKEFILE.read_text(encoding="utf-8")))
        missing = sorted(gates - calls_in_all_workflows() - set(COVERED_ANOTHER_WAY))
        self.assertEqual(
            missing,
            [],
            "these targets are prerequisites of `make all` but no workflow calls them, so they run "
            "only when someone runs `make all` by hand: "
            f"{missing}. Add a step, or record why another workflow covers it in "
            "COVERED_ANOTHER_WAY.",
        )

    def test_no_exemption_names_a_target_make_all_no_longer_has(self) -> None:
        """A renamed target must not leave its exemption behind.

        An exemption for a target that no longer exists excuses nothing and looks like it does. The
        next real gap gets the same treatment because the list already reads as maintained.
        """
        gates = leaf_gates(prerequisites(MAKEFILE.read_text(encoding="utf-8")))
        stale = sorted(set(COVERED_ANOTHER_WAY) - gates)
        self.assertEqual(
            stale,
            [],
            f"exempted but not part of `make all` any more: {stale}",
        )

    def test_the_parsers_are_not_returning_empty_sets(self) -> None:
        """Both sides must be non-empty, or the comparison above is vacuous.

        A set difference against an empty set is empty, so a regex that stopped matching would keep
        every assertion here green. Naming specific members pins that: `python` is called by a step
        and `test` is the last one, so losing either parser is a failure rather than a silence.
        """
        gates = leaf_gates(prerequisites(MAKEFILE.read_text(encoding="utf-8")))
        called = calls_in_all_workflows()
        self.assertIn("python", gates, "the Makefile parser found no known gate")
        self.assertIn("test", gates, "the Makefile parser lost a known gate")
        self.assertIn("python", called, "the workflow parser found no known make call")
        self.assertIn("test", called, "the workflow parser lost a known make call")

    def test_detects_a_gate_missing_from_the_workflow(self) -> None:
        """The break case. A green run has to be distinguishable from a broken parser."""
        makefile = ".PHONY: all\nall: lint audit\nlint: python headings\n"
        workflow = "      - run: make python\n      - run: make audit\n"
        gates = leaf_gates(prerequisites(makefile))
        self.assertEqual(gates, {"python", "headings", "audit"})
        self.assertEqual(sorted(gates - make_calls(workflow)), ["headings"])

    def test_a_commented_out_call_does_not_count_as_running(self) -> None:
        """`ci.yml` really does mention a target inside a comment."""
        self.assertEqual(
            make_calls("      # they were in `make all` but not here\n"), set()
        )
        self.assertEqual(make_calls("      - run: make all\n"), {"all"})

    def test_a_call_inside_a_run_block_counts(self) -> None:
        """A multi-line `run: |` is still a call, and is the easiest kind to overlook."""
        self.assertEqual(
            make_calls("      - run: |\n          make audit\n          make links\n"),
            {"audit", "links"},
        )


if __name__ == "__main__":
    unittest.main()
