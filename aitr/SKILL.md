---
name: aitr
description: >-
  Internal LLM router. USE PROACTIVELY before any subagent dispatch, gate
  invocation, or workflow fan-out — picks the right model+provider+effort for a
  task signal and emits a citation-style reason. Reads the AI Tracker catalog
  (HTTP or bundled snapshot) and ranks candidates against task fit, cost,
  latency, and quality floor. Sibling to claude_account_router (account-level)
  and cross-model-check (provider-swap gates); this skill is the missing
  task→model layer that those routers don't own.
allowed-tools:
  - Bash
  - Read
  - Write
---

# aitr — AI Tracker Router

A **recommender** skill: emits `use claude-sonnet-4-6 because …` for a task. Does NOT intercept calls. Caller (human, agent, gate, workflow) reads the recommendation and dispatches.

Boundary:
- `aitr` picks the model class + provider + (optional) reasoning effort
- `claude_account_router.py` continues to pick which Claude OAuth account serves the chosen model
- `codex-usage-router` continues to pick which Codex account
- `cross-model-check` continues to swap providers for second-opinion gates — it just calls `aitr` first to pick the *right* opposite-provider model rather than always using the default

## When to invoke

Before any of these:
- A subagent is about to be dispatched (`Agent` tool, `Task` tool)
- A gate is about to run (`pr-gate`, `qa-gate`, `cross-model-check`)
- A workflow step is about to spawn agents (parallel/pipeline fan-out)
- A fakematt-* skill is about to draft / review / copyedit
- Any one-off `zclaude --model X` or `codex --model X` invocation where you're unsure

If the answer is obviously the active session model and there's no budget/latency pressure, you can skip — but logging the decision is still useful for tuning.

## CLI surface

```bash
python3 ~/.claude/skills/aitr/scripts/pick.py <verb> [signal …] [--format json|human|both]

# Verbs:
pick           # default — return one recommendation
explain        # return top-3 with rationale paragraph
refresh-cache  # force-refresh the local catalog cache
list-models    # print the current catalog with key fields
replay <id>    # print the decision recorded for a prior pick (by decision_id)
```

### Signal

Pass either `--signal '<json>'` or repeated `key=value` args:

| Field                    | Type     | Required | Default       | Notes |
|--------------------------|----------|----------|---------------|-------|
| `task_kind`              | enum     | yes      | —             | code-review, prose-review, brainstorm, draft-prose, structured-extract, sql, image-gen, summarize, refute, research, classify |
| `artifact_size_tokens`   | int      | no       | 4000          | approximate input size |
| `latency_budget_seconds` | int      | no       | none          | hard floor; otherwise scored softly |
| `cost_budget_usd`        | float    | no       | none          | hard floor; otherwise scored softly |
| `quality_floor`          | enum     | no       | medium        | cheap-ok, medium, high-stakes |
| `caller`                 | string   | yes      | —             | skill/agent name, for the decision log |
| `provider_constraint`    | enum     | no       | any           | any, anthropic-only, openai-only |
| `modality_required`      | enum     | no       | none          | vision, tools, extended-thinking |

Examples:
```bash
# pr-gate calling for a code-review:
aitr pick task_kind=code-review caller=pr-gate quality_floor=high-stakes artifact_size_tokens=8000

# cross-model-check picking the opposite-provider model:
aitr pick task_kind=refute caller=cross-model-check provider_constraint=openai-only

# fakematt-copyedit calling for a prose review:
aitr pick task_kind=prose-review caller=fakematt-copyedit quality_floor=high-stakes

# explain with rationale + alternatives:
aitr explain task_kind=brainstorm caller=consultant-engagement quality_floor=high-stakes
```

## Output format

`--format json` (default for machine consumers):
```json
{
  "decision_id": "aitr-20260601-184312-a1b2c3",
  "model": "claude-sonnet-4-6",
  "provider": "anthropic",
  "model_class": "sonnet",
  "estimated_cost_usd": 0.04,
  "reason": "prose-review on 4k input — sonnet fits the quality floor (medium) at $0.04, faster than opus.",
  "alternatives": [
    { "model": "claude-haiku-4-5", "model_class": "haiku", "score": 0.71, "reason": "cheaper but quality floor=medium prefers sonnet" },
    { "model": "gpt-5.4", "model_class": "gpt-5", "score": 0.68, "reason": "fits but provider=anthropic preferred by tag overlap" }
  ]
}
```

