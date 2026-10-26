"""Public reader contracts and publication boundaries, without network services."""

import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from news.render import render_edition, reader_snapshot


def edition():
    return {
        "schema_version": 3,
        "run_id": "run-1",
        "generated_at": "2026-10-19T01:00:00Z",
        "publication_status": "preview",
        "private_audit": "DO_NOT_PUBLISH",
        "stories": [
            {
                "event_id": "event-1",
                "title": "A <new> event",
                "summary": "Facts & context",
                "why_matters": "",
                "topics": ["Science"],
                "geography": ["NZ"],
                "importance": "notable",
                "freshness": "new",
                "featured": True,
                "support": "PRIVATE_SUPPORT",
                "sources": [
                    {
                        "source": "BBC",
                        "url": "https://www.bbc.com/news",
                        "published": "2026-10-18T23:00:00Z",
                        "evidence_basis": "feed_summary",
                        "used_in_summary": True,
                        "raw_text": "PRIVATE_SOURCE",
                    }
                ],
            }
        ],
    }


class ReaderTests(unittest.TestCase):
    def test_fallback_contains_one_card_and_familiar_template(self):
        page = render_edition(edition(), [])
        self.assertIn("assets/dunder_park.jpg", page)
        self.assertIn("AJC Analytics Limited", page)
        self.assertEqual(page.count('class="article reader-story'), 1)
        self.assertIn("A &lt;new&gt; event", page)
        self.assertIn("RSS-summary evidence", page)
        self.assertIn("Review preview", page)
        self.assertIn('id="topic-filter"', page)
        self.assertIn('id="geography-filter"', page)
        self.assertIn('id="unread-filter"', page)
        self.assertIn('id="reset-read"', page)

    def test_geographic_aliases_share_one_filter(self):
        item = edition()
        item["stories"][0]["geography"] = [
            "US",
            "U.S.",
            "USA",
            "United States",
            "New Zealand",
        ]
        self.assertEqual(
            reader_snapshot(item)["stories"][0]["geography"], ["United States", "NZ"]
        )

    def test_snapshot_whitelists_and_sanitizes_fields(self):
        item = edition()
        item["stories"][0]["sources"].append(
            {"source": "Unsafe", "url": "javascript:alert(1)"}
        )
        snapshot = reader_snapshot(item)
        serialized = json.dumps(snapshot)
        for secret in (
            "DO_NOT_PUBLISH",
            "PRIVATE_SUPPORT",
            "PRIVATE_SOURCE",
            "javascript:",
        ):
            self.assertNotIn(secret, serialized)
        self.assertEqual(len(snapshot["stories"][0]["sources"]), 1)

    def test_public_snapshot_is_safe_to_render_again(self):
        snapshot = reader_snapshot(edition())
        self.assertEqual(reader_snapshot(snapshot), snapshot)
        self.assertIn("RSS-summary evidence", render_edition(snapshot, []))

    def test_unsafe_source_schemes_and_credentials_are_removed(self):
        item = edition()
        for url in (
            "data:text/html,bad",
            "//example.com/news",
            "https://user:secret@example.com/news",
            "https://[invalid",
        ):
            item["stories"][0]["sources"] = [{"source": "Unsafe", "url": url}]
            self.assertEqual(reader_snapshot(item)["stories"][0]["sources"], [])

    def test_empty_summary_exposes_processing_boundary(self):
        item = edition()
        item["stories"][0]["summary"] = ""
        self.assertIn("Summary unavailable", render_edition(item, []))

    def test_story_markup_cannot_close_script_and_no_duplicate_payload(self):
        item = edition()
        item["stories"][0]["summary"] = '</script><img src=x onerror="alert(1)">'
        page = render_edition(item, [])
        self.assertNotIn("<img src=x", page)
        self.assertIn(
            "&lt;/script&gt;&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", page
        )
        self.assertNotIn('id="reader-data"', page)
        self.assertEqual(page.count("</script>"), 1)

    def test_same_event_update_identity_ignores_placement_and_freshness(self):
        item = edition()
        first = reader_snapshot(item)["stories"][0]["read_key"]
        item["stories"][0].update(featured=False, freshness="previously_featured")
        self.assertEqual(reader_snapshot(item)["stories"][0]["read_key"], first)
        item["stories"][0]["summary"] = "A material update"
        self.assertNotEqual(reader_snapshot(item)["stories"][0]["read_key"], first)

    def test_lineage_revision_preserves_read_identity_across_editorial_wording(self):
        item = edition()
        item["stories"][0]["revision_key"] = "revision-1"
        snapshot = reader_snapshot(item)
        self.assertEqual(snapshot["stories"][0]["read_key"], "event-1:revision-1")
        self.assertEqual(reader_snapshot(snapshot), snapshot)
        item["stories"][0].update(
            summary="Same facts, clearer wording",
            title="A clearer title",
            featured=False,
            freshness="catch_up",
        )
        self.assertEqual(
            reader_snapshot(item)["stories"][0]["read_key"], "event-1:revision-1"
        )
        item["stories"][0]["revision_key"] = "revision-2"
        self.assertEqual(
            reader_snapshot(item)["stories"][0]["read_key"], "event-1:revision-2"
        )

    def test_week_deduplicates_same_lineage_with_different_summary_wording(self):
        item = edition()
        item["stories"][0]["revision_key"] = "revision-1"
        old = copy.deepcopy(item)
        old.update(run_id="run-0", generated_at="2026-10-18T01:00:00Z")
        old["stories"][0]["summary"] = "Earlier wording of unchanged facts"
        page = render_edition(item, [old])
        self.assertEqual(page.count('class="article reader-story'), 1)
        old["stories"][0]["revision_key"] = "revision-0"
        page = render_edition(item, [old])
        self.assertEqual(page.count('class="article reader-story'), 2)

    def test_archive_paths_are_bounded_and_week_deduplicates_updates(self):
        old = copy.deepcopy(edition())
        old.update(
            run_id="run-0",
            generated_at="2026-10-18T01:00:00Z",
            publication_status="published",
        )
        bad = dict(old, run_id="../private")
        page = render_edition(edition(), [old, bad])
        self.assertIn('href="archive/run-0.html"', page)
        self.assertNotIn('href="archive/../', page)
        self.assertEqual(page.count('class="article reader-story'), 1)
        old["stories"][0]["summary"] = "Earlier report"
        page = render_edition(edition(), [old])
        self.assertEqual(page.count('class="article reader-story'), 2)
        self.assertIn("Earlier report", page)

    def test_week_excludes_old_editions_but_keeps_date_navigation(self):
        old = copy.deepcopy(edition())
        old.update(run_id="old", generated_at="2026-09-01T01:00:00Z")
        old["stories"][0]["summary"] = "Outside the week"
        page = render_edition(edition(), [old])
        self.assertIn('href="archive/old.html"', page)
        self.assertNotIn("Outside the week", page)

    @unittest.skipUnless(
        shutil.which("node"), "Node is needed to execute browser control logic"
    )
    def test_filter_toggles_preserve_featured_and_collection_order(self):
        harness = r"""
const assert = require("node:assert/strict");
const make = () => ({hidden: false, value: "", checked: false, events: {},
  addEventListener(name, callback) { this.events[name] = callback; },
  focus() { document.activeElement = this; }});
const card = key => ({...make(), dataset: {readKey: key, topics: '["Science"]', geography: '["NZ"]'},
  classList: {toggle() {}}, button: {...make(), setAttribute() {}}, label: {},
  querySelector(selector) { return selector === ".read-toggle" ? this.button : this.label; }});
const f1 = card("featured-1"), f2 = card("featured-2"), l1 = card("library-1"), l2 = card("library-2");
const h1 = card("historic-1");
h1.dataset.topics = '["Politics"]';
const cards = [f1, f2, l1, l2, h1];
const containers = [];
function container(children) {
  const result = {...make(), children,
    querySelectorAll() { return [...this.children]; },
    appendChild(child) {
      containers.forEach(parent => parent.children = parent.children.filter(item => item !== child));
      this.children.push(child);
    },
    insertBefore(child, before) {
      containers.forEach(parent => parent.children = parent.children.filter(item => item !== child));
      const index = before ? this.children.indexOf(before) : this.children.length;
      this.children.splice(index, 0, child);
    },
    get firstChild() { return this.children[0] || null; }};
  containers.push(result);
  return result;
}
const featured = container([f1, f2]), collection = container([l1, l2]);
const elements = Object.fromEntries(["topic-filter", "geography-filter", "unread-filter", "storage-status", "no-results", "result-count", "reset-read", "no-results-message", "show-history"].map(id => [id, make()]));
elements["featured-section"] = featured;
elements["collection-cards"] = collection;
const week = container([h1]);
week.open = false;
week.contains = item => week.children.includes(item);
week.querySelector = () => week;
elements["week-overview"] = week;
global.document = {querySelectorAll() { return cards; }, querySelector() { return make(); }, getElementById(id) { return elements[id]; }};
global.localStorage = {getItem() { return null; }, setItem() {}};
global.window = {addEventListener() {}};
"""
        source = Path(__file__).parents[1].joinpath("src/news/reader.js").read_text()
        checks = r"""
const keys = parent => parent.children.map(item => item.dataset.readKey);
for (let i = 0; i < 3; i++) {
  elements["topic-filter"].value = "Science";
  elements["topic-filter"].events.change();
  assert.deepEqual(keys(collection), ["featured-1", "featured-2", "library-1", "library-2"]);
  elements["topic-filter"].value = "";
  elements["topic-filter"].events.change();
  assert.deepEqual(keys(featured), ["featured-1", "featured-2"]);
  assert.deepEqual(keys(collection), ["library-1", "library-2"]);
}
elements["topic-filter"].value = "Politics";
elements["topic-filter"].events.change();
assert.equal(elements["no-results"].hidden, false);
assert.equal(elements["show-history"].hidden, false);
assert.match(elements["no-results-message"].textContent, /Earlier reports match/);
elements["show-history"].events.click();
assert.equal(week.open, true);
assert.equal(elements["result-count"].textContent, "1 report shown across recent editions.");
week.open = false;
week.events.toggle();
assert.equal(week.open, false);
assert.equal(elements["show-history"].hidden, false);
elements["topic-filter"].value = "Science";
elements["unread-filter"].checked = true;
elements["topic-filter"].events.change();
f1.button.focus();
f1.button.events.click();
assert.equal(f1.hidden, true);
assert.equal(document.activeElement, f2.button);
for (const item of [f2, l1, l2]) {
  item.button.focus();
  item.button.events.click();
}
assert.equal(document.activeElement, elements["unread-filter"]);
"""
        result = subprocess.run(
            ["node", "-e", harness + source + checks], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_absent_sources_and_bad_dates_remain_readable(self):
        item = edition()
        item["stories"][0]["sources"] = []
        item["generated_at"] = "unknown"
        self.assertIn("Facts &amp; context", render_edition(item, []))


if __name__ == "__main__":
    unittest.main()


class ArchiveWindowTests(unittest.TestCase):
    def test_seven_day_window_includes_more_than_seven_editions_and_excludes_stale(
        self,
    ):
        current = edition()
        archives = []
        for n in range(9):
            old = edition()
            old["run_id"] = f"old-{n}"
            old["generated_at"] = f"2026-10-18T{n:02}:00:00Z"
            old["stories"][0]["event_id"] = f"event-old-{n}"
            old["stories"][0]["title"] = f"Historic report {n}"
            archives.append(old)
        stale = copy.deepcopy(archives[-1])
        stale["run_id"] = "stale"
        stale["generated_at"] = "2026-10-01T00:00:00Z"
        stale["stories"][0]["title"] = "Stale report"
        page = render_edition(current, archives + [stale])
        self.assertIn("Historic report 8", page)
        self.assertNotIn("Stale report", page)
