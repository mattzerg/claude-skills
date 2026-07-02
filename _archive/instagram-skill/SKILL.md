---
name: instagram-skill
description: "Read and (eventually) post on Instagram via a Playwright-driven logged-in browser session. Use for scraping a user's follows/saves/explore, reading a profile's posts and bio, drafting captions through the queue, and (after Phase 1) posting feed/story/reel content with hard confirmation gates. Supports multiple accounts via per-account persistent Chromium contexts. Sibling of reddit-skill / twitter-skill / linkedin-skill. Optional second backend — Meta Graph API once a Facebook Page is linked."
allowed-tools: Bash, Read
---


# Instagram Skill — Playwright Edition (v0, scaffolding)

Drive a real, logged-in Chromium session to read and post on Instagram. Instagram's Graph API requires a Business account + Facebook Page link, so v0 uses Playwright. The skill is structured so v1 can swap in the Graph API behind the same verbs once the Business linkage exists.

This is a sibling of `reddit-skill`, `twitter-skill`, `linkedin-skill`, `slack-skill`, and `discord-skill` — same channel-skill conventions: subcommand verbs, JSON output, per-account session abstraction, hard-required confirmation before any write.

**Status:** v0 = bootstrap (login.py, scrape_follows.py). v1 = full verb surface (in design — see plan at `~/.claude/plans/i-want-to-build-jaunty-puzzle.md`).

## CRITICAL: Posting Confirmation Required (v1+)

Before submitting any post / story / reel, you MUST get explicit user confirmation. Show:
- Account (IG handle)
- Surface (feed / story / reel)
- Caption (full)
- Image / video preview path
- Copyright posture (`tagged-story` / `collab-approved` / `original`) — see `MattZerg/Projects/detroit-hub/sources.md`
- Any links — already routed through `utm-attribution`

Wait for an explicit "yes / post it" before invoking the write verb. Read verbs (`me`, `feed`, `saved`, `profile`) do not require confirmation.

## CRITICAL: Copyright Posture Gate (v1+)

The Detroit hub project (and any curation account) MUST attach a `copyright_posture` to every queued item. Feed posts require `collab-approved` or `original`. Stories can use `tagged-story`. Anything else stays in queue. See `MattZerg/Projects/detroit-hub/sources.md` for the full schema.

## CRITICAL: All Outbound Zerg Links MUST Be UTM-Attributed (v1+)

Every Zerg-domain URL in any caption / story / link-in-bio MUST be routed through `utm-attribution` first. Standard channel-skill rule.

## First-Time Setup

```bash
pip install playwright
playwright install chromium
```

Then authenticate the first account (opens a visible Chromium window — log in by hand once):

```bash
/usr/bin/python3 ~/.claude/skills/instagram-skill/login.py --account matteisn
```

The session (cookies + localStorage) is saved to `~/.claude/skills/instagram-skill/state/<account>/storage_state.json`. Future runs reuse it headlessly.

## v0 Bootstrap Verbs (shipped)

| Script | Purpose |
|---|---|
| `login.py --account <label>` | Visible Chromium → manual login → auto-save session on completion. Handles 2FA. |
| `scrape_follows.py --account <label>` | Scrape follows + bios → write seed-corpus.md to `MattZerg/Projects/detroit-hub/`. Music/nightlife filter + Detroit-anchored subset. |

## v1 Verb Surface (planned)

```bash
# Identity
instagram_skill.py accounts                              # list authenticated accounts
instagram_skill.py me [--account L]                      # whoami
instagram_skill.py login [--account L]                   # visible browser login

# Read
instagram_skill.py profile HANDLE [--account L]                              # bio + counts
instagram_skill.py posts HANDLE [--limit N] [--account L]                    # recent posts
instagram_skill.py saved [--folder F] [--limit N] [--account L]              # your saved
instagram_skill.py feed [--limit N] [--account L]                            # your home feed
instagram_skill.py explore [--limit N] [--account L]                         # your explore feed
instagram_skill.py search QUERY [--account L]                                # account search

# Queue / approval (v1 contract — Detroit hub Sunday batch)
instagram_skill.py queue list [--account L]                                  # pending drafts
instagram_skill.py queue show ID [--account L]                               # one draft detail
instagram_skill.py queue approve ID [--account L]                            # approve + schedule
instagram_skill.py queue reject ID --reason "..." [--account L]              # reject
instagram_skill.py queue snooze ID --until DATE [--account L]                # bump later

# Write (CONFIRMATION REQUIRED)
instagram_skill.py post --account L --image PATH --caption "..." [--carousel PATH ...]
instagram_skill.py story --account L --image PATH [--sticker JSON]
instagram_skill.py reel --account L --video PATH --caption "..." [--audio AUDIOREF]
```

## Multi-Account Model

Accounts are folders under `state/`. Each has:
- `storage_state.json` — Playwright cookies + localStorage
- `meta.json` — username, last-login timestamp, label

`--account <label>` selects which session to use. Same skill, many accounts (Matt personal, future Detroit hub branded handle, future Zerg curation accounts).

## Two Backends, One Verb Surface

Both backends behind the same CLI verbs:
- **Playwright backend (v0/v1)** — drives the IG web UI. Works for any account. Slower, more brittle.
- **Graph API backend (v2)** — requires Instagram Business account + Facebook Page link. Faster, official, supports scheduled posts via the publish API. Selected automatically when `graph_api.json` config is present for the account.

## Why Playwright First

- Graph API requires Instagram Business + FB Page (not Matt's personal account today)
- For RESEARCH and scraping (follows, saves, explore), only Playwright works — Graph API doesn't expose other users' content for personal accounts
- The curation hub's source pipeline reads from venue/label IGs Matt doesn't own — Playwright is the only path

Once the Detroit hub launches under a Business account + FB Page, the Graph API backend takes over the WRITE path. Reads still use Playwright (Graph API can't read other accounts).

## Sources

- `~/.claude/skills/reddit-skill/SKILL.md` — closest pattern cousin (Playwright auth + verb surface + write gates)
- `~/.claude/skills/playwright-skill/SKILL.md` — session model
- `~/.claude/skills/linkedin-skill/SKILL.md` — multi-account token convention
- Plan: `~/.claude/plans/i-want-to-build-jaunty-puzzle.md`
- Project home: `MattZerg/Projects/detroit-hub/`

## Security

- Session state files in `state/<account>/storage_state.json` ARE auth. Mode 600.
- Never log session contents.
- Never run `login` headlessly. UI flow only.
- `logout` deletes local state — does NOT revoke IG-side session (revoke via IG settings).
