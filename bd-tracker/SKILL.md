---
name: bd-tracker
description: Track Product BD partner conversations + Solutions referrer pipeline. Thin Zergboard-board template + skill that logs partner status (planned / outreach / engaged / paused / closed-won / closed-lost), next-touch dates, owner, conversation threads. Reads MattZerg/Projects/Zerg-Production/Growth/bd-targets.md (canonical 25-target list). Posts stale-card alerts to Slack DM for cards untouched >14 days. Sister to network-reach (warm prospecting) and prospects.md (Solutions deal pipeline). Phase 2 build (Day 31–60), small effort. USE PROACTIVELY when Matt mentions a partner conversation, integration discussion, podcast pitch, ecosystem listing, or co-marketing opportunity.
allowed-tools: Bash, Read, Write
---


# BD Tracker Skill (v1 — Phase 2, implemented 2026-05-07)

Plan: `~/.claude/plans/i-am-planning-growth-splendid-bee.md`. Dogfood pattern: Zergboard board IS the CRM, this skill is a thin wrapper.

## Status

**v1 — implemented.** All 4 modes (`list`, `log`, `status`, `stale`) functional. File-based touch log at `Growth/bd-touch-log.md`. Reads 28 targets from `Growth/bd-targets.md`.

## What it does

Two-way sync between `MattZerg/Projects/Zerg-Production/Growth/bd-targets.md` and a Zergboard "BD" board.

```bash
python3 ~/.claude/skills/bd-tracker/run.py sync           # bd-targets.md → Zergboard cards
python3 ~/.claude/skills/bd-tracker/run.py log <target> --note "..." [--status NEW]
python3 ~/.claude/skills/bd-tracker/run.py stale [--days 14]   # alerts for stale cards
python3 ~/.claude/skills/bd-tracker/run.py list [--category integration|co-marketing|podcast|ecosystem]
```

## Status legend

`planned` (on list, no contact yet) · `outreach` (first contact sent) · `engaged` (in conversation) · `paused` · `closed-won` · `closed-lost`

## Anti-drift contract

- Cards untouched >14 days → `stale` mode posts to Slack DM
- Status transitions logged with date + note
- Phase-gate review (Day 90, 180): any card in `planned` status >60 days gets archived

## Build phases

- **Phase 2 Day 31–45:** v0 — `sync`, `log`, `stale`, `list` modes
- **Phase 2 Day 60+:** v0.1 — auto-create Zergboard cards from new bd-targets.md rows
- **Phase 3:** v1 — read partner-conversation threads from Gmail (via gmail-skill) and surface activity

## Implementation notes

- File-based + Zergboard board sync; no separate DB
- Reuses `zergboard-skill` patterns for board interaction
- Slack DM via `slack-skill` for stale alerts (channel `D0B0T0ETDR8`)

## Pairs with

- `network-reach` for warm-network prospecting (Solutions side)
- `prospects.md` for Solutions deal pipeline (separate from BD)
- `bd-targets.md` for canonical Product BD target list
