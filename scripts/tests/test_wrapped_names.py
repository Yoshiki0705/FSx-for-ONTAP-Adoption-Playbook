"""A required name wrapped across a line break is not a violation, and a violation stays one.

Why this exists
---------------
The audit read one line at a time. `FSx for` at the end of a line and `ONTAP` at the start of the
next is the required name, but a rule that sees only the first line sees a bare `FSx`: its lookahead
cannot reach `for ONTAP`. `Amazon` at the end of a line and `FSx` at the start of the next lost the
`Amazon` lookbehind the same way. Correct text was reported as a violation, three lines of it in a
sibling repository's tree; found during that repository's naming-gate work.

The fix is the easy half. The other half is what a reader that joins lines can get wrong: join too
eagerly and a real violation disappears into the next line. `Amazon.` ends a sentence, a blank line
ends a paragraph, a list item and a table row start something new, and a code fence is not the next
words of anything. A rule that stopped reporting wrapped names by reading past all of those would
make the gate quieter in exactly the places it should not be.

So the assertions run both ways, and the main one is an invariant rather than a list. **Wrapping a
sentence at a different place must not change whether it is reported.** A list of wrapped cases only
shows the cases someone thought of; wrapping each base sentence at every space, and at all of them
at once, covers the places nobody did. Each base is wrapped behind four prefixes because the
continuation line is not always bare text: a shell or YAML comment starts with `#`, a block quote
with `>`, and a list item's second line is indented.

These go through the command line, not `audit_line`, because the behaviour under test is the pairing
of `iter_lines` with `audit_line` that `main` performs. A rule that works on the arguments a test
hands it and is never handed them is the failure this file exists to rule out.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "tools" / "audit_public_output.py"

sys.path.insert(0, str(ROOT / "tools"))

import audit_public_output as audit

# What stands in front of every line of a wrapped sentence, and the file it lives in. A comment
# prefix is only a comment in a shell script or YAML file, so that one is written to a `.sh`.
PREFIXES: dict[str, tuple[str, str]] = {
    "bare text": ("", ".md"),
    "indented": ("  ", ".md"),
    "shell comment": ("# ", ".sh"),
    "block quote": ("> ", ".md"),
}

FINDING = re.compile(
    r"^\s+(?P<file>\S+?):(?P<line>\d+): \[naming\] (?P<message>.*)$", re.MULTILINE
)


def render(lines: list[str], kind: str) -> str:
    """The lines behind one prefix. A blank line stays blank, as it does in a real document."""
    prefix, _ = PREFIXES[kind]
    return "\n".join(prefix + line if line else line for line in lines)


def naming_findings(files: dict[str, str]) -> dict[str, list[tuple[int, str]]]:
    """Run the real audit once over a scratch tree and return its naming findings per file.

    One run for the whole batch: the invariant below writes a few hundred files, and starting the
    audit for each would make the test too slow to keep.
    """
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in files.items():
            (Path(tmp) / name).write_text(text + "\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(AUDIT), "--path", tmp, "--only", "naming", "--report"],
            capture_output=True,
            text=True,
            check=False,
        )
    found: dict[str, list[tuple[int, str]]] = {name: [] for name in files}
    for match in FINDING.finditer(result.stdout):
        found[match["file"]].append((int(match["line"]), match["message"]))
    return found


def flagged_lines(cases: dict[str, tuple[str, list[str]]]) -> dict[str, list[int]]:
    """For each (kind, lines) case, the line numbers the audit reported."""
    files = {
        f"case-{index:03d}{PREFIXES[kind][1]}": render(lines, kind)
        for index, (kind, lines) in enumerate(cases.values())
    }
    found = naming_findings(files)
    return {
        label: sorted({line for line, _ in found[name]})
        for label, name in zip(cases, files, strict=True)
    }


# The required name, split at each place a writer splits it. Every one of these is correct text.
WRAPPED_CORRECT: list[tuple[str, list[str]]] = [
    (
        "for ONTAP split after for",
        ["The volume lives on FSx for", "ONTAP in the same VPC."],
    ),
    (
        "for ONTAP split after FSx",
        ["The volume lives on FSx", "for ONTAP in the same VPC."],
    ),
    (
        "for NetApp ONTAP split after NetApp",
        ["The volume lives on FSx for NetApp", "ONTAP in the same VPC."],
    ),
    (
        "for NetApp ONTAP split after for",
        ["The volume lives on FSx for", "NetApp ONTAP in the same VPC."],
    ),
    (
        "for NetApp ONTAP split at every space",
        ["The volume lives on FSx", "for", "NetApp", "ONTAP in the same VPC."],
    ),
    (
        "the family name split after Amazon",
        ["The volume lives on Amazon", "FSx in the same VPC."],
    ),
    (
        "sibling service split after for",
        ["Both FSx for", "Windows File Server and FSx for", "Lustre are siblings."],
    ),
    ("sibling service split after FSx", ["It differs from FSx", "for OpenZFS here."]),
]

# Wrapped, and still wrong. The number is the line the report must point at.
WRAPPED_VIOLATIONS: list[tuple[str, list[str], int]] = [
    ("a bare name ending a line", ["The service uses FSx", "API calls for this."], 1),
    ("a bare name starting a line", ["The service uses", "FSx API calls for this."], 2),
    ("a missing for", ["The service uses FSx", "ONTAP volumes for this."], 1),
    (
        "for followed by something else",
        ["The service uses FSx for", "this purpose."],
        1,
    ),
    ("NetApp without ONTAP", ["A volume on FSx for NetApp", "volumes."], 1),
]

# Places a sentence does not continue, so the name on the far side is not the near side's. Each
# list is the text, and the number is the line that must still be reported.
ENDS_OF_A_SENTENCE: dict[str, tuple[list[str], int]] = {
    "blank line after for": (
        ["The volume lives on FSx for", "", "ONTAP in the same VPC."],
        1,
    ),
    "blank line after Amazon": (
        ["The volume lives on Amazon", "", "FSx API calls here."],
        3,
    ),
    "full stop after Amazon": (
        ["The volume lives on Amazon.", "FSx API calls here."],
        2,
    ),
    "bulleted list item": (
        ["- The volume lives on FSx", "- for ONTAP in the same VPC."],
        1,
    ),
    "bulleted list item after Amazon": (["- Amazon", "- FSx API calls here."], 2),
    "numbered list item": (
        ["1. The volume lives on FSx", "2. for ONTAP in the same VPC."],
        1,
    ),
    "table row": (["| FSx |", "| for ONTAP |"], 1),
    "code fence": (["The volume lives on FSx for", "```", "ONTAP", "```"], 1),
    "code fence after Amazon": (
        ["```", "Amazon", "```", "FSx API calls here."],
        4,
    ),
}

# `FSx` as part of a token rather than prose. The audit exempts these by looking a few characters
# either side of the match, in the line and not in the text joined around it.
IDENTIFIER_LINES: list[tuple[str, str]] = [
    ("resource type", "Type: AWS::FSx::FileSystem"),
    ("key", "FSx: enabled"),
    ("assignment", "FSx = 1"),
]

# Base sentences for the invariant. Each is reported at most once however it is wrapped, so the
# count is comparable across wraps. A base with a two-word forbidden form would not be: wrapped at
# that space it loses the literal rule's finding and keeps the bare one, which is still reported but
# no longer twice.
INVARIANT_BASES: list[tuple[str, int]] = [
    ("Use Amazon FSx API calls here.", 0),
    ("Use FSx API calls here.", 1),
    ("The FSx for ONTAP volume is mounted.", 0),
    ("The FSx for NetApp ONTAP file system.", 0),
    ("FSx for Windows File Server is a sibling service.", 0),
    ("Run FSx for OpenZFS beside it.", 0),
    ("Amazon FSx for NetApp ONTAP is the product.", 0),
    ("Pass the FSx S3 Access Point alias.", 1),
]


class WrappedNames(unittest.TestCase):
    def test_amazon_at_the_end_of_a_line_still_qualifies_the_next_line(self) -> None:
        cases = {
            kind: (kind, ["The volume lives on Amazon", "FSx in the same VPC."])
            for kind in PREFIXES
        }
        for kind, lines in flagged_lines(cases).items():
            self.assertEqual(lines, [], f"{kind}: the family name was reported")

    def test_for_ontap_split_across_lines_is_one_name(self) -> None:
        cases = {
            f"{label} / {kind}": (kind, lines)
            for label, lines in WRAPPED_CORRECT
            if "Amazon" not in lines[0]
            for kind in PREFIXES
        }
        wrong = {k: v for k, v in flagged_lines(cases).items() if v}
        self.assertEqual(
            wrong, {}, "a correct name was reported because it was wrapped"
        )

    def test_comment_and_quote_markers_do_not_end_the_sentence(self) -> None:
        cases = {
            f"{label} / {kind}": (kind, lines)
            for label, lines in WRAPPED_CORRECT
            for kind in ("shell comment", "block quote")
        }
        wrong = {k: v for k, v in flagged_lines(cases).items() if v}
        self.assertEqual(wrong, {}, "a marker at the start of the next line ended it")

    def test_indentation_does_not_end_the_sentence(self) -> None:
        cases = {
            f"{label} / {kind}": (kind, lines)
            for label, lines in WRAPPED_CORRECT
            for kind in ("bare text", "indented")
        }
        wrong = {k: v for k, v in flagged_lines(cases).items() if v}
        self.assertEqual(wrong, {}, "leading spaces on the next line ended it")

    def test_a_violation_wrapped_across_lines_is_still_reported(self) -> None:
        for kind in PREFIXES:
            cases = {label: (kind, lines) for label, lines, _ in WRAPPED_VIOLATIONS}
            found = flagged_lines(cases)
            for label, _, line in WRAPPED_VIOLATIONS:
                with self.subTest(case=label, prefix=kind):
                    self.assertEqual(found[label], [line])

    def _assert_ends(self, *labels: str) -> None:
        cases = {label: ("bare text", ENDS_OF_A_SENTENCE[label][0]) for label in labels}
        found = flagged_lines(cases)
        for label in labels:
            with self.subTest(case=label):
                self.assertEqual(
                    found[label],
                    [ENDS_OF_A_SENTENCE[label][1]],
                    "the sentence continued past a boundary that ends it",
                )

    def test_a_blank_line_ends_the_sentence(self) -> None:
        self._assert_ends("blank line after for", "blank line after Amazon")

    def test_a_full_stop_ends_the_sentence(self) -> None:
        self._assert_ends("full stop after Amazon")

    def test_a_list_item_or_table_row_ends_the_sentence(self) -> None:
        self._assert_ends(
            "bulleted list item",
            "bulleted list item after Amazon",
            "numbered list item",
            "table row",
        )

    def test_a_code_fence_ends_the_sentence(self) -> None:
        self._assert_ends("code fence", "code fence after Amazon")

    def test_count_does_not_depend_on_where_a_sentence_is_wrapped(self) -> None:
        """The invariant: every way of wrapping a sentence reports it as often as the unwrapped one."""
        cases: dict[str, tuple[str, list[str]]] = {}
        expected: dict[str, int] = {}
        for base, count in INVARIANT_BASES:
            words = base.split(" ")
            wraps = [[base]]
            wraps += [
                [" ".join(words[:k]), " ".join(words[k:])] for k in range(1, len(words))
            ]
            wraps.append(words)
            for kind in PREFIXES:
                for index, lines in enumerate(wraps):
                    label = f"{base!r} / {kind} / {len(lines)} lines / #{index}"
                    cases[label] = (kind, lines)
                    expected[label] = count
        found = flagged_lines(cases)
        wrong = {
            label: (expected[label], len(lines))
            for label, lines in found.items()
            if len(lines) != expected[label]
        }
        self.assertEqual(
            wrong,
            {},
            "wrapping changed how often a sentence is reported "
            "(label: (expected, reported lines)):\n  "
            + "\n  ".join(f"{k}: {v}" for k, v in sorted(wrong.items())[:10]),
        )

    def test_the_invariant_covers_both_outcomes(self) -> None:
        """A base list with no violation would pass a rule that reports nothing at all."""
        self.assertTrue(any(count for _, count in INVARIANT_BASES))
        self.assertTrue(any(not count for _, count in INVARIANT_BASES))

    def test_a_neighbours_violation_is_reported_on_its_own_line_only(self) -> None:
        """Reading the next line must not move that line's finding onto this one."""
        cases = {
            "clean line then a bare name": (
                "bare text",
                ["The volume lives on Amazon FSx today.", "The service uses FSx API."],
            ),
            "bare name then a clean line": (
                "bare text",
                ["The service uses FSx API.", "The volume lives on Amazon FSx today."],
            ),
        }
        found = flagged_lines(cases)
        self.assertEqual(found["clean line then a bare name"], [2])
        self.assertEqual(found["bare name then a clean line"], [1])

    def test_a_link_at_the_end_of_the_previous_line_is_not_the_word_amazon(
        self,
    ) -> None:
        """A URL that happens to end in `Amazon` is not the start of `Amazon FSx`."""
        cases = {
            "url ends in Amazon": (
                "bare text",
                ["See https://example.com/docs/Amazon", "FSx API calls here."],
            )
        }
        self.assertEqual(flagged_lines(cases)["url ends in Amazon"], [2])

    def test_an_identifier_is_exempt_whatever_the_neighbours_are(self) -> None:
        """The exemption reads the line, so its offset must survive the lines joined around it.

        A long line above moves the match well to the right in the joined text. An offset that
        forgot that would look for the identifier in the wrong place and report a resource type.
        """
        above = (
            "A previous line that is long enough to move the match a long way along."
        )
        below = "A following line."
        cases = {
            f"{label} / {kind}": (kind, [above, line, below])
            for label, line in IDENTIFIER_LINES
            for kind in PREFIXES
        }
        wrong = {k: v for k, v in flagged_lines(cases).items() if v}
        self.assertEqual(wrong, {}, "an identifier was reported as a bare name")

    def test_the_default_audit_accepts_a_wrapped_name(self) -> None:
        """Exit status, every category on: the report-mode runs above would not show a gate failing."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "probe.md").write_text(
                "The volume lives on FSx for\nONTAP in the same VPC.\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(AUDIT), "--path", tmp],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class NeighbouringLines(unittest.TestCase):
    """`iter_lines` decides what each line may read, so its contract is tested directly.

    The end-to-end cases above cannot see the code fence rule: a fence delimiter is itself text
    that no name pattern matches across, so a version that let a sentence run through one would
    still report the same lines. The delimiter has to be absent from the neighbourhood, and only
    the generator can be asked about that.
    """

    def test_neighbours_are_the_adjacent_lines_of_the_same_run(self) -> None:
        rows = list(audit.iter_lines(["a", "b", "c", "d", "e", "f"]))
        self.assertEqual(
            [(n, before, after) for n, _, _, before, after in rows],
            [
                (1, "", ("b", "c", "d")),
                (2, "a", ("c", "d", "e")),
                (3, "b", ("d", "e", "f")),
                (4, "c", ("e", "f")),
                (5, "d", ("f",)),
                (6, "e", ()),
            ],
        )

    def test_a_fence_delimiter_is_not_read_and_is_not_a_neighbour(self) -> None:
        rows = list(audit.iter_lines(["before", "```", "inside", "```", "after"]))
        self.assertEqual(
            rows,
            [
                (1, "before", False, "", ()),
                (3, "inside", True, "", ()),
                (5, "after", False, "", ()),
            ],
        )

    def test_a_fence_closes_only_on_a_line_of_its_own_kind(self) -> None:
        lines = ["````", "```", "~~~", "x", "````", "after"]
        rows = list(audit.iter_lines(lines))
        self.assertEqual(
            [(n, in_fence) for n, _, in_fence, _, _ in rows],
            [(4, True), (6, False)],
            "fence-shaped lines inside a fence are not read and do not close it",
        )

    def test_a_longer_closing_fence_still_closes(self) -> None:
        rows = list(audit.iter_lines(["```", "x", "`````", "after"]))
        self.assertEqual(
            [(n, in_fence) for n, _, in_fence, _, _ in rows], [(2, True), (4, False)]
        )


if __name__ == "__main__":
    unittest.main()
