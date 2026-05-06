# Software Product Video Best Practices

A reference for short (15–60s) launch / feature demo videos used by B2B SaaS, dev-tool, and productivity-software companies. Built to feed a reusable Claude Code skill that helps a PM/CoS produce these consistently and to address three specific pain points: vague title copy, dead space in frame, text too small to read.

---

## 1. Reference catalog — exemplar videos

A mix verified directly via WebFetch (live site embeds), via web search confirming the launch artifact exists, and a few where only the YouTube/Twitter posting was confirmable. Where I could not verify the live URL, I say so.

| # | Company / Product | Where it lives | Why exemplar |
|---|---|---|---|
| 1 | **Linear — homepage hero / feature reels** (`linear.app`) | linear.app, plus per-feature pages e.g. `linear.app/insights`, `linear.app/monitor` | Sets the bar for product-shot-as-marketing: tight crops on real UI, slab type, no chrome, ~2–4s per beat. Linear's launch artifacts on X/YouTube reuse the same visual language. (Verified live; the homepage uses tightly-cropped UI stills + interactions rather than a single hero video.) |
| 2 | **Linear Insights** (launch March 2023, not 2024) | `linear.app/insights` and `linear.app/changelog/2023-03-23-linear-insights` | Charts-first frame composition; the new capability (segmented dashboards) is on screen in the first beat. |
| 3 | **Vercel — Next.js Conf keynote drops + Vercel Ship recaps** | `vercel.com/blog/recap-next-js-conf-2024`, YouTube `Next.js Conf 2024` | Long-form keynote, but the *clips* that travel on X are 20–45s with one feature per clip, captioned, end-card with "Available today on vercel.com". |
| 4 | **Granola — homepage demo** | `granola.ai/demo-meeting`, intro clip on `granola.ai` | Shows the actual product surface (notepad with grey AI text vs black user text) — the value is legible without VO. (Verified live; specific durations not extractable from HTML.) |
| 5 | **Notion Calendar (née Cron) launch Jan 2024** | `notion.com/blog/introducing-notion-calendar`, YouTube `TNVXuVxRa8k`, `GbkbW0WOnek` | Cron's pre-acquisition launch reels were the canonical "calendar app feels native" template; the Notion Calendar relaunch reuses the same crisp keystroke-shortcut showcase. |
| 6 | **Cursor — homepage and product page demos** | `cursor.com`, `cursor.com/product`, `cursor.com/features` | Multiple short autoplay loops, each tied to one capability (Tab autocomplete, Agent, Mission Control). Shown over a "subtle, solid brand background" rather than chrome. (Verified live.) |
| 7 | **Arc Browser launch 1.0 (May 2022) + "Act II" (Feb 2024)** | YouTube `QsCNcqdHVrc` (intro), `WIeJF3kL5ng` (Act II) | Cinematic, narrative, longer than the genre — but the Act II reveal is the rare example of a 90-second hero that still works as a 30-second cut-down because of how it's beat-structured. |
| 8 | **Raycast — feature reels** (`raycast.com` and YouTube) | `raycast.com` hero, plus YouTube channel ("Introducing Raycast Focus", "Raycast Notes is Finally Out") | Feature-by-feature short videos in a YouTube grid; thumbnails consistent, clips run 25–60s, keyboard-overlay HUD shows the shortcut as it happens. (Verified: 18 YouTube embeds on homepage.) |
| 9 | **Stripe — Sessions launches** | `stripe.com/newsroom`, YouTube playlist `Products` (`PLcoWp8pBTM3AqxZC9Gdty36o_Bt6rDb7z`) | Stripe's product reels are notable for end-card discipline: brand mark, one-line CTA, URL on screen for ~3s. I could not confirm a single "Atlas + Radar" launch video; treat as separate per-product reels. |
| 10 | **Superhuman — "How Superhuman Email Works"** (Rahul Vohra walkthrough, Jan 2020) plus AI Instant Replies (Feb 2024) | YouTube channel `@SuperhumanCo` | A counterexample on the longer end (~3 min) — but the AI Instant Replies clip is a textbook 30-second feature beat: cursor lands, three replies appear, one is picked, sent. |
| 11 | **Figma — Config 2024 keynote + per-feature drops** | YouTube `n5gJgkO2Dg0` (keynote), feature clips on `figma.com/blog` | Config keynote demos are the source of every "Make Designs" 20-second clip on X. Captions come *with* the action, not before. |
| 12 | **Replit — Agent 4 launch (Oct 2025)** | YouTube `-2xHmkpmCBM`, `blog.replit.com/introducing-agent-4-built-for-creativity` | Replit also publishes a meta-resource: `blog.replit.com/vibe-code-videos-in-replit` ("Ship Motion-Style Launch Videos in Minutes") — itself useful as primary source on the genre. |
| 13 | **Lex — original launch (Oct 2022, Nathan Baschez)** | `lex.page`, "How Lex Happened" on Every | Famous recorded-at-3am launch demo. Carries a single mechanic ("type +++") through the whole video. Strong example of one-mechanic-per-video discipline. |
| 14 | **Cal.com — feature drops** (`cal.com`, channel `@CalcomInc`) | `cal.com`, YouTube `IcYk8pqO1zs` (2025 demo) | OSS scheduling — videos lean explainer rather than cinematic; useful as a reference for the *informational* end of the spectrum. |
| 15 | **Loops — product reels** (`loops.so`) | `loops.so`, Product Hunt | I could not verify a canonical launch video URL. The on-site product reels are short, square-ish, silent; treat as a reference rather than a verified exemplar. |

