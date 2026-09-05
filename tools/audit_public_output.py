#!/usr/bin/env python3
"""Pre-publication audit for a public repository.

Five independent concerns, all of which have historically been caught late or not at all:

  1. naming      - "Amazon FSx for NetApp ONTAP" / "FSx for ONTAP" are the only accepted forms,
                   and three products must never be proposed.
  2. neutrality  - vendor-versus framing is inappropriate for an AWS Community Builder.
  3. pii         - personal names, account IDs, internal IPs, case numbers must never be committed.
  4. role-label  - inline callouts labeled with a job title imply a review that did not happen.
  5. support-referral - telling a reader to contact AWS or NetApp Support is not a finding, and
                   publishing it before a case exists puts a dead end in a knowledge base.

Two escape hatches, because there are two genuinely different reasons for a false positive.

Line level - a single line legitimately contains a flagged pattern:

    Some verbatim citation title containing the short form   <!-- allow:naming -->
    | `name@example.com` | "(internal reviewer)" |          <!-- allow:pii -->

File level - the whole document's job is to *define* the rules, so it must quote what it forbids.
Declare it once anywhere in the first 40 lines:

    <!-- audit-file-allow: naming,neutrality,pii -->

`allow:all` opts a single line out entirely. Use every marker sparingly: each one is a claim that
the match is a false positive, and a reviewer should be able to see why at a glance.

Run:  python3 tools/audit_public_output.py [--path DIR]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from frontmatter import IGNORED_DIRS

# `tools` is added on top of the shared list: these validators necessarily contain the
# patterns they search for, so auditing them reports every rule as a violation of itself.
SKIP_DIRS = (*IGNORED_DIRS, "tools")
# `.sh` is here because examples/ ships shell scripts. Leaving it out would have created the
# failure mode this repository has already hit twice: a detector that is silent because of its scan
# range rather than because the tree is clean. A script's comments carry exactly the naming, vendor
# and private-address content this audit exists to catch.
SCAN_SUFFIXES = {".md", ".txt", ".yml", ".yaml", ".json", ".sh"}

CATEGORIES = ("naming", "neutrality", "pii", "role-label", "support-referral")
ALLOW = re.compile(r"allow:(naming|neutrality|pii|role-label|support-referral|all)")
# Bounded so the trailing "-->" of the HTML comment is not swallowed into the category list.
FILE_ALLOW = re.compile(r"audit-file-allow:\s*([a-z-]+(?:\s*,\s*[a-z-]+)*)")
FILE_ALLOW_SCAN_LINES = 40

# ---------------------------------------------------------------- naming

NAMING_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bFSxN\b"), "use 'FSx for ONTAP'"),
    (re.compile(r"\bFSx\s+ONTAP\b"), "use 'FSx for ONTAP' (missing 'for')"),
    (re.compile(r"\bFSx\s+NetApp\b"), "use 'Amazon FSx for NetApp ONTAP'"),
    (
        re.compile(r"\bBlueXP\b|NetApp\s+Workload\s+Factory|NetApp\s+Console\b"),
        (
            "do not propose; reframe to CloudWatch / ONTAP REST API / FabricPool / DataSync / "
            "Snapshot-FlexClone-SnapMirror"
        ),
    ),
]

# Bare "FSx" that is prose rather than part of an accepted phrase or an identifier.
BARE_FSX = re.compile(
    r"(?<!Amazon\s)"  # "Amazon FSx" is the official family name, not an abbreviation
    r"\bFSx\b"
    r"(?!\s+for\s+(?:NetApp\s+)?ONTAP)"  # FSx for ONTAP / FSx for NetApp ONTAP
    r"(?!\s+for\s+(?:Windows|Lustre|OpenZFS))"  # sibling AWS services are legitimate
    r"(?!-for-ONTAP)"  # repo / URL slugs
    r"(?![-\w]*\.(?:md|py|ya?ml|json|svg|png|drawio))"  # filenames
)
# Contexts where "FSx" is a token, not prose. Matched against the same span as BARE_FSX
# rather than the whole line: as a line-wide test, one URL or one backticked identifier
# exempted every bare "FSx" beside it, and prose next to a link went unreported for as
# long as the rule existed. Links are common in these notes, so that was most of them.
IDENT_CONTEXT = re.compile(
    r"FSx[A-Za-z0-9_]*\s*[=:]|AWS::FSx|aws\s+fsx|\bfsx-|FSxOntap|FSX_"
)
# Spans where prose rules do not apply, removed before the prose tests run. Replaced with
# spaces so that reported column offsets and the "Amazon " lookbehind stay meaningful.
NON_PROSE = re.compile(r"https?://\S+|`[^`]*`")

# ---------------------------------------------------------------- neutrality

NEUTRALITY_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"競合(ツール|製品|他社)|より優れて|優位性|劣[るっ]て"),
        "use right-tool-for-the-job framing; state trade-offs symmetrically",
    ),
    (
        re.compile(r"\b(?:beats|outperforms)\s+\w", re.IGNORECASE),
        "avoid vendor-versus phrasing",
    ),
    (
        re.compile(
            r"\b(?:is|are)\s+(?:far\s+)?(?:better|superior|inferior)\s+(?:than|to)\b",
            re.IGNORECASE,
        ),
        "state which option suits which context instead",
    ),
    (
        re.compile(
            r"\bgame[- ]changer\b|\bbest[- ]in[- ]class\b|\bindustry[- ]leading\b",
            re.IGNORECASE,
        ),
        "avoid marketing superlatives; show, don't tell",
    ),
]

# ---------------------------------------------------------------- pii / internal identifiers

PII_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bcase\s*[#:]?\s*\d{5,}\b", re.IGNORECASE),
        "remove support case numbers; say 'filed with the vendor (tracked)'",
    ),
    (
        re.compile(r"\b[A-Z]{2,4}-I-\d{4,}\b"),
        "remove vendor-internal ticket IDs; say 'an internal product request (tracked)'",
    ),
    (
        re.compile(r"/Users/[A-Za-z][\w.-]*/"),
        "personal absolute path; use a relative path or ${PROJECT_DIR}",
    ),
    (
        re.compile(r"\b[\w.+-]+@(?!example\.(?:com|org)\b)[\w-]+\.[a-z]{2,}\b"),
        "remove email addresses; use '(internal reviewer)' or an example.com address",
    ),
    (
        re.compile(
            r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"
        ),
        "mask internal IPs as 10.0.x.x or <management-ip>",
    ),
]

# 12-digit AWS account IDs other than the sanctioned placeholder.
ACCOUNT_ID = re.compile(r"(?<![\d.\w])\d{12}(?![\d.\w])")
PLACEHOLDER_ACCOUNT = "123456789012"

# Inline callouts labeled with a role/persona imply a review that did not happen.
ROLE_LABEL = re.compile(
    r"^\s*>\s*\*\*[^*]*(?:lens|の視点|perspective)[^*]*\*\*", re.IGNORECASE
)

# ---------------------------------------------------------------- support referral
#
# Directing a reader to a vendor's support desk is not knowledge. It is the absence of it, and
# publishing it does three things a knowledge base should not: it hands the reader a dead end, it
# implies the question was pursued as far as it can be pursued, and it dates badly, because the
# behaviour that prompted it is usually documented somewhere already.
#
# This exists because it was written. A note in this repository once concluded that a FlexClone
# relationship blocking a volume deletion "could not be cleared" and that the remedy was to wait or
# to file with the vendor. The mechanism was ONTAP's volume recovery queue, documented, with a
# one-command remedy -- found only after a reviewer asked whether the question had been researched at
# all. The claim of impossibility and the support referral arrived together, and the referral is the
# half a regex can see.
#
# **Attribution is deliberately not matched.** "AWS Support confirmed X (date)" records where a fact
# came from and is how several notes here are sourced. What is matched is an instruction aimed at the
# reader: contact them, file with them, escalate to them. If a case really is the only remaining path,
# that belongs in `.private/`, not in a published note.
SUPPORT_REFERRAL = re.compile(
    r"(?:AWS\s+Support|NetApp\s+Support|ベンダー|サポート)\s*(?:に|へ)\s*"
    r"(?:問い合わせ|上げ|連絡|相談|起票|確認を依頼)"
    r"|(?:file|filing|open|raise|escalate)\s+(?:a\s+)?(?:support\s+)?(?:case|ticket)\s+with"
    r"|contact\s+(?:AWS|NetApp)\s*Support"
    r"|ベンダーに上げ|サポートケースを(?:開|起)",
    re.IGNORECASE,
)


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SCAN_SUFFIXES:
            yield path


def file_allowances(lines: list[str]) -> set[str]:
    """Categories a document opts out of wholesale via an audit-file-allow declaration."""
    allowed: set[str] = set()
    for line in lines[:FILE_ALLOW_SCAN_LINES]:
        match = FILE_ALLOW.search(line)
        if not match:
            continue
        for raw in match.group(1).split(","):
            category = raw.strip()
            if category in CATEGORIES:
                allowed.add(category)
            elif category:
                raise SystemExit(
                    f"audit-file-allow: unknown category {category!r} "
                    f"(allowed: {', '.join(CATEGORIES)})"
                )
    return allowed


def audit_line(
    line: str, file_allowed: frozenset[str] = frozenset()
) -> list[tuple[str, str]]:
    """Return (category, message) findings for one line, honouring allow markers."""
    allowed = {match.group(1) for match in ALLOW.finditer(line)} | set(file_allowed)
    if "all" in allowed:
        return []

    findings: list[tuple[str, str]] = []

    if "naming" not in allowed:
        for pattern, message in NAMING_RULES:
            if pattern.search(line):
                findings.append(("naming", message))
        prose = NON_PROSE.sub(lambda m: " " * len(m.group()), line)
        for match in BARE_FSX.finditer(prose):
            window = prose[max(0, match.start() - 12) : match.end() + 12]
            if not IDENT_CONTEXT.search(window):
                findings.append(("naming", "bare 'FSx'; use 'FSx for ONTAP'"))
                break

    if "neutrality" not in allowed:
        for pattern, message in NEUTRALITY_RULES:
            if pattern.search(line):
                findings.append(("neutrality", message))

    if "pii" not in allowed:
        for pattern, message in PII_RULES:
            if pattern.search(line):
                findings.append(("pii", message))
        for match in ACCOUNT_ID.finditer(line):
            if match.group() != PLACEHOLDER_ACCOUNT:
                findings.append(
                    ("pii", f"possible AWS account ID; use {PLACEHOLDER_ACCOUNT}")
                )
                break

    if "support-referral" not in allowed and SUPPORT_REFERRAL.search(line):
        findings.append(
            (
                "support-referral",
                (
                    "do not tell a reader to contact vendor support; publish the mechanism, or "
                    "record the open question in .private/ until there is an answer"
                ),
            )
        )
    if "role-label" not in allowed and ROLE_LABEL.match(line):
        findings.append(
            (
                "role-label",
                (
                    "role/persona-labeled callout implies a review that did not happen; "
                    "relabel to a neutral topic note (e.g. '**Security note**')"
                ),
            )
        )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(ROOT), help="directory to audit")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    findings: list[str] = []
    scanned = 0

    for path in iter_files(root):
        scanned += 1
        rel = path.relative_to(root)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            findings.append(f"{rel}: not valid UTF-8")
            continue
        file_allowed = frozenset(file_allowances(lines))
        for lineno, line in enumerate(lines, start=1):
            for category, message in audit_line(line, file_allowed):
                findings.append(f"{rel}:{lineno}: [{category}] {message}")

    if findings:
        print(f"Audit failed ({len(findings)} finding(s)):", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1

    print(f"audit: {scanned} file(s) clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
