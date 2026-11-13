"""The supply-chain copy gate passes on the real tree and fails on each kind of broken copy."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools" / "check_supply_chain_copy.py"
RECORD = Path("docs/agent/supply-chain-source.json")


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


class SupplyChainCopyGate(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        for directory in ("tools/supply_chain", "tools/supply_chain_adapters"):
            shutil.copytree(
                ROOT / directory,
                self.root / directory,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        (self.root / RECORD).parent.mkdir(parents=True)
        shutil.copy(ROOT / RECORD, self.root / RECORD)

    def test_real_tree_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GATE)], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("examined 14 file(s)", result.stdout)

    def test_pristine_scratch_copy_passes(self) -> None:
        self.assertEqual(_run(self.root).returncode, 0)

    def test_one_byte_change_fails(self) -> None:
        path = self.root / "tools/supply_chain/models.py"
        path.write_bytes(path.read_bytes() + b"#")
        result = _run(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("tools/supply_chain/models.py: content differs", result.stdout)

    def test_missing_file_fails(self) -> None:
        (self.root / "tools/supply_chain_adapters/spdx.py").unlink()
        result = _run(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing from the tree", result.stdout)

    def test_file_not_in_record_fails(self) -> None:
        (self.root / "tools/supply_chain/extra.py").write_text("X = 1\n")
        result = _run(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("tools/supply_chain/extra.py: not in the record", result.stdout)

    def test_malformed_sha256_fails(self) -> None:
        record = json.loads((self.root / RECORD).read_text(encoding="utf-8"))
        record["files"]["tools/supply_chain/vex.py"]["sha256"] = "not-a-hash"
        (self.root / RECORD).write_text(json.dumps(record), encoding="utf-8")
        result = _run(self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not 64 lowercase hex", result.stdout)

    def test_selftest_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GATE), "--selftest"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
