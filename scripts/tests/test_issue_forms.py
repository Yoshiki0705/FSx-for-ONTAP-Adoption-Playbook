"""Check that public issue forms remain distinct and collect safe evidence."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORMS_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"
EXPECTED = {
    "correction.yml": ("Accuracy correction", "[Accuracy correction]"),
    "knowledge-request.yml": ("New note proposal", "[New note]"),
    "translation-request.yml": ("Translation request", "[Translation]"),
    "cross-repo-finding.yml": ("Cross-repository finding", "[cross-repo]"),
}
BLOCK = re.compile(r"(?ms)^  - type: (?P<type>[^\n]+)\n(?P<body>.*?)(?=^  - type: |\Z)")


def widget(content: str, widget_id: str) -> str:
    """Return one complete issue-form widget, bounded by the next widget."""
    for match in BLOCK.finditer(content):
        block = match.group(0)
        if re.search(rf"(?m)^    id: {re.escape(widget_id)}$", block):
            return block
    raise AssertionError(f"widget {widget_id!r} not found")


def validation_is_required(block: str) -> bool:
    return bool(re.search(r"(?m)^    validations:\n      required: true$", block))


class IssueFormTests(unittest.TestCase):
    def setUp(self) -> None:
        self.forms = {
            name: (FORMS_DIR / name).read_text(encoding="utf-8") for name in EXPECTED
        }

    def test_request_types_are_unique(self) -> None:
        names = []
        prefixes = []
        for filename, (expected_name, expected_prefix) in EXPECTED.items():
            content = self.forms[filename]
            self.assertRegex(content, rf"(?m)^name: {re.escape(expected_name)}$")
            self.assertIn(f'title: "{expected_prefix} ', content)
            names.append(expected_name)
            prefixes.append(expected_prefix)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(prefixes), len(set(prefixes)))

    def test_widget_ids_are_unique_and_dropdowns_have_options(self) -> None:
        for filename, content in self.forms.items():
            with self.subTest(filename=filename):
                ids = re.findall(r"(?m)^    id: ([a-z][a-z0-9_]*)$", content)
                self.assertTrue(ids)
                self.assertEqual(len(ids), len(set(ids)))
                dropdowns = content.split("  - type: dropdown")[1:]
                for dropdown in dropdowns:
                    self.assertRegex(dropdown, r"(?m)^      options:$")
                    self.assertRegex(dropdown, r"(?m)^        - .+$")

    def test_every_form_requires_public_data_confirmation(self) -> None:
        for filename, content in self.forms.items():
            with self.subTest(filename=filename):
                self.assertIn("private case data", content.lower())
                safety = widget(content, "safety")
                self.assertRegex(safety, r"(?m)^          required: true$")

    def test_forms_do_not_overlap(self) -> None:
        correction = self.forms["correction.yml"]
        proposal = self.forms["knowledge-request.yml"]
        translation = self.forms["translation-request.yml"]
        self.assertNotIn("Translation diverges", correction)
        self.assertNotIn("source_language", correction)
        self.assertIn("Question the note should answer", proposal)
        self.assertNotIn("Accuracy problem", proposal)
        self.assertIn("Japanese is the authoritative source language", translation)
        self.assertNotIn("id: source_language", translation)
        target = widget(translation, "target_language")
        self.assertNotRegex(target, r"(?m)^        - ja$")
        self.assertIn("        - en", target)
        self.assertNotIn("Lifecycle phase", translation)

    def test_accuracy_and_cross_repo_forms_require_evidence(self) -> None:
        correction_evidence = widget(self.forms["correction.yml"], "evidence")
        cross_repo_conditions = widget(
            self.forms["cross-repo-finding.yml"], "conditions"
        )
        cross_repo_tier = widget(self.forms["cross-repo-finding.yml"], "tier")
        self.assertIn("Primary source or reproducible evidence", correction_evidence)
        for block in (correction_evidence, cross_repo_conditions, cross_repo_tier):
            self.assertTrue(validation_is_required(block), block)

    def test_required_check_is_bounded_to_one_widget(self) -> None:
        evidence = widget(self.forms["correction.yml"], "evidence")
        made_optional = evidence.replace("required: true", "required: false", 1)
        self.assertFalse(validation_is_required(made_optional))
        self.assertIn("required: true", self.forms["correction.yml"])


if __name__ == "__main__":
    unittest.main()
