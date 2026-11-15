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


if __name__ == "__main__":
    unittest.main()
