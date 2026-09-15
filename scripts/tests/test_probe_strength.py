"""The probe-strength rule, as a truth table, and the constraint that one copy of it exists.

Three of the four outcomes are silent in normal use. `absent` is the loud one — someone deleted a
line — while `duplicated` and `heading-only` both leave a gate green while it stops guarding
anything. A rule that only ever returns `ok` is indistinguishable from no rule, so each verdict is
pinned rather than trusted.

`duplicated` has a specific origin worth keeping: writing prose that quotes a pinned string is the
ordinary way to create the second copy. Documenting a probe is what breaks it.

The second class asserts the rule is not written twice. It guards both directions — the strings this
repository pins elsewhere and the strings other repositories pin here — and the two were about to
get their own copies. A second copy is how they end up enforcing different rules while both
reporting success.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from probe_strength import VERDICTS, verdict

PROBE = "ホストを経由するのでコピーが 1 本発生します"

# Both directions must read the shared rule rather than carry their own.
READERS = ("check_cross_repo.py", "check_inbound_probes.py")


class TheVerdict(unittest.TestCase):
    def test_one_body_occurrence_is_accepted(self) -> None:
        self.assertEqual(verdict(PROBE, f"前置き\n\n{PROBE}\n"), "ok")

    def test_a_deleted_string_is_absent(self) -> None:
        """The citing side's gate fails, and reads as a retraction rather than someone's edit."""
        self.assertEqual(verdict(PROBE, "前置き\n\n別の文\n"), "absent")

    def test_a_second_copy_is_rejected(self) -> None:
        """The failure this rule exists for: the gate stays green while guarding nothing."""
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
        """A document showing the string as an example must not satisfy a gate by doing so."""
        text = f"```text\n{PROBE}\n```\n\n本文は別のことを言う\n"
        self.assertEqual(verdict(PROBE, text), "absent")

    def test_every_returned_verdict_is_declared(self) -> None:
        """A verdict the module does not declare cannot be handled by either caller."""
        seen = {
            verdict(PROBE, f"{PROBE}\n"),
            verdict(PROBE, "別の文\n"),
            verdict(PROBE, f"{PROBE}\n{PROBE}\n"),
            verdict(PROBE, f"## {PROBE}\n"),
        }
        self.assertEqual(seen, set(VERDICTS))


class EveryVerdictCanBeReported(unittest.TestCase):
    def test_the_inbound_check_has_wording_for_each_failure(self) -> None:
        """Wording is per-direction, but a missing entry is a KeyError at the moment the gate would
        otherwise have reported a real defect."""
        from check_inbound_probes import EXPLANATION

        missing = [
            name for name in VERDICTS if name != "ok" and name not in EXPLANATION
        ]
        self.assertEqual(missing, [], f"no message for these verdicts: {missing}")


class OneCopyOfTheRule(unittest.TestCase):
    def test_both_directions_import_the_shared_rule(self) -> None:
        for name in READERS:
            with self.subTest(name):
                source = (ROOT / "tools" / name).read_text(encoding="utf-8")
                self.assertRegex(
                    source,
                    r"from probe_strength import [^\n]*\bverdict\b",
                    f"{name} must read the shared verdict rather than carry its own",
                )

    def test_neither_direction_defines_its_own_verdict(self) -> None:
        """The failure mode: two copies, both reporting success, enforcing different rules."""
        for name in READERS:
            with self.subTest(name):
                source = (ROOT / "tools" / name).read_text(encoding="utf-8")
                self.assertNotRegex(
                    source,
                    r"^def verdict\(",
                    f"{name} defines a second copy of the rule",
                )

    def test_the_shared_rule_is_where_it_is_claimed_to_be(self) -> None:
        """The prose points readers at this path; a move would leave that pointing nowhere."""
        self.assertTrue((ROOT / "tools" / "probe_strength.py").exists())
        index = (ROOT / "docs" / "ja" / "reference" / "cross-repo-index.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("tools/probe_strength.py", index)

    def test_the_definition_is_not_restated_in_prose(self) -> None:
        """Enumerating the verdicts in a document is the drift this repository has already had:
        an issue body listing probe strings went on describing a gate that had changed."""
        index = (ROOT / "docs" / "ja" / "reference" / "cross-repo-index.md").read_text(
            encoding="utf-8"
        )
        restated = [name for name in VERDICTS if re.search(rf"`{name}`", index)]
        self.assertEqual(
            restated,
            [],
            "the verdict names are quoted in the citation index, which is a second copy of the "
            f"rule that nothing compares: {restated}",
        )


if __name__ == "__main__":
    unittest.main()