`--format human` (one-liner, useful in CI logs):
```
claude-sonnet-4-6 — fits quality_floor=medium, $0.04 estimated, anthropic preferred for prose
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0    | success — recommendation emitted |
| 1    | usage error — bad signal, unknown verb, etc. |
| 2    | no candidate satisfies hard constraints — caller decides to relax |
| 3    | data backend unreachable AND no bundled snapshot — fail-loud; do NOT silently default to a model |

## Data backend (catalog)

Fallback chain (catalog.py):
1. Live HTTP fetch of `${TRACKER_ORIGIN}/api/search.json` (default origin from `~/.config/zerg/aitr.toml`)
2. Local cache at `~/.cache/zerg/aitr/search.json` (1h TTL)
3. Stale cache (any age) with `X-Catalog-Stale: true` warning to stderr
4. Bundled snapshot at `~/.claude/skills/aitr/data/snapshot/search.json` (~12 canonical models)
5. Exit 3

Per-model detail (`/models/<id>.json`) cached for 24h at `~/.cache/zerg/aitr/models/<id>.json`.

## Ranking logic

For each model in the catalog (filtered by `status == "ga"`):

1. **Hard filters** — drop if any required modality missing, `provider_constraint` violated, `context_window < artifact_size_tokens × 1.3`
2. **Capability score** (0-1) — Jaccard overlap of `model.tags` with `routing_table[task_kind].preferred_tags` + benchmark lookup
3. **Cost score** (0-1) — `(artifact × input_per_mtok + 2000 × output_per_mtok) / 1e6`, normalized against `cost_budget_usd` if set
4. **Latency score** (0-1) — tag-based (`fast`/`small-model` → 1.0, `extended-thinking` → 0.3)
5. **Quality floor gate** — `cheap-ok` allows any; `medium` requires capability ≥ 0.5; `high-stakes` requires capability ≥ 0.75 or whitelist
6. **Composite** — weighted sum (default capability 0.5 / cost 0.3 / latency 0.2; tunable via `data/routing_table.yaml`)
7. **Tie-break** — cheaper class first, then most recent `released` date

## Configuration

`~/.config/zerg/aitr.toml`:
```toml
tracker_origin = "https://zergai.com/resources/ai-tool-tracker"  # uses proxied JSON twins; falls back to TRACKER_ORIGIN env
cache_dir = "~/.cache/zerg/aitr"
decisions_log = "~/.local/state/zerg/aitr/decisions.log"
weekly_report_target = "fakematt"  # where weekly tuning report posts
```

Routing rules live in `~/.claude/skills/aitr/data/routing_table.yaml` (per-task_kind preferred tags, latency class, opposite_provider hint, composite weights).

## Decision logging

Every `pick` appends a JSONL line to `~/.local/state/zerg/aitr/decisions.log`:
```json
{"ts": "2026-06-01T18:43:12Z", "decision_id": "aitr-...", "signal": {...}, "picked_model": "...", "reason": "...", "alternatives": [...], "caller": "..."}
```

Used by:
- `replay <id>` — reproduce a prior decision
- `weekly_report.py` — Friday cron summarizes pick distribution + cost spend + corrections
- `llm-feedback` — when Matt files `wrong-model-picked`, the decision_id ties the correction back to the original pick; ranker applies a bounded penalty on next pick

## Failure mode

If the catalog is unreachable AND no bundled snapshot exists, `aitr` exits **3** — never silently defaults to a model. Callers (pr-gate, agents, workflows) MUST treat exit 3 as fail-loud and surface a clear error. Mirrors `pr-gate`'s fail-closed posture.

## Not in scope

- Runtime call interception (would change shape from recommender to gateway — deferred per the original design)
- Account-level routing (owned by `claude_account_router.py` / `codex-usage-router`)
- Cost dashboard / spend tracking (separate work; weekly_report.py is informational only)
