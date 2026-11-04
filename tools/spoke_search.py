#!/usr/bin/env python3
"""Search what the sibling repositories (Spokes) have already investigated.

The failure this exists for: a note called a behaviour "unverified" while a Spoke had already
investigated it, in a feature request, an evidence ledger and a verification record. The writer,
an agent, did not know to look, and the human who did know was being asked to remember.
Remembering is not a mechanism. This is.

What it searches, and what it deliberately does not:

* **Committed content at a ref** (default ``origin/main``), through ``git grep <ref>``. Never a
  working copy. A grep across ``~/Projects/*`` reads whatever each checkout happens to hold, a
  stale branch or a half-edited file, and reports it as the repository's state.
* **A ref that is current.** A search that reads a month-old ``origin/main`` and answers "no
  match" is the failure again, so an explicit search runs ``git fetch origin <branch>`` first for
  every repository not fetched within the hour. Only remote-tracking refs move; no checkout,
  merge or local branch is touched. ``--no-fetch`` skips it, and the output says which
  repositories were not refreshed, because "no match" in those is weaker.
* **Every Spoke it can find**, not a list someone has to keep current. A Spoke is a local clone
  whose ``origin`` has the same owner as the repository you are standing in. Worktrees of one
  repository share a git directory and are counted once; two clones of one GitHub repository
  are counted once, the newer ``origin/main`` winning.
* **Not ``.private/``.** That area is untracked, so ``git grep`` of a ref cannot reach it, and
  it holds vendor correspondence that must not become the basis of a published claim.

Output puts the files most likely to hold a *decision* first (evidence ledgers, feature
requests, verification records, open-item lists), and prints a ledger entry as its id, tier and
claim rather than as a fragment of JSON, because the tier is the answer a writer needs.

Usage:
    python3 tools/spoke_search.py healthomics              # files containing the term
    python3 tools/spoke_search.py healthomics "access point"   # files containing both
    python3 tools/spoke_search.py --any flexcache snapmirror
    python3 tools/spoke_search.py --digest < prompt.txt    # distinctive terms in free text
    python3 tools/spoke_search.py --selftest

Exit status is 0 whether or not anything matched: finding nothing is an answer, not a failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Refs tried in order. ``origin/main`` is the repository's published state; the others only
#: matter for a clone with no remote, which is how the self-test builds some fixtures.
REFS = ("origin/main", "origin/master", "main", "master", "HEAD")

#: Never searched. ``.private`` is excluded even though git will not hold it, so the intent
#: survives someone force-adding a file. The rest is machine output with nothing to decide.
EXCLUDE = (
    ".private",
    "node_modules",
    "cdk.out",
    "*.lock",
    "package-lock.json",
    "*.svg",
    "*.drawio",
    "*.min.js",
    "*.png",
    "*.jpg",
)

#: Where a conclusion is recorded: a claim with a tier, a request to a vendor, a known gap, a
#: limit, a pitfall, a decision. Listed first, and what ``--digest`` and the write guard count as
#: "a Spoke investigated this". The shapes come from the sibling repositories as they are today;
#: a Spoke that names such a file differently is still found, just not promoted.
RECORD_PATH = re.compile(
    r"(evidence[-_]?ledger|aws-feature-requests|feature-requests?|open-items|known-gaps|"
    r"support-matrix|limitations|pitfalls|decision)",
    re.IGNORECASE,
)

#: Where a result is recorded: verification output. Listed after the records. It is not counted as
#: an investigation of a term, because a measurement log names every metric and API it touched.
RESULT_PATH = re.compile(r"(verification|findings)", re.IGNORECASE)


def path_tier(path: str) -> int:
    """0 for a record of a conclusion, 1 for a recorded result, 2 for anything else."""
    if RECORD_PATH.search(path):
        return 0
    return 1 if RESULT_PATH.search(path) else 2


#: A structured ledger: ``{"claims": [{"id", "tier", "claim", ...}]}``.
LEDGER_PATH = re.compile(r"(?:^|/)evidence[-_]ledger\.json$", re.IGNORECASE)

#: Words too common in this family to say anything about a topic. Never chosen as the
#: distinctive term in ``--digest``.
GENERIC = frozenset(
    re.split(
        r"\s+",
        """
        fsx ontap netapp amazon aws access point points file files data cloud storage volume volumes
        http https www com docs github blob main this that with from have will your their there
        about which what when where while would could should also into then than them they been being
        make makes test tests note notes tier region regions true false none null
        lambda bedrock python json yaml markdown claude kiro
        nfs smb iscsi nvme s3ap ec2 vpc iam kms
        please thanks thank continue readme
        verified unverified documented hypothesis measured unmeasured untested reasoned
        observation field-observation
        """.strip(),
    )
)

#: A term in more files than this across all Spokes names no topic. Measured on the real spread:
#: a product a Spoke investigated sits in tens of files (HealthOmics 28, Quick Suite 29); a
#: family-wide word sits in hundreds (FlexCache 660, SnapMirror 610).
MAX_FILES_FOR_TOPIC = 80

#: An explicit search skips the fetch for a repository fetched within this many seconds.
FETCH_TTL = 3600
FETCH_TIMEOUT = 25


def _env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The caller's environment without any ``GIT_*`` variable.

    Git exports ``GIT_DIR`` and ``GIT_INDEX_FILE`` to a hook, and ``make all`` runs from the
    pre-commit hook. An inherited ``GIT_DIR`` outranks ``-C`` and ``cwd``, so every repository
    this tool looks at would be answered with the committing repository's data -- silently, and
    as exactly one repository after de-duplication.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    if extra:
        env.update(extra)
    return env


@dataclass(frozen=True)
class Repo:
    name: str  # the GitHub repository name, as in the origin URL
    owner: str
    git_dir: str  # the common git directory: shared by every worktree of the repository
    ref: str
    sha: str
    committed: datetime  # when the searched commit was made
    status: str = "not fetched"  # fetched | recent | not fetched | fetch failed

    @property
    def scope(self) -> str:
        """The Kiro memory scope string for this repository."""
        return f"repo:github/{self.owner}/{self.name}"


def _git(git_dir: str, *args: str, timeout: int = 30) -> str | None:
    """Run git against a git directory. ``None`` on failure: absence is information."""
    try:
        done = subprocess.run(
            ["git", f"--git-dir={git_dir}", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode in (0, 1) else None


ORIGIN = re.compile(r"[:/](?P<owner>[^/:]+)/(?P<name>[^/]+?)(?:\.git)?/?$")


def parse_origin(url: str) -> tuple[str, str] | None:
    """``owner, name`` from an https, ssh or local-path remote URL."""
    match = ORIGIN.search(url.strip())
    return (match["owner"], match["name"]) if match else None


def _resolve_ref(git_dir: str) -> tuple[str, str, datetime] | None:
    for ref in REFS:
        out = _git(git_dir, "log", "-1", "--format=%H%x09%cI", ref, "--")
        if out and out.strip():
            sha, _, iso = out.strip().partition("\t")
            try:
                return ref, sha[:7], datetime.fromisoformat(iso)
            except ValueError:
                continue
    return None


def _git_path(path: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            env=_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = done.stdout.strip()
    return out if done.returncode == 0 and out else None


def toplevel(path: Path) -> Path | None:
    """The working-tree root containing ``path``, or ``None`` outside a repository."""
    out = _git_path(path, "rev-parse", "--show-toplevel")
    return Path(out) if out else None


def _common_git_dir(path: Path) -> str | None:
    return _git_path(path, "rev-parse", "--path-format=absolute", "--git-common-dir")


def default_roots(current: Path) -> list[Path]:
    """Directories to look in for sibling clones.

    The parent of the repository's main working tree comes first. A session worktree lives
    elsewhere (``~/Projects/.kiro-worktrees/<id>``), and its own parent holds no siblings.
    """
    roots: list[Path] = []
    common = _common_git_dir(current)
    if common:
        roots.append(Path(common).parent.parent)
    roots.append(current.parent)
    seen: list[Path] = []
    for root in roots:
        if root not in seen:
            seen.append(root)
    return seen


def discover(
    current: Path, roots: list[Path] | None = None, *, include_current: bool = False
) -> list[Repo]:
    """Every sibling repository with a local clone, one entry per GitHub repository.

    ``current`` is the repository you are working in. It is left out unless
    ``include_current``: its own pages come back from an ordinary grep, and what goes missing
    is everywhere else. "Left out" means by GitHub identity, not by directory: a second clone of
    the repository you are in is the same repository, not a sibling.
    """
    here = _common_git_dir(current)
    here_origin = (
        parse_origin(_git(here, "config", "--get", "remote.origin.url") or "")
        if here
        else None
    )
    if here_origin is None:
        return []
    owner = here_origin[0]
    here_identity = (here_origin[0].lower(), here_origin[1].lower())
    seen_git_dirs: set[str] = set()
    best: dict[str, Repo] = {}
    for search_root in roots or default_roots(current):
        try:
            children = sorted(p for p in search_root.iterdir() if p.is_dir())
        except OSError:
            continue
        for child in children:
            if not (child / ".git").exists():
                continue
            git_dir = _common_git_dir(child)
            if not git_dir or git_dir in seen_git_dirs:
                continue
            seen_git_dirs.add(git_dir)
            parsed = parse_origin(
                _git(git_dir, "config", "--get", "remote.origin.url") or ""
            )
            if not parsed or parsed[0] != owner:
                continue
            if (
                parsed[0].lower(),
                parsed[1].lower(),
            ) == here_identity and not include_current:
                continue
            resolved = _resolve_ref(git_dir)
            if not resolved:
                continue
            ref, sha, committed = resolved
            repo = Repo(parsed[1], parsed[0], git_dir, ref, sha, committed)
            previous = best.get(repo.name.lower())
            if previous is None or repo.committed > previous.committed:
                best[repo.name.lower()] = repo
    return sorted(best.values(), key=lambda r: r.name.lower())


def _recently_fetched(git_dir: str, ttl: int = FETCH_TTL) -> bool:
    try:
        age = time.time() - os.stat(os.path.join(git_dir, "FETCH_HEAD")).st_mtime
    except OSError:
        return False
    return age < ttl


def refresh(repo: Repo) -> Repo:
    """``origin``'s current tip of the searched branch.

    Only the remote-tracking ref moves: no checkout, merge or local branch is touched. Any
    failure (offline, no credential, a repository this machine cannot read) leaves the repository
    as it was and says so in ``status``, so the output can warn that "no match" is weaker there.
    """
    if not repo.ref.startswith("origin/"):
        return repo
    if _recently_fetched(repo.git_dir):
        return replace(repo, status="recent")
    branch = repo.ref.split("/", 1)[1]
    try:
        done = subprocess.run(
            [
                "git",
                f"--git-dir={repo.git_dir}",
                "fetch",
                "--quiet",
                "--no-tags",
                "origin",
                branch,
            ],
            capture_output=True,
            text=True,
            timeout=FETCH_TIMEOUT,
            check=False,
            env=_env({"GIT_TERMINAL_PROMPT": "0"}),
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # no controlling terminal: ssh fails fast instead of prompting
        )
    except (OSError, subprocess.TimeoutExpired):
        return replace(repo, status="fetch failed")
    if done.returncode != 0:
        return replace(repo, status="fetch failed")
    resolved = _resolve_ref(repo.git_dir)
    if not resolved:
        return replace(repo, status="fetch failed")
    ref, sha, committed = resolved
    return replace(repo, ref=ref, sha=sha, committed=committed, status="fetched")


def refresh_all(repos: list[Repo]) -> list[Repo]:
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(refresh, repos))


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    text: str


@dataclass(frozen=True)
class LedgerEntry:
    id: str
    tier: str
    claim: str


def grep(
    repo: Repo, terms: list[str], *, all_match: bool = True
) -> dict[str, list[Hit]]:
    """Committed files in ``repo`` that contain the terms, with the matching lines."""
    if not terms:
        return {}
    args = ["grep", "-n", "-I", "-i", "-F"]
    if all_match and len(terms) > 1:
        args.append("--all-match")
    for term in terms:
        args += ["-e", term]
    args += [repo.ref, "--", "."] + [f":(exclude){pattern}" for pattern in EXCLUDE]
    out = _git(repo.git_dir, *args, timeout=60)
    hits: dict[str, list[Hit]] = {}
    if not out:
        return hits
    prefix = repo.ref + ":"
    for raw in out.splitlines():
        if not raw.startswith(prefix):
            continue
        path, _, tail = raw[len(prefix) :].partition(":")
        number, _, text = tail.partition(":")
        if not number.isdigit():
            continue
        hits.setdefault(path, []).append(Hit(path, int(number), text.strip()))
    return hits


def ledger_entries(
    repo: Repo, path: str, terms: list[str], *, all_match: bool = True
) -> list[LedgerEntry]:
    """Entries of a structured evidence ledger that mention the terms."""
    body = _git(repo.git_dir, "show", f"{repo.ref}:{path}", timeout=15)
    if not body:
        return []
    try:
        claims = json.loads(body).get("claims")
    except (ValueError, AttributeError):
        return []
    if not isinstance(claims, list):
        return []
    wanted = [t.lower() for t in terms]
    found: list[LedgerEntry] = []
    for entry in claims:
        if not isinstance(entry, dict):
            continue
        text = json.dumps(entry, ensure_ascii=False).lower()
        matched = [t in text for t in wanted]
        if all(matched) if all_match else any(matched):
            found.append(
                LedgerEntry(
                    str(entry.get("id", "?")),
                    str(entry.get("tier", "?")),
                    str(entry.get("claim", "")),
                )
            )
    return found


def heading_for(repo: Repo, path: str, line: int) -> str:
    """The nearest Markdown heading above a line, so a hit says which section it is in."""
    if not path.lower().endswith((".md", ".markdown")):
        return ""
    body = _git(repo.git_dir, "show", f"{repo.ref}:{path}", timeout=15)
    if not body:
        return ""
    heading = ""
    for number, text in enumerate(body.splitlines(), start=1):
        if number > line:
            break
        if re.match(r"^#{1,6}\s", text):
            heading = text.strip()
    return heading


def rank(hits: dict[str, list[Hit]], terms: list[str] | None = None) -> list[str]:
    """Paths in reading order: records, then results, each with files named for the term first.

    A file whose own path contains a term (``lambda-healthomics-s3ap-gaps.md`` for
    ``healthomics``) is about it; a file that mentions it in one table row is not. Within equal
    rank, more matching lines first, then path, so the order is stable.
    """
    wanted = [t.lower() for t in terms or []]

    def key(path: str) -> tuple[int, int, int, str]:
        named = 0 if any(t in path.lower() for t in wanted) else 1
        return (path_tier(path), named, -len(hits[path]), path)

    return sorted(hits, key=key)


def clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


@dataclass(frozen=True)
class Found:
    hits: dict[str, list[Hit]]
    ledgers: dict[str, list[LedgerEntry]]


def search(
    repos: list[Repo], terms: list[str], *, all_match: bool = True
) -> dict[Repo, Found]:
    def one(repo: Repo) -> Found:
        hits = grep(repo, terms, all_match=all_match)
        ledgers = {
            path: entries
            for path in hits
            if LEDGER_PATH.search(path)
            and (entries := ledger_entries(repo, path, terms, all_match=all_match))
        }
        return Found(hits, ledgers)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {repo: pool.submit(one, repo) for repo in repos}
        return {repo: future.result() for repo, future in futures.items()}


def _age(repo: Repo, now: datetime) -> str:
    return f"last commit {(now - repo.committed).days} d ago"


def _status(repo: Repo) -> str:
    return {
        "fetched": "refreshed now",
        "recent": "refreshed within the hour",
        "fetch failed": "FETCH FAILED, may lack newer work",
    }.get(repo.status, "NOT refreshed, may lack newer work")


def render(
    query: list[str],
    results: dict[Repo, Found],
    *,
    per_repo: int = 6,
    per_file: int = 2,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    shown = " + ".join(f'"{t}"' for t in query)
    lines = [
        f"spoke-search: {shown}   ({len(results)} repositories; committed content at each ref, not working copies)"
    ]
    matched: list[Repo] = []
    empty: list[Repo] = []
    for repo, found in results.items():
        if not found.hits:
            empty.append(repo)
            continue
        matched.append(repo)
        ordered = rank(found.hits, query)
        lines.append(
            f"- {repo.name} @ {repo.ref} {repo.sha} ({_age(repo, now)}; {_status(repo)}): {len(ordered)} file(s)"
        )
        for path in ordered[:per_repo]:
            tag = ("[record] ", "[result] ", "")[path_tier(path)]
            first = found.hits[path][0]
            if path in found.ledgers:
                lines.append(f"  {tag}{path}")
                for entry in found.ledgers[path][:4]:
                    lines.append(
                        f"      {entry.id} [{entry.tier}] {clip(entry.claim, 240)}"
                    )
                continue
            section = heading_for(repo, path, first.line)
            lines.append(
                f"  {tag}{path}:{first.line}" + (f"   {section}" if section else "")
            )
            for hit in found.hits[path][:per_file]:
                lines.append(f"      {hit.text[:160]}")
        if len(ordered) > per_repo:
            lines.append(
                f"  ... and {len(ordered) - per_repo} more file(s) in {repo.name}"
            )
    if empty:
        noun = "repository" if len(empty) == 1 else "repositories"
        lines.append(
            f"- no match in {len(empty)} {noun}: " + ", ".join(r.name for r in empty)
        )
        weak = [r for r in empty if r.status not in ("fetched", "recent")]
        if weak:
            lines.append(
                "  not refreshed, so weaker: "
                + ", ".join(f"{r.name} ({_age(r, now)})" for r in weak)
            )
    lines.append("")
    if matched:
        lines.append(
            "Read these before writing that something is unverified, unmeasured or unsupported."
        )
        lines.append(
            "Kiro memories are per repository and are not all shown at session start:"
        )
        lines += [f"  memory list scopeFilter={repo.scope}" for repo in matched]
    else:
        lines.append(
            "Nothing in any sibling repository. That is an answer; say what you searched."
        )
    return "\n".join(lines)


# --- digest: pick the distinctive terms out of free text ----------------------------------------

URL = re.compile(r"https?://\S+")
ASCII_WORD = re.compile(r"[A-Za-z][A-Za-z0-9._-]{3,}")
KATAKANA = re.compile(r"[\u30A1-\u30FA\u30FC]{4,}")
#: What can precede the first word of a sentence, a list item, a table cell or a heading.
SENTENCE_BOUNDARY = ".!?。！？\n-*|>#:：、"
FILE_NAME = re.compile(r"\.(?:md|json|ya?ml|py|sh|txt|toml|ts|js)$", re.IGNORECASE)

#: Keys a prompt hook payload may carry the user's text under, tried in order. The schema is not
#: documented; ``prompt_text`` falls back to every long string in the payload.
PROMPT_KEYS = (
    "prompt",
    "user_prompt",
    "userPrompt",
    "message",
    "text",
    "content",
    "input",
)

#: Payload fields that describe the session, not what the user said. Skipped in the fallback so a
#: short prompt is not outweighed by a working-directory path or a session id.
NOT_PROMPT_KEYS = re.compile(
    r"(cwd|path|dir|session|^id$|_id$|event|transcript|workspace|root|url|uri|model)",
    re.IGNORECASE,
)


def prompt_text(raw: str) -> str:
    """The user's text from a hook payload on stdin, or ``raw`` itself when it is not JSON."""
    raw = raw.strip()
    if not raw.startswith(("{", "[")):
        return raw
    try:
        payload = json.loads(raw)
    except ValueError:
        return raw
    if isinstance(payload, dict):
        for key in PROMPT_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    strings: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, str):
            strings.append(node)
        elif isinstance(node, dict):
            for key, value in node.items():
                if not NOT_PROMPT_KEYS.search(str(key)):
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return max(strings, key=len, default="")


