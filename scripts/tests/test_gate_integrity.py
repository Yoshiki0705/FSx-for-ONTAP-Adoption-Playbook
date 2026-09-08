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

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.tests.gitenv import scrubbed_env

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
        """Hide the tool with an empty PATH and an absolute make, then require the message.

        Narrowing PATH to `/usr/bin:/bin` was not a reliable way to hide a tool -- it worked here
        only because these linters happen to install elsewhere, and on a runner where one lives in
        /usr/bin the premise silently stops holding. `shell` and `cfn` were moved to an empty PATH
        for exactly that reason; these two were left behind.

        The message assertion is the whole mechanism, not decoration. With no PATH the recipe cannot
        reach `find` either, so it dies at 127 whether or not the guard exists: a bare non-zero exit
        is satisfied by deleting the guard. Only naming the tool distinguishes "the gate refused to
        run without its tool" from "the recipe fell over".
        """
        make_bin = shutil.which("make")
        self.assertIsNotNone(make_bin, "make is not on PATH; this test cannot run")
        for target in ("markdown", "secrets"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as empty:
                done = subprocess.run(
                    [str(make_bin), target],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    env={"PATH": empty, "HOME": str(Path.home())},
                    check=False,
                )
                self.assertNotEqual(
                    done.returncode,
                    0,
                    f"`make {target}` succeeded with its tool unreachable:\n"
                    f"{done.stdout}{done.stderr}",
                )
                self.assertIn(
                    "not installed",
                    done.stdout + done.stderr,
                    f"`make {target}` failed without saying which tool is missing, so deleting "
                    "the guard would leave this test passing",
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
            "cross-repo",
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
                env=scrubbed_env(),
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


class NetworkTestsHaveACredential(unittest.TestCase):
    """A break test that skips on someone else's quota verifies nothing, and still exits 0.

    Four tests in `test_doc_gates.py` reach the GitHub API and skip with the reason named when it
    answers `cannot resolve`. Skipping is the right behaviour — a sibling repository being briefly
    unreachable is not a defect in the change under review, and a gate that reddens for that gets
    ignored. What is not right is skipping *routinely*: unauthenticated access is 60 requests an
    hour against an address a hosted runner shares, so with no credential those four are the normal
    outcome rather than the exception, and `make test` reports `OK` having checked none of them.

    Measured locally: the skip count moved between runs (9, then 11, then 0) purely with the quota
    state, which is the property that makes a green run unreadable. With a token the network skips
    went to zero and only the `.kiro/hooks` ones remained, those being absent by design in CI.

    `cross-repo-external.yml` already passes `github.token` for the same reason. The test step is a
    second, separate path to the same API and did not.
    """

    STEP_START = re.compile(r"^\s*-\s+name:")
    # A job key at two-space indent. Without this the last step of a job runs on into the next job,
    # and a token belonging to a different job would read as covering this step.
    JOB_START = re.compile(r"^ {2}[A-Za-z0-9_-]+:\s*$")
    RUNS_MAKE_TEST = re.compile(r"^\s*run:\s*make\s+test\b", re.MULTILINE)

    def steps_running_make_test(self) -> list[tuple[Path, str]]:
        found: list[tuple[Path, str]] = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            current: list[str] = []
            chunks: list[str] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                boundary = self.STEP_START.match(line) or self.JOB_START.match(line)
                if boundary and current:
                    chunks.append("\n".join(current))
                    current = [] if self.JOB_START.match(line) else [line]
                else:
                    current.append(line)
            if current:
                chunks.append("\n".join(current))
            found += [(path, c) for c in chunks if self.RUNS_MAKE_TEST.search(c)]
        return found

    def test_the_step_running_make_test_is_given_a_token(self) -> None:
        steps = self.steps_running_make_test()
        self.assertTrue(
            steps, "no workflow step runs `make test`; this test is looking at nothing"
        )
        for path, chunk in steps:
            with self.subTest(workflow=path.name):
                self.assertIn(
                    "GITHUB_TOKEN",
                    chunk,
                    f"{path.name} runs `make test` without a token, so the API-dependent break "
                    "tests skip on the anonymous 60-per-hour limit and the gate still exits 0. "
                    "Add `env: GITHUB_TOKEN: ${{ github.token }}`; it needs no permission beyond "
                    "the read-only `contents` already granted.",
                )

    @unittest.skipUnless(
        os.environ.get("GITHUB_ACTIONS") == "true",
        "asserts a property of the runner; there is no runner locally",
    )
    def test_a_runner_actually_receives_a_non_empty_token(self) -> None:
        """The workflow text can name a token that arrives empty.

        `secrets.SOMETHING_MISPELLED` expands to the empty string, so the step above would pass
        while every network test still skipped. This is the half that only a runner can answer.
        """
        self.assertTrue(
            os.environ.get("GITHUB_TOKEN", "").strip(),
            "GITHUB_TOKEN is empty on the runner, so the API-dependent tests will skip on quota "
            "while this gate reports success",
        )


if __name__ == "__main__":
    unittest.main()
