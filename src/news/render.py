"""
=== render.py ===

Purpose: Produce separate reader and private editorial-review HTML.
Extended Description:
    Consumes saved data only; model calls and publishing belong elsewhere.
Usage:
    render_edition(edition); render_review(...).
Work Log:
    19/10/2026 -> PostgreSQL-backed news-only MVP.
"""

# ========================================================================
# IMPORTS & CONFIGURATION
# ========================================================================
import html
import json
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

RENDER_VERSION = 3

STYLE = """
:root{color-scheme:light;--paper:#f7f5f0;--ink:#182a2c;--muted:#566969;--rule:#d9dfd8;--accent:#166c62}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.65 system-ui,sans-serif}
main{max-width:1080px;margin:auto;padding:46px 28px 70px}header{border-top:5px solid var(--ink);border-bottom:1px solid var(--rule);padding:22px 0 26px;margin-bottom:35px}
h1{font-family:Georgia,serif;font-size:clamp(38px,7vw,68px);line-height:1.05;margin:8px 0 16px;letter-spacing:-1.6px}
h2{font-family:Georgia,serif;font-size:28px;line-height:1.25;margin:8px 0 16px}h3{font-size:20px;line-height:1.3}.eyebrow{font-size:12px;letter-spacing:1.8px;text-transform:uppercase;font-weight:700;color:var(--accent)}
.meta,.sources{font-size:13px;color:var(--muted)}.intro{max-width:650px;color:var(--muted)}a{color:var(--accent);text-underline-offset:3px}
.leads{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 36px}.story{padding:24px 0;border-top:1px solid var(--rule)}.leads .story:first-child{grid-column:1/-1}.leads .story:first-child h2{font-size:38px;max-width:840px}
.story p{margin:12px 0}.significance{padding-left:14px;border-left:3px solid var(--accent)}.significance b{display:block;font-size:12px;text-transform:uppercase;letter-spacing:1px}
.section-label{margin-top:40px;font-size:13px;letter-spacing:2px;text-transform:uppercase}.quick .story{display:grid;grid-template-columns:1fr 1.7fr;gap:24px}.quick h2{font-size:23px}.sources a{display:inline-block;margin-right:12px}
footer{border-top:1px solid var(--ink);margin-top:38px;padding-top:18px;font-size:12px;color:var(--muted)}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid var(--rule);padding:8px;text-align:left;vertical-align:top}.scroll{overflow-x:auto}pre{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;background:#e9eee8;padding:16px}details{margin:12px 0;padding:12px;background:#fff}summary{cursor:pointer;font-weight:600}
@media(max-width:650px){main{padding:24px 18px 45px}.leads{display:block}.quick .story{display:block}.leads .story:first-child h2{font-size:30px}h2{font-size:26px}}
"""


# ========================================================================
# RENDERING HELPERS
# ========================================================================


def escape(value):
    return html.escape(str(value), quote=True)


def safe_link(url):
    try:
        p = urlsplit(url)
        return (
            url
            if p.scheme in ("http", "https")
            and p.hostname
            and not p.username
            and not p.password
            else None
        )
    except (ValueError, TypeError):
        return None


def page(title, body):
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>{STYLE}</style></head><body><main>{body}</main></body></html>'


def render_edition(edition):
    date = (
        datetime.fromisoformat(edition["generated_at"].replace("Z", "+00:00"))
        .astimezone(ZoneInfo("Pacific/Auckland"))
        .strftime("%A, %d %B %Y")
    )
    body = f'<header><div class="eyebrow">News / Technology / Business / Science</div><h1>The Daily Brief</h1><div class="meta">{escape(date)} · New Zealand time</div><p class="intro">A concise selection of developments worth understanding, with the original reporting one click away.</p></header>'
    for tier, label, cls in [
        ("top", "The lead stories", "leads"),
        ("quick", "Also worth knowing", "quick"),
    ]:
        stories = [s for s in edition["stories"] if s["tier"] == tier]
        if not stories:
            continue
        body += f'<h2 class="section-label">{label}</h2><section class="{cls}">'
        for story in stories:
            links = []
            seen = set()
            for source in story["sources"]:
                url = safe_link(source.get("url", ""))
                if url and url not in seen:
                    links.append(
                        f'<a href="{escape(url)}" rel="noopener noreferrer">{escape(source["source"])}</a>'
                    )
                    seen.add(url)
            why = (
                f'<p class="significance"><b>Why it matters</b>{escape(story["why_matters"])}</p>'
                if story.get("why_matters")
                else ""
            )
            fallback = any(
                s.get("used_in_summary") and s.get("evidence_basis") == "feed_summary"
                for s in story["sources"]
            )
            note = "<span>Includes RSS-summary evidence.</span>" if fallback else ""
            body += f'<article class="story"><div><div class="eyebrow">{escape(story.get("topic","News"))}</div><h2>{escape(story["title"])}</h2></div><div><p>{escape(story["summary"])}</p>{why}<div class="sources">{" ".join(links)} {note}</div></div></article>'
        body += "</section>"
    body += "<footer>Summaries are generated from source reporting with AI assistance. Follow the links for the original articles.</footer>"
    return page("The Daily Brief | " + date, body)


