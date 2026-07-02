---
name: experiment-designer
description: Turn a growth, product, pricing, onboarding, or launch idea into a disciplined experiment plan with hypothesis, variants, metric, thresholds, sample target, risks, and decision rules. Use for CRO tests, onboarding experiments, pricing tests, landing-page tests, lifecycle experiments, and feature-launch validation.
---


# Experiment Designer

This skill converts "we should test this" into a governed experiment. It defines the hypothesis, what changes between control and treatment, what metric decides the outcome, when to kill it, and what evidence should count as a real learning.

## When to invoke

- "Should we test this idea?"
- "Write the experiment plan"
- "Turn this growth idea into a real test"
- "What metric and kill rule should we use?"
- Before running CRO, pricing, onboarding, email-lifecycle, signup, or launch-distribution tests

Use it when the team needs a real test design, not just a backlog of ideas. If the surface itself needs audit first, pair with `cro-auditor` or `fakematt-feedback`.

## Core outputs

1. **Hypothesis** — if X changes, Y moves, because Z
2. **Variant design** — control, treatment, and traffic or rollout plan
3. **Measurement plan** — success metric, guardrail, sample target, kill date
4. **Risk model** — confounders, dependencies, and failure modes
5. **Decision rules** — scale, kill, rerun, or mark inconclusive

## Modes

### Mode 1 — New experiment

Use when the idea is still rough.

Output:
- cleaned hypothesis
- strongest testable variant
- metric and threshold design

### Mode 2 — Experiment rewrite

Use when an existing test draft is vague or under-specified.

Output:
- tightened hypothesis
- removed ambiguity
- corrected metric / threshold logic

### Mode 3 — Readout prep

Use when the test exists and the team needs decision discipline before the read.

Output:
- read template
- verdict logic
- follow-on test recommendations

## Anchors

- `references/experiment_patterns.md`
- `MattZerg/Projects/Zerg-Production/Growth/experiments/_template.md`
- `MattZerg/Projects/Zerg-Production/Growth/experiments/exp-026.md` as a live example
- `cro-auditor` when the experiment comes from conversion findings
- `dashboard-spec` when the deciding metric or event path is not yet defined

## Working rules

- Force one primary **success metric**. Supporting metrics are allowed; multiple success metrics are not.
- Specify the **exact difference** between control and treatment. If the change is fuzzy, the test is not ready.
- Name the **mechanism** in the hypothesis. Why should this change move the metric?
- Separate **success threshold**, **kill threshold**, and **sample size target**.
- Name the main **confounders**: seasonality, traffic quality, product instability, launch overlap, attribution blind spots.
- Prefer tests that can produce a real decision within a bounded time window.
- When the experiment depends on instrumentation that does not exist, block it until `dashboard-spec` or an event plan closes the gap.

## Hard rules

- Do not propose an experiment without a kill date or stop condition.
- Do not let a test hinge on a vague metric like "engagement" unless the event formula is explicit.
- Do not treat implementation effort as zero; call out when the variant requires product, copy, design, or data work.
- Do not recommend simultaneous overlapping tests on the same bottleneck unless the user explicitly wants a multivariate or staged design.
- Do not confuse a marketing campaign with an experiment if no controlled comparison exists.

## Relationship to sibling skills

- `cro-auditor` — identifies the funnel problems worth testing
- `dashboard-spec` — defines metrics and instrumentation for the read
- `launch-ops` — governs timing when the test overlaps a launch
- `review-pack` — routes an artifact to the right audits before the test is declared ready
