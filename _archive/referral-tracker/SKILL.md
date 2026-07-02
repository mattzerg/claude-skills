---
name: referral-tracker
description: Track Zerg's two referral programs — Product (in-product invite-a-teammate, K-factor + activation rate of invitees) and Solutions (10% of first engagement to referrer). Reads new Zergalytics events (referral_invite_sent, referral_invite_accepted, referral_invitee_activated) for the product side and the Zergboard Solutions board's `referrer` field for the Solutions side. Calculates K-factor weekly and surfaces it on dashboard line
allowed-tools: Bash, Read, Write
---


# Referral Tracker Skill (v0 stub — Phase 2-3 build, retention-gated for product side)

Plan: `~/.claude/plans/i-am-planning-growth-splendid-bee.md`. Two programs, sequenced.

## Status

**v0 stub — not yet implemented.** Build sequence:
- **Phase 2 Day 31:** Solutions referral fee program launches (exp-018). This skill's `solutions` mode lights up.
- **Week 10 retention check:** if 14d activation curve confirms K-factor would compound, build product invite mechanic (exp-019). This skill's `product` mode lights up.
- **Phase 3:** full mechanic + automation (referral fee auto-card, K-factor on dashboard).

## Two programs

### Program A — Product (Zstack invite-a-teammate, tiered)

**Three-tier structure** (sourced from web3-style micro-referral precedent — `Notes/Apple Notes/notes/b2b-acquisition-via-plume.md`):

| Tier | Trigger | Reward |
|---|---|---|
| 1 | Inviter sends invite + invitee accepts | 1 month Pro free per accepted invite (capped at 6 months total) |
| 2 | Invitee activates (hits aha event within 14d) | Additional $5 swag credit to inviter (small but real) |
| 3 | Workspace bonus: 5+ teammates from same workspace invite | Original inviter gets a 6-month Pro extension (workspace-multiplier kicker) |

Workspace-native, not viral-gimmick.

**Tracking events** (new Zergalytics taxonomy additions):
- `referral_invite_sent` — `{user_id, invite_target_email_hash, sent_at, surface}`
- `referral_invite_accepted` — `{inviter_user_id, invitee_user_id, accepted_at}`
- `referral_invitee_activated` — `{invitee_user_id, activated_at}` (on aha-event)

**K-factor calculation** (weekly): `(invites_sent_per_user × invite_acceptance_rate × invitee_activation_rate)` averaged across active users in the trailing week. Reported on dashboard line #10.

**Build trigger:** week 10 retention data shows >50% of activated users still WAU at day 30. Without that, virality on a leaky bucket = negative-value.

### Program B — Solutions (referral fee, tiered)

**Three-tier structure** (sourced from Dinari/Plume B2B precedent in `Notes/Apple Notes/notes/b2b-acquisition-via-plume.md`):

| Tier | Trigger | Reward | Eligible referrers |
|---|---|---|---|
| 1 (top) | Referral closes a Solutions engagement | 10% of first-engagement fee (e.g., $2,500 on a $25k Sprint), paid on collection | Existing clients + warm network + integration partners |
| 2 (mid) | Referral reaches scoping call (qualified) | $500 Zerg Solutions credit, applied to referrer's future engagement OR transferable | Same |
| 3 (low) | Referral signs up via tracked link, reaches discovery call | Public thanks + $50 swag credit | Anyone |

**Internal-champion expansion** (employee-level incentive, sourced from Dinari Plume note): when the referrer is the **internal-champion at the buyer** (the engineer/operator at the buying company who advocated internally), they ALSO receive a small personal credit on close — $1k of Zergboard Pro for personal use, OR $X/mo for 12 months. Costs Zerg almost nothing; gives the champion a real reason to push internally. Discovery-script flags this beat.

**Tracking** (Zergboard Solutions board):
- Every Solutions card has a `referrer` custom field.
- New stage transition: `referred-by-X` (substage of `inbound`).
- On `closed-won` transition with non-empty `referrer`: auto-file a "Referral fee payable: X% × $Y to Z" card on the Ops board with 30-day due-date.

**Build trigger:** Phase 2 Day 31 (no retention gate).

## Modes

```bash
python3 ~/.claude/skills/referral-tracker/run.py kfactor [--week YYYY-WW]
python3 ~/.claude/skills/referral-tracker/run.py solutions list [--status pending|paid]
python3 ~/.claude/skills/referral-tracker/run.py solutions log <closed-won-card> --referrer <name> --fee-pct 10
python3 ~/.claude/skills/referral-tracker/run.py audit [--days 30]
```

## Pairs with

- `growth-dashboard` (line #10 reads K-factor + Solutions-referrals-received)
- `experiment-tracker` (exp-018 Solutions referral, exp-019 product invite)
- `bd-tracker` (overlap when integration-partner refers Solutions deal)
- `zergboard-skill` (board read/write for Solutions referrer field)

## Build phases

- **Phase 2 Day 31–60:** v0 — `solutions list` + `solutions log` + auto-card-on-closed-won
- **Phase 2 Day 60–90:** v0.1 — `audit` mode (find unpaid referral fees >30d)
- **Phase 3 Day 91+ (if retention confirms):** v1 — `kfactor` mode + product-side event ingestion

## Anti-drift contract

- Solutions referrer field on every Zergboard Solutions card — empty allowed but tracked
- Closed-won with non-empty referrer → auto-card on Ops board within 24h
- Stale-referral-fee alerts via Slack DM (similar to bd-tracker stale check) for unpaid >45d

## Voice / register

Same as `bd-tracker` — operational/transactional output. No upsell language. Referral fee is a real obligation, treated like any other AP item.
