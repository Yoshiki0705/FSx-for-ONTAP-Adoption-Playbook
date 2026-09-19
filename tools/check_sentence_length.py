"""Report Japanese sentences above 50 visible characters; check mode fails above 80.

Only prose paragraphs and list items are inspected. Headings, tables, fenced code,
URLs, generated language switchers, and block quotes are excluded. Report mode always
returns success after printing the full migration inventory; parser or I/O errors still fail.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from editorial_markdown import normalized_visible_text, prose_blocks
from frontmatter import IGNORED_DIRS

ROOT = Path(__file__).resolve().parent.parent
SENTENCE_END = re.compile(r"(?<=[。！？!?])")
JAPANESE = re.compile(r"[ぁ-んァ-ヶ一-龠々〆ヵヶ]")
WARN = 50
VIOLATION = 80


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    length: int
    level: str


def japanese_files(root: Path):
    for path in sorted(root.rglob("*.md")):
        if any(
            part in IGNORED_DIRS or part.startswith("_")
            for part in path.relative_to(root).parts[:-1]
        ):
            continue
        rel = path.relative_to(root)
        if rel == Path("README.md") or rel.parts[:2] == ("docs", "ja"):
            yield path


def inspect(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    text = path.read_text(encoding="utf-8")
    for block in prose_blocks(text):
        visible = normalized_visible_text(block.raw, include_inline_code=True)
        for sentence in SENTENCE_END.split(visible):
            if not JAPANESE.search(sentence):
                continue
            length = len(re.sub(r"\s+", "", sentence))
            if length > WARN:
                findings.append(
                    Finding(
                        path,
                        block.line,
                        length,
                        "violation" if length > VIOLATION else "warning",
                    )
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(ROOT))
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when a sentence exceeds 80 characters",
    )
    args = parser.parse_args()
    root = Path(args.path).resolve()
    findings = [finding for path in japanese_files(root) for finding in inspect(path)]
    warnings = sum(f.level == "warning" for f in findings)
    violations = len(findings) - warnings
    for finding in findings:
        print(
            f"{finding.path.relative_to(root)}:{finding.line}: {finding.level}: "
            f"Japanese sentence has {finding.length} visible characters"
        )
    print(
        f"sentence report (not a gate): {len(findings)} finding(s); "
        f"{warnings} warning(s) over 50, {violations} violation(s) over 80"
    )
    return 1 if args.check and violations else 0


if __name__ == "__main__":
    sys.exit(main())
