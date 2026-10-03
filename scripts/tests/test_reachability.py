"""The reachability benchmark, as a truth table, and proof that the gate can fail.

`tools/check_reachability.py` answers a question no other gate asks: does a question an agent is
given lead from `llms.txt` to the document that answers it, within the hop budget. A gate that
answers "yes" for everything is worse than none, because it is then credited with a property it
never checked. So the first class below runs the tool as a subprocess against a tree where one
answer is deliberately unreachable and asserts on what it printed, not only on its exit status, with
a reachable control in the same tree so the failure cannot come from an unrelated cause.

Every fixture is built in a temporary directory. A tracked fixture `.md` would be read by
markdownlint, the link checker and the audit, and a deliberately orphaned one would trip them.
Nothing here touches the network: external verdicts are driven by an injected opener.
"""

from __future__ import annotations

import contextlib
import functools
import inspect
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Self
from unittest import mock

from scripts.tests.gitenv import scrubbed_env

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check_reachability as cr
from check_links import anchors_of

TOOL = ROOT / "tools" / "check_reachability.py"
SIB = f"{cr.OWNER}/Sib"


def question(qid: str, *targets: str, scope: str = "hub", **extra: object) -> dict:
    category = {"wl": "workload", "tr": "tr", "sm": "spoke-measurement"}[
        qid.split("-", 1)[0]
    ]
    return {
        "id": qid,
        "question": f"Where is the answer for {qid}?",
        "keywords": [{"en": ["answer", "reply"], "ja": ["回答", "答え"]}],
        "category": category,
        "scope": scope,
        "targets": [{"path": t} for t in targets],
        "rationale": "fixture",
        **extra,
    }


def keywords(en: list[str], ja: list[str] | None = None) -> list[dict]:
    """One keyword group: a question with a single subject."""
    return [{"en": en, "ja": ja or ["回答", "答え"]}]


def groups(*pairs: tuple[list[str], list[str]]) -> list[dict]:
    """Several keyword groups: a hop must name one word from each."""
    return [{"en": en, "ja": ja} for en, ja in pairs]


class Tree:
    """A throwaway repository root with the given files and a question set."""

    def __init__(self, files: dict[str, str], questions: list[dict]) -> None:
        self.files = files
        self.questions = questions

    def __enter__(self) -> Self:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        for name, body in self.files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        self.qfile = self.root / "q.json"
        self.qfile.write_text(
            json.dumps({"schema": cr.SCHEMA, "questions": self.questions}),
            encoding="utf-8",
        )
        return self

    def __exit__(self, *exc: object) -> None:
        self._tmp.cleanup()

    def load(self) -> list[dict]:
        return cr.load_questions(self.qfile, self.root)

    def evaluate(self, **kwargs: object) -> dict[str, dict]:
        result = cr.evaluate(self.load(), self.root, **kwargs)  # type: ignore[arg-type]
        return {r["id"]: r for r in result.results}


CHAIN = {
    "llms.txt": "[a](a.md)\n",
    "a.md": "[b](b.md)\n",
    "b.md": "[c](c.md)\n",
    "c.md": "[d](d.md)\n",
    "d.md": "end\n",
    "orphan.md": "nothing links here\n",
}


