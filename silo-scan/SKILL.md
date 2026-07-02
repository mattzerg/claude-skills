---
name: silo-scan
description: Composite cross-silo "what happened lately" reader. One call surfaces recent activity across all of Matt's data silos in one chronological feed — Codex sessions, iMessage, browser history, open Reminders, optionally ZergAudience signups. Single verb — `silo-scan [--hours N]` (default 12h). USE PROACTIVELY at the start of morning-brief, standup, or any "what's been going on" conversation. Pairs with morning-brief / standup / memory-triage — those routines currently miss most of this signal. Read-only — every call delegates to the underlying skill's read scripts; no skill ever writes back.
---

# silo-scan

One call → unified picture of what's happened across Matt's silos in the last N hours.

Sub-readers (each is read-only):

| Silo | Backed by | What it surfaces |
|---|---|---|
| Codex sessions | `codex-transcript-read` | What the other LLM has been doing, slug-tagged by `cwd` |
| iMessage | `imessage-skill` | Personal SMS/iMessage — invisible to slack-skill |
| Browser history | `browser-history-skill` | URLs Matt visited — competitive, idea, "what was that page" signal |
| Open reminders | `apple-captures-skill` | Open Reminders across all lists |
| ZergAudience signups | `zergaudience-skill` | New contacts in the canonical zstack contacts table — IF `psql` is installed |

## Usage

```bash
python3 ~/.claude/skills/silo-scan/silo_scan.py
python3 ~/.claude/skills/silo-scan/silo_scan.py --hours 24
python3 ~/.claude/skills/silo-scan/silo_scan.py --hours 2 --skip browser  # skip noisy silos
```

Sections render in order: Codex → iMessage → ZergAudience → Browser → Reminders. Each section either prints rows or `(no signal)`. Sub-readers that aren't installable (psql missing, TCC denied) print their error inline — silo-scan never hard-fails on a partial silo.

## When to use

- **At the top of `morning-brief`** — replaces the manual "I should check Slack and email" pre-pass. Currently morning-brief misses iMessage + Codex + browser entirely.
- **At the top of `standup`** — surfaces "Codex shipped X, signups: N new" lines for free.
- **`memory-triage`** — before claiming a topic isn't in flight elsewhere, scan the silos.
- **Matt asks "what's happening" / "what should I be paying attention to"** — single command answers it.

## Wire-up notes (for future Claude)

- `morning-brief` (`~/.claude/skills/morning-brief/render_rich.py`) — add a `silo_scan(hours=12)` call before the existing assembly step. Treat each silo's output as a section in the brief.
- `standup` (`~/.claude/fakematt-today/standup_draft.py`) — surface Codex-shipped slugs into the Product lane, ZergAudience new contacts into the Marketing lane.
- Anti-pattern: don't have silo-scan auto-fire from a hook. It's pull, not push.

## Read-only

Every sub-call is read-only. silo-scan adds no writes of its own.
