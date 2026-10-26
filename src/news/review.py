"""Private audit rendering; never included in published reader exports."""

import json

from .render import escape, safe_link


def render_private_review(edition, config, prepared, analyses, decisions, events=None):
    body = f'<h1>News collection review</h1><p><a href="index.html">Read the edition</a></p><h2>Measured funnel</h2><pre>{escape(json.dumps(edition["counts"],indent=2))}</pre><h2>Preferences</h2><pre>{escape(json.dumps(config["profile"],indent=2))}</pre><h2>Every article analysis</h2>'
    for a in prepared["articles"]:
        v = analyses[a["id"]]
        url = safe_link(a.get("url", ""))
        link = (
            f'<p><a href="{escape(url)}" target="_blank" rel="noopener noreferrer">Open source</a></p>'
            if url
            else ""
        )
        body += f'<details><summary>{escape(a["source"])}: {escape(a["title"])} ({escape(v["state"])})</summary>{link}<pre>{escape(json.dumps(v,indent=2))}</pre></details>'
    body += (
        "<h2>Event groups and history matches</h2><pre>"
        + escape(json.dumps(events or [], indent=2))
        + "</pre>"
    )
    body += (
        "<h2>Event summary failures</h2><pre>"
        + escape(json.dumps(edition.get("summary_failures", []), indent=2))
        + "</pre>"
    )
    body += (
        "<h2>Event decisions</h2><pre>"
        + escape(json.dumps(decisions, indent=2))
        + "</pre><h2>Exact prompts</h2>"
    )
    for name, prompt in config["prompts"].items():
        body += f"<details><summary>{escape(name)}</summary><pre>{escape(prompt)}</pre></details>"
    return (
        '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Private news review</title><style>body{font:16px/1.6 system-ui;max-width:1000px;margin:30px auto;padding:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{margin:12px 0;padding:12px;background:#f5f5f5}</style></head><body>'
        + body
        + "</body></html>"
    )
