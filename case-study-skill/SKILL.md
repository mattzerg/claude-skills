---
name: case-study-skill
description: Capture, scaffold, and review Zerg AI client case studies (CesiumAstro, Andesite, Durable, etc.) against a 12-exemplar corpus from McKinsey, BCG, Thoughtworks, Anthropic, OpenAI, Glean, Stripe, Vercel, Snowflake, Pivotal, Modal. Three modes — `capture` (pull raw evidence from vault + Linear + Zergboard + Conversations into a structured brief), `scaffold` (generate a draft from the brief), and `review` (audit a draft for fabricated metrics, NDA leakage, voice drift, missing structural beats). Anchored on `~/Obsidian/Zerg/MattZerg/_style/case_study_style.md` + the corpus exemplars. Output is professional/structured with citations to the rule or pattern; never auto-posts; hard-refuses scaffolding without NDA clearance. USE PROACTIVELY when Matt or Idan mentions a Zerg client win, asks "let's draft a case study for [client]", or before any case study leaves the vault.
allowed-tools: Bash, Read, Write
---

# Case Study Skill

Sibling to `launch-announcement` (genre-layer review/scaffold for launch posts), `fakematt-copyedit` (sentence-level voice review), and `competitive-review-skill` (category review). This one operates at the **case-study genre** layer: third-person narratives of Zerg client engagements, anchored in dated evidence and named people.

Genre = Zerg solution-delivery case study. NOT testimonial. NOT launch post. NOT internal Zstack dogfooding write-up. NOT Matt's pre-Zerg portfolio.

## When to invoke

- Before any case study ships to the Zerg blog or is sent to a prospect
- When Matt or Idan says "let's draft a case study for CesiumAstro" / "we should write up the Durable engagement"
- When a client engagement closes a meaningful milestone and the win deserves capture
- When an existing draft needs a pre-publish review (anti-fabrication grep, NDA gate check, structural beats)
- As a pair with `fakematt-copyedit`: scaffold or review here first (genre layer), then copyedit (sentence layer)

## Three modes

### capture — pull raw evidence into a structured brief

```bash
python3 ~/.claude/skills/case-study-skill/run.py capture <client> [--project <slug>] [--kind delivery|advisory] [flags]
```

Searches in priority order, with provenance tagged on every snippet:

1. `~/Obsidian/Zerg/MattZerg/Companies/<client>.md` — CRM stub, sets identity (HIGH weight)
2. `~/Obsidian/Zerg/MattZerg/Epoch/Projects/Client Pipeline.md` — primary source for active engagements (HIGH)
3. `~/Obsidian/Zerg/MattZerg/Epoch/Projects/Product Glossary.md` — what Zerg products were used (HIGH)
4. `~/Obsidian/Zerg/MattZerg/Conversations/Claude/` grep — task narrative (MEDIUM)
5. `~/Obsidian/Zerg/MattZerg/Conversations/Slack/<channel>/` grep, incl. `#standup` — decision history (MEDIUM)
6. `~/Obsidian/Zerg/MattZerg/Roadmap/*.md` — recent roadmap docs (MEDIUM)
7. `~/Obsidian/Zerg/MattZerg/Notes/Testimonials.md` — candidate quotes (HIGH for verbatim quotes)

Linear and Zergboard pulls are deferred to live skill calls when the user asks the agent to enrich the brief — the capture script writes a brief skeleton + identifies which trackers should be queried, but doesn't shell out itself.

Writes to `state/briefs/<client>-<project>.brief.md` with frontmatter + sections: scope · deliverables · outcomes (each tagged HIGH/MEDIUM/LOW confidence with evidence path) · candidate_quotes · evidence_links · gaps · risks · `nda_status: unknown` (default).

### scaffold — generate a draft case study from a brief

```bash
python3 ~/.claude/skills/case-study-skill/run.py scaffold <brief-path> [flags]
```

Flags:
- `--out-dir DIR` — default: `~/Obsidian/Zerg/MattZerg/CaseStudies/<client-slug>/`
- `--model MODEL` — default: `claude-opus-4-7`
- `--length WORDS` — target word count (default: 1500; band: 1,200–2,000)
- `--cleared-for-publication` — explicit override of `nda_status: unknown`. Logs `nda_override_at` + `nda_override_by` into the case-study frontmatter. **Hard-refused** if brief says `nda_status: restricted`.
- `--no-pdf` — skip PDF + Preview open

Beat sequence (from style guide): Headline → Dek → Challenge → Why Zerg → Approach → Solution → Results → Quote → What's next → CTA.

