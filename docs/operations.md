# Run and maintain the news workflow

[Back to the project](../README.md)

## Run it

Python 3.11+ and a reachable PostgreSQL database named `news` are required. The language model must expose an OpenAI-compatible chat-completions endpoint. Connection settings belong in an ignored environment file.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
# Fill in the private settings in .env.
news migrate
news build
```

The command prints the run UUID and paths to `index.html` and `review.html` under ignored `.local/news-editions/`. The private review contains source analyses, evidence references, grouping judgments, selection reasons, failures and exact prompts. Keep that entire directory private.

```sh
news build --resume RUN_UUID
news stats
news --env-file .local/news.env build
```

Source audits can withhold a confirmed bad article without overwriting its evidence or model analysis. For a new run, use `news build --article-holds .local/editorial-holds.json`, where the private JSON is a list of `{"article_id":"ARTICLE_ID","reason":"Concrete source-audit finding"}`. Unknown or duplicate IDs fail. Holds are frozen for that run and exclude the source before grouping, including affected preview history. A hold intersecting the run's published history stops for separate release review; it does not rewrite published archives. Hold reasons stay in the private review, and the measured funnel reports their count.

Resume uses frozen inputs, prompts and settings and reuses validated checkpoints. A failed group of up to five article checkpoints can repeat work inside that unfinished group; this is restartable processing, not exactly-once inference. Changed processing settings require a new run. Database migrations preserve retained records. Executable resumes from retired prototype workflow versions are intentionally unsupported; their saved editions and evidence remain in PostgreSQL.

## Processing and storage

1. Collect and retain feed observations, preserving publication, update and collection times.
2. Retrieve bounded evidence from approved public publishers and analyse every valid unique article before personal filtering. Exact cached analyses can be reused for 24 hours.
3. Generate and review one article per model request so each response has an unambiguous source identity. Review factual summaries and optional significance. Allow one factual revision and one format-repair retry per review request; a persistently malformed review stops the run, and unsupported drafts stay withheld in the private review.
4. Propose event comparisons using shared distinctive words and historical source identities. The model decides identity. Conflicting verdicts hold the affected component before synthesis.
5. Apply the versioned [editorial profile](../src/news/profile.json). Relevance, importance, topic, geography and freshness are separate; useful domestic reporting does not need global consequences.
6. Review multi-source summaries, choose featured placement and retain other relevant stories. Keep a seven-day current pool without deleting older observations.
7. Save the edition and render the private review and reader. Empty/unusable output fails rather than replacing a good edition.

PostgreSQL retains source observations, article identities, versioned analyses, evidence, model audit, stage checkpoints, event membership, editorial decisions, edition snapshots, publication receipts and size samples. The application refuses writes outside the `news` database. Tests use disposable schemas on an explicitly selected loopback test database.

Published history, preview history and read state are different. Previously featured events require a material update to lead again. Published editions support dated navigation and a seven-day overview without a seven-edition cap. Read state is explicit and browser-local; opening a source does not mark it read.

## Publish a reviewed edition

Private processing runs on a machine that can reach the configured model and database. GitHub only deploys the exported static reader. No scheduler is installed by this repository; generation can be invoked by an on-prem scheduler using the same `news build` command.

```sh
news export --run RUN_UUID --output site
```

Export writes only reader HTML, the banner, published archive pages and `release.json`. It rejects empty output, unsafe source URLs, private path/network strings and unexpected files. It does not record publication. Never copy a private run directory into the public site.

Run `news verify-release` to check the staged artifact boundary without loading private settings. Review the staged `site/` files, run the tests and the public-repository privacy checks in [AGENTS.md](../AGENTS.md), then commit them through a PR. Merging into `main` triggers the deployment-only Pages workflow. After the delivered files are available:

```sh
news confirm-publication --run RUN_UUID \
  --manifest site/release.json \
  --site-url https://asif-jc.github.io/daily-news-letter-public/
```

Confirmation rebuilds the intended release from the retained edition, checks the deployed manifest and every file hash, then records publication transactionally. Failed delivery leaves publication history unchanged. If deployment succeeds but database confirmation fails, rerun this command; do not regenerate or falsely mark a different run as delivered.

## Develop and verify

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

Integration tests are skipped unless `NEWS_TEST_DATABASE_URL` is explicitly set. They require a `postgresql://...@localhost:PORT/news` URL, accept loopback addresses only, and remove their own isolated test schemas. They never load private environment files automatically. CI supplies an ephemeral PostgreSQL 17 service and runs the full suite.

The package has one execution path: `news` and `python -m news` call the same CLI. Its modules separate ingestion, article analysis, event grouping, editorial policy, synthesis, persistence, rendering and publication. `pyproject.toml` is the dependency and packaging manifest.

## Limits worth reviewing

Model self-review is not independent fact checking. Source references establish traceability, not entailment. Lexical comparison proposals can miss paraphrases; model judgments can mistake added context for a new development. Six feeds from five publishers do not provide exhaustive news coverage. Extraction is bounded and can fall back to clearly labeled feed evidence. Read state does not sync between devices. Storage is measured but no automatic retention deletion is installed.

[Dispatch report](../dispatch_report.html) records the latest executed review, tests, run counts and delivery evidence. Historical prototype code and generated artifacts were retired; PostgreSQL records were preserved.
