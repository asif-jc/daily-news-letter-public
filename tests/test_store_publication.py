"""Delivery metadata is transactional and cannot rewrite the saved edition."""

import os
import unittest
import uuid
from datetime import datetime, timezone, timedelta
from tests.database import database_url, drop_test_schema
from news.store import NewsStore


@unittest.skipUnless(
    os.getenv("NEWS_TEST_DATABASE_URL"), "Set an explicit loopback test database"
)
class PublicationStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = NewsStore(database_url(), schema="test_" + uuid.uuid4().hex[:12])
        self.store.migrate()
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        drop_test_schema(self.store)

    def edition(self, when):
        run = self.store.create_run({}, when)
        self.store.save_edition(
            run,
            {"run_id": run, "generated_at": when.isoformat(), "stories": []},
            {"id": "reader"},
        )
        self.store.finish_run(run)
        return run

    def test_verified_receipt_preserves_payload_and_publication_date_on_retry(self):
        run = self.edition(self.now)
        before = self.store.get_edition(run)
        receipt = {
            "public_url": "https://example.github.io/news/",
            "release_sha256": "a" * 64,
            "verified_at": self.now.isoformat(),
            "files_verified": 2,
        }
        self.store.record_publication(run, receipt)
        row = self.store.connection.execute(
            "SELECT status,published_at,payload FROM editions WHERE run_id=%s", (run,)
        ).fetchone()
        self.assertEqual(row["status"], "published")
        self.assertIsNotNone(row["published_at"])
        self.assertEqual(row["payload"]["stories"], before["stories"])
        self.assertEqual(
            self.store.record_publication(run, {**receipt, "verified_at": "later"}),
            receipt,
        )
        self.assertEqual(self.store.stage_output(run, "publication"), receipt)
        with self.assertRaises(ValueError):
            self.store.record_publication(run, {**receipt, "release_sha256": "b" * 64})
        self.assertEqual(
            row["published_at"],
            self.store.connection.execute(
                "SELECT published_at FROM editions WHERE run_id=%s", (run,)
            ).fetchone()["published_at"],
        )

    def test_calendar_window_keeps_more_than_seven_editions(self):
        for index in range(10):
            self.edition(self.now - timedelta(hours=index))
        self.edition(self.now - timedelta(days=8))
        self.assertEqual(len(self.store.editions_within("reader", self.now, 7)), 10)

    def test_presentation_receipts_preserve_content_and_first_publication(self):
        run = self.edition(self.now)
        first = {
            "public_url": "https://example.github.io/old/",
            "release_sha256": "a" * 64,
            "verified_at": self.now.isoformat(),
            "files_verified": 2,
        }
        with self.assertRaises(ValueError):
            self.store.record_presentation(run, first)
        self.store.record_publication(run, first)
        before_edition = self.store.connection.execute(
            'SELECT * FROM editions WHERE run_id=%s', (run,)
        ).fetchone()
        before_run = self.store.get_run(run)
        new = {**first, 'public_url': 'https://example.github.io/news/', 'release_sha256': 'b' * 64}
        receipt = self.store.record_presentation(run, new)
        self.assertEqual(receipt['publication_sha256'], first['release_sha256'])
        self.assertEqual(self.store.record_presentation(run, {**new, 'verified_at':'later'}), receipt)
        self.store.record_presentation(run, {**new, 'public_url':'https://example.github.io/new-url/'})
        self.store.record_presentation(run, {**new, 'release_sha256':'c' * 64})
        rows = self.store.connection.execute(
            "SELECT output FROM stages WHERE run_id=%s AND name='presentation'", (run,)
        ).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual(self.store.stage_output(run, 'publication'), first)
        self.assertEqual(self.store.get_run(run), before_run)
        self.assertEqual(self.store.connection.execute(
            'SELECT * FROM editions WHERE run_id=%s', (run,)
        ).fetchone(), before_edition)
