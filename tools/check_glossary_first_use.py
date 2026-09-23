"""Report required glossary terms whose first eligible prose use is not linked.

The scan covers prose paragraphs and list items. It excludes headings, tables, fenced
code, inline code, URLs, generated language switchers, and block quotes. Report mode is
nonblocking; --check fails when findings exist.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from editorial_markdown import IMAGE, INLINE_CODE, LINK, URL, prose_blocks
from frontmatter import IGNORED_DIRS

ROOT = Path(__file__).resolve().parent.parent
GLOSSARY_TARGET = re.compile(r"(?:^|/)reference/glossary/(?:README\.md)?(?:#|$)")
ASCII_LEFT = r"(?<![A-Za-z0-9_])"
ASCII_RIGHT = r"(?![A-Za-z0-9_])"
TERM_ALIASES = {
    "S3 Access Point": ("S3 Access Point", "S3 Access Points"),
    "throughput capacity": ("throughput capacity", "スループット容量"),
    "capacity pool": ("capacity pool", "容量プール"),
    "security style": ("security style", "セキュリティスタイル"),
    "SnapMirror": ("SnapMirror",),
    "FlexClone": ("FlexClone",),
    "FlexCache": ("FlexCache",),
    "FlexVol": ("FlexVol",),
    "NVRAM": ("NVRAM",),
    "inode": ("inode",),
    "SVM": ("SVM",),
    "LIF": ("LIF",),
}
TERM_NAMES = tuple(TERM_ALIASES)
TERM_PATTERNS = {
    term: re.compile(
        ASCII_LEFT
        + r"(?:"
        + "|".join(re.escape(alias) for alias in aliases)
        + r")"
        + ASCII_RIGHT,
        re.IGNORECASE,
    )
    for term, aliases in TERM_ALIASES.items()
}


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    term: str


def markdown_files(root: Path):
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part in IGNORED_DIRS or part.startswith("_") for part in rel.parts[:-1]):
            continue
        if "reference/glossary" not in rel.as_posix():
            yield path


def _eligible(raw: str) -> str:
    text = IMAGE.sub(lambda match: " " * len(match.group()), raw)
    text = INLINE_CODE.sub(lambda match: " " * len(match.group()), text)
    return URL.sub(lambda match: " " * len(match.group()), text)


def _linked_ranges(raw: str) -> list[tuple[int, int]]:
    return [
        (match.start(1), match.end(1))
        for match in LINK.finditer(raw)
        if GLOSSARY_TARGET.search(match.group(2).split()[0])
    ]


def inspect(path: Path) -> list[Finding]:
    seen: set[str] = set()
    findings: list[Finding] = []
    for block in prose_blocks(path.read_text(encoding="utf-8")):
        text = _eligible(block.raw)
        ranges = _linked_ranges(text)
        occurrences: list[tuple[int, str, re.Match[str]]] = []
        for term, pattern in TERM_PATTERNS.items():
            if term in seen:
                continue
            match = pattern.search(text)
            if match:
                occurrences.append((match.start(), term, match))
        for _, term, match in sorted(occurrences):
            seen.add(term)
            if not any(
                start <= match.start() and match.end() <= end for start, end in ranges
            ):
                findings.append(Finding(path, block.line, term))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(ROOT))
    parser.add_argument(
        "--check", action="store_true", help="fail when a first use is not linked"
    )
    args = parser.parse_args()
    root = Path(args.path).resolve()
    findings = [finding for path in markdown_files(root) for finding in inspect(path)]
    for finding in findings:
        print(
            f"{finding.path.relative_to(root)}:{finding.line}: first use of {finding.term!r} is not linked to the glossary"
        )
    print(f"glossary report (not a gate): {len(findings)} unlinked first use(s)")
    return 1 if args.check and findings else 0


if __name__ == "__main__":
    sys.exit(main())