Cases where I could **not** verify a specific claim from the prompt:
- "Linear cycles launch video" — cycles is core to Linear but I did not find a dedicated launch video for that specific feature.
- A single "Stripe Atlas + Radar" launch video — Atlas and Radar appear to have separate marketing artifacts.
- Loops launch video — exists conceptually, but I did not surface a canonical URL.

---

## 2. Structural patterns — what good videos do

### Hook timing
The value prop should land **by 0:03**. LinkedIn's mobile and desktop autoplay both kick off muted, and the platform's own creative guidance says you have ~3 seconds before the user keeps scrolling; X/Twitter behaves the same way on autoplay. Animoto and the broader "3-second rule" literature (Brandefy, Opus, MarketingBlocks) all converge on the same number. Cursor's homepage reels and Linear's per-feature pages both put the new capability on screen *as the first frame*, not after a brand bumper.

**Anti-pattern (well documented):** drawn-out logo intros and slow B-roll openers — multiple guides explicitly call these out as "skip buttons."

### Beat structure (typical breakdowns)

**15s — single-mechanic teaser, near-always silent autoplay.**
- 0.0–0.5s: end-state visual (the "after" — the dashboard, the populated calendar, the cleaned inbox)
- 0.5–3.0s: title card or caption naming the capability
- 3.0–11.0s: the mechanic in action — one cursor path, one or two zooms
- 11.0–15.0s: end card (URL, one CTA verb)

**30s — the dominant length for hero / launch clips.** This is the one most worth templating; full reusable template in §8.
- 0.0–3.0s: hook / value prop visible
- 3.0–8.0s: setup (problem framing — often the "before" UI state)
- 8.0–22.0s: mechanic — 2–3 actions, each its own beat
- 22.0–27.0s: result / payoff state
- 27.0–30.0s: end card hold

**60s — feature-level walkthrough, often with VO or music swell.**
- 0.0–3.0s: hook
- 3.0–15.0s: context / problem
- 15.0–45.0s: 3–4 capability beats, each ~8–10s, with a clear connector
- 45.0–55.0s: the bigger payoff (multi-step, integrated outcome)
- 55.0–60.0s: end card