def candidate_terms(
    text: str, limit: int = 12, *, named_only: bool = False
) -> list[str]:
    """Words in ``text`` that could name a topic, most specific first. No repository access.

    ``named_only`` keeps the words shaped like a product or feature name (CamelCase, hyphenated
    with a capital, digit-bearing, or capitalised mid-sentence) and drops plain lowercase words
    and katakana. Without it, a paragraph's ordinary vocabulary ("collapsing", "symmetrically",
    "チャネル") turns up in a few Spoke files by chance and reads as a topic.
    """
    text = URL.sub(" ", text)
    seen: dict[str, int] = {}
    for match in ASCII_WORD.finditer(text):
        raw = match.group(0)
        word = raw.strip("._-").lower()
        if len(word) < 4 or word in GENERIC or word.isdigit():
            continue
        # CamelCase or digit-bearing words name a product or a feature, and so does a hyphenated
        # one with a capital. A hyphen alone does not ("crash-consistent", "re-measure"), nor does
        # a file name. A capitalised word counts unless it opens a sentence, where English
        # capitalises everything.
        starts = text[: match.start()].rstrip(" \t")
        opens_sentence = not starts or starts[-1] in SENTENCE_BOUNDARY
        specific = not FILE_NAME.search(raw) and (
            bool(re.search(r"[a-z][A-Z]|[0-9]", raw))
            or ("-" in raw and any(ch.isupper() for ch in raw))
            or (raw[0].isupper() and not opens_sentence)
        )
        seen[word] = max(seen.get(word, 0), 2 if specific else 1)
    for match in KATAKANA.finditer(text):
        seen.setdefault(match.group(0), 1)
    ordered = sorted(seen, key=lambda w: (-seen[w], -len(w), w))
    if named_only:
        ordered = [w for w in ordered if seen[w] >= 2]
    return ordered[:limit]


