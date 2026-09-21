#!/usr/bin/env python3
"""Verify that citations of sibling repositories are registered, and still say what we claim.

Why this exists
---------------
This repository does not re-measure what a sibling project has already measured. It cites. That
keeps one number in one place, which is the right call — and it introduces a failure mode with no
symptom: the cited file gets moved, or the claim gets retracted, and the sentence here goes on
saying what it always said.

Two checks, split by whether they need the network, following the same division as
`check_links.py`:

Offline (in `make all`)
    Every link into a sibling repository that appears in tracked prose has a row in
    `docs/ja/reference/cross-repo-index.md`, and every row of that table names a file in this
    repository that exists and actually contains the link. A citation nobody makes and a claim
    nobody registered are both defects.

External (opt-in)
    Each cited path is fetched and must still contain the recorded probe string. The probe is
    supposed to name the claim, not the heading, so that a retraction fails the gate rather than
    passing it.

    Every sibling repository named anywhere in prose is also resolved, and a name that only works
    because GitHub redirects it fails. A rename is normal; the old name continuing to resolve is
    what makes it invisible, and the table above keys on the name.

The table is the single source, and a *hand-maintained* second list of its contents is refused: a
copy nothing compares drifts, and this repository has already been on the receiving end of that —
an issue body enumerated seven probe strings, two were later replaced, and the enumeration went on
describing a gate that no longer existed until a sibling reported a string as broken that had never
been registered.

`docs/agent/cross-repo-probe-contract.txt` is not that. It is generated from this table and compared
on every run, so drift fails here rather than being discovered by someone else. It exists because the
probe check is one-directional: only this repository can run it, so a claim we cite going stale is
invisible to the repository that owns the claim until our CI fails. Publishing the strings lets that
side check before committing a reword, which is the same trade the anchor contract makes in the other
direction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from probe_strength import strip_code, verdict

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "ja" / "reference" / "cross-repo-index.md"
CONTRACT = ROOT / "docs" / "agent" / "cross-repo-probe-contract.txt"
OWNER = "Yoshiki0705"
THIS_REPO = "FSx-for-ONTAP-Adoption-Playbook"

# What a probe firing is allowed to mean. Two values, because one verdict cannot carry both: a
# string quoting the extremes of a measured set moves when the cited side *adds* a measurement,
# and treating that as a retraction records an extension as a withdrawal.
ROLES = {
    "retraction": (
        "expected to survive; its absence means the claim moved or was retracted"
    ),
    "reread": (
        "quotes a min/max over the cited document's measured set, so an added "
        "measurement rewrites it while the finding stands. Firing is not a retraction"
    ),
}

CONTRACT_HEADER = """\
# Probe strings this repository registers against sibling repositories. Generated - do not hand-edit.
#
# Regenerate with: python3 tools/check_cross_repo.py --write-contract
# Source of truth: docs/ja/reference/cross-repo-index.md (the table the gate parses).
#
# Why this is published: the probe check runs here and nowhere else, so a claim we cite being
# reworded is invisible to the repository that owns it until our CI fails. Reading this file lets
# that side see, before committing, which of its strings something outside it depends on.
#
# Format: <repo>\\t<cited path>\\t<role>\\t<probe>, sorted. One line per cited string; the citing file
# on our side is deliberately absent, being our concern rather than yours.
#
# role:
#   retraction  Expected to survive. Its absence means the claim moved or was retracted, and the
#               guidance built on it here has lost its basis. Worth failing on.
#   reread      Quotes a min/max over the measured set in the cited document, so adding a
#               measurement rewrites the string while the finding still stands. A gate cannot tell
#               an addition from a withdrawal, so treat firing as "read this section again", not as
#               a retraction. Editing prose automatically on this one records an extension as a
#               withdrawal.
#
# An absence claim ("the column is not in the table", "not stated in public documentation") is a
# third shape and is deliberately filed as `retraction`: when it stops being true, the guidance
# resting on it changes, and that is something to be stopped by rather than warned about.
"""

TABLE_START = "<!-- cross-repo-table:start -->"
TABLE_END = "<!-- cross-repo-table:end -->"

# A citation is a blob link into a sibling repository. Tree links are navigation rather than
# citation, so they are not required to be registered — but "not a citation" is not "checked
# somewhere else". The claim that check_links.py resolves them was wrong: that check skips every
# http(s) URL unless --external is passed, and --external runs in no workflow. Twenty-one tree
# links into one sibling repository were verified by nothing at all. PATH_LINK below is what the
# network half now resolves.
BLOB_LINK = re.compile(
    rf"https://github\.com/{OWNER}/(?P<repo>[A-Za-z0-9._-]+)/blob/(?P<ref>[^/\s)]+)/(?P<path>[^\s)\"'#]+)"
)
# Any path into a repository this account owns, blob or tree. The split that matters is not
# citation-versus-navigation, it is **what a failure means**: a URL into our own account is
# deterministic and entirely within our control, so a 404 is always a real defect that we can fix.
# That is the reason vendor URLs stay out of a blocking gate, and it does not transfer here.
PATH_LINK = re.compile(
    rf"https://github\.com/{OWNER}/(?P<repo>[A-Za-z0-9._-]+)/(?P<kind>blob|tree)/"
    rf"(?P<ref>[^/\s)]+)/(?P<path>[^\s)\"'#]+)"
)

# Any reference to a sibling repository, citation or not. A rename leaves the old name working
# through GitHub's redirect, so a stale name has no symptom until someone compares two documents
# that spell the same repository differently.
REPO_REF = re.compile(rf"https://github\.com/{OWNER}/(?P<repo>[A-Za-z0-9._-]+)")

# Files whose prose can carry citations. Code and templates are excluded: a citation belongs next to
# the claim it supports, and neither of those states claims.
PROSE_GLOBS = ("docs/**/*.md", "*.md", "llms.txt")
SKIP_PARTS = {".private", ".kiro", ".venv", "node_modules", "_template"}

ADOPTION_CONTRACT_SCHEMA = "knowledge-quality/adoption-contract/v1"
OVERRIDE_SCHEMA = "knowledge-quality/repository-overrides/v1"
HUB_REPOSITORY = f"{OWNER}/{THIS_REPO}"
PROFILE_ARTIFACTS = {
    "cross-repository-quality-v1": frozenset(
        {"tools/check_cross_repo.py", "tools/check_inbound_probes.py"}
    )
}
RULE_INDEX = "docs/ja/reference/cross-repo-index.md#引用表"
OVERRIDE_LIMITS = {
    "scan-root": 8,
    "exclusion": 8,
    "localization-tier": 1,
    "repository-rule": 8,
}
MAX_OVERRIDES = 16
_CONTRACT_FIELDS = frozenset(
    {
        "contract_schema",
        "hub_repository",
        "hub_revision",
        "profile",
        "validator_artifacts",
        "rule_index",
        "repository_overrides",
    }
)
_OVERRIDE_FIELDS = frozenset({"category", "value", "reason"})


@dataclass(frozen=True)
class AdoptionContractProblem:
    category: str
    message: str

    def render(self) -> str:
        return f"[adoption-contract:{self.category}] {self.message}"


def _problem(category: str, message: str) -> AdoptionContractProblem:
    return AdoptionContractProblem(category, message)


def _safe_relative_path(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    if (
        candidate.is_absolute()
        or ".." in candidate.parts
        or candidate.as_posix() != value
    ):
        return None
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _heading_anchor_exists(path: Path, anchor: str) -> bool:
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if not match:
            continue
        heading = re.sub(r"[*_`]", "", match.group(1)).strip()
        slug = re.sub(r"[\s]+", "-", heading.lower())
        slug = re.sub(r"[^\w\-\u3040-\u30ff\u3400-\u9fff]", "", slug)
        if slug == anchor:
            return True
    return False


def _copied_rule_body(value: str, rule_index_body: str) -> bool:
    normalized_value = " ".join(value.split())
    if len(normalized_value) < 32:
        return False
    for raw in rule_index_body.splitlines():
        line = " ".join(raw.strip().lstrip("#").strip().split())
        if len(line) >= 32 and (line in normalized_value or normalized_value in line):
            return True
    return False


def _override_problems(
    document: object, *, rule_index_body: str
) -> list[AdoptionContractProblem]:
    problems: list[AdoptionContractProblem] = []
    if not isinstance(document, Mapping):
        return [_problem("override-schema", "override document must be an object")]
    if set(document) != {"schema", "overrides"}:
        problems.append(
            _problem(
                "override-schema",
                "override document must contain only schema and overrides",
            )
        )
    if document.get("schema") != OVERRIDE_SCHEMA:
        problems.append(
            _problem("override-schema", f"override schema must be {OVERRIDE_SCHEMA}")
        )
    overrides = document.get("overrides")
    if not isinstance(overrides, list):
        return problems + [_problem("override-schema", "overrides must be an array")]
    if len(overrides) > MAX_OVERRIDES:
        problems.append(
            _problem(
                "override-limit",
                f"override total {len(overrides)} exceeds limit {MAX_OVERRIDES}",
            )
        )

    categories: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    for index, override in enumerate(overrides):
        if not isinstance(override, Mapping):
            problems.append(
                _problem("override-schema", f"override {index} must be an object")
            )
            continue
        if set(override) != _OVERRIDE_FIELDS:
            problems.append(
                _problem(
                    "override-schema",
                    f"override {index} must contain only category, value, and reason",
                )
            )
        category = override.get("category")
        value = override.get("value")
        reason = override.get("reason")
        if category not in OVERRIDE_LIMITS:
            problems.append(
                _problem(
                    "override-category",
                    f"override {index} has unsupported category {category!r}",
                )
            )
            continue
        categories[category] += 1
        if not isinstance(value, str) or not value.strip():
            problems.append(
                _problem("override-schema", f"override {index} value must be non-empty")
            )
            continue
        if not isinstance(reason, str) or not reason.strip():
            problems.append(
                _problem(
                    "override-schema", f"override {index} reason must be non-empty"
                )
            )
        key = (category, value)
        if key in seen:
            problems.append(
                _problem(
                    "override-duplicate",
                    f"override {index} duplicates category {category!r} value {value!r}",
                )
            )
        seen.add(key)
        if (
            category in {"scan-root", "exclusion"}
            and _safe_relative_path(value) is None
        ):
            problems.append(
                _problem(
                    "override-path",
                    f"override {index} {category} must be a repository-relative path",
                )
            )
        if category == "repository-rule" and _copied_rule_body(value, rule_index_body):
            problems.append(
                _problem(
                    "copied-rule-body",
                    f"override {index} copies text from the Hub rule index",
                )
            )

    for category, count in categories.items():
        limit = OVERRIDE_LIMITS[category]
        if count > limit:
            problems.append(
                _problem(
                    "override-limit",
                    f"override category {category!r} has {count} entries; limit is {limit}",
                )
            )
    return problems


def validate_adoption_contract(
    contract: object,
    *,
    hub_root: Path = ROOT,
    adopter_root: Path,
) -> list[AdoptionContractProblem]:
    """Validate one adopter's immutable connection to the Hub rule source."""
    problems: list[AdoptionContractProblem] = []
    if not isinstance(contract, Mapping):
        return [_problem("schema", "contract must be a JSON object")]
    unknown = set(contract) - _CONTRACT_FIELDS
    missing = _CONTRACT_FIELDS - set(contract)
    if unknown:
        problems.append(_problem("schema", f"unsupported fields: {sorted(unknown)}"))
    if missing:
        problems.append(_problem("schema", f"missing fields: {sorted(missing)}"))
    if contract.get("contract_schema") != ADOPTION_CONTRACT_SCHEMA:
        problems.append(
            _problem(
                "schema-mismatch", f"contract_schema must be {ADOPTION_CONTRACT_SCHEMA}"
            )
        )
    if contract.get("hub_repository") != HUB_REPOSITORY:
        problems.append(
            _problem("hub-repository", f"hub_repository must be {HUB_REPOSITORY}")
        )
    revision = contract.get("hub_revision")
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        problems.append(
            _problem(
                "mutable-revision",
                "hub_revision must be a full lowercase 40-character commit SHA",
            )
        )

    profile = contract.get("profile")
    required_artifacts = (
        PROFILE_ARTIFACTS.get(profile) if isinstance(profile, str) else None
    )
    if required_artifacts is None:
        problems.append(
            _problem("profile-mismatch", f"unsupported profile {profile!r}")
        )
        required_artifacts = frozenset()

    artifacts = contract.get("validator_artifacts")
    observed_paths: set[str] = set()
    if not isinstance(artifacts, list) or not artifacts:
        problems.append(
            _problem("artifact-schema", "validator_artifacts must be a non-empty array")
        )
    else:
        for index, artifact in enumerate(artifacts):
            if not isinstance(artifact, Mapping) or set(artifact) != {"path", "sha256"}:
                problems.append(
                    _problem(
                        "artifact-schema",
                        f"validator artifact {index} must contain only path and sha256",
                    )
                )
                continue
            path_value = _safe_relative_path(artifact.get("path"))
            digest = artifact.get("sha256")
            if path_value is None:
                problems.append(
                    _problem(
                        "artifact-path", f"validator artifact {index} path is unsafe"
                    )
                )
                continue
            observed_paths.add(path_value)
            if (
                not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                problems.append(
                    _problem(
                        "artifact-digest",
                        f"validator artifact {path_value} has an invalid SHA-256 digest",
                    )
                )
                continue
            target = hub_root / path_value
            if not target.is_file():
                problems.append(
                    _problem(
                        "artifact-path", f"validator artifact {path_value} is missing"
                    )
                )
            elif _sha256(target) != digest:
                problems.append(
                    _problem(
                        "artifact-digest-mismatch",
                        f"validator artifact {path_value} does not match its SHA-256 digest",
                    )
                )
    if required_artifacts and observed_paths != set(required_artifacts):
        problems.append(
            _problem(
                "profile-artifacts",
                f"profile {profile} requires exactly {sorted(required_artifacts)}",
            )
        )

    rule_index = contract.get("rule_index")
    rule_index_body = ""
    if rule_index != RULE_INDEX:
        problems.append(_problem("rule-index", f"rule_index must be {RULE_INDEX}"))
    if isinstance(rule_index, str) and "#" in rule_index:
        rule_path_value, anchor = rule_index.split("#", 1)
        safe_rule_path = _safe_relative_path(rule_path_value)
        if safe_rule_path is None or not anchor:
            problems.append(
                _problem("rule-index", "rule_index path or anchor is invalid")
            )
        else:
            rule_path = hub_root / safe_rule_path
            if not rule_path.is_file():
                problems.append(_problem("rule-index", "rule_index file is missing"))
            else:
                rule_index_body = rule_path.read_text(encoding="utf-8")
                if not _heading_anchor_exists(rule_path, anchor):
                    problems.append(
                        _problem(
                            "rule-index", f"rule_index anchor {anchor!r} is missing"
                        )
                    )
    else:
        problems.append(
            _problem("rule-index", "rule_index must contain a path and anchor")
        )

    override_path_value = _safe_relative_path(contract.get("repository_overrides"))
    if override_path_value is None:
        problems.append(
            _problem(
                "override-path",
                "repository_overrides must be a repository-relative path",
            )
        )
    else:
        override_path = adopter_root / override_path_value
        if not override_path.is_file():
            problems.append(
                _problem(
                    "override-path", f"override file {override_path_value} is missing"
                )
            )
        else:
            try:
                override_document = json.loads(
                    override_path.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError as exc:
                problems.append(
                    _problem(
                        "override-schema", f"override file is invalid JSON: {exc.msg}"
                    )
                )
            else:
                problems.extend(
                    _override_problems(
                        override_document, rule_index_body=rule_index_body
                    )
                )
    return problems


def check_adoption_contract_file(
    contract_path: Path, *, hub_root: Path = ROOT, adopter_root: Path | None = None
) -> list[str]:
    """Load and validate a contract for either cross-repository CLI direction."""
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [
            _problem("schema", f"contract file {contract_path} is missing").render()
        ]
    except json.JSONDecodeError as exc:
        return [
            _problem("schema", f"contract file is invalid JSON: {exc.msg}").render()
        ]
    root = adopter_root if adopter_root is not None else contract_path.parent
    return [
        problem.render()
        for problem in validate_adoption_contract(
            contract, hub_root=hub_root, adopter_root=root
        )
    ]


@dataclass(frozen=True)
class Row:
    citing: str
    repo: str
    path: str
    probe: str
    role: str
    what: str
    line: int
    ref: str = "main"


PUBLIC_AUTHORITY_SCHEMA = "knowledge-quality/public-authority/v1"
LOCAL_CHECKOUT_SCHEMA = "knowledge-quality/local-checkout/v1"
LOCAL_ONLY_SCHEMA = "knowledge-quality/local-only-kiro/v1"
AUTHORITY_MAP_SCHEMA = "knowledge-quality/authority-map/v1"


@dataclass(frozen=True)
class PublicAuthorityRecord:
    repository_id: int
    canonical_full_name: str
    default_branch: str
    default_branch_head_sha: str
    visibility: str
    archived: bool


@dataclass(frozen=True)
class LocalCheckoutRecord:
    path: str
    included: bool
    reason: str
    repository_id: int | None = None
    authority_state: str = "NOT_APPLICABLE"
    authority_reason: str = "not evaluated"
    remote: str | None = None
    head_sha: str | None = None
    branch: str | None = None
    detached: bool = False
    dirty: bool = False
    ahead: int | None = None
    behind: int | None = None
    worktree_git_dir: str | None = None
    duplicate: bool = False
    stale: bool = False


@dataclass(frozen=True)
class LocalOnlyKiroRecord:
    project_key: str
    checkout_path: str
    head_sha: str
    branch: str | None
    detached: bool
    dirty: bool
    reason: str


@dataclass(frozen=True)
class AuthorityResolution:
    state: str
    record: PublicAuthorityRecord | None
    reason: str


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _github_coordinates(remote: str | None) -> tuple[str, str] | None:
    """Return owner/repository for a GitHub origin without changing local Git state."""
    if not remote:
        return None
    value = remote.strip().removesuffix(".git")
    match = re.match(
        r"^(?:https?://github\.com/|ssh://git@github\.com/|git@github\.com:)([^/]+)/([^/]+)$",
        value,
    )
    if not match:
        return None
    return match.group(1), match.group(2)


def _github_headers() -> dict[str, str]:
    headers = {
        "User-Agent": "cross-repo-check",
        "Accept": "application/vnd.github+json",
    }
    # Authentication raises the request budget but does not widen the inventory: a response whose
    # visibility is not public is rejected before it can become a PublicAuthorityRecord.
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def resolve_public_authority(
    owner: str,
    repo: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> AuthorityResolution:
    """Resolve immutable public identity and its current default-branch head.

    A missing public repository is a definite non-match. Authentication, throttling, server,
    DNS, and timeout failures remain inconclusive and never fabricate a local-only identity.
    """
    metadata_url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        request = urllib.request.Request(metadata_url, headers=_github_headers())
        with opener(request, timeout=30) as response:
            metadata = json.loads(response.read().decode("utf-8", "replace"))
        if not isinstance(metadata, dict):
            return AuthorityResolution(
                "INCONCLUSIVE", None, "public metadata response is not an object"
            )
        repository_id = metadata.get("id")
        full_name = metadata.get("full_name")
        default_branch = metadata.get("default_branch")
        visibility = metadata.get("visibility")
        archived = metadata.get("archived")
        if (
            not isinstance(repository_id, int)
            or not isinstance(full_name, str)
            or not isinstance(default_branch, str)
            or not isinstance(visibility, str)
            or not isinstance(archived, bool)
        ):
            return AuthorityResolution(
                "INCONCLUSIVE", None, "public metadata response is incomplete"
            )
        if visibility != "public":
            return AuthorityResolution(
                "DEFECT",
                None,
                "repository is not public and cannot be public authority",
            )
        head_url = f"{metadata_url}/commits/{default_branch}"
        request = urllib.request.Request(head_url, headers=_github_headers())
        with opener(request, timeout=30) as response:
            head = json.loads(response.read().decode("utf-8", "replace"))
        if not isinstance(head, dict):
            return AuthorityResolution(
                "INCONCLUSIVE",
                None,
                "default-branch response is not an object",
            )
        head_sha = head.get("sha")
        if not isinstance(head_sha, str) or not re.fullmatch(
            r"[0-9a-fA-F]{40}", head_sha
        ):
            return AuthorityResolution(
                "INCONCLUSIVE",
                None,
                "default-branch response carries no full commit SHA",
            )
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return AuthorityResolution(
                "DEFECT", None, "public repository not found (404)"
            )
        return AuthorityResolution(
            "INCONCLUSIVE", None, f"GitHub returned HTTP {exc.code}"
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return AuthorityResolution(
            "INCONCLUSIVE", None, f"GitHub request failed: {exc}"
        )
    return AuthorityResolution(
        "PASS",
        PublicAuthorityRecord(
            repository_id=repository_id,
            canonical_full_name=full_name,
            default_branch=default_branch,
            default_branch_head_sha=head_sha.lower(),
            visibility=visibility,
            archived=archived,
        ),
        "resolved from GitHub public metadata and default-branch head",
    )


def _candidate_directories(root: Path, max_depth: int) -> list[Path]:
    """Find bounded project roots that expose Git or Kiro markers.

    Descendants of a project root are not scanned as independent projects. This prevents a
    checkout's internal directories from inflating the candidate set while still retaining
    non-Git Kiro directories and Git checkouts without Kiro as reasoned exclusions.
    """
    if max_depth < 0:
        raise ValueError("max_depth must be zero or greater")
    if not root.is_dir():
        raise ValueError(f"inventory root is not a directory: {root}")
    candidates: list[Path] = []
    pending = [(root, 0)]
    while pending:
        current, depth = pending.pop(0)
        has_marker = (current / ".git").exists() or (current / ".kiro").exists()
        if has_marker:
            candidates.append(current)
            continue
        if depth >= max_depth:
            continue
        try:
            children = sorted(path for path in current.iterdir() if path.is_dir())
        except OSError:
            continue
        pending.extend((child, depth + 1) for child in children)
    return candidates


def _git(
    checkout: Path,
    args: list[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    return runner(
        ["git", "-C", str(checkout), *args],
        capture_output=True,
        text=True,
        check=False,
        env={
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        },
    )


def _git_value(
    checkout: Path,
    args: list[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> str | None:
    result = _git(checkout, args, runner=runner)
    return result.stdout.strip() if result.returncode == 0 else None


def build_read_only_inventory(
    projects_root: Path,
    max_depth: int,
    *,
    resolver: Callable[[str, str], AuthorityResolution] = resolve_public_authority,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Build separate public, local-checkout, and local-only records.

    Every subprocess command is a Git read. Public authority is keyed only by GitHub repository
    ID. Local paths and local-only keys remain in private inventory records and are absent from
    the public-safe aggregate returned by :func:`public_inventory_aggregate`.
    """
    authorities: dict[int, PublicAuthorityRecord] = {}
    local_records: list[LocalCheckoutRecord] = []
    local_only: list[LocalOnlyKiroRecord] = []
    eligible_indexes: list[int] = []
    candidates = _candidate_directories(projects_root, max_depth)
    if not candidates:
        raise ValueError("inventory scan found no Git/Kiro candidates")

    for candidate in candidates:
        inside = _git_value(
            candidate, ["rev-parse", "--is-inside-work-tree"], runner=runner
        )
        if inside != "true":
            local_records.append(
                LocalCheckoutRecord(
                    path=str(candidate),
                    included=False,
                    reason="excluded: not a Git repository",
                )
            )
            continue
        if not (candidate / ".kiro").is_dir():
            local_records.append(
                LocalCheckoutRecord(
                    path=str(candidate),
                    included=False,
                    reason="excluded: Kiro configuration is absent",
                )
            )
            continue

        head = _git_value(candidate, ["rev-parse", "HEAD"], runner=runner)
        if not head:
            local_records.append(
                LocalCheckoutRecord(
                    path=str(candidate),
                    included=False,
                    reason="excluded: Git HEAD cannot be read",
                )
            )
            continue
        branch = _git_value(
            candidate, ["symbolic-ref", "--quiet", "--short", "HEAD"], runner=runner
        )
        status = _git_value(candidate, ["status", "--porcelain"], runner=runner)
        remote = _git_value(candidate, ["remote", "get-url", "origin"], runner=runner)
        counts = _git_value(
            candidate,
            ["rev-list", "--left-right", "--count", "@{upstream}...HEAD"],
            runner=runner,
        )
        behind = ahead = None
        if counts and re.fullmatch(r"\d+\s+\d+", counts):
            behind, ahead = (int(value) for value in counts.split())
        git_dir = _git_value(
            candidate, ["rev-parse", "--absolute-git-dir"], runner=runner
        )
        coordinates = _github_coordinates(remote)
        resolution = (
            resolver(*coordinates)
            if coordinates
            else AuthorityResolution(
                "DEFECT", None, "origin is absent or is not a GitHub repository"
            )
        )
        repository_id = (
            resolution.record.repository_id if resolution.record is not None else None
        )
        if resolution.record is not None:
            existing = authorities.get(repository_id)
            if existing is not None and existing != resolution.record:
                raise ValueError(
                    "conflicting public authority records for repository ID "
                    f"{repository_id}"
                )
            authorities[repository_id] = resolution.record
        record = LocalCheckoutRecord(
            path=str(candidate),
            included=True,
            reason="included: Git repository with Kiro configuration",
            repository_id=repository_id,
            authority_state=resolution.state,
            authority_reason=resolution.reason,
            remote=remote,
            head_sha=head,
            branch=branch,
            detached=branch is None,
            dirty=bool(status),
            ahead=ahead,
            behind=behind,
            worktree_git_dir=git_dir,
            stale=(
                resolution.record is not None
                and head.lower() != resolution.record.default_branch_head_sha
            ),
        )
        local_records.append(record)
        eligible_indexes.append(len(local_records) - 1)
        if resolution.state == "DEFECT" and resolution.record is None:
            local_only.append(
                LocalOnlyKiroRecord(
                    project_key=f"local-{len(local_only) + 1:04d}",
                    checkout_path=str(candidate),
                    head_sha=head,
                    branch=branch,
                    detached=branch is None,
                    dirty=bool(status),
                    reason=resolution.reason,
                )
            )

    counts_by_id: dict[int, int] = {}
    for index in eligible_indexes:
        repository_id = local_records[index].repository_id
        if repository_id is not None:
            counts_by_id[repository_id] = counts_by_id.get(repository_id, 0) + 1
    for index in eligible_indexes:
        record = local_records[index]
        if record.repository_id is not None and counts_by_id[record.repository_id] > 1:
            local_records[index] = replace(record, duplicate=True)

    public_records = [asdict(authorities[key]) for key in sorted(authorities)]
    checkout_records = [asdict(record) for record in local_records]
    local_only_records = [asdict(record) for record in local_only]
    joined = [
        {
            "repository_id": repository_id,
            "checkout_indexes": [
                index
                for index, record in enumerate(local_records)
                if record.repository_id == repository_id
            ],
        }
        for repository_id in sorted(authorities)
    ]
    return {
        "public_authority": {
            "schema": PUBLIC_AUTHORITY_SCHEMA,
            "generated_at": _timestamp(),
            "records": public_records,
        },
        "local_checkouts": {
            "schema": LOCAL_CHECKOUT_SCHEMA,
            "generated_at": _timestamp(),
            "scan_root": str(projects_root),
            "max_depth": max_depth,
            "records": checkout_records,
        },
        "local_only_kiro": {
            "schema": LOCAL_ONLY_SCHEMA,
            "generated_at": _timestamp(),
            "records": local_only_records,
        },
        "authority_map": {
            "schema": AUTHORITY_MAP_SCHEMA,
            "generated_at": _timestamp(),
            "authoritative_repository_count": len(public_records),
            "joins": joined,
            "inconclusive_checkout_indexes": [
                index
                for index, record in enumerate(local_records)
                if record.included and record.authority_state == "INCONCLUSIVE"
            ],
        },
    }


def public_inventory_aggregate(inventory: dict[str, Any]) -> dict[str, int]:
    """Project only public-authority facts; local state is private inventory data."""
    return {
        "authoritative_repository_count": inventory["authority_map"][
            "authoritative_repository_count"
        ]
    }


def write_inventory_snapshots(inventory: dict[str, Any], output_dir: Path) -> None:
    """Write four private snapshots; callers choose the ignored destination."""
    output_dir.mkdir(parents=True, exist_ok=True)
    names = {
        "public_authority": "public-authority.json",
        "local_checkouts": "local-checkouts.json",
        "local_only_kiro": "local-only-kiro.json",
        "authority_map": "authority-map.json",
    }
    for key, name in names.items():
        (output_dir / name).write_text(
            json.dumps(inventory[key], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def prose_files() -> list[Path]:
    seen: dict[Path, None] = {}
    for pattern in PROSE_GLOBS:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            if SKIP_PARTS & set(path.relative_to(ROOT).parts):
                continue
            seen[path] = None
    return sorted(seen)


def parse_table() -> tuple[list[Row], list[str]]:
    problems: list[str] = []
    if not INDEX.exists():
        return [], [f"{INDEX.relative_to(ROOT)} is missing"]

    lines = INDEX.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if TABLE_START in line)
        end = next(i for i, line in enumerate(lines) if TABLE_END in line)
    except StopIteration:
        return [], [
            (
                f"{INDEX.relative_to(ROOT)}: the table markers "
                f"{TABLE_START} / {TABLE_END} must both be present"
            )
        ]

    rows: list[Row] = []
    for offset, raw in enumerate(lines[start + 1 : end], start=start + 2):
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 6:
            problems.append(
                f"{INDEX.relative_to(ROOT)}:{offset}: expected 6 columns, found {len(cells)}. "
                "The gate reads this table, so a changed shape is a broken gate."
            )
            continue
        if cells[0].startswith("---") or cells[0] in {"引用元"}:
            continue
        citing, repo, path, probe, role, what = (c.strip("`") for c in cells)
        if not all((citing, repo, path, probe, role)):
            problems.append(
                f"{INDEX.relative_to(ROOT)}:{offset}: a required cell is empty"
            )
            continue
        if role not in ROLES:
            problems.append(
                f"{INDEX.relative_to(ROOT)}:{offset}: role {role!r} is not one of "
                f"{', '.join(sorted(ROLES))}. The value is published in "
                f"{CONTRACT.relative_to(ROOT)} and read by the cited repository, so an "
                "unrecognized one leaves it unable to tell a retraction from an extension."
            )
            continue
        rows.append(Row(citing, repo, path, probe, role, what, offset))
    return rows, problems


def refs_in_prose() -> dict[tuple[str, str], str]:
    """Map each cited (repo, path) to the ref the citing prose pins it to.

    Every citation points at `blob/main` today. A citation pinned to a commit is the
    ordinary response to a source that keeps moving, and verifying that against `main`
    would check a revision the reader never sees.
    """
    found: dict[tuple[str, str], str] = {}
    for path in prose_files():
        body = strip_code(path.read_text(encoding="utf-8"))
        for match in BLOB_LINK.finditer(body):
            found.setdefault(
                (match.group("repo"), match.group("path")), match.group("ref")
            )
    return found


def check_offline(rows: list[Row]) -> list[str]:
    problems: list[str] = []

    # Registered rows must point at a real citing file that really carries the link.
    for row in rows:
        citing = ROOT / row.citing
        if not citing.exists():
            problems.append(
                f"{INDEX.relative_to(ROOT)}:{row.line}: citing file {row.citing} does not exist"
            )
            continue
        body = strip_code(citing.read_text(encoding="utf-8"))
        wanted = f"https://github.com/{OWNER}/{row.repo}/blob/"
        if wanted not in body or row.path not in body:
            problems.append(
                f"{INDEX.relative_to(ROOT)}:{row.line}: {row.citing} does not link to "
                f"{row.repo}/{row.path}. A registered citation that nobody makes is a stale row."
            )

    # Every citation in prose must be registered, per citing file. Keying on the cited path
    # alone would let a second document cite the same claim unrecorded — and when a probe does
    # fail, what you need is every file that has to be revisited, not one of them.
    registered = {(r.citing, r.repo, r.path) for r in rows}
    for path in prose_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == INDEX.relative_to(ROOT).as_posix():
            continue
        body = strip_code(path.read_text(encoding="utf-8"))
        for match in BLOB_LINK.finditer(body):
            repo, cited = match.group("repo"), match.group("path")
            if repo == THIS_REPO:
                continue  # A link into our own repository is not a cross-repo citation.
            if (rel, repo, cited) not in registered:
                problems.append(
                    f"{rel}: cites {repo}/{cited} with no row for this file in "
                    f"{INDEX.relative_to(ROOT)}. Add one, with a probe string naming the claim. "
                    "Another file citing the same path does not cover this one."
                )
    return problems


def check_self_paths() -> list[str]:
    """Resolve absolute links that point back into this repository, against this working tree.

    The whole path problem looked like one thing needing the citation index and the network, so
    it sat in the network half. One subset needs neither: **an absolute URL pointing back into the
    repository doing the checking** can be resolved against the files already on disk. It is
    deterministic and entirely within our control, so it belongs in the per-commit gate rather
    than the weekly one — the reasoning that keeps vendor URLs out of a blocking gate does not
    transfer to a link we can break ourselves and fix ourselves.

    `check_offline` skipped these deliberately, on the correct ground that a self-link is not a
    cross-repository citation. That is true about *citation* and says nothing about whether the
    path exists, which is how a self-link to a deleted file passed both halves.

    Two boundaries, drawn on purpose:

    - **A ref other than `main` is inconclusive, not dead.** A commit-pinned or branch-pinned link
      points at a revision this working tree need not hold, so resolving it here would report a
      defect that does not exist.
    - **Paths inside sibling repositories stay out of scope.** Those genuinely need the network and
      the index, and they are covered by ``--external``.

    Credit where it belongs: a sibling repository found this subset was free after both of us had
    filed the path gap as a single problem that needed infrastructure.
    """
    problems: list[str] = []
    for path in prose_files():
        rel = path.relative_to(ROOT).as_posix()
        body = strip_code(path.read_text(encoding="utf-8"))
        for match in PATH_LINK.finditer(body):
            if match.group("repo") != THIS_REPO:
                continue
            if match.group("ref") != "main":
                continue
            target = match.group("path").rstrip("/")
            if (ROOT / target).exists():
                continue
            problems.append(
                f"{rel}: links to {target} in this repository, which does not exist. "
                "The repository name is correct, so the name check passes — the path moved. "
                "Fix the link, or the file, before this ships."
            )
    return problems


def contract_lines(rows: list[Row]) -> list[str]:
    """The published view of the table: one line per cited string, deduplicated.

    Keyed on the cited side, so two of our documents citing the same claim collapse to one line.
    Which of our files carries a citation is what `check_offline` is for; the repository being
    cited needs the set of strings it must not silently reword, and nothing else.
    """
    return sorted({f"{r.repo}\t{r.path}\t{r.role}\t{r.probe}" for r in rows})


def stored_contract() -> list[str] | None:
    if not CONTRACT.exists():
        return None
    return sorted(
        line.rstrip("\n")
        for line in CONTRACT.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def check_contract(rows: list[Row]) -> list[str]:
    """Fail when the published contract no longer matches the table it is generated from.

    Without this the file is exactly the hand-maintained copy the docstring refuses. With it, a row
    added or a probe reworded here cannot reach `main` while the published view still shows the old
    one — which matters because the other side reads the published view, not this table.
    """
    current = contract_lines(rows)
    previous = stored_contract()
    if previous is None:
        return [
            (
                f"{CONTRACT.relative_to(ROOT)} is missing. "
                "Generate it with: python3 tools/check_cross_repo.py --write-contract"
            )
        ]
    problems = [
        f"contract is missing: {line}" for line in current if line not in previous
    ]
    problems += [
        f"contract has a stale line: {line}" for line in previous if line not in current
    ]
    if problems:
        problems.append(
            f"{CONTRACT.relative_to(ROOT)} is generated from {INDEX.relative_to(ROOT)} and read by "
            "the cited repository. Regenerate it in the same change: "
            "python3 tools/check_cross_repo.py --write-contract"
        )
    return problems


def check_repo_names() -> list[str]:
    """Fail on a repository name that is not the repository's current name.

    Renames are normal. What is not survivable is that the old name keeps resolving, so two
    documents can name the same repository differently and neither looks broken. The citation
    table keys on the name, so a stale one there also silently splits one repository into two.

    This asks the API for `full_name` rather than following an HTML redirect, because **a
    case-only rename does not redirect.** GitHub resolves repository names case-insensitively
    and serves the requested casing with 200, so comparing the final URL reports the old name
    as current. Two of the seven stale names this check was written for were case-only, and the
    first redirect-based version was silent on both — while passing a break test that happened
    to use one of the five that do redirect. Proving a detector fires on one instance of a
    family says nothing about the rest of the family.
    """
    problems: list[str] = []
    seen: dict[str, list[str]] = {}
    for path in prose_files():
        rel = path.relative_to(ROOT).as_posix()
        # Deliberately NOT strip_code(): a repository name inside a fenced block is usually a
        # `git clone` URL, which a reader runs. That is where an old name survives longest and
        # matters most. Fences are blanked for citations, where an example link is not a claim —
        # the two checks want opposite things from the same text.
        body = path.read_text(encoding="utf-8")
        for match in REPO_REF.finditer(body):
            repo = match.group("repo").rstrip(".")
            # A clone URL ends in `.git`, and clone URLs are the reason fences are scanned.
            repo = repo.removesuffix(".git")
            # This repository is not excluded. If it is renamed, its own self-references go
            # stale the same way, and nothing else would report them.
            seen.setdefault(repo, [])
            if rel not in seen[repo]:
                seen[repo].append(rel)

    for repo, files in sorted(seen.items()):
        url = f"https://api.github.com/repos/{OWNER}/{repo}"
        headers = {
            "User-Agent": "cross-repo-check",
            "Accept": "application/vnd.github+json",
        }
        # Unauthenticated is 60 requests an hour, which a few dozen repositories fits inside
        # once but not while iterating on this file. A token raises it to 5,000; CI has one.
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            # Three outcomes, not two, and the split is on the *status code* rather than the
            # exception type — `HTTPError` covers 404 and 403 alike, so branching on the type
            # collapses a verdict about the name into a verdict about the request.
            #
            #   404  DEAD          the name resolves to nothing. A definite defect.
            #   403  INCONCLUSIVE  rate limited or forbidden. Says nothing about the name.
            #   else INCONCLUSIVE  outage, DNS, timeout.
            #
            # The tell is asymmetry in arrival, which a sibling repository named: a rename or a
            # dead link appears one repository at a time, while rate limiting appears for every
            # name at once. Classify 403 as a stale name and a single throttled run reports the
            # whole tree as stale — which is how a gate teaches people to ignore it.
            status = getattr(exc, "code", None)
            if status == 404:
                # A 404 is two defects, not one. This is precisely what a link checker catches,
                # so if this gate is the thing that found it, no link checker ran that path.
                problems.append(
                    f"{repo}: DEAD — the name resolves to nothing (404). "
                    f"Fix the name, and check why no link check covered it: {sorted(files)}"
                )
            else:
                problems.append(f"{repo}: INCONCLUSIVE — cannot resolve ({exc})")
            continue
        full_name = str(payload.get("full_name", ""))
        canonical = full_name.rsplit("/", 1)[-1] if "/" in full_name else ""
        if not canonical:
            problems.append(f"{repo}: the API response carried no full_name")
            continue
        if canonical != repo:
            listed = ", ".join(files[:4]) + (" …" if len(files) > 4 else "")
            problems.append(
                f"{repo} is not the current name; it is {canonical}. The old name still "
                f"resolves, so nothing else reports it. Update: {listed}"
            )
    return problems


def check_own_org_paths(rows: list[Row]) -> list[str]:
    """Resolve every path into this account's repositories that no probe already covers.

    The category rule is **what a failure means**, not where the URL points. A vendor URL can fail
    for reasons no local change fixes, which is why it stays out of a blocking gate. **A URL into an
    account we own cannot**: a 404 there is a defect we introduced and can fix, so it belongs in a
    gate that fails.

    This existed as a recorded gap and stayed open one release too long. A DEAD name was reported
    with the note that a 404 is what a link checker catches — and then the link check here turned out
    to skip every http(s) URL unless asked, with `--external` wired into no workflow. **Twenty-one
    tree links into one sibling repository were verified by nothing.**

    Registered citations are skipped: their probe already reads the file's contents, which cannot
    succeed if the path is gone. What is left is navigation — `tree/` links, and blob links nobody
    registered because they are not claims.

    Own-repository paths are resolved offline by `check_self_paths` and skipped here, so the network
    is only used where it is the only option.
    """
    problems: list[str] = []
    registered = {(r.repo, r.path) for r in rows}
    cache: dict[tuple[str, str, str], str | None] = {}
    headers = {
        "User-Agent": "cross-repo-check",
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for path in prose_files():
        rel = path.relative_to(ROOT).as_posix()
        body = strip_code(path.read_text(encoding="utf-8"))
        for match in PATH_LINK.finditer(body):
            repo, ref = match.group("repo"), match.group("ref")
            target = match.group("path").rstrip("/")
            if repo == THIS_REPO:
                continue  # resolved offline against this working tree
            if (repo, target) in registered:
                continue  # the probe reads the file, so the path is already proven
            key = (repo, ref, target)
            if key in cache:
                verdict = cache[key]
            else:
                url = f"https://api.github.com/repos/{OWNER}/{repo}/contents/{target}?ref={ref}"
                request = urllib.request.Request(url, headers=headers)
                try:
                    with urllib.request.urlopen(request, timeout=30):
                        verdict = None
                except (
                    urllib.error.URLError,
                    urllib.error.HTTPError,
                    TimeoutError,
                ) as exc:
                    status = getattr(exc, "code", None)
                    if status == 404:
                        verdict = (
                            f"DEAD — {repo}@{ref}/{target} does not exist. The repository name "
                            "resolves, so the path moved. A reader following this link gets a 404"
                        )
                    else:
                        verdict = (
                            f"INCONCLUSIVE — cannot resolve {repo}/{target} ({exc})"
                        )
                cache[key] = verdict
            if verdict:
                problems.append(f"{rel}: {verdict}")
    return problems


def check_external(rows: list[Row]) -> list[str]:
    """Fetch each cited file and confirm the probe string still appears in it.

    **A server that did not answer is not a citation that is wrong.** This conflated the two: every
    exception became "cannot fetch", which fails the scheduled run with a message that reads like a
    moved file. A sibling repository measured the case that makes this matter — github.com's HTML
    endpoint returns 504 **persistently** for particular repositories on a hosted runner while the
    REST API answers immediately, and it had read a local pass as evidence about the runner. This
    repository's blocking path asks `api.github.com` and `raw.githubusercontent.com`, so that
    specific 504 does not reach it, but the category error was here regardless.

    So the verdicts split. **404 is a problem**: the file moved and the citation now sends a reader
    nowhere. **5xx, a timeout, or a DNS failure is undetermined**: nothing was learned about the
    citation, and reporting it as broken teaches people to ignore a check that is right the rest of
    the time.

    **The known limit: a citation that is undetermined every week is indistinguishable here from one
    that is checked and passes.** Reporting it every time is the whole of the mitigation — recording
    consecutive-run state is not worth a database in a repository with no runtime.
    """
    problems: list[str] = []
    undetermined: list[str] = []
    cache: dict[tuple[str, str, str], str | None] = {}
    for row in rows:
        # Fetch the ref the citation actually points at. Assuming `main` would verify a
        # commit-pinned citation against a different file than the reader is sent to.
        key = (row.repo, row.ref, row.path)
        if key not in cache:
            url = f"https://raw.githubusercontent.com/{OWNER}/{row.repo}/{row.ref}/{row.path}"
            request = urllib.request.Request(
                url, headers={"User-Agent": "cross-repo-check"}
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    cache[key] = response.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as exc:
                cache[key] = None
                if exc.code == 404:
                    problems.append(f"{row.repo}/{row.path}: gone (HTTP 404)")
                else:
                    undetermined.append(f"{row.repo}/{row.path}: HTTP {exc.code}")
            except (urllib.error.URLError, TimeoutError) as exc:
                cache[key] = None
                undetermined.append(f"{row.repo}/{row.path}: unreachable ({exc})")
        body = cache[key]
        if body is None:
            continue
        # Presence and strength are answered by the same fetch, so classifying costs nothing extra.
        # `absent` keeps its original wording: it is the one verdict that says something about the
        # cited side rather than about our choice of string.
        result = verdict(row.probe, body)
        if result == "absent":
            problems.append(
                f"{row.repo}@{row.ref}/{row.path}: the probe {row.probe!r} is gone. Either the claim moved "
                f"or it was retracted — check before adjusting {row.citing}."
            )
        elif result == "duplicated":
            problems.append(
                f"{row.repo}@{row.ref}/{row.path}: the probe {row.probe!r} occurs more than once, so "
                "either copy can be reworded with this gate still green. Re-pin to a string that "
                f"appears once and names the claim {row.citing} rests on."
            )
        elif result == "heading-only":
            problems.append(
                f"{row.repo}@{row.ref}/{row.path}: the probe {row.probe!r} matches only a heading, so "
                "the section can keep its title while the content is replaced. Re-pin to the claim "
                "in body text."
            )
    if undetermined:
        print(
            "undetermined (the server did not answer; nothing learned about the citation):"
        )
        for line in undetermined:
            print(f"  ?   {line}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--external",
        action="store_true",
        help="Fetch each cited file and confirm the probe string is still present.",
    )
    parser.add_argument(
        "--write-contract",
        action="store_true",
        help="Regenerate docs/agent/cross-repo-probe-contract.txt from the table.",
    )
    parser.add_argument(
        "--inventory-root",
        type=Path,
        help="Read Git/Kiro candidates below this directory and write private snapshots.",
    )
    parser.add_argument(
        "--inventory-depth",
        type=int,
        default=2,
        help="Maximum directory depth for the bounded inventory scan (default: 2).",
    )
    parser.add_argument(
        "--inventory-output",
        type=Path,
        default=ROOT / ".private" / "knowledge-quality",
        help="Ignored directory for the four inventory snapshots.",
    )
    parser.add_argument(
        "--adoption-contract",
        type=Path,
        help="Validate an adopter contract while preserving the normal offline checks.",
    )
    parser.add_argument(
        "--adopter-root",
        type=Path,
        help="Repository root used to resolve repository_overrides.",
    )
    args = parser.parse_args()

    if args.inventory_root is not None:
        try:
            inventory = build_read_only_inventory(
                args.inventory_root.expanduser().resolve(), args.inventory_depth
            )
        except ValueError as exc:
            parser.error(str(exc))
        write_inventory_snapshots(inventory, args.inventory_output)
        public_summary = public_inventory_aggregate(inventory)
        local_records = inventory["local_checkouts"]["records"]
        eligible_count = sum(record["included"] for record in local_records)
        excluded_count = sum(not record["included"] for record in local_records)
        local_only_count = len(inventory["local_only_kiro"]["records"])
        inconclusive_count = len(
            inventory["authority_map"]["inconclusive_checkout_indexes"]
        )
        print(
            "inventory: "
            f"{public_summary['authoritative_repository_count']} public authority record(s), "
            f"{eligible_count} eligible checkout(s), "
            f"{local_only_count} local-only Kiro project(s), "
            f"{excluded_count} excluded candidate(s), "
            f"{inconclusive_count} inconclusive resolution(s)"
        )
        return 0

    rows, problems = parse_table()
    if args.adoption_contract is not None:
        problems += check_adoption_contract_file(
            args.adoption_contract,
            adopter_root=(
                args.adopter_root.expanduser().resolve()
                if args.adopter_root is not None
                else None
            ),
        )

    if args.write_contract:
        if problems:
            print("cannot generate the contract from a table that does not parse:")
            for problem in problems:
                print(f"  {problem}")
            return 1
        lines = contract_lines(rows)
        CONTRACT.parent.mkdir(parents=True, exist_ok=True)
        CONTRACT.write_text(CONTRACT_HEADER + "\n".join(lines) + "\n", encoding="utf-8")
        print(
            f"probe contract: wrote {len(lines)} probe(s) to {CONTRACT.relative_to(ROOT)}"
        )
        return 0

    problems += check_offline(rows)
    # Only meaningful against a table that parsed: rows dropped by a shape or vocabulary error
    # would otherwise be reported a second time as contract drift.
    if not problems:
        problems += check_contract(rows)
    # Offline and deterministic, so it runs in the per-commit gate rather than the weekly one.
    problems += check_self_paths()

    pinned = refs_in_prose()
    rows = [replace(row, ref=pinned.get((row.repo, row.path), row.ref)) for row in rows]
    if args.external and not problems:
        problems += check_repo_names()
        problems += check_external(rows)
        problems += check_own_org_paths(rows)

    if problems:
        print(f"cross-repo check failed ({len(problems)} issue(s)):")
        for problem in problems:
            print(f"  {problem}")
        return 1

    scope = "and every probe still present" if args.external else "registered"
    published = contract_lines(rows)
    reread = sum(1 for line in published if "\treread\t" in line)
    print(
        f"cross-repo: {len(rows)} citation(s) {scope}, "
        "and every absolute link into this repository names a path that exists; "
        f"{len(published)} probe(s) published, {reread} reread-only"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
