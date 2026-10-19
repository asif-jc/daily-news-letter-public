"""Exercise retained data and checkpoints against an explicitly configured test schema."""

import os
import unittest
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(".local/news-test-db.env")


@unittest.skipUnless(
    os.getenv("NEWS_TEST_DATABASE_URL"),
    "Set NEWS_TEST_DATABASE_URL for PostgreSQL integration",
)
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        from src.news.store import NewsStore

        self.store = NewsStore(
            os.environ["NEWS_TEST_DATABASE_URL"], schema="test_" + uuid.uuid4().hex[:12]
        )
        self.store.migrate()

    def tearDown(self):
        self.store.close()

    def test_migration_repeats_without_changing_records(self):
        run = self.store.create_run(
            {"profile": {"id": "asif", "version": 1}}, datetime.now(timezone.utc)
        )
        self.store.migrate()
        self.assertEqual(self.store.get_run(run)["config"]["profile"]["id"], "asif")

    def test_reingestion_keeps_identity_and_each_observation(self):
        article = {
            "id": "a",
            "source": "BBC",
            "category": "world",
            "title": "First",
            "url": "https://www.bbc.com/news/a",
            "published": None,
            "published_basis": "unknown",
        }
        first = self.store.create_run({}, datetime.now(timezone.utc))
        second = self.store.create_run({}, datetime.now(timezone.utc))
        self.store.save_articles(first, [article])
        self.store.save_articles(second, [{**article, "title": "Changed"}])
        self.assertEqual(self.store.counts()["articles"], 1)
        self.assertEqual(self.store.counts()["observations"], 2)
        self.assertEqual(self.store.observations(first)[0]["title"], "First")

    def test_checkpoint_completion_is_immutable_and_resumable(self):
        run = self.store.create_run({}, datetime.now(timezone.utc))
        self.store.start_stage(run, "collect")
        self.store.complete_stage(run, "collect", {"articles": []})
        self.assertEqual(self.store.stage_output(run, "collect"), {"articles": []})
        with self.assertRaises(ValueError):
            self.store.complete_stage(run, "collect", {"articles": ["replacement"]})

    def test_run_lock_rejects_another_connection(self):
        from src.news.store import NewsStore

        run = self.store.create_run({}, datetime.now(timezone.utc))
        other = NewsStore(
            os.environ["NEWS_TEST_DATABASE_URL"], schema=self.store.schema
        )
        try:
            with self.store.lock_run(run):
                with self.assertRaises(RuntimeError), other.lock_run(run):
                    pass
        finally:
            other.close()

    def test_wrong_database_refused(self):
        from src.news.store import NewsStore
        from psycopg.conninfo import make_conninfo

        with self.assertRaises(ValueError):
            NewsStore(
                make_conninfo(os.environ["NEWS_TEST_DATABASE_URL"], dbname="propley")
            )