def focused_terms(
    text: str, repos: list[Repo], *, top: int = 3
) -> dict[str, dict[Repo, dict[str, list[Hit]]]]:
    """Terms in ``text`` that a few Spoke files cover, with where. The topics, not the vocabulary."""
    terms = candidate_terms(text)
    if not terms or not repos:
        return {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            (term, repo): pool.submit(grep, repo, [term])
            for term in terms
            for repo in repos
        }
        found = {key: future.result() for key, future in futures.items()}
    scored: list[tuple[int, str]] = []
    for term in terms:
        total = sum(len(found[(term, repo)]) for repo in repos)
        decisive = sum(
            1
            for repo in repos
            for path in found[(term, repo)]
            if RECORD_PATH.search(path)
        )
        # A record of a conclusion is what separates "a Spoke investigated this" from "a Spoke's
        # code, prose or measurement log happens to contain the word".
        if 0 < total <= MAX_FILES_FOR_TOPIC and decisive >= 1:
            scored.append((-(decisive * 100) + total, term))
    scored.sort()
    chosen = [term for _, term in scored[:top]]
    return {
        term: {repo: found[(term, repo)] for repo in repos if found[(term, repo)]}
        for term in chosen
    }


def digest(text: str, repos: list[Repo], *, top: int = 3) -> str:
    """For each distinctive term in ``text`` that a Spoke has files on: where. Empty when none."""
    topics = focused_terms(text, repos, top=top)
    if not topics:
        return ""
    out = [
        "spoke-search: sibling repositories already hold material on terms in this text."
    ]
    for term, per_repo in topics.items():
        for repo, hits in per_repo.items():
            ordered = rank(hits, [term])
            decisive = [p for p in ordered if RECORD_PATH.search(p)]
            shown = (decisive or ordered)[:3]
            kind = "records" if decisive else "files"
            out.append(
                f'  "{term}" -- {repo.name}: {len(hits)} file(s); {kind}: '
                + ", ".join(shown)
            )
    first = next(iter(topics))
    out.append(
        "Before calling any of it unverified (未確認) or proposing a new check, read it: "
        + read_command(first)
    )
    return "\n".join(out)


