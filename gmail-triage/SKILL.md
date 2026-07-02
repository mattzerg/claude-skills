---
name: gmail-triage
description: Run a triage pass over the Gmail inbox — classify threads into HUMAN-IN / MINE-OUT / DEAL / PROJECT / RECEIPT / KILL buckets, archive kill-list candidates, surface time-bound deals + follow-ups + Tier A/B human replies into morning-brief digests. Reads `~/.claude/skills/fakematt-email/tier_map.json` for tier classification + `MattZerg/_agent_memory/feedback_email_kill_list.md` for archive rules + `feedback_email_deal_watchlist.md` for deal thresholds + `feedback_email_human_tier_overrides.md` for tier promotions. Wraps `gmail-skill` for transport. Never auto-replies — drafts only, gated by `send-gate`. USE PROACTIVELY when Matt asks "triage my inbox", "what's in my inbox", "any new humans waiting on me", "any good flight deals", or before standup / morning-brief.
---

# gmail-triage

## What this skill does

Walks the Gmail inbox, classifies every thread, and produces three digests + one decision artifact:

| Output | Goes to |
|---|---|
| `humans_awaiting_reply.md` | morning-brief, FakeMatt Slack DM |
| `my_follow_ups.md` | morning-brief, `MattZerg/Tasks/inbox.md` |
| `actions_and_deals.md` | morning-brief, FakeMatt Slack DM, `zpub` queue |
| `kill_log.jsonl` | append-only audit of what got archived |

## Verbs

- `triage` — full pass over the entire inbox
- `triage --since 24h` — incremental (last 24h only) — this is the LaunchAgent default
- `digest humans` — produce only `humans_awaiting_reply.md`
- `digest follow-ups` — produce only `my_follow_ups.md`
- `digest deals` — produce only `actions_and_deals.md`
- `apply-kill-list <path>` — given a kill_list_ids.txt, archive each via gmail-skill
- `learn` — fold new senders observed today into the kill-list / deal-watchlist (Matt confirms before write)

## Inputs

1. **Tier map** — `~/.claude/skills/fakematt-email/tier_map.json` (canonical)
2. **Tier overrides** — `MattZerg/_agent_memory/feedback_email_human_tier_overrides.md`
3. **Kill-list** — `MattZerg/_agent_memory/feedback_email_kill_list.md`
4. **Deal-watchlist** — `MattZerg/_agent_memory/feedback_email_deal_watchlist.md`
5. **Curated CRM** — `MattZerg/People/` (~30 tier-1 files, names → email if missing from tier_map)

## Classification rules (in order)

For each unread inbox thread:
1. If sender in `_excluded` (family) → keep, do nothing.
2. If sender in tier_map A/B → bucket **HUMAN-IN**, label `Email/Action`, star.
3. If thread has Matt-sent message and no reply ≥5d → bucket **MINE-OUT**, label `Email/Soon`.
4. If sender matches kill-list rules → bucket **KILL**, append to kill_log, archive.
5. If sender matches receipt rules (Uber/Gopuff/Amazon orders, Apple/PayPal/Anthropic/Stripe receipts) → bucket **RECEIPT**, label `Finance/Business/Money/Purchases`, archive.
6. If sender on deal-watchlist AND snippet hits the deal threshold → bucket **DEAL**, label `Coupons`, surface in `actions_and_deals.md` with extracted expiry.
7. If subject contains `action required`, `final reminder`, `expires`, `due` → bucket **PROJECT**, label `Email/Action`.
8. Otherwise → bucket **KEEP_INBOX**, leave alone.

## Never
- Auto-reply or auto-send anything.
- Archive a thread from a Tier A/B contact without Matt's explicit confirmation.
- Modify `tier_map.json` directly — go through `feedback_email_human_tier_overrides.md` + `promote.py`.
- Apply a Gmail filter via API without Matt approving the filter manifest.

## Output paths

- Per-run dir: `~/Downloads/email_triage_<date>/`
- Memory file updates: `MattZerg/_agent_memory/feedback_email_*.md`
- Optional Slack DM via FakeMatt for high-signal items.

## Status

**v1 — runner shipped 2026-06-01.** `gmail_triage.py` is live with 11/11 classifier fixtures passing. LaunchAgent ready at `~/Library/LaunchAgents/com.matteisn.gmail-triage-daily.plist` (07:00 PT daily); bootstrap once Matt approves with `launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.matteisn.gmail-triage-daily.plist`. Runs in dry-run mode by default; add `--apply` to actually archive KILL threads. Requires gmail-skill CLI deps installed first (`pip3 install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client requests` + browser re-auth for `gmail.modify` scope).

## Future (Phase B build)

- `gmail_triage.py` — Python runner that calls `gmail-skill list` / `search` + applies classification rules.
- LaunchAgent `com.matteisn.gmail-triage-daily.plist` at 07:00 PT → folds into morning-brief.
- `deal-watch` sub-mode → PushNotification on flight deals.
- `follow-up-prompter` → cross-link with `~/.config/zerg/inbox_triage.py` to surface Matt-sent silent threads into `Tasks/inbox.md`.
- `workstreams.yaml` integration — add `email` lane (`digests`, `follow-ups`, `deals`) for RAYG.
