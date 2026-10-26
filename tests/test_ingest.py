import unittest
from unittest.mock import Mock, patch


def article(**changes):
    return {"description": "Feed evidence.", **changes}


class RetrievalTests(unittest.TestCase):
    def test_model_rejects_truncation_and_does_not_expose_endpoint_in_errors(self):
        from news.llm import JsonModel

        response = Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"finish_reason": "length", "message": {"content": None}}]
        }
        model = JsonModel("http://localhost:1/v1", "test")
        with (
            patch("news.llm.requests.post", return_value=response),
            self.assertRaises(ValueError),
        ):
            model.complete("test", {})
        import requests

        with (
            patch(
                "news.llm.requests.post",
                side_effect=requests.ConnectionError("private endpoint"),
            ),
            self.assertRaisesRegex(
                RuntimeError, "^Model request failed: ConnectionError$"
            ),
        ):
            model.complete("test", {})

    def test_extraction_never_requests_an_unapproved_host(self):
        from news.ingest import extract_article

        with patch("news.ingest.requests.get") as get:
            result = extract_article(article(url="http://localhost/private"))
        get.assert_not_called()
        self.assertEqual(result["basis"], "feed_summary")

    def test_publisher_redirect_cannot_fetch_private_service(self):
        from news.ingest import extract_article

        response = Mock(
            status_code=302, headers={"Location": "http://localhost/private"}
        )
        with patch("news.ingest.requests.get", return_value=response) as get:
            result = extract_article(article(url="https://www.bbc.com/news/example"))
        self.assertEqual(get.call_count, 1)
        self.assertEqual(result["status"], "unapproved_host")

    def test_download_stops_reading_at_byte_limit_and_closes_response(self):
        from news.ingest import download_public
        from news.sources import PUBLISHER_HOSTS

        response = Mock(status_code=200)
        response.iter_content.return_value = iter([b"1234", b"5678", b"never read"])
        with (
            patch("news.ingest.requests.get", return_value=response) as get,
            patch("news.ingest.MAX_DOWNLOAD_BYTES", 6),
        ):
            with self.assertRaisesRegex(ValueError, "download_too_large"):
                download_public(
                    "https://www.rnz.co.nz/news/political/1", PUBLISHER_HOSTS
                )
        self.assertTrue(get.call_args.kwargs["stream"])
        self.assertEqual(next(response.iter_content.return_value), b"never read")
        response.close.assert_called_once()

    def test_feed_redirect_and_unapproved_catalog_cannot_fetch_private_service(self):
        from news.ingest import collect_articles

        response = Mock(
            status_code=302, headers={"Location": "http://127.0.0.1/private"}
        )
        for initial in (
            "http://127.0.0.1/feed",
            "https://www.rnz.co.nz/rss/political.xml",
        ):
            with patch("news.ingest.requests.get", return_value=response) as get:
                articles, health = collect_articles(
                    {"nz": [{"name": "Test", "url": initial}]}
                )
            self.assertEqual(articles, [])
            self.assertEqual(health[0]["status"], "error")
            self.assertEqual(get.call_count, int(initial.startswith("https:")))

    def test_publisher_links_reject_credentials_ports_and_private_hosts(self):
        from news.urls import allowed_publisher_url
        from news.render import reader_snapshot

        for url in (
            "http://localhost/news",
            "http://127.0.0.1/",
            "https://rnz.co.nz:8000/news",
            "https://rnz.co.nz.evil.example/news",
            "https://user:pass@rnz.co.nz/news",
        ):
            self.assertFalse(allowed_publisher_url(url))
            self.assertEqual(
                reader_snapshot({"stories": [{"sources": [{"url": url}]}]})["stories"][
                    0
                ]["sources"],
                [],
            )
        self.assertTrue(allowed_publisher_url("https://www.rnz.co.nz/news/political/1"))

    def test_collector_identity_ignores_tracking_and_preserves_unknown_dates(self):
        from news.ingest import collect_articles

        xml = b"""<rss version="2.0"><channel><title>News</title>
        <item><title>A decision</title><link>https://www.rnz.co.nz/news/1?utm_source=rss</link><description>Useful feed evidence.</description></item>
        <item><title>Same decision</title><link>https://www.rnz.co.nz/news/1</link><description>Useful feed evidence.</description></item>
        </channel></rss>"""
        response = Mock(status_code=200)
        response.iter_content.return_value = iter([xml])
        with patch("news.ingest.requests.get", return_value=response):
            articles, health = collect_articles(
                {
                    "nz": [
                        {
                            "name": "RNZ Politics",
                            "url": "https://www.rnz.co.nz/rss/political.xml",
                        }
                    ]
                }
            )
        self.assertEqual(health[0]["status"], "ok")
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]["id"], articles[1]["id"])
        self.assertIsNone(articles[0]["published"])
        self.assertEqual(articles[0]["published_basis"], "unknown")
        self.assertEqual(articles[0]["description"], "Useful feed evidence.")
