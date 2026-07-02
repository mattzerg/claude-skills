---
name: fm-ops
description: 'Generate Matt''s weekly Fake Matt operational dashboard on-demand using the same logic as the Monday 7:30am cron. 10 lines: open promises, standup cadence, PR-gate overrides, blocked PRs, days-since-last-standup, cron health, DM dispatches, promises cleared, meeting brief coverage, open question of the week. By default prints to stdout (dry-run); explicit --post fires to Fake Matt → Matt DM and writes to vault. USE PROACTIVELY when Matt asks for the FM-ops weekly review, ''how is FM doing'', ''where is FM drifting'', or before a phase-gate review of the FM toolchain.'
---


# FM-ops Dashboard Skill

Thin wrapper over `~/.claude/fakematt-today/fm_ops_dashboard.py`. Cron auto-fires Mondays at 7:30am PT (sequenced 30 min after `growth-dashboard` so the DM stream stays ordered: growth → ops). This skill lets Matt pull the same 10-line view on-demand any day.

## Modes

**Default (dry-run):** Print the dashboard to stdout.

```bash
python3 ~/.claude/fakematt-today/fm_ops_dashboard.py --dry-run
```

**Post:** Fire to Fake Matt → Matt DM (channel `D0B0T0ETDR8`) AND write the body to `MattZerg/Projects/Zerg-Production/Growth/weekly/fm-ops/YYYY-MM-DD.md`.

```bash
python3 ~/.claude/fakematt-today/fm_ops_dashboard.py
```

## When to use

- Matt asks "FM ops" / "how is Fake Matt doing" / "weekly FM review"
- Before any phase-gate decision on the FM toolchain
- After a long break to see what drifted

## The 10 lines

1. **Open promises** — count, oldest age, count ≥7d
2. **Standup cadence** — posts this week vs target 3+
3. **PR-gate overrides last 7d** — count + reasons (capped at 3 + "+N")
4. **Blocked PRs** — currently across `~/zerg`, `~/zerg/zergwallet`, `~/.claude/skills`
5. **Days since last #standup post**
6. **FM cron health** — worst daemon delta from `health_state.json` (placeholder until that file is wired)
7. **DM dispatches last 7d** — count by destination (Linear/Zergboard/Gmail/Calendar). Phase F state file; until then shows "0".
8. **Promises cleared last 7d** — via promise_state status transitions
9. **Meeting briefs last 7d** — sum of "posted N briefs" lines from `brief.log`
10. **Open question of the week** — auto-rotates from a 10-question pool by ISO week number

## Calibration

Mirrors `growth-dashboard` register: numbered bullets, no padding, embarrassing-3-weeks-running = forcing function. Lines that depend on Phase E/F state files gracefully show a placeholder until those phases ship in Stretch 2.

Don't reinvent — this skill always shells out to the underlying script.
