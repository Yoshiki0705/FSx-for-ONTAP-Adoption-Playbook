#!/usr/bin/env python3
"""Block an agent from unilaterally enabling immutability (WORM) features.

WHY THIS EXISTS
---------------
On 2026-08-06 an AI agent working in this repository created an Amazon FSx for NetApp
ONTAP SnapLock audit log volume in order to verify a documented claim. It did not ask
which retention period to use, and it read the relevant warning only *after* the
operation failed to reverse.

One 128 MiB volume made the volume, its storage virtual machine, and **the entire file
system** undeletable for six months. The agent had also already set privileged delete to
`PERMANENTLY_DISABLED`, which closed the only remaining escape route. The verification it
was performing produced no usable finding.

The general lesson is not about SnapLock. It is this:

    A feature whose stated purpose is to remove your ability to delete data must never
    be enabled by an agent acting on its own judgement.

Such a feature working correctly is indistinguishable from an outage you caused. There is
no rollback, no support escalation that reliably helps, and the blast radius is routinely
wider than the resource you named in the call.

WHAT THIS DOES
--------------
Reads a Kiro PreToolUse hook payload on stdin, extracts the command, and exits 2 (block)
when the command both (a) touches an immutability or terminal-state feature and (b) is
mutating. Read-only inspection is always allowed, because refusing to let an agent *look*
would just push it toward guessing.

Exit codes: 0 allow, 2 block (stderr is shown to the agent).

REUSE
-----
Stdlib only, no repository-specific assumptions. Copy it into any project and wire it to
a PreToolUse hook. Extend IMMUTABILITY_PATTERNS as you meet new features; the categories
matter more than the exact list.
"""

from __future__ import annotations

import json
import re
import sys

# Features that deliberately remove the ability to delete, or that latch into a state with
# no documented return path. Grouped by service so the block message can name the risk.
IMMUTABILITY_PATTERNS: dict[str, list[str]] = {
    "FSx for ONTAP SnapLock": [
        r"snaplock",
        r"AuditLogVolume",
        r"PrivilegedDelete",
        r"SnaplockType",
        r"VolumeAppendModeEnabled",
        r"audit-logs",
    ],
    "S3 Object Lock": [
        r"object-lock",
        r"ObjectLock(?:Configuration|Retention|LegalHold)?",
        r"put-object-retention",
        r"put-object-legal-hold",
    ],
    "S3 Glacier Vault Lock": [
        r"initiate-vault-lock",
        r"complete-vault-lock",
    ],
    "AWS Backup Vault Lock": [
        r"backup-vault-lock",
        r"put-backup-vault-lock-configuration",
        r"ChangeableForDays",
    ],
    "EBS snapshot lock": [
        r"lock-snapshot",
        r"CoolOffPeriod",
    ],
    "Terminal / permanently-disabled states": [
        r"PERMANENTLY_DISABLED",
        r"permanently[-_]disabled",
    ],
}

# Verbs that change state. An immutability pattern alone is not enough to block, or the
# guard would stop an agent from reading the state it needs in order to ask a good question.
#
# The CLI verb is anchored to its command position on purpose. An unanchored `lock-` also
# matches inside `get-object-lock-configuration`, which turned a read into a block during
# testing — exactly the over-blocking that trains people to disable a guard.
MUTATING = re.compile(
    r"""(?xi)
    \baws\s+[\w-]+\s+
      (?:create|update|put|modify|delete|initiate|complete|lock|enable|associate|tag)-
  | -X\s*(?:POST|PATCH|PUT|DELETE)
  | --method\s*(?:POST|PATCH|PUT|DELETE)
  | \b(?:volume|vserver|snapmirror)\s+[\w\s-]*?\b(?:create|modify|delete)\b   # ONTAP CLI
    """
)

BLOCK_MESSAGE = """\
BLOCKED: this command enables or alters an immutability / terminal-state feature.

  Feature area : {areas}
  Matched      : {matches}

An agent must not decide this on its own. These features work by removing the ability to
delete, so a mistake cannot be undone by you, by the account owner, or reliably by AWS
Support. The affected scope is regularly wider than the resource named in the call — an
FSx for ONTAP SnapLock audit log volume, for example, locks its SVM and the whole file
system for a minimum of six months, in Enterprise mode too.

Do this instead:

  1. Stop. Do not retry, and do not look for an equivalent call that evades this check.
  2. Tell the human, in the conversation, exactly:
       - which resource the operation targets,
       - what becomes undeletable, and for how long,
       - the widest scope affected (volume? SVM? file system? account?),
       - the cost of holding that scope for the full period,
       - whether any documented path exists to reverse it early (usually: none).
  3. Ask for the retention value explicitly. Never infer it, never accept a service
     default silently, and state the minimum the service permits.
  4. Proceed only on an instruction that names the value and the scope.

If this is verification work, ask whether a disposable, dedicated file system or account
should be used first. Verification is never a reason to skip this gate — the incident that
produced this guard was verification work, and it yielded no usable finding.
"""


def extract_command(payload: dict) -> str:
    """Pull the command text out of a hook payload without assuming one exact shape."""
    for key in ("command", "cmd", "input", "arguments", "toolInput", "tool_input"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, dict):
            for inner in ("command", "cmd", "text"):
                nested = value.get(inner)
                if isinstance(nested, str) and nested.strip():
                    return nested
    # Fall back to the whole payload: a miss here should fail safe toward inspection.
    return json.dumps(payload, ensure_ascii=False)


def find_matches(command: str) -> tuple[list[str], list[str]]:
    """Return (feature areas, matched substrings) for immutability patterns."""
    areas: list[str] = []
    matches: list[str] = []
    for area, patterns in IMMUTABILITY_PATTERNS.items():
        for pattern in patterns:
            found = re.search(pattern, command, re.IGNORECASE)
            if found:
                if area not in areas:
                    areas.append(area)
                if found.group(0) not in matches:
                    matches.append(found.group(0))
    return areas, matches


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {"command": raw}

    command = extract_command(payload)
    areas, matches = find_matches(command)
    if not areas:
        return 0

    # Inspection stays allowed: an agent that cannot read the current state will guess.
    if not MUTATING.search(command):
        return 0

    print(
        BLOCK_MESSAGE.format(areas=", ".join(areas), matches=", ".join(matches)),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
