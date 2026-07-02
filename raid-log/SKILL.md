---
name: raid-log
description: RAID log — Risks / Assumptions / Issues / Dependencies tracker. Reads or scaffolds a structured markdown table per category with owner, status, mitigation, due date. Three modes — `scaffold` (build empty from engagement context), `add` (append a single row from CLI flags), `review` (audit existing for stale entries + missing owners). Anchored on `MattZerg/_style/consultant_thinking_style.md`. Different from `raci-matrix` (who-does-what per activity), `workplan-skill` (Gantt timeline), `working-session` (meeting agenda + decisions). USE PROACTIVELY when Matt says "RAID log", "risks and dependencies", "what could go wrong", "track the unknowns", "assumptions register", or during any multi-week engagement. Never auto-posts.
allowed-tools: Bash, Read, Write
---

# RAID Log

Phase 3 program-ops sibling. Tracks Risks / Assumptions / Issues / Dependencies for a multi-week engagement.

## When to invoke

- Matt says "RAID log", "risks", "assumptions", "issues", "dependencies", "what could go wrong", "track unknowns".
- Mid-engagement risk-review touchpoints.

## Modes

### `scaffold`

```bash
python3 ~/.claude/skills/raid-log/run.py scaffold --engagement <slug> --mode <mode>
```

Writes `<engagement>/07-raid.md` with empty tables.

### `add`

```bash
python3 ~/.claude/skills/raid-log/run.py add <path> --category risk \
  --description "Activation model assumes signup→aha in 7d" \
  --owner matt --status open --due 2026-06-15 --mitigation "Validate against last 30d data"
```

### `review`

```bash
python3 ~/.claude/skills/raid-log/run.py review <path>
```

Flags rows without owner, stale rows (>14d no update), risks marked open but past due, missing mitigation on HIGH-severity risks.

## Output shape

```markdown
## Risks
| ID | Description | Severity | Likelihood | Owner | Status | Due | Mitigation |
| R1 | ... | high | med | matt | open | 2026-06-15 | ... |

## Assumptions
| ID | Description | Owner | Status | Validation plan |

## Issues
| ID | Description | Severity | Owner | Status | Due | Resolution |

## Dependencies
| ID | Description | Depends on | Owner | Status | Due |
```
