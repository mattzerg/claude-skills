---
name: compact-session
description: Within-session context compaction. Reads the current conversation, writes a structured summary (completed work, open tasks, in-flight agents, Matt blockers, key memory rules invoked, files touched, decisions made), and declares "from here forward I work from this summary, not prior context." Pure-prompt — no scripts, no CLI. Pairs with claude-mem (session-to-session); this is WITHIN-session noise shedding. USE PROACTIVELY when the transcript is heavy with stale tool outputs, before invoking a compute-expensive subagent (Task, dispatching-parallel-agents, large research loops), when Matt asks to "compact", "summarize where we are", "tighten the context", "reset focus", or when the assistant notices it is re-reading the same files because earlier reads are buried. See SKILL.md body for FOCUS argument syntax.
---

# compact-session

Within-session context compaction. Pure-prompt — the entire skill lives in this file. No subprocess, no CLI, no external state.

## Why this skill exists

Long Claude sessions accumulate context noise:

- Old tool outputs that are no longer relevant (a dashboard from 40 turns ago, a search that found nothing, a plan that was discarded)
- Completed work that's still sitting in the transcript (files read, edits applied, sub-tasks finished and verified)
- Stale dashboards, expired status snapshots, superseded plans
- Re-reads of the same file because the earlier read scrolled out of working memory

Anthropic's "Effective Context Engineering" guidance names **explicit context compaction** as a missing pattern in most agent loops: read what you've done, write a focused summary, then deliberately work from the summary forward.

This is the within-session counterpart to `claude-mem` (session-to-session). Use both.

## When to invoke

- Matt says: "compact", "summarize where we are", "tighten the context", "reset focus", "what's left to do here", "where are we"
- Before invoking a compute-expensive subagent (Task tool, `dispatching-parallel-agents`, large research loops) — a compacted summary becomes the agent's starting brief instead of the full noisy transcript
- When the assistant notices it is re-reading the same files repeatedly because earlier reads are buried under tool noise
- After a long "exploration phase" that produced a clear next step — compact, then execute the next step against the summary
- Before a long-running parent task hands off to a downstream task (compaction = handoff brief)

Do NOT invoke for:
- Short sessions (<10 turns) — there is nothing to compact
- Mid-flow on a single tight task — compaction breaks momentum
- Just to "tidy up" — only compact when the noise is actually costing tokens or causing re-reads

## Invocation

```
/compact-session [FOCUS]
```

- `FOCUS` is an optional bare-word topic. Examples:
  - `open-tasks` — emphasize what's left to do
  - `in-flight-agents` — emphasize subagents/parallel work still running
  - `matt-blockers` — emphasize items waiting on Matt's decision or input
  - `files-touched` — emphasize file paths read/written this session
  - `decisions-made` — emphasize the choice points and what was decided
- No FOCUS = full structured summary (all sections, balanced).

The FOCUS hint shifts which section gets the most detail; the other sections still appear (truncated) so the summary stays self-contained.

## What to do when invoked

When this skill triggers, the assistant produces ONE structured summary document, in this exact order, then stops referring to prior conversation context unless it explicitly re-reads a file.

### Step 1 — Read the current conversation

Re-scan the session transcript from the start (or from the last compaction if one already occurred this session). Look for:

- User messages that set goals or shifted direction
- Tool calls that produced load-bearing output (file reads that informed decisions, searches that landed)
- Tool calls that produced NOISE (dashboards, status checks, exploratory searches that went nowhere) — these get discarded
- Subagent Task invocations and their results
- Files touched (Read / Write / Edit) — keep the absolute paths
- Decisions made — pick a path, reject an alternative, lock a name, approve a draft
- Memory rules invoked or cited
- Blockers raised — items waiting on Matt, on Idan, on external counterparties

### Step 2 — Produce the structured summary

Emit ONE markdown document with these sections, in this order. Skip a section only if it is genuinely empty; do not pad.

