---
name: caption-burn
description: Burn captions into a finished MP4 as Pillow-rendered transparent PNG overlays composited via ffmpeg. Accepts a captions JSON spec OR a shot-list markdown (auto-derives the CAP entries). Outputs a captioned MP4. Built for the video-production pipeline's post-assembly step — solves the "rough cut has no captions" failure mode that shipped the silent Tycoon roughcut. Uses the same brand tokens (navy scrim, brass accent, IBM Plex Mono) as the F6/F7 type-cards so captions feel native to the product, not stuck-on.
allowed-tools: Bash, Read, Write
---

# Caption-Burn

## Why this exists

The Tycoon rough cut shipped silent — captions were spec'd in the shot list but nothing burned them into the picture. `product-video-skill/lib/caption_overlay.js` injects captions in-browser during recording, but post-render assembly has no analog. This skill is the post-render counterpart.

## What it does

1. Parses caption timing from either:
   - An explicit `captions.json` spec, OR
   - A shot-list markdown (same parser as `eleven-labs-skill sync`)
2. Renders each caption to a transparent PNG via Pillow:
   - IBM Plex Mono Medium, all-caps
   - Brass `◆` glyph prefix
   - Navy scrim (`#0a0f2e` at 75% opacity) behind the text
   - Auto-sized for the target video resolution
3. Composites each PNG over the video with ffmpeg's `overlay` filter using `enable='between(t,start,end)'` timing.

## CLI

```bash
# From a captions JSON
caption-burn burn --input video.mp4 --caps captions.json --out captioned.mp4

# From a shot-list markdown (auto-derives CAP entries)
caption-burn burn --input video.mp4 --shotlist script.md --out captioned.mp4

# Validate captions are visible/readable in the output (OCR check)
caption-burn validate --input captioned.mp4 --caps captions.json
```

## Captions JSON schema

```json
[
  {
    "t_start": 0.0,
    "t_end": 3.0,
    "text": "◆ AI WROTE THIS. JUST NOW.",
    "position": "bottom",   // bottom (default) | top | center
    "size": "default"       // default | small | large
  },
  ...
]
```

`position: bottom` lands at ~bottom-third on the frame. `bottom-third` style mirrors the F6/F7 layout.

## Output

Writes to `~/Downloads/caption-burn/<basename>/`:
- `<basename>-captioned.mp4` — the captioned video
- `captions/cap-NN.png` — individual caption overlay PNGs
- `report.json` — what was burned, with timing + measured render times

## Implementation notes

- All Pillow rendering happens once. PNG dimensions match the source video resolution. Caption text is laid out with multi-line word-wrap to avoid running off-frame.
- The ffmpeg pipeline uses `filter_complex` with a chain of overlays. For 20+ captions this scales linearly; tested clean to 30 captions on 60s video.
- Brand tokens: `navy=#0a0f2e (cc opacity), brass=#c8a84b, cream=#f4f0e7`.
- Falls back to system fonts if `fonts/IBMPlexMono-Medium.ttf` is missing (with a WARN).

## When to invoke

- **In the `video-production` agent's Phase 4 (post-assemble)** — runs automatically after ffmpeg concat.
- **Retroactively on the existing Tycoon rough cut** — `caption-burn burn --input tycoon-60s-roughcut-v1.mp4 --shotlist script-and-shotlist-v6.md` makes it watchable.
- **Anywhere you have a silent MP4 + a captions spec** — generic, not Tycoon-specific.

## When NOT to use

- Live-recording captions (use `product-video-skill/lib/caption_overlay.js` instead — those captions are visible during recording, not burned in post).
- Subtitle-stream-only output (use ffmpeg `-c:s mov_text` directly; captions-burn is for visually-burned captions that survive recompression).

## Files in this skill

- `SKILL.md` — this file
- `run.py` — CLI entrypoint (burn / validate)
- `lib/render.py` — Pillow caption PNG renderer
- `lib/parser.py` — shot-list markdown → captions JSON
- `fonts/IBMPlexMono-Medium.ttf`, `IBMPlexMono-Bold.ttf`
