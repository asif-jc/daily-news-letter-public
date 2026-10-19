import hashlib
from collections import deque
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def canonical_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Expected a public HTTP article URL")
    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query)
        if not k.lower().startswith("utm_")
        and k.lower()
        not in {"fbclid", "gclid", "at_medium", "at_campaign", "ref", "source"}
    ]
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            urlencode(sorted(query)),
            "",
        )
    )


def filter_candidates(rows, now, hours=24, limit=100):
    accepted, excluded, seen = [], [], set()
    for ordinal, row in enumerate(rows):
        item = dict(row)
        reason = None
        try:
            url = canonical_url(item.get("url", ""))
        except (ValueError, TypeError):
            reason = "invalid_url"
            url = ""
        try:
            published = datetime.fromisoformat(
                (item.get("published") or "").replace("Z", "+00:00")
            )
            if published.tzinfo is None:
                raise ValueError("Date needs a timezone")
        except (ValueError, TypeError):
            published = None
        if not reason:
            if not published:
                reason = "unknown_date"
            elif published > now + timedelta(minutes=5):
                reason = "future_date"
            elif published < now - timedelta(hours=hours):
                reason = "outside_window"
            elif not item.get("title", "").strip():
                reason = "missing_title"
            elif "sponsored" in item["title"].lower():
                reason = "sponsored"
            elif url in seen:
                reason = "duplicate_url"
        if reason:
            excluded.append(
                {
                    "id": item.get("id"),
                    "ordinal": ordinal,
                    "source": item.get("source"),
                    "reason": reason,
                }
            )
            continue
        seen.add(url)
        item["url"] = url
        item.setdefault("id", hashlib.sha256(url.encode()).hexdigest()[:16])
        item["published"] = published.astimezone(timezone.utc).isoformat()
        item["observation_ordinal"] = ordinal
        accepted.append(item)
    # A bounded model call should not silently become a first-publisher-only shortlist.
    queues = {}
    for item in sorted(accepted, key=lambda a: a["published"], reverse=True):
        queues.setdefault(item["source"], deque()).append(item)
    bounded = []
    while any(queues.values()) and len(bounded) < limit:
        for queue in queues.values():
            if queue and len(bounded) < limit:
                bounded.append(queue.popleft())
    excluded.extend(
        {
            "id": item["id"],
            "ordinal": item["observation_ordinal"],
            "source": item["source"],
            "reason": "candidate_budget",
        }
        for queue in queues.values()
        for item in queue
    )
    return bounded, excluded


def _text(value, field, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"Expected text for {field}")
    return value.strip()


