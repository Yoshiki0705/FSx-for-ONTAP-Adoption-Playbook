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
mutated there.

**The unit of copying is a trade-off, not an obvious choice.** A sibling repository copies a *single
file* and calls its `--selftest` in a subprocess, which makes it structurally impossible for a
repository fixture to leak into a verdict — and impossible to mutation-test any detector whose
selftest legitimately needs one, because the control fails first. Copying the tree, as here, keeps
every detector testable and accepts that a fixture can participate. **The control is what makes the
second choice safe**: if the copy cannot pass its own tests, no verdict is read from it. An earlier version of a different check in this repository wrote to the real index
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
        # From a comment that says "Do not replace them with `\b`". A sibling repository named the
        # general technique: **a comment forbidding something is a mutation candidate**, and if the
        # mutation survives, the comment was an unenforced claim rather than a rule.
        "name": "ASCII boundaries replaced by the word boundary they replaced",
        "why": (
            "The original defect, restored. `\\b` is defined over `\\w`, which matches CJK, so the "
            "Japanese-adjacent form stops matching while every ASCII case keeps working."
        ),
        "module": "scripts.tests.test_cjk_word_boundaries",
        "edits": [
            (
                "tools/audit_public_output.py",
                'ASCII_LEFT = r"(?<![A-Za-z0-9_])"',
                'ASCII_LEFT = r"\\b"',
            ),
            (
                "tools/audit_public_output.py",
                'ASCII_RIGHT = r"(?![A-Za-z0-9_])"',
                'ASCII_RIGHT = r"\\b"',
            ),
        ],
        "must_fail": ["test_japanese_adjacent_forms_are_reported"],
        "must_pass": [
            "test_spaced_ascii_forms_are_still_reported",
            "test_embedded_forms_are_not_reported",
        ],
    },
    {
        "name": "pinned-ref exemption removed from the self-path check",
        "why": (
            "A commit-pinned link points at a revision this working tree need not hold, so "
            "resolving it reports a defect that does not exist. A gate that fires on a correct "
            "link gets an allow marker rather than a fix."
        ),
        "module": "scripts.tests.test_doc_gates",
        "edits": [
            (
                "tools/check_cross_repo.py",
                '            if match.group("ref") != "main":\n                continue',
                "            if False:\n                continue",
            ),
        ],
        "must_fail": ["test_self_link_pinned_to_a_commit_is_accepted"],
        "must_pass": ["test_self_link_to_a_missing_path_is_rejected"],
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
        # The mirror-image mistake a sibling repository made first and reported. Testing for an
        # unchanged report finds only markers that suppress nothing, and misses one that makes the
        # checker report something that is not there.
        "name": "suppression predicate accepts any change",
        "why": (
            "'!=' calls a marker justified whenever the count moved, including when the marker adds "
            "a finding that does not exist. A rule written to hunt quiet failures will not look for "
            "loud ones, so this is the shape that survives review."
        ),
        "module": "scripts.tests.test_allow_budget_verdicts",
        "edits": [
            (
                "tools/check_allow_budget.py",
                'return "justified" if findings_without > findings_with else "inert"',
                'return "justified" if findings_without != findings_with else "inert"',
            ),
        ],
        "must_fail": ["test_a_marker_that_adds_a_finding_is_not_justified"],
        "must_pass": [
            "test_a_marker_that_hides_a_finding_is_justified",
            "test_a_marker_that_hides_nothing_is_inert",
        ],
    },
    {
        # The hole this closed: a line mentioning the marker in prose exempted itself.
        "name": "allow marker recognised as bare text",
        "why": (
            "Dropping the HTML comment wrapper is the shortest way to make the regex simpler, and it "
            "restores the hole where any line mentioning allow:naming - inside backticks included - "
            "silenced the detector on that line."
        ),
        "module": "scripts.tests.test_allow_budget_verdicts",
        "edits": [
            (
                "tools/audit_public_output.py",
                'r"<!--[^>]*?allow:(naming|neutrality|pii|role-label|support-referral|all)[^>]*?-->"',
                'r"allow:(naming|neutrality|pii|role-label|support-referral|all)"',
            ),
        ],
        "must_fail": ["test_a_bare_prose_mention_does_not_suppress"],
        "must_pass": ["test_a_real_marker_suppresses"],
    },
    {
        "name": "allow budget accepts a grown set",
        "why": (
            "Returning 'ok' when a marker appears is the state before this guard existed. Adding an "
            "allow marker looks identical to fixing the problem it silences, because the audit "
            "passes either way - so nothing surfaces until someone reads the file."
        ),
        "module": "scripts.tests.test_allow_budget_verdicts",
        "edits": [
            (
                "tools/check_allow_budget.py",
                '    if actual > recorded:\n        return "added"',
                '    if False:\n        return "added"',
            ),
        ],
        "must_fail": ["test_one_more_than_recorded_is_added"],
        "must_pass": ["test_fewer_than_recorded_is_stale", "test_equal_counts_are_ok"],
    },
    {
        # The quieter half. A surplus in the baseline breaks nothing today, which is exactly why it
        # is worth a mutation: it is headroom that lets a marker return without a word.
        "name": "allow budget stops reporting surplus",
        "why": (
            "Dropping the 'stale' verdict is the plausible edit, since a budget recording more than "
            "exists fails nothing at the time. The surplus is headroom, so the marker it once "
            "counted can come back silently."
        ),
        "module": "scripts.tests.test_allow_budget_verdicts",
        "edits": [
            (
                "tools/check_allow_budget.py",
                'FAILING = ("added", "stale")',
                'FAILING = ("added",)',
            ),
        ],
        "must_fail": ["test_stale_fails_the_check"],
        "must_pass": [
            "test_added_fails_the_check",
            "test_fewer_than_recorded_is_stale",
        ],
    },
    {
        # Only mutatable because the decision was extracted from `main`. While it lived there, the
        # only possible tests asserted that the source *contained* certain strings — which a
        # mutation kills trivially without saying anything about behaviour. A sibling repository
        # named the axis: **a prohibition is enforceable only if the code enforcing it can be
        # reached by a test**, and the fix is extracting a function, not moving a comment.
        "name": "stale-head verdict dropped",
        "why": (
            "Returning 'answer' for a mismatch is what the command did before this guard existed. "
            "After a push the API serves the previous head, so every verdict keys on a SHA that is "
            "correct and stale — and a passing old SHA would clear a merge never examined."
        ),
        "module": "scripts.tests.test_pr_verify_head_match",
        "edits": [
            (
                "scripts/verify_pr_checks.py",
                '    if local and local != head:\n        return "stale"',
                '    if False:\n        return "stale"',
            ),
        ],
        "must_fail": ["test_the_same_branch_at_a_different_commit_is_stale"],
        "must_pass": [
            "test_a_different_branch_is_not_compared",
            "test_the_same_branch_at_the_same_commit_answers",
        ],
    },
    {
        "name": "head comparison unscoped from the branch",
        "why": (
            "Comparing unconditionally refuses every run from main and against anyone else's pull "
            "request. A check that refuses ordinary use gets worked around, which is the failure "
            "this command exists to prevent."
        ),
        "module": "scripts.tests.test_pr_verify_head_match",
        "edits": [
            (
                "scripts/verify_pr_checks.py",
                '    if not branch or branch != pr_branch:\n        return "answer"',
                '    if not branch:\n        return "answer"',
            ),
        ],
        "must_fail": ["test_a_different_branch_is_not_compared"],
        "must_pass": ["test_the_same_branch_at_a_different_commit_is_stale"],
    },
    {
        "name": "own-org path check removed",
        "why": (
            "'A tree link is navigation, not a citation' is true and says nothing about whether "
            "the path exists. Reading it as coverage is how twenty-one links ended up verified by "
            "nothing."
        ),
        "module": "scripts.tests.test_doc_gates",
        "edits": [
            (
                "tools/check_cross_repo.py",
                "        problems += check_own_org_paths(rows)",
                "        pass  # mutation: own-org path check removed",
            ),
        ],
        "must_fail": ["test_a_dead_path_in_a_sibling_repository_is_rejected"],
        "must_pass": ["test_self_link_pinned_to_a_commit_is_accepted"],
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
    for match in re.finditer(
        r"^(test_\w+) \([^)]*\)(?:.*?)\.\.\. (skipped[^\n]*)$",
        result.stderr,
        re.MULTILINE | re.DOTALL,
    ):
        outcomes[match.group(1)] = match.group(2)
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
                # A network-dependent test skips itself without a token, and a skipped control
                # cannot support any verdict: under the mutation it would skip too, and "not run"
                # would read as "not detected". So the mutation is skipped rather than assumed —
                # the alternative is a green run that verified nothing, which is the failure this
                # whole file exists to prevent.
                skipped = [
                    n for n in names if str(clean.get(n, "")).startswith("skipped")
                ]
                if skipped:
                    self.skipTest(
                        f"{mutation['name']}: {skipped} skipped on the clean copy "
                        "(no network or no GITHUB_TOKEN), so this mutation cannot be verified here"
                    )
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
                    # Exactly one, not "at least one". The replace below is bounded to the first
                    # occurrence, so a second copy of the same source string leaves half the
                    # detector intact — and **that direction is quieter than survival**. A
                    # partially broken detector still fails its test, the mutation reads as
                    # `killed`, and the guard looks protected while one site is unguarded.
                    #
                    # Zero was already caught. Two was not. Reported by a sibling repository,
                    # which had the same bounded replace and the same missing half of the check.
                    count = body.count(old)
                    self.assertEqual(
                        count,
                        1,
                        f"the mutation for {mutation['name']!r} matches {count} time(s) in "
                        f"{relative}, and exactly one is required. Zero means the source moved and "
                        "this mutation now tests nothing; more than one means only the first site "
                        "is broken, which still shows as killed while leaving a site unguarded. "
                        "Update the mutation rather than deleting it.",
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
