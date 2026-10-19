import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import feedparser
import requests
from bs4 import BeautifulSoup

from src.mvp_news_aggregator.sources import RSS_FEEDS
from .events import canonical_url, filter_candidates, group_events, select_events, _text

ARTICLE_HOSTS = (
    "bbc.co.uk",
    "bbc.com",
    "techcrunch.com",
    "arstechnica.com",
    "cnbc.com",
)


def write_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.replace(temporary, path)


def collect_articles(feeds=None):
    rows, health = [], []
    for category, sources in (feeds or RSS_FEEDS).items():
        for source in sources:
            record = {
                "source": source["name"],
                "category": category,
                "status": "error",
                "articles": 0,
            }
            try:
                response = requests.get(
                    source["url"],
                    timeout=(5, 15),
                    headers={"User-Agent": "DailyBrief/2.0 RSS reader"},
                )
                response.raise_for_status()
                feed = feedparser.parse(response.content)
                record["parse_warning"] = bool(feed.bozo)
                for entry in feed.entries[:50]:
                    parsed = entry.get("published_parsed") or entry.get(
                        "updated_parsed"
                    )
                    published = (
                        datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
                        if parsed
                        else None
                    )
                    url = entry.get("link", "")
                    try:
                        identity_url = canonical_url(url)
                    except ValueError:
                        identity_url = url
                    description = BeautifulSoup(
                        entry.get("summary") or entry.get("description") or "",
                        "html.parser",
                    ).get_text(" ", strip=True)
                    rows.append(
                        {
                            "id": hashlib.sha256(identity_url.encode()).hexdigest()[
                                :16
                            ],
                            "title": entry.get("title", "").strip(),
                            "url": url,
                            "description": description[:1000],
                            "source": source["name"],
                            "category": category,
                            "published": published,
                            "published_basis": (
                                "published"
                                if entry.get("published_parsed")
                                else "updated" if parsed else "unknown"
                            ),
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    record["articles"] += 1
                record["status"] = "ok" if record["articles"] else "empty"
            except requests.RequestException as exc:
                record["error_type"] = type(exc).__name__
            health.append(record)
    return rows, health


def _allowed_article_url(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme in ("http", "https")
        and not parsed.username
        and not parsed.password
        and parsed.port in (None, 80, 443)
        and any(
            host == allowed or host.endswith("." + allowed) for allowed in ARTICLE_HOSTS
        )
    )


def extract_article(article):
    fallback = {
        "basis": "feed_summary",
        "text": article.get("description", ""),
        "status": "unavailable",
    }
    url = article["url"]
    try:
        # Feed links and redirects must not make the home host fetch arbitrary private services.
        for _ in range(4):
            if not _allowed_article_url(url):
                return {**fallback, "status": "unapproved_host"}
            response = requests.get(
                url,
                timeout=(5, 15),
                allow_redirects=False,
                headers={"User-Agent": "Mozilla/5.0 (compatible; DailyBrief/2.0)"},
            )
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get("Location", ""))
                continue
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            for node in soup.select(
                "script, style, nav, header, footer, aside, form, iframe"
            ):
                node.decompose()
            node = next(
                (
                    soup.select_one(s)
                    for s in (
                        "article",
                        ".article-content",
                        ".post-content",
                        ".story-body",
                        "main",
                    )
                    if soup.select_one(s)
                ),
                soup,
            )
            paragraphs = node.find_all("p")
            text = " ".join(p.get_text(" ", strip=True) for p in paragraphs)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) < 200 or any(
                term in text[:300].lower()
                for term in (
                    "access denied",
                    "enable javascript",
                    "verify you are human",
                )
            ):
                return {**fallback, "status": "insufficient_article_text"}
            return {"basis": "article_text", "text": text[:8000], "status": "ok"}
        return {**fallback, "status": "redirect_limit"}
    except (requests.RequestException, ValueError):
        return fallback


