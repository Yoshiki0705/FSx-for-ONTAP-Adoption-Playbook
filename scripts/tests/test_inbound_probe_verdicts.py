"""The inbound-probe gate, as a truth table.

Three of the four outcomes are silent in normal use. `absent` is the loud one — someone deleted a
line — while `duplicated` and `heading-only` both leave the *citing* repository's gate green while
it stops guarding anything. A gate that only ever returns `ok` is indistinguishable from no gate,
so each verdict is pinned rather than trusted.

`duplicated` has a specific origin worth keeping: writing prose that quotes a pinned string is the
ordinary way to create the second copy. Documenting a probe is what breaks it.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from check_inbound_probes import EXPLANATION, verdict

PROBE = "ホストを経由するのでコピーが 1 本発生します"


class TheVerdict(unittest.TestCase):
    def test_one_body_occurrence_is_accepted(self) -> None:
        self.assertEqual(verdict(PROBE, f"前置き\n\n{PROBE}\n"), "ok")

    def test_a_deleted_string_is_absent(self) -> None:
        """Their gate fails, and it reads as a retraction of their claim rather than our edit."""
        self.assertEqual(verdict(PROBE, "前置き\n\n別の文\n"), "absent")

    def test_a_second_copy_is_rejected(self) -> None:
        """The failure this gate exists for: their probe stays green while guarding nothing."""
        self.assertEqual(verdict(PROBE, f"{PROBE}\n\nまた: {PROBE}\n"), "duplicated")

    def test_quoting_the_string_in_prose_about_it_is_the_duplicate(self) -> None:
        """The concrete way the second copy appears — describing a probe by quoting it."""
        text = f"{PROBE}\n\n> この行は他リポジトリが pin しています: {PROBE}\n"
        self.assertEqual(verdict(PROBE, text), "duplicated")

    def test_a_heading_only_match_is_rejected(self) -> None:
        """A section keeps its title while its content is replaced by the opposite finding."""
        self.assertEqual(
            verdict(PROBE, f"## {PROBE}\n\n本文は別のことを言う\n"), "heading-only"
        )

    def test_a_heading_plus_body_is_still_a_duplicate(self) -> None:
        """One of the two copies being a heading does not rescue it — the body copy can be reworded
        while the heading keeps the gate green, which is the same failure."""
        self.assertEqual(verdict(PROBE, f"## {PROBE}\n\n{PROBE}\n"), "duplicated")

    def test_a_fenced_occurrence_does_not_count(self) -> None:
        """A document showing the string as an example must not satisfy the gate by doing so."""
        text = f"```text\n{PROBE}\n```\n\n本文は別のことを言う\n"
        self.assertEqual(verdict(PROBE, text), "absent")

    def test_every_failing_verdict_has_an_explanation(self) -> None:
        """A verdict with no message reports a number and no way to act on it."""
        for name in ("absent", "heading-only", "duplicated"):
            with self.subTest(name):
                self.assertIn(name, EXPLANATION)


if __name__ == "__main__":
    unittest.main()
