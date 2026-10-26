"""Compose and review multi-source event summaries against retained evidence."""

import hashlib
import json

from .editorial import story_freshness
from .urls import _text
from .analysis import review_batch


def synthesize_event(event, decision, article_lookup, evidence, model, max_sources=3):
    ids = [event["representative_id"]] + [
        i for i in event["source_ids"] if i != event["representative_id"]
    ]
    inputs = []
    for id in (ids if max_sources is None else ids[:max_sources]):
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
    if not isinstance(summary, dict):
        raise ValueError("Expected an event summary object")
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
        if (
            section not in ("summary", "why_matters")
            or not isinstance(segment_id, str)
            or segment_id not in passages
        ):
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


def source_usage(story):
    cited = {span["id"] for span in story["support"]}
    return {
        **story,
        "sources": [
            {**source, "used_in_summary": source["id"] in cited}
            for source in story["sources"]
        ],
    }


def reviewed_event(event, decision, articles, evidence, model):
    feedback = ""
    for attempt in (1, 2):
        try:
            story = synthesize_event(
                {**event, "reviewer_feedback": feedback},
                decision,
                articles,
                evidence,
                model,
                max_sources=None,
            )
        except ValueError as error:
            feedback = "Invalid event synthesis: " + str(error)
            continue
        passages = [
            {"passage_id": f"{id}:full", "text": evidence[id]["text"]}
            for id in (
                [event["representative_id"]]
                + [i for i in event["source_ids"] if i != event["representative_id"]]
            )
        ]
        inputs = [
            {
                "id": "e1",
                "title": story["title"],
                "passages": passages,
                "draft": {
                    "summary": story["summary"],
                    "why_matters": story["why_matters"],
                },
            }
        ]
        try:
            review = review_batch(inputs, model, task="review_event")[0]
        except ValueError as error:
            feedback = "Invalid event review: " + str(error)
            continue
        if review["verdict"] == "approved":
            return {**source_usage(story), "summary_review": review["reason"]}
        if attempt == 2 and set(review.get("unsupported_sections", [])) == {
            "why_matters"
        }:
            facts = {
                **story,
                "why_matters": "",
                "support": [s for s in story["support"] if s["section"] == "summary"],
            }
            try:
                checked = review_batch(
                    [
                        {
                            **inputs[0],
                            "draft": {"summary": facts["summary"], "why_matters": ""},
                        }
                    ],
                    model,
                    task="review_event",
                )[0]
            except ValueError as error:
                feedback = "Invalid event review: " + str(error)
                continue
            if checked["verdict"] == "approved":
                return {
                    **source_usage(facts),
                    "summary_review": checked["reason"],
                    "significance_omitted": True,
                }
            review = checked
        feedback = review["reason"]
    return {"state": "needs_review", "review": feedback, "event_id": event["event_id"]}


def compose_story(event, decision, story, articles, analyses, evidence, history, now):
    primary = event["representative_id"]
    topics = list(
        dict.fromkeys(t for i in event["source_ids"] for t in analyses[i]["topics"])
    )
    geography = list(
        dict.fromkeys(g for i in event["source_ids"] for g in analyses[i]["geography"])
    )
    cited = (
        {s["id"] for s in story.get("sources", []) if s.get("used_in_summary")}
        if len(event["source_ids"]) > 1
        else {primary}
    )
    sources = [
        {
            "id": id,
            "source": articles[id]["source"],
            "url": articles[id]["url"],
            "published": articles[id].get("published"),
            "updated": articles[id].get("updated"),
            "used_in_summary": id in cited,
            "evidence_basis": evidence[id]["basis"],
        }
        for id in event["source_ids"]
    ]
    previous = next(
        (s for s in history["stories"] if s["event_id"] == event["event_id"]),
        {},
    )
    # Publishers can change facts without changing dates; lineage and retained text distinguish updates.
    revision = (
        hashlib.sha256(
            json.dumps(
                [
                    previous.get("revision_key", "initial"),
                    [
                        (
                            i,
                            articles[i].get("published"),
                            articles[i].get("updated"),
                            hashlib.sha256(evidence[i]["text"].encode()).hexdigest(),
                        )
                        for i in sorted(event["source_ids"])
                    ],
                ]
            ).encode()
        ).hexdigest()[:24]
        if event["novelty"] == "update"
        else previous.get("revision_key", "initial")
    )
    return {
        **story,
        **decision,
        "revision_key": revision,
        "novelty": event["novelty"],
        "change": event.get("change", ""),
        "topics": topics,
        "geography": geography,
        "sources": sources,
        "freshness": story_freshness(event, articles, now),
    }
