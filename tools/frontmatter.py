"""Minimal YAML frontmatter reader.

Deliberately dependency-free: this repository has no runtime, and requiring PyYAML for a
docs-only project adds an install step to every contributor's first commit. The subset
supported here (scalars, inline lists, quoted strings, comments) is exactly what the note
schema in AGENTS.md uses, and `validate_frontmatter.py` rejects anything outside it rather
than guessing.
"""

from __future__ import annotations

from pathlib import Path

DELIMITER = "---"


class FrontmatterError(ValueError):
    """Raised when a frontmatter block is malformed."""


def split(text: str) -> tuple[str | None, str]:
    """Split raw file text into (frontmatter_block, body).

    Returns (None, text) when the file has no frontmatter block.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != DELIMITER:
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() == DELIMITER:
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    raise FrontmatterError("frontmatter block opened with '---' but never closed")


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_value(raw: str) -> str | list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [
            _strip_quotes(item.strip()) for item in inner.split(",") if item.strip()
        ]
    return _strip_quotes(raw)


def parse(block: str) -> dict[str, str | list[str]]:
    """Parse a frontmatter block into a flat mapping."""
    data: dict[str, str | list[str]] = {}
    for lineno, line in enumerate(block.splitlines(), start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line != line.lstrip():
            raise FrontmatterError(
                f"line {lineno}: nested / indented keys are not supported by the note schema"
            )
        if ":" not in stripped:
            raise FrontmatterError(
                f"line {lineno}: expected 'key: value', got {stripped!r}"
            )
        key, _, raw = stripped.partition(":")
        key = key.strip()
        if key in data:
            raise FrontmatterError(f"line {lineno}: duplicate key {key!r}")
        data[key] = _parse_value(raw)
    return data


def read(path: Path) -> tuple[dict[str, str | list[str]] | None, str]:
    """Read a file and return (frontmatter_mapping, body)."""
    text = path.read_text(encoding="utf-8")
    block, body = split(text)
    if block is None:
        return None, body
    return parse(block), body


def iter_markdown(
    root: Path, *, skip: tuple[str, ...] = (".private", "node_modules", ".kiro")
):
    """Yield every tracked Markdown file under root, skipping excluded directories."""
    for path in sorted(root.rglob("*.md")):
        if any(part in skip for part in path.parts):
            continue
        yield path
