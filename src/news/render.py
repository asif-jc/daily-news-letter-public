"""Render reader-safe snapshots, cards and dated edition navigation."""

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import html

from .analysis import TOPICS
from .urls import allowed_publisher_url

FOOTER_HTML = """
        <div class="footer">
            <div class="mission">
                Inform on global events capturing key and interesting events that influence our lives and delivering that information in an easily consumable format.
            </div>
            <div class="branding">
                AJC Analytics Limited
            </div>
        </div>
        """


def escape(value):
    return html.escape(str(value), quote=True)


def safe_link(url):
    return url if allowed_publisher_url(url) else None


GEOGRAPHY_ALIASES = {
    "US": "United States",
    "U.S.": "United States",
    "USA": "United States",
    "U.S.A.": "United States",
    "New Zealand": "NZ",
    "UK": "United Kingdom",
    "U.K.": "United Kingdom",
}
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


def _timestamp(value):
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _date(value):
    timestamp = _timestamp(value)
    return (
        timestamp.astimezone(ZoneInfo("Pacific/Auckland")).strftime(
            "%d %b %Y, %-I:%M %p %Z"
        )
        if timestamp
        else "Date unavailable"
    )


def reader_snapshot(edition):
    """Whitelist only intended reader fields, including source URLs and dates."""
    stories = []
    for story in edition.get("stories", []):
        sources = []
        for source in story.get("sources", []):
            url = safe_link(source.get("url", ""))
            if not url:
                continue
            sources.append(
                {
                    "source": str(source.get("source", "Source")),
                    "url": url,
                    "published": str(source.get("published") or ""),
                    "updated": str(source.get("updated") or ""),
                    "rss_only": bool(
                        source.get("rss_only")
                        or (
                            source.get("used_in_summary")
                            and source.get("evidence_basis") == "feed_summary"
                        )
                    ),
                }
            )
        clean = {
            key: str(story.get(key) or "")
            for key in ("event_id", "title", "summary", "why_matters")
        }
        clean["sources"] = sources
        clean["topics"] = [tag for tag in story.get("topics", []) if tag in TOPICS]
        clean["geography"] = list(
            dict.fromkeys(
                GEOGRAPHY_ALIASES.get(tag, tag)
                for tag in story.get("geography", [])
                if isinstance(tag, str)
            )
        )
        clean["importance"] = (
            story.get("importance")
            if story.get("importance") in ("major", "notable", "useful")
            else "useful"
        )
        clean["freshness"] = (
            story.get("freshness")
            if story.get("freshness")
            in ("new", "updated", "catch_up", "previously_featured")
            else "new"
        )
        clean["featured"] = bool(story.get("featured"))
        revision = story.get("revision_key")
        clean["revision_key"] = revision if isinstance(revision, str) else ""
        # Material-update lineage survives harmless summary rewrites. Older editions
        # have no lineage key, so their factual content supplies a conservative fallback.
        content = [
            clean[key] for key in ("event_id", "title", "summary", "why_matters")
        ]
        signature = hashlib.sha256(
            json.dumps(content, ensure_ascii=False).encode()
        ).hexdigest()[:24]
        identity = clean["event_id"] or signature
        clean["read_key"] = identity + ":" + (clean["revision_key"] or signature)
        stories.append(clean)
    status = edition.get("publication_status")
    return {
        "run_id": str(edition.get("run_id", "")),
        "generated_at": str(edition.get("generated_at", "")),
        "publication_status": "published" if status == "published" else "preview",
        "stories": stories,
    }


def _card(story, generated_at, historic=False):
    title = escape(story["title"])
    sources = story["sources"]
    if sources:
        title = f'<a href="{escape(sources[0]["url"])}" target="_blank" rel="noopener noreferrer">{title}</a>'
    topics = " · ".join(story["topics"])
    geography = " · ".join(story["geography"])
    metadata = " · ".join(
        filter(
            None,
            (
                geography,
                story["importance"].capitalize(),
                story["freshness"].replace("_", " ").capitalize(),
            ),
        )
    )
    summary = (
        escape(story["summary"])
        if story["summary"]
        else "Summary unavailable: this report has not completed evidence review."
    )
    body = f'<article class="article reader-story {"critical" if story["featured"] and not historic else "key"}" data-read-key="{escape(story["read_key"])}" data-topics="{escape(json.dumps(story["topics"]))}" data-geography="{escape(json.dumps(story["geography"]))}"><div class="article-header"><span class="category-badge world">{escape(topics or "News")}</span><h3 class="article-title">{title}</h3></div><p class="article-meta">{escape(metadata)}</p><p class="article-summary">{summary}</p>'
    if story["why_matters"]:
        body += f'<p class="why-matters"><strong>Why this matters:</strong> {escape(story["why_matters"])}</p>'
    if sources:
        links = []
        for source in sources:
            dates = " · ".join(
                f"{label} {_date(source[key])}"
                for key, label in (("published", "Published"), ("updated", "Updated"))
                if source[key]
                and (
                    key != "updated"
                    or not source["published"]
                    or _timestamp(source[key]) != _timestamp(source["published"])
                )
            )
            links.append(
                f'<a href="{escape(source["url"])}" target="_blank" rel="noopener noreferrer">{escape(source["source"])}</a>'
                + (f" <span>{escape(dates)}</span>" if dates else "")
            )
        body += f'<p class="article-meta">Sources: {"; ".join(links)}</p>'
    if any(source["rss_only"] for source in sources):
        body += '<p class="article-meta">Includes RSS-summary evidence.</p>'
    if historic:
        body += f'<p class="article-meta">Edition: {escape(_date(generated_at))}</p>'
    return (
        body
        + '<button class="read-toggle" type="button" hidden>Mark read</button><span class="read-label" aria-live="polite"></span></article>'
    )


