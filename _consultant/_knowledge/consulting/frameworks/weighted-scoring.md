---
id: weighted-scoring
name: Weighted Scoring Model
when_to_use:
  - Choosing between 3+ alternatives where criteria have unequal importance
  - When stakeholders disagree on weights — forces the conversation
  - Vendor selection, feature prioritization, hire decisions
when_not_to_use:
  - Two equally weighted criteria (use a 2x2)
  - When you have no quantitative score per criterion per option (use Pugh +/0/- instead)
anti_patterns:
  - Weights chosen after seeing scores (anchoring — confirms preordained answer)
  - All weights equal (then it's just an unweighted average — use 2x2 with axes that matter)
  - No sensitivity analysis (one weight change shouldn't flip the ranking)
chart_recipe: bar
---

Columns: option × {raw score per criterion, weighted score}. Final column = sum of weighted scores. Sensitivity: change top weight by ±30%, see if ranking flips.
