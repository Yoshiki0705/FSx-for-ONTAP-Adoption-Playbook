"""Task 3.1 tests for separated, read-only knowledge-quality inventory."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from typing import Any, Self

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from check_cross_repo import (
    AuthorityResolution,
    PublicAuthorityRecord,
    build_read_only_inventory,
    public_inventory_aggregate,
    resolve_public_authority,
    write_inventory_snapshots,
)

from scripts.tests.gitenv import scrubbed_env


class Response:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def public_record(repository_id: int, head: str) -> PublicAuthorityRecord:
    return PublicAuthorityRecord(
        repository_id=repository_id,
        canonical_full_name=f"example/repository-{repository_id}",
        default_branch="main",
        default_branch_head_sha=head,
        visibility="public",
        archived=False,
    )


def resolution(repository_id: int, head: str) -> AuthorityResolution:
    return AuthorityResolution("PASS", public_record(repository_id, head), "fixture")


class GitFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.env = scrubbed_env()

    def repository(
        self,
        name: str,
        *,
        kiro: bool = True,
        remote: str | None = "https://github.com/example/shared.git",
    ) -> tuple[Path, str]:
        path = self.root / name
        path.mkdir(parents=True)
        self.run(path, "init", "-q")
        if kiro:
            (path / ".kiro").mkdir()
        (path / "content.txt").write_text(name + "\n", encoding="utf-8")
        self.run(path, "add", "content.txt")
        self.run(path, "commit", "-q", "-m", "fixture")
        if remote:
            self.run(path, "remote", "add", "origin", remote)
        head = self.run(path, "rev-parse", "HEAD").stdout.strip()
        return path, head

    def run(self, path: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            check=True,
            env=self.env,
        )


class PublicAuthorityTests(unittest.TestCase):
    def test_metadata_and_default_head_form_the_public_authority(self) -> None:
        payloads = iter(
            [
                {
                    "id": 42,
                    "full_name": "canonical/renamed",
                    "default_branch": "trunk",
                    "visibility": "public",
                    "archived": False,
                },
                {"sha": "a" * 40},
            ]
        )
        urls: list[str] = []

        def opener(request: Any, timeout: int) -> Response:
            urls.append(request.full_url)
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(timeout, 30)
            return Response(next(payloads))

        result = resolve_public_authority("old", "name", opener=opener)
        self.assertEqual(result.state, "PASS")
        self.assertEqual(
            result.record,
            public_record(42, "a" * 40).__class__(
                repository_id=42,
                canonical_full_name="canonical/renamed",
                default_branch="trunk",
                default_branch_head_sha="a" * 40,
                visibility="public",
                archived=False,
            ),
        )
        self.assertEqual(
            urls,
            [
                "https://api.github.com/repos/old/name",
                "https://api.github.com/repos/old/name/commits/trunk",
            ],
        )

    def test_external_response_classes_remain_three_state(self) -> None:
        def failing(status: int):
            def opener(request: Any, timeout: int) -> Response:
                error = urllib.error.HTTPError(
                    request.full_url, status, "fixture", {}, None
                )
                error.close()
                raise error

            return opener

        self.assertEqual(
            resolve_public_authority("o", "r", opener=failing(404)).state,
            "DEFECT",
        )
        private_metadata = Response(
            {
                "id": 9,
                "full_name": "o/private",
                "default_branch": "main",
                "visibility": "private",
                "archived": False,
            }
        )
        self.assertEqual(
            resolve_public_authority(
                "o", "private", opener=lambda request, timeout: private_metadata
            ).state,
            "DEFECT",
        )
        for status in (403, 500):
            with self.subTest(status=status):
                self.assertEqual(
                    resolve_public_authority("o", "r", opener=failing(status)).state,
                    "INCONCLUSIVE",
                )

    def test_malformed_public_payloads_are_inconclusive(self) -> None:
        for payloads in (
            ([],),
            (
                {
                    "id": 9,
                    "full_name": "o/r",
                    "default_branch": "main",
                    "visibility": "public",
                    "archived": False,
                },
                [],
            ),
        ):
            with self.subTest(payloads=payloads):
                responses = iter(Response(payload) for payload in payloads)
                result = resolve_public_authority(
                    "o",
                    "r",
                    opener=lambda request, timeout, responses=responses: next(
                        responses
                    ),
                )
                self.assertEqual(result.state, "INCONCLUSIVE")
                self.assertIsNone(result.record)


class InventoryPropertyTests(unittest.TestCase):
    def test_any_number_of_checkouts_for_one_id_keeps_authority_count_one(self) -> None:
        """**Validates: Requirements 1.6, 2.6, 3.7**"""
        for checkout_count in range(1, 6):
            with (
                self.subTest(checkout_count=checkout_count),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp)
                fixture = GitFixture(root)
                heads = [
                    fixture.repository(f"copy-{index}")[1]
                    for index in range(checkout_count)
                ]

                public_head = heads[0]

                def resolver(
                    owner: str, repo: str, head: str = public_head
                ) -> AuthorityResolution:
                    self.assertEqual((owner, repo), ("example", "shared"))
                    return resolution(7, head)

                inventory = build_read_only_inventory(root, 1, resolver=resolver)
                self.assertEqual(
                    inventory["authority_map"]["authoritative_repository_count"], 1
                )
                records = inventory["local_checkouts"]["records"]
                self.assertEqual(len(records), checkout_count)
                self.assertTrue(all(record["repository_id"] == 7 for record in records))
                self.assertTrue(
                    all(record["duplicate"] for record in records)
                    if checkout_count > 1
                    else not records[0]["duplicate"]
                )

    def test_conflicting_records_for_one_repository_id_are_rejected(self) -> None:
        """**Validates: Requirements 1.6, 2.6**"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = GitFixture(root)
            _, first_head = fixture.repository(
                "first", remote="https://github.com/example/first.git"
            )
            _, second_head = fixture.repository(
                "second", remote="https://github.com/example/second.git"
            )

            def resolver(owner: str, repo: str) -> AuthorityResolution:
                head = first_head if repo == "first" else second_head
                return AuthorityResolution(
                    "PASS",
                    PublicAuthorityRecord(
                        repository_id=7,
                        canonical_full_name=f"example/{repo}",
                        default_branch="main",
                        default_branch_head_sha=head,
                        visibility="public",
                        archived=False,
                    ),
                    "fixture",
                )

            with self.assertRaisesRegex(
                ValueError, "conflicting public authority records"
            ):
                build_read_only_inventory(root, 1, resolver=resolver)

    def test_candidates_receive_include_or_exclude_reasons_and_local_state(
        self,
    ) -> None:
        """**Validates: Requirements 1.6, 2.6, 3.7**"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = GitFixture(root)
            current_path, current_head = fixture.repository("current")
            stale_path, _ = fixture.repository("stale")
            no_kiro_path, _ = fixture.repository("no-kiro", kiro=False)
            local_path, _ = fixture.repository(
                "local-only", remote="file:///private/local.git"
            )
            uncertain_path, _ = fixture.repository(
                "uncertain", remote="https://github.com/example/uncertain.git"
            )
            non_git_path = root / "non-git"
            (non_git_path / ".kiro").mkdir(parents=True)
            (current_path / "content.txt").write_text("dirty\n", encoding="utf-8")
            fixture.run(stale_path, "checkout", "--detach", "-q")

            def resolver(owner: str, repo: str) -> AuthorityResolution:
                if repo == "uncertain":
                    return AuthorityResolution("INCONCLUSIVE", None, "rate limited")
                return resolution(7, current_head)

            def runner(
                command: list[str], **kwargs: Any
            ) -> subprocess.CompletedProcess[str]:
                if command[2] == str(current_path) and command[3] == "rev-list":
                    return subprocess.CompletedProcess(command, 0, "2 3\n", "")
                kwargs.pop("check", None)
                return subprocess.run(command, check=False, **kwargs)

            inventory = build_read_only_inventory(
                root, 1, resolver=resolver, runner=runner
            )
            by_path = {
                record["path"]: record
                for record in inventory["local_checkouts"]["records"]
            }
            self.assertTrue(by_path[str(current_path)]["included"])
            self.assertFalse(by_path[str(current_path)]["stale"])
            self.assertTrue(by_path[str(current_path)]["dirty"])
            self.assertEqual(by_path[str(current_path)]["behind"], 2)
            self.assertEqual(by_path[str(current_path)]["ahead"], 3)
            self.assertTrue(by_path[str(stale_path)]["stale"])
            self.assertTrue(by_path[str(stale_path)]["detached"])
            self.assertFalse(by_path[str(no_kiro_path)]["included"])
            self.assertIn("Kiro configuration", by_path[str(no_kiro_path)]["reason"])
            self.assertFalse(by_path[str(non_git_path)]["included"])
            self.assertIn("not a Git repository", by_path[str(non_git_path)]["reason"])
            self.assertEqual(by_path[str(local_path)]["authority_state"], "DEFECT")
            self.assertIn("not a GitHub", by_path[str(local_path)]["authority_reason"])
            self.assertEqual(
                by_path[str(uncertain_path)]["authority_state"], "INCONCLUSIVE"
            )
            self.assertEqual(
                by_path[str(uncertain_path)]["authority_reason"], "rate limited"
            )
            self.assertIsNone(by_path[str(uncertain_path)]["repository_id"])
            self.assertEqual(len(inventory["local_only_kiro"]["records"]), 1)
            self.assertEqual(
                inventory["local_only_kiro"]["records"][0]["project_key"],
                "local-0001",
            )

    def test_local_only_sentinels_do_not_enter_public_aggregate(self) -> None:
        """**Validates: Requirements 1.6, 2.6, 3.7**"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = GitFixture(root)
            local_path, _ = fixture.repository(
                "private-path-sentinel", remote="file:///private/authority-sentinel.git"
            )
            inventory = build_read_only_inventory(root, 1)
            local_only = inventory["local_only_kiro"]["records"][0]
            self.assertEqual(local_only["checkout_path"], str(local_path))
            aggregate_object = public_inventory_aggregate(inventory)
            aggregate = json.dumps(aggregate_object, sort_keys=True)
            self.assertEqual(set(aggregate_object), {"authoritative_repository_count"})
            self.assertNotIn(str(local_path), aggregate)
            self.assertNotIn(local_only["project_key"], aggregate)
            self.assertNotIn("authority-sentinel", aggregate)


