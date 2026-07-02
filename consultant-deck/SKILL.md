---
name: consultant-deck
description: Action-title slide deck production with embedded charts + branded chrome. Writes a canonical `.md` shadow outline FIRST (the storyline source of truth), then renders to `.pptx` via python-pptx. Auto-discovers charts from the engagement's `05-analysis/charts/` and embeds them as slide bodies; auto-pulls source citations onto the appendix slide. 10 layout types (title, exec-summary, section-divider, chart, two-col, stats-strip, quote, table, recommendation, appendix-sources) with branded chrome on every slide. Different from `google-slides-skill` (transport — Google Slides API CRUD), `gamma-skill` (transport — Gamma API), `one-pager-skill` (single-page collateral), `case-study-skill` (long-form narrative). USE PROACTIVELY when Matt says "build the deck", "consultant deck", "action-title deck", "render to PPTX", "slide deck for", "synthesize into slides", or after `minto-pyramid` is approved (Gate 3). Never auto-posts; refuses to render in client mode if any `[needs-verification]` survives upstream.
allowed-tools: Bash, Read, Write
---

# Consultant Deck

Phase 3 deliverable-layer flagship. Renders an approved `minto-pyramid` into an action-title deck with embedded charts + branded chrome.

## Anchors

This skill draws its voice and pattern catalog from:

- **Style fingerprint:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_deck_visual_style.md`
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` (Consultant section H + Viz section G)
- **Review-mode corpus (artifact):** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_artifact_feedback_corpus.md`
- **Review-mode corpus (viz):** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/viz_feedback_corpus.md`

Read these BEFORE producing output (especially before review-mode invocations).

- **Catalog patterns to cite by slug** (Section A Universal / process): honest-scoping
- **Catalog patterns to cite by slug** (Section B UI / product design): ia-ordering
- **Catalog patterns to cite by slug** (Section G Viz / video): action-title, hierarchy, deck-slide-density, recommendation-slide-discipline, stats-strip-discipline, scorecard-deltas
- **Catalog patterns to cite by slug** (Section I Launch / deck): deferred-with-reason

## When to invoke

- After `minto-pyramid` is approved (Gate 3 in the engagement orchestrator)
- Matt says "build the deck", "consultant deck", "action-title deck", "render to PPTX"
- Cross-cuts the storyline-to-deliverable transition

## Layout types (10)

| Type | Body content | Used for |
|---|---|---|
| `title` | Engagement name (display), subtitle, date | Slide 1 |
| `exec-summary` | Governing thought (italic) + numbered keys (accent numbers) | Slide 2 |
| `section-divider` | Big eyebrow + chapter title; minimal body | Phase transitions |
| `chart` | Embedded chart PNG (10×4.4in) + caption + source line | Phase 2 analysis evidence |
| `two-col` | Left bullets (1.6fr) / right chart or text (1fr) | Comparisons, claim+chart |
| `stats-strip` | 3–4 equal-width cells, each with stat (big accent) + unit (eyebrow) + caption | Top-line metrics |
| `quote` | Pull quote (large italic) + accent quote mark + attribution | Customer/partner voice |
| `table` | Markdown table → PPTX table with banded rows + accent header | Pricing tiers, workstream lists |
| `recommendation` | Action (large accent) + RISKS column + NEXT STEPS column | Decision slides |
| `appendix-sources` | Auto-generated sources list from upstream `source_citations` | End matter |

## Chrome (every slide except title)

- **Eyebrow band** — small-caps tracked label in accent color above the action title (`EXECUTIVE SUMMARY`, `KEY 2 / 3`, `ANALYSIS — KEY 1`, `RECOMMENDATION`, `APPENDIX`)
- **Action title** — bold 22pt body claim
- **Accent rule** — short burnt-orange bar under the title
- **Footer band** — engagement name (left) | date (center) | slide # / total (right) + thin accent rule above

## Two-step protocol

### Step 1: `outline` — write shadow outline

```bash
python3 ~/.claude/skills/consultant-deck/run.py outline \
  --from <minto-pyramid-path> \
  --engagement <slug> --mode <mode>
```

Writes `<engagement>/08-deliverable/storyline.md` — the canonical source of truth. Each slide spec carries `type`, `title`, `eyebrow`, and (when applicable) `chart_path`, `caption`, `source`, `table_md`, `stats`, `quote`, `action` / `risks` / `next_steps`, `sources`.

**Auto-discovery:**
- Scans `<engagement>/05-analysis/charts/*.png` and assigns charts to support slides in order
- Walks every artifact in the engagement to collect `source_citations` for the appendix slide
- Lint warns when a `support` slide has no `chart_path` and no `table_md` (body will be empty)
- Lint warns when titles look like topics (under 5 words)
- Hard cap: 35 slides (refuses to render); soft cap: 25 slides (flagged)

### Step 2: `render` — produce `.pptx`

```bash
python3 ~/.claude/skills/consultant-deck/run.py render \
  <storyline-path> --target pptx \
  [--palette default|dark]
```

Targets:
- `pptx` (default) — python-pptx deterministic render via `consultant_kit.layout.dispatch()`
- `gslides` — wraps `google-slides-skill` (Phase 2 — not yet implemented; falls back to `pptx`)
- `gamma` — wraps `gamma-skill` `--scaffold-only` (Phase 2)

Writes `<engagement>/08-deliverable/<engagement>-deck.pptx`.

## Hard rules

- **Storyline-first**: render is preceded by an outline + manual approval pass on titles
- **Client mode gate**: client mode + storyline contains `[needs-verification]` → render refused
- **Action titles only**: titles must be complete claims, not topics. Lint warns <5 words
- **One chart, one table, or one structured callout per slide** — no kitchen-sink slides
- **Markdown → PPTX table** via `consultant_kit.layout.md_table_to_rows()` (banded rows, accent header)

## Composition

- Reads `minto-pyramid` storyline as input
- Reads `chart-builder` outputs from `05-analysis/charts/` (embeds PNGs as slide bodies)
- Reads any `*.md` with `source_citations` frontmatter (aggregates onto appendix slide)
- Audited by `viz-review deck <pptx-or-storyline>` against `consultant_deck_visual_style.md`

## Customizing slide types

After `outline`, edit `storyline.md` frontmatter `extra.slides[i]` to switch a slide's `type` from `support` → `stats-strip`, `quote`, `table`, `two-col`, etc. Then provide the type-specific fields:

```yaml
- n: 5
  type: stats-strip
  title: "Activation lift is 4–12 percentage points across signup channels."
  eyebrow: "KEY METRICS"
  stats:
    - {value: "11pp", unit: "ACTIVATION LIFT", caption: "Direct signup cohort"}
    - {value: "4pp",  unit: "ACTIVATION LIFT", caption: "Paid social cohort"}
    - {value: "$120K", unit: "ANNUAL UPLIFT", caption: "Triangulated"}
```

## Output

- `<engagement>/08-deliverable/<engagement>-deck.pptx` — primary deliverable
- Render to PDF for review: `soffice --headless --convert-to pdf <pptx>`
