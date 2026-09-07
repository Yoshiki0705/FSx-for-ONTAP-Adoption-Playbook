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
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
# Wide enough for a call formatted across several lines by the formatter, narrow enough that it
# cannot reach into an unrelated call further down.
WINDOW = 12
GIT_CALL = re.compile(r"\[\s*\"git\"")


class GitCallsPassAnEnvironment(unittest.TestCase):
    def test_every_git_call_passes_env(self) -> None:
        offenders: list[str] = []
        for path in sorted(TESTS.glob("test_*.py")):
            if path.name == Path(__file__).name:
                continue  # This file quotes the pattern it looks for.
            lines = path.read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines):
                if not GIT_CALL.search(line):
                    continue
                window = "\n".join(lines[number : number + WINDOW])
                if "env=" not in window:
                    offenders.append(f"{path.name}:{number + 1}: {line.strip()}")
        self.assertEqual(
            offenders,
            [],
            "these git calls inherit GIT_DIR from a pre-commit hook and would act on the real "
            "repository; pass env=scrubbed_env():\n  " + "\n  ".join(offenders),
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
