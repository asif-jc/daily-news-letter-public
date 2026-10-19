"""Exercise rolling retention without touching the live news schema."""

import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".local/news-test-db.env")


@unittest.skipUnless(
    os.getenv("NEWS_TEST_DATABASE_URL"),
    "Set NEWS_TEST_DATABASE_URL for PostgreSQL integration",
)
class LibraryDatabaseTests(unittest.TestCase):
    def setUp(self):
        from src.news.store import NewsStore

        self.store = NewsStore(
            os.environ["NEWS_TEST_DATABASE_URL"], schema="test_" + uuid.uuid4().hex[:12]
        )
        self.store.migrate()
        self.now = datetime(2026, 10, 19, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.store.close()

    def article(self, id="a", **fields):
        return {
            "id": id,
            "url": "https://example.com/" + id,
            "source": "BBC",
            "category": "world",
            "title": "Original title",
            "published": self.now.isoformat(),
            **fields,
        }

    def save(self, when, articles):
        run = self.store.create_run({}, when)
        self.store.save_articles(run, articles)
        return run

    def test_rolling_pool_uses_latest_observation_and_frozen_run_time(self):
        self.save(self.now - timedelta(days=2), [self.article(), self.article("b")])
        self.save(self.now - timedelta(days=1), [self.article(title="Latest title")])
        self.save(self.now + timedelta(seconds=1), [self.article(title="Future title")])
        result = {a["id"]: a for a in self.store.rolling_articles(self.now)}
        self.assertEqual(set(result), {"a", "b"})
        self.assertEqual(result["a"]["title"], "Latest title")
        self.assertEqual(self.store.counts()["observations"], 4)

    def test_pool_includes_updates_and_unknown_dates_but_not_old_or_future_dates(self):
        old = (self.now - timedelta(days=20)).isoformat()
        self.save(
            self.now,
            [
                self.article("old", published=old),
                self.article("updated", published=old, updated=self.now.isoformat()),
                self.article("unknown", published=None),
                self.article("invalid", published=None, updated="invalid"),
                self.article(
                    "future", published=(self.now + timedelta(days=1)).isoformat()
                ),
                self.article(
                    "boundary", published=(self.now - timedelta(days=7)).isoformat()
                ),
            ],
        )
        self.assertEqual(
            {a["id"] for a in self.store.rolling_articles(self.now)},
            {"updated", "unknown", "invalid", "boundary"},
        )

    def test_latest_metadata_cannot_resurrect_an_obsolete_observation(self):
        self.save(self.now - timedelta(days=1), [self.article()])
        self.save(
            self.now,
            [self.article(published=(self.now - timedelta(days=20)).isoformat())],
        )
        self.assertEqual(self.store.rolling_articles(self.now), [])

    def test_cache_exact_key_article_age_and_retained_payload(self):
        self.save(self.now, [self.article(), self.article("b")])
        payload = {
            "evidence": {"text": "Private evidence"},
            "analysis": {"summary": "Facts"},
        }
        self.store.save_analysis("a", "metadata-v1", payload)
        since = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.assertEqual(self.store.cached_analysis("a", "metadata-v1", since), payload)
        self.assertIsNone(self.store.cached_analysis("a", "metadata-v2", since))
        self.assertIsNone(self.store.cached_analysis("b", "metadata-v1", since))
        self.assertIsNone(
            self.store.cached_analysis("a", "metadata-v1", since + timedelta(days=1))
        )
        newer = {**payload, "analysis": {"summary": "Updated facts"}}
        self.store.save_analysis("a", "metadata-v1", newer)
        self.assertEqual(self.store.cached_analysis("a", "metadata-v1", since), newer)
        self.assertEqual(self.store.counts()["article_analyses"], 2)
        self.assertEqual(self.store.stats()["rows"]["article_analyses"], 2)

    def test_review_history_is_profile_scoped_immutable_and_not_publication(self):
        for offset, profile, status in [
            (-2, "asif", "published"),
            (-1, "asif", "ready_for_review"),
            (0, "other", "published"),
            (1, "asif", "published"),
        ]:
            when = self.now + timedelta(days=offset)
            run = self.store.create_run({}, when)
            payload = {
                "generated_at": when.isoformat(),
                "stories": [{"event_id": str(offset)}],
            }
            self.store.save_edition(run, payload, {"id": profile})
            self.store.save_edition(run, {"stories": []}, {"id": profile})
            if status == "published":
                self.store.connection.execute(
                    "UPDATE editions SET status='published',published_at=%s WHERE run_id=%s",
                    (when, run),
                )
        history = self.store.recent_editions("asif", now=self.now)
        self.assertEqual([e["stories"][0]["event_id"] for e in history], ["-1", "-2"])
        self.assertEqual(
            [e["publication_status"] for e in history],
            ["ready_for_review", "published"],
        )
        self.assertEqual(len(self.store.recent_editions("asif", limit=1)), 1)
        self.assertTrue(all("run_id" in e for e in history))
        self.assertNotIn(
            "-1",
            [s["event_id"] for s in self.store.published_history("asif")["stories"]],
        )

    def test_history_orders_by_generation_time_and_excludes_future_snapshots(self):
        for offset, generated_offset in [(-3, -1), (-2, -2), (-1, 1)]:
            run = self.store.create_run({}, self.now + timedelta(days=offset))
            self.store.save_edition(
                run,
                {
                    "generated_at": (
                        self.now + timedelta(days=generated_offset)
                    ).isoformat(),
                    "stories": [{"event_id": str(generated_offset)}],
                },
                {"id": "asif"},
            )
        history = self.store.recent_editions("asif", now=self.now)
        self.assertEqual([e["stories"][0]["event_id"] for e in history], ["-1", "-2"])
        self.assertEqual(self.store.recent_editions("asif", limit=0), [])

    def test_published_history_uses_run_generation_and_publication_cutoffs(self):
        cases = [
            ("past", -2, -2, -1),
            ("late_publication", -2, -2, 1),
            ("late_generation", -2, 1, -1),
            ("future_run", 1, -2, -1),
            ("missing_publication", -2, -2, None),
            ("legacy_generation", -2, None, -1),
            ("invalid_generation", -2, "invalid", -1),
        ]
        for name, run_offset, generated_offset, published_offset in cases:
            run = self.store.create_run({}, self.now + timedelta(days=run_offset))
            payload = {"stories": [{"event_id": name}]}
            if isinstance(generated_offset, int):
                payload["generated_at"] = (
                    self.now + timedelta(days=generated_offset)
                ).isoformat()
            elif generated_offset is not None:
                payload["generated_at"] = generated_offset
            self.store.save_edition(run, payload, {"id": "asif"})
            self.store.connection.execute(
                "UPDATE editions SET status='published',published_at=%s WHERE run_id=%s",
                (
                    (
                        self.now + timedelta(days=published_offset)
                        if published_offset is not None
                        else None
                    ),
                    run,
                ),
            )
        visible = self.store.published_history("asif", now=self.now)["stories"]
        self.assertEqual(
            {s["event_id"] for s in visible},
            {"past", "legacy_generation", "invalid_generation"},
        )
        self.assertEqual(
            self.store.published_history("asif"),
            self.store.published_history("asif", now=None),
        )
        self.assertEqual(len(self.store.published_history("asif")["stories"]), 7)

    def test_recent_editions_exposes_serializable_authoritative_publication_time(self):
        run = self.store.create_run({}, self.now)
        self.store.save_edition(
            run, {"stories": [], "published_at": "untrusted"}, {"id": "asif"}
        )
        self.assertIsNone(self.store.recent_editions("asif")[0]["published_at"])
        self.store.connection.execute(
            "UPDATE editions SET status='published',published_at=%s WHERE run_id=%s",
            (self.now, run),
        )
        edition = self.store.recent_editions("asif")[0]
        self.assertEqual(datetime.fromisoformat(edition["published_at"]), self.now)
        import json

        json.dumps(edition)

    def test_additive_migration_preserves_version_one_data(self):
        from psycopg import sql
        from src.news.store import NewsStore

        old = NewsStore(
            os.environ["NEWS_TEST_DATABASE_URL"], schema="test_" + uuid.uuid4().hex[:12]
        )
        try:
            old.connection.execute(
                sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(old.schema))
            )
            old.connection.execute(Path("src/news/migrations/001_news.sql").read_text())
            run = old.create_run({"workflow_version": 1}, self.now)
            old.save_articles(run, [self.article()])
            old.migrate()
            old.migrate()
            self.assertEqual(old.get_run(run)["config"]["workflow_version"], 1)
            self.assertEqual(old.observations(run)[0]["title"], "Original title")
            self.assertEqual(
                [
                    r["version"]
                    for r in old.connection.execute(
                        "SELECT version FROM schema_versions ORDER BY version"
                    )
                ],
                [1, 2],
            )
            self.assertEqual(old.counts()["article_analyses"], 0)
        finally:
            old.close()
