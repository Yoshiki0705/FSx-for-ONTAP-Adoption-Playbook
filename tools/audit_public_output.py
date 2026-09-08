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
# The HTML comment wrapper is required, not decoration. Without it, **a line that merely mentions
# `allow:naming` in prose suppresses the detector on that line** - inside backticks too, so every
# line documenting these markers was exempting itself. Verified before tightening: one line in the
# tree relied on the loose form and no new finding appears. It also made the budget count prose as
# markers, so writing about a marker could fail `make allow-budget` with nothing wrong - the loud
# half of the same defect.
ALLOW = re.compile(
    r"<!--[^>]*?allow:(naming|neutrality|pii|role-label|support-referral|all)[^>]*?-->"
)
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

# `\b` is the wrong boundary in a Japanese repository, and it fails silently in the direction
# that matters most.
#
# Python defines `\b` in terms of `\w`, and `\w` matches CJK. So `\bFSx\b` matches `FSx を使う`
# and does **not** match `FSxを使う` — there is no boundary between `x` and `を`, because both
# are word characters. The same applies on the left: `のFSx` never matched either. Japanese prose
# attaches particles directly, so the common form is the one that went unreported, and this is
# the most-repeated rule in the project.
#
# Reported by a sibling repository, which hit the identical asymmetry in a parity checker: its
# trailing `(?![\w])` let `100 MB and up` match while `100MB以上` did not, so the check was
# silent on exactly the language it existed to read, and it inflated its own findings with false
# positives manufactured by the same rule.
#
# These say "not adjacent to an ASCII word character", which treats a Japanese character as a
# boundary. Do not replace them with `\b`.
ASCII_LEFT = r"(?<![A-Za-z0-9_])"
ASCII_RIGHT = r"(?![A-Za-z0-9_])"

# Bare "FSx" that is prose rather than part of an accepted phrase or an identifier.
BARE_FSX = re.compile(
    r"(?<!Amazon\s)"  # "Amazon FSx" is the official family name, not an abbreviation
    + ASCII_LEFT
    + r"FSx"
    + ASCII_RIGHT
    # The lookaheads follow the boundary, so they still see the text after "FSx".
    + r"(?!\s+for\s+(?:NetApp\s+)?ONTAP)"  # FSx for ONTAP / FSx for NetApp ONTAP
    + r"(?!\s+for\s+(?:Windows|Lustre|OpenZFS))"  # sibling AWS services are legitimate
    + r"(?!-for-ONTAP)"  # repo / URL slugs
    + r"(?![-\w]*\.(?:md|py|ya?ml|json|svg|png|drawio))"  # filenames
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
        # Explicit boundaries, not `\b`: see ASCII_LEFT. `課題AB-I-1234` was excluded by its own
        # leading boundary, and Japanese prose is where these IDs actually get written.
        re.compile(ASCII_LEFT + r"[A-Z]{2,4}-I-\d{4,}" + ASCII_RIGHT),
        "remove vendor-internal ticket IDs; say 'an internal product request (tracked)'",
    ),
    (
        re.compile(r"/Users/[A-Za-z][\w.-]*/"),
        "personal absolute path; use a relative path or ${PROJECT_DIR}",
    ),
    (
        # Explicit boundaries, not `\b`: see ASCII_LEFT. A Japanese character before the local
        # part suppressed the match, so `連絡先name@example.jp` went unreported.
        re.compile(
            r"(?<![0-9A-Za-z_.+-])[0-9A-Za-z_.+-]+@"
            r"(?!example\.(?:com|org)(?![0-9A-Za-z_.]))"
            r"[0-9A-Za-z-]+\.[a-z]{2,}(?![0-9A-Za-z_.])"
        ),
        "remove email addresses; use '(internal reviewer)' or an example.com address",
    ),
    (
        # Explicit boundaries, not `\b`: see ASCII_LEFT. `管理IPは10.0.0.1です` was suppressed at
        # both ends, which is the form an internal address appears in here.
        re.compile(
            r"(?<![0-9A-Za-z_.])"
            r"(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))"
            r"\.\d{1,3}\.\d{1,3}"
            r"(?![0-9A-Za-z_.])"
        ),
        "mask internal IPs as 10.0.x.x or <management-ip>",
    ),
]

# 12-digit AWS account IDs other than the sanctioned placeholder. The boundaries are explicit
# for the reason given at ASCII_LEFT: `\w` matches CJK, so `アカウント123456789013` was excluded
# by its own lookbehind.
ACCOUNT_ID = re.compile(r"(?<![0-9A-Za-z_.])\d{12}(?![0-9A-Za-z_.])")
PLACEHOLDER_ACCOUNT = "123456789012"

# Real resource identifiers. `fs-` and `svm-` were already covered by the account-ID rule only by
# accident of digit count, and the ONTAP cluster name form was covered by nothing: an FSx for ONTAP
# cluster is named `FsxId<hex>`, which is the file system ID with the `fs-` swapped for a prefix, so
# every CLI prompt and every `FileServer` dimension value carries it. A real one reached a published
# note and the audit passed, because no rule looked for it. The sanctioned stand-ins are the
# hex-digit placeholder from AGENTS.md and the literal EXAMPLE the ONTAP transcripts already use.
RESOURCE_ID = re.compile(r"\b(?:FsxId|fs-|svm-|vol-)[0-9a-f]{8,}\b")
PLACEHOLDER_RESOURCE_IDS = frozenset(
    {
        "fs-0123456789abcdef0",
        "svm-0123456789abcdef0",
        "vol-0123456789abcdef0",
    }
)

