"""
=== workflow.py ===

Purpose: Produce a retained news edition and private HTML review artifacts.
Extended Description:
    Coordinates stages; SQL belongs in store.py and publication remains outside this workflow.
Usage:
    python -m src.news --env-file .env
Work Log:
    19/10/2026 -> PostgreSQL-backed news-only MVP.
"""

# ========================================================================
# IMPORTS & CONFIGURATION
# ========================================================================
import hashlib
import json
import shutil
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.mvp_news_aggregator.sources import RSS_FEEDS
from .editorial import qualify_events, select_with_evidence
from .events import filter_candidates, group_events
from .llm import INSTRUCTIONS, prompt_versions
from .pipeline import collect_articles, extract_article, synthesize_event, write_json
from .render import RENDER_VERSION, render_edition, render_review

PROFILE_PATH = Path(__file__).with_name("profile.json")
WORKFLOW_VERSION = 1


# ========================================================================
# PRIMARY EXECUTION
# ========================================================================


def run_workflow(
    store,
    model,
    output_root,
    run_id=None,
    now=None,
    rows=None,
    source_health=None,
    profile=None,
    top_limit=5,
    quick_limit=10,
    history=None,
):
    if (
        not 0 <= top_limit <= 10
        or not 0 <= quick_limit <= 20
        or not top_limit + quick_limit
    ):
        raise ValueError("Invalid edition limits")
    if run_id is None:
        profile = profile or json.loads(PROFILE_PATH.read_text())
        if not isinstance(profile.get("id"), str) or not isinstance(
            profile.get("version"), int
        ):
            raise ValueError("Profile needs an ID and integer version")
        config = {
            "workflow_version": WORKFLOW_VERSION,
            "profile": profile,
            "prompts": dict(INSTRUCTIONS),
            "prompt_versions": prompt_versions(),
            "model": model.model,
            "top_limit": top_limit,
            "quick_limit": quick_limit,
            "history": (
                history
                if history is not None
                else store.published_history(profile["id"])
            ),
            "sources": RSS_FEEDS,
            "input_mode": "replay" if rows is not None else "feeds",
            "replay_input": (
                {"articles": rows, "source_health": source_health or []}
                if rows is not None
                else None
            ),
        }
        run_id = store.create_run(config, now or datetime.now(timezone.utc))
    run_id = str(run_id)
    run = store.get_run(run_id)
    config = run["config"]
    now = run["started_at"]
    if (
        config["workflow_version"] != WORKFLOW_VERSION
        or config["prompt_versions"] != prompt_versions()
        or config["model"] != model.model
    ):
        raise ValueError(
            "Workflow, prompts or model changed; start a new run instead of resuming"
        )
    profile = config["profile"]
    top_limit = config["top_limit"]
    quick_limit = config["quick_limit"]
    output_dir = Path(output_root) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    model.audit_hook = lambda task, messages, response: store.audit_model(
        run_id, task, messages, response
    )

    def stage(name, execute, persist=None, item_key=""):
        completed = store.stage_output(run_id, name, item_key)
        if completed is not None:
            return completed
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
            replay = config.get("replay_input")
            collected, health = (
                (replay["articles"], replay["source_health"])
                if replay is not None
                else collect_articles(config.get("sources", RSS_FEEDS))
            )
            if not collected:
                raise ValueError("No articles collected")
            return {"articles": collected, "source_health": health}

        collection = stage(
            "collect", collect, lambda v: store.save_articles(run_id, v["articles"])
        )

        def clean():
            candidates, exclusions = filter_candidates(collection["articles"], now)
            return {"candidates": candidates, "exclusions": exclusions}

        filtered = stage(
            "clean",
            clean,
            lambda v: store.save_filter(run_id, v["candidates"], v["exclusions"]),
        )
        candidates = filtered["candidates"]
        if not candidates:
            error = ValueError("No eligible candidates")
            store.fail_stage(run_id, "clean", error)
            raise error
        events = stage(
            "group",
            lambda: group_events(candidates, model, config["history"]),
            lambda v: store.save_events(run_id, v),
        )
        qualifications = stage(
            "qualify",
            lambda: qualify_events(events, model, profile),
            lambda v: store.save_decisions(run_id, "qualify", v, profile),
        )
        tags = {q["event_id"]: q["tag"] for q in qualifications}
        shortlist = [e for e in events if tags[e["event_id"]] != "irrelevant"]
        article_lookup = {a["id"]: a for a in candidates}

        def retrieve():
            evidence = {}
            for event in shortlist:
                ids = [event["representative_id"]] + [
                    i for i in event["source_ids"] if i != event["representative_id"]
                ]
                for id in ids[:3]:
                    evidence[id] = stage(
                        "retrieve_article",
                        lambda id=id: extract_article(article_lookup[id]),
                        lambda value, id=id: store.save_evidence(run_id, id, value),
                        item_key=id,
                    )
            return evidence

        evidence = stage("retrieve", retrieve)

        def select():
            rows = (
                select_with_evidence(
                    shortlist, evidence, model, profile, top_limit, quick_limit
                )
                if shortlist
                else []
            )
            rows.extend(
                {
                    "event_id": q["event_id"],
                    "tier": "exclude",
                    "score": None,
                    "topic": "Excluded",
                    "reason": q["reason"],
                    "decision_basis": (
                        "already_covered"
                        if q["decision_basis"] == "already_covered"
                        else "off_brief"
                    ),
                }
                for q in qualifications
                if q["tag"] == "irrelevant"
            )
            return rows

        decisions = stage(
            "select",
            select,
            lambda v: store.save_decisions(run_id, "select", v, profile),
        )
        selected = sorted(
            (d for d in decisions if d["tier"] != "exclude"),
            key=lambda d: (d["tier"] != "top", -d["score"]),
        )
        if not selected:
            error = ValueError("No events met the editorial policy")
            store.fail_stage(run_id, "select", error)
            raise error
        event_lookup = {e["event_id"]: e for e in events}

        def synthesize():
            return [
                stage(
                    "synthesize_event",
                    lambda d=d: synthesize_event(
                        event_lookup[d["event_id"]], d, article_lookup, evidence, model
                    ),
                    item_key=d["event_id"],
                )
                for d in selected
            ]

        stories = stage("synthesize", synthesize)
        edition = {
            "schema_version": 2,
            "run_id": run_id,
            "generated_at": now.isoformat(),
            "status": "ready_for_review",
            "profile_id": profile["id"],
            "profile_version": profile["version"],
            "source_health": collection["source_health"],
            "counts": {
                "collected": len(collection["articles"]),
                "candidates": len(candidates),
                "events": len(events),
                "qualified": len(shortlist),
                "top": sum(s["tier"] == "top" for s in stories),
                "quick": sum(s["tier"] == "quick" for s in stories),
            },
            "selected_topics": dict(Counter(s["topic"] for s in stories)),
            "stories": stories,
        }
        edition = stage(
            "edition", lambda: edition, lambda v: store.save_edition(run_id, v, profile)
        )

        def render():
            stages = list(
                store.connection.execute(
                    "SELECT name,item_key,status,attempts,started_at,finished_at,error_type FROM stages WHERE run_id=%s AND name!=%s ORDER BY started_at,name,item_key",
                    (run_id, "render"),
                )
            )
            return {
                "renderer_version": RENDER_VERSION,
                "reader": render_edition(edition),
                "review": render_review(
                    edition,
                    collection["articles"],
                    candidates,
                    events,
                    qualifications,
                    decisions,
                    profile,
                    config["prompts"],
                    stages,
                ),
            }

        rendered = stage("render", render, item_key=str(RENDER_VERSION))

        def export():
            assets = output_dir / "assets"
            assets.mkdir(exist_ok=True)
            shutil.copyfile(
                Path(__file__).resolve().parents[2] / "assets" / "dunder_park.jpg",
                assets / "dunder_park.jpg",
            )
            for name, content in [
                ("index.html", rendered["reader"]),
                ("review.html", rendered["review"]),
            ]:
                temporary = output_dir / (name + ".tmp")
                temporary.write_text(content)
                temporary.replace(output_dir / name)
            write_json(output_dir / "edition.json", edition)
            write_json(
                output_dir / "run.json",
                {
                    "run_id": run_id,
                    "status": "ready_for_review",
                    "counts": edition["counts"],
                },
            )
            return {
                "reader_sha256": hashlib.sha256(
                    rendered["reader"].encode()
                ).hexdigest(),
                "review_sha256": hashlib.sha256(
                    rendered["review"].encode()
                ).hexdigest(),
            }

        # Exports can be repeated onto another local disk; each attempt needs its own outcome.
        stage("export", export, item_key=str(uuid.uuid4()))
        stage("storage", store.stats)
        store.finish_run(run_id)
        return edition
