# Dense archive reader implementation plan

**Goal:** Adapt Dense Discovery's warm archive reader to our retained news stories, then deliver an unmerged PR and a live isolated preview for Asif.

**Architecture:** Keep the Python workflow, PostgreSQL records and reviewed edition fields. Render a static, progressively enhanced HTML reader with a left story index, a single selected story, filters and dated archives. Plain JavaScript handles selection and history; CSS handles the desktop split and mobile browse drawer. No frontend framework or backend service is needed.

## Requirements and evidence

| Requirement | Implementation | Verification |
|---|---|---|
| Use REA on the reference | Retain desktop/mobile browser scenarios privately; inspect archive shell and issue | Recorded navigation, screenshots and explicit limitations |
| Left browsing uses story titles | Story index, selected state, topic/place/search/read filters | Desktop, keyboard and filter browser scenarios |
| Warm illustrated header and quote | Original editorial illustrations; pull text from an existing reviewed summary, labelled as briefing text | Visual review and escaped-content tests; no fabricated attribution |
| Original logo | Small original typographic/paper mark, Daily News Reader identity | Desktop and mobile inspection |
| Readable story text and metadata | Paragraphs, title, evidence-basis labels, dates and all source links | Safe-render and source-preservation tests |
| Top-right source link | Labelled external link to the primary reporting, alongside all sources in the story | URL validation and browser checks |
| Mobile | Compact header, Browse stories drawer, focus return and usable article width | 390px and 320px browser checks; overflow and keyboard checks |
| Low noise | No related-stories footer, subscription backend or recommendation system | Inspect the resulting reader |
| Current workflow stays reliable | Preserve read identity, seven-day pool, archive paths and strict export boundary | Existing suites plus redesigned-reader contracts |
| Review then deploy for review | Astra requirements audit, address feedback, second pass; PR code review | Recorded review results against actual branch/PR |
| Do not merge main | Isolated branch and preview under a unique Pages prefix | PR remains open; root production manifest hashes unchanged |
| Public repository privacy | Explicit allowlist for assets and edition fields; scan every outgoing push | Fully redacted Gitleaks plus path/network/PII checks |

## Task 1: Build the static reader

Files: `src/news/render.py`, `src/news/reader.css`, `src/news/reader.js`, `src/news/assets/`, `tests/test_render.py`.

- [x] Replace the old visual shell, retaining `reader_snapshot` as the field boundary.
- [x] Render stable anchor identities, the sidebar and full escaped story content once. With JavaScript disabled, anchors still navigate readable stories.
- [x] Add selection, browser history, independent filters and explicit read state. Reuse the existing storage key; source navigation never marks a story read.
- [x] Give mobile browsing explicit open/close controls and reliable keyboard focus.
- [x] Add original artwork and a small original logo. Document generated asset provenance. Pull-quote text comes from reviewed summary sentences; no new factual LLM output is needed for this presentation change.
- [x] Verify sanitization, missing metadata/source fallbacks, history, read identity, empty filtering and browser-local storage failure.

## Task 2: Integrate assets and prove the edition

Files: `src/news/publication.py`, `src/news/workflow.py`, `pyproject.toml`, publication and workflow tests.

- [x] Give preview runs and strict public exports the same finite reader-asset set.
- [x] Preserve validation of legacy manifests while new exports require the complete new asset set.
- [x] Render the retained, source-audited 81-story edition through the new code into an ignored preview directory. Do not alter its news content or publication receipt.
- [x] Run the application tests and actual desktop/mobile browser interactions. Inspect screenshots and verify source links, history, filters and read state.

## Task 3: Review and deploy the checkpoint

Files: concise design notes, `dispatch_report.html`, PR metadata; preview-only generated artifacts.

- [x] Astra reviews the implementation against the email requirements. Fix findings and request a second pass.
- [x] Scan and push the feature branch; create the PR; review the actual PR for correctness and unnecessary complexity.
- [x] Publish only the verified reader artifact under an isolated preview path on Pages. Do not overwrite the root edition, its manifest, or its assets. Record before/after root hashes.
- [x] Verify the delivered preview bytes and mobile/desktop behaviour. Leave the PR open for Asif's review and email a concise completion link.

## Reference and limits

Reference: https://www.densediscovery.com/issues/411 . The reference uses an archive sidebar and an issue iframe. We preserve its browsing and visual principles, without importing the iframe implementation, subscriptions, tracking scripts, branded logo or artist artwork. Issue 411 explicitly credits Justina Leisyte; a reusable artwork-library license has not been established.

Baseline: 120 tests discovered, 91 executed successfully and 29 database-dependent tests skipped without a disposable test database. Full raw reference pages, REA evidence, email requirements and runtime settings remain ignored and private.
