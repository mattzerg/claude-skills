---
name: idea-backlog
description: "Capture/organize/surface Matt's ideas across product/content/tooling/personal/research. One file per idea at `MattZerg/Ideas/[category]/` with status+conviction+effort+cost frontmatter. Four surfacing channels — Dataview, CLI recall, in-session auto-suggest, weekly FM-DM digest. Bidir with `Tasks/inbox.md` (`from-task` / `to-task`). USE PROACTIVELY when Matt says \"what if we...\", names an idea, or asks for related ideas on a topic. Never auto-publishes. Spec — `MattZerg/Projects/idea-backlog.md`."
---

# idea-backlog

Categorized idea repository for Matt. See full spec at `MattZerg/Projects/idea-backlog.md`.

> **Open redesign question (per `feedback_idea_backlog_revisit.md`):** Matt flagged after the 2026-05-09 seed sweep that "this kind of doesn't make sense to me" — likely culprits: LLM-generated `## Why interesting` (editorializing in his voice), too many empty schema fields (effort/time/cost), category split may not match his mental axes, or the 1,400+ aggressive sweep produced a dump rather than a curated repo. When Matt next mentions the idea backlog or returns to triage, OPEN this question explicitly before stacking more content on the existing shape. Don't silently keep going.

## Commands

| Command | What it does |
|---|---|
| `capture "<text>" [--category X] [--tags a,b,c]` | Fast-write a new idea file. Defaults sane; <1s. |
| `recall <topic>` | Semantic + tag search across all ideas. ALSO scans `Tasks/inbox.md` for keyword matches. Returns combined view. |
| `extract [--paths …] [--include-mhe] [--limit N]` | Stage 1 of seed sweep. Walks vault, LLM-classifies, writes raw extracts to `_workdir/raw_extracts.jsonl`. Resumable. |
| `dedupe` | Stage 2. Embed-cluster near-duplicates from `_workdir/raw_extracts.jsonl`. |
| `write-inbox` | Stage 3. Emit clustered candidates into `Ideas/_inbox/<auto-category>/<slug>.md` as `status: raw`. |
| `triage` | Walks `_inbox/` interactively: keep / merge / kill / defer / to-task. |
| `touch <id>` | Bumps `last_touched` (kills the idle flag). |
| `promote <id> [--category Y]` | Raw → active, optional category move. |
| `kill <id> [reason]` | Move to `_archive/` with reason. |
| `from-task "<text-or-id>"` | Demote `Tasks/inbox.md` row → idea. Replaces row with strikethrough + link. |
| `to-task <id> [--bucket "To Do" | "Should Do" | "Reminders / Alerts / Opportunities"]` | Promote idea → new inbox table row. Links bidirectionally. |
| `rebuild-index` | Regenerate `Ideas/_meta/index.json` for auto-suggest. (Cron'd every 4h.) |
| `weekly-digest [--dry-run]` | Sun 9am cron: 3 idle + 1 new + triage queue + 7d metrics → FM self-DM. |
| `metrics [--window N] [--json]` | 7d / 30d / lifetime usage snapshot. State + capture/recall/triage/auto-surface counts + extract-run cost. |
| `log-suggest "<topic>" --count N` | Hand-log an auto-surface fire. Called by Claude when the in-session surfacing rule (memory: `feedback_idea_backlog_surfacing`) fires. |
| `browse [--top|--fresh|--idle|--by-category|--tags|--inbox|--all]` | Terminal version of the Dataview dashboard. Default = top + by-category + inbox. |
| `generate-top [--per-category N]` | Regenerate `Ideas/_top.md` — single-page scannable snapshot, sorted by `depth × viability` within each category. |
| `score [--limit N] [--batch-size 10]` | Grade each unscored inbox idea on `depth` (1-5) + `viability` (1-5) via Sonnet 4.5 batched 10/call. ~$1 across 1,388 items. |
| `batch_triage --apply-scores --commit` | Filter on scored items: kill if `depth=1 AND viability<=2`; promote-high if `>=4/>=4`; promote-medium if `>=3/>=3`. |

## Vault paths

- Data: `~/Obsidian/Zerg/MattZerg/Ideas/`
- Categories: `product`, `content`, `tooling`, `personal`, `research`
- Inbox: `Ideas/_inbox/`
- Archive: `Ideas/_archive/`
- Meta: `Ideas/_meta/` (schema, sources, extraction-log, index.json)

## Tasks integration

`Tasks/inbox.md` uses markdown tables with bucket headers. Buckets:
- `## To Do` — committed, dated, blocking
- `## Should Do` — non-blocking, can slip
- `## Reminders / Alerts / Opportunities` — trigger-based
- `## Relevant Ideas` (with sub-buckets via `### …`) — capture, not actionable yet

`from-task` parses any of these. `to-task` defaults to "To Do".

The 35 rows under `## Relevant Ideas` are the highest-priority initial seed — already curated.

## Hard rules

- **Never auto-publishes.** Ideas live in vault; FM digest only goes to Matt's self-DM.
- **No auto-migration tasks ↔ ideas.** Movement is always explicit.
- **No duplication.** Promoted ideas leave a stub pointing at the task, not parallel entries.
- **Open files once.** Default `--no-open` on writes; user-facing artifact opens at end of a triage session, not per-item.

## Measurement

Every mutating script logs to `_workdir/usage.jsonl` via `_lib/usage.log_event`. Auto-surface fires log via `log_suggest.py`. `metrics.py` reads them. Weekly digest surfaces a 7d snapshot. Read `MattZerg/Projects/idea-backlog.md` § Success Criteria for the metrics-vs-goals mapping.
