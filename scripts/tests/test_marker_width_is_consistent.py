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
    ALLOW,
    FENCE,
    _outside_code_spans,
    iter_files,
    marker_categories,
    strip_markers,
)


class CountedAndRemovedAgree(unittest.TestCase):
    """What is counted as a marker is exactly what is removed, over the whole corpus.

    **The first version of this asserted nothing.** It compared `inert` against `load_bearing`, defined
    as `without <= with` and `without > with` - **exact complements, so neither "both" nor "neither"
    can occur** and the assertion could not fail. Proven rather than reasoned: with `strip_markers`
    replaced by `return line`, it still passed.

    A sibling repository found the same weakness from the other side and reached the opposite
    conclusion for its own code, correctly. Its judgement is **one predicate**, so the relation holds
    structurally and a runtime check over data cannot fire - **the guarantee belongs in a mutation.**
    Here the judgement is a **pair**, `marker_categories` and `strip_markers`, so "counted equals
    removed" rides on the relationship between two functions and **a corpus check does bite.**

    The split it drew: **axes about which part of the input is examined depend on the data, so a corpus
    check finds them. Axes about code structure do not, so a mutation must.** This file is on the first
    side only because the pair cannot be reduced to a single definition.
    """

    def _marker_lines(self):
        for path in iter_files(ROOT):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            in_fence = False
            for number, line in enumerate(lines, 1):
                if FENCE.match(line):
                    in_fence = not in_fence
                    continue
                if in_fence or not marker_categories(line):
                    continue
                yield f"{path.relative_to(ROOT)}:{number}", line

    def test_nothing_counted_survives_removal(self) -> None:
        """One direction: a marker that is counted and not removed makes the inert check lie."""
        survivors = [
            where
            for where, line in self._marker_lines()
            if marker_categories(strip_markers(line))
        ]
        self.assertEqual(
            survivors, [], "a counted marker is still present after removal"
        )

    def test_nothing_uncounted_is_removed(self) -> None:
        """The other direction, and the one the earlier width mismatch broke.

        Removal used to apply to the raw line, so it deleted code-span examples that were never
        counted. Asserted by length: the deletion accounts for exactly the markers counted, so any
        extra deletion shows up as a shortfall.
        """
        for where, line in self._marker_lines():
            removed = len(line) - len(strip_markers(line))
            spans = sum(
                len(m.group(0))
                for segment, is_code in _outside_code_spans(line)
                if not is_code
                for m in ALLOW.finditer(segment)
            )
            with self.subTest(where):
                self.assertEqual(
                    removed,
                    spans,
                    "removal deleted something that was not a counted marker",
                )

    def test_a_code_span_is_never_touched(self) -> None:
        """Stated directly as well, because the length check alone would accept a compensating edit."""
        for where, line in self._marker_lines():
            for segment, is_code in _outside_code_spans(line):
                if is_code:
                    with self.subTest(where):
                        self.assertIn(segment, strip_markers(line))

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
