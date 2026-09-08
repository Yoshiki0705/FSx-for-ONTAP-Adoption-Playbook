"""A role label must name a person. Two ways it stopped doing so.

Why this exists
---------------
The rule is that a callout or heading labeled with a job title implies a review by someone in that
role, and if no such review happened the label is a false claim. Everything here is about the gap
between that rule and the two regexes implementing it, in the direction that *over*-reports: a
label naming a subject rather than a person.

**Ordinary words.** One of the two patterns needs no role token, so any word in its vocabulary
fires on its own. `観点` was kept out of that list for exactly this reason; `視点` was left in, and
so 「> **コストの視点からの補足**」 and 「> **運用視点の注意**」 were reported. Both are topic
labels. `perspective` was in the same position. They are now behind the role-token requirement,
where `観点` already was.

**Prefixes.** The Japanese tokens carry no boundary class, which is right — Japanese attaches
particles without a space, so an ASCII boundary would block the adjacent form the rule is for. It is
also unrelated to `エンジニア` sitting inside `エンジニアリング`, and 「## エンジニアリングの観点」
and 「## 担当範囲の観点」 were reported: a field and a scope.

Both were found by a sibling repository, the second of them by asking a question about the first.

Why the tests run the audit rather than the regexes
---------------------------------------------------
A regex-level assertion passes while the line never reaches the rule — a fence, a code span, an
allow marker, a category name that stopped matching. The category is asserted too, so a finding
raised by a *different* rule cannot stand in for the one under test.

`test_mutation_discrimination.py` registers the plausible wrong fixes and requires this file to be
the one that notices them.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "tools" / "audit_public_output.py"
CATEGORY = "[role-label]"

# Labels that name a person, or a job title, and must be reported.
MUST_FLAG = [
    ("callout, English lens", "> **AppSec lens**: x"),
    ("callout, Japanese lens", "> **SRE レンズ**: x"),
    ("callout, title + の視点", "> **Storage Specialist の視点**: x"),
    ("callout, standalone title", "> **DPO の視点**: x"),
    ("callout, lens not at the end", "> **Storage Specialist lens (measured)**: x"),
    # The one thing the token-free path is uniquely for. No role-token list can hold a personal
    # name, and no other rule in the audit matches one — the `pii` rules cover case numbers, ticket
    # IDs, paths, addresses and identifiers. Deleting `の視点` from that path would leave this form
    # matched by nothing, which is why it survives the narrowing.
    ("callout, a name + の視点", "> **Yamada の視点**: x"),
    ("heading, title + 観点", "## 前提（Storage Specialist 観点）"),
    ("heading, title + 視点", "## 前提（Storage Specialist 視点）"),
    ("heading, Japanese role", "## エンジニアの観点"),
    ("heading, 担当 as a person", "## 担当の観点"),
    ("heading, 担当者", "## 担当者の視点"),
    ("heading, レビュアー keeps its long vowel", "## レビュアーの観点"),
    ("heading, アーキテクト", "## アーキテクトの観点"),
]

# Labels naming a subject. Every one of these was reported before this change, or would be by the
# shortest fix to it.
MUST_PASS = [
    # 観点 was already behind the role-token requirement; these are the control.
    ("topic, 観点 mid-label", "> **コスト観点の補足**: x"),
    ("topic, 観点 in prose", "> **Cost note**: セキュリティの観点からも確認します。"),
    # 視点 was not, and these three were reported.
    ("topic, 視点 mid-label", "> **コストの視点からの補足**: x"),
    ("topic, 視点 with no particle", "> **運用視点の注意**: x"),
    ("topic, 視点 mid-label again", "> **移行の視点での整理**: x"),
    # perspective is ordinary English in the same way.
    ("topic, perspective", "> **Cost perspective**: x"),
    # A field is not a person; this is the line the sibling drew and this repository adopted.
    ("field, FinOps", "## 前提（FinOps 観点）"),
    ("field, Engineering", "## Engineering 観点"),
    # The prefix family.
    ("field, エンジニアリング", "## エンジニアリングの観点"),
    ("scope, 担当範囲", "## 担当範囲の観点"),
    ("scope, 担当領域", "## 担当領域の観点"),
    ("field, アーキテクチャ", "## アーキテクチャの観点"),
    # Not a callout and no role token, so neither pattern applies.
    ("bold run outside a callout", "**観点の整理**: x"),
]


def audit(text: str) -> tuple[int, str]:
    """Run the audit over a scratch file containing only `text`; return (exit code, report).

    Findings go to stderr and the clean line to stdout, so both are joined. Asserting on stdout
    alone reports every finding as absent — which is how this helper was first written, and the
    category assertion below is what caught it. A sibling test file checks only the exit code, so
    it never had to know.
    """
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "probe.md").write_text(text + "\n", encoding="utf-8")
        done = subprocess.run(
            [sys.executable, str(AUDIT), "--path", tmp],
            capture_output=True,
            text=True,
            check=False,
        )
    return done.returncode, done.stdout + done.stderr


class ALabelMustNameAPerson(unittest.TestCase):
    def test_labels_naming_a_person_are_reported(self) -> None:
        missed = []
        for label, text in MUST_FLAG:
            code, report = audit(text)
            if code == 0:
                missed.append(f"{label}: {text}")
            elif CATEGORY not in report:
                missed.append(
                    f"{label}: reported, but not as role-label: {report.strip()}"
                )
        self.assertEqual(
            missed,
            [],
            "these labels claim a review by a person and were not reported:\n  "
            + "\n  ".join(missed),
        )

    def test_labels_naming_a_subject_are_not_reported(self) -> None:
        """The half that a widened vocabulary fails.

        A rule that reddens a correct label does not get fixed, it gets an allow marker — and a
        marker is headroom, exempting the line for the real violation written there later. Measured
        before changing anything: the tree held no `allow:role-label` marker and no callout label
        containing 視点, so nothing had been worked around yet.
        """
        wrong = []
        for label, text in MUST_PASS:
            code, report = audit(text)
            if code != 0:
                wrong.append(f"{label}: {text} -> {report.strip()}")
        self.assertEqual(
            wrong,
            [],
            "these labels name a subject rather than a person and must not be reported:\n  "
            + "\n  ".join(wrong),
        )

    def test_the_accepted_residual_is_still_reported(self) -> None:
        """A topic label ending in `の視点` is reported, and that is accepted.

        Pinned rather than left as a surprise. Position is a habit of word order and carries no
        information about whether a person is named, so 「**コストの視点**」 cannot be separated from
        「**<a name> の視点**」 by a regex. Keeping the personal-name form is worth the narrower
        false positive, because no other rule in the audit matches a bare name.

        If this test is ever made to fail deliberately, the personal-name case above is what needs
        another mechanism first.
        """
        code, report = audit("> **コストの視点**: x")
        self.assertNotEqual(code, 0, "the accepted residual stopped being reported")
        self.assertIn(CATEGORY, report)


if __name__ == "__main__":
    unittest.main()
