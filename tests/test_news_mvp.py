"""Editorial and reader-output behavior without external services."""

import unittest
from unittest.mock import Mock


class EditorialTests(unittest.TestCase):
    def events(self):
        return [
            {
                "event_id": "a",
                "title": "A",
                "description": "Facts",
                "novelty": "new",
                "source_ids": ["one"],
            },
            {
                "event_id": "b",
                "title": "B",
                "description": "Facts",
                "novelty": "new",
                "source_ids": ["two"],
            },
        ]

    def test_uncertain_survives_qualification_and_every_event_needs_a_reason(self):
        from src.news.editorial import qualify_events

        model = Mock()
        model.complete.return_value = {
            "qualifications": [
                {"event_id": "q1", "tag": "uncertain", "reason": "Need body"},
                {"event_id": "q2", "tag": "irrelevant", "reason": "Sport only"},
            ]
        }
        result = qualify_events(self.events(), model, {"id": "asif", "version": 1})
        self.assertEqual(
            [q["event_id"] for q in result if q["tag"] != "irrelevant"], ["a"]
        )
        model.complete.return_value = {
            "qualifications": [
                {"event_id": "q1", "tag": "relevant", "reason": "Useful"}
            ]
        }
        with self.assertRaises(ValueError):
            qualify_events(self.events(), model, {})

    def test_final_selection_uses_evidence_and_accounts_for_every_event(self):
        from src.news.editorial import select_with_evidence

        model = Mock()
        model.complete.return_value = {
            "decisions": [
                {
                    "event_id": "s1",
                    "tier": "top",
                    "score": 8,
                    "topic": "Policy",
                    "reason": "Material new policy",
                    "decision_basis": "selected",
                },
                {
                    "event_id": "s2",
                    "tier": "exclude",
                    "score": None,
                    "topic": "Other",
                    "reason": "Only teaser available",
                    "decision_basis": "insufficient_evidence",
                },
            ]
        }
        evidence = {"one": {"text": "Policy evidence", "basis": "article_text"}}
        result = select_with_evidence(self.events(), evidence, model, {}, 1, 1)
        self.assertEqual(len(result), 2)
        self.assertIn("Policy evidence", str(model.complete.call_args))
        model.complete.return_value["decisions"].pop()
        with self.assertRaises(ValueError):
            select_with_evidence(self.events(), evidence, model, {}, 1, 1)


class RenderTests(unittest.TestCase):
    def test_reader_escapes_text_and_keeps_private_audit_out(self):
        from src.news.render import render_edition

        edition = {
            "generated_at": "2026-10-19T00:00:00Z",
            "stories": [
                {
                    "title": "<script>bad</script>",
                    "summary": "A & B",
                    "why_matters": "Useful",
                    "tier": "top",
                    "topic": "Policy",
                    "sources": [{"source": "BBC", "url": "javascript:alert(1)"}],
                    "support": [{"quote": "PRIVATE EXCERPT"}],
                    "reason": "PRIVATE DECISION",
                }
            ],
        }
        html = render_edition(edition)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("javascript:", html)
        self.assertNotIn("PRIVATE", html)


class BudgetTests(unittest.TestCase):
    def test_evidence_selection_has_a_total_text_budget(self):
        from src.news.editorial import select_with_evidence

        events = [
            {
                "event_id": str(n),
                "title": "Event",
                "novelty": "new",
                "source_ids": [str(n)],
                "representative_id": str(n),
            }
            for n in range(100)
        ]
        evidence = {
            str(n): {"text": "x" * 8000, "basis": "article_text"} for n in range(100)
        }
        model = Mock()
        model.complete.return_value = {
            "decisions": [
                {
                    "event_id": f"s{n+1}",
                    "tier": "exclude",
                    "score": None,
                    "topic": "Other",
                    "reason": "Not enough space",
                    "decision_basis": "crowded_out",
                }
                for n in range(100)
            ]
        }
        select_with_evidence(events, evidence, model, {}, 5, 10)
        data = model.complete.call_args.args[1]
        self.assertLessEqual(
            sum(len(doc["text"]) for e in data["events"] for doc in e["evidence"]),
            60000,
        )


