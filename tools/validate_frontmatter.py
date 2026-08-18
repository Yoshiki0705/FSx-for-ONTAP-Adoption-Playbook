#!/usr/bin/env python3
"""Validate YAML frontmatter on every knowledge note.

The evidence tier is the central discipline of this repository, so the rules that tie a tier
to its supporting metadata are enforced here rather than left to review:

    evidence: verified   -> requires verified_on (a real ISO date, not in the future) and region
    evidence: documented -> requires source
    field-observation    -> must be labeled as unreproduced in the body
    hypothesis           -> must be labeled as untested in the body

Keys are also checked against a known set. A misspelled key is worse than a missing one: the
value is present in the file, so a human reviewer reads the note as carrying it, while every
gate silently ignores it. `regoin: ap-northeast-1` used to pass.

Run:  python3 tools/validate_frontmatter.py [--stats]
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections import Counter
from pathlib import Path

from frontmatter import FrontmatterError, iter_markdown, read

ROOT = Path(__file__).resolve().parent.parent

LIFECYCLE = {"assess", "design", "migrate", "build", "operate", "optimize"}
DOMAINS = {
    "data-protection",
    "data-utilization",
    "security-governance",
    "performance",
    "cost",
    "multiprotocol-identity",
}
EVIDENCE = {"verified", "documented", "field-observation", "hypothesis"}
LANGS = {"ja", "en", "ko", "zh-CN", "zh-TW", "fr", "de", "es"}

REQUIRED = ("title", "lifecycle", "domains", "evidence", "lang")

# Every key the schema recognizes. Anything else is a typo or an undocumented extension, and both
# read as data to a human while being invisible to every gate — so both are errors rather than
# warnings. `industry` and `scale_band` belong to case studies (docs/ja/case-studies/_template/).
KNOWN_KEYS = frozenset(
    {
        "title",
        "lifecycle",
        "domains",
        "evidence",
        "lang",
        "verified_on",
        "source",
        "ontap_version",
        "region",
        "industry",
        "scale_band",
    }
)

# Body must make the limitation explicit for the two low-confidence tiers.
UNREPRODUCED_MARKERS = (
    "再現",
    "not reproduced",
    "unreproduced",
    "observed once",
    "一度のみ",
)
UNTESTED_MARKERS = ("未検証", "untested", "not verified", "hypothesis", "仮説")


def collect(root: Path) -> list[Path]:
    """Files subject to frontmatter validation.

    Two rules, because "where notes live" and "what carries frontmatter" are not the same set:

      * Everything under a `notes/` directory MUST have frontmatter - it is a knowledge note by
        location, so a missing block is an error rather than an opt-out.
      * Anything else that already opens with a frontmatter block is validated too. Decision trees
        and comparison matrices under `reference/` carry the same metadata and would otherwise be
        silently exempt from the evidence-tier rules they are most likely to need.
    """
    selected: list[Path] = []
    for path in iter_markdown(root):
        # Underscore-prefixed *directories* are scaffolding (`_template/`, `_assets/`): they hold
        # TODO placeholders on purpose, so validating them would make the gate fail by design.
        #
        # The filename is deliberately excluded from this rule. Skipping on the filename too meant
        # a note called `_draft.md` sitting in a real `notes/` directory was never validated at
        # all — no evidence tier checked, no error printed. Scaffolding is a property of where a
        # file lives, not of what it is called.
        relative = path.relative_to(root)
        if any(part.startswith("_") for part in relative.parts[:-1]):
            continue
        in_notes_dir = "notes" in path.parts
        if in_notes_dir:
            selected.append(path)
            continue
        try:
            head = path.read_text(encoding="utf-8").lstrip().startswith("---")
        except (OSError, UnicodeDecodeError):
            continue
        if head:
            selected.append(path)
    return selected


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        return [value]
    return []


def validate(path: Path) -> tuple[list[str], str | None]:
    """Return (errors, evidence_tier) for one note."""
    rel = path.relative_to(ROOT)
    try:
        meta, body = read(path)
    except FrontmatterError as exc:
        return [f"{rel}: {exc}"], None
    except UnicodeDecodeError:
        return [f"{rel}: file is not valid UTF-8"], None

    if meta is None:
        return [f"{rel}: missing YAML frontmatter block"], None

    errors: list[str] = []
    for key in REQUIRED:
        if key not in meta or not meta[key]:
            errors.append(f"{rel}: missing required key '{key}'")

    for key in sorted(set(meta) - KNOWN_KEYS):
        errors.append(
            f"{rel}: unknown frontmatter key {key!r} "
            f"(allowed: {', '.join(sorted(KNOWN_KEYS))})"
        )

    title = meta.get("title")
    if isinstance(title, str) and title.strip().startswith("TODO"):
        errors.append(f"{rel}: title is still a TODO placeholder")

    for name, allowed in (("lifecycle", LIFECYCLE), ("domains", DOMAINS)):
        values = _as_list(meta.get(name))
        if name in meta and not values:
            errors.append(f"{rel}: '{name}' must list at least one value")
        for value in values:
            if value not in allowed:
                errors.append(
                    f"{rel}: '{name}' has unknown value {value!r} "
                    f"(allowed: {', '.join(sorted(allowed))})"
                )

    lang = meta.get("lang")
    if isinstance(lang, str) and lang and lang not in LANGS:
        errors.append(f"{rel}: unknown 'lang' value {lang!r}")

    evidence = meta.get("evidence")
    tier = evidence if isinstance(evidence, str) else None
    if tier and tier not in EVIDENCE:
        errors.append(
            f"{rel}: 'evidence' must be one of {', '.join(sorted(EVIDENCE))}, got {tier!r}"
        )
        tier = None

    lowered = body.lower()

    if tier == "verified":
        raw_date = meta.get("verified_on")
        if not raw_date:
            errors.append(
                f"{rel}: evidence 'verified' requires 'verified_on' (YYYY-MM-DD)"
            )
        elif isinstance(raw_date, str):
            try:
                parsed = dt.date.fromisoformat(raw_date)
            except ValueError:
                errors.append(
                    f"{rel}: 'verified_on' must be YYYY-MM-DD, got {raw_date!r}"
                )
            else:
                # UTC, not local time: a verified_on recorded today reads as "future" to a
                # runner behind the author's timezone, so a naive today() makes the check
                # disagree between a local run and CI.
                if parsed > dt.datetime.now(dt.UTC).date():
                    errors.append(f"{rel}: 'verified_on' {raw_date} is in the future")
        # `verified` claims the author reproduced this somewhere, and a reader cannot tell
        # whether their own environment differs without knowing where. AGENTS.md has asked for
        # this since the schema was written; nothing enforced it, and a note with measured
        # timings and no region had been sitting in the tree.
        if not meta.get("region"):
            errors.append(
                f"{rel}: evidence 'verified' requires 'region' (where it was reproduced); "
                f"downgrade the tier if the environment cannot be named"
            )
    elif tier == "documented":
        if not meta.get("source"):
            errors.append(
                f"{rel}: evidence 'documented' requires 'source' (URL or doc name)"
            )
    elif tier == "field-observation":
        if not any(marker in lowered for marker in UNREPRODUCED_MARKERS):
            errors.append(
                f"{rel}: evidence 'field-observation' must state in the body that the "
                f"observation was not reproduced"
            )
    elif tier == "hypothesis":
        if not any(marker in lowered for marker in UNTESTED_MARKERS):
            errors.append(
                f"{rel}: evidence 'hypothesis' must state in the body that it is untested"
            )

    return errors, tier


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stats", action="store_true", help="print counts by evidence tier"
    )
    args = parser.parse_args()

    notes = collect(ROOT)

    all_errors: list[str] = []
    tiers: Counter[str] = Counter()
    for path in notes:
        errors, tier = validate(path)
        all_errors.extend(errors)
        if tier:
            tiers[tier] += 1

    if args.stats:
        print(f"notes: {len(notes)}")
        for tier in sorted(EVIDENCE):
            print(f"  {tier:<18} {tiers.get(tier, 0)}")

    if all_errors:
        print(
            f"\nFrontmatter validation failed ({len(all_errors)} issue(s)):",
            file=sys.stderr,
        )
        for error in all_errors:
            print(f"  {error}", file=sys.stderr)
        return 1

    print(f"frontmatter: {len(notes)} note(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
