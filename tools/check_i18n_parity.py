#!/usr/bin/env python3
"""Check that Tier 1 documents have the same section structure across all 8 languages.

Translations drift silently: a section gets added in Japanese and the other seven files keep
rendering an older story. Comparing heading *structure* (level + order + count) rather than text
catches that without requiring the translations themselves to be machine-comparable.

Tier 1 = root README, plus the docs/ files listed in `docs/i18n-manifest.txt`.
Tier 2 (module READMEs) is checked as ja + en only.

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


def readme_for(base: Path, lang: str) -> Path:
    """Root/module README path for a language. Japanese is the unsuffixed file."""
    return base / ("README.md" if lang == "ja" else f"README.{lang}.md")


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

    # --- Tier 1: root README, 8 languages -------------------------------------
    root_readme = readme_for(ROOT, "ja")
    if root_readme.exists():
        checked += 1
        errors += compare(
            "root README",
            root_readme,
            [(lang, readme_for(ROOT, lang)) for lang in TIER1_LANGS if lang != "ja"],
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
    for group in ("playbooks", "domains"):
        base = ROOT / group
        if not base.is_dir():
            continue
        for module in sorted(base.iterdir()):
            if not module.is_dir() or module.name.startswith("_"):
                continue
            reference = readme_for(module, "ja")
            if not reference.exists():
                errors.append(f"{group}/{module.name}: missing README.md")
                continue
            checked += 1
            errors += compare(
                f"{group}/{module.name}/README",
                reference,
                [
                    (lang, readme_for(module, lang))
                    for lang in TIER2_LANGS
                    if lang != "ja"
                ],
            )

    if errors:
        print(f"i18n parity failed ({len(errors)} issue(s)):", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1

    print(f"i18n: {checked} document group(s) in parity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
