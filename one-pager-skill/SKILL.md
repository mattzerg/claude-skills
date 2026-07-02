---
name: one-pager-skill
description: Scaffold or review a one-page sales/marketing sheet — for Zerg, Zerg Solutions, ZergStack, microproduct, or client brief. Three variants — `company` (multi-use leave-behind), `consulting` (Vang Algorand/Pento/Quit Genius brief shape), `product` (prospect overview w/ pricing). Two modes — `scaffold` and `review`. Anchored on `_style/one_pager_style.md` + 10-exemplar corpus. USE PROACTIVELY for sell sheet / leave-behind / fact sheet / services brief, OR before any one-pager leaves the vault. Never auto-posts.
allowed-tools: Bash, Read, Write
---


# One-Pager Skill

Sibling to `launch-announcement` (long-form launch posts) and `case-study-skill` (third-person client stories). This one operates on the **one-page collateral** genre — sell sheets, fact sheets, services briefs, leave-behinds, deck-appendix overviews.

A one-pager is not a short blog post. It has its own beats, its own audience contract (skim-first, hierarchy-driven), and its own constraint: it must fit on **one printed page** at 11pt body with 0.75in margins.

## When to invoke

- Matt or Idan asks for a one-pager / sell sheet / leave-behind / company overview / services brief / fact sheet
- Before any one-pager leaves the vault (review pass)
- When Matt wants a short-form-of-deck appendix for an investor or partner conversation
- When a new microproduct ships and needs reseller-enablement collateral
- As the canonical structure for any single-page "what is this and how do I buy it" handoff

## Three variants

| Variant | Audience | Beat shape | Exemplars |
|---|---|---|---|
| **company** | Multi-use: enterprise sales, reseller enablement, network/stakeholder distribution, deck appendix, documentation | Tagline → What we do → Two arms (or one arc) → Who we work with → Why us → Proof → Contact | RELAYTO 7Ms, Hoy Health B2B, eHubCo |
| **consulting** | Services prospects (CTO/CEO evaluating an engagement) | Overview → Workstreams (categories w/ scope hints) → Engagement model + pricing → Past work / about us → Next steps | Algorand Ecosystem Growth, Pento Growth & Analytics, Quit Genius Growth (Matt-authored at Vang) |
| **product** | Product prospects (ops/IT/eng leader evaluating a tool) | Tagline → What it does → Capabilities (3–5 or product list) → Pricing tiers + comparator → Integration / proof → Contact | Hoy Health B2C, Joi (seed pitch), Intercept TeleMed |

## Two modes

### scaffold — generate a draft skeleton from a brief

```bash
python3 ~/.claude/skills/one-pager-skill/run.py scaffold <variant> "<product or org brief>" [flags]
```

`<variant>` ∈ `company` | `consulting` | `product`

The brief is a free-text description. Examples:
- `scaffold company "Zerg AI — agent-native software stack + services arm; ZergStack (5 microproducts) + Zerg Solutions (CesiumAstro, Andesite, Durable)"`
- `scaffold consulting "Zerg Solutions — agent-native product/GTM/platform shipped, not advised; workstream-based engagements; Idan + Matt"`
- `scaffold product "ZergStack — Zergboard + ZergChat + ZergCal + ZergMeeting + ZergMail; agent-aware; $1 Basic / $9 Pro; bundle SKU $19"`

Flags:
- `--out-dir DIR` — default: `/tmp/one-pager/`
- `--vault` — write directly to the vault (default: `/tmp/one-pager/`). Routes by variant: `company`→`MattZerg/Zerg/`, `consulting`→`MattZerg/Consulting/`, `product`→`MattZerg/Projects/Zerg-Production/Zstack/` (override with `--vault-dir DIR`).
- `--vault-dir DIR` — explicit vault destination, overrides the variant routing
- `--slug SLUG` — file slug (default: derived from brief)
- `--audience X` — `enterprise-sales` | `reseller-enablement` | `services-prospect` | `product-prospect` | `network-leave-behind` | `investor` (default per variant)
- `--length WORDS` — target word count (default: 380, valid 250–550). One-pager fits ~400 words at 11pt body w/ 0.75in margins.
- `--cta X` — `try` | `contact` | `book-call` | `docs` | `none` (default per variant)
- `--model MODEL` — Claude model (default: `claude-opus-4-7`)
- `--no-pdf` — skip PDF + Preview open

