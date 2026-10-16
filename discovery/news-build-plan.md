# News source and filtering slice

Approved scope: four sources (BBC, Ars, TechCrunch, CNBC), direct configured local LLM, inspectable event filtering and concise synthesis. Source growth and UI redesign follow evidence from this slice. Merge and deployment remain review-gated.

Architecture: `src/news` replaces the prototype's news path through a manual local command. It reads the shared four-source configuration, collects and normalizes articles, groups events, selects across categories, extracts selected evidence, and validates structured summaries. It writes review artifacts only under ignored local storage. The deployed entry point is left on the prototype until the replacement is reviewed; there is no second scheduled service.

Use existing requests, feedparser, BeautifulSoup, and dotenv. No orchestration framework or new dependency. Edition history is an optional previously reviewed edition supplied explicitly, not an automatic claim that a generated edition was published.

## Ordered work

- [x] Thin `src/mvp_news_aggregator/sources.py` to four approved sources. Confirm names in a regression test.
- [x] Add `src/news/llm.py`: `JsonModel.from_env()` and `complete(task, data) -> dict`; reject incomplete, malformed or absent output, sanitize transport errors, save private prompt/response evidence. Settings have no private committed defaults.
- [x] Add `src/news/events.py`: URL normalization, `filter_candidates(rows, now)`, validated partition `group_events(articles, model, history)`, bounded cross-category `select_events(events, model, top_limit, quick_limit)`. Keep supporting source membership. Reject unknown/duplicated IDs; materialize unreported new singletons deterministically so none are dropped. Exclude repeats but allow explained material updates.
- [x] Add `src/news/pipeline.py` and CLI: fetch four feeds with explicit source-health records; extract allowed-source article text; synthesize selected events into a dated edition with evidence basis. Write atomic per-stage artifacts under a new run directory. Model failure stops the run rather than publishing feed-order fallback.
- [x] Add focused unittest checks for freshness, URL identity, semantic-group membership, repeat/update behavior, selection budgets, malformed model output, extraction access boundaries and full pipeline replay with controlled external responses.
- [x] Run a real manual edition with the supplied endpoint. Inspect groups, exclusions, selected evidence and summary output. Capture actual counts and timings without publishing infrastructure details.
- [x] Update the dispatch report and runnable usage. Run the suite, diff checks, and private publication scans. Do not merge or deploy.

## Proposed defaults and limits

24-hour news window, reject unknown/future dates, keep short descriptions for model assessment. At most 100 candidates, balanced across contributing publishers, with every deterministic exclusion recorded. Maximum five lead stories and ten quick reads, adjustable by CLI and not mandatory fill quotas. This bounds the first model workload and reading output; these defaults are exploratory rather than an inferred user preference.

Event grouping compares candidate title/description and optional previously reviewed titles/summaries. It cannot prove absence of updates hidden in unextracted article bodies. Extraction and summaries must disclose feed-only fallback. Source/topic balance is a selection criterion to inspect, not a hard quota that admits weak stories. Selected events carry model scores/reasons; all remaining events receive an explicit procedural budget exclusion without a fabricated per-event score.

## Executed checkpoint

Implemented and exercised locally. The real run collected 107 entries, retained 64 candidates, formed 59 events and selected 5 lead stories plus 6 quick reads. All 21 tests pass; replay using captured external responses reproduces the edition exactly. See [validation evidence](evidence/news-slice-validation.json) and [dispatch report](../dispatch_report.html). No merge or deployment. Passage support is traceability, not automatic factual verification. Editorial mix and news-only page integration remain review checkpoints.
