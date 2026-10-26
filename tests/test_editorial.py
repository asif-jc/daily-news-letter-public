"""Rolling eligibility and event placement are distinct editorial decisions."""

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock


class EditorialPolicyTests(unittest.TestCase):
    def article(self, id="a", **kw):
        return {
            "id": id,
            "url": "https://bbc.com/" + id,
            "title": "A useful story",
            "source": "BBC World News",
            "category": "world",
            "published": "2026-10-16T00:00:00Z",
            **kw,
        }

    def test_old_newly_collected_articles_are_understood_but_not_fresh(self):
        from news.editorial import prepare_articles

        now = datetime(2026, 10, 19, tzinfo=timezone.utc)
        rows = [
            self.article(),
            self.article("old", published="2026-10-01T00:00:00Z"),
            self.article("unknown", published=None),
        ]
        accepted, excluded = prepare_articles(rows, now)
        self.assertEqual(len(accepted), 3)
        self.assertFalse(excluded)
        self.assertFalse(next(a for a in accepted if a["id"] == "old")["in_pool"])
        self.assertTrue(next(a for a in accepted if a["id"] == "unknown")["in_pool"])

    def test_updated_article_is_eligible_without_falsifying_publication(self):
        from news.editorial import prepare_articles

        a = self.article(
            published="2026-10-01T00:00:00Z", updated="2026-10-18T00:00:00Z"
        )
        row = prepare_articles([a], datetime(2026, 10, 19, tzinfo=timezone.utc))[0][0]
        self.assertTrue(row["in_pool"])
        self.assertEqual(row["published"], a["published"])

    def test_updated_fallback_is_not_presented_as_original_publication(self):
        from news.editorial import prepare_articles

        a = self.article(published="2026-10-18T00:00:00Z", published_basis="updated")
        prepared = prepare_articles([a], datetime(2026, 10, 19, tzinfo=timezone.utc))[
            0
        ][0]
        self.assertIsNone(prepared["published"])
        self.assertEqual(prepared["updated"], a["published"])

    def test_recent_metadata_update_does_not_make_old_reporting_new(self):
        from news.editorial import story_freshness

        now = datetime(2026, 10, 19, tzinfo=timezone.utc)
        article = self.article(
            published="2026-10-15T00:00:00Z", updated="2026-10-19T00:00:00Z"
        )
        self.assertEqual(
            story_freshness(
                {"novelty": "new", "source_ids": ["a"]}, {"a": article}, now
            ),
            "catch_up",
        )
        self.assertEqual(
            story_freshness(
                {"novelty": "update", "source_ids": ["a"]}, {"a": article}, now
            ),
            "updated",
        )

    def test_invalid_url_and_future_date_have_reasons(self):
        from news.editorial import prepare_articles

        rows = [
            self.article(url="http://name:secret@bbc.com/a"),
            self.article("future", published="2030-01-01T00:00:00Z"),
        ]
        accepted, excluded = prepare_articles(
            rows, datetime(2026, 10, 19, tzinfo=timezone.utc)
        )
        self.assertFalse(accepted)
        self.assertEqual(
            {e["reason"] for e in excluded}, {"invalid_url", "future_date"}
        )

    def test_relevance_does_not_limit_collection_to_featured_budget(self):
        from news.editorial import place_stories

        stories = [
            {
                "event_id": str(i),
                "score": 9 - i / 10,
                "topics": ["AI"],
                "novelty": "new",
                "freshness": "new",
            }
            for i in range(12)
        ]
        placed = place_stories(stories, set(), featured_limit=3)
        self.assertEqual(len(placed), 12)
        self.assertEqual(sum(s["featured"] for s in placed), 3)

    def test_narrow_useful_reports_do_not_fill_featured_slots(self):
        from news.editorial import place_stories

        stories = [
            {
                "event_id": "small",
                "score": 4,
                "topics": ["Technology"],
                "novelty": "new",
                "freshness": "new",
            }
        ]
        placed = place_stories(stories, set(), featured_limit=6)
        self.assertEqual(len(placed), 1)
        self.assertFalse(placed[0]["featured"])

    def test_previous_featured_repeat_is_browsable_but_update_can_lead(self):
        from news.editorial import place_stories

        stories = [
            {
                "event_id": "repeat",
                "score": 10,
                "topics": ["Politics"],
                "novelty": "repeat",
                "freshness": "new",
            },
            {
                "event_id": "update",
                "score": 9,
                "topics": ["Conflict"],
                "novelty": "update",
                "freshness": "new",
            },
        ]
        placed = place_stories(stories, {"repeat", "update"}, featured_limit=6)
        self.assertFalse(placed[0]["featured"])
        self.assertEqual(placed[0]["freshness"], "previously_featured")
        self.assertTrue(placed[1]["featured"])
        self.assertEqual(placed[1]["freshness"], "updated")

    def test_classification_accounts_for_every_event_and_rejects_bad_score(self):
        from news.editorial import classify_events

        model = Mock()
        model.complete.return_value = {
            "decisions": [
                {
                    "id": "e1",
                    "relevant": True,
                    "score": 99,
                    "importance": "major",
                    "reason": "Useful",
                }
            ]
        }
        with self.assertRaises(ValueError):
            classify_events(
                [
                    {
                        "event_id": "x",
                        "source_ids": ["a"],
                        "title": "X",
                        "novelty": "new",
                    }
                ],
                {
                    "a": {
                        "summary": "Facts",
                        "why_matters": "",
                        "topics": ["AI"],
                        "geography": ["Global"],
                    }
                },
                model,
                {"include": []},
            )