class InventoryIntegrationTests(unittest.TestCase):
    def test_empty_scan_fails_instead_of_reporting_green(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            self.assertRaisesRegex(ValueError, "no Git/Kiro candidates"),
        ):
            build_read_only_inventory(Path(tmp), 1)

    def test_snapshots_use_separate_files_schemas_and_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "projects"
            output = Path(tmp) / "private-output"
            root.mkdir()
            fixture = GitFixture(root)
            _, head = fixture.repository("checkout")
            inventory = build_read_only_inventory(
                root, 1, resolver=lambda owner, repo: resolution(8, head)
            )
            write_inventory_snapshots(inventory, output)
            names = {
                "public-authority.json",
                "local-checkouts.json",
                "local-only-kiro.json",
                "authority-map.json",
            }
            self.assertEqual({path.name for path in output.iterdir()}, names)
            documents = [
                json.loads((output / name).read_text(encoding="utf-8"))
                for name in sorted(names)
            ]
            self.assertEqual(len({document["schema"] for document in documents}), 4)
            self.assertTrue(all(document["generated_at"] for document in documents))

    def test_inventory_git_commands_are_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = GitFixture(root)
            _, head = fixture.repository("checkout")
            commands: list[list[str]] = []

            def spy(
                command: list[str], **kwargs: Any
            ) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                kwargs.pop("check", None)
                return subprocess.run(command, check=False, **kwargs)

            build_read_only_inventory(
                root,
                1,
                resolver=lambda owner, repo: resolution(8, head),
                runner=spy,
            )
            self.assertTrue(commands)
            allowed = {
                ("rev-parse", "--is-inside-work-tree"),
                ("rev-parse", "HEAD"),
                ("symbolic-ref", "--quiet", "--short", "HEAD"),
                ("status", "--porcelain"),
                ("remote", "get-url", "origin"),
                ("rev-list", "--left-right", "--count", "@{upstream}...HEAD"),
                ("rev-parse", "--absolute-git-dir"),
            }
            observed = {tuple(command[3:]) for command in commands}
            self.assertEqual(observed, allowed)
            forbidden = {
                "add",
                "branch",
                "checkout",
                "clean",
                "commit",
                "fetch",
                "merge",
                "pull",
                "push",
                "remote-add",
                "reset",
                "restore",
                "switch",
                "tag",
                "worktree-add",
            }
            self.assertFalse(forbidden & {command[3] for command in commands})


if __name__ == "__main__":
    unittest.main()
