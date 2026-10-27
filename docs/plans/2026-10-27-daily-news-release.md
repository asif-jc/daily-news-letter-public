# Daily News release and playable Brag tour

Asif authorized carrying out PR #25's comment tasks, merging the PRs, and creatively updating the video while fixing its playback problem.

## Scope and order

1. Review and merge PR #25. Its independent standards and requirements reviews passed; merge commit `d512beb` contains the reader and sidebar refinements.
2. Build a new 24-second Brag film using actual redesigned desktop/mobile reader captures. The story goes from news overload to browsing, personal relevance and original reporting. Keep captions, poster, GIF, credits and README branding aligned.
3. Replace the README's raw GitHub MP4 entry point with a Pages-hosted player. Native playback/seek/volume controls, chapter jumps, transcript, download and a separate live-reader link make the result usable without authoring tools.
4. Export the existing published edition through the real store and strict reader whitelist. Its date and stories do not change. Stage the reader plus only the four named public tour files for Pages.
5. Retain a separate verified presentation receipt for a changed design/URL. First publication remains immutable; no schema migration, new news run, publication-date update or weakened delivery check is needed.
6. Review the release PR, scan outgoing commits/files/media, then rename the GitHub repository to `daily-news` and merge. Update maintained links and origin. Verify the new Pages reader and tour, HTTP media type/ranges, desktop/mobile playback and the database receipt. Keep authoring projects and raw diagnostic data private.

## Playback diagnosis

The former README link redirects to a GitHub raw response with `application/octet-stream`. Its H.264/AAC codecs were compatible, but that route is a file download rather than a reliable player. Video scrubbing also needs byte-range support: a basic local Python server reproduced seek-to-zero; a range-aware server returned `206`/`video/mp4` and chapter seeking correctly reached 8s and 14s. The hosted page is the fix, not a codec change alone.

## Verification targets

- Exact PR heads reviewed, checks successful, merge states verified.
- Hyperframes check passes with real contrast coverage; every scene visually inspected. Intentional paper scraps leaving the canvas are reviewed decorative warnings.
- Final film: 1920×1080, 30fps,720frames,24seconds,H.264/yuv420p,AAC,fast-start; settled poster baked into frame0, metadata checked.
- Application and presentation-receipt tests, including unchanged original publication/payload/timestamps/run state, retry idempotence, URL/design distinctions and no receipt on failed verification.
- Native play/pause, chapter seek, captions/transcript, download and live-app navigation checked on the deployed page; 390px/mobile overflow checked. Safari and screen-reader coverage must not be implied.
- Every intended deployed file compared with local bytes. Reader manifest remains reader-only; tour assets have a separate explicit staging owner.
- Full-redaction Gitleaks and separate private-network/path/personal-data/media checks before every push. Do not publish local credentials, infrastructure, raw reference captures or model responses.
