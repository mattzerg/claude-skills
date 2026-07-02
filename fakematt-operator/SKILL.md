---
name: fakematt-operator
description: 'Operate Fake Matt as Matt''s digital-twin intake and response layer. Use when Matt wants Fake Matt to ingest information from chat, Gmail, Slack, notes, attachments, or forwarded messages; classify it into tasks, memory, reminders, CRM/contact context, health logs, ideas, calendar items, or draft replies; update the right local/vault source of truth; and route outbound drafts through fakematt-email, fakematt-personal, fakematt-slack, gmail-skill, slack-skill, gcal-skill, zergboard-skill, or other live connectors. Trigger on "digital twin", "ingest this", "remember this", "add this to my tasks", "I emailed/slacked Fake Matt", "process my inbox/DMs", "respond as me", "triage this thread", "turn this into memory", or cross-channel personal ops. Never sends, posts, or creates calendar events without explicit confirmation.'
allowed-tools: Bash, Read, Write
---

# Fake Matt Operator

Top-level orchestration for Fake Matt as a working memory, task, and response layer. This skill decides where incoming material belongs, which sibling Fake Matt voice skill should draft a reply, and which live connector should read or write the external surface.

## Anchors

This skill orchestrates voice-bound siblings; it does not draft prose itself. Cross-reference anchors (read when the operator needs to reason about voice routing or surface a finding in Matt-voice receipts):

- **Voice fingerprint (considered surfaces — receipts, structured summaries, vault writes):** `~/Obsidian/Zerg/MattZerg/_style/matt_considered_voice.md`
- **Cross-surface voice patterns:** `~/Obsidian/Zerg/MattZerg/_style/feedback_voice_patterns.md`
- **Pattern catalog:** `~/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md`
- **Catalog patterns to cite by slug** (Section A Universal / process): honest-scoping, minimize-prs, bundling-rule, prior-review-carry-forward
- **Catalog patterns to cite by slug** (Section C Prose / writing): cross-format-repetition
- **Catalog patterns to cite by slug** (Section E CRO / marketing): shipped-vs-roadmap-visibility, capability-claim-unverified, single-cta, missing-cta
- **Catalog patterns to cite by slug** (Section I Launch / deck): deferred-with-reason

For actual outbound drafting, always route to the voice-bound sibling (`fakematt-email`, `fakematt-personal`, `fakematt-slack`) — those skills own their own primary voice anchors.

## First Move

1. Identify the source: direct chat, Gmail thread, Slack thread/DM/channel, note/file, calendar event, health log, Zergboard card, or mixed packet.
2. Load only the anchors needed:
   - Always read `MattZerg/AGENTS.md` for vault rules and hard constraints.
   - Read `~/Obsidian/Zerg/MattZerg/claude-memory/MEMORY.md` before writing or relying on persistent memory.
   - Read `MattZerg/Tasks/inbox.md` before adding or deduping tasks.
   - Read `references/intake-routing.md` when the item has more than one possible destination.
3. Fetch live context with the relevant connector skill only when the user points at live Gmail, Slack, Calendar, Zergboard, Drive, or another app surface.
4. Create a source packet in your reasoning: source, author, timestamp if known, raw excerpt/link/id, requested action, confidence, and any privacy/safety flags.

## Routing

Classify each packet into one or more outcomes:

- **Reply needed**: draft with `fakematt-email`, `fakematt-personal`, or `fakematt-slack`; use `gmail-skill` or `slack-skill` only for search, draft creation, or confirmed sending/posting.
- **Committed task**: update `MattZerg/Tasks/inbox.md`; mirror to Zergboard only when the item is Zerg-owned and current.
- **Reminder or date trigger**: add/update `Tasks/inbox.md` Reminders; use `gcal-skill` for calendar events only after confirmation.
- **Persistent memory**: write a concise memory file only for durable preferences, corrections, identity/routing rules, project facts, recurring failure modes, or user feedback. Link it from `MEMORY.md`.
- **Contact or CRM context**: update or create the relevant `People/`, `Companies/`, or `Firms/` note only when the fact is stable and useful later.
- **Idea**: route to the vault idea system, not the task table, unless Matt explicitly commits to action.
- **Health or habit log**: use `~/.claude/fakematt-today/health_parser.py` or the `zhealth` command pattern from `MattZerg/Health/README.md`.
- **No write**: summarize, answer, or park when the item is ambiguous, duplicative, stale, or not Matt-owned.

