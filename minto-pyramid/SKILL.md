---
name: minto-pyramid
description: Answer-first storyline scaffold — the synthesis layer that takes SCQA + issue tree + hypothesis tree + framework outputs + analyses and produces a Minto pyramid (governing thought + 3 key supporting arguments + 2-4 supporting lines per key, each linked to upstream artifact). Two modes — `scaffold` (build from upstream paths) and `review` (audit existing pyramid for pyramid-rule violations). Anchored on `MattZerg/_style/consultant_thinking_style.md`. Different from `scqa-framing` (frames Question), `issue-tree` (decomposes), `hypothesis-tree` (initial answer per leaf), `framework-library` (applies named frameworks). This skill is the FINAL thinking-layer step — its output is the input to `consultant-deck` (becomes the deck spine, one action title per supporting line). USE PROACTIVELY when Matt says "storyline", "Minto", "answer-first", "synthesize", "governing thought", "what's the punchline", "deck spine", or before any `consultant-deck` invocation. Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Minto Pyramid

Phase 1 thinking-layer sibling. Final step before deliverable production.

## Anchors

This skill draws its voice and pattern catalog from:

- **Style fingerprint:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_thinking_style.md`
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` (Consultant section H)
- **Review-mode corpus:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/consultant_artifact_feedback_corpus.md`

Read these BEFORE producing output (especially before review-mode invocations).

- **Catalog patterns to cite by slug** (Section A Universal / process): honest-scoping, prior-review-carry-forward

Minimal pattern overlap; primary anchor remains `consultant_thinking_style.md`.

## When to invoke

- After Phase 2 analyses have landed and hypothesis-tree rows have been `score`d with updated confidence.
- Whenever Matt says "storyline", "Minto", "answer-first", "governing thought", "deck spine", "what's the punchline".
- Before `consultant-deck` runs — the Minto rows become deck slides (one action title per row).

## Different from

| Sibling | Owns |
|---|---|
| `scqa-framing` | Question (root) |
| `issue-tree` | MECE decomposition |
| `hypothesis-tree` | Initial answer + evidence per leaf |
| `framework-library` | Filled framework artifacts |
| `minto-pyramid` (this) | Final answer-first synthesis ready for a deck |

## Output shape

```
Governing thought (the SCQA Answer, hardened)
├── Key 1: <complete claim>
│   ├── Supporting 1.1 — <claim + [source] / upstream: ...>
│   ├── Supporting 1.2 — <claim + [source] / upstream: ...>
│   └── Supporting 1.3 — ...
├── Key 2: <complete claim>
│   ├── Supporting 2.1 ...
│   └── ...
└── Key 3: <complete claim>
    └── ...
```

Every line is a complete claim, not a topic. Every supporting line cites the upstream artifact that backs it (hypothesis row, framework output, chart, data file).

## Modes

### `scaffold` — build from upstream

```bash
python3 ~/.claude/skills/minto-pyramid/run.py scaffold \
  --engagement <slug> --mode <mode> \
  --from <scqa.md> <hypothesis-tree.md> [<framework-1.md> ...]
```

Writes `<engagement>/06-synthesis-minto.md`. Pulls the SCQA Answer as governing thought; uses hypothesis rows with `confidence: high|med` as the supporting evidence; flags rows still `low`.

### `review` — audit pyramid

```bash
python3 ~/.claude/skills/minto-pyramid/run.py review <minto-path>
```

Flags: topic-as-key (no verb), supporting line that could move under a different key (pyramid violation), unlinked supporting line (no `upstream:` cite), missing confidence on governing thought.

## Anti-patterns flagged

- **Topic keys** ("Pricing") instead of claim keys ("Pricing is leaving 12% on the table").
- **Floating supporting lines** — no `[source: ...]` or `upstream:` cite.
- **Pyramid violation** — supporting line that supports a different key than the one it's under.
- **Governing-thought drift** — top of pyramid doesn't answer the SCQA Question.
- **Confidence collapse** — all keys/supporting lines are `[high]` with no analysis trail. Earned confidence only.
