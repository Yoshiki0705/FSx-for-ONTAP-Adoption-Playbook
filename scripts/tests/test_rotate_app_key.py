"""`scripts/rotate_app_key.sh` checks the new key before it touches the secret, and never shows it.

The script is run with fake `gh` and `curl` first on PATH, and an `openssl` that logs the call and
then runs the real one, so the key handling is real and nothing leaves the machine. The key is a
throw-away RSA key generated here. Each fake records what it was called with and what it was given on
standard input, which is how a test can say where the JWT travelled.

* A verification that is not a 200 stops the script before `gh secret set`.
* The key file is deleted on every path after it was accepted as a file, and is left alone when the
  script refuses to start (inside a git work tree, or not a file).
* Neither the key's contents nor the JWT reach the output or any command line.
* A workflow run that fails prints no instruction to delete the old key.

Not tested here, and not run for real: `gh`, `curl` and `openssl` against their real services.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.tests.gitenv import scrubbed_env

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "rotate_app_key.sh"
REAL_OPENSSL = shutil.which("openssl")
REAL_BASH = shutil.which("bash")

FAKE_GH = r"""#!/usr/bin/env bash
echo "gh $*" >> "$FAKE_LOG"
case "$1 $2" in
  "auth status") exit "${FAKE_GH_AUTH_EXIT:-0}" ;;
  "variable get") printf '%s\n' "${FAKE_CLIENT_ID-Iv1.fakeclientid0001}" ;;
  "secret set") cat > "$FAKE_SECRET_STDIN"; echo "Set Actions secret" ;;
  "workflow run") exit "${FAKE_WORKFLOW_RUN_EXIT:-0}" ;;
  "run list")
    if [ "$(grep -c '^gh run list' "$FAKE_LOG")" -le 1 ]; then
      printf '100\n'
    else
      printf '101\n100\n'
    fi ;;
  "run watch") exit "${FAKE_WATCH_EXIT:-0}" ;;
esac
"""

FAKE_CURL = r"""#!/usr/bin/env bash
echo "curl $*" >> "$FAKE_LOG"
cat >> "$FAKE_CURL_STDIN"
out=""
want_code=0
while [ $# -gt 0 ]; do
  case "$1" in
    -o|--output) out="$2"; shift ;;
    -w|--write-out) want_code=1; shift ;;
  esac
  shift
done
status="${FAKE_CURL_STATUS:-200}"
if [ "${FAKE_CURL_FAIL:-0}" = 1 ]; then
  exit 7
fi
if [ -n "$out" ]; then
  if [ "$status" = 200 ]; then
    printf '{"id":1,"slug":"sc-aggregator-yoshiki0705","name":"aggregator"}' > "$out"
  else
    printf '{"message":"body-that-must-not-be-printed"}' > "$out"
  fi
fi
if [ "$want_code" = 1 ]; then
  printf '%s' "$status"
