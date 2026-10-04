#!/usr/bin/env python3
"""Measure whether each benchmark question reaches its answer from `llms.txt` within a hop budget.

Why this exists
---------------
The other gates prove that links resolve, that anchors exist, and that every module README routes
its reader. None of them proves that a question an operator or an instructed agent actually asks
leads to the document holding the answer. A note can be correct, linked, and still sit four
documents deep behind pages that never mention its subject, and nothing reports it. This tool
records a set of questions with the documents that answer them
(`docs/agent/reachability-questions.json`) and measures the shortest link path to each.

What a hop is
-------------
One followed link. An entry point (`llms.txt` by default) is hop 0, a document linked from it is
hop 1. A link's `#fragment` does not change the node: reaching a document is the hop, and a target's
`anchor` is checked separately against that document's headings.

Why the budget is three
-----------------------
The designed route is `llms.txt` -> an index, map or module README (1) -> a note (2) -> one further
hop for a section-linked or comparison document (3). Every hop costs an agent a whole document of
context, and `llms.txt` alone is tens of kilobytes, so a route that needs three intermediate
documents with nothing pointing the way is not one an instructed agent reliably follows. One
budget applies to Hub and cross-repo questions alike: a sibling answer that needs more than three
hops from the Hub is exactly what this measurement exists to surface. The budget is `MAX_HOPS`
below and nowhere else; `--max-hops` overrides it for a run.

What PASS means, and what it does not
-------------------------------------
PASS means **a link path exists within the budget and ends on a document that exists**. A Hub
target exists when it is on disk. With `--external`, every reached sibling target within the budget
is fetched, including one linked at exactly the budget that the crawl would not otherwise open, so a
link to a sibling page that answers 404 is a FAIL rather than a PASS. PASS does not mean an agent
will choose that path: this is a measurement of link structure, a sample over the questions in the
file, not a run of any model. A FAIL is a finding about navigation, and this tool does not fix
navigation.

What SIGNPOSTED means
---------------------
A linked PASS only says some path exists, and `llms.txt` links nearly every note, so nearly every
Hub question passes at hop 1 whether or not anything on the way names its subject. The second
verdict, reported for every question beside the linked one, asks for more: **a path within the
budget on which every hop is signposted**. A question's `keywords` are a list of groups, one per
subject the question names (FlexCache *and* FPolicy, a technical report *and* its topic), each
holding that subject's words in English and Japanese. A hop is signposted when one block attached
to the link contains at least one word **from every group**; one word from a broad union would let
a line about any other subject that shares a generic word (`audit`, `TR`) signpost the question.
A question with one subject has one group. The attached text is the block holding the link, which
always includes the link's visible text:

- in an `llms.txt` (the Hub's or a sibling's), the list item's own line, never the line after it;
- in Markdown, the containing table row, heading, list item with its continuation lines, or
  paragraph. A blank line ends a block; fenced code belongs to none.

Inline links inside the block count by their visible text only; a URL slug is not something a
reader sees. Matching is case-insensitive. An ASCII keyword must stand as a word (`TR` matches
`TR-4572`, not `string` or `TRANSFER`); a keyword with any non-ASCII character is a substring match with
whitespace removed, so a Japanese phrase that wraps across two source lines still matches.

Keywords and their grouping are written from each question's wording and the words a reader would
type, never from the current link text: deriving them from what the pages already say would make
the verdict pass by construction, and grouping them by which paths would then fail is the same
mistake in the other direction. This is still a property of link text, not a run of any model. For a signposted FAIL
whose linked verdict passes, the report names the first unsignposted hop of the reported shortest
linked path; another route may be the easier fix. The signposted crawl only follows hops the linked
crawl already followed, so it fetches nothing of its own, and the same INCONCLUSIVE rule applies to
its own crawl. Without `--signposted` it is reported and does not change the exit status.

Modes and verdicts
------------------
Default (offline, the gate): only `scope == "hub"` questions are evaluated, over the graph of every
tracked Markdown file plus `llms.txt`. Links into sibling repositories are recorded as leaves and
never expanded. Exit 1 iff any evaluated question FAILs. Cross-repo questions are counted as
skipped.

`--external` (opt-in, network): cross-repo questions are evaluated too. A sibling document is
fetched from `raw.githubusercontent.com` only when it is popped at a distance below the budget, so
the crawl depth equals the hop budget, every fetch is cached for the run, and `MAX_FETCHES`
(`--max-fetches`) caps the total. A fetch that answers 404 is a dead end. A 403, 429, any other HTTP
error, a network error or a timeout teaches nothing about the link, and neither does a fetch the cap
skipped. Such a node is *blocked*. An unreached cross-repo question is INCONCLUSIVE only when its own
crawl, the nodes reached from its entry points below the budget, contains a blocked node, or when the
existence fetch of one of its targets was blocked: those are the only places the missing link could
be. A blocked node elsewhere in the run says nothing about this question, so it stays FAIL. This is
the same third verdict `check_links.py` and `check_cross_repo.py --external` use. INCONCLUSIVE alone
exits 0; it is listed under `undetermined:` so it is not read as a pass. The cap is sized so a normal
run stays under it, and the report records whether it was reached.

Parser limits
-------------
Links are parsed with the line loop and the `LINK` / `FENCE` patterns of `check_links.iter_links`,
so this tool and the link gate agree on what a link is: inline `[text](target)` outside fenced code;
image embeds are not edges. Reference-style links
and HTML `<a href>` are not parsed, which is the same limit `check_links.py` has. In a fetched
sibling document, a relative link ending in `/` or without a file suffix, and a `tree/` URL, are read
as that directory's `README.md`, because a directory cannot be distinguished from a file without
listing the tree. That node is a guess, so a 404 on it is an absence rather than a dead link, the
same treatment a repository root's `llms.txt` gets.

Run:  python3 tools/check_reachability.py [--external] [--signposted] [--max-hops N]
                                          [--max-fetches N] [--report PATH]
      python3 tools/check_reachability.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import pairwise
from pathlib import Path
from typing import Self
from urllib.parse import quote, unquote, urlparse

from check_links import ANCHOR, FENCE, LINK, anchors_of, slugify
from frontmatter import iter_markdown

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT / "docs/agent/reachability-questions.json"

MAX_HOPS = 3
# About twice what a full external run of the question set needed when last sized (274 fetches),
# so a normal run stays under it. A run that reaches it says so in its report (`cap_reached`).
MAX_FETCHES = 550
FETCH_TIMEOUT = 30
OWNER = "Yoshiki0705"
THIS_REPO = "FSx-for-ONTAP-Adoption-Playbook"

SCHEMA = "reachability-questions/v3"
REPORT_SCHEMA = "reachability-report/v2"
USER_AGENT = "adoption-playbook-reachability-check"

CATEGORY_PREFIX = {"workload": "wl", "tr": "tr", "spoke-measurement": "sm"}
SCOPES = ("hub", "cross-repo")
QUESTION_REQUIRED = (
    "id",
    "question",
    "keywords",
    "category",
    "scope",
    "targets",
    "rationale",
)
KEYWORD_LANGS = ("en", "ja")
KEYWORD_GROUPS = (1, 4)
KEYWORDS_PER_LANG = (2, 12)
EXCERPT_CHARS = 160
QUESTION_OPTIONAL = ("question_ja", "entry_points")
TARGET_KEYS = ("path", "anchor")
MAX_TARGETS = 8
ID_RE = re.compile(r"^(wl|tr|sm)-[a-z0-9-]+$")
SIBLING_TARGET_RE = re.compile(rf"^{OWNER}/[A-Za-z0-9._-]+:[^:]+$")
# A route is not an answer. Accepting the map or an index as a target would let any question pass
# by naming the page that lists everything, which is padding by another name.
ROUTE_DOCUMENTS = frozenset(
    {"llms.txt", "README.md", "navigation.md", "workload-entry-map.md"}
)

GITHUB_BLOB = re.compile(
    rf"^https?://github\.com/{OWNER}/([A-Za-z0-9._-]+)/(blob|tree)/([^/]+)/(.+)$",
    re.IGNORECASE,
)
GITHUB_ROOT = re.compile(
    rf"^https?://github\.com/{OWNER}/([A-Za-z0-9._-]+?)(?:\.git)?/?$", re.IGNORECASE
)
RAW = re.compile(
    rf"^https?://raw\.githubusercontent\.com/{OWNER}/([A-Za-z0-9._-]+)/([^/]+)/(.+)$",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------------------------
# Question set
# --------------------------------------------------------------------------------------------


def _target_problems(qid: str, scope: str, target: object, entries: list) -> list[str]:
    if not isinstance(target, dict):
        return [f"{qid}: each target must be an object"]
    problems = [
        f"{qid}: unknown target key {key!r}" for key in target if key not in TARGET_KEYS
    ]
    path = target.get("path")
    if not isinstance(path, str) or not path:
        return [*problems, f"{qid}: target needs a non-empty 'path'"]
    if "anchor" in target and (
        not isinstance(target["anchor"], str) or not target["anchor"]
    ):
        problems.append(f"{qid}: target anchor must be a non-empty string")
    if scope == "hub":
        if ":" in path or path.startswith("/") or ".." in path.split("/"):
            problems.append(
                f"{qid}: hub target {path!r} must be a repository-relative path"
            )
        document = path
    else:
        if not SIBLING_TARGET_RE.match(path):
            problems.append(
                f"{qid}: cross-repo target {path!r} must look like {OWNER}/<Repo>:<path>"
            )
        document = path.partition(":")[2]
    if posixpath.basename(document) in ROUTE_DOCUMENTS or path in entries:
        problems.append(
            f"{qid}: {path!r} is a route, not an answer, so it cannot be a target"
        )
    return problems


def _keyword_problems(qid: str, keywords: object) -> list[str]:
    """A short list of groups, each with both languages, and Japanese really Japanese.

    One group per subject of the question: a hop must name every subject, not just one. Counts and
    duplicates are checked per language across all groups, so a keyword sits in exactly one group.
    Duplicates are not checked across languages: a product name such as `FlexCache` is what a reader
    types in either language, so it legitimately appears in both.
    """
    g_low, g_high = KEYWORD_GROUPS
    if (
        not isinstance(keywords, list)
        or not g_low <= len(keywords) <= g_high
        or not all(isinstance(g, dict) for g in keywords)
    ):
        shape = f"each an object with {list(KEYWORD_LANGS)}"
        return [
            f"{qid}: keywords must be a list of {g_low} to {g_high} groups, {shape}"
        ]
    problems: list[str] = []
    flat: dict[str, list[str]] = {lang: [] for lang in KEYWORD_LANGS}
    for n, group in enumerate(keywords, start=1):
        problems += [
            f"{qid}: unknown keywords key {key!r} in group {n}"
            for key in group
            if key not in KEYWORD_LANGS
        ]
        for lang in KEYWORD_LANGS:
            words = group.get(lang)
            if (
                not isinstance(words, list)
                or not words
                or not all(isinstance(w, str) and w.strip() for w in words)
            ):
                problems.append(
                    f"{qid}: group {n} keywords.{lang} must be a non-empty list of "
                    "non-empty strings"
                )
                continue
            flat[lang] += words
    if problems:
        return problems
    low, high = KEYWORDS_PER_LANG
    for lang, words in flat.items():
        if not low <= len(words) <= high:
            problems.append(
                f"{qid}: keywords.{lang} must hold {low} to {high} keywords across groups"
            )
        folded = [w.strip().casefold() for w in words]
        if len(set(folded)) != len(folded):
            problems.append(f"{qid}: keywords.{lang} repeats a keyword (ignoring case)")
        for word in words:
            if word.isascii() and len(word.strip()) < 2:
                problems.append(
                    f"{qid}: ASCII keyword {word!r} is too short to mean anything"
                )
        if lang == "ja" and all(w.isascii() for w in words):
            problems.append(f"{qid}: keywords.ja needs at least one Japanese keyword")
    return problems


def load_questions(path: Path, root: Path | None = None) -> list[dict]:
    """Load and validate the question set. Raise ValueError listing every problem found.

    With `root`, entry points are also required to exist under it. Target existence is not checked
    here: a Hub target is checked by the test suite against the tree, and a sibling target can only
    be checked over the network.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: cannot read question set: {exc}") from exc
    problems: list[str] = []
    if not isinstance(data, dict) or set(data) != {"schema", "questions"}:
        raise ValueError(f"{path}: top level must be exactly {{schema, questions}}")
    if data["schema"] != SCHEMA:
        problems.append(f"schema must be {SCHEMA!r}, got {data['schema']!r}")
    questions = data["questions"]
    if not isinstance(questions, list) or not questions:
        raise ValueError(f"{path}: 'questions' must be a non-empty list")
    seen: set[str] = set()
    for index, q in enumerate(questions):
        if not isinstance(q, dict):
            problems.append(f"question {index}: must be an object")
            continue
        qid = q.get("id", f"question {index}")
        for key in q:
            if key not in QUESTION_REQUIRED + QUESTION_OPTIONAL:
                problems.append(f"{qid}: unknown key {key!r}")
        for key in QUESTION_REQUIRED:
            if key not in q:
                problems.append(f"{qid}: missing required key {key!r}")
        for key in ("question", "rationale", "question_ja"):
            if key in q and (not isinstance(q[key], str) or not q[key].strip()):
                problems.append(f"{qid}: {key!r} must be a non-empty string")
        if "keywords" in q:
            problems += _keyword_problems(qid, q["keywords"])
        if not isinstance(qid, str) or not ID_RE.match(qid):
            problems.append(f"{qid}: id must match {ID_RE.pattern}")
        elif qid in seen:
            problems.append(f"{qid}: duplicate id")
        else:
            seen.add(qid)
        category = q.get("category")
        if category not in CATEGORY_PREFIX:
            problems.append(f"{qid}: category must be one of {sorted(CATEGORY_PREFIX)}")
        elif (
            isinstance(qid, str)
            and ID_RE.match(qid)
            and qid.split("-", 1)[0] != CATEGORY_PREFIX[category]
        ):
            problems.append(
                f"{qid}: id prefix must be {CATEGORY_PREFIX[category]!r} for {category}"
            )
        scope = q.get("scope")
        if scope not in SCOPES:
            problems.append(f"{qid}: scope must be one of {list(SCOPES)}")
        if category == "spoke-measurement" and scope != "cross-repo":
            problems.append(f"{qid}: a spoke-measurement question must be cross-repo")
        entries = q.get("entry_points", ["llms.txt"])
        if (
            not isinstance(entries, list)
            or not entries
            or not all(isinstance(e, str) and e for e in entries)
        ):
            problems.append(f"{qid}: entry_points must be a non-empty list of paths")
            entries = []
        for entry in entries:
            if ":" in entry or entry.startswith("/") or ".." in entry.split("/"):
                problems.append(f"{qid}: entry point {entry!r} must be hub-relative")
            elif root is not None and not (Path(root) / entry).is_file():
                problems.append(f"{qid}: entry point {entry!r} does not exist")
        targets = q.get("targets")
        if not isinstance(targets, list) or not 1 <= len(targets) <= MAX_TARGETS:
            problems.append(f"{qid}: targets must be a list of 1 to {MAX_TARGETS}")
        elif scope in SCOPES:
            for target in targets:
                problems += _target_problems(qid, scope, target, entries)
    if problems:
        raise ValueError("invalid question set:\n  " + "\n  ".join(problems))
    for q in questions:
        q.setdefault("entry_points", ["llms.txt"])
    return questions