class TheGateCanFail(unittest.TestCase):
    def test_an_unreachable_question_fails_the_gate(self) -> None:
        """Run as `make reachability` would, and read what it said, not only how it exited."""
        questions = [
            question("wl-reachable-control", "b.md"),
            question("wl-deliberately-unreachable", "orphan.md"),
        ]
        with Tree(CHAIN, questions) as tree:
            run = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--root",
                    str(tree.root),
                    "--questions",
                    str(tree.qfile),
                ],
                env=scrubbed_env(),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertRegex(
            run.stdout, r"(?m)^FAIL  wl-deliberately-unreachable  hops=none  "
        )
        self.assertRegex(run.stdout, r"(?m)^PASS  wl-reachable-control  hops=2  ")
        summary = run.stdout.strip().splitlines()[-1]
        self.assertIn("1 pass, 1 fail, 0 inconclusive", summary)
        self.assertIn(f"budget <={cr.MAX_HOPS} hop(s), mode hub", summary)

    def test_the_selftest_reports_its_cases(self) -> None:
        run = subprocess.run(
            [sys.executable, str(TOOL), "--selftest"],
            env=scrubbed_env(),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertRegex(run.stdout, r"^selftest: \d+ case\(s\) passed")


def _map_rows(path: Path, header: str) -> list[str]:
    """The first Read-first link of every row in every workload table of an entry map."""
    rows: list[str] = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"| {header} |"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            in_table = False
            continue
        if set(line.replace("|", "").strip()) <= {"-", " "}:
            continue
        read_first = line.split("|")[2]
        match = re.search(r"\]\(([^)\s]+)\)", read_first)
        if match:
            rows.append(match.group(1))
    return rows


class EveryHubTargetExists(unittest.TestCase):
    """A target that does not exist cannot be reached, and a question about it measures nothing."""

    def setUp(self) -> None:
        self.questions = cr.load_questions(cr.QUESTIONS, ROOT)

    def test_every_hub_target_is_a_file_and_its_anchor_exists(self) -> None:
        for q in self.questions:
            if q["scope"] != "hub":
                continue
            for target in q["targets"]:
                with self.subTest(question=q["id"], target=target["path"]):
                    path = ROOT / target["path"]
                    self.assertTrue(path.is_file(), f"{target['path']} does not exist")
                    if "anchor" in target:
                        self.assertIn(target["anchor"], anchors_of(path))

    def test_every_workload_map_row_is_covered_by_a_workload_question(self) -> None:
        """Derived from the maps on disk, so a row added later without a question fails here."""
        covered = {
            t["path"]
            for q in self.questions
            if q["category"] == "workload"
            for t in q["targets"]
        }
        for rel, header in (
            ("docs/en/reference/workload-entry-map.md", "Workload"),
            ("docs/ja/reference/workload-entry-map.md", "ワークロード"),
        ):
            links = _map_rows(ROOT / rel, header)
            with self.subTest(map=rel):
                self.assertGreater(len(links), 0, f"no workload rows parsed from {rel}")
            for link in links:
                nodes = cr.normalize_link(rel, link, ROOT)
                with self.subTest(map=rel, link=link):
                    self.assertEqual(len(nodes), 1, f"{link} does not resolve")
                    self.assertIn(nodes[0], covered)


class TheSchemaIsEnforced(unittest.TestCase):
    def _rejects(self, questions: list[dict], *, schema: str = cr.SCHEMA) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "llms.txt").write_text("x\n", encoding="utf-8")
            path = root / "q.json"
            path.write_text(
                json.dumps({"schema": schema, "questions": questions}), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                cr.load_questions(path, root)

    def test_the_real_question_set_loads(self) -> None:
        questions = cr.load_questions(cr.QUESTIONS, ROOT)
        self.assertGreater(len(questions), 0)

    def test_each_rule_rejects_its_violation(self) -> None:
        ok = question("wl-ok", "docs/a.md")
        cases = {
            "unknown question key": [question("wl-x", "a.md", extra_key=1)],
            "duplicate id": [ok, dict(ok)],
            "bad category": [{**ok, "category": "other"}],
            "spoke-measurement in hub scope": [question("sm-x", "a.md", scope="hub")],
            "hub target with a colon": [question("wl-x", f"{SIB}:a.md")],
            "cross-repo target without owner": [
                question("sm-x", "Sib:docs/a.md", scope="cross-repo")
            ],
            "README as target": [question("wl-x", "docs/README.md")],
            "llms.txt as target": [question("wl-x", "llms.txt")],
            "entry map as target": [
                question("wl-x", "docs/en/reference/workload-entry-map.md")
            ],
            "sibling README as target": [
                question("sm-x", f"{SIB}:README.md", scope="cross-repo")
            ],
            "no targets": [{**ok, "targets": []}],
            "too many targets": [
                question("wl-x", *[f"t{i}.md" for i in range(cr.MAX_TARGETS + 1)])
            ],
            "id prefix disagrees with category": [{**ok, "category": "tr"}],
            "unknown target key": [{**ok, "targets": [{"path": "a.md", "x": 1}]}],
            "missing entry point": [{**ok, "entry_points": ["absent.md"]}],
            "missing rationale": [{k: v for k, v in ok.items() if k != "rationale"}],
            "missing keywords": [{k: v for k, v in ok.items() if k != "keywords"}],
            "empty en keywords": [{**ok, "keywords": keywords([])}],
            "ja keywords with only ASCII": [
                {**ok, "keywords": keywords(["answer", "reply"], ["TR", "NFS"])}
            ],
            "keyword duplicated up to case": [
                {**ok, "keywords": keywords(["Cache", "cache"])}
            ],
            "one-character ASCII keyword": [
                {**ok, "keywords": keywords(["a", "answer"])}
            ],
            "unknown key in a keyword group": [
                {
                    **ok,
                    "keywords": [
                        {**keywords(["answer", "reply"])[0], "fr": ["réponse"]}
                    ],
                }
            ],
            "keywords as a v2 object rather than groups": [
                {**ok, "keywords": {"en": ["answer", "reply"], "ja": ["回答", "答え"]}}
            ],
            "keywords as bare words": [{**ok, "keywords": ["answer", "reply"]}],
            "no keyword groups": [{**ok, "keywords": []}],
            "too many keyword groups": [
                {
                    **ok,
                    "keywords": groups(
                        *[
                            ([f"en{i}"], [f"語{i}"])
                            for i in range(cr.KEYWORD_GROUPS[1] + 1)
                        ]
                    ),
                }
            ],
            "a group without Japanese": [
                {
                    **ok,
                    "keywords": groups((["answer"], ["回答"]), (["reply"], [])),
                }
            ],
            "one keyword in two groups": [
                {
                    **ok,
                    "keywords": groups(
                        (["answer", "reply"], ["回答"]), (["Reply"], ["答え"])
                    ),
                }
            ],
        }
        for name, questions in cases.items():
            with self.subTest(name):
                self._rejects(questions)
        with self.subTest("wrong schema"):
            self._rejects([ok], schema="reachability-questions/v0")
        with self.subTest("a v1 file, which has no keywords"):
            self._rejects(
                [{k: v for k, v in ok.items() if k != "keywords"}],
                schema="reachability-questions/v1",
            )
        with self.subTest("a v2 file, whose keywords are one ungrouped union"):
            self._rejects(
                [
                    {
                        **ok,
                        "keywords": {"en": ["answer", "reply"], "ja": ["回答", "答え"]},
                    }
                ],
                schema="reachability-questions/v2",
            )


class HopsAreCountedCorrectly(unittest.TestCase):
    def test_a_link_from_llms_txt_is_one_hop(self) -> None:
        with Tree(CHAIN, [question("wl-a", "a.md")]) as tree:
            self.assertEqual(tree.evaluate()["wl-a"]["hops"], 1)

    def test_a_target_within_budget_passes(self) -> None:
        with Tree(CHAIN, [question("wl-c", "c.md")]) as tree:
            r = tree.evaluate()["wl-c"]
        self.assertEqual((r["verdict"], r["hops"]), ("PASS", cr.MAX_HOPS))
        self.assertEqual(r["path"], ["llms.txt", "a.md", "b.md", "c.md"])

    def test_beyond_budget_reports_the_true_distance(self) -> None:
        with Tree(CHAIN, [question("wl-d", "d.md")]) as tree:
            r = tree.evaluate()["wl-d"]
        self.assertEqual((r["verdict"], r["hops"]), ("FAIL", cr.MAX_HOPS + 1))

    def test_an_unreachable_target_fails_with_no_hop_count(self) -> None:
        with Tree(CHAIN, [question("wl-o", "orphan.md")]) as tree:
            r = tree.evaluate()["wl-o"]
        self.assertEqual((r["verdict"], r["hops"]), ("FAIL", None))

    def test_the_nearest_enclosing_readme_is_reported_for_an_orphan(self) -> None:
        files = {
            "llms.txt": "[m](docs/m/README.md)\n",
            "docs/m/README.md": "module\n",
            "docs/m/notes/x.md": "orphan\n",
        }
        with Tree(files, [question("wl-x", "docs/m/notes/x.md")]) as tree:
            r = tree.evaluate()["wl-x"]
        self.assertEqual(r["nearest"], {"node": "docs/m/README.md", "hops": 1})

    def test_several_entry_points_take_the_minimum(self) -> None:
        q = question("wl-d", "d.md", entry_points=["llms.txt", "c.md"])
        with Tree(CHAIN, [q]) as tree:
            r = tree.evaluate()["wl-d"]
        self.assertEqual((r["verdict"], r["hops"]), ("PASS", 1))

    def test_fragments_do_not_change_the_node_and_anchors_are_checked(self) -> None:
        files = {
            "llms.txt": "[a](a.md#nowhere)\n",
            "a.md": "## Real heading\n",
        }
        good = {
            **question("wl-good", "a.md"),
            "targets": [{"path": "a.md", "anchor": "real-heading"}],
        }
        bad = {
            **question("wl-bad", "a.md"),
            "targets": [{"path": "a.md", "anchor": "missing"}],
        }
        with Tree(files, [good, bad]) as tree:
            graph = cr.build_hub_graph(tree.root)
            results = tree.evaluate()
        self.assertEqual(graph["llms.txt"], {"a.md"})
        self.assertEqual(results["wl-good"]["verdict"], "PASS")
        self.assertEqual(results["wl-bad"]["verdict"], "FAIL")

    def test_directory_links_and_fences(self) -> None:
        files = {
            "llms.txt": "[d](dir)\n[d2](dir/)\n```text\n[f](f.md)\n```\n![img](f.md)\n",
            "dir/README.md": "x\n",
            "f.md": "x\n",
        }
        with Tree(files, []) as tree:
            graph = cr.build_hub_graph(tree.root)
        # Both directory forms land on the README; the fenced link and the image embed are not
        # edges, so f.md is absent.
        self.assertEqual(graph["llms.txt"], {"dir/README.md"})

    def test_urls_normalize_to_the_expected_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "docs").mkdir()
            (root / "docs/x.md").write_text("x\n", encoding="utf-8")
            (root / "README.md").write_text("x\n", encoding="utf-8")
            (root / "llms.txt").write_text("x\n", encoding="utf-8")
            own = f"https://github.com/{cr.OWNER}/{cr.THIS_REPO}"
            cases = {
                f"{own}/blob/main/docs/x.md#frag": ["docs/x.md"],
                f"{own.lower()}/blob/main/docs/x.md": ["docs/x.md"],
                f"{own}": ["README.md", "llms.txt"],
                f"https://github.com/{cr.OWNER}/Sib/blob/main/docs/a.md": [
                    f"{SIB}:docs/a.md"
                ],
                f"https://github.com/{cr.OWNER}/Sib/tree/main/patterns/p": [
                    f"{SIB}:patterns/p/README.md"
                ],
                f"https://raw.githubusercontent.com/{cr.OWNER}/Sib/main/docs/a.md": [
                    f"{SIB}:docs/a.md"
                ],
                f"https://github.com/{cr.OWNER}/Sib": [
                    f"{SIB}:README.md",
                    f"{SIB}:llms.txt",
                ],
                f"https://github.com/{cr.OWNER}/Sib/issues/1": [],
                "https://example.com/docs/a.md": [],
                "mailto:someone@example.com": [],
            }
            for url, expected in cases.items():
                with self.subTest(url=url):
                    self.assertEqual(cr.normalize_link("llms.txt", url, root), expected)
            with self.subTest("relative link inside a sibling document"):
                self.assertEqual(
                    cr.normalize_link(f"{SIB}:docs/ja/a.md", "../en/b.md#x", root),
                    [f"{SIB}:docs/en/b.md"],
                )
                self.assertEqual(
                    cr.normalize_link(f"{SIB}:docs/a.md", "../../../out.md", root), []
                )

    def test_the_budget_is_the_constant_and_the_flag_overrides_it(self) -> None:
        self.assertEqual(
            inspect.signature(cr.evaluate).parameters["max_hops"].default, cr.MAX_HOPS
        )
        with Tree(CHAIN, [question("wl-b", "b.md")]) as tree:
            argv = ["--root", str(tree.root), "--questions", str(tree.qfile)]
            for extra, expected_exit, verdict in (
                ([], 0, "PASS"),
                (["--max-hops", "1"], 1, "FAIL"),
            ):
                out = io.StringIO()
                with self.subTest(extra=extra), contextlib.redirect_stdout(out):
                    status = cr.main(argv + extra)
                self.assertEqual(status, expected_exit, out.getvalue())
                self.assertIn(f"{verdict}  wl-b  hops=2", out.getvalue())
            self.assertIn(f"budget <={cr.MAX_HOPS} hop(s)", self._run(argv))

    @staticmethod
    def _run(argv: list[str]) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cr.main(argv)
        return out.getvalue()


