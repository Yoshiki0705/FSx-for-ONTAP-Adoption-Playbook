#!/usr/bin/env python3
"""Block a write that calls something unverified when a sibling repository already investigated it.

WHY THIS EXISTS
---------------
Two things recurred in this repository's own history. A note said a performance result was
"not reproduced" while the sibling repositories (Spokes) had measured file, block and
S3 Access Points performance and a Hub page indexed it. A note said HealthOmics with
S3 Access Points was "unverified" while a Spoke held a feature request and two evidence-ledger
entries on exactly that. Each time the writer was an agent with no way to know the work existed,
and the only safeguard was the human who happened to remember.

A reminder in a steering file did not help: it is read once, before the sentence is written.
This runs at the moment the sentence is written.

WHAT THIS DOES
--------------
Reads a PreToolUse payload for a write tool (``fs_write``, ``str_replace``, ``fs_append``) on
stdin. If the write **adds** a Markdown line saying something is unverified, unmeasured or
untested, it searches the Spokes' committed content for the product-shaped terms in that
paragraph (``tools/spoke_search.py``). It blocks (exit 2) when a Spoke records a conclusion about
a term (an evidence ledger, a feature request, a limits or pitfalls page, a decision) and the
paragraph neither names that Spoke nor says the Spokes were checked.

It never blocks on a pre-existing line, a file that is not reader-facing Markdown (``EXEMPT``:
private notes, contributor instructions, translations), a write with no such line, or a term no
Spoke covers. Everything else is allowed, and any internal error allows the call: a hook that can
brick every write gets disabled, which is worse than no hook.

WAYS FORWARD (the block message says the same)
----------------------------------------------
1. Read the Spoke material (``make spoke-search Q="<term>"``), then state its tier and link the
   Spoke file in that paragraph. Linking the repository is what clears the block.
2. If the Spokes were read and the claim still stands (they cover a neighbouring thing), say what
   they cover and what they do not, and add ``<!-- spoke-checked: <term> -->`` to the text. The
   term is named so the override is auditable: ``git grep spoke-checked`` lists every one.

WHAT IT DOES NOT CATCH
----------------------
A term that appears in more than ``FOCUSED_MAX_FILES`` Spoke files (FlexCache, SnapMirror,
S3 Access Points) names no topic; a block there would fire on most sentences and get the hook
disabled. A lowercase or katakana word is not product-shaped either, so ``snapmirror`` in a code
span is not matched. A claim about performance is the one broad topic that is routed: it must
name the evidence map or a Spoke (``TOPIC_ROUTES``). Everything else is reached by the explicit
search and by the prompt-time digest (``spoke_search.py --digest``), which see the user's words.

Exit codes: 0 allow, 2 block.

SELF-TEST
---------
``python3 scripts/guard_unverified_claims.py --selftest`` builds scratch repositories and covers
block and allow in both directions. A guard proven only to block has not shown it stays quiet on
ordinary prose, and one that over-blocks is switched off.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve()


def _load_spoke_search():
    """Load the tracked search tool next to this script without touching ``sys.path``."""
    path = HERE.parents[1] / "tools" / "spoke_search.py"
    spec = importlib.util.spec_from_file_location("spoke_search", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["spoke_search"] = (
        module  # dataclasses resolve string annotations through it
    )
    spec.loader.exec_module(module)
    return module


ss = _load_spoke_search()

#: A line that says something has not been verified. Japanese first: that is what is written.
MARKER_PATTERNS = (
    r"未(?:確認|検証|測定|実測|実施|調査|評価|試験)",
    r"(?:確認|検証|測定|実測|調査|試験)(?:して|でき(?:て)?)(?:い)?(?:ない|ません)",
    r"(?:試|調べ)て(?:い)?(?:ない|ません)",
    r"要(?:検証|確認)",
    r"\bun(?:verified|tested|measured|confirmed|validated)\b",
    r"\bnot (?:yet )?(?:been )?(?:verified|measured|tested|confirmed|validated|investigated)\b",
    r"\b(?:has|have|had) not been (?:verified|measured|tested|confirmed|validated)\b",
    r"\bto be (?:verified|confirmed|measured)\b",
    r"\bwe have not (?:verified|measured|tested)\b",
)
MARKER = re.compile("|".join(MARKER_PATTERNS), re.IGNORECASE)

TABLE_ROW = re.compile(r"^\s*\|")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
ESCAPE = re.compile(
    r"<!--\s*spoke-checked\s*:\s*(.*?)\s*-->", re.IGNORECASE | re.DOTALL
)
LINK_TARGET = re.compile(r"\]\([^)]*\)")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

#: Never checked: private notes, tooling state, test fixtures, instructions to contributors and
#: agents (which quote the very sentences this guard looks for), the changelog, and the
#: translations of other languages (the markers are Japanese and English; a translation mirrors
#: the Japanese).
EXEMPT = re.compile(
    r"(^|/)(\.private|\.kiro|\.agents|\.venv|node_modules|tests?|fixtures)(/|$)"
    r"|(^|/)docs/agent/"
    r"|(^|/)(AGENTS|CONTRIBUTING|SECURITY|CHANGELOG)\.md$"
    r"|(^|/)docs/(ko|zh-CN|zh-TW|fr|de|es)/"
    r"|\.(ko|zh-CN|zh-TW|fr|de|es)\.md$"
)

#: More Spoke files than this and a term is family vocabulary, not a topic. Measured on the real
#: spread: HealthOmics 28, Quick Suite 29; FlexCache 660, SnapMirror 610, FPolicy 1038.
FOCUSED_MAX_FILES = 40
MAX_TERMS = 8

#: A marker that says a *measurement* was not made, as opposed to something merely unconfirmed.
MEASUREMENT_MARKER = re.compile(
    r"未(?:測定|実測|計測)|(?:測定|実測|計測)(?:して|でき(?:て)?)(?:い)?(?:ない|ません)|"
    r"\b(?:un)?measured\b|\bnot (?:yet )?(?:been )?measured\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Route:
    """A topic too broad for term search, sent to the page that indexes the Spokes' work on it."""

    key: str  # what `spoke-checked: <key>` names
    scope: re.Pattern[str]  # words that put a paragraph on this topic
    doc: str  # repo-relative path of the page; the route applies only where it exists
    mention: str  # what the paragraph must contain to show the page was consulted
    only_measurement: bool = False  # fire only for a "not measured" claim
    index_pages: tuple[str, ...] = ()  # file names exempt from this route


