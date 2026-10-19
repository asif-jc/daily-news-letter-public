import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

NOW = datetime(2026, 10, 17, 0, tzinfo=timezone.utc)


def article(id="a", **changes):
    return {
        "id": id,
        "url": f"https://example.com/{id}",
        "title": f"Story {id}",
        "description": "Brief useful evidence.",
        "source": "Example",
        "category": "tech",
        "published": NOW.isoformat(),
        **changes,
    }


class ReplyModel:
    def __init__(self, reply):
        self.reply = reply

    def complete(self, task, data):
        return self.reply


class NewsTests(unittest.TestCase):
    def test_only_four_approved_sources(self):
        from src.mvp_news_aggregator.sources import RSS_FEEDS

        self.assertEqual(
            {s["name"] for feeds in RSS_FEEDS.values() for s in feeds},
            {"BBC World News", "Ars Technica", "TechCrunch", "CNBC Finance"},
        )

    def test_unknown_future_and_old_dates_are_not_fresh(self):
        from src.news.events import filter_candidates

        rows = [
            article(),
            article("b", published=None),
            article("c", published="2026-10-18T00:00:00Z"),
            article("d", published="2026-10-14T00:00:00Z"),
        ]
        accepted, excluded = filter_candidates(rows, NOW)
        self.assertEqual([a["id"] for a in accepted], ["a"])
        self.assertEqual(
            {r["reason"] for r in excluded},
            {"unknown_date", "future_date", "outside_window"},
        )

    def test_short_descriptions_survive_and_tracking_urls_deduplicate(self):
        from src.news.events import filter_candidates

        rows = [
            article(
                "a",
                url="https://example.com/story?utm_source=rss",
                description="Policy changed.",
            ),
            article(
                "b", url="https://example.com/story", description="Policy changed."
            ),
        ]
        accepted, excluded = filter_candidates(rows, NOW)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(excluded[0]["reason"], "duplicate_url")

    def test_group_partition_preserves_supporting_sources(self):
        from src.news.events import group_events

        rows = [article("a"), article("b", source="Other"), article("c")]
        response = {"events": [event(["a", "b"]), event(["c"])]}
        events = group_events(rows, ReplyModel(response))
        self.assertEqual(events[0]["source_ids"], ["a", "b"])
        self.assertEqual(len(events), 2)

    def test_invalid_group_membership_is_rejected(self):
        from src.news.events import group_events

        for ids in [["unknown"], ["a", "a"], []]:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                group_events([article()], ReplyModel({"events": [event(ids)]}))
        groups = group_events([article("a"), article("b")], ReplyModel({"events": []}))
        self.assertEqual(
            {i for group in groups for i in group["source_ids"]}, {"a", "b"}
        )

    def test_repeat_needs_existing_history_and_update_needs_explanation(self):
        from src.news.events import group_events

        previous = {
            "events": [
                {"event_id": "past", "title": "Past event", "summary": "Prior facts"}
            ]
        }
        repeated = event(["a"], novelty="repeat", previous_event_id="past")
        result = group_events([article()], ReplyModel({"events": [repeated]}), previous)
        self.assertEqual(result[0]["novelty"], "repeat")
        with self.assertRaises(ValueError):
            group_events([article()], ReplyModel({"events": [repeated]}))
        updated = event(["a"], novelty="update", previous_event_id="past", change="")
        with self.assertRaises(ValueError):
            group_events([article()], ReplyModel({"events": [updated]}), previous)

    def test_unmatched_singletons_are_materialized_without_model_bookkeeping(self):
        from src.news.events import group_events

        groups = group_events([article("a"), article("b")], ReplyModel({"events": []}))
        self.assertEqual(len(groups), 2)
        self.assertTrue(all(g["novelty"] == "new" for g in groups))

    def test_selection_cannot_repeat_an_event_or_exceed_budget(self):
        from src.news.events import select_events

        events = [
            {"event_id": "e1", "novelty": "new", "title": "One"},
            {"event_id": "e2", "novelty": "new", "title": "Two"},
        ]
        choices = [choice("e1"), choice("e2")]
        with self.assertRaises(ValueError):
            select_events(events, ReplyModel({"decisions": choices}), top_limit=1)
        with self.assertRaises(ValueError):
            select_events(
                events, ReplyModel({"decisions": [choice("e1"), choice("e1")]})
            )

    def test_unselected_events_have_explicit_budget_exclusions(self):
        from src.news.events import select_events

        events = [
            {"event_id": "e1", "novelty": "new", "title": "One"},
            {"event_id": "e2", "novelty": "new", "title": "Two"},
        ]
        model = ReplyModel({"decisions": [choice("e1")]})
        result = select_events(events, model, top_limit=2)
        excluded = next(d for d in result if d["event_id"] == "e2")
        self.assertEqual(excluded["tier"], "exclude")
        self.assertEqual(excluded["decision_basis"], "edition_budget")
        self.assertIsNone(excluded["score"])

    def test_model_shortlist_cannot_include_exclusion_records(self):
        from src.news.events import select_events

        events = [{"event_id": "e1", "novelty": "new", "title": "One"}]
        with self.assertRaises(ValueError):
            select_events(
                events, ReplyModel({"decisions": [choice("e1", tier="exclude")]})
            )

    def test_repeat_is_excluded_without_asking_model_to_select_it(self):
        from src.news.events import select_events

        events = [{"event_id": "e1", "novelty": "repeat", "title": "One"}]
        model = Mock()
        decisions = select_events(events, model)
        model.complete.assert_not_called()
        self.assertEqual(decisions[0]["tier"], "exclude")

    def test_model_rejects_truncation_and_does_not_expose_endpoint_in_errors(self):
        from src.news.llm import JsonModel

        response = Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"finish_reason": "length", "message": {"content": None}}]
        }
        model = JsonModel("http://localhost:1/v1", "test")
        with patch(
            "src.news.llm.requests.post", return_value=response
        ), self.assertRaises(ValueError):
            model.complete("test", {})
        import requests

        with patch(
            "src.news.llm.requests.post",
            side_effect=requests.ConnectionError("private endpoint"),
        ), self.assertRaisesRegex(
            RuntimeError, "^Model request failed: ConnectionError$"
        ):
            model.complete("test", {})

    def test_collector_identity_ignores_tracking_and_preserves_unknown_dates(self):
        from src.news.pipeline import collect_articles

        response = Mock()
        response.content = b'<rss version="2.0"><channel><title>Test</title><item><title>One</title><link>https://example.com/story?utm_source=rss</link></item><item><title>One updated title</title><link>https://example.com/story</link></item></channel></rss>'
        with patch("src.news.pipeline.requests.get", return_value=response):
            rows, health = collect_articles()
        self.assertEqual(rows[0]["id"], rows[1]["id"])
        self.assertIsNone(rows[0]["published"])
        self.assertEqual(rows[0]["published_basis"], "unknown")

    def test_failed_grouping_leaves_audited_failure_without_an_edition(self):
        from src.news.pipeline import build_edition
        from pathlib import Path
        import tempfile, json

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                build_edition(
                    [article()],
                    ReplyModel({"events": [event(["unknown"])]}),
                    Path(tmp),
                    now=NOW,
                )
            self.assertFalse((Path(tmp) / "edition.json").exists())
            manifest = json.loads((Path(tmp) / "run.json").read_text())
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(manifest["stage"], "group_events")

    def test_extraction_never_requests_an_unapproved_host(self):
        from src.news.pipeline import extract_article

        with patch("src.news.pipeline.requests.get") as get:
            result = extract_article(article(url="http://localhost/private"))
        get.assert_not_called()
        self.assertEqual(result["basis"], "feed_summary")

    def test_summary_cannot_cite_only_an_empty_source(self):
        from src.news.pipeline import build_edition
        from pathlib import Path
        import tempfile, json

        class Model:
            def complete(self, task, data):
                if task == "group_events":
                    return {"events": [event(["a", "b"])]}
                if task == "select_events":
                    return {"decisions": [choice(data["events"][0]["event_id"])]}
                return {
                    "summary": "Source facts.",
                    "why_matters": "",
                    "support": [{"section": "summary", "segment_id": "b:0"}],
                }

        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "src.news.pipeline.extract_article",
                side_effect=[
                    {"basis": "article_text", "text": "Actual facts."},
                    {"basis": "feed_summary", "text": ""},
                ],
            ), self.assertRaises(ValueError):
                build_edition([article("a"), article("b")], Model(), Path(tmp), now=NOW)
            self.assertFalse((Path(tmp) / "edition.json").exists())
            self.assertEqual(
                json.loads((Path(tmp) / "run.json").read_text())["stage"], "synthesize"
            )

    def test_synthesis_rejects_unknown_source_passages(self):
        from src.news.pipeline import build_edition
        from pathlib import Path
        import tempfile

        class Model:
            def complete(self, task, data):
                if task == "group_events":
                    return {"events": []}
                if task == "select_events":
                    return {"decisions": [choice(data["events"][0]["event_id"])]}
                return {
                    "summary": "Source facts.",
                    "why_matters": "Officials reported hundreds of cases.",
                    "evidence_ids": ["a"],
                    "support": [
                        {"section": "summary", "segment_id": "a:0"},
                        {"section": "why_matters", "segment_id": "a:999"},
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "src.news.pipeline.extract_article",
                return_value={"basis": "article_text", "text": "Actual facts."},
            ), self.assertRaises(ValueError):
                build_edition([article("a")], Model(), Path(tmp), now=NOW)
            self.assertFalse((Path(tmp) / "edition.json").exists())

    def test_source_passages_have_bounded_verbatim_excerpts(self):
        from src.news.pipeline import build_edition
        from pathlib import Path
        import tempfile

        text = " ".join(f"fact{i}" for i in range(30))

        class Model:
            def complete(self, task, data):
                if task == "group_events":
                    return {"events": []}
                if task == "select_events":
                    return {"decisions": [choice(data["events"][0]["event_id"])]}
                return {
                    "summary": "Source facts.",
                    "why_matters": "",
                    "evidence_ids": ["a"],
                    "support": [{"section": "summary", "segment_id": "a:0"}],
                }

        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "src.news.pipeline.extract_article",
                return_value={"basis": "article_text", "text": text},
            ):
                edition = build_edition([article("a")], Model(), Path(tmp), now=NOW)
            self.assertEqual(
                len(edition["stories"][0]["support"][0]["quote"].split()), 25
            )

    def test_cited_sources_are_derived_from_passages_not_model_source_lists(self):
        from src.news.pipeline import build_edition
        from pathlib import Path
        import tempfile

        class Model:
            def complete(self, task, data):
                if task == "group_events":
                    return {"events": [event(["a", "b"])]}
                if task == "select_events":
                    return {"decisions": [choice(data["events"][0]["event_id"])]}
                return {
                    "summary": "Source facts.",
                    "why_matters": "",
                    "evidence_ids": ["a", "b"],
                    "support": [{"section": "summary", "segment_id": "a:0"}],
                }

        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "src.news.pipeline.extract_article",
                return_value={"basis": "article_text", "text": "Actual facts."},
            ):
                edition = build_edition(
                    [article("a"), article("b")], Model(), Path(tmp), now=NOW
                )
            used = {
                s["id"]: s["used_in_summary"] for s in edition["stories"][0]["sources"]
            }
            self.assertEqual(used, {"a": True, "b": False})

    def test_publisher_redirect_cannot_fetch_private_service(self):
        from src.news.pipeline import extract_article

        response = Mock(
            status_code=302, headers={"Location": "http://localhost/private"}
        )
        with patch("src.news.pipeline.requests.get", return_value=response) as get:
            result = extract_article(article(url="https://www.bbc.com/news/example"))
        self.assertEqual(get.call_count, 1)
        self.assertEqual(result["status"], "unapproved_host")

    def test_full_edition_preserves_groups_and_audits_exclusions(self):
        from src.news.pipeline import build_edition
        import tempfile, json
        from pathlib import Path

        rows = [article("a"), article("b", source="Other")]

        class Model:
            def complete(self, task, data):
                if task == "group_events":
                    return {"events": [event(["a", "b"])]}
                if task == "select_events":
                    return {"decisions": [choice(data["events"][0]["event_id"])]}
                return {
                    "summary": "One event happened. These are its main facts.",
                    "why_matters": "This affects readers.",
                    "evidence_ids": ["a"],
                    "support": [
                        {"section": "summary", "segment_id": "a:0"},
                        {"section": "why_matters", "segment_id": "a:0"},
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "src.news.pipeline.extract_article",
                return_value={
                    "basis": "article_text",
                    "text": "Actual source evidence.",
                },
            ):
                edition = build_edition(rows, Model(), Path(tmp), now=NOW)
            self.assertEqual(len(edition["stories"]), 1)
            self.assertEqual(len(edition["stories"][0]["sources"]), 2)
            self.assertEqual(edition["status"], "ready_for_review")
            self.assertEqual(
                json.loads((Path(tmp) / "events.json").read_text())[0]["source_ids"],
                ["a", "b"],
            )


def event(ids, **changes):
    return {
        "source_ids": ids,
        "representative_id": ids[0] if ids else "",
        "title": "One event",
        "novelty": "new",
        "previous_event_id": None,
        "change": "",
        "reason": "Same specific event.",
        **changes,
    }


def choice(id, **changes):
    return {
        "event_id": id,
        "tier": "top",
        "score": 8,
        "topic": "technology",
        "reason": "Significant development.",
        **changes,
    }


if __name__ == "__main__":
    unittest.main()