### End-card pattern
Across Linear, Vercel, Stripe, Figma, Cursor, the convention is consistent enough to standardize:
- **Brand mark** (top-left or center, never animated dramatically at this stage)
- **One-line headline** stating what shipped (e.g. "Insights — now in beta")
- **One verb-led CTA** ("Try it", "Start free", "Read the post", "Available today")
- **URL** in plain typography below or beside the CTA
- **Hold time: 3–5 seconds.** The standard guidance (Vidyard, Lemonlight, Gumlet) is 5–10s for end-screen CTAs on long-form, but on a 30s social cut you compress this to 3–5s — long enough to read, not long enough to bore.

Optional: pricing call-out on end card. Stripe sometimes does this; Linear and Cursor generally don't. **Default to no pricing on the end card** unless price *is* the news.

### Pacing (average shot length, motion intensity)
The cinematic norm is now ~2.5s average shot length (vs ~12s in the 1930s; per Peachpit / VashiVisuals). For 30-second product demos in this category, the working rule is:
- **Average beat ~3–4 seconds** of held screen time per "thing the viewer needs to absorb"
- **Internal motion** (cursor moves, content populating) inside each held beat — so you're not literally hard-cutting every 2.5s, but the *meaningful* event rate is on that order
- Accelerate through middle beats (the demonstration), decelerate on the payoff and the end card

Replit's "Vibe Code Videos" post (their internal motion-design playbook) is a useful primary source on this if the team wants to go deeper.

### Length norms by channel
- **X/Twitter autoplay (silent-friendly):** 15–45s, 16:9 or 1:1, captions on, hook by 0:03
- **LinkedIn feed:** under 30s preferred, 1:1 strongly favored for organic per LinkedIn's own guidance, captions mandatory, autoplay-muted
- **Marketing-site hero (embedded, often loops):** 8–25s, no audio (page audio is jarring), no end card (the page is the CTA), often muted GIF/MP4 loop on `<video autoplay muted loop playsinline>`
- **YouTube (channel page / Shorts):** 30–90s for feature demos; 60s+ benefits from VO
- **Product Hunt:** 30–60s, 16:9, often the same cut as the X launch reel

---

## 3. Visual / framing patterns

### Real product UI vs stylized mockup
- **Use real UI when** the product has visual polish at small sizes (Linear, Cursor, Granola, Notion Calendar). The credibility win > mockup flexibility.
- **Use stylized mockup when** real UI is dense, info-heavy at small sizes, or pre-launch (e.g. the product is mid-redesign). Vercel often shows "browser-mockup" framing rather than literal Vercel dashboard chrome — it lets them swap in the customer story.
- **Mid-ground:** real UI with the chrome cropped out, on a brand-color or gradient backdrop. This is Cursor's homepage approach (UI "over a subtle, solid brand background") and is usually the right default — keeps credibility, kills empty space.

### Cursor / zoom focus techniques
- **Synthetic cursor moves**: ScreenStudio (and now Rapidemo, Tella, Arcade) auto-smooth cursor paths and add inertia. Use synthetic cursor any time the video is for marketing rather than tutorial; raw cursors look amateur.
- **Zoom-into-detail beats**: 1.0x → 1.4–1.8x zoom on the moment of interaction, held for ~1.5s, then zoom back out. ScreenStudio does this automatically on click. Don't over-zoom — past 2.0x you lose the surrounding context.
- **Keystroke HUD overlays**: Raycast videos use these. Useful when the *shortcut itself* is the news. Skip if the action is mouse-only.

### Aspect ratios and safe areas
- **16:9** — site hero embed, YouTube, X landscape autoplay. Use when the UI is genuinely wide (IDE, dashboard, calendar grid).
- **1:1** — single best ratio for LinkedIn organic and X feed mobile. Crop the UI tighter; you'll lose horizontal chrome.
- **9:16** — only when targeting Reels/Shorts/TikTok or a paid-social vertical placement. Most B2B dev-tool launches don't live here.
- **The cross-platform tax:** good shops master one ratio (usually 16:9), then reframe to 1:1 by cropping side chrome rather than letterboxing. Letterboxed bars in 1:1 are the single most common "lazy reframe" tell.

