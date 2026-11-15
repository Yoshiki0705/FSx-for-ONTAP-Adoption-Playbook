"""The skip-paths input of sbom-generate rejects unsafe values and records what it excludes.

The check body and the helper script are cut out of the workflow file and executed as they are, so the
test cannot drift from the code the workflow runs. Only the cutting is text-based.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "sbom-generate.yml"
SHA = "0123456789abcdef0123456789abcdef01234567"


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def check_inputs_script() -> str:
    """The `run:` body of the step named `Check inputs`, dedented."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(
        i for i, ln in enumerate(lines) if ln.strip() == "- name: Check inputs"
    )
    run = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    body_indent = _indent(lines[run]) + 2
    body: list[str] = []
    for ln in lines[run + 1 :]:
        if ln.strip() and _indent(ln) < body_indent:
            break
        body.append(ln[body_indent:] if ln.strip() else "")
    return "\n".join(body) + "\n"


def helper_script() -> str:
    """The Python heredoc that the workflow writes to sc.py, dedented."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip().endswith("<<'PY'"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "PY")
    margin = _indent(lines[end])
    return "\n".join(ln[margin:] for ln in lines[start + 1 : end]) + "\n"


class SkipPathsCheck(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.temp = Path(self._tmp.name)
        self.script = self.temp / "check.sh"
        self.script.write_text(check_inputs_script(), encoding="utf-8")

    def run_check(self, value: str) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": os.environ["PATH"],
            "RUNNER_TEMP": str(self.temp),
            "RETENTION_DAYS": "90",
            "IMAGE_BUILD_COMMAND": "",
            "IMAGE_REF": "",
            "SCANNER_SERIES": "trivy",
            "SKIP_PATHS": value,
        }
        return subprocess.run(
            ["bash", "-e", str(self.script)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def accepted(self, value: str) -> list[str]:
        result = self.run_check(value)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = (self.temp / "skip-paths.txt").read_text(encoding="utf-8")
        return text.splitlines()

    def rejected(self, value: str) -> subprocess.CompletedProcess[str]:
        result = self.run_check(value)
        self.assertEqual(result.returncode, 1, f"{value!r} was accepted")
        self.assertIn("::error::skip-paths", result.stdout)
        return result

    def test_empty_value_writes_an_empty_file(self) -> None:
        self.assertEqual(self.accepted(""), [])
        self.assertEqual((self.temp / "skip-paths.txt").read_text(encoding="utf-8"), "")

    def test_blank_lines_only_write_an_empty_file(self) -> None:
        self.assertEqual(self.accepted("\n  \n\t\n"), [])

    def test_accepted_forms_are_normalized(self) -> None:
        value = (
            "tests/fixtures\n  ./examples/legacy/  \n\n**/testdata\ndocs/*/sample?\n"
        )
        self.assertEqual(
            self.accepted(value),
            ["tests/fixtures", "examples/legacy", "**/testdata", "docs/*/sample?"],
        )

    def test_crlf_line_endings_are_accepted(self) -> None:
        self.assertEqual(
            self.accepted("tests/fixtures\r\nexamples/old\r\n"),
            ["tests/fixtures", "examples/old"],
        )

    def test_unsafe_values_are_rejected(self) -> None:
        for value in (
            "/etc",
            "~/fixtures",
            "-rf",
            "../outside",
            "a/../b",
            "a..b",
            "a\\b",
            "a//b",
            "has space/inside",
            "semi;colon",
            "dollar$HOME",
            "back`tick`",
            "quote'd",
            "brace{a,b}",
            "uni/コード",
        ):
            with self.subTest(value=value):
                self.rejected(value)

    def test_values_that_match_the_whole_repository_are_rejected(self) -> None:
        for value in (".", "./", "./.", "*", "**", "**/*", "**/", "./*", "././", "*/"):
            with self.subTest(value=value):
                self.rejected(value)

    def test_more_than_fifty_entries_are_rejected(self) -> None:
        fifty = "\n".join(f"fixtures/d{i}" for i in range(50))
        self.assertEqual(len(self.accepted(fifty)), 50)
        self.rejected(fifty + "\nfixtures/one-more")

    def test_error_names_the_line_not_its_content(self) -> None:
        result = self.rejected("tests/ok\n\nsecret$value")
        self.assertIn("line 3", result.stdout)
        self.assertNotIn("secret", result.stdout)


class SkipPathsRecord(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.temp = Path(self._tmp.name)
        self.sc = self.temp / "sc.py"
        self.sc.write_text(helper_script(), encoding="utf-8")

    def sc_run(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = {"PATH": os.environ["PATH"], "COMMIT_SHA": SHA}
        return subprocess.run(
            [sys.executable, str(self.sc), *args],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def write_sbom(self) -> Path:
        path = self.temp / "sbom.spdx.json"
        path.write_text(
            json.dumps(
                {
                    "spdxVersion": "SPDX-2.3",
                    "creationInfo": {
                        "created": "2026-01-01T00:00:00Z",
                        "creators": ["Tool: trivy-0.76.2"],
                    },
                    "packages": [],
                    "relationships": [],
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_generation_without_the_file_records_an_empty_list(self) -> None:
        sbom, out = self.write_sbom(), self.temp / "generation.json"
        result = self.sc_run("generation", str(sbom), str(out), "trivy", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(out.read_text(encoding="utf-8"))["skipped_paths"], []
        )

    def test_generation_records_paths_in_order_without_duplicates(self) -> None:
        sbom, out = self.write_sbom(), self.temp / "generation.json"
        skip = self.temp / "skip-paths.txt"
        skip.write_text("b/fixtures\na/fixtures\nb/fixtures\n", encoding="utf-8")
        result = self.sc_run("generation", str(sbom), str(out), "trivy", "0", str(skip))
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(doc["skipped_paths"], ["b/fixtures", "a/fixtures"])
        self.assertEqual(doc["image_sbom_count"], 0)

    def test_empty_skip_file_records_an_empty_list(self) -> None:
        sbom, out = self.write_sbom(), self.temp / "generation.json"
        skip = self.temp / "skip-paths.txt"
        skip.write_text("", encoding="utf-8")
        self.sc_run("generation", str(sbom), str(out), "trivy", "0", str(skip))
        self.assertEqual(
            json.loads(out.read_text(encoding="utf-8"))["skipped_paths"], []
        )

    def test_is_skipped_matches_directories_and_globs(self) -> None:
        spec = importlib.util.spec_from_file_location("sc_under_test", self.sc)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        is_skipped = module.is_skipped
        cases = [
            ("tests/fixtures/a.yaml", ["tests/fixtures"], True),
            ("tests/fixtures/deep/a.yaml", ["tests/fixtures"], True),
            ("tests/fixtures2/a.yaml", ["tests/fixtures"], False),
            ("src/tests/fixtures/a.yaml", ["tests/fixtures"], False),
            ("a/testdata/x.yaml", ["**/testdata"], True),
            ("testdata/x.yaml", ["**/testdata"], True),
            ("docs/one/sample/x.yaml", ["docs/*/sample"], True),
            ("template.yaml", [], False),
            ("template.yaml", ["tests/fixtures"], False),
        ]
        for rel, patterns, expected in cases:
            with self.subTest(rel=rel, patterns=patterns):
                self.assertEqual(is_skipped(rel, patterns), expected)


@unittest.skipUnless(
    subprocess.run(
        [sys.executable, "-c", "import yaml"], capture_output=True, check=False
    ).returncode
    == 0,
    "PyYAML is not installed; the workflow installs it before the helper runs",
)
class SkipPathsInventory(unittest.TestCase):
    def test_inventory_leaves_out_templates_under_skipped_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            sc = temp / "sc.py"
            sc.write_text(helper_script(), encoding="utf-8")
            repo = temp / "repo"
            for rel in ("app/template.yaml", "tests/fixtures/old/template.yaml"):
                path = repo / rel
                path.parent.mkdir(parents=True)
                path.write_text(
                    "AWSTemplateFormatVersion: '2010-09-09'\n"
                    "Resources:\n"
                    "  Fn:\n"
                    "    Type: AWS::Lambda::Function\n"
                    "    Properties:\n"
                    "      Runtime: python3.12\n",
                    encoding="utf-8",
                )
            skip = temp / "skip-paths.txt"
            skip.write_text("tests/fixtures\n", encoding="utf-8")
            env = {"PATH": os.environ["PATH"]}

            def inventory(*extra: str) -> dict[str, object]:
                out = temp / "inventory.json"
                out.unlink(missing_ok=True)
                result = subprocess.run(
                    [sys.executable, str(sc), "inventory", str(repo), str(out), *extra],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(out.read_text(encoding="utf-8"))

            self.assertEqual(inventory()["templates"], 2)
            self.assertEqual(inventory(str(skip))["templates"], 1)


if __name__ == "__main__":
    unittest.main()