# --------------------------------------------------------------------------------------------
# Signposts
# --------------------------------------------------------------------------------------------

TABLE_ROW = re.compile(r"^\s*\|")
HEADING = re.compile(r"^\s*#{1,6}\s")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
QUOTE = re.compile(r"^\s*(?:>\s?)+")
# Inline links and image embeds, replaced by their visible text. The URL is not shown in rendered
# Markdown, and a slug such as `counting-bytes-is-not-counting-files.md` would otherwise signpost
# "files" for free.
INLINE_LINK = re.compile(r"!?\[([^\]]*)\]\([^)\s]+(?:\s+\"[^\"]*\")?\)")


def _clean(lines: list[str]) -> str:
    text = " ".join(lines)
    text = INLINE_LINK.sub(r"\1", text).replace("`", "")
    return " ".join(text.split())


def blocks(text: str, *, llms: bool) -> dict[int, str]:
    """Map each 1-based line number to the cleaned text of the block that contains it.

    A block is what a reader sees around a link: a table row, a heading, a list item (with its lazy
    continuation lines), or a paragraph. A blank line ends any block, and a fence line or a line
    inside a fence belongs to none. In an `llms.txt`, a list item is exactly its own line, because
    llms.txt items are one line each and the paragraph after a list must not be read as part of its
    last item.
    """
    out: dict[int, str] = {}
    current: list[int] = []
    bodies: dict[int, str] = {}
    kind: str | None = None
    in_fence = False

    def flush() -> None:
        if current:
            joined = _clean([bodies[i] for i in current])
            for i in current:
                out[i] = joined
            current.clear()

    for lineno, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            flush()
            kind = None
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        body = QUOTE.sub("", line)
        if not body.strip():
            flush()
            kind = None
            continue
        bodies[lineno] = body
        if TABLE_ROW.match(body) or HEADING.match(body):
            flush()
            kind = None
            out[lineno] = _clean([body])
            continue
        if LIST_ITEM.match(body):
            flush()
            current.append(lineno)
            kind = "item"
            if llms:
                flush()
                kind = None
            continue
        if kind is None:
            kind = "paragraph"
        current.append(lineno)
    flush()
    return out


