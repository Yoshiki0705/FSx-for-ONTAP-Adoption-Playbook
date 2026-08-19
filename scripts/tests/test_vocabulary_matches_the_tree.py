"""The declared vocabularies and the directory tree must agree.

`LIFECYCLE`, `DOMAINS` and the language lists restate what the directory layout already shows:
`docs/ja/playbooks/01-assess` and `lifecycle: assess` are the same fact written twice, and nothing
noticed if they stopped matching. A sibling repository found the same shape in its own tooling - a
repository name held as a constant that git already knew - and removed the constant.

Deriving is the wrong fix here, and the difference is worth stating. Their constant had an
authoritative source to derive from. These do not: the vocabulary is the authority and the tree must
conform to it. Reading the vocabulary off disk would invert that, and a directory created with a typo
would silently widen what the validator accepts instead of being rejected by it.

So the duplication stays and the divergence becomes an error. Both directions are checked, because
each catches a different mistake:

  * declared but absent - a value nothing can ever use, usually left behind by a rename
  * present but undeclared - a directory whose notes the validator would reject, or worse, a typo

`docs/<lang>/` is the language model, so the language lists are checked against it too. The Japanese
hub is the repository-root README.md by design, which is why `docs/ja/README.md` does not exist and
that absence is not evidence of a missing language.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from check_i18n_parity import TIER1_LANGS  # noqa: E402
from validate_frontmatter import DOMAINS, LANGS, LIFECYCLE  # noqa: E402

# Directories under docs/ that are not languages.
NON_LANGUAGE = {"_assets", "agent"}


def subdirectories(path: Path) -> set[str]:
    return {
        child.name
        for child in path.iterdir()
        if child.is_dir() and not child.name.startswith("_")
    }


class VocabularyMatchesTheTree(unittest.TestCase):
    def assert_same(self, label: str, declared: set[str], on_disk: set[str]) -> None:
        missing = sorted(declared - on_disk)
        extra = sorted(on_disk - declared)
        self.assertFalse(
            missing,
            f"{label} declares {missing} with no directory - a value nothing can use",
        )
        self.assertFalse(
            extra,
            f"{label}: {extra} exist on disk but are not declared, so notes there would be "
            f"rejected; add them deliberately or fix the directory name",
        )

    def test_lifecycle_matches_the_playbook_modules(self) -> None:
        modules = {
            name.split("-", 1)[1] for name in subdirectories(ROOT / "docs/ja/playbooks")
        }
        self.assert_same("LIFECYCLE", LIFECYCLE, modules)

    def test_domains_match_the_domain_modules(self) -> None:
        self.assert_same("DOMAINS", DOMAINS, subdirectories(ROOT / "docs/ja/domains"))

    def test_language_lists_match_the_language_directories(self) -> None:
        languages = subdirectories(ROOT / "docs") - NON_LANGUAGE
        self.assert_same("LANGS", LANGS, languages)
        self.assert_same("TIER1_LANGS", set(TIER1_LANGS), languages)

    def test_the_two_language_lists_agree_with_each_other(self) -> None:
        """Two tools carrying the same list is how one of them falls behind."""
        self.assertEqual(
            LANGS,
            set(TIER1_LANGS),
            "validate_frontmatter.LANGS and check_i18n_parity.TIER1_LANGS have diverged",
        )


if __name__ == "__main__":
    unittest.main()
