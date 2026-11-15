"""The watchdog runs hourly at minute 47, and the Aggregator keeps minute 17.

The design sets the watchdog to `47 * * * *`, a minute that does not coincide with the Aggregator's
17. The watchdog limit of 8 hours was derived from the Aggregator's start interval of at most 6
hours plus a `schedule` delay of 2 hours.

**The limit itself is not tested here.** This repository has no Policy_File. The limit comes from
the commit that `SUPPLY_CHAIN_POLICY_REF` points to in another repository.

The cron lines are read from the `on:` block with the same parser `make workflow-observability`
uses (`check_workflow_observability.ON_BLOCK`), so no YAML dependency is added.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_workflow_observability as W

WORKFLOWS = ROOT / ".github" / "workflows"
WATCHDOG = WORKFLOWS / "supply-chain-watchdog.yml"
AGGREGATOR = WORKFLOWS / "supply-chain-aggregator.yml"

CRON_LINE = re.compile(r"^[ \t]+-[ \t]+cron:[ \t]*(['\"])(.*?)\1", re.MULTILINE)


def crons(text: str) -> list[str]:
    """Cron expressions listed under `on:`; a `cron:` line elsewhere in the file is not counted."""
    match = W.ON_BLOCK.search(text)
    if not match:
        return []
    return [m.group(2) for m in CRON_LINE.finditer(match.group(1))]


def minute_field(cron: str) -> str:
    return cron.split()[0]


class TheCronParser(unittest.TestCase):
    """The parser has to see a cron, or the assertions below would pass on an empty list."""

    def test_reads_a_quoted_cron_under_on(self) -> None:
        text = "on:\n  schedule:\n    - cron: '47 * * * *'\n  workflow_dispatch:\n\njobs:\n"
        self.assertEqual(crons(text), ["47 * * * *"])

    def test_reads_every_cron_of_a_list(self) -> None:
        text = "on:\n  schedule:\n    - cron: '47 * * * *'\n    - cron: \"5 1 * * *\"\n\njobs:\n"
        self.assertEqual(crons(text), ["47 * * * *", "5 1 * * *"])

    def test_ignores_a_cron_outside_the_on_block(self) -> None:
        text = "on:\n  workflow_dispatch:\n\njobs:\n  x:\n    steps:\n      - cron: '1 * * * *'\n"
        self.assertEqual(crons(text), [])

    def test_ignores_a_commented_cron(self) -> None:
        text = "on:\n  schedule:\n    # - cron: '1 * * * *'\n    - cron: '47 * * * *'\n\njobs:\n"
        self.assertEqual(crons(text), ["47 * * * *"])

    def test_the_six_hourly_form_is_not_the_hourly_form(self) -> None:
        text = "on:\n  schedule:\n    - cron: '47 */6 * * *'\n\njobs:\n"
        self.assertNotEqual(crons(text), ["47 * * * *"])


class TheWatchdogRunsHourlyAtMinute47(unittest.TestCase):
    def setUp(self) -> None:
        self.watchdog = crons(WATCHDOG.read_text(encoding="utf-8"))
        self.aggregator = crons(AGGREGATOR.read_text(encoding="utf-8"))

    def test_the_watchdog_has_exactly_one_schedule_and_it_is_hourly_at_47(self) -> None:
        self.assertEqual(self.watchdog, ["47 * * * *"])

    def test_the_aggregator_keeps_its_own_schedule(self) -> None:
        """Pinned so that a change to the watchdog cannot be paid for by changing this one."""
        self.assertEqual(self.aggregator, ["17 */6 * * *"])

    def test_the_two_do_not_share_a_minute(self) -> None:
        self.assertEqual(len(self.watchdog), 1)
        self.assertEqual(len(self.aggregator), 1)
        self.assertNotEqual(
            minute_field(self.watchdog[0]),
            minute_field(self.aggregator[0]),
            "the watchdog and the Aggregator start in the same minute",
        )


if __name__ == "__main__":
    unittest.main()
