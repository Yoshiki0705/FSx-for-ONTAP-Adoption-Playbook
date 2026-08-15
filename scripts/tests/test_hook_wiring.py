"""Kiro hooks must actually fire, and must be able to block when that is the intent.

Why this exists
---------------
A hook can be present, well-formatted, and completely inert. Every failure below
has been observed in practice, and none of them produce an error:

  * A matcher over-escaped in JSON. `"\\\\.(py)$"` is the regex `\\.(py)$`, which
    matches a literal backslash and therefore never matches `handler.py`.
  * A command referring to `$KIRO_FILE_PATH`, which is not in the documented
    interface. It expands to empty, the command runs against nothing, exit 0.
  * A command ending in `2>/dev/null || true`, which cannot report anything by
    construction — the hook is decoration.
  * `action.type: "agent"` on a hook whose purpose is to stop something. Only
    `command` plus exit 2 blocks; an agent action appends a prompt and proceeds.
  * A command pointing at a script that is not there. The hook exits non-zero,
    which for anything other than 2 is a warning, so execution continues.

`.kiro/` is gitignored (BLEA convention), so these files do not exist in CI.
The suite skips loudly rather than passing quietly, because a skip that reads
like a pass is the same defect one level up.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = ROOT / ".kiro" / "hooks"

VALID_TRIGGERS = {
    "PreToolUse",
    "PostToolUse",
    "SessionStart",
    "Stop",
    "UserPromptSubmit",
    "PreTaskExec",
    "PostTaskExec",
    "PostFileCreate",
    "PostFileSave",
    "PostFileDelete",
}
BLOCKING_TRIGGERS = {"PreToolUse", "UserPromptSubmit", "PreTaskExec"}
FILE_TRIGGERS = {"PostFileCreate", "PostFileSave", "PostFileDelete"}

# Environment variables that do not exist in the documented hook interface.
# Substituting one yields an empty string, so the command silently no-ops.
UNDOCUMENTED_ENV = re.compile(
    r"\$\{?KIRO_(?:FILE_PATH|FILENAME|WORKSPACE_ROOT|PROJECT)\b"
)

# Swallowing output and forcing success leaves the hook unable to report at all.
MUTED = re.compile(r"\|\|\s*true\s*$|2>\s*/dev/null[^|]*\|\|\s*true")

# Words that mark a hook whose purpose is to stop something from happening.
BLOCK_INTENT = re.compile(r"\bblock|\bprevent|\bdeny|\bforbid|\brefuse", re.IGNORECASE)

SCRIPT_REF = re.compile(r"[\w./$(){}-]*?([\w-]+\.py)")


def load_hooks() -> list[tuple[Path, dict]]:
    found: list[tuple[Path, dict]] = []
    for path in sorted(HOOKS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data.get("hooks", []):
            found.append((path, entry))
    return found


if not HOOKS_DIR.is_dir():
    # `unittest -q` reports only a skip count, so the reason would never reach a CI
    # log. An unexplained "skipped=6" is the same defect one level up: it reads as a
    # pass. Say it plainly on stderr instead.
    print(
        "note: .kiro/hooks is absent, so hook wiring was NOT verified here. Expected in "
        "CI (.kiro/ is gitignored); run `make test` on a working copy that has it.",
        file=sys.stderr,
    )


@unittest.skipUnless(
    HOOKS_DIR.is_dir(),
    ".kiro/hooks is absent (gitignored, so not present in CI). "
    "Run this locally: make test",
)
class HookWiring(unittest.TestCase):
    def setUp(self) -> None:
        self.hooks = load_hooks()
        self.assertTrue(self.hooks, "no hooks found; nothing was verified")

    def test_trigger_names_are_valid(self) -> None:
        for path, hook in self.hooks:
            with self.subTest(hook=path.name):
                self.assertIn(
                    hook.get("trigger"),
                    VALID_TRIGGERS,
                    "an unrecognized trigger never fires and reports nothing",
                )

    def test_matchers_compile_and_are_not_over_escaped(self) -> None:
        for path, hook in self.hooks:
            matcher = hook.get("matcher")
            if not matcher:
                continue
            with self.subTest(hook=path.name):
                compiled = re.compile(matcher)
                self.assertNotIn(
                    "\\\\.",
                    matcher,
                    "a doubled backslash before a dot matches a literal backslash, "
                    "not an extension; JSON needs \\\\.py$ to mean the regex \\.py$",
                )
                if hook["trigger"] in FILE_TRIGGERS:
                    self.assertTrue(
                        any(
                            compiled.search(str(p.relative_to(ROOT)))
                            for p in ROOT.rglob("*")
                            if p.is_file()
                        ),
                        f"matcher {matcher!r} matches no file in this repository, "
                        "so the hook can never fire",
                    )
                if hook["trigger"] in {"PreToolUse", "PostToolUse"}:
                    self.assertTrue(
                        compiled.search("execute_bash"),
                        f"matcher {matcher!r} does not match any tool name used here",
                    )

    def test_blocking_intent_uses_a_command_action(self) -> None:
        for path, hook in self.hooks:
            text = f"{hook.get('name', '')} {hook.get('description', '')}"
            if not BLOCK_INTENT.search(text):
                continue
            with self.subTest(hook=path.name):
                self.assertEqual(
                    hook.get("action", {}).get("type"),
                    "command",
                    "only a command action can block (exit 2); an agent action "
                    "appends a prompt and lets the tool run",
                )
                self.assertIn(
                    hook.get("trigger"),
                    BLOCKING_TRIGGERS,
                    "blocking is only possible on PreToolUse, UserPromptSubmit, "
                    "or PreTaskExec",
                )

    def test_commands_are_not_muted_and_use_no_undocumented_variables(self) -> None:
        for path, hook in self.hooks:
            command = hook.get("action", {}).get("command")
            if not command:
                continue
            with self.subTest(hook=path.name):
                self.assertIsNone(
                    UNDOCUMENTED_ENV.search(command),
                    "this variable is not part of the documented hook interface; "
                    "it expands to empty and the command silently does nothing. "
                    "Use the stdin JSON event or {{filePath}}.",
                )
                self.assertIsNone(
                    MUTED.search(command.strip()),
                    "a command that discards output and forces success cannot "
                    "report or block anything",
                )

    def test_referenced_scripts_exist(self) -> None:
        for path, hook in self.hooks:
            command = hook.get("action", {}).get("command") or ""
            for name in SCRIPT_REF.findall(command):
                with self.subTest(hook=path.name, script=name):
                    candidates = list(ROOT.rglob(name)) + list(
                        (Path.home() / ".kiro").rglob(name)
                    )
                    self.assertTrue(
                        candidates,
                        f"{name} is referenced but not found; the hook would exit "
                        "non-zero, which (other than 2) is only a warning",
                    )

    def test_worm_guard_is_wired_to_the_tracked_implementation(self) -> None:
        """The enforced pattern set must be the one under review.

        `.kiro/` is not published, so a guard living only there is invisible to
        collaborators and to CI. Pointing the hook at the tracked script is what
        makes the claim in AGENTS.md true.
        """
        tracked = "scripts/guard_irreversible_ops.py"
        wired = [
            hook
            for _path, hook in self.hooks
            if tracked in (hook.get("action", {}).get("command") or "")
        ]
        self.assertTrue(
            wired,
            "no hook runs the tracked guard. A copy under .kiro/ or $HOME can "
            "drift from the reviewed one without any test noticing.",
        )


if __name__ == "__main__":
    unittest.main()
