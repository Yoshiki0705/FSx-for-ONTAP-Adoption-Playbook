"""Cursor pagination and the EPSS redirect in the Aggregator's I/O layer. No test reaches the network.

* ``GitHubApi.pages()`` sends no ``page`` parameter and follows the Link header's rel="next", because
  the Dependabot alerts list answers a ``page`` parameter with HTTP 400.
* ``fetch_epss()`` follows at most three redirects, and only to the same host over https. The
  transport itself still never follows a redirect.
"""

from __future__ import annotations

import gzip
import json
import sys
import unittest
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from supply_chain_io import (
    EPSS_URL,
    Client,
    GitHubApi,
    HttpError,
    Response,
    UrllibTransport,
)

ALERTS = "/repos/example-org/example-repo/dependabot/alerts"
ROOT_URL = "https://api.github.com"


class Recorder:
    """A transport that answers from a function and records every URL."""

    def __init__(self, answer: Any) -> None:
        self.urls: list[str] = []
        self._answer = answer

    def request(
        self, method: str, url: str, headers: Any, body: bytes | None
    ) -> Response:
        self.urls.append(url)
        return self._answer(url)


def json_response(data: Any, link: str | None = None, status: int = 200) -> Response:
    headers = {"link": link} if link else {}
    return Response(status, headers, json.dumps(data).encode("utf-8"))


def api(answer: Any) -> tuple[GitHubApi, Recorder]:
    net = Recorder(answer)
    return GitHubApi(Client(net, sleep=lambda _: None), "token-value"), net


class CursorPagination(unittest.TestCase):
    def cursor_list(self, url: str) -> Response:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        if "page" in query:
            return json_response(
                {"message": "Pagination using the `page` parameter is not supported."},
                status=400,
            )
        after = query.get("after", [None])[0]
        if after is None:
            nxt = f'<{ROOT_URL}{ALERTS}?per_page=100&after=c1>; rel="next", <{ROOT_URL}{ALERTS}?per_page=100&before=c0>; rel="prev"'
            return json_response([1, 2], nxt)
        if after == "c1":
            nxt = f'<{ROOT_URL}{ALERTS}?per_page=100&after=c2>; rel="next"'
            return json_response([3, 4], nxt)
        return json_response([5])

    def test_it_follows_next_links_without_sending_page(self) -> None:
        github, net = api(self.cursor_list)
        self.assertEqual(list(github.pages(ALERTS)), [1, 2, 3, 4, 5])
        self.assertEqual(len(net.urls), 3)
        for url in net.urls:
            self.assertNotIn("page=", url.replace("per_page=", ""))
            self.assertIn("per_page=100", url)

    def test_a_response_without_a_link_header_is_the_last_page(self) -> None:
        github, net = api(lambda url: json_response(list(range(100))))
        self.assertEqual(len(list(github.pages(ALERTS))), 100)
        self.assertEqual(len(net.urls), 1, "a full page without Link was followed")

    def test_a_keyed_container_is_unwrapped_on_every_page(self) -> None:
        def answer(url: str) -> Response:
            if "after=c1" in url:
                return json_response({"artifacts": [{"id": 2}]})
            link = f'<{ROOT_URL}/x?per_page=100&after=c1>; rel="next"'
            return json_response({"artifacts": [{"id": 1}]}, link)

        github, _ = api(answer)
        self.assertEqual(
            list(github.pages("/x", key="artifacts")), [{"id": 1}, {"id": 2}]
        )

    def test_a_next_link_to_another_host_is_refused(self) -> None:
        for target in (
            "https://evil.example.test/x?after=c1",
            "http://api.github.com/x?after=c1",
        ):
            with self.subTest(target=target):
                github, net = api(
                    lambda url, t=target: json_response([1], f'<{t}>; rel="next"')
                )
                with self.assertRaises(HttpError):
                    list(github.pages("/x"))
                self.assertEqual(
                    len(net.urls), 1, "the foreign next link was requested"
                )

    def test_an_endless_chain_stops_at_the_page_limit(self) -> None:
        github, net = api(
            lambda url: json_response([1], f'<{ROOT_URL}/x?after=c>; rel="next"')
        )
        with self.assertRaises(HttpError):
            list(github.pages("/x"))
        self.assertEqual(len(net.urls), 100)

    def test_a_failing_page_raises(self) -> None:
        github, _ = api(lambda url: json_response({"message": "no"}, status=403))
        with self.assertRaises(HttpError):
            list(github.pages("/x"))


