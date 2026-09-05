"""A gate that cannot run must fail, not skip — and CI must inspect the same tree.

Why this exists
---------------
Three of this repository's gates used to degrade quietly when their tool was
absent. `make markdown` printed "skipping" and returned success. `make audit`
printed "skipping secret scan" and returned success — and that is the state it
was in inside CI's docs-quality job, where gitleaks is not installed, so half
of that target was decorative on every run. `make python` warned about a ruff
version mismatch and carried on.

All three produce the same artifact: a green result standing in for a check that
did not happen. A gate whose tool is missing has to say so with a non-zero exit,
because the alternative is indistinguishable from passing.

The second half of the file guards against the other direction: CI and a
developer's machine inspecting different trees. The lint scope is defined once in
the Makefile, and these tests fail if a workflow starts carrying its own copy.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
WORKFLOWS = ROOT / ".github" / "workflows"

TOOL_PROBE = re.compile(r"command -v\s+(\S+)")


def makefile_text() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


def variable(name: str) -> list[str]:
    match = re.search(rf"^{name}\s*:?=\s*(.*)$", makefile_text(), re.MULTILINE)
    return match.group(1).split() if match else []


def recipe(target: str) -> str:
    """Return the recipe body for one target."""
    source = makefile_text()
    start = re.search(rf"^{re.escape(target)}\s*:", source, re.MULTILINE)
    if not start:
        return ""
    body: list[str] = []
    for line in source[start.end() :].splitlines()[1:]:
        if line and not line[0].isspace():
            break
        body.append(line)
    return "\n".join(body)


class ToolAbsenceFailsLoudly(unittest.TestCase):
    def test_a_target_that_probes_for_a_tool_also_exits_non_zero(self) -> None:
        """Probing for a tool is fine. Continuing without it is not.

        Checked structurally rather than by looking for the word "skipping", so
        that an explanation mentioning the word does not read as the defect.
        """
        for target in (
            "markdown",
            "secrets",
            "python",
            "audit",
            "frontmatter",
            "links",
            "shell",
            "cfn",
        ):
            body = recipe(target)
            if not TOOL_PROBE.search(body):
                continue
            with self.subTest(target=target):
                self.assertIn(
                    "exit 1",
                    body,
                    f"`make {target}` tests for its tool but has no failing branch, so "
                    "it reports success when the tool is absent — indistinguishable "
                    "from having run.",
                )

    def test_missing_tool_produces_a_non_zero_exit(self) -> None:
        """Run each gate with an empty PATH, so its tool cannot be found."""
        # "shell" and "cfn" are not listed here: on some runners their tools live in /usr/bin,
        # which this PATH keeps reachable, so the premise "its tool cannot be found" does not
        # hold. scripts/tests/test_example_gates.py checks those two with an empty PATH and an
        # absolute make instead.
        for target in ("markdown", "secrets"):
            with self.subTest(target=target):
                done = subprocess.run(
                    ["make", target],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    # /usr/bin keeps make and the shell reachable while removing the
                    # linters, which live in /opt/homebrew/bin and ~/.local/bin.
                    env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
                    check=False,
                )
                self.assertNotEqual(
                    done.returncode,
                    0,
                    f"`make {target}` succeeded with its tool unavailable:\n"
                    f"{done.stdout}{done.stderr}",
                )

    def test_python_gate_fails_when_ruff_cannot_be_resolved(self) -> None:
        """Emptying PATH is not enough for this one, deliberately.

        `make python` resolves ruff from `.venv/bin` first, so on a machine with a
        virtual environment the tool stays reachable with no PATH at all — which is
        the point of that change. The failing branch is therefore driven by
        overriding the resolved value, rather than by an environment trick that
        only works when no venv exists.
        """
        done = subprocess.run(
            ["make", "python", "RUFF="],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("would check nothing", done.stdout + done.stderr)

    def test_python_gate_prefers_a_project_local_virtualenv(self) -> None:
        """Otherwise resolution depends on PATH order, and a copy installed for
        something else silently wins — which is how linting ran on 0.15.20 here
        while the pin said otherwise."""
        self.assertIn(".venv/bin/ruff", makefile_text())
        for line in makefile_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "RUFF :=" in stripped:
                continue
            with self.subTest(line=stripped):
                self.assertNotRegex(
                    stripped,
                    r"^@?ruff\s",
                    "invoke ruff through $(RUFF) so the venv is preferred",
                )

    def test_secret_scanning_is_separate_from_the_output_audit(self) -> None:
        """Bundled, only one of the two was running in CI and nothing said so."""
        self.assertNotIn("gitleaks", recipe("audit"))
        self.assertIn("gitleaks", recipe("secrets"))

    def test_commit_gate_includes_every_check(self) -> None:
        expected = {
            "lint",
            "i18n-check",
            "switcher-check",
            "audit",
            "secrets",
            "links",
            "drift",
            "test",
        }
        match = re.search(r"^all:([^#]*)", makefile_text(), re.MULTILINE)
        assert match
        self.assertTrue(
            expected.issubset(set(match.group(1).split())),
            f"`make all` is missing: {sorted(expected - set(match.group(1).split()))}",
        )


class CiInspectsTheSameTree(unittest.TestCase):
    def workflow_text(self) -> str:
        return "\n".join(p.read_text(encoding="utf-8") for p in WORKFLOWS.glob("*.yml"))

    def test_python_paths_are_not_restated_in_any_workflow(self) -> None:
        """`ruff check tools scripts` in CI plus PY_PATHS here is two lists to keep."""
        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            for number, line in enumerate(
                workflow.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if line.strip().startswith("#"):
                    continue
                with self.subTest(workflow=workflow.name, line=number):
                    self.assertNotRegex(
                        line,
                        r"ruff\s+(check|format)\s+\S",
                        "call `make python` instead; the path list belongs in PY_PATHS",
                    )

    def test_markdown_globs_match_the_makefile(self) -> None:
        """The action and the Makefile must lint the same set of files.

        The two notations differ — the CLI marks an exclusion with a leading `#`
        (escaped in the Makefile so make does not read it as a comment) and the
        action's YAML uses `!` — so the comparison normalizes before matching.
        Comparing the raw strings instead just proves the two files are written
        differently, which they are.
        """
        includes, excludes = set(), set()
        for raw in variable("MD_GLOBS"):
            glob = raw.strip('"').lstrip("\\")
            (excludes if glob.startswith(("#", "!")) else includes).add(
                glob.lstrip("#!")
            )

        text = self.workflow_text()
        for glob in includes:
            self.assertIn(
                glob,
                text,
                f"the Makefile lints {glob} but no workflow does, so a file can fail "
                "locally and pass in CI or the reverse",
            )
        for glob in excludes:
            if f"!{glob}" in text:
                continue
            # An exclusion may be absent from CI when the path cannot be there:
            # a gitignored directory is not in a fresh checkout, so excluding it
            # is a local-only concern rather than a divergence.
            ignored = subprocess.run(
                ["git", "check-ignore", "-q", glob],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                ignored.returncode,
                0,
                f"the Makefile excludes {glob} from markdownlint, no workflow does, "
                "and it is not gitignored — so CI lints files that pass locally",
            )

    def test_validators_are_invoked_through_make(self) -> None:
        """One definition of how a check runs, so it cannot run two ways."""
        text = self.workflow_text()
        for target in (
            "make python",
            "make audit",
            "make links",
            "make test",
            "make drift",
        ):
            with self.subTest(target=target):
                self.assertIn(target, text)


if __name__ == "__main__":
    unittest.main()
