"""Positive and breaking fixtures for every staged editorial validator family."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import audit_public_output as audit
import check_document_structure as structure
import check_glossary_first_use as glossary
import check_mermaid as mermaid
import check_sentence_length as sentences
import editorial_markdown
import frontmatter
import validate_frontmatter

from scripts.tests.test_ci_gate_parity import leaf_gates, prerequisites

AGREED_GLOSSARY_TERMS = {
    "S3 Access Point": ("S3 Access Point", "S3 Access Points"),
    "throughput capacity": ("throughput capacity", "スループット容量"),
    "capacity pool": ("capacity pool", "容量プール"),
    "security style": ("security style", "セキュリティスタイル"),
    "SnapMirror": ("SnapMirror",),
    "FlexClone": ("FlexClone",),
    "FlexCache": ("FlexCache",),
    "FlexVol": ("FlexVol",),
    "NVRAM": ("NVRAM",),
    "inode": ("inode",),
    "SVM": ("SVM",),
    "LIF": ("LIF",),
}


class TemporaryMarkdown(unittest.TestCase):
    def write(self, content: str, relative: str = "sample.md") -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path


class MarkdownProseFamilies(TemporaryMarkdown):
    def test_paragraph_and_list_are_returned_and_exclusions_are_omitted(self) -> None:
        blocks = editorial_markdown.prose_blocks(
            """---
title: x
---
# Heading

paragraph line one
line two

- list item

| table | value |
|---|---|
table | value
--- | ---
SVM | hidden
> quoted SVM
```text
fenced SVM
```
<!-- lang-switcher:start -->
SVM
<!-- lang-switcher:end -->
"""
        )
        self.assertEqual(
            [block.raw for block in blocks],
            ["paragraph line one line two", "list item"],
        )
        self.assertEqual([block.line for block in blocks], [6, 9])

    def test_link_label_remains_visible_but_url_and_markup_do_not(self) -> None:
        visible = editorial_markdown.normalized_visible_text(
            "**See** [SVM](https://example.com) https://example.com/x `code`",
            include_inline_code=False,
        )
        self.assertEqual(visible.strip(), "See SVM")

    def test_bare_url_stops_before_japanese_punctuation_and_prose(self) -> None:
        visible = editorial_markdown.normalized_visible_text(
            "https://example.com/path。SVMを使います。",
            include_inline_code=False,
        )
        self.assertEqual(visible, "。SVMを使います。")


class SentenceLengthFamilies(TemporaryMarkdown):
    def _lengths(self, body: str) -> list[tuple[int, str]]:
        path = self.write(body)
        return [(finding.length, finding.level) for finding in sentences.inspect(path)]

    def test_exact_boundaries(self) -> None:
        self.assertEqual(self._lengths("あ" * 49 + "。"), [])
        self.assertEqual(self._lengths("あ" * 50 + "。"), [(51, "warning")])
        self.assertEqual(self._lengths("あ" * 79 + "。"), [(80, "warning")])
        self.assertEqual(self._lengths("あ" * 80 + "。"), [(81, "violation")])

    def test_paragraph_and_list_are_checked(self) -> None:
        self.assertEqual(
            len(self._lengths("あ" * 51 + "。\n\n- " + "い" * 51 + "。")), 2
        )

    def test_every_excluded_block_family_is_ignored(self) -> None:
        long = "あ" * 90 + "。"
        body = (
            f"# {long}\n\n| {long} | x |\n| --- | --- |\n\n{long} | x\n--- | ---\n\n> {long}\n\n"
            f"```text\n{long}\n```\n\n<!-- lang-switcher:start -->\n{long}\n<!-- lang-switcher:end -->\n"
            f"https://example.com/{'x' * 100}\n"
        )
        self.assertEqual(self._lengths(body), [])

    def test_bare_url_does_not_hide_adjacent_japanese_sentence(self) -> None:
        self.assertEqual(
            self._lengths("https://example.com/path。" + "あ" * 80 + "。"),
            [(81, "violation")],
        )

    def test_thresholds_apply_only_to_sentences_with_japanese_script(self) -> None:
        self.assertEqual(self._lengths("A" * 101 + "."), [])
        self.assertEqual(self._lengths("A" * 101 + "!短い文です。"), [])
        self.assertEqual(self._lengths("SVM " + "あ" * 80 + "。"), [(84, "violation")])


class GlossaryFirstUseFamilies(TemporaryMarkdown):
    TARGET = "../../ja/reference/glossary/README.md#term"

    def terms(self, body: str) -> list[str]:
        return [finding.term for finding in glossary.inspect(self.write(body))]

    def test_agreed_terms_and_aliases_are_pinned_independently(self) -> None:
        self.assertEqual(glossary.TERM_ALIASES, AGREED_GLOSSARY_TERMS)
        for term, aliases in AGREED_GLOSSARY_TERMS.items():
            for alias in aliases:
                with self.subTest(term=term, alias=alias):
                    self.assertEqual(self.terms(f"{alias}を確認します。"), [term])

    def test_each_required_term_is_detected_unlinked(self) -> None:
        body = "。".join(AGREED_GLOSSARY_TERMS)
        self.assertEqual(set(self.terms(body)), set(AGREED_GLOSSARY_TERMS))

    def test_linked_first_use_allows_later_plain_use(self) -> None:
        self.assertEqual(
            self.terms(f"[SVM]({self.TARGET})を作成します。\n\nSVM を確認します。"), []
        )

    def test_unlinked_first_use_is_reported_even_when_later_use_is_linked(self) -> None:
        self.assertEqual(
            self.terms(f"SVMを作成します。\n\n[SVM]({self.TARGET})を確認します。"),
            ["SVM"],
        )

    def test_japanese_adjacency_plural_and_case_insensitive_phrases(self) -> None:
        found = self.terms(
            "SVMを確認し、S3 Access PointsとCAPACITY POOL、"
            "スループット容量、セキュリティスタイルを使います。"
        )
        self.assertEqual(
            found,
            [
                "SVM",
                "S3 Access Point",
                "capacity pool",
                "throughput capacity",
                "security style",
            ],
        )

    def test_each_excluded_block_family_is_ignored(self) -> None:
        body = """# SVM

