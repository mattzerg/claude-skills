---
name: session-handoff
description: Cross-session continuity lookup. Before regenerating, redoing, or producing v2/v3 of any artifact, check whether a sibling session (same Claude, different window) already touched the slug/branch/file and what it declared canonical. Backed by an append-only JSONL written by the session_handoff_capture Stop hook. USE PROACTIVELY before any "regenerate" / "v2" / "redo" / "fix the X" verb on shared content; pairs with `feedback_hero_cross_session_approval_awareness.md`.
---

# Session-Handoff Skill

Operationalizes the "cross-session approval awareness" memory rule. Instead of
relying on Claude remembering what sibling sessions did, it persists the
relevant state to disk on Stop and lets future sessions query it.

## When to use

**MANDATORY before any of:**
- regenerating an image / hero / asset that may already exist
- producing a "v2" / "v3" / "fix" of an artifact
- declaring a content slug "needs draft" / "ready to ship"
- editing a file that another session may have just modified

**Useful for:**
- triage views — see what's actively moving in other sessions
- post-incident — "which session approved this and when"

## Commands

```bash
# Search: did any sibling session touch this slug/branch/file?
/usr/bin/python3 ~/.claude/skills/session-handoff/lookup.py gigacontext-threshold
/usr/bin/python3 ~/.claude/skills/session-handoff/lookup.py matt/zergvert-foundation

# Wider window
/usr/bin/python3 ~/.claude/skills/session-handoff/lookup.py gigacontext-threshold --days 7

# Survey recent activity
/usr/bin/python3 ~/.claude/skills/session-handoff/lookup.py --recent --hours 24

# Audit-grade
/usr/bin/python3 ~/.claude/skills/session-handoff/lookup.py --approvals --days 7
/usr/bin/python3 ~/.claude/skills/session-handoff/lookup.py --canonical --days 7
```

## What the index captures

Every session-stop (the `Stop` hook fires), the capture script writes one JSONL
record at `~/.claude/state/session_handoff.jsonl` containing:

- `session_id`, `ts`, `cwd`, `transcript_path`, `record_count`
- `pub_slugs` — every `pub-*` ID mentioned in transcript
- `dashed_slugs` — likely-content slugs (3+ dashed parts, 12–80 chars)
- `branches` — `matt/* feat/* fix/* chore/* docs/*`
- `approvals` — `zerg_approve.py …` and `zpub.py set … gates.signoff/approval.locked …`
- `canonical_declared` — boolean: did the assistant declare any artifact "canonical/final/approved"
- `vault_paths`, `zerg_paths`, `claude_paths` — file paths mentioned

It does NOT capture full transcripts — only structured signals. The transcript
file path is recorded so deeper inspection is possible after a hit.

## Wiring

Stop hook (writes the index):
- `~/.claude/hooks/session_handoff_capture.py`
- Append-only writes to `~/.claude/state/session_handoff.jsonl`
- Fail-open; budget ≤8s

Lookup CLI (reads the index):
- `~/.claude/skills/session-handoff/lookup.py`
- Read-only

## When NOT to use

- For active-session in-flight check, use `zinflight` instead (it shows
  *running* sessions, this skill shows *finished* ones).
- For PR queue state, use `pr-table` — this skill doesn't track GitHub.
- For content state, use `zpub` / `zstate` — this skill is a tripwire layer
  on top, not a replacement.
