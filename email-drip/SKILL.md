---
name: email-drip
description: Sequence-based email drip + broadcast newsletter sender for Zerg's email marketing program. Reads YAML campaign files at MattZerg/Marketing/Email/<campaign>.yaml (trigger → delay → template per step) and dispatches via Resend (Phase 2) → ZergMail (Phase 3 when product-ready). Two streams — `lifecycle` (transactional drips: welcome, trial-day-N, "you reached limit", post-Pro) and `broadcast` (bi-weekly newsletter with optional segmentation). UTM-instruments every link via utm-attribution skill (hard-fails on raw links). Logs every send to MattZerg/Marketing/Email/sent-log.md. Phase 1 uses gmail-skill manual sequences for welcome drip — this skill is the Phase 2 upgrade once list ≥200. USE PROACTIVELY when Matt mentions sending a sequence, drip, broadcast, newsletter, or "follow-up email N days after X."
allowed-tools: Bash, Read, Write
---

# Email Drip Skill (v0 stub — Phase 2 build, deferred until list ≥200 + ESP chosen)

Phase 2 deliverable. Plan: `~/.claude/plans/i-am-planning-growth-splendid-bee.md`. Defer trigger: Phase 1 uses `gmail-skill` manual sequences; build this when list size justifies infra.

## Status

**v0 stub — not yet implemented.** Phase 2 Day 31–60 build window.

## Two streams

### Stream A — Lifecycle (transactional, triggered)

Sequences fire on user actions.

```bash
python3 ~/.claude/skills/email-drip/run.py lifecycle send \\
  --user-email <email> --sequence welcome-drip
```

Phase 2 sequences:
- `welcome-drip` — 5 emails over 14 days (already drafted at `Writing/Zergboard Welcome Drip.md`)
- `trial-day-3-nudge` — single email 3 days post-signup if no aha event
- `trial-day-10-conversion` — single push to upgrade as 14-day trial winds down
- `pro-onboarding` — 3-email post-Pro-upgrade sequence

### Stream B — Broadcast (newsletter)

Bi-weekly. ~150 subscribers Phase 1 → grows organically.

```bash
python3 ~/.claude/skills/email-drip/run.py broadcast send \\
  --campaign newsletter-broadcast --content issue-NNN \\
  --segment all  # or zstack-users | solutions-prospects | newsletter-only
```

Each issue is a Markdown file at `MattZerg/Marketing/Email/Newsletters/issue-NNN.md` with frontmatter:
```yaml
---
issue: NNN
subject: <subject>
preview_text: <preheader>
publish_date: YYYY-MM-DD
segment: all | zstack-users | solutions-prospects
---
```

## ESP integration

- **Phase 2 (Day 31–60):** Resend (best dev-DX). API key via Keychain (`~/.config/zerg/load_resend_key.sh` pattern, parallel to ANTHROPIC_API_KEY).
- **Phase 3 (Day 91–180):** migrate to ZergMail when product-ready (dogfood).

## Compliance

- SPF/DKIM/DMARC verified on `zergai.com` (Phase 1 Day 5 — manual prerequisite)
- Subscribe/unsubscribe handled via Resend's built-in or self-hosted endpoint
- Domain warmup before any broadcast >100 recipients
- Refuses to send if `unsubscribed` flag is set on the recipient

## UTM hard-fail

Every link in every email body MUST be routed through `utm-attribution` (campaign + medium=email). Build-time validator scans templates and refuses to send if any raw `zergai.com` link found.

## Output destinations

- Sent emails via ESP API
- Send log: `MattZerg/Marketing/Email/sent-log.md` (date, recipient, sequence, subject, link clicks)
- Dashboard line #9 (email program health) reads from this log

## Build phases

- **Phase 2 Day 31–45:** v0 — Resend integration, lifecycle stream (welcome-drip migration from gmail-skill)
- **Phase 2 Day 45–60:** v0.1 — broadcast stream (newsletter)
- **Phase 2 Day 60–75:** v0.2 — basic segmentation
- **Phase 3 Day 91–180:** v1 — ZergMail migration; trigger automation via `lifecycle-email` skill (sister)

## Implementation notes

- File-based campaigns (YAML); no DB required Phase 2
- List management via Markdown DB `MattZerg/Marketing/Email/list.md` (Phase 2) → graduate to ESP-managed list Phase 3
- Test mode: `--dry-run` flag prints what would send, doesn't dispatch