## Bridge Script

For recurring or batched intake, prefer the bundled bridge:

```bash
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py
```

Useful modes:

```bash
# Safe collection/classification preview; no writes.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py

# Apply internal vault writes only: tasks, reminders, durable memories.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --apply

# Apply only deterministic explicit commands such as task:/remember:/remind:/health:.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --apply-safe

# Post the receipt to Matt's Fake Matt DM after scanning.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --apply --post

# Debug collection without an LLM call.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --no-llm --no-gmail

# Run parser self-tests without scanning channels or writing vault/state.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --self-test

# Summarize the run ledger without scanning Slack or Gmail.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --report --report-days 7

# Review deferred/skipped patterns and suggest parser upgrades.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --review-deferred --review-days 14 --write-review-note

# Review pending/generated reply requests without sending or posting.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --review-replies --reply-days 14 --write-reply-review

# Generate drafts for pending reply queue items; does not send email or post Slack.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --generate-reply-drafts --reply-days 14 --reply-limit 5

# Preview or confirm a single drafted reply queue item.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --send-gmail-draft <queue-id> --dry-run
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --send-gmail-draft <queue-id> --confirm "SEND <queue-id>"
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --post-slack-draft <queue-id> --dry-run
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --post-slack-draft <queue-id> --confirm "POST <queue-id>"

# Review context inbox notes and suggest People/Companies/Projects reconciliation.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --review-context --context-days 14 --write-context-review

# Stage exact append blocks for reviewed context reconciliation; does not apply them.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --stage-context-reconciliation --context-days 14 --write-context-stage

# Print or post the command syntax Matt can use from Slack/Gmail.
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --print-command-reference
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --print-command-reference --post
```

The bridge scans:

- `~/.codex/skills/slack-skill/inbox.jsonl` for Matt's direct Fake Matt DM or explicit intake phrases.
- Gmail messages matching the default explicit Fake Matt query, across `matteisn@gmail.com` and `matthew@zergai.com`.

The LaunchAgent writes runtime state to `~/.config/zerg/fakematt-intake/state.json` and run accounting to `~/.config/zerg/fakematt-intake/state_events.jsonl`; manual runs default to `MattZerg/Tasks/fakematt-intake/state.json` plus adjacent `state_events.jsonl` unless `FAKEMATT_OPERATOR_STATE` or `FAKEMATT_OPERATOR_EVENTS` is set. It never sends email, posts public Slack messages, creates calendar invites, or performs irreversible external actions. Reply and idea actions are deferred into `MattZerg/Tasks/fakematt-intake/YYYY-MM-DD.md` unless a future script adds a confirmed path.

The local LaunchAgents are:

- `com.matteisn.fakematt-intake`: runs every 15 minutes with `--apply-safe --post --mark-seen`.
- `com.matteisn.fakematt-intake-report`: posts a 7-day ledger report to Matt's Fake Matt DM on Sundays at 9:10am PT.

Use `--review-deferred` after enough packets have accumulated. It groups deferred and skipped action samples from the ledger, writes optional notes under `MattZerg/Tasks/fakematt-intake/reviews/`, and proposes the next deterministic parser candidates without changing runtime behavior.

For weekly reliability reporting, run `--review-deferred --review-days 14 --write-review-note` and treat repeated skips/deferred packets as parser backlog. Do not expand LLM autonomy just to clear the backlog.

Use `--review-replies` to inspect `reply:` requests that entered `MattZerg/Tasks/fakematt-intake/reply-queue/`. The queue records surface, recipient, source, task, and draft artifact status. It is review-only.

Use `--generate-reply-drafts` after reviewing the queue. It processes pending queue items only, honors `--reply-limit`, and can be narrowed with `--reply-surface gmail` or `--reply-surface slack`. Gmail items become Gmail drafts; Slack items become local Slack draft artifacts. It never sends email or posts Slack messages.

Use `--send-gmail-draft <queue-id>` and `--post-slack-draft <queue-id>` only after Matt has reviewed the draft. First run with `--dry-run`; live mode refuses unless `--confirm` exactly matches `SEND <queue-id>` or `POST <queue-id>`. These commands update the queue status to `sent` or `posted` only after the external action succeeds.

