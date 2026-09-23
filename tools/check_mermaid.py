"""Render Mermaid fences and report bounded decision-flow clarity patterns.

Report mode inventories parser failures, vague decision labels, and unlabeled outgoing
branches without changing tracked content. ``--check`` returns nonzero for those findings.
The clarity checks are syntactic and pattern-based; they do not judge business semantics.
A missing CLI always fails because reporting zero findings without running the parser would
be a false success.
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
FLOWCHART = re.compile(r"^\s*(?:graph|flowchart)\b", re.IGNORECASE | re.MULTILINE)
DECISION = re.compile(
    r"(?<![\w-])(?P<id>[A-Za-z_][\w-]*)\s*\{\s*"
    r'(?P<label>"(?:[^"\\]|\\.)*"|[^{}]*)\s*\}'
)
EDGE_TEXT_LABEL = r"--[ \t]+(?P<text_label>.+?)[ \t]+-->"
EDGE = re.compile(
    r"(?<![\w-])(?P<source>[A-Za-z_][\w-]*)"
    r"(?:\s*(?:\{[^{}]*\}|\[[^\[\]]*\]|\([^()]*\)))?\s*"
    rf"(?:-->\s*(?:\|(?P<pipe_label>[^|]*)\|)?|{EDGE_TEXT_LABEL})"
)
HTML_TAG = re.compile(r"<[^>]+>")
NON_WORD = re.compile(r"[^0-9A-Za-z一-龠ぁ-んァ-ヶー]+")

# Exact normalized labels only. This bounded vocabulary intentionally avoids substring
# matching: a node such as "What must be retained" names an input, while "What" does not.
VAGUE_DECISION_LABELS = frozenset(
    {
        "choice",
        "condition",
        "decision",
        "purpose",
        "select",
        "what",
        "which",
        "why",
        "どれ",
        "どちら",
        "何",
        "何を",
        "判断",
        "条件",
        "選択",
        "目的",
    }
)


@dataclass(frozen=True)
class Block:
    path: Path
    line: int
    source: str
    error: str | None = None


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    message: str


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


def _normalized_label(label: str) -> str:
    unquoted = label.strip().strip("\"'`")
    visible = HTML_TAG.sub(" ", unquoted)
    return NON_WORD.sub("", visible).casefold()


def decision_clarity(block: Block) -> list[Finding]:
    """Return bounded syntactic findings for Mermaid flowchart decision nodes.

    The function deliberately does not infer whether a label is technically correct or
    whether two branches are exhaustive. Sequence diagrams, flowcharts without decision
    diamonds, and maps with no explicit branch-state labels are outside this rule.
    """
    if block.error or not FLOWCHART.search(block.source):
        return []

    lines = block.source.splitlines()
    decisions: dict[str, tuple[int, str]] = {}
    outgoing: dict[str, list[tuple[int, str | None]]] = {}

    for offset, line in enumerate(lines, start=1):
        for match in DECISION.finditer(line):
            decisions[match.group("id")] = (offset, match.group("label"))
        for match in EDGE.finditer(line):
            label = match.group("pipe_label")
            if label is None:
                label = match.group("text_label")
            outgoing.setdefault(match.group("source"), []).append((offset, label))

    if not any(
        label is not None and label.strip()
        for node in decisions
        for _, label in outgoing.get(node, [])
    ):
        return []

    findings: list[Finding] = []
    for node, (offset, label) in decisions.items():
        if _normalized_label(label) in VAGUE_DECISION_LABELS:
            findings.append(
                Finding(
                    block.path,
                    block.line + offset,
                    f'decision node {node} has vague label "{label.strip()}"',
                )
            )

        branches = outgoing.get(node, [])
        if len(branches) < 2:
            continue
        for edge_offset, edge_label in branches:
            if edge_label is None or not edge_label.strip():
                findings.append(
                    Finding(
                        block.path,
                        block.line + edge_offset,
                        f"decision node {node} has an unlabeled outgoing branch",
                    )
                )
    return findings


def render(block: Block, cli: Path) -> str | None:
    if block.error:
        return block.error
    with tempfile.TemporaryDirectory(prefix="mermaid-report-") as directory:
        source = Path(directory) / "block.mmd"
        output = Path(directory) / "block.svg"
        # mmdc launches Chromium through Puppeteer. A sandboxed CI runner (no setuid root,
        # unprivileged user namespaces) makes Chromium's own sandbox fail to initialize, and
        # the failure surfaces as a bare Node.js child-process exit rather than a mermaid parse
        # error -- every render call failed this way in CI even for syntactically valid input,
        # which a local machine with a normal desktop Chromium install never reproduces.
        # --no-sandbox is mmdc's own documented workaround for exactly this environment.
        puppeteer_config = Path(directory) / "puppeteer-config.json"
        puppeteer_config.write_text(
            '{"args": ["--no-sandbox", "--disable-setuid-sandbox"]}', encoding="utf-8"
        )
        source.write_text(block.source, encoding="utf-8")
        result = subprocess.run(
            [
                str(cli),
                "--input",
                str(source),
                "--output",
                str(output),
                "--quiet",
                "--puppeteerConfigFile",
                str(puppeteer_config),
            ],
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
        "--check",
        action="store_true",
        help="fail on Mermaid parse/render or bounded decision-clarity findings",
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
    rendered = [(block, render(block, cli)) for block in blocks]
    failures = [(block, error) for block, error in rendered if error]
    clarity = [finding for block in blocks for finding in decision_clarity(block)]

    for block, error in failures:
        print(
            f"{block.path.relative_to(root)}:{block.line}: Mermaid parse/render failed: {error}"
        )
    for finding in clarity:
        print(
            f"{finding.path.relative_to(root)}:{finding.line}: "
            f"Mermaid decision clarity: {finding.message}"
        )
    print(
        "mermaid report (pattern-based; business semantics are not evaluated): "
        f"{len(blocks)} block(s), {len(failures)} parse/render failure(s), "
        f"{len(clarity)} decision-clarity finding(s)"
    )
    return 1 if args.check and (failures or clarity) else 0


if __name__ == "__main__":
    sys.exit(main())
