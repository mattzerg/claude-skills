# Data-Product UI Patterns

Tuned for analytics dashboards, observability tools, growth reports, ops monitoring. **Not** for marketing pages, blog posts, or generic SaaS settings UI.

---

## Pattern 1 — Persistent left sidebar is the default

Analytics products have ≥4 distinct views (Overview, Pages, Sources, etc.). A topbar of tabs forces all views into one rank; a sidebar groups them and leaves room for sub-views.

**Use a sidebar when:**
- View count ≥ 4
- Operators move between views frequently in a session
- Some views need sub-items (e.g. Sources → Referrers / Campaigns / Direct)

**Use topbar-only when:**
- View count ≤ 3
- Mobile is the primary surface

**Hybrid (sidebar + view-local subnav)** is correct for products with 8+ views (Mixpanel, Amplitude). Don't reach for it before you need it.

**Exemplars:** Plausible (sidebar), GA4 (sidebar), Amplitude (sidebar+subnav), Datadog (sidebar+subnav), PostHog (sidebar+subnav).

**Anti-pattern:** No nav at all. Cards stacked down a single page = "PDF report" mode. The operator can't bookmark a view, can't deep-link to a dimension, can't find the analysis they did yesterday.

---

## Pattern 2 — Topbar carries scope, sidebar carries view

Two different concerns. Don't conflate.

**Scope** (what dataset am I looking at) — lives in topbar:
- Property / project / site picker
- Period picker
- Active filters (chips)
- Real-time indicator
- User menu

**View** (what dimension am I exploring) — lives in sidebar:
- Overview, Pages, Sources, Locations, Devices, Goals, Funnels, Real-time, Settings

When a user changes scope (period, filter), every view reuses that scope. When they change view, scope is preserved.

**Anti-pattern:** Period switcher buried inside a single card. If "last 30 days" only applies to ONE chart on the page, you've designed wrong — it should apply to every dimension visible.

---

## Pattern 3 — KPI strip is the first row, always

Plausible, GA4, Amplitude, Mixpanel — all put a horizontal strip of 4-6 topline numbers at the top of every view. This is non-negotiable for analytics products.

- Each KPI shows: label, value, comparison delta, optional sparkline
- Strip is sticky under the topbar (or near-sticky)
- Click a KPI → it becomes the metric plotted in the chart below

**Density:** 4 KPIs at narrow desktop, 5-6 at wide desktop. Each card ~120-200px wide. Don't pad them to 300px+ — that's the PDF-report tell.

**Anti-pattern:** stat cards as massive boxes with 60% whitespace. The numbers should *almost* feel cramped. Plausible's stat strip is ~60-90px tall total; aim there.

---

## Pattern 4 — Information density floor

A real analytics product gets dense. Targets at desktop ≥1280px:

- **4-column card grid** for dimension breakdowns (sources, pages, countries, browsers, etc.)
- **2-column** for richer cards (funnel, drill-down, map)
- **Card padding** ≤ 1rem, gutters ≤ 16px
- **List rows** at ~28-36px tall with bar+label+value+sparkline visible
- **Type:** body 13-14px, labels 11px uppercase tracked

Plausible's ratio is roughly 60/40 ink-to-paper at the dimensions block. GA4 is ~50/50. Anything below 40% ink reads as a marketing page.

**Anti-pattern:** Each card on its own row. Each card padded to 200px tall. Single-column layouts at 1440px wide. These are the dead giveaways of a dashboard built like a report.

---

## Pattern 5 — Drill-down: three valid models, pick one

When an operator wants to "see deeper" on a row:

| Model | Pattern | Best for | Exemplars |
|-------|---------|----------|-----------|
| **Filter** | Click row → adds a filter chip → all cards re-scope | Cross-dimension exploration ("show me Chrome users from US on mobile") | Plausible (signature) |
| **Drawer** | Click "↗" icon → side drawer with that one item's deep dive | One-shot "tell me about THIS row" | Datadog, Stripe |
| **Dedicated explore** | Click row → navigate to a sub-view with its own URL | Persistent, shareable analysis | Amplitude, Mixpanel |

**Pick one model per surface and stick to it.** Mixing them confuses operators ("does click drill or filter?").

If you have both filter-on-click AND a separate ↗ drawer (like ZergAlytics today), the affordances need to be visually distinct: row body click = filter, explicit ↗ button click = drawer.

---

## Pattern 6 — Comparison is structural, not a toggle

GA's signature feature is "compare to previous period" — it's not buried in a toggle, it's the default rendering. Plausible bakes it into every metric (delta arrow on every stat card).

