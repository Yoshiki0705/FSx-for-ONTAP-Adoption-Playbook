"""Regression boundaries found while reviewing the staged editorial reports."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import audit_public_output as audit
import check_document_structure as structure
import check_mermaid as mermaid


class TemporaryTree(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write(self, relative: str, text: str, *, executable: bool = False) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if executable:
            path.chmod(0o755)
        return path

    def run_tool(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / script),
                "--path",
                str(self.root),
                *args,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )


class VocabularySurface(TemporaryTree):
    def test_every_registered_japanese_and_english_family(self) -> None:
        cases = (
            "顧客向け",
            "お客様向け",
            "差別化要素",
            "訴求する",
            "採用の決め手",
            "勝ち筋",
            "負けない",
            "テイクアウト",
            "競合奪還",
            "ソリューション",
            "提案する",
            "商談",
            "最も確実",
            "業界をリードする",
            "劇的に速い",
            "大幅に改善",
            "堅牢な設計",
            "強固な設計",
            "シームレスな移行",
            "スムーズな移行",
            "圧倒的な性能",
            "究極の構成",
            "最強の構成",
            "革命的な機能",
            "非常に速い",
            "極めて速い",
            "かなり速い",
            "The BEST option",
            "a customer workload",
            "competitive positioning",
            "a differentiator",
            "value proposition",
            "a win",
            "best-in-class",
            "industry-leading",
            "seamless migration",
            "revolutionary feature",
            "ultimate design",
            "unmatched speed",
            "unrivaled performance",
            "effortless operation",
            "dramatically faster",
            "significantly improves throughput",
            "guarantees all outcomes",
            "eliminates every failure",
            "competing tools",
            "competing product",
        )
        for text in cases:
            with self.subTest(text=text):
                categories = {category for category, _ in audit.audit_line(text)}
                self.assertIn("sales-vocabulary", categories)

    def test_frontmatter_non_prose_files_and_scan_flag_are_excluded(self) -> None:
        self.write(
            "note.md", "---\ntitle: best migration\n---\nMeasured behavior only.\n"
        )
        self.write("config.yml", "mode: best\n")
        result = self.run_tool(
            "audit_public_output.py", "--only", "sales-vocabulary", "--report"
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("clean", result.stdout)
        categories = {
            category for category, _ in audit.audit_line("best", scan_sales=False)
        }
        self.assertNotIn("sales-vocabulary", categories)

    def test_existing_neutrality_allowance_covers_staged_vocabulary(self) -> None:
        allowed_file = {
            category
            for category, _ in audit.audit_line(
                "best", file_allowed=frozenset({"neutrality"})
            )
        }
        allowed_line = {
            category
            for category, _ in audit.audit_line("best <!-- allow:neutrality -->")
        }
        self.assertNotIn("sales-vocabulary", allowed_file)
        self.assertNotIn("sales-vocabulary", allowed_line)

    def test_longer_outer_fence_is_not_closed_by_shorter_inner_fence(self) -> None:
        self.write("note.md", "````text\n```\nbest\n````\nbest\n")
        result = self.run_tool(
            "audit_public_output.py", "--only", "sales-vocabulary", "--report"
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("note.md:5: [sales-vocabulary]", result.stdout)
        self.assertNotIn("note.md:3: [sales-vocabulary]", result.stdout)

    def test_unclosed_frontmatter_fails_instead_of_hiding_vocabulary(self) -> None:
        self.write("note.md", "---\ntitle: x\nbest\n")
        result = self.run_tool(
            "audit_public_output.py", "--only", "sales-vocabulary", "--report"
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("frontmatter opens but never closes", result.stderr)

    def test_default_audit_rejects_sales_vocabulary(self) -> None:
        self.write("note.md", "best\n")
        result = self.run_tool("audit_public_output.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("note.md:1: [sales-vocabulary]", result.stderr)

    def test_full_clean_tree_passes_default_audit(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "audit_public_output.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(" clean", result.stdout)

    def test_exact_title_allowance_suppresses_only_its_line(self) -> None:
        self.write(
            "note.md",
            "| Source | Detail |\n"
            "|---|---|\n"
            "| [Best practices](https://example.com/source) | Exact title "
            "<!-- allow:sales-vocabulary - exact external title --> |\n"
            "| Local prose | best choice |\n",
        )
        result = self.run_tool(
            "audit_public_output.py", "--only", "sales-vocabulary", "--report"
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("note.md:4: [sales-vocabulary]", result.stdout)
        self.assertNotIn("note.md:3: [sales-vocabulary]", result.stdout)

    def test_report_succeeds_while_check_mode_fails(self) -> None:
        self.write("note.md", "best\n")
        reported = self.run_tool(
            "audit_public_output.py", "--only", "sales-vocabulary", "--report"
        )
        checked = self.run_tool("audit_public_output.py", "--only", "sales-vocabulary")
        self.assertEqual(reported.returncode, 0)
        self.assertEqual(checked.returncode, 1)


class StructureSurface(TemporaryTree):
    NOTE = """# 何を確認しますか？

