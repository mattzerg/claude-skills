# aitr — AI Tracker Router

Internal LLM router. Reads the AI Tracker catalog (HTTP or bundled snapshot), ranks models against a task signal, and emits a recommendation with a citation-style reason. **Recommender, not a gateway** — callers read the output and dispatch.

User-facing docs live in `SKILL.md`. This README is for developers.

## Module layout

```
scripts/
  pick.py           # CLI entry — wires signal + catalog + ranker, logs decisions
  ranker.py         # PURE rank(signal, catalog, routing_table) -> [Candidate]
  catalog.py        # Live → cache → stale → snapshot fallback chain
  task_signal.py    # Signal dataclass + parsers (kv args, JSON)
data/
  routing_table.json     # Per-task_kind rules + composite weights — TUNABLE
  snapshot/
    search.json          # Bundled offline fallback (~12 canonical models)
    models/              # Bundled per-model details (currently empty)
tests/
  conftest.py            # Puts scripts/ on sys.path
  test_signal.py         # Schema + parsing
  test_ranker.py         # Hard filters + score functions + e2e ranks
  test_catalog_fallback.py  # Fallback chain order
  test_golden_routing.py    # 20 canonical signals × expected class — drift detector
  golden/golden_routing.json
references/
  workflow_pattern.md      # Phase B4 — Bash snippet for workflow scripts
examples/
  fanout_refute.sh         # Phase B4 — adversarial verify across opposite providers
  pipeline_summarize_then_review.sh   # Phase B4
aitr.toml.sample
```

## Running

```bash
# Tests
python3 -m pytest ~/.claude/skills/aitr/tests/

# CLI smoke
python3 ~/.claude/skills/aitr/scripts/pick.py pick \
    task_kind=code-review caller=pr-gate quality_floor=high-stakes \
    artifact_size_tokens=8000 --offline --format both

# List models in the snapshot
python3 ~/.claude/skills/aitr/scripts/pick.py list-models --offline
```

## Tuning routing behavior

1. Edit `data/routing_table.json` to change preferred_tags / latency_class / weights for a task_kind.
2. Run `python3 -m pytest tests/test_golden_routing.py -v` to see which canonical cases pass/fail.
3. If a case fails and the new behavior is correct, update `tests/golden/golden_routing.json` with a note on WHY.
4. The threshold test passes when ≥ `golden.threshold` (default 0.80) of cases match.

## Updating the bundled snapshot

`data/snapshot/search.json` is a hand-curated subset of the live tracker. Refresh manually:

```bash
curl https://zergai.com/resources/ai-tool-tracker/api/search.json | jq . > /tmp/search.json
# Review for additions/removals, hand-edit data/snapshot/search.json.
```

Keep the snapshot small (≤15 canonical models) — it's a fallback, not a mirror.

## Boundary

- `aitr` picks the model class. `claude_account_router.py` picks the OAuth account that serves it.
- `cross-model-check` does provider-swap gates; it calls `aitr` first to pick the right opposite-provider model.
- `llm-feedback` captures corrections; Phase B6 adds the `wrong-model-picked` bucket that feeds back into the ranker.

## Not in scope

- Runtime call interception (would change shape from recommender to gateway — deferred).
- Account-level routing.
- Cost dashboards.
