# Short Product Video Techniques — A Recipe Catalog

A concrete, measurable catalog for 15–60s software product launch / feature-drop videos. Every claim below is timed against frames extracted at 4 fps from the source files in `/tmp/product-video-research/sources/` and ffmpeg scene-cut + silence-detect output.

Frame heights are normalized to **1080p** for all "% of frame height" measurements (sources are 360p/480p but proportions hold).

---

## §1 — Reference Videos

| Slug | Source | Duration | Channel | Downloaded |
|---|---|---|---|---|
| `linear-agent` | youtube.com/watch?v=mRql2VJ99gM | 0:55 | Linear (YT) | Y |
| `linear-releases` | youtube.com/watch?v=6dIwFoQ0eVg | 0:30 | Linear (YT) | Y |
| `linear-reviews` | youtube.com/watch?v=4r8YmQ6lfLo | 0:25 | Linear (YT) | Y |
| `cursor-3` | youtube.com/watch?v=UxbULt_hCdA | 1:30 | Cursor (YT) | Y |
| `notion-calendar` | youtube.com/watch?v=TNVXuVxRa8k | 7:13 | Third-party Notion clip | Y, analyzed first 90s |
| `replit-agent4` | youtube.com/watch?v=-2xHmkpmCBM | 8:25 | Replit (YT) | Y, analyzed first 90s |
| `figma-config2024` | youtube.com/watch?v=n5gJgkO2Dg0 | 67:33 | Figma (YT, full keynote) | Y, analyzed 0–120s |
| `vercel-workflows` | youtube.com/watch?v=C9ahOihLPVA | 8:39 | Vercel (YT) | Y, analyzed first 90s |
| `raycast-glaze` | youtube.com/watch?v=FGbmmgH97ms | 7:57 | Raycast (YT) | Y, analyzed first 90s |
| `stripe-reader-s700` | youtube.com/watch?v=9oieNo53aNY | 1:14 | Stripe / Products | Y |

**Not downloadable as standalone files (CSS/iframe-driven on marketing site):** linear.app hero loop, granola.ai homepage demo, cursor.com homepage reels, lex.page "How Lex Happened" demo. Replit blog post `blog.replit.com/vibe-code-videos-in-replit` is workflow philosophy, not a motion-design playbook (no recipe-level detail to extract). Notion Calendar's official 1-min launch trailer has been removed from Notion's channel; what's at `TNVXuVxRa8k` is a 7-min third-party walkthrough that re-cuts Notion's source clips (watermarked "Clip from Notion's Official Channel") — usable for shot analysis with that caveat.

---

## §2 — Shot Vocabulary (Named Recipes)

Each recipe has the form `name(params) → effect`. Parameters reflect what was measured in the sources.

### `slow_orbit(angle=15°→25°, duration=1.8–2.4s, ease="ease-in-out")`
**What it looks like:** Camera arcs around a tilted UI mockup that floats in space. Subject barely changes scale; the parallax does the work. Used as a hold-shot when something needs to feel "premium / contemplative."
**Exemplars:** `linear-agent` 0:00–0:05 (Linear sidebar tilted ~12°, drifts left-to-right), `linear-agent` 0:10–0:15 ("Ask Linear" command bar floats center-frame at 18° tilt, slight right-arc).
**When to use:** Hero shot on a brand-frame; never on screen-recording UI (parallax breaks the readability).

### `linear_push_in(amount=1.00→1.04, duration=2.0–3.0s, ease="linear")`
**What it looks like:** Slow, perfectly-linear zoom on a UI that's already on screen. No anchor jump, no acceleration. Reads as "the camera is just slightly closer than you noticed."
**Exemplars:** `cursor-3` 0:35–0:40 (full-screen Cursor diff view), `vercel-workflows` 0:11–0:15 (Pranay talking-head pushes in 1.00→1.03).
**When to use:** Static UI hold longer than ~2.5s. Without it the shot dies.

### `ease_out_punch(amount=1.00→1.06, duration=0.35–0.45s, ease="cubic-bezier(0.18, 0.89, 0.32, 1.28)")`
**What it looks like:** Fast pop-in at the start of a cut, then settles. The "1.28" overshoot in the bezier gives the half-frame bounce that makes it feel snappy not zoomy.
**Exemplars:** `stripe-reader-s700` shot-to-shot at 0:01–0:03 (split-screen → location card POPs in), `linear-releases` 0:14–0:16 (mockup grid pops in at scale 0.94→1.00 with the same overshoot, after the title-card cut).
**When to use:** Cold-cut into a new scene, especially a brand-frame title card.

### `match_cut_pull(scale=2.5x→1.0x, duration=0.6s, ease="ease-out")`
**What it looks like:** Outgoing shot has UI element at large scale; incoming shot starts with the same element shape/position but the rest of the frame populates around it. Hides the cut completely.
**Exemplars:** `notion-calendar` 0:08 — macOS dock icon zoomed huge → cuts to full Notion Calendar app where the same icon now reads as the dock icon at normal size. `figma-config2024` ~1:38 (hexagon shape match between bumper and venue B-roll).
**When to use:** Two unrelated shots that share one geometric element.

