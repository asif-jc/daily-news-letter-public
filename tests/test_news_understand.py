"""Grounding and repair behavior for article-level understanding."""

import unittest
from unittest.mock import Mock


class UnderstandingTests(unittest.TestCase):
    def article(self):
        return {
            "id": "a",
            "title": "Minister claims a policy will reduce costs",
            "source": "BBC World News",
            "category": "world",
            "published": "2026-10-19T00:00:00Z",
            "url": "https://bbc.com/a",
        }

    def response(
        self, summary="The minister said the policy would reduce costs.", why=""
    ):
        return {
            "articles": [
                {
                    "id": "a1",
                    "summary": summary,
                    "why_matters": why,
                    "topics": ["Politics", "Economy"],
                    "geography": ["NZ"],
                    "support": [{"section": "summary", "passage_id": "p1"}],
                }
            ]
        }

    def test_reviewed_summary_retains_actual_source_passage(self):
        from src.news.understand import analyse_batch

        model = Mock()
        model.complete.side_effect = [
            self.response(),
            {
                "reviews": [
                    {
                        "id": "a1",
                        "verdict": "approved",
                        "reason": "Attribution preserved.",
                    }
                ]
            },
        ]
        result = analyse_batch(
            [self.article()],
            {
                "a": {
                    "basis": "article_text",
                    "text": "The minister said the policy would reduce costs.",
                    "status": "ok",
                }
            },
            model,
        )
        self.assertEqual(result["a"]["state"], "ready")
        self.assertEqual(
            result["a"]["support"][0]["quote"],
            "The minister said the policy would reduce costs.",
        )
        self.assertEqual(result["a"]["topics"], ["Politics", "Economy"])

    def test_unsupported_motive_is_repaired_then_reviewed(self):
        from src.news.understand import analyse_batch

        model = Mock()
        model.complete.side_effect = [
            self.response("The policy will reduce costs."),
            {
                "reviews": [
                    {
                        "id": "a1",
                        "verdict": "revise",
                        "reason": "Prediction must stay attributed.",
                    }
                ]
            },
            self.response(),
            {
                "reviews": [
                    {"id": "a1", "verdict": "approved", "reason": "Attribution fixed."}
                ]
            },
        ]
        result = analyse_batch(
            [self.article()],
            {
                "a": {
                    "basis": "article_text",
                    "text": "The minister said the policy would reduce costs.",
                    "status": "ok",
                }
            },
            model,
        )
        self.assertIn("minister said", result["a"]["summary"])
        self.assertEqual(result["a"]["attempts"], 2)

    def test_persistent_unsupported_summary_is_not_reader_ready(self):
        from src.news.understand import analyse_batch

        model = Mock()
        model.complete.side_effect = [
            self.response(),
            {"reviews": [{"id": "a1", "verdict": "revise", "reason": "Unsupported."}]},
            self.response(),
            {
                "reviews": [
                    {"id": "a1", "verdict": "revise", "reason": "Still unsupported."}
                ]
            },
        ]
        r = analyse_batch(
            [self.article()],
            {
                "a": {
                    "basis": "article_text",
                    "text": "Different evidence.",
                    "status": "ok",
                }
            },
            model,
        )["a"]
        self.assertEqual(r["state"], "needs_review")
        self.assertEqual(r["summary"], "")

    def test_empty_evidence_has_explicit_state_and_no_model_call(self):
        from src.news.understand import analyse_batch

        model = Mock()
        r = analyse_batch(
            [self.article()],
            {"a": {"basis": "feed_summary", "text": "", "status": "unavailable"}},
            model,
        )
        self.assertEqual(r["a"]["state"], "unavailable")
        model.complete.assert_not_called()

    def test_unknown_topic_and_missing_article_are_rejected(self):
        from src.news.understand import analyse_batch

        for response in [
            {"articles": []},
            {"articles": [{**self.response()["articles"][0], "topics": ["Whatever"]}]},
        ]:
            model = Mock()
            model.complete.return_value = response
            with self.assertRaises(ValueError):
                analyse_batch(
                    [self.article()],
                    {
                        "a": {
                            "basis": "article_text",
                            "text": "Evidence exists here.",
                            "status": "ok",
                        }
                    },
                    model,
                )
