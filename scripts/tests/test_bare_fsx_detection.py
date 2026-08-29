"""The bare-`FSx` naming rule must fire on prose and stay quiet on identifiers.

Why this exists
---------------
This rule spent its whole life exempting the cases it most needed to catch. The
"is this an identifier rather than prose?" test was applied to the *whole line*,
so one URL or one backticked token anywhere on a line exempted every bare `FSx`
beside it. These notes cite sources constantly, so that covered most prose — and
`make audit` reported a clean tree throughout. Two violations were found by hand
during authoring, one of which had been in `docs/ja/reference/limits/` for as
long as the rule existed.

A rule that only ever passes is indistinguishable from no rule. So this asserts
both directions: prose next to a link or a code span is flagged, and genuine
identifiers are not. The negative cases matter as much as the positive ones —
an over-eager version of this rule would flag `AWS::FSx::Volume` and get
switched off, which is the same outcome by a different route.

`Amazon FSx` is the official service-family name, not the forbidden
abbreviation, so it belongs with the identifiers.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from audit_public_output import audit_line

# (line, expected to be flagged, why it is here)
CASES: list[tuple[str, bool, str]] = [
    # Prose. Each of these was exempted by the line-wide identifier test.
    (
        "FSx はこの「完全には管理されていない」側です（https://example.com/enc.html）。",
        True,
        "bare FSx on a line that also carries a URL",
    ),
    (
        "この API は FSx 共通で、`fsx:CopyBackup` を使います。",
        True,
        "bare FSx on a line that also carries a code span",
    ),
    (
        "FSx の API 単体では届きません。",
        True,
        "bare FSx with nothing to mask it",
    ),
    (
        "The FSx API is fewer moving parts.",
        True,
        "bare FSx in English prose",
    ),
    # Accepted forms and identifiers.
    (
        "Amazon FSx を含む Resource Group 3 について、",
        False,
        "official service-family name",
    ),
    (
        "Amazon FSx for NetApp ONTAP のバックアップ",
        False,
        "full product name",
    ),
    ("FSx for ONTAP のバックアップをコピーします。", False, "the required short form"),
    ("FSx for Windows File Server も対象です。", False, "sibling AWS service"),
    ("FSx for Lustre では以前から対応しています。", False, "sibling AWS service"),
    ("    Type: AWS::FSx::Volume", False, "CloudFormation type identifier"),
    ("aws fsx describe-backups --backup-ids b-0", False, "CLI invocation"),
    ("FSxOntapVolume = build()", False, "code identifier"),
    ("FSX_ENDPOINT=https://example.com", False, "environment variable"),
    ("see docs/_assets/diagrams/FSx-for-ONTAP-copy.drawio", False, "path slug"),
]


class BareFsxDetection(unittest.TestCase):
    def test_each_case(self) -> None:
        for line, expected, why in CASES:
            with self.subTest(why=why):
                flagged = any(
                    category == "naming" and "bare 'FSx'" in message
                    for category, message in audit_line(line)
                )
                self.assertEqual(
                    flagged,
                    expected,
                    f"{'expected a finding' if expected else 'expected no finding'}"
                    f" for {why}: {line!r}",
                )

    def test_an_allow_marker_still_silences_it(self) -> None:
        """Verbatim citation titles need the documented escape hatch to keep working."""
        line = "| [Why is TPS supported on fabricpool volumes in FSx](https://example.com) <!-- allow:naming --> |"
        self.assertEqual(
            [f for f in audit_line(line) if f[0] == "naming"],
            [],
            "an explicit allow:naming marker must suppress the naming finding",
        )

    def test_the_rule_covers_both_directions(self) -> None:
        """A case list with no negatives would pass an always-flagging rule."""
        self.assertTrue(any(expected for _, expected, _ in CASES))
        self.assertTrue(any(not expected for _, expected, _ in CASES))


if __name__ == "__main__":
    unittest.main()