def read_command(term: str) -> str:
    """How to read the material on ``term`` from wherever the reader is.

    ``make`` only works in the repository that has the target; the path works anywhere, and it is
    the path of the copy that is running, so it exists.
    """
    return f'make spoke-search Q="{term}"   (anywhere: python3 {Path(__file__).resolve()} {term})'


# --- self-test ------------------------------------------------------------------------------------


def _run(*args: str, cwd: Path) -> str:
    done = subprocess.run(
        list(args),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env=_env(
            {
                "GIT_AUTHOR_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@example.com",
                "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@example.com",
            }
        ),
    )
    return done.stdout


def _remote(base: Path, owner: str, name: str) -> Path:
    """A bare repository standing in for GitHub; its path ends ``<owner>/<name>.git``."""
    bare = base / "remotes" / owner / f"{name}.git"
    bare.mkdir(parents=True)
    _run("git", "init", "-q", "--bare", "-b", "main", str(bare), cwd=base)
    return bare


def _commit(path: Path, files: dict[str, str], message: str = "change") -> None:
    for rel, body in files.items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    _run("git", "add", "-A", cwd=path)
    _run("git", "commit", "-q", "-m", message, cwd=path)


def _clone(
    base: Path, remote: Path, name: str, files: dict[str, str] | None = None
) -> Path:
    """Clone ``remote`` into ``base/work/<name>``; with ``files``, commit and push them first."""
    work = base / "work"
    work.mkdir(exist_ok=True)
    _run("git", "clone", "-q", str(remote), str(work / name), cwd=base)
    path = work / name
    if files:
        _run("git", "checkout", "-q", "-B", "main", cwd=path)
        _commit(path, files)
        _run("git", "push", "-q", "origin", "main", cwd=path)
    return path