| SVM | x |
|---|---|
term | SVM
--- | ---
> SVM
```text
SVM
```
`SVM` https://example.com/SVM
<!-- lang-switcher:start -->
SVM
<!-- lang-switcher:end -->
"""
        self.assertEqual(self.terms(body), [])

    def test_bare_url_does_not_hide_adjacent_glossary_term(self) -> None:
        self.assertEqual(
            self.terms("https://example.com/path。SVMを使います。"), ["SVM"]
        )

    def test_glossary_directory_and_readme_targets_allow_optional_anchors(self) -> None:
        for target in (
            "../../ja/reference/glossary/",
            "../../ja/reference/glossary/#svm",
            "../../ja/reference/glossary/README.md",
            "../../ja/reference/glossary/README.md#svm",
        ):
            with self.subTest(target=target):
                self.assertEqual(self.terms(f"[SVM]({target})を作成します。"), [])

    def test_non_glossary_link_does_not_satisfy_first_use(self) -> None:
        self.assertEqual(
            self.terms("[SVM](https://example.com/page)を作成します。"), ["SVM"]
        )


class StructureFamilies(TemporaryMarkdown):
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
    EN_NOTE = """# What should you verify?

This summary uses exactly sixteen short words to exceed the agreed English maximum for one line today.

## What you will learn

- First
- Second

## What this note does not answer

- First
- Second

## Prerequisite level

basic

## Body

Explanation.

## Verify it in your environment

```bash
printf 'verify'
```

### Expected output

Success.

## Read next

[Next](next.md)
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

    def test_valid_note_and_checklist(self) -> None:
        self.assertEqual(structure.inspect(self.write(self.NOTE), "note"), [])
        self.assertEqual(structure.inspect(self.write(self.CHECKLIST), "checklist"), [])

    def test_english_summary_limit_is_enforced(self) -> None:
        messages = {
            finding.message
            for finding in structure.inspect(self.write(self.EN_NOTE), "note")
        }
        self.assertIn("English summary exceeds 15 words", messages)

    def test_note_breaks_question_summary_counts_order_expected_output_and_read_next(
        self,
    ) -> None:
        broken = self.NOTE.replace("# 何を確認しますか？", "# 確認事項").replace(
            "一行の要約です。", "一行目\n二行目"
        )
        broken = broken.replace("- 二つ目", "", 1).replace(
            "### 期待結果\n\n成功します。", ""
        )
        broken = broken.replace("[次へ](next.md)", "[一](one.md) [二](two.md)")
        messages = {
            finding.message for finding in structure.inspect(self.write(broken), "note")
        }
        self.assertTrue(
            {
                "note H1 is not a question",
                "summary must be one non-empty line",
                "learn section must contain exactly two bullets",
                "environment verification lacks non-empty expected output",
                "Read next must contain exactly one link",
            }
            <= messages
        )

    def test_checklist_missing_empty_and_out_of_order_sections(self) -> None:
        broken = "# x\n\n## 適用条件\n\n## 目的\n\nx\n\n## Read next\n\nnone\n"
        messages = {
            finding.message
            for finding in structure.inspect(self.write(broken), "checklist")
        }
        self.assertIn("missing verification section", messages)
        self.assertIn("Read next must contain exactly one link", messages)

    def test_verification_requires_command_and_expected_output_independently(
        self,
    ) -> None:
        without_command = self.NOTE.replace("```bash\nprintf 'verify'\n```\n\n", "")
        messages = {
            finding.message
            for finding in structure.inspect(self.write(without_command), "note")
        }
        self.assertIn(
            "environment verification lacks a non-empty fenced command", messages
        )
        self.assertNotIn(
            "environment verification lacks non-empty expected output", messages
        )

        without_output = self.NOTE.replace("成功します。", "")
        messages = {
            finding.message
            for finding in structure.inspect(self.write(without_output), "note")
        }
        self.assertNotIn(
            "environment verification lacks a non-empty fenced command", messages
        )
        self.assertIn(
            "environment verification lacks non-empty expected output", messages
        )

    def test_duplicate_fixed_heading_and_content_before_h1_are_rejected(self) -> None:
        duplicate = self.NOTE.replace(
            "## 本文\n\n説明です。",
            "## 本文\n\n説明です。\n\n## 本文\n\n重複です。",
        )
        messages = {
            finding.message
            for finding in structure.inspect(self.write(duplicate), "note")
        }
        self.assertIn("duplicate body section", messages)
        for prefix in ("先行する本文です。\n\n", "## 先行する見出し\n\n"):
            with self.subTest(prefix=prefix):
                messages = {
                    finding.message
                    for finding in structure.inspect(
                        self.write(prefix + self.NOTE), "note"
                    )
                }
                self.assertIn("H1 must be the first non-empty content", messages)


