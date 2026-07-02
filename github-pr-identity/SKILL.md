---
name: github-pr-identity
description: Enforce Matt's GitHub account routing before PRs, pushes, branch publication, and review requests. Use whenever creating or preparing a pull request, pushing a branch, checking GitHub auth, or deciding whether work should be attributed to Matt personally or to the work-identity (mattzerg).
metadata:
  short-description: Route PRs to the right GitHub account + commit author
---


# GitHub PR Identity

Two independent decisions for any Zerg-related PR:

1. **Which GitHub account opens the PR** — determined by REPO NAMESPACE.
2. **Which commit author is recorded on the commits** — determined by COMMIT INTENT (content/marketing/small vs. product/AI-heavy).

Decoupling these is intentional. `matteisn` cannot open PRs against `Epoch-ML/*` (no org membership). But commit attribution shows up on github.com under each commit, independent of who opened the PR — so `matteisn` can still be the visible author on content/marketing commits that flow through an `mattzerg`-opened PR.

## Rule 1 — PR opener (repo namespace)

| Repo namespace | PR opener account |
|---|---|
| `Epoch-ML/*` (zerg, zerg-gg, ca-org, durable, airwallex_poc, …) | **`mattzerg`** (only account with Epoch-ML org membership) |
| `matteisn/*` (matteisn-site, vang.capital, vang.advisory, personal projects) | **`matteisn`** |
| `mattzerg/*` (shared dev infra: claude-skills, marketing sites) | **`mattzerg`** |

There is **no authorship-mode override** for Epoch-ML repos. AI-heavy or Matt-heavy, the PR opens via `mattzerg` because no other account works.

## Rule 2 — Commit author (intent)

Within a single PR, individual commits can have different authors. Set commit author at commit time (`git commit --author="..."` or via `git config user.name`/`user.email` before the commit).

| Commit shape | Commit author |
|---|---|
| Content pushes (blog markdown, marketing copy, social drafts, case-study text) | `Matt Eisner <matteisn@gmail.com>` |
| Marketing pages (landing pages, web copy, brand pages) | `Matt Eisner <matteisn@gmail.com>` |
| Small commits (≤200 lines, non-product changes — config tweaks, docs, copy fixes) | `Matt Eisner <matteisn@gmail.com>` |
| Major product changes (feature code, API, schema, infra) | `Matt Eisner <matthew@zergai.com>` |
| AI-heavy (≥85% offloaded to AI/Claude/Codex) | `Matt Eisner <matthew@zergai.com>` |

Path heuristics (apply when ambiguous):

- `*/blog/`, `*/content/blog/`, `*/Writing/`, `*/CaseStudies/` → matteisn
- `*/marketing/`, `*/landing/`, `*/brand/`, `*/web/src/public/content/` → matteisn
- `*/src/**` (code, not content), `*/api/`, `*/schema/`, `*/migrations/` → mattzerg
- `*/SKILL.md`, `*.py` under `.claude/` or `.config/zerg/` (Matt's tooling) → mattzerg (heavily AI-assisted)
- Mixed-path commit → split into two commits before pushing if the boundary is clean; otherwise default to the larger-impact path.

## Required Check

Before any `gh pr create`, branch push, or PR metadata update:

1. **Identify the target repo namespace** — read from `gh repo view` or remote URL. This decides PR opener.
2. **Run `gh auth status`** to confirm the active account matches Rule 1. If not, switch via `gh auth switch -u <account>`.
3. **Inspect the commits being pushed** — for each, check the commit author. If author doesn't match the commit shape per Rule 2, rebase to re-author before pushing.
4. **Open the PR.** Mention in the final handoff: PR opener account + the commit-author split if non-trivial.

## Why two rules

The 2026-05-09 PR #303 incident lost ~5 min when `--matt-led` flag flipped the gate to `matteisn`, then `gh pr create` failed against an Epoch-ML repo. Root cause: trying to encode "Matt-led authorship" via the PR opener axis when that axis is constrained by org membership. Splitting the decision — namespace for opener, intent for commit author — eliminates the failure mode while still surfacing Matt's personal-credibility signal on the commits that warrant it.

## Examples

- **Blog post for zergai.com** (Epoch-ML/zerg, paths under `web/src/public/content/blog/`):
  PR opener: `mattzerg`. Commit author: `Matt Eisner <matteisn@gmail.com>`. Visible attribution on the commits reads as Matt-personal.

- **Zergboard feature shipping new schema** (Epoch-ML/zerg, paths under `zerg/src/zergboard/`):
  PR opener: `mattzerg`. Commit author: `Matt Eisner <matthew@zergai.com>`. Visible attribution as work-identity.

- **Mixed PR — blog post + a small Zergboard config tweak**:
  Two commits. Commit 1 (blog markdown) → matteisn. Commit 2 (config) → matteisn (≤200 lines, non-product). PR opens from mattzerg.

- **vang.capital landing page update**:
  PR opener: `matteisn`. Commit author: `Matt Eisner <matteisn@gmail.com>`. Personal-site repo all the way through.

- **claude-skills repo (mattzerg/claude-skills) — new skill added with heavy AI assistance**:
  PR opener: `mattzerg`. Commit author: `Matt Eisner <matthew@zergai.com>`.

## Legacy flags (`--matt-led`, `--matt-personal`)

The `pr-gate` skill still accepts these flags for backward compatibility on personal-site repos (`matteisn/*`), where they're meaningful. For `Epoch-ML/*` repos the flags are effectively ignored — namespace rules win. A follow-up pr-gate change can deprecate them entirely once usage tails off.

## Pairs with

- `pr-gate` skill — wraps `gh pr create` and enforces both rules at push time.
- `feedback_epoch_ml_org_account.md` — empirical constraint that drove Rule 1.
- `MattZerg/Projects/Zerg-Production/Growth/decisions/dec-github-account-routing.md` — closed decision record.
