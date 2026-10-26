# Canonical news workflow and release plan

Goal: Replace the stacked prototypes with one maintained news application, add NZ politics/economy, publish today's verified reader, and merge PR23 as explicitly authorized on 26 October.

Architecture: Installed Python package `news` owns collection, analysis, grouping, editorial selection, PostgreSQL checkpoints and rendering. Processing runs with private environment settings; GitHub only deploys a deliberately exported static reader. Publication history is recorded after the delivered files match their release hashes.

Keep the original visual design, retained database records, seven-day pool, source provenance and explicit read state. Retire old executable resumes with a clear error; keep their stored editions/evidence intact. No new agent platform, crawler, markets, quizzes or email product.

## Review gates

- [x] Pin origin/main `59b7920` and reviewed feature head `3dc32ff`.
- [x] Astra full architecture/code review; independent Spec review. Findings cover deployment mismatch, absent NZ feeds, legacy duplication, malformed synthesis, empty output, URL safety, unsafe test settings and archive truncation.
- [x] Re-review final changes with Astra, resolve important findings and document remaining limitations.

## 1. Canonical core

- [x] Move the active retained workflow into `src/news/workflow.py`; remove old workflow/build/grouping variants and dead prototype packages.
- [x] Give ingestion, source registry, article analysis, synthesis, editorial policy, rendering and private review explicit modules. Export `run_workflow`, `render_edition`, `reader_snapshot`.
- [x] Preserve meaningful active regressions; remove tests exclusive to retired code. Test DSNs must be explicitly supplied and loopback-only, with disposable isolated schemas.
- [x] Verify `python -m unittest discover -s tests -v` with the owned PostgreSQL instance, and build/install the package.

## 2. NZ coverage and correctness

- [x] Add RNZ Politics and Business feeds and allow RNZ extraction. Primary feed probes returned HTTP 200 and 17/16 entries on 26 October.
- [x] Stream bounded downloads, validate publisher URLs at admission/projection, repair malformed event outputs once, and reject unusable empty editions.
- [x] Bound archives by seven days rather than seven editions. Domestic NZ politics/economy and useful specific research do not require global consequences for relevance.
- [x] Inspect real NZ source text, analyses, event membership and selected summaries from today's run. Final reviewed edition: 81 stories, 17 tagged NZ; 15 explicit source-audit holds.
- [x] Add explicit per-run editorial holds from source audits; retain analyses/evidence unchanged, exclude held sources before grouping and remove affected preview baselines. Reject unknown IDs and changed resume policy.

## 3. Publication boundary

- [x] `news build` writes private review output; `news export --run RUN --output site` writes only reader HTML, banner, published archive and a release hash manifest.
- [x] Reject empty editions, unexpected files, unsafe links and private infrastructure/path strings at export. Raw evidence, responses, review pages, connection settings and full edition JSON never enter `site`.
- [x] Replace the scheduled Gemini workflow with deployment of `site` on main. CI installs the canonical package and runs on PRs/main.
- [x] Implement and test `news confirm-publication --run RUN --site-url URL --manifest site/release.json`: verify the deployed manifest and every file hash before recording PostgreSQL publication state. Failed delivery leaves history unchanged.
- [x] Test private-field omission, stale/unexpected-file rejection, failed delivery, hash mismatch and successful publication.

## 4. End-to-end release and handoff

- [x] Generate today’s edition using the configured private model/database. Save actual logs and counters privately; verify completed-run resume adds zero model calls and preserves output.
- [x] Review actual HTML/summary/exclusion quality; operate desktop/mobile filters and read state in the browser.
- [x] Replace stale README/roadmap with the one current operating path. Update `dispatch_report.html` with both review axes, architecture/debt, actual tests/schema/output/NZ coverage and publication evidence.

## Release procedure

1. Inspect the exact outgoing files and commits. Run fully redacted credential scans plus private-network, hostname, personal-data, private-path and banner-metadata checks; keep details ignored.
2. Push the corrected reader and report through PR23. Require final CI, including the staged-site verifier. Merge by squash as explicitly authorized for this checkpoint.
3. Verify Pages delivery and run `news confirm-publication`. The PostgreSQL publication receipt and GitHub merge/deployment records own the actual release status; a checked plan is not delivery proof.
4. Open today's public reader in the user's browser, inspect the rendered date/counts/NZ content and retain the screenshot privately. Email the verified milestone using the existing private recipient configuration.

Generation remains an explicit private command. This work does not install a recurring scheduler.
