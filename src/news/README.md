# News-only workflow

One Python workflow collects four RSS feeds, retains observations in PostgreSQL, groups events, applies a versioned editorial profile, retrieves evidence, selects an edition and produces reader/review HTML. It never sends email, merges, or deploys. The old production entry point remains in place pending review.

## Setup and run

Use Python 3.10 or newer. Install only the news slice's dependencies:

```sh
python -m pip install -r requirements-news.txt
cp .env.example .env
# Set private PostgreSQL and model settings in ignored .env.
python -m src.news --migrate
python -m src.news
```

The PostgreSQL database must already exist and be named `news`. The workflow refuses any other database name and creates only its `news` schema and versioned tables. Runtime credentials need permission for that schema. Database administration and host access policy are outside the application; no command modifies other databases or PostgreSQL configuration.

Use a dedicated runtime account scoped to `news`, rather than shared administrative credentials. The verified runtime role has no superuser, database-creation, role-creation or replication capability. It can create schemas within this database for isolated tests, use the application schema, read/insert/update its tables and use its sequences. Initial provisioning and future ownership-sensitive migrations remain operator tasks.

The model must support OpenAI-style chat completions, JSON responses and `chat_template_kwargs.enable_thinking`. This is a direct client for the configured local service, not an agent framework or universal provider abstraction.

```sh
python -m src.news --resume RUN_UUID
python -m src.news --input .local/saved-collected.json
python -m src.news --profile src/news/profile.json --top-limit 5 --quick-limit 10
python -m src.news --stats
```

Each run freezes the profile, prompts, model identity, time window, input mode, edition limits and history. Resume reuses completed database stages and article/synthesis checkpoints. Changed workflow code version, prompts or model require a new run. Incomplete external calls may repeat; this is restartable execution, not exactly-once delivery. There is one PostgreSQL advisory lock per running edition, so multiple machines cannot execute that same run simultaneously. Different runs remain independent.

Output is private under `.local/news-editions/RUN_UUID/`:

- `index.html`: reader page with intended story fields and source links.
- `review.html`: source counts, every event's qualification/selection, exact profile/task prompts and summary support passages.
- `edition.json`: complete private editorial snapshot, including provenance.
- `run.json`: short local run summary. The database is authoritative for stage state and retained data.

The static page can later be deployed without database access. Do not deploy the private review page or full edition JSON. No deployment path is enabled by these commands. The prototype's shared source configuration has been reduced on this branch; it would change upon an approved release.

## Workflow and editorial policy

1. **Collect:** first 50 entries from BBC World, TechCrunch, Ars Technica and CNBC Finance. Retain all returned observations, including later exclusions and missing dates.
2. **Clean:** canonical URL identity, date/title/URL/sponsored-title checks and a publisher-balanced 100-candidate budget. Default freshness is 24 hours; missing dates are rejected. A feed's updated date is used only when published is absent, and that basis is retained.
3. **Group:** the LLM groups specific events, preserving supporting articles. Generic topic overlap is insufficient. Ordinary singletons are preserved deterministically. Supplied published/reviewed history distinguishes repeats and material updates.
4. **Qualify:** batches of at most 15 events get relevant / irrelevant / uncertain with a concrete reason. Only clear profile mismatches are removed; uncertainty survives to retrieval. Starting preferences are explicit in `profile.json`, not built into ingestion.
5. **Retrieve:** extract up to three supporting articles per shortlisted event. Failed/insufficient extraction is labeled feed-summary fallback. Only approved publisher hosts and redirects are fetched.
6. **Select:** rank the entire shortlist using bounded evidence. The total source-text budget is 60,000 characters, at most 6,000 per event, divided across its available sources. Truncation is explicit. Every event gets a selected or excluded decision; exclusion bases are off_brief, insufficient_evidence, already_covered or crowded_out. Defaults of five leads and ten quick reads are maxima, not quotas.
7. **Synthesize:** concise summaries and supported significance cite numbered source passages. Code attaches exact bounded excerpts. Valid passages establish traceability, not semantic entailment or independent factual verification.
8. **Render:** save the edition and private HTML snapshots; re-export the saved HTML on resume without model or article requests. A new renderer version creates a separate render checkpoint from the same saved edition.

Published history is scoped to the editorial profile and loaded from published editions only. `--history` can explicitly supply a reviewed edition. Merely generating an edition does not mark it published. This MVP has no command that changes publication status; release integration remains review-gated.

## Retained data

| Table | Purpose |
|---|---|
| `sources`, `articles` | Publisher catalog and canonical article identity |
| `observations` | Every collected entry for a run, original metadata/date basis and eligibility |
| `runs`, `stages` | Frozen configuration, execution status, attempts and completed output checkpoints |
| `events`, `event_articles` | Per-run event snapshots and supporting article membership |
| `decisions` | Qualification and selection, with profile ID/version and reasons |
| `evidence` | Retrieved text, extraction status, timestamp and content fingerprint |
| `model_calls` | Private model inputs/responses and prompt fingerprint |
| `editions` | Immutable generated edition snapshot and separate publication state |
| `storage_samples` | Database/table sizes and row counts over time |

Article and event storage is independent of your profile: rejection never deletes collected data. Full article text is retained only for retrieved items. Event snapshots are run-scoped; this MVP does not claim a permanent global event taxonomy across every domain.

Example queries, with database connection settings kept private:

```sql
SELECT source_name, eligibility, count(*)
FROM news.observations
WHERE run_id = 'RUN_UUID'
GROUP BY source_name, eligibility;

SELECT phase, tag, tier, basis, reason
FROM news.decisions
WHERE run_id = 'RUN_UUID'
ORDER BY phase, event_id;

SELECT name, item_key, status, attempts, finished_at - started_at AS duration
FROM news.stages WHERE run_id = 'RUN_UUID'
ORDER BY started_at;

SELECT sampled_at, database_bytes, tables_bytes, row_counts
FROM news.storage_samples ORDER BY sampled_at DESC LIMIT 10;
```

No retention deletion is automatic. A completed run records a size sample automatically; `--stats` records an additional on-demand sample. later retention policy should distinguish raw model audit, article evidence and edition history. PostgreSQL persistence alone is not a backup: use an operator-controlled `pg_dump` archive and test its restore in isolation. Keep backups private and off-host when operating the service.

## Verification

```sh
python -m unittest discover -s tests -v
python -m src.news.evaluate --env-file .env
```

Database tests require `NEWS_TEST_DATABASE_URL`, pointing to a database named `news`. They create unique `test_...` schemas and leave them for inspection; they never truncate production tables or alter other databases. CI supplies an ephemeral PostgreSQL service. The real-model evaluation checks nine labeled cases; it is a regression set, not an exhaustive accuracy benchmark. Raw model evaluation audit stays ignored.

The first PostgreSQL implementation has one SQL migration and a checked schema version. Future schema changes require new migrations and matching checkpoint compatibility changes. This is deliberate, rather than silently modifying tables on every run.

Private endpoints, credentials, retrieved text, model output, database exports and the private review page stay outside Git and the deployed site. Follow `AGENTS.md` before public pushes. A passing run is ready for editorial review, not approved for publication.