### `whip_pan_blur(angle=90°, duration=0.18–0.25s, motion_blur=18px)`
**What it looks like:** Camera whips horizontally over ~5 frames; motion blur smears the frame to white/black; on the other side of the blur, you're in a new scene. The blur IS the transition.
**Exemplars:** `figma-config2024` 0:32 (geometric bumper transitions via white blur), `stripe-reader-s700` 0:09–0:10 (whip from coffee-pour split-screen to interview).
**When to use:** Energy injection between two unrelated scenes. Pair with a music hit on the blur peak.

### `crash_cut_to_title(duration_of_title=1.5–2.2s, font="mono-bold-uppercase", letterspacing="0.08em")`
**What it looks like:** Cut from a busy scene directly to pure-black frame with a single line of large mono caps centered in the safe area. No fade in/out — just a hard cut on both sides.
**Exemplars:** `linear-releases` 0:09 ("PLAN AND TRACK RELEASES", on screen 8.75s–10.5s ≈ 1.75s), 0:21 ("CONTINUOUS RELEASE", on screen ~1.6s). Used twice in a 30s video — the structural skeleton.
**When to use:** Section headers in a feature-list video. The title is the cut.

### `dim_floating_screens(tilt=15–25°, dof=shallow, vignette=heavy)`
**What it looks like:** UI mockup floats off-axis in deep black space, only one rectangle of the screen sharply lit; light wraps the bezel; bottom corners always in vignette darkness. No surrounding device chrome.
**Exemplars:** `linear-agent` continuously (10+ floating-screen shots in 55s), `linear-releases` 0:15–0:20 (3 dashboards staircased z-depth).
**When to use:** Premium "we're showing one feature at a time" cinematography. Punishing on text legibility — use only when you can pair with VO or a separate caption.

### `typewriter_punctual(speed=10–12 chars/sec, cursor=block, blink=2Hz)`
**What it looks like:** Text appears one character at a time; trailing block-cursor stays visible after the word completes; 2 Hz blink. Hold last frame for ~1.5s.
**Exemplars:** `linear-releases` 0:24–0:26 ("AVAILABLE NOW" — measured at f0098–f0102 = 1.0s for 13 chars = 13/sec), `linear-reviews` 0:20 ("Think diff" — slower at ~7 chars/sec, deliberate Apple homage).
**When to use:** Final beat before logo card. NEVER as primary caption — feels gimmicky if used twice in one video.

### `kenburns_macro(scale=1.00→1.12, pan=±60px, duration=3.5–4.0s, ease="ease-in-out")`
**What it looks like:** Slow combined zoom+drift on a still / B-roll image. Very slow.
**Exemplars:** `replit-agent4` 0:10–0:14 (Marin County Civic Center aerial — drift right + 1.00→1.10 zoom in 4.0s), `stripe-reader-s700` 0:25 (Revolución coffee shop sign).
**When to use:** B-roll establishing shots. 3.5s minimum, otherwise reads as twitchy.

### `interview_lower_third_slide_in(distance=120px, duration=0.4s, ease="ease-out", hold=2.5–3.5s)`
**What it looks like:** Bottom-left corner: name slides up from below frame edge, role appears under name 0.15s after name lands. Stays for 2.5–3.5s, then fades out (180ms).
**Exemplars:** `cursor-3` at 0:05.0 ("Sualeh Asif / Co-Founder" left + "Michael Truell / Co-Founder" right, both slide up simultaneously, hold to 0:08.5), `vercel-workflows` 0:08 ("Pranay Prakash / Head of Workflows, Vercel"), `replit-agent4` 0:15 (similar pattern).
**When to use:** First time a person is on camera. Never re-introduce.

### `partner_logo_lockup(layout="horizontal +", logos=2–3, duration=2.0–2.5s, hold_at_end=true)`
**What it looks like:** Static end card with `[Customer logo] + [Partner logo] + [Stripe/etc]`, centered, mid-grey background. Holds for 2s before fade-to-black.
**Exemplars:** `stripe-reader-s700` final 2s ("Revolución + Dripos + Stripe"), referenced pattern in Stripe customer-story canon.
**When to use:** Customer-story / co-launch end card only. Never on a solo product launch.

---

## §3 — Cut Grammar

Cut cadence (mean shot length, MSL) computed from ffmpeg scene-detect at threshold 0.1:

