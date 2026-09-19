"""Shared Markdown prose extraction for staged editorial reports.

Eligible prose consists of paragraphs and list items. Headings, tables, fenced code,
block quotes, generated language switchers, and frontmatter are excluded. URLs are
removed while Markdown link labels remain visible. Callers choose whether inline code
is visible because sentence length includes rendered code while glossary first-use does not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from frontmatter import split

FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
HEADING = re.compile(r"^\s*#{1,6}\s+")
LIST_ITEM = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+(.*)$")
LINK = re.compile(r"(?<!!)\[([^]\n]+)\]\(([^)\n]+)\)")
IMAGE = re.compile(r"!\[[^]\n]*\]\([^)\n]+\)")
INLINE_CODE = re.compile(r"`[^`\n]*`")
URL = re.compile(r"https?://[^\s。！？、，；]+")
HTML = re.compile(r"<[^>]+>")
MARKUP = re.compile(r"(?:\*\*|__|~~|(?<!\*)\*(?!\*)|(?<!_)_(?!_))")
SWITCHER_START = "<!-- lang-switcher:start -->"
SWITCHER_END = "<!-- lang-switcher:end -->"
TABLE_DELIMITER = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")


@dataclass(frozen=True)
class ProseBlock:
    """One eligible Markdown prose block and its one-based starting line."""

    line: int
    raw: str


def _table_lines(lines: list[str]) -> set[int]:
    """Return zero-based lines belonging to pipe tables, with or without outer pipes."""
    excluded: set[int] = set()
    for index, line in enumerate(lines):
        if not TABLE_DELIMITER.match(line) or index == 0 or "|" not in lines[index - 1]:
            continue
        excluded.update({index - 1, index})
        following = index + 1
        while (
            following < len(lines)
            and lines[following].strip()
            and "|" in lines[following]
        ):
            excluded.add(following)
            following += 1
    return excluded


def strip_fenced_blocks(text: str) -> str:
    """Blank fenced blocks while preserving line numbers for structural parsing."""
    output: list[str] = []
    marker: str | None = None
    for line in text.splitlines():
        match = FENCE.match(line)
        if marker is None and match:
            marker = match.group(1)
            output.append("")
        elif marker is not None:
            stripped = line.strip()
            if (
                stripped
                and set(stripped) == {marker[0]}
                and len(stripped) >= len(marker)
            ):
                marker = None
            output.append("")
        else:
            output.append(line)
    return "\n".join(output)


def prose_blocks(text: str) -> list[ProseBlock]:
    """Return paragraph and list-item blocks after all block-level exclusions."""
    block, body = split(text)
    body_start = len(block.splitlines()) + 3 if block is not None else 1
    lines = body.splitlines()
    blocks: list[ProseBlock] = []
    paragraph: list[str] = []
    paragraph_line = 0
    in_fence: str | None = None
    in_switcher = False
    table_lines = _table_lines(lines)

    def flush() -> None:
        nonlocal paragraph, paragraph_line
        if paragraph:
            blocks.append(
                ProseBlock(paragraph_line, " ".join(part.strip() for part in paragraph))
            )
        paragraph = []
        paragraph_line = 0

    for offset, line in enumerate(lines):
        lineno = body_start + offset
        if SWITCHER_START in line:
            flush()
            in_switcher = True
            continue
        if SWITCHER_END in line:
            in_switcher = False
            continue
        if in_switcher:
            continue
        fence = FENCE.match(line)
        if in_fence is None and fence:
            flush()
            in_fence = fence.group(1)
            continue
        if in_fence is not None:
            stripped_fence = line.strip()
            if (
                stripped_fence
                and set(stripped_fence) == {in_fence[0]}
                and len(stripped_fence) >= len(in_fence)
            ):
                in_fence = None
            continue
        stripped = line.strip()
        if not stripped or HEADING.match(line) or stripped.startswith(">"):
            flush()
            continue
        if offset in table_lines:
            flush()
            continue
        item = LIST_ITEM.match(line)
        if item:
            flush()
            blocks.append(ProseBlock(lineno, item.group(1).strip()))
            continue
        if not paragraph:
            paragraph_line = lineno
        paragraph.append(line)
    flush()
    return blocks


def normalized_visible_text(raw: str, *, include_inline_code: bool) -> str:
    """Return rendered prose text while retaining Markdown link labels."""
    text = IMAGE.sub("", raw)
    if not include_inline_code:
        text = INLINE_CODE.sub("", text)
    else:
        text = INLINE_CODE.sub(lambda match: match.group()[1:-1], text)
    text = LINK.sub(lambda match: match.group(1), text)
    text = URL.sub("", text)
    text = HTML.sub("", text)
    return MARKUP.sub("", text)
