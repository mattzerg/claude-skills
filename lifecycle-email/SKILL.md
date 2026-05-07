---
name: lifecycle-email
description: Trigger-based lifecycle email automation for Zerg's Phase 3 retention + expansion motion. Reads Zergalytics events (signup, aha-event, pro-upgrade, bundle-upgrade, 14d-inactive, churn-risk-signal) and dispatches matched campaigns via email-drip skill. Three campaign families — `re-engagement` (14-day-inactive nudges), `churn-save` (downgrade-risk save campaigns), `expansion` (post-Pro nudge to Bundle, post-Bundle nudge to Solutions). Pairs with email-drip (transport) + growth-dashboard (reads outcomes onto line #9). Phase 3 build (Day 91-180) — depends on event-stream maturity that doesn't exist Phase 1. USE PROACTIVELY when Matt mentions retention emails, churn-risk save campaigns, expansion nudges, or "the user did X, send Y."
allowed-tools: Bash, Read, Write
---

# Lifecycle Email Skill (v0 stub — Phase 3 build, depends on Phase 2 event maturity)

Plan: `~/.claude/plans/i-am-planning-growth-splendid-bee.md`. The "automation moves Matt past spot-checking" stage of the email program.

## Status

**v0 stub — not yet implemented.** Phase 3 Day 91–180 build window. Depends on:
- Phase 2 Zergalytics event taxonomy mature (signup, aha-event, pro-upgrade, bundle-upgrade all firing reliably)
- `email-drip` v1 (Resend Phase 2 → ZergMail Phase 3) shipped
- ≥200 active accounts (sample size for trigger-based campaigns)

If those preconditions slip, this skill slips with them.

## Three campaign families

### Re-engagement (14d-inactive)

```bash
python3 ~/.claude/skills/lifecycle-email/run.py reengagement scan
```

For users with `last_active_at` >14 days AND `unsubscribed_at` IS NULL: dispatch one of the re-engagement sequences (`came-back`, `feature-update`, `case-study-relevant`). Branched by user's last-known persona segment.

### Churn-save

```bash
python3 ~/.claude/skills/lifecycle-email/run.py churn-save scan
```

For Pro/Bundle accounts with declining usage signal (e.g., `pro_actions_per_week` dropped >50% W/W for 2+ weeks): trigger one of the save sequences (`founder-personal-email`, `feature-they-haven't-tried`, `office-hours-invite`). Founder-personal-email is highest-trust and most-effective per playbook; use it for highest-value accounts.

### Expansion

```bash
python3 ~/.claude/skills/lifecycle-email/run.py expansion scan
```

For Pro accounts that haven't attached Bundle: post-day-30 nudge with personalized savings calc (uses cost calculator math). For Bundle accounts that hit certain seat-count thresholds (≥25): nudge to Solutions Sprint.

## Schema (per Zergalytics event taxonomy — Phase 2 deliverable)

Required events:
- `signup` `{user_id, signed_up_at, source}`
- `aha_event_<product>` `{user_id, occurred_at, product}`
- `pro_upgrade` `{user_id, upgraded_at, tier}`
- `bundle_upgrade` `{user_id, upgraded_at}`
- `last_active_at` (derived weekly)
- `pro_actions_per_week` (derived weekly, used for churn-risk)
- `unsubscribed_at` `{user_id, unsubscribed_at, scope}`

If any of these aren't reliably firing by Phase 3 Day 91, this skill stays in stub.

## Anti-drift contract

- **Per-user max 1 lifecycle email per 7 days** — prevents spam-cluster
- **Refuses to send** if user is `unsubscribed_at` (any scope)
- **Refuses to send** if user is in active welcome-drip sequence (no overlap)
- **Logs every send** to `Marketing/Email/sent-log.md` (shared with email-drip)
- **Founder-personal-email saves** require Matt's manual approval — skill drafts via fakematt-email, never auto-sends

## Pairs with

- `email-drip` for transport (Phase 2 ESP → Phase 3 ZergMail)
- `growth-dashboard` line #9 (email program health) reads send + open + click stats
- `experiment-tracker` for testing variants of save sequences (these become real A/Bs at scale)
- `fakematt-email` for personal save emails Matt sends himself

## Build phases

- **Phase 3 Day 91–120:** v0 — re-engagement scan + dispatch via email-drip
- **Phase 3 Day 120–150:** v0.1 — churn-save with founder-personal hand-off via fakematt-email
- **Phase 3 Day 150–180:** v0.2 — expansion campaigns (Bundle attach + Solutions upsell)

## What this skill is NOT

- Not a marketing-automation platform (use ConvertKit/Customer.io if that's your shape)
- Not a CDP or event-warehouse (Zergalytics is the event store)
- Not transactional drip (that's `email-drip` Stream A — welcome, trial-day-N, post-Pro onboarding)
- Not broadcast newsletter (that's `email-drip` Stream B — bi-weekly Zerg newsletter)

## Implementation notes

- Polls Zergalytics on cron (hourly during Phase 3 ramp; daily once stable)
- File-based campaign definitions at `Marketing/Email/Lifecycle/<campaign>.yaml`
- Heavy reliance on `email-drip` for transport — no duplication of dispatch logic
- Test mode: `--dry-run` flag prints would-fire matches, doesn't dispatch