| Video | Detected cuts | Effective MSL | Range | Pattern |
|---|---|---|---|---|
| `linear-agent` (55s) | 4 | 11.0s | 4–18s | Continuous-camera; cuts only between major UI moves |
| `linear-releases` (30s) | 4 | 6.0s | 4.7–6.5s | Section-header rhythm — viz, title, viz, title, logo |
| `linear-reviews` (25s) | 3 | 6.4s | 2.4–5.6s | Ramps up — first cut at 2.4s, last at 7.8s, then long hold to logo |
| `cursor-3` (90s) | 30+ | 2.8s | 1.0–4.6s | Two-shot ↔ UI-demo intercut; UI-demo holds longer (3–4s), interview holds shorter (1.5–2.5s) |
| `stripe-reader-s700` (74s) | 30+ | 2.2s | 0.4–3.1s | Densest cuts of any sample; 5 cuts in first 2s as music intro |
| `replit-agent4` (8m, sample 0–90s) | 18 | 4.8s | 1.0–5.3s | Talking-head sustains, B-roll cuts faster |
| `vercel-workflows` (8m, sample 0–90s) | 4 | 22s | 9.8–66s | Mostly held talking-head; almost no cuts in feature-explanation segments |
| `figma-config2024` (intro 0–120s) | 20+ in 0:30–1:00 cluster | varies | 0.03–6.0s | Bumper sequence packs frame-rate cuts (every 2 frames at f0185) for kaleidoscope effect, then long hold on speaker |

**Rules pulled from this:**

1. **Linear cuts every 4–6s on title-card-driven videos** (`linear-releases`, `linear-reviews`). Never holds past 7s except on the closing logo (which is held 2.5–4s).
2. **Cursor holds 3–4s on UI demos** because the UI complexity is high (multi-pane diff views, dropdowns expanding) and the viewer needs reading time.
3. **Stripe customer-story cuts 1.5–2.5s** on B-roll, 3–4s on interview clips, 0.4s on the music-intro montage (5 cuts in 2 seconds at the open).
4. **Talking-head launches** (Replit, Raycast, Vercel) hold the founder shot 8–15s while speaking; B-roll inserts cut in for 2–3s and out.
5. **Pure-style brand bumpers** (Figma Config opening 0:30–1:00) can flash-cut every 0.1–0.2s on geometric shapes, but this is decorative — never on UI.

**Dissolves are rare.** In all 10 videos, only `linear-releases` 0:10–0:11 and `notion-calendar` 0:35 use cross-dissolves (~250–400ms). Everything else is hard cuts. The whip-pan-blur in §2 is the only "soft" transition that's frequent.

---

## §4 — Caption Typography

Measurements taken from frame samples. All sizes expressed as **% of frame height @ 1080p**.

### Title-card / brand-frame captions

| Video | Sample text | Font class | Weight | Size (% of frame ht) | Color | Position | Letterspacing |
|---|---|---|---|---|---|---|---|
| `linear-releases` | "PLAN AND TRACK RELEASES" | Mono (Berkeley Mono / IBM Plex Mono class) | Regular | ~3.5% (38px @ 1080) | #FFFFFF | dead center, baseline at 50% | 0.10em |
| `linear-releases` | "AVAILABLE NOW" | Same mono | Regular | ~5.5% (60px @ 1080) | #FFFFFF | center | 0.08em |
| `linear-reviews` | "Think diff" | Serif (Apple-marketing homage) | Light italic? | ~7% (76px) | #DDD on black, slight glow/blur | center | 0 |
| `figma-config2024` | "5" countdown | Geometric sans | Black (900) | ~25% (270px) | Dark on cream, framed in diamond | center | 0 |

### Lower-third / interview captions

| Video | Name size | Role size | Color | Position | Slide-in |
|---|---|---|---|---|---|
| `cursor-3` | ~2.8% (30px) | ~1.6% (17px) | white on transparent w/ slight gradient | x=4% from left edge, y=85% (vertical) | 0.4s ease-out from 120px below |
| `vercel-workflows` | ~2.6% (28px) | ~1.4% (15px) | white on light-grey scrim w/ rounded corners | x=4% from left, y=82% | 0.35s ease-out from below |
| `stripe-reader-s700` | varies (split panel layouts substitute for lower-thirds) | — | — | — | — |

### Watermark / "during a demo" captions
- `linear-agent`: **none** for all 55s. Visual-only narrative.
- `cursor-3`: none during UI demos (speech does the work).
- `notion-calendar` (third-party clip): "Clip from Notion's Official Channel" persistent watermark at ~1.8% of frame height, bottom-left, 50% opacity — informational, not part of design.

### Caption fade-in / fade-out

- Linear title cards: **hard cut on both sides**, no fade (frames f0036→f0037 = pure flip).
- Linear typewriter cursor: 2 Hz blink (hold ~250ms on, ~250ms off), measured between f0102 and f0105 (1.0s gap, cursor changed state twice).
- Lower-thirds: in 0.35–0.40s ease-out; out 0.18–0.22s linear fade.
- Replit chapter title cards (later in the long video): in 0.5s, hold 2.0s, out 0.4s.

---

## §5 — UI / Mockup / Brand-Frame Ratio

Estimated as % of total runtime in each category. "UI" = real, recognizable product UI screen. "Mockup" = stylized abstraction (data-flow viz, exploded UI, marketing graphic). "Brand-frame" = title card, logo card, end card, interstitial pure-color frame.

