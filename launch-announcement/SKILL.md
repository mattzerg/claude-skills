---
name: launch-announcement
description: Review or scaffold a launch announcement blog post (product, feature, funding, milestone) against a 15-post corpus from Stripe, Linear, Anthropic, OpenAI, Vercel, Cloudflare, Plaid, Resend, Supabase, Modal, Replit, Notion, Figma, GitHub, and Mercury. Two modes — `review` (audit a draft for missing structural beats, voice drift, anti-patterns) and `scaffold` (generate a draft skeleton from a product brief). Anchored on `MattZerg/_style/launch_announcement_style.md` + the corpus exemplars. Output is professional/structured with citations to the rule or pattern; never auto-posts. USE PROACTIVELY (mandatory entry-point — do NOT draft directly) when Matt says any of — "scaffold a launch", "launch announcement for X", "draft a launch post", "write the launch for", "blog post for the X launch", "v2 launch", or before ANY launch post leaves the vault. Hypothesis 2026-05-28 — stronger trigger phrases lift skill invocation in -p mode from 0/5 to ≥1/5 golden cases within 14 days.
allowed-tools: Bash, Read, Write
---


# Launch Announcement Skill

Sibling to `fakematt-copyedit` (sentence-level voice review). This one operates one layer up: at the **structural / genre** level. The copyedit skill catches em-dash overuse; this skill catches "you led with the news in paragraph 3 instead of paragraph 1" or "you have no concrete number in the body."

Genre = launch announcement (product, feature, funding round, milestone, version bump).

## When to invoke

- Before any launch post ships to the Zerg blog
- When Matt has a product/feature ready and asks "let's draft a launch post"
- When Matt drops an existing draft and asks for a structural / pre-publish review
- As a pair with `fakematt-copyedit`: scaffold or review here first (genre layer), then copyedit (sentence layer)
- Before the LinkedIn / X variants are derived — the launch post needs to land structurally first

## Two modes

### review — audit an existing draft

```bash
python3 ~/.claude/skills/launch-announcement/run.py review <draft.md> [<more.md>...] [flags]
```

Flags:
- `--out-dir DIR` — output directory (default: `/tmp/launch-announcement/`)
- `--model MODEL` — Claude model (default: `claude-opus-4-7`)
- `--no-pdf` — skip PDF + Preview open
- `--quick` — drop the corpus-exemplar comparison; faster, less calibrated

Per draft, writes:
- `<draft>.review.md` — annotated review with HIGH/MEDIUM/LOW findings, each citing a rule from `launch_announcement_style.md` + a corpus exemplar where relevant
- `<draft>.interview.md` — LOW-confidence items routed for live discussion (only if any exist)

Plus a session-level `session-summary.md`.

### scaffold — generate a draft skeleton from a brief

```bash
python3 ~/.claude/skills/launch-announcement/run.py scaffold "<product brief>" [flags]
```

The brief is a free-text product description. Examples:
- `"Zergwallet — multi-rail crypto + fiat wallet, atomic cross-rail asset swap, AI agents within scoped policy"`
- `"ZergSend Phase 2 — broadcast emails + drips with canonical contact graph, paired with Zergboard signup"`

Flags:
- `--out-dir DIR` — default: `/tmp/launch-announcement/`
- `--model MODEL` — default: `claude-opus-4-7`
- `--length WORDS` — target word count (default: 1500; valid 600–3000). Outside the 1,200–1,800 sweet spot, the script will emit a comment in the scaffold.
- `--audience AUDIENCE` — `infra-engineer` (default) | `designer` | `fintech-buyer` | `general-tech`. Drives hook style, technical depth, and CTA shape.
- `--cta CTA` — `try` (default) | `waitlist` | `docs` | `sales` | `none`
- `--companion` — also emit a `<draft>.companion.md` outline for a paired technical post (Vercel pattern)
- `--no-pdf` — skip PDF + Preview open

