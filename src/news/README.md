# Retained news collection

The default CLI runs an evidence-first Python workflow backed by the isolated PostgreSQL `news` database. It retains every feed observation, understands new articles before personal filtering, groups related reports into events, and renders a concise featured selection above a broader topic collection. It never publishes, sends newsletters, merges or deploys.

## Run and resume

```sh
python -m pip install -r requirements-news.txt
cp .env.example .env
# Fill the ignored environment file with runtime database/model settings.
python -m src.news --migrate
python -m src.news --pool-days 7 --featured-limit 6
python -m src.news --resume RUN_UUID
python -m src.news --stats
```

PostgreSQL must already contain a database named `news`. The application checks both connection configuration and actual backend identity before schema operations. Migrations touch its application schema only. Schema version 2 adds retained article analyses without replacing version-1 records. On an existing database whose tables belong to an administrator, that administrator must apply migration 2 and grant runtime SELECT/INSERT/UPDATE on the new table plus identity-sequence access. Do not broaden the runtime role to superuser or modify other databases/access rules.

The model endpoint must support OpenAI-style chat completions, JSON responses and `chat_template_kwargs.enable_thinking`. Private addresses, model names and credentials belong in ignored env files. No agent framework or orchestration service is required.

New runs use workflow 2. Resume automatically selects the original workflow for version-1 runs, preserving their frozen prompts and inputs. New workflow/profile/prompt choices require a new run; renderer changes have separate checkpoints. `--top-limit` and `--quick-limit` belong to legacy resumes; new runs use `--featured-limit`, which does not limit the browsable collection.

`--input FILE` replays normalized feed observations. `--history FILE` explicitly supplies reviewed edition history for repeat/update experiments; it does not mark database editions published. Runtime connection and model errors are reported without private transport details.

## Workflow

1. **Collect and retain.** BBC World, Ars Technica, TechCrunch and CNBC Finance, at most 50 entries per feed. Record published, updated and fetched timestamps separately. RSS remains discovery, not proof of comprehensive publisher coverage.
2. **Build a rolling pool.** Use latest retained observations from runs no later than the edition time. Seven days is the default current-reading window, not a retention deletion policy. Every newly collected valid unique article is understood, including older background material. Unknown dates remain explicitly unknown; invalid URLs, empty titles and future dates are quarantined with reasons. Duplicate URLs are processed once.
3. **Retrieve and understand.** Fetch publisher-approved article URLs with bounded extraction. When extraction fails, label RSS-only evidence; never imply full-text access. Analyse articles in small batches independently of personal preferences. Store factual summaries, optional supported significance, controlled topics, geography, passage references and review outcomes. Reuse exact metadata/model/prompt matches for 24 hours; publisher body changes without feed metadata changes may not be discovered until refresh.
4. **Review and repair.** A separate model call checks attribution, actors, numbers, scientific uncertainty and unsupported significance against supplied evidence. One revision attempt is allowed. A malformed article field is repaired independently of valid batch neighbors; persistent malformed fields become needs-review. Invalid batch membership still stops the stage rather than guessing article identity. If only optional significance remains unsupported, remove it and review the factual summary again before admitting that summary. An article that still fails is retained as needs-review, without a reader-ready summary. No-evidence articles remain unavailable. This is model-assisted checking, not independent fact verification.
5. **Group specific events.** Propose comparison pairs globally from grounded titles/summaries: exact historical source identities plus each current article's two closest lexical candidates sharing at least two terms. TF-IDF gives distinctive words more weight, so generic news terms do not dominate the comparison budget. These are candidate hints only: the LLM reviews batches of twelve pairs and must return a verdict for each. Only approved same-event edges form groups; unmatched articles remain singletons. Source IDs/URLs never automatically establish repeat/update. Shared companies, topics or countries do not establish one event. Response/aftermath can share one explicitly identified incident; later approval/completion of the same deal can be an update, while separate decisions remain distinct. Published baselines take priority over preview identities, and prior featured aliases survive reconciliation. History respects the edition's time boundary. Lexical candidate recall remains limited: paraphrases without shared terms can be missed. Pair generation is quadratic in the bounded current/history pool; no vector search service is introduced. Runs freeze grouping version and prompts; old version-1 grouping checkpoints remain resumable.
6. **Curate and rank.** Preferences include politics, conflict/geopolitics, economies/markets, business, AI/technology, science/research, environment/geography and NZ/Pacific relevance. Every event gets a reasoned relevance/importance decision. Relevant lower-ranked events remain browsable; six featured slots are a presentation choice. Topic diversity breaks close ranking choices. Within the rolling publication-history window, previously featured events need a material update to feature again. Past featured membership is retained separately from the latest factual snapshot, so a subsequent unfeatured appearance cannot erase it. Both use the configured pool horizon (seven days by default), rather than an edition-count limit; this bounds processing and keeps suppression backed by the history available to grouping.
7. **Summarise events.** A single-source event uses its reviewed article summary. Multi-source events synthesize all available supporting documents with actual source references and another review/repair pass. Failed event reviews remain private and count as processing failures. A significance paragraph is optional, never filled with speculation.
8. **Render and inspect.** Preserve the original park banner, typography and single-column story cards. Add topic/geography filters, explicit local read/unread controls, dated editions and a seven-day overview. No article/link click silently marks a report read. Store read state in this browser only; it does not sync between devices or change publication state. Material-update revisions can be unread while the older report remains read. Revision keys include prior lineage and retained text, so unchanged publisher timestamps do not hide a later approved update. Rejected history matches cannot inherit reserved historical IDs.