```
## Session compaction — [ISO date] — focus: [FOCUS or "full"]

### Goal
One sentence. What is this session actually trying to accomplish? If it shifted mid-session, name the current goal and parenthetically note the prior one.

### Completed work
Bulleted. Each bullet is one verifiable accomplishment with the artifact path or commit/PR ref. Drop everything that was explored-but-abandoned. Example:
- Wrote ~/zerg/foo/bar.ts (added handler for X case)
- Confirmed ~/.codex/skills/baz/SKILL.md validator passes

### Open tasks
Bulleted, ordered by what's next. Each bullet has the action verb + the artifact. Example:
- Mirror compact-session/ to ~/.codex/skills/
- Run validate_all_skills.py against codex root

### In-flight agents / async work
List any Task() subagents that were dispatched and have not returned, any background bash commands still running, any external waits (PR awaiting review, email awaiting reply). Skip if none.

### Matt blockers
Items that need Matt's input, decision, or action before further progress. One bullet each, phrased as the question or the ask. Skip if none.

### Key memory rules invoked
Cite the memory file paths that shaped decisions this session (e.g., `feedback_codex_vs_claude_skill_paths.md`, `feedback_check_deferred_tools_first.md`). This lets the post-compaction context know which rails are already locked in.

### Files touched
Absolute paths only. Group by Read vs Written/Edited. Skip files that were read-and-discarded (proved irrelevant).

### Decisions made
Choice points with the chosen path. Example:
- Pure-prompt skill (no scripts) — chosen because Matt's spec required no external CLI
- Skill name `compact-session` (rejected `compact`, `session-compact` for collision with existing patterns)

### Discarded context
ONE line per item — what's being dropped from working memory. This makes the shedding explicit. Example:
- Old dashboard output from turn 12 (superseded by current state)
- Exploratory grep for "frobnicate" that found nothing
- Initial draft of SKILL.md (replaced by current version)
```

### Step 3 — Declare the shed

End the summary with this exact line, verbatim:

> **From here forward I will work from this summary, not prior conversation context. If I need detail from earlier, I will re-read the file or re-run the query.**

This is the load-bearing part. It is a commitment surface for the assistant's own future turns. The user can hold the assistant to it.

### Step 4 — Stop

Do not continue the prior task in the same turn. The user (or the next turn) decides what to do with the compacted summary. Common next moves:

- Continue work, but referring to the summary as ground truth
- Dispatch a subagent with the summary as its brief
- Save the summary to disk if Matt asks (default: ephemeral, just in the transcript)
- Hand off to a fresh session (paste summary into the new context)

## Output format notes

- Plain markdown. No frontmatter. No code fences around the summary itself (the section headings are markdown).
- Keep each bullet under one line where possible. Compaction is the point.
- Absolute file paths only (no `./` or `~/` relatives in the Files section — the summary may outlive the cwd).
- Do not invent content. If a section would require fabrication to populate, write `(none)` or omit.

## What this skill is NOT

- Not a session-to-session memory writer — that's `claude-mem` (and the auto-memory at `MEMORY.md`).
- Not a transcript reader skill — does not call `codex-transcript-read` or scrape `~/.claude/projects/`. Reads the current in-context conversation only.
- Not a summarizer for external documents — for that, just use Read + write a summary inline.
- Not a status report generator — `standup` / `morning-brief` / `pr-table` cover that.
- Not a TodoList rewriter — does not mutate the TodoWrite list.

## Anti-patterns

- **Don't compact mid-tight-task.** If the assistant is 3 turns into surgically editing one file, compaction is noise. Wait for a natural break.
- **Don't compact and then ignore the shed declaration.** The "from here forward" line is a commitment, not decoration. If a later turn needs detail not in the summary, re-read explicitly — don't paw through the transcript for it.
- **Don't pad sections.** An empty "In-flight agents" section means there are no in-flight agents. Say `(none)` or omit. Padding defeats compaction.
- **Don't compact for show.** If Matt didn't ask and the context isn't actually heavy, don't volunteer a compaction.
