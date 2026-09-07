"""A server that did not answer is not a link that is broken - nor one that was checked.

Both wrong answers are reachable from the same place. Calling a 5xx broken fails a run over someone
else's outage, and **a check that is wrong when nothing is wrong stops being read**. Calling it fine
is worse: a permanently unreachable URL then looks verified. A sibling repository measured the case
that makes the second one concrete - github.com's HTML endpoint returns 504 **persistently** for
particular repositories on a hosted runner while the REST API answers immediately.
"""

import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check_links


def _raise(code: int):
    def fake(request, timeout=0):
        raise urllib.error.HTTPError(request.full_url, code, "", {}, None)

    return fake


class ServerErrorsAreUndetermined(unittest.TestCase):
    def test_a_504_is_marked_undetermined_rather_than_broken(self) -> None:
        with mock.patch.object(check_links.urllib.request, "urlopen", _raise(504)):
            verdict = check_links.check_external("https://example.invalid/x")
        assert verdict is not None
        self.assertTrue(
            verdict.startswith(check_links.UNDETERMINED),
            f"a 504 is reported as a broken link: {verdict!r}",
        )

    def test_undetermined_is_not_silence(self) -> None:
        """The marker has to survive as a value. None would read as "checked and fine"."""
        with mock.patch.object(check_links.urllib.request, "urlopen", _raise(503)):
            self.assertIsNotNone(
                check_links.check_external("https://example.invalid/x"),
                "a 503 returns None, so an unreachable URL looks verified",
            )

    def test_a_404_stays_a_broken_link(self) -> None:
        """The distinction is worth something only if the other side still fails."""
        with mock.patch.object(check_links.urllib.request, "urlopen", _raise(404)):
            verdict = check_links.check_external("https://example.invalid/x")
        assert verdict is not None
        self.assertFalse(verdict.startswith(check_links.UNDETERMINED))
        self.assertIn("404", verdict)

    def test_bot_blocking_is_still_neither(self) -> None:
        """403 predates this: the probe was refused, not that the page is missing."""
        with mock.patch.object(check_links.urllib.request, "urlopen", _raise(403)):
            self.assertIsNone(check_links.check_external("https://example.invalid/x"))


if __name__ == "__main__":
    unittest.main()
