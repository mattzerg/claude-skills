---
id: raci
name: RACI Matrix
roles: ["Responsible", "Accountable", "Consulted", "Informed"]
when_to_use:
  - Multi-person workstream where accountability is fuzzy
  - Cross-team initiative spanning functions
  - Pre-launch ops planning (who decides, who executes, who reviews)
when_not_to_use:
  - Two-person tasks (overhead > value)
  - Single-decision contexts where one person owns it
  - Pure individual-contributor work
anti_patterns:
  - Multiple "A"s on the same row (only one person is Accountable — the rest are R, C, or I)
  - Empty Accountable column (the most common failure)
  - Same person across all four roles on one row (no real distinction)
chart_recipe: null
---

Rows = activities. Columns = people. Each row has exactly one A. R can be 1–N. C and I can be 0–N. Empty cells are valid.
