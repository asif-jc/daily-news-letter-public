"""Restartable orchestration from public feed collection to a private review edition."""

import hashlib
import json
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .analysis import ANALYSE_PROMPT, REVIEW_PROMPT, analyse_batch, input_key
from .editorial import (
    CURATE_PROMPT,
    timestamp,
    prepare_articles,
    classify_events,
    place_stories,
    validate_article_holds,
)
from .grouping import GROUP_PAIR_PROMPT, group_events_bounded
from .ingest import collect_articles, extract_article, write_json
from .llm import INSTRUCTIONS, model_messages, parse_response
from .render import render_edition
from .reader_assets import write_reader_assets
from .review import render_private_review
from .sources import RSS_FEEDS
from .synthesis import reviewed_event, compose_story

WORKFLOW_VERSION = 3
GROUPING_VERSION = 3
RENDER_VERSION = 8
BATCH_SIZE = 5
PROMPTS = {
    "analyse_articles": ANALYSE_PROMPT,
    "review_articles": REVIEW_PROMPT,
    "curate_events": CURATE_PROMPT,
    "synthesize": INSTRUCTIONS["synthesize"],
    "compare_event_pairs": GROUP_PAIR_PROMPT,
}


def run_workflow(
    store,
    model,
    output_root,
    run_id=None,
    now=None,
    rows=None,
    source_health=None,
    profile=None,
    history=None,
    pool_days=7,
    featured_limit=6,
    include_review_previews=False,
    article_holds=None,
):
    if not 1 <= pool_days <= 30 or not 0 <= featured_limit <= 20:
        raise ValueError("Invalid rolling window or featured limit")
    if run_id is not None and article_holds is not None:
        raise ValueError("Resume uses frozen editorial holds; start a new run")
    if run_id is None:
        article_holds = validate_article_holds(
            article_holds if article_holds is not None else []
        )
        held_ids = {h["article_id"] for h in article_holds}
        now = now or datetime.now(timezone.utc)
        profile = profile or json.loads(
            Path(__file__).with_name("profile.json").read_text()
        )
        archives = store.editions_within(profile["id"], now=now, days=7)
        # Preview identity can persist without falsely claiming an edition was published.
        identity = {}
        for edition in archives:
            for story in edition["stories"]:
                identity.setdefault(story["event_id"], story)
        published = (
            history
            if history is not None
            else store.published_history(profile["id"], now=now, days=pool_days)
        )

        def contains_held_source(story):
            return any(s["id"] in held_ids for s in story.get("sources", []))

        if any(contains_held_source(s) for s in published.get("stories", [])) or any(
            e.get("publication_status") == "published"
            and any(contains_held_source(s) for s in e["stories"])
            for e in archives
        ):
            raise ValueError(
                "Held article appears in published history; review that release separately"
            )
        # A rejected preview cannot supply the next edition's event comparison baseline.
        identity = {
            key: story
            for key, story in identity.items()
            if not contains_held_source(story)
        }
        published_identity = {
            story["event_id"]: story for story in published.get("stories", [])
        }
        # When old previews split one incident, the published baseline wins any later reconciliation.
        for event_id, story in identity.items():
            published_identity.setdefault(event_id, story)
        identity = published_identity
        archive_views = []
        for edition in archives:
            published_at = timestamp(edition.get("published_at"))
            is_published = (
                edition.get("publication_status") == "published"
                and published_at
                and published_at <= now
            )
            if is_published or (
                include_review_previews
                and not any(contains_held_source(story) for story in edition["stories"])
            ):
                archive_views.append(
                    {
                        **edition,
                        "publication_status": (
                            "published" if is_published else "ready_for_review"
                        ),
                    }
                )
        config = {
            "workflow_version": WORKFLOW_VERSION,
            "grouping_version": GROUPING_VERSION,
            "profile": profile,
            "prompts": PROMPTS,
            "model": model.model,
            "pool_days": pool_days,
            "featured_limit": featured_limit,
            "sources": RSS_FEEDS,
            "article_holds": article_holds,
            "archives": archive_views,
            "include_review_previews": include_review_previews,
            "identity_history": {"stories": list(identity.values())},
            "published_history": published,
            "replay_input": (
                {"articles": rows, "source_health": source_health or []}
                if rows is not None
                else None
            ),
        }
        run_id = store.create_run(config, now)
    run_id = str(run_id)
    run = store.get_run(run_id)
    config = run["config"]
    now = run["started_at"]
    if (
        config["workflow_version"] != WORKFLOW_VERSION
        or config.get("grouping_version") != GROUPING_VERSION
        or config["prompts"] != PROMPTS
        or config["model"] != model.model
    ):
        raise ValueError(
            "Unsupported workflow version, prompts or model; start a new run"
        )
    profile = config["profile"]
    model.audit_hook = lambda task, messages, response: store.audit_model(
        run_id, task, messages, response
    )
    output = Path(output_root) / run_id
    output.mkdir(parents=True, exist_ok=True)

    def stage(name, execute, persist=None, item_key=""):
        cached = store.stage_output(run_id, name, item_key)
        if cached is not None:
            return cached
        store.start_stage(run_id, name, item_key)
        try:
            value = execute()
            with store.transaction():
                if persist:
                    persist(value)
                store.complete_stage(run_id, name, value, item_key)
            return value
        except Exception as error:
            store.fail_stage(run_id, name, error, item_key)
            raise

    with store.lock_run(run_id):

        def collect():
            replay = config["replay_input"]
            articles, health = (
                (replay["articles"], replay["source_health"])
                if replay is not None
                else collect_articles(config["sources"])
            )
            if not articles:
                raise ValueError("No articles collected")
            return {"articles": articles, "source_health": health}

        collection = stage(
            "collect", collect, lambda v: store.save_articles(run_id, v["articles"])
        )

        def pool():
            # Analyse all newly collected valid documents, including older background material.
            retained = store.rolling_articles(now, days=config["pool_days"])
            accepted, excluded = prepare_articles(
                collection["articles"] + retained, now, days=config["pool_days"]
            )
            return {"articles": accepted, "exclusions": excluded}

        prepared = stage("pool", pool)
        articles = {a["id"]: a for a in prepared["articles"]}

        def check_holds():
            holds = validate_article_holds(config.get("article_holds", []))
            if {h["article_id"] for h in holds} - set(articles):
                raise ValueError("Unknown held article in this run")
            return holds

        holds = stage("editorial_holds", check_holds)
        held_ids = {h["article_id"] for h in holds}
        evidence, analyses = {}, {}
        pending = []
        cache_hits = 0
        for article in articles.values():
            id = article["id"]
            key = input_key(article, model)

            def obtain(article=article, key=key):
                cached = store.cached_analysis(
                    article["id"], key, now - timedelta(hours=24)
                )
                if cached is not None:
                    return {**cached, "cache_hit": True}
                ev = stage(
                    "retrieve_article",
                    lambda: extract_article(article),
                    lambda v: store.save_evidence(run_id, article["id"], v),
                    item_key=article["id"],
                )
                return {"evidence": ev, "cache_hit": False}

            item = stage(
                "article_input",
                obtain,
                lambda v, id=id: store.save_evidence(run_id, id, v["evidence"]),
                item_key=id,
            )
            cache_hits += bool(item.get("cache_hit"))
            evidence[id] = item["evidence"]
            if "analysis" in item:
                analyses[id] = item["analysis"]
            else:
                pending.append(article)
        for offset in range(0, len(pending), BATCH_SIZE):
            batch = pending[offset : offset + BATCH_SIZE]
            key = hashlib.sha256("|".join(a["id"] for a in batch).encode()).hexdigest()[
                :16
            ]

            def persist(value, batch=batch):
                for a in batch:
                    store.save_analysis(
                        a["id"],
                        input_key(a, model),
                        {"analysis": value[a["id"]], "evidence": evidence[a["id"]]},
                    )

            analyses.update(
                stage(
                    "analyse_articles",
                    lambda batch=batch: analyse_batch(batch, evidence, model),
                    persist,
                    item_key=key,
                )
            )
        stage("analysis_index", lambda: analyses)
        candidates = [
            {
                **a,
                "description": analyses[id]["summary"]
                + " "
                + analyses[id].get("why_matters", ""),
                "evidence_basis": evidence[id]["basis"],
            }
            for id, a in articles.items()
            if a["in_pool"] and analyses[id]["state"] == "ready" and id not in held_ids
        ]

        def compare_pairs(inputs, validate):
            data = {"pairs": inputs}
            key = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

            def execute():
                retained = store.audited_response(
                    run_id,
                    "compare_event_pairs",
                    model_messages("compare_event_pairs", data, GROUP_PAIR_PROMPT),
                )
                if retained is not None:
                    try:
                        return validate(parse_response(retained))
                    except ValueError:
                        # Raw audit is not an accepted checkpoint until the current contract validates it.
                        pass
                return validate(
                    model.complete(
                        "compare_event_pairs", data, instructions=GROUP_PAIR_PROMPT
                    )
                )

            return stage("compare_event_pairs", execute, item_key=key)

        events = stage(
            "group",
            lambda: group_events_bounded(
                candidates,
                model,
                config["identity_history"],
                compare_batch=compare_pairs,
            ),
            lambda v: store.save_events(run_id, v),
        )
        decisions = stage(
            "curate",
            lambda: classify_events(events, analyses, model, profile),
            lambda v: store.save_decisions(run_id, "curate", v, profile),
        )
        lookup = {e["event_id"]: e for e in events}
        relevant = [d for d in decisions if d["tier"] != "exclude"]
        stories = []
        summary_failures = []
        for decision in relevant:
            event = lookup[decision["event_id"]]
            primary = event["representative_id"]
            a = analyses[primary]

            def summary(event=event, decision=decision, a=a):
                if event.get("grouping_conflicts"):
                    return {
                        "state": "needs_review",
                        "event_id": event["event_id"],
                        "reason": "Contradictory event comparisons; component withheld.",
                        "grouping_conflicts": event["grouping_conflicts"],
                    }
                if len(event["source_ids"]) > 1:
                    return reviewed_event(
                        event, decision, articles, evidence, model
                    ) or {"state": "needs_review"}
                return {
                    "event_id": event["event_id"],
                    "title": event["title"],
                    "summary": a["summary"],
                    "why_matters": a["why_matters"],
                    "support": a["support"],
                    "summary_review": a["review"],
                }

            story = stage("summarize_event", summary, item_key=event["event_id"])
            if story.get("state") == "needs_review":
                summary_failures.append(story)
                continue
            stories.append(
                compose_story(
                    event,
                    decision,
                    story,
                    articles,
                    analyses,
                    evidence,
                    config["identity_history"],
                    now,
                )
            )
        published_ids = set(
            config["published_history"].get("featured_event_ids", [])
        ) | {
            s["event_id"]
            for s in config["published_history"].get("stories", [])
            if s.get("featured", True)
        }
        for event in events:
            if published_ids.intersection(event.get("previous_event_ids", [])):
                published_ids.add(event["event_id"])
        stories = place_stories(stories, published_ids, config["featured_limit"])
        source_counts = {}
        for source in {a["source"] for a in articles.values()}:
            source_counts[source] = {
                "observed": sum(a["source"] == source for a in collection["articles"]),
                "analysed": sum(a["source"] == source for a in articles.values()),
                "in_pool": sum(
                    a["source"] == source and a["in_pool"] for a in articles.values()
                ),
                "ready": sum(
                    articles[id]["source"] == source and a["state"] == "ready"
                    for id, a in analyses.items()
                ),
                "editorial_holds": sum(
                    articles[id]["source"] == source for id in held_ids
                ),
                "reader_events": sum(
                    any(s["source"] == source for s in story["sources"])
                    for story in stories
                ),
            }
        counts = {
            "sources": source_counts,
            "collected": len(collection["articles"]),
            "analysed": len(analyses),
            "cache_hits": cache_hits,
            "editorial_holds": len(held_ids),
            "article_repairs": sum(a.get("attempts", 0) > 1 for a in analyses.values()),
            "pool_articles": sum(a["in_pool"] for a in articles.values()),
            "events": len(events),
            "relevant": len(relevant),
            "stories": len(stories),
            "featured": sum(s["featured"] for s in stories),
            "summary_failures": len(summary_failures),
            "grouping_holds": sum(bool(e.get("grouping_conflicts")) for e in events),
            "extraction": dict(Counter(v["basis"] for v in evidence.values())),
            "analysis_states": dict(Counter(a["state"] for a in analyses.values())),
            "topics": dict(Counter(t for s in stories for t in s["topics"])),
        }

        def require_stories():
            if not stories:
                raise ValueError("No reviewed reader stories; edition withheld")
            return {"stories": len(stories)}

        stage("validate_edition", require_stories)
        edition = stage(
            "edition",
            lambda: {
                "schema_version": 3,
                "run_id": run_id,
                "status": "ready_for_review",
                "publication_status": "ready_for_review",
                "generated_at": now.isoformat(),
                "profile_id": profile["id"],
                "profile_version": profile["version"],
                "counts": counts,
                "source_health": collection["source_health"],
                "stories": stories,
                "summary_failures": summary_failures,
            },
            lambda v: store.save_edition(run_id, v, profile),
        )

        def render():
            reader = render_edition(edition, config["archives"])
            review = render_private_review(
                edition, config, prepared, analyses, decisions, events
            )
            return {"reader": reader, "review": review}

        rendered = stage("render", render, item_key=str(RENDER_VERSION))

        def export():
            write_reader_assets(output)
            archive_dir = output / "archive"
            archive_dir.mkdir(exist_ok=True)
            for old in config["archives"]:
                old_html = render_edition(
                    old, [a for a in config["archives"] if a["run_id"] != old["run_id"]],
                    archive=True,
                )
                (archive_dir / (old["run_id"] + ".html")).write_text(
                    old_html.replace("<head>", '<head><base href="../">', 1)
                )
            for name, text in [
                ("index.html", rendered["reader"]),
                ("review.html", rendered["review"]),
            ]:
                temp = output / (name + ".tmp")
                temp.write_text(text)
                temp.replace(output / name)
            write_json(output / "edition.json", edition)
            write_json(
                output / "run.json",
                {"run_id": run_id, "counts": counts, "status": "ready_for_review"},
            )
            return {
                "reader_sha256": hashlib.sha256(rendered["reader"].encode()).hexdigest()
            }

        # A retained database checkpoint cannot prove that local preview files still exist.
        stage("export", export, item_key=str(uuid.uuid4()))
        stage("storage", store.stats)
        store.finish_run(run_id)
        return edition
