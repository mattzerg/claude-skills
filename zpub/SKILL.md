---
name: zpub
description: 'Unified publishing/content tracker. Action-led 4-color table (🔴 ideating/failed → 🟠 drafting → 🟡 review/scheduled → 🟢 published) across blogs, launches, case studies, video, drip, social, one-pagers. Vault-canonical at `MattZerg/Projects/Zerg-Production/Growth/publishing/`; bidir-syncs Zergboard PUB-* board. Verbs: `zpub`, `zpub all`, `zpub show <id>`, `zpub add`, `zpub set`, `zpub sync`, `zpub open`. USE PROACTIVELY for "content pipeline", "publishing status", "what''s publishing", "content status", "what''s blocking content", or before standup/morning brief. When state=ideating with no draft, dispatch content-production agent.'
---

# zpub — Publishing/Content Board CLI

Unified tracker over every content surface in flight. Vault is canonical (`MattZerg/Projects/Zerg-Production/Growth/publishing/`); the Zergboard "Publishing" board is a bidirectional mirror via a fenced `<!-- zpub:state -->` block in each card description.

## Why this exists

Status used to be split across `Growth/content/` (editorial state), `Growth/launches/` (launch state), `Writing/Launches/` (channel matrix), `MattZerg/CaseStudies/`, ad-hoc filenames, and `MAR-*` / `WEB-*` Zergboard cards. There was no single answer to "what's about to publish, what's blocking, what needs my attention TODAY." `zpub` is that answer.

## Verbs

| Verb | Purpose |
|------|---------|
| `zpub` | Default action-led RAG table — Reds first, Ambers next, Greens hidden, max 5 visible |
| `zpub all` | Full table including Greens, grouped by type |
| `zpub <id>` | Entry detail (frontmatter + body + Zergboard URL) |
| `zpub add` | Wizard — prompts for type, title, target date, owner |
| `zpub set <id> <field> <value>` | Update entry field (auto-bumps `updated_at`) |
| `zpub sync` | Bidirectional sync with Zergboard, prints diff summary |
| `zpub open <id>` | Open vault entry in `$EDITOR` |
| `zpub bootstrap-board` | One-time: create the Zergboard "Publishing" board |
| `zpub --reds-only [--max=N]` | Compact reds-only view (used by morning-brief) |

## RAG rules

For each entry:
- **RED** — `publish_target` is past AND `status != published/distributed/archived`, OR any required gate has status `failed`, OR `blockers` is non-empty
- **AMBER** — `publish_target` within 3 days, OR any required gate has status `pending`
- **GREEN** — on schedule, all required gates `passed` or `n_a`, no blockers

Required gates per `type` are in `gates.json`. Override per-entry by adding/removing keys under `gates:`.

## Render rules

Per `feedback_dashboard_must_drive_action.md`:
- Reds first, then Ambers; Greens hidden behind `--all`
- Cap visible at 5 (without `--all`); overflow is `...N more (zpub all)`
- Each Red row gets a `↳ next:` line stating the single next move
- ASCII only (per `feedback_ascii_layouts_for_status.md`); emoji 🔴 🟠 🟢

## Files

- `MattZerg/Projects/Zerg-Production/Growth/publishing/<id>.md` — entity files (canonical)
- `MattZerg/Projects/Zerg-Production/Growth/publishing/_meta/index.json` — denormalized cache (regenerated on every write)
- `MattZerg/Projects/Zerg-Production/Growth/publishing/_meta/gates.json` — per-type gate config (mirror of skill copy)
- `MattZerg/Projects/Zerg-Production/Growth/publishing/_meta/conflicts.log` — sync conflict ledger
- `~/.claude/skills/zpub/board.json` — stores Zergboard board UUID after bootstrap
- `~/Library/LaunchAgents/com.zerg.zpub-gtm-sync.plist` — hourly sync cron (`zpub_gtm_sync.py`)

## Bidirectional sync

Each Zergboard card description has a fenced state block:

```
<free-form body>

---
<!-- zpub:state -->
id: pub-...
status: review
publish_target: 2026-05-15
gates.fakematt_copyedit: passed
gates.signoff: pending
blockers:
  - Waiting on Idan numbers signoff
updated_at: 2026-05-10T14:32:00Z
<!-- /zpub:state -->
```

Last-write-wins via `updated_at`. Conflicts (both edited within 60s) prefer vault, log to `_meta/conflicts.log`.

## Anchor docs

- Plan: `~/.claude/plans/build-a-publishing-content-board-clever-balloon.md`
- Memory: `project_zpub_publishing_board.md`, `feedback_zpub_table_render.md`, `feedback_zpub_autonomous.md`, `feedback_publish_status_explicit_yes.md`
- Schema reference: `~/.claude/skills/zpub/schema.md`

## HARD GATE: blog admin status flips (per `feedback_publish_status_explicit_yes.md`)

NEVER call the blog admin API (`PUT /api/blog/admin/posts/<id>/`) to flip a post's status to `queued` or `published` — even if every zpub gate is green — without:

1. Asking Matt explicitly in chat, naming the slug + target status + moment-of-publish time.
2. Receiving an unambiguous YES in the same thread.

Prior-session `gates.signoff: passed` does NOT carry this forward. Queue == publish for this gate (the queued state is the auto-publish trigger via `publishedAt`). Transitions to `draft` or `archived` are safe — no ask required.

## Autonomous use (per `feedback_zpub_autonomous.md`)

When ANY content surface is in motion in conversation (drafted, in review, scheduled, blocker mentioned, target date set), act on it without asking:

1. `zpub add` with `--type / --title / --target / --status` to register it.
2. `zpub set <id> gates.<name> <value>` for obvious gate states (e.g. fakematt_copyedit=passed when the review already ran).
3. `zpub set <id> blocker.add "..."` when a blocker surfaces.
4. `zpub sync` after a batch — not after every single edit.

Don't add purely speculative pieces ("we should write about X someday") — wait until there's a target date or actual draft.

## Approval locks (canonical signoff; per gigacontext-2026-05-19 incident)

The `approval` block on an entry's YAML frontmatter is the CANONICAL signoff
record — `locked: true` + `locked_by: matt|idan` means a human approved.
`tools/check_gates.py` derives `gates.signoff=passed` FROM it; validators must
never flip signoff the other way, and no tool may delete the block
(`Entry.extra` round-trips unknown frontmatter keys through `save_entry`
specifically so `zpub set` can't silently destroy a lock).

Verbs (replace hand-editing the YAML):

```
zpub set <id> approval.locked_by matt|idan   # who approved (humans only)
zpub set <id> approval.locked true           # lock; stamps locked_at if absent
zpub set <id> approval.locked false          # unlock (prefer adding an unlock_log entry with reason)
```

Rules:
- Lock only on an explicit human approval in-channel (Slack thread, chat YES);
  record the source in `approval.approval_source` when known.
- Unlocks for mechanical edits (CMS authoring, metadata fixes) should append to
  `approval.unlock_log` with reason + expiry rather than clearing the lock.
- `check_gates.py <id>` shows whether the lock is being honored
  (`signoff … approval block: locked_by=… — canonical signoff`).
