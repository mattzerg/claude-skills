---
name: hypothesis-tree
description: Initial answer + evidence required + analyses to run, per leaf of an issue tree. Anchored on `MattZerg/_style/consultant_thinking_style.md`. Reads an issue tree, emits a row-per-leaf table with `initial_answer`, `evidence_required`, `would_disprove`, `analyses_to_run`, `confidence`. Two modes — `scaffold` (build from tree) and `score` (update confidence after analysis). Different from `scqa-framing` (frames root Question), `issue-tree` (MECE decomposition — runs FIRST), `framework-library` (applies named framework to a slice), `minto-pyramid` (final answer-first synthesis). USE PROACTIVELY when Matt says "hypothesize", "initial answer per branch", "what would we have to believe", "what proves/disproves this", "Day-1 hypothesis", "stake the bet", or after `issue-tree` and before any analysis is dispatched. Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Hypothesis Tree

Phase 1 thinking-layer sibling. Consumes an `issue-tree` output and emits a table — one row per leaf — capturing the Day-1 best guess and what would change our mind.

## Anchors

This skill draws its voice and pattern catalog from:

- **Style fingerprint:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_thinking_style.md`
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` (Consultant section H)
- **Review-mode corpus:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_artifact_feedback_corpus.md`

Read these BEFORE producing output (especially before review-mode invocations).

- **Catalog patterns to cite by slug** (Section A Universal / process): honest-scoping, prior-review-carry-forward, minimize-prs

Process-heavy skill; primary anchor remains `consultant_thinking_style.md`.

## When to invoke

- After `issue-tree` — every leaf gets a hypothesis row.
- When Matt says "what would we have to believe", "Day-1 hypothesis", "stake the bet", "hypothesize".
- Before dispatching Phase 2 analyses — the hypothesis tree names which skills to fire.

## Different from

Same sibling map as `issue-tree`. This one owns the **initial answer + evidence + analyses** column.

## Output

Markdown table with one row per leaf:

| Leaf ID | Sub-question | Initial answer | Evidence that would prove | Evidence that would disprove | Analyses to run | Confidence |
|---|---|---|---|---|---|---|
| L1.1 | Is pricing under-discounting? | Yes, ~15% below MM peers | MM win-rate vs SMB win-rate; ASP by segment | MM win-rate ≥ SMB | `cohort-analyzer` segment=size; `competitive-review-skill` | low |

If a leaf has NO falsifiable analysis path, the skill flags it for kill or restructure — unfalsifiable hypotheses waste the engagement.

## Modes

### `scaffold` — build from issue tree

```bash
python3 ~/.claude/skills/hypothesis-tree/run.py scaffold --from <issue-tree-path> \
  --engagement <slug> --mode <mode>
```

Writes `<engagement>/03-hypothesis-tree.md`. Each row pre-seeded with placeholders + `[confidence: low]`.

### `score` — update confidence + answer after analysis

```bash
python3 ~/.claude/skills/hypothesis-tree/run.py score <tree-path> \
  --leaf L1.1 --answer "...new answer..." --confidence high \
  --evidence-paths <analysis-md> <chart-md>
```

Updates the row + appends to `source_citations`.

## Anti-patterns flagged

- **Unfalsifiable hypothesis** — no analysis would prove or disprove it.
- **Tautology answer** — "yes if true, no if false".
- **Missing analysis path** — no skill or workstream named.
- **Confidence not updated** after Phase 2 analyses landed (`score` not run).
