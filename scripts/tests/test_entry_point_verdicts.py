"""The entry-point gate, as a truth table.

An absent entry point is invisible: a missing decision tree is a missing file, this is nothing at
all. That is how twelve of fourteen modules went without one while the criterion sat in the template,
so the verdict is pinned rather than trusted.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from check_entry_points import ACCEPTED_JA, entry_verdict


class TheVerdict(unittest.TestCase):
    def test_an_entry_heading_is_accepted(self) -> None:
        for heading in ACCEPTED_JA:
            with self.subTest(heading):
                self.assertEqual(entry_verdict(f"## {heading}\n", "ja"), "ok")

    def test_a_table_of_contents_is_not_an_entry_point(self) -> None:
        """The template's own words: the entry point is not a table of contents."""
        self.assertEqual(
            entry_verdict("## このモジュールが扱う問い\n", "ja"), "missing"
        )

    def test_a_heading_inside_a_fence_is_an_example(self) -> None:
        """A README documenting the section must not satisfy the gate by doing so."""
        text = "```markdown\n## 最初に読むもの\n```\n\n## このモジュールが扱う問い\n"
        self.assertEqual(entry_verdict(text, "ja"), "missing")

    def test_english_headings_are_judged_against_the_english_set(self) -> None:
        """An English reader arrives at the English README, so it needs its own entry point."""
        self.assertEqual(entry_verdict("## Read first\n", "en"), "ok")
        self.assertEqual(entry_verdict("## 最初に読むもの\n", "en"), "missing")


if __name__ == "__main__":
    unittest.main()