### On-screen text / captions — typography norms
This is where the user's "text too small" pain point lives. Concrete numbers:
- **Caption font size:** ~36–48px at 1080p (call it ~3–4.5% of frame height). Smaller than that is unreadable on a phone in a feed.
- **Caption width:** ≤42 characters per line (LinkedIn's own ad-creative guidance), ideally 1–2 lines maximum on screen at once.
- **Contrast:** white on black scrim, or black on white scrim. Don't use semi-transparent overlays without a backing — feed compression eats them.
- **Hold time:** every caption needs to be on screen for at least the time required to read it twice. Rule of thumb: ~1 second per 3 words, minimum 2 seconds even for short captions.
- **Animation:** ~0.2–0.3s fade-in or slide-up; avoid slower because feed thumbnails preview the static start frame and a half-faded caption looks broken.
- **Position:** keep captions out of the bottom 12% of the frame on social platforms (UI overlays — like time stamps, captions toggles, profile pills — eat that strip).

### Negative space — addressing the "dead space" pain point
The default failure mode is an iframe/screenshot floating in 60% of the frame with brand-color emptiness around it. Three things good shops do instead:
1. **Crop hard.** Linear, Cursor, Granola all crop deeper into the UI than feels natural. If a panel isn't load-bearing for the beat, it's gone.
2. **Stack content into the negative space.** Captions, label callouts, before/after split, a small secondary UI element (e.g. the keyboard shortcut HUD).
3. **Push the UI to fill 80–90% of the frame.** Reserve the remaining 10–20% as deliberate breathing room around captions and the end-card mark — not as accidental padding.

A simple test: if you screenshotted any frame and removed the UI, would the remaining composition still feel intentional? If you'd be left with 50% empty brand color, the framing's wrong.

### Scaling UI to fill frame vs leaving chrome
- **Crop chrome (window bar, sidebar, browser toolbar) when** it's not part of the message. Almost always for marketing.
- **Keep chrome when** the chrome itself is the value prop ("now lives in your menu bar", "command-palette anywhere") — Notion Calendar's menu-bar shots, Raycast's launcher.

---

## 4. Audio patterns

### Silent vs music vs VO vs music+VO

| Channel / context | Default audio approach |
|---|---|
| Site-hero embed loop | **Silent.** Page has its own audio context. |
| X/LinkedIn autoplay | **Silent-first** with captions. Add light music for sound-on viewers as a bonus, never as a dependency. |
| Product Hunt / launch reel | **Music + captions.** No VO unless founder cred is itself the message. |
| YouTube long-form / keynote cut-down | **VO + music bed.** |
| Tutorial / docs walkthrough | **VO only**, music optional and quiet. |

### Music characteristics for productivity software
The dominant template across this category is: minimal-electronic / lo-fi-with-pulse / muted-pop instrumental. Common attributes:
- **BPM ~90–120** for a steady "things are moving" feel without urgency
- **Sparse arrangement** in the first 3 seconds (don't fight the hook), build over the middle, resolve into the end card
- **No vocals, no lyrics** — they fight on-screen text
- **Energy curve:** flat → rising at ~30% mark → peak at the payoff beat → resolve under end card

### Audio levels — music duck under VO
Standard broadcast convention applies:
- **Music bed alone:** -14 to -16 LUFS (loudness)
- **Music ducked under VO:** drop ~10–12 dB (so music lives at ~-24 LUFS while VO sits at ~-14 LUFS)
- **VO target:** -14 to -16 LUFS integrated, peaks not above -1 dBFS

(These are widely used streaming/social loudness norms; specific platforms — YouTube, TikTok — normalize on top, but mastering near these values keeps the post-normalization result intact.)

### SFX usage
- **Add when** the SFX *replaces* a caption (a short, click-like sound on the moment a feature triggers, instead of a "Click" caption).
- **Skip when** the video is busy with motion already — UI sounds on top of music + cursor moves + zoom = noise.
- **Transition stings** between beats are a tell of overproduced video. Hard cuts beat stings on a 30-second clip.

---

## 5. Copy patterns — text on screen and end-card

### The "Watch this." anti-pattern
"Watch this." / "You won't believe this." / "New thing 👀" — vague meta copy that doesn't tell the viewer what they're looking at — kills hook performance. The viewer's brain is *already* deciding whether to watch; meta-prompts to watch don't add information.

**Replace with concrete patterns:**

1. **Name the capability outright.** "Insights now segments by team." "Drag a note onto a calendar event." "Composer agents run end-to-end." This is Linear's, Cursor's, and Granola's house style.
2. **Before/after framing.** "Used to take 6 clicks. Now it's one." Works because the second clause delivers the value frame *and* sets up what to look for in the demo.
3. **"X without Y" dichotomies.** "Email without the inbox." "Calendars without the chrome." "AI without the prompt-engineering." Carries an implied competitor without naming one.
4. **Outcome-led number.** "Onboard a customer in 90 seconds." "Cut the deploy from 4 minutes to 30 seconds." Specific number > vague faster.

### End-card CTA copy
- **One verb.** "Try Insights." "Start with Granola." "Deploy it." "Read the changelog."
- **Length:** 2–4 words for the CTA itself. URL on its own line.
- **Pricing:** only call out price if free/cheap is the news. Default off.
- **No sentence-case marketing hedge.** Don't write "If you'd like to learn more, please visit…" — every word past 4 hurts.

### Caption synchronization with motion
Captions must appear **with the action they describe**, not before and not after.
- If a button gets clicked at 0:08, the caption "Click to publish" appears at 0:07.9 (just before, fading in over 0.2s) and clears at 0:09.5.
- A caption that pre-states an action 2s before it happens trains viewers to read and then look away. A caption that lags the action is invisible.
- Rule of thumb: **caption fade-in starts within 200ms of the action, fade-out begins as the next action starts.**

---

## 6. Tooling / production

### Screen recording
- **Screen Studio** (macOS, one-time purchase) — *de facto* default for this genre. Auto-zoom on click, smoothed cursor, optional cursor-hide, optional cursor-return-for-loops, normalized voice, transcript-as-subtitles. Cursor, Granola-quality cursor work usually starts here.
- **CleanShot X** — primary alternative; lighter-weight, good for quick clips and GIFs. Click highlights, keystroke overlay, mic + cam.
- **Loom** — record + share + transcribe in one. Best for async / sales / docs use; rarely the master file for a marketing reel.
- **Rapidemo / Tella / Arcade** — newer entrants in the same auto-cinematic space.
- **Custom Playwright recordings** — the Replit "Vibe Code Videos" post advocates scripted browser recordings for repeatability. Worth it when the same UI flow needs to be re-shot every time the design changes.

### Editing
- **Final Cut Pro / Premiere** — default for any reel that mixes screen-rec + VO + music + captions.
- **Screen Studio** itself is enough for ~70% of single-feature reels (it has trimming, captions, music, exports).
- **ffmpeg** — pipeline glue: re-encode to platform-specific codecs, generate 16:9 + 1:1 + 9:16 variants from one master, strip metadata, set faststart for inline web autoplay.
- **Descript** — strong when there's VO + transcript-driven editing; the "edit text → edit video" loop is faster than scrubbing. Good for tutorials, less essential for music-only reels.

### Music sources
- **Epidemic Sound** — most common B2B SaaS choice. "Demos & Testimonials" theme is on-brief for this genre.
- **Artlist** — comparable; tracks tend to lean cinematic.
- **Musicbed / Soundstripe** — higher-end, useful for long-form keynote drops.
- **AI-generated (Stable Audio 2.5 via FAL)** — viable for short cuts, especially when you want a unique cue per launch. Stable Audio 2.5 generates up to 3-min tracks in seconds at $0.20/track on FAL. Quality is genre-dependent — atmospheric/ambient is strong, complex arrangements less so. Use for hero loops on the marketing site; replace with licensed track for paid placements.

### Export specs
- **Master:** ProRes 422 or H.264 high-profile, 1080p (or 1440p for site hero), 60fps, full color.
- **X / LinkedIn delivery:** H.264, 1080p at 30fps (60fps gets normalized), 8–10 Mbps bitrate, AAC audio at 128–192 kbps. MP4 container.
- **Site hero loop:** H.264 + WebM (VP9) for browser fallback, 1080p, no audio track at all (some browsers silently fail on autoplay-muted with audio track present), faststart enabled. Aim ~2–4 MB for an 8–15s loop.
- **Frame rate:** 30 or 60. Don't ship 24 — UI animations interpolate poorly.
- **Captions:** ship a separate `.srt`/`.vtt` *and* burn captions into the video. LinkedIn shows uploaded SRT, but the burned version is what survives reposts and screen-recordings.

---

## 7. Pre-publish checklist (~15 binary items)

This is the gate the skill should enforce before the video ships.

1. [ ] Value prop is visible on screen by 0:03 (no logo/bumper before the hook).
2. [ ] First frame is interesting alone — would work as the autoplay-paused thumbnail.
3. [ ] Title/caption copy names the capability, not "Watch this." or similar meta copy.
4. [ ] Captions are ≥3% of frame height (~36px+ at 1080p), with backing scrim or solid contrast.
5. [ ] Captions sync to the action within ±300ms; no caption lingers after its action ends.
6. [ ] Video plays meaningfully with sound off (test by muting and watching once).
7. [ ] No audio track at all on the site-hero loop file (or muted-by-default and user-toggleable).
8. [ ] UI fills ≥75% of the frame area; no >25% expanses of empty brand color.
9. [ ] Cursor moves are smoothed (synthetic, not raw); zooms held ≥1.0s on the moment.
10. [ ] One mechanic per video (don't try to teach two things in 30 seconds).
11. [ ] End-card has: brand mark + one-line headline + one verb-led CTA + URL + 3–5s hold.
12. [ ] No pricing in the end card unless price *is* the news.
13. [ ] Aspect-ratio variants exist for the platforms it'll ship on (16:9 master + 1:1 reframe for LinkedIn/X feed at minimum).
14. [ ] Bottom 12% of frame is clear of important content (platform UI overlays).
15. [ ] Export is H.264 MP4, 1080p, faststart enabled, captions burned in.

---

## 8. Reusable beat template — 20–30s site-hero / launch clip

Total runtime: 28 seconds. Designed for silent autoplay on X, LinkedIn, and embed-on-marketing-site with the same master.

```
TIME    BEAT                        VISUAL                                  COPY (on-screen)
────────────────────────────────────────────────────────────────────────────────────────
0:00.0  Cold open — payoff state    [Final state of the feature, full bleed,  —
        (no logo, no bumper)        cropped tight, ~85% of frame]

0:00.5  Hook caption fades in       [Same shot, caption appears upper-third]  "<Capability> — now in <Product>"
                                                                              e.g. "Segmented dashboards — now in Insights"

0:03.0  Caption fades out           [Tiny dissolve into the "before" state]   —
        (3-second hook lands here)

0:03.5  Setup beat                  [The status-quo UI / problem state]       "Used to mean <pain point>."
                                                                              e.g. "Used to mean exporting to a spreadsheet."

0:07.0  Action beat 1               [First click / keystroke,                 "<Verb the action>"
                                    auto-zoom 1.4x, 1.5s hold]                e.g. "Drop in a query."

0:11.0  Action beat 2               [Second action,                           "<Verb the action>"
                                    smooth cursor path]                       e.g. "Group by team."

0:15.0  Action beat 3               [Third action — small variation]          "<Verb the action>"
                                                                              e.g. "Save to dashboard."

0:19.0  Payoff state                [Wide shot back to full feature,          "<Outcome in concrete terms>"
                                    populated with results, decel]            e.g. "Live for the whole team. No spreadsheet."

0:23.5  End card transition         [Fade through to brand backdrop]          —

0:24.0  End card hold               [Brand mark + headline + CTA + URL]       <Brand mark>
                                                                              "<Capability> is live."
                                                                              <CTA verb> · <URL>

0:28.0  End                         [Cut]                                     —
```

**Placeholder copy slots to fill before recording:**
- `<Product>` — your product name
- `<Capability>` — the feature, in customer language
- `<pain point>` — the status-quo problem in 4–6 words
- `<Verb the action>` — imperative verb + object, ≤4 words
- `<Outcome in concrete terms>` — number / time / removed-step language preferred
- `<CTA verb>` — single verb: "Try", "Start", "Read", "Deploy"
- `<URL>` — short URL, ideally a vanity path (`/<feature>`)

**Audio:** music-bed only (no VO), -14 LUFS, sparse 0–3s, build to 0:19 payoff, decay under end card. Stable Audio 2.5 prompt for the placeholder cue: "minimal electronic, 100 BPM, no drums first 3s, soft synth pad, builds at 60% with light percussion, resolves at 0:24, no vocals."

**Captions:** burn-in, ≥36px @1080p, white-on-black scrim 80% opacity, fade 0.2s in / 0.2s out, sync within 200ms of action.

**Exports needed:** 1080p H.264 16:9 (X/site hero), 1080p H.264 1:1 (LinkedIn — reframe by cropping side chrome, not letterboxing), optional 1080×1920 9:16 if a vertical placement is in plan.

---

## Sources

Verified live or via web search during this research:

- [Linear Insights — changelog](https://linear.app/changelog/2023-03-23-linear-insights)
- [Linear Insights — feature page](https://linear.app/insights)
- [Granola homepage](https://www.granola.ai/)
- [Cursor homepage](https://cursor.com/)
- [Raycast homepage](https://www.raycast.com/)
- [Vercel — Recap: Next.js Conf 2024](https://vercel.com/blog/recap-next-js-conf-2024)
- [Notion — Introducing Notion Calendar](https://www.notion.com/blog/introducing-notion-calendar)
- [Notion Calendar tutorial — YouTube](https://www.youtube.com/watch?v=TNVXuVxRa8k)
- [Arc Browser intro — YouTube](https://www.youtube.com/watch?v=QsCNcqdHVrc)
- [Arc Act II — YouTube](https://www.youtube.com/watch?v=WIeJF3kL5ng)
- [Replit Agent 4 launch — YouTube](https://www.youtube.com/watch?v=-2xHmkpmCBM)
- [Replit — Vibe Code Videos in Replit](https://blog.replit.com/vibe-code-videos-in-replit)
- [Figma Config 2024 keynote — YouTube](https://www.youtube.com/watch?v=n5gJgkO2Dg0)
- [Superhuman YouTube channel](https://www.youtube.com/@SuperhumanCo)
- [Lex — How Lex Happened (Every)](https://every.to/divinations/how-lex-happened)
- [Cal.com tutorial 2025 — YouTube](https://www.youtube.com/watch?v=IcYk8pqO1zs)
- [Screen Studio](https://screen.studio/)
- [CleanShot X — features](https://cleanshot.com/features)
- [Stable Audio 2.5 on FAL](https://blog.fal.ai/stable-audio-2-5-now-available-on-fal/)
- [Loom — 7 Tips for Impactful Product Launch Videos](https://www.loom.com/blog/product-launch-video)
- [LinkedIn video caption best practices (Opus)](https://www.opus.pro/blog/linkedin-video-caption-subtitle-best-practices)
- [Animoto — Why First 3 Seconds Matter](https://animoto.com/blog/video-marketing/why-first-3-seconds-matter)
- [Vidyard — End Video with Strong CTA](https://www.vidyard.com/blog/end-video-strong-call-action-examples/)
- [Peachpit — Pacing for Video Editors (shot length data)](https://www.peachpit.com/articles/article.aspx?p=2233986&seqNum=3)
- [Synthesia — Video Aspect Ratios guide](https://www.synthesia.io/post/video-aspect-ratio)
- [Epidemic Sound — Demos & Testimonials theme](https://www.epidemicsound.com/music/themes/corporate/demos-testimonials/)
