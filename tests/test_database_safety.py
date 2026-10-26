"""Reject integration-test connections before opening PostgreSQL."""

import unittest
from unittest.mock import patch

from tests.database import database_url


class DatabaseSafetyTests(unittest.TestCase):
    def test_only_explicit_loopback_news_database_is_accepted(self):
        for dsn in (
            "postgresql://localhost/news",
            "host=127.0.0.1 port=58471 dbname=news",
            "host=localhost hostaddr=127.0.0.1 dbname=news",
        ):
            with patch.dict("os.environ", {"NEWS_TEST_DATABASE_URL": dsn}):
                self.assertEqual(database_url(), dsn)

    def test_remote_hosts_database_override_and_services_are_rejected(self):
        for dsn in (
            "postgresql://localhost/production",
            "host=database.example dbname=news",
            "host=localhost hostaddr=192.0.2.1 dbname=news",
            "host=localhost dbname=news service=production",
            "postgresql://localhost/news?host=database.example",
        ):
            with patch.dict("os.environ", {"NEWS_TEST_DATABASE_URL": dsn}):
                with self.assertRaises(ValueError):
                    database_url()
