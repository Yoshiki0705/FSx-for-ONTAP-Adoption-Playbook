"""Every git call in this suite must pass an explicit environment.

The tracked pre-commit hook runs `make all`, which runs this suite, so a git call here inherits
`GIT_DIR` and `GIT_INDEX_FILE` from the hook and acts on the real repository. That fabricated a
committed file in this repository and then re-created it every time it was removed, silently. The
full diagnosis is in `gitenv.py`.

Two tests were fixed one at a time before the shape was recognised, which is the argument for a
check on the shape rather than on the instances. **A test that shells out to git is a test that
can act on the wrong repository**, and there is nothing about a scratch directory that prevents it.

This is a source check, so state the limits plainly:

- It looks for `"git"` as the first element of a subprocess argument list and requires `env=`
  within the following window of lines. A call spread wider than the window reads as a violation,
  which is the safe direction.
- It cannot tell whether the environment passed is actually scrubbed. `gitenv.scrubbed_env` exists
  so there is one place to get that right, and a caller that hand-builds a dict satisfies this
  check while being wrong. That is why the fixtures also assert they own their git dir — a
  behavioural check, downstream of this one.
- **It sees git invocations, not scripts that call git internally.** A test that launches one of
  the tools under `tools/` or `scripts/` passes this check while handing that tool an inherited
  `GIT_DIR`. That happened immediately: the fixture's `_git` was scrubbed and its `run()`, which
  launches the checker, was not — so `git add` wrote to the fixture while the checker read the
  caller's repository. Before either half was scrubbed the two agreed on the wrong tree and the
  suite passed. **Fixing one half is what made the disagreement visible**, which is the argument
  for scrubbing every subprocess in a fixture rather than the ones that say `git`.

**Why production code is scanned, not only this test suite.** The suite is not the only code the
hook runs. `make all` runs the whole gate, so any `git` call inside a tool under `scripts/` or
`tools/` inherits the hook's `GIT_DIR` too — and there `cwd=ROOT` looks like protection but is not,
because an inherited `GIT_DIR` outranks `cwd`. Such a call does not write; it reads the wrong
repository and returns a wrong answer **silently**. A sibling repository shipped exactly this: three
production `git` calls with no `env=`, caught by nothing because the enforcement scan only looked at
its own tests. So the scan below covers every `.py` under `scripts/` and `tools/`, which subsumes
the test suite rather than sitting beside it.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent.parent
# Wide enough for a call formatted across several lines by the formatter, narrow enough that it
# cannot reach into an unrelated call further down.
WINDOW = 12
GIT_CALL = re.compile(r"\[\s*\"git\"")


def _scanned_files() -> list[Path]:
    """Every `.py` under scripts/ and tools/, minus this file, which quotes the pattern.

    Recursive on purpose: it takes in the production tools and the test suite in one set, so a
    new `git` call is covered wherever it lands. `sorted` keeps the offender list deterministic.
    """
    self_name = Path(__file__).resolve()
    found: list[Path] = []
    for root in (ROOT / "scripts", ROOT / "tools"):
        found += root.rglob("*.py")
    return sorted(p for p in found if p.resolve() != self_name)


class GitCallsPassAnEnvironment(unittest.TestCase):
    def test_every_git_call_passes_env(self) -> None:
        offenders: list[str] = []
        for path in _scanned_files():
            lines = path.read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines):
                if not GIT_CALL.search(line):
                    continue
                window = "\n".join(lines[number : number + WINDOW])
                if "env=" not in window:
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{number + 1}: {line.strip()}"
                    )
        self.assertEqual(
            offenders,
            [],
            "these git calls inherit GIT_DIR from a pre-commit hook and would act on the wrong "
            "repository; pass env={k: v for k, v in os.environ.items() if not "
            "k.startswith('GIT_')} (or gitenv.scrubbed_env() in the test suite):\n  "
            + "\n  ".join(offenders),
        )

    def test_the_scan_covers_production_code(self) -> None:
        """The scan must reach the tools, not only the test suite it started as.

        A regression that narrowed the set back to `scripts/tests/` would make the scan pass while
        blind to every production tool — the exact shape it exists to close. Anchor it on a known
        production file rather than a count, so it does not drift with the tree.
        """
        scanned = {p.resolve() for p in _scanned_files()}
        for name in (
            "tools/report_i18n_status.py",
            "scripts/check_agent_context_budget.py",
        ):
            self.assertIn(
                (ROOT / name).resolve(),
                scanned,
                f"{name} is a production git caller and must be in the scan set",
            )

    def test_the_check_detects_a_bare_call(self) -> None:
        """A source check that matches nothing is indistinguishable from a clean tree."""
        sample = 'subprocess.run(["git", "init"], cwd=work, check=True)'
        self.assertRegex(
            sample, GIT_CALL, "the pattern no longer matches a git call at all"
        )
        self.assertNotIn("env=", sample)


if __name__ == "__main__":
    unittest.main()