def iter_signposts(text: str, *, llms: bool) -> Iterable[tuple[str, str]]:
    """Yield (target, attached block text) for every inline link outside fenced code.

    The line loop and the two regexes are the ones `check_links.iter_links` uses, so this tool and
    the link gate agree on what a link is; only the attached text is added.
    """
    attached = blocks(text, llms=llms)
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in LINK.finditer(line):
            yield match.group(1), attached.get(lineno, "")


def _is_llms(node: str) -> bool:
    """True for the Hub's llms.txt or a sibling's (`Owner/Repo:llms.txt`)."""
    return posixpath.basename(node.rpartition(":")[2]) == "llms.txt"


def group_matchers(keywords: list[dict]) -> list[Callable[[str], bool]]:
    """One predicate per keyword group, each true when a text contains one of the group's words.

    Case-insensitive. An ASCII keyword must stand as a word, so `TR` matches `TR-4572` and `TR `
    but not `string`, `TRANSFER` or `STRUCTURE`, and its spaces match any whitespace. A keyword
    with any non-ASCII character is a plain substring with all whitespace removed on both sides,
    because Japanese has no word boundaries and a phrase may wrap across two source lines.
    """
    return [_group_matcher(group) for group in keywords]


def matcher(keywords: list[dict]) -> Callable[[str], bool]:
    """A predicate that is true when a text names every subject: one word from each group."""
    groups = group_matchers(keywords)

    def match(text: str) -> bool:
        return all(group(text) for group in groups)

    return match


def _group_matcher(group: dict) -> Callable[[str], bool]:
    patterns: list[re.Pattern[str]] = []
    phrases: list[str] = []
    for word in (*group["en"], *group["ja"]):
        word = word.strip().casefold()
        if word.isascii():
            body = r"\s+".join(re.escape(part) for part in word.split())
            pattern = rf"(?<![a-z0-9]){body}(?![a-z0-9])"
            patterns.append(re.compile(pattern))
        else:
            phrases.append("".join(word.split()))

    def match(text: str) -> bool:
        folded = text.casefold()
        if any(p.search(folded) for p in patterns):
            return True
        squeezed = "".join(folded.split())
        return any(phrase in squeezed for phrase in phrases)

    return match


def _hop_signposted(
    signs: dict[tuple[str, str], list[str]],
    match: Callable[[str], bool],
    source: str,
    target: str,
) -> bool:
    """A hop is signposted when one occurrence of the link sits in a block naming every subject.

    The groups must all match within one block: one subject named beside one occurrence of the link
    and another beside a different occurrence is two half-signposts, not one.
    """
    return any(match(block) for block in signs.get((source, target), ()))


