#!/usr/bin/env python3
"""Verify that the supply-chain core copied into this repository is still the recorded copy.

`tools/supply_chain/` and `tools/supply_chain_adapters/` are byte-for-byte copies of files at
one pinned commit of another repository. A copy that is edited here silently becomes a fork, and
the two sides then disagree about the same decision rules. The record
`docs/agent/supply-chain-source.json` names the source commit and the SHA-256 of every copied file;
this gate compares the tree with the record.

Usage:
    python3 tools/check_supply_chain_copy.py             # offline: tree against the record
    python3 tools/check_supply_chain_copy.py --external  # also fetch the source commit (network)
    python3 tools/check_supply_chain_copy.py --selftest  # broken copies must fail

`--external` needs the network, so it is not part of `make all` or CI.
The last output line always states how many files were examined, including zero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = Path("docs/agent/supply-chain-source.json")
COPY_DIRS = ("tools/supply_chain", "tools/supply_chain_adapters")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_FETCH_TIMEOUT_SECONDS = 30


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load(root: Path) -> tuple[dict, list[str]]:
    path = root / RECORD
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, [f"{RECORD}: record unreadable ({exc.__class__.__name__})"]
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        return {}, [f"{RECORD}: record has no 'files' object"]
    return data, []


def check(root: Path) -> tuple[list[str], int]:
    """Return (problems, number of files examined)."""
    data, problems = _load(root)
    if problems:
        return problems, 0
    commit = data.get("source_commit")
    if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
        problems.append(f"{RECORD}: source_commit is not 40 lowercase hex digits")
    if not isinstance(data.get("source_repo"), str) or not data["source_repo"]:
        problems.append(f"{RECORD}: source_repo missing")
    examined = 0
    recorded = set()
    for rel, entry in data["files"].items():
        recorded.add(rel)
        examined += 1
        want = entry.get("sha256") if isinstance(entry, dict) else None
        if not isinstance(want, str) or not _SHA256.fullmatch(want):
            problems.append(f"{rel}: recorded sha256 is not 64 lowercase hex digits")
            continue
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel}: missing from the tree")
        elif _sha256(path.read_bytes()) != want:
            problems.append(f"{rel}: content differs from the record")
    for directory in COPY_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(root).as_posix()
            examined += rel not in recorded
            if rel not in recorded:
                problems.append(f"{rel}: not in the record")
    return problems, examined


def check_external(root: Path) -> tuple[list[str], int]:
    data, problems = _load(root)
    if problems:
        return problems, 0
    examined = 0
    for rel, entry in data["files"].items():
        url = f"https://raw.githubusercontent.com/{data['source_repo']}/{data['source_commit']}/{entry['source_path']}"
        examined += 1
        try:
            with urllib.request.urlopen(
                url, timeout=_FETCH_TIMEOUT_SECONDS
            ) as response:
                body = response.read()
        except (urllib.error.URLError, OSError) as exc:
            problems.append(f"{rel}: source fetch failed ({exc.__class__.__name__})")
            continue
        if _sha256(body) != entry["sha256"]:
            problems.append(f"{rel}: source content differs from the record")
    return problems, examined


def _report(problems: Sequence[str], examined: int) -> int:
    for line in problems:
        print(line)
    print(f"examined {examined} file(s); {len(problems)} problem(s)")
    return 1 if problems else 0


def _write_tree(root: Path, files: dict[str, bytes], commit: str = "a" * 40) -> None:
    record = {
        "source_repo": "example-org/example-repo",
        "source_commit": commit,
        "files": {
            rel: {"source_path": f"src/{Path(rel).name}", "sha256": _sha256(body)}
            for rel, body in sorted(files.items())
        },
    }
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(body)
    (root / RECORD).parent.mkdir(parents=True, exist_ok=True)
    (root / RECORD).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def selftest() -> int:
    good = {
        "tools/supply_chain/a.py": b"A = 1\n",
        "tools/supply_chain_adapters/b.py": b"B = 2\n",
    }
    failures = 0

    def expect(name: str, want_ok: bool, mutate) -> None:
        nonlocal failures
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tree(root, good)
            mutate(root)
            problems, examined = check(root)
        ok = not problems
        verdict = "ok" if ok == want_ok and examined > 0 else "FAIL"
        failures += verdict == "FAIL"
        print(f"selftest {name}: {verdict}")

    def flip_byte(root: Path) -> None:
        (root / "tools/supply_chain/a.py").write_bytes(b"A = 2\n")

    def drop_file(root: Path) -> None:
        (root / "tools/supply_chain_adapters/b.py").unlink()

    def add_file(root: Path) -> None:
        (root / "tools/supply_chain/extra.py").write_bytes(b"X = 0\n")

    def bad_sha(root: Path) -> None:
        record = json.loads((root / RECORD).read_text(encoding="utf-8"))
        record["files"]["tools/supply_chain/a.py"]["sha256"] = "zz"
        (root / RECORD).write_text(json.dumps(record), encoding="utf-8")

    def bad_commit(root: Path) -> None:
        record = json.loads((root / RECORD).read_text(encoding="utf-8"))
        record["source_commit"] = "main"
        (root / RECORD).write_text(json.dumps(record), encoding="utf-8")

    expect("intact copy", True, lambda root: None)
    expect("one byte changed", False, flip_byte)
    expect("file missing", False, drop_file)
    expect("file not in record", False, add_file)
    expect("malformed sha256", False, bad_sha)
    expect("malformed commit", False, bad_commit)
    print(f"selftest: {'passed' if not failures else f'{failures} failure(s)'}")
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--external",
        action="store_true",
        help="fetch the source commit and compare (network)",
    )
    parser.add_argument(
        "--selftest", action="store_true", help="check that broken copies fail"
    )
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    problems, examined = (check_external if args.external else check)(args.root)
    return _report(problems, examined)


if __name__ == "__main__":
    sys.exit(main())