Writes:
- `~/Obsidian/Zerg/MattZerg/CaseStudies/<client-slug>/<project-slug>.md` — durable draft
- `~/Obsidian/Zerg/MattZerg/CaseStudies/<client-slug>/<project-slug>.checklist.md` — pre-publish gates auto-filled

### review — audit a draft against the corpus + style guide

```bash
python3 ~/.claude/skills/case-study-skill/run.py review <draft.md> [<more.md>...] [flags]
```

Flags:
- `--out-dir DIR` — default: `/tmp/case-study/`
- `--model MODEL` — default: `claude-opus-4-7`
- `--no-pdf` — skip PDF + Preview open
- `--quick` — drop the corpus from anchors (style guide only)

Per draft, writes:
- `<draft>.review.md` — annotated review with HIGH/MEDIUM/LOW findings, each citing a `case_study_style.md` rule + a corpus exemplar where relevant
- `<draft>.interview.md` — LOW-confidence items routed for live discussion (only if any exist)

Plus a session-level `session-summary.md`.

## Output register

**Professional/technical/structured, NOT Matt-voice cosplay.** Findings cite:
- **Rule:** which line/section of `case_study_style.md` (or the AI Cleanup checklist where applicable)
- **Corpus exemplar:** which company in the 12-post corpus does this well (or demonstrates the anti-pattern)
- **Confidence:** HIGH / MEDIUM / LOW (review mode only)
- **Suggestion:** rewrite OR scaffold beat OR question

## Anti-fabrication guardrails (load-bearing)

These are the hard rules baked into every prompt:

- **Cite or omit.** Every metric, name, and quote must reference a path/URL from the brief's `evidence_links[]`. No citation → drop the claim.
- **No round numbers** (50%, 100%, 10×) unless verbatim in the source.
- **Quotes must be verbatim** from `candidate_quotes[]`. Paraphrase = drop + interview.
- **No first-person.** Case studies are third-person narratives; `we`/`our` is forbidden outside quoted text.
- **Named attribution only.** "The team" / "the client" — must be a named human or omit.

## NDA gate

Three states in brief frontmatter, enforced by `scaffold`:
- `unknown` (default after capture) — `scaffold` warns + requires `--cleared-for-publication` flag
- `cleared` — scaffold proceeds normally
- `restricted` — `scaffold` hard-refuses regardless of flags; must be flipped manually in the brief

Defense / aerospace / hardware clients (CesiumAstro, Andesite, Apple) default `unknown` until proven otherwise. Andesite's metamorph codebase is explicitly under NDA — that brief should be marked `restricted`.

When `--cleared-for-publication` is used, scaffold logs override metadata into the case study frontmatter so the audit trail exists.

## Anchors loaded each run

1. `~/Obsidian/Zerg/MattZerg/_style/case_study_style.md` — primary genre guide (default shape, voice rules, anti-patterns, pre-publish gates)
2. `~/Obsidian/Zerg/MattZerg/_style/writing_style.md` — sentence-level voice (loaded for context; copyedit-skill is the primary catcher)
3. `~/.claude/skills/case-study-skill/corpus/case-study-corpus.md` — 12-exemplar analysis (skipped with `--quick`)

## Publish workflow (staged trust)

Case studies follow the same approval cadence as blog posts: heavy review at first, autonomy earned over time. The skill writes drafts to the vault. Publishing to `~/zerg/web/` is **not** automated in MVP — Matt or Idan moves cleared drafts to the marketing site repo manually, mirroring the existing thought-piece publication process. A `publish` subcommand may be added in v2 once the skill earns trust on three pilots (Durable → CesiumAstro → Andesite).

## What this skill is NOT

- Not a sentence-level copyeditor — that's `fakematt-copyedit`. Run both: this for genre/structure, copyedit for voice.
- Not a publisher — doesn't push to the Zerg site repo (manual operation, mirrors blog flow).
- Not a hero-image generator — that's `blog-imagery`.
- Not a launch announcement — that's `launch-announcement`. Different genre, different shape.
- Not a backfill for Matt's pre-Zerg work — Vang, Dinari, Touch Surgery belong in personal portfolio, not Zerg case studies.

## Safety

- **Never auto-posts.** Writes to disk only.
- **Doesn't modify source briefs or drafts.** Reviews land in separate files; scaffolds get a fresh path.
- **Hard NDA refuse.** `nda_status: restricted` blocks scaffold regardless of flags.
- **No memory writes.** Reads anchors; doesn't write to memory.
