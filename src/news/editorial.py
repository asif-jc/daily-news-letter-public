"""
=== editorial.py ===

Purpose: Qualify and rank events against an explicit editorial profile.
Extended Description:
    Ingestion and event identity are independent; they belong in pipeline.py and events.py.
Usage:
    Called by workflow.run_workflow.
Work Log:
    19/10/2026 -> PostgreSQL-backed news-only MVP.
"""

# ========================================================================
# IMPORTS & CONFIGURATION
# ========================================================================
from .events import _text

QUALIFICATION_BATCH_SIZE = 15
SELECTION_TEXT_BUDGET_CHARS = 60000
MAX_EVENT_EVIDENCE_CHARS = 6000

REJECTION_BASES = {
    "off_brief",
    "insufficient_evidence",
    "already_covered",
    "crowded_out",
}


# ========================================================================
# EDITORIAL VALIDATION
# ========================================================================


def _partition(rows, expected, label):
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError(f"Expected {label} objects")
    ids = [r.get("event_id") for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError(f"{label} must account for every supplied event exactly once")


def qualify_events(events, model, profile):
    result = []
    repeats = [e for e in events if e["novelty"] == "repeat"]
    result.extend(
        {
            "event_id": e["event_id"],
            "tag": "irrelevant",
            "reason": "Already covered without a material update.",
            "decision_basis": "already_covered",
        }
        for e in repeats
    )
    eligible = [e for e in events if e["novelty"] != "repeat"]
    for offset in range(0, len(eligible), QUALIFICATION_BATCH_SIZE):
        batch = eligible[offset : offset + QUALIFICATION_BATCH_SIZE]
        # Short references avoid asking the model to transcribe hexadecimal identity hashes.
        references = {f"q{n+1}": event["event_id"] for n, event in enumerate(batch)}
        inputs = [{**event, "event_id": ref} for ref, event in zip(references, batch)]
        rows = model.complete(
            "qualify_events", {"profile": profile, "events": inputs}
        ).get("qualifications")
        _partition(rows, references, "Qualification")
        for row in rows:
            if row.get("tag") not in ("relevant", "irrelevant", "uncertain"):
                raise ValueError("Unknown qualification tag")
            result.append(
                {
                    "event_id": references[row["event_id"]],
                    "tag": row["tag"],
                    "reason": _text(row.get("reason"), "qualification reason"),
                    "decision_basis": "profile",
                }
            )
    return result


def select_with_evidence(events, evidence, model, profile, top_limit, quick_limit):
    if not events:
        raise ValueError("No qualified events to select")
    inputs = []
    per_event_budget = min(
        MAX_EVENT_EVIDENCE_CHARS, SELECTION_TEXT_BUDGET_CHARS // len(events)
    )
    references = {f"s{n+1}": event["event_id"] for n, event in enumerate(events)}
    for ref, event in zip(references, events):
        ids = [event.get("representative_id")] + event["source_ids"]
        ids = list(dict.fromkeys(id for id in ids if id in evidence))
        per_source_budget = per_event_budget // max(1, len(ids))
        inputs.append(
            {
                **{
                    k: event.get(k)
                    for k in ("event_id", "title", "novelty", "change", "sources")
                },
                "event_id": ref,
                "evidence": [
                    {
                        "article_id": id,
                        "basis": evidence[id]["basis"],
                        "status": evidence[id].get("status", "unknown"),
                        "text": evidence[id]["text"][:per_source_budget],
                        "truncated": len(evidence[id]["text"]) > per_source_budget,
                    }
                    for id in ids
                ],
            }
        )
    rows = model.complete(
        "select_with_evidence",
        {
            "profile": profile,
            "events": inputs,
            "top_limit": top_limit,
            "quick_limit": quick_limit,
        },
    ).get("decisions")
    _partition(rows, references, "Selection")
    rows = [{**row, "event_id": references[row["event_id"]]} for row in rows]
    counts = {"top": 0, "quick": 0}
    result = []
    for row in rows:
        tier = row.get("tier")
        basis = row.get("decision_basis")
        score = row.get("score")
        if tier not in ("top", "quick", "exclude"):
            raise ValueError("Unknown selection tier")
        if tier == "exclude":
            if basis not in REJECTION_BASES or score is not None:
                raise ValueError(
                    "Excluded events need a rejection category and null score"
                )
        else:
            if (
                basis != "selected"
                or isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not 0 <= score <= 10
            ):
                raise ValueError(
                    "Selected events need an importance score and selected basis"
                )
            event = next(e for e in events if e["event_id"] == row["event_id"])
            if not any(
                evidence.get(id, {}).get("text", "").strip()
                for id in event["source_ids"]
            ):
                raise ValueError("Cannot select an event without usable evidence")
            counts[tier] += 1
        result.append(
            {
                "event_id": row["event_id"],
                "tier": tier,
                "score": score,
                "topic": _text(row.get("topic"), "topic"),
                "reason": _text(row.get("reason"), "selection reason"),
                "decision_basis": basis,
            }
        )
    if counts["top"] > top_limit or counts["quick"] > quick_limit:
        raise ValueError("Selection exceeded edition budget")
    return result