class EpssRedirect(unittest.TestCase):
    TEXT = "#model_version:v2026.01.01,score_date:2026-01-02T12:00:00Z\ncve,epss,percentile\nCVE-2021-0001,0.5,0.9\n"
    DATED = "https://epss.empiricalsecurity.com/epss_scores-2026-01-02.csv.gz"

    def file(self) -> Response:
        return Response(200, {}, gzip.compress(self.TEXT.encode("utf-8")))

    def client(self, answer: Any) -> tuple[Client, Recorder]:
        net = Recorder(answer)
        return Client(net, sleep=lambda _: None), net

    def test_a_relative_redirect_is_followed_and_the_table_returned(self) -> None:
        from supply_chain_io import fetch_epss

        def answer(url: str) -> Response:
            if url == EPSS_URL:
                return Response(302, {"location": "epss_scores-2026-01-02.csv.gz"}, b"")
            return self.file()

        client, net = self.client(answer)
        table = fetch_epss(client, ["CVE-2021-0001"])
        self.assertEqual(net.urls, [EPSS_URL, self.DATED])
        self.assertEqual(table["CVE-2021-0001"][0], "0.5")

    def test_a_redirect_off_the_host_or_off_https_is_an_error(self) -> None:
        from supply_chain_io import fetch_epss

        for location in (
            "https://other.example.test/epss.csv.gz",
            "http://epss.empiricalsecurity.com/epss.csv.gz",
        ):
            with self.subTest(location=location):
                client, net = self.client(
                    lambda url, loc=location: Response(302, {"location": loc}, b"")
                )
                with self.assertRaises(HttpError):
                    fetch_epss(client, [])
                self.assertEqual(
                    net.urls, [EPSS_URL], "the redirect target was requested"
                )

    def test_a_redirect_without_location_is_an_error(self) -> None:
        from supply_chain_io import fetch_epss

        client, _ = self.client(lambda url: Response(302, {}, b""))
        with self.assertRaises(HttpError):
            fetch_epss(client, [])

    def test_three_redirects_are_followed_and_the_fourth_is_not(self) -> None:
        from supply_chain_io import fetch_epss

        def chain(length: int) -> Any:
            def answer(url: str) -> Response:
                step = 0 if url == EPSS_URL else int(url.rsplit("/h", 1)[1])
                if step < length:
                    return Response(302, {"location": f"/h{step + 1}"}, b"")
                return self.file()

            return answer

        client, net = self.client(chain(3))
        self.assertIn("CVE-2021-0001", fetch_epss(client, ["CVE-2021-0001"]))
        self.assertEqual(len(net.urls), 4)

        client, net = self.client(chain(4))
        with self.assertRaises(HttpError):
            fetch_epss(client, [])
        self.assertEqual(len(net.urls), 4, "a fourth redirect was followed")

    def test_the_transport_still_does_not_follow_redirects(self) -> None:
        from supply_chain_io import _NoRedirect

        self.assertIsNone(
            _NoRedirect().redirect_request(
                None, None, 302, "Found", {}, "https://x.test/"
            )
        )
        self.assertTrue(hasattr(UrllibTransport, "request"))