def render_edition(edition, archives=()):
    """Return standalone HTML; archive exports use a root-relative base element."""
    current = reader_snapshot(edition)
    generated = _timestamp(current["generated_at"])
    history = [
        reader_snapshot(item)
        for item in archives
        if RUN_ID.fullmatch(str(item.get("run_id", "")))
        and item.get("run_id") != current["run_id"]
    ]
    stories = current["stories"]
    seen = {story["read_key"] for story in stories}
    historic = []
    for item in history:
        timestamp = _timestamp(item["generated_at"])
        if (
            not generated
            or not timestamp
            or not generated - timedelta(days=7) <= timestamp <= generated
        ):
            continue
        for story in item["stories"]:
            if story["read_key"] not in seen:
                historic.append((story, item["generated_at"]))
                seen.add(story["read_key"])
    all_stories = stories + [story for story, _ in historic]
    status = (
        "Published edition"
        if current["publication_status"] == "published"
        else "Review preview - not published"
    )
    body = f'<header class="header"><h1>Daily News Feed</h1><div class="date">{escape(_date(current["generated_at"]))}</div><div class="last-updated">{status}</div></header><main class="content"><nav class="edition-history" aria-label="Dated editions"><a href="index.html">Latest edition</a>'
    for item in history:
        label = (
            "Published"
            if item["publication_status"] == "published"
            else "Review preview"
        )
        body += f'<a href="archive/{escape(item["run_id"])}.html">{escape(_date(item["generated_at"]))} ({label})</a>'
    body += '</nav><div class="reader-controls" hidden><label>Topic <select id="topic-filter"><option value="">All topics</option>'
    for topic in TOPICS:
        if any(topic in story["topics"] for story in all_stories):
            body += f"<option>{escape(topic)}</option>"
    body += '</select></label><label>Geography <select id="geography-filter"><option value="">All places</option>'
    for geography in sorted(
        {tag for story in all_stories for tag in story["geography"]}
    ):
        body += f"<option>{escape(geography)}</option>"
    body += '</select></label><label class="unread-control"><input type="checkbox" id="unread-filter"> Unread only</label><button id="reset-read" type="button">Reset read state</button><p id="storage-status" role="status">Read state is stored in this browser only. Opening a source does not mark a story read.</p></div><noscript><p>All summaries and dated editions are available below. Topic filters and local read controls need JavaScript.</p></noscript><p id="result-count" role="status" hidden></p>'
    body += '<section id="featured-section"><h2>Featured</h2>'
    featured = [story for story in stories if story["featured"]]
    body += (
        "".join(_card(story, current["generated_at"]) for story in featured)
        or "<p>No featured stories in this edition.</p>"
    )
    body += '</section><section id="collection-section"><h2>Topic collection</h2><p class="collection-intro">Additional stories appear below. Topic, geography and unread filters search the entire edition, including featured stories.</p><div id="collection-cards">'
    body += "".join(
        _card(story, current["generated_at"])
        for story in stories
        if not story["featured"]
    )
    body += '</div></section><details id="week-overview"><summary>Seven-day overview</summary><p>Distinct reports from this edition and all editions generated within the preceding seven days. Repeated unchanged reports appear once; earlier versions remain available below.</p>'
    body += (
        "".join(_card(story, date, True) for story, date in historic)
        or "<p>No additional reports in the recent editions.</p>"
    )
    body += (
        '</details><p id="no-results" hidden><span id="no-results-message">No stories match these filters.</span> <button id="show-history" type="button" hidden>Open seven-day overview</button></p></main>'
        + FOOTER_HTML
    )
    directory = Path(__file__).parent
    css = directory.joinpath("reader.css").read_text()
    script = directory.joinpath("reader.js").read_text()
    return f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Daily News Feed - {escape(_date(current["generated_at"]))}</title><style>{css}</style></head><body><div class="container">{body}</div><script>{script}</script></body></html>'
