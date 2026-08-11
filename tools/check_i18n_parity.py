#!/usr/bin/env python3
"""Check that Tier 1 documents have the same section structure across all 8 languages.

Translations drift silently: a section gets added in Japanese and the other seven files keep
rendering an older story. Comparing heading *structure* (level + order + count) rather than text
catches that without requiring the translations themselves to be machine-comparable.

Tier 1 = the language hubs, plus the docs/ files listed in `docs/i18n-manifest.txt`.
Tier 2 (module READMEs under docs/<lang>/) is checked as ja + en only.
Tier 3 (notes, checklists) is *optional* in English - but any file that exists in both languages is
compared, because an English translation that silently stops matching its Japanese counterpart is
worse than no translation at all: the reader cannot tell they are being given an older story. So the
rule is not "translate everything", it is "a translation that exists must keep up".

A document's language is its directory, not a filename suffix. The one exception is the Japanese
hub: it is the repository-root README.md, because that is what GitHub renders on the landing page,
so `docs/ja/README.md` deliberately does not exist.

The manifest exists so that a new guide can land in Japanese and English first and be promoted to
all eight languages deliberately. Without it, either every new doc blocks the commit gate until
eight translations exist, or the gate has to be switched off - and a gate that is switched off
stops catching the drift it was built for.

Run:  python3 tools/check_i18n_parity.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs" / "i18n-manifest.txt"

TIER1_LANGS = ["ja", "en", "ko", "zh-CN", "zh-TW", "fr", "de", "es"]
TIER2_LANGS = ["ja", "en"]

ATX = re.compile(r"^(#{1,6})\s+\S")
SUMMARY = re.compile(r"<summary>", re.IGNORECASE)
FENCE = re.compile(r"^\s*(?:```|~~~)")


def structure(path: Path) -> list[str]:
    """Return a structural fingerprint: heading levels and <summary> markers, in order.

    Heading *text* is intentionally ignored - it is translated. Fenced code blocks are skipped so
    that comments starting with '#' inside a shell snippet are not mistaken for headings.
    """
    fingerprint: list[str] = []
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = ATX.match(line)
        if match:
            fingerprint.append(f"h{len(match.group(1))}")
        elif SUMMARY.search(line):
            fingerprint.append("details")
    return fingerprint


def read_manifest() -> list[tuple[str, list[str]]]:
    """Parse docs/i18n-manifest.txt into [(filename, [langs])].

    Format, one entry per line:  <filename>[: lang,lang,...]
    Omitting the language list means all eight Tier 1 languages are required.
    """
    if not MANIFEST.exists():
        return []
    entries: list[tuple[str, list[str]]] = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        name, sep, raw_langs = stripped.partition(":")
        name = name.strip()
        if sep and raw_langs.strip():
            langs = [lang.strip() for lang in raw_langs.split(",") if lang.strip()]
            unknown = sorted(set(langs) - set(TIER1_LANGS))
            if unknown:
                raise SystemExit(
                    f"i18n-manifest.txt: unknown language(s) {unknown} for {name}"
                )
        else:
            langs = list(TIER1_LANGS)
        entries.append((name, langs))
    return entries


def hub_for(lang: str) -> Path:
    """The top-level hub for a language. Japanese is the repository-root README."""
    if lang == "ja":
        return ROOT / "README.md"
    return ROOT / "docs" / lang / "README.md"


def module_readme(lang: str, group: str, module: str) -> Path:
    """Module README for a language, e.g. docs/en/domains/cost/README.md."""
    return ROOT / "docs" / lang / group / module / "README.md"


def compare(label: str, reference: Path, others: list[tuple[str, Path]]) -> list[str]:
    errors: list[str] = []
    expected = structure(reference)
    for lang, path in others:
        if not path.exists():
            errors.append(
                f"{label}: missing {lang} translation ({path.relative_to(ROOT)})"
            )
            continue
        actual = structure(path)
        if actual == expected:
            continue
        if len(actual) != len(expected):
            errors.append(
                f"{label}: {lang} has {len(actual)} section marker(s), "
                f"reference has {len(expected)} ({path.relative_to(ROOT)})"
            )
            continue
        for index, (want, got) in enumerate(zip(expected, actual)):
            if want != got:
                errors.append(
                    f"{label}: {lang} section #{index + 1} is '{got}', "
                    f"reference has '{want}' ({path.relative_to(ROOT)})"
                )
                break
    return errors


def main() -> int:
    errors: list[str] = []
    checked = 0

    # --- Tier 1: language hubs, 8 languages -----------------------------------
    ja_hub = hub_for("ja")
    if ja_hub.exists():
        checked += 1
        errors += compare(
            "hub README",
            ja_hub,
            [(lang, hub_for(lang)) for lang in TIER1_LANGS if lang != "ja"],
        )
    else:
        errors.append("root README.md not found")

    # --- Tier 1: docs listed in the manifest ----------------------------------
    for name, langs in read_manifest():
        reference = ROOT / "docs" / "ja" / name
        if not reference.exists():
            errors.append(
                f"docs/*/{name}: listed in i18n-manifest.txt but docs/ja/{name} is missing"
            )
            continue
        checked += 1
        others = [(lang, ROOT / "docs" / lang / name) for lang in langs if lang != "ja"]
        errors += compare(f"docs/*/{name}", reference, others)

    # --- Tier 2: module READMEs, ja + en --------------------------------------
    # Modules are discovered from the Japanese tree because Japanese is the reference language and
    # the only complete one. A module that exists only in a translation is itself a defect, and
    # surfaces here as a directory nobody compares against.
    for group in ("playbooks", "domains"):
        base = ROOT / "docs" / "ja" / group
        if not base.is_dir():
            continue
        for module in sorted(base.iterdir()):
            if not module.is_dir() or module.name.startswith("_"):
                continue
            reference = module_readme("ja", group, module.name)
            if not reference.exists():
                errors.append(f"docs/ja/{group}/{module.name}: missing README.md")
                continue
            checked += 1
            errors += compare(
                f"{group}/{module.name}/README",
                reference,
                [
                    (lang, module_readme(lang, group, module.name))
                    for lang in TIER2_LANGS
                    if lang != "ja"
                ],
            )

    # --- Tier 3: any document that happens to exist in both ja and en ---------
    # Discovered from the English tree rather than declared, because English is opt-in here. A file
    # only enters this check by being translated, so the check cannot block a Japanese-only note -
    # it can only stop an existing translation from drifting. Tier 1 and 2 paths are skipped since
    # they are already compared above, against a wider language set.
    for path in sorted((ROOT / "docs" / "en").rglob("*.md")):
        rel = path.relative_to(ROOT / "docs" / "en")
        if any(part.startswith("_") for part in rel.parts):
            continue
        if rel.name == "README.md":
            continue  # hub and module READMEs: covered by Tier 1 / Tier 2
        if str(rel).replace("\\", "/") in {name for name, _ in read_manifest()}:
            continue  # manifest entries: covered by Tier 1
        reference = ROOT / "docs" / "ja" / rel
        if not reference.exists():
            errors.append(
                f"docs/en/{rel}: no Japanese counterpart at docs/ja/{rel}; "
                f"Japanese is the reference language, so a translation cannot lead it"
            )
            continue
        checked += 1
        errors += compare(f"docs/*/{rel}", reference, [("en", path)])

    if errors:
        print(f"i18n parity failed ({len(errors)} issue(s)):", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1

    print(f"i18n: {checked} document group(s) in parity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
