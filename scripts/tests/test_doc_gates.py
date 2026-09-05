"""Each documentation gate must fail on a broken input, not merely pass on a clean tree.

Why this exists
---------------
`make all` printing "All checks passed" proves the validators ran. It does not
prove any of them can still detect the thing they were written to detect. A
regex narrowed during a refactor, a scan whose file discovery quietly stopped
reaching `notes/`, an exit code changed from 1 to 0 — each leaves the gate green
forever, and the repository's central discipline (evidence tiers, naming,
neutrality, cross-language parity) becomes unenforced without any signal.

So every test here breaks something on purpose, runs the real validator as a
subprocess, and asserts a non-zero exit. Two properties are checked together,
because either alone is misleading: the gate must reject the broken input, and
the tree must be clean again afterwards.

A silently-skipped file is a defect of the same family, so the probes use
ordinary filenames. Anything starting with `_` is treated as a template and is
not validated at all.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
import unittest
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE = "zz-gate-probe"

NOTE_HEADER = """\
---
title: gate probe
lifecycle: [optimize]
domains: [cost]
evidence: {evidence}
lang: {lang}
---
"""


def run_gate(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / script), *args],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=ROOT,
        check=False,
    )


@contextlib.contextmanager
def temp_files(files: dict[str, str]) -> Iterator[None]:
    """Write probe files, then remove them even when an assertion fails."""
    written: list[Path] = []
    try:
        for relative, content in files.items():
            path = ROOT / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            written.append(path)
        yield
    finally:
        for path in written:
            path.unlink(missing_ok=True)


class GateStillDetects(unittest.TestCase):
    def assert_rejected(
        self, result: subprocess.CompletedProcess[str], expect: str
    ) -> None:
        output = result.stdout + result.stderr
        self.assertNotEqual(
            result.returncode,
            0,
            f"the gate accepted a deliberately broken input:\n{output}",
        )
        self.assertIn(expect, output)

    def test_evidence_tier_requires_its_evidence(self) -> None:
        """`verified` without `verified_on` is the promotion that must not pass."""
        probe = {
            f"docs/ja/domains/cost/notes/{PROBE}.md": NOTE_HEADER.format(
                evidence="verified", lang="ja"
            )
            + "\n# gate probe\n"
        }
        with temp_files(probe):
            self.assert_rejected(run_gate("validate_frontmatter.py"), "verified_on")

    def test_verified_without_region_is_rejected(self) -> None:
        """A measurement whose environment is not named cannot be compared against."""
        body = (
            "---\n"
            "title: gate probe\n"
            "lifecycle: [optimize]\n"
            "domains: [cost]\n"
            "evidence: verified\n"
            "verified_on: 2026-01-01\n"
            "lang: ja\n"
            "---\n\n# gate probe\n"
        )
        with temp_files({f"docs/ja/domains/cost/notes/{PROBE}.md": body}):
            self.assert_rejected(run_gate("validate_frontmatter.py"), "region")

    def test_misspelled_frontmatter_key_is_rejected(self) -> None:
        """A typo leaves the value visible to a reader and invisible to every gate."""
        body = (
            "---\n"
            "title: gate probe\n"
            "lifecycle: [optimize]\n"
            "domains: [cost]\n"
            "evidence: verified\n"
            "verified_on: 2026-01-01\n"
            "regoin: ap-northeast-1\n"
            "lang: ja\n"
            "---\n\n# gate probe\n"
        )
        with temp_files({f"docs/ja/domains/cost/notes/{PROBE}.md": body}):
            self.assert_rejected(
                run_gate("validate_frontmatter.py"), "unknown frontmatter key"
            )

    def test_renaming_an_externally_cited_heading_is_rejected(self) -> None:
        """A renamed heading silently redirects an outside citation to the top of the page."""
        target = (
            ROOT
            / "docs/ja/domains/security-governance/notes/access-point-authorization-layers.md"
        )
        original = target.read_text(encoding="utf-8")
        first_h2 = next(line for line in original.split("\n") if line.startswith("## "))
        try:
            target.write_text(
                original.replace(first_h2, f"{first_h2} renamed", 1), encoding="utf-8"
            )
            self.assert_rejected(run_gate("check_anchor_contract.py"), "GONE")
        finally:
            target.write_text(original, encoding="utf-8")

    def test_table_literal_drift_between_languages_is_rejected(self) -> None:
        """A stale number in a translation keeps the heading fingerprint identical."""
        target = (
            ROOT
            / "docs/en/domains/security-governance/notes/access-point-authorization-layers.md"
        )
        original = target.read_text(encoding="utf-8")
        try:
            target.write_text(original.replace("24,861", "24,681", 1), encoding="utf-8")
            self.assert_rejected(run_gate("check_i18n_parity.py"), "24,681")
        finally:
            target.write_text(original, encoding="utf-8")

    def test_role_labeled_callout_is_rejected(self) -> None:
        """A job-title label implies a review that did not happen."""
        body = (
            NOTE_HEADER.format(evidence="hypothesis", lang="ja")
            + "\n# gate probe\n\n> **Application Security Engineer lens**: note.\n"
        )
        with temp_files({f"docs/ja/domains/cost/notes/{PROBE}.md": body}):
            self.assert_rejected(run_gate("audit_public_output.py"), "role-label")

    def test_forbidden_naming_is_rejected(self) -> None:
        body = (
            NOTE_HEADER.format(evidence="hypothesis", lang="ja")
            + "\n# gate probe\n\nFSxN の設定を確認する。\n"
        )
        with temp_files({f"docs/ja/domains/cost/notes/{PROBE}.md": body}):
            self.assert_rejected(run_gate("audit_public_output.py"), "naming")

    def test_vendor_versus_framing_is_rejected(self) -> None:
        body = (
            NOTE_HEADER.format(evidence="hypothesis", lang="ja")
            + "\n# gate probe\n\n競合ツールより優れている。\n"
        )
        with temp_files({f"docs/ja/domains/cost/notes/{PROBE}.md": body}):
            self.assert_rejected(run_gate("audit_public_output.py"), "neutrality")

    def test_cross_language_section_drift_is_rejected(self) -> None:
        """The failure translations introduce over time: one language gains a section.

        Invisible from the other side — an English reader cannot tell that the
        Japanese page grew two subsections last month.
        """
        ja = (
            NOTE_HEADER.format(evidence="hypothesis", lang="ja")
            + "\n# gate probe\n\n## one\n\nbody\n\n## two\n\nbody\n"
        )
        en = (
            NOTE_HEADER.format(evidence="hypothesis", lang="en")
            + "\n# gate probe\n\n## one\n\nbody\n"
        )
        probe = {
            f"docs/ja/domains/cost/notes/{PROBE}.md": ja,
            f"docs/en/domains/cost/notes/{PROBE}.md": en,
        }
        with temp_files(probe):
            self.assert_rejected(run_gate("check_i18n_parity.py"), PROBE)

    def test_broken_internal_link_is_rejected(self) -> None:
        body = (
            NOTE_HEADER.format(evidence="hypothesis", lang="ja")
            + "\n# gate probe\n\n[missing](./does-not-exist-anywhere.md)\n"
        )
        with temp_files({f"docs/ja/domains/cost/notes/{PROBE}.md": body}):
            self.assert_rejected(run_gate("check_links.py"), PROBE)

    def test_underscore_named_note_is_still_validated(self) -> None:
        """Scaffolding is where a file lives, not what it is called.

        `_template/` holds deliberate placeholders and is exempt. A note named
        `_draft.md` inside a real `notes/` directory is not scaffolding, and it
        used to be skipped silently — no tier checked, no message printed.
        """
        probe = {
            "docs/ja/domains/cost/notes/_zz-gate-probe.md": NOTE_HEADER.format(
                evidence="verified", lang="ja"
            )
            + "\n# gate probe\n"
        }
        with temp_files(probe):
            self.assert_rejected(run_gate("validate_frontmatter.py"), "verified_on")

    def test_template_directories_stay_exempt(self) -> None:
        """The narrowing above must not start failing on intentional placeholders."""
        self.assertEqual(run_gate("validate_frontmatter.py").returncode, 0)

    def test_hand_edited_language_switcher_is_rejected(self) -> None:
        """Switcher blocks are generated; a hand-edited one drifts from the tree."""
        block = (
            "<!-- lang-switcher:start -->\n"
            "🌐 [日本語](../../../ja/domains/cost/notes/zz-gate-probe.md) | [Klingon](../../../tlh/x.md)\n"
            "<!-- lang-switcher:end -->\n"
        )
        ja = NOTE_HEADER.format(evidence="hypothesis", lang="ja") + "\n# gate probe\n"
        en = (
            NOTE_HEADER.format(evidence="hypothesis", lang="en")
            + "\n# gate probe\n\n"
            + block
        )
        probe = {
            f"docs/ja/domains/cost/notes/{PROBE}.md": ja,
            f"docs/en/domains/cost/notes/{PROBE}.md": en,
        }
        with temp_files(probe):
            self.assert_rejected(run_gate("sync_lang_switcher.py"), PROBE)

    def test_unlabelled_link_into_japanese_prose_is_rejected(self) -> None:
        """An English reader must not reach Japanese prose without being told first.

        The rule is written in `docs/agent/localization.md` and was unenforced, so it held in module
        READMEs and drifted in body prose. A link that silently changes language is the failure the
        marker exists to prevent, so the gate has to reject one.
        """
        en = (
            NOTE_HEADER.format(evidence="hypothesis", lang="en")
            + "\n# gate probe\n\n"
            + "See [ACL preservation]"
            + "(../../../../ja/playbooks/03-migrate/notes/preserving-acls-during-migration.md).\n"
        )
        with temp_files({f"docs/en/domains/cost/notes/{PROBE}.md": en}):
            self.assert_rejected(run_gate("check_ja_only_markers.py"), PROBE)

    def test_unregistered_cross_repo_citation_is_rejected(self) -> None:
        """A citation nobody registered is the failure the gate exists to prevent.

        The offline half of `check_cross_repo.py` is what runs in `make all`, so
        it is the half that has to keep detecting. Registration is keyed on the
        citing file, and this probe cites a real sibling path from a file that
        has no row — which is exactly how a second document quietly starts
        depending on a claim nobody is watching.
        """
        body = (
            NOTE_HEADER.format(evidence="hypothesis", lang="ja")
            + "\n# gate probe\n\nSee "
            + "https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/"
            + "docs/ja/verification/perf-matrix-results.md for the measurement.\n"
        )
        with temp_files({f"docs/ja/domains/cost/notes/{PROBE}.md": body}):
            self.assert_rejected(run_gate("check_cross_repo.py"), PROBE)

    def test_cross_repo_table_shape_change_is_rejected(self) -> None:
        """The gate parses the index table, so a changed shape is a broken gate.

        Dropping a column would otherwise leave every row unparsed and the gate
        reporting zero problems over zero citations.
        """
        index = ROOT / "docs" / "ja" / "reference" / "cross-repo-index.md"
        original = index.read_text(encoding="utf-8")
        broken = original.replace(
            "| 引用元 | リポジトリ | パス | 確認する文字列 | 何を引いているか |",
            "| 引用元 | リポジトリ | パス | 確認する文字列 |",
            1,
        )
        self.assertNotEqual(broken, original, "the header row moved; update this test")
        try:
            index.write_text(broken, encoding="utf-8")
            self.assert_rejected(run_gate("check_cross_repo.py"), "5 columns")
        finally:
            index.write_text(original, encoding="utf-8")

    def test_tree_is_clean_after_the_probes(self) -> None:
        """A probe left behind would poison every later run of `make all`."""
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        ).stdout
        self.assertNotIn(PROBE, dirty, "a probe file survived cleanup")


if __name__ == "__main__":
    unittest.main()
