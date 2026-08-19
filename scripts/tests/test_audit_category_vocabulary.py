"""`CATEGORIES` and the `allow:` pattern must list the same categories.

`audit_public_output.py` holds the category vocabulary twice: as a tuple, and as alternatives inside
the regex that parses a line's `<!-- allow:... -->` marker. The tuple is the authority. Only one
direction was checked - the file-level `audit-file-allow` marker rejects an unknown category - and the
line-level marker accepted whatever the regex matched.

Demonstrated rather than assumed. Renaming the category in the tuple and in the reporting side while
leaving the regex alone leaves `allow:role-label` parsing successfully, joining the allowed set, and
matching no finding, so an author who believed they had suppressed a finding still sees it reported.

The harm is not the visible failure. It is that the marker is a claim: someone read the finding,
decided it was acceptable, and wrote that decision down. A dead marker discards the decision, and the
next person meets a CI failure with no record of why it was once allowed.

A sibling repository found the same pair in its own copy of this file and kept the duplication rather
than building the regex from the tuple at import time - a regex is not a list, and assembling it
elsewhere hides it from the place a reader looks for it. Same choice here, with the divergence made
an error instead.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from audit_public_output import ALLOW, CATEGORIES

# `all` opts a line out of every category, so it is expected in the pattern and not in the tuple.
WILDCARD = "all"


def alternatives_in(pattern: re.Pattern[str]) -> set[str]:
    """Category names the `allow:` pattern accepts, read from the pattern itself."""
    group = re.search(r"allow:\(([^)]+)\)", pattern.pattern)
    assert group, (
        f"the allow pattern no longer has a single alternation group: {pattern.pattern}"
    )
    return set(group.group(1).split("|"))


class AuditCategoryVocabulary(unittest.TestCase):
    def test_every_category_can_be_allowed_on_a_line(self) -> None:
        """A category the pattern does not accept has no line-level suppression at all."""
        missing = sorted(set(CATEGORIES) - alternatives_in(ALLOW))
        self.assertFalse(
            missing,
            f"CATEGORIES lists {missing}, which the allow pattern does not accept, so "
            f"<!-- allow:{missing[0] if missing else ''} --> would be ignored",
        )

    def test_the_pattern_has_no_orphan_alternatives(self) -> None:
        """An alternative matching no category is a marker that suppresses nothing.

        This is the direction that was unchecked. It survives a rename: the tuple and the reporting
        side move together, the regex stays behind, and the stale name keeps parsing.
        """
        orphans = sorted(alternatives_in(ALLOW) - set(CATEGORIES) - {WILDCARD})
        self.assertFalse(
            orphans,
            f"the allow pattern accepts {orphans}, which match no category; "
            f"<!-- allow:{orphans[0] if orphans else ''} --> would parse and suppress nothing",
        )

    def test_the_wildcard_is_still_available(self) -> None:
        """`allow:all` is documented in the module docstring, so it has to keep working."""
        self.assertIn(WILDCARD, alternatives_in(ALLOW))
        self.assertNotIn(
            WILDCARD,
            CATEGORIES,
            "'all' is a wildcard, not a category; listing it in CATEGORIES would let "
            "audit-file-allow: all read as a category name",
        )


if __name__ == "__main__":
    unittest.main()
