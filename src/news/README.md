# News-only review workflow

This is the replacement news path under development. It does not publish, send email, or change the existing generated pages. The current GitHub Actions entry point still uses the prototype until this slice is reviewed. Its shared source configuration is intentionally reduced on this branch and would change upon an approved release.

## Run locally

From the repository root, use an environment with `requirements.txt` installed:

```sh
cp .env.example .env
# Fill in your private model settings in .env.
python -m src.news
```

The model service must support OpenAI-style chat completions, JSON responses, and the `chat_template_kwargs.enable_thinking` setting used by the verified local service. This first client targets that service, not every possible provider.

Optional controls:

```sh
python -m src.news --env-file .env --top-limit 5 --quick-limit 10
python -m src.news --input .local/news-runs/RUN/collected.json
python -m src.news --history .local/news-runs/REVIEWED_RUN/edition.json
```

Supply history only for an edition whose stories you want treated as already covered. Generation does not mark an edition as published. In this manual slice there is no automatic historical state update or scheduler.

## Inspect a run

Each run gets a new ignored `.local/news-runs/` directory:

| File | What to inspect |
|---|---|
| `run.json` | Current stage, status, source failures, completion/failure evidence |
| `collected.json` | Raw normalized RSS candidates, including original date basis |
| `candidates.json` | Eligible candidates, balanced if the 100-candidate budget is reached |
| `exclusions.json` | Unknown/future/old dates, invalid URLs, sponsorship, exact duplicate URLs, budget exclusions |
| `events.json` | Event groups, representative article, supporting source IDs, repeat/update judgment |
| `decisions.json` | Model scores/topics/reasons for selected events; explicit budget or history exclusions for all others |
| `evidence.json` | Selected source text, retrieval status and article-text versus feed-summary basis |
| `model/` | Private prompts and raw model responses |
| `edition.json` | Validated stories and provenance; ready for human review, not automatically approved |

Four sources are active: BBC World, TechCrunch, Ars Technica and CNBC Finance. No new sources or crawler are included. Thin RSS metadata is retained rather than rejected solely for a short description. Unknown dates are no longer relabeled as fresh.

Exact URLs are deduplicated first. The model reports semantic duplicate/history matches, and unmatched articles become singleton events deterministically. This saves model output while preserving every candidate. Related topics are not automatically duplicates; material updates may survive a history match. The model can still miss or misgroup events: saved groups and source references are for inspection, not proof of perfect semantic recall.

Selection chooses a global shortlist across the event pool. Unselected events have a procedural budget-exclusion reason, not an invented individual model score or explanation. This keeps model output bounded; detailed rejection rationales are deferred. Defaults are at most five lead stories and ten quick reads, with no mandatory fill quota; these are provisional review limits. Diversity is an editorial criterion, not a hard quota. Full text is retrieved only for selected events, from at most three supporting articles per event. Summary citations must reference supplied nonempty evidence. Each nonempty section must cite numbered source passages. The code constructs their bounded verbatim excerpts from the retrieved text, so the model cannot fabricate the quoted text. Every cited source needs a supporting passage. These private excerpts aid review; their existence does not prove semantic entailment or factual accuracy. They are not intended public edition fields. Retrieval failure is recorded as feed-summary fallback rather than silently implying full-text access.

A failed model call or invalid response stops the run. It does not fall back to feed-order selection or overwrite the current public edition. Partial source collection is visible in source health and needs human judgment. Title/description-only history comparison can miss updates visible only in an article body. These are limits of the first slice to measure before expanding it.

Run verification:

```sh
python -m unittest discover -s tests -v
```

Private endpoints, credentials, raw retrieved text and model output must stay ignored. Follow the repository's `AGENTS.md` privacy gate before any public branch push. Neither merge nor deployment is authorized by successful local generation.
