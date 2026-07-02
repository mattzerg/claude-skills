---
id: pugh
name: Pugh Matrix (concept selection)
when_to_use:
  - Choosing between 3+ alternatives across multiple criteria
  - Engineering / design / vendor selection
  - When a baseline option exists and others are compared against it (+/0/-)
when_not_to_use:
  - Binary choices (use cost-benefit instead)
  - When criteria weights aren't agreed on (resolve weights first or use weighted-scoring)
anti_patterns:
  - Comparing concepts against the strongest concept instead of a neutral baseline
  - All "+1" rows — the baseline is wrong, or criteria don't differentiate
  - No iteration after the first matrix (Pugh expects 2–3 rounds, refining concepts)
chart_recipe: heatmap
---

Columns = options (incl. a baseline). Rows = criteria. Cells = +1 / 0 / -1 vs baseline. Sum columns to rank.
