---
name: brand-illustration
description: Brand-aware illustration scaffolder + generator. Loads presets from `brands.json` (matteisn / vang-capital / vang-advisory / zerg-default / zerg-dark), assembles prompt with palette + typography + voice-tells + anti-patterns, dispatches to chatgpt-image / nano-banana / fal-image, auto-runs `graphic-layout review`. Three modes — `list`, `prompt`, `generate`. Different from raw image-gen skills (no brand context). USE PROACTIVELY for branded illustration — never call raw image-gen for branded work.
allowed-tools: Bash, Read, Write
---

# Brand Illustration Skill

The "I need a custom illustration for X" entry point. Solves the gap surfaced 2026-05-08 when Matt asked for "more eye-catching" lifts and the only options were raw image-gen calls (no brand context) or hand-written prompts (reinvent each time).

## Anchors

This skill draws its voice and pattern catalog from:

- **Voice fingerprint:** `/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg/_style/matt_considered_voice.md`
- **Pattern catalog:** `/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg/_style/feedback_patterns_catalog.md`
- **Domain corpus:** `/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg/_style/brand_feedback_corpus.md`
- **Catalog patterns to cite by slug** (Section C Prose / writing): pulp-caption-discipline
- **Catalog patterns to cite by slug** (Section F Brand): brand-color-restraint, brand-token-codemod
- **Catalog patterns to cite by slug** (Section G Viz / video): annotation-near-the-point, data-density, color-encoding-discipline

Read these BEFORE producing output. Cite patterns by slug from the catalog.

## Why this exists

Three image-gen skills already exist (`chatgpt-image-skill`, `nano-banana-pro`, `fal-image-skill`) — all brand-agnostic. For Matt's branded surfaces (matteisn / vang / zerg) every prompt should carry brand DNA: palette, typography, voice-tells, anti-patterns. This skill assembles that layer once, routes to the right backend, and auto-reviews via graphic-layout.

## Modes

### `list`
```bash
python3 ~/.claude/skills/brand-illustration/run.py list
```
Shows available brand presets and their site / register.

### `prompt` (dry-run, no API call)
```bash
python3 ~/.claude/skills/brand-illustration/run.py prompt \
  --brand matteisn \
  --intent "hero illustration of a sailing vang rope"
```
Prints the assembled brand-aware prompt without spending tokens. **Use this first** to review what's going to the backend — cheaper than an iteration round on a bad prompt.

### `generate`
```bash
python3 ~/.claude/skills/brand-illustration/run.py generate \
  --brand vang-capital \
  --intent "abstract geometric mark — sailing rope under tension forming a triangle" \
  --aspect 16:9 \
  --backend fal \
  --output ~/vang-capital-site/assets/illustrations/hero.png
```
Builds the prompt → invokes the chosen backend → writes to disk → auto-runs `graphic-layout review` (skip with `--skip-review`).

If `--output` is omitted, defaults to `<brand-asset_path>/<slugified-intent>.png`. So `--brand matteisn --intent "sailing rope"` writes to `~/matteisn-site/assets/illustrations/sailing-rope.png`.

`--aspect` accepts: `1:1` / `square` / `portrait` / `9:16` / `16:9` / `landscape` / `hero` / `og`. Defaults to `16:9` (hero).

`--dry-run` prints the prompt + the backend invocation without calling. Last-minute review.

## Backend routing — current reliability (2026-05-09)

| Backend | Status | Notes |
|---|---|---|
| **fal** (Flux Pro) | ✅ **most reliable, default this in practice** | Verified working 2026-05-09 with matteisn vang-rope test |
| chatgpt-image-skill | ⚠️ **routinely billing-limit-blocked** | Idan's preferred per memory, but OpenAI hard-limits hit often. Verify availability before relying on it. |
| nano-banana-pro | ⚠️ **Gemini free tier `limit: 0`** | Usually 429 RESOURCE_EXHAUSTED. Don't reach for it without a paid Gemini account. |

**In practice, default to `--backend fal`** until OpenAI/Gemini quotas restore. The skill's nominal default is `chatgpt` (matches Idan's stated preference), but if the request is time-sensitive, just route to fal directly.

## Brand presets (in `brands.json`)

| Key | Site | Register | Palette signature |
|---|---|---|---|
| `matteisn` | matteisn.com | editorial-personal | navy + teal, near-white paper, Fraunces |
| `vang-capital` | vang.capital | fund / pre-seed VC | navy + purple gradient, geometric / sailing-rope, Montserrat |
| `vang-advisory` | vangadvisory.com | consultancy / advisory | same Vang language as vang-capital, more diagrammatic |
| `zerg-default` | zergai.com | Zstack / non-tech | cream paper, charcoal, burnt-orange + green, Space Grotesk |
| `zerg-dark` | zergai.com | Zerg-parent / heavy-tech | charcoal paper, cream foreground, brighter burnt-orange |

Each preset carries: palette tokens, typography refs, voice-tells (4-6 brand statements), anti-patterns (what NOT to draw), `asset_path` (where output goes by default), `style_guidance` (free-form direction).

## Workflow

```
1. Matt: "draft an illustration for matteisn — vang sailing-rope theme"
2. brand-illustration prompt --brand matteisn --intent "..."         # preview the prompt
3. brand-illustration generate --brand matteisn --intent "..." --backend fal --aspect 16:9
   ↳ saves PNG to ~/matteisn-site/assets/illustrations/...
   ↳ auto-runs graphic-layout review (target-kind=hero by default)
4. (optional) webpage-layout/recipes/visual-richness.md → swap into a hero R3 / R5 / standalone <figure>
```

## Refining a brand preset

`brands.json` evolves with feedback. When Matt corrects "no, that's not Vang feel — too consumer," capture by:
1. Adding to the brand's `anti_patterns` list
2. (optional) Tightening `style_guidance`
3. (optional) Adding voice-tells
Re-run `prompt` to verify before generating again.

## Pairs with

- `chatgpt-image-skill` / `nano-banana-pro` / `fal-image-skill` — actual image generation backends
- `graphic-layout` — composition review (auto-runs post-gen unless `--skip-review`)
- `webpage-layout/recipes/visual-richness.md` — when illustration is part of a hero richness lift
- `blog-imagery` — for blog-post hero/body imagery (already brand-context-aware for Zerg blog)

## What this is NOT

- A photography skill (those need real photos, not generation)
- A logo / mark designer (those should be commissioned or vector-edited)
- An animation / motion skill (use product-video-skill or fal-video-skill for video)
- A replacement for the Zerg blog imagery skill (that one carries Zerg-specific layout rules)

## Production reference

The matteisn vang-rope illustration generated 2026-05-09 is shipped at:
- Source PNG: `~/.claude/skills/brand-illustration/test/matteisn-vang-rope.png`
- Optimized JPEG live on matteisn.com: `~/matteisn-site/assets/illustrations/vang-rope.jpg`
- Inspect on the site between the stat-band and the vang-aside

That's a working test case for: brand-aware prompt → fal-image-skill → graphic-layout review → optimize → ship.
