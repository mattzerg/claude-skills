---
name: content-distribution
description: Enforces Zerg's 14-surface content distribution playbook — given a published blog post file, generates platform variants (Twitter thread, LinkedIn long-form, Idan repost, Reddit, HN submission text, newsletter inclusion drafts, outbound snippet, sales-deck add, internal Slack post, repurpose-to-video brief, webinar topic candidate) and creates a Zergboard "Distribution checklist" card with each draft attached. The card refuses to close until every surface is checked. Hard rule: no blog publishes without this card filed. UTM-instruments every link via utm-attribution. Routes share-card variants through blog-imagery for X/LI dimensions. Pairs with launch-announcement (genre layer) + fakematt-copyedit (sentence layer) — runs AFTER both have passed. USE PROACTIVELY whenever Matt publishes a blog post, ships a launch announcement, or mentions distribution on a piece of content.
allowed-tools: Bash, Read, Write
---

# Content Distribution Skill (v0 stub — Phase 2 build)

Plan: `~/.claude/plans/i-am-planning-growth-splendid-bee.md`. The hard rule: every blog publish triggers a 14-surface checklist that won't close until done.

## Status

**v0 stub — not yet implemented.** Phase 2 Day 31–60 build window.

## Invocation

```bash
python3 ~/.claude/skills/content-distribution/run.py distribute \\
  --post-file ~/zerg/web/src/public/content/blog/<slug>.md \\
  [--campaign-slug <utm-campaign>] [--no-card]
```

## What it produces

For the input blog file:

1. **Twitter/X thread draft** (5–7 tweets) → file at `<slug>.x-thread.md`
2. **LinkedIn long-form draft** (LI-native rewrite, 1200-char opener) → `<slug>.linkedin.md`
3. **Idan repost draft** (boost on LI + X) → `<slug>.idan-repost.md`
4. **Reddit post draft** (per niche sub: r/devops, r/SaaS, r/MachineLearning, r/selfhosted) → `<slug>.reddit-<sub>.md`
5. **HN submission text** (title + first comment) → `<slug>.hn.md`
6. **Newsletter inclusion drafts** (TLDR, Bytes, Console, JS Weekly, Hacker Newsletter, SaaS Weekly — one short pitch each) → `<slug>.newsletters.md`
7. **Slack/Discord community shares** (where Idan/Matt have standing) → `<slug>.communities.md`
8. **Outbound snippet** (2-line cold-email teaser for Solutions outbound) → `<slug>.outbound.md`
9. **Sales-enablement add** (slide content for Solutions discovery deck) → `<slug>.sales-deck.md`
10. **Internal Slack post** (#zerg-internal amplification ask) → `<slug>.internal.md`
11. **Email newsletter inclusion** (next bi-weekly Zerg broadcast) → `<slug>.zerg-newsletter.md`
12. **Repurpose-to-video brief** (if signal strong, hand to `product-video-skill`) → `<slug>.video-brief.md`
13. **Webinar topic candidate** (if 800+ engagement, schedule deep-dive) → `<slug>.webinar.md`
14. **Hero/share-card images** (delegated to `blog-imagery` for X 1200x675 + LI 1200x1200 if not already done) → confirms imagery exists

## Zergboard checklist card

Files a Zergboard card on the Marketing or Website board with:
- Title: `[Distribution] <post-title>`
- Body: 14-item checklist with link to each draft file
- Refuses to close until every checkbox is marked

The skill itself doesn't enforce closure (that's Zergboard's contract) but the dashboard line #8 reads card completion to track distribution coverage.

## UTM hard-fail

Every external link in every variant draft MUST route through `utm-attribution` with `utm_campaign=<campaign-slug>` and `utm_content=<surface>`. Build-time validator refuses to write a draft that contains a raw `zergai.com` link.

## Voice + style

Each variant invokes `fakematt-copyedit` in review mode against `~/Obsidian/Zerg/MattZerg/_style/writing_style.md` voice fingerprint before writing the draft. Threads obey "no double-posting" rule (per memory `feedback_fakematt_no_double_post.md`); LinkedIn follows "blog→social quote reuse" rule (per memory `feedback_blog_to_social_quote_reuse.md` — verbatim quote max twice per thread).

## Build phases

- **Phase 2 Day 31–60:** v0 — generate variants, create Zergboard card
- **Phase 2 Day 60–75:** v0.1 — UTM validator, voice gates
- **Phase 2 Day 75–90:** v1 — `--auto-schedule` for variants that don't need human review (e.g., internal Slack)
- **Phase 3:** v2 — read engagement back from each surface, surface "what worked" to next post's brief

## Pairs with

- `launch-announcement` (runs FIRST — genre review)
- `fakematt-copyedit` (runs SECOND — voice review)
- This skill runs THIRD — distribution prep
- `product-video-skill` for surface 12
- `blog-imagery` for surface 14

## Implementation notes

- Reads via Claude API (similar to `case-study-skill`/`launch-announcement`) for variant generation
- File-based output; lands variant drafts next to the source post
- No external dispatch — all variants are drafts for Matt to manually post (per `feedback_fakematt_no_autopost.md`)