一行の要約です。

## このノートで学べること

- 一つ目
- 二つ目

## このノートが答えないこと

- 一つ目
- 二つ目

## 前提レベル

basic

## 本文

説明です。

## 自環境での確認手順

```bash
printf 'verify'
```

### 期待結果

成功します。

## Read next

[次へ](next.md)
"""
    CHECKLIST = """# 作業前確認

## 目的

事故を防ぎます。

## 適用条件

作業前です。

## 検証手順

確認します。

## Read next

[次へ](next.md)
"""

    def messages(self, body: str, kind: str) -> set[str]:
        return {
            finding.message
            for finding in structure.inspect(self.write(f"{kind}.md", body), kind)
        }

    def test_fenced_examples_do_not_satisfy_structure(self) -> None:
        for marker in ("```", "~~~~"):
            with self.subTest(marker=marker):
                messages = self.messages(
                    f"{marker}markdown\n{self.NOTE}{marker}\n", "note"
                )
                self.assertIn("missing H1", messages)
                self.assertIn("missing learn section", messages)

    def test_summary_limits_and_prerequisite_vocabulary(self) -> None:
        japanese = self.NOTE.replace("一行の要約です。", "あ" * 61)
        self.assertIn(
            "Japanese summary exceeds 60 characters",
            self.messages(japanese, "note"),
        )
        bad_level = self.NOTE.replace("\nbasic\n", "\nexpert\n")
        self.assertIn(
            "prerequisite level must be basic, intermediate, or advanced",
            self.messages(bad_level, "note"),
        )

    def test_each_remaining_note_rule_has_a_breaking_fixture(self) -> None:
        cases = {
            "note H1 is not a question": self.NOTE.replace(
                "# 何を確認しますか？", "# 確認事項"
            ),
            "summary must be one non-empty line": self.NOTE.replace(
                "一行の要約です。", "一行目\n二行目"
            ),
            "learn section must contain exactly two bullets": self.NOTE.replace(
                "- 二つ目", "", 1
            ),
            "does-not-answer section must contain exactly two bullets": self.NOTE.replace(
                "- 二つ目", "", 2
            ),
            "prerequisite level must be basic, intermediate, or advanced": self.NOTE.replace(
                "\nbasic\n", "\nunknown\n"
            ),
            "missing body section": self.NOTE.replace("## 本文\n\n説明です。\n\n", ""),
            "environment verification lacks non-empty expected output": self.NOTE.replace(
                "### 期待結果\n\n成功します。", "### 期待結果\n"
            ),
            "environment verification lacks a non-empty fenced command": self.NOTE.replace(
                "```bash\nprintf 'verify'\n```\n\n", ""
            ),
            "duplicate body section": self.NOTE.replace(
                "## 本文\n\n説明です。",
                "## 本文\n\n説明です。\n\n## 本文\n\n重複です。",
            ),
            "H1 must be the first non-empty content": "先行本文です。\n\n" + self.NOTE,
            "Read next must contain exactly one link": self.NOTE.replace(
                "[次へ](next.md)", "none"
            ),
            "missing learn section": self.NOTE.replace(
                "## このノートで学べること", "## 別の節"
            ),
            "note sections are out of order": self.NOTE.replace(
                "## このノートで学べること", "## TEMP"
            )
            .replace("## このノートが答えないこと", "## このノートで学べること")
            .replace("## TEMP", "## このノートが答えないこと"),
        }
        for expected, body in cases.items():
            with self.subTest(expected=expected):
                self.assertIn(expected, self.messages(body, "note"))

    def test_content_heading_before_h1_is_rejected(self) -> None:
        messages = self.messages("## 先行見出し\n\n" + self.NOTE, "note")
        self.assertIn("H1 must be the first non-empty content", messages)

    def test_each_checklist_rule_has_a_breaking_fixture(self) -> None:
        cases = {
            "purpose section is empty": self.CHECKLIST.replace(
                "\n事故を防ぎます。\n", "\n"
            ),
            "applicability section is empty": self.CHECKLIST.replace(
                "\n作業前です。\n", "\n"
            ),
            "verification section is empty": self.CHECKLIST.replace(
                "\n確認します。\n", "\n"
            ),
            "Read next must contain exactly one link": self.CHECKLIST.replace(
                "[次へ](next.md)", "none"
            ),
            "missing purpose section": self.CHECKLIST.replace("## 目的", "## 別の節"),
            "checklist sections are out of order": self.CHECKLIST.replace(
                "## 目的", "## TEMP"
            )
            .replace("## 適用条件", "## 目的")
            .replace("## TEMP", "## 適用条件"),
        }
        for expected, body in cases.items():
            with self.subTest(expected=expected):
                self.assertIn(expected, self.messages(body, "checklist"))

    def test_report_succeeds_while_check_mode_fails(self) -> None:
        self.write("docs/ja/domain/notes/sample.md", "# statement\n")
        self.assertEqual(self.run_tool("check_document_structure.py").returncode, 0)
        self.assertEqual(
            self.run_tool("check_document_structure.py", "--check").returncode, 1
        )


class CliModeSurface(TemporaryTree):
    def test_sentence_and_glossary_report_check_modes(self) -> None:
        self.write("docs/ja/sample.md", "SVMを使います。" + "あ" * 81 + "。\n")
        for script in ("check_sentence_length.py", "check_glossary_first_use.py"):
            with self.subTest(script=script):
                self.assertEqual(self.run_tool(script).returncode, 0)
                self.assertEqual(self.run_tool(script, "--check").returncode, 1)

    def test_mermaid_report_check_and_missing_tool_modes(self) -> None:
        self.write("docs/sample.md", "````mermaid\nflowchart LR\nA-->B\n")
        cli = self.write("mmdc", "#!/bin/sh\nexit 0\n", executable=True)
        self.assertEqual(
            self.run_tool("check_mermaid.py", "--cli", str(cli)).returncode, 0
        )
        self.assertEqual(
            self.run_tool("check_mermaid.py", "--cli", str(cli), "--check").returncode,
            1,
        )
        missing = self.run_tool("check_mermaid.py", "--cli", "missing-mmdc")
        self.assertEqual(missing.returncode, 2)
        self.assertIn("unavailable", missing.stderr)

    def test_mermaid_info_metadata_reaches_real_renderer(self) -> None:
        cli = ROOT / "node_modules/.bin/mmdc"
        if not cli.is_file():
            self.skipTest("run npm ci to install the exact-pinned Mermaid CLI")
        source = self.write(
            "metadata.md", "```mermaid title=flow\nflowchart LR\nA-->B\n```\n"
        )
        blocks = mermaid.extract(source)
        self.assertEqual(len(blocks), 1)
        self.assertIsNone(mermaid.render(blocks[0], cli))

    def test_mermaid_clarity_report_succeeds_while_check_fails(self) -> None:
        self.write(
            "docs/sample.md",
            "```mermaid\n"
            "flowchart TD\n"
            "Q{Purpose} -- Archive --> A[Archive]\n"
            "Q --> B[Availability]\n"
            "```\n",
        )
        cli = self.write("mmdc", "#!/bin/sh\nexit 0\n", executable=True)
        reported = self.run_tool("check_mermaid.py", "--cli", str(cli))
        checked = self.run_tool("check_mermaid.py", "--cli", str(cli), "--check")
        self.assertEqual(reported.returncode, 0, reported.stderr)
        self.assertIn("business semantics are not evaluated", reported.stdout)
        self.assertIn("2 decision-clarity finding(s)", reported.stdout)
        self.assertEqual(checked.returncode, 1)

    def test_long_mermaid_fence_reaches_real_renderer(self) -> None:
        cli = ROOT / "node_modules/.bin/mmdc"
        if not cli.is_file():
            self.skipTest("run npm ci to install the exact-pinned Mermaid CLI")
        source = self.write("sample.md", "```` mermaid\nflowchart LR\nA-->B\n`````\n")
        blocks = mermaid.extract(source)
        self.assertEqual(len(blocks), 1)
        self.assertIsNone(mermaid.render(blocks[0], cli))


if __name__ == "__main__":
    unittest.main()
