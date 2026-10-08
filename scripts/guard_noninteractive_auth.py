#!/usr/bin/env python3
"""Ask before an agent drives an authenticating login non-interactively.

WHY THIS EXISTS
---------------
On 2026-09-28 an agent working in this repository needed to run one ONTAP CLI command
(`cluster peer create`) on an FSx for NetApp ONTAP file system. It could not reach the
management endpoint directly, so it stood up a bastion and drove the login with `sshpass`,
feeding the fsxadmin password on stdin. The ONTAP SSH server offered
`password,keyboard-interactive`; the `sshpass -o PreferredAuthentications=password` attempt
did not satisfy it cleanly, the login was retried, and after a few failures ONTAP **locked
the fsxadmin account**.

The lock was not permanent. But it was still an outage of the exact credential the task
needed, and it arrived during a time-boxed operation — a cluster-peering passphrase on the
GCNV side expires in one hour — so the lockout threatened to force the whole peering
handshake to be restarted. Worse, the failure was read wrong at first: because a locked
ONTAP account returns `Permission denied` at the SSH layer, the agent nearly concluded the
stored password was wrong and went looking to reset it, which would have compounded the
change.

The general lesson is not about `sshpass` or ONTAP:

    Driving an authenticating login non-interactively, in a loop or a retrying wrapper,
    can lock the account out. A locked account is indistinguishable from a wrong
    credential, so the failure is also easy to misdiagnose.

WHAT THIS DOES
--------------
Reads a Kiro PreToolUse hook payload on stdin, extracts the command, and emits an
`ask` decision (exit 0 + a permissionDecision payload) when the command drives an
authenticating login with a machine-supplied secret — `sshpass`, a password or passphrase
piped or `here-string`-fed into `ssh`/`scp`/`sftp`, `ssh ... 'cluster peer create'` and
similar, or a bare credential handed to a CLI login. Interactive logins a human types into,
and read-only inspection, are left alone.

It never blocks. The point is a single pause to think about lockout thresholds and to
capture the exact error, not to forbid the technique — the technique was the right call
here; doing it blind was not.

Exit codes: 0 always (either silent-allow, or allow-with-ask-payload on stdout). It cannot
return 2. A gate that only ever asks must never be able to hard-block, or one bad pattern
takes out every shell command.

SELF-TEST
---------
Run `python3 guard_noninteractive_auth.py --selftest`. It covers both verdicts — ask and
allow — because a gate that only proves it fires has not shown that it stays quiet on the
ordinary logins that make up most of the work, and an ask that fires on everything gets
clicked through, which is how a gate stops working without failing.

REUSE
-----
Stdlib only, no repository-specific assumptions. Copy it into any project and wire it to a
PreToolUse hook alongside guard_irreversible_ops.py. Extend AUTH_PATTERNS as you meet new
wrappers; the categories matter more than the exact list.
"""

from __future__ import annotations

import json
import re
import sys

# Ways an agent feeds a secret into a login without a human typing it. Grouped so the
# ask message can name what was recognized. These are the shapes that retry on failure
# and so can trip a lockout threshold.
AUTH_PATTERNS: dict[str, str] = {
    # sshpass in any of its forms: -p inline, -e from env, -f from file, or bare.
    "sshpass non-interactive login": r"\bsshpass\b",
    # A secret piped or here-string-fed into an ssh/scp/sftp/telnet client. The login
    # program reads the password from the pipe, so failures are unattended and repeat.
    "secret piped into ssh/scp/sftp": (
        r"(?:\||<<<|printf|echo)[^|]*\|\s*(?:sshpass\s+)?(?:ssh|scp|sftp)\b"
        r"|(?:ssh|scp|sftp)\b[^|]*<<<"
    ),
    # ONTAP / network-appliance CLI driven over a one-shot ssh command. cluster peer
    # create, security login, and vserver peer are the ones that authenticate and can
    # lock; running them through `ssh host 'cmd'` is the unattended path.
    "appliance CLI over one-shot ssh": (
        r"\bssh\b[^\n]*\b(?:cluster\s+peer|security\s+login|vserver\s+peer)\b"
    ),
    # A password/passphrase handed to a CLI login verb on the command line.
    "credential on a CLI login command": (
        r"\b(?:login|auth(?:enticate)?)\b[^\n]*"
        r"(?:--?password|--?passwd|--?passphrase|--?secret|--?token)\b"
    ),
}

