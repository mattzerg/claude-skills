---
name: cross-model-check
description: >-
  Cross-model verification for feedback and gate workflows. Asks the other LLM in
  Matt's stack to second-pass code, prose, launch, email, or generic artifacts,
  writes a dated HIGH/MED/LOW review, and lets pr-gate or qa-gate treat HIGH
  findings as block-eligible while skipped checks remain informational.
allowed-tools:
  - Bash
  - Read
  - Write
---

# cross-model-check

A second-opinion gate that asks the OTHER LLM in Matt's stack for findings on an artifact. Always-on inside pr-gate and qa-gate; also invocable directly.

## When to invoke directly

- A standalone artifact (blog draft, email, one-pager, video script) needs a sanity check before publish, and pr-gate / send-gate aren't in the loop.
- You want to compare two models' reviews of the same artifact side by side.
- Debugging a gate finding — "would the other model agree?"

## When the gates invoke it automatically

- `pr-gate` runs `cross-model-check` against the full diff as a 4th review section (after fakeidan, fakematt-copyedit, launch-announcement). HIGH findings count toward `total_high` and trigger the existing block logic.
- `qa-gate` runs it parallel to fakeidan; xmodel HIGH findings surface in the manifest under `xmodel_review` and append to the verdict if non-empty.

## CLI surface

```bash
python3 ~/.claude/skills/cross-model-check/run.py <artifact-path> \
    [--mode {code,prose,launch,email,generic}] \
    [--from {claude,codex}] \
    [--primary-review PATH] \
    [--diff REF | --diff-file PATH] \
    [--out-dir DIR] \
    [--timeout SECONDS] \
    [--effort {high,xhigh}] \
    [--repo-root PATH] \
    [--model MODEL] \
    [--no-aitr]
```

Exit codes:
- `0` — ran, no HIGH findings
- `1` — usage error (missing args, can't auto-detect `--from`)
- `2` — ran, HIGH findings present (gate-block signal)
- `3` — skipped (rate-limited / binary missing / timeout / error) — gate-informational

Stdout: the path to the output review file. Stderr: progress + verdict summary.

## Output format

`<out-dir>/<artifact-name>.xmodel.<YYYY-MM-DD>.md`:

```markdown
# Cross-Model Check — <artifact>

**Reviewer:** codex|claude
**Primary author/model:** claude|codex
**Mode:** code|prose|launch|email|generic
**Date:** YYYY-MM-DD
**Verdict:** Concur | Challenge | Mixed | Skipped | Unknown
**Status:** ok | skipped — <reason>
**Model selection:** <aitr pick + reason, manual override, or loud fallback note>

---

(model output — adheres to a strict template with `## HIGH`, `## MEDIUM`,
`## LOW`, `## Likely-missed-by-primary`, `## Notes` sections.)
```

The `## HIGH` header is the same regex shape pr-gate already scans for, so xmodel findings naturally block gates without further plumbing.

## Routing

`scripts/detect_active_model.py` sniffs env vars:
- `CLAUDECODE`, `CLAUDE_CODE_*` → active = Claude → invoke Codex
- `CODEX_*` → active = Codex → invoke Claude

If neither env hint is present and `--from` is not passed, exits with code 1 and a usage message.

## Model selection (aitr)

When `--model` is NOT explicitly passed, `scripts/aitr_select.py` asks the `aitr` skill
which model the REVIEWER should use:

- Mode → task_kind: `code`→code-review, `prose`/`launch`/`email`→prose-review, `generic`→refute
- Reviewer = claude → `provider_constraint=anthropic-only`; aitr's pick maps to the
  claude CLI alias (`opus`/`sonnet`/`haiku`)
- Reviewer = codex → `provider_constraint=openai-only`; aitr's pick maps to codex
  reasoning effort (pro-class models ⇒ `xhigh`, else `high`)
- Quality floor is always `high-stakes` (this is a gate)

Precedence: manual `--model` > aitr pick > reviewer default. `--no-aitr` disables.

Failure posture: aitr failures (not installed / catalog unreachable / no candidate)
NEVER block the cross-check. The reviewer default is used, and the failure is recorded
loudly in the review header's `**Model selection:**` line and stderr — visible in
pr-gate/qa-gate review files. Every `aitr` pick is also logged to
`~/.local/state/zerg/aitr/decisions.log` with a decision_id for replay/tuning.

## Pre-flight skip path

Before firing the OTHER model:
- Codex side: `scripts/check_rate_limit.py` consults `codex-usage-router` for rate-limit / cap state. Hard skip when 98%+ or explicit rate-limit signal.
- Claude side: binary presence only (no Claude-side usage router yet); auth errors surface as exit-3.

Skip never blocks the gate — it writes an informational review file with empty HIGH and exits 3.

## Anti-patterns — do not

- **Do not pass `--no-cross-model` casually** at pr-gate or qa-gate. The whole point of the skill is to be always-on; the flag exists for rate-limit conservation and CI-smoke scenarios, not as a default workflow.
- **Do not invoke this on locked content** without checking the lock first. The cross-check is read-only and doesn't violate the lock, but it adds Codex / Claude usage you may not want during a freeze.
- **Do not call this from inside another cross-model-check** (e.g., Codex calling Claude calling Codex…). Detection only checks the active session env; there's no recursion guard. If you build orchestrators on top, pass `--from` explicitly and break recursion at the caller layer.
- **Do not delete `<artifact>.xmodel.<date>.md` files casually.** Gates re-read them; pr-gate's `.pr-gate-review.md` regenerates each run but qa-gate's manifest path is durable in `~/.codex/artifacts/qa-gate/`.

## Memory anchors

- Operationalizes the cross-model verification idea from 2026-05-13 — single-model review converges on its own blind spots, so a second-model pass is the cheapest catch for hallucinated APIs, voice drift, and unsupported public claims.
- Pairs with `feedback_fakeidan_iterative_stop_rule.md` — xmodel is one of the "2-3 rounds" that should run before merge.
- Reuses the `codex exec -C <repo> -s read-only -c 'model_reasoning_effort="high"' --enable web_search_cached --json` invocation pattern from `~/.claude/skills/codex/SKILL.md` verbatim — do not invent a new Codex shell pattern.
- Auth: reuses existing `~/.codex/auth.json` for Codex and `~/.config/zerg/zclaude` for Claude. No new tokens.

## Codex-side mirror

Symlinked at `~/.codex/skills/cross-model-check → ~/.claude/skills/cross-model-check` so Codex sessions discover the skill the same way Claude does.
