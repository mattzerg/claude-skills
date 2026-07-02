---
name: data-product-ui
description: Design analytics-product UI — sidebar app shells, multi-view structure, info-dense card grids, drill-down architecture, comparison overlays, real-time strips. Anchored on Plausible / GA4 / Amplitude / Mixpanel / PostHog / Datadog. Sibling to `ui-designer` (generic product UI) and `dashboard-spec` (KPI selection); this one owns the *structural* patterns specific to data products. Use when designing or auditing an analytics dashboard, observability tool, growth report, or any UI whose primary job is "operator scans many dimensions of one dataset."
---

# Data Product UI

Analytics products fail in two recognisable ways. **Failure mode A** is the "PDF report" — cards stacked down a single page, low density, sparse whitespace, no navigation. **Failure mode B** is the "kitchen sink" — every dimension fights for attention, no hierarchy, the operator can't find anything.

This skill is a pattern catalog tuned to avoid both. It pairs with `ui-designer` (which handles generic product UI) and `dashboard-spec` (which picks WHICH metrics to show); this one owns HOW the analytics surface is structured.

## When to invoke

- Designing a new analytics product UI from scratch
- Auditing an existing analytics dashboard against industry conventions
- "Why does my dashboard feel like a report and not an app?"
- Reorganising a single-page dashboard into a multi-view product
- Picking the right info-density / spacing / column counts for a data canvas

Use this skill ONLY for surfaces whose job is operator-scans-many-dimensions-of-one-dataset. For marketing pages → `landing-page-skill`. For generic product UI → `ui-designer`. For business-question → KPI selection → `dashboard-spec`.

## Modes

### Mode 1 — Audit

Given a screenshot, URL, or markup, score the surface against `references/dp_ui_patterns.md` and emit findings:

- Severity-tagged: **HIGH** (architectural failure), **MED** (density / hierarchy), **LOW** (polish)
- Each finding cites a pattern + a concrete exemplar
- Output is a punch list with fix recipes — never modifies code

### Mode 2 — Restructure

Given an existing dashboard, propose the redesign:

1. App shell decision (sidebar / topbar-only / hybrid)
2. View graph (which dimensions get their own view vs nest as cards)
3. Per-view layout (KPI strip, chart row, dimension cards)
4. Drill architecture (filter chips vs side drawer vs dedicated view)
5. Real-time / comparison / segment overlays
6. Empty states + loading patterns

### Mode 3 — Greenfield

For new analytics products without an existing UI. Output:

- App-shell wireframe
- Default view inventory
- KPI hierarchy
- Filter / segment / comparison model
- Density rules per breakpoint

## Core outputs

Every mode emits at minimum:

1. **App-shell decision** — sidebar / topbar / hybrid + reasoning
2. **View map** — list of named views with their primary job
3. **Density spec** — cards per row × breakpoint, padding scales, type sizes
4. **Filter / drill model** — how operators move from broad to narrow
5. **Comparison model** — period-over-period / segment-over-segment treatment
6. **Anti-pattern check** — confirm none of the 8 failure modes from `dp_ui_patterns.md` are present

## Anchors

- `references/dp_ui_patterns.md` — the pattern catalog (read this every invocation)
- `references/exemplars.md` — Plausible / GA4 / Amplitude / Mixpanel / PostHog / Datadog reference
- Sibling skills:
  - `ui-designer` — generic product UI structure
  - `dashboard-spec` — KPI / metric / segment selection
  - `cro-auditor` — funnel / conversion focus
  - `webpage-layout` — empirical 6-axis scoring of marketing surfaces

## Guardrails

- Never claim a pattern is "best" — claim it's used by N exemplars and works for M operator job
- Don't over-prescribe density. A funnel-debugger UI needs different density than an executive summary
- For each recommendation, identify the operator job it serves (decide / monitor / explore / explain)
- Refuse to redesign without naming the operator and their job — generic redesigns drift toward bland

## Output shape

```markdown
## App shell
**Decision:** [persistent left sidebar | top tabs | hybrid]
**Why:** [reasoning grounded in operator job + view count]

## View map
| View | Primary job | Default density | Key cards |
|------|-------------|-----------------|-----------|
| ... | ... | ... | ... |

## Density spec
- Desktop ≥1280: 4-column card grid, 16px gutter, 13px body, 11px label uppercase
- Tablet 768–1279: 2-column, 14px gutter
- Mobile <768: stack, full-width

## Filter / drill model
[chips at top + global scope | side drawer per row | dedicated explore view]

## Comparison model
[overlay on chart | dedicated compare view | toggle in nav]

## Anti-patterns avoided
- ✅ no PDF-report stacking
- ✅ density floor met
- ⚠️ ... (call out partial misses)
```