@unittest.skipUnless(
    os.getenv("NEWS_TEST_DATABASE_URL"),
    "Set NEWS_TEST_DATABASE_URL for PostgreSQL integration",
)
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        from src.news.store import NewsStore

        self.store = NewsStore(
            os.environ["NEWS_TEST_DATABASE_URL"], schema="test_" + uuid.uuid4().hex[:12]
        )
        self.store.migrate()

    def tearDown(self):
        self.store.close()

    def test_interrupted_run_resumes_completed_stages_and_renders(self):
        from src.news.workflow import run_workflow
        from src.news.llm import JsonModel
        from tests.test_news import article
        from unittest.mock import patch
        import tempfile

        now = datetime.now(timezone.utc)
        row = article(published=now.isoformat(), url="https://www.bbc.com/news/test")

        class Model:
            model = "test"
            calls = 0
            audit_hook = None
            fail = True

            def complete(self, task, data):
                self.calls += 1
                if task == "group_events":
                    return {"events": []}
                if task == "qualify_events":
                    if self.fail:
                        raise RuntimeError("Controlled interruption")
                    return {
                        "qualifications": [
                            {
                                "event_id": e["event_id"],
                                "tag": "relevant",
                                "reason": "Policy finding",
                            }
                            for e in data["events"]
                        ]
                    }
                if task == "select_with_evidence":
                    return {
                        "decisions": [
                            {
                                "event_id": e["event_id"],
                                "tier": "top",
                                "score": 8,
                                "topic": "Policy",
                                "reason": "Useful development",
                                "decision_basis": "selected",
                            }
                            for e in data["events"]
                        ]
                    }
                return {
                    "summary": "The policy changed. It applies tomorrow.",
                    "why_matters": "",
                    "support": [{"section": "summary", "segment_id": "a:0"}],
                }

        model = Model()
        with tempfile.TemporaryDirectory() as tmp, patch(
            "src.news.workflow.collect_articles",
            return_value=([row], [{"source": "Example", "status": "ok"}]),
        ) as collect, patch(
            "src.news.workflow.extract_article",
            return_value={
                "text": "The policy changed and applies tomorrow.",
                "basis": "article_text",
                "status": "ok",
            },
        ) as extract:
            with self.assertRaises(RuntimeError):
                run_workflow(self.store, model, tmp, now=now)
            run = str(
                self.store.connection.execute("SELECT id FROM runs").fetchone()["id"]
            )
            self.assertEqual(self.store.get_run(run)["status"], "failed")
            model.fail = False
            result = run_workflow(self.store, model, tmp, run_id=run)
            self.assertEqual(result["status"], "ready_for_review")
            self.assertEqual(collect.call_count, 1)
            self.assertEqual(extract.call_count, 1)
            calls = model.calls
            run_workflow(self.store, model, tmp, run_id=run)
            self.assertEqual(model.calls, calls)
            self.assertEqual(self.store.counts()["observations"], 1)
            self.assertEqual(
                self.store.connection.execute(
                    "SELECT count(*) AS n FROM storage_samples"
                ).fetchone()["n"],
                1,
            )
            from pathlib import Path

            self.assertTrue((Path(tmp) / run / "index.html").exists())
            self.assertEqual(
                (Path(tmp) / run / "assets" / "dunder_park.jpg").read_bytes(),
                Path("assets/dunder_park.jpg").read_bytes(),
            )
            self.assertTrue((Path(tmp) / run / "review.html").exists())
            with patch(
                "pathlib.Path.write_text", side_effect=OSError("Disk interruption")
            ), self.assertRaises(OSError):
                run_workflow(self.store, model, tmp, run_id=run)
            self.assertEqual(self.store.get_run(run)["status"], "failed")
            self.assertEqual(self.store.get_run(run)["stage"], "export")
            failure = self.store.connection.execute(
                "SELECT output FROM stages WHERE run_id=%s AND name='export' AND status='failed'",
                (run,),
            ).fetchone()
            self.assertEqual(failure["output"]["error_message"], "Disk interruption")
            run_workflow(self.store, model, tmp, run_id=run)
            self.assertEqual(model.calls, calls)
            self.assertEqual(self.store.get_run(run)["status"], "ready_for_review")

    def test_transaction_rollback_does_not_leave_a_completed_stage(self):
        run = self.store.create_run({}, datetime.now(timezone.utc))
        self.store.start_stage(run, "collect")
        with self.assertRaises(RuntimeError), self.store.transaction():
            self.store.complete_stage(run, "collect", {"items": []})
            raise RuntimeError("Rollback")
        self.assertIsNone(self.store.stage_output(run, "collect"))

    def test_duplicate_url_exclusion_marks_only_the_duplicate_observation(self):
        from src.news.events import filter_candidates

        now = datetime.now(timezone.utc)
        row = {
            "id": "same",
            "source": "BBC",
            "category": "world",
            "title": "Policy",
            "url": "https://www.bbc.com/news/one",
            "published": now.isoformat(),
        }
        run = self.store.create_run({}, now)
        observations = [row, {**row, "url": row["url"] + "?utm_source=rss"}]
        self.store.save_articles(run, observations)
        candidates, exclusions = filter_candidates(observations, now)
        self.store.save_filter(run, candidates, exclusions)
        actual = list(
            self.store.connection.execute(
                "SELECT eligibility FROM observations WHERE run_id=%s ORDER BY ordinal",
                (run,),
            )
        )
        self.assertEqual(
            [r["eligibility"] for r in actual], ["eligible", "duplicate_url"]
        )

    def test_replay_input_survives_failure_before_collection_checkpoint(self):
        from src.news.workflow import run_workflow
        from unittest.mock import Mock, patch
        import tempfile

        row = {
            "id": "a",
            "source": "BBC",
            "category": "world",
            "title": "Policy",
            "url": "https://www.bbc.com/news/one",
            "published": datetime.now(timezone.utc).isoformat(),
        }
        model = Mock(model="test")
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(
                self.store,
                "save_articles",
                side_effect=RuntimeError("Storage interruption"),
            ), self.assertRaises(RuntimeError):
                run_workflow(self.store, model, tmp, rows=[row])
            run = str(
                self.store.connection.execute("SELECT id FROM runs").fetchone()["id"]
            )
            model.complete.side_effect = RuntimeError("Stop after saved collection")
            with patch(
                "src.news.workflow.collect_articles"
            ) as collect, self.assertRaises(RuntimeError):
                run_workflow(self.store, model, tmp, run_id=run)
            collect.assert_not_called()
            self.assertEqual(self.store.observations(run)[0]["title"], "Policy")

    def test_render_failure_is_saved_and_can_resume_without_model_calls(self):
        from src.news.workflow import run_workflow
        from unittest.mock import Mock, patch
        import tempfile, json
        from pathlib import Path

        now = datetime.now(timezone.utc)
        profile = {"id": "test", "version": 1}
        from src.news.llm import INSTRUCTIONS, prompt_versions

        config = {
            "workflow_version": 1,
            "profile": profile,
            "prompts": INSTRUCTIONS,
            "prompt_versions": prompt_versions(),
            "model": "test",
            "top_limit": 1,
            "quick_limit": 1,
            "history": {},
            "input_mode": "replay",
            "replay_input": None,
        }
        run = self.store.create_run(config, now)
        article = {
            "id": "a",
            "source": "BBC",
            "category": "world",
            "title": "Policy",
            "url": "https://www.bbc.com/news/a",
            "published": now.isoformat(),
        }
        event = {
            "event_id": "event",
            "source_ids": ["a"],
            "representative_id": "a",
            "title": "Policy",
            "novelty": "new",
            "reason": "One event",
        }
        qualification = {
            "event_id": "event",
            "tag": "relevant",
            "reason": "Policy",
            "decision_basis": "profile",
        }
        decision = {
            "event_id": "event",
            "tier": "top",
            "score": 8,
            "topic": "Policy",
            "reason": "Useful",
            "decision_basis": "selected",
        }
        story = {
            **event,
            **decision,
            "summary": "Policy changed.",
            "why_matters": "",
            "support": [],
            "sources": [{"source": "BBC", "url": article["url"]}],
        }
        outputs = {
            "collect": {"articles": [article], "source_health": []},
            "clean": {
                "candidates": [{**article, "observation_ordinal": 0}],
                "exclusions": [],
            },
            "group": [event],
            "qualify": [qualification],
            "retrieve": {"a": {"basis": "article_text", "text": "Policy changed."}},
            "select": [decision],
            "synthesize": [story],
        }
        for name, value in outputs.items():
            self.store.start_stage(run, name)
            self.store.complete_stage(run, name, value)
        model = Mock(model="test")
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "src.news.workflow.render_edition",
                side_effect=OSError("Disk simulation"),
            ), self.assertRaises(OSError):
                run_workflow(self.store, model, tmp, run_id=run)
            self.assertEqual(self.store.get_run(run)["status"], "failed")
            self.assertEqual(self.store.get_run(run)["stage"], "render")
            run_workflow(self.store, model, tmp, run_id=run)
            model.complete.assert_not_called()
            self.assertTrue((Path(tmp) / run / "index.html").exists())

    def test_failure_retains_actionable_validation_detail_privately(self):
        run = self.store.create_run({}, datetime.now(timezone.utc))
        self.store.start_stage(run, "qualify")
        self.store.fail_stage(run, "qualify", ValueError("Missing an event decision"))
        row = self.store.connection.execute(
            "SELECT output FROM stages WHERE run_id=%s", (run,)
        ).fetchone()
        self.assertEqual(row["output"]["error_message"], "Missing an event decision")
        self.assertIsNone(self.store.stage_output(run, "qualify"))

    def test_all_irrelevant_events_still_retain_final_exclusions(self):
        from src.news.workflow import run_workflow
        from unittest.mock import patch
        import tempfile

        now = datetime.now(timezone.utc)
        row = {
            "id": "a",
            "source": "BBC",
            "category": "world",
            "title": "Sports result",
            "url": "https://www.bbc.com/news/a",
            "published": now.isoformat(),
        }

        class Model:
            model = "test"
            audit_hook = None

            def complete(self, task, data):
                if task == "group_events":
                    return {"events": []}
                if task == "qualify_events":
                    return {
                        "qualifications": [
                            {
                                "event_id": e["event_id"],
                                "tag": "irrelevant",
                                "reason": "Sports result outside profile",
                            }
                            for e in data["events"]
                        ]
                    }
                raise AssertionError("No selection/synthesis should run")

        with tempfile.TemporaryDirectory() as tmp, patch(
            "src.news.workflow.collect_articles", return_value=([row], [])
        ):
            with self.assertRaises(ValueError):
                run_workflow(self.store, Model(), tmp)
        rows = list(
            self.store.connection.execute(
                "SELECT tier,basis FROM decisions WHERE phase='select'"
            )
        )
        self.assertEqual(rows, [{"tier": "exclude", "basis": "off_brief"}])


