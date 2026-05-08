---
name: pr-gate
description: Hard gate before opening any PR. Runs fakematt-* (relevant to the diff) + fakeidan automatically; if any HIGH finding surfaces, refuses to open the PR until it's addressed (or `--force`d). Operationalizes `feedback_pre_pr_ritual.md` and `feedback_minimize_prs.md` — turns "always run pre-flight reviews" into "the system literally won't let you open a PR without them." USE PROACTIVELY whenever Matt is about to open a PR. Wraps `gh pr create` — just call this instead of gh directly. Never auto-merges; outputs gate findings + the underlying gh result.
allowed-tools: Bash, Read, Write
---


# PR Gate Skill

Pre-flight gate that wraps `gh pr create`. Refuses to open a PR until:
1. **GitHub identity routing** is satisfied — Matt personal projects and Matt-led/heavily supervised PRs use `matteisn`; AI/Fake Matt-led Zerg/company PRs use `mattzerg`.
2. **Open-PR cap** is satisfied — Matt has at most 2 open PRs across all repos (3 with `--urgent`). Bundle, don't multiply Idan's review queue.
3. **fakeidan** has reviewed the diff and produced no HIGH findings
4. **fakematt-copyedit** has reviewed any prose files in the diff and produced no HIGH findings
5. **launch-announcement review** has run on any launch-post drafts touched (if any)

Plus a silent scrub: any `Co-Authored-By: Claude` / `Generated with Claude Code` lines in `--body` or `--body-file` are stripped before `gh pr create` runs. AI agents never appear as PR coauthors.

Plus an **asset-preview block**: when the diff touches images, videos, blog/MDX posts, landing pages, or other copy, the gate auto-builds a collapsible `<details>` block (images embedded inline, videos linked to their inline player, blogs excerpted with title/description/hero, landing pages linked to the deploy preview, copy shown as diff hunks) and prepends it to `--body` / `--body-file`. The block is also written to `<repo>/.pr-gate-asset-previews.md` so Matt can paste it manually if `gh` opens an editor instead. Suppress with `--no-asset-previews`.

Failures dump findings to `<repo>/.pr-gate-review.md` and halt. Matt either fixes them or runs with `--force` to override (the override is logged).

## Why this exists

`feedback_pre_pr_ritual.md` and `feedback_minimize_prs.md` together codify the rule: never open a PR without running the fake-skills + simulating Idan first. That rule is high-priority but human enforcement is unreliable. The gate makes it mechanical.

## When to invoke

- Whenever Matt is about to open a PR. Use this skill instead of `gh pr create` directly.
- When automation/cron wants to open a PR — same gate applies.

If you're not opening a PR, don't use this. Use `gh pr` directly for things like `gh pr list` / `gh pr view`.

## Default invocation

```bash
python3 ~/.claude/skills/pr-gate/run.py [gh-pr-create-args...] [gate-flags...]

# gate-flags:
#   --base BRANCH        base branch (default: development; falls back to main)
#   --skip-copyedit      skip fakematt-copyedit (only if no prose touched)
#   --skip-fakeidan      skip fakeidan (DON'T — gate's main value)
#   --urgent             raise open-PR cap from 2 to 3 (logged)
#   --force              override HIGH findings or backlog cap (logged)
#   --dry-run            run gate, print verdict, do NOT open the PR
#   --matt-personal      require the matteisn GitHub account
#   --matt-led           require the matteisn GitHub account
#   --ai-led             require mattzerg unless this is a personal project
#   --no-asset-previews  suppress auto-generated asset preview block in PR body

# any other flags are passed through to `gh pr create` verbatim:
python3 ~/.claude/skills/pr-gate/run.py \
  --title "fix: dedup before write" \
  --body "..." \
  --label "bug,zergwallet"
```

## Workflow

1. Verify GitHub identity before any PR work. Personal projects and `--matt-led`/`--matt-personal` require `matteisn`; `--ai-led` and default agent-led non-personal work require `mattzerg`.
2. Query open-PR backlog via `gh search prs --author=@me --state=open` (cheap, runs first)
3. If backlog ≥ cap (default 2, `--urgent` → 3) → block with the list of open PRs so Matt can pick one to fold into
4. Compute diff: `git diff <base>...HEAD --name-only` + full diff content
5. Classify changed files (code / prose / config / other)
6. Run fakeidan on the diff (mode auto-picked: `code` if any code files, else `prose`)
7. Run fakematt-copyedit on changed prose files (`*.md` in `Writing/`, `MattZerg/`, `web/src/public/content/`)
8. If any launch-post files touched (`MattZerg/Writing/Launch*` or similar), run launch-announcement review
9. Parse outputs for HIGH findings (regex scan)
10. If any HIGH → write `.pr-gate-review.md`, exit 1 (unless `--force`)
11. Build asset preview block from any image/video/blog/landing/copy file in the diff (skipped via `--no-asset-previews`); write to `.pr-gate-asset-previews.md` and prepend to `--body` / `--body-file`
12. On pass: scrub `--body` / `--body-file` for AI-coauthor lines, then invoke `gh pr create`
13. On `--force` / `--urgent`: log to `~/.claude/skills/pr-gate/logs/overrides.log`, open anyway

## Hard rules

- **Never auto-merges.** Just opens; Matt or CI handles merge.
- **Wrong GitHub account blocks.** `--force` does not override identity routing; switch accounts first.
- **Override is logged.** `--force` and `--urgent` are allowed but recorded. Audit trail = accountability.
- **Failure mode is fail-closed.** If a fake-skill crashes, the gate refuses to open the PR (don't accidentally bypass review on a tooling bug).
- **Gate only runs `--review` modes.** It does NOT modify the diff or push fixes — that's Matt's job after seeing findings.
- **No AI coauthors.** `Co-Authored-By: Claude` / `Generated with Claude Code` lines are stripped from the PR body silently. Claude Code is a tool, not a contributor.

## Hook / CI Identity Config

The pre-push hook auto-detects personal repos from GitHub owner `matteisn` or `mattheweisner`. For ambiguous repos, set one of:

```bash
git config pr-gate.identity matt-personal
git config pr-gate.identity matt-led
git config pr-gate.identity ai-led
```

The GitHub Action source also supports repo variable `PR_GATE_IDENTITY` with the same values. It fails CI if the PR author does not match the configured identity. If unset on non-personal repos, CI does not infer Matt-led vs AI-led because GitHub Actions cannot observe oversight context.

## See also

- `feedback_pre_pr_ritual.md` — the rule this enforces
- `feedback_minimize_prs.md` — bundle, don't split
- `feedback_idan_pr_review_bar.md` — what fakeidan checks against
- `feedback_pr_body_unlocks.md` — every PR body needs "why now + what this unlocks"
