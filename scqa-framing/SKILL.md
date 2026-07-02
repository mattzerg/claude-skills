---
name: scqa-framing
description: Turn a fuzzy problem brief into a structured Situation/Complication/Question/Answer frame — the anchor for every downstream consultant artifact. Anchored on `MattZerg/_style/consultant_thinking_style.md`. Two modes — `scaffold` (build from a brief) and `review` (audit an existing SCQA for sharpness). Different from `issue-tree` (decomposes the Question into MECE leaves), `hypothesis-tree` (proposes answers per leaf), and `minto-pyramid` (synthesizes the final answer-first storyline). USE PROACTIVELY when Matt says "frame this", "SCQA", "what's the real question", "tighten the question", "what are we actually deciding", or before any `issue-tree` / `hypothesis-tree` invocation. Never auto-posts. Outputs `.md` with the standard frontmatter envelope.
allowed-tools: Bash, Read, Write
---

# SCQA Framing

Sibling to `issue-tree`, `hypothesis-tree`, `framework-library`, `minto-pyramid`. Anchor of the consultant-toolkit thinking layer.

## Anchors

This skill draws its voice and pattern catalog from:

- **Style fingerprint:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_thinking_style.md`
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` (Consultant section H)
- **Review-mode corpus:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_artifact_feedback_corpus.md`

Read these BEFORE producing output (especially before review-mode invocations).

- **Catalog patterns to cite by slug** (Section A Universal / process): honest-scoping, prior-review-carry-forward
- **Catalog patterns to cite by slug** (Section C Prose / writing): single-cta

Minimal pattern overlap; primary anchor remains `consultant_thinking_style.md`.

## When to invoke

- Matt drops a fuzzy strategic problem ("should we…", "what about…", "is X worth it") and you need to know what the question actually is before decomposing.
- Before any `issue-tree` run — the SCQA Question is the issue tree's root.
- When the user has a 1–3 paragraph brief and you need to identify the surprise (the Complication) that makes it a decision.
- When a draft SCQA looks soft — Question is a topic, Answer is vague — and needs to be sharpened.

## Different from

| Sibling | Owns |
|---|---|
| `scqa-framing` (this) | Sharpening the Question |
| `issue-tree` | Decomposing the Question into MECE leaves |
| `hypothesis-tree` | Initial answer + evidence required per leaf |
| `framework-library` | Applying a named framework (2x2/Porter/BCG/…) to a slice |
| `minto-pyramid` | Final answer-first synthesis ready for a deck |

## Modes

### `scaffold` — build SCQA from a brief

```bash
python3 ~/.claude/skills/scqa-framing/run.py scaffold "<problem brief>" \
  --engagement <slug> --mode <client|pm|ops|life> [--out-dir DIR]
```

Writes `<engagement>/01-scqa.md` (or `/tmp/consultant/scqa-framing/<slug>.md` without `--engagement`).

### `review` — audit existing SCQA

```bash
python3 ~/.claude/skills/scqa-framing/run.py review <path-to-scqa.md>
```

Returns findings: Question sharpness, Answer specificity, Complication "is it surprising?" check, hedging-adjective + floating-number flags. Severity HIGH/MED/LOW.

## Output

```
---
engagement: <slug>
slug: <slug>-scqa
date: YYYY-MM-DD
skill: scqa-framing
inputs: ["<brief or path>"]
upstream: []
source_citations: []
---

## Situation
...3 sentences max...

## Complication
...2 sentences max — the surprise that makes this a decision...

## Question
...one sentence ending in ?...

## Answer
... ≤2 sentences with [confidence: low/med/high] tag ...
```

## Anti-patterns (the skill flags these in `review`)

- Topic-as-Question ("Pricing strategy?" — not a question)
- Answer-as-Question ("Should we 2x the price?" — that's the Answer)
- Soft Complication ("As we grow, we need to…" — that's not a surprise)
- Hedging adjectives ("significant", "robust", "comprehensive")
- Floating numbers without `[source: …]` or `[needs-verification]`
