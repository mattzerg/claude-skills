---
name: issue-tree
description: MECE decomposition of a question into a hierarchical issue tree. Reads an SCQA (or takes a raw question), produces tree as markdown bullets + mermaid + optional graphviz. Three modes — `scaffold` (build a tree from a question), `review` (audit existing tree for MECE violations), `mece-check` (just the lint, no rewrite). Anchored on `MattZerg/_style/consultant_thinking_style.md`. Different from `scqa-framing` (sharpens the root Question — runs FIRST), `hypothesis-tree` (initial answer per leaf — runs AFTER this), `framework-library` (applies named frameworks like 2x2/Porter/BCG to a slice), `minto-pyramid` (final answer-first storyline). USE PROACTIVELY when Matt says "MECE this", "issue tree", "decompose this", "break this down", "what are the sub-questions", "structure the problem", or before any `hypothesis-tree` run. Stable leaf IDs (`L1.2.3`) propagate to downstream artifacts. Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Issue Tree

Phase 1 thinking-layer sibling to `scqa-framing`, `hypothesis-tree`, `framework-library`, `minto-pyramid`.

## Anchors

This skill draws its voice and pattern catalog from:

- **Style fingerprint:** `~/Obsidian/Zerg/MattZerg/_style/consultant_thinking_style.md`
- **Pattern catalog:** `~/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` (Consultant section H)
- **Review-mode corpus:** `~/Obsidian/Zerg/MattZerg/_style/consultant_artifact_feedback_corpus.md`

Read these BEFORE producing output (especially before review-mode invocations).

- **Catalog patterns to cite by slug** (Section A Universal / process): honest-scoping, minimize-prs, bundling-rule

Process-heavy skill; primary anchor remains `consultant_thinking_style.md`.

## When to invoke

- After `scqa-framing` — the SCQA Question becomes the issue tree's root.
- Whenever Matt says "MECE", "issue tree", "decompose", "sub-questions", "structure", "break this down".
- Before `hypothesis-tree` runs — each leaf becomes one hypothesis row.
- When a draft tree has overlap or gaps and needs a MECE audit.

## Different from

| Sibling | Owns |
|---|---|
| `scqa-framing` | Sharpening the root Question (runs first) |
| `issue-tree` (this) | MECE decomposition of the Question into leaves |
| `hypothesis-tree` | Initial answer + evidence required per leaf |
| `framework-library` | Applying a named framework (2x2 / Porter / BCG / value chain / BMC / RACI / Pugh / weighted-scoring / SWOT) |
| `minto-pyramid` | Final answer-first synthesis ready for a deck |

## Modes

### `scaffold` — build tree from a question (or SCQA path)

```bash
python3 ~/.claude/skills/issue-tree/run.py scaffold "<question>" \
  --engagement <slug> --mode <client|pm|ops|life> [--depth 2|3] [--branches 3-5]

# OR build from an existing SCQA file:
python3 ~/.claude/skills/issue-tree/run.py scaffold --from <scqa-path> \
  --engagement <slug> --mode <mode>
```

Writes `<engagement>/02-issue-tree.md` + `.mmd` (mermaid). Stable leaf IDs `L1`, `L1.1`, `L1.1.2`.

### `review` — audit existing tree

```bash
python3 ~/.claude/skills/issue-tree/run.py review <tree-path>
```

Flags: topic-leaves (no `?`), overlap candidates (shared keywords across siblings), depth >3, branch counts outside 3–5, root mismatch with SCQA Question.

### `mece-check` — just the lint

```bash
python3 ~/.claude/skills/issue-tree/run.py mece-check <tree-path>
```

Same checks as `review`, no rewrite suggestions. Exit code 1 on HIGH findings.

## Output shape

```yaml
---
engagement: <slug>
slug: <slug>-issue-tree
date: YYYY-MM-DD
skill: issue-tree
inputs: [<scqa-path>]
upstream: [<scqa-path>]
root_question: <Q>
leaves: [{id: L1, q: "..."}, {id: L1.1, q: "..."}, ...]
---

## Root

> <Question>

## Tree

- **L1** Sub-question?
  - **L1.1** Deeper sub-question?
    - **L1.1.1** Leaf?
- **L2** Sub-question?
```

Plus a sibling `.mmd` mermaid file for visualization.

## Anti-patterns flagged

- **Topic leaves** ("Pricing", "Distribution") — must end in `?`.
- **Overlapping siblings** — significant keyword overlap between L1.1 and L1.2.
- **Branch count outside 3–5** — fewer means too narrow, more means a layer is missing.
- **Depth >3** — usually means root Question is wrong.
- **Root drift** — tree root doesn't match SCQA Question.
