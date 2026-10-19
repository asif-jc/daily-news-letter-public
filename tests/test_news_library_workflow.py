"""Execute the retained library workflow, cache, history and resume in isolated SQL schemas."""

import os
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from dotenv import load_dotenv

load_dotenv(".local/news-test-db.env")


class Model:
    model = "test-model"
    audit_hook = None

    def __init__(self):
        self.calls = []
        self.fail = False

    def complete(self, task, data, instructions=None):
        self.calls.append(task)
        if task == "analyse_articles":
            return {
                "articles": [
                    {
                        "id": a["id"],
                        "summary": a["passages"][0]["text"],
                        "why_matters": "",
                        "topics": ["Politics"],
                        "geography": ["NZ"],
                        "support": [
                            {
                                "section": "summary",
                                "passage_id": a["passages"][0]["passage_id"],
                            }
                        ],
                    }
                    for a in data["articles"]
                ]
            }
        if task in ("review_articles", "review_event"):
            return {
                "reviews": [
                    {"id": a["id"], "verdict": "approved", "reason": "Grounded."}
                    for a in data["articles"]
                ]
            }
        if task == "group_events":
            history = data["history"]
            if history and "Updated" in data["articles"][0]["title"]:
                return {
                    "events": [
                        {
                            "source_ids": [data["articles"][0]["id"]],
                            "representative_id": data["articles"][0]["id"],
                            "novelty": "update",
                            "previous_event_id": history[0]["event_id"],
                            "change": "A new council decision.",
                            "reason": "Same event with a new decision.",
                        }
                    ]
                }
            return {"events": []}
        if task == "curate_events":
            if self.fail:
                raise ValueError("Interrupted curation")
            return {
                "decisions": [
                    {
                        "id": e["id"],
                        "relevant": True,
                        "score": 8,
                        "importance": "notable",
                        "reason": "A public decision.",
                    }
                    for e in data["events"]
                ]
            }
        raise AssertionError(task)


@unittest.skipUnless(os.getenv("NEWS_TEST_DATABASE_URL"), "Set NEWS_TEST_DATABASE_URL")
class LibraryWorkflowTests(unittest.TestCase):
    def setUp(self):
        from src.news.store import NewsStore

        self.store = NewsStore(
            os.environ["NEWS_TEST_DATABASE_URL"], schema="test_" + uuid.uuid4().hex[:12]
        )
        self.store.migrate()
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.article = {
            "id": "a",
            "url": "https://bbc.com/a",
            "title": "Council decision",
            "source": "BBC World News",
            "category": "world",
            "description": "Council approved the map.",
            "published": (self.now - timedelta(days=3)).isoformat(),
            "published_basis": "published",
        }
        self.profile = {"id": "test", "version": 2, "include": ["Politics"]}

    def tearDown(self):
        self.store.close()

    def run_news(self, model, output, **kwargs):
        from src.news.library import run_library_workflow

        with patch(
            "src.news.library.extract_article",
            return_value={
                "basis": "article_text",
                "status": "ok",
                "text": "The council approved a flood map.",
            },
        ):
            return run_library_workflow(
                self.store, model, output, profile=self.profile, **kwargs
            )

    def test_old_article_is_understood_shown_and_replayed_without_calls(self):
        m = Model()
        with tempfile.TemporaryDirectory() as out:
            edition = self.run_news(m, out, rows=[self.article], now=self.now)
            self.assertEqual(edition["counts"]["analysed"], 1)
            self.assertEqual(edition["stories"][0]["freshness"], "catch_up")
            before = list(m.calls)
            again = self.run_news(m, out, run_id=edition["run_id"])
            self.assertEqual(edition, again)
            self.assertEqual(m.calls, before)
            self.assertTrue(
                (Path(out) / edition["run_id"] / "assets/dunder_park.jpg").exists()
            )
            second = self.run_news(
                m, out, rows=[self.article], now=self.now + timedelta(hours=1)
            )
            self.assertEqual(m.calls.count("analyse_articles"), 1)
            archived = (
                Path(out) / second["run_id"] / "archive" / f'{edition["run_id"]}.html'
            )
            self.assertFalse(archived.exists())
            preview = self.run_news(
                m,
                out,
                rows=[self.article],
                now=self.now + timedelta(hours=2),
                include_review_previews=True,
            )
            self.assertTrue(
                (
                    Path(out)
                    / preview["run_id"]
                    / "archive"
                    / f'{second["run_id"]}.html'
                ).exists()
            )

    def test_next_day_repeat_is_browsable_without_being_featured_again(self):
        m = Model()
        with tempfile.TemporaryDirectory() as out:
            first = self.run_news(m, out, rows=[self.article], now=self.now)
            self.store.connection.execute(
                "UPDATE editions SET status='published', published_at=%s WHERE run_id=%s",
                (self.now, first["run_id"]),
            )
            tomorrow = self.run_news(
                m, out, rows=[self.article], now=self.now + timedelta(days=1)
            )
            self.assertEqual(len(tomorrow["stories"]), 1)
            self.assertFalse(tomorrow["stories"][0]["featured"])
            self.assertEqual(tomorrow["stories"][0]["freshness"], "previously_featured")
            archive = (
                Path(out) / tomorrow["run_id"] / "archive" / (first["run_id"] + ".html")
            )
            self.assertTrue(archive.exists())
            self.assertIn("Published edition", archive.read_text())
            self.store.connection.execute(
                "UPDATE editions SET status='published', published_at=%s WHERE run_id=%s",
                (self.now + timedelta(days=1), tomorrow["run_id"]),
            )
            third = self.run_news(
                m, out, rows=[self.article], now=self.now + timedelta(days=2)
            )
            self.assertFalse(third["stories"][0]["featured"])
            self.assertEqual(third["stories"][0]["freshness"], "previously_featured")

    def test_failure_resumes_analyses_and_update_since_publication_can_feature(self):
        m = Model()
        m.fail = True
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaisesRegex(ValueError, "Interrupted"):
                self.run_news(m, out, rows=[self.article], now=self.now)
            run = str(
                self.store.connection.execute(
                    "SELECT id FROM runs WHERE config->'profile'->>'id'='test'"
                ).fetchone()["id"]
            )
            m.fail = False
            edition = self.run_news(m, out, run_id=run)
            self.assertEqual(m.calls.count("analyse_articles"), 1)
            self.store.connection.execute(
                "UPDATE editions SET status='published',published_at=%s WHERE run_id=%s",
                (self.now, run),
            )
            updated = {
                **self.article,
                "title": "Updated council decision",
                "updated": (self.now + timedelta(hours=1)).isoformat(),
            }
            new = self.run_news(
                m, out, rows=[updated], now=self.now + timedelta(hours=2)
            )
            self.assertTrue(new["stories"][0]["featured"])
            self.assertEqual(new["stories"][0]["freshness"], "updated")
            # Previewing that update must not suppress it relative to the older published version.
            preview = self.run_news(
                m, out, rows=[updated], now=self.now + timedelta(hours=3)
            )
            self.assertTrue(preview["stories"][0]["featured"])
            self.assertEqual(preview["stories"][0]["freshness"], "updated")