fi
"""

FAKE_OPENSSL = r"""#!/usr/bin/env bash
echo "openssl $1" >> "$FAKE_LOG"
exec "$REAL_OPENSSL" "$@"
"""


def write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@unittest.skipUnless(REAL_OPENSSL and REAL_BASH, "needs openssl and bash")
class Base(unittest.TestCase):
    pem_text = ""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        key = Path(cls._tmp.name) / "key.pem"
        assert REAL_OPENSSL
        subprocess.run(
            [REAL_OPENSSL, "genrsa", "-out", str(key), "2048"],
            check=True,
            capture_output=True,
            timeout=120,
        )
        cls.pem_text = key.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def setUp(self) -> None:
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        base = Path(self.work.name)
        self.bin = base / "bin"
        self.bin.mkdir()
        write_executable(self.bin / "gh", FAKE_GH)
        write_executable(self.bin / "curl", FAKE_CURL)
        write_executable(self.bin / "openssl", FAKE_OPENSSL)
        self.log = base / "calls.log"
        self.log.write_text("", encoding="utf-8")
        self.secret_stdin = base / "secret-stdin"
        self.curl_stdin = base / "curl-stdin"
        self.curl_stdin.write_text("", encoding="utf-8")
        self.pem = base / "new-key.pem"
        self.pem.write_text(self.pem_text, encoding="utf-8")

    def run_script(
        self, *args: str, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = scrubbed_env()
        env.update(
            {
                "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                "FAKE_LOG": str(self.log),
                "FAKE_SECRET_STDIN": str(self.secret_stdin),
                "FAKE_CURL_STDIN": str(self.curl_stdin),
                "REAL_OPENSSL": str(REAL_OPENSSL),
                "ROTATE_POLL_SECONDS": "0",
            }
        )
        env.update(extra_env or {})
        assert REAL_BASH
        return subprocess.run(
            [REAL_BASH, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
            check=False,
        )

    def calls(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines()

    def called(self, prefix: str) -> list[int]:
        return [i for i, line in enumerate(self.calls()) if line.startswith(prefix)]


class TheSuccessfulRun(Base):
    def setUp(self) -> None:
        super().setUp()
        self.result = self.run_script(str(self.pem))
        self.output = self.result.stdout + self.result.stderr

    def test_it_succeeds(self) -> None:
        self.assertEqual(self.result.returncode, 0, self.output)

    def test_the_new_key_is_checked_before_the_secret_is_set(self) -> None:
        verify = self.called("curl")
        setting = self.called("gh secret set")
        self.assertEqual(len(verify), 1)
        self.assertEqual(len(setting), 1)
        self.assertLess(verify[0], setting[0])

    def test_the_steps_run_in_the_documented_order(self) -> None:
        order = [
            "gh auth status",
            "gh variable get SUPPLY_CHAIN_APP_CLIENT_ID",
            "curl",
            "gh secret set SUPPLY_CHAIN_APP_PRIVATE_KEY",
            "gh workflow run supply-chain-key-rotation.yml",
            "gh run watch",
        ]
        positions = []
        for prefix in order:
            found = self.called(prefix)
            self.assertTrue(found, f"never called: {prefix}")
            positions.append(found[0])
        self.assertEqual(positions, sorted(positions))

    def test_the_secret_is_given_on_standard_input_and_carries_the_key(self) -> None:
        self.assertEqual(self.secret_stdin.read_text(encoding="utf-8"), self.pem_text)
        line = self.calls()[self.called("gh secret set")[0]]
        self.assertNotIn("--body", line)
        self.assertNotIn("BEGIN", line)

    def test_the_run_it_started_is_the_run_it_watches(self) -> None:
        watch = self.calls()[self.called("gh run watch")[0]]
        self.assertIn("101", watch)
        self.assertNotIn(" 100", watch)
        self.assertIn("--exit-status", watch)

    def test_the_default_repository_is_used_and_named_in_every_gh_call(self) -> None:
        for line in self.calls():
            if line.startswith("gh") and not line.startswith("gh auth"):
                self.assertIn(
                    "--repo Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook", line
                )

    def test_the_key_file_is_deleted_and_the_output_says_so(self) -> None:
        self.assertFalse(self.pem.exists())
        self.assertIn(str(self.pem), self.output)

    def test_the_app_slug_and_the_fingerprint_are_shown(self) -> None:
        self.assertIn("sc-aggregator-yoshiki0705", self.output)
        assert REAL_OPENSSL
        der = subprocess.run(
            [REAL_OPENSSL, "rsa", "-pubout", "-outform", "DER"],
            input=self.pem_text.encode(),
            capture_output=True,
            check=True,
        ).stdout
        expected = base64.b64encode(hashlib.sha256(der).digest()).decode()
        self.assertIn(f"SHA256:{expected}", self.output)

    def test_the_person_is_told_to_delete_the_other_key_in_the_settings(self) -> None:
        self.assertIn(
            "https://github.com/settings/apps/sc-aggregator-yoshiki0705", self.output
        )
        self.assertIn("Delete", self.output)
        self.assertIn("25", self.output)

    def test_neither_the_key_nor_the_jwt_is_printed_or_put_on_a_command_line(
        self,
    ) -> None:
        body_lines = [
            line
            for line in self.pem_text.splitlines()
            if line and not line.startswith("-----")
        ]
        self.assertTrue(body_lines)
        for line in body_lines:
            self.assertNotIn(line, self.output)
        self.assertNotIn("BEGIN", self.output)
        logged = self.log.read_text(encoding="utf-8")
        self.assertNotIn("eyJ", logged, "a JWT is on a command line")
        self.assertNotIn("Bearer", logged)
        for line in body_lines:
            self.assertNotIn(line, logged)

    def test_the_jwt_travelled_on_standard_input_so_the_check_above_means_something(
        self,
    ) -> None:
        sent = self.curl_stdin.read_text(encoding="utf-8")
        match = re.search(r"Bearer (eyJ[\w-]+\.[\w-]+\.[\w-]+)", sent)
        self.assertIsNotNone(match, "no JWT reached curl, so nothing was verified")
        assert match
        self.assertNotIn(match.group(1), self.output)
        payload = match.group(1).split(".")[1]
        claims = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
        self.assertIn('"iss":"Iv1.fakeclientid0001"', claims)
        iat = int(re.search(r'"iat":(\d+)', claims).group(1))  # type: ignore[union-attr]
        exp = int(re.search(r'"exp":(\d+)', claims).group(1))  # type: ignore[union-attr]
        self.assertEqual(exp - iat, 600, "iat is now - 60 and exp is now + 540")

    def test_the_verification_asks_the_app_endpoint(self) -> None:
        line = self.calls()[self.called("curl")[0]]
        self.assertIn("https://api.github.com/app", line)


class ARepositoryCanBeNamed(Base):
    def test_repo_is_passed_to_every_gh_call(self) -> None:
        result = self.run_script(str(self.pem), "--repo", "example-org/example-repo")
        self.assertEqual(result.returncode, 0, result.stderr)
        for line in self.calls():
            if line.startswith("gh") and not line.startswith("gh auth"):
                self.assertIn("--repo example-org/example-repo", line)

    def test_the_option_may_come_before_the_path(self) -> None:
        result = self.run_script("--repo", "example-org/example-repo", str(self.pem))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_repository_that_is_not_owner_slash_name_is_refused(self) -> None:
        for bad in ["nothing", "a/b/c", "a b/c"]:
            with self.subTest(bad=bad):
                result = self.run_script(str(self.pem), "--repo", bad)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.calls(), [])


class AFailedVerificationLeavesTheSecretAlone(Base):
    def assert_stopped_before_the_secret(
        self, result: subprocess.CompletedProcess[str]
    ) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.called("gh secret set"), [], "the secret was touched")
        self.assertEqual(self.called("gh workflow run"), [])
        self.assertFalse(self.pem.exists(), "the key file was left behind")

    def test_a_401(self) -> None:
        result = self.run_script(str(self.pem), extra_env={"FAKE_CURL_STATUS": "401"})
        self.assert_stopped_before_the_secret(result)
        output = result.stdout + result.stderr
        self.assertNotIn("body-that-must-not-be-printed", output)
        self.assertIn("401", output)

    def test_any_other_status(self) -> None:
        for status in ["403", "404", "500", "000"]:
            with self.subTest(status=status):
                self.setUp()
                result = self.run_script(
                    str(self.pem), extra_env={"FAKE_CURL_STATUS": status}
                )
                self.assert_stopped_before_the_secret(result)

    def test_curl_itself_failing(self) -> None:
        result = self.run_script(str(self.pem), extra_env={"FAKE_CURL_FAIL": "1"})
        self.assert_stopped_before_the_secret(result)

    def test_an_empty_client_id(self) -> None:
        result = self.run_script(str(self.pem), extra_env={"FAKE_CLIENT_ID": ""})
        self.assert_stopped_before_the_secret(result)
        self.assertEqual(self.called("curl"), [], "a JWT was made without a client ID")

    def test_a_file_that_is_not_a_private_key(self) -> None:
        self.pem.write_text("not a key\n", encoding="utf-8")
        result = self.run_script(str(self.pem))
        self.assert_stopped_before_the_secret(result)
        self.assertEqual(self.called("curl"), [])

    def test_gh_not_logged_in(self) -> None:
        result = self.run_script(str(self.pem), extra_env={"FAKE_GH_AUTH_EXIT": "1"})
        self.assert_stopped_before_the_secret(result)
        self.assertEqual(self.called("curl"), [])


class AFailedWorkflowRunKeepsTheOldKey(Base):
    def setUp(self) -> None:
        super().setUp()
        self.result = self.run_script(str(self.pem), extra_env={"FAKE_WATCH_EXIT": "1"})
        self.output = self.result.stdout + self.result.stderr

    def test_it_exits_1_after_the_secret_was_set(self) -> None:
        self.assertEqual(self.result.returncode, 1, self.output)
        self.assertEqual(len(self.called("gh secret set")), 1)

    def test_no_instruction_to_delete_the_old_key_is_printed(self) -> None:
        self.assertNotIn("Delete", self.output)
        self.assertNotIn("https://github.com/settings/apps", self.output)

    def test_it_says_how_to_go_back_and_that_the_old_key_is_still_valid(self) -> None:
        self.assertIn("gh secret set SUPPLY_CHAIN_APP_PRIVATE_KEY", self.output)
        self.assertIn("まだ有効", self.output)

    def test_the_key_file_is_still_deleted(self) -> None:
        self.assertFalse(self.pem.exists())

    def test_a_workflow_that_cannot_be_started_is_the_same_failure(self) -> None:
        Base.setUp(
            self
        )  # a fresh key file; the setUp of this class already used the first
        result = self.run_script(
            str(self.pem), extra_env={"FAKE_WORKFLOW_RUN_EXIT": "1"}
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Delete", result.stdout + result.stderr)
        self.assertEqual(self.called("gh run watch"), [])


class TheScriptRefusesToStart(Base):
    def test_no_argument(self) -> None:
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), [])

    def test_a_path_that_is_not_a_file(self) -> None:
        result = self.run_script(str(self.pem.parent / "missing.pem"))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), [])

    def test_an_unknown_option(self) -> None:
        result = self.run_script(str(self.pem), "--force")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(self.pem.exists())

    def test_a_key_inside_a_git_work_tree_is_refused_and_left_where_it_is(self) -> None:
        tree = Path(self.work.name) / "tree"
        tree.mkdir()
        subprocess.run(
            ["git", "init", "-q", str(tree)],
            check=True,
            timeout=60,
            env=scrubbed_env(),
        )
        inside = tree / "sub" / "key.pem"
        inside.parent.mkdir()
        inside.write_text(self.pem_text, encoding="utf-8")
        result = self.run_script(str(inside))
        self.assertEqual(result.returncode, 2)
        self.assertTrue(inside.exists(), "the script deleted a file it refused to use")
        self.assertEqual(self.calls(), [], "a command ran before the refusal")
        self.assertIn("git", result.stdout + result.stderr)


class TheScriptTextHasNoLeak(unittest.TestCase):
    """Static checks, since a leak needs only one careless line."""

    def setUp(self) -> None:
        self.text = SCRIPT.read_text(encoding="utf-8")
        self.code = "\n".join(
            line for line in self.text.splitlines() if not line.lstrip().startswith("#")
        )

    def test_strict_mode(self) -> None:
        self.assertIn("set -euo pipefail", self.code)

    def test_nothing_turns_on_tracing(self) -> None:
        self.assertNotRegex(self.code, r"set\s+-[a-z]*x")
        self.assertNotIn("xtrace", self.code)

    def test_the_key_is_never_read_into_the_output_or_a_variable(self) -> None:
        self.assertNotRegex(self.code, r"\bcat\b[^\n|]*\"?\$\{?pem")
        self.assertNotRegex(self.code, r"=\s*\"?\$\(<\s*\"?\$\{?pem")

    def test_the_jwt_is_not_a_curl_argument(self) -> None:
        self.assertNotRegex(self.code, r"curl[^\n]*\$\{?jwt")
        self.assertRegex(self.code, r"--config\s+-|-K\s+-")


if __name__ == "__main__":
    unittest.main()
