"""The portable UI checker reacts to flagged source and stays silent on clean source.

A checker that returns 0 findings proves nothing until it has been seen to return findings on
input it must reject, so both directions are asserted. Node is required: the checker is a Node
script and this test fails, rather than skips, when `node` is absent.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

CHECKER_DIR = Path(__file__).resolve().parents[2] / "tools" / "portable" / "check-ui"
CHECKER = CHECKER_DIR / "check-ui.mjs"
FIXTURES = CHECKER_DIR / "fixtures"

# Every rule the flagged fixture is written to trigger. A rule added to the checker without a line
# here and in the fixture has no demonstrated positive case.
EXPECTED_RULES = {
    "side-stripe",
    "emoji",
    "gradient-text",
    "loud-gradient",
    "glow",
    "transition-all",
    "looping-motion",
    "heavy-weight",
    "tracked-uppercase",
    "italic",
    "off-grid-spacing",
    "small-input-font",
    "waiting-copy",
    "hype-copy",
    "exclamation",
    "hover-scale",
    "hover-menu",
}


def run(*args: str) -> tuple[int, dict]:
    node = shutil.which("node")
    assert node, "node is required to run the portable UI checker tests"
    proc = subprocess.run(
        [node, str(CHECKER), "--json", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, json.loads(proc.stdout)


class PortableCheckUiTest(unittest.TestCase):
    def test_flagged_fixture_triggers_every_rule(self) -> None:
        code, report = run(str(FIXTURES / "flagged.html"))
        self.assertEqual(code, 1)
        self.assertEqual({f["rule"] for f in report["findings"]}, EXPECTED_RULES)

    def test_clean_fixture_has_no_findings(self) -> None:
        code, report = run(str(FIXTURES / "clean.html"))
        self.assertEqual((code, report["findings"]), (0, []))

    def test_every_declared_rule_has_a_positive_case(self) -> None:
        declared = set()
        for line in CHECKER.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("id: '"):
                declared.add(line.split("'")[1])
        self.assertEqual(declared, EXPECTED_RULES)

    def test_removed_rule_stays_removed(self) -> None:
        self.assertNotIn(
            "key-hint", CHECKER.read_text(encoding="utf-8").split("RULES")[1]
        )


if __name__ == "__main__":
    unittest.main()
