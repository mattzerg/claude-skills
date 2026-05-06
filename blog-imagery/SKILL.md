---
name: blog-imagery
description: Generate the full image set for a blog post in one pass — hero (OG card 1200x630), 2+ in-body images/diagrams/tables, plus platform-optimized share variants for Twitter/X (1200x675 16:9) and LinkedIn (1200x1200 square for in-feed engagement). Routes by post type: technical/data posts use coded SVG templates (stat-card, funnel, tree, before-after) so the whole campaign matches the body-diagram visual language; narrative/concept posts use AI image gen (chatgpt-image-skill primary, then nano-banana-pro → fal-image-skill → Pollinations fallback). Writes assets to `~/zerg/web/src/public/images/blog/`. USE PROACTIVELY when Matt drafts a new blog post, when an existing post is missing imagery, or before a launch where social shares matter. Never auto-posts to social — only writes asset files + a Markdown insertion plan.
allowed-tools: Bash, Read, Write, Edit
---

# Blog Imagery Skill

Generate the full image set for a blog post in one orchestrated pass. Sibling to `chatgpt-image-skill` / `nano-banana-pro` / `fal-image-skill` (single-image AI providers) and `landing-page-skill` (page-level design) — this skill is the **per-post asset bundle** that handles hero, body imagery, and platform-optimized share variants together.

## Routing strategy (read this first)

