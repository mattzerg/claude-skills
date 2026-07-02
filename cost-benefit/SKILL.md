---
name: cost-benefit
description: Cost-benefit analysis — NPV, IRR, ROI, payback period, with explicit assumption block + sensitivity to top driver. Reads a JSON spec (initial investment, cash flows per period, discount rate) or an inline CLI shorthand. Outputs `.md` narrative with assumptions table, NPV/IRR/ROI/payback computed, and a waterfall chart via `chart-builder`. Anchored on `MattZerg/_style/consultant_thinking_style.md`. Different from `scenario-modeler` (general what-if), `market-sizing` (TAM/SAM/SOM only), `cohort-analyzer` (backward retention). USE PROACTIVELY when Matt says "NPV", "ROI", "payback", "IRR", "cost-benefit", "investment case", "should we spend $X", "buy vs build", or before any spend decision. Every input carries a source tag or [needs-verification]. Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Cost-Benefit

Phase 2 numbers-layer. NPV/IRR/ROI/payback with assumptions surfaced + sensitivity.

## When to invoke

- Matt says "NPV", "ROI", "payback", "IRR", "investment case", "cost-benefit", "buy vs build", "is X worth $Y".
- Any spend decision where multiple costs and benefits land across periods.

## Modes

### `run` — JSON spec

```bash
python3 ~/.claude/skills/cost-benefit/run.py run spec.json \
  --engagement <slug> --mode <mode>
```

Spec JSON shape:
```json
{
  "name": "Zergboard self-serve docs build",
  "discount_rate": 0.12,
  "periods": ["FY26 Q1", "FY26 Q2", "FY26 Q3", "FY26 Q4"],
  "investment": -120000,
  "cash_flows": [10000, 35000, 65000, 110000],
  "assumptions": [
    {"label": "Activation rate lift", "value": "+4pp", "source": "[needs-verification]"},
    {"label": "Build cost", "value": "$120K", "source": "[source: Idan estimate 2026-05-15]"}
  ]
}
```

Writes:
- `<engagement>/05-analysis/cost-benefit/<name>.md`
- `.../charts/<name>-waterfall.png`

## Outputs

| Metric | Computed |
|---|---|
| NPV | `npf.npv(rate, [-invest] + cash_flows)` |
| IRR | `npf.irr([-invest] + cash_flows)` (skipped if no sign change) |
| ROI | `(sum(cash_flows) + investment) / -investment` |
| Payback | First period where cumulative ≥ 0 |

## Anti-patterns

- All-positive or all-negative cash flow series — IRR skipped + flagged
- No discount rate — defaults to 10% + flagged in narrative
- Any assumption without `source` — emits `[needs-verification]` and refuses client-mode deck
