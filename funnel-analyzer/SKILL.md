---
name: funnel-analyzer
description: Computes measured conversion rates per funnel step from Zergalytics events. Funnels are YAML at `Growth/funnels/<name>.yaml` (name, product, ordered steps). Five modes: `define`, `query` (drop-off table + ASCII chart), `compare` (segmented cuts), `top-friction` (worst step across funnels), `list`. Data sources in priority order: Zergalytics public API, direct Postgres on `zerg/api/analytics/PageMetricEvent`, Stripe webhooks for paid steps; ships with a fixture-mode fallback for development. USE PROACTIVELY for "what's the actual signup conversion," "where do users drop off," or after `cro-auditor` to verify a hypothesis with measured data. `cro-auditor` is heuristic friction on marketing surfaces; funnel-analyzer is data-driven measurement. `growth-dashboard` is the rolled-up weekly summary; funnel-analyzer is per-funnel deep-dive.
allowed-tools: Bash, Read, Write
---

# Funnel Analyzer Skill

Data-driven complement to `cro-auditor` (heuristic) and `growth-dashboard` (rolled-up summary). Where cro-auditor SUGGESTS where friction might be, this skill MEASURES where it actually is.

## Why this exists

`growth-dashboard` line #3 is "activation rate." It's a single number rolled up across the whole product. When that number drops, the question is "which step broke?" — and there's no skill to answer that. `cro-auditor` can guess based on heuristics. Funnel-analyzer queries the actual events and shows the drop-off per step.

## Modes

### `define` — scaffold a new funnel YAML

```bash
python3 ~/.claude/skills/funnel-analyzer/run.py define \
  --name signup \
  --product zergboard \
  --steps "view:landing,click:cta_signup,submit:signup_form,activate:first_card_created"
```

Writes `MattZerg/Projects/Zstack/Growth/funnels/signup.yaml`. Each step is `event_type:event_name`. Order matters — funnel computation walks them in sequence.

### `query` — measured drop-off rates

```bash
python3 ~/.claude/skills/funnel-analyzer/run.py query --name signup --days 30
```

Output:

```
# signup funnel — last 30 days

| Step                      | Count   | Cum %   | Step % | Drop |
|---|---|---|---|---|
| view:landing              | 4,120   | 100.0%  | —      | —    |
| click:cta_signup          | 1,648   | 40.0%   | 40.0%  | 60.0% ▓▓▓▓▓▓
| submit:signup_form        | 824     | 20.0%   | 50.0%  | 50.0% ▓▓▓▓▓
| activate:first_card_created | 412   | 10.0%   | 50.0%  | 50.0% ▓▓▓▓▓

Top friction: view:landing → click:cta_signup (60.0% drop).
Suggestion: run cro-auditor on landing page, then experiment-designer to draft test.
```

If a step has drop-off ≥ 50%, it's flagged as friction and surfaces a suggested next-step skill.

### `compare` — segmented cuts

```bash
python3 ~/.claude/skills/funnel-analyzer/run.py compare --name signup --segment utm_source --days 30
```

Returns the same drop-off table per segment value. Useful for "is the X campaign converting differently than Y?"

### `top-friction` — worst step across all funnels

```bash
python3 ~/.claude/skills/funnel-analyzer/run.py top-friction --days 7
```

Sorted by absolute drop count × drop rate (so high-volume drops outrank tiny edge cases).

## Data sources (priority order)

1. **Zergalytics public API** — when `ZERGALYTICS_API_URL` env var is set + funnel `data_source: api` in YAML
2. **Direct Postgres** — when `ZERGALYTICS_DATABASE_URL` env var is set + funnel `data_source: postgres` in YAML
3. **Stripe webhooks** — for paid-step funnels (e.g. `paid_signup → first_charge`); requires `STRIPE_API_KEY` from keychain
4. **Stub fixture** — `funnels/<name>/_fixture.json` for development. Always last-resort, never source-of-truth in prod.

Credentials read from macOS Keychain via `~/.config/zerg/load_anthropic_key.sh` pattern (per `feedback_api_keys_via_keychain.md`).

## Funnel YAML schema

```yaml
---
name: signup
product: zergboard
data_source: api  # api | postgres | stripe | fixture
default_days: 30
steps:
  - id: landing-view
    event_type: view_start
    event_name: ""
    page_path: /
  - id: cta-click
    event_type: cta_click
    event_name: signup_cta
  - id: form-submit
    event_type: signup_complete
    event_name: ""
  - id: activation
    event_type: custom
    event_name: first_card_created
friction_threshold: 0.50  # drop ≥ 50% flags as friction
---
```

## Anti-drift contract

- **Funnels MUST be defined before query.** No ad-hoc computations without a written YAML — keeps definitions reproducible.
- **Step order is canonical.** Reordering = new funnel (rename file).
- **No silent data-source fallback.** If `data_source: api` is declared but API is unreachable, errors with an actionable message — does NOT silently fall through to fixture.
- **`top-friction` requires ≥ 100 events at the head.** Below that, dataset is too small and surfacing friction is noise.

## Routing to other skills

| Output | Suggested next |
|---|---|
| Friction step ≥ 50% drop | `cro-auditor` (heuristic), then `experiment-designer` |
| Step has 0 events | `utm-attribution` audit — instrumentation may be broken |
| `compare` shows large segment delta | `experiment-tracker` register a treatment |

## Implementation notes

- File-based funnel definitions (YAML) at `Growth/funnels/<name>.yaml`
- Per-run output at `Growth/funnels/_runs/<name>-YYYY-MM-DD.md`
- Stdlib-only for Phase 1 (urllib for API, json for fixtures)
- DB driver is optional — Phase 2 wires psycopg / SQLAlchemy when needed
- Cache nothing — always re-read funnel YAML
