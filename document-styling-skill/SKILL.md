---
name: document-styling-skill
description: Render markdown documents to branded PDF using Zerg's visual template system. Owns the brand palette, type system, and layout zones (header band, hero, body, optional sidebar/chip strip, footer). Two canonical Zerg themes per the dual-palette routing rule — `zerg-default` (cream paper, Zstack/non-technical audiences) and `zerg-dark` (charcoal paper, Zerg-parent / heavy-technical content). Both pull from the live site (`~/zerg/web/src/pages/index.vue`), NOT `main.css`. Designed for one-pagers but reusable for any single-page or short-document collateral. Pairs with `one-pager-skill` (which scaffolds content) — content lives there, visual treatment lives here. Never auto-publishes; writes PDF + HTML next to source. USE PROACTIVELY when Matt asks for a branded / designed / styled PDF, or wants to swap visual treatment on an existing one-pager / brief.
allowed-tools: Bash, Read, Write
---


# Document Styling Skill

Sibling to `one-pager-skill` (content) and `blog-imagery` (image assets). This skill owns the **visual treatment** layer — the brand palette, type system, layout zones, and CSS themes that turn a plain markdown document into branded collateral.

Built from research across the 10-doc Drive corpus (Hoy Health, Joi, Intercept TeleMed, eHubCo) plus public B2B SaaS exemplars (Stripe, Linear, Vercel, Anthropic). Recurring visual moves codified in `themes/zerg-default.css`.

## When to invoke

- Matt asks for a "branded" / "designed" / "styled" PDF rather than the plain professional default
- Matt wants to swap visual treatment on an existing one-pager / brief
- A new doc-genre needs a visual template (decks-as-PDF, partner briefs, investor sheets)
- Pair: `one-pager-skill scaffold` → fill content → `document-styling render --theme zerg-default`

## Themes shipped

Per the **dual-palette routing** rule (`feedback_zerg_brand.md`, locked 2026-05-08), Zerg has TWO valid surfaces — cream paper (default, Zstack/non-technical/buyer audiences) and charcoal dark (Zerg-parent / heavy-technical / dev / MCP-API / research-genre). Pick by audience + product context, not preference.

| Theme | Paper + accent | Type | Vibe | When to use |
|---|---|---|---|---|
| **zerg-default** | Cream `#f4f0e7` + burnt-orange `#b3662f` (with `#8a4a1f` for AA-contrast labels on cream) + brand-green `#6FBE31` secondary | Space Grotesk | Matches the live marketing site exactly | Default for **Zstack products + non-technical audiences** (buyers, marketing, ops, sales personas, comparison pages, pricing pages, one-pagers, leave-behinds) |
| **zerg-dark** | Charcoal `#111514` paper + cream `#f4f0e7` text + burnt-orange `#d57a32` (bright variant works on dark) + brand-green `#6FBE31` secondary | Space Grotesk | Brand-correct dark — Zerg-parent register | **Zerg parent brand + heavy-technical content** (research posts, integration pages targeting devs, MCP/API docs, architecture explainers, founder-voice / Idan-genre) |
| **zerg-navy** | White paper + `#1F3A5F` deep navy | Inter | Enterprise-grade, conservative | Investor briefs, enterprise sales contexts where the burnt-orange feels too warm |
| **zerg-warm** | Warm paper `#FAF9F5` + `#D97757` rust orange | Inter | Editorial, Anthropic-style warmth | Partner briefs, network leave-behinds, anything that should feel less "deck" and more "thoughtful" |

`zerg-default` and `zerg-dark` are the two canonical Zerg-brand surfaces. `zerg-navy` and `zerg-warm` are context-specific overrides for non-Zerg-default genres. Switch by passing `--theme <name>` to `render.py`.

## Visual template — five zones

