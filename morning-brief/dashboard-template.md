# Conversational morning-brief render template

When Matt asks for the morning brief / to-do dashboard *in a Claude Code session* (not when the 7am cron fires), DO NOT paste the raw 15-line Slack-compressed output. Render the rich ASCII dashboard below.

Two surfaces, two formats — both pull from the same underlying data:

| Surface | Format | Constraint |
|---|---|---|
| 7am M-F cron DM | `~/.claude/fakematt-today/morning_brief.py` Slack output | 15-line ceiling, closed emoji set, `slack_format.compose()` |
| Conversational pull (this skill) | Rich ASCII dashboard (template below) | ≤80-char width, full emoji vocabulary |

The conversational surface needs more density because Matt is at a desk reading on a wide terminal, not glancing at a phone notification.

## Anchored patterns

- `feedback_dashboard_must_drive_action.md` — lead with ONE action, hide healthy, ≤5 visible sections, no jargon
- `feedback_three_lists_format.md` — Blocked on Matt / Autonomous / Async layout for "what's next"
- `feedback_pr_dashboard_format.md` — ASCII box format, cap bar, NEXT MOVE callout
- `feedback_zpub_table_render.md` — group by RAG, 3 cols max, lead action first
- `feedback_visual_richness_in_responses.md` — ASCII tables + emoji + arrows for quantitative content

## Sections (in order)

1. **🎯 TODAY** — single-line lead action. Pulled from `_pick_now_action()` in `morning_brief.py` or `Tasks/inbox.md` priority row.
2. **🔴 BLOCKED ON YOU** — only items Matt himself must move. Decisions, drafts, sends, approvals, picks. Cap at 5. Each line: 1 emoji + 1 line + concrete artifact ref.
3. **🤖 AUTONOMOUS — I CAN PUSH NOW** — concrete deliverables I can produce without Matt input. Cap at 4. Each line names the output (file, PR, asset).
4. **📆 TODAY'S CALENDAR** — only today's meetings. Skip if empty.
5. **🚦 PR PIPELINE** — cap bar + open PRs + force-override warnings. Skip if no PRs in flight.
6. **⏳ ASYNC / WAITING** — FYI only. PR re-reviews, external waits, overnight team signal. Cap at 4.
7. **🗓 NEXT 7 DAYS** — calendar lookahead skipping today + travel-only items.
8. **🎯 NEXT MOVE** — numbered concrete sequence (1, 2, 3). Reinforces the lead.

After the box, ONE folded healthy footer line: `Healthy: <comma-list>` — promises clean, standup current, etc.

## Section omission rules

Hide any section that has no content. Don't render an empty zone with "—" placeholders. The dashboard breathes when sections drop.

If everything is healthy → render a tight box with just 🎯 TODAY + ✅ ALL CLEAR + 📆 calendar. Skip the rest.

## Template

```
╔══ 🌅 MORNING BRIEF ══ <weekday> <Mon> <DD> <YYYY> ════════════════╗
║                                                                   ║
║  🎯 TODAY                                                         ║
║  <one-line lead action with concrete next step>                   ║
║                                                                   ║
╠══ 🔴 BLOCKED ON YOU (action required) ═══════════════════════════╣
║                                                                   ║
║  <emoji>  <action> — <artifact ref or path>                       ║
║  ...                                                              ║
║                                                                   ║
╠══ 🤖 AUTONOMOUS — I CAN PUSH NOW ════════════════════════════════╣
║                                                                   ║
║  • <verb> <concrete deliverable>                                  ║
║  ...                                                              ║
║                                                                   ║
╠══ 📆 TODAY'S CALENDAR ═══════════════════════════════════════════╣
║                                                                   ║
║  HH:MM  <title>  <🤝 if external>                                 ║
║                                                                   ║
╠══ 🚦 PR PIPELINE ════════════════════════════════════════════════╣
║                                                                   ║
║  Cap ████████████████████  N/cap   <emoji> <state>  · held: M     ║
║                                                                   ║
║  🔴 #NNN  <short title>     <state> · <reviewer> (<age>)          ║
║                                                                   ║
║  ⚠ <override warning if any>                                      ║
║                                                                   ║
╠══ ⏳ ASYNC / WAITING ════════════════════════════════════════════╣
║                                                                   ║
║  • <who> <what> (<when>)                                          ║
║                                                                   ║
╠══ 🗓 NEXT 7 DAYS ════════════════════════════════════════════════╣
║                                                                   ║
║  <Day> HH:MM  <emoji> <title>                                     ║
║                                                                   ║
╠══ 🎯 NEXT MOVE ══════════════════════════════════════════════════╣
║                                                                   ║
║  1) <first concrete step>                                         ║
║  2) <second>                                                      ║
║  3) <third — optional>                                            ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝

Healthy (folded): <comma-list of clean signals>
```

## Anti-patterns (don't ship)

- Pasting raw `morning_brief.py --dry-run` Slack output verbatim — that's the cron view
- Wide markdown tables (`| col | col | col |`) instead of ASCII zones
- Status nouns without verbs ("Open promises: 0") — say "✅ promises clean" in the footer instead
- "Embarrassing line items" framing
- More than 5 zones visible (excluding 🎯 lead + 🎯 NEXT MOVE)
- Empty placeholder rows with `—` or `n/a`

## Render flow

1. Run `python3 ~/.claude/fakematt-today/morning_brief.py --dry-run` to get the underlying data and verify the 🎯 lead picked.
2. Fan out for the missing-from-cron context (do these in parallel via Bash):
   - `python3 ~/.claude/skills/pr-table/run.py` → PR pipeline + held queue
   - Read `~/.claude/workstreams/state.json` → hot/stale lanes for the footer
   - Read top of `MattZerg/Tasks/inbox.md` To Do table → "Blocked on you" candidates
   - `gtm decisions` (or read `Growth/decisions/*.md`) → GTM decision rows for "Blocked on you"
3. Classify every candidate into one of the 3 lists per `feedback_three_lists_format.md`.
4. Render the box. Skip sections with no rows. Keep total height ≤ ~50 lines.
5. Single folded healthy footer below the box.

## After rendering

End with ONE short paragraph reading the picture — where the choke point is + the single move that unblocks it. Don't bury that in the box.

If `Autonomous — I can push now` has rows, ALWAYS end with: "Want me to push on [#1, #2]?" — per `feedback_offer_to_push_autonomous.md`.
