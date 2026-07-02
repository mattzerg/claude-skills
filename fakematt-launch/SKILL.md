---
name: fakematt-launch
description: Draft launch CAMPAIGN packages in Matt's voice — campaign asset lists, channel plans, Product Hunt prep, partner rollouts, press kits, coordinated GTM copy. For the launch ANNOUNCEMENT post itself, defer to the `launch-announcement` skill (canonical per CLAUDE.md); this skill covers the surrounding campaign assets.
allowed-tools: Bash, Read, Write
---


# Fake Matt Launch Skill

This skill is the **launch packaging** counterpart to `fakematt-copyedit` and `fakematt-feedback`. It does not just polish a single asset. It turns a product, feature, or campaign into a coordinated launch package in Matt's voice.

## When to invoke

- "Help me launch this"
- "Draft the announcement, one-pager, and social copy"
- "Put together the GTM package for this feature"
- "Write the launch assets for Product Hunt / partners / press"
- When Matt has product context but the launch surface is still fragmented across docs, bullets, screenshots, and half-written posts

Use this before external launches, feature announcements, partner pushes, or any moment when the copy, assets, and distribution plan need to line up.

## What this skill produces

Pick the smallest package that matches the ask. Default outputs:

1. **Launch brief** — audience, problem, wedge, proof, CTA, risks, exclusions
2. **Core copy** — headline/tagline, short description, long description, announcement post, CTA variants
3. **Asset checklist** — screenshots, GIFs, one-pager, logos, proof points, testimonials, FAQs, press-kit gaps
4. **Channel plan** — launch-day sequence and channel-specific adaptation for Product Hunt, X/Twitter, LinkedIn, email, partner outreach, communities

If the user asks for only one asset, do not force the full package. If the launch is fuzzy, start from the brief.

## Output modes

### Mode 1 — Announcement package

Use for feature launches, homepage changes, product releases, Product Hunt, launch posts.

Output:
- launch brief
- primary announcement post
- 3-5 supporting variants
- asset checklist

### Mode 2 — One-pager package

Use for partner conversations, sales enablement, accelerator/client deliverables, launch-adjacent decks.

Output:
- one-pager structure
- headline / subhead
- proof blocks
- objections / FAQ section
- CTA section

### Mode 3 — Rollout plan

Use when the user mostly needs sequencing, ownership, and asset readiness.

Output:
- pre-launch
- day-of-launch
- post-launch
- owner/gap list

## Anchors

- `MattZerg/_style/launch_announcement_style.md`
- `MattZerg/_style/one_pager_style.md`
- `MattZerg/_style/case_study_style.md` when proof/customer framing matters
- `MattZerg/_style/writing_style.md` for prose hygiene
- `references/launch_system_patterns.md` for recurring packaging patterns derived from Matt's product-delivery and marketing planning files
- `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_considered_voice.md` — voice fingerprint for launch prose (launch packaging is the canonical matt_considered surface; load as the voice anchor for headlines / announcement body / FAQ copy)
- `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` — pattern catalog (launch section); cite findings by slug when auditing or producing launch copy
- **Catalog patterns to cite by slug** (Section C Prose / writing): cross-format-repetition, pulp-caption-discipline, punchline-isolation, em-dash-budget
- **Catalog patterns to cite by slug** (Section E CRO / marketing): shipped-vs-roadmap-visibility, single-cta, missing-cta, capability-claim-unverified
- **Catalog patterns to cite by slug** (Section I Launch / deck): deferred-with-reason, one-product-at-a-time

Read only the anchor files you need for the task. Do not load everything by default. Cite launch-section patterns by slug from `feedback_patterns_catalog.md`.

## Working rules

- Start with the **wedge**. Name the specific problem, persona, and why this launch matters now.
- When the artifact is selling **Zerg as a system** rather than a single feature, hold two layers together:
  1. the immediate wedge
  2. the broader promise: custom-tailored systems, lower software cost, shared data infrastructure, AI chat / agent plumbing, and implementation capacity
- Keep **copy and operations tied together**. If the announcement implies proof, screenshots, partner logos, or a FAQ, call out the missing asset rather than hand-waving it.
- Separate **core message** from **channel adaptation**. Write the canonical message once, then adapt it to channel constraints.
- Prefer **proof-rich specificity** over generic launch adjectives.
- Treat launch work as a **package**: message, assets, sequencing, owners, and gaps.
- When product context is weak, produce a **question list** and a provisional brief instead of faking certainty.

## Hard rules

- Do not auto-send, auto-post, or auto-publish anything.
- Do not invent launch proof, customer quotes, metrics, or partner approvals.
- Do not default to generic startup-launch tropes like "we're thrilled" or "game-changing" unless the source material truly earns them.
- If the user already has a draft announcement, use `fakematt-copyedit` for sentence-level review after the package is structured.

## Relationship to sibling skills

- `fakematt-copyedit` — use after the package exists and needs line editing
- `fakematt-feedback` — use when the product or landing page itself needs critique before launch
- `case-study-skill` — use when the output should become a full customer story rather than a launch package
- `landing-page-skill` — use when the launch requires a dedicated page build or page audit
