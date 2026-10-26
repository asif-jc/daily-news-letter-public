"""Verify citation provenance and explicit failure states through the retained workflow."""

import os
from tests.database import database_url, drop_test_schema
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


from tests.test_workflow import Model


class EventModel(Model):
    def __init__(self, reject=False):
        super().__init__()
        self.reject = reject
        self.synthesis_sources = []
        self.review_sources = []
        self.feedback = []

    def complete(self, task, data, instructions=None):
        if task == "compare_event_pairs":
            self.calls.append(task)
            return {
                "pairs": [
                    {
                        "id": p["id"],
                        "same_event": True,
                        "novelty": "repeat" if p["historical"] else "new",
                        "change": "",
                        "reason": "Same council decision.",
                    }
                    for p in data["pairs"]
                ]
            }
        if task == "synthesize":
            self.calls.append(task)
            self.synthesis_sources.append([item["id"] for item in data["evidence"]])
            self.feedback.append(data["event"].get("reviewer_feedback", ""))
            return {
                "summary": "The council approved the flood map.",
                "why_matters": "",
                "support": [{"section": "summary", "segment_id": "d:0"}],
            }
        if task == "review_event":
            self.calls.append(task)
            self.review_sources.append(
                [p["passage_id"].split(":")[0] for p in data["articles"][0]["passages"]]
            )
            return {
                "reviews": [
                    {
                        "id": data["articles"][0]["id"],
                        "verdict": "revise" if self.reject else "approved",
                        "reason": (
                            "Private reviewer: actor attribution unsupported."
                            if self.reject
                            else "Grounded."
                        ),
                    }
                ]
            }
        return super().complete(task, data, instructions=instructions)


class EventReviewRegressionTests(unittest.TestCase):
    def test_reviewer_receives_exact_synthesis_sources_with_representative_first(self):
        from news.synthesis import reviewed_event

        ids = ["a", "b", "c", "d"]
        event = {
            "event_id": "event",
            "source_ids": ids,
            "representative_id": "d",
            "title": "Council approves map",
            "novelty": "new",
            "change": "",
        }
        articles = {
            id: {
                "title": "Council approves map",
                "source": "BBC World News",
                "url": "https://bbc.com/" + id,
                "published": None,
            }
            for id in ids
        }
        evidence = {
            id: {"text": "The council approved the flood map.", "basis": "article_text"}
            for id in ids
        }
        model = EventModel()
        story = reviewed_event(event, {"tier": "include"}, articles, evidence, model)
        self.assertEqual(model.synthesis_sources, [["d", "a", "b", "c"]])
        self.assertEqual(model.review_sources, model.synthesis_sources)
        self.assertEqual(
            {s["id"] for s in story["sources"] if s["used_in_summary"]}, {"d"}
        )

    def test_optional_event_significance_can_be_omitted_after_repair(self):
        from news.synthesis import reviewed_event
        from unittest.mock import Mock

        model = Mock()

        def reply(task, data, instructions=None):
            if task == "synthesize":
                return {
                    "summary": "The council approved the map.",
                    "why_matters": "This guarantees prosperity.",
                    "support": [
                        {"section": "summary", "segment_id": "a:0"},
                        {"section": "why_matters", "segment_id": "a:0"},
                    ],
                }
            draft = data["articles"][0]["draft"]
            return {
                "reviews": [
                    {
                        "id": data["articles"][0]["id"],
                        "verdict": "revise" if draft["why_matters"] else "approved",
                        "reason": "Only the facts are supported.",
                        "unsupported_sections": (
                            ["why_matters"] if draft["why_matters"] else []
                        ),
                    }
                ]
            }

        model.complete.side_effect = reply
        event = {
            "event_id": "event",
            "title": "Council",
            "novelty": "new",
            "change": "",
            "source_ids": ["a"],
            "representative_id": "a",
        }
        article = {
            "a": {
                "title": "Council",
                "source": "BBC World News",
                "url": "https://bbc.com/a",
                "published": "2026-10-19T00:00:00Z",
            }
        }
        result = reviewed_event(
            event,
            {"tier": "include", "score": 8},
            article,
            {
                "a": {
                    "basis": "article_text",
                    "text": "The council approved the map.",
                    "status": "ok",
                }
            },
            model,
        )
        self.assertEqual(result["why_matters"], "")
        self.assertTrue(result["significance_omitted"])
        self.assertTrue(all(s["section"] == "summary" for s in result["support"]))

    def test_removed_significance_does_not_keep_its_source_marked_as_cited(self):
        from news.synthesis import reviewed_event
        from unittest.mock import Mock

        model = Mock()

        def reply(task, data, instructions=None):
            if task == "synthesize":
                return {
                    "summary": "The council approved the map.",
                    "why_matters": "This guarantees prosperity.",
                    "support": [
                        {"section": "summary", "segment_id": "a:0"},
                        {"section": "why_matters", "segment_id": "b:0"},
                    ],
                }
            why = data["articles"][0]["draft"]["why_matters"]
            return {
                "reviews": [
                    {
                        "id": data["articles"][0]["id"],
                        "verdict": "revise" if why else "approved",
                        "reason": "Facts supported.",
                        "unsupported_sections": ["why_matters"] if why else [],
                    }
                ]
            }

        model.complete.side_effect = reply
        event = {
            "event_id": "event",
            "title": "Council",
            "novelty": "new",
            "change": "",
            "source_ids": ["a", "b"],
            "representative_id": "a",
        }
        articles = {
            id: {
                "title": "Council",
                "source": "BBC World News",
                "url": "https://bbc.com/" + id,
                "published": "2026-10-19T00:00:00Z",
            }
            for id in ("a", "b")
        }
        evidence = {
            id: {
                "basis": "article_text",
                "text": "The council approved the map.",
                "status": "ok",
            }
            for id in articles
        }
        result = reviewed_event(
            event, {"tier": "include", "score": 8}, articles, evidence, model
        )
        self.assertEqual(
            {s["id"]: s["used_in_summary"] for s in result["sources"]},
            {"a": True, "b": False},
        )