class KevCatalogue(unittest.TestCase):
    """``fetch_kev`` reads dueDate, forensicTriage and the catalogue's dateReleased, entry by entry.

    The catalogue below is a fake. Its field names come from the models' docstring; the real catalogue was not
    fetched in this session (no network), so the real shape of ``dateReleased`` is unconfirmed.
    """

    def fetch(self, doc: Any) -> Any:
        from supply_chain_io import KEV_URL, fetch_kev

        net = Recorder(lambda url: json_response(doc))
        client = Client(net, sleep=lambda _: None)
        result = fetch_kev(client)
        self.assertEqual(net.urls, [KEV_URL])
        return result

    @staticmethod
    def entry(cve: str, **extra: Any) -> dict[str, Any]:
        return {"cveID": cve, "dateAdded": "2026-11-14", **extra}

    def test_due_date_and_forensic_triage_fill_the_entry(self) -> None:
        from datetime import date

        from supply_chain.models import KevEntry

        table, catalog, _ = self.fetch(
            {
                "catalogVersion": "2026.11.14",
                "dateReleased": "2026-11-14T15:04:05.123Z",
                "vulnerabilities": [
                    self.entry(
                        "CVE-2026-0001",
                        dueDate="2026-12-05",
                        forensicTriage="Yes",
                        knownRansomwareCampaignUse="Known",
                    ),
                    self.entry(
                        "CVE-2026-0002",
                        dueDate="2026-12-06",
                        forensicTriage="No",
                        knownRansomwareCampaignUse="Unknown",
                    ),
                ],
            }
        )
        self.assertEqual(catalog, "2026.11.14")
        self.assertEqual(
            table["CVE-2026-0001"],
            KevEntry(date(2026, 11, 14), True, date(2026, 12, 5), True),
        )
        self.assertIsInstance(table["CVE-2026-0001"], KevEntry)
        self.assertEqual(
            table["CVE-2026-0002"],
            KevEntry(date(2026, 11, 14), None, date(2026, 12, 6), False),
        )

    def test_a_missing_field_is_none_and_a_bad_field_does_not_hide_the_others(
        self,
    ) -> None:
        from datetime import date

        table, _, _ = self.fetch(
            {
                "vulnerabilities": [
                    self.entry("CVE-2026-0010"),
                    self.entry(
                        "CVE-2026-0011",
                        dueDate="soon",
                        forensicTriage="Yes",
                        knownRansomwareCampaignUse="Known",
                    ),
                    self.entry(
                        "CVE-2026-0012", dueDate=20261205, forensicTriage="maybe"
                    ),
                    self.entry(
                        "CVE-2026-0013", dueDate="2026-12-05", forensicTriage=None
                    ),
                ]
            }
        )
        self.assertEqual(
            tuple(table["CVE-2026-0010"]), (date(2026, 11, 14), None, None, None)
        )
        self.assertEqual(
            tuple(table["CVE-2026-0011"]), (date(2026, 11, 14), True, None, True)
        )
        self.assertEqual(
            tuple(table["CVE-2026-0012"]), (date(2026, 11, 14), None, None, None)
        )
        self.assertEqual(
            tuple(table["CVE-2026-0013"]),
            (date(2026, 11, 14), None, date(2026, 12, 5), None),
        )

    def test_date_released_is_read_as_utc_without_a_fraction_of_a_second(self) -> None:
        from datetime import UTC, datetime

        for raw in (
            "2026-11-14T15:04:05.123Z",
            "2026-11-14T15:04:05.1233Z",
            "2026-11-14T15:04:05Z",
        ):
            with self.subTest(raw=raw):
                _, _, released = self.fetch(
                    {"dateReleased": raw, "vulnerabilities": []}
                )
                self.assertEqual(released, datetime(2026, 11, 14, 15, 4, 5, tzinfo=UTC))

    def test_an_unreadable_date_released_is_none(self) -> None:
        for doc in (
            {"vulnerabilities": []},
            {"dateReleased": "garbage", "vulnerabilities": []},
            {"dateReleased": "2026-11-14T15:04:05", "vulnerabilities": []},
            {"dateReleased": 20261114, "vulnerabilities": []},
        ):
            with self.subTest(doc=doc):
                _, _, released = self.fetch(doc)
                self.assertIsNone(released)

    def test_the_released_time_passes_the_snapshot_check(self) -> None:
        from supply_chain.models import FeedSnapshot

        table, _, released = self.fetch(
            {
                "dateReleased": "2026-11-14T15:04:05.999Z",
                "vulnerabilities": [self.entry("CVE-2026-0001")],
            }
        )
        FeedSnapshot(
            kev=table,
            epss={},
            malicious={},
            malicious_withdrawn={},
            malicious_delisted=frozenset(),
            malicious_unconfirmed=frozenset(),
            kev_released_at=released,
        )


