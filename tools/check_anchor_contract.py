#!/usr/bin/env python3
"""Pin the section anchors that other repositories link to.

A heading in this repository is an interface once something outside it links to a section. Renaming
one does not break loudly: GitHub answers an unknown fragment with the top of the page, so the
citing side keeps rendering a link that silently lands somewhere else. Neither repository's link
checker can see it - `check_links.py` resolves anchors inside this tree, and a checker on the other
side cannot resolve an anchor in a repository it does not have.

So the anchors of externally cited documents are recorded in `docs/agent/external-anchor-contract.txt`
and compared here. Renaming a heading then fails the commit gate instead of failing silently in
someone else's docs. Adding, reordering or rewriting sections is unaffected - only the anchor text
matters, which is exactly the surface a citation depends on.

The snapshot is deliberately a second copy of data that already exists in the documents. That is the
mechanism: a rename has to be acknowledged in a diff rather than discovered by a reader.

Run:    python3 tools/check_anchor_contract.py
Update: python3 tools/check_anchor_contract.py --write   (then say so in CHANGELOG.md)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from check_links import anchors_of

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "docs" / "agent" / "external-anchor-contract.txt"

HEADER = """\
# Section anchors that other repositories cite. Generated - do not hand-edit.
#
# Regenerate with: python3 tools/check_anchor_contract.py --write
# A change here means a heading was renamed, which silently redirects an external citation to the
# top of the page. Renaming is allowed; doing it without noticing is what this file prevents.
#
# Format: one "<path>#<anchor>" per line, sorted. A path with no anchors records the path alone.
"""


def tracked_files() -> list[Path]:
    """Documents cited by section from outside this repository.

    Confirmed rather than guessed. The citing repository counted 19 anchored links into the Japanese
    file and 18 into the English one, and reported that it references the decision tree and the
    evidence policy in prose only. Both of those were listed here at first and have been removed: a
    contract claiming an anchor is externally cited when it is not makes the gate fire on renames
    that break nothing, and friction without benefit is how a gate ends up switched off.
    """
    return [
        ROOT
        / "docs"
        / lang
        / "domains"
        / "security-governance"
        / "notes"
        / "access-point-authorization-layers.md"
        for lang in ("ja", "en")
    ]


def snapshot() -> list[str]:
    lines: list[str] = []
    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        if not path.exists():
            lines.append(f"{rel}#<MISSING FILE>")
            continue
        anchors = sorted(anchors_of(path))
        lines.extend(
            f"{rel}#{anchor}" for anchor in anchors
        ) if anchors else lines.append(rel)
    return sorted(lines)


def stored() -> list[str] | None:
    if not CONTRACT.exists():
        return None
    return sorted(
        line.strip()
        for line in CONTRACT.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="record the current anchors as the contract",
    )
    args = parser.parse_args()

    current = snapshot()
    if args.write:
        CONTRACT.parent.mkdir(parents=True, exist_ok=True)
        CONTRACT.write_text(HEADER + "\n".join(current) + "\n", encoding="utf-8")
        print(
            f"anchor contract: wrote {len(current)} anchor(s) to {CONTRACT.relative_to(ROOT)}"
        )
        return 0

    previous = stored()
    if previous is None:
        print(
            f"anchor contract: {CONTRACT.relative_to(ROOT)} is missing; "
            f"run python3 tools/check_anchor_contract.py --write",
            file=sys.stderr,
        )
        return 1

    removed = [line for line in previous if line not in current]
    added = [line for line in current if line not in previous]
    if not removed and not added:
        print(f"anchors: {len(current)} externally cited anchor(s) unchanged")
        return 0

    print("anchor contract drift:", file=sys.stderr)
    for line in removed:
        print(f"  GONE  {line}", file=sys.stderr)
    for line in added:
        print(f"  NEW   {line}", file=sys.stderr)
    if removed:
        print(
            "\nA GONE anchor is the dangerous one: an external citation to it now lands on the top\n"
            "of the page instead, and neither side's link checker can see that. If the rename is\n"
            "intended, tell the citing repositories and note it in CHANGELOG.md before recording it.",
            file=sys.stderr,
        )
    else:
        print(
            "\nOnly additions. Nothing external breaks - the snapshot just needs refreshing so that\n"
            "a later rename of these new anchors is still caught.",
            file=sys.stderr,
        )
    print(
        "\nRecord with: python3 tools/check_anchor_contract.py --write",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
