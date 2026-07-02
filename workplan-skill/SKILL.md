---
name: workplan-skill
description: Workplan / Gantt-style timeline — milestones, owners, dependencies, start/end dates, lightweight critical-path indication. Reads a YAML/JSON spec OR scaffolds empty, renders a Gantt-like horizontal bar via `chart-builder`. Anchored on `MattZerg/_style/consultant_thinking_style.md`. Different from `raid-log` (risks/dependencies in static list, not timeline), `raci-matrix` (who-does-what, no dates), `working-session` (single meeting agenda). USE PROACTIVELY when Matt says "workplan", "Gantt", "timeline", "milestones", "project plan", "critical path", "phase plan", or before any multi-week engagement kicks off. Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Workplan

Phase 3 program-ops sibling. Multi-week timeline with milestones + owners.

## When to invoke

- Matt says "workplan", "Gantt", "timeline", "milestones", "project plan", "critical path".
- Before a multi-week engagement kicks off.

## Modes

### `scaffold`

```bash
python3 ~/.claude/skills/workplan-skill/run.py scaffold --engagement <slug> --mode <mode>
```

### `render` — from JSON spec

```bash
python3 ~/.claude/skills/workplan-skill/run.py render spec.json --engagement <slug> --mode <mode>
```

Spec JSON:
```json
{
  "tasks": [
    {"id": "T1", "name": "Discovery", "owner": "matt", "start": "2026-06-01", "end": "2026-06-07", "depends_on": []},
    {"id": "T2", "name": "Data pull", "owner": "idan", "start": "2026-06-08", "end": "2026-06-14", "depends_on": ["T1"]},
    {"id": "T3", "name": "Analysis", "owner": "matt", "start": "2026-06-15", "end": "2026-06-21", "depends_on": ["T2"]},
    {"id": "T4", "name": "Readout", "owner": "matt", "start": "2026-06-22", "end": "2026-06-23", "depends_on": ["T3"], "milestone": true}
  ]
}
```

Writes `<engagement>/07-workplan.md` + `.../charts/workplan-gantt.png`.

## Critical-path notes

Simple longest-path through dependencies. Marked in the markdown body. Not a full resource-leveled MS Project replacement — meant for "is this 2 weeks or 6?" calibration.