# --------------------------------------------------------------------------------------------
# Graph
# --------------------------------------------------------------------------------------------


def _sibling(repo: str, path: str) -> str:
    return f"{OWNER}/{repo}:{path}"


def split_sibling(node: str) -> tuple[str, str] | None:
    """Return (repo, path) for a sibling node id, or None for a Hub node."""
    if ":" not in node:
        return None
    head, _, path = node.partition(":")
    return head.partition("/")[2], path


class _Names:
    """Canonical display case for repository names. GitHub resolves names case-insensitively."""

    def __init__(self, known: Iterable[str] = ()) -> None:
        self._by_lower: dict[str, str] = {}
        for name in (THIS_REPO, *known):
            self._by_lower.setdefault(name.lower(), name)

    def __call__(self, name: str) -> str:
        return self._by_lower.setdefault(name.lower(), name)


_DEFAULT_NAMES = _Names()


def _hub_path(root: Path, raw: str | Path) -> str | None:
    """A repository-relative path that exists, with a directory resolved to its README.

    `root` must already be resolved. `raw` may be relative to it or absolute.
    """
    candidate = (root / raw).resolve()
    try:
        rel = candidate.relative_to(root)
    except ValueError:
        return None
    if candidate.is_dir():
        readme = candidate / "README.md"
        return (rel / "README.md").as_posix() if readme.is_file() else None
    return rel.as_posix() if candidate.is_file() else None


def _sibling_path(joined: str, trailing_slash: bool) -> tuple[str, bool] | None:
    """A normalized path inside a sibling repository, and whether a directory README was guessed.

    A directory cannot be told from a file without listing the tree, so a path ending in `/` or
    without a file suffix is read as that directory's README. The guess is speculative: a 404 on it
    means "no README there", not a dead link.
    """
    path = posixpath.normpath(joined).lstrip("/")
    if path in (".", ""):
        return "README.md", True
    if path.startswith(".."):
        return None
    if trailing_slash or not posixpath.splitext(posixpath.basename(path))[1]:
        return posixpath.join(path, "README.md"), True
    return path, False


def _normalize(
    source: str, target: str, root: Path, names: _Names = _DEFAULT_NAMES
) -> list[tuple[str, str | None, bool]]:
    """Resolve one link to (node, ref, speculative) triples. ref is None for Hub nodes."""
    root = root.resolve()
    target = target.strip("<>")
    parsed = urlparse(target)
    if parsed.scheme in ("http", "https"):
        url = target.split("#", 1)[0].split("?", 1)[0]
        match = GITHUB_BLOB.match(url)
        if match:
            repo, kind, ref, path = match.groups()
            path = unquote(path)
            tree = kind.lower() == "tree"
            if tree:
                path = posixpath.join(path.rstrip("/"), "README.md")
            repo = names(repo)
            if repo.lower() == THIS_REPO.lower():
                node = _hub_path(root, path)
                return [(node, None, False)] if node else []
            return [(_sibling(repo, path), ref, tree)]
        match = RAW.match(url)
        if match:
            repo, ref, path = match.groups()
            repo = names(repo)
            if repo.lower() == THIS_REPO.lower():
                node = _hub_path(root, unquote(path))
                return [(node, None, False)] if node else []
            return [(_sibling(repo, unquote(path)), ref, False)]
        match = GITHUB_ROOT.match(url)
        if match:
            repo = names(match.group(1))
            if repo.lower() == THIS_REPO.lower():
                return [
                    (node, None, False)
                    for node in (
                        _hub_path(root, "README.md"),
                        _hub_path(root, "llms.txt"),
                    )
                    if node
                ]
            # A repository root lands on its README, and an agent there can read the root
            # llms.txt. That is how sibling llms.txt files enter the graph; the second is
            # speculative, because not every sibling publishes one.
            return [
                (_sibling(repo, "README.md"), "HEAD", False),
                (_sibling(repo, "llms.txt"), "HEAD", True),
            ]
        return []
    if parsed.scheme:
        return []
    raw = unquote(target.split("#", 1)[0])
    if not raw:
        return []
    sibling = split_sibling(source)
    if sibling is None:
        base = root if raw.startswith("/") else (root / source).parent
        node = _hub_path(root, base / raw.lstrip("/"))
        return [(node, None, False)] if node else []
    repo, source_path = sibling
    joined = (
        raw
        if raw.startswith("/")
        else posixpath.join(posixpath.dirname(source_path), raw)
    )
    resolved = _sibling_path(joined, raw.endswith("/"))
    if resolved is None:
        return []
    return [(_sibling(repo, resolved[0]), None, resolved[1])]


def normalize_link(source_node: str, target: str, root: Path) -> list[str]:
    """Resolve one link found in `source_node` to the 0 to 2 node ids it leads to."""
    return [node for node, _, _ in _normalize(source_node, target, Path(root))]


def _hub_sources(root: Path) -> list[Path]:
    extra = [root / "llms.txt"] if (root / "llms.txt").is_file() else []
    return [*iter_markdown(root), *extra]


Signs = dict[tuple[str, str], list[str]]


def _build(
    root: Path, names: _Names
) -> tuple[dict[str, set[str]], dict[str, str], dict[str, bool], Signs]:
    """The Hub graph, the ref each sibling node was first linked at, which nodes were only ever
    guessed (a 404 on those is an absence, not a dead link), and the block text attached to every
    occurrence of every edge."""
    root = root.resolve()
    graph: dict[str, set[str]] = {}
    refs: dict[str, str] = {}
    guessed: dict[str, bool] = {}
    signs: Signs = {}
    for path in _hub_sources(root):
        source = path.relative_to(root).as_posix()
        edges = graph.setdefault(source, set())
        text = path.read_text(encoding="utf-8")
        for target, block in iter_signposts(text, llms=_is_llms(source)):
            for node, ref, spec in _normalize(source, target, root, names):
                if node == source:
                    continue
                edges.add(node)
                signs.setdefault((source, node), []).append(block)
                if ref is not None:
                    refs.setdefault(node, ref)
                guessed[node] = guessed.get(node, True) and spec
    return graph, refs, guessed, signs


def build_hub_graph(root: Path) -> dict[str, set[str]]:
    """Every tracked Markdown file plus llms.txt, mapped to the nodes it links to."""
    return _build(Path(root), _Names())[0]