@unittest.skipUnless(os.getenv("NEWS_TEST_DATABASE_URL"), "Set NEWS_TEST_DATABASE_URL")
class WorkflowSynthesisTests(unittest.TestCase):
    def setUp(self):
        from news.store import NewsStore

        self.store = NewsStore(database_url(), schema="test_" + uuid.uuid4().hex[:12])
        self.store.migrate()
        self.now = datetime(2026, 10, 19, tzinfo=timezone.utc)
        self.profile = {"id": "regression", "version": 2, "include": ["Politics"]}
        self.articles = [
            {
                "id": id,
                "title": "Council approves map",
                "source": "BBC World News",
                "category": "world",
                "url": "https://bbc.com/" + id,
                "published": self.now.isoformat(),
            }
            for id in ["a", "b", "c", "d"]
        ]

    def tearDown(self):
        drop_test_schema(self.store)

    def run_news(self, model, output, rows=None):
        from news.workflow import run_workflow

        with patch(
            "news.workflow.extract_article",
            return_value={
                "basis": "article_text",
                "status": "ok",
                "text": "The council approved the flood map.",
            },
        ):
            return run_workflow(
                self.store,
                model,
                output,
                now=self.now,
                rows=self.articles if rows is None else rows,
                profile=self.profile,
            )

    def test_workflow_preserves_only_actually_cited_source_flags(self):
        with tempfile.TemporaryDirectory() as output:
            edition = self.run_news(EventModel(), output)
            sources = edition["stories"][0]["sources"]
            self.assertEqual({s["id"] for s in sources}, {"a", "b", "c", "d"})
            self.assertEqual({s["id"] for s in sources if s["used_in_summary"]}, {"d"})
            self.assertEqual(
                {span["id"] for span in edition["stories"][0]["support"]}, {"d"}
            )

    def test_twice_rejected_event_is_visible_privately_and_absent_from_reader(self):
        model = EventModel(reject=True)
        with tempfile.TemporaryDirectory() as output:
            with self.assertRaisesRegex(ValueError, "No reviewed reader stories"):
                self.run_news(model, output)
            run = str(
                self.store.connection.execute("SELECT id FROM runs").fetchone()["id"]
            )
            events = self.store.stage_output(run, "group")
            failure = self.store.stage_output(
                run, "summarize_event", events[0]["event_id"]
            )
            self.assertEqual(failure["state"], "needs_review")
            self.assertEqual(model.calls.count("synthesize"), 2)
            self.assertEqual(model.calls.count("review_event"), 2)
            self.assertEqual(model.feedback[1], failure["review"])
            self.assertIsNone(self.store.stage_output(run, "edition"))
            self.assertFalse((Path(output) / run / "index.html").exists())

    def test_malformed_group_summary_is_held_while_other_story_survives(self):
        class MalformedGroup(EventModel):
            def complete(self, task, data, instructions=None):
                if task == "compare_event_pairs":
                    result = super().complete(task, data, instructions)
                    for pair, verdict in zip(data["pairs"], result["pairs"]):
                        verdict["same_event"] = {
                            pair["left"]["id"],
                            pair["right"]["id"],
                        } == {"n1", "n2"}
                    return result
                if task == "synthesize":
                    self.calls.append(task)
                    return {"summary": "The council approved the map.", "support": []}
                return super().complete(task, data, instructions)

        with tempfile.TemporaryDirectory() as output:
            model = MalformedGroup()
            edition = self.run_news(model, output, rows=self.articles[:3])
            self.assertEqual(edition["counts"]["stories"], 1)
            self.assertEqual(edition["counts"]["summary_failures"], 1)
            self.assertEqual(edition["stories"][0]["sources"][0]["id"], "c")
            self.assertEqual(model.calls.count("synthesize"), 2)
            self.assertTrue((Path(output) / edition["run_id"] / "index.html").exists())

    def test_current_collection_wins_over_equal_time_retained_metadata(self):
        current = {**self.articles[0], "title": "Current council decision"}
        retained = {**current, "title": "Obsolete council decision"}
        with (
            tempfile.TemporaryDirectory() as output,
            patch.object(self.store, "rolling_articles", return_value=[retained]),
        ):
            edition = self.run_news(Model(), output, rows=[current])
            pool = self.store.stage_output(edition["run_id"], "pool")
            self.assertEqual(len(pool["articles"]), 1)
            self.assertEqual(pool["articles"][0]["title"], "Current council decision")
            self.assertEqual(edition["stories"][0]["title"], "Current council decision")


