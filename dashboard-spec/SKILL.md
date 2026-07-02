---
name: dashboard-spec
description: Turn a business or product question into a concrete dashboard specification with KPIs, event definitions, chart lineup, segment cuts, freshness rules, owner notes, and decision thresholds. Use for growth dashboards, activation reporting, public analytics pages, internal operator views, and launch measurement readouts.
---


# Dashboard Spec

This skill turns "we need a dashboard for this" into a concrete measurement artifact. It defines what should be measured, why it matters, how it is computed, which events feed it, how fresh it must be, and what decision the dashboard should enable.

## When to invoke

- "What should be on this dashboard?"
- "Turn this growth / product question into KPI specs"
- "Define the metrics and event model for this reporting view"
- "What do we need to instrument before we can ship this dashboard?"
- Before building a public analytics page, internal ops dashboard, launch readout, activation board, or admin reporting surface

Use it when the problem is measurement design, not the UI layout alone. If the surface itself needs screen structure, pair with `ui-designer`.

## Core outputs

1. **Decision frame** — the business question the dashboard is meant to answer
2. **Metric stack** — north-star, supporting KPIs, guardrails, and diagnostic cuts
3. **Event / data spec** — required entities, events, dimensions, and joins
4. **Chart lineup** — what charts/tables belong on the page and why
5. **Operating rules** — freshness, owner, alerting, and data quality checks

## Modes

### Mode 1 — KPI spec

Use when the metrics themselves are unclear.

Output:
- KPI list
- definitions
- formula notes
- thresholds

### Mode 2 — Dashboard page spec

Use when the consumer and use case are known, but the page needs structure.

Output:
- section lineup
- chart/table recommendations
- segment cuts
- default date range and sort logic

### Mode 3 — Instrumentation gap audit

Use when a dashboard is blocked on missing data.

Output:
- missing events
- ambiguous definitions
- broken joins
- minimum viable measurement path

## Anchors

- `references/dashboard_patterns.md`
- `MattZerg/Writing/Zergboard Welcome Drip.md` for activation-event and admin-view shape
- `MattZerg/Writing/_thought-piece-template.md` for the public-dashboard narrative constraint
- `launch-ops` when dashboard readiness is part of launch readiness
- `cro-auditor` and `experiment-designer` when the dashboard is downstream of tests or funnel questions

## Working rules

- Start from the **decision**, not the chart. What action should change after someone reads this dashboard?
- Name one **north-star metric**, then separate supporting KPIs from guardrails and diagnostics.
- Define the **grain** of every metric: user, workspace, session, signup, email send, card, or event.
- Distinguish **leading indicators** from lagging outcomes.
- For every metric, specify the **source event(s)** and the main dimension cuts.
- Call out when the dashboard depends on data that is not yet instrumented or not trustworthy enough to expose.
- For public dashboards, separate what is safe to publish from what is only useful internally.

## Hard rules

- Do not ship a dashboard spec without naming the decision owner and read cadence.
- Do not define metrics with fuzzy verbs like "engagement" or "quality" unless the formula is explicit.
- Do not mix raw counts, rates, and cumulative totals without saying which each chart is showing.
- Do not recommend a dense dashboard when a single digest view would answer the actual question.
- Do not call instrumentation "good enough" if event names, actor identity, or timestamps are inconsistent.

## Relationship to sibling skills

- `ui-designer` — layout and interaction design for the reporting surface
- `experiment-designer` — tests that consume or produce the metrics this skill defines
- `launch-ops` — launch-day and post-launch readouts
- `cro-auditor` — conversion surfaces whose metrics need instrumentation and reporting
- `process-streamliner` — operating cadences built around recurring dashboard review