def group_events(articles, model, history=None, instructions=None):
    if not articles:
        return []
    lookup = {a["id"]: a for a in articles}
    if len(lookup) != len(articles):
        raise ValueError("Candidate IDs must be unique")
    previous = (history or {}).get("stories", (history or {}).get("events", []))
    historical = {a["event_id"]: a for a in previous}
    data = {
        "articles": [
            {k: a.get(k) for k in ("id", "title", "description", "source", "published")}
            for a in articles
        ],
        "history": [
            {k: a.get(k) for k in ("event_id", "title", "summary")} for a in previous
        ],
    }
    options = {} if instructions is None else {"instructions": instructions}
    groups = model.complete("group_events", data, **options).get("events")
    if not isinstance(groups, list):
        raise ValueError("Expected events list")
    result, seen = [], set()
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("Expected event object")
        ids = group.get("source_ids")
        if (
            not isinstance(ids, list)
            or not ids
            or not all(isinstance(i, str) for i in ids)
            or len(set(ids)) != len(ids)
            or not set(ids) <= lookup.keys()
            or seen.intersection(ids)
        ):
            raise ValueError("Event membership must partition known article IDs")
        representative = group.get("representative_id")
        if representative not in ids:
            raise ValueError("Representative must belong to event")
        novelty = group.get("novelty")
        previous_id = group.get("previous_event_id")
        if novelty not in ("new", "repeat", "update"):
            raise ValueError("Invalid event novelty")
        if novelty in ("repeat", "update") and previous_id not in historical:
            raise ValueError("Repeat/update must reference supplied history")
        if novelty == "new" and previous_id is not None:
            raise ValueError("New event must not reference history")
        change = _text(
            group.get("change", ""), "change", allow_empty=novelty != "update"
        )
        event_id = (
            previous_id
            or hashlib.sha256("|".join(sorted(ids)).encode()).hexdigest()[:16]
        )
        result.append(
            {
                "event_id": event_id,
                "source_ids": ids,
                "representative_id": representative,
                "title": lookup[representative]["title"],
                "novelty": novelty,
                "change": change,
                "reason": _text(group.get("reason"), "reason"),
                "sources": sorted({lookup[i]["source"] for i in ids}),
                "category": lookup[representative]["category"],
                "description": lookup[representative].get("description", ""),
            }
        )
        seen.update(ids)
    # The model need only report semantic matches; all unmatched input is preserved.
    for id, article in lookup.items():
        if id not in seen:
            result.append(
                {
                    "event_id": hashlib.sha256(id.encode()).hexdigest()[:16],
                    "source_ids": [id],
                    "representative_id": id,
                    "title": article["title"],
                    "novelty": "new",
                    "change": "",
                    "reason": "No event match identified.",
                    "sources": [article["source"]],
                    "category": article["category"],
                    "description": article.get("description", ""),
                }
            )
    if len({e["event_id"] for e in result}) != len(result):
        raise ValueError("Historical event was split across groups")
    return result


def select_events(events, model, top_limit=5, quick_limit=10):
    eligible = [e for e in events if e["novelty"] != "repeat"]
    decisions = [
        {
            "event_id": e["event_id"],
            "tier": "exclude",
            "score": 0,
            "topic": "repeat",
            "decision_basis": "history",
            "reason": "Already covered without a material new development.",
        }
        for e in events
        if e["novelty"] == "repeat"
    ]
    if not eligible:
        return decisions
    raw = model.complete(
        "select_events",
        {
            "events": [
                {
                    k: (e.get(k, "")[:300] if k == "description" else e.get(k))
                    for k in (
                        "event_id",
                        "title",
                        "description",
                        "sources",
                        "category",
                        "novelty",
                        "change",
                    )
                }
                for e in eligible
            ],
            "top_limit": top_limit,
            "quick_limit": quick_limit,
        },
    ).get("decisions")
    if not isinstance(raw, list):
        raise ValueError("Expected selection decisions")
    expected = {e["event_id"] for e in eligible}
    seen, counts = set(), {"top": 0, "quick": 0}
    for decision in raw:
        if not isinstance(decision, dict):
            raise ValueError("Expected decision object")
        id = decision.get("event_id")
        if id not in expected or id in seen:
            raise ValueError("Unknown or repeated event selection")
        tier = decision.get("tier")
        if tier not in ("top", "quick"):
            raise ValueError("Model shortlist must contain top/quick stories only")
        score = decision.get("score")
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not 0 <= score <= 10
        ):
            raise ValueError("Importance score must be between zero and ten")
        decision = {
            "event_id": id,
            "tier": tier,
            "score": score,
            "topic": _text(decision.get("topic"), "topic"),
            "reason": _text(decision.get("reason"), "reason"),
            "decision_basis": "model",
        }
        decisions.append(decision)
        seen.add(id)
        if tier in counts:
            counts[tier] += 1
    if counts["top"] > top_limit or counts["quick"] > quick_limit:
        raise ValueError("Selection exceeded the edition budget")
    decisions.extend(
        {
            "event_id": e["event_id"],
            "tier": "exclude",
            "score": None,
            "topic": None,
            "decision_basis": "edition_budget",
            "reason": "Not selected within the edition relevance/diversity budget.",
        }
        for e in eligible
        if e["event_id"] not in seen
    )
    return decisions
