---
name: gif-builder
description: Create small, optimized animated GIFs from brand marks, logos, UI moments, frame sequences, or simple procedural motion. Use for Gmail/profile avatars, social stickers, tiny launch accents, and other lightweight gif-able locations.
---


# GIF Builder

Use this skill when Matt asks for an animated GIF, animated logo, profile image loop, small social animation, or lightweight looping visual.

## Workflow

1. Pick the smallest usable canvas first. For profile/avatar contexts, start with `128x128`; also export `256x256` and a master if useful.
2. Keep motion subtle unless the request asks otherwise. Good defaults: 24-40 frames, 60-90ms per frame, seamless loop, no hard cuts.
3. Build from source/vector brand assets when available. If rasterizing SVG tooling is unavailable, use a deterministic Pillow drawing script for simple marks.
4. Export a still preview PNG and one peak/mid-animation PNG beside the GIF.
5. Validate file type, dimensions, frame count, duration, and file size.
6. Record the asset in the relevant brand/asset catalog when it is part of a kit.

## Quality Bar

- Tiny-size readability matters more than clever motion.
- Avoid spin, bounce, strobe, or heavy gradients for profile images.
- Prefer one subtle behavior: a small sparkle, a gentle status loop, slow glow, or slight opacity warmth.
- For profile/avatar logos, avoid visible bars, ticks, bounce, spin, or geometry shifts unless explicitly requested.
- For Zerg marks, render the actual SVG logo instead of redrawing the logo shape procedurally.
- Keep the 128px variant under ~150 KB when possible.

## Bundled Script

For the current Zerg compact-mark profile loops, run:

```bash
python3 ~/.claude/skills/gif-builder/scripts/build_zerg_logo_gif.py --out-dir MattZerg/Brand/assets/logos/zerg/animated
```

This exports both approved Zerg avatar families:

- `zerg-mark-sparkle-loop-*`
- `zerg-mark-gentle-loop-*`