# Inline callouts labeled with a role/persona imply a review that did not happen.
#
# Two patterns, because the family is wider than the first one assumed. The first version matched
# `lens` and `の視点` in a blockquote callout. A sibling repository then reported two forms it could
# not see: `レンズ` (added), and `（Storage Specialist 観点）` as a *section heading* rather than a
# callout. Each miss was found by a person, not by this file — which is the argument for widening on
# the word list and on the form at the same time.
ROLE_LABEL = re.compile(
    r"^\s*>\s*\*\*[^*]*(?:lens|レンズ|の視点|視点|perspective)[^*]*\*\*", re.IGNORECASE
)

# `観点` and `視点` are ordinary words — 「セキュリティの観点から」 is not a role label. So this
# second pattern requires a role token *and* a lens word in the same label, which is what makes it
# read as "a person in this role reviewed this". It covers headings as well as callouts, because a
# heading carries the same implication and is more visible.
#
# The tokens are *job titles*, not fields of practice. A sibling repository drew this line while
# relabeling its own headings: it changed `（VMware Specialist 観点）` and `（Storage Specialist 観点）`
# and deliberately kept `（FinOps 観点）` and `（Reliability/Ops 観点）`, on the grounds that the latter
# name a subject rather than a person. That is the right cut, and this list did not make it — it
# carried bare `FinOps`, `AppSec`, `DevOps` and `SRE`, so 「FinOps 観点」 was rejected while
# 「Reliability/Ops 観点」 passed. Arbitrary, and in the direction that costs a gate its credibility:
# the ban exists because a job title implies a person in that role reviewed the content, and a field
# name implies no such thing. Dropping the bare disciplines loses no coverage, because the role forms
# of all four end in a title that is still listed — `FinOps Engineer`, `AppSec Engineer`. `SA`, `CISO`
# and `DPO` stay, being titles that stand alone.
_ROLE = (
    r"Specialist|Engineer|Architect|Officer|Analyst|Consultant|Manager|Lead|Admin|Reviewer|"
    r"Practitioner|SA\b|CISO|DPO|"
    r"スペシャリスト|エンジニア|アーキテクト|担当|責任者|レビュア"
)
_LENS = r"lens|レンズ|視点|観点|perspective"
ROLE_LABEL_WITH_ROLE = re.compile(
    rf"^\s*(?:>\s*\*\*|#{{2,6}}\s+)[^\n]*?(?:{_ROLE})[^\n]*?(?:{_LENS})", re.IGNORECASE
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


CODE_SPAN = re.compile(r"`[^`]*`")
# A fenced block and a code span are two forms of one rule - **this is code, not prose** - and only
# one of them was implemented. A sibling repository named the shape after finding the same split in
# its own detector: the recorded rule was not missing, its scope was one step too narrow.
FENCE = re.compile(r"^\s*(```|~~~)")


def _outside_code_spans(line: str):
    """Yield (segment, is_code) pairs so a rule can apply to prose only, once."""
    position = 0
    for match in CODE_SPAN.finditer(line):
        if match.start() > position:
            yield line[position : match.start()], False
        yield match.group(0), True
        position = match.end()
    if position < len(line):
        yield line[position:], False


def marker_categories(line: str, in_fence: bool = False) -> set[str]:
    """Categories this line *directs* to be suppressed.

    **The single definition of "is this a marker".** It was written three times - here, in the budget's
    counter, and in the inert check - and a fourth place removed markers from the raw line while the
    others detected them in the code-span-stripped one. **Widths that differ by one step produce a
    line that fails whether the marker stays or goes**, with each check correct on its own. A sibling
    repository hit exactly that and reported the fix: extract it, rather than align two copies, because
    two copies get touched one at a time.
    """
    if in_fence:
        return set()
    return {
        match.group(1)
        for segment, is_code in _outside_code_spans(line)
        if not is_code
        for match in ALLOW.finditer(segment)
    }


def strip_markers(line: str, in_fence: bool = False) -> str:
    """The line with its honoured markers removed, and nothing else.

    Paired with `marker_categories` deliberately: whatever counts as a marker is what gets removed. A
    marker shown inside a code span is an example, so it survives here - the earlier version removed
    it, which is the width mismatch this pairing prevents.
    """
    if in_fence:
        return line
    return "".join(
        segment if is_code else ALLOW.sub("", segment)
        for segment, is_code in _outside_code_spans(line)
    )


def audit_line(
    line: str,
    file_allowed: frozenset[str] = frozenset(),
    in_fence: bool = False,
) -> list[tuple[str, str]]:
    """Return (category, message) findings for one line, honouring allow markers.

    **A marker inside a code span or a fenced block is documentation of the syntax, not a use of it.**
    The two are one rule in two shapes - this is code, not prose - and only the code-span half was
    implemented here. A sibling repository found the identical split in its own detector, where a
    heading telling authors to add a marker went unreported because the example silenced the very line
    describing it.

    Without this,
    the line in `AGENTS.md` that tells an author to write `<!-- allow:naming -->` was itself an
    exempt line - and appending a code-span marker to any sentence silenced the detector on it,
    which is the same smuggling path as the prose form. Findings are still matched against the
    original line, so a forbidden term inside a code span is still reported.
    """
    allowed = marker_categories(line, in_fence) | set(file_allowed)
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
        for match in RESOURCE_ID.finditer(line):
            if match.group() not in PLACEHOLDER_RESOURCE_IDS:
                findings.append(
                    (
                        "pii",
                        (
                            f"real resource identifier {match.group()!r}; "
                            "use fs-0123456789abcdef0 / FsxIdEXAMPLE"
                        ),
                    )
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
    if "role-label" not in allowed and (
        ROLE_LABEL.match(line) or ROLE_LABEL_WITH_ROLE.match(line)
    ):
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
        in_fence = False
        for lineno, line in enumerate(lines, start=1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            for category, message in audit_line(line, file_allowed, in_fence):
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