```
+-----------------------------------------------------------+
|  HEADER BAND   (60-90pt tall)                             |
|  [LOGO/wordmark]                  zerg.ai · contact info  |
+-----------------------------------------------------------+
|  HERO LEAD     (single col, ~120pt)                       |
|  ## EYEBROW (accent, all-caps tracked)                    |
|  # H1 headline                                            |
|  > One-line dek                                           |
+-----------------------------------------------------------+
|  BODY                                                     |
|  Section headings as eyebrow labels in accent color       |
|  Body copy at 9.5pt Inter regular                         |
|  Tables w/ thin accent rules                              |
|  Optional inline SVG diagrams (e.g. integration arc)      |
+-----------------------------------------------------------+
|  CHIP STRIP    (optional, ~36pt — product variant only)   |
|  [Zergboard] [ZergChat] [ZergCal] [ZergMeeting] [ZergMail]|
+-----------------------------------------------------------+
|  FOOTER BAND   (thin, accent top rule)                    |
|  zerg.ai  ·  contact@zerg.ai  ·  2026                     |
+-----------------------------------------------------------+
```

Zones are populated from markdown frontmatter + body structure. Frontmatter fields the renderer reads:

```yaml
---
title: ZergStack          # H1 if not in body
tagline: Five products...  # dek line under H1
brand_line: Zerg AI       # top-right of header band
footer_line: zerg.ai · contact@zergai.com
chip_strip: [Zergboard, ZergChat, ZergCal, ZergMeeting, ZergMail]  # optional
theme: zerg-default       # default if omitted
---
```

If frontmatter is absent, the renderer falls back to: H1 from first `# Heading`, dek from first blockquote, no chip strip, no brand line.

## Two modes

### render — produce a branded PDF

```bash
python3 ~/.claude/skills/document-styling-skill/render.py <markdown.md> [<more.md>...] [flags]
```

Flags:
- `--theme NAME` — `zerg-default` (default) | `zerg-navy` | `zerg-warm`
- `--accent HEX` — override accent color without picking a theme (advanced)
- `--out-dir DIR` — output directory (default: next to source)
- `--no-open` — skip Preview open
- `--strict-one-page` — fail loud if rendered output exceeds one page (default true for files matching `*.one-pager.md`)

Writes:
- `<input>.pdf` next to the source
- `<input>.html` sidecar (debug; can be deleted)

### list — show available themes

```bash
python3 ~/.claude/skills/document-styling-skill/render.py list
```

Prints theme names + accent colors + the markdown frontmatter required.

## Brand system

Full reference at `brand.md` next to this file. Summary:

- **Primary accent**: `#b3662f` burnt orange (eyebrow labels on dark sections, callouts, dividers). Use `#8a4a1f` for small uppercase labels on cream so they pass WCAG AA contrast. Use `#d57a32` brighter variant on charcoal `#111514` bg.
- **Secondary accent**: `#6FBE31` brand green (chip strips, footer rules, accent counterweight). Use `#0a4d33` for status pills on cream — passes WCAG AAA.
- **Neutrals**: charcoal `#111514` (display + dark CTA fill), mid-gray `#52605c` / `#41504c` (dek, captions), rule-gray `#dad6cb` (borders on cream), paper `#f4f0e7` (cream — live-site bg).
- **Type**: Space Grotesk (display + body), Space Mono for tracked uppercase eyebrow labels. Loaded via Google Fonts CDN with virtual-time-budget so fonts paint before PDF capture.
- **Type scale**: H1 22pt / eyebrow 8pt all-caps tracked / H2 11pt / H3 10.5pt / body 9.5pt / metadata 8pt.
- **Spacing**: 0.4in × 0.45in page margins; 7pt section vertical rhythm; tighten to 5pt before reducing type if overflow.

## How this skill differs from one-pager-skill

| Concern | one-pager-skill | document-styling-skill |
|---|---|---|
| **Owns** | Content structure (beats, voice, copy) | Visual treatment (palette, type, layout) |
| **Modes** | `scaffold`, `review` | `render`, `list` |
| **Output** | Markdown + checklist + plain PDF | Branded PDF (renders any markdown) |
| **Reusable** | One-pager genre only | Any single-page / short doc |

The plain `render_pdf.py` in `one-pager-skill/` stays — it's the "no-brand" fallback. Pass `--theme` to one-pager-skill OR call this skill directly to get branded output.

## Safety

- **Never auto-publishes.** Writes PDF + HTML next to source.
- **Strict one-page enforcement** for `*.one-pager.md` files — fails loud rather than silently spilling.
- **No memory writes.** Reads anchors + themes; doesn't modify the source markdown.
- **Doesn't override frontmatter.** If a doc declares `theme: zerg-warm`, that wins over the `--theme` flag unless `--force-theme` is passed.