# An authenticating context. A pattern above plus one of these is what makes the command
# a login attempt rather than, say, prose about ssh. Kept broad but not universal: a bare
# `ssh host uptime` with a key is unattended too, but it does not carry a password to
# fumble, so it cannot drive the lockout this guard is about.
CREDENTIAL_SIGNAL = re.compile(
    r"""(?xi)
      sshpass
    | -o\s*PreferredAuthentications\s*=?\s*password
    | -o\s*PubkeyAuthentication\s*=?\s*no
    | \bpass(?:word|phrase|wd)\b
    | \bSSHPASS\b
    | --?password | --?passwd | --?passphrase
    | \bcluster\s+peer\b | \bsecurity\s+login\b | \bvserver\s+peer\b
    """
)

ASK_MESSAGE = """\
CONFIRM REQUIRED: this command drives an authenticating login non-interactively.

  Recognized : {areas}
  Matched    : {matches}

A machine-fed login that fails is retried without a human noticing, and enough failures
lock the account. A locked account then returns the same "permission denied" / "access
denied" as a wrong credential, so the lockout is easy to misdiagnose as a bad password and
"fix" by resetting it — compounding the change.

Before continuing, confirm in the conversation:

  1. The credential is known-correct (read it from its source; do not assume it is stale
     because a first attempt failed).
  2. The target's lockout threshold and whether one more failed attempt would trip it.
  3. That the login method matches what the server offers (e.g. an appliance offering
     keyboard-interactive may reject a password-only sshpass attempt and retry).
  4. If this is a one-shot command over ssh, that the account is not already locked —
     check the account/lock state first rather than letting the wrapper retry.

If the account may already be locked, stop and read its state; do not send more attempts.
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
    # Fall back to the whole payload: a miss here should fail safe toward asking.
    return json.dumps(payload, ensure_ascii=False)


def find_matches(command: str) -> tuple[list[str], list[str]]:
    """Return (recognized areas, matched substrings) for auth-login patterns."""
    areas: list[str] = []
    matches: list[str] = []
    for area, pattern in AUTH_PATTERNS.items():
        found = re.search(pattern, command, re.IGNORECASE)
        if found:
            if area not in areas:
                areas.append(area)
            snippet = found.group(0).strip()
            if snippet and snippet not in matches:
                matches.append(snippet)
    return areas, matches


# Prose about these tools is not a login. A commit or PR body naming sshpass was flagged
# during testing — the same "documentation about the hazard trips the guard" failure the
# sibling guard had to fix. A guard that blocks writing about the hazard gets switched off.
PROSE_CONTEXT = re.compile(
    r"""(?xi)
      \bgit\s+commit\b
    | \bgit\s+tag\b
    | \bgh\s+(?:pr|issue|release)\b
    | \bglab\s+(?:mr|issue)\b
    | \becho\b | \bprintf\b(?![^|]*\|\s*(?:sshpass\s+)?(?:ssh|scp|sftp)\b)
    """
)


def verdict(command: str) -> str:
    """Return 'ask' or 'allow' for one command. Never 'block' — this gate cannot hard-fail."""
    areas, _ = find_matches(command)
    if not areas:
        return "allow"
    # A recognized pattern must be paired with a credential signal, so that prose or a
    # key-based `ssh host cmd` with no password does not get flagged.
    if not CREDENTIAL_SIGNAL.search(command):
        return "allow"
    # Writing about the technique (a commit message, a PR body) is not performing it.
    # Checked after the credential signal so a real `printf secret | ssh` still asks: the
    # printf negative-lookahead above keeps a piped-secret printf out of this exemption.
    if PROSE_CONTEXT.search(command) and not re.search(r"\bsshpass\b\s+-", command):
        return "allow"
    return "ask"


# (expected_verdict, description, command) — kept in this file so the cases travel with the
# guard when it is copied into another repository. Both verdicts are covered: a gate that
# only proves it asks has not shown it stays quiet on ordinary logins, and over-asking is
# what trains people to click through.
SELFTEST_CASES: list[tuple[str, str, str]] = [
    # ---- ask: the shapes that can drive a lockout ----
    (
        "ask",
        "the sshpass login that locked fsxadmin",
        (
            "export SSHPASS='secret'; sshpass -e ssh -o PreferredAuthentications=password"
            " fsxadmin@172.30.131.210 'cluster peer create -peer-addrs 172.16.1.82'"
        ),
    ),
    (
        "ask",
        "sshpass with an inline password",
        "sshpass -p 'hunter2' ssh admin@10.0.0.5 version",
    ),
    (
        "ask",
        "passphrase piped into ssh",
        "printf '%s\\n' 'my-passphrase' | ssh fsxadmin@10.0.0.5 'cluster peer create'",
    ),
    (
        "ask",
        "password here-string fed into ssh",
        "ssh admin@10.0.0.5 'security login show' <<< 'password123'",
    ),
    (
        "ask",
        "cluster peer create over a one-shot ssh with a password flag",
        "ssh admin@host 'cluster peer create -peer-addrs 1.2.3.4' -o PubkeyAuthentication=no",
    ),
    (
        "ask",
        "a CLI login verb carrying a password",
        "some-cli login --username admin --password 's3cr3t'",
    ),
    # ---- allow: interactive logins and read-only work must stay quiet ----
    (
        "allow",
        "an interactive ssh a human types the password into",
        "ssh fsxadmin@172.30.131.210",
    ),
    (
        "allow",
        "key-based ssh running a read-only command, no password",
        "ssh -i key.pem ec2-user@10.0.0.5 'uptime'",
    ),
    (
        "allow",
        "reading cluster peer state via the AWS API",
        "aws fsx describe-file-systems --file-system-id fs-0123456789abcdef0",
    ),
    (
        "allow",
        "prose mentioning sshpass in a commit message is not a login",
        "git commit -m 'docs: explain why sshpass locked the account'",
    ),
    (
        "allow",
        "a plain reachability test, no credential",
        "nc -z -w 5 172.30.131.210 22",
    ),
    (
        "allow",
        "reading the fsxadmin secret is not itself a login",
        "aws secretsmanager get-secret-value --secret-id fsx-ontap-fsxadmin-credentials",
    ),
]


def selftest() -> int:
    failures = 0
    for want, description, command in SELFTEST_CASES:
        got = verdict(command)
        if got == want:
            print(f"  pass ({got})  {description}")
        else:
            failures += 1
            print(f"  FAIL want={want} got={got}  {description}")
    total = len(SELFTEST_CASES)
    print(f"\n{total - failures}/{total} cases passed")
    return 1 if failures else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    # Run by hand with no piped input, json.load blocks on the terminal with no
    # indication why. Kiro always supplies stdin, so this only affects someone
    # verifying the guard manually. Point at the self-test instead.
    if sys.stdin.isatty():
        print(
            "This is a PreToolUse hook: it expects a JSON event on stdin.\n"
            "  To verify ask / allow behaviour, run:\n"
            "    python3 scripts/guard_noninteractive_auth.py --selftest",
            file=sys.stderr,
        )
        return 0

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {"command": raw}

    command = extract_command(payload)
    if verdict(command) == "ask":
        areas, matches = find_matches(command)
        json.dump(
            {
                "hookSpecificOutput": {
                    "permissionDecision": "ask",
                    "permissionDecisionReason": ASK_MESSAGE.format(
                        areas=", ".join(areas),
                        matches=", ".join(matches) or "(login pattern)",
                    ),
                }
            },
            sys.stdout,
        )
        return 0

    # Interactive logins and read-only work stay silent: over-asking trains people to
    # click through, which is how a gate stops working without ever failing.
    return 0


if __name__ == "__main__":
    sys.exit(main())