class FrontmatterFamilies(TemporaryMarkdown):
    def validate_deployment(self, raw: str) -> list[str]:
        path = ROOT / "docs/ja/domains/cost/notes/zz-gate-probe-editorial.md"
        self.addCleanup(path.unlink, missing_ok=True)
        path.write_text(
            f"""---
title: probe
lifecycle: [design]
domains: [cost]
evidence: hypothesis
deployment_type: {raw}
lang: ja
---
# probe

未検証です。
""",
            encoding="utf-8",
        )
        return validate_frontmatter.validate(path)[0]

    def test_scalar_and_nonempty_inline_lists_accept_only_four_values(self) -> None:
        for raw in ["MULTI_AZ_1", "[MULTI_AZ_2]", "[SINGLE_AZ_1, SINGLE_AZ_2]"]:
            parsed = frontmatter.parse(f"deployment_type: {raw}")
            values = validate_frontmatter._as_list(parsed["deployment_type"])
            self.assertTrue(values)
            self.assertLessEqual(set(values), validate_frontmatter.DEPLOYMENT_TYPES)
            self.assertEqual(self.validate_deployment(raw), [])

    def test_empty_and_unknown_deployment_values_fail_schema_validation(self) -> None:
        self.assertTrue(
            any("at least one" in error for error in self.validate_deployment("[]"))
        )
        self.assertTrue(
            any(
                "unknown value" in error
                for error in self.validate_deployment("MULTI_AZ_3")
            )
        )

    def test_empty_and_malformed_inline_lists_are_rejected(self) -> None:
        self.assertEqual(
            frontmatter.parse("deployment_type: []")["deployment_type"], []
        )
        with self.assertRaises(frontmatter.FrontmatterError):
            frontmatter.parse("deployment_type: [MULTI_AZ_1, , SINGLE_AZ_1]")

    def test_missing_verified_report_names_only_absent_future_fields(self) -> None:
        path = ROOT / "docs/ja/domains/cost/notes/zz-gate-probe-editorial.md"
        self.addCleanup(path.unlink, missing_ok=True)
        path.write_text(
            """---
title: probe
lifecycle: [design]
domains: [cost]
evidence: verified
verified_on: 2026-01-01
region: ap-northeast-1
ontap_version: 9.17.1P7D1
lang: ja
---
# probe
""",
            encoding="utf-8",
        )
        self.assertEqual(
            validate_frontmatter.missing_verified_metadata(path), ("deployment_type",)
        )


class SalesVocabularyFamilies(unittest.TestCase):
    def categories(self, line: str, *, in_fence: bool = False) -> set[str]:
        return {category for category, _ in audit.audit_line(line, in_fence=in_fence)}

    def test_japanese_and_english_vocab_case_and_adjacency(self) -> None:
        for text in (
            "圧倒的です",
            "これは非常に速い",
            "The BEST option",
            "competing tools",
            "Seamless migration",
        ):
            with self.subTest(text=text):
                self.assertIn("sales-vocabulary", self.categories(text))

    def test_code_url_fence_and_explicit_allowance_are_excluded(self) -> None:
        for text, fenced in (
            ("`best`", False),
            ("https://example.com/best", False),
            ("best", True),
            ("best <!-- allow:sales-vocabulary -->", False),
        ):
            with self.subTest(text=text):
                self.assertNotIn(
                    "sales-vocabulary", self.categories(text, in_fence=fenced)
                )
        self.assertNotIn(
            "sales-vocabulary",
            {
                category
                for category, _ in audit.audit_line(
                    "best", file_allowed=frozenset({"sales-vocabulary"})
                )
            },
        )

    def test_legitimate_measured_language_is_accepted(self) -> None:
        self.assertNotIn(
            "sales-vocabulary",
            self.categories("Throughput was 385 MB/s in the named test environment."),
        )


