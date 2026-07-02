---
name: scenario-modeler
description: Scenario + sensitivity modeling — what-if sweeps, tornado charts, simple Monte Carlo. Reads a model spec (Python function string + parameter ranges), runs base / low / high cases, executes parameter sweeps, optionally simulates N draws with numpy. Outputs `.md` narrative with assumptions table + sensitivity chart via `chart-builder`. Anchored on `MattZerg/_style/consultant_thinking_style.md`. Different from `cost-benefit` (NPV/ROI specifically, with assumptions-block convention), `cohort-analyzer` (backward retention from data), `funnel-analyzer` (measured funnel). USE PROACTIVELY when Matt says "scenario", "sensitivity", "what-if", "tornado", "Monte Carlo", "best case worst case", "range of outcomes", or before any forward-looking decision that depends on parameter assumptions. Surfaces which parameter dominates (sensitivity). Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Scenario Modeler

Phase 2 numbers-layer. Forward-looking parameter modeling with sensitivity + scenarios.

## When to invoke

- Matt says "scenario", "sensitivity", "what-if", "tornado", "best/worst case", "Monte Carlo", "range of outcomes".
- Forward-looking decision with multiple uncertain parameters.

## Modes

### `run` — JSON spec file

```bash
python3 ~/.claude/skills/scenario-modeler/run.py run spec.json \
  --engagement <slug> --mode <mode> [--monte-carlo 1000]
```

Spec JSON shape:
```json
{
  "name": "Pro→Bundle expansion",
  "outcome": "Annual revenue uplift ($K)",
  "model": "(pro_users * upgrade_rate * (bundle_price - pro_price) * 12) / 1000",
  "params": {
    "pro_users":    {"base": 1200, "low": 800, "high": 1800},
    "upgrade_rate": {"base": 0.15, "low": 0.08, "high": 0.25},
    "bundle_price": {"base": 19, "low": 19, "high": 19},
    "pro_price":    {"base": 9, "low": 9, "high": 9}
  }
}
```

Writes:
- `<engagement>/05-analysis/scenarios/<name>.md` — base/low/high + sensitivity rank
- `.../charts/<name>-tornado.png` — tornado chart of param sensitivity
- (`--monte-carlo N`) `.../charts/<name>-distribution.png` — outcome histogram

## Anti-patterns

- Model with no named parameters (all literals) — refused
- Same low + high for every param (no real sensitivity) — flagged
- Monte Carlo with no specified distribution (uniform default) — flagged in narrative
