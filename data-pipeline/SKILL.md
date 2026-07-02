---
name: data-pipeline
description: Load → clean → quality-audit → describe a tabular dataset (CSV / Parquet / JSON). Outputs cleaned `.parquet`, a `.md` quality-audit narrative (missing values, outliers, distributions, schema), and a `.json` schema. Anchored on `MattZerg/_style/consultant_thinking_style.md`. Different from `chart-builder` (renders charts but doesn't ingest data), `cohort-analyzer` / `scenario-modeler` / `cost-benefit` / `market-sizing` (analyze cleaned data — they read this skill's output). USE PROACTIVELY when Matt names a CSV / dataset / data file, says "clean this", "load this", "audit the data", "describe the dataset", "schema for", "data quality", or before any cohort / scenario / sizing analysis runs. Refuses to silently drop rows — surfaces every modification in the audit narrative. Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Data Pipeline

Phase 2 numbers-layer foundation. Every other numbers skill reads this skill's `.parquet` output.

## When to invoke

- Matt drops a CSV/Parquet/JSON path or URL.
- Before `cohort-analyzer` / `scenario-modeler` / `cost-benefit` / `market-sizing` run on raw data.
- When data quality is in question and Matt wants an audit before analysis.

## Modes

### `load` — load → clean → audit → describe

```bash
python3 ~/.claude/skills/data-pipeline/run.py load <path-or-url> \
  --engagement <slug> --mode <mode> [--slug <name>] \
  [--date-cols col1,col2] [--id-cols user_id] [--drop-cols col]
```

Writes to `<engagement>/05-analysis/data/<slug>-clean-YYYY-MM-DD.parquet`, audit `.md`, and `.json` schema.

### `describe` — re-emit describe from existing parquet

```bash
python3 ~/.claude/skills/data-pipeline/run.py describe <parquet-path>
```

## Audit narrative

- **Schema**: column → dtype → non-null count → sample values
- **Missing values**: per-column missing-rate + per-row missing-pattern
- **Outliers**: per-numeric IQR-based outlier count + top 5 by magnitude
- **Distributions**: per-numeric mean / median / p25 / p75 / std + skew flag
- **Duplicates**: id-column dup count (if `--id-cols` provided)
- **Modifications**: every transform applied — type coercions, drops, renames — listed inline

## Anti-patterns

- Dropping rows without surfacing in audit (this skill refuses)
- Renaming columns without a `_orig` sidecar (this skill keeps both)
- Silently coercing types (audit lists every coercion)
