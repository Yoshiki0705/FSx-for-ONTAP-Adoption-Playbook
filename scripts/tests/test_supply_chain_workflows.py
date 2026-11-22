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


KEY_ROTATION = WORKFLOWS / "supply-chain-key-rotation.yml"

USES_LINE = re.compile(
    r"^\s*-?\s*uses:[ \t]*(\S+)[ \t]*(?:#[ \t]*(.*))?$", re.MULTILINE
)
PINNED = re.compile(r"^([\w.-]+/[\w./-]+)@([0-9a-f]{40})$")
PERMISSION_INPUT = re.compile(r"^\s*(permission-[a-z-]+):[ \t]*(\S+)", re.MULTILINE)
DAILY_CRON = re.compile(r"^(\d{1,2}) (\d{1,2}) \* \* \*$")


def pinned_uses(text: str) -> list[tuple[str, str, str]]:
    """Each `uses:` as (action, sha, version comment); an unpinned one raises."""
    found = []
    for match in USES_LINE.finditer(text):
        pin = PINNED.match(match.group(1))
        if not pin:
            raise AssertionError(f"not pinned to a 40-digit commit: {match.group(1)}")
        found.append((pin.group(1), pin.group(2), (match.group(2) or "").strip()))
    return found


def run_lines(text: str) -> list[str]:
    """Every line that is shell: an inline `run:` value and each line of a `run: |` block."""
    lines = text.splitlines()
    shell: list[str] = []
    index = 0
    while index < len(lines):
        match = re.match(r"^(\s*)(?:-\s+)?run:[ \t]*(.*)$", lines[index])
        index += 1
        if not match:
            continue
        indent = len(match.group(1))
        value = match.group(2).strip()
        if value and value not in {"|", ">", "|-", ">-"}:
            shell.append(value)
            continue
        while index < len(lines):
            line = lines[index]
            if line.strip() and len(line) - len(line.lstrip()) <= indent:
                break
            shell.append(line)
            index += 1
    return shell


def job_permissions(text: str) -> dict[str, str]:
    """The `permissions:` map of the first job, read at the 4-space indent a job key has."""
    block = re.search(r"^ {4}permissions:[ \t]*\n((?: {6}\S.*\n)+)", text, re.MULTILINE)
    if not block:
        return {}
    pairs = (line.strip().split(":", 1) for line in block.group(1).splitlines())
    return {key.strip(): value.strip() for key, value in pairs}


class TheHelpersSeeWhatTheyAreAskedAbout(unittest.TestCase):
    """The assertions below would pass on empty lists, so the helpers are tried on known text."""

    def test_uses_reads_the_sha_and_the_comment(self) -> None:
        sha = "a" * 40
        text = f"      - uses: owner/action@{sha} # v1.2.3\n"
        self.assertEqual(pinned_uses(text), [("owner/action", sha, "v1.2.3")])

    def test_a_tag_reference_is_refused(self) -> None:
        with self.assertRaises(AssertionError):
            pinned_uses("      - uses: owner/action@v4\n")

    def test_run_lines_reads_a_block_and_an_inline_value(self) -> None:
        text = (
            "    steps:\n"
            "      - name: a\n"
            "        run: echo ${{ github.ref }}\n"
            "      - name: b\n"
            "        run: |\n"
            "          echo one\n"
            "          echo ${{ github.ref }}\n"
            "      - name: c\n"
            "        env:\n"
            "          X: ${{ vars.X }}\n"
        )
        shell = run_lines(text)
        self.assertEqual(sum("${{" in line for line in shell), 2)
        self.assertNotIn("X: ${{ vars.X }}", [line.strip() for line in shell])

    def test_job_permissions_reads_the_job_map_only(self) -> None:
        text = (
            "permissions: {}\n\njobs:\n  j:\n    permissions:\n"
            "      contents: read\n      issues: write\n    steps:\n"
        )
        self.assertEqual(job_permissions(text), {"contents": "read", "issues": "write"})


