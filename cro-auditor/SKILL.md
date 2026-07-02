---
name: cro-auditor
description: Audit a marketing or signup surface for conversion friction, proof gaps, CTA hierarchy issues, experiment opportunities, and measurement blockers. Use for homepages, pricing pages, signup funnels, onboarding entry points, waitlists, and launch landing pages. Different from fakematt-feedback (broad UX heuristics across page types) — cro-auditor is FUNNEL/CONVERSION-focused on marketing surfaces. Different from funnel-analyzer (which queries actual Zergalytics event data for measured drop-off rates) — cro-auditor is HEURISTIC; pair them (cro-auditor for hypotheses → funnel-analyzer for measurement).
---


# CRO Auditor

This skill reviews a conversion surface as a funnel, not just as a piece of copy or design. It names what is blocking the next action, what proof is missing, where measurement is blind, and which tests are worth running.

## When to invoke

- "Why is this page not converting?"
- "Audit this homepage / pricing page / signup flow"
- "What experiments should we run here?"
- "Where is the friction in this funnel?"
- Before shipping a launch landing page, pricing update, waitlist page, or signup/onboarding entry point

Use it for public marketing pages, pricing tables, gated CTA paths, signup flows, onboarding entry screens, and upgrade surfaces. For product usability beyond conversion, pair with `fakematt-feedback`.

## Core outputs

1. **Conversion audit** — friction points, hierarchy problems, proof gaps, trust gaps
2. **Funnel map** — traffic source → page → CTA → form → activation handoff
3. **Measurement blockers** — missing events, broken endpoints, unclear success metrics, attribution blind spots
4. **Experiment slate** — test ideas with hypothesis, primary metric, guardrail, and likely effort
5. **Fix ranking** — quick wins vs structural changes

## Modes

### Mode 1 — Page audit

Use for a single page or single step in a funnel.

Output:
- above-the-fold audit
- CTA hierarchy
- proof / trust audit
- friction list

### Mode 2 — Funnel audit

Use when the issue may live across multiple steps.

Output:
- step-by-step funnel map
- dominant drop-off risks
- handoff mismatches
- measurement gaps

### Mode 3 — Experiment design

Use when the page is good enough to test rather than rewrite blindly.

Output:
- ranked test backlog
- hypothesis shape
- success metric and kill rule

## Anchors

This skill draws its voice and pattern catalog from:

- **Voice fingerprint:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_considered_voice.md` (considered-register voice for CRO findings — sober, evidence-cited, no exclamation, no hype)
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` (cite findings by pattern slug)
- **Domain corpus:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/cro_feedback_corpus.md` (CRO-specific exemplars + anti-patterns)
- **Catalog patterns to cite by slug** (Section E CRO): missing-cta, capability-claim-unverified, proof-gap, cta-hierarchy, shipped-vs-roadmap-visibility, friction-stack, measurement-blind, cta-promise-must-match-form-shape, triple-cta-dilution, mid-page-cta-on-long-scroll, canonical-signup-infra-required, pricing-page-roadmap-transparency, trust-signal-table-shape

Read these BEFORE producing output. Cite patterns by slug from the catalog.

Sibling references:

- `references/cro_patterns.md`
- `landing-page-skill` outputs when competitor comparison is useful
- `fakematt-feedback` findings when the surface already has product/UX audit data
- `experiment-tracker` and `growth-dashboard` as downstream systems for tests and metrics

## Working rules

- Start from the **next user action**. What exact commitment should this surface produce?
- Separate **message problems** from **flow problems** from **measurement problems**.
- Treat missing proof, missing trust, and weak CTA hierarchy as first-class blockers.
- Call out when the problem cannot be diagnosed honestly because instrumentation is missing.
- Prefer a small number of high-signal tests over giant speculative backlogs.
- For signup and onboarding entry points, define the handoff to activation explicitly. A “conversion” that hands to an empty product surface is not a win.

## Hard rules

- Do not recommend experiments without naming a success metric and guardrail.
- Do not treat more copy as a default fix when the issue is weak hierarchy or broken flow.
- Do not praise conversion surfaces without checking proof, trust, CTA clarity, and event instrumentation.
- Do not confuse generic marketing best practices with the actual wedge of the product.

## Relationship to sibling skills

- `landing-page-skill` — competitor research and page generation
- `experiment-tracker` — register and govern the tests this skill proposes
- `growth-dashboard` — measurement destination for the metrics this skill depends on
- `fakematt-copyedit` — polish copy after the conversion structure is sound
- `fakematt-feedback` — broader UX/product audit when the issue extends beyond marketing conversion
