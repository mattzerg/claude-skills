---
name: standup
description: 'Generate a Slack #standup draft on-demand using the same exec-format logic as the 5pm cron. Reads activity from Matt''s last #standup post (floored at start-of-yesterday-PT) and renders Marketing / Product / BD / Skills / Admin lanes — empty lanes are omitted, never placeholdered. By default prints to terminal (dry-run); explicit `--post` fires to Fake Matt → Matt DM. USE PROACTIVELY when Matt asks for a standup draft, says ''what would I post'', or is about to post before the 5pm cron has fired.'
---


# Standup Skill

Thin wrapper over `~/.claude/fakematt-today/standup_draft.py` so Matt can pull a draft on-demand from any session, not just at the 5pm cron.

## Modes

**Default (dry-run):** Print the draft to stdout. Matt copies what he wants.

```bash
python3 ~/.claude/fakematt-today/standup_draft.py --dry-run
```

**Post:** Fire to Fake Matt → Matt DM (channel `D0B0T0ETDR8`). Same as cron behavior.

```bash
python3 ~/.claude/fakematt-today/standup_draft.py
```

**Workstream format:** Engineering-flavored alt view (Development w/ sub-products, Blog/Content, Meetings).

```bash
python3 ~/.claude/fakematt-today/standup_draft.py --dry-run --format workstream
```

**Weekly priorities (`--weekly`):** Turn Matt's most recent POSTED #standup into the canonical weekly-priorities surface — `Growth/weekly-priorities/<week-monday>.md` — one checkable block per item, tagged by autonomy (🟡 blocked-on-Matt / 🟢 autonomous / 🔴 async-waiting), linked to each item's owning tracker (zpub / inbox). Optionally mirrors to the Zergboard "This Week" board (`thisweek_board.json`) for mobile check-off; swiping a card to Done flips the file checkbox.

```bash
# parse + preview (writes nothing)
python3 ~/.claude/fakematt-today/weekly_from_standup.py --dry-run
# write/merge the weekly file (preserves checkboxes + hand-edited autonomy tags + manual context)
python3 ~/.claude/fakematt-today/weekly_from_standup.py --write
# also push the This Week board
python3 ~/.claude/fakematt-today/weekly_from_standup.py --write --mirror
# board-only sync incl. Done→checkbox pull (what the hourly travel cron runs)
python3 ~/.claude/fakematt-today/weekly_from_standup.py --mirror-only
```

Merge is idempotent: blocks key on `<!-- _id: ... -->`, reused by surface-id or name; vanished items move to "Carried / dropped?" (never deleted); `<!-- manual -->` blocks are never auto-touched. Durable layer: `com.matteisn.weekly-from-standup` (Mon 9am seed) + `com.zerg.weekly-thisweek-sync` (hourly Done-pull) — both on disk, bootstrap when wanted.

## When to use

- Matt asks "what would I post?" / "help me write a standup" / "draft today's standup"
- Matt is about to post in #standup before the 5pm cron has fired
- Matt wants the workstream/dev view to remember PR detail before writing the exec rollup

## Output style (calibrated 2026-05-06)

Five lanes — Marketing / Product / BD / Skills / Admin — matching Matt's actual style. Empty lanes are **omitted** (not placeholdered) and a footnote outside the code block hints which lanes Matt may want to add manually. Window floors at start-of-yesterday-PT so a same-day re-run still gives ≥24h coverage.

See `MattZerg/_style/` and the `feedback_matt_standup_style.md` memory for the lens. Don't reinvent — this skill should always shell out to the underlying script so cron + on-demand stay in sync.