@unittest.skipUnless(
    os.getenv("NEWS_TEST_DATABASE_URL"),
    "Set NEWS_TEST_DATABASE_URL for PostgreSQL integration",
)
class PublishedHistoryTests(unittest.TestCase):
    setUp = DatabaseTests.setUp
    tearDown = DatabaseTests.tearDown

    def test_history_is_profile_scoped_and_generation_is_not_publication(self):
        now = datetime.now(timezone.utc)
        first = self.store.create_run({}, now)
        second = self.store.create_run({}, now)
        self.store.save_edition(
            first,
            {"stories": [{"event_id": "one", "title": "A", "summary": "Facts"}]},
            {"id": "first"},
        )
        self.store.save_edition(
            second,
            {"stories": [{"event_id": "two", "title": "B", "summary": "Facts"}]},
            {"id": "second"},
        )
        self.assertEqual(self.store.published_history("first")["stories"], [])
        self.store.connection.execute(
            "UPDATE editions SET status='published',published_at=now() WHERE run_id=%s",
            (first,),
        )
        self.assertEqual(
            [s["event_id"] for s in self.store.published_history("first")["stories"]],
            ["one"],
        )
        self.assertEqual(self.store.published_history("second")["stories"], [])


if __name__ == "__main__":
    unittest.main()