The hard lesson from agents-that-remember (2026-05-04 → 2026-05-05): mixing coded SVG body diagrams with AI-generated decorative hero/social on one post produces "two different brands stapled together" (Idan's words). The fix is to pick ONE register per campaign:

**Tier 1 — coded SVG templates (technical/data posts).** Use when the post has metrics, before/after numbers, process steps, comparisons, or architecture. Hero + body + LinkedIn + X all coded in the body-diagram visual language (#07111E bg, #0E1B2D card, #F4A261 / #44B8FF / #1FC78D accents, system sans). Render via Chrome headless. Reference templates: `~/zerg/web/src/public/images/blog/agents-that-remember-{hero,body-1,body-2,linkedin,twitter}.svg`.

**Tier 2 — AI image gen (narrative/concept/vision posts).** Use when the post is essay/opinion/vision with no body diagrams. Provider order:
1. **chatgpt-image-skill (gpt-image-1)** — Idan's stated preference (2026-05-05)
2. nano-banana-pro (Gemini 3 Pro Image)
3. fal-image-skill (Flux Pro)
4. Pollinations (free, last resort)

**Decision rule:** if the post body has any of (metric numbers, "before/after", "X → Y", process steps, comparison vs competitors, architecture diagram language) → Tier 1. Otherwise → Tier 2. When ambiguous, Tier 1 wins for any Zerg-research/Zerg-product post; Tier 2 for opinion essays.

See memory: `feedback_blog_imagery_coherence.md` for the full reasoning.

## When to invoke

- Matt drafts or polishes a blog post and the asset bundle is missing
- A launch is approaching and social share images haven't been built
- Re-running on an existing post to refresh dated imagery
- After a copyedit pass changes the title or angle (image set should match the new framing)

When in doubt, suggest running it.

## What the skill produces (per blog post)

For a blog at `~/zerg/web/src/public/content/blog/<slug>.md`, the skill writes to `~/zerg/web/src/public/images/blog/`:

| Output | Filename | Size | Purpose |
|---|---|---|---|
| Hero / OG card | `<slug>-hero.png` | 1200×630 | Used by Open Graph crawlers (Facebook, LinkedIn, Slack, generic OG) AND as the on-page hero |
| Twitter/X share | `<slug>-twitter.png` | 1200×675 (16:9) | Twitter `summary_large_image` card. Often = hero, but sometimes a more text-heavy variant works better |
| LinkedIn in-feed | `<slug>-linkedin.png` | 1200×1200 (1:1) | LinkedIn's algorithm favors square in-feed images over landscape. Distinct from the OG card LinkedIn uses on link previews |
| Body image #1 | `<slug>-body-1.png` OR `.svg` | 1200×675 typical | Process diagram, architecture, or concept visual |
| Body image #2 | `<slug>-body-2.png` OR `.svg` | varies | Second concept visual OR comparison table (rendered as image OR raw markdown) |
| Comparison table | inline markdown | n/a | When a competitor/feature comparison is the natural body content (no image needed) |

Plus a sidecar:

- **`<slug>-imagery-plan.md`** in `/tmp/blog-imagery/` — a Markdown patch showing where to insert each image in the blog body (with alt text, captions, and the `![alt](path)` line ready to paste).

## Best-practices research (sources cited inline below)

### Hero / Open Graph card — 1200×630

- **Why this size:** Facebook's OG image spec recommends 1200×630 (1.91:1) and treats anything below 600×315 as a small thumbnail. LinkedIn and Slack honor the same OG tag, so one image serves all three. Twitter's `summary_large_image` accepts 1.91:1 too (renders fine inside a 16:9 frame). Source: [Facebook OG image guide](https://developers.facebook.com/docs/sharing/webmasters/images/), LinkedIn share preview docs.
- **Safe area:** Keep the load-bearing visual elements in the center 80% of the frame. Different platforms crop differently — LinkedIn often crops a bit narrower than Facebook on mobile.
- **Avoid text in the image.** Platform link previews already overlay your title and description; embedded text duplicates and gets truncated awkwardly. Source: Buffer, Hootsuite cheat-sheets (updated annually).
- **File size <300KB ideal, 1MB hard ceiling.** Keeps OG crawlers from skipping the image. Use PNG for graphics with hard edges, JPEG for photographs.
- **Aspect ratio: exactly 1.91:1.** Slight deviations (e.g. 1376×768 from existing Zerg blog heroes) work but get cropped on some platforms. New work targets 1200×630 unless there's a reason.

### Twitter/X share image — 1200×675 (16:9)

- **Why this size:** Twitter's `summary_large_image` card spec recommends 2:1 minimum, and the actual render frame is 16:9 on web. 1200×675 nails this. Source: [Twitter Cards documentation](https://developer.x.com/en/docs/twitter-for-websites/cards/overview/markup).
- **File size <5MB hard limit.** Realistic target <500KB.
- **Often = hero.** If the hero already conveys the post's claim, reuse it. Build a Twitter-specific image only when (a) the post needs a different visual hook for the timeline (more contrast, bigger numbers, etc.) or (b) you want a quote-tweet-friendly version.

### LinkedIn in-feed image — 1200×1200 (1:1 square)

- **Why this size:** LinkedIn's feed algorithm consistently favors square images over landscape — they take more vertical real estate and dwell longer. Multiple LinkedIn growth studies (Onalytica, Buffer 2024) show ~30% higher engagement on 1:1 vs 1.91:1 in-feed.
- **Distinct from the OG share card.** When someone shares the blog URL on LinkedIn, LinkedIn fetches the OG image (1200×630). When Matt manually posts to LinkedIn with an attached image, he can attach the 1200×1200 variant for better feed performance. The skill produces both.
- **File size <5MB.** Realistic target <500KB.

### Body images / diagrams / tables

- **Width: 1200×675 (16:9) or 1200×800 (3:2) for diagrams; 1200×1200 (1:1) for circular concept visuals.**
  Most blog containers max-width at 800-1000px, so anything above 1200 wide just gets shrunk on display. 1200 is the right native size — sharp on retina, no upscaling.
- **File size <500KB ideal.** Lazy-load below the fold; CLS-friendly markup uses explicit width/height attributes.
- **Alt text is mandatory** (WCAG 1.1.1). The skill writes alt text into the imagery plan that gets inserted into the markdown.
- **Captions for diagrams** — the bare image isn't always self-explanatory. The plan file includes a one-line caption suggestion under each image.
- **Choose the right type per content:**

  | Content | Best body asset |
  |---|---|
  | Process / pipeline (call → cards → board) | Diagram (Mermaid → PNG, or AI-rendered concept image) |
  | Architecture (where does X sit in the stack) | Diagram (Mermaid hierarchy) |
  | Comparison (us vs Linear/Trello/Otter/etc.) | Markdown table inline (no image) |
  | Stats / metrics (22% → 54%) | Inline callout OR small chart (Mermaid pie/bar) |
  | Decorative / aesthetic break | AI-generated concept image |
  | Code / config | Markdown code block (no image) |

  **Rule of thumb:** if the content is informational, prefer text/table/Mermaid (crisp, theme-aware, no AI weirdness). If the content is aesthetic, prefer AI image. The skill auto-decides based on a content-type classifier in the body of the post.

### Brand / style anchors for AI generation

These get prepended to every AI prompt to keep visuals on-brand:

- **Aesthetic:** dark cosmic / deep navy background; electric blue + warm amber accents; minimalist; futuristic; abstract conceptual art (NOT photorealistic).
- **Reference posts:** existing heroes at `~/zerg/web/src/public/images/blog/{build-now-hero,alphaevolve-hero,business-velocity-hero}.png` are the visual anchors. New work should look at-home next to these.
- **Forbidden:** stock photos of people, isometric office illustrations, gradient blob art, cartoon mascots, text/letters embedded in the image, Zerg logos (the site adds those separately).
- **Aspect-specific composition:**
  - 1.91:1 hero → centered hero element with aura/glow extending into the wide frame
  - 16:9 body → can use horizontal flow or before/after split
  - 1:1 LinkedIn feed → centered or vertically stacked elements

## Default invocation

```bash
python3 ~/.claude/skills/blog-imagery/run.py <blog_md_path> [flags]

# flags:
#   --slug SLUG           override slug (defaults to filename stem)
#   --provider auto|nano-banana|fal|pollinations  (default: auto = nano-banana → fal → pollinations chain)
#   --skip hero|twitter|linkedin|body  (skip an output type; repeatable)
#   --body-count N        number of body images (default: 2)
#   --out-dir DIR         where to write images (default: ~/zerg/web/src/public/images/blog/)
#   --plan-only           emit the imagery plan file but skip image generation (useful when quota is dead)
#   --apply               edit the blog markdown to insert image embeds (default: write plan only, don't touch md)
```

## Tier 1: SVG templates (technical/data posts)

Reusable brand-coherent templates derived from agents-that-remember. CLI:

```bash
# List templates
python3 ~/.claude/skills/blog-imagery/svg_template.py --list

# Print a template's example config (use as a starting point)
python3 ~/.claude/skills/blog-imagery/svg_template.py stat-card --show-example > /tmp/hero.json

# Edit /tmp/hero.json to your post's content, then render to PNG
# (writes a sibling .svg next to the PNG for later editing)
python3 ~/.claude/skills/blog-imagery/svg_template.py stat-card \
    --config /tmp/hero.json \
    --out ~/zerg/web/src/public/images/blog/<slug>-hero.png
```

### Template matrix (which one fits which content)

| Template    | Best for                                                           | Default aspect | Other aspects                |
|-------------|--------------------------------------------------------------------|----------------|------------------------------|
| `stat-card` | One headline delta (e.g., 22% → 54%). Hero / X 16:9 / LinkedIn 1:1 | og 1200×630    | `square` 1200×1200, `wide` 1200×675 |
| `funnel`    | Multi-stage compression (raw → unique → filtered). 1–4 stages      | body 1600×900  | `square` 1200×1200           |
| `tree`      | Two strategies / one root with comparison panels                   | body 1600×1000 | `wide` 1200×675              |

### Coverage strategy across one post

For a typical technical post, generate all 5 assets from templates so the campaign is one identity:

| Asset       | Template + aspect                                |
|-------------|--------------------------------------------------|
| Hero / OG   | `stat-card` aspect=`og` (1200×630)               |
| Body 1      | `funnel` aspect=`body` (1600×900)                |
| Body 2      | `tree` aspect=`body` (1600×1000)                 |
| LinkedIn 1:1| `stat-card` aspect=`square` OR `funnel` aspect=`square` |
| X 16:9      | `stat-card` aspect=`wide` OR `tree` aspect=`wide`|

Pick the aspect that fits the content most cleanly — don't force a stat-card for every channel if the funnel reads better at square. The point is one register, not one template.

### Adding a new template

1. Copy `templates/stat_card.py` as a starting point — render function takes a config dict, returns SVG markup, uses the shared palette from `_palette.py`.
2. Define `DESCRIPTION`, `DEFAULT_VIEWBOX`, `EXAMPLE_CONFIG`.
3. Register in `templates/__init__.py` REGISTRY dict.
4. The `svg_template.py` CLI picks it up automatically.

Templates derived from agents-that-remember (2026-05-05). Reference SVGs in `~/zerg/web/src/public/images/blog/agents-that-remember-{hero,body-1,body-2,linkedin,twitter}.svg`.

## Provider chain + quota behavior (Tier 2 only)

Applies to AI image gen for narrative/concept posts. For technical posts, use Tier 1 (coded SVG templates) — see Routing strategy above.

1. **Try `chatgpt-image-skill` (gpt-image-1) first.** Idan's stated preference. ~$0.04–0.17/image depending on quality.
2. **On OpenAI 429 / quota error:** fall through to nano-banana-pro.
3. **Try `nano-banana-pro` (Gemini 3 Pro Image).** ~$0.04/image when out of free tier.
4. **On 429 / RESOURCE_EXHAUSTED:** retry once after 60s. If still failing, fall through to FAL.
5. **Try `fal-image-skill` (Flux Pro).** Different account/quota, often available when others aren't. ~$0.05/image.
6. **On FAL 403 / "exhausted balance":** fall through to Pollinations.
7. **Pollinations (free, no key):** works always but quality is JPEG-as-PNG, lower resolution (1059×556 typical). Use as last resort.
8. **All providers down:** skill writes the prompts to a queue file (`/tmp/blog-imagery/queue/<slug>.json`) for manual retry later. Skill exits non-zero so the user knows.

Override per-provider with `--provider`. `--provider pollinations` skips paid providers entirely (useful when Matt knows the quota is dead).

## Output: what gets written where

```
~/zerg/web/src/public/images/blog/
  ├── <slug>-hero.png
  ├── <slug>-twitter.png       (skipped if --skip twitter)
  ├── <slug>-linkedin.png      (skipped if --skip linkedin)
  ├── <slug>-body-1.png        (or .svg if Mermaid renders)
  └── <slug>-body-2.png        (or omitted if a markdown table replaces it)

/tmp/blog-imagery/
  ├── <slug>-imagery-plan.md   (Markdown patch + insertion instructions)
  ├── <slug>-prompts.md        (the actual prompts used; reusable for re-rolls)
  └── queue/<slug>.json        (only if any provider failed and the prompt is queued for retry)
```

## When to invoke `--apply`

- The `<slug>-imagery-plan.md` always shows the full Markdown patch, but doesn't touch the blog source by default.
- Pass `--apply` to inline-edit `~/zerg/web/src/public/content/blog/<slug>.md` with the recommended image embeds + captions.
- If the blog has existing images in body, the skill respects them: it inserts new ones in suggested positions but doesn't overwrite.

## Mermaid diagrams

If `mmdc` (Mermaid CLI) is installed (`npm install -g @mermaid-js/mermaid-cli`), the skill can render concept diagrams to PNG/SVG with brand-controlled colors. Without `mmdc`, the skill emits Mermaid as a text code block in the plan and lets you decide whether to render manually or fall back to AI imagery. Auto-detected at runtime.

## What this skill is NOT

- Not a hero-only generator (use `nano-banana-pro` or `fal-image-skill` directly for one-off images).
- Not a video/animation generator (use `fal-video-skill` for that).
- Not a publisher (doesn't deploy the blog or post to social — Matt does that manually).
- Not a layout/CSS skill (use `landing-page-skill` for full-page design work).

## Safety

- **Never auto-posts.** Writes asset files + plan only.
- **Doesn't modify blog markdown by default** (use `--apply` opt-in).
- **Respects existing images** — won't overwrite a non-empty image file unless `--force` is passed.
- **Quota guardrails** — fails fast with a clear retry queue rather than silently producing bad fallback art.
