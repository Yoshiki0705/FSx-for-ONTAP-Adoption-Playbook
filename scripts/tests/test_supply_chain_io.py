"""Cursor pagination and the EPSS redirect in the Aggregator's I/O layer. No test reaches the network.

* ``GitHubApi.pages()`` sends no ``page`` parameter and follows the Link header's rel="next", because
  the Dependabot alerts list answers a ``page`` parameter with HTTP 400.
* ``fetch_epss()`` follows at most three redirects, and only to the same host over https. The
  transport itself still never follows a redirect.
"""

from __future__ import annotations

import gzip
import hashlib
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
        table, _payload = fetch_epss(client, ["CVE-2021-0001"])
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
        self.assertIn("CVE-2021-0001", fetch_epss(client, ["CVE-2021-0001"])[0])
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
        return result[:3]  # the payload is checked in FeedPayloads

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


class FeedPayloads(unittest.TestCase):
    """``fetch_kev`` and ``fetch_epss`` say what they read: the hash of the body, the count, the URL, the Date.

    The ``Date`` header is faked here; that a real KEV or EPSS response carries one was not observed.
    """

    DATE = "Sat, 14 Nov 2026 15:04:05 GMT"

    @staticmethod
    def kev_body(count: int = 2) -> bytes:
        doc = {
            "catalogVersion": "2026.11.14",
            "vulnerabilities": [
                {"cveID": f"CVE-2026-{n:04d}", "dateAdded": "2026-11-14"}
                for n in range(count)
            ],
        }
        return json.dumps(doc).encode("utf-8")

    def kev(self, body: bytes, headers: dict[str, str]) -> Any:
        from supply_chain_io import fetch_kev

        client = Client(
            Recorder(lambda url: Response(200, headers, body)), sleep=lambda _: None
        )
        return fetch_kev(client)

    def test_kev_reports_the_hash_of_the_body_bytes_and_the_entry_count(self) -> None:
        from supply_chain_io import KEV_URL

        body = self.kev_body(2)
        _table, _catalog, _released, payload = self.kev(body, {"date": self.DATE})
        self.assertEqual(payload.sha256, hashlib.sha256(body).hexdigest())
        self.assertEqual(payload.entry_count, 2)
        self.assertEqual(payload.source_url, KEV_URL)
        self.assertEqual(payload.http_date, self.DATE)

    def test_kev_with_no_vulnerabilities_counts_zero(self) -> None:
        payload = self.kev(self.kev_body(0), {})[3]
        self.assertEqual(payload.entry_count, 0)

    def test_a_response_without_a_date_header_has_no_date(self) -> None:
        payload = self.kev(self.kev_body(1), {})[3]
        self.assertIsNone(payload.http_date)

    def test_epss_hashes_the_bytes_as_received_and_counts_every_row_read(self) -> None:
        from supply_chain_io import fetch_epss

        text = (
            "#model_version:v2026.01.01,score_date:2026-01-02T12:00:00Z\n"
            "cve,epss,percentile\n"
            "CVE-2021-0001,0.5,0.9\nCVE-2021-0002,0.1,0.2\nCVE-2021-0003,0.2,0.3\n"
        )
        compressed = gzip.compress(text.encode("utf-8"))
        client = Client(
            Recorder(lambda url: Response(200, {"date": self.DATE}, compressed)),
            sleep=lambda _: None,
        )
        table, payload = fetch_epss(client, ["CVE-2021-0001"])
        self.assertEqual(list(table), ["CVE-2021-0001"])
        self.assertEqual(payload.sha256, hashlib.sha256(compressed).hexdigest())
        self.assertEqual(payload.entry_count, 3, "all rows, not only the wanted ones")
        self.assertEqual(payload.source_url, EPSS_URL)
        self.assertEqual(payload.http_date, self.DATE)

    def test_epss_names_the_url_that_answered_without_its_query_and_its_date(
        self,
    ) -> None:
        from supply_chain_io import fetch_epss

        text = (
            "#model_version:v1,score_date:2026-01-02T12:00:00Z\ncve,epss,percentile\n"
        )
        final = "https://epss.empiricalsecurity.com/epss_scores-2026-01-02.csv.gz"

        def answer(url: str) -> Response:
            if url == EPSS_URL:
                return Response(
                    302,
                    {"location": f"{final}?sig=secret", "date": "redirect date"},
                    b"",
                )
            return Response(
                200,
                {"date": self.DATE},
                gzip.compress(text.encode("utf-8")),
            )

        client = Client(Recorder(answer), sleep=lambda _: None)
        _table, payload = fetch_epss(client, [])
        self.assertEqual(payload.source_url, final)
        self.assertNotIn("secret", payload.source_url)
        self.assertEqual(payload.http_date, self.DATE)
        self.assertEqual(payload.entry_count, 0)


