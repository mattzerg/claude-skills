# Fake Matt Intake Routing

Use this reference when a packet could belong in several places.

## Destination Table

| Signal | Destination | Action |
|---|---|---|
| "Please do X", deadline, blocker, current obligation | `MattZerg/Tasks/inbox.md` To Do | Add or update one row; include domain and why-now |
| Useful but not committed | `MattZerg/Ideas/_inbox/<category>/` or `Tasks/inbox.md` Should Do | Prefer idea backlog for speculative product/content/tooling thoughts; use Should Do for plausible next actions |
| Date/event trigger | `Tasks/inbox.md` Reminders or Google Calendar | Calendar creation requires explicit confirmation |
| Reusable user preference, correction, hard rule | project `memory/feedback_*.md` | Create concise memory and link from `MEMORY.md` |
| Stable project fact | project `memory/project_*.md` or project session summary | Verify current source before relying on old memory |
| Contact fact, relationship context, personal detail | Context inbox first; later reconcile to `People/`, `Companies/`, `Firms/` | Add only stable facts with provenance |
| Reply requested | Fake Matt voice skill + Gmail/Slack connector | Draft first; send/post only after explicit confirmation |
| Personal health/workout/calorie data | `zhealth` / health parser | Log structured events; do not put routine health data into general memory |
| Ambiguous, stale, or not owned by Matt | No durable write by default | Summarize or ask one clarifying question if needed |

## Memory Write Shape

Memory files should be short and operational:

```markdown
---
name: <human-readable rule/fact>
description: <one-sentence trigger for future agents>
type: feedback|project|preference|routing
originSessionId: <if known>
---
<1-5 paragraphs. Include source, date, and concrete application guidance.>
```

After creating the file, add it to `MEMORY.md` in the nearest matching section. If no section fits, add a small "Recently added" style entry rather than reorganizing the whole index.

## Task Row Shape

For `Tasks/inbox.md`, preserve the existing table shape:

```markdown
| N | <verb-first item> | <Domain> | <Why now> |
```

Use `Should Do` when timing is soft. Use `Reminders / Alerts / Opportunities` when the task only becomes relevant at a date, signal, or external event. Add `[zb:CARD_ID]` only when a Zergboard card already exists or was deliberately mirrored.

## Reply Routing

- Family or close friend email: `fakematt-personal`.
- External/professional email: `fakematt-email`.
- Slack DM, channel post, or thread reply: `fakematt-slack`.
- Broad launch, campaign, or public package: `fakematt-launch` or `fakematt-copyedit` before channel-specific drafting.

When a live thread is involved, read enough surrounding context to avoid replying to the wrong ask. When in doubt, draft a short "checking my understanding" response rather than inventing context.

## Confirmation Gates

Ask for explicit confirmation before:

- Sending email.
- Posting to Slack.
- Creating or updating calendar events with attendees.
- Creating external-facing social posts.
- Making irreversible external state changes.

Internal vault writes can be made without confirmation when the requested intake is clear, reversible, and source-backed.

## Idea Capture

Explicit `idea:` commands are safe to apply because they create raw backlog files rather than tasks:

```text
idea: <idea text>
idea: [zerg-tooling] <idea text>
idea: zerg-content: <idea text>
```

The bridge writes to `MattZerg/Ideas/_inbox/<category>/<slug>.md` using the canonical idea schema with `status: raw`, `subcategory: fakematt-intake`, unknown estimates, and the source packet ID in `sources:`. Category prefixes can be one of `zerg-product`, `zerg-content`, `zerg-tooling`, `personal-venture`, `personal-life`, `shopping`, or `research`; otherwise the bridge uses a conservative keyword guess.

## Context Capture

Use `note:` or `context:` for source-backed facts that should not become a task, idea, or memory rule yet:

```text
note: <general source-backed context>
context: [project: ZTC] <source-backed project fact>
context: [person: Jane Doe] <source-backed person fact>
context: [company: Acme] <source-backed company fact>
context: project ZTC: <alternate project syntax>
```

The bridge writes these to `MattZerg/Tasks/fakematt-intake/context/YYYY-MM-DD.md` with timestamp, source packet ID, context type, and target. It deliberately does not edit `People/`, `Companies/`, `Firms/`, or project source-of-truth files directly from scheduled intake; those reconciliations should happen as a reviewed follow-up once enough context has accumulated.

To produce that reviewed follow-up:

```bash
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --review-context --context-days 14 --write-context-review
```

The review groups context entries by `context_type + target`, shows source-backed excerpts, and suggests whether the next manual reconciliation belongs in `People/`, `Companies/` / `Firms/`, a project source-of-truth page, or general triage.

To stage exact reviewed append blocks without applying them:

```bash
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --stage-context-reconciliation --context-days 14 --write-context-stage
```

This writes a markdown staging file under `MattZerg/Tasks/fakematt-intake/context/reconciliations/` with candidate target files and proposed append blocks. Treat it as a patch draft for a later reviewed edit pass, not as authorization for the daemon to mutate CRM or project source-of-truth files.

## Mixed Capture

Use `capture:` when Matt sends a multi-line packet with several explicit commands:

```text
capture:
- task: <committed task>
- should: <soft task>
- remind: <thing> @ <date or condition>
- remember: <durable rule/fact>
- idea: [zerg-tooling] <raw idea>
- context: [project: ZTC] <source-backed project fact>
- health: <health log>
- reply: slack to <@person or #channel>: <drafting task>
```

The bridge strips bullets and numeric list markers, then parses each line as if Matt had sent it separately. It only applies known command prefixes; ambiguous capture lines become `skip` actions in the ledger so the next parser review can inspect them.

## Operator Ledger

The recurring bridge appends one JSON object per scan to `FAKEMATT_OPERATOR_EVENTS` or, by default, `state_events.jsonl` next to the runtime state file. Use this ledger to audit whether Fake Matt is actually ingesting useful packets and to decide which deterministic parsers to add next.

```bash
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --report --report-days 7
```

The weekly LaunchAgent posts that report to Matt's Fake Matt DM. Treat the report as an operations dashboard: high deferred or skipped counts mean the next capability should be a parser/routing rule for the repeated form, not a broader LLM prompt change.

For a more focused parser backlog, run:

```bash
python3 /Users/mattheweisner/.codex/skills/fakematt-operator/scripts/intake_bridge.py --review-deferred --review-days 14 --write-review-note
```

This reads compact deferred/skipped action samples from the ledger and writes a review note under `MattZerg/Tasks/fakematt-intake/reviews/`. Do not let the bridge edit its own parser rules automatically; use the review note as a human-readable backlog for the next safe parser patch.
