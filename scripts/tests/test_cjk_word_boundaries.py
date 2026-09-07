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