class LastCommitSha(unittest.TestCase):
    """``GitHubApi.last_commit_sha`` names the newest commit that touched one path, from a given commit.

    The responses below are fakes. The parameters (``path``, ``sha``, ``per_page``) and the field ``sha`` of
    a list item were written from memory of the List commits reference, which was not reachable when this was
    written, so the real shape is unconfirmed.
    """

    @staticmethod
    def commit(sha: Any) -> dict[str, Any]:
        return {"sha": sha, "commit": {"committer": {"date": "2026-11-14T15:04:05Z"}}}

    def read(self, answer: Any) -> tuple[Any, Recorder]:
        github, net = api(answer)
        return github.last_commit_sha("o/r", ".vex/a.json", "a" * 40), net

    def test_the_sha_of_the_first_commit_of_the_list_is_returned(self) -> None:
        sha, net = self.read(
            lambda url: json_response([self.commit("b" * 40), self.commit("c" * 40)])
        )
        self.assertEqual(sha, "b" * 40)
        self.assertEqual(len(net.urls), 1)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(net.urls[0]).query)
        self.assertEqual(
            query, {"path": [".vex/a.json"], "sha": ["a" * 40], "per_page": ["1"]}
        )
        self.assertTrue(net.urls[0].startswith(f"{ROOT_URL}/repos/o/r/commits?"))

    def test_an_empty_list_is_none(self) -> None:
        sha, _ = self.read(lambda url: json_response([]))
        self.assertIsNone(sha)

    def test_an_item_without_a_readable_sha_is_an_error_not_none(self) -> None:
        for body in (
            [{}],
            [{"sha": None}],
            [{"sha": 5}],
            [{"sha": "B" * 40}],
            [{"sha": "abc"}],
            ["not an object"],
        ):
            with self.subTest(body=body):
                github, _ = api(lambda url, b=body: json_response(b))
                with self.assertRaises(HttpError):
                    github.last_commit_sha("o/r", ".vex/a.json", "a" * 40)

    def test_an_answer_that_is_not_a_list_is_an_error(self) -> None:
        github, _ = api(lambda url: json_response({"commits": []}))
        with self.assertRaises(HttpError):
            github.last_commit_sha("o/r", ".vex/a.json", "a" * 40)

    def test_a_refusal_is_an_error(self) -> None:
        for status in (404, 500):
            with self.subTest(status=status):
                github, _ = api(
                    lambda url, s=status: json_response({"message": "no"}, status=s)
                )
                with self.assertRaises(HttpError):
                    github.last_commit_sha("o/r", ".vex/a.json", "a" * 40)


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


class OsvReceivedBodies(unittest.TestCase):
    """``Osv`` keeps, for every response it received, the hash of the body and the ``Date`` header, in order.

    The responses are fakes. That a real OSV response carries a ``Date`` header was not observed (no network).
    """

    D1 = "Sat, 14 Nov 2026 15:04:05 GMT"
    D2 = "Sat, 14 Nov 2026 15:04:06 GMT"

    @staticmethod
    def sha(body: bytes) -> str:
        return hashlib.sha256(body).hexdigest()

    def osv(self, answer: Any) -> Any:
        from supply_chain_io import Osv

        return Osv(Client(Recorder(answer), sleep=lambda _: None))

    def test_every_page_and_every_record_is_kept_in_the_order_received(self) -> None:
        first = json.dumps(
            {"results": [{"vulns": [{"id": "MAL-1"}], "next_page_token": "t"}]}
        ).encode("utf-8")
        second = json.dumps({"results": [{"vulns": [{"id": "MAL-2"}]}]}).encode("utf-8")
        record = b'{"id": "MAL-1"}'

        def answer(url: str) -> Response:
            if url.endswith("/v1/querybatch"):
                # the Recorder does not pass the body, so the second call is told by count
                calls = [u for u in net.urls if u.endswith("/v1/querybatch")]
                return Response(
                    200,
                    {"date": self.D1 if len(calls) == 1 else self.D2},
                    first if len(calls) == 1 else second,
                )
            return Response(200, {}, record)

        from supply_chain_io import Osv

        net = Recorder(answer)
        osv = Osv(Client(net, sleep=lambda _: None))
        self.assertEqual(osv.received, [])
        found = osv.query_purls(["pkg:npm/a@1"])
        osv.get_vuln("MAL-1")
        self.assertEqual(found, {"pkg:npm/a@1": ["MAL-1", "MAL-2"]})
        self.assertEqual(
            [(r.sha256, r.http_date) for r in osv.received],
            [
                (self.sha(first), self.D1),
                (self.sha(second), self.D2),
                (self.sha(record), None),
            ],
        )

    def test_a_response_that_did_not_arrive_is_not_kept(self) -> None:
        from supply_chain_io import TransportError

        def answer(url: str) -> Response:
            raise TransportError("connection reset")

        osv = self.osv(answer)
        with self.assertRaises(TransportError):
            osv.get_vuln("MAL-1")
        self.assertEqual(osv.received, [])

    def test_the_summary_is_the_hash_of_the_lines_of_hashes(self) -> None:
        from supply_chain_io import ReceivedBody, summarize_received

        a, b = "a" * 64, "b" * 64
        digest, date = summarize_received(
            [ReceivedBody(a, self.D1), ReceivedBody(b, self.D2)]
        )
        self.assertEqual(digest, self.sha(f"{a}\n{b}\n".encode()))
        self.assertEqual(date, self.D1)
        swapped, _ = summarize_received(
            [ReceivedBody(b, self.D2), ReceivedBody(a, self.D1)]
        )
        self.assertNotEqual(swapped, digest, "the order must change the value")
        self.assertEqual(summarize_received([]), (None, None))

    def test_the_date_is_that_of_the_first_response_even_when_it_has_none(self) -> None:
        from supply_chain_io import ReceivedBody, summarize_received

        _digest, date = summarize_received(
            [ReceivedBody("a" * 64, None), ReceivedBody("b" * 64, self.D2)]
        )
        self.assertIsNone(date)


if __name__ == "__main__":
    unittest.main()