**Strong:** Every metric shows current AND prior, with a delta. Comparison is on by default.
**Acceptable:** Toggle to flip comparison off, persisted in URL.
**Weak:** Comparison only visible in the chart, not in the dimension lists.

**For two-period compare on the chart**, render BOTH series as solid lines (different hues), not "current solid, prior dashed faded ghost." The ghost treatment reads as "you can ignore this" — which defeats the point.

---

## Pattern 7 — Real-time is a strip, not a view (until it isn't)

For most analytics products, "real-time" is a 1-row strip at the top of the Overview view: live visitor count + last-N-events stream.

When the product is *primarily* real-time (Datadog ops, Plausible's "Realtime" tab), promote it to a full view with its own URL.

**Anti-pattern:** Real-time data scattered across the dashboard. The operator can't tell what's live vs cached.

---

## Pattern 8 — Empty states tell operators what to do

Analytics products have a lot of empty states (new property, filtered to nothing, period with no events). Each one needs:

1. A line explaining WHY it's empty
2. The single most useful action ("Drop this `<script>` on your site to start collecting events")
3. NOT a generic "No data" + sad icon

For property-just-added empty states, surface the install snippet pre-filled with the property's domain (we already do this in the empty rollup — extend it everywhere).

**Anti-pattern:** Generic empty illustration with no actionable next step.

---

## 8 Failure Modes (anti-patterns checklist)

When auditing, confirm none of these are present:

1. **No nav at all** — cards stacked top-to-bottom on a single page
2. **Card-per-row** — each card on its own line at 1440px wide
3. **Whitespace bloat** — > 50% paper-to-ink, padding > 1.5rem on cards
4. **Period switcher per card** — scope concerns scattered across the page
5. **Mixed drill semantics** — same click does different things in different cards
6. **Comparison-as-afterthought** — prior period only on the chart, not on lists/cards
7. **Real-time scattered** — live numbers next to cached numbers with no visual distinction
8. **Generic empty states** — "No data" with no concrete next step

---

## Density sanity check (the 1280px test)

Open the dashboard at 1280×800. Count what you can see without scrolling:

- KPI strip (4-6 numbers): ✓
- Time-series chart: ✓
- At least 2 dimension breakdowns (e.g. Top pages + Top sources): ✓
- Filter chip area (when active): ✓

If the time-series chart pushes the dimension breakdowns below the fold, the chart is too tall (≤240px is normal). If only the KPI strip + chart are visible, you're in PDF-report mode.

---

## Per-view archetypes

Common analytics views and their canonical layouts:

### Overview
- KPI strip (4-6)
- Time-series chart (full width, ~240px tall)
- Dimension breakdowns (2 or 3 columns: Top pages, Top sources, Top countries)
- Real-time strip
- Goals + funnel (when present)

### Pages
- KPI strip filtered to current view
- Pages list (full width, dense, sortable, with sparklines per row)
- Sub-tabs: All / Entry / Exit / 404

### Sources
- KPI strip
- Sources list with bar+value+sparkline
- Sub-tabs: Referrers / UTM campaigns / Direct
- Optional: campaign-matrix table (utm_source × utm_medium)

### Locations
- World map (when worth the weight) OR country list
- Country / region / city tabs
- Sources-by-country crosstab (rich)

### Devices
- 3-up: Browser, OS, Device
- Each is a list with share-of-visitors %

### Goals
- Per-goal cards with conversion % and visitor count
- Time-series of conversions
- Goals editor (CRUD)

### Funnels
- Funnel viz (Sankey or step bars)
- Per-step drop-off %
- Funnel editor

### Real-time
- Live count (large)
- Live event stream
- Top live pages
- Top live sources
- Geo of live visitors

### Settings
- Property list (CRUD)
- API tokens
- Share links
- Team members
- Audit log link

---

## Layout spec template

For any view, define:

```
density:
  desktop_breakpoint: 1280px
  desktop_grid_cols: 4
  tablet_breakpoint: 768px
  tablet_grid_cols: 2
  mobile_grid_cols: 1
  card_padding: 12px 14px
  card_gutter: 16px
  body_font: 13px
  label_font: 11px uppercase 0.05em tracked

regions:
  topbar:
    - brand
    - property_picker
    - period_picker
    - filter_chips (when active)
    - user_menu
  sidebar:
    width: 200px
    items: [overview, pages, sources, locations, devices, goals, funnels, realtime, settings]
  main:
    max_width: 1440px (with margin auto, not stretched)
    KPI_strip: { sticky: true, height: 80px }
    chart_card: { height: 240px }
    breakdown_grid: { cols: 4, min_card_width: 280px }
```

This template is what `data-product-ui` outputs in Restructure or Greenfield mode.
