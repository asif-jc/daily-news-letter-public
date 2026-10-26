"""Execute the retained workflow, cache, history and resume in isolated SQL schemas."""

import os
from tests.database import database_url, drop_test_schema
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


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
        if task == "compare_event_pairs":
            return {
                "pairs": [
                    {
                        "id": p["id"],
                        "same_event": p["historical"],
                        "novelty": (
                            ("update" if "Updated" in p["left"]["title"] else "repeat")
                            if p["historical"]
                            else "new"
                        ),
                        "change": (
                            "A new council decision."
                            if p["historical"] and "Updated" in p["left"]["title"]
                            else ""
                        ),
                        "reason": "Compared the council decision.",
                    }
                    for p in data["pairs"]
                ]
            }
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
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        from news.store import NewsStore

        self.store = NewsStore(database_url(), schema="test_" + uuid.uuid4().hex[:12])
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
        drop_test_schema(self.store)

    def run_news(
        self, model, output, evidence_text="The council approved a flood map.", **kwargs
    ):
        from news.workflow import run_workflow

        with patch(
            "news.workflow.extract_article",
            return_value={
                "basis": "article_text",
                "status": "ok",
                "text": evidence_text,
            },
        ):
            return run_workflow(
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
                (Path(out) / edition["run_id"] / "assets/editorial-world.png").exists()
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

    def test_contradictory_group_is_retained_but_never_summarized_or_rendered(self):
        class ContradictoryPairs(Model):
            def complete(self, task, data, instructions=None):
                result = super().complete(task, data, instructions)
                if task == "compare_event_pairs":
                    for pair, verdict in zip(data["pairs"], result["pairs"]):
                        verdict["same_event"] = {
                            pair["left"]["id"],
                            pair["right"]["id"],
                        } != {"n1", "n3"}
                return result

        rows = [
            {**self.article, "id": id, "url": "https://bbc.com/" + id}
            for id in ("a", "b", "c")
        ]
        with tempfile.TemporaryDirectory() as out:
            model = ContradictoryPairs()
            with self.assertRaisesRegex(ValueError, "No reviewed reader stories"):
                self.run_news(model, out, rows=rows, now=self.now)
            run = str(
                self.store.connection.execute("SELECT id FROM runs").fetchone()["id"]
            )
            self.assertIsNone(self.store.stage_output(run, "edition"))
            events = self.store.stage_output(run, "group")
            self.assertEqual(len(events), 1)
            self.assertTrue(events[0]["grouping_conflicts"])
            held = self.store.stage_output(
                run, "summarize_event", events[0]["event_id"]
            )
            self.assertIn("Contradictory event comparisons", held["reason"])
            self.assertNotIn("synthesize", model.calls)
            self.assertFalse((Path(out) / run / "index.html").exists())

    def test_editorial_hold_preserves_analysis_but_excludes_source_and_preview_identity(
        self,
    ):
        rows = [self.article, {**self.article, "id": "b", "url": "https://bbc.com/b"}]
        holds = [
            {"article_id": "a", "reason": "The draft invents an unsupported unit."}
        ]
        with tempfile.TemporaryDirectory() as out:
            first = self.run_news(Model(), out, rows=rows, now=self.now)
            edition = self.run_news(
                Model(),
                out,
                rows=rows,
                now=self.now + timedelta(minutes=1),
                article_holds=holds,
                include_review_previews=True,
            )
            run = edition["run_id"]
            self.assertEqual(edition["counts"]["analysed"], 2)
            self.assertEqual(edition["counts"]["editorial_holds"], 1)
            self.assertEqual(
                self.store.stage_output(run, "analysis_index")["a"]["state"], "ready"
            )
            self.assertEqual(self.store.stage_output(run, "editorial_holds"), holds)
            self.assertEqual(
                {
                    i
                    for e in self.store.stage_output(run, "group")
                    for i in e["source_ids"]
                },
                {"b"},
            )
            self.assertTrue(
                all(s["id"] != "a" for e in edition["stories"] for s in e["sources"])
            )
            config = self.store.get_run(run)["config"]
            self.assertEqual(config["archives"], [])
            self.assertFalse(
                (Path(out) / run / "archive" / (first["run_id"] + ".html")).exists()
            )
            self.assertTrue(
                all(
                    s["id"] != "a"
                    for e in config["identity_history"]["stories"]
                    for s in e["sources"]
                )
            )
            self.assertIn(
                holds[0]["reason"], (Path(out) / run / "review.html").read_text()
            )
            with self.assertRaisesRegex(ValueError, "frozen"):
                self.run_news(Model(), out, run_id=run, article_holds=[])

    def test_unknown_editorial_hold_fails_instead_of_being_silently_ignored(self):
        with (
            tempfile.TemporaryDirectory() as out,
            self.assertRaisesRegex(ValueError, "Unknown held article"),
        ):
            self.run_news(
                Model(),
                out,
                rows=[self.article],
                now=self.now,
                article_holds=[{"article_id": "missing", "reason": "Bad source."}],
            )

    def test_hold_on_published_article_requires_separate_history_review(self):
        with tempfile.TemporaryDirectory() as out:
            first = self.run_news(Model(), out, rows=[self.article], now=self.now)
            self.store.connection.execute(
                "UPDATE editions SET status='published', published_at=%s WHERE run_id=%s",
                (self.now, first["run_id"]),
            )
            with self.assertRaisesRegex(ValueError, "published history"):
                self.run_news(
                    Model(),
                    out,
                    rows=[self.article],
                    now=self.now + timedelta(minutes=1),
                    article_holds=[{"article_id": "a", "reason": "Unsupported unit."}],
                )

    def test_all_failed_article_analysis_never_creates_ready_edition(self):
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaisesRegex(ValueError, "No reviewed reader stories"):
                self.run_news(
                    Model(), out, rows=[self.article], now=self.now, evidence_text=""
                )
            run = str(
                self.store.connection.execute("SELECT id FROM runs").fetchone()["id"]
            )
            self.assertIsNone(self.store.stage_output(run, "edition"))
            self.assertEqual(
                self.store.stage_output(run, "analysis_index")["a"]["state"],
                "unavailable",
            )
            self.assertFalse((Path(out) / run / "index.html").exists())

    def test_prototype_run_resume_is_explicitly_unsupported(self):
        from news.workflow import run_workflow

        run = self.store.create_run({"workflow_version": 2}, self.now)
        with (
            tempfile.TemporaryDirectory() as out,
            self.assertRaisesRegex(ValueError, "Unsupported workflow version"),
        ):
            run_workflow(self.store, Model(), out, run_id=run)

    def test_grouping_resume_reuses_validated_pair_batches(self):
        class InterruptedPairs(Model):
            def __init__(self):
                super().__init__()
                self.pair_calls = 0

            def complete(self, task, data, instructions=None):
                if task == "compare_event_pairs":
                    self.pair_calls += 1
                    if self.pair_calls == 2:
                        raise ValueError("Interrupted comparison")
                return super().complete(task, data, instructions)

        model = InterruptedPairs()
        rows = [
            {
                **self.article,
                "id": str(n),
                "url": "https://bbc.com/" + str(n),
                "title": "Council flood map decision " + str(n),
            }
            for n in range(13)
        ]
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaisesRegex(ValueError, "Interrupted comparison"):
                self.run_news(model, out, rows=rows, now=self.now)
            run = str(
                self.store.connection.execute("SELECT id FROM runs").fetchone()["id"]
            )
            result = self.run_news(model, out, run_id=run)
            self.assertEqual(len(result["stories"]), 13)
            self.assertEqual(model.pair_calls, 3)
            batches = self.store.connection.execute(
                "SELECT status FROM stages WHERE run_id=%s AND name='compare_event_pairs'",
                (run,),
            ).fetchall()
            self.assertEqual(len(batches), 2)
            self.assertTrue(all(b["status"] == "complete" for b in batches))

    def test_reconciled_history_keeps_any_prior_featured_identity(self):
        history = {
            "stories": [
                {
                    "event_id": id,
                    "title": "Council decision",
                    "summary": "Council approved the flood map.",
                    "featured": featured,
                    "sources": [{"id": "a", "url": self.article["url"]}],
                }
                for id, featured in [
                    ("newer-unfeatured", False),
                    ("older-featured", True),
                ]
            ]
        }
        with tempfile.TemporaryDirectory() as out:
            edition = self.run_news(
                Model(), out, rows=[self.article], now=self.now, history=history
            )
            self.assertEqual(edition["stories"][0]["event_id"], "newer-unfeatured")
            self.assertFalse(edition["stories"][0]["featured"])
            self.assertEqual(edition["stories"][0]["freshness"], "previously_featured")

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
            self.store.connection.execute(
                "UPDATE editions SET status='published',published_at=%s WHERE run_id=%s",
                (self.now + timedelta(hours=2), new["run_id"]),
            )
            changed = {
                **updated,
                "title": "Updated council construction rules",
                "description": "Council adopted new construction rules.",
            }
            later = self.run_news(
                m,
                out,
                rows=[changed],
                now=self.now + timedelta(hours=4),
                evidence_text="The council adopted new construction rules.",
            )
            self.assertEqual(later["stories"][0]["freshness"], "updated")
            self.assertNotEqual(
                new["stories"][0]["revision_key"], later["stories"][0]["revision_key"]
            )
