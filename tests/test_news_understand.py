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
                    "support": [{"section": "summary", "passage_id": "p1"}]
                    + ([{"section": "why_matters", "passage_id": "p1"}] if why else []),
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

    def test_unsupported_optional_significance_is_removed_and_facts_rechecked(self):
        from src.news.understand import analyse_batch

        bad = self.response(why="This guarantees economic prosperity.")
        reject = {
            "reviews": [
                {
                    "id": "a1",
                    "verdict": "revise",
                    "reason": "Significance unsupported.",
                    "unsupported_sections": ["why_matters"],
                }
            ]
        }
        model = Mock()
        model.complete.side_effect = [
            bad,
            reject,
            bad,
            reject,
            {
                "reviews": [
                    {
                        "id": "a1",
                        "verdict": "approved",
                        "reason": "Facts are supported.",
                        "unsupported_sections": [],
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
        )["a"]
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["why_matters"], "")
        self.assertTrue(result["significance_omitted"])
        last_draft = model.complete.call_args_list[-1].args[1]["articles"][0]["draft"]
        self.assertEqual(last_draft["why_matters"], "")
        self.assertTrue(all(s["section"] == "summary" for s in result["support"]))

    def test_dropping_significance_cannot_rescue_unsupported_facts(self):
        from src.news.understand import analyse_batch

        bad = self.response(why="This guarantees prosperity.")
        reject = {
            "reviews": [
                {
                    "id": "a1",
                    "verdict": "revise",
                    "reason": "Both sections unsupported.",
                    "unsupported_sections": ["summary", "why_matters"],
                }
            ]
        }
        model = Mock()
        model.complete.side_effect = [bad, reject, bad, reject]
        result = analyse_batch(
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
        self.assertEqual(result["state"], "needs_review")
        self.assertEqual(model.complete.call_count, 4)

    def test_geographic_breadth_is_not_an_arbitrary_five_place_cutoff(self):
        from src.news.understand import analyse_batch

        response = self.response()
        response["articles"][0]["geography"] = [
            "NZ",
            "Australia",
            "Japan",
            "France",
            "Germany",
            "Canada",
        ]
        model = Mock()
        model.complete.side_effect = [
            response,
            {"reviews": [{"id": "a1", "verdict": "approved", "reason": "Supported."}]},
        ]
        result = analyse_batch(
            [self.article()],
            {
                "a": {
                    "basis": "article_text",
                    "status": "ok",
                    "text": "The minister said the policy would reduce costs across NZ, Australia, Japan, France, Germany and Canada.",
                }
            },
            model,
        )
        self.assertEqual(len(result["a"]["geography"]), 6)

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
