"""Every audit rule must fire when Japanese text is directly adjacent.

Python defines `\\b` in terms of `\\w`, and `\\w` matches CJK. So `\\bFSx\\b` matches `FSx を使う`
and does **not** match `FSxを使う`: there is no boundary between `x` and `を`, because both are
word characters. Japanese attaches particles without a space, so **the form that went unreported
was the common one**, in a repository whose reference language is Japanese.

Five rules were affected — bare `FSx`, account IDs, email addresses, vendor ticket IDs and
internal IPs. Each is the audit's own subject matter, and each was silent on the side of the tree
where it mattered. Nothing errored; the audit printed "clean".

Reported by a sibling repository, which hit the identical asymmetry in a parity checker. Its
trailing `(?![\\w])` let `100 MB and up` match while `100MB以上` did not, and it then reported 13
findings where the truth was 9 — four false positives manufactured by the same rule. **The
asymmetry does not only hide findings; it also invents them**, so a clean run and a noisy run are
equally untrustworthy while it is present.

Each case below pairs the Japanese-adjacent form with the spaced ASCII form. Testing only the
Japanese form would let a fix that breaks ordinary English detection pass.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "tools" / "audit_public_output.py"

sys.path.insert(0, str(ROOT / "tools"))

# Each case: a label, the Japanese-adjacent text, and the spaced text that already worked.
#
# Both are positive. **A version with the boundaries deleted outright passes them both**, because
# removing a boundary only widens a match — so on their own they cannot tell the correct fix apart
# from the laziest one. NEGATIVE below is what separates the two. A sibling repository found this by
# mutation-testing its own equivalent: a guard-free version passed every positive case.
CASES = [
    ("bare FSx", "FSxを使う構成です。", "The FSx deployment is ready."),
    (
        "account id",
        "アカウント987654321098の設定です。",
        "Account 987654321098 is set.",
    ),
    ("email", "連絡先person@corp.jpまで。", "Mail person@corp.jp for details."),
    ("vendor ticket", "課題AB-I-12345を参照。", "See AB-I-12345 for status."),
    ("internal ip", "管理IPは10.0.0.5です。", "The address 10.0.0.5 answers."),
]


# Embedded forms that must NOT match. Every one is a substring of a legitimate identifier, which is
# why the fix cannot be "delete the boundary".
#
# `FSx_OnPre` also constrains the replacement. A guard written as `[^A-Za-z0-9]` is *looser* than
# `\b`, because it treats `_` as a boundary, and a configured resource name then reads as prose.
# `_` stays inside the character class for that reason.
NEGATIVE = [
    ("bare FSx", "XFSxN is a scratch identifier."),
    ("bare FSx", "FSxNN appears in a generated name."),
    ("bare FSx", "FSxN_OnPre is a storage virtual machine name."),
    ("bare FSx", "FSx_OnPre_root is a volume name."),
    ("bare FSx", "識別子 FSxN_OnPre を使っています。"),
    ("account id", "1234567890123 is thirteen digits, not an account ID."),
    ("account id", "v123456789012x is embedded in an identifier."),
    ("vendor ticket", "XAB-I-12345Z is not a ticket reference."),
    ("internal ip", "310.0.0.5 is not an RFC 1918 address."),
]


def audit(text: str) -> subprocess.CompletedProcess[str]:
    """Run the audit over a scratch file containing only `text`."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "probe.md").write_text(text + "\n", encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(AUDIT), "--path", tmp],
            capture_output=True,
            text=True,
            check=False,
        )


class RulesFireBesideJapanese(unittest.TestCase):
    def test_japanese_adjacent_forms_are_reported(self) -> None:
        missed = []
        for label, japanese, _ in CASES:
            if audit(japanese).returncode == 0:
                missed.append(f"{label}: {japanese}")
        self.assertEqual(
            missed,
            [],
            "these rules stayed silent with Japanese directly adjacent, which is the common "
            "form in this repository:\n  " + "\n  ".join(missed),
        )

    def test_spaced_ascii_forms_are_still_reported(self) -> None:
        """A boundary fix must not trade one silence for another."""
        missed = []
        for label, _, ascii_form in CASES:
            if audit(ascii_form).returncode == 0:
                missed.append(f"{label}: {ascii_form}")
        self.assertEqual(
            missed,
            [],
            "the boundary change lost detection of the spaced form:\n  "
            + "\n  ".join(missed),
        )

    def test_embedded_forms_are_not_reported(self) -> None:
        """The negative side, which is what a deleted boundary fails.

        Every string here is a substring of a legitimate identifier. A version with
        the boundaries removed matches inside all of them, so this is the test that
        tells a correct fix apart from "delete the boundary so the Japanese case
        passes". Verified by mutation: with the two guards emptied, this fails while
        both positive tests still pass.
        """
        wrong = []
        for label, text in NEGATIVE:
            result = audit(text)
            if result.returncode != 0:
                wrong.append(f"{label}: {text} -> {result.stdout.strip()}")
        self.assertEqual(
            wrong,
            [],
            "these are substrings of legitimate identifiers and must not be reported:\n  "
            + "\n  ".join(wrong),
        )

    def test_the_sanctioned_placeholder_is_still_accepted(self) -> None:
        """The account rule exempts one value on purpose; widening must not lose that."""
        result = audit("アカウント123456789012を使ってください。")
        self.assertEqual(
            result.returncode,
            0,
            f"the placeholder account was rejected:\n{result.stdout}{result.stderr}",
        )

    def test_example_addresses_are_still_accepted(self) -> None:
        result = audit("連絡先reviewer@example.comまで。")
        self.assertEqual(
            result.returncode,
            0,
            f"an example.com address was rejected:\n{result.stdout}{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
