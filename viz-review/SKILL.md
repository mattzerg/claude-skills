---
name: viz-review
description: Audit charts + decks + chart-builder specs against Tufte chart hygiene + Zerg slide visual rules. Three modes — `chart <png|svg|md>` audits a single rendered chart against `MattZerg/_style/chart_style.md` (data-ink, axis truncation, label presence, color count, source citation, accessibility); `deck <pptx|storyline.md>` audits a deck or its shadow outline against `MattZerg/_style/consultant_deck_visual_style.md` (action-title compliance, chrome, font, layout variety, source slide, recommendation slide, slide count); `recipe <spec.json>` lints a chart-builder spec before render (HIGH/MED/LOW findings). Different from `brand-check` + `graphic-layout` (viz-review CALLS them) and `fakematt-feedback` (UX walkthrough). USE PROACTIVELY when Matt says "viz review", "review this chart", "audit the deck", "Tufte check", "lint this chart", "is this chart any good", or before any chart/deck leaves the vault. Never auto-fixes — outputs ranked findings only.
allowed-tools: Bash, Read, Write
---

# Viz Review

Sibling to `brand-check` (palette/logo on rendered assets) and `graphic-layout` (composition). This one audits chart + deck visual hygiene against named style rules.

## Anchors

This skill draws its voice and pattern catalog from:

- **Voice fingerprint:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_considered_voice.md`
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md`
- **Domain corpus:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/viz_feedback_corpus.md`
- **Catalog patterns to cite by slug** (Section G Viz / video): scorecard-deltas, demo-or-perish, action-title, chart-junk, axis-truncation-honesty, color-encoding-discipline, data-density, annotation-placement, deck-slide-density, hierarchy, no-redundant-legends, annotation-near-the-point, stats-strip-discipline, recommendation-slide-discipline

Read these BEFORE producing output. Cite patterns by slug from the catalog.

For a **multi-page PDF document or deck SET**, also apply the document-set delivery bar in memory `feedback_nick_consulting_doc_bar.md`: page-break hygiene (no heading stranded from its body, no table/glossary row split, no figure separated from its caption/color key), clickable TOC + internal cross-references in the rendered PDF, and same-theme consistency across the set. `document-styling-skill` enforces these on multi-page renders — flag (HIGH) if a shipped PDF still shows a split figure/glossary or dead internal links.

## When to invoke

- Matt drops a chart PNG/SVG and asks "is this any good"
- Before any `consultant-deck` PPTX ships to a client
- Before a chart-builder spec is rendered (`recipe` mode lints early)
- As the final pass in `consultant-engagement` Phase 3 before deliverable handoff

## Different from

| Sibling | Owns |
|---|---|
| `viz-review` (this) | Chart/deck audit against Tufte + consultant_deck_visual_style |
| `brand-check` | Logo/palette/hierarchy on any rendered asset (called by viz-review) |
| `graphic-layout` | Composition (balance, text fit, whitespace) on any rendered asset |
| `fakematt-feedback` | UX walkthrough on live URLs / Figma / screenshots |

## Modes

### `chart` — single chart audit

```bash
python3 ~/.claude/skills/viz-review/run.py chart <path-to-chart-png-or-svg> \
  [--mode default|dark] [--caption-md <caption.md>]
```

Checks against `chart_style.md`:
- Value labels present (looks for digits in image text via OCR if available, else checks for caption sidecar)
- Caption sidecar exists (`.caption.md`)
- Source citation present in caption (`Source:` line)
- Color palette compliance (calls `brand-check`)
- Composition (calls `graphic-layout` with target-kind=body-figure)
- File size sanity (< 2MB PNG, > 5KB)

### `deck` — full deck audit

```bash
python3 ~/.claude/skills/viz-review/run.py deck <path-to-pptx-or-storyline.md>
```

Checks against `consultant_deck_visual_style.md`:
- Action-title compliance (each slide title ≥ 5 words, has a verb)
- Layout-type variety (warn if 15+ slides all `support` or `chart` type)
- Required slides present: title, exec-summary, recommendation, appendix-sources
- Slide count (warn > 25; refuse > 35)
- Source slide populated (≥ 1 source if any quantitative claim made)
- Chrome on every non-title slide (eyebrow + footer band)
- Client-mode citation gate (any `[needs-verification]` blocks deck)
- Empty `support` slides (no chart_path AND no table_md)

### `recipe` — chart-builder spec lint

```bash
python3 ~/.claude/skills/viz-review/run.py recipe <spec.json>
```

Wraps `chart-builder validate` and re-frames findings as HIGH/MED/LOW. Catches missing required fields, list-length mismatches, pathological data ranges (flat series, all-zero waterfall, degenerate 2x2).

## Output

Severity-ranked findings (HIGH → MED → LOW):

```
## viz-review chart — bar.png
- **HIGH** — No value labels detected; bar chart values cannot be read directly
- **MED** — No `.caption.md` sidecar (action-title caption missing)
- **LOW** — Image file 38KB — below typical 60–800KB range for branded chart
```

Exit code: 0 if no HIGH findings; 1 if any HIGH.

## Composition

- For `chart` mode: calls `brand-check` on the image for palette + brand hierarchy
- For `chart` mode: calls `graphic-layout` for composition
- For `deck` mode: opens PPTX via python-pptx and inspects slide-level structure; for `storyline.md`, parses frontmatter directly
- For `recipe` mode: calls `consultant_kit.chart.validate_spec` directly

## Anchoring

- `MattZerg/_style/chart_style.md` — chart rules (8 numbered)
- `MattZerg/_style/consultant_deck_visual_style.md` — deck rules (8 numbered)
- `MattZerg/_style/writing_style.md` — universal voice rules for captions/titles

## Hard rule

`viz-review` never auto-fixes. Emits findings + the rule citation. Fixes are made manually or by re-invoking `chart-builder` / `consultant-deck` with corrected inputs.
