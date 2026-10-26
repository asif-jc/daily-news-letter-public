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
        from news.analysis import analyse_batch

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
        from news.analysis import analyse_batch

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
        from news.analysis import analyse_batch

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
        from news.analysis import analyse_batch

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
        from news.analysis import analyse_batch

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
        from news.analysis import analyse_batch

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
        from news.analysis import analyse_batch

        model = Mock()
        r = analyse_batch(
            [self.article()],
            {"a": {"basis": "feed_summary", "text": "", "status": "unavailable"}},
            model,
        )
        self.assertEqual(r["a"]["state"], "unavailable")
        model.complete.assert_not_called()

    def test_invalid_topic_is_repaired_without_discarding_the_batch(self):
        from news.analysis import analyse_batch

        bad = self.response()
        bad["articles"][0]["topics"] = ["Privacy"]
        model = Mock()
        model.complete.side_effect = [
            bad,
            self.response(),
            {"reviews": [{"id": "a1", "verdict": "approved", "reason": "Grounded."}]},
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
        self.assertEqual(result["attempts"], 2)
        self.assertIn(
            "topics", model.complete.call_args_list[1].args[1]["feedback"][0]["reason"]
        )

    def test_valid_batch_members_are_not_regenerated_for_an_invalid_neighbor(self):
        from news.analysis import analyse_batch

        bad = self.response()["articles"][0]
        bad["topics"] = ["Privacy"]
        good = {**self.response()["articles"][0], "id": "a2"}

        def approved(id):
            return {
                "reviews": [{"id": id, "verdict": "approved", "reason": "Grounded."}]
            }

        model = Mock()
        model.complete.side_effect = [
            {"articles": [bad, good]},
            approved("a2"),
            self.response(),
            approved("a1"),
        ]
        evidence = {
            id: {
                "basis": "article_text",
                "text": "The minister said the policy would reduce costs.",
                "status": "ok",
            }
            for id in ["a", "b"]
        }
        result = analyse_batch(
            [self.article(), {**self.article(), "id": "b"}], evidence, model
        )
        self.assertEqual(
            {id: a["attempts"] for id, a in result.items()}, {"a": 2, "b": 1}
        )
        repair_ids = [
            a["id"] for a in model.complete.call_args_list[2].args[1]["articles"]
        ]
        self.assertEqual(repair_ids, ["a1"])

    def test_persistently_invalid_topic_is_retained_as_needs_review(self):
        from news.analysis import analyse_batch

        bad = self.response()
        bad["articles"][0]["topics"] = ["Privacy"]
        model = Mock()
        model.complete.return_value = bad
        result = analyse_batch(
            [self.article()],
            {"a": {"basis": "article_text", "text": "Some evidence.", "status": "ok"}},
            model,
        )["a"]
        self.assertEqual(result["state"], "needs_review")
        self.assertEqual(result["summary"], "")
        self.assertEqual(result["topics"], [])
        self.assertEqual(model.complete.call_count, 2)

    def test_malformed_support_id_uses_the_same_bounded_repair(self):
        from news.analysis import analyse_batch

        bad = self.response()
        bad["articles"][0]["support"][0]["passage_id"] = []
        model = Mock()
        model.complete.return_value = bad
        result = analyse_batch(
            [self.article()],
            {"a": {"basis": "article_text", "text": "Some evidence.", "status": "ok"}},
            model,
        )["a"]
        self.assertEqual(result["state"], "needs_review")
        self.assertEqual(model.complete.call_count, 2)

    def test_missing_article_is_rejected(self):
        from news.analysis import analyse_batch

        model = Mock()
        model.complete.return_value = {"articles": []}
        with self.assertRaises(ValueError):
            analyse_batch(
                [self.article()],
                {
                    "a": {
                        "basis": "article_text",
                        "text": "Evidence exists.",
                        "status": "ok",
                    }
                },
                model,
            )