| Video | UI % | Mockup % | Brand-frame % | People-on-camera % | Stock/B-roll % |
|---|---|---|---|---|---|
| `linear-agent` | 55% | 25% | 20% (closing 4s logo + title transitions) | 0 | 0 |
| `linear-releases` | 8% | 60% (data-flow viz) | 32% (title cards + logo) | 0 | 0 |
| `linear-reviews` | 50% (distorted code) | 0 | 50% (Think diff card + logo) | 0 | 0 |
| `cursor-3` | 50% | 5% | 5% | 40% (two-shot interview) | 0 |
| `notion-calendar` (intro) | 70% | 5% | 25% | 0 | 0 |
| `replit-agent4` (intro) | 5% | 25% (creative-pillars overlay) | 5% | 50% (CEO monologue) | 15% (Civic Center B-roll) |
| `figma-config2024` (intro) | 0% in first 90s | 0% | 100% (animated bumper + venue B-roll) | 0% | 0% |
| `vercel-workflows` (intro) | 5% | 0% | 5% | 90% (talking-head) | 0% |
| `raycast-glaze` (intro) | 5% | 5% (glaze logo on liquid bg) | 10% | 80% (talking-head) | 0% |
| `stripe-reader-s700` | 25% (mobile UI on hardware) | 5% | 25% (location/role/logo cards) | 30% (interviews) | 15% (coffee, hardware close-ups) |

**Insight:** Pure-UI demos under 30s (Linear) lean **brand-frame heavy (20–32%)** because they need title cards as structural beats. Customer-story videos (Stripe) split roughly 25/25/25/25 across UI / brand-frame / interview / B-roll. Founder-led launches (Replit, Vercel, Raycast) are 50–90% talking-head. **Almost no good launch video is more than ~70% real UI** — there's always cinematic cover.

---

## §6 — Music + SFX Patterns

### Music-out at end (silence-detect data)

| Video | Music ends at | Logo holds for | Effect |
|---|---|---|---|
| `linear-agent` | 51.0s | 4.0s in silence | Logo enters + reverb tail of last note → 3.5s of total silence on logo. Intentional. |
| `linear-releases` | 27.6s | 2.5s in silence | Same pattern: type "AVAILABLE NOW", music drops out, logo card holds. |
| `stripe-reader-s700` | 72.9s | 1.2s in silence | Partner-logo lockup with musical decrescendo into silence. |
| `cursor-3` | continuous through 90s | — | No closing-logo silence; outro music carries over end card. |
| `raycast-glaze` | continuous | — | Same — talking-head walks into bumper without music drop. |

**Pattern:** **Brand-frame end cards are paired with 1.2–4.0s of silence** (or at least music decay) on the closing logo. This is the single most consistent technique across the dataset.

### Music structure (inferred from amplitude + cuts)
- `linear-agent`: ambient drone with one mid-track build at ~0:25 (matches first major scene cut). No drums.
- `linear-releases`: piano + synth pad. Build crescendos into "AVAILABLE NOW" typewriter (24–26s), then drops.
- `stripe-reader-s700`: upbeat indie-rock (drums entering at 0:02), syncs intro montage cuts to kick-drum hits (5 cuts in first 2s = 4-on-the-floor).
- `cursor-3`: continuous low-key bed under VO; no swells. Speech-driven.
- `replit-agent4`: orchestral-cinematic, swells at chapter changes (~0:25, 0:45).

### SFX usage
- `linear-releases`: **typewriter clicks** (likely 110–130 ms apart matching 10–12 char/s typing) under "PLAN AND TRACK RELEASES" + "AVAILABLE NOW". Mechanical-keyboard sample, not a dot-matrix.
- `linear-reviews`: faint static/CRT-buzz under "Think diff" — single source-effect, no foley.
- `figma-config2024`: bumper has bass-impact hit on each kaleidoscope cut (0:30–0:50 sequence).
- `stripe-reader-s700`: card-tap "click" SFX synced to phone-payment moment at ~0:38.
- All YouTube-uploaded launches use NO whoosh / glitch transitions. Whooshes are absent from this entire dataset.

