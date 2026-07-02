---
name: raci-matrix
description: RACI accountability matrix — rows = activities, columns = people, cells = R/A/C/I (Responsible, Accountable, Consulted, Informed). Enforces exactly-one-A per row (the most common RACI failure). Three modes — `scaffold`, `validate`, `audit`. Anchored on `MattZerg/_style/consultant_thinking_style.md`. Different from `raid-log` (risks/assumptions/issues/dependencies), `workplan-skill` (Gantt timeline), `working-session` (meeting agenda). USE PROACTIVELY when Matt says "RACI", "accountability matrix", "who does what", "ownership map", or before any multi-person workstream kicks off. Never auto-posts.
allowed-tools: Bash, Read, Write
---

# RACI Matrix

Phase 3 program-ops sibling. Locks accountability across multi-person workstreams.

## When to invoke

- Matt says "RACI", "accountability", "ownership", "who does what".
- Before a multi-person workstream kicks off.
- When ownership is fuzzy and decisions stall.

## Modes

### `scaffold`

```bash
python3 ~/.claude/skills/raci-matrix/run.py scaffold \
  --engagement <slug> --mode <mode> \
  --people "matt,idan,client-pm,client-eng" \
  --activities "discovery,data-pull,storyline-draft,deck-render,readout"
```

### `validate` — lint existing matrix

```bash
python3 ~/.claude/skills/raci-matrix/run.py validate <raci-path>
```

Enforces:
- **Exactly one A per row** (Accountable column). HIGH if violated.
- **At least one R per row**. MED if missing.
- **No empty-everyone row** (at least one R/A/C/I per row).

### `audit` — full review with anti-pattern checks

```bash
python3 ~/.claude/skills/raci-matrix/run.py audit <raci-path>
```

Adds: same person across all four roles on one row, no consulted/informed listed (common RACI thinness), >5 people on one activity (likely needs splitting).