TOPIC_ROUTES = (
    Route(
        "performance",
        re.compile(
            r"スループット|レイテンシ|性能|パフォーマンス|ベンチマーク|"
            r"\bthroughput\b|\blatency\b|\bIOPS\b|\bbenchmark|\bperformance\b",
            re.IGNORECASE,
        ),
        "docs/ja/reference/performance-evidence-map.md",
        "performance-evidence-map",
        only_measurement=True,
        index_pages=("performance-evidence-map.md", "cross-repo-index.md"),
    ),
)


@dataclass(frozen=True)
class Change:
    path: str
    new_text: str
    old_text: str


@dataclass(frozen=True)
class Finding:
    sentence: str
    term: str  # the searched term, or the route key
    detail: list[str]  # lines to show: repositories and files, or the page to read
    kind: str  # "spoke" | "route"


# --- reading the payload --------------------------------------------------------------------------


def _first_str(source: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = source.get(key)
        if isinstance(value, str):
            return value
    return None


PATH_KEYS = ("path", "file_path", "filePath", "filename")
INPUT_KEYS = (
    "tool_input",
    "toolInput",
    "input",
    "arguments",
    "parameters",
    "params",
    "args",
)


def _input_dict(payload: dict) -> dict | None:
    """The tool's own arguments inside a hook payload.

    The payload schema is not documented, so look under every name seen in practice, then in any
    nested object that carries a path, then in the payload itself. A miss here allows the write
    (nothing is checked), which is the safe direction.
    """
    for key in INPUT_KEYS:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    for value in payload.values():
        if isinstance(value, dict) and any(k in value for k in PATH_KEYS):
            return value
    return payload if any(k in payload for k in PATH_KEYS) else None


def change_from(payload: dict, cwd: Path) -> Change | None:
    """The text a write tool call would add, without assuming one exact payload shape."""
    tool = _first_str(payload, ("tool_name", "toolName", "tool")) or ""
    given = _input_dict(payload)
    if given is None:
        return None
    path = _first_str(given, PATH_KEYS)
    if not path:
        return None
    new_str = _first_str(given, ("newStr", "new_str", "newText", "new_text"))
    old_str = _first_str(given, ("oldStr", "old_str", "oldText", "old_text"))
    text = _first_str(given, ("text", "file_text", "content", "contents"))
    if new_str is not None:
        return Change(path, new_str, old_str or "")
    if text is None:
        return None
    if tool in ("fs_append", "fsAppend", "append"):
        return Change(path, text, "")
    target = Path(path) if Path(path).is_absolute() else cwd / path
    try:
        existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    except (OSError, UnicodeDecodeError):
        existing = ""
    return Change(path, text, existing)


def checked_path(path: str) -> bool:
    return path.lower().endswith((".md", ".markdown")) and not EXEMPT.search(
        path.replace("\\", "/")
    )


# --- finding what a write adds --------------------------------------------------------------------


def added_marker_lines(change: Change) -> list[int]:
    """Indexes (into the new text's lines) of added lines that say something is unverified.

    A line counts as added when the old text has no more copies of it than the new text does, so
    moving a paragraph or editing a neighbour does not make its old wording new.
    """
    remaining = Counter(
        line.strip() for line in change.old_text.splitlines() if line.strip()
    )
    found: list[int] = []
    for index, line in enumerate(change.new_text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        if remaining[stripped] > 0:
            remaining[stripped] -= 1
            continue
        if MARKER.search(line):
            found.append(index)
    return found


def scope_of(lines: list[str], index: int, reach: int = 6) -> str:
    """The marker line's own block: its table row, its list item, or its paragraph."""
    if TABLE_ROW.match(lines[index]):
        return lines[index]

    def stops(line: str) -> bool:
        return not line.strip() or bool(HEADING.match(line) or TABLE_ROW.match(line))

    low = index
    while (
        low > 0
        and index - low < reach
        and not stops(lines[low - 1])
        and not BULLET.match(lines[low])
    ):
        low -= 1
    high = index
    while (
        high + 1 < len(lines)
        and high - index < reach
        and not stops(lines[high + 1])
        and not BULLET.match(lines[high + 1])
    ):
        high += 1
    return "\n".join(lines[low : high + 1])


def clean(scope: str) -> str:
    """The prose of a scope, without link targets and comments that would read as terms."""
    return COMMENT.sub(" ", LINK_TARGET.sub("]", scope))


def acknowledged_terms(text: str) -> set[str]:
    named: set[str] = set()
    for match in ESCAPE.finditer(text):
        named.update(
            part.strip().lower()
            for part in re.split(r"[,\s]+", match.group(1))
            if part.strip()
        )
    return named


# --- the check --------------------------------------------------------------------------------------


def evaluate(change: Change, *, repos=None, root: Path | None = None) -> list[Finding]:
    """What, if anything, a write must change before it is allowed. Empty means allow."""
    if not checked_path(change.path):
        return []
    lines = change.new_text.splitlines()
    markers = added_marker_lines(change)
    if not markers:
        return []
    waived = acknowledged_terms(change.new_text)
    if root is None:
        root = ss.toplevel(_existing_parent(change.path))
    if repos is None:
        repos = ss.discover(root) if root else []
    cache: dict[tuple[str, str], dict[str, list]] = {}

    def lookup(terms: list[str]) -> None:
        wanted = [(t, r) for t in terms for r in repos if (t, r.name) not in cache]
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {(t, r.name): pool.submit(ss.grep, r, [t]) for t, r in wanted}
            for key, future in futures.items():
                cache[key] = future.result()

    findings: list[Finding] = []
    for index in markers:
        scope = scope_of(lines, index)
        prose = clean(scope)
        sentence = " ".join(lines[index].split())[:140]
        lowered = scope.lower()
        terms = [
            t
            for t in ss.candidate_terms(prose, limit=MAX_TERMS, named_only=True)
            if t not in waived
        ]
        if repos and terms:
            lookup(terms)
        for term in terms:
            holding = [
                (r, cache[(term, r.name)]) for r in repos if cache.get((term, r.name))
            ]
            files = sum(len(hits) for _, hits in holding)
            decisive = sum(
                1 for _, hits in holding for p in hits if ss.RECORD_PATH.search(p)
            )
            # Focused: few enough files to be one topic. Decisive: at least one is a record of a
            # decision, a result or a known gap, not code or prose that happens to hold the word.
            if not (0 < files <= FOCUSED_MAX_FILES and decisive >= 1):
                continue
            if any(r.name.lower() in lowered for r, _ in holding):
                continue  # the paragraph already points at the Spoke that holds it
            detail = []
            for repo, hits in holding:
                shown = ss.rank(hits, [term])[:3]
                detail.append(
                    f"{repo.name}: {len(hits)} file(s); e.g. " + ", ".join(shown)
                )
            findings.append(Finding(sentence, term, detail, "spoke"))
        for route in TOPIC_ROUTES:
            if route.key in waived or not route.scope.search(prose):
                continue
            if route.only_measurement and not MEASUREMENT_MARKER.search(lines[index]):
                continue
            if root is None or not (root / route.doc).is_file():
                continue
            if change.path.replace("\\", "/").endswith(route.index_pages):
                continue  # the index itself, and the table of citations, say what is unmeasured
            if route.mention in lowered or any(
                r.name.lower() in lowered for r in repos
            ):
                continue  # the paragraph names the page, or a Spoke, it relies on
            findings.append(
                Finding(
                    sentence, route.key, [f"read {route.doc} and link it here"], "route"
                )
            )
    # One finding per (term, sentence); the same term can come up through two sentences.
    unique: dict[tuple[str, str], Finding] = {}
    for finding in findings:
        unique.setdefault((finding.term, finding.sentence), finding)
    return list(unique.values())


def _existing_parent(path: str) -> Path:
    here = Path(path)
    here = here if here.is_absolute() else Path.cwd() / here
    for candidate in (here.parent, *here.parents):
        if candidate.is_dir():
            return candidate
    return Path.cwd()


BLOCK_MESSAGE = """\
BLOCKED (nothing was written): this text says something is unverified, but a sibling repository
already holds material on it. Writing "unverified" over investigated work is the failure this guard
exists to stop.

{findings}
The parameters of this call need to change. Revise the text you are writing, then call again;
repeating the same call is blocked again.

  1. Read it:  {how}
     Then state the tier it records and link that Spoke's file in the same paragraph. Naming the
     repository in the paragraph clears the block.
  2. If the Spokes were read and your claim still stands (they cover a neighbouring thing), say
     what they cover and what they do not, and add  <!-- spoke-checked: {first} -->  to the text.
     That is an override on the record: `git grep spoke-checked` lists every one.
"""


def render_block(findings: list[Finding]) -> str:
    shown = []
    for finding in findings[:4]:
        shown.append(f'  sentence: "{finding.sentence}"')
        if finding.kind == "route":
            shown.append(f"    topic {finding.term}: " + "; ".join(finding.detail))
        else:
            shown.append(f'    term "{finding.term}":')
            shown += [f"      {line}" for line in finding.detail]
    if len(findings) > 4:
        shown.append(f"  ... and {len(findings) - 4} more")
    first = findings[0].term
    return BLOCK_MESSAGE.format(
        findings="\n".join(shown) + "\n", first=first, how=ss.read_command(first)
    )


# --- self-test ------------------------------------------------------------------------------------

MARKER_JA = (
    "FSx for ONTAP の S3 Access Points から HealthOmics を読めるかは未確認です。"
)


def selftest() -> int:
    failures = 0

    def expect(want_block: bool, label: str, change: Change, **kw) -> None:
        nonlocal failures
        findings = evaluate(change, **kw)
        got = bool(findings)
        if got == want_block:
            print(f"  pass ({'block' if got else 'allow'})  {label}")
        else:
            failures += 1
            print(
                f"  FAIL want={'block' if want_block else 'allow'} got={'block' if got else 'allow'}  {label}"
            )

    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        hub = ss._clone(
            base, ss._remote(base, "acme", "Hub"), "hub", {"README.md": "# Hub\n"}
        )
        (hub / "docs/ja/reference").mkdir(parents=True)
        (hub / "docs/ja/reference/performance-evidence-map.md").write_text(
            "# Map\n", encoding="utf-8"
        )
        spoke = ss._clone(
            base,
            ss._remote(base, "acme", "Serverless-Patterns"),
            "serverless",
            {
                "docs/aws-feature-requests/healthomics-gaps.md": "# Gaps\nHealthOmics cannot take the access point.\n",
                "docs/notes.md": "# Notes\nNextflow appears once, in passing.\n",
                "docs/a.md": "Quuxlib is used.\n",
                "docs/b.md": "Quuxlib again.\n",
                "docs/c.md": "Quuxlib a third time.\n",
            },
        )
        roots = [base / "work"]
        repos = ss.discover(hub, roots)
        doc = str(hub / "docs/ja/note.md")

        def write(text: str, old: str = "", path: str = doc) -> Change:
            return Change(path, text, old)

        print("block:")
        expect(
            True,
            "an added 未確認 about a term a Spoke recorded as a decision",
            write(MARKER_JA),
            repos=repos,
            root=hub,
        )
        expect(
            True,
            "the same sentence added to an existing file's other text",
            write(
                "# T\n\n既存の段落。\n\n" + MARKER_JA + "\n", "# T\n\n既存の段落。\n"
            ),
            repos=repos,
            root=hub,
        )
        expect(
            True,
            "an English marker and the same term",
            write("Reading from HealthOmics through the access point is not verified."),
            repos=repos,
            root=hub,
        )
        expect(
            True,
            "a table row carries its own scope",
            write(
                "| 項目 | 状態 |\n|---|---|\n| HealthOmics での読み取り | 未確認 |\n"
            ),
            repos=repos,
            root=hub,
        )
        expect(
            True,
            "a performance claim that does not consult the evidence map",
            write("FlexCache のスループットは未測定です。"),
            repos=repos,
            root=hub,
        )
        expect(
            True,
            "an English measurement claim on a performance paragraph",
            write("FlexCache latency is not measured."),
            repos=repos,
            root=hub,
        )
        expect(
            True,
            "a list item is judged on its own text, not the next item's",
            write("- 無関係な項目\n- HealthOmics の読み取りは未確認\n- 別の項目\n"),
            repos=repos,
            root=hub,
        )
        expect(
            True,
            "an override for a different term does not cover this one",
            write(MARKER_JA + "\n<!-- spoke-checked: quuxlib -->\n"),
            repos=repos,
            root=hub,
        )

        print("allow:")
        expect(
            False,
            "the paragraph links the Spoke that holds it",
            write(
                MARKER_JA
                + " 記録は [Serverless-Patterns](https://github.com/acme/Serverless-Patterns/blob/main/docs/x.md) を参照。"
            ),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "the override names the term",
            write(MARKER_JA + "\n<!-- spoke-checked: healthomics -->\n"),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "the marker line was already in the file",
            write(MARKER_JA + "\n他の文。\n", MARKER_JA + "\n"),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "a term no Spoke covers",
            write("Zzyzxlib の挙動は未確認です。"),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "a term in one ordinary Spoke file is a passing mention",
            write("Nextflow の挙動は未確認です。"),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "a named term in three ordinary Spoke files and no record of a conclusion",
            write("新しい Quuxlib の挙動は未検証です。"),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "an ordinary word that a record happens to contain is not a topic",
            write("The path cannot be read, and this is not verified."),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "an unconfirmed performance paragraph is not a missing measurement",
            write("FlexCache のスループットの扱いは未確認です。"),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "no marker at all",
            write("HealthOmics の run 入出力は S3 URI です。"),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "a marker does not borrow a term from another paragraph",
            write(
                "HealthOmics の run 入出力は S3 URI です。\n\n別の件の挙動は未確認です。\n"
            ),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "a marker does not borrow a term from another table row",
            write("| HealthOmics | 文書化済み |\n| 別の機能 | 未確認 |\n"),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "not a Markdown file",
            write(MARKER_JA, path=str(hub / "tools/x.py")),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "a private note",
            write(MARKER_JA, path=str(hub / ".private/notes.md")),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "instructions to contributors quote the marker sentences",
            write(MARKER_JA, path=str(hub / "docs/agent/pitfalls.md")),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "a translation into another language",
            write(MARKER_JA, path=str(hub / "docs/de/note.md")),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "a performance claim that links the evidence map",
            write(
                "FlexCache のスループットは未測定です。測定済みの範囲は [performance-evidence-map](performance-evidence-map.md) を参照。"
            ),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "a performance claim with the route override",
            write(
                "FlexCache のスループットは未測定です。\n<!-- spoke-checked: performance -->\n"
            ),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "a performance claim that names the Spoke it relies on",
            write(
                "FlexCache のスループットは未測定です。測定値は Serverless-Patterns 側にあります。"
            ),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "the evidence map itself lists what is unmeasured",
            write(
                "FlexCache のスループットは未測定です。",
                path=str(hub / "docs/ja/reference/performance-evidence-map.md"),
            ),
            repos=repos,
            root=hub,
        )
        expect(
            False,
            "no sibling repositories to compare with",
            write(MARKER_JA),
            repos=[],
            root=hub,
        )
        expect(
            False,
            "the Spoke writing about its own subject",
            write(MARKER_JA, path=str(spoke / "docs/x.md")),
            repos=ss.discover(spoke, roots),
            root=spoke,
        )

        print("payload:")
        payloads = {
            "str_replace": {
                "tool_name": "str_replace",
                "tool_input": {"path": doc, "oldStr": "a", "newStr": MARKER_JA},
            },
            "fs_write": {
                "toolName": "fs_write",
                "toolInput": {"path": doc, "text": MARKER_JA},
            },
            "fs_append": {
                "tool_name": "fs_append",
                "tool_input": {"path": doc, "text": MARKER_JA},
            },
        }
        for name, payload in payloads.items():
            parsed = change_from(payload, hub)
            if parsed is not None and parsed.new_text == MARKER_JA:
                print(f"  pass  {name} payload is read")
            else:
                failures += 1
                print(f"  FAIL  {name} payload is read")
        for name, payload in {
            "a flat payload": {"tool_name": "fs_write", "path": doc, "text": MARKER_JA},
            "arguments under another key": {
                "tool": "fs_write",
                "parameters": {"file_path": doc, "file_text": MARKER_JA},
            },
            "arguments in an unnamed nested object": {
                "event": "preToolUse",
                "call": {"path": doc, "text": MARKER_JA},
            },
        }.items():
            parsed = change_from(payload, hub)
            if parsed is not None and parsed.new_text == MARKER_JA:
                print(f"  pass  {name} is read")
            else:
                failures += 1
                print(f"  FAIL  {name} is read")
        for label, payload in {
            "an unknown shape": {"something": "else"},
            "no path": {"tool_name": "fs_write", "tool_input": {"text": MARKER_JA}},
            "a read tool": {"tool_name": "read_file", "tool_input": {"path": doc}},
        }.items():
            if change_from(payload, hub) is None:
                print(f"  pass  {label} yields no change (allowed)")
            else:
                failures += 1
                print(f"  FAIL  {label} yields no change")

        message = render_block(evaluate(write(MARKER_JA), repos=repos, root=hub))
        for needle, label in (
            (
                "parameters of this call need to change",
                "the block message says the call must change",
            ),
            (
                "spoke-checked: healthomics",
                "the block message names the override for this term",
            ),
            ("make spoke-search", "the block message says how to read the material"),
            (
                f"python3 {HERE.parents[1] / 'tools' / 'spoke_search.py'} healthomics",
                "the block message gives a command that works outside the Hub",
            ),
            ("Serverless-Patterns", "the block message names the Spoke"),
        ):
            if needle in message:
                print(f"  pass  {label}")
            else:
                failures += 1
                print(f"  FAIL  {label}")

        # The whole path, as the hook runs it: JSON on stdin, a verdict in the exit status.
        print("end to end:")

        def run(stdin: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, str(HERE)],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
                cwd=hub,
                env=ss._env(),
            )

        scenarios = (
            (
                "an added 未確認 over Spoke records exits 2 and explains itself",
                json.dumps(
                    {
                        "tool_name": "fs_write",
                        "tool_input": {"path": doc, "text": MARKER_JA},
                    }
                ),
                2,
                "need to change",
            ),
            (
                "a write with no marker exits 0 and says nothing",
                json.dumps(
                    {
                        "tool_name": "fs_write",
                        "tool_input": {
                            "path": doc,
                            "text": "HealthOmics の run 入出力は S3 URI です。",
                        },
                    }
                ),
                0,
                "",
            ),
            ("malformed input exits 0", "{not json", 0, ""),
            ("empty input exits 0", "", 0, ""),
        )
        for label, stdin, want_status, want_text in scenarios:
            done = run(stdin)
            ok = done.returncode == want_status and want_text in done.stderr
            ok = ok and (want_status == 2 or done.stderr == "")
            if ok:
                print(f"  pass  {label}")
            else:
                failures += 1
                print(
                    f"  FAIL  {label} (exit {done.returncode}, stderr {done.stderr[:80]!r})"
                )

    print(f"\n{'FAILED' if failures else 'all passed'}")
    return 1 if failures else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if sys.stdin.isatty():
        print(
            "This is a PreToolUse hook: it expects a JSON event on stdin.\n"
            "  To verify block / allow behaviour, run:\n"
            "    python3 scripts/guard_unverified_claims.py --selftest",
            file=sys.stderr,
        )
        return 0
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    change = change_from(payload, Path.cwd())
    if change is None or not checked_path(change.path):
        return 0
    findings = evaluate(change)
    if not findings:
        return 0
    print(render_block(findings), file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - a hook must not brick every write
        print(
            f"guard_unverified_claims: allowing the call after an internal error: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)
