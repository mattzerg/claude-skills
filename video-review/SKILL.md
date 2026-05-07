---
name: video-review
description: Pre-flight critique for short product launch / demo videos. Runs structured checks against the techniques.md + pm_tools_density.md catalogs (~/.claude/skills/product-video-skill/) and emits failure findings with concrete fix recipes BEFORE shipping. Catches v11/v12/v13-style regressions: zoompan jitter, hook timing, missing music-out + logo silence, off-brand bookends, low interaction density, format/codec specs. Sibling to product-video-skill (which builds videos); this one reviews them. USE PROACTIVELY before showing any product video to Matt or shipping externally.
allowed-tools: Bash, Read, Write
---

# Video Review Skill — Pre-Flight Critique

A structured critique pass against any draft product video. Runs deterministic checks (format, duration, cut cadence, music-out, silence-on-logo, motion jitter) and prints a human-judgment checklist for items the algorithm can't decide.

Modeled after `fakematt-feedback` (UX/product critique) but specialized for video. Reads from the same catalog as `product-video-skill`:

- `~/.claude/skills/product-video-skill/techniques.md` — frame-by-frame measurements from 10 launch videos (Linear, Cursor, Stripe, Notion, Replit, Figma, etc.)
- `~/.claude/skills/product-video-skill/pm_tools_density.md` — interaction-density measurements from 10 PM-tool demos (Asana, monday, Height, etc.)

## When to invoke

- **Before showing any draft product video to Matt** (this is the primary use)
- Before shipping a video externally to Slack / blog / Twitter / LinkedIn
- After re-rendering a video to verify the changes didn't introduce regressions
- Manual self-review during iteration

## Usage

```bash
python3 ~/.claude/skills/video-review/run.py <video.mp4> [--storyboard storyboard.md]
```

## What it checks

### Auto checks (deterministic, no human required)

| # | Check | Pass criteria | Source |
|---|---|---|---|
| 1 | Codec | H.264 (h264) | Standard for web/social |
| 2 | Resolution | ≥1080p | techniques.md export specs |
| 3 | Frame rate | 30 or 60 fps (not 24) | techniques.md export specs |
| 4 | Faststart | moov atom before mdat | Web autoplay requirement |
| 5 | Duration | 8–90s | techniques.md §1 reference range |
| 6 | Cut cadence (MSL) | 2–6s for title-card-driven, 3–4s for UI demos | techniques.md §3 |
| 7 | Hook timing | First non-brand frame ≤ 0:03 | techniques.md (3-second rule) |
| 8 | End-card silence | ≥1s of audio silence in last 3s | techniques.md §6 — most consistent technique across the dataset |
| 9 | Motion jitter | Frame-to-frame pixel oscillation < jitter threshold (catches zoompan shake) | Failure mode in v11/v12/v13 |
| 10 | End card hold | Last static segment ≥ 2.5s | techniques.md §6 (Linear: 4s, Stripe: 1.2s; midpoint 2.5) |

### Human-judgment checklist

Printed for the operator to confirm before shipping (yes/no per item):

1. Value prop visible by 0:03 (caption or branded title card)
2. First frame interesting alone (works as autoplay-paused thumbnail)
3. Title copy is concrete (NOT "Watch this." / "👀" / vague meta)
4. Captions readable on a phone (≥36px equivalent, scrimmed)
5. Captions sync to action within ±300ms
6. Plays meaningfully with sound off
7. UI fills ≥75% of frame (no >25% empty brand-color expanses)
8. Cursor moves smoothed; zooms held ≥1.0s on the moment
9. ONE mechanic per video — OR if multi-mechanic, density ≥0.4 events/sec on demo content
10. End card has: brand mark + headline + verb-led CTA + URL + 3–6s hold
11. Bookends carry brand identity (NOT Linear-clone mono caps as bookends)
12. No pricing in end card unless price IS the news
13. Bottom 12% of frame clear of important content
14. Music drops out before logo (silence on logo card)
15. Aspect-ratio variants exist for planned channels

### Output

Writes a structured Markdown report to `/tmp/video-review/<video-slug>-<timestamp>.md`:

```
# Video Review: <slug>
<auto check results — pass/fail per item with measured value>
<human checklist for operator>
<concrete fix recipes for each failure, citing the catalog rule that diagnosed it>
```

Exits non-zero if any auto check fails.

## What this skill is NOT

- Not a video editor — it doesn't fix issues, only diagnoses them
- Not a generator — use product-video-skill to build videos
- Not a perceptual-quality estimator (no PSNR / SSIM analysis); structural only
- Not a brand-style auditor (no color-palette match against brand spec — that's a v2 add)
