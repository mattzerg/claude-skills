# Skill Archive Audit Log

Soft-archived skills via `~/.claude/settings.json :: skills.disabled`. The skill directories at `~/.claude/skills/<name>/` are **unchanged on disk** — only the session-reminder visibility is suppressed. The skill remains explicitly invocable via `Skill(skill="<name>")`.

**Loader reference:** `~/zerg/ztc/src/skills/registry.ts:159-163` (`applyDisabledFilter`).

## Un-archive

To restore a single skill, remove its ID from `skills.disabled` in `~/.claude/settings.json` and start a new session. To restore all 70, set `skills.disabled` to `[]`.

A pre-edit backup of `settings.json` lives at `~/.claude/settings.json.bak.20260529-022909`.

## 2026-05-29 archive — 70 skills

Source: `~/.zerg/effectiveness/skill_fire_rates_latest.csv` (graveyard rows, `fires_in_window=0`). All entries are skills with directories present in `~/.claude/skills/` and were 0-fire over the measurement window.

**Curation rule:** the full graveyard had 135 valid-skill entries. 65 were held visible because they're (a) Codex-mirrored per `MattZerg/_agent_memory/shared/codex-skill-curation.md` and archiving in Claude risks Codex parity drift, (b) heavy agent-dispatch targets (content-production, design-review, launch-pack, marketing-review, launch-readiness, metrics-investigation, prospect-research, social-distribution fan out to them — direct-fire count understates real usage), (c) seasonal / reference-only per the prior `graveyard_candidates_2026-05-28.md` review, or (d) daily-ops entry points (morning-brief, standup, workstreams, zpub, etc.).

### Archived (skills.disabled)

| # | Skill | Bucket |
|---|---|---|
| 1 | alexa-skill | IoT / smart-home (rare) |
| 2 | amazon-skill | shopping (rare) |
| 3 | apple-captures-skill | Mac capture (rare) |
| 4 | bd-tracker | BD tracking (use gtm-hub) |
| 5 | blink-skill | IoT / camera (rare) |
| 6 | brand-guide-creator | brand ops (rare) |
| 7 | brand-illustration | rare image gen |
| 8 | brand-kit-creator | rare brand setup |
| 9 | browser-history-skill | Mac integration (rare) |
| 10 | caption-burn | video caption util |
| 11 | capture-validator | meta utility |
| 12 | cloudflare-skill | infra (rare) |
| 13 | data-product-ui | unused design helper |
| 14 | discord-skill | channel (rare) |
| 15 | document-styling-skill | PDF render (rare direct) |
| 16 | dogfood-walkthrough | meta walkthrough |
| 17 | dreamhost-skill | infra (rare) |
| 18 | eleven-labs-skill | TTS (rare) |
| 19 | experiment-tracker | use gtm-hub |
| 20 | fal-image-skill | image gen (chatgpt-image-skill is primary) |
| 21 | fal-music-skill | music gen (rare) |
| 22 | fal-video-skill | video gen (rare) |
| 23 | figma-skill | design tool (rare) |
| 24 | film-maker-skill | video (use product-launch-video) |
| 25 | fm-corrected | fake-matt variant (unused) |
| 26 | fm-ops | fake-matt variant (unused) |
| 27 | gamma-skill | deck tool (rare) |
| 28 | gif-builder | rare media util |
| 29 | godaddy-skill | registrar (rare) |
| 30 | google-docs-skill | rare direct call |
| 31 | google-sheets-skill | rare direct call |
| 32 | google-slides-skill | rare direct call |
| 33 | growth-dashboard | use gtm-hub |
| 34 | gsc-skill | GSC pulls (rare) |
| 35 | imessage-skill | channel (rare) |
| 36 | instagram-skill | channel (rare) |
| 37 | launch-campaign | use launch-ops + launch-announcement |
| 38 | lifecycle-email | unused per graveyard_candidates curation |
| 39 | linkedin-sales-nav | niche sales tool |
| 40 | namecheap-skill | registrar (rare) |
| 41 | notion-skill | cross-tool (rare) |
| 42 | office-hours | unused calendar helper |
| 43 | process-streamliner | unused ops skill |
| 44 | product-docs-skill | unused docs builder |
| 45 | reddit-skill | channel (rare) |
| 46 | referral-tracker | use gtm-hub |
| 47 | scansnap-bridge | Mac integration (rare) |
| 48 | suno-skill | music gen (rare) |
| 49 | twilio-sms | channel (rare) |
| 50 | ui-designer | unused design helper |
| 51 | ux-flow-mapper | unused design helper |
| 52 | video-editing-director | unused (video-production-planner is primary) |
| 53 | video-production-planner | unused (use product-launch-video) |
| 54 | video-review | unused video helper |
| 55 | video-scriptwriter | unused video helper |
| 56 | video-shot-sequencer | unused video helper |
| 57 | video-storyboarder | unused video helper |
| 58 | webflow-skill | infra (rare) |
| 59 | whatsapp-skill | channel (rare) |
| 60 | wyze-skill | IoT / camera (rare) |
| 61 | youtube-skill | channel (rare) |
| 62 | zergaudience-skill | unused audience tool |
| 63 | zergguard-audit | personal cybersec (on-demand) |
| 64 | zergguard-clipboard-guard | personal cybersec (on-demand) |
| 65 | zergguard-identity | personal cybersec (on-demand) |
| 66 | zergguard-imessage-watch | personal cybersec (on-demand) |
| 67 | zergguard-scam-check | personal cybersec (on-demand) |
| 68 | zergguard-state | personal cybersec (on-demand) |
| 69 | zmail | alt email (use gmail-skill) |
| 70 | zstack-product | bootstrap helper (rare) |

### Held visible (65) — rationale

- **Codex-mirror parity** (per `codex-skill-curation.md`): qa-gate, gcal-skill, linear-skill, zergboard-skill, playwright-skill, skill-editor, github-pr-identity, github-skill, fakematt-email, fakematt-personal, fakematt-operator
- **Agent-dispatch targets** (direct-fire understates usage): blog-imagery, brand-check, case-study-skill, launch-announcement, one-pager-skill, webpage-layout, website-designer, fakematt-feedback, cro-auditor, graphic-layout, landing-page-skill, launch-ops, content-distribution, social-distribution, funnel-analyzer, dashboard-spec, experiment-designer, ship-gate, product-launch-video, product-video-skill, utm-attribution, zerg-prospecting, network-reach, fakematt-launch, review-pack
- **Daily-ops entry points**: morning-brief, standup, workstreams, idea-backlog, zpub, gtm-hub, content-calendar, content-release, triage, llm-feedback, compact-session, crm-bridge
- **Seasonal / reference / cross-model** (per graveyard_candidates curation): flight-skill, swag-design, cv-tailor, callout-recipes, careful, frictionless-setup, codex, codex-usage-router, anthropic-usage-router
- **Primary channel + image-gen + publishing pipeline**: linkedin-skill, twitter-skill, chatgpt-image-skill, nano-banana-pro, email-drip, programmatic-seo, competitive-review-skill
- **Self-discovery / measurement skills**: skill-scout, silo-scan, freeze

## Estimated impact

- **Token savings per session reminder:** ~5–7k tokens (70 skills × ~75–100 tokens average description). Verify with a fresh-session reminder length comparison.
- **Behavior risk:** none for archived skills (callable via explicit `Skill(skill=...)`). No Codex sync impact (skill files unchanged on disk).
- **Reversibility:** per-skill (edit `skills.disabled`).
