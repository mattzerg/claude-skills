---
name: content-distribution
description: Generate and track Zerg content distribution CHECKLISTS across launch and social surfaces. Sub-tool under zpub — for "content status" / pipeline-state questions use `zpub all` (hard rule 13); for the actual platform drafts use the social-distribution agent.
allowed-tools: Bash, Read, Write
---


# Content Distribution Skill

Plan: `~/.claude/plans/i-am-planning-growth-splendid-bee.md`. The hard rule: every blog publish triggers a **17-surface** checklist that won't close until done (was 14; grew to 17 on 2026-05-27 after Gigacontext post-mortem — see `MattZerg/_style/launch_distribution_playbook.md`).

## Verbs

### `generate <slug>` — render the 17-surface distribution.md

```bash
python3 ~/.claude/skills/content-distribution/run.py generate <slug> [--cards]
```

Reads `Growth/launches/<slug>/announcement.md` + `Growth/launches/<slug>.md` + `Growth/measurement/<slug>.yaml` (utm_allowlist). Writes `Growth/launches/<slug>/distribution.md` with per-surface copy + UTM-tagged links. With `--cards`, also files a Zergboard card per surface. Refuses to write if any surface's UTM tuple violates `utm_allowlist` (exit 3).

### `cards <slug>` — create Zergboard cards for an existing distribution

```bash
python3 ~/.claude/skills/content-distribution/run.py cards <slug>
```

### `list` — print the 17 canonical surfaces + example UTM

```bash
python3 ~/.claude/skills/content-distribution/run.py list
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
15. **Quote engineering (PRE-LAUNCH)** — 1–3 quotes from ≥5k-follower people locked into the post or share assets, with reposter DMs pre-drafted. Hard rule from memory `feedback_x_audience_too_small_engineer_quotes.md`. → `<slug>.quote-engineering.md`
16. **Waitlist-share CTA** — if the product has a waitlist or free-credit tier, the share-to-move-up line is present in the post and all variants. Hard rule from memory `feedback_waitlist_share_to_move_up_mechanic.md`. → `<slug>.waitlist-share-cta.md`
17. **Quote-post wave plan (Day-2)** — named: who quote-posts on Day-2 if Day-1 engagement clears threshold (LinkedIn ≥10 reactions in 4h), and what one sentence of POV each adds. NOT a plain repost — quote-posts compound. → `<slug>.quote-post-wave.md`

## Zergboard checklist card

Files a Zergboard card on the Marketing or Website board with:
- Title: `[Distribution] <post-title>`
- Body: 17-item checklist with link to each draft file
- Refuses to close until every checkbox is marked

## Post-launch cadence (NEW 2026-05-27)

Beyond surface generation, this skill is responsible for scheduling the post-launch operating cadence per `MattZerg/_style/launch_distribution_playbook.md`:

| When | Action |
|---|---|
| T+0 publish | Fire DMs to quoted people; internal Slack amp; LinkedIn first-comment + Matt repost + Idan repost |
| T+0 +4h | Check Day-1 engagement; if LinkedIn ≥10 reactions → trigger Day-2 quote-post wave |
| T+1 | Pull Zerglytics + X + LI metrics into a status update (Matt-facing, not auto-Slacked) |
| T+3 | 72h analytics pull; HN / Reddit / niche-community drop decision |
| T+7 | 7-day analytics pull; post-mortem note if flagship |
| T+30 | If top-5 referral driver → evergreen variants (video, newsletter inclusion, sales-deck slide) |

The cadence runs **whether or not Matt feels ready to read the numbers** — same forcing-function logic as `growth-dashboard` skill.

The skill itself doesn't enforce closure (that's Zergboard's contract) but the dashboard line #8 reads card completion to track distribution coverage.

## UTM hard-fail

Every external link in every variant draft MUST route through `utm-attribution` with `utm_campaign=<campaign-slug>` and `utm_content=<surface>`. Build-time validator refuses to write a draft that contains a raw `zergai.com` link.

## Voice + style

Each variant invokes `fakematt-copyedit` in review mode against `MattZerg/_style/writing_style.md` voice fingerprint before writing the draft. Threads obey "no double-posting" rule (per memory `feedback_fakematt_no_double_post.md`); LinkedIn follows "blog→social quote reuse" rule (per memory `feedback_blog_to_social_quote_reuse.md` — verbatim quote max twice per thread).

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
