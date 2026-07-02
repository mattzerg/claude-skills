---
name: launch-campaign
description: Plan and track product-launch campaigns across Product Hunt, Hacker News, AI product directories, SaaS startup directories, dev communities, and newsletters. Sibling to launch-ops (operational/ownership layer) and content-distribution (post-publish blog distribution). This one owns the CHANNEL MATRIX for product launches — which surfaces to hit, in what order, with what lead time, and how to track per-channel status. Pairs with launch-announcement (which produces the canonical announcement post). Reads the canonical channel registry at `~/.claude/skills/launch-campaign/channels.md`. USE PROACTIVELY when Matt mentions Product Hunt, HN launch, AI directory submission, BetaList, "launch campaign", "where else should we post", or before any product launch ships.
---

# Launch Campaign Skill

Owns the **WHERE** layer of a product launch. Sibling to:

- **`launch-ops`** — owns WHO/WHEN (operational state, owners, dependencies, day-of runbook)
- **`launch-announcement`** — owns the canonical announcement POST (blog-shape, structural review, scaffold)
- **`content-distribution`** — owns the post-publish 14-surface fanout for any blog (not launch-specific)
- **`launch-campaign`** — owns the cross-surface CHANNEL MATRIX for product launches (Product Hunt, HN, AI directories, SaaS directories, communities, newsletters)

Don't duplicate launch-ops or content-distribution. This skill answers: "where do we submit, when, with what copy, who owns it, what's the status."

## Channel registry

Canonical source: `~/.claude/skills/launch-campaign/channels.md`. Six tiers:

1. **Coordinated launch day** — Product Hunt, Hacker News, Twitter/X (company + personal + Idan repost), LinkedIn (company + personal + Idan repost)
2. **AI product directories** — There's An AI For That, Future Tools, Futurepedia, AI Tool Hunt, Toolify
3. **SaaS / startup directories** — BetaList, Launching Next, AlternativeTo, G2, Capterra
4. **Communities** — Indie Hackers, r/SaaS, r/sideproject, r/programming, Designer News, Dev.to, Hashnode
5. **Newsletters** — TLDR, Pragmatic Engineer, Bytes.dev, Console, TLDR AI
6. **Category-specific** — Latent Space, AI Engineer community, LangChain, MCP-aware spaces

## When to invoke

- Matt mentions Product Hunt / HN / launch campaign / "where else should we post" / AI directory submission
- Before any product launch ships (T-14 minimum to hit BetaList lead times)
- After a launch announcement post is drafted, before it's published

## Verbs

### `generate <slug>` — render per-tier copy variants

```bash
python3 ~/.claude/skills/launch-campaign/run.py generate <slug> [--cards]
```

Reads `Growth/launches/<slug>.md` + `Growth/launches/<slug>/announcement.md` + `channels.md`. Writes `Growth/launches/<slug>/campaign.md` with PH/HN/AI-dirs/SaaS-dirs/communities/newsletters copy + a T+0/+1/+3/+7 cadence section. With `--cards`, also files Zergboard cards for each tier×channel pair.

### `list` — print tier registry

```bash
python3 ~/.claude/skills/launch-campaign/run.py list
```

Dumps the six-tier channel taxonomy from `channels.md` to stdout, for inspection during planning.

## Anti-drift contract

- **Never auto-submit.** Plans are drafts; humans submit. Refuses any auto-post / auto-submission attempt.
- **Cite channel-registry source.** Per-channel claims (lead time, format, audience size) trace back to channels.md so they can be updated when channels change.
- **Verify before submit.** AI-directory market churns fast — channels.md flags every entry with `verify_before_submit: true|false`. Plans surface this so the owner pre-checks the URL works before relying on it.
- **Don't claim a channel that's roadmapped or paid-only as free.** Channels.md tracks `pricing` field (free, freemium, paid). Plans must label paid placements clearly.
- **Cadence rule.** Per `feedback_publishing_cadence.md` — plans default to 1 release per week, never two pieces day-after-day. The campaign WINDOW (multiple channels lighting up day-of) is fine; the LAUNCH WINDOW (releasing two pieces close together) is not.

## Pairs with

- `launch-announcement` — produces the post the campaign distributes. Run announcement first.
- `launch-ops` — owns the operational fire plan. Campaign feeds channel sequence into launch-ops.
- `fakematt-email` / `fakematt-copyedit` — voice-check per-channel copy variants before submission.
- `utm-attribution` — every link in the campaign must be UTM-instrumented. Campaign plan refuses to ship raw links.
- `content-distribution` — fires after the launch lands, owns the 14-surface blog fanout. Don't duplicate channels here.