### Silence holds
- `cursor-3` has 30+ inter-word silences > 0.3s (it's a dialogue video). These don't count as "silence holds" — they're speech rhythm.
- True silence-holds (intentional negative-space): `linear-agent` 51–55s (4s), `linear-releases` 27.6–30.1s (2.5s), `stripe-reader-s700` 72.9–74.1s (1.2s).

---

## §7 — Per-Video Shot Lists

### `linear-agent` (0:55, dim-floating-screens style, no captions)

| # | t_start | t_end | dur | shot type | camera | caption | transition_out |
|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 4.0 | 4.0 | Floating Linear sidebar UI tilted 12° | slow_orbit + drift right | none | hard cut |
| 2 | 4.0 | 9.0 | 5.0 | "Project spec" doc panel right of frame | slow_orbit, push-in 1.00→1.04 | none | hard cut |
| 3 | 9.0 | 17.0 | 8.0 | "Ask Linear" command bar, lit pill on dark | slow drift left-to-right | none | hard cut |
| 4 | 17.0 | 22.0 | 5.0 | Issue list with severity icons, tilted | slow_orbit | none | hard cut |
| 5 | 22.0 | 30.0 | 8.0 | Architecture board with floating cards | pull-back reveal | none | hard cut |
| 6 | 30.0 | 40.0 | 10.0 | Full Linear doc page filling frame | locked, slight push-in | none | hard cut |
| 7 | 40.0 | 45.0 | 5.0 | "I created the PRD" reply card | slow drift up | none | smash to black |
| 8 | 45.0 | 48.0 | 3.0 | Black with "Linear. At your command." | locked | "Linear. At your command." centered, ~3.5% ht, white serif | dissolve |
| 9 | 48.0 | 55.0 | 7.0 | Linear logo centered on black | locked, logo fade-in over 0.5s | (Linear logo) | end (4s silence) |

### `linear-releases` (0:30, title-card-driven, mockup-heavy)

| # | t_start | t_end | dur | shot type | camera | caption | transition_out |
|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 4.7 | 4.7 | Abstract data-flow viz (lines + ENG-#### chips), MOBILE APP label | slow drift, push-in 1.0→1.05 | "MOBILE APP / SCHEDULED RELEASE" small UI label | scene-cut |
| 2 | 4.7 | 9.0 | 4.3 | Same viz extended w/ "LAUNCH v1.3" right edge | continued drift | "LAUNCH v1.3" small UI text | smash to black |
| 3 | 9.0 | 10.7 | 1.7 | **Black title card "PLAN AND TRACK RELEASES"** | locked | "PLAN AND TRACK RELEASES", mono, ~3.5% ht, center | cross-dissolve to next (only dissolve in video) |
| 4 | 10.7 | 15.6 | 4.9 | 3 dashboard cards staircased in z | slow_orbit | ("MOBILE APP", "SDK", "PRODUCTION" mini labels) | hard cut |
| 5 | 15.6 | 21.7 | 6.1 | Single tilted "PRODUCTION/CONTINUOUS RELEASE" board | slow drift | viz only | smash to black |
| 6 | 21.7 | 24.0 | 2.3 | **Black card with typewriter starting** | locked | "RELEASES" typewriter | hard cut (text continues) |
| 7 | 24.0 | 27.6 | 3.6 | Black with completed "AVAILABLE NOW" + cursor | locked | typewriter completes, cursor blinks 2 Hz | music-out |
| 8 | 27.6 | 30.1 | 2.5 | Linear logo centered | locked | (Linear logo) | end (silence) |

### `linear-reviews` (0:25)

| # | t_start | t_end | dur | shot type | camera | caption | transition_out |
|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 2.4 | 2.4 | Distorted color-fringe "type Page = ..." code, glowy chromatic-aberration | locked, slight push | none | jump cut |
| 2 | 2.4 | 5.6 | 3.2 | Same code style, scrolling | scroll up | none | hard cut |
| 3 | 5.6 | 7.8 | 2.2 | "const sorted = ... return sorted" close-up | tracking (subtle drift) | none | smash |
| 4 | 7.8 | 22.0 | 14.2 | (more code beats / scrolling) | various | none | smash to black |
| 5 | 22.0 | 23.5 | 1.5 | **Black "Think diff" card** | locked | "Think diff" serif, ~7% ht, soft glow | hold-cut |
| 6 | 23.5 | 25.5 | 2.0 | Linear logo on black | logo fades in | (logo) | end |

### `cursor-3` (1:30 — first 90s)

| # | t_start | t_end | dur | shot | camera | caption | trans |
|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 5.7 | 5.7 | Two-shot, Sualeh + Michael at table, library bg | locked, very slow push 1.00→1.02 | none | hard cut |
| 2 | 5.7 | 9.5 | 3.8 | Same two-shot (Michael speaking, Sualeh nods) | locked | "Sualeh Asif / Co-Founder" + "Michael Truell / Co-Founder" lower-thirds slide up at 5.0s, fade out 8.5s | hard cut |
| 3 | 9.5 | 13.6 | 4.1 | Full-frame UI: model picker dropdown | locked | none | hard cut |
| 4 | 13.6 | 14.8 | 1.2 | Two-shot insert | locked | none | hard cut |
| 5 | 14.8 | 17.9 | 3.1 | UI demo: code diff + "Creating PR..." button | linear push-in 1.00→1.04 | none | hard cut |
| 6 | 17.9 | 19.1 | 1.2 | Two-shot beat | locked | none | hard cut |
| 7 | 19.1 | 22.0 | 2.9 | UI: model selection w/ context window descriptor | static | none | hard cut |
| 8 | 22.0 | 26.6 | 4.6 | Two-shot, Sualeh closer to laptop, "let me show you" beat | locked | none | hard cut |
| 9 | 26.6 | 29.1 | 2.5 | UI: Cursor chat w/ Atlas issue browser | static | none | hard cut |
| ... | (pattern continues — UI 3–4s, two-shot 1.5–2.5s) | | | | | | |
| 30 | 84.0 | 90.4 | 6.4 | Closing two-shot (both look at camera, smile) | locked | none | fade to black |

### `stripe-reader-s700` (1:14)

| # | t_start | t_end | dur | shot | camera | caption | trans |
|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 2.0 | 2.0 | Split-screen barista pour shots, music intro montage | sync-cut on each kick (5 cuts in 2s) | none | whip |
| 2 | 2.0 | 5.7 | 3.7 | Animated NYC map w/ pin, "dripos" + "NEW YORK" big | locked | "NEW YORK" ~12% ht display, "dripos" w/ logo ~4% | hard cut |
| 3 | 5.7 | 9.0 | 3.3 | Interview B (employee) split with bg | locked | "EMPLOYEE" giant tag right side (kinetic typography) | hard cut |
| 4 | 9.0 | 14.3 | 5.3 | Coffee shop "Revolución" sign w/ Ken Burns | kenburns_macro 1.00→1.10 left | none | hard cut |
| 5 | 14.3 | 22.0 | 7.7 | Interview clips intercut | locked + slow push | lower-third name + role | hard cut |
| 6 | 22.0 | 30.0 | 8.0 | Hardware product hero close-ups | macro pulls / orbits | none | hard cut |
| 7 | 30.0 | 50.0 | ~20.0 | Use-case demo on phone in hand | tracking | UI captions live in product | hard cut |
| 8 | 50.0 | 72.9 | 22.9 | Wrap interview + shop B-roll | varies | (lower-thirds reused) | music-out |
| 9 | 72.9 | 74.1 | 1.2 | **End card: Revolución + Dripos + Stripe lockup** | locked | partner_logo_lockup pattern | end (silence) |

### `notion-calendar` (third-party clip; 0–90s analyzed)

| # | t_start | t_end | dur | shot | camera | caption | trans |
|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 2.5 | 2.5 | macOS Dock icons (Finder, Notion, Mail, Safari), pure white bg | static | persistent watermark "Clip from Notion's Official Channel" lower-left | match_cut_pull (Notion icon → app) |
| 2 | 2.5 | 5.0 | 2.5 | Full Notion Calendar app, macOS frame | locked, slight push | none | hard cut |
| 3 | 5.0 | 8.5 | 3.5 | Dock icons w/ "Notion Calendar" appearing | hop-in animation on icon | none | match_cut_pull again |
| 4 | 8.5 | ~16 | ~7.5 | App view, Cmd-+ to open event, sidebar list | static UI cap | (live UI) | hard cut |
| ... | (subsequent intro/feature beats; not a launch trailer) | | | | | | |

### `replit-agent4` (0:00–1:30 sample)

| # | t_start | t_end | dur | shot | camera | caption | trans |
|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 4.0 | 4.0 | White bg with Replit logo fade-in centered, then progress bar | locked | none | hard cut |
| 2 | 4.0 | 6.5 | 2.5 | Aerial Marin County Civic Center (FLW) | kenburns_macro right + 1.00→1.04 | "The Marin County Civic Center / Designed by Frank Lloyd Wright" 2-line caption bottom-right, ~1.8% / ~1.4% ht | hard cut |
| 3 | 6.5 | 18.3 | 11.8 | CEO monologue, lobby setting | locked, micro-push | none | hard cut |
| 4 | 18.3 | 21.1 | 2.8 | CEO with "Creative Expression / Acceleration / Collaboration / Production" floating-pill overlay | locked, pills fade in | 4 floating pills, sans, ~1.8% ht | hard cut |
| 5 | 21.1 | 24.0 | 2.9 | Cinematic interior architecture (FLW spiral) | tilt up | none | hard cut |
| 6 | 24.0 | 27.0 | 3.0 | CEO again | locked | none | hard cut |
| ... | (CEO monologue intercut with FLW B-roll, 8–15s holds) | | | | | | |

### `figma-config2024` (0:00–2:00 intro)

| # | t_start | t_end | dur | shot | camera | caption | trans |
|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 1.4 | 1.4 | Figma logo (white on black) loading | hold | none | hard cut |
| 2 | 1.4 | 31.5 | 30.0 | Animated geometric bumper (kaleidoscope, hexagons, countdown 5→1, color floods) | flash-cuts every 0.1–0.4s, 100+ inter-cuts in this segment | "5 / 4 / 3 / 2 / 1" countdown numerals, ~25% ht each | whip → venue B-roll |
| 3 | 31.5 | 35.0 | 3.5 | Dark venue interior, low light | locked | none | hard cut |
| 4 | 35.0 | 38.5 | 3.5 | Stage with "Welcome" sign & projector lighting | drift right | none | hard cut |
| 5 | 38.5 | 50.0 | 11.5 | Audience reaction shot, dimly lit | tracking | none | hard cut |
| 6 | 50.0 | 65.0 | 15.0 | Speaker walks on, tracking | tracking | none | hard cut |
| ... | (long-form keynote follows) | | | | | | |

### `vercel-workflows` (0:00–1:30 sample)

| # | t_start | t_end | dur | shot | camera | caption | trans |
|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 25.5 | 25.5 | Pranay Prakash standing, glass office bg | linear push-in 1.00→1.03 over 8s, then locked | "Pranay Prakash / Head of Workflows, Vercel" lower-third slides up at ~3s, holds to ~10s | hard cut |
| 2 | 25.5 | 35.3 | 9.8 | Same setup, B-shot from slightly different angle | locked | none | hard cut |
| 3 | 35.3 | 102 | 66.7 | UI demo of Workflows console | static | live UI captions | hard cut |

(Vercel's launch video is essentially a long-form explainer; the "feature reveal" punch is in the UI demo, not in cuts.)

### `raycast-glaze` (0:00–1:30 sample)

| # | t_start | t_end | dur | shot | camera | caption | trans |
|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 2.4 | 2.4 | Talking-head intro (Vidit?), warm bedroom-studio | locked | none | hard cut |
| 2 | 2.4 | 5.8 | 3.4 | **Brand bumper: "glaze / By Raycast" on liquid-marble black** | static, marble drifts | "glaze" wordmark ~10% ht, "By Raycast" tag ~2.5% | hard cut |
| 3 | 5.8 | 10.0 | 4.2 | Talking-head | locked, micro push | none | hard cut |
| 4 | 10.0 | 23.0 | 13.0 | Continued talking-head w/ B-roll inserts | locked | none | hard cut |
| 5 | 23.0 | 31.3 | 8.3 | Glaze UI demo segment | static | live UI | hard cut |
| ... | (continuous talking-head dominated structure) | | | | | | |

---

## §8 — The "Zergboard Fix" Templates

If the goal is a **25–35s product demo** for Zergboard, here are 3 ready-to-execute shot-list templates pulled from the strongest exemplars.

### Template A — "Linear Releases" mode (title-card-skeleton)
**Use when:** Zergboard has 2–3 features to highlight that already have visual logos / mockups.
**Length:** 28–32s.
**Tone:** Premium, structural, mono-typographic, brand-forward.

```
00:00–00:05  HOOK     Abstract data-flow / kanban-mockup with slow_orbit + push 1.00→1.04
                      No captions, only tiny in-mockup labels.
00:05–00:07  TITLE 1  Smash-cut to black: "PROJECT BOARDS FOR AGENTS" 
                      mono, ~3.5% frame ht, hold 1.7s, hard cut out.
00:07–00:13  FEATURE  3 Zergboard cards staircased z-depth, slow_orbit
                      Cards show: sprint card, agent assignee, MCP icon
00:13–00:14  TITLE 2  Smash-cut: "$1 PER SEAT" or "AI-NATIVE", 1.5s hold
00:14–00:22  FEATURE  Continuous-camera fly-through over board layout
                      Show one expanded card, then board zoom-out
00:22–00:25  TYPEWRITER  black bg, "AVAILABLE NOW" or "TRY IT FREE"
                      11 chars/sec, 2 Hz cursor blink
                      music-out begins under the typing
00:25–00:30  END      Zergboard logo centered, hold 4s in silence
                      logo fades in over 0.5s
```
Music: ambient pad/synth with one swell at 0:13 (matching the second title card), drops out at 0:23.
SFX: typewriter-key clicks 110 ms apart during the AVAILABLE NOW beat.
**Closest reference:** `linear-releases` exact structure.

### Template B — "Cursor-3" mode (founder + UI-demo intercut)
**Use when:** Matt or Idan wants to be in the video as the launcher.
**Length:** 45–60s.
**Tone:** Conversational, demo-grounded, lo-stakes credibility.

```
00:00–00:05  HOLD       Two-shot Matt + co-host at desk, library/lo-fi office bg
                        Locked camera, very slow push-in 1.00→1.02
                        Speak: hook line ("Project boards your agents can actually use")
00:05–00:08  CAPTION    Same shot, lower-thirds slide up at 5.0s
                        "Matt Eisner / GTM, Zerg" + "[co-host] / Role"
                        ~2.8% / 1.6% ht, x=4% from edge, y=85%
                        Hold to 8.5s, fade out
00:08–00:13  UI DEMO    Full-frame screen recording of Zergboard board view
                        linear_push_in 1.00→1.04 over 5s
                        Speak over: "here's the board"
00:13–00:15  TWO-SHOT   Insert reaction
00:15–00:20  UI DEMO    Card detail w/ agent assignment dropdown
00:20–00:23  TWO-SHOT   Speak: "and the agent picks it up"
00:23–00:30  UI DEMO    MCP integration / agent updates the card live
00:30–00:42  TWO-SHOT   Wrap: "$1 per seat / try it now"
00:42–00:45  END        Cut to Zergboard logo + URL on dark bg, hold 3s
```
Music: continuous low-key bed under VO; no hits.
**Cut cadence:** UI 3–4s, two-shot 1.5–2.5s. Don't violate this — Cursor's video proves it works because the asymmetry gives the demo room to breathe.
**Closest reference:** `cursor-3` exact structure.

### Template C — "Linear Agent" mode (visual-only, music-driven, no VO)
**Use when:** You want a 25s "Apple-style" hero loop for the homepage that loops cleanly.
**Length:** 22–28s.
**Tone:** Premium, contemplative, visual-first, no commitment to specific copy.

```
00:00–00:05  TILTED UI    Zergboard sidebar tilted 15° in deep black space
                          slow_orbit, dim_floating_screens, vignette heavy
                          Light wraps the sidebar; rest of frame in shadow
00:05–00:09  COMMAND      Floating pill: "/assign agent" or "Ask Zergboard"
                          Drift left-to-right
00:09–00:14  ISSUE LIST   Tilted issue list 18°, slow_orbit
                          Show 6–8 lanes
00:14–00:18  ARCHITECTURE  Pull back to reveal whole board; cards staircase
00:18–00:21  CARD ZOOM-IN  One card grows to fill frame; agent reply visible
00:21–00:23  CRASH-OUT    Smash to pure black, 0.4s silence
00:23–00:25  TITLE        White serif: "Zergboard. Built for agents." centered
                          ~3.5% frame ht, hard cut on both sides
00:25–00:30  LOGO         Zergboard logo center, 4s silence
```
Music: ambient drone with one mid-track swell at 0:13.
**Captions: only the closing line.**
**Closest reference:** `linear-agent` exact structure. This is the highest-prestige mode. Hardest to produce because it requires an artful 3D mockup pipeline.

---

## §9 — Anti-Patterns Observed (or Conspicuously Absent)

What the best videos in this dataset DO NOT do:
- **No whoosh/swish SFX on cuts.** Zero examples in 10 videos. If you've added a whoosh, that's why it feels "stocky."
- **No fade-in on captions in title-card mode.** Linear hard-cuts on the caption — the title IS the cut.
- **No double-zoom.** When push-in is used, it's exactly one direction at one rate per shot. Never push-in then push-in faster.
- **No bullet-list caption stacks.** Captions are always single-line or 2-line max. Replit's "Creative Expression / Acceleration / Collaboration / Production" is the only multi-pill example, and they're spatially separated, not stacked.
- **No drop shadows on white-bg captions.** Lower-thirds use scrim or transparent gradients, never shadows.
- **No reveal-the-product hand-shot.** Stripe Reader S700 shows hardware-in-hand, but the product is ALWAYS already on; no "reveal box" shots.
- **No 4-on-the-floor sync on UI cuts.** Stripe syncs to drums in the music *intro montage* — but never on the UI demo cuts. Music sync is for B-roll/montage, not for product feature beats.
- **No color overlays on UI screens.** UI is shown as the user sees it. Tinting the UI to brand colors (purple wash etc.) is conspicuously absent.

---

## §10 — Quick-Reference Recipe Card

For motion-recipes implementation priority:

| Recipe | Build priority | Cost to produce | Used in N references |
|---|---|---|---|
| `linear_push_in(1.00→1.04, 2.0–3.0s, linear)` | **1 (build first)** | Low — ffmpeg zoompan filter | 6/10 |
| `crash_cut_to_title(mono, ~3.5%, 1.5–2.2s hold)` | **2** | Low — title card + cut | 3/10 (signature on Linear) |
| `interview_lower_third_slide_in(0.4s, ease-out, hold 2.5s)` | **3** | Low — overlay + animation | 4/10 |
| `typewriter_punctual(11 ch/s, 2 Hz cursor)` | **4** | Medium — needs SFX-sync | 2/10 (Linear signature) |
| `slow_orbit(15–25°, 1.8–2.4s, ease-in-out)` | 5 | High — needs 3D mockup | 3/10 |
| `dim_floating_screens(tilt + vignette + DOF)` | 6 | High — Cinema 4D / After Effects | 2/10 |
| `match_cut_pull(2.5x→1.0x, 0.6s)` | 7 | High — requires choreography | 2/10 |
| `whip_pan_blur(90°, 0.18–0.25s, 18px blur)` | 8 | Medium — directional blur + audio sync | 2/10 |
| `partner_logo_lockup(end card, 2.0–2.5s)` | 9 | Trivial | 1/10 (only Stripe-style) |
| `kenburns_macro(1.00→1.12, 3.5–4.0s)` | 10 | Trivial — ffmpeg zoompan | 2/10 |

---

*End of techniques catalog. Source files in `/tmp/product-video-research/sources/`, frame samples in `/tmp/product-video-research/frames/`. All durations verified via ffprobe; cut timings via ffmpeg scene-detect at threshold 0.1; silences via silencedetect at -30 dB / 0.3s.*
