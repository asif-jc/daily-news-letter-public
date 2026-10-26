# Canonical news workflow and release plan

Goal: Replace the stacked prototypes with one maintained news application, add NZ politics/economy, publish today's verified reader, and merge PR23 as explicitly authorized on 26 October.

Architecture: Installed Python package `news` owns collection, analysis, grouping, editorial selection, PostgreSQL checkpoints and rendering. Processing runs with private environment settings; GitHub only deploys a deliberately exported static reader. Publication history is recorded after the delivered files match their release hashes.

Keep the original visual design, retained database records, seven-day pool, source provenance and explicit read state. Retire old executable resumes with a clear error; keep their stored editions/evidence intact. No new agent platform, crawler, markets, quizzes or email product.

## Review gates

- [x] Pin origin/main59b7920 and reviewed feature head3dc32ff.
- [x] Astra full architecture/code review; independent Spec review. Findings cover deployment mismatch, absent NZ feeds, legacy duplication, malformed synthesis, empty output, URL safety, unsafe test settings and archive truncation.
- [x] Re-review final changes with Astra, resolve important findings and document remaining limitations.

## 1. Canonical core

- [x] Move the active retained workflow into `src/news/workflow.py`; remove old workflow/build/grouping variants and dead prototype packages.
- [x] Give ingestion, source registry, article analysis, synthesis, editorial policy, rendering and private review explicit modules. Export `run_workflow`, `render_edition`, `reader_snapshot`.
- [x] Preserve meaningful active regressions; remove tests exclusive to retired code. Test DSNs must be explicitly supplied and loopback-only, with disposable isolated schemas.
- [x] Verify `python -m unittest discover -s tests -v` with the owned PostgreSQL instance, and build/install the package.

## 2. NZ coverage and correctness

- [x] Add RNZ Politics and Business feeds and allow RNZ extraction. Primary feed probes returned HTTP200 and17/16entries on26October.
- [x] Stream bounded downloads, validate publisher URLs at admission/projection, repair malformed event outputs once, and reject unusable empty editions.
- [x] Bound archives by seven days rather than seven editions. Domestic NZ politics/economy and useful specific research do not require global consequences for relevance.
- [ ] Inspect real NZ source text, analyses, event membership and selected summaries from today's run.
- [x] Add explicit per-run editorial holds from source audits; retain analyses/evidence unchanged, exclude held sources before grouping and remove affected preview baselines. Reject unknown IDs and changed resume policy.

## 3. Publication boundary

- [x] `news build` writes private review output; `news export --run RUN --output site` writes only reader HTML, banner, published archive and a release hash manifest.
- [x] Reject empty editions, unexpected files, unsafe links and private infrastructure/path strings at export. Raw evidence, responses, review pages, connection settings and full edition JSON never enter `site`.
- [x] Replace the scheduled Gemini workflow with deployment of `site` on main. CI installs the canonical package and runs on PRs/main.
- [ ] `news confirm-publication --run RUN --site-url URL --manifest site/release.json` verifies the deployed manifest and every file hash before recording PostgreSQL publication state. Failed delivery must not affect history.
- [x] Test private-field omission, stale/unexpected-file rejection, failed delivery, hash mismatch and successful publication.

## 4. End-to-end release and handoff

- [ ] Generate today’s edition using the configured private model/database. Save actual logs and counters privately; verify completed-run resume adds zero model calls and preserves output.
- [ ] Review actual HTML/summary/exclusion quality; operate desktop/mobile filters and read state in the browser.
- [ ] Replace stale README/roadmap with the one current operating path. Update `dispatch_report.html` with both review axes, architecture/debt, actual tests/schema/output/NZ coverage and publication evidence.
- [ ] Inspect exact outgoing files/commits; Gitleaks full-redacted file/history scans plus private-network, hostname, personal-data and private-path checks. Keep detailed results private.
- [ ] Push/update existing PR23, pass CI, merge as authorized, verify Pages delivery, confirm publication, and open today's public news page in the user's browser.
- [ ] Email meaningful milestones using the existing private recipient configuration. Final response links to actual reader, report and merged PR, with material limitations.
