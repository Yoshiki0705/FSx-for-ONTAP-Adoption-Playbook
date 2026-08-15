"""Every Makefile target must be declared .PHONY.

Why this exists
---------------
`make` treats a target name as a filename. When a target shares its name with a
directory that exists — and this repository has `docs/`, `scripts/`, `tools/` —
make compares timestamps, finds nothing to do, prints "up to date", and never
runs the recipe. The target reports success without executing anything.

That failure is silent in the worst way: the gate appears in the Makefile, CI
appears to call it, the output says nothing is wrong. In a sibling project a
`security` target sat in exactly this state; its first real execution reported
nine findings at Medium or above, two of which were live SQL injection paths.

Declaring every target .PHONY costs one line and removes the whole class. This
test exists so a target added later cannot reintroduce it.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"

# `target:` at the start of a line, excluding `VAR := value` and `VAR ?= value`.
TARGET_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*)\s*:(?!=)", re.MULTILINE)
PHONY_RE = re.compile(r"^\.PHONY:((?:[^\n\\]|\\\n)*)", re.MULTILINE)


def _read() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


def declared_targets(source: str) -> set[str]:
    return {m.group(1) for m in TARGET_RE.finditer(source) if m.group(1) != ".PHONY"}


def phony_targets(source: str) -> set[str]:
    names: set[str] = set()
    for match in PHONY_RE.finditer(source):
        names.update(match.group(1).replace("\\\n", " ").split())
    return names


class MakefilePhony(unittest.TestCase):
    def test_every_target_is_phony(self) -> None:
        source = _read()
        missing = sorted(declared_targets(source) - phony_targets(source))
        self.assertEqual(
            missing,
            [],
            "these Makefile targets are not declared .PHONY, so make will report "
            f"'up to date' and skip the recipe if a path of the same name appears: {missing}",
        )

    def test_no_phony_entry_without_a_target(self) -> None:
        """A stale .PHONY name usually means a target was renamed and the
        declaration was left behind, which is how the next rename goes unnoticed."""
        source = _read()
        orphans = sorted(phony_targets(source) - declared_targets(source))
        self.assertEqual(orphans, [], f"declared .PHONY but no such target: {orphans}")

    def test_detects_an_undeclared_target(self) -> None:
        """The check must fail on a broken Makefile, not just pass on a good one.

        Verifying the parser against a synthetic break is the point: a regex that
        silently stopped matching would leave both tests above passing forever.
        """
        broken = ".PHONY: help\n\nhelp:\n\t@echo hi\n\ndocs:\n\t@echo built\n"
        self.assertEqual(
            sorted(declared_targets(broken) - phony_targets(broken)), ["docs"]
        )


if __name__ == "__main__":
    unittest.main()
