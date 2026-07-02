---
name: research-bx-meta
description: Run the meta-analytic stats backend on a CSV of extracted effect sizes. Outputs forest plot, I², τ², funnel plot, Egger test, and p-curve. Pairs with research-bx-write for preprint drafting. Trigger phrases — "run the meta-analysis", "build the forest plot", "compute heterogeneity", "p-curve analysis".
---

# Research / Behavioral-Sciences — Meta-Analytic Stats

Stage 4 of the meta-analysis pipeline. Takes the CSV from `research-bx-extract` and runs the meta-analytic stats. Outputs results to the experiment folder (`MattZerg/Research/Experiments/<slug>/results/`).

## Backend

Default: R (metafor + dmetar). Fallback: Python (PythonMeta + statsmodels).

Decision deferred to Phase 4 implementation — see plan open question #2.

## Outputs

- `forest-plot.png` (with study weights, CIs, pooled effect)
- `funnel-plot.png` (with Egger test result)
- `p-curve.png`
- `results.md` (numeric summary: pooled effect, CI, I², τ², Egger p, p-curve evidence statement)
- `sensitivity/` (leave-one-out, trim-and-fill, robust-variance variants)

## Hypotheses-locked

Refuses to run if `hypotheses.md` is missing or modified after lock timestamp. Prevents post-hoc hypothesis fitting.

## Implementation status

**v0 stub.** Phase 4 deliverable.

## Pairs with

- `research-bx-extract` — input CSV.
- `research-bx-write` — consumes results.md and plots.
- `research-bx-audit` — validates that every cited effect size traces to a verified paper.