class EvidenceValidationTests(unittest.TestCase):
    def test_selection_cannot_choose_an_event_without_usable_evidence(self):
        from src.news.editorial import select_with_evidence

        model = Mock()
        model.complete.return_value = {
            "decisions": [
                {
                    "event_id": "s1",
                    "tier": "top",
                    "score": 9,
                    "topic": "Policy",
                    "reason": "Important",
                    "decision_basis": "selected",
                }
            ]
        }
        with self.assertRaises(ValueError):
            select_with_evidence(
                [{"event_id": "a", "title": "A", "source_ids": ["one"]}],
                {"one": {"text": "", "basis": "feed_summary"}},
                model,
                {},
                5,
                10,
            )

    def test_exclusion_requires_a_real_reason_category(self):
        from src.news.editorial import select_with_evidence

        model = Mock()
        model.complete.return_value = {
            "decisions": [
                {
                    "event_id": "s1",
                    "tier": "exclude",
                    "score": None,
                    "topic": "Policy",
                    "reason": "Skip",
                    "decision_basis": "other",
                }
            ]
        }
        with self.assertRaises(ValueError):
            select_with_evidence(
                [{"event_id": "a", "title": "A", "source_ids": []}],
                {},
                model,
                {},
                5,
                10,
            )

    def test_qualification_rejects_unknown_and_duplicate_ids(self):
        from src.news.editorial import qualify_events

        events = [{"event_id": "a", "title": "A", "novelty": "new"}]
        model = Mock()
        for rows in [
            [{"event_id": "b", "tag": "relevant", "reason": "Fit"}],
            [{"event_id": "a", "tag": "relevant", "reason": "Fit"}] * 2,
        ]:
            model.complete.return_value = {"qualifications": rows}
            with self.assertRaises(ValueError):
                qualify_events(events, model, {})


class ReferenceTests(unittest.TestCase):
    def test_qualification_uses_short_references_and_restores_stable_ids(self):
        from src.news.editorial import qualify_events

        model = Mock()

        def reply(task, data):
            self.assertEqual(data["events"][0]["event_id"], "q1")
            return {
                "qualifications": [
                    {"event_id": "q1", "tag": "relevant", "reason": "Useful policy"}
                ]
            }

        model.complete.side_effect = reply
        result = qualify_events(
            [{"event_id": "29720081c56cfc5d", "title": "Policy", "novelty": "new"}],
            model,
            {},
        )
        self.assertEqual(result[0]["event_id"], "29720081c56cfc5d")


class ReviewCountTests(unittest.TestCase):
    def test_review_counts_observations_not_duplicate_article_identity(self):
        from src.news.render import render_review
        from bs4 import BeautifulSoup

        row = {
            "id": "same",
            "source": "BBC",
            "title": "Policy",
            "url": "https://www.bbc.com/news/a",
        }
        html = render_review(
            {"stories": []},
            [row, row],
            [{**row, "observation_ordinal": 0}],
            [],
            [],
            [],
            {},
            {},
            [],
        )
        cells = [
            td.get_text()
            for td in BeautifulSoup(html, "html.parser")
            .select("table tr")[1]
            .select("td")
        ]
        self.assertEqual(cells, ["BBC", "2", "1", "0"])


class DatabaseBoundaryTests(unittest.TestCase):
    def test_backend_database_is_verified_before_any_schema_write(self):
        from src.news.store import NewsStore
        from unittest.mock import patch

        connection = Mock()
        connection.info.dbname = "news"
        connection.execute.return_value.fetchone.return_value = {
            "name": "another_database"
        }
        with patch(
            "src.news.store.psycopg.connect", return_value=connection
        ), self.assertRaises(ValueError):
            NewsStore("dbname=news")
        connection.close.assert_called_once()
        self.assertEqual(connection.execute.call_count, 1)


if __name__ == "__main__":
    unittest.main()
