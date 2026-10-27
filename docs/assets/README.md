# Daily News tour assets

The 24-second story-style tour was made with the [Brag skill](https://github.com/latent-spaces/brag) and [Hyperframes](https://github.com/heygen-com/hyperframes). Actual captures of the redesigned Daily News reader show the retained 26 October 2026 edition: title browsing, NZ politics filtering on mobile, a selected story, its briefing and original reporting. Captures are recorded examples; the tour does not imply fresh stories or live counts.

- [`../tour/reader-tour.mp4`](../tour/reader-tour.mp4): 1920 × 1080, 30 fps, H.264/yuv420p and AAC, with fast-start metadata for browser playback. A selected product poster is baked into frame zero.
- `reader-tour.gif`: a silent README preview linked to the hosted player.
- [`../tour/reader-tour-poster.jpg`](../tour/reader-tour-poster.jpg): a settled real-product frame.
- [`../tour/reader-tour.vtt`](../tour/reader-tour.vtt): English on-screen story captions. There is music, with no narration.
- `readme-banner.png`: a title frame from the new film.

[Watch and interact with the tour](https://asif-jc.github.io/daily-news/tour/). The player has native play/pause, seeking and volume controls, chapter buttons, captions, a text transcript, an MP4 download and a separate link to the live reader. A movie is not a live app; the reader link opens the actual interactive product.

The previous README linked to a GitHub raw MP4 response with `application/octet-stream`, which could download rather than open a playable page. The hosted player requests a relative `video/mp4` source from GitHub Pages. Deployment verification checks the real Content-Type, range response and desktop/mobile playback rather than treating an encoded file as delivery proof.

Music: **“Happy Beats / Business Moves Vol. 11” by Sascha Ende, [ende.app](https://ende.app/en)**, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). A trimmed excerpt is mixed at reduced volume with fades. The track retains its separate licence. [Brag music catalogue](https://github.com/latent-spaces/brag/blob/main/skills/brag/assets/music/README.md).

Interface sounds: **Kenney**, [Interface Sounds](https://kenney.nl/assets/interface-sounds), [CC0](https://creativecommons.org/publicdomain/zero/1.0/). Original editorial art and the folded-paper/N logo are documented in [the reader design](../design/reader.md). The paper reveal uses a Hyperframes registry component. Authoring source and intermediate captures remain in ignored local storage.
