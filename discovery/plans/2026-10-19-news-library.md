# Rolling news collection and reader implementation plan

> Execute with the subagent-driven-development skill. Keep changes on `feat/news-source-filtering`; no merge or public deployment.

**Goal:** Understand retained news broadly, avoid repeated lead stories, and let Asif browse meaningful summaries by topic and edition date using the familiar template.

**Architecture:** A version-2 Python workflow analyses every valid unique article in a seven-day pool before applying preferences. PostgreSQL retains reusable article analyses and edition snapshots. A static reader presents a small featured selection above a topic library, with local browser read state and a dated edition archive. Existing version-1 runs remain resumable through their original workflow.

**Stack:** Existing Python, psycopg/PostgreSQL, direct LLM JSON client, static HTML/CSS and small browser JavaScript. No extra service or frontend framework.

## Constraints and decisions

- The four sources remain BBC World, TechCrunch, Ars Technica and CNBC Finance.
- Keep all observations; seven days limits current processing, not retention. Preserve publisher dates, update dates and collection dates separately. Repeated URLs reuse an analysis unless metadata changes or the analysis is older than 24 hours.
- Every valid unique pool article receives evidence retrieval and an analysis, including material outside Asif's preferences. Explicit unavailable/limited-evidence states replace invented summaries.
- Group specific events using evidence-grounded article summaries; retain all membership. Topic overlap does not establish event identity.
- Preferences version 2 include politics, conflict/geopolitics, economics/markets, business, AI/technology, science/research and geography/environment, including NZ/Pacific relevance. Human-interest or entertainment is not the default focus.
- Topic, geography, importance, freshness and evidence quality are distinct fields. Topics use a small controlled vocabulary; multiple tags are allowed.
- History identity includes prior review editions, but only published editions (or an explicitly supplied reviewed history) suppress previously featured stories. Preview generation never marks publication.
- Read state is local browser state with explicit mark read/unread and reset; it is not inferred from a link click or confused with publication.
- Preserve original banner, typography and cards. All browsable events get factual summaries; significance is optional and must be supported. Do not force a significance paragraph.
- Article text and raw audits stay private; reader-safe snapshots contain intended story fields and links only. Archive export must exclude private review data.
- Public pushes require redacted credentials and private infrastructure scans. Email actual milestones to the privately configured recipient.

## Tasks and interfaces

### 1. Retained rolling pool and analysis cache
Files: `src/news/store.py`, `src/news/migrations/002_library.sql`, `tests/test_news_library_database.py`.
Add migration 2 without changing any other schema/database. Methods: `rolling_articles(now, days=7)` returns latest observation per article by run time, including unknown-date observations; `cached_analysis(article_id, input_key, since)` returns a retained payload or None; `save_analysis(article_id, input_key, payload)` retains evidence and analysis; `recent_editions(profile_id, limit=7)` returns immutable snapshots including publication state. Add new table to size accounting.
Test cross-run availability, changed metadata/cache age, backwards migration, profile-scoped history and publication boundaries. Use unique test schemas.

### 2. Article understanding and summary review
Files: `src/news/understand.py`, `tests/test_news_understand.py`.
Define controlled topics and geographic scopes. `analyse_batch(articles, evidence, model)` uses short article references and returns one analysis per input, with factual summary, optional supported significance, tags, geography and source passage references. Validate complete partitions, known tags, bounded text and evidence references. A second LLM review checks factual entailment, actor attribution, uncertainty and significance; rejected output is repaired once then retained as a visible processing failure instead of quietly published.
Test injection-like source text, attributed motives, preliminary research, contradictions, unknown dates, empty extraction and unsupported significance. Run labeled real-model cases and inspect actual output.

### 3. Evidence-first workflow and broader editorial policy
Files: `src/news/library.py`, `src/news/profile.json`, `src/news/__main__.py`, `src/news/pipeline.py`, `tests/test_news_library.py`.
`run_library_workflow(store, model, output_root, run_id=None, now=None, rows=None, source_health=None, profile=None, history=None, ...)` owns frozen stages and per-article checkpoints. New CLI runs use workflow 2; version-1 resumes dispatch to the existing workflow. Retain all observations, query rolling pool, validate/dedupe without the 24-hour cliff, retrieve/analyse all pool documents, group events, qualify/rank all events in batches and synthesize multi-source events. Store all decisions, summaries, failures and counters. Separate relevance from featured placement; no fixed total library limit. Evidence-only and unavailable states remain explicit. Defaults: seven-day pool, six featured stories; no repeat featured stories without material update.
Verify interruption/resume avoids completed calls, each valid article has an analysis state, no silent candidate-budget loss, all relevant events remain browsable, old run replay still works, and seen/published/read states differ.

### 4. Familiar reader, topic browsing and dated archive
Files: `src/news/library_render.py`, `src/news/library_reader.js`, `src/news/reader.css`, `tests/test_news_library_render.py`.
`render_library(edition, archives)` consumes schema-3 edition data. Each story has existing title/summary/why_matters/sources plus topics, geography, importance, freshness, featured, event_id. Archives contain run_id, generated_at, publication_status and reader-safe edition snapshots. Keep original news visual baseline; add topic/geography filters, unread filter, mark read/unread, featured and topic collection, dated editions and seven-day overview. History links serve local exported snapshots, not server credentials. Preserve URLs and dates, accessible controls, escaping, safe links and RSS-only labels. Browser storage failures do not break reading.
Test content escaping, no audit leakage, useful fallback without JS, event read-state identity, navigation links and archive path boundaries. Visually inspect desktop/mobile and operate filters, read state and archive navigation in the browser.

### 5. Real run and coverage experiments
Replay the same saved 100 observations at the original run time to compare 24-hour baseline with rolling/evidence-first processing, then collect a fresh real edition. Record per-source observations, pool eligibility, analysis/cache/extraction outcomes, grouped events, relevance, featured/library counts, topics and rejection reasons. Inspect useful additions and false exclusions. Exercise a second-day fixture/history to prove repeats are not re-featured and genuine updates survive. Use actual archived previews only; label their publication state.

### 6. Review, evidence and delivery
Expand `dispatch_report.html` with a six-row task/result table, measured experiments, exact prompts/profile links, actual summary examples and accepted limitations. Update README and implementation ledger. Run full tests, rendered browser checks, real-model regression cases and completed-run replay. Scan exact publishable files and outgoing commits. Push the existing branch/update draft PR23, keep main/deployment unchanged, email the review milestone, and leave the actual HTML open. Final chat includes the requested six-row executed-results table and links to reader/report/PR.

## Verification ledger

- [x] 1. Rolling pool/cache/history migration and integration tests
- [x] 2. Grounded article analyses, repair/review and labeled model evaluation
- [x] 3. New workflow, broader preferences, structured ranking, resume and history
- [x] 4. Topic/read/history UI, desktop/mobile browser interaction
- [x] 5. Baseline, fresh run and multi-day experiments reviewed
- [x] 6. Dispatch report, full tests, privacy scans, draft PR and milestone email
