---
name: framework-library
description: Apply a named strategic framework — 2x2, Porter's Five Forces, BCG growth-share, value chain, Business Model Canvas, RACI, Pugh matrix, weighted scoring, SWOT — to a slice of an issue tree or to a standalone question. Three modes — `render` (build the filled framework), `suggest` (pick 2–3 frameworks that fit a question), `audit` (lint an existing framework artifact). Recipe cards at `_consultant/_knowledge/consulting/frameworks/`. Each card has `when_to_use` / `when_not_to_use` / `anti_patterns` — skill refuses to render when `when_not_to_use` matches the input. Different from `scqa-framing` (frames root Question), `issue-tree` (MECE decomposition), `hypothesis-tree` (initial answer per leaf), `minto-pyramid` (final answer-first synthesis). USE PROACTIVELY when Matt says "Porter on", "BCG matrix", "build a 2x2", "value chain", "Pugh matrix", "weighted scoring", "SWOT", "business model canvas", "RACI", "which framework fits". Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Framework Library

Phase 1 thinking-layer sibling. Owns the 9-recipe library + the "pick the right framework" suggestion engine.

## Anchors

This skill draws its voice and pattern catalog from:

- **Style fingerprint:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_thinking_style.md`
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` (Consultant section H)
- **Review-mode corpus:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_artifact_feedback_corpus.md`

Read these BEFORE producing output (especially before review-mode invocations).

- **Catalog patterns to cite by slug** (Section A Universal / process): honest-scoping
- **Catalog patterns to cite by slug** (Section E CRO / marketing): shipped-vs-roadmap-visibility, capability-claim-unverified

## When to invoke

- Matt names a framework ("Porter on the LLM training market", "build a 2x2 on these projects", "SWOT this").
- Matt asks "which framework fits?" → use `suggest`.
- A leaf in an issue tree calls for a specific framework lens.
- Before `minto-pyramid` synthesis if a framework output anchors one of the supporting arguments.

## Different from

| Sibling | Owns |
|---|---|
| `scqa-framing` | Sharpening the root Question |
| `issue-tree` | MECE decomposition of the Question |
| `hypothesis-tree` | Initial answer + evidence per leaf |
| `framework-library` (this) | Filling a named strategic framework |
| `minto-pyramid` | Final answer-first synthesis |

## Recipe cards

| id | name | chart |
|---|---|---|
| `2x2` | 2x2 Matrix | scatter-2x2 |
| `porter-5f` | Porter's Five Forces | heatmap |
| `bcg` | BCG Growth-Share Matrix | scatter-2x2 |
| `value-chain` | Porter Value Chain | bar |
| `bmc` | Business Model Canvas | — |
| `raci` | RACI Matrix | — |
| `pugh` | Pugh Matrix | heatmap |
| `weighted-scoring` | Weighted Scoring | bar |
| `swot` | SWOT | — |

Each card lives at `~/.claude/skills/_consultant/_knowledge/consulting/frameworks/<id>.md` with `when_to_use` / `when_not_to_use` / `anti_patterns` / `chart_recipe`. New frameworks need a card before they're routable (anti-sprawl gate).

## Modes

### `render` — fill a named framework

```bash
python3 ~/.claude/skills/framework-library/run.py render <framework-id> \
  --engagement <slug> --mode <mode> [--from <issue-tree-leaf>] \
  [--items "a,b,c"] [--axes "Effort,Impact"] [--question "..."]
```

Writes `<engagement>/frameworks/<framework-id>-<slug>.md` (+ `.png` if recipe has chart_recipe). Pre-checks `when_not_to_use` against the input and refuses if any pattern matches.

### `suggest` — pick 2–3 frameworks for a question

```bash
python3 ~/.claude/skills/framework-library/run.py suggest "<question>"
```

Returns ranked candidate frameworks with rationale. Used by `consultant-engagement` Phase 1.

### `audit` — lint a filled framework

```bash
python3 ~/.claude/skills/framework-library/run.py audit <framework-md-path>
```

Checks: anti-patterns from the recipe card, named-number presence, action-titled quadrants/rows.

## Anti-patterns flagged

Each card's `anti_patterns` list is enforced. Common ones:

- 2x2 with quadrants that aren't actions
- Porter's Five Forces with no named numbers
- BCG with absolute (not relative) market share
- BMC with adjectives instead of named entities
- RACI with multiple A's or empty A
- Pugh with no neutral baseline
- Weighted scoring with weights chosen after seeing scores
- SWOT presented as the recommendation (instead of the situation)
