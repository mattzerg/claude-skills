---
name: graphic-layout
description: Composition + balance review for any rendered image asset Matt or Claude builds — blog hero, body figure, share variant, GIF frame, one-pager page, slide. Sibling to fakematt-feedback (UX) and fakematt-copyedit (prose). Anchored on `MattZerg/_style/graphic_layout.md` (templates) + `feedback_graphic_basics.md` (memory rules). Two modes — `review` (audit a rendered PNG/PDF for layout failures) and `template` (return the canonical composition for a target intent: hero / split-comparison / stat-strip / step-sequence / title-card / annotated-screenshot). Output is a structured findings list with cited rules + suggested fixes; never modifies source files. USE PROACTIVELY whenever Matt or Claude renders a graphic, before declaring it done; whenever building a multi-frame GIF/video so each frame's composition is intentional; whenever an asset feels "weird" (left-heavy, dead space, generic eyebrow noise) so the issue gets named instead of guessed at. Hard rule: graphic shipping requires this check to pass.
---

# Graphic Layout Skill

Sibling to `fakematt-feedback` (product/UX review on live targets) and `fakematt-copyedit` (sentence-level prose review). This one operates on **rendered image assets** — PNG, PDF page, GIF frame, slide — and audits **composition + balance**, not content.

It exists because composition mistakes have been recurring on Matt's deliverables (left-pile, eyebrow noise, top-bottom asymmetry, minimalism), and "guess and iterate" wastes turns. With this skill, Claude has a named template + checklist to consult during build, and a review pass to run before declaring done.

## When to invoke

- Before declaring any graphic done — render → run `review` → fix → re-render until clean.
- Before building a multi-frame sequence (GIF, slide deck) — pick a `template` first so each frame's intended composition is explicit.
- When Matt says an asset feels "weird," "off," "heavy on one side," "minimal," or "wasted space" — run `review` and produce findings with cited rules.
- During launch-pack builds, where there are 5–7 assets in a campaign — run `review` once per asset to keep visual coherence.

## Two modes

### review — audit a rendered asset

```bash
python3 ~/.claude/skills/graphic-layout/run.py review <png_or_pdf_page> [flags]
```

Flags:
- `--target-kind KIND` — `hero` | `body-figure` | `body-annotated` | `share-square` | `share-16x9` | `gif-frame` | `title-card` | `slide` | `one-pager-page`. Affects which checks weight HIGH.
- `--out-dir DIR` — default `/tmp/graphic-layout/`
- `--no-pdf` — skip side-by-side annotated render of findings

Emits per-asset:
- `<asset>.review.md` — findings list (HIGH / MEDIUM / LOW), each with cited rule + suggested fix
- `<asset>.annotated.png` — the source image with overlay rectangles showing dead-space regions, weight imbalance arrows, edge-clip danger zones (only when `--annotated`)

### template — return the canonical composition for a target intent

```bash
python3 ~/.claude/skills/graphic-layout/run.py template <intent> [--canvas WxH]
```

Intents:
- `hero` — blog OG card. Centered or rule-of-thirds. One headline, one supporting visual. 1200×630 default.
- `split-comparison` — A vs B (price vs price, before vs after). 50/50 split, equal weight.
- `stat-strip` — 3 stat boxes equal-width in a horizontal row. Centered title above.
- `step-sequence` — multi-frame GIF/carousel: shared anchor point across frames, one idea per frame. Returns per-frame composition spec.
- `title-card` — endcap / final-frame: wordmark + headline + sub + CTA + 1 supporting element. Center-vertical, slight left-bias on text or fully centered. 1200×630 default.
- `annotated-screenshot` — UI-mockup with numbered callouts + side rail. Pane left, rail right. See `body-annotated` rules in graphic_basics.

Returns a markdown spec with:
- Pixel coordinates for every region (header band, hero zone, body zone, footer)
- Type sizes + weights
- Padding floors (top/bottom/left/right)
- Eyebrow inclusion test (only include if it adds info)

## Composition rules (the layer this skill enforces)

These are anchored in `MattZerg/_style/graphic_layout.md` and `feedback_graphic_basics.md` (memory). Quick reference:

### 1. Top/bottom balance (already in graphic_basics rule 5)
Top padding ≥40px above first element; bottom padding within 1.5× of top; no continuous empty strip >150px at either end. **Size canvas to longest content + ~80px total padding** — don't ship a 1000px-tall canvas with content filling 600px.