Writes:
- `<slug>.draft.md` — section-by-section skeleton with placeholders, beat names as comments, target word counts per section, and corpus-exemplar callouts
- `<slug>.companion.md` (with `--companion`) — outline for the paired "how we built it" post
- `<slug>.checklist.md` — pre-publish checklist auto-filled with the ten gates from `launch_announcement_style.md`

## Output convention

When invoked with `--product <slug>` (or by `launch-pack`), the canonical
output path is `Growth/launches/<slug>/announcement.md` inside the MattZerg
vault. The skill still writes a `<slug>.draft.md` + `<slug>.checklist.md`
into `--out-dir` for backward compatibility; the canonical path is the
copy other skills (zpub, launch-ops, content-distribution) read from.

Pass `--out PATH` to override the canonical path entirely. With neither
flag set, output stays in `--out-dir` (default `/tmp/launch-announcement/`)
and no canonical copy is written.

## Output register

**Professional/technical/structured, NOT Matt-voice cosplay.** Same rule as `fakematt-copyedit`. Findings cite:
- **Rule:** which line/section of `launch_announcement_style.md` (or the AI Cleanup checklist where applicable)
- **Corpus exemplar:** which company in the 15-post corpus does this well (or which one demonstrates the anti-pattern)
- **Confidence:** HIGH / MEDIUM / LOW (review mode only)
- **Suggestion:** rewrite OR scaffold beat OR question

## Anchors loaded each run

1. `MattZerg/_style/launch_announcement_style.md` — primary genre guide (default shape, what works, what hurts, voice rules, pre-publish test)
2. `MattZerg/_style/launch_distribution_playbook.md` — post-publish operating playbook (gates 11–17 in the pre-publish test, T+0/T+1/T+3/T+7/T+30 cadence). Required reading since 2026-05-27 — Gigacontext post-mortem.
3. `MattZerg/_style/writing_style.md` — sentence-level voice + AI tells (loaded for context; copyedit-skill is the primary catcher)
4. `~/.claude/skills/launch-announcement/corpus/launch-announcement-corpus.md` — full 15-post analysis (per-post breakdown + synthesis), used as ground truth for "X company does this"
5. `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` — cross-genre pattern catalog. Cross-reference the **launch** and **prose** sections during scaffold + review; cite findings by pattern slug alongside the launch_announcement_style.md rule.
- **Catalog patterns to cite by slug** (Section A Universal / process): honest-scoping, prior-review-carry-forward
- **Catalog patterns to cite by slug** (Section C Prose / writing): cross-format-repetition, pulp-caption-discipline, punchline-isolation, em-dash-budget
- **Catalog patterns to cite by slug** (Section E CRO / marketing): shipped-vs-roadmap-visibility, capability-claim-unverified, single-cta, missing-cta
- **Catalog patterns to cite by slug** (Section I Launch / deck): deferred-with-reason, one-product-at-a-time

## What this skill is NOT

- Not a sentence-level copyeditor — that's `fakematt-copyedit`. Run both: this for genre/structure, copyedit for voice.
- Not a hero-image generator — that's `blog-imagery`.
- Not a publisher — doesn't push to the Zerg blog repo (that's a CLAUDE.md operation).
- Not a social-variant deriver — drafts the launch post, not LinkedIn/thread/single-tweet variants. (`fakematt-copyedit` reviews those.)
- Not for thought pieces — generic blog posts go through `fakematt-copyedit` only. Launch posts have genre conventions thought pieces don't.

## Safety

- **Never auto-posts.** Writes to disk only.
- **Doesn't modify the source draft.** Reviews land in a separate file; scaffolds get a fresh slug.
- **No memory writes.** Reads anchors; doesn't write to memory.

## Cross-genre review rules (memory anchors)

The review pass should apply these universal rules in addition to the skill's genre-specific corpus:

- **Honest scoping** — see `feedback_honest_scoping_universal.md`. Cover/intro/dek must reconcile with body content; name what's NOT included as explicitly as what IS. Cover-vs-body mismatch is a ship-blocker, not a polish item.