def bfs(
    entry_nodes: Iterable[str],
    neighbors: Callable[[str], Iterable[str]],
    max_hops: int | None,
    expand_if: Callable[[str, int], bool],
) -> dict[str, tuple[int, str | None]]:
    """Shortest hop count from any entry node. Returns {node: (hops, parent)}.

    `max_hops=None` is unbounded, so a target beyond the budget still gets its true distance. A node
    is expanded only when `expand_if(node, hops)` is true, which is how sibling documents stay leaves
    offline and are fetched only below the budget with --external.
    """
    seen: dict[str, tuple[int, str | None]] = {}
    queue: deque[str] = deque()
    for node in entry_nodes:
        if node not in seen:
            seen[node] = (0, None)
            queue.append(node)
    while queue:
        node = queue.popleft()
        hops = seen[node][0]
        if max_hops is not None and hops >= max_hops:
            continue
        if not expand_if(node, hops):
            continue
        for nxt in sorted(neighbors(node)):
            if nxt not in seen:
                seen[nxt] = (hops + 1, node)
                queue.append(nxt)
    return seen


def verdict_for(hops: int | None, max_hops: int) -> str:
    """PASS iff the target was reached within the budget. Unreached is never a pass."""
    if hops is not None and hops <= max_hops:
        return "PASS"
    return "FAIL"


# --------------------------------------------------------------------------------------------
# External fetching
# --------------------------------------------------------------------------------------------


def _text_anchors(text: str) -> set[str]:
    found: set[str] = set()
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = ANCHOR.match(line)
        if match:
            found.add(slugify(match.group(2)))
        for named in re.finditer(r'(?:id|name)="([^"]+)"', line):
            found.add(named.group(1).lower())
    return found


@dataclass
class _Fetcher:
    opener: Callable
    max_fetches: int
    attempted: int = 0
    cached_hits: int = 0
    cap_reached: bool = False
    cache: dict[str, str | None] = field(default_factory=dict)
    inconclusive: list[dict] = field(default_factory=list)
    dead: list[str] = field(default_factory=list)
    absent: set[str] = field(default_factory=set)
    # Nodes whose content is unknown: the cap skipped them or the server did not answer. Kept per
    # node so a verdict can ask whether *its own* crawl was blocked, not whether anything was.
    blocked: dict[str, str] = field(default_factory=dict)

    def get(self, node: str, ref: str, speculative: bool) -> str | None:
        """Return the document text, or None for a dead end or an undetermined fetch."""
        repo, path = split_sibling(node)  # type: ignore[misc]
        url = f"https://raw.githubusercontent.com/{OWNER}/{repo}/{ref}/{quote(path)}"
        if url in self.cache:
            self.cached_hits += 1
            return self.cache[url]
        if self.attempted >= self.max_fetches:
            self.cap_reached = True
            self.blocked.setdefault(node, "skipped by the fetch cap")
            return None
        self.attempted += 1
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        text: str | None = None
        try:
            with self.opener(request, timeout=FETCH_TIMEOUT) as response:
                text = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            exc.close()
            if exc.code == 404:
                if speculative:
                    self.absent.add(node)  # no llms.txt there; not a dead link
                else:
                    self.dead.append(node)
            else:
                self.inconclusive.append({"node": node, "reason": f"HTTP {exc.code}"})
                self.blocked[node] = f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            self.inconclusive.append({"node": node, "reason": f"unreachable ({exc})"})
            self.blocked[node] = "unreachable"
        self.cache[url] = text
        return text


# --------------------------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------------------------


@dataclass
class Result:
    mode: str
    max_hops: int
    results: list[dict]
    counts: dict[str, int]
    max_fetches: int = MAX_FETCHES
    fetch: dict | None = None
    signposted_counts: dict[str, int] = field(
        default_factory=lambda: {"pass": 0, "fail": 0, "inconclusive": 0, "skipped": 0}
    )


def _path_to(seen: dict[str, tuple[int, str | None]], node: str) -> list[str]:
    chain: list[str] = []
    current: str | None = node
    while current is not None:
        chain.append(current)
        current = seen[current][1]
    return list(reversed(chain))


def _nearest(seen: dict[str, tuple[int, str | None]], target: str) -> dict | None:
    """The closest reached README in a directory enclosing the target, as a pointer for the fix."""
    prefix, _, path = target.rpartition(":")
    prefix = f"{prefix}:" if prefix else ""
    directory = posixpath.dirname(path)
    while True:
        candidate = prefix + posixpath.join(directory, "README.md")
        if candidate in seen:
            return {"node": candidate, "hops": seen[candidate][0]}
        if not directory:
            return None
        directory = posixpath.dirname(directory)


