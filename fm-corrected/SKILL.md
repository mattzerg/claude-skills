---
name: fm-corrected
description: 'Manual correction override for any fakematt-* skill. When auto-reconciliation can''t pair a draft with the sent message (different thread, edited offline, sent through a different surface), use this to log the correction explicitly and capture the WHY. Appends to the appropriate corrections.md in the format promote.py mines, so the correction starts influencing future drafts immediately. Use when Matt says "FM got X wrong, the actual sent version was Y" or wants to teach FM a specific lesson.'
---

# FM Corrected — Manual Voice Correction

Thin wrapper over `~/.claude/fakematt-today/fm_corrected.py` for explicit override of FM's voice-learning loop. Closes the gap where auto-reconciliation can't pair a draft with what Matt actually sent (offline edits, different thread, sent through another tool).

## Default usage

Identifies the most-recent unchecked sent-log record for the skill, prints the diff, and (unless --dry-run) appends to corrections.md + marks the record checked.

```bash
python3 ~/.claude/fakematt-today/fm_corrected.py \
    --skill email \
    --sent-file /tmp/what_matt_actually_sent.txt \
    --reason "Cut the second CTA — pulp closer should be one ask"
```

## Specifying a particular record

If the most recent record isn't the one you want to correct, pass `--ts`:

```bash
python3 ~/.claude/fakematt-today/fm_corrected.py \
    --skill personal --ts 20260507T093412 \
    --sent "Hey Christine, ..." \
    --reason "Family emails skip the closing 'Best,'"
```

## Skills supported

`email | personal | copyedit | feedback | launch`

## What it writes

- Appends a `## YYYY-MM-DD — to <recipient>` section to the skill's `corrections.md` in the same format as auto-mined corrections (so promote.py picks it up).
- Stores `--reason` as `_Reason (manual): ..._` line for human auditability.
- Marks the sent-log record `checked: true`, sets `edit_distance: N`, sets `manual_override: true`.

## Dry-run

```bash
python3 ~/.claude/fakematt-today/fm_corrected.py --skill email --sent-file /tmp/sent.txt --dry-run
```
