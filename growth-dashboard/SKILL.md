---
name: growth-dashboard
description: Generate the weekly Zerg growth dashboard — auto-posts every Monday 7am PT to Matt's Slack DM with the 11 priority lines (activated accounts, paid conversions, activation rate, top sources, active experiments, Solutions pipeline, case-study status, content distribution coverage, email program health, referral metrics, open question of the week). Reads Zergalytics public API + Growth/experiments.md + Zergboard cards (via zergboard-skill) + Stripe webhooks (when revenue live). Writes to ~/Obsidian/Zerg/MattZerg/Projects/Zstack/Growth/weekly/YYYY-MM-DD.md and posts to Fake Matt → Matt DM. Critical anti-drift guardrail — auto-posts whether or not Matt feels ready; embarrassing line items 3 Mondays in a row = forcing function. USE PROACTIVELY when Matt asks for the weekly review, "where are we", or before any growth meeting / phase gate.
allowed-tools: Bash, Read, Write
---

# Growth Dashboard Skill (v0 stub — Phase 1 Day 3–7 build)

The measurement spine for the Zerg growth program. Plan: `~/.claude/plans/i-am-planning-growth-splendid-bee.md`.

## Status

**v0 stub — not yet implemented.** Phase 1 Day 3–7 deliverable. Even a 3-line version is acceptable to ship — the schedule is what matters, not feature completeness. Once running it iterates.

## What it produces

A Markdown file at `~/Obsidian/Zerg/MattZerg/Projects/Zstack/Growth/weekly/YYYY-MM-DD.md` with these 11 lines, in priority order:

1. **Activated accounts this week** (signup + "aha" event)
2. **Paid conversions** ($1, $9, $19 bundle, Enterprise) with net-new MRR + churn delta
3. **Activation rate** (activated / signed-up, 7-day cohort)
4. **Top 3 acquisition sources by activated accounts** (UTM-resolved)
5. **Active experiments + days-until-kill-date** with current read vs. threshold
6. **Solutions pipeline** (# qualified, # proposals out, weighted $, won-this-week $)
7. **Case-study-in-flight status** (captured / drafted / reviewed / published)
8. **Content distribution coverage** (last week's blog → how many of 14 surfaces hit)
9. **Email program health** (list size, last broadcast open/click, drip activation rate)
10. **Referral metrics** (Phase 2+: K-factor, # Solutions referrals received)
11. **Open question of the week**

## Invocation

```bash
python3 ~/.claude/skills/growth-dashboard/run.py [--week YYYY-WW] [--no-post]
```

Cron entry (Phase 1 Day 7):
```
0 7 * * 1  python3 ~/.claude/skills/growth-dashboard/run.py >> ~/.claude/skills/growth-dashboard/run.log 2>&1
```

Flags:
- `--week YYYY-WW` — target a specific week (default: current week)
- `--no-post` — generate file only, skip Slack DM
- `--verbose` — log data sources + counts

## Data sources (in priority order, partial OK Phase 1)

1. **Zergalytics public API** at `https://zerglytics.fly.dev/api/v1/...` — primary event-stream metrics
2. **`Growth/experiments.md` + `Growth/experiments/<id>.md`** — active experiments + kill dates
3. **Zergboard cards via `zergboard-skill`** — Solutions pipeline, case-study-in-flight, content distribution checklist completion
4. **Stripe webhooks** (when revenue live) — paid conversions
5. **Email program**: Phase 1 = Gmail thread search; Phase 2 = ESP API (Resend/ZergMail)

If a data source is unavailable, render the line as `(no data — TODO: <source>)` instead of failing.

## Output destinations

- **Primary**: `~/Obsidian/Zerg/MattZerg/Projects/Zstack/Growth/weekly/YYYY-MM-DD.md`
- **Secondary**: Slack DM via `slack-skill` to Fake Matt → Matt DM (channel `D0B0T0ETDR8` per memory)
- **Tertiary** (Phase 2): Zergboard card on the Growth board with the same content

## Anti-drift contract

- **Auto-posts every Monday 7am PT regardless of Matt's readiness.** Embarrassing line items 3 Mondays in a row = forcing function for fixing data sources.
- **Phase-gate review (Day 30, 90, 180):** must show ≥9 of 11 lines populated.
- **No skill ships without a corresponding line on this dashboard.** Inverse: every skill we build must move at least one line.

## Build phases

- **Phase 1 (Day 3–7):** v0 — Markdown only, lines 1–6 from manual data + Zergboard read; lines 7–11 stubbed
- **Phase 1 (Day 14–25):** v0.1 — Slack DM auto-post wired
- **Phase 1 (Day 25–30):** v0.2 — Zergalytics API integration for lines 1, 3, 4
- **Phase 2 (Day 31–60):** v1 — full 11 lines with real data
- **Phase 2 (Day 60–90):** v1.1 — Zergboard card output, dashboard read of Stripe events
- **Phase 3 (Day 91–180):** v2 — cohort layer + attribution layer surfaced

## Output register

Professional/operational. Not casual. No emoji. Direct numbers, no padding. If a line moved >10% W/W, flag it. If a line moved <2%, mute it. Don't editorialize the numbers.

## Implementation notes

- Use `~/.claude/skills/zergboard-skill/` patterns for Zergboard reads
- Use `~/.claude/skills/slack-skill/` for the auto-post (channel `D0B0T0ETDR8`)
- Cache prior week for delta calc; store at `state/weekly-cache.json`
- File-based state, no DB required
