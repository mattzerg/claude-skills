---
name: fal-image-skill
description: Generate images using FAL.ai. Access Flux Pro/Dev/Schnell, Recraft v3, Ideogram v2, SDXL, and SD 3.5 through a single API. Use as the primary backup when nano-banana-pro is rate-limited.
---

# FAL Image Skill

Image generation via FAL.ai. Covers the major hosted models in one place.

## Setup

Reuses the same `FAL_KEY` as `fal-video-skill`. If video is configured, image works automatically.

```bash
python3 ~/.claude/skills/fal-image-skill/fal_image_skill.py config YOUR_API_KEY
# or
export FAL_KEY="your_api_key"
```

Get a key at https://fal.ai/dashboard/keys.

## Commands

### Generate

```bash
python3 ~/.claude/skills/fal-image-skill/fal_image_skill.py gen "PROMPT" [OPTIONS]
```

Options:
- `--model, -m` — model name (default: `flux-pro`)
- `--aspect-ratio, -a` — `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `21:9` (default: `16:9`)
- `--num-images, -n` — how many to generate (default: 1)
- `--negative-prompt` — what to avoid
- `--style` — Recraft/Ideogram style hint
- `--seed` — for reproducibility
- `--output, -o` — output file path (default: `output/image_<model>_<ts>.png`)
- `--timeout, -t` — seconds (default: 180)

Examples:

```bash
# Default (Flux Pro Ultra), 16:9
python3 fal_image_skill.py gen "A cinematic still of a panda eating ramen, 35mm film grain"

# Cheap/fast draft
python3 fal_image_skill.py gen "concept sketch of a cyberpunk city" --model flux-schnell

# Caption that needs to render correctly in-image (Ideogram is best at text)
python3 fal_image_skill.py gen "A motivational poster reading 'SHIP IT'" --model ideogram

# Specific output path
python3 fal_image_skill.py gen "..." -o /path/to/meme_base.jpg
```

### List models

```bash
python3 fal_image_skill.py models
```

### Check / set API key

```bash
python3 fal_image_skill.py config            # show status
python3 fal_image_skill.py config YOUR_KEY   # save key
```

## Model picker

- **`flux-pro`** (default) — Flux Pro 1.1 Ultra. Best photorealism. Use for finished work.
- **`flux-pro-1.1`** — Faster than Ultra, still high quality.
- **`flux-dev`** / **`flux-schnell`** — Cheaper / faster drafts.
- **`flux-realism`** — Realism LoRA tuned for faces/scenes.
- **`recraft`** — Recraft v3. Best for designs, illustrations, brand-style work.
- **`ideogram`** / **`ideogram-turbo`** — Best in-image text rendering. Use when the caption needs to be baked into the image (rare for memes — usually composite captions with PIL instead).
- **`sdxl`** / **`sdxl-lightning`** — Fast SDXL variants.
- **`stable-diffusion-3.5`** — SD 3.5 Large.

## Meme workflow

For the meme archive at `MattZerg/Memes/`:

1. Generate base with **`flux-pro`** and `NO TEXT` in the prompt (diffusion mangles captions).
2. Save to `MattZerg/Memes/sources/<slug>_base.jpg`.
3. Composite the caption with PIL using Impact font + black stroke.
4. Save final to `MattZerg/Memes/<slug>.jpg`.
5. Append entry to `MattZerg/Memes/Memes.md`.

Priority order if generation fails: `nano-banana-pro` → this skill (`flux-pro`) → Pollinations.ai (curl, free fallback).
