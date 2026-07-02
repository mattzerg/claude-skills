---
name: llm-feedback
description: Capture lane for natural-language feedback on any LLM output (Claude or Codex drafts, code, plans, prose, hero, slack, email). Appends a structured entry to MattZerg/Tasks/llm-feedback-log.md + JSON mirror at MattZerg/.llm-feedback/, auto-classifies the entry into a learn-matt bucket (needs-tool-regression / needs-skill-wiring / new-rule / already-covered / archive-only), and when the feedback names a recurring rule hands off to `learn-matt classify`. Use whenever Matt corrects an LLM output ("this should have...", "don't do X again", "redo Y but with Z") and the correction is reusable. Sibling to `learn-matt` (memory consolidation). Verbs — `capture` (default; `--dry-run` supported), `list --days N`, `promote ID`, `reclassify ID BUCKET`, `digest --since=last-friday [--post]`. Friday 4pm PT digest auto-fires via launchd. Never auto-edits the artifact; never auto-writes memory rules.
---

# LLM Feedback Skill

## Overview

One-shot capture for natural-language feedback on any LLM-generated artifact. Writes a dated, structured entry to `MattZerg/Tasks/llm-feedback-log.md` (the canonical ledger) and prints the entry + a suggested next-step (`learn-matt classify` if the feedback names a recurring rule, otherwise "captured, one-off").

Phase 2 added: auto-classify on capture, `reclassify` verb for overrides, `digest` verb + Friday 4pm PT launchd cron, and an optional Stop hook that suggests `capture` when a correction-shape lands in the session's last few user turns.

The point is to keep the friction of "this output was wrong, here's why" near zero so Matt actually gives the feedback. Memory promotion / hook wiring / skill edits stay downstream in `learn-matt` and `skill-editor`.

## When to use

- Matt says something like "this should have / shouldn't have / next time / don't ever / always" about a Claude or Codex output.
- Matt redoes work that the LLM produced and gives the reason.
- An artifact ships and Matt later flags a regression class ("you keep doing X").

## When NOT to use

- One-off typo fix on a single artifact (just edit it).
- Feedback that's already captured in a recent `MEMORY.md` entry — verify first.
- Memory promotion / rule consolidation — that's `learn-matt classify` + `learn-matt doctor`.

## Verbs

### `capture` (default)

```bash
python3 ~/.claude/skills/llm-feedback/scripts/capture.py capture \
  --artifact <path-or-slug-or-pr-or-session-id> \
  --feedback "<natural language feedback>" \
  --type <code|prose|plan|hero|slack|email|other> \
  [--dry-run]
```

Appends an entry with: ISO timestamp (PT), artifact pointer, feedback, type tag (auto-inferred from artifact extension when `--type other`), session id (auto-detected from `CLAUDE_SESSION_ID`/`CODEX_SESSION_ID`), model+provider (from `LLM_FEEDBACK_MODEL`/`LLM_FEEDBACK_PROVIDER` env), promotion hint, and **auto-classified bucket** (mirrors `learn-matt` bucket regex inline so capture doesn't shell out).

`--dry-run` classifies + prints without writing — useful for testing.

### `list [--days N]`

Tail-style view of the ledger over the last N days (default 7).

### `promote <entry-id>`

Prints the `learn-matt classify` hand-off command for the entry; does NOT auto-run it.

### `reclassify <entry-id> <bucket>`

Override the auto-assigned bucket. Bucket must be one of: `wrong-model-picked`, `needs-tool-regression`, `needs-skill-wiring`, `new-rule`, `already-covered`, `archive-only`. Updates the JSON mirror and appends a `RECLASSIFIED:` audit note to the ledger (append-only invariant preserved).

### The `wrong-model-picked` bucket (aitr feedback loop)

Corrections like "haiku would have been fine", "wrong model", "too expensive for this" auto-classify into `wrong-model-picked`. When the artifact pointer or feedback text contains an aitr decision id (`aitr-YYYYMMDD-HHMMSS-xxxxxx` — printed by every `aitr pick` and recorded in gate review files), the capture stores it as `aitr_decision_id`. aitr's ranker reads these corrections and applies a bounded penalty (-0.1 per correction, cap -0.3, 60-day decay) to the corrected (caller, task_kind, model) combination on future picks. The weekly `aitr` tuning report (`~/.claude/skills/aitr/scripts/weekly_report.py`, optionally cron'd via the plist template in that skill) reports active penalties and suggests routing-table changes when corrections cluster.

### `digest --since=<date|last-friday> [--post]`

Renders a grouped-by-bucket digest of captures in the window. `--post` fires to Fake Matt -> Matt DM (best-effort via slack-skill `send_dm.py` or the `fakematt-today` self-DM script). The launchd plist at `~/Library/LaunchAgents/com.matteisn.llm-feedback-digest.plist` runs this Friday 4pm PT, mirroring `workstreams rayg` cadence.

## Storage

- Canonical ledger: `MattZerg/Tasks/llm-feedback-log.md` (markdown table, append-only). Phase 2 added a `Bucket` column — migration is idempotent on first Phase 2 write.
- Per-entry mirror: `MattZerg/.llm-feedback/<YYYY-MM-DD>-<seq>.json` (machine-readable, used by `learn-matt` and digest).
- Cron log: `~/.claude/skills/llm-feedback/_workdir/cron-digest.log`.

## Hand-offs

- **`learn-matt classify`** — promotion path. Runs after capture if `promotion_hint == "recurring"` and Matt confirms.
- **`skill-editor`** — when the captured feedback is "this skill's trigger description should be tighter" or "this skill is missing a verb."
- **Memory composite (`MEMORY.md` index)** — only via `learn-matt`; never written directly from this skill.

## Hooks (Matt activates manually)

- `~/.claude/hooks/llm_feedback_stop_suggest.py` — Stop hook. If the session's last few user turns match a correction-shape, prints a suggested `llm-feedback capture` invocation in the Stop output. Not auto-wired; Matt adds to `settings.json` `hooks.Stop` to activate.

## Cron (Matt activates manually)

- `~/Library/LaunchAgents/com.matteisn.llm-feedback-digest.plist` — Friday 4pm PT digest. Matt runs `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.matteisn.llm-feedback-digest.plist` to activate.

## Anti-drift

- This skill captures; it does not consolidate, edit memory, or modify the artifact.
- No auto-promotion. The `recurring` hint and auto-bucket are advisory; Matt or `learn-matt` decides.
- Ledger is append-only. Reclassify writes an audit note, never mutates rows.
- Auto-classify regex is duplicated from `learn-matt` BUCKETS for capture-time speed — keep in sync.

## Pairs with

- `learn-matt` — memory promotion / consolidation / doctor.
- `skill-editor` — when feedback targets a skill's trigger or workflow.
- `response_quality_audit.py` — retrospective audit; this skill is the proactive intake.
- `correction_capture_inline.py` — UserPromptSubmit hook that writes a draft to `~/.claude/state/feedback_inbox/`; this skill is the canonical-ledger lane.