def render_review(
    edition,
    collected,
    candidates,
    events,
    qualifications,
    decisions,
    profile,
    prompts,
    stages,
):
    body = '<header><div class="eyebrow">Private editorial review</div><h1>How this edition was made</h1><p><a href="index.html">Read the news edition</a></p></header>'
    counts = {}
    eligible = {a["observation_ordinal"] for a in candidates}
    selected = {d["event_id"] for d in decisions if d["tier"] != "exclude"}
    for ordinal, a in enumerate(collected):
        row = counts.setdefault(
            a["source"], {"collected": 0, "eligible": 0, "selected_events": 0}
        )
        row["collected"] += 1
        row["eligible"] += ordinal in eligible
    lookup = {a["id"]: a for a in candidates}
    for e in events:
        if e["event_id"] in selected:
            counts[lookup[e["representative_id"]]["source"]]["selected_events"] += 1
    body += '<h2>Sources and counts</h2><div class="scroll"><table><tr><th>Source</th><th>Collected</th><th>Eligible observations</th><th>Selected representative</th></tr>'
    for name, values in counts.items():
        body += (
            f"<tr><td>{escape(name)}</td>"
            + "".join(f"<td>{n}</td>" for n in values.values())
            + "</tr>"
        )
    body += "</table></div><h2>Workflow</h2><p>Collect → clean → group events → qualify broadly → retrieve evidence → select with evidence → synthesize → render.</p>"
    body += '<div class="scroll"><table><tr><th>Stage</th><th>Status</th><th>Seconds</th><th>Attempts</th></tr>'
    for stage in stages:
        if stage.get("item_key"):
            continue
        start, end = stage.get("started_at"), stage.get("finished_at")
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)
        duration = round((end - start).total_seconds(), 2) if start and end else "-"
        body += f'<tr><td>{escape(stage["name"])}</td><td>{escape(stage["status"])}</td><td>{duration}</td><td>{stage["attempts"]}</td></tr>'
    body += (
        "</table></div><details><summary>Per-article execution details</summary><pre>"
        + escape(json.dumps(stages, indent=2, default=str))
        + "</pre></details>"
    )
    body += (
        "<details><summary>Feed health</summary><pre>"
        + escape(json.dumps(edition.get("source_health", []), indent=2))
        + "</pre></details>"
    )
    body += (
        "<h2>Editorial preference</h2><p>"
        + escape(profile.get("audience", ""))
        + "</p><details><summary>Exact preference profile</summary><pre>"
        + escape(json.dumps(profile, indent=2))
        + "</pre></details>"
    )
    q = {r["event_id"]: r for r in qualifications}
    d = {r["event_id"]: r for r in decisions}
    body += "<h2>Every event and decision</h2>"
    for e in events:
        decision = d.get(e["event_id"], {})
        qualification = q[e["event_id"]]
        body += f'<details><summary>{escape(decision.get("tier",qualification["tag"]))}: {escape(e["title"])}</summary><p>Grouping: {escape(e["reason"])}</p><p>Qualification: {escape(qualification["tag"])}. {escape(qualification["reason"])}</p><p>Selection: {escape(decision.get("reason","Not retrieved after qualification."))}</p>'
        for id in e["source_ids"]:
            a = lookup[id]
            url = safe_link(a["url"])
            body += (
                f'<p>{escape(a["source"])}: '
                + (
                    f'<a href="{escape(url)}">{escape(a["title"])}</a>'
                    if url
                    else escape(a["title"])
                )
                + "</p>"
            )
        body += "</details>"
    body += "<h2>Summary provenance</h2>"
    for story in edition["stories"]:
        body += (
            f'<details><summary>{escape(story["title"])}</summary><p>{escape(story["summary"])}</p><p>{escape(story.get("why_matters",""))}</p><pre>'
            + escape(json.dumps(story["support"], indent=2))
            + "</pre></details>"
        )
    body += "<h2>Exact LLM task prompts</h2>"
    for task, prompt in prompts.items():
        if task == "select_events":
            continue
        body += f"<details><summary>{escape(task)}</summary><pre>{escape(prompt)}</pre></details>"
    return page("Private news workflow review", body)