class MalformedSynthesisTests(unittest.TestCase):
    def test_invalid_source_passage_is_repaired_once_or_held(self):
        from unittest.mock import Mock
        from news.synthesis import reviewed_event

        event = {
            "event_id": "event",
            "title": "Council decision",
            "novelty": "new",
            "change": "",
            "source_ids": ["a", "b"],
            "representative_id": "a",
        }
        articles = {
            key: {
                "title": "Council decision",
                "source": "BBC",
                "url": "https://www.bbc.com/" + key,
                "published": None,
            }
            for key in ("a", "b")
        }
        evidence = {
            key: {"text": "The council approved the map.", "basis": "article_text"}
            for key in articles
        }
        invalid = {
            "summary": "The council approved the map.",
            "support": [{"section": "summary", "segment_id": ["bad"]}],
        }
        valid = {
            "summary": "The council approved the map.",
            "support": [{"section": "summary", "segment_id": "a:0"}],
        }
        for repaired in (True, False):
            calls = []
            model = Mock()

            def reply(task, data, instructions=None):
                calls.append((task, data))
                if task == "synthesize":
                    return valid if repaired and len(calls) > 1 else invalid
                return {
                    "reviews": [
                        {
                            "id": data["articles"][0]["id"],
                            "verdict": "approved",
                            "reason": "Supported.",
                        }
                    ]
                }

            model.complete.side_effect = reply
            result = reviewed_event(
                event, {"tier": "include"}, articles, evidence, model
            )
            self.assertEqual(sum(task == "synthesize" for task, _ in calls), 2)
            self.assertIn(
                "Invalid event synthesis", calls[1][1]["event"]["reviewer_feedback"]
            )
            if repaired:
                self.assertEqual(result["summary"], valid["summary"])
            else:
                self.assertEqual(result["state"], "needs_review")

    def test_synthesis_derives_citations_from_bounded_source_passages(self):
        from unittest.mock import Mock
        from news.synthesis import synthesize_event

        event = {
            "event_id": "event",
            "title": "Council decision",
            "novelty": "new",
            "change": "",
            "source_ids": ["a", "b"],
            "representative_id": "a",
        }
        articles = {
            key: {
                "title": "Council decision",
                "source": "BBC",
                "url": "https://www.bbc.com/" + key,
                "published": None,
            }
            for key in ("a", "b")
        }
        evidence = {
            key: {
                "text": " ".join("word" + str(n) for n in range(70)),
                "basis": "article_text",
            }
            for key in articles
        }
        model = Mock()
        model.complete.return_value = {
            "summary": "Council decision.",
            "source_ids": ["b"],
            "support": [{"section": "summary", "segment_id": "a:1"}],
        }
        story = synthesize_event(event, {"tier": "include"}, articles, evidence, model)
        self.assertEqual(
            story["support"][0]["quote"],
            " ".join("word" + str(n) for n in range(25, 50)),
        )
        self.assertEqual(
            {source["id"] for source in story["sources"] if source["used_in_summary"]},
            {"a"},
        )
        payload = model.complete.call_args.args[1]["evidence"]
        self.assertTrue(all("text" not in article for article in payload))
        self.assertTrue(
            all(
                len(segment["text"].split()) <= 25
                for article in payload
                for segment in article["segments"]
            )
        )