Writes:
- `<slug>.one-pager.md` — beat-by-beat skeleton with placeholders + corpus exemplar callouts
- `<slug>.checklist.md` — pre-publish checklist auto-filled from `one_pager_style.md`
- `<slug>.one-pager.pdf` (unless `--no-pdf`)

### review — audit an existing draft

```bash
python3 ~/.claude/skills/one-pager-skill/run.py review <draft.md> [<more.md>...] [flags]
```

Flags:
- `--out-dir DIR` — output directory (default: `/tmp/one-pager/`)
- `--model MODEL` — default: `claude-opus-4-7`
- `--no-pdf` — skip PDF + Preview open
- `--quick` — drop the corpus from anchors; faster, less calibrated

Per draft, writes:
- `<draft>.review.md` — annotated review with HIGH/MEDIUM/LOW findings, each citing a rule from `one_pager_style.md` + a corpus exemplar where relevant
- `<draft>.interview.md` — LOW-confidence items routed for live discussion (only if any exist)

## Output register

**Professional/technical/structured, NOT Matt-voice cosplay.** Findings cite:
- **Rule:** which line/section of `one_pager_style.md`
- **Corpus exemplar:** which doc in the 10-doc corpus does this well (or demonstrates the anti-pattern)
- **Confidence:** HIGH / MEDIUM / LOW (review mode only)
- **Suggestion:** rewrite OR scaffold beat OR question

## Anchors loaded each run

1. `MattZerg/_style/one_pager_style.md` — primary genre guide (variant-specific beat sequences, voice rules, anti-patterns, pre-publish test, page-fit rules)
2. `MattZerg/_style/writing_style.md` — sentence-level voice + AI tells (loaded for context; copyedit-skill is the primary catcher)
3. `~/.claude/skills/one-pager-skill/corpus/one-pager-corpus.md` — 10 Drive exemplar analysis (Hoy Health B2B/B2C, Joi, Econometrics, Intercept TeleMed, RELAYTO, Algorand, Quit Genius, Pento, eHubCo)
4. `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` — cross-genre pattern catalog. Cross-reference the **prose** section during scaffold + review; cite findings by pattern slug alongside the one_pager_style.md rule.
- **Catalog patterns to cite by slug** (Section A Universal / process): honest-scoping
- **Catalog patterns to cite by slug** (Section C Prose / writing): cross-format-repetition, pulp-caption-discipline, em-dash-budget
- **Catalog patterns to cite by slug** (Section E CRO / marketing, ia-ordering cross-cited from Section B): ia-ordering, single-cta, missing-cta, shipped-vs-roadmap-visibility, capability-claim-unverified
- **Catalog patterns to cite by slug** (Section I Launch / deck): deferred-with-reason
4. **Variant-specific positioning** (loaded only when relevant):
   - `company` → `MattZerg/Zerg/positioning.md` (if exists)
   - `consulting` → `MattZerg/Consulting/positioning.md` (if exists)
   - `product` → `MattZerg/Projects/Zerg-Production/Zstack/Zstack.md` + `Pricing-Snapshot.md` + `Integration.md`

## What this skill is NOT

- Not a sentence-level copyeditor — that's `fakematt-copyedit`. Pair: scaffold/review here (genre layer), then copyedit (sentence layer).
- Not a long-form launch post drafter — that's `launch-announcement`.
- Not a case-study writer — that's `case-study-skill`.
- Not a designed-PDF renderer (yet) — Phase 1 ships markdown → Chrome-headless PDF. Branded HTML+CSS variant is a Phase 4 follow-up.
- Not a publisher — doesn't push to Drive. Matt uploads after review.

## Safety

- **Never auto-posts.** Writes to disk only.
- **Vault writes require explicit `--vault` flag.** Default output goes to `/tmp/one-pager/`.
- **Doesn't modify the source draft.** Reviews land in a separate file; scaffolds get a fresh slug.
- **No memory writes.** Reads anchors; doesn't write to memory.

## Cross-genre review rules (memory anchors)

The review pass should apply these universal rules in addition to the skill's genre-specific corpus:

- **Honest scoping** — see `feedback_honest_scoping_universal.md`. Cover/intro/dek must reconcile with body content; name what's NOT included as explicitly as what IS. Cover-vs-body mismatch is a ship-blocker, not a polish item.
