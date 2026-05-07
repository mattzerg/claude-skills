# Zerg Brand Reference

Captured 2026-05-06 from visual research across the 10-doc Drive corpus + public B2B SaaS exemplars (Stripe, Linear, Vercel, Anthropic). This is the canonical brand reference for all printed Zerg collateral until Idan locks an official brand system.

## Color palette

### Primary accent
- **`#C0392B` Brick Red** — controlled, slightly desaturated. Single accent across the page: wordmark, eyebrow labels, links, callout borders, chip backgrounds.
- **Why red:** B2B SaaS in 2026 sits in the blue/navy/black neutral zone (Linear, Stripe, Vercel, Plaid). Red differentiates without being childish (the Hoy Health red works because it's confident, not bright).

### Alternates (theme overrides)
- **`#1F3A5F` Deep Navy** — when red feels too punchy (investor briefs, conservative enterprise contexts)
- **`#D97757` Rust Orange** — when warmth wins (Anthropic-style editorial; pairs with warm paper)

### Neutrals
- **`#1A1A1A` Charcoal** — display type, H1, primary body
- **`#5A5A5A` Mid-Gray** — secondary body, metadata, captions
- **`#D8D8D8` Rule Gray** — table borders, section dividers
- **`#FFFFFF` Paper** (default) or **`#FAF9F5` Warm Paper** (for `zerg-warm` theme)

### Discipline rule
**Single accent, four jobs:** wordmark/header band, section eyebrow labels, links/CTAs, callout backgrounds. Never introduce a second accent. Gradients are forbidden. The discipline is the brand.

## Typography

### Font family
- **Display + body: Inter** (Google Fonts, weights 400/500/600/700)
- **Optional mono accent: JetBrains Mono** for monospace eyebrow labels (Vercel-style — reserved for `product` and `consulting` variants)

### Type scale
| Element | Size | Weight | Tracking | Color |
|---|---|---|---|---|
| H1 | 22pt | 700 | -0.01em | charcoal |
| H2 (eyebrow) | 8pt | 600 | 0.08em ALL CAPS | accent |
| H2 prose | 11pt | 600 | 0 | charcoal |
| H3 | 10.5pt | 600 | 0 | charcoal |
| Body | 9.5pt | 400 | 0 | charcoal |
| Metadata | 8pt | 500 | 0 | mid-gray |
| Eyebrow (sub) | 7.5pt | 600 | 0.1em ALL CAPS | accent |

### Eyebrow labels (the signature move)
Tiny ALL-CAPS tracked labels in the accent color, sitting above section headings or as standalone section markers. Source: Hoy Health, Stripe, Joi.

```html
<div class="eyebrow">PRICING</div>
<h2>$19/seat for the bundle</h2>
```

This single pattern is what makes a doc read as "designed" rather than "Word output."

## Layout zones

A branded one-pager has up to five zones:

1. **Header band** (60-90pt tall) — wordmark left, contact metadata right, accent bottom rule
2. **Hero lead** (~120pt) — eyebrow + H1 + dek
3. **Body** — single column; eyebrow + section heading pattern repeats
4. **Chip strip** (optional, ~36pt) — uniform accent-colored chips for product family / sister apps; only on `product` variant by default
5. **Footer band** (thin, ~24pt) — accent top rule, contact metadata centered

Margins: `0.4in 0.45in` (top/bottom × left/right) on Letter.
Vertical rhythm: 7pt between sections; tighten to 5pt before shrinking type.

## Component patterns

### Header band
```
[Brand wordmark, large]                    Brand line · Contact
                                                ·  ·  ·
═══════════════════════════════════════════════════════════════ (accent rule)
```

### Hero
```
EYEBROW IN ACCENT COLOR
H1 Headline (large, charcoal, tight tracking)
> Dek line, mid-gray italic, ~11pt
```

### Sectioned body
```
EYEBROW
H2 Section heading (charcoal, 11pt, normal weight)
Body prose at 9.5pt regular...
```

### Chip strip
```
[ Zergboard ]  [ ZergChat ]  [ ZergCal ]  [ ZergMeeting ]  [ ZergMail ]
   accent-bg, white text, uniform 110pt × 28pt, 8pt gap
```

### Footer band
```
═══════════════════════════════════════════════════════════════ (accent thin rule)
zerg.ai  ·  contact@zergai.com  ·  2026
                          (centered, mid-gray, 8pt)
```

### Callout / sidebar block
Bordered or tinted block (left-border 3pt accent OR background `rgba(C0392B,0.05)`). Used for pricing tier card, key facts rail, or "what's included" highlight.

## Recurring visual moves (steal from corpus)

1. **Hero band that owns the top 25-30%** of the page — anchors the eye before body copy.
2. **Single accent color, four jobs.** Stripe/Hoy/Linear all do this.
3. **Tiny ALL-CAPS tracked eyebrow labels** above section headings — the highest-leverage micro-pattern.
4. **Metadata rail, not metadata prose** — six+ facts go in a sidebar or footer band, never inline.
5. **Footer chip strip** — repeating uniform-accent elements signal scope/credibility and visually close the page.

## Anti-patterns (cut on sight)

1. **Logo soup** — chaotic mixed-aspect-ratio logos. Logos need uniform height + monochrome treatment, or skip.
2. **Centered prose in long sections** — defaults to "Word doc" feel. Always left-align.
3. **No accent at all** — grayscale-only is generic. Even one accent application transforms the read.
4. **Two competing accents** — never red+blue, orange+teal, etc. Monochromatic+1 is the rule.
5. **Big author photos** — eat space that named past work would fill better. Skip in print.

## When to deviate

- **Single-product one-pager** (e.g., Zergboard alone): may drop the chip strip; lean on capabilities.
- **Investor variant**: traction numbers in the hero zone; sidebar = round metadata (raise, valuation, run rate, burn). Inspired by Joi.
- **Confidential / NDA contexts**: drop named clients from chip strip; use anonymized chips ("Top-3 defense aerospace prime").

## Loading and rendering notes

- Fonts loaded via `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">` with `--virtual-time-budget=2000` Chrome flag so fonts paint before PDF capture
- For offline reliability, self-host Inter as woff2 in `~/.claude/skills/document-styling-skill/assets/` and `@font-face` from `file://` URL — Phase 2
- SVG for chips/diagrams (not HTML divs) — print rendering of `border-radius` + `background` on inline-block can be inconsistent
- Inline base64 data-URIs for any embedded images so file:// resolution doesn't break

## Sources

- Drive corpus: Hoy Health B2B/B2C, Joi, eHubCo, Intercept TeleMed
- Public exemplars: Stripe brand palette, Linear brand guidelines, Vercel Geist, Anthropic palette
- Pattern collections: Dock — 17 Sales One-Pager Examples; AFFiNE — One Pager Examples 2026; Visme — One-Pager Layout Ideas

## Versioning

This is v1 (2026-05-06). Idan to review and lock or override before any of these themes ship to a customer-facing PDF. Once locked, capture in `MattZerg/_style/brand_visual.md` as the canonical source of truth.