def build_edition(
    rows,
    model,
    output_dir,
    now=None,
    history=None,
    source_health=None,
    top_limit=5,
    quick_limit=10,
):
    now = now or datetime.now(timezone.utc)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "started_at": now.isoformat(),
        "status": "running",
        "stage": "filter",
        "source_health": source_health or [],
    }
    write_json(output_dir / "run.json", manifest)
    try:
        write_json(output_dir / "collected.json", rows)
        candidates, excluded = filter_candidates(rows, now)
        write_json(output_dir / "candidates.json", candidates)
        write_json(output_dir / "exclusions.json", excluded)
        if not candidates:
            raise ValueError("No eligible dated news candidates")
        manifest["stage"] = "group_events"
        write_json(output_dir / "run.json", manifest)
        events = group_events(candidates, model, history)
        write_json(output_dir / "events.json", events)
        manifest["stage"] = "select_events"
        write_json(output_dir / "run.json", manifest)
        decisions = select_events(events, model, top_limit, quick_limit)
        write_json(output_dir / "decisions.json", decisions)
        selected = sorted(
            (d for d in decisions if d["tier"] != "exclude"),
            key=lambda d: (d["tier"] != "top", -d["score"]),
        )
        if not selected:
            raise ValueError("No events met the editorial selection policy")
        article_lookup = {a["id"]: a for a in candidates}
        event_lookup = {e["event_id"]: e for e in events}
        evidence, stories = {}, []
        manifest["stage"] = "synthesize"
        write_json(output_dir / "run.json", manifest)
        for decision in selected:
            event = event_lookup[decision["event_id"]]
            # Three documents bound retrieval while preserving a representative and corroboration.
            ids = [event["representative_id"]] + [
                i for i in event["source_ids"] if i != event["representative_id"]
            ]
            for id in ids[:3]:
                evidence[id] = extract_article(article_lookup[id])
            write_json(output_dir / "evidence.json", evidence)
            stories.append(
                synthesize_event(event, decision, article_lookup, evidence, model)
            )
        edition = {
            "schema_version": 1,
            "generated_at": now.isoformat(),
            "status": "ready_for_review",
            "history_supplied": history is not None,
            "source_health": source_health or [],
            "counts": {
                "collected": len(rows),
                "candidates": len(candidates),
                "events": len(events),
                "top": sum(s["tier"] == "top" for s in stories),
                "quick": sum(s["tier"] == "quick" for s in stories),
            },
            "selected_topics": dict(Counter(s["topic"] for s in stories)),
            "selected_representative_sources": dict(
                Counter(
                    article_lookup[event_lookup[s["event_id"]]["representative_id"]][
                        "source"
                    ]
                    for s in stories
                )
            ),
            "stories": stories,
        }
        write_json(output_dir / "edition.json", edition)
        manifest.update(
            status="ready_for_review",
            stage="complete",
            counts=edition["counts"],
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        write_json(output_dir / "run.json", manifest)
        return edition
    except Exception as exc:
        manifest.update(
            status="failed",
            error_type=type(exc).__name__,
            error=str(exc),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        write_json(output_dir / "run.json", manifest)
        raise


def synthesize_event(event, decision, article_lookup, evidence, model):
    ids = [event["representative_id"]] + [
        i for i in event["source_ids"] if i != event["representative_id"]
    ]
    inputs = []
    for id in ids[:3]:
        words = evidence[id]["text"].split()
        segments = [
            {"segment_id": f"{id}:{n // 25}", "text": " ".join(words[n : n + 25])}
            for n in range(0, len(words), 25)
        ]
        inputs.append(
            {
                "id": id,
                "title": article_lookup[id]["title"],
                **evidence[id],
                "segments": segments,
            }
        )
    if not any(i["text"].strip() for i in inputs):
        raise ValueError("Selected event has no usable evidence")
    summary = model.complete(
        "synthesize",
        {
            "event": event,
            "tier": decision["tier"],
            "evidence": [
                {k: v for k, v in item.items() if k != "text"} for item in inputs
            ],
        },
    )
    text = _text(summary.get("summary"), "summary")
    significance = _text(
        summary.get("why_matters", ""), "why_matters", allow_empty=True
    )
    if len(text.split()) > 110 or len(significance.split()) > 90:
        raise ValueError("Summary exceeded concise edition limits")
    support = summary.get("support")
    if not isinstance(support, list) or not support:
        raise ValueError("Summary needs verifiable source excerpts")
    passages = {
        segment["segment_id"]: {"id": item["id"], **segment}
        for item in inputs
        for segment in item["segments"]
    }
    sections, source_ids, verified_support = set(), set(), []
    for span in support:
        if not isinstance(span, dict):
            raise ValueError("Invalid support passage")
        section, segment_id = span.get("section"), span.get("segment_id")
        if section not in ("summary", "why_matters") or segment_id not in passages:
            raise ValueError("Support must reference a supplied source passage")
        passage = passages[segment_id]
        verified_support.append(
            {
                "section": section,
                "id": passage["id"],
                "segment_id": segment_id,
                "quote": passage["text"],
            }
        )
        sections.add(section)
        source_ids.add(passage["id"])
    cited = source_ids
    if "summary" not in sections or (significance and "why_matters" not in sections):
        raise ValueError("Each nonempty summary section needs source support")
    return {
        "event_id": event["event_id"],
        "title": event["title"],
        "novelty": event["novelty"],
        "change": event["change"],
        **decision,
        "summary": text,
        "why_matters": significance,
        "support": verified_support,
        "sources": [
            {
                "id": id,
                "source": article_lookup[id]["source"],
                "url": article_lookup[id]["url"],
                "published": article_lookup[id]["published"],
                "used_in_summary": id in cited,
                "evidence_basis": (
                    evidence[id]["basis"] if id in evidence else "metadata_only"
                ),
            }
            for id in event["source_ids"]
        ],
    }