Use `--review-context` to roll up `note:` and `context:` inbox entries by type/target and produce reconciliation candidates for `People/`, `Companies/`, `Firms/`, and project source-of-truth notes. It is read-only unless `--write-context-review` is passed.

Use `--stage-context-reconciliation` after reviewing context notes. It searches likely `People/`, `Companies/`, `Firms/`, and `Projects/` targets, then drafts exact markdown append blocks under `MattZerg/Tasks/fakematt-intake/context/reconciliations/`. It never applies those patches automatically.

Use `--print-command-reference --post` to send Matt a compact Fake Matt DM containing the current intake syntax.

Use `--self-test` after changing command parsing. It exercises deterministic commands and mixed `capture:` packets without scanning Gmail/Slack or writing to the vault/state ledger.

Deterministic command syntax, safe for `--apply-safe`:

```text
task: <committed task>
todo: <committed task>
should: <soft task>
remind: <thing> @ <date or condition>
remember: <durable preference, correction, project fact, or routing rule>
health: <zhealth-compatible log, e.g. 50 pushups, 700 cal lunch>
idea: <idea to write into the raw idea backlog>
idea: [zerg-tooling] <idea with explicit backlog category>
idea: zerg-content: <idea with explicit backlog category>
note: <general source-backed context>
context: [project: ZTC] <source-backed project fact>
context: [contact: Jane Doe] <source-backed contact fact>
capture:
- task: <committed task>
- remind: <thing> @ <date or condition>
- remember: <durable preference, correction, project fact, or routing rule>
- idea: [zerg-tooling] <idea>
- context: [project: ZTC] <source-backed project fact>
- reply: slack to <@person or #channel>: <what the draft should say>
reply: <drafting task to defer into intake notes>
reply: email to <email>: <what the draft should say>
reply: slack to <@person or #channel>: <what the draft should say>
```

In `--apply-safe` mode, explicit `capture:` commands split known prefixed lines into the same safe actions. Ambiguous capture lines are skipped rather than guessed. Explicit `idea:` commands write raw idea files under `MattZerg/Ideas/_inbox/<category>/`. Explicit `note:` and `context:` commands write source-backed context inbox entries under `MattZerg/Tasks/fakematt-intake/context/` instead of editing People/Projects directly. Explicit Gmail reply commands create Gmail drafts only; they never send. Explicit Slack reply commands write a draft artifact under `MattZerg/Tasks/fakematt-intake/drafts/`; they never post to Slack.

## Write Policy

- Preserve provenance. Every durable write should say where it came from: Gmail message ID, Slack channel/thread, user quote, file path, or date.
- Deduplicate before appending. Search the target file and related memory names first.
- Keep writes small. Prefer one task row, one memory rule, or one contact note update over broad transcript dumps.
- Do not silently overwrite source-of-truth files. Append or make targeted edits that keep existing structure.
- For memory files, use the existing frontmatter style in the project memory directory and link the new file from `MEMORY.md`.
- For outbound communications, draft only until Matt explicitly confirms the final send/post.

## Response Pattern

When processing intake, end with a compact receipt:

```text
Ingested
- <source/context>

Updated
- <file/app>: <change>

Drafted
- <surface/recipient>: <status or draft path>

Needs Matt
- <confirmation/question/blocker>
```

Omit empty sections. If no durable write was made, say so and why.

## Source-Specific Notes

- **Gmail**: read the full thread before replying or turning it into tasks. Respect professional vs personal routing. Create Gmail drafts instead of sending.
- **Slack**: distinguish DM, channel broadcast, and thread reply. Use `fakematt-slack` for voice; `slack-skill` for live context or confirmed posting.
- **Direct notes from Matt**: treat as high-authority input, but still decide whether it is memory, task, reminder, idea, contact context, or just current-session instruction.
- **Forwarded/pasted text**: preserve quoted source and do not infer private facts beyond the text.
- **Mixed packets**: split into atomic outcomes, dedupe each, then report all writes together.

## Hard Rules

- Never auto-send emails, Slack messages, social posts, or calendar invites.
- Never post Fake Matt output to a shared channel or external recipient without explicit confirmation.
- Never make Fake Matt sound more certain than the source supports.
- Do not create cards or tasks for work Matt does not own; produce a reference note or draft handoff instead.
- Do not use "digital twin" as permission to act without scoped confirmation. It means better intake, memory, routing, and drafting; it does not remove consent gates.
