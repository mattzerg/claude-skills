---
name: ui-designer
description: Design product UI structure for screens, flows, dashboards, settings, and internal tools BEFORE pixels harden. Different from data-product-ui (analytics-screen-specific patterns), dashboard-spec (KPI selection + layout for status dashboards), and ux-flow-mapper (multi-screen journey + drop-off annotations) — ui-designer owns the single-screen structure pass. USE PROACTIVELY when designing a new internal tool, admin/settings surface, dashboard, or product screen, or when Matt asks "how should this screen lay out", "what goes on this page", or "structure the UI for X". Pairs with ux-flow-mapper (multi-screen) and webpage-layout (post-build audit).
---


# UI Designer

This skill designs the interface before pixels harden. It is for shaping product UI structure, not merely critiquing an existing screen.

## When to invoke

- "Design this screen / flow / dashboard"
- "What should the UI for this feature look like?"
- "Help me structure onboarding / settings / table UX / admin UI"
- "Turn this product idea into a sane interface"
- When the team has requirements, rough notes, or product intent but not a coherent UI shape

Use it for product screens, onboarding flows, dashboards, internal tools, admin surfaces, and operational interfaces. For marketing landing pages, prefer `landing-page-skill`.

## Core outputs

1. **Screen architecture** — page purpose, primary action, information hierarchy
2. **Wireframe spec** — sections, regions, component choices, ordering
3. **State model** — empty, loading, success, error, permission, edge-case states
4. **Interaction notes** — what changes inline, what opens a modal, what deserves progressive disclosure
5. **Handoff brief** — implementation notes, data dependencies, analytics hooks, unresolved questions

## Modes

This skill takes a `--mode` parameter that selects between design output and review output. Default selection is input-driven:

- Default `--mode review` if input is a URL, Figma link, screenshot, or rendered screen
- Default `--mode design` if input is a prose brief, requirements doc, or product notes without an existing UI

### `--mode design`

Use when the user is designing from scratch or rethinking a screen's structure. Produces design output — mockups, screen structure, IA recommendations.

Pulls voice cues from `matt_fast_voice.md` (this is generative work, weight fast/decisive register) plus the patterns catalog. Outputs:
- screen architecture (purpose, primary action, hierarchy)
- wireframe spec (sections, regions, components, ordering)
- state model (empty, loading, success, error, permission, edge-case)
- interaction notes (inline / modal / progressive disclosure)
- handoff brief (data deps, analytics hooks, open questions)

Sub-flavors:
- **New flow** — flow overview + screen-by-screen + primary/secondary actions
- **Screen redesign** — current problems + revised hierarchy + component-level rewrite
- **Engineer handoff** — region/component map + states + interaction contract + implementation questions

### `--mode review`

Use when a screen exists and needs critique against the UI density corpus. Produces severity-tagged findings citing pattern slugs from `feedback_patterns_catalog.md` and density-specific patterns from `ui_density_feedback_corpus.md`.

Pulls voice from `matt_considered_voice.md` (review = considered register). Outputs:
- HIGH / MED / LOW findings with cited pattern slug
- per-finding concrete fix recipe (not "improve hierarchy" — actual change)
- density/whitespace verdict drawing on `ui_density_feedback_corpus.md`
- pass/fail signal at top

## Anchors

This skill draws its voice and pattern catalog from:

- **Voice fingerprint (review mode):** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_considered_voice.md`
- **Voice fingerprint (design mode):** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_fast_voice.md`
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md`
- **Domain corpus (heavy emphasis):** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/ui_density_feedback_corpus.md`
- **Catalog patterns to cite by slug** (Section B UI / product design): main-sticking-action, ia-ordering, smart-defaults, blank-canvas-friction, library-recurring, ui-weight-vs-importance, scope-grouping, natural-language-commands, density-vs-padding
- **Catalog patterns to cite by slug** (Section E CRO / marketing): single-cta, hero-clarity

Read these BEFORE producing output. Cite patterns by slug from the catalog. Density/whitespace findings in particular should ground in `ui_density_feedback_corpus.md`.

Supporting references:
- `references/ui_design_patterns.md`
- product notes, roadmap docs, copy docs, screenshots, and any existing design system artifacts the user provides
- sibling skills:
  - `fakematt-feedback` after a design exists and needs critique
  - `graphic-layout` for rendered static assets
  - `landing-page-skill` for marketing pages rather than product UI

## Working rules

- Start with the **job of the screen**. What decision or action is this UI helping complete?
- Design around the **primary action** first, then supporting context.
- Treat **state design** as part of the UI, not a cleanup pass.
- Prefer progressive disclosure over dumping every option onto the first surface.
- Keep data-dense interfaces scannable: stable columns, clear grouping, explicit filters, visible status.
- For operator and dashboard surfaces, always specify the default sort, queue state, success metric, and obvious next action.
- Name when a problem is actually **workflow** or **permissioning**, not just layout.

## Hard rules

- Do not jump straight to visual polish if hierarchy and state logic are still unclear.
- Do not overuse modals, tabs, or hidden controls when inline structure would reduce memory load.
- Do not describe a UI without saying what happens in empty, error, and loading states.
- Do not use generic “modern SaaS dashboard” filler as a substitute for real interaction design.

## Relationship to sibling skills

- `fakematt-feedback` — review an existing UI
- `process-streamliner` — when the core issue is operational flow rather than screen layout
- `landing-page-skill` — marketing surface design
- `fakematt-copyedit` — copy polish once the interface structure exists
