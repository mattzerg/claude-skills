---
name: working-session
description: Pre-meeting agenda scaffolder + live decision log + parking-lot capture for engagement working sessions. Three modes — `scaffold` (build agenda from engagement state + invitees), `log` (append decision/parking item during session), `summarize` (post-meeting digest with action items + decisions made + next session). Anchored on `MattZerg/_style/consultant_thinking_style.md`. Different from `workplan-skill` (full Gantt — sessions are atomic), `raid-log` (risks/assumptions — sessions surface them), `raci-matrix` (accountability map — sessions reference it). USE PROACTIVELY when Matt says "working session", "meeting agenda", "decision log", "facilitate", "parking lot", or before any scheduled engagement meeting. Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Working Session

Phase 3 program-ops sibling. Single-meeting structure for engagement working sessions.

## When to invoke

- Matt says "working session", "meeting agenda", "facilitate", "decision log", "parking lot".
- Before any scheduled engagement meeting (>30min).
- During / after a meeting to capture decisions + actions.

## Modes

### `scaffold`

```bash
python3 ~/.claude/skills/working-session/run.py scaffold \
  --engagement <slug> --mode <mode> \
  --date 2026-06-15 --duration 60 \
  --invitees "matt,idan,client-pm" \
  --topics "review hypothesis tree,decide go/no-go on Plan B"
```

Writes `<engagement>/working-sessions/<date>.md` with timed agenda blocks, decision-log table, parking-lot table, action-item table.

### `log` — append during/after session

```bash
python3 ~/.claude/skills/working-session/run.py log <session-path> \
  --type decision --description "Approved Plan B at $120K" --owner client-pm
```

Types: `decision`, `action`, `parking-lot`, `question-for-followup`.

### `summarize` — post-session digest

```bash
python3 ~/.claude/skills/working-session/run.py summarize <session-path>
```

Prints clean summary suitable for cross-team broadcast.
