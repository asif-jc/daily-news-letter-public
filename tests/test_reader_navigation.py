"""Contracts for a story-first archive reader, including script-free navigation."""

import copy
import unittest

from bs4 import BeautifulSoup

from news.render import render_edition
from tests.test_render import edition


class StoryNavigationTests(unittest.TestCase):
    def page(self, item=None, **kwargs):
        return BeautifulSoup(render_edition(item or edition(), **kwargs), "html.parser")

    def test_every_story_has_one_real_anchor_and_one_article(self):
        item = edition()
        other = copy.deepcopy(item["stories"][0])
        other.update(event_id="second", title="Second story", featured=False)
        item["stories"].append(other)
        page = self.page(item)
        links = page.select(".story-link")
        articles = page.select("article.reader-story")
        self.assertEqual(len(links), 2)
        self.assertEqual(len(articles), 2)
        self.assertEqual(
            {link["href"].split("#")[1] for link in links},
            {article["id"] for article in articles},
        )
        self.assertTrue(all(not article.has_attr("hidden") for article in articles))
        self.assertIn("Browse stories", page.get_text())

    def test_source_action_is_reporting_not_a_fake_copy_control(self):
        page = self.page()
        link = page.select_one(".story-original")
        self.assertEqual(link["href"], "https://www.bbc.com/news")
        self.assertIn("original", link["aria-label"].lower())
        self.assertIn("noopener", link["rel"])
        self.assertEqual(page.select_one(".story-title").get_text(), "A <new> event")

    def test_header_pull_quote_is_existing_briefing_text_without_attribution(self):
        item = edition()
        item["stories"][0]["summary"] = "A reviewed opening sentence. Supporting detail follows."
        page = self.page(item)
        self.assertEqual(page.select_one(".briefing-quote").get_text(strip=True), "A reviewed opening sentence.")
        self.assertIn("From this briefing", page.get_text())
        self.assertIsNone(page.select_one(".briefing-quote cite"))
        self.assertTrue(page.select_one(".editorial-art")["src"].startswith("assets/editorial-"))

    def test_archive_story_links_stay_in_the_selected_edition(self):
        page = self.page(archive=True)
        self.assertTrue(page.select_one(".story-link")["href"].startswith("archive/run-1.html#story-"))

    def test_search_and_mobile_browser_have_explicit_labels(self):
        page = self.page()
        self.assertEqual(page.select_one("#story-search")["type"], "search")
        self.assertEqual(page.select_one("#browse-stories")["aria-controls"], "story-browser")
        self.assertIsNotNone(page.select_one("#close-browser"))
        self.assertIsNotNone(page.select_one("#reader-empty"))
        self.assertIsNotNone(page.select_one("#topic-filter"))
        self.assertIsNotNone(page.select_one("#geography-filter"))

    def test_no_related_story_or_subscription_noise(self):
        page = self.page()
        self.assertIsNone(page.select_one("form"))
        self.assertNotIn("Related stories", page.get_text())
        self.assertIn("Briefing produced", page.get_text())


if __name__ == "__main__":
    unittest.main()
