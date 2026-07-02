---
name: morning-brief
description: Generate Matt's daily morning brief on-demand using the same logic as the 7am M-F cron. Pulls open promises, today's meetings, overnight team signal, PR-gate state, and next 7 days into a single post. By default prints to stdout (dry-run); explicit `--post` fires to Fake Matt → Matt DM. USE PROACTIVELY when Matt asks 'what's on my plate today', 'morning brief', or starts the day before the 7am cron has fired.
---


# Morning Brief Skill

Thin wrapper over `~/.claude/fakematt-today/morning_brief.py`. Cron auto-fires at 7am M-F PT; this skill lets Matt pull the same view on-demand from any session.

## Modes

**Conversational pull (default for in-session use) — rich ASCII dashboard:**

```bash
/usr/bin/python3 ~/.claude/skills/morning-brief/render_rich.py
# or just: ~/.claude/skills/morning-brief/render_rich.py  (shebang pinned)
```

> ⚠️ Use `/usr/bin/python3` (or the script directly via its shebang), NOT bare `python3`. Homebrew's `python3` (3.14) is missing `requests` and crashes on import. The system `/usr/bin/python3` (3.9) has the deps. Same interpreter the cron uses.

Fans out morning_brief.py data builders + pr-table + workstreams state + inbox.md + Growth/decisions + action_led_targets/review (yesterday's lead status) → renders the 8-zone ASCII box. ~50 lines on a 78-col terminal. Format spec at `dashboard-template.md`.

**Slack cron view (dry-run preview):** Print the 15-line compressed Slack output.

```bash
python3 ~/.claude/fakematt-today/morning_brief.py --dry-run
```

**Post to FM DM:** Fire the Slack-compressed view to Fake Matt → Matt DM (channel `D0B0T0ETDR8`). Same as 7am M-F cron.

```bash
python3 ~/.claude/fakematt-today/morning_brief.py
```

## When to use

- Matt asks "morning brief" / "what's on my plate today" / "what should I focus on this morning"
- Matt is starting the day before the 7am cron has fired
- After a long break (weekend, travel) and Matt wants the fresh view

## Render format — depends on surface

**Conversational pull (this skill, called from a Claude Code session):** invoke `/usr/bin/python3 ~/.claude/skills/morning-brief/render_rich.py` (NOT bare `python3` — see warning above). It does the data fan-out + classification + ASCII render deterministically — don't hand-assemble. Format spec at `dashboard-template.md`.

**7am M-F cron DM:** the underlying script emits a 15-line Slack-compressed view via `slack_format.compose()`. Do not paste that verbatim when Matt asks for the brief in-session — it's a different format for a different surface.

## Sections rendered (cron view, for reference)

1. **Top 3 today** — synthesized from oldest open promise ≥3d, highest-priority Linear issue, longest meeting today, and blocked PRs (filler)
2. **Today's meetings** — with 🤝 external badge for off-domain attendees
3. **Overnight from team** — Idan / André / Michael / Alex / Franklin posts in #standup since 7pm previous business day (Mondays reach back to Friday)
4. **Open promises summary** — count, ≥3d-old count, oldest age (full list lives in digest)
5. **PR-gate today** — force overrides + currently-blocked PRs
6. **Next 7 days** — calendar lookahead (skips today's meetings, drops travel all-day events)

## Calibration

Mirrors the digest pattern but is one-shot, not rolling — fires at 7am only, posts a NEW message (does not chat-update). Designed to live alongside digest (rolling, mid-day visibility) and standup_draft (5pm, EOD draft).

Don't reinvent — this skill always shells out to the underlying script so cron + on-demand stay in sync. Reformat on the conversational surface per `dashboard-template.md`.
