"""Collect public feeds and retrieve bounded publisher evidence."""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from .sources import RSS_FEEDS, FEED_HOSTS, PUBLISHER_HOSTS
from .urls import canonical_url, allowed_public_url

MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024


def download_public(url, hosts):
    """Bound transferred bytes and recheck each redirect before fetching it."""
    for _ in range(4):
        if not allowed_public_url(url, hosts):
            raise ValueError("unapproved_host")
        response = requests.get(
            url,
            timeout=(5, 15),
            allow_redirects=False,
            stream=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DailyBrief/3.0)"},
        )
        try:
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get("Location", ""))
                continue
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(chunk_size=65536):
                size += len(chunk)
                if size > MAX_DOWNLOAD_BYTES:
                    raise ValueError("download_too_large")
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            response.close()
    raise ValueError("redirect_limit")


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
                feed = feedparser.parse(download_public(source["url"], FEED_HOSTS))
                record["parse_warning"] = bool(feed.bozo)
                for entry in feed.entries[:50]:
                    parsed = entry.get("published_parsed") or entry.get(
                        "updated_parsed"
                    )
                    updated_parts = entry.get("updated_parsed")
                    updated = (
                        datetime(*updated_parts[:6], tzinfo=timezone.utc).isoformat()
                        if updated_parts
                        else None
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
                            "updated": updated,
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
            except (requests.RequestException, ValueError) as exc:
                record["error_type"] = type(exc).__name__
            health.append(record)
    return rows, health


def extract_article(article):
    fallback = {
        "basis": "feed_summary",
        "text": article.get("description", ""),
        "status": "unavailable",
    }
    url = article["url"]
    try:
        content = download_public(url, PUBLISHER_HOSTS)
        soup = BeautifulSoup(content, "html.parser")
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
    except ValueError as error:
        return {**fallback, "status": str(error)}
    except requests.RequestException:
        return fallback
