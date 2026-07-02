---
name: pr-table
description: 'Generate a single-screen markdown table view of Matt''s PR pipeline — open PRs (with cap state, review state, CI, last activity), merged in past 7 days, closed-without-merge in past 7 days, and held local branches (queued behind cap). Reads `gh search prs --author=@me`, `gh pr view` for review/CI/mergeable detail, and `git worktree list` plus per-worktree git logs for held branches. Read-only — never opens, closes, pushes, or comments. USE PROACTIVELY when Matt asks for "PR table", "PR status", "PR pipeline", "what PRs do I have", "show my PRs", or before any planning conversation that needs the queue state.'
---


# PR Table Skill

One-command snapshot of Matt's PR universe — open, recent merged, recent closed, and held local branches queued behind the open-PR cap. The win is one command instead of fifteen `gh` + `git` invocations across worktrees.

## Run

```bash
python3 ~/.claude/skills/pr-table/run.py
```

Prints markdown to stdout. Claude renders inline. No flags needed in the common case.

## Optional flags

- `--repo <owner/name>` — scope to one repo (default: scans `Epoch-ML/zerg`).
- `--days N` — change the merged/closed window (default 7).
- `--cap N` — show "X / N" cap state (default 2 per `feedback_pr_cap_check_first.md`).
- `--no-held` — skip held-branch scan if you only want PR-side state.

## What it shows

**Header line** — open / cap / held / merged-this-week counts.

**Section 1 — Open PRs** (counts toward cap)

| # | Title | State | Reviews | CI | Last activity |

State values: `MERGEABLE/CLEAN`, `MERGEABLE/BLOCKED` (review or required-check), `BEHIND` (base moved), `CONFLICTING`, `DRAFT`. Reviews collapses the latest decision per reviewer (`APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`, or `awaiting`). CI is `✓` / `✗` / `⏳` / `—`. Last activity is the most recent of (commit pushed, comment posted, review submitted) with the actor.

**Section 2 — Held local** (queued behind cap)

Discovered via `git worktree list` for `Epoch-ML/zerg`. A worktree is "held" if its branch has no associated open PR.

| Branch | Surface | Ahead/Behind | Last commit | Pre-flight | Blockers |

`Surface` is inferred from the first non-trivial changed-path prefix (`web/`, `zergwallet/`, `zergaudience/`, `.github/`, etc.). `Pre-flight` reads `.pr-stage-state.json` if present (fresh / stale / never). `Blockers` checks: `cap` if open count ≥ cap; `launch-confirm` if branch touches a route that needs a token; `behind` if base has moved.

**Section 3 — Merged in past N days**

| # | Title | Merged | By |

**Section 4 — Closed without merge in past N days** (FYI only)

| # | Title | Closed | Last reviewer note |

## When NOT to use

- For deep dive on a single PR — use `gh pr view <num>` directly.
- For the launch-readiness ship gate — that's `ship-gate`.
- For draft creation — that's `pr-gate` (this skill is read-only).

## Conventions

- Times are local PT, relative ("2h ago", "1d ago") for ≤7d; absolute date for older.
- Long titles truncated at 50 chars with `…`.
- Output is markdown so it renders cleanly in Claude Code chat AND can be piped to a file or Slack.
- Never auto-posts. If Matt wants the table in Slack, paste it manually.

## Anti-drift

The skill is intentionally a *view*, not a *driver*. It must never:
- Open, close, push, or comment on PRs
- Run `git rebase`, `git push`, or anything that mutates worktree state
- Invoke pre-flight skills (fakeidan / fakematt-copyedit) — those are pr-gate / pr-stage's job

If Matt wants action on what the table shows, route through `pr-gate` (submission) or a future `pr-stage` (rebase / pre-flight).