def evaluate(
    questions: list[dict],
    root: Path,
    *,
    external: bool = False,
    max_hops: int = MAX_HOPS,
    max_fetches: int | None = None,
    opener: Callable = urllib.request.urlopen,
) -> Result:
    """Evaluate every question in scope for the mode. Hub questions always use the Hub graph only.

    `max_fetches=None` means `MAX_FETCHES`, read at call time so a test can lower the module value.
    """
    if max_fetches is None:
        max_fetches = MAX_FETCHES
    root = Path(root).resolve()
    known = [
        split_sibling(t["path"])[0]  # type: ignore[index]
        for q in questions
        if q["scope"] == "cross-repo"
        for t in q["targets"]
    ]
    names = _Names(known)
    graph, refs, guessed, signs = _build(root, names)
    fetcher = _Fetcher(opener, max_fetches) if external else None
    fetched: dict[str, set[str]] = {}
    texts: dict[str, str | None] = {}

    def hub_neighbors(node: str) -> set[str]:
        return graph.get(node, set())

    def sibling_text(node: str) -> str | None:
        assert fetcher is not None
        if node not in texts:
            texts[node] = fetcher.get(
                node, refs.get(node, "HEAD"), guessed.get(node, False)
            )
        return texts[node]

    def ext_neighbors(node: str) -> set[str]:
        if split_sibling(node) is None:
            return graph.get(node, set())
        if node in fetched:
            return fetched[node]
        text = sibling_text(node)
        edges: set[str] = set()
        for target, block in iter_signposts(text or "", llms=_is_llms(node)):
            for nxt, ref, spec in _normalize(node, target, root, names):
                if nxt == node:
                    continue
                edges.add(nxt)
                signs.setdefault((node, nxt), []).append(block)
                refs.setdefault(nxt, ref if ref is not None else refs.get(node, "HEAD"))
                guessed[nxt] = guessed.get(nxt, True) and spec
        fetched[node] = edges
        return edges

    def judge(
        q: dict, seen: dict[str, tuple[int, str | None]]
    ) -> tuple[str, int | None, tuple[int, str] | None, list[str]]:
        """Verdict, hop count, best target and reasons for one crawl of one question.

        The linked and the signposted crawl go through the same target checks and the same
        INCONCLUSIVE rule; only `seen` differs.
        """
        best: tuple[int, str] | None = None
        reasons: list[str] = []
        blocked_targets: list[str] = []
        for target in q["targets"]:
            node = target["path"]
            if split_sibling(node) is not None:
                repo, path = split_sibling(node)  # type: ignore[misc]
                node = _sibling(names(repo), path)
            if node not in seen:
                reasons.append(f"{target['path']}: not reached")
                continue
            hops = seen[node][0]
            text: str | None = None
            if (
                fetcher is not None
                and split_sibling(node) is not None
                and hops <= max_hops
            ):
                # Reaching a link is not reaching a document. A target below the budget was
                # fetched when the crawl expanded it; one at exactly the budget is fetched here,
                # so "reached" always means "exists" and never only "linked".
                text = sibling_text(node)
                if text is None:
                    if node in fetcher.blocked:
                        blocked_targets.append(node)
                        reasons.append(
                            f"{target['path']}: existence not determined "
                            f"({fetcher.blocked[node]})"
                        )
                    else:
                        reasons.append(f"{target['path']}: link leads to a 404")
                    continue
            anchor = target.get("anchor")
            if anchor and hops <= max_hops:
                if split_sibling(node) is None:
                    anchors = anchors_of(root / node)
                else:
                    anchors = _text_anchors(text or "")
                if slugify(anchor) not in anchors:
                    reasons.append(f"{target['path']}: anchor #{anchor} not found")
                    continue
            if best is None or hops < best[0]:
                best = (hops, node)
        hops = best[0] if best else None
        verdict = verdict_for(hops, max_hops)
        if verdict == "FAIL" and q["scope"] == "cross-repo" and fetcher is not None:
            # Only this question's own crawl can hide its missing link: a node it reached below
            # the budget whose links are unknown, or a target whose existence is unknown. A cap
            # hit or an unanswered fetch anywhere else in the run teaches nothing about it.
            frontier = sorted(
                n for n, (h, _) in seen.items() if h < max_hops and n in fetcher.blocked
            )
            if frontier or blocked_targets:
                verdict = "INCONCLUSIVE"
                shown = ", ".join(f"{n} ({fetcher.blocked[n]})" for n in frontier[:3])
                more = f" and {len(frontier) - 3} more" if len(frontier) > 3 else ""
                if frontier:
                    reasons.append(
                        f"crawl blocked at {shown}{more}, so the unreached branch was not "
                        "measured"
                    )
        return verdict, hops, best, reasons

    hub_runs: dict[tuple[str, ...], dict] = {}
    ext_runs: dict[tuple[str, ...], dict] = {}
    results: list[dict] = []
    counts = {"pass": 0, "fail": 0, "inconclusive": 0, "skipped": 0}
    signposted_counts = dict.fromkeys(counts, 0)

    def hub_expand(node: str, hops: int) -> bool:
        return True

    def ext_expand(node: str, hops: int) -> bool:
        # Hub nodes expand without bound so a distance beyond the budget is still reported; a
        # sibling node is fetched only below the budget.
        return split_sibling(node) is None or hops < max_hops

    for q in questions:
        entries = tuple(q["entry_points"])
        if q["scope"] == "cross-repo" and not external:
            counts["skipped"] += 1
            signposted_counts["skipped"] += 1
            continue
        if q["scope"] == "hub":
            neighbors, expand = hub_neighbors, hub_expand
            if entries not in hub_runs:
                hub_runs[entries] = bfs(entries, neighbors, None, expand)
            seen = hub_runs[entries]
        else:
            assert fetcher is not None
            neighbors, expand = ext_neighbors, ext_expand
            if entries not in ext_runs:
                ext_runs[entries] = bfs(entries, neighbors, None, expand)
            seen = ext_runs[entries]

        verdict, hops, best, reasons = judge(q, seen)
        entry = {
            "id": q["id"],
            "category": q["category"],
            "scope": q["scope"],
            "verdict": verdict,
            "hops": hops,
            "path": _path_to(seen, best[1]) if best else [],
            "reason": "; ".join(reasons) if verdict != "PASS" else "",
        }
        if verdict == "FAIL" and best is None:
            nearest = [
                n for n in (_nearest(seen, t["path"]) for t in q["targets"]) if n
            ]
            entry["nearest"] = (
                min(nearest, key=lambda n: n["hops"]) if nearest else None
            )
        entry["signposted"] = _signposted_run(q, entry, judge, neighbors, expand, signs)
        results.append(entry)
        counts[verdict.lower()] += 1
        signposted_counts[entry["signposted"]["verdict"].lower()] += 1

    fetch = None
    if fetcher is not None:
        fetch = {
            "attempted": fetcher.attempted,
            "cached_hits": fetcher.cached_hits,
            "inconclusive": fetcher.inconclusive,
            "dead_nodes": sorted(set(fetcher.dead)),
            "cap_reached": fetcher.cap_reached,
        }
    return Result(
        mode="external" if external else "hub",
        max_hops=max_hops,
        results=results,
        counts=counts,
        max_fetches=max_fetches,
        fetch=fetch,
        signposted_counts=signposted_counts,
    )


def _first_unsignposted(
    path: list[str], signs: Signs, keywords: list[dict]
) -> dict | None:
    """The first hop of `path` whose attached text does not name every subject.

    `unmatched` lists, by the first English keyword of each, the groups the hop's first block does
    not name. This is a pointer along the one shortest linked path reported, not the only place a
    fix could go: another route may be easier to signpost.
    """
    match = matcher(keywords)
    groups = group_matchers(keywords)
    for hop, (source, target) in enumerate(pairwise(path), start=1):
        if not _hop_signposted(signs, match, source, target):
            first = signs.get((source, target), [""])[0]
            return {
                "hop": hop,
                "from": source,
                "to": target,
                "unmatched": [
                    g["en"][0]
                    for g, ok in zip(keywords, groups, strict=True)
                    if not ok(first)
                ],
                "excerpt": first[:EXCERPT_CHARS],
            }
    return None


def _signposted_run(
    q: dict,
    linked: dict,
    judge: Callable,
    neighbors: Callable[[str], Iterable[str]],
    expand: Callable[[str, int], bool],
    signs: Signs,
) -> dict:
    """The same crawl as the linked one, following only hops whose attached text names the subject.

    Every node this crawl expands was reached at least as early by the linked crawl, so its
    document was already fetched: the signposted verdict costs no fetch of its own.
    """
    match = matcher(q["keywords"])

    def signposted_neighbors(node: str) -> set[str]:
        return {
            nxt for nxt in neighbors(node) if _hop_signposted(signs, match, node, nxt)
        }

    seen = bfs(q["entry_points"], signposted_neighbors, None, expand)
    verdict, hops, best, reasons = judge(q, seen)
    if verdict == "PASS" and linked["verdict"] != "PASS":
        raise AssertionError(
            f"{q['id']}: signposted PASS without a linked PASS; the crawls disagree"
        )
    missing = None
    if verdict != "PASS" and linked["verdict"] == "PASS":
        missing = _first_unsignposted(linked["path"], signs, q["keywords"])
    lead: list[str] = []
    if missing:
        lead.append(
            f"missing at hop {missing['hop']}: {missing['from']} -> {missing['to']}"
        )
    elif verdict != "PASS" and linked["verdict"] != "PASS":
        lead.append("target not linked within the budget")
    return {
        "verdict": verdict,
        "hops": hops,
        "path": _path_to(seen, best[1]) if best else [],
        "missing": missing,
        "reason": "; ".join(lead + reasons) if verdict != "PASS" else "",
    }