class MermaidFamilies(TemporaryMarkdown):
    def test_multiple_complete_blocks_and_non_mermaid_fence(self) -> None:
        path = self.write("""```mermaid
flowchart LR
 A --> B
```
```text
not Mermaid
```
~~~~mermaid
sequenceDiagram
 A->>B: hi
~~~~~
""")
        blocks = mermaid.extract(path)
        self.assertEqual(len(blocks), 2)
        self.assertTrue(all(block.error is None for block in blocks))
        self.assertIn("sequenceDiagram", blocks[1].source)

    def test_spaced_mermaid_info_string_is_extracted(self) -> None:
        for opening in ("``` mermaid", "```mermaid title=flow"):
            with self.subTest(opening=opening):
                blocks = mermaid.extract(
                    self.write(f"{opening}\nflowchart LR\n A --> B\n```\n")
                )
                self.assertEqual(len(blocks), 1)
                self.assertIsNone(blocks[0].error)
                self.assertIn("flowchart LR", blocks[0].source)

    def test_unterminated_block_is_a_finding(self) -> None:
        block = mermaid.extract(self.write("```mermaid\nflowchart LR\n A --> B\n"))[0]
        self.assertEqual(block.error, "unterminated Mermaid fence")

    def test_renderer_propagates_parser_failure_and_accepts_success(self) -> None:
        cli = self.write(
            '#!/bin/sh\ncase "$(cat "$2")" in *INVALID*) echo syntax-error >&2; exit 1;; esac\nexit 0\n',
            "mmdc",
        )
        cli.chmod(0o755)
        valid = mermaid.Block(self.write(""), 1, "flowchart LR\nA-->B\n")
        invalid = mermaid.Block(valid.path, 1, "INVALID\n")
        self.assertIsNone(mermaid.render(valid, cli))
        self.assertEqual(mermaid.render(invalid, cli), "syntax-error")

    def test_real_cli_accepts_valid_and_rejects_invalid_mermaid(self) -> None:
        cli = ROOT / "node_modules/.bin/mmdc"
        if not cli.is_file():
            self.skipTest("run npm ci to install the exact-pinned Mermaid CLI")
        source = self.write("")
        spaced = mermaid.extract(self.write("``` mermaid\nflowchart LR\nA-->B\n```\n"))[
            0
        ]
        self.assertIsNone(mermaid.render(spaced, cli))
        self.assertIsNotNone(
            mermaid.render(
                mermaid.Block(source, 1, "flowchart LR\nA -- definitely broken\n"), cli
            )
        )


class ReportTargetsStayNonBlocking(unittest.TestCase):
    def test_report_targets_are_not_reachable_from_make_all(self) -> None:
        source = (ROOT / "Makefile").read_text(encoding="utf-8")
        gates = leaf_gates(prerequisites(source))
        reports = {
            "editorial-report",
            "frontmatter-report",
            "sentence-report",
            "glossary-report",
            "structure-report",
            "vocabulary-report",
            "mermaid-report",
        }
        self.assertFalse(gates & reports)
        for target in reports:
            line = next(
                line for line in source.splitlines() if line.startswith(f"{target}:")
            )
            self.assertIn("not a gate", line)


class SupplyChainContract(unittest.TestCase):
    def test_mermaid_cli_is_exact_pinned_in_manifest_and_lockfile(self) -> None:
        import json

        manifest = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["devDependencies"]["@mermaid-js/mermaid-cli"], "11.17.0"
        )
        self.assertEqual(
            lock["packages"]["node_modules/@mermaid-js/mermaid-cli"]["version"],
            "11.17.0",
        )
        self.assertIn(
            "integrity",
            lock["packages"]["node_modules/@mermaid-js/mermaid-cli"],
        )

    def test_ci_uses_npm_ci_without_running_the_mermaid_report_as_a_gate(self) -> None:
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("run: npm ci", text)
        self.assertNotIn("make mermaid-report", text)


class WorkflowContract(unittest.TestCase):
    def test_external_link_workflow_contract(self) -> None:
        text = (ROOT / ".github/workflows/external-links.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("schedule:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("run: make links-external", text)
        for line in text.splitlines():
            if "uses:" in line:
                ref = line.split("@", 1)[1].split()[0]
                self.assertRegex(ref, r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
