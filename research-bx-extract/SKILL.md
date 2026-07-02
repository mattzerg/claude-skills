---
name: research-bx-extract
description: Extract effect sizes, sample sizes, and moderators from a screened paper corpus. Outputs a meta-analytic CSV ready for research-bx-meta. Trigger phrases — "extract effect sizes", "code the included papers", "build the meta CSV", "run effect-size extraction".
---

# Research / Behavioral-Sciences — Effect-Size Extraction

Stage 3 of meta-analysis pipeline. Takes screened-included PDFs and produces a CSV of effect sizes + moderators ready for `research-bx-meta`.

## Modes

- `pdf-to-row <pdf-path>` — extract effect sizes from a single PDF (tabula-py + LLM-assisted manual verification).
- `corpus <screened-list>` — iterate full included list, building the CSV.

## Output schema (CSV)

```csv
paper_id,bibtex_key,year,N,paradigm,outcome_var,effect_metric,effect_size,SE,CI_low,CI_high,moderators,extractor,verified
```

## Hard rules

- Every row must trace to a verified bibtex key (via `research-bx-audit`).
- Effect sizes that cannot be extracted from the paper text → flag for manual entry, do not invent.
- All extractions are dual-coded for meta-analysis pipeline (single-coded for card seeding is acceptable).
- Preferred metrics: Cohen's d, r, log(OR). Convert at the meta-analysis stage.

## Implementation status

**v0 stub.** Phase 4 sprint deliverable. Manual extraction acceptable for Phase 2 card seeding.

## Pairs with

- `research-bx-screen` — provides the included list this skill extracts from.
- `research-bx-meta` — consumes this skill's CSV output.
- `research-bx-audit` — validates row-by-row that bibtex keys are verified.
