"""Report notes and checklists that do not follow their future editorial templates.

This is a migration report. It does not rewrite existing documents or affect required gates.
Use --check only for fixtures or after a future migration is complete.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from editorial_markdown import normalized_visible_text, strip_fenced_blocks
from frontmatter import IGNORED_DIRS, split

ROOT = Path(__file__).resolve().parent.parent
H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)
H2 = re.compile(r"^##\s+(.+)$", re.MULTILINE)
ANY_HEADING = re.compile(r"^#{1,3}\s+", re.MULTILINE)
BULLET = re.compile(r"^\s*[-*+]\s+\S", re.MULTILINE)
LINK = re.compile(r"(?<!!)\[[^]]+\]\([^)]+\)")
COMMAND_FENCE = re.compile(
    r"^\s*(?P<marker>`{3,}|~{3,})[ \t]*(?P<info>[^\s`~]+)?[ \t]*$"
)
COMMAND_LANGUAGES = frozenset({"bash", "sh", "shell", "console", "powershell", "pwsh"})
EXPECTED_OUTPUT_HEADING = re.compile(
    r"^###\s+(?:期待結果|Expected output)\s*$", re.MULTILINE
)

NOTE_HEADINGS = {
    "learn": {"このノートで学べること", "What you will learn"},
    "non_goals": {"このノートが答えないこと", "What this note does not answer"},
    "prerequisites": {"前提レベル", "Prerequisite level"},
    "body": {"本文", "Body"},
    "verification": {"自環境での確認手順", "Verify it in your environment"},
    "read_next": {"Read next"},
}
CHECKLIST_HEADINGS = {
    "purpose": {"目的", "Purpose"},
    "applicability": {"適用条件", "Applicability"},
    "verification": {"検証手順", "Verification procedure"},
    "read_next": {"Read next"},
}
EXPECTED_OUTPUT = ("期待結果", "Expected output")
PREREQUISITE_LEVELS = {"basic", "intermediate", "advanced"}
JAPANESE = re.compile(r"[ぁ-んァ-ヶ一-龠]")


@dataclass(frozen=True)
class Finding:
    path: Path
    message: str


def documents(root: Path):
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part in IGNORED_DIRS or part.startswith("_") for part in rel.parts[:-1]):
            continue
        kind = (
            "note"
            if "notes" in rel.parts
            else "checklist"
            if "checklists" in rel.parts
            else None
        )
        if kind:
            yield path, kind


def _sections(body: str, raw_body: str) -> tuple[list[str], dict[str, str]]:
    matches = list(H2.finditer(body))
    headings = [match.group(1).strip() for match in matches]
    raw_lines = raw_body.splitlines()
    sections: dict[str, str] = {}
    for index, (heading, match) in enumerate(zip(headings, matches, strict=True)):
        start_line = body.count("\n", 0, match.end()) + 1
        end_line = (
            body.count("\n", 0, matches[index + 1].start())
            if index + 1 < len(matches)
            else len(raw_lines)
        )
        sections.setdefault(heading, "\n".join(raw_lines[start_line:end_line]))
    return headings, sections


def _has_nonempty_command_fence(section: str) -> bool:
    marker: str | None = None
    command_fence = False
    content: list[str] = []
    for line in section.splitlines():
        if marker is None:
            opening = COMMAND_FENCE.match(line)
            if opening:
                marker = opening.group("marker")
                info = (opening.group("info") or "").lower()
                command_fence = info in COMMAND_LANGUAGES
                content = []
            continue
        stripped = line.strip()
        if stripped and set(stripped) == {marker[0]} and len(stripped) >= len(marker):
            if command_fence and any(value.strip() for value in content):
                return True
            marker = None
            command_fence = False
            content = []
            continue
        content.append(line)
    return False


def _has_nonempty_expected_output(section: str) -> bool:
    heading = EXPECTED_OUTPUT_HEADING.search(section)
    if not heading:
        return False
    content = section[heading.end() :]
    following_heading = ANY_HEADING.search(content)
    if following_heading:
        content = content[: following_heading.start()]
    return any(
        line.strip() and not COMMAND_FENCE.match(line) for line in content.splitlines()
    )


def _named_heading(headings: list[str], accepted: set[str]) -> str | None:
    return next((heading for heading in headings if heading in accepted), None)


def inspect(path: Path, kind: str) -> list[Finding]:
    _, raw_body = split(path.read_text(encoding="utf-8"))
    body = strip_fenced_blocks(raw_body)
    errors: list[str] = []
    first_content = next((line for line in raw_body.splitlines() if line.strip()), "")
    if first_content and not re.match(r"^#\s+", first_content):
        errors.append("H1 must be the first non-empty content")
    h1 = H1.search(body)
    if not h1:
        errors.append("missing H1")
    elif kind == "note" and not h1.group(1).rstrip().endswith(("?", "？", "か")):
        errors.append("note H1 is not a question")
    headings, sections = _sections(body, raw_body)
    first_h2 = H2.search(body)
    if kind == "note":
        summary_lines = [
            line
            for line in body[
                h1.end() if h1 else 0 : first_h2.start() if first_h2 else len(body)
            ]
            .strip()
            .splitlines()
            if line.strip()
        ]
        if len(summary_lines) != 1:
            errors.append("summary must be one non-empty line")
        else:
            visible_summary = normalized_visible_text(
                summary_lines[0], include_inline_code=True
            )
            if JAPANESE.search(h1.group(1) if h1 else visible_summary):
                if len(re.sub(r"\s+", "", visible_summary)) > 60:
                    errors.append("Japanese summary exceeds 60 characters")
            elif len(re.findall(r"\b[\w'-]+\b", visible_summary)) > 15:
                errors.append("English summary exceeds 15 words")
        names = {
            key: _named_heading(headings, values)
            for key, values in NOTE_HEADINGS.items()
        }
        for key, values in NOTE_HEADINGS.items():
            if sum(heading in values for heading in headings) > 1:
                errors.append(f"duplicate {key.replace('_', ' ')} section")
        for key, heading in names.items():
            if heading is None:
                errors.append(f"missing {key.replace('_', ' ')} section")
        positions = [headings.index(names[key]) for key in NOTE_HEADINGS if names[key]]
        if len(positions) > 1 and positions != sorted(positions):
            errors.append("note sections are out of order")
        if names["learn"] and len(BULLET.findall(sections[names["learn"]])) != 2:
            errors.append("learn section must contain exactly two bullets")
        if (
            names["non_goals"]
            and len(BULLET.findall(sections[names["non_goals"]])) != 2
        ):
            errors.append("does-not-answer section must contain exactly two bullets")
        if names["prerequisites"]:
            level = sections[names["prerequisites"]].replace("`", "").strip()
            if level not in PREREQUISITE_LEVELS:
                errors.append(
                    "prerequisite level must be basic, intermediate, or advanced"
                )
        if names["body"] and not sections[names["body"]].strip():
            errors.append("body section is empty")
        if names["verification"]:
            verification = sections[names["verification"]]
            if not _has_nonempty_command_fence(verification):
                errors.append(
                    "environment verification lacks a non-empty fenced command"
                )
            if not _has_nonempty_expected_output(verification):
                errors.append(
                    "environment verification lacks non-empty expected output"
                )
        if names["read_next"] and len(LINK.findall(sections[names["read_next"]])) != 1:
            errors.append("Read next must contain exactly one link")
    else:
        names = {
            key: _named_heading(headings, values)
            for key, values in CHECKLIST_HEADINGS.items()
        }
        for key, values in CHECKLIST_HEADINGS.items():
            if sum(heading in values for heading in headings) > 1:
                errors.append(f"duplicate {key.replace('_', ' ')} section")
        for key, heading in names.items():
            if heading is None:
                errors.append(f"missing {key.replace('_', ' ')} section")
        positions = [
            headings.index(names[key]) for key in CHECKLIST_HEADINGS if names[key]
        ]
        if len(positions) > 1 and positions != sorted(positions):
            errors.append("checklist sections are out of order")
        for key in ("purpose", "applicability", "verification"):
            if names[key] and not sections[names[key]].strip():
                errors.append(f"{key} section is empty")
        if names["read_next"] and len(LINK.findall(sections[names["read_next"]])) != 1:
            errors.append("Read next must contain exactly one link")
    return [Finding(path, error) for error in errors]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(ROOT))
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when documents do not match the future template",
    )
    args = parser.parse_args()
    root = Path(args.path).resolve()
    findings = [
        finding for path, kind in documents(root) for finding in inspect(path, kind)
    ]
    for finding in findings:
        print(f"{finding.path.relative_to(root)}: {finding.message}")
    print(f"structure report (not a gate): {len(findings)} finding(s)")
    return 1 if args.check and findings else 0


if __name__ == "__main__":
    sys.exit(main())
