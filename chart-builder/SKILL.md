---
name: chart-builder
description: Render Zerg-branded data visualizations. 12 recipes (bar, line, stacked-bar, waterfall, heatmap, scatter-2x2, marimekko, grouped-bar, slope-graph, dot-plot, bullet, small-multiples). Defaults — value labels ON, light y-gridline ON, smart axis formatter ($K/$M/%/int), two-accent palette. Outputs PNG + SVG + caption markdown. Five verbs — `render` (inline flags), `render-spec` (JSON spec), `batch` (manifest of specs in one call), `validate` (lint a spec before render), `recipes` (list available). Anchored on `MattZerg/_style/chart_style.md`. Different from `dashboard-spec` (defines what charts SHOULD exist, doesn't render), `data-pipeline` (loads + audits, doesn't render), `consultant-deck` (composes rendered charts onto slides). USE PROACTIVELY when Matt says "chart this", "waterfall on", "bar chart of", "heatmap", "2x2 scatter", "marimekko", "grouped bar", "slope graph", "dot plot", "bullet chart", "small multiples", or names a chart recipe by type. Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Chart Builder

Phase 2 numbers-layer foundation. Every other numbers skill (`cohort-analyzer`, `scenario-modeler`, `cost-benefit`, `market-sizing`, `workplan-skill`) renders through `chart-builder`.

## Defaults (Matt-approved 2026-05-29)

- **Value labels ON** (every bar/dot/line endpoint labeled with formatted value)
- **Light y-gridline ON** (Tufte-anchored — readers shouldn't eyeball numbers)
- **Smart axis formatter** (auto-chooses `$12K` / `$1.2M` / `7.2%` / `1,240` based on data scale + unit)
- **Two-accent palette** (cream `zerg-default` default, charcoal `zerg-dark` via `--palette dark`)
- Opt-out via `--no-labels`, `--no-grid`

## Recipes (12)

| Recipe | Use for | Inline-flag-renderable |
|---|---|---|
| `bar` | Categorical comparison | ✅ |
| `line` | Time-series, trend, multi-series | ✅ |
| `stacked-bar` | Categorical with sub-decomposition | ✅ |
| `waterfall` | Bridge analysis (start → contributions → end) | ✅ |
| `heatmap` | Matrix scoring (Porter, Pugh, segment × variant) | spec only |
| `scatter-2x2` | 2x2 prioritization with quadrant labels (DO NOW / PLAN / BACKLOG / KILL) | spec only |
| `marimekko` | Share-of-segment vs segment-size | spec only |
| `grouped-bar` | Before/after by segment; multi-category × multi-series | ✅ |
| `slope-graph` | Two time points, change as slope (Tufte favorite for 5–15 items) | spec only |
| `dot-plot` | Horizontal alternative to bar with better ink ratio (sorted + banded) | ✅ |
| `bullet` | Target vs actual vs qualitative bands | spec only |
| `small-multiples` | Faceted grid of mini charts | spec only |

## Verbs

### `render` — inline flags (fastest)

```bash
python3 ~/.claude/skills/chart-builder/run.py render bar \
  --labels "Q1,Q2,Q3,Q4" --values "12000,18000,21000,29000" \
  --ylabel "MRR ($)" --target 30000 \
  --caption "MRR grew 142% across Q1–Q4." \
  --out ~/Downloads/mrr-bar.png
```

Supports `bar`, `line`, `stacked-bar`, `waterfall`, `grouped-bar`, `dot-plot` inline. Others require `render-spec`.

### `render-spec` — JSON spec

```bash
python3 ~/.claude/skills/chart-builder/run.py render-spec spec.json --out chart.png
```

Spec format:
```json
{
  "recipe": "slope-graph",
  "items": [
    {"label": "Onboarding", "before": 28, "after": 47},
    {"label": "Pricing",    "before": 35, "after": 32}
  ],
  "highlight": ["Onboarding"],
  "left_label": "Pre",
  "right_label": "Post",
  "caption": "Onboarding mentions grew 68% post-launch.",
  "palette": "default"
}
```

Auto-validates before render. Use `--force` to bypass HIGH findings.

### `batch` — multiple charts in one call

```bash
python3 ~/.claude/skills/chart-builder/run.py batch manifest.json
```

Manifest = JSON array of specs each carrying its own `out` path. Saves orchestrator turns when rendering many charts for a deck.

### `validate` — spec lint

```bash
python3 ~/.claude/skills/chart-builder/run.py validate spec.json
```

Catches: missing required fields, list-length mismatches, pathological data ranges (flat series, negative stacked-bar, degenerate 2x2), illegal flag combos.

### `recipes` — list available

```bash
python3 ~/.claude/skills/chart-builder/run.py recipes
```

## Shared flags

| Flag | Effect |
|---|---|
| `--no-labels` | Suppress value labels |
| `--no-grid` | Suppress gridlines |
| `--target N` | Reference line at `N` with auto-formatted label |
| `--baseline N` | Reference line at `N` (mid-gray) |
| `--highlight NAME` (line) | Highlight one series, mute others |
| `--highlight-idx N` (bar/dot-plot) | Highlight one bar/dot at index N |
| `--accessible` | Switch to Okabe-Ito color-blind-safe palette |
| `--semantic` (bar) | Positive = green, negative = primary accent |
| `--palette default\|dark` | Cream (default) or charcoal |
| `--currency $` | Currency symbol for $-formatted values |
| `--caption "..."` | Action-title caption written to `.caption.md` sidecar |

## Output

- `<out>.png` — 180dpi render
- `<out>.svg` — vector
- `<out>.caption.md` — action-title caption + recipe + palette (for `consultant-deck` to read directly)

## Anchoring

- Brand palette from `~/.claude/skills/document-styling-skill/brand.md`
- Tufte chart conventions in `MattZerg/_style/chart_style.md`
- Cream (`zerg-default`) default — Zstack/non-technical surfaces
- Charcoal (`zerg-dark`) for Zerg-parent / heavy-technical content

## Composition

- Reads `data-pipeline` `.parquet` outputs indirectly (via callers like `cohort-analyzer`)
- Outputs are embedded by `consultant-deck` as slide-body images
- Audited by `viz-review chart <png>` against `chart_style.md` rules