# --------------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------------


def format_result(result: Result) -> str:
    lines: list[str] = []
    undetermined: list[str] = []
    for r in result.results:
        hops = "none" if r["hops"] is None else str(r["hops"])
        label = {"PASS": "PASS", "FAIL": "FAIL", "INCONCLUSIVE": "? INCONCLUSIVE"}[
            r["verdict"]
        ]
        if r["path"]:
            where = " -> ".join(r["path"])
        elif r.get("nearest"):
            where = f"nearest: {r['nearest']['node']} (hops={r['nearest']['hops']})"
        else:
            where = "nearest: n/a"
        lines.append(f"{label}  {r['id']}  hops={hops}  {where}")
        if r["verdict"] == "INCONCLUSIVE":
            undetermined.append(f"  ? {r['id']}: {r['reason']}")
        s = r["signposted"]
        s_hops = "none" if s["hops"] is None else str(s["hops"])
        s_label = {"PASS": "PASS", "FAIL": "FAIL", "INCONCLUSIVE": "? INCONCLUSIVE"}[
            s["verdict"]
        ]
        if s["verdict"] == "PASS":
            s_where = " -> ".join(s["path"])
        elif s["missing"]:
            m = s["missing"]
            s_where = f"missing at hop {m['hop']}: {m['from']} -> {m['to']}"
        elif s["verdict"] == "INCONCLUSIVE":
            s_where = s["reason"]
        else:
            s_where = "target not linked within the budget"
        lines.append(f"  signposted {s_label}  hops={s_hops}  {s_where}")
        if s["verdict"] == "INCONCLUSIVE":
            undetermined.append(f"  ? {r['id']} (signposted): {s['reason']}")
    if result.fetch and result.fetch["inconclusive"]:
        for item in result.fetch["inconclusive"]:
            undetermined.append(f"  ? fetch {item['node']}: {item['reason']}")
    if undetermined:
        lines.append(
            "undetermined: (the server did not answer; nothing learned about these)"
        )
        lines += undetermined
    if result.fetch is not None:
        f = result.fetch
        cap = ", cap reached" if f["cap_reached"] else ""
        lines.append(
            f"fetch: {f['attempted']} attempted (cap {result.max_fetches}{cap}), "
            f"{f['cached_hits']} cached, {len(f['dead_nodes'])} dead link(s), "
            f"{len(f['inconclusive'])} undetermined"
        )
        for node in f["dead_nodes"]:
            lines.append(f"  dead: {node}")
    c = result.counts
    hint = " (cross-repo; run with --external)" if result.mode == "hub" else ""
    sc = result.signposted_counts
    lines.append(
        f"signposted: {sc['pass']} pass, {sc['fail']} fail, "
        f"{sc['inconclusive']} inconclusive, {sc['skipped']} skipped"
    )
    lines.append(
        f"reachability: {c['pass']} pass, {c['fail']} fail, {c['inconclusive']} inconclusive, "
        f"{c['skipped']} skipped{hint}, "
        f"budget <={result.max_hops} hop(s), mode {result.mode}"
    )
    return "\n".join(lines)


def _git_sha(root: Path) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def build_report(
    result: Result, root: Path, questions_file: Path, *, gate: str = "linked"
) -> dict:
    """The run as JSON. `gate` records which verdict decided the exit status (`--signposted`)."""
    root = Path(root).resolve()
    questions_file = Path(questions_file).resolve()
    try:
        shown = questions_file.relative_to(root).as_posix()
    except ValueError:
        shown = str(questions_file)
    report = {
        "schema": REPORT_SCHEMA,
        "run_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": _git_sha(root),
        "mode": result.mode,
        "max_hops": result.max_hops,
        "max_fetches": result.max_fetches,
        "questions_file": shown,
        "questions_sha256": hashlib.sha256(questions_file.read_bytes()).hexdigest(),
        "counts": result.counts,
        "signposted_counts": result.signposted_counts,
        "gate": gate,
        # Present in every mode, so a reader never has to infer the count from an absent key:
        # the offline mode fetches nothing.
        "fetch": result.fetch
        or {
            "attempted": 0,
            "cached_hits": 0,
            "inconclusive": [],
            "dead_nodes": [],
            "cap_reached": False,
        },
        "results": [
            {
                k: r[k]
                for k in (
                    "id",
                    "category",
                    "scope",
                    "verdict",
                    "hops",
                    "path",
                    "reason",
                )
            }
            | ({"nearest": r["nearest"]} if "nearest" in r else {})
            | {"signposted": r["signposted"]}
            for r in result.results
        ],
    }
    return report


# --------------------------------------------------------------------------------------------
# Selftest
# --------------------------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")
        self.status = 200

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _fake_opener(status: int, body: str = "") -> Callable:
    def opener(request: urllib.request.Request, timeout: float = 0) -> _FakeResponse:
        if status == 200:
            return _FakeResponse(body)
        raise urllib.error.HTTPError(request.full_url, status, "fake", None, None)  # type: ignore[arg-type]

    return opener


def _paths_opener(bodies: dict[str, str]) -> Callable:
    """200 with the body for a path ending in a key of `bodies`, 404 for anything else."""

    def opener(request: urllib.request.Request, timeout: float = 0) -> _FakeResponse:
        for suffix, body in bodies.items():
            if request.full_url.endswith("/" + suffix):
                return _FakeResponse(body)
        raise urllib.error.HTTPError(request.full_url, 404, "fake", None, None)  # type: ignore[arg-type]

    return opener


