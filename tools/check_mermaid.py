"""Render every Mermaid fence with the exact-pinned CLI using temporary files.

Report mode inventories existing syntax failures without changing tracked content. --check
returns nonzero for malformed or unterminated Mermaid blocks. A missing CLI always fails because
reporting zero findings without running the parser would be a false success.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from frontmatter import IGNORED_DIRS

ROOT = Path(__file__).resolve().parent.parent
OPEN = re.compile(
    r"^\s*(`{3,}|~{3,})[ \t]*mermaid(?:[ \t]+[^\r\n]*)?\s*$", re.IGNORECASE
)
CLOSE = re.compile(r"^\s*(`{3,}|~{3,})\s*$")


@dataclass(frozen=True)
class Block:
    path: Path
    line: int
    source: str
    error: str | None = None


def extract(path: Path) -> list[Block]:
    blocks: list[Block] = []
    marker: str | None = None
    start = 0
    source: list[str] = []
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if marker is None:
            match = OPEN.match(line)
            if match:
                marker = match.group(1)
                start = lineno
                source = []
            continue
        close = CLOSE.match(line)
        if (
            close
            and close.group(1)[0] == marker[0]
            and len(close.group(1)) >= len(marker)
        ):
            blocks.append(Block(path, start, "\n".join(source) + "\n"))
            marker = None
            continue
        source.append(line)
    if marker is not None:
        blocks.append(
            Block(path, start, "\n".join(source), "unterminated Mermaid fence")
        )
    return blocks


def markdown_files(root: Path):
    for path in sorted(root.rglob("*.md")):
        if not any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            yield path


def render(block: Block, cli: Path) -> str | None:
    if block.error:
        return block.error
    with tempfile.TemporaryDirectory(prefix="mermaid-report-") as directory:
        source = Path(directory) / "block.mmd"
        output = Path(directory) / "block.svg"
        source.write_text(block.source, encoding="utf-8")
        result = subprocess.run(
            [str(cli), "--input", str(source), "--output", str(output), "--quiet"],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if result.returncode:
            return (
                (result.stderr or result.stdout or f"mmdc exited {result.returncode}")
                .strip()
                .splitlines()[-1]
            )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(ROOT))
    parser.add_argument(
        "--check", action="store_true", help="fail when Mermaid parsing/rendering fails"
    )
    parser.add_argument("--cli", default="node_modules/.bin/mmdc")
    args = parser.parse_args()
    root = Path(args.path).resolve()
    cli = (
        (root / args.cli).resolve()
        if not Path(args.cli).is_absolute()
        else Path(args.cli)
    )
    if not cli.is_file():
        print(
            "mermaid report unavailable: run npm ci to install the exact-pinned Mermaid CLI",
            file=sys.stderr,
        )
        return 2
    blocks = [block for path in markdown_files(root) for block in extract(path)]
    findings = [(block, render(block, cli)) for block in blocks]
    failures = [(block, error) for block, error in findings if error]
    for block, error in failures:
        print(
            f"{block.path.relative_to(root)}:{block.line}: Mermaid parse/render failed: {error}"
        )
    print(
        f"mermaid report (not a gate): {len(blocks)} block(s), {len(failures)} failure(s)"
    )
    return 1 if args.check and failures else 0


if __name__ == "__main__":
    sys.exit(main())
