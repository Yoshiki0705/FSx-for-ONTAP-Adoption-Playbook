#!/usr/bin/env python3
"""Pre-publication audit for a public repository.

Six independent concerns, all of which have historically been caught late or not at all:

  1. naming      - "Amazon FSx for NetApp ONTAP" / "FSx for ONTAP" are the only accepted forms,
                   and three products must never be proposed.
  2. neutrality  - vendor-versus framing is inappropriate for an AWS Community Builder.
  3. pii         - personal names, account IDs, internal IPs, case numbers must never be committed.
  4. role-label  - inline callouts labeled with a job title imply a review that did not happen.
  5. support-referral - telling a reader to contact AWS or NetApp Support is not a finding, and
                   publishing it before a case exists puts a dead end in a knowledge base.
  6. support-attribution - a vendor's support reply is the vendor's confidential information, so it
                   cannot be the published basis for a claim, however it is worded.

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

CATEGORIES = (
    "naming",
    "neutrality",
    "pii",
    "role-label",
    "support-referral",
    "support-attribution",
)
# The HTML comment wrapper is required, not decoration. Without it, **a line that merely mentions
# `allow:naming` in prose suppresses the detector on that line** - inside backticks too, so every
# line documenting these markers was exempting itself. Verified before tightening: one line in the
# tree relied on the loose form and no new finding appears. It also made the budget count prose as
# markers, so writing about a marker could fail `make allow-budget` with nothing wrong - the loud
# half of the same defect.
ALLOW = re.compile(
    r"<!--[^>]*?allow:"
    r"(naming|neutrality|pii|role-label|support-referral|support-attribution|all)"
    r"[^>]*?-->"
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
#
# This first pattern needs no role token, so its vocabulary has to be **idiom-bound**. `lens` and
# `レンズ` qualify: outside this construction nobody labels a callout with them. `視点` did not, and
# was in the list anyway — so 「> **コストの視点からの補足**」 and 「> **運用視点の注意**」 were
# reported, both of them topic labels naming no person. That is the same mistake `観点` was already
# kept out of this list to avoid; only one of the two ordinary words had been handled. Asked about it
# by a sibling repository, whose own detector requires a role token on every path and therefore never
# had the hole. `perspective` moves for the same reason — 「> **Cost perspective**」 is a topic.
#
# `の視点` stays, but only when it **ends** the label, which is the shape of the construction:
# 「**X の視点**」. A topic label puts the word mid-label and continues past it. That keeps the one
# thing this token-free path is uniquely for — a label naming a *person*, whose name no role-token
# list can hold. Nothing else in this file covers that form: the `pii` rules match case numbers,
# ticket IDs, paths, addresses and identifiers, and **not a bare personal name**. Dropping `の視点`
# entirely would have left 「> **<a name> の視点**」 matched by no rule at all — caught only because
# the sibling asked what else covered it before agreeing to the change.
#
# The residual is stated rather than hidden: a topic label that ends in `の視点`
# (「> **コストの視点**」) is still reported. Position is a habit of word order and carries no
# information about whether a person is named, so no regex separates that from 「**<a name> の視点**」.
# The surface is narrower than "any label containing 視点", and none of the neutral topic labels this
# repository actually prescribes — `**Security note**`, `**〜に関する補足**` — ends that way.
ROLE_LABEL = re.compile(
    r"^\s*>\s*\*\*(?:[^*]*(?:lens|レンズ)[^*]*|[^*]*の視点\s*)\*\*", re.IGNORECASE
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
#
# Every ASCII token is bounded on **both** sides, because an unbounded one matches inside a longer
# and unrelated word. The list carried `SA\b`, a boundary on the right only, and that single
# character produced a false positive and a miss at the same time: 「USA 市場の観点」 was reported,
# while 「（SA観点）」 was not — `\b` needs a non-word character, and Python counts CJK as a word
# character, so the particle-adjacent form that is normal in Japanese never had a boundary to find.
# Reported by a sibling repository. Checking the rest of the list found four more members of the
# same family: `Lead` inside `Leadership`, `Admin` inside `Administration`, `Engineer` inside
# `Engineering`, and — because this pattern is case-insensitive — `SA` inside `Visa`. Each is a
# field or an unrelated noun, so each was a heading the gate would have reddened for no reason.
#
# `s?` keeps the plural: `Engineers` and `Reviewers` name people, while `Engineering` names a
# field. That is the same job-title-versus-field cut as above, applied to word endings.
#
# The boundary class holds `_` and digits, not only letters. A class of `[^A-Za-z]` would be
# *looser* than `\b` — it treats `_` as a boundary, so a configured identifier reads as prose.
# `scripts/tests/test_cjk_word_boundaries.py` pins that with `FSx_OnPre`.
#
# The Japanese tokens take no ASCII boundary class: Japanese attaches particles without a space, so
# one around 担当 or エンジニア would block exactly the adjacent form this change exists to catch.
#
# That reasoning is right about ASCII boundaries and says nothing about the *prefix* problem, which
# the same tokens have. 「## エンジニアリングの観点」 and 「## 担当範囲の観点」 were both reported —
# a field and a scope, neither a person. Reported by a sibling repository, which hit `エンジニア`
# inside `エンジニアリング` in its own copy. Checking the rest of the list found exactly one more,
# `担当` inside every kanji compound built on it, and no others: `アーキテクト` is not a prefix of
# `アーキテクチャ` (they diverge at the sixth character), and `スペシャリスト`, `責任者`, `レビュア`
# are prefixes of nothing ordinary.
#
# The guards are script-based rather than a list of compounds, because a list of compounds is a guess
# about which nouns exist. `担当` followed by a kanji is a compound noun; `担当者` is a person, so it
# is listed first and matches before the guard applies. `エンジニア` followed by more katakana is a
# longer katakana word.
#
# `レビュア` deliberately gets no katakana guard: `レビュアー` is the ordinary spelling of the same
# word, and the guard would block it. The cost of the `エンジニア` guard is stated for the same
# reason — `エンジニアチーム` names a group of people and now passes.
_ROLE_W = r"[A-Za-z0-9_]"
_ROLE_TITLE = (
    r"Specialist|Engineer|Architect|Officer|Analyst|Consultant|Manager|Lead|Admin|Reviewer|"
    r"Practitioner|SA|CISO|DPO"
)
_ROLE = (
    rf"(?<!{_ROLE_W})(?:{_ROLE_TITLE})s?(?!{_ROLE_W})|"
    r"スペシャリスト|エンジニア(?![ァ-ヶー])|アーキテクト|担当者|担当(?![一-龠])|責任者|レビュア"
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
# What is matched here is an instruction aimed at the reader: contact them, file with them, escalate
# to them. If a case really is the only remaining path, that belongs in `.private/`, not in a
# published note.
#
# Attribution -- "AWS Support confirmed X (date)" -- is a different failure and is matched by
# `support-attribution` below. It used to be explicitly permitted here, on the reasoning that
# recording where a fact came from is not the same as sending the reader away. That reasoning was
# sound about referrals and wrong about publication, and the section below says why.
SUPPORT_REFERRAL = re.compile(
    r"(?:AWS\s+Support|NetApp\s+Support|ベンダー|サポート)\s*(?:に|へ)\s*"
    r"(?:問い合わせ|上げ|連絡|相談|起票|確認を依頼)"
    r"|(?:file|filing|open|raise|escalate)\s+(?:a\s+)?(?:support\s+)?(?:case|ticket)\s+with"
    r"|contact\s+(?:AWS|NetApp)\s*Support"
    r"|ベンダーに上げ|サポートケースを(?:開|起)",
    re.IGNORECASE,
)

# ------------------------------------------------- support-attribution
#
# A vendor's support reply cannot be the published basis for a claim. AWS treats replies from AWS
# Support as its confidential information under the customer agreement and asked, in a reply on a
# case in 2026-09, that they not be published; NetApp, Databricks and Snowflake carry comparable
# terms, so the rule is vendor-neutral.
#
# **Paraphrasing is not a way around it.** What is confidential is the content, not the wording, so
# "Support confirmed X", "サポートの回答によれば X" and "X であるとの回答を得た" are the same act.
#
# This replaces an explicit permission. Several notes here were sourced to what a vendor confirmed
# during a case, with a date, on the reasoning that attribution merely records where a fact came
# from. It does -- and that is the problem: it makes the published claim rest on a source a reader
# cannot consult and the author is not free to quote.
#
# A reply may still change what you conclude. What it cannot do is appear as the reason. After a
# reply, one of three things has to happen before the claim is published: find the public page that
# says it (`documented`), observe it yourself (`verified`), or leave it `open` and say so.
#
# What stays publishable, and is deliberately not matched: the fact that a question was asked, the
# date, and that a feature or documentation request was filed. Those are the ledger's own fields.
# Also not matched: "サポート対象" and "サポートされません" -- those are about whether a product
# supports something, not about a support desk. And "NetApp Support のログインが必要" names a
# portal, not a reply. Both shapes are in the test fixtures.
#
# Two corrections found by running it across sibling repositories, one in each direction. It
# missed 'AWS サポート確認済み', because 確認 was not in the reply-noun list. And it fired on
# 'FSx S3 Access Point のサポートが実際に機能することを確認' -- the vendor name was optional in
# the subject alternative, so any 'サポートが...確認' matched. The vendor name is now required
# there, with `サポート側` as the one exception, since that phrase names the desk on its own.
# **A detector that is loose in one direction is usually tight in the other**: both defects were
# in the same two lines.
SUPPORT_ATTRIBUTION = re.compile(
    # A vendor's support desk followed by a reply noun.
    r"(?:AWS|NetApp|Databricks|Snowflake|ClickHouse|ベンダー)\s*(?:Support|サポート)\s*(?:の)?\s*"
    r"(?:回答|見解|返信|指摘|案内|確認)"
    r"|サポート回答"
    # "...との回答を得た" / "回答がありました" attached to a confirmation.
    r"|(?:回答|見解)\s*(?:を\s*(?:得|受け|もら)|が\s*あり)"
    # The desk as the subject of confirming or reproducing.
    r"|(?:(?:AWS|NetApp|Databricks|Snowflake|ベンダー)\s*(?:Support|サポート)|サポート側)"
    # `に` is excluded here on purpose: "サポートに確認中" is the act of asking and stays
    # publishable. The completed form "サポートに確認した / 済み" has its own alternative below.
    r"\s*(?:が|は|で)[^。\n]{0,24}?(?:確認|回答|再現|指摘|説明)"
    # Presenting a completed confirmation as the basis. "確認中" is the act of asking and is left
    # alone on purpose.
    r"|(?:Support|サポート)\s*(?:に|へ)\s*確認\s*(?:した|済み)"
    # English: the desk as the subject of a reporting verb.
    r"|(?:AWS|NetApp|Databricks|Snowflake|ClickHouse)\s+Support\s+"
    r"(?:confirmed|reproduced|replied|advised|stated|said|indicated|explained|clarified)"
    r"|(?:per|according\s+to)\s+(?:AWS|NetApp|Databricks|Snowflake)\s+Support",
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
    if "support-attribution" not in allowed and SUPPORT_ATTRIBUTION.search(line):
        findings.append(
            (
                "support-attribution",
                (
                    "a vendor's support reply cannot be the published basis for a claim; cite the "
                    "public page, state your own observation, or mark it open. Recording that you "
                    "asked, and when, is fine"
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
