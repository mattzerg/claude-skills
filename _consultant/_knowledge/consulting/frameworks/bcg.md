---
id: bcg
name: BCG Growth-Share Matrix
axes: {x: "Relative market share", y: "Market growth rate"}
quadrants: ["Star (high growth, high share — invest)", "Cash Cow (low growth, high share — milk)", "Question Mark (high growth, low share — decide)", "Dog (low growth, low share — divest)"]
when_to_use:
  - Multi-product portfolio company allocating capital across SBUs
  - Considering a divestiture or sunset of a product line
  - Visualizing where cash is generated vs consumed across a portfolio
when_not_to_use:
  - Single-product company (no portfolio)
  - Software companies where "relative market share" is poorly defined
  - Markets where category leader changes annually (instability invalidates the axes)
anti_patterns:
  - Renaming "Dog" without re-examining the underlying call
  - Plotting share against absolute growth (must be relative — competitor #2 vs #1)
  - Allocating equal investment to every quadrant
chart_recipe: scatter-2x2
---

Bubble size = revenue. Bubbles in different quadrants get different capital-allocation rules, not the same.
