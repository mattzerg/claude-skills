---
name: decision-queue
description: Single canonical queue of every "needs Matt" decision across the OS (zpub, gtm-hub, inbox, pr-table), surfaced through Slack Block Kit DM cards, a local Tinder-style swipe app, and a terminal rapid-fire CLI. Each answered decision logs the full briefing snapshot to ~/.claude/state/decisions_log.jsonl — the corpus that feeds autonomy-class upgrades (mining-to-composite pipeline). USE PROACTIVELY whenever Matt has ≥5 minutes of attention to clear decisions; whenever a decision count >0 surfaces in morning-brief; before any "what should I work on" planning conversation. Aggregator runs every 15min via LaunchAgent com.zerg.decision-queue-regen; server runs persistently via com.zerg.decision-queue-serve at localhost:8788.
---

# decision-queue

The rapid-feedback spine of Matt's OS. One canonical queue of every entity awaiting his input, three reply channels (Slack / swipe / terminal), one log that captures the full briefing snapshot per answer.

## Why this exists

Before: blockers were scattered across `Tasks/inbox.md`, `gtm-hub/_meta/decisions.json`, zpub reds, and pr-table review state. Matt had to assemble the queue every time he wanted to give feedback. No structured taxonomy for "safe to autonomously progress" vs "needs Matt's call" — so Claude either over-asked or under-asked.

After: one aggregator pulls them all into `MattZerg/Tasks/decisions_pending.md` (human) + `~/.claude/state/decisions_pending.jsonl` (machine), every entity gets an autonomy verdict via `~/.config/zerg/autonomy.yaml`, and Matt clears decisions through whichever channel he's in.

## Resolution model

For each candidate entity:

1. **Entity-level frontmatter** `autonomy: auto | needs_matt | blocked_external` wins.
2. **Tags** like `[blocked:idan]`, `[waiting:vendor]` force `blocked_external`.
3. **Class default** from `~/.config/zerg/autonomy.yaml` (e.g., `pseo_publish: needs_matt`).
4. **Fallback**: `needs_matt` (safe).

Only `needs_matt` items land in the queue. `auto` items proceed silently. `blocked_external` items show up in the morning-brief "Waiting" lane, not the decision queue.

## Channels

### Slack Block Kit DM card (primary)
Each item posts to Matt's FM self-DM as one card with 4 buttons: ✅ yes / ❌ no / ⏸ defer-1d / 🔍 details. Tap fires the Slack interactive webhook → `serve.py /slack/action` → `decisions_log.jsonl`. Works on phone with no extra setup beyond the Slack app.

```bash
/usr/bin/python3 ~/.claude/skills/decision-queue/tools/slack_card.py digest --limit 3
```

### Local swipe web app (`localhost:8788/swipe`)
Tinder-style card stack. Swipe right = yes, left = no, up = defer, down = details. Mobile-first responsive; binds 127.0.0.1 by default. To access from phone over LAN/Tailscale set `DECISION_QUEUE_BIND=0.0.0.0`.

```bash
open http://127.0.0.1:8788/swipe
```

### Terminal rapid-fire (`rapid_fire.py`)
Fastest path. Single-keystroke: y/n/d/?/s/q. Regenerates the queue first by default. Optional `--class=pseo_publish` filter.

```bash
/usr/bin/python3 ~/.claude/skills/decision-queue/tools/rapid_fire.py
/usr/bin/python3 ~/.claude/skills/decision-queue/tools/rapid_fire.py --class=content_publish
```

## Files

- `~/.config/zerg/autonomy.yaml` — class-by-class default verdicts. Edit when promoting a class from `needs_matt` → `auto` after stable decision-log pattern.
- `~/.claude/skills/decision-queue/lib/autonomy.py` — resolver. Import + call `resolve(entity_autonomy=..., entity_class=..., tags=...)`.
- `~/.claude/skills/decision-queue/tools/aggregate.py` — scan + render. Reads gtm-hub `_meta/decisions.json` + zpub `pub-*.md` + `Tasks/inbox.md`. Writes `decisions_pending.{md,jsonl}`.
- `~/.claude/skills/decision-queue/tools/serve.py` — Flask app on 8788. Routes: `/`, `/swipe`, `/api/queue`, `/api/decide`, `/slack/action`, `/api/regen`, `/health`.
- `~/.claude/skills/decision-queue/tools/slack_card.py` — Block Kit poster (`digest` | `full` | `dry-run`).
- `~/.claude/skills/decision-queue/tools/rapid_fire.py` — terminal CLI.
- `~/.claude/skills/decision-queue/templates/swipe.html` — vanilla-JS swipe UI.
- `MattZerg/Tasks/decisions_pending.md` — canonical human view (auto-regenerated, never hand-edit).
- `~/.claude/state/decisions_pending.jsonl` — machine-readable queue.
- `~/.claude/state/decisions_log.jsonl` — append-only log of every answer + full briefing snapshot. Source of truth for the mining-to-composite pipeline (P1.4).

## LaunchAgents

- `com.zerg.decision-queue-regen` — `aggregate.py` every 15min.
- `com.zerg.decision-queue-serve` — Flask server, always on.

```bash
launchctl load   ~/Library/LaunchAgents/com.zerg.decision-queue-regen.plist
launchctl load   ~/Library/LaunchAgents/com.zerg.decision-queue-serve.plist
launchctl unload ~/Library/LaunchAgents/com.zerg.decision-queue-regen.plist
```

## Integration points

- **morning-brief** reads `decisions_pending.jsonl` and posts top-3 cards inline if N>0.
- **triage** reads the same JSONL for the "Blocked by you" section.
- **fakematt-today/digest.py** can call `slack_card.py digest` to deliver decisions inline with daily digest.
- **mining-to-composite (P1.4)** reads `decisions_log.jsonl` weekly to propose autonomy-class upgrades and new feedback rules.

## When NOT to use

- Don't use to communicate decisions back to other humans (Slack DM threads with teammates, email to Idan). Those have their own channels.
- Don't use for ideation capture — use `idea-backlog`.
- Don't use for in-progress work coordination — use `zinflight` / `session-handoff`.

## Adding a new decision source

1. Add a `from_<source>()` generator to `aggregate.py`.
2. Yield `DecisionItem` instances. Use `autonomy.resolve(...)` to filter to `needs_matt`.
3. Re-run aggregate; new source items appear in all 3 channels automatically.

## Promoting a class to `auto`

After ≥8 stable same-answer rows in `decisions_log.jsonl` for one class, P1.4 surfaces a proposal in the queue. Approve it → edit `autonomy.yaml`. Until P1.4 is built, do it manually by inspecting:

```bash
jq -c 'select(.autonomy_class=="content_draft")' ~/.claude/state/decisions_log.jsonl | tail -20
```

If Matt always answered "yes" for that class, safe to flip the default.
