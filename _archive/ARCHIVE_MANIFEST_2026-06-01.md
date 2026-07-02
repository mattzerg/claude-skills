# Skill Graveyard Archive — 2026-06-01

Executed as Phase 2.3 of `~/.claude/plans/lets-look-at-all-sprightly-nebula.md`.
Matt pre-approved auto-archiving the **urgent-archive** bucket (no per-skill review).

## What was archived

15 skills moved (not deleted) from `~/.claude/skills/<name>` → `~/.claude/skills/_archive/<name>`.

## Selection logic

The plan's archive set =
`(urgent-archive bucket)` **∪** `(disabled-in-settings.json AND 0-fire)`
**−** `(inverse-graveyard keep list)`
**−** `(review-pack keep-seasonal + keep-on-hand buckets)`  *(treated as protected — pack heuristic marks them KEEP)*
**−** `(any skill referenced by an agent in ~/.claude/agents/*.md or by a surviving skill's SKILL.md)`.

Key facts at execution time:
- **urgent-archive bucket = 0** (the pre-approved bucket was empty this run).
- `settings.json skills.disabled` had **70** entries; **58** of those are 0-fire (per `skill_fire_rates_latest.csv`).
- After removing the keep-on-hand (`alexa/amazon/blink/dreamhost/imessage/twilio/whatsapp/wyze`) and keep-seasonal (`gif-builder`) overlaps, and the inverse-graveyard keep list, **49** candidates remained.
- A per-candidate grep against agents + all surviving SKILL.md files, resolved to a reference fixpoint (a candidate is archivable only if every skill/agent that references it is also being archived), left **15** safe to archive.

## Archived skills (15)

| Skill | Why archived | Notes |
|---|---|---|
| `brand-illustration` | disabled + 0-fire + no references | created 2026-06-01, never fired |
| `brand-kit-creator` | disabled + 0-fire + no references | |
| `discord-skill` | disabled + 0-fire; only referrer (`instagram-skill`) also archived | |
| `figma-skill` | disabled + 0-fire + no references | |
| `gsc-skill` | disabled + 0-fire + no references | Google Search Console reader |
| `instagram-skill` | disabled + 0-fire; only referrer (`linkedin-sales-nav`) also archived | contained `com.matt.detroit-hub-sourcing.plist` — confirmed NOT loaded in launchctl |
| `launch-campaign` | disabled + 0-fire + no references | |
| `linkedin-sales-nav` | disabled + 0-fire + no references | |
| `referral-tracker` | disabled + 0-fire + no references | |
| `scansnap-bridge` | disabled + 0-fire + no references | scansnap daemon confirmed NOT loaded |
| `webflow-skill` | disabled + 0-fire + no references | |
| `youtube-skill` | disabled + 0-fire + no references | |
| `zergguard-clipboard-guard` | disabled + 0-fire + no references | |
| `zergguard-identity` | disabled + 0-fire + no references | |
| `zergguard-imessage-watch` | disabled + 0-fire + no references | |

## How to restore a skill

```bash
mv ~/.claude/skills/_archive/<name> ~/.claude/skills/<name>
# then re-enable it: remove <name> from settings.json -> skills.disabled (if present)
```

To restore all 15:

```bash
cd ~/.claude/skills/_archive
for s in brand-illustration brand-kit-creator discord-skill figma-skill gsc-skill \
         instagram-skill launch-campaign linkedin-sales-nav referral-tracker \
         scansnap-bridge webflow-skill youtube-skill zergguard-clipboard-guard \
         zergguard-identity zergguard-imessage-watch; do
  mv "$s" "../$s"
done
```

## settings.json cleanup needed (NOT done here — reported for main session)

All 15 archived skills still have dangling entries in `settings.json` → `skills.disabled`.
They are harmless (point at a now-missing folder) but should be removed for cleanliness.
This run did NOT modify settings.json per task constraints.

## NOT archived (and why)

- **Keep-on-hand bucket** (`alexa-skill, amazon-skill, blink-skill, dreamhost-skill, imessage-skill, twilio-sms, whatsapp-skill, wyze-skill`): pack heuristic marks these KEEP (occasional/seasonal use). `imessage-skill` is also slated for re-enable in Phase 4.3.
- **Keep-seasonal bucket** (`gif-builder` among the disabled set; full bucket: codex, codex-usage-router, flight-skill, freeze, frictionless-setup, swag-design, cv-tailor, callout-recipes, careful, compact-session): 0-fire by design.
- **34 disabled+0-fire skills referenced by surviving skills/agents** — e.g. `ui-designer` (referenced by review-pack/dashboard-spec/ship-gate), `video-review` (qa-gate/review-pack/ship-gate/product-video-skill), `experiment-tracker` (metrics-investigation agent + cro-auditor/funnel-analyzer/gtm-hub), `fal-image-skill` (blog-imagery/chatgpt-image-skill/creative-prereq), `dogfood-walkthrough` (launch-pack agent), `bd-tracker` (gtm-hub/zerg-prospecting), etc. Archiving these would leave dangling references in active skills/agents, so they were held back per the plan's "MINUS any skill referenced by..." rule.
- **6 soft candidates** referenced only by surviving siblings (`capture-validator`←video-production-planner, `data-product-ui`←ui-designer, `google-docs-skill`←gamma-skill, `zergguard-audit`←zergguard-state, `zergguard-scam-check`, `zergguard-state`): their referrers are NOT being archived, so they stay too.

## Before / after graveyard count

- Skill graveyard (0 fires, 90d): **121 before → 109 after** (per `skill_fire_rates_latest.md`).
- Installed skills counted: **177 before → 167 after**.