class _Response:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")
        self.status = 200

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class Opener:
    """A fake `urlopen`: a body per path, or an exception, with a log of what was requested."""

    def __init__(
        self,
        bodies: dict[str, str],
        error: BaseException | None = None,
        errors: dict[str, BaseException] | None = None,
    ):
        self.bodies = bodies
        self.error = error
        self.errors = errors or {}
        self.calls: list[str] = []

    def __call__(
        self, request: urllib.request.Request, timeout: float = 0
    ) -> _Response:
        url = request.full_url
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        # Any ref: a link carries its own, and a repository root is fetched at HEAD.
        path = re.sub(r"^.*?/Sib/[^/]+/", "", url)
        if path in self.errors:
            raise self.errors[path]
        if path in self.bodies:
            return _Response(self.bodies[path])
        raise urllib.error.HTTPError(url, 404, "not found", None, None)  # type: ignore[arg-type]


EXT_FILES = {
    "llms.txt": f"[s](https://github.com/{cr.OWNER}/Sib/blob/main/docs/x.md)\n",
}
EXT_Q = question("sm-y", f"{SIB}:docs/y.md", scope="cross-repo")

# Two crawls in one run. other.md's crawl opens x.md and z1.md (the BFS visits node ids in sorted
# order), then the cap skips z2.md. The llms.txt crawl needs only x.md, already fetched and cached,
# so it is complete even though the run reached the cap.
CAP_FILES = {
    **EXT_FILES,
    "other.md": "".join(
        f"[{n}](https://github.com/{cr.OWNER}/Sib/blob/main/docs/{n}.md)\n"
        for n in ("x", "z1", "z2")
    ),
}
CAP_BODIES = {"docs/x.md": "no links\n", "docs/z1.md": "z\n", "docs/z2.md": "z\n"}
CAP_OTHER = question(
    "sm-other", f"{SIB}:docs/t.md", scope="cross-repo", entry_points=["other.md"]
)