def selftest() -> int:
    """A truth table in a temporary tree. The gate proves it can fail before it is trusted."""
    failures: list[str] = []
    cases = 0

    def check(name: str, ok: bool) -> None:
        nonlocal cases
        cases += 1
        if not ok:
            failures.append(name)

    def q(qid: str, target: str, scope: str = "hub") -> dict:
        return {
            "id": qid,
            "question": "q",
            "keywords": [
                {"en": ["FlexCache", "cache"], "ja": ["キャッシュ", "整合性"]}
            ],
            "category": "workload" if scope == "hub" else "spoke-measurement",
            "scope": scope,
            "targets": [{"path": target}],
            "rationale": "selftest",
            "entry_points": ["llms.txt"],
        }

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "dir").mkdir()
        files = {
            "llms.txt": "[a](a.md)\n[dir](dir)\n```text\n[f](f.md)\n```\n"
            f"[s](https://github.com/{OWNER}/Sib/blob/main/docs/x.md)\n",
            "a.md": "[b](b.md)\n",
            "b.md": "[c](c.md)\n",
            "c.md": "[d](d.md)\n",
            "d.md": "end\n",
            "e.md": "orphan\n",
            "f.md": "only linked from a fence\n",
            "dir/README.md": "dir\n",
        }
        for name, body in files.items():
            (root / name).write_text(body, encoding="utf-8")
        graph = build_hub_graph(root)
        check("fenced link is not an edge", "f.md" not in graph["llms.txt"])
        check("directory link resolves to README", "dir/README.md" in graph["llms.txt"])
        seen = bfs(["llms.txt"], lambda n: graph.get(n, set()), None, lambda n, h: True)
        check("b is two hops", seen.get("b.md", (None,))[0] == 2)
        result = evaluate(
            [q("wl-b", "b.md"), q("wl-d", "d.md"), q("wl-e", "e.md")], root
        )
        by_id = {r["id"]: r for r in result.results}
        check("b passes", by_id["wl-b"]["verdict"] == "PASS")
        check(
            "d at four hops fails at budget three",
            by_id["wl-d"]["verdict"] == "FAIL" and by_id["wl-d"]["hops"] == 4,
        )
        check(
            "orphan fails with no hops",
            by_id["wl-e"]["verdict"] == "FAIL" and by_id["wl-e"]["hops"] is None,
        )
        sib = q("sm-x", f"{OWNER}/Sib:docs/y.md", "cross-repo")
        for status, expected in ((200, "PASS"), (404, "FAIL"), (403, "INCONCLUSIVE")):
            ext = evaluate(
                [sib], root, external=True, opener=_fake_opener(status, "[y](y.md)\n")
            )
            check(
                f"external {status} -> {expected}",
                ext.results[0]["verdict"] == expected,
            )
        # docs/y.md sits at hop 2; with a budget of 2 the crawl never opens it, so only the
        # existence fetch can tell a link from a document.
        for bodies, expected in (
            ({"docs/x.md": "[y](y.md)\n", "docs/y.md": "y\n"}, "PASS"),
            ({"docs/x.md": "[y](y.md)\n"}, "FAIL"),
        ):
            ext = evaluate(
                [sib], root, external=True, max_hops=2, opener=_paths_opener(bodies)
            )
            check(
                f"target at the budget, {'present' if 'docs/y.md' in bodies else '404'} "
                f"-> {expected}",
                ext.results[0]["verdict"] == expected,
            )
        # The cap is hit by another entry point's crawl after this question's own crawl was
        # fully fetched (x.md is cached), so the unreached target is a FAIL.
        (root / "other.md").write_text(
            f"[s](https://github.com/{OWNER}/Sib/blob/main/docs/x.md)\n"
            f"[u](https://github.com/{OWNER}/Sib/blob/main/docs/z1.md)\n"
            f"[v](https://github.com/{OWNER}/Sib/blob/main/docs/z2.md)\n",
            encoding="utf-8",
        )
        capped = evaluate(
            [{**sib, "id": "sm-o", "entry_points": ["other.md"]}, sib],
            root,
            external=True,
            max_fetches=2,
            opener=_paths_opener({"docs/x.md": "x\n", "docs/z1.md": "z\n"}),
        )
        verdicts = [r["verdict"] for r in capped.results]
        check(
            "cap on another crawl -> FAIL; cap on own crawl -> INCONCLUSIVE",
            verdicts == ["INCONCLUSIVE", "FAIL"] and capped.fetch["cap_reached"],  # type: ignore[index]
        )

    # Signposted: the same link, once with its llms.txt description naming the subject and once
    # with the subject only in a neighboring paragraph.
    for llms, expected in (
        ("- [Note](a.md): how FlexCache stays consistent\n", "PASS"),
        ("- [Note](a.md): overview\nFlexCache is described here.\n", "FAIL"),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "llms.txt").write_text(llms, encoding="utf-8")
            (root / "a.md").write_text("a\n", encoding="utf-8")
            r = evaluate([q("wl-a", "a.md")], root).results[0]
            check(
                f"linked PASS, signposted {expected}",
                r["verdict"] == "PASS" and r["signposted"]["verdict"] == expected,
            )

    # Two subjects: a line naming only one of them is not a signpost for the question.
    two = [
        {"en": ["FlexCache", "cache"], "ja": ["キャッシュ"]},
        {"en": ["FPolicy"], "ja": ["FPolicy", "ポリシー"]},
    ]
    for llms, expected in (
        ("- [Note](a.md): FPolicy on a FlexCache cache\n", "PASS"),
        ("- [Note](a.md): FPolicy on an origin volume\n", "FAIL"),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "llms.txt").write_text(llms, encoding="utf-8")
            (root / "a.md").write_text("a\n", encoding="utf-8")
            r = evaluate([{**q("wl-a", "a.md"), "keywords": two}], root).results[0]
            check(
                f"two groups, signposted {expected}",
                r["signposted"]["verdict"] == expected,
            )

    for name in failures:
        print(f"selftest FAILED: {name}", file=sys.stderr)
    if failures:
        return 1
    print(f"selftest: {cases} case(s) passed")
    return 0


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure question-to-document reachability from llms.txt."
    )
    parser.add_argument(
        "--external",
        action="store_true",
        help="also evaluate cross-repo questions (network)",
    )
    parser.add_argument(
        "--max-hops",
        type=_positive,
        default=MAX_HOPS,
        help=f"hop budget (default {MAX_HOPS})",
    )
    parser.add_argument(
        "--max-fetches",
        type=_positive,
        default=None,
        help=f"cap on sibling fetches with --external (default {MAX_FETCHES})",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        help="question set (default docs/agent/reachability-questions.json under --root)",
    )
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument(
        "--signposted",
        action="store_true",
        help="exit non-zero when any question in scope is not signposted",
    )
    parser.add_argument("--report", type=Path, help="write a JSON report here")
    parser.add_argument(
        "--selftest", action="store_true", help="run the built-in truth table"
    )
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    root = args.root.resolve()
    questions_file = args.questions or (root / "docs/agent/reachability-questions.json")
    try:
        questions = load_questions(questions_file, root)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    result = evaluate(
        questions,
        root,
        external=args.external,
        max_hops=args.max_hops,
        max_fetches=args.max_fetches,
    )
    print(format_result(result))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                build_report(
                    result,
                    root,
                    questions_file,
                    gate="signposted" if args.signposted else "linked",
                ),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    if result.counts["fail"]:
        return 1
    return 1 if args.signposted and result.signposted_counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