def selftest() -> int:
    failures: list[str] = []

    def check(condition: bool, label: str) -> None:
        if not condition:
            failures.append(label)

    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        hub = _clone(
            base, _remote(base, "acme", "Hub"), "hub", {"README.md": "# Hub\n"}
        )
        spoke_remote = _remote(base, "acme", "Serverless-Patterns")
        spoke = _clone(
            base,
            spoke_remote,
            "serverless",
            {
                "docs/aws-feature-requests/gaps.md": "# Gaps\n\n## FR-6\nHealthOmics cannot take the access point.\n",
                "docs/notes.md": "# Notes\nHealthOmics is mentioned here too. S3 Access Point as well.\n",
                # Sorts before every decision file by path, so an unranked listing puts it first.
                "docs/a-overview.md": "# Overview\nHealthOmics overview.\n",
                "docs/agent/evidence-ledger.json": json.dumps(
                    {
                        "claims": [
                            {
                                "id": "E-009",
                                "tier": "documented",
                                "claim": "HealthOmics run inputs are S3 URIs",
                            },
                            {
                                "id": "E-020",
                                "tier": "open",
                                "claim": "Unrelated claim about something else",
                            },
                        ]
                    }
                ),
                "README.md": "unrelated\n",
            },
        )
        _clone(
            base,
            _remote(base, "someone-else", "Thing"),
            "stranger",
            {"a.md": "HealthOmics\n"},
        )
        # A second clone of the same GitHub repository must not be searched twice.
        _run(
            "git",
            "clone",
            "-q",
            str(spoke_remote),
            str(base / "work" / "serverless-old"),
            cwd=base,
        )
        _run(
            "git",
            "worktree",
            "add",
            "-q",
            str(base / "work" / "serverless-wt"),
            "-b",
            "side",
            cwd=spoke,
        )
        roots = [base / "work"]

        repos = discover(hub, roots)
        names = [r.name for r in repos]
        check(
            names == ["Serverless-Patterns"],
            f"discovers owner-matched Spokes once, current repo excluded, got {names}",
        )
        everyone = [r.name for r in discover(hub, roots, include_current=True)]
        check(
            everyone == ["Hub", "Serverless-Patterns"],
            f"include_current adds this repository, got {everyone}",
        )
        from_worktree = [
            r.name for r in discover(base / "work" / "serverless-wt", roots)
        ]
        check(
            from_worktree == ["Hub"],
            f"a worktree is the same repository as its main clone, got {from_worktree}",
        )
        check(
            discover(base, roots) == [],
            "outside any repository there is nothing to compare with",
        )

        # An inherited GIT_DIR (what a git hook exports) must not redirect the search.
        os.environ["GIT_DIR"] = str(hub / ".git")
        try:
            leaked = [r.name for r in discover(hub, roots)]
        finally:
            del os.environ["GIT_DIR"]
        check(
            leaked == ["Serverless-Patterns"],
            f"an inherited GIT_DIR is ignored, got {leaked}",
        )

        # Uncommitted edits and staged files are not repository state.
        (spoke / "docs" / "dirty.md").write_text(
            "HealthOmics uncommitted\n", encoding="utf-8"
        )
        (spoke / "docs" / "notes.md").write_text(
            "working copy rewrite\n", encoding="utf-8"
        )
        _run("git", "add", "docs/dirty.md", cwd=spoke)
        found = search(repos, ["healthomics"])
        hits = next(iter(found.values())).hits
        check(
            "docs/dirty.md" not in hits, "a staged but uncommitted file is not searched"
        )
        check(
            "healthomics is mentioned"
            in hits.get("docs/notes.md", [Hit("", 0, "")])[0].text.lower(),
            "searches the committed text, not the working-copy rewrite",
        )
        ordered = rank(hits, ["healthomics"])
        check(
            path_tier(ordered[0]) == 0 and path_tier(ordered[-1]) == 2,
            f"ledger and feature-request files precede an ordinary note, got {ordered}",
        )
        check(
            [path_tier(p) for p in ordered] == sorted(path_tier(p) for p in ordered),
            f"records, then results, then everything else, got {ordered}",
        )
        named = rank(hits, ["gaps"])
        check(
            named[0] == "docs/aws-feature-requests/gaps.md",
            f"among records, the file named for the term comes first, got {named}",
        )
        both = search(repos, ["healthomics", "access point"])
        check(
            set(next(iter(both.values())).hits)
            == {"docs/aws-feature-requests/gaps.md", "docs/notes.md"},
            "several terms require all of them in one file",
        )
        anyof = search(
            repos, ["no-such-topic-xyz", "mentioned here too"], all_match=False
        )
        check(
            set(next(iter(anyof.values())).hits) == {"docs/notes.md"},
            "--any matches files containing either term",
        )
        none = search(repos, ["no-such-topic-xyz"])
        check(
            not next(iter(none.values())).hits,
            "no match is an empty result, not an error",
        )

        ledgers = next(iter(found.values())).ledgers
        entries = ledgers.get("docs/agent/evidence-ledger.json", [])
        check(
            [e.id for e in entries] == ["E-009"],
            f"only ledger entries that mention the term, got {entries}",
        )
        check(
            entries and entries[0].tier == "documented",
            "a ledger entry carries its tier",
        )

        text = render(["healthomics"], found, now=datetime.now(timezone.utc))
        check(
            "[record] docs/aws-feature-requests/gaps.md" in text,
            "render marks decision files",
        )
        check(
            "E-009 [documented] HealthOmics run inputs are S3 URIs" in text,
            "render prints a ledger entry as id, tier, claim",
        )
        check(
            "E-020" not in text,
            "render omits ledger entries that do not mention the term",
        )
        check("## FR-6" in text, "render shows the section a hit sits in")
        check(
            "origin/main" in text and "last commit" in text,
            "render states the ref and its age",
        )
        check(
            "NOT refreshed" in text,
            "render warns when the repository was not refreshed",
        )
        check(
            "memory list scopeFilter=repo:github/acme/Serverless-Patterns" in text,
            "render points at per-repo memories",
        )
        check(
            "working copy rewrite" not in text, "render never shows working-copy text"
        )
        quiet = render(["no-such-topic-xyz"], none)
        check(
            "no match in 1 repository: Serverless-Patterns" in quiet,
            "repositories without a match are one line",
        )
        check(
            "say what you searched" in quiet,
            "an empty result still asks to be reported",
        )

        # Refresh: a commit pushed upstream after the clone is invisible until fetched.
        pusher = _clone(base, spoke_remote, "pusher")
        _commit(
            pusher, {"docs/new.md": "# New\nHealthOmics newly investigated upstream.\n"}
        )
        _run("git", "push", "-q", "origin", "HEAD:main", cwd=pusher)
        stale = next(iter(search(repos, ["newly investigated"]).values())).hits
        check(not stale, "before a fetch, an upstream commit is not visible")
        (spoke / ".git" / "FETCH_HEAD").unlink(missing_ok=True)
        refreshed = refresh_all(repos)
        check(
            refreshed[0].status == "fetched",
            f"a repository not fetched recently is fetched, got {refreshed[0].status}",
        )
        fresh = next(iter(search(refreshed, ["newly investigated"]).values())).hits
        check("docs/new.md" in fresh, "after a fetch, the upstream commit is searched")
        check(
            refresh(refreshed[0]).status == "recent",
            "a repository fetched within the hour is not fetched again",
        )
        check(
            "refreshed now" in render(["x"], search(refreshed, ["healthomics"])),
            "render says which repositories were refreshed",
        )
        _run(
            "git",
            "remote",
            "set-url",
            "origin",
            str(base / "does-not-exist.git"),
            cwd=spoke,
        )
        (spoke / ".git" / "FETCH_HEAD").unlink(missing_ok=True)
        failed = refresh(refreshed[0])
        check(
            failed.status == "fetch failed",
            f"an unreachable remote is reported, not raised, got {failed.status}",
        )
        check(
            "FETCH FAILED"
            in render(["healthomics"], search([failed], ["healthomics"])),
            "render warns about a failed fetch",
        )
        check(
            bool(next(iter(search([failed], ["healthomics"]).values())).hits),
            "a failed fetch still searches what is there",
        )

        topics = focused_terms(
            "HealthOmics と Nextflow の話。続きをお願いします。", repos
        )
        check(
            "healthomics" in topics,
            f"a term a Spoke covers is a topic, got {list(topics)}",
        )
        check("nextflow" not in topics, "a term no Spoke covers is not reported")
        said = digest("HealthOmics で S3 Access Points を使えるかは未確認", repos)
        check(
            "Serverless-Patterns" in said and "records:" in said,
            "digest names the Spoke and its records",
        )
        check(
            'make spoke-search Q="healthomics"' in said
            and f"python3 {Path(__file__).resolve()} healthomics" in said,
            "digest says how to read the material",
        )
        check(
            digest("続きをお願いします。", repos) == "",
            "digest is silent when no term is a topic",
        )

    terms = candidate_terms(
        "HealthOmics と Amazon Bedrock AgentCore で https://example.com/some-long-slug を読む。続きをお願いします。"
    )
    check(
        "healthomics" in terms, f"CamelCase product names are candidates, got {terms}"
    )
    check("agentcore" in terms, "a second product name is a candidate")
    check(
        "amazon" not in terms and "bedrock" not in terms,
        "generic family words are not candidates",
    )
    check(not any("slug" in t for t in terms), "words inside URLs are ignored")
    check(
        candidate_terms("続きをお願いします。") == [],
        "a short prompt with no product name has no candidates",
    )
    opening = candidate_terms(
        "Unfortunately the Nextflow path is unknown. Whether it works is open."
    )
    check(
        opening[:1] == ["nextflow"],
        f"a capitalised word mid-sentence outranks one that merely opens a sentence, got {opening}",
    )

    check(
        prompt_text('{"prompt": "HealthOmics 未確認", "cwd": "/x"}')
        == "HealthOmics 未確認",
        "prompt key is read",
    )
    check(
        prompt_text("plain text") == "plain text", "non-JSON stdin is the text itself"
    )
    check(
        prompt_text('{"detail": "a much longer message about HealthOmics", "id": "x"}')
        == "a much longer message about HealthOmics",
        "an unknown payload shape falls back to its longest string",
    )
    check(
        prompt_text(
            '{"cwd": "/Users/someone/Projects/some-long-repository-name", "note": "HealthOmics"}'
        )
        == "HealthOmics",
        "a session path is not mistaken for the prompt",
    )
    check(prompt_text("{not json") == "{not json", "malformed JSON is treated as text")

    # A prompt with no distinctive term must not pay for finding the sibling clones.
    import io
    from contextlib import redirect_stdout

    class _Piped(io.StringIO):
        def isatty(self) -> bool:
            return False

    calls: list[object] = []
    real_discover, real_stdin = globals()["discover"], sys.stdin
    globals()["discover"] = lambda *a, **k: calls.append(a) or []
    sys.stdin = _Piped('{"prompt": "マージしてください。"}')
    try:
        with redirect_stdout(io.StringIO()) as printed:
            status = main(["--digest"])
    finally:
        globals()["discover"], sys.stdin = real_discover, real_stdin
    check(
        status == 0 and not calls and printed.getvalue() == "",
        "a prompt with no distinctive term skips discovery and prints nothing",
    )

    if failures:
        print("selftest FAILED:", file=sys.stderr)
        for label in failures:
            print(f"  - {label}", file=sys.stderr)
        return 1
    print("selftest: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "terms", nargs="*", help="terms; a file must contain all of them unless --any"
    )
    parser.add_argument(
        "--any", action="store_true", help="match files containing any term"
    )
    parser.add_argument(
        "--digest",
        action="store_true",
        help="read text (or a hook payload) on stdin and report on its distinctive terms",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="do not refresh stale refs first (--digest never fetches)",
    )
    parser.add_argument(
        "--include-current",
        action="store_true",
        help="also search the repository you are in",
    )
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        help="extra directory holding clones (repeatable)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    here = toplevel(Path.cwd()) or ROOT
    roots = [*args.root, *default_roots(here)] if args.root else None

    text = ""
    if args.digest:
        text = prompt_text(sys.stdin.read()) if not sys.stdin.isatty() else ""
        # Finding the sibling clones costs about 75 git calls (0.27 s measured), and this runs on
        # every prompt. A prompt with no distinctive term has nothing to look up, so say nothing
        # before paying for it. ``focused_terms`` returns empty in exactly this case.
        if not candidate_terms(text):
            return 0

    repos = discover(here, roots, include_current=args.include_current)
    if not repos:
        print(
            "spoke-search: no sibling clones found next to this repository. "
            "Clone them beside it, or pass --root <dir>.",
            file=sys.stderr,
        )
        return 0

    if args.digest:
        out = digest(text, repos)
        if out:
            print(out)
        return 0

    if not args.terms:
        parser.error("give at least one term, or --digest")
    if not args.no_fetch:
        repos = refresh_all(repos)
    results = search(repos, args.terms, all_match=not args.any)
    if args.json:
        payload = {
            repo.name: {
                "ref": repo.ref,
                "sha": repo.sha,
                "status": repo.status,
                "files": {p: [h.line for h in hs] for p, hs in found.hits.items()},
                "ledger": {p: [vars(e) for e in es] for p, es in found.ledgers.items()},
            }
            for repo, found in results.items()
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render(args.terms, results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
