---
name: codex-transcript-read
description: Read recent Codex CLI session transcripts so Claude can see what the other model in Matt's stack has been doing. Backed by `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`. Verbs — `recent [--hours N]` (default 24h, lists sessions by newest with cwd + first user message), `for-slug SLUG` (filters sessions whose cwd contains the slug), `show SESSION-ID` (dumps the user turns of one session). Use whenever cross-LLM coordination matters — memory-triage, cross-model-check, standup, "what did Codex do today," "is Codex already working on X."
---

# codex-transcript-read

Cross-model visibility skill. Codex CLI writes a JSONL transcript per session to `~/.codex/sessions/YYYY/MM/DD/rollout-<ISO-ts>-<session-id>.jsonl`. This skill reads them.

Sibling intent: a `claude-transcript-read` skill should live on the Codex side, pointing at `~/.claude/projects/`. Not built here — Codex owns its own skill set.

## Verbs

### `recent [--hours N]`
List sessions newer than N hours, newest first. Default 24h.

```bash
python3 ~/.claude/skills/codex-transcript-read/read_codex.py recent --hours 24
```

Output per session: `[timestamp] <session-id-short>  cwd=<path>  msgs=<N>  first="<first user message, truncated>"`.

### `for-slug <slug>`
Same as `recent` but filtered to sessions where `cwd` contains the slug substring. Useful for "is Codex already working on `zergvert-alpha-launch`."

```bash
python3 ~/.claude/skills/codex-transcript-read/read_codex.py for-slug zergvert --hours 72
```

### `show <session-id>`
Dump the user-turn text of a specific session (full or short id prefix match).

```bash
python3 ~/.claude/skills/codex-transcript-read/read_codex.py show 019e47c4
```

## When to use

- Before claiming "Codex hasn't touched X" or "no one is working on X."
- During `memory-triage` / `cross-model-check` to see Codex's recent surface.
- When Matt asks "what's Codex been doing" or "what did the other side ship today."
- Pairs with `feedback_check_in_flight_across_silos.md` — this is the Codex-side check that memory rule implies.

## Read-only

Never writes to `~/.codex/`. Never modifies transcripts.
