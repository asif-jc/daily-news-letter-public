# Scheduled publication implementation plan

**Approved goal:** run news independently inside the existing Dagster instance at 03:00 and 15:00 Pacific/Auckland, automatically publish validated editions through GitHub, and verify delivery against PostgreSQL. Existing services and unrelated workloads retain their configuration and ownership.

**Architecture:** a separate code location and Python environment run one restartable publication job. PostgreSQL owns processing evidence and edition checkpoints. Private SSD state retains the current publication attempt across retries. A repository-specific SSH key can push only reviewed public exports from a dedicated checkout. GitHub validates and deploys the static reader; the private job confirms delivered hashes before reporting success.

## Implementation and verification

- [x] Build a restartable `news refresh` command with a whole-attempt lock, atomic private attempt state, bounded deployment polling, explicit Git paths and secret scanning. Save the pipeline run ID before processing so retries resume rather than recollect. Test failure between build, push and confirmation, overlapping execution, stale editions, divergent main, and retry after an ambiguous push.
- [x] Add the optional pinned Dagster dependency, separate code location, 03:00/15:00 timezone-aware schedule, bounded step retries and sanitized logs. Keep detailed evidence in the existing private database and output directory. Test the actual schedule ticks and job execution contract.
- [x] Add a public freshness check independent of the home machine, using GitHub Actions and a deduplicated issue for stale/failed publication. Preserve the previous good edition on generation failure. Keep main code changes reviewed and restrict automation commits to `site/`.
- [x] Run the full suite using a disposable PostgreSQL database and Chromium, inspect diffs, scan outgoing commits and public artifacts, then merge the implementation PR under the user's explicit release approval.
- [x] Install the isolated SSD runtime, private environment and repository-specific deploy key; register the new code location additively in the shared Dagster workspace. Verify existing jobs and schedules remain available. Start and inspect the news schedule.
- [x] Execute a real full refresh on the local runner, observe build, public commit, successful Actions deployment and database publication receipt. Inspect the deployed reader on desktop/mobile. Exercise checkpoint resume and scheduled execution without publishing an older edition over a newer one.
- [x] Reconcile and retire verified merged feature branches, preserve private authoring artifacts, and record executed evidence, limitations and recovery commands in dispatch_report.html and operations documentation. Milestone emails were sent; final delivery status is recorded in the release PR and completion audit.

## Operational choices

- Target completion by 06:00/18:00, pending measured run duration. Do not promise a runtime before measurement.
- News alone uses its own runtime settings, filesystem, deploy key and code server. No private infrastructure identifiers are committed.
- One publication job owns generation through delivery confirmation. Retries reuse the same pipeline run and commit; a deployment failure does not generate another edition.
- Freshness is checked from GitHub, so a dead home machine is observable. A failed or stale delivery opens/updates one issue; recovery closes it. Account notification delivery remains dependent on GitHub notification settings.
- A deploy key is repository-scoped but GitHub does not path-restrict it. The publisher enforces site-only changes and normal fast-forward pushes; no force pushes.
- No platform migration, database replacement, broad container changes, or automatic deletion of retained news evidence.

## Added requirement: Dependabot

- [x] Configure weekly Monday 09:00 Pacific/Auckland checks for pip/pyproject.toml and GitHub Actions. Keep update PRs reviewed, with no automatic merging. Verify the committed configuration, GitHub's update-job execution and resulting status or PRs; local YAML parsing alone is insufficient.

## Runtime findings incorporated

- The existing global run limit was one. Two total slots plus one per code location preserve the original workload's one-run limit while allowing news to proceed independently.
- Explicit control-group shutdown and news-only startup recovery prevent an interrupted worker record from permanently occupying its schedule slot. Queued runs and other locations are excluded.
- Independent review found and resolved two publisher-checkout wedges: abandoned commits now belong to detached per-attempt worktrees, and disjoint reviewed code updates can fast-forward while preserving an export. Real Git regressions cover both, lost push responses, and refusal to replace a newer edition.

## Executed result

The scheduled validation published 154 stories from 232 analysed articles and verified the delivered release against PostgreSQL. The complete cold run took 152.1 minutes with 675 audited model calls. The permanent 03:00/15:00 Pacific/Auckland schedule is running. A controlled service restart and a confirmed-attempt Dagster re-execution passed. Dependabot update checks succeeded and its update PRs remain for review. The dispatch report contains the measured funnel, source counts, actual schema sample and verification limits.
