# aitr in workflows and fan-outs

Two canonical patterns, depending on what's doing the fan-out.

## Pattern 1 — Workflow tool scripts (JS `agent()` calls)

Workflow scripts can't run Bash themselves, but agents they spawn can. Use a
stage-0 routing agent that calls aitr once for every stage profile, then thread
the picks into later `agent()` calls' `model` opts.

```javascript
export const meta = {
  name: 'routed-review',
  description: 'Review findings with aitr-routed model selection per stage',
  phases: [{ title: 'Route' }, { title: 'Find' }, { title: 'Verify' }],
}

const ROUTES_SCHEMA = {
  type: 'object',
  properties: {
    finder: { type: 'string', enum: ['opus', 'sonnet', 'haiku', 'inherit'] },
    verifier: { type: 'string', enum: ['opus', 'sonnet', 'haiku', 'inherit'] },
    log: { type: 'string' },
  },
  required: ['finder', 'verifier', 'log'],
}

phase('Route')
// Stage 0: one agent calls aitr for each stage profile and maps model_class →
// Agent-tool model. Cross-provider picks map to "inherit".
const routes = await agent(
  `Run these two commands and map each result's model_class to opus/sonnet/haiku
   (anything else → "inherit"). Return JSON {finder, verifier, log} where log is
   a one-line summary of both picks with their decision_ids.

   python3 ~/.claude/skills/aitr/scripts/pick.py pick task_kind=classify caller=workflow-routed-review quality_floor=cheap-ok --format json
   python3 ~/.claude/skills/aitr/scripts/pick.py pick task_kind=refute caller=workflow-routed-review quality_floor=high-stakes --format json`,
  { schema: ROUTES_SCHEMA, phase: 'Route' },
)
log(routes.log)

const modelOpt = (m) => (m === 'inherit' ? {} : { model: m })

phase('Find')
const findings = await parallel(ITEMS.map((item) => () =>
  agent(`Find issues in: ${item}`, { ...modelOpt(routes.finder), phase: 'Find', schema: FINDINGS })))

// Verify with the (usually more capable) verifier model
const verified = await parallel(findings.filter(Boolean).flatMap(f => f.issues).map((issue) => () =>
  agent(`Adversarially verify: ${issue.title}`, { ...modelOpt(routes.verifier), phase: 'Verify', schema: VERDICT })))
```

Key points:
- ONE routing agent per workflow, not one per item — picks are stage-level, not item-level.
- `model_class` → Agent model map: `opus`→`opus`, `sonnet`→`sonnet`, `haiku`→`haiku`, anything else → omit (inherit).
- The routing agent's stdout JSON includes decision_ids — put them in `log()` so the run is traceable back to `~/.local/state/zerg/aitr/decisions.log`.

## Pattern 2 — Bash fan-out scripts (orchestrator agents, cron jobs, ad-hoc)

```bash
#!/usr/bin/env bash
set -euo pipefail

AITR="python3 $HOME/.claude/skills/aitr/scripts/pick.py"

# 1. Pick per stage profile (NOT per item).
#    IMPORTANT: constrain provider to what your executor can actually reach.
#    `claude -p` scripts → anthropic-only. `codex exec` scripts → openai-only.
#    Agent-tool workflows → any (cross-provider maps to "inherit").
SUMMARIZE_PICK=$($AITR pick task_kind=summarize caller=my-pipeline quality_floor=cheap-ok provider_constraint=anthropic-only --format json)
REVIEW_PICK=$($AITR pick task_kind=prose-review caller=my-pipeline quality_floor=high-stakes provider_constraint=anthropic-only --format json)

# 2. Extract the model class; map to the claude CLI alias
summarize_model=$(echo "$SUMMARIZE_PICK" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['model_class'] if d['model_class'] in ('opus','sonnet','haiku') else '')")
review_model=$(echo "$REVIEW_PICK" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['model_class'] if d['model_class'] in ('opus','sonnet','haiku') else '')")

# 3. Thread into claude -p calls (empty model = CLI default)
for doc in docs/*.md; do
  claude -p "Summarize: $(cat "$doc")" ${summarize_model:+--model "$summarize_model"} > "out/$(basename "$doc").summary" &
done
wait

claude -p "Review these summaries: $(cat out/*.summary)" ${review_model:+--model "$review_model"} > out/review.md
```

Key points:
- `${var:+--model "$var"}` pattern: pass `--model` only when the pick maps to a claude alias.
- aitr exit codes: bail on 1 (usage error — your signal is malformed), proceed-with-default on 2/3 (no candidate / no data) but `echo` the failure so it's visible in logs.

## Failure handling in both patterns

| aitr exit | Meaning | Workflow/script behavior |
|-----------|---------|--------------------------|
| 0 | pick emitted | use it |
| 1 | usage error | FIX THE SIGNAL — this is a bug in your script |
| 2 | no candidate | proceed with default model, log loudly |
| 3 | no catalog data | proceed with default model, log loudly, file an issue to fix aitr's data backend |

Never swallow exit 2/3 silently. The forbidden move is silent defaulting — loud defaulting is fine.