class ExternalVerdicts(unittest.TestCase):
    def test_a_fetched_link_to_the_target_passes(self) -> None:
        opener = Opener({"docs/x.md": "[y](y.md)\n", "docs/y.md": "answer\n"})
        with Tree(EXT_FILES, [EXT_Q]) as tree:
            r = tree.evaluate(external=True, opener=opener)["sm-y"]
        self.assertEqual((r["verdict"], r["hops"]), ("PASS", 2))

    def test_a_target_that_answers_404_is_not_reached(self) -> None:
        """Reaching a link is not reaching a document: the target itself must exist."""
        opener = Opener({"docs/x.md": "[y](y.md)\n"})
        with Tree(EXT_FILES, [EXT_Q]) as tree:
            result = cr.evaluate(tree.load(), tree.root, external=True, opener=opener)
        self.assertEqual(result.results[0]["verdict"], "FAIL")
        self.assertIn(f"{SIB}:docs/y.md", result.fetch["dead_nodes"])

    def test_offline_mode_skips_cross_repo_and_fetches_nothing(self) -> None:
        opener = Opener({"docs/x.md": "[y](y.md)\n"})
        with Tree(EXT_FILES, [EXT_Q]) as tree:
            result = cr.evaluate(tree.load(), tree.root, opener=opener)
        self.assertEqual(result.counts["skipped"], 1)
        self.assertEqual(result.results, [])
        self.assertEqual(opener.calls, [])

    def test_a_404_is_a_dead_end_and_fails(self) -> None:
        opener = Opener({})
        with Tree(EXT_FILES, [EXT_Q]) as tree:
            result = cr.evaluate(tree.load(), tree.root, external=True, opener=opener)
        self.assertEqual(result.results[0]["verdict"], "FAIL")
        self.assertEqual(result.fetch["dead_nodes"], [f"{SIB}:docs/x.md"])

    def test_a_404_on_a_guessed_node_is_not_a_dead_link(self) -> None:
        files = {"llms.txt": f"[s](https://github.com/{cr.OWNER}/Sib)\n"}
        opener = Opener({"README.md": "[y](docs/y.md)\n", "docs/y.md": "answer\n"})
        with Tree(files, [EXT_Q]) as tree:
            result = cr.evaluate(tree.load(), tree.root, external=True, opener=opener)
        self.assertEqual(result.results[0]["verdict"], "PASS")
        self.assertEqual(result.fetch["dead_nodes"], [])

    def test_an_unanswered_fetch_is_inconclusive_not_fail(self) -> None:
        errors = {
            "403": urllib.error.HTTPError("u", 403, "forbidden", None, None),  # type: ignore[arg-type]
            "429": urllib.error.HTTPError("u", 429, "rate", None, None),  # type: ignore[arg-type]
            "503": urllib.error.HTTPError("u", 503, "down", None, None),  # type: ignore[arg-type]
            "URLError": urllib.error.URLError("no route"),
            "TimeoutError": TimeoutError("slow"),
        }
        for name, error in errors.items():
            opener = Opener({}, error)
            with self.subTest(name), Tree(EXT_FILES, [EXT_Q]) as tree:
                out = io.StringIO()
                patched = functools.partial(cr.evaluate, opener=opener)
                with (
                    mock.patch.object(cr, "evaluate", patched),
                    contextlib.redirect_stdout(out),
                ):
                    status = cr.main(
                        [
                            "--root",
                            str(tree.root),
                            "--questions",
                            str(tree.qfile),
                            "--external",
                        ]
                    )
                text = out.getvalue()
                self.assertEqual(status, 0, text)
                self.assertRegex(text, r"(?m)^\? INCONCLUSIVE  sm-y  ")
                self.assertIn("undetermined:", text)
                self.assertRegex(text, r"(?m)^  \? sm-y: ")
                self.assertIn("0 fail, 1 inconclusive", text)

    def test_the_fetch_cap_makes_an_unreached_target_inconclusive(self) -> None:
        opener = Opener({"docs/x.md": "[z](z.md)\n", "docs/z.md": "[y](y.md)\n"})
        with (
            mock.patch.object(cr, "MAX_FETCHES", 1),
            Tree(EXT_FILES, [EXT_Q]) as tree,
        ):
            result = cr.evaluate(tree.load(), tree.root, external=True, opener=opener)
        self.assertEqual(result.results[0]["verdict"], "INCONCLUSIVE")
        self.assertTrue(result.fetch["cap_reached"])
        self.assertEqual(result.fetch["attempted"], 1)

    @staticmethod
    def _capped() -> cr.Result:
        with (
            mock.patch.object(cr, "MAX_FETCHES", 2),
            Tree(CAP_FILES, [CAP_OTHER, EXT_Q]) as tree,
        ):
            return cr.evaluate(
                tree.load(), tree.root, external=True, opener=Opener(CAP_BODIES)
            )

    def test_a_cap_hit_on_another_crawl_does_not_mask_a_failure(self) -> None:
        """The cap was reached, but not where this question's link could be: FAIL, exit 1."""
        result = self._capped()
        self.assertTrue(result.fetch["cap_reached"])
        r = {r["id"]: r for r in result.results}["sm-y"]
        self.assertEqual((r["verdict"], r["hops"]), ("FAIL", None))
        self.assertEqual(result.counts["fail"], 1)

    def test_a_cap_skipped_node_in_the_own_crawl_is_inconclusive(self) -> None:
        result = self._capped()
        r = {r["id"]: r for r in result.results}["sm-other"]
        self.assertEqual(r["verdict"], "INCONCLUSIVE")
        self.assertIn(f"{SIB}:docs/z2.md (skipped by the fetch cap)", r["reason"])

    def test_a_target_linked_at_the_budget_that_answers_404_fails(self) -> None:
        """y.md is linked at exactly the budget, so the crawl never opens it; existence must."""
        opener = Opener({"docs/x.md": "[z](z.md)\n", "docs/z.md": "[y](y.md)\n"})
        with Tree(EXT_FILES, [EXT_Q]) as tree:
            r = tree.evaluate(external=True, opener=opener)["sm-y"]
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("link leads to a 404", r["reason"])
        self.assertTrue(opener.calls[-1].endswith("/docs/y.md"))

    def test_a_target_linked_at_the_budget_that_exists_passes(self) -> None:
        opener = Opener(
            {"docs/x.md": "[z](z.md)\n", "docs/z.md": "[y](y.md)\n", "docs/y.md": "y\n"}
        )
        with Tree(EXT_FILES, [EXT_Q]) as tree:
            r = tree.evaluate(external=True, opener=opener)["sm-y"]
        self.assertEqual((r["verdict"], r["hops"]), ("PASS", cr.MAX_HOPS))

    def test_an_unanswered_existence_fetch_at_the_budget_is_inconclusive(self) -> None:
        opener = Opener(
            {"docs/x.md": "[z](z.md)\n", "docs/z.md": "[y](y.md)\n"},
            errors={"docs/y.md": urllib.error.HTTPError("u", 503, "down", None, None)},  # type: ignore[arg-type]
        )
        with Tree(EXT_FILES, [EXT_Q]) as tree:
            r = tree.evaluate(external=True, opener=opener)["sm-y"]
        self.assertEqual(r["verdict"], "INCONCLUSIVE")
        self.assertIn("existence not determined (HTTP 503)", r["reason"])

    def test_the_fetch_cap_flag_overrides_the_constant(self) -> None:
        opener = Opener({"docs/x.md": "[z](z.md)\n", "docs/z.md": "[y](y.md)\n"})
        with Tree(EXT_FILES, [EXT_Q]) as tree:
            report = tree.root / "r.json"
            out = io.StringIO()
            patched = functools.partial(cr.evaluate, opener=opener)
            with (
                mock.patch.object(cr, "evaluate", patched),
                contextlib.redirect_stdout(out),
            ):
                cr.main(
                    [
                        "--root",
                        str(tree.root),
                        "--questions",
                        str(tree.qfile),
                        "--external",
                        "--max-fetches",
                        "1",
                        "--report",
                        str(report),
                    ]
                )
            data = json.loads(report.read_text(encoding="utf-8"))
        self.assertIn("fetch: 1 attempted (cap 1, cap reached)", out.getvalue())
        self.assertEqual(data["max_fetches"], 1)
        self.assertTrue(data["fetch"]["cap_reached"])

    def test_a_sibling_node_at_the_budget_is_never_fetched(self) -> None:
        opener = Opener(
            {
                "docs/x.md": "[z](z.md)\n",
                "docs/z.md": "[w](w.md)\n",
                "docs/w.md": "[y](y.md)\n",
            }
        )
        with Tree(EXT_FILES, [EXT_Q]) as tree:
            r = tree.evaluate(external=True, opener=opener)["sm-y"]
        fetched = [url.rsplit("/", 1)[1] for url in opener.calls]
        self.assertEqual(fetched, ["x.md", "z.md"])
        self.assertEqual((r["verdict"], r["hops"]), ("FAIL", None))

    def test_fetches_are_cached_for_the_run(self) -> None:
        q2 = question("sm-z", f"{SIB}:docs/z.md", scope="cross-repo")
        opener = Opener(
            {
                "docs/x.md": "[y](y.md) [z](z.md)\n",
                "docs/y.md": "a\n",
                "docs/z.md": "b\n",
            }
        )
        with Tree(EXT_FILES, [EXT_Q, q2]) as tree:
            result = cr.evaluate(tree.load(), tree.root, external=True, opener=opener)
        self.assertEqual([r["verdict"] for r in result.results], ["PASS", "PASS"])
        self.assertEqual(len(opener.calls), len(set(opener.calls)))