Importance, freshness, evidence quality, relevance and reader state are separate concepts. A major story is not necessarily urgent. New/updated/catch-up/previously-featured labels explain timing; topic tags describe subject matter independently of the publisher feed category.

## Private and reader-safe outputs

Each run exports under ignored `.local/news-editions/RUN_UUID/`:

- `index.html`: intended reader stories, links and browser controls.
- `assets/dunder_park.jpg`: original banner.
- `archive/RUN_UUID.html`: reader-safe snapshots of available previous editions; real previews are labeled previews, not published editions.
- `review.html`: private article analyses, processing states, event decisions, preferences and exact prompts.
- `edition.json`: full private retained edition, including supporting excerpts/review metadata.
- `run.json`: private counts and status.

**Never deploy the whole run directory.** Only an intentionally reviewed reader HTML/assets/archive subset belongs in a public release. Raw retrieved text, model audit, support passages, database connection information and the private review page stay private.

There is no publication command in this slice. Generating or viewing a preview never marks it published. The original production entry point remains unchanged pending release review. Archive navigation covers actual available published editions by default; the system does not invent newsletters for missing days. `--include-review-previews` explicitly includes unapproved local drafts for comparisons, labeled as review previews. They are not publication history.

## Retained records

| Table | Purpose |
|---|---|
| `sources`, `articles`, `observations` | Source catalog, stable article identity and every run observation |
| `runs`, `stages` | Frozen settings, transactional checkpoints, failures and attempts |
| `article_analyses` | Append-only reusable evidence/summary/review cache, independent of reader profile |
| `events`, `event_articles` | Per-run event identity and article membership |
| `decisions` | Profile-versioned relevance, ranking and reasons |
| `evidence`, `model_calls` | Private source snapshots and actual model requests/responses |
| `editions` | Immutable review snapshots with separate publication state |
| `storage_samples` | Application-table/database size and row counts |

Run locking prevents two workers from executing the same edition simultaneously. Event comparison batches have validated checkpoints. On resume, exact same-run/task/request audit responses are revalidated before reuse; malformed or unsupported responses require a fresh call. A raw model audit is never automatically an accepted result. Completed checkpoints are immutable; an interrupted network request may repeat. Cache identity includes article metadata, model, prompts and extractor version. This is restartable execution, not exactly-once delivery. No retention deletion runs automatically. Size samples include the analysis cache; whole database size may also include isolated retained test schemas.

## Verify and inspect

```sh
python -m unittest discover -s tests -v
python -m src.news.evaluate --env-file .env
# Add --legacy to evaluate original version-1 grouping.
```

Integration tests require `NEWS_TEST_DATABASE_URL` pointing to a database named `news`. Each creates its own `test_...` schema and leaves it for inspection. CI uses an ephemeral PostgreSQL service; no test truncates application tables or touches other databases.

Useful private queries:

```sql
SELECT name,status,count(*) FROM news.stages
WHERE run_id='RUN_UUID' GROUP BY name,status;
SELECT phase,tier,basis,reason FROM news.decisions WHERE run_id='RUN_UUID';
SELECT id,article_id,created_at,payload->'analysis'->>'state' AS state
FROM news.article_analyses ORDER BY id DESC LIMIT 20;
SELECT status,published_at,payload->'counts' FROM news.editions WHERE run_id='RUN_UUID';
SELECT sampled_at,database_bytes,tables_bytes FROM news.storage_samples ORDER BY sampled_at DESC LIMIT 10;
```

Passage references prove traceability, not entailment. Extraction is heuristic and bounded; grouping and ranking are model judgments. Model self-review does not independently establish a report's truth. More categories cannot supply missing NZ reporting from these four feeds. Read state is local and may be cleared by the browser. Backups and reviewed production publication remain operational responsibilities; restore-test database archives before relying on them.
