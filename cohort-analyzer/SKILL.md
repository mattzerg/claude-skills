---
name: cohort-analyzer
description: Cohort analysis — retention curves, Day-N retention, vintage matrices. Reads a cleaned event dataset (output of `data-pipeline`), groups by cohort key (signup-week / acquisition-channel / etc.), computes retention per period, renders curves via `chart-builder`. Anchored on `MattZerg/_style/consultant_thinking_style.md`. Different from `funnel-analyzer` (single-funnel step-by-step drop-off — uses Zergalytics events), `scenario-modeler` (forward-looking what-ifs), `data-pipeline` (just loads + audits). USE PROACTIVELY when Matt says "cohort", "retention curve", "Day-N retention", "vintage", "signup cohorts", "weekly cohorts", or before drawing any retention conclusion. Refuses to render with fewer than 3 cohorts. Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Cohort Analyzer

Phase 2 numbers-layer. Reads `data-pipeline` `.parquet` output; produces retention curves + vintage matrix.

## When to invoke

- Matt says "cohort", "retention", "Day-N", "weekly cohorts", "vintage", "signup retention".
- A hypothesis-tree row needs cohort evidence ("Is activation degrading over time?").

## Modes

### `analyze` — load + cohort + chart

```bash
python3 ~/.claude/skills/cohort-analyzer/run.py analyze <parquet-path> \
  --user-col user_id --event-col event_name --time-col occurred_at \
  --signup-event signup --target-event activated \
  --period week --horizon 8 \
  --engagement <slug> --mode <mode>
```

Writes:
- `<engagement>/05-analysis/cohort-retention-YYYY-MM-DD.md` — narrative
- `<engagement>/05-analysis/charts/cohort-retention-curves.png` — overlay
- `<engagement>/05-analysis/charts/cohort-vintage-matrix.png` — heatmap

## Anti-patterns

- Fewer than 3 cohorts (skill refuses)
- Cohort size below 30 — flagged as "low-n"
- Horizon longer than data permits — clamped + flagged
