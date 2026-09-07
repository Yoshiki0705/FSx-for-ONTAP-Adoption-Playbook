"""Break the tools on purpose, and require the right test to be the one that notices.

A test that fires on a bad input has shown it can fail. It has **not** shown that it can tell a
correct fix from a lazy one, and those are different properties. This repository learned the
difference the hard way: the boundary tests for the audit were both positive, so a version with the
boundaries **deleted outright** passed them — and deleting the boundary is exactly the shortest way
to make the failing case pass. A sibling repository found that by mutation-testing its own
equivalent, and this file is the mechanism rather than a note saying to remember.

Each mutation below records a **plausible wrong fix**, not an arbitrary corruption. The value is in
the plausibility: nobody accidentally empties a regex, but "the Japanese case fails, so remove the
`\\b`" is a fix someone would ship.

Two assertions per mutation, and the second is the one that carries the weight:

- the discriminating test **fails** — otherwise it does not discriminate;
- the tests that were already green **stay green** — otherwise the mutation is simply broken and
  proves nothing about which test is doing the work.

**Nothing is written inside the repository.** The tree is copied to a temporary directory and
mutated there. An earlier version of a different check in this repository wrote to the real index
through an inherited `GIT_DIR` and fabricated a committed file; a harness whose whole job is to
corrupt source must not be able to do that. `GIT_*` is scrubbed for the same reason.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.tests.gitenv import scrubbed_env

ROOT = Path(__file__).resolve().parents[2]
# The whole tree, minus what a gate never reads. The first version copied only `tools/` and
# `scripts/`, and the control caught it: the doc gates resolve every path against their own root, so
# a partial copy failed tests that had nothing to do with any mutation. **That is the control doing
# its job** — without it, those failures would have read as mutations being detected.
IGNORED = shutil.ignore_patterns(
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".private",
    "semantic-review",
    ".DS_Store",
)

MUTATIONS: list[dict] = [
    {
        "name": "ASCII boundaries emptied",
        "why": (
            "The shortest way to make the Japanese-adjacent case pass. Removing a boundary only "
            "widens a match, so every positive case still passes and the fix looks correct."
        ),
        "module": "scripts.tests.test_cjk_word_boundaries",
        "edits": [
            (
                "tools/audit_public_output.py",
                'ASCII_LEFT = r"(?<![A-Za-z0-9_])"',
                'ASCII_LEFT = r""',
            ),
            (
                "tools/audit_public_output.py",
                'ASCII_RIGHT = r"(?![A-Za-z0-9_])"',
                'ASCII_RIGHT = r""',
            ),
            (
                "tools/audit_public_output.py",
                r'r"(?<![0-9A-Za-z_.])\d{12}(?![0-9A-Za-z_.])"',
                r'r"\d{12}"',
            ),
        ],
        "must_fail": ["test_embedded_forms_are_not_reported"],
        "must_pass": [
            "test_japanese_adjacent_forms_are_reported",
            "test_spaced_ascii_forms_are_still_reported",
        ],
    },
    {
        "name": "underscore dropped from the boundary class",
        "why": (
            "Looks like a tightening and is a loosening. Without `_` the guard treats it as a "
            "boundary, so a configured resource name reads as prose — looser than the `\\b` it "
            "replaced. Reported by a sibling repository, which hit it on four names."
        ),
        "module": "scripts.tests.test_cjk_word_boundaries",
        "edits": [
            (
                "tools/audit_public_output.py",
                'ASCII_LEFT = r"(?<![A-Za-z0-9_])"',
                'ASCII_LEFT = r"(?<![A-Za-z0-9])"',
            ),
            (
                "tools/audit_public_output.py",
                'ASCII_RIGHT = r"(?![A-Za-z0-9_])"',
                'ASCII_RIGHT = r"(?![A-Za-z0-9])"',
            ),
        ],
        "must_fail": ["test_embedded_forms_are_not_reported"],
        "must_pass": [
            "test_japanese_adjacent_forms_are_reported",
            "test_spaced_ascii_forms_are_still_reported",
        ],
    },
    {
        "name": "self-link path check removed",
        "why": (
            "A self-link is not a cross-repository citation, which is true about citation and "
            "says nothing about whether the path exists. Skipping the whole check is how that "
            "distinction became a wider exclusion than the distinction it drew."
        ),
        "module": "scripts.tests.test_doc_gates",
        "edits": [
            (
                "tools/check_cross_repo.py",
                "    problems += check_self_paths()",
                "    pass  # mutation: self-path check removed",
            ),
        ],
        "must_fail": ["test_self_link_to_a_missing_path_is_rejected"],
        "must_pass": ["test_self_link_pinned_to_a_commit_is_accepted"],
    },
]


def run_tests(work: Path, module: str, names: list[str]) -> dict[str, str]:
    """Run exactly the named tests inside `work` and return {test name: outcome}.

    Only the declared tests, because the point is a verdict on those and the alternative is running
    an entire module twice per mutation for results nobody reads.
    """
    selectors: list[str] = []
    for name in names:
        selectors += ["-k", name]
    result = subprocess.run(
        [sys.executable, "-m", "unittest", module, "-v", *selectors],
        cwd=work,
        env=scrubbed_env(),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    outcomes: dict[str, str] = {}
    # unittest -v writes "name (path) ... ok" / "... FAIL" / "... ERROR" to stderr, and wraps the
    # line when a docstring is present, so the verdict can land on a later line.
    for match in re.finditer(
        r"^(test_\w+) \([^)]*\)(?:.*?)\.\.\. (ok|FAIL|ERROR|skipped.*)$",
        result.stderr,
        re.MULTILINE | re.DOTALL,
    ):
        outcomes.setdefault(match.group(1), match.group(2))
    for name in re.findall(
        r"^(?:FAIL|ERROR): (test_\w+) ", result.stderr, re.MULTILINE
    ):
        outcomes[name] = "FAIL"
    for match in re.finditer(r"^(test_\w+) \(", result.stderr, re.MULTILINE):
        outcomes.setdefault(match.group(1), "ok")
    return outcomes


class MutationsAreCaughtByTheRightTest(unittest.TestCase):
    def test_each_mutation_is_caught_and_only_by_the_right_test(self) -> None:
        """Control and mutation on the same copy, in that order.

        The control is not optional and not a separate test: without it, "the mutation was
        detected" and "the copy is broken" are the same observation. Measuring it on the very copy
        that then gets mutated removes the remaining gap between the two runs.
        """
        for mutation in MUTATIONS:
            names = mutation["must_fail"] + mutation["must_pass"]
            with self.subTest(mutation=mutation["name"]), self._tree() as work:
                clean = run_tests(work, mutation["module"], names)
                for name in names:
                    self.assertEqual(
                        clean.get(name),
                        "ok",
                        f"{name} does not pass on an unmutated copy, so the copy is the problem "
                        f"rather than the mutation: {clean}",
                    )

                for relative, old, new in mutation["edits"]:
                    target = work / relative
                    body = target.read_text(encoding="utf-8")
                    self.assertIn(
                        old,
                        body,
                        f"the mutation for {mutation['name']!r} no longer applies to {relative}. "
                        "The source moved and this mutation is now testing nothing — update it "
                        "rather than deleting it.",
                    )
                    target.write_text(body.replace(old, new, 1), encoding="utf-8")

                outcomes = run_tests(work, mutation["module"], names)
                for name in mutation["must_fail"]:
                    self.assertEqual(
                        outcomes.get(name),
                        "FAIL",
                        f"{mutation['name']}: {name} passed under the mutation, so it does not "
                        f"discriminate. {mutation['why']}",
                    )
                for name in mutation["must_pass"]:
                    self.assertEqual(
                        outcomes.get(name),
                        "ok",
                        f"{mutation['name']}: {name} also failed, so the mutation is simply broken "
                        "and proves nothing about which test does the work.",
                    )

    def _tree(self):
        """A throwaway copy of the tree, outside the repository."""

        class Copy:
            def __enter__(self) -> Path:
                self.tmp = tempfile.mkdtemp(prefix="mutation-")
                work = Path(self.tmp) / "repo"
                shutil.copytree(ROOT, work, ignore=IGNORED, symlinks=True)
                return work

            def __exit__(self, *exc: object) -> None:
                shutil.rmtree(self.tmp, ignore_errors=True)

        return Copy()


if __name__ == "__main__":
    unittest.main()