class LastCommitTime(unittest.TestCase):
    """``GitHubApi.last_commit_time`` reads the newest commit that touched one path, from a given commit.

    The responses below are fakes. The query parameters (``path``, ``sha``, ``per_page``) and the field
    ``commit.committer.date`` were written from memory of the List commits reference; the reference was not
    reachable when this was written, so the real shape is unconfirmed.
    """

    @staticmethod
    def commit(date_text: str | None) -> dict[str, Any]:
        committer = {} if date_text is None else {"date": date_text}
        return {"sha": "f" * 40, "commit": {"committer": committer}}

    def read(self, answer: Any) -> tuple[Any, Recorder]:
        github, net = api(answer)
        return github.last_commit_time("o/r", ".vex/a.json", "a" * 40), net

    def test_the_first_commit_of_the_list_gives_the_committer_date_in_utc(self) -> None:
        from datetime import UTC, datetime

        when, net = self.read(
            lambda url: json_response(
                [
                    self.commit("2026-11-14T15:04:05+09:00"),
                    self.commit("2020-01-01T00:00:00Z"),
                ]
            )
        )
        self.assertEqual(when, datetime(2026, 11, 14, 6, 4, 5, tzinfo=UTC))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(net.urls[0]).query)
        self.assertEqual(
            query, {"path": [".vex/a.json"], "sha": ["a" * 40], "per_page": ["1"]}
        )
        self.assertTrue(net.urls[0].startswith(f"{ROOT_URL}/repos/o/r/commits?"))

    def test_a_fraction_of_a_second_is_dropped(self) -> None:
        from datetime import UTC, datetime

        when, _ = self.read(
            lambda url: json_response([self.commit("2026-11-14T15:04:05.678Z")])
        )
        self.assertEqual(when, datetime(2026, 11, 14, 15, 4, 5, tzinfo=UTC))

    def test_no_commit_or_an_unreadable_date_is_none(self) -> None:
        for body in (
            [],
            [self.commit(None)],
            [self.commit("soon")],
            [self.commit("2026-11-14T15:04:05")],
            [{"commit": None}],
            [{}],
        ):
            with self.subTest(body=body):
                when, _ = self.read(lambda url, b=body: json_response(b))
                self.assertIsNone(when)

    def test_an_answer_that_is_not_a_list_is_an_error(self) -> None:
        github, _ = api(lambda url: json_response({"commits": []}))
        with self.assertRaises(HttpError):
            github.last_commit_time("o/r", ".vex/a.json", "a" * 40)

    def test_a_refusal_is_an_error(self) -> None:
        for status in (404, 500):
            with self.subTest(status=status):
                github, _ = api(
                    lambda url, s=status: json_response({"message": "no"}, status=s)
                )
                with self.assertRaises(HttpError):
                    github.last_commit_time("o/r", ".vex/a.json", "a" * 40)


class LabelCalls(unittest.TestCase):
    def test_delete_sends_a_delete_with_the_token_and_no_body(self) -> None:
        seen: list[tuple[str, str, Any]] = []

        class Net:
            def request(
                self, method: str, url: str, headers: Any, body: bytes | None
            ) -> Response:
                seen.append((method, url, body))
                return json_response([], status=200)

        github = GitHubApi(Client(Net(), sleep=lambda _: None), "token-value")
        self.assertEqual(github.delete("/repos/o/r/issues/7/labels/x").status, 200)
        self.assertEqual(
            seen, [("DELETE", f"{ROOT_URL}/repos/o/r/issues/7/labels/x", None)]
        )


if __name__ == "__main__":
    unittest.main()
