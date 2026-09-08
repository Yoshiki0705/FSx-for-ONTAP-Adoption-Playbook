"""One definition of "is this a marker", asserted as an invariant rather than case by case.

The judgement was written three times - the audit, the budget's counter, the inert check - and a
fourth place removed markers from the raw line while the others detected them in the code-span-stripped
one. **Widths that differ by one step produce a line that fails whether the marker stays or goes**,
with each check correct on its own.

A sibling repository hit exactly that and reported both halves of the fix: extract the judgement
instead of aligning copies, because **two copies get touched one at a time** - and pin the
*relationship* rather than individual expectations, because **individual cases all passed for the
whole period the contradiction existed.**
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from audit_public_output import (
    FENCE,
    audit_line,
    file_allowances,
    iter_files,
    marker_categories,
    strip_markers,
)


class NoLineFailsBothWays(unittest.TestCase):
    """The invariant, over the whole corpus rather than over chosen examples.

    A marker cannot be **inert** (suppressing nothing, so the budget says delete it) and at the same
    time be **load-bearing** (removing it produces a finding). Each verdict alone is defensible; only
    the combination is a contradiction, and no single-check test can see it.
    """

    def test_inert_and_load_bearing_are_never_both_true(self) -> None:
        contradictions: list[str] = []
        for path in iter_files(ROOT):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            allowed = frozenset(file_allowances(lines))
            in_fence = False
            for number, line in enumerate(lines, 1):
                if FENCE.match(line):
                    in_fence = not in_fence
                    continue
                if in_fence or not marker_categories(line):
                    continue
                with_marker = len(audit_line(line, allowed))
                without = len(audit_line(strip_markers(line), allowed))
                inert = without <= with_marker
                load_bearing = without > with_marker
                if inert and load_bearing:
                    contradictions.append(f"{path.relative_to(ROOT)}:{number}")
        self.assertEqual(
            contradictions,
            [],
            "these lines fail whether the marker stays or goes, which no single check can report",
        )

    def test_detection_and_removal_agree_on_what_a_marker_is(self) -> None:
        """The pairing is the point: whatever counts as a marker is what gets removed.

        A code-span example is not a marker, so removal must leave it in place. The earlier version
        removed it, which is the width mismatch that produced the contradiction.
        """
        line = "FSxN is short `<!-- allow:naming -->` <!-- allow:pii -->"
        self.assertEqual(marker_categories(line), {"pii"})
        self.assertIn("`<!-- allow:naming -->`", strip_markers(line))
        self.assertNotIn("<!-- allow:pii -->", strip_markers(line))

    def test_a_fence_makes_both_halves_inert_together(self) -> None:
        line = "FSxN is short <!-- allow:naming -->"
        self.assertEqual(marker_categories(line, in_fence=True), set())
        self.assertEqual(strip_markers(line, in_fence=True), line)


if __name__ == "__main__":
    unittest.main()
