---
name: product-video-skill
description: Plan, record, and assemble short (15–60s) software product launch / feature demo videos. Codifies the 15-item pre-publish checklist, beat-template patterns (15s/30s/60s), caption-overlay typography, end-card layout, and ffmpeg assembly pipeline. Reads a JSON storyboard, renders a Markdown brief for human approval, then drives the recording + assembly. USE PROACTIVELY whenever Matt mentions a product video, demo video, launch reel, or sizzle clip — and as a pre-flight on existing video drafts before they ship. Never auto-publishes — writes asset files + a storyboard brief for sign-off.
allowed-tools: Bash, Read, Write, Edit
---

# Product Video Skill

A skill for producing short software product launch / feature demo videos that don't fall into the common failure modes (vague hook copy, dead space, captions too small, drawn-out logo bumpers).

## Doctrine (the things this skill is built to enforce)

1. **Value prop on screen by 0:03.** No logo bumper, no slow B-roll opener. The first frame should work as the autoplay-paused thumbnail.
2. **Concrete copy.** "Watch this." / "You won't believe…" / "New 👀" are anti-patterns. Replace with *capability named outright*, *before/after*, *X without Y*, or *outcome number*.
3. **One mechanic per video.** Two ideas in 30s = neither lands.
4. **Crop hard.** UI fills ≥75% of the frame. Empty brand color is dead space, not breathing room.
5. **Captions are large, contrasted, action-synced.** ≥36px @1080p, scrimmed, ±200ms of the action.
6. **End card is disciplined.** Brand mark + one-line headline + one verb-led CTA + URL, held 3–5s. No pricing unless price is the news.
7. **Silent-first.** The master cut plays meaningfully muted. Sound is bonus, never load-bearing.

## Catalogs (the measured truth — read before iterating)

The skill is anchored on three documents in this directory. Read them BEFORE designing a new video:

1. **`techniques.md`** — frame-by-frame measurements from 10 launch videos (Linear, Cursor, Stripe, Notion Calendar, Replit, Figma, Vercel, Raycast, Lex). Every recipe has measured numbers. §8 has 3 ready-to-execute templates ("Linear Releases mode," "Cursor mode," "Linear Agent mode"). §10 is the recipe priority list.
2. **`pm_tools_density.md`** — interaction-density measurements from 10 PM-tool demos (Asana, monday.com, Height, Linear Insights, ClickUp, Notion, Trello, Coda). §6 has the "v14 interaction packing" recipe. Targets: 0.5 events/sec on demo content, 6+ distinct verb types.
3. **`best-practices.md`** — older general-launch-video research. Superseded by techniques.md; kept for the 15-item pre-publish checklist.

## Library (composable primitives — use these, don't roll your own)

`lib/motion_recipes.py` — measured ffmpeg primitives. Use these instead of writing ad-hoc filters:
- `linear_push_in(scale=1.00→1.04, 2.5s, linear)` — used in 6/10 reference videos. The default UI hold motion.
- `crash_cut_to_title(text, 1.7s)` — Linear-style mono caps for INTERNAL section breaks. NOT bookends.
- `title_card_branded(headline, subtitle, hold=1.5s)` — Zerg-branded opening title card with logo + amber accent. USE FOR BOOKEND OPENERS.
- `logo_card_silence(headline, cta, url, hold=4.0s)` — branded end card paired with music-out. USE FOR BOOKEND CLOSERS.
- `typewriter_punctual(text, 11ch/s, 2Hz blink)` — Linear's signature pre-logo beat.
- `kenburns_macro(scale=1.00→1.10, 3.5s)` — B-roll motion. Min 3.5s or it twitches.
- `mix_music(silent, music, music_out_at_s=duration-3, fade_out=2)` — pairs with `logo_card_silence` so logo holds in silence (most consistent technique across the dataset).

`lib/smooth_record.py` — Playwright helpers for in-browser CSS-driven motion DURING recording. Use these instead of post-production zoompan (which produces visible jitter at slow rates):
- `setup_smooth_record(page)` — call once after page load.
- `smooth_zoom(page, scale=1.04, duration_s=2.5, easing="linear")`
- `smooth_pan_to(page, x_px=-200, duration_s=1.5)`
- `smooth_zoom_pan(page, scale, x, y, duration)`
- Browser compositor handles sub-pixel interpolation — no shake.

`lib/end_card.py` — render branded title or end card PNGs (used by the recipes above).
`lib/caption_overlay.js` — canonical caption styling for in-page captions (only when not using post-production text overlay).
`lib/checklist.py` — 13-item pre-publish gate (subset of the new video-review skill).
`lib/storyboard_schema.json` — JSON schema for storyboards.

## Sibling skill: `video-review`

After ANY new video render, run `~/.claude/skills/video-review/run.py <video.mp4>` BEFORE showing Matt. It runs 10 deterministic auto-checks (codec, fps, faststart, duration, cut cadence, hook timing, end-silence, motion jitter, end-card hold) and prompts the 15-item human checklist. **This is the gate that catches regressions** — v11/v12/v13 would all have flagged structural issues here.

## Failure modes captured in memory