class TheKeyRotationWorkflow(unittest.TestCase):
    """The daily check of the App key's age, held to the same habits as the other two workflows."""

    def setUp(self) -> None:
        self.text = KEY_ROTATION.read_text(encoding="utf-8")

    def test_the_name(self) -> None:
        self.assertRegex(self.text, r"(?m)^name: supply-chain-key-rotation$")

    def test_it_runs_on_schedule_and_by_hand_and_on_nothing_else(self) -> None:
        self.assertEqual(W.triggers(self.text), {"schedule", "workflow_dispatch"})
        self.assertEqual(W.observability(self.text), "unobserved")

    def test_the_manual_run_takes_no_input(self) -> None:
        self.assertNotIn("inputs:", self.text)

    def test_the_schedule_is_once_a_day_and_off_the_other_two_minutes(self) -> None:
        found = crons(self.text)
        self.assertEqual(len(found), 1, found)
        match = DAILY_CRON.match(found[0])
        self.assertIsNotNone(match, f"not a once-a-day cron: {found[0]}")
        assert match is not None
        self.assertNotIn(int(match.group(1)), {17, 47})
        self.assertLess(int(match.group(1)), 60)
        self.assertLess(int(match.group(2)), 24)

    def test_the_workflow_takes_no_permission_and_the_job_takes_two(self) -> None:
        self.assertRegex(self.text, r"(?m)^permissions: \{\}$")
        self.assertEqual(
            job_permissions(self.text), {"contents": "read", "issues": "write"}
        )

    def test_the_run_in_progress_is_never_cut_off(self) -> None:
        self.assertRegex(self.text, r"(?m)^concurrency:\n(?:  .*\n)*?  group: \S+\n")
        self.assertRegex(self.text, r"(?m)^  cancel-in-progress: false$")

    def test_every_action_is_pinned_and_none_is_new(self) -> None:
        """Pinned to a commit, and the same commit and version an existing workflow already uses."""
        known = {
            use
            for path in (AGGREGATOR, WATCHDOG)
            for use in pinned_uses(path.read_text(encoding="utf-8"))
        }
        mine = pinned_uses(self.text)
        self.assertTrue(mine)
        for use in mine:
            with self.subTest(use=use[0]):
                self.assertTrue(use[2], "the version comment is missing")
                self.assertIn(use, known, "an action or pin no other workflow uses")

    def test_every_checkout_drops_its_credentials(self) -> None:
        steps = re.split(r"(?m)^      - ", self.text)
        checkouts = [s for s in steps if "uses: actions/checkout@" in s]
        self.assertTrue(checkouts)
        for step in checkouts:
            self.assertIn("persist-credentials: false", step)

    def test_the_app_token_asks_for_secrets_read_and_nothing_else(self) -> None:
        self.assertEqual(
            PERMISSION_INPUT.findall(self.text), [("permission-secrets", "read")]
        )

    def test_the_token_step_may_fail_so_the_script_can_say_so(self) -> None:
        step = re.search(
            r"(?m)^      - name:[^\n]*\n(?:        .*\n)*?"
            r"        id: (\S+)\n(?:        .*\n)*?"
            r"        uses: actions/create-github-app-token@[\s\S]*?(?=^      - |\Z)",
            self.text,
        )
        self.assertIsNotNone(step, "no step with an id uses create-github-app-token")
        assert step is not None
        self.assertIn("continue-on-error: true", step.group(0))
        self.assertIn(
            "client-id: ${{ vars.SUPPLY_CHAIN_APP_CLIENT_ID }}", step.group(0)
        )
        self.assertIn(
            "private-key: ${{ secrets.SUPPLY_CHAIN_APP_PRIVATE_KEY }}", step.group(0)
        )
        # The repository name alone, taken from github.repository by an earlier step: the action
        # takes names, and an empty value would widen the token to every repository of the owner.
        self.assertRegex(
            step.group(0), r"repositories: \$\{\{ steps\.\w+\.outputs\.name \}\}"
        )
        token_id = step.group(1)
        self.assertIn(f"steps.{token_id}.outputs.token", self.text)
        self.assertIn(f"steps.{token_id}.outcome", self.text)

    def test_the_script_gets_the_four_values_through_env(self) -> None:
        for name in ["GH_REPO", "ISSUE_TOKEN", "APP_TOKEN", "TOKEN_STEP_OUTCOME"]:
            with self.subTest(name=name):
                self.assertRegex(self.text, rf"(?m)^ +{name}: \$\{{\{{ ")
        self.assertIn("ISSUE_TOKEN: ${{ github.token }}", self.text)
        self.assertIn("python3 scripts/check_app_key_age.py", self.text)

    def test_no_expression_reaches_the_shell_directly(self) -> None:
        shell = run_lines(self.text)
        self.assertTrue(shell, "no shell line was found, so this proves nothing")
        for line in shell:
            self.assertNotIn("${{", line)

    def test_nothing_forces_its_own_success(self) -> None:
        """Only the token step may continue on error; the script's own exit code is the verdict."""
        self.assertEqual(self.text.count("continue-on-error"), 1)
        self.assertNotRegex(self.text, r"\|\|\s*true")


if __name__ == "__main__":
    unittest.main()
