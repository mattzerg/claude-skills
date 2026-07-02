---
name: chatgpt-image-skill
description: Generate images using OpenAI's gpt-image-1 model (the API equivalent of ChatGPT's Image 2.0). Use as the primary AI image generator for Zerg blog hero/concept work — Idan's stated preference. Falls back to nano-banana-pro / fal-image-skill / Pollinations when OpenAI rate-limits or the key is missing.
allowed-tools: Bash, Read, Write
---


# ChatGPT Image (gpt-image-1)

Single-image AI generation via OpenAI. Sibling of `nano-banana-pro`. Used as primary provider in `blog-imagery` for concept/narrative posts where AI imagery (vs coded SVG diagrams) is the right tool.

## When to use

- Concept / vision / narrative blog posts (no body diagrams) where AI imagery is the right fit
- One-off hero images Idan or Matt asks for outside of the blog pipeline
- When a coded SVG isn't a fit (the post isn't about numbers/process/comparison)

## When NOT to use

- Technical posts with body SVG diagrams. Use coded SVG templates for hero + social so the campaign reads as one brand. (See `feedback_blog_imagery_coherence.md`.)
- Logo / mark / brand asset work. AI gen is unreliable for brand marks.
- Photographs of real people or real products.

## Setup

```bash
# Save OpenAI API key to macOS Keychain (one-time)
security add-generic-password -a "$USER" -s OPENAI_API_KEY -w "sk-..."
```

The skill loads the key from Keychain automatically, or `OPENAI_API_KEY` env var if set.

## Usage

```bash
python3 ~/.claude/skills/chatgpt-image-skill/generate_image.py "your prompt here" [options]
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--size` | `1024x1024`, `1024x1536` (portrait), `1536x1024` (landscape), or `auto` | `auto` |
| `--quality` | `low`, `medium`, `high`, or `auto` | `auto` |
| `--output` | Output PNG path | `./generated_images/<slug>.png` |
| `--n` | Number of variations | `1` |

Note: `gpt-image-1` only supports those three sizes. For 1200×630 (OG card) or 1200×1200 (LinkedIn) or 1200×675 (X), generate at the closest aspect (`1536x1024` for landscape, `1024x1024` for square) and resize after — or just use coded SVGs for those formats.

## Cost (as of 2026-05)

- Low quality: ~$0.011 / image (1024×1024)
- Medium quality: ~$0.042 / image (1024×1024)
- High quality: ~$0.167 / image (1024×1024)
- Larger sizes scale proportionally.

Default is `auto` which usually lands on medium. Set `--quality low` for drafts/exploration.

## Brand prompt prefix

These get prepended automatically when invoked from `blog-imagery`:

> Dark navy background (#07111E), restrained data-forward composition, electric blue and warm amber accent colors, system sans typography if any text, abstract conceptual (NOT photorealistic), no embedded text/logos/Zerg marks, safe area in centered 80% of frame.

For one-off generation, pass `--no-brand-prefix` to skip.

## Provider chain integration

`blog-imagery` calls providers in this order for AI image work (skip Tier 1 = SVG templates if not applicable):

1. **chatgpt-image-skill (gpt-image-1)** — primary, Idan's stated preference
2. **nano-banana-pro (Gemini 3 Pro Image)** — fallback if OpenAI rate-limits or fails
3. **fal-image-skill (Flux Pro)** — secondary fallback
4. **Pollinations** — last-resort free fallback

Never auto-posts. Writes asset files only.