### 2. Left/right balance
**Don't pile content on one side unless using rule-of-thirds intentionally.** Common failure: title in left third + viz on right takes a single concept and stretches it across the full canvas. Better moves:
- Centered hero (single column, headline above viz)
- 50/50 split with a real equal-weight comparison (not "title vs supporting viz")
- Rule of thirds where the off-center anchor is dominant and the negative space is intentional

Rule of thumb: if you can describe the layout as "title left, viz right" you're probably making the canvas wider than it should be. Either crop to a square or center the title above the viz.

### 3. Eyebrow value test
**Eyebrow text only earns its place if it carries information.** "ZERGBOARD · LAUNCH" on every frame of a 5-frame GIF is dead weight — it never changes, never says anything new, and steals the top 40px of every frame. Cut it. Keep eyebrows when they:
- Number a step in a multi-step diagram ("Step 2 of 5")
- Identify a different speaker / source / surface in a multi-source pack
- Add genuine context that a reader who lands mid-loop needs

Default for product-launch GIFs: no eyebrow. The visual itself is the launch.

### 4. Single dominant headline
One element should be the visual anchor (largest type, highest weight, most saturation). If two elements compete (e.g., a left-side headline at 56pt and a right-side numeric at 180pt), the smaller one looks decorative and the bigger one looks alone. Pick one to lead.

### 5. Frame coherence across a sequence
For multi-frame GIFs / carousels: pick a fixed anchor point (e.g., headline always at y=200, or always centered) and let only the supporting visual change. The eye should not chase across the canvas between frames.

### 6. White space is a design element, not leftover
Empty regions should feel intentional. If 40% of the canvas is empty dark space and the empty region has no compositional purpose (breathing for an off-center anchor; framing the hero), shrink the canvas. Don't fill empty space with token decoration (random particles, decorative dots, repeated words) — that's worse than the empty space.

### 7. Composition templates by intent

| Intent | Template | Canvas | Notes |
|---|---|---|---|
| Blog hero / OG card | Centered headline + viz below OR rule-of-thirds | 1200×630 | One idea, one viz, one CTA-or-anchor |
| LinkedIn share | Square — headline center + viz center | 1200×1200 | Same scene as hero, square-cropped |
| X / Twitter share | 16:9 — same as hero, slight angle variation | 1200×675 | Pair with hero, not duplicate |
| In-body figure (cinematic) | Painterly / illustrative, anchor centered | 1600×1000 | Canvas height OK to leave atmospheric whitespace if intentional |
| In-body annotated screenshot | Pane left + numbered side-rail right | 1600×720 (sized to content) | See annotated rules in graphic_basics |
| Title card / endcap | Wordmark top-left or center, headline center, CTA below, comparator right OR below | 1200×630 | Final frame of GIFs; standalone share asset |
| Stat strip | 3 equal columns, headline centered above | varies | Centered title, equal-weight cards |
| GIF frame (in a sequence) | Same anchor point across frames; one centered idea | 1200×630 | No eyebrow unless it numbers the step |

## Output register

Findings are professional/structured (not Matt-voice cosplay). Each cites:
- **Rule:** which composition rule (1–6 above) or which `feedback_graphic_basics.md` rule (1–6)
- **Confidence:** HIGH (clear violation) / MEDIUM (judgment call) / LOW (style preference)
- **Suggested fix:** specific (move element X to coord Y; shrink canvas to H×W; cut element Z)

## Anchors loaded each run

- `MattZerg/_style/graphic_layout.md` — canonical composition templates with pixel specs
- `feedback_graphic_basics.md` (memory) — the 6 generation-time rules + 6-point self-check
- `feedback_internal_review_pack_format.md` (memory) — required asset set for launch packs
- `feedback_blog_imagery_coherence.md` (memory) — visual coherence across an asset campaign

## What this skill is NOT

- Not a **content** reviewer (use `fakematt-feedback` for product UX, `fakematt-copyedit` for prose)
- Not a **generator** — it doesn't produce graphics. It reviews and templates them. Generators include `blog-imagery`, `chatgpt-image-skill`, the per-launch SVG builders.
- Not a **video reviewer** — that's `video-review`. Layout overlaps but timing/audio/codec do not.

## Safety

- Never modifies source files. Writes findings to `/tmp/graphic-layout/<asset>.review.md`.
- Never auto-posts. If Matt asks for a Slack copy, drops it in his self-DM.
- Never silently overwrites the canonical PNG. Versioned saves go through the originating builder, per `feedback_label_iteration_versions.md`.
