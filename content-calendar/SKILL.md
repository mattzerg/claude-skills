---
name: content-calendar
description: Manage the Zerg editorial calendar mechanics — target dates and review/distribution gates. Sub-tool under zpub — for "content status", "what's publishing", or pipeline-state questions, use `zpub all` (hard rule 13), not this skill.
allowed-tools: Bash, Read, Write
---


# Content Calendar Skill

Sequences editorial work into a dated queue with state transitions. Sister to `experiment-tracker` (same vault pattern, different domain — experiments vs content pieces).

## Why this exists

The pieces (`programmatic-seo`, `blog-imagery`, `fakematt-copyedit`, `launch-announcement`, `content-distribution`) all work, but nothing sequences them into a publishable queue. Result: Matt holds the calendar in his head, things slip, and there's no "what's overdue" view.

This skill is the orchestrator. It doesn't generate content — it tracks state and routes to the right downstream skill at each transition.

## States

```
idea → drafted → reviewed → scheduled → published → distributed
```

Forward-only. Skipping is refused. Slipping a target date is allowed (logs reason).

## Modes

### `add` — register a new piece

```bash
python3 ~/.claude/skills/content-calendar/run.py add \
  --title "Why agent memory matters" \
  --type blog \
  --target 2026-05-15 \
  --slug agent-memory \
  --owner Matt
```

Types: `blog | launch | pseo | case-study | newsletter | thread`. Each type has type-specific gates (e.g. `case-study` requires NDA clearance before `scaffolded`; `launch` requires `launch-announcement` review before `reviewed`).

### `next` — today's queue + forecast

```bash
python3 ~/.claude/skills/content-calendar/run.py next [--days 7]
```

Lists pieces with target dates within the window, sorted by date. Shows current state and next required action.

### `status` — table view of all pieces

```bash
python3 ~/.claude/skills/content-calendar/run.py status [--state idea|drafted|...] [--type blog|...]
```

Markdown table of all pieces. Used by `growth-dashboard` line for content-distribution coverage.

### `slip` — push target date

```bash
python3 ~/.claude/skills/content-calendar/run.py slip --slug agent-memory --to 2026-05-22 --reason "waiting on Idan review"
```

Updates target date, appends slip-log entry. Three slips on the same piece triggers a warning (drift alert).

### `transition` — move state forward

```bash
python3 ~/.claude/skills/content-calendar/run.py transition --slug agent-memory --to reviewed
```

Refuses if required artifact for the state is missing. Suggests the next downstream skill (e.g. `transition --to drafted` → "next: run blog-imagery").

### `pulse` — terminal-friendly publishing snapshot

```bash
python3 ~/.claude/skills/content-calendar/run.py pulse [--past-days 30] [--next-days 30]
```

Single-screen view, ≤36 chars wide, intended for recurring inline check-ins. Three sections:

- **PAST 30D** — pieces in `published`/`distributed` with target_date in the past window
- **NEXT 30D** — pieces in any non-terminal state with target_date in the upcoming window (sorted by date, shows days delta)
- **OVERDUE** — pieces with target_date in the past but state still non-terminal (sorted oldest-first)

Per-row columns: `MM-DD slug T ST O [D]` — date, slug (truncated to 17, prefixed `!` if slips ≥ 3), type marker (B/L/P/C/N/T), state code (id/dr/rv/sc/pb/di), owner initial, and (NEXT/OVERDUE only) signed days delta.

Use as the "what shipped, what's next, what's slipping" daily/weekly check. Pair with `audit` (drift alarms) and `next` (artifact-routing forecast).

### `audit` — flag overdue + missing artifacts

```bash
python3 ~/.claude/skills/content-calendar/run.py audit
```

Surfaces:
- Pieces past target date still in non-terminal state
- Pieces in `drafted` without imagery (would block `reviewed`)
- Pieces in `published` without distribution (would block `distributed`)
- Pieces with ≥3 slips

Used by Monday cron (light version of growth-dashboard).

## Ledger schema (per-piece YAML frontmatter)

```yaml
---
slug: agent-memory
title: "Why agent memory matters"
type: blog
state: drafted
target_date: 2026-05-15
slips: 0
slip_log: []
owner: Matt
created: 2026-05-07
artifacts:
  draft: ~/zerg/web/src/public/content/blog/agent-memory.md
  imagery: ~/zerg/web/src/public/images/blog/agent-memory/
  copyedit_review: ""
  distribution_card: ""
related_experiments: []
---
```

## Anti-drift contract

- **Forward-only state machine.** No regressions; if a piece needs to go back to `drafted`, mark it `cancelled` and create a new piece.
- **`distributed` requires `content-distribution` card filed.** Hard rule.
- **`reviewed` requires `fakematt-copyedit` artifact.** Hard rule for type=blog/launch.
- **`scheduled` requires target_date ≤ 14 days out.** Beyond that = back to `drafted`.
- **3 slips on the same piece = audit alert.** Drift forcing function.

## Routing to other skills

| Transition | Suggested next skill |
|---|---|
| `idea → drafted` (type=pseo) | `programmatic-seo` |
| `idea → drafted` (type=launch) | `launch-announcement` (scaffold) |
| `idea → drafted` (type=case-study) | `case-study-skill` (scaffold) |
| `drafted → (any)` | `blog-imagery` |
| `(any) → reviewed` | `fakematt-copyedit` |
| `(launch) → reviewed` | `launch-announcement` (review) |
| `published → distributed` | `content-distribution` |
| Any external link | `utm-attribution` |

## Why this isn't a Zergboard wrapper

Content workflow has type-specific transitions that cards alone can't enforce: pseo doesn't need launch-announcement; case-study needs NDA gate; blog needs imagery before review. The calendar logic in Python is what makes the gates real.

## Implementation notes

- File-based, no DB
- Per-piece file at `MattZerg/Projects/Zerg-Production/Growth/content/<slug>.md`
- Top ledger at `Growth/content-calendar.md` (regenerated from per-piece files on each `status` call)
- Cache nothing — always re-read source of truth
- States transition forward-only; refuses skips