def _main(argv: list[str], opener: Opener | None = None) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.ExitStack() as stack:
        if opener is not None:
            patched = functools.partial(cr.evaluate, opener=opener)
            stack.enter_context(mock.patch.object(cr, "evaluate", patched))
        stack.enter_context(contextlib.redirect_stdout(out))
        status = cr.main(argv)
    return status, out.getvalue()


FLEXCACHE = keywords(["FlexCache", "cache"], ["キャッシュ", "整合性"])


class SignpostsAreRequiredOnEveryHop(unittest.TestCase):
    """A linked path proves a route exists; a signposted path proves every hop names the subject.

    The linked verdict passed at hop 1 for every Hub question, because llms.txt links almost
    everything, so it could not show a navigation change improving anything. These cases pin the
    second verdict: what text counts as attached to a link, how keywords match, and that the
    external INCONCLUSIVE rule still asks only about the question's own crawl.
    """

    def test_a_signposted_hop_via_the_llms_txt_description_passes(self) -> None:
        files = {
            "llms.txt": "- [Note](a.md): how FlexCache stays consistent\n",
            "a.md": "answer\n",
        }
        with Tree(files, [question("wl-a", "a.md", keywords=FLEXCACHE)]) as tree:
            r = tree.evaluate()["wl-a"]
        self.assertEqual((r["verdict"], r["hops"]), ("PASS", 1))
        s = r["signposted"]
        self.assertEqual((s["verdict"], s["hops"]), ("PASS", 1))
        self.assertEqual(s["path"], ["llms.txt", "a.md"])
        self.assertIsNone(s["missing"])

    def test_a_signposted_hop_via_table_row_text_passes(self) -> None:
        """The row names the subject, not the link text; the neighboring row does not count."""
        files = {
            "llms.txt": "- [Index](idx.md): cache index\n",
            "idx.md": (
                "| Topic | Read |\n|---|---|\n"
                "| FlexCache consistency | [read](a.md) |\n"
                "| Volume sizing | [read](b.md) |\n"
            ),
            "a.md": "x\n",
            "b.md": "x\n",
        }
        questions = [
            question("wl-row", "a.md", keywords=FLEXCACHE),
            question("wl-other-row", "b.md", keywords=FLEXCACHE),
        ]
        with Tree(files, questions) as tree:
            results = tree.evaluate()
        s = results["wl-row"]["signposted"]
        self.assertEqual((s["verdict"], s["hops"]), ("PASS", 2))
        self.assertEqual(s["path"], ["llms.txt", "idx.md", "a.md"])
        control = results["wl-other-row"]
        self.assertEqual(control["verdict"], "PASS")
        self.assertEqual(control["signposted"]["verdict"], "FAIL")
        self.assertEqual(control["signposted"]["missing"]["hop"], 2)

    def test_a_linked_hop_without_keywords_fails_signposted(self) -> None:
        files = {
            "llms.txt": "- [Docs](idx.md): everything\n",
            "idx.md": "FlexCache is covered below.\n\n[x](a.md)\n",
            "a.md": "x\n",
        }
        with Tree(files, [question("wl-a", "a.md", keywords=FLEXCACHE)]) as tree:
            r = tree.evaluate()["wl-a"]
            argv = ["--root", str(tree.root), "--questions", str(tree.qfile)]
            plain_status, plain_out = _main(argv)
            gated_status, gated_out = _main([*argv, "--signposted"])
        self.assertEqual((r["verdict"], r["hops"]), ("PASS", 2))
        s = r["signposted"]
        self.assertEqual((s["verdict"], s["hops"]), ("FAIL", None))
        missing = s["missing"]
        self.assertEqual(
            (missing["hop"], missing["from"], missing["to"]), (1, "llms.txt", "idx.md")
        )
        self.assertIn("everything", missing["excerpt"])
        self.assertEqual(plain_status, 0, plain_out)
        self.assertEqual(gated_status, 1, gated_out)
        self.assertRegex(
            gated_out,
            r"(?m)^  signposted FAIL  hops=none  missing at hop 1: llms\.txt -> idx\.md$",
        )
        self.assertRegex(gated_out, r"(?m)^signposted: 0 pass, 1 fail, 0 inconclusive")
        self.assertIn("1 pass, 0 fail", gated_out.strip().splitlines()[-1])

    def test_japanese_keywords_match_as_substrings(self) -> None:
        small = keywords(
            ["small files", "file count"], ["小さなファイル", "ファイル数"]
        )
        files = {
            "llms.txt": (
                "- [ノート](a.md): 大量の小さなファイルで容量が残っていても\n"
                "- [索引](m.md): ファイル数の索引\n"
            ),
            "a.md": "x\n",
            # The phrase wraps across two source lines, which renders as one paragraph.
            "m.md": "大量の小さな\nファイルは [ここ](b.md) にある。\n",
            "b.md": "x\n",
        }
        questions = [
            question("wl-ja", "a.md", keywords=small),
            question("wl-ja-wrapped", "b.md", keywords=small),
        ]
        with Tree(files, questions) as tree:
            results = tree.evaluate()
        self.assertEqual(results["wl-ja"]["signposted"]["verdict"], "PASS")
        wrapped = results["wl-ja-wrapped"]["signposted"]
        self.assertEqual((wrapped["verdict"], wrapped["hops"]), ("PASS", 2))

    def test_an_ascii_keyword_does_not_match_inside_a_word(self) -> None:
        tr = keywords(
            ["TR", "technical report"], ["テクニカルレポート", "技術レポート"]
        )
        files = {
            "llms.txt": "- [s](s.md): STRUCTURE overview\n- [t](t.md): see TR-4572\n",
            "s.md": "x\n",
            "t.md": "x\n",
        }
        questions = [
            question("tr-inside-a-word", "s.md", keywords=tr),
            question("tr-standalone", "t.md", keywords=tr),
        ]
        with Tree(files, questions) as tree:
            results = tree.evaluate()
        self.assertEqual(results["tr-inside-a-word"]["signposted"]["verdict"], "FAIL")
        self.assertEqual(results["tr-standalone"]["signposted"]["verdict"], "PASS")
        match = cr.matcher(tr)
        for text in ("a string value", "TRANSFER rates", "an attribute"):
            with self.subTest(inside=text):
                self.assertFalse(match(text))
        for text in ("TR-4572", "see TR for details", "the tr guide", "(TR)"):
            with self.subTest(standalone=text):
                self.assertTrue(match(text))

    def test_every_keyword_group_must_match_on_a_hop(self) -> None:
        """One word from each subject, inside one block; one subject alone is not a signpost."""
        cache_and_fpolicy = groups(
            (["FlexCache", "cache"], ["キャッシュ"]),
            (["FPolicy"], ["FPolicy", "ポリシー"]),
        )
        files = {
            "llms.txt": (
                "- [Both](a.md): FPolicy on a FlexCache cache\n"
                "- [One](b.md): FPolicy on an origin volume\n"
                "- [Idx](idx.md): FlexCache and FPolicy index\n"
            ),
            "idx.md": "FlexCache: [c](c.md)\n\nFPolicy: [c](c.md)\n",
            "a.md": "x\n",
            "b.md": "x\n",
            "c.md": "x\n",
        }
        questions = [
            question("wl-both", "a.md", keywords=cache_and_fpolicy),
            question("wl-one", "b.md", keywords=cache_and_fpolicy),
            question("wl-split", "c.md", keywords=cache_and_fpolicy),
        ]
        with Tree(files, questions) as tree:
            results = tree.evaluate()
        self.assertEqual(results["wl-both"]["signposted"]["verdict"], "PASS")
        one = results["wl-one"]
        self.assertEqual(one["verdict"], "PASS")
        self.assertEqual(one["signposted"]["verdict"], "FAIL")
        self.assertEqual(one["signposted"]["missing"]["unmatched"], ["FlexCache"])
        # Each subject is named beside a different occurrence of the same link: two halves.
        split = results["wl-split"]
        self.assertEqual(split["verdict"], "PASS")
        self.assertEqual(split["signposted"]["verdict"], "FAIL")
        self.assertEqual(split["signposted"]["missing"]["hop"], 2)

    def test_a_markdown_list_item_carries_its_continuation_lines(self) -> None:
        """Outside llms.txt, a wrapped list item is one block; a blank line still ends it."""
        files = {
            "llms.txt": "- [Idx](idx.md): FlexCache index\n",
            "idx.md": (
                "- [a](a.md) is the note\n  on FlexCache consistency\n"
                "- [b](b.md) is another note\n\nFlexCache follows a blank line.\n"
            ),
            "a.md": "x\n",
            "b.md": "x\n",
        }
        questions = [
            question("wl-wrapped", "a.md", keywords=FLEXCACHE),
            question("wl-next-item", "b.md", keywords=FLEXCACHE),
        ]
        with Tree(files, questions) as tree:
            results = tree.evaluate()
        self.assertEqual(results["wl-wrapped"]["signposted"]["verdict"], "PASS")
        self.assertEqual(results["wl-next-item"]["signposted"]["verdict"], "FAIL")

    def test_a_heading_is_its_own_block(self) -> None:
        """A heading neither lends its words to the line under it nor borrows that line's."""
        files = {
            "llms.txt": "- [Idx](idx.md): FlexCache index\n",
            "idx.md": (
                "## FlexCache\n[a](a.md) is here\n\n"
                "## Overview [b](b.md)\nFlexCache is described here.\n\n"
                "## FlexCache [c](c.md)\n"
            ),
            "a.md": "x\n",
            "b.md": "x\n",
            "c.md": "x\n",
        }
        questions = [
            question("wl-under", "a.md", keywords=FLEXCACHE),
            question("wl-in-heading", "b.md", keywords=FLEXCACHE),
            question("wl-named-heading", "c.md", keywords=FLEXCACHE),
        ]
        with Tree(files, questions) as tree:
            results = tree.evaluate()
        self.assertEqual(results["wl-under"]["signposted"]["verdict"], "FAIL")
        self.assertEqual(results["wl-in-heading"]["signposted"]["verdict"], "FAIL")
        self.assertEqual(results["wl-named-heading"]["signposted"]["verdict"], "PASS")

    def test_external_signposted_inconclusive_is_per_question(self) -> None:
        """A blocked node only makes a signposted FAIL undetermined if a signposted path reached it."""
        files = {
            "llms.txt": (
                f"- [Sib x](https://github.com/{cr.OWNER}/Sib/blob/main/docs/x.md): "
                "alpha topics\n"
            ),
        }
        down = urllib.error.HTTPError("u", 503, "down", None, None)  # type: ignore[arg-type]
        questions = [
            question(
                "sm-alpha",
                f"{SIB}:docs/y.md",
                scope="cross-repo",
                keywords=keywords(["alpha", "alphas"]),
            ),
            question(
                "sm-beta",
                f"{SIB}:docs/y.md",
                scope="cross-repo",
                keywords=keywords(["beta", "betas"]),
            ),
        ]
        with Tree(files, questions) as tree:
            results = tree.evaluate(
                external=True, opener=Opener({}, errors={"docs/x.md": down})
            )
            argv = [
                "--root",
                str(tree.root),
                "--questions",
                str(tree.qfile),
                "--external",
            ]
            plain_status, plain_out = _main(
                argv, Opener({}, errors={"docs/x.md": down})
            )
            gated_status, gated_out = _main(
                [*argv, "--signposted"], Opener({}, errors={"docs/x.md": down})
            )
        alpha, beta = results["sm-alpha"], results["sm-beta"]
        self.assertEqual(alpha["verdict"], "INCONCLUSIVE")
        self.assertEqual(alpha["signposted"]["verdict"], "INCONCLUSIVE")
        self.assertIn("HTTP 503", alpha["signposted"]["reason"])
        self.assertEqual(beta["verdict"], "INCONCLUSIVE")
        self.assertEqual(beta["signposted"]["verdict"], "FAIL")
        self.assertEqual(plain_status, 0, plain_out)
        self.assertEqual(gated_status, 1, gated_out)
        self.assertRegex(gated_out, r"(?m)^  \? sm-alpha \(signposted\): ")

    def test_signposted_adds_no_fetches(self) -> None:
        opener = Opener({"docs/x.md": "[y](y.md)\n", "docs/y.md": "a\n"})
        with Tree(EXT_FILES, [EXT_Q]) as tree:
            r = tree.evaluate(external=True, opener=opener)["sm-y"]
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["signposted"]["verdict"], "FAIL")
        self.assertEqual([u.rsplit("/", 1)[1] for u in opener.calls], ["x.md", "y.md"])

    def test_signpost_parsing_agrees_with_the_link_gate(self) -> None:
        from check_links import iter_links

        text = (
            "# Title\n\n[a](a.md) and ![img](i.png)\n\n```text\n[f](f.md)\n```\n\n"
            "| x | [b](b.md) |\n|---|---|\n\n- [c](c.md#frag): item\n> [d](d.md)\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_text(text, encoding="utf-8")
            expected = [target for _, target in iter_links(path)]
        found = [target for target, _ in cr.iter_signposts(text, llms=False)]
        self.assertEqual(found, expected)
        self.assertEqual(found, ["a.md", "b.md", "c.md#frag", "d.md"])

    def test_llms_txt_items_do_not_absorb_the_next_paragraph(self) -> None:
        files = {
            "llms.txt": "- [Docs](a.md): overview\nFlexCache is described here.\n",
            "a.md": "x\n",
        }
        with Tree(files, [question("wl-a", "a.md", keywords=FLEXCACHE)]) as tree:
            r = tree.evaluate()["wl-a"]
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["signposted"]["verdict"], "FAIL")


