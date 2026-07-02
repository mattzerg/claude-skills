---
name: triage
description: Single-screen "who's blocked by whom" view across Matt's workstreams. Renders 4 sections — Blocked by Matt (decisions/replies Matt owes), Autonomous in flight (sessions/agents currently running), Autonomous queued (work Claude can pick up on greenlight), Async-waiting (counterparties owe a reply). Fans out to workstreams + zpub + pr-table + inbox.md without re-pulling, in ~10s. USE PROACTIVELY when Matt asks "what's blocked by me", "where are we", "what should I focus on", or before any planning conversation. Sibling to morning-brief (daily firehose); /triage is the categorical filter on top.
---

# Triage Skill

Single-screen, 4-section view for "what's blocked by me vs. autonomous":

1. **Blocked by you** — items where Matt is the sole unblocker (decision, signoff, send, call, payment).
2. **Autonomous in flight (mine)** — sessions and agent dispatches currently running.
3. **Autonomous queued (yours to greenlight)** — work Claude can execute on a single "go".
4. **Async-waiting** — external counterparties owe a response (Idan PR reviews, vendor invoices, etc.).

## Run modes

```bash
# Conversational pull, default — print 4-section ASCII box to stdout
/usr/bin/python3 ~/.claude/skills/triage/run.py

# JSON dump (for downstream tools)
/usr/bin/python3 ~/.claude/skills/triage/run.py --json
```

Uses `/usr/bin/python3` per `feedback_gui_path_resolution.md` — bare `python3` picks Homebrew (Python 3.14) which is missing transitive deps.

## When to use

- Matt asks: "what's blocked by me", "where are we", "what should I focus on", "what can you do without me", "triage", or any planning-prologue question.
- Before standup or signoff sessions — quickly enumerates what Matt has to decide vs. what's already moving.

## Output structure

4 ASCII-boxed sections, ranked within each by recency / external counterparty count.

## Sources

- `workstreams show` (cache + live mix; counts inbox + ideas + PRs per workstream)
- `zpub all` (publishing pipeline state)
- `pr-table run.py` (open PRs + held branches across Zerg repos)
- `inbox.md` (TODO + blocked tags)
- `~/.claude/state/correction_repairs.jsonl` (recent loop activity)
- `zinflight` (active sessions)

## What's NOT here

- No deep-dive on any one item — for that, use the specific tool (`zpub show <slug>`, `gh pr view`, etc.)
- No counterfactual or strategic recommendations — just classification of current state.
- No mutations — strictly read-only.
