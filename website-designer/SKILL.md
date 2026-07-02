---
name: website-designer
description: Design and critique marketing, personal, and agency websites against references and a static anti-pattern bank (AI-stencil traits, generic hero copy, copycat layouts). Different from webpage-layout (data-driven 6-axis SCORING against a curated corpus) and landing-page-skill (GENERATES Zerg's own marketing pages) — website-designer owns the anti-pattern catalog and the pre-build design pass for personal / agency / fund / marketing sites. USE PROACTIVELY when Matt asks to design, critique, or sanity-check a personal-site, agency-site, fund-site, or marketing landing draft. Pairs with webpage-layout (score it after) and fakematt-feedback (UX walkthrough after).
---


# Website Designer Skill

The point of this skill is to keep Claude from shipping AI-stencil personal websites.

## Anchors

This skill draws its voice and pattern catalog from:

- **Voice fingerprint:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_considered_voice.md`
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md`
- **Domain corpus:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/ui_density_feedback_corpus.md`
- **Catalog patterns to cite by slug** (Section B UI / product design): main-sticking-action, blank-canvas-friction, ia-ordering, smart-defaults
- **Catalog patterns to cite by slug** (Section E CRO / marketing): hero-clarity, missing-cta, cta-promise-must-match-form-shape, triple-cta-dilution, shipped-vs-roadmap-visibility
- **Catalog patterns to cite by slug** (Section F Brand): brand-color-restraint

Read these BEFORE producing output. Cite patterns by slug from the catalog.

The failure mode is concrete and Matt has named it (2026-05-07): I shipped 3 sites I called "pretty" that he rated **1/10** — worse than the bare-bones v1 they replaced. The redesign hit every cliché in the AI-generated personal-site playbook and called it premium.

This skill exists so that **never happens again** without something stopping it.

## When to invoke

- **Before designing anything** new for a personal/agency landing page — run `brief` first. Pulls reference exemplars + design rules + Matt's known-bad anti-patterns into a single brief Claude reads before writing any HTML.
- **After rendering a draft** — run `review` on screenshots (mobile + desktop, full-page) and the live URL. Output is structured findings. **Hard rule: don't push a design without `review` passing.** If output contains any HIGH finding, the design is not ready.
- When Matt says a site looks "off" or "template-y" — `review` will name the offense.

## Modes

### `brief` — pre-design brief

```bash
python3 ~/.claude/skills/website-designer/run.py brief --target <site-name> --persona <persona> [--references <site1,site2>]
```

Persona examples: `personal-operator`, `personal-investor`, `consultancy-firm`, `vc-fund`, `solo-founder-portfolio`, `agency-services`, `executive-bio`.

Output (`/tmp/website-designer/<site>/brief.md`):
- Reference exemplars (3-5 real URLs Matt rates 8+, with what makes each work)
- Anti-patterns to actively avoid (with examples)
- Design constraints derived from persona (typography, color, density, photography)
- Distinctiveness ledger — at least 3 things this site will do that are NOT in the AI personal-site playbook
- Sign-off criteria — "this site is done when..."

### `review` — post-design audit

```bash
python3 ~/.claude/skills/website-designer/run.py review <url-or-localhost> --screenshots <desktop.png>,<mobile.png> [--site-name NAME]
```

Output (`/tmp/website-designer/<site>/review.md`):
- Severity-tagged findings: HIGH (would block ship) / MEDIUM (loose end) / LOW (polish)
- Each finding cites a specific principle in `principles.md` OR an anti-pattern in `anti-patterns.md`
- Concrete fix recipe per finding (not just "improve typography" — actual changes)
- Distinctiveness audit: "name 3 things this site does that 100 other AI-generated personal sites don't"
- Pass/fail signal at the top

## Files

- `principles.md` — design principles (typography, hierarchy, color, density, voice). Reread by `run.py` on every invocation.
- `anti-patterns.md` — the AI-stencil playbook to AVOID. Each entry: pattern name, why it reads as template, the actual cure.
- `corpus/personal-sites.md` — real personal sites Matt rates 8+/10, annotated with what makes each work
- `corpus/agency-sites.md` — agency / consultancy sites Matt rates 8+
- `corpus/fund-sites.md` — VC fund / investor sites Matt rates 8+

## Hard rules

- **Don't claim "pretty"** without running `review` and getting no HIGH findings. The "looks competent at a glance" failure is what created the 1/10 disaster.
- **Don't reuse Inter + Fraunces** as the default typography pairing without explicit reason. It's now a tell of AI-generated.
- **Don't include animated blob art** for "abstract hero accent." It is a 100% AI-stencil signal.
- **Don't include the "stat strip"** of 4 numbers separated by `/` if those numbers haven't earned the room. ("Years operating / acquisitions / investments / programs" is not interesting; one really specific number is.)
- **Don't ship without 3+ distinctive details.** Distinctiveness budget = 3 things this site does that no other auto-generated personal site does. Examples: a custom one-off section structure, hand-set kerning, a non-standard color palette, real photography (not stock + not AI), embedded micro-interactions tied to specific content (not generic hover lifts).
- **Real specificity over generic SaaS structure.** "Currently / Selected operating roles / Testimonials / CTA" IS a stencil. The remedy is finding what's true and unrepeated about THIS person/firm and structuring around that.

## What "good" looks like (corpus seeds)

These are starting reference points. The skill grows as Matt rates more.

**Personal sites (operator/investor/operator-investor):**
- frankchimero.com — designer, custom typography, idiosyncratic structure
- jeremykeith.com / adactio.com — opinionated, density of content, voice
- pieter.com (Pieter Levels) — extreme personality, specific projects with revenue numbers
- jasonsantamaria.com — designer, custom-set type
- robinrendle.com — bold typography, pull quotes that interrupt
- danluu.com — extreme density of content (anti-pattern in some contexts but works for him)
- buildingsf.com — bold scrolling sections
- harshjv.com — premium personal feel without templates
- alvaromontoro.com — distinctive hero treatment

**VC fund sites (Vang Capital reference):**
- benchmark.com — restrained, minimal, partner-driven
- founders.fund — bold typography, narrative hero
- thrive.com — image-led, polished
- a16z.com — content-led not portfolio-led
- spark.capital — restraint over pomp
- generalcatalyst.com — premium without busy

**Consultancy/agency sites (Vang Advisory reference):**
- pentagram.com — case-study-led, premium
- thoughtbot.com — services structure done well
- workandco.com — black-tie agency feel
- pineapple.studio — boutique consultancy
- zone-7.studio — services with character
- highresolution.studio — bold but not templated

## Anti-corpus (what to NOT look like)

- "Personal portfolio template #47" on Webflow / Framer marketplace
- ThemeForest "creative agency 2024" templates
- AI-generated landing page tools' default outputs
- Anything with: animated gradient blobs in hero, 4-stat strip, generic icon grid, "We help with X / Y / Z" services template, glass-morphism cards, the same testimonial-quote-card layout

## Output guidelines

- Findings cite principle/anti-pattern by name (e.g. "Anti-pattern: blob-hero, see anti-patterns.md")
- Fixes are concrete: "Replace blob art with X" not "Improve hero visual"
- Severity is honest: HIGH = "Matt would call this 1/10", MEDIUM = "this looks generic", LOW = "polish"
- Always include a distinctiveness audit — even if everything else is fine, if there's nothing distinctive the site fails

## Pair with

- `fakematt-feedback` — UX/heuristics review (different layer; this skill is about design distinctiveness, not usability)
- `fakeidan` — Idan's review bar (catches different things)
- `graphic-layout` — composition review on screenshots (visual balance; this skill is about whether the whole feels generic)
- All four together = the design review-pack for personal/agency sites