class TheReportCarriesItsEnvironment(unittest.TestCase):
    KEYS = frozenset(
        {
            "schema",
            "run_date",
            "git_sha",
            "mode",
            "max_hops",
            "max_fetches",
            "questions_file",
            "questions_sha256",
            "counts",
            "signposted_counts",
            "gate",
            "fetch",
            "results",
        }
    )

    def test_the_report_has_every_key(self) -> None:
        with Tree(
            CHAIN, [question("wl-b", "b.md"), question("wl-o", "orphan.md")]
        ) as tree:
            report = tree.root / "out" / "report.json"
            with contextlib.redirect_stdout(io.StringIO()):
                cr.main(
                    [
                        "--root",
                        str(tree.root),
                        "--questions",
                        str(tree.qfile),
                        "--report",
                        str(report),
                    ]
                )
            data = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(set(data), self.KEYS)
        self.assertEqual(data["schema"], cr.REPORT_SCHEMA)
        self.assertEqual(data["max_hops"], cr.MAX_HOPS)
        self.assertEqual(data["mode"], "hub")
        self.assertRegex(data["run_date"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertRegex(data["questions_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            data["counts"], {"pass": 1, "fail": 1, "inconclusive": 0, "skipped": 0}
        )
        # CHAIN's link texts are single letters, so no hop names the fixture's subject.
        self.assertEqual(
            data["signposted_counts"],
            {"pass": 0, "fail": 2, "inconclusive": 0, "skipped": 0},
        )
        self.assertEqual(data["gate"], "linked")
        # Hub mode fetches nothing, and the report says so rather than leaving it out.
        self.assertEqual(data["fetch"]["attempted"], 0)
        result_keys = {
            "id",
            "category",
            "scope",
            "verdict",
            "hops",
            "path",
            "reason",
            "signposted",
        }
        for entry in data["results"]:
            self.assertLessEqual(result_keys, set(entry))
            self.assertEqual(
                set(entry["signposted"]),
                {"verdict", "hops", "path", "missing", "reason"},
            )

    def test_an_external_report_carries_fetch_statistics(self) -> None:
        opener = Opener({"docs/x.md": "[y](y.md)\n"})
        with Tree(EXT_FILES, [EXT_Q]) as tree:
            result = cr.evaluate(tree.load(), tree.root, external=True, opener=opener)
            report = cr.build_report(result, tree.root, tree.qfile)
        self.assertEqual(report["mode"], "external")
        self.assertEqual(
            set(report["fetch"]),
            {"attempted", "cached_hits", "inconclusive", "dead_nodes", "cap_reached"},
        )


if __name__ == "__main__":
    unittest.main()
