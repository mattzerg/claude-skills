---
name: workstreams
description: Workstream tracker — categorical view over Matt's active work (Zerg + personal). Groups open PRs / inbox items / vault folders / ideas / sessions into a user-curated set of workstreams (manifest at `~/.config/zerg/workstreams.yaml`). Surfaces hot / stale / parked / blocked, flags uncategorized items, suggests which session to resume per workstream. Also exposes `workstreams rayg` — Red/Amber/Yellow/Green health dashboard across all 12 lanes with rollup, drilldown, and cuts (amber=what-to-start, red=what's-stuck, yellow=nearly-done). Auto-snapshots to `Growth/weekly-rayg/` every Friday 4pm PT. USE PROACTIVELY when Matt asks "where am I on X", "what should I work on next", "what's hot/stale", or wants a RAYG status board. Categorical lens (not a replacement) alongside the fakematt-today daemons.
---

# workstreams

A workstream is a category of work — "Zergboard Launch", "Personal Finance & Tax", "Solutions Consulting", etc. Each workstream defines selectors that match against PRs, inbox items, vault folders, ideas, and Claude sessions. Run `/workstreams show` to see the rolled-up state.

## Commands

| Command | What it does |
|---|---|
| `/workstreams` or `/workstreams show` | Render the dashboard. Default = all non-empty workstreams. |
| `/workstreams show hot` | Only `hot` workstreams (touched in last 24h). |
| `/workstreams show stale` | `stale` (no activity 3+ days, not parked) — likely dropped balls. |
| `/workstreams show parked` | Long-idle / explicitly parked. |
| `/workstreams show all` | Include empty workstreams too. |
| `/workstreams show <id>` | Drill into one workstream — full item list. |
| `/workstreams refresh` | Re-run `collect.py` and re-render. |
| `/workstreams edit` | Open the manifest in `$EDITOR`. |
| `/workstreams add` | Wizard: append a new workstream to the manifest. |
| `/workstreams tag <inbox-line\|PR#\|vault-path> <ws-id>` | Annotate an item with a workstream id (writes back to the source). |
| `/workstreams catchall` | Show only the catchall workstream — items that didn't match anywhere. Use to find selector gaps. |
| `/workstreams resume <id>` | Print the right `zclaude --resume <sid>` command for a workstream (or new-session command if none exist). |
| `/workstreams hygiene [--threshold 48]` | Session hygiene analysis: alive sessions grouped by workstream + idle candidates + consolidation flags + hot workstreams missing a session. Never auto-kills — emits `zsession kill / relaunch` lines. |
| `/workstreams rayg` | RAYG health rollup of all 12 lanes (Red/Amber/Yellow/Green). Each lane shows MAX-severity color + next-move. |
| `/workstreams rayg <lane>` | Drill into one lane — balanced sample of items per color with reason. |
| `/workstreams rayg --cut amber` | Ranked "what to start" — decisions first, then queued items + high-conviction ideas. |
| `/workstreams rayg --cut red` | "What's stuck" — Red items grouped by blocker type (counterparty / Matt / failed-gate / etc.). |
| `/workstreams rayg --cut yellow` | "Nearly done" — Yellow items sorted by effort-to-flip-green. |
| `/workstreams rayg --weekly [--post]` | Write snapshot to `Growth/weekly-rayg/YYYY-MM-DD.md`. Auto-runs Fri 4pm PT. With `--post`, also enqueues rollup to Fake Matt → Matt DM. |
| `/workstreams rayg --diff [--diff-against YYYY-MM-DD]` | Compare current state to most recent weekly snapshot (or named one). Shows color flips (↑ improved / ↓ regressed), newly tracked items, and cleared items. |
| `/workstreams rayg --json` | Machine-readable item list for downstream tooling. |

## RAYG semantics

| Color | Meaning |
|---|---|
| 🔴 RED | Serious roadblock — NDA / counterparty wait / hard external dependency |
| 🟠 AMBER | Not started but valuable / urgent — backlog items, decisions pending, redo-gate work |
| 🟡 YELLOW | Pending completion — drafting, review, scheduled, in-flight |
| 🟢 GREEN | Shipped / completed / running smoothly |

Lane rollup color = MAX severity of underlying items: 🔴 > 🟠 > 🟡 > 🟢.

## How it works

1. **Manifest** at `~/.config/zerg/workstreams.yaml` defines workstreams + selectors.
2. **collect.py** runs the selectors against current data (gh PRs, inbox.md, vault folder mtimes, ideas index, sessions JSONs).
3. **state.json** is written to `~/.claude/workstreams/state.json` with per-workstream rollup.
4. **show.py** renders state.json to terminal. **dashboard.py** (P2) will post to FM DM + write `MattZerg/Workstreams.md`.

## Health buckets

| Bucket | Meaning |
|---|---|
| `hot` | Last activity in last 24h |
| `warm` | Last activity in last 3 days (stale_after_days) |
| `stale` | No activity in 3+ days but not parked — likely a dropped ball |
| `parked` | Status=`parked` OR no activity in 14+ days (parked_after_days) |
| `shipped` | Status=`shipped` |
| `empty` | No items match any selector |
| `blocked` | (P3) — explicitly blocked on external waits |

## Hard rules

- **Never auto-modifies the manifest.** All changes go through `/workstreams edit` or `/workstreams add`.
- **Never auto-publishes.** Dashboard posts will go to Matt's FM self-DM only (P2).
- **Never auto-kills sessions.** Terminal hygiene (P3) suggests; never executes destructive ops.
- **Catchall is required** — exactly one workstream must have `catchall: true`. Validation enforces this.

## Files

- Manifest: `~/.config/zerg/workstreams.yaml`
- Daemon home: `~/.claude/workstreams/` (collect.py, render.py, state.json, metrics.jsonl)
- Skill: `~/.claude/skills/workstreams/`
- Spec: `~/.claude/plans/staged-noodling-ocean.md`

## Measurement

`metrics.jsonl` logs every collect run with: total items, catchall total, coverage_pct (% of items in named workstreams), error count. Target: catchall <15% after 2 weeks of selector tuning.
