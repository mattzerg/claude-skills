---
name: pr-stage
description: 'Mutation verbs for the PR queue — sibling to pr-table (read-only) and pr-gate (final-strict submission check). Three verbs: `list` (pass-through to pr-table), `rebase-all` (fetch origin/development once, then rebase every held-branch worktree onto it; aborts on conflict and reports per-branch), and `check branch` (run lightweight pre-flight — fakeidan + fakematt-copyedit on the branch diff vs base, write `.pr-stage/state.json` so pr-table can show fresh/stale). Reads `git worktree list` for `Epoch-ML/zerg`. Skips worktrees that match an open PR headRefName. USE PROACTIVELY when Matt asks to "rebase the queue", "refresh held branches", "sync held branches against dev", "pre-flight a branch", or before pr-gate on a held branch. Never opens, closes, pushes, or comments — only rebases local branches and writes state files.'
---


# PR Stage Skill

Sibling to `pr-table` (read-only) and `pr-gate` (final-strict submission check). pr-stage is the workshop layer where held branches stay current with `origin/development` while they wait behind the open-PR cap.

## Run

```bash
python3 ~/.claude/skills/pr-stage/run.py <verb> [flags]
```

## Verbs

**`list`** — pass-through to `pr-table`. Shows open + held + merged 7d + closed 7d.

```bash
python3 ~/.claude/skills/pr-stage/run.py list
```

**`rebase-all`** — fetch `origin/development` once, iterate held-branch worktrees, rebase each onto base. Aborts the rebase on conflict and reports the branch — does not force-resolve. After all rebases attempted, prints a per-branch summary (`✓ rebased`, `→ no-op`, `✗ conflict`, `↷ skipped (matches open PR)`).

```bash
python3 ~/.claude/skills/pr-stage/run.py rebase-all
python3 ~/.claude/skills/pr-stage/run.py rebase-all --base origin/main
python3 ~/.claude/skills/pr-stage/run.py rebase-all --dry-run     # show what would happen
```

**`check <branch>`** — run lightweight pre-flight on the branch's diff vs base. Shells out to `fakeidan` (mode auto-detected: code if any code files else prose) and `fakematt-copyedit` (only if prose files in diff). Writes `.pr-stage/state.json` in the worktree with `diff_hash`, `checked_at`, and per-skill summary, plus review files alongside. pr-table reads this state to show `fresh (Nh)` / `stale (diff changed)` / `never` in its Pre-flight column.

```bash
python3 ~/.claude/skills/pr-stage/run.py check matt/zergwallet-plaid-v2
python3 ~/.claude/skills/pr-stage/run.py check matt/zw-ui-refresh --skip-copyedit
python3 ~/.claude/skills/pr-stage/run.py check matt/zw-prgate-ci --base origin/main
```

Unlike pr-gate, `check` does NOT block — it informs. pr-gate at submit time is the actual block. This separation is intentional per `feedback_gate_thresholds.md`.

## Future verbs (not yet built)

- **`promote <branch>`** — verify clean rebase + fresh pre-flight + cap-slot-available + launch-confirm (if applicable), then hand off to `pr-gate`.

When you need it, add it — don't pre-build verbs that aren't being used.

## When to use

- Before declaring held branches "ready to PR" — run `rebase-all` so they're current against the just-merged head.
- After an open PR merges and a cap slot frees — `list` first to see the queue, then `rebase-all` before pre-flight on the next promotion candidate.
- After a major dev-branch landing (e.g., a refactor that touches many products) — refresh the queue.

## When NOT to use

- For a single branch — `cd` to the worktree and `git rebase origin/development` directly.
- If any held worktree has uncommitted changes — pr-stage skips them with `↷ dirty` rather than risk losing work. Resolve manually first.
- For force-pushes after rebase — pr-stage NEVER pushes. After a rebase, run `git push --force-with-lease` from the worktree manually if the branch is already on origin.

## Anti-drift

- `rebase-all` aborts on conflict (`git rebase --abort`) and continues to the next branch. It will not silently leave a worktree mid-rebase.
- Worktrees whose branch matches an open PR's `headRefName` are SKIPPED — those are pr-gate's territory, not pr-stage's.
- The skill never invokes pr-gate, never runs `gh pr create`, never pushes. Hand-off is explicit: pr-stage prepares; user invokes pr-gate.

## Pairs with

- `pr-table` — read-only view of the same queue. `pr-stage list` pass-throughs to it.
- `pr-gate` — final-strict submission check. pr-stage is the upstream prep step.
