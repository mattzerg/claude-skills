---
name: callout-recipes
description: "Apply on-screen callouts (arrows, highlight boxes, label chips, state badges, metric badges) to a video clip via Pillow-rendered PNG overlays composited through ffmpeg. Five canonical recipes spec'd by a JSON callouts file with per-callout timing. Built for the look-here beats in product/demo videos — fixes the failure mode where rough cuts have UI captures but no indication of what the viewer should notice. Brand-aligned — brass arrows on navy translucent backplates, IBM Plex Mono labels."
allowed-tools: Bash, Read, Write
---

# Callout-Recipes

## Why this exists

`product-video-skill/lib/motion_recipes.py` covers timing primitives (push-in, ken burns, title cards) but has no "draw an arrow here" / "highlight this UI element" / "label this state change" capability. Without callouts, demo videos look like documentation screenshots — the viewer can't tell where to look. This skill is the missing primitive.

## Five canonical recipes

1. **`arrow_to`** — draws a brass arrow from a label to a target pixel coordinate. Used for "PLAYER ACTION → click here".
2. **`highlight_box`** — a navy-translucent box outlined in brass around a rectangle. Used for "this panel matters".
3. **`label_chip`** — a small mono-caps chip with brass `◆` glyph, positioned anchored to a target coordinate. Used for "this thing is called X".
4. **`state_badge`** — a top-right or top-left chip showing a state name in brass on navy. Used for "PERIOD 1 IS LIVE" / "GAME OVER".
5. **`metric_badge`** — number + delta indicator (▲ green / ▼ red). Used for "CASH ON HAND: −$177M".

All five share the Tycoon brand palette (navy `#0a0f2e`, brass `#c8a84b`, cream `#e8ecf5`, IBM Plex Mono).

## CLI

```bash
# Apply callouts to a single clip
callout-recipes apply --input clip.mp4 --callouts spec.json --out annotated.mp4

# Show the rendered PNGs without burning to video (debug)
callout-recipes preview --callouts spec.json --w 1920 --h 1080 --out preview_dir/
```

## Callouts JSON schema

```json
[
  {
    "type": "arrow_to",
    "t_start": 0.0,
    "t_end": 3.0,
    "x": 1200, "y": 480,
    "label": "PLAYER ACTION",
    "direction": "from-left",
    "color": "brass"
  },
  {
    "type": "highlight_box",
    "t_start": 4.0,
    "t_end": 7.0,
    "x": 100, "y": 200, "w": 800, "h": 400,
    "pulse": true
  },
  {
    "type": "label_chip",
    "t_start": 2.0,
    "t_end": 5.0,
    "anchor_x": 960, "anchor_y": 540,
    "text": "AGENT CHAIN",
    "position": "above"
  },
  {
    "type": "state_badge",
    "t_start": 0.0,
    "t_end": 60.0,
    "text": "PERIOD 1 · Q1 2007",
    "position": "top-left"
  },
  {
    "type": "metric_badge",
    "t_start": 30.0,
    "t_end": 35.0,
    "label": "CASH ON HAND",
    "value": "−$177,750,000",
    "delta_color": "red",
    "position": "top-right"
  }
]
```

## Implementation notes

- All callouts render once as transparent PNGs (Pillow), then composite via ffmpeg's `overlay` filter with `enable='between(t,start,end)'` timing — same pattern as `caption-burn`.
- The `pulse` option on `highlight_box` adds a 1.5s breathing animation by emitting 30 PNGs at varied opacity and using `overlay` with frame-modulated timing (v2 feature; v1 is static).
- Coordinates are in source-resolution space (e.g., 1920×1080), automatically scaled if the input video is a different resolution.

## When to invoke

- **In the video-production agent's Phase 4 (post-assembly)** — runs after captions are burned, before the final review.
- **Retroactively to add "look here" beats** to an existing video that lacks them.
- **Standalone for one-off callouts** on a single clip.

## Files in this skill

- `SKILL.md` — this file
- `run.py` — CLI entrypoint (apply / preview)
- `lib/recipes.py` — Pillow renderers for the 5 callout types
