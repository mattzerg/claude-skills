# LLM Feedback Ledger Shape

## Canonical paths

- Markdown ledger (human): `MattZerg/Tasks/llm-feedback-log.md`
- JSON mirror (machine): `MattZerg/.llm-feedback/<YYYY-MM-DD>-<seq>.json`

## Entry fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | `YYYY-MM-DD-NNN`, sequence resets per day |
| `when` | ISO timestamp | local PT |
| `artifact` | string | path / slug / PR# / session-id / URL — pointer is recorded raw, not resolved |
| `type` | enum | `code | prose | plan | hero | slack | email | other` |
| `feedback` | string | the natural-language correction, verbatim |
| `session_id` | string \| null | `CLAUDE_SESSION_ID` / `CODEX_SESSION_ID` env at capture time |
| `model` | string \| null | optional; caller sets `LLM_FEEDBACK_MODEL` |
| `provider` | string \| null | optional; caller sets `LLM_FEEDBACK_PROVIDER` |
| `hint` | string | `"recurring -> learn-matt classify"` or `"captured (one-off)"` |

## Recurring-trigger regex

Capture promotes to `learn-matt classify` when the feedback text matches (case-insensitive):

```
\b(always|never|every time|don't|do not|stop|this keeps|you keep|from now on|going forward)\b
```

Tune this regex in `scripts/capture.py:RECURRING_TRIGGERS` as new patterns surface.

## Promotion flow

1. `capture` writes the entry.
2. If `hint == "recurring -> ..."`, the script prints the suggested `learn-matt` command.
3. Matt (or downstream automation) runs `learn-matt classify` with the feedback text.
4. `learn-matt` decides: slot into existing composite vs. new rule file.
5. New rules get linked from `MEMORY.md` index per the existing convention.

## Anti-drift

- This skill never edits memory directly.
- This skill never edits the original artifact.
- This skill never auto-runs `learn-matt`. Promotion is always Matt-gated.