- `feedback_video_motion_pitfalls.md` — three concrete pitfalls from v8–v13 iterations: ffmpeg zoompan creates shake at low rates (use smooth_record instead); title/end cards must carry brand identity (not Linear-clone mono caps); demos need ≥1 UI event per 1.5–2s.
- `feedback_internal_review_pack_format.md` — review pack format for sharing drafts.
- `project_zergboard_video_brief.md` — standing brief for Zergboard demo videos.

## Workflow

### 1. Brief + storyboard

Write a storyboard JSON to `/tmp/<slug>-storyboard.json` matching `lib/storyboard_schema.json`. The schema requires: core message (single sentence), audience, channels, length, tone, beats (timing + visual + on-screen copy + audio direction), end card (mark + headline + CTA + URL).

Render the brief for human approval:

```bash
python3 ~/.claude/skills/product-video-skill/storyboard.py /tmp/<slug>-storyboard.json --out /tmp/<slug>-brief.md
```

The brief is what goes to Matt/Idan for sign-off **before recording**. This is the gate that prevents lazy placeholder copy from shipping.

### 2. Recording

For Playwright-driven product UI recordings, inject `lib/caption_overlay.js` into the page and use the `set_caption(page, text)` helper it exposes. The overlay enforces the canonical typography (40px+, white-on-dark scrim, 0.2s fade in/out, brand-color border accent) so all captions across all videos are visually consistent.

For screen-rec workflows (Screen Studio, CleanShot), captions are added in the editor — apply the same typographic rules listed in `best-practices.md` §3.

### 3. End card

Generate the end-card frame as a still PNG via `lib/end_card.py`:

```bash
python3 ~/.claude/skills/product-video-skill/lib/end_card.py \
  --headline "Zergboard is live." \
  --cta "Try it" \
  --url "zergboard.com" \
  --brand zergboard \
  --aspect 16:9 \
  --out /tmp/end-card.png
```

The end card uses the same dark-mode brand palette as `blog-imagery` SVG templates so videos and blog imagery share visual identity.

### 4. Assembly

Use `lib/assemble.py` (or copy from `/tmp/zb_demo_assemble.py` and adapt). The skill enforces:
- Title and end card with no fade-in (full opacity on first frame)
- Hard cuts between beats (no transition stings) for cuts under 45s
- Music ducked to ~55% (~-12 dB) when present, with 0.5s fade-in / 0.8s fade-out
- Poster grabbed at mid-body (t=4–6s), never inside title or end-card region
- Faststart enabled, captions burned in, H.264 1080p

### 5. Pre-publish check

Run the checklist:

```bash
python3 ~/.claude/skills/product-video-skill/checklist.py /path/to/video.mp4
```

It verifies the verifiable items (duration, codec, faststart, dimensions, end-card hold time via frame analysis) and prints the human-judgement items (hook by 0:03, captions readable, dead space) for the approver to confirm.

## When to invoke

- **Before recording any new product/launch/feature video.** Even a 15s site-hero loop benefits from the storyboard step.
- **As a pre-flight on existing drafts** — drop a video at the skill and run `checklist.py` to see what's wrong.
- **When a video iteration goes wrong** ("text too small", "doesn't say what it is") — the doctrine + checklist diagnose the failure mode and prescribe the fix.

## When NOT to use

- Tutorial / docs walkthrough videos (different genre — VO-led, longer, not optimized for autoplay).
- Customer-story / testimonial videos (different genre — interview-led, narrative).
- Internal Loom screen recordings for async comms.

## Channel variants

The same master cut should ship in multiple aspect ratios. Default reframe rule: **crop side chrome, never letterbox.** A 16:9 master becomes a 1:1 LinkedIn cut by removing horizontal whitespace, not by adding bars.

| Channel | Aspect | Length | Audio | Notes |
|---|---|---|---|---|
| Site hero (embed loop) | 16:9 | 8–25s | none | `<video autoplay muted loop playsinline>`, no audio track at all |
| Twitter/X feed | 16:9 or 1:1 | 15–45s | silent + captions | hook ≤0:03 |
| LinkedIn feed | 1:1 | <30s | silent + captions | LinkedIn favors square |
| YouTube | 16:9 | 30–90s | music or VO | longer ok with VO |
| Product Hunt | 16:9 | 30–60s | music + captions | usually = X cut |

## Files in this skill

- `SKILL.md` — this file
- `best-practices.md` — full research with exemplar catalog (~3000 words). Read once.
- `storyboard.py` — CLI: storyboard JSON → Markdown brief for human review
- `lib/storyboard_schema.json` — JSON schema for the storyboard format
- `lib/caption_overlay.js` — canonical caption styles for Playwright-injected overlays
- `lib/end_card.py` — generate end-card PNG from headline + CTA + URL + brand
- `lib/checklist.py` — 15-item pre-publish gate (auto + human-judgement items)
- `lib/assemble.py` — title + body + end-card + music ffmpeg pipeline
- `templates/storyboard_30s.json` — starter for the dominant length

Sibling to `blog-imagery` (per-post asset bundle) and `landing-page-skill` (page-level design). This skill owns *moving* product narrative; those own *static* product narrative.
