---
name: reddit-skill
description: Read and post on Reddit via a Playwright-driven logged-in browser session. Use when the user asks to browse a subreddit, search Reddit, read a post + comments, submit a post, comment on a post, or check who's logged in. Replaces the deprecated Reddit-API-backed skill (Reddit API gated for non-enterprise 2026-05-09). Supports multiple accounts via per-account persistent Chromium contexts. Hard-requires utm-attribution on every outbound link.
allowed-tools: Bash, Read
---


# Reddit Skill — Playwright Edition

Drive a real, logged-in Chromium session to read and post on Reddit. The official Reddit API is gated for non-enterprise access (confirmed 2026-05-09), so this skill automates the web UI through a persistent Playwright context per account.

This is a sibling of `twitter-skill`, `linkedin-skill`, and `slack-skill` — same channel-skill conventions: subcommand verbs, JSON output, account abstraction, hard-required confirmation before any write.

## CRITICAL: Posting Confirmation Required

Before submitting a post or comment, you MUST get explicit user confirmation. Show:
- Account (Reddit username)
- Subreddit
- Title (for posts)
- Body / comment text (full)
- Any links — already routed through `utm-attribution` (see below)

Wait for an explicit "yes / post it / go ahead" before invoking the write verb. Read verbs (`subreddit`, `search`, `me`) do not require confirmation.

## CRITICAL: All Outbound Links MUST Be UTM-Attributed

Every URL that appears in a Reddit post body, comment body, or as the URL of a link post MUST be routed through `utm-attribution` first. The skill refuses to submit any text containing a Zerg-domain URL without UTM params (`utm_source=reddit`, `utm_medium=community`, `utm_campaign=<kebab>`). Non-Zerg links pass through unchanged.

If you need to post a Zerg link, build it first:

```bash
python3 ~/.claude/skills/utm-attribution/run.py build \
  --destination https://zergai.com/zergboard \
  --source reddit --medium community \
  --campaign <campaign-slug> --content <kebab-context>
```

Then paste the resulting URL into the `--body` / `--url` flag.

## First-Time Setup

```bash
pip install playwright
playwright install chromium
```

Then authenticate the first account (opens a visible Chromium window — log in by hand once):

```bash
python3 ~/.claude/skills/reddit-skill/reddit_skill.py login --account matteisn
```

The session (cookies + localStorage) is saved to `~/.claude/skills/reddit-skill/state/<account>/storage_state.json`. Future runs reuse it headlessly.

## Account Management

Accounts are folders under `state/`. Each account has:
- `storage_state.json` — Playwright storage state (cookies, localStorage)
- `meta.json` — username, last-login timestamp, label

No real credentials are ever stored. Login happens through the visible browser window — the same way Matt logs in personally — and only the resulting session state is persisted.

`config.json` (optional) lists declared accounts. It does NOT hold credentials — only labels and Keychain references for tying account labels to Matt's password manager out-of-band.

```bash
# List authenticated accounts
python3 ~/.claude/skills/reddit-skill/reddit_skill.py accounts

# Add / re-auth an account (opens visible browser)
python3 ~/.claude/skills/reddit-skill/reddit_skill.py login --account <label>

# Remove an account's session (deletes state/<label>/)
python3 ~/.claude/skills/reddit-skill/reddit_skill.py logout --account <label>
```

## Verb Surface (v1)

```bash
# Identity
python3 reddit_skill.py accounts                                # list accounts + session staleness
python3 reddit_skill.py me [--account L]                         # current user (from /api/me.json via UI session)
python3 reddit_skill.py login [--account L]                      # opens visible browser for manual login

# Read
python3 reddit_skill.py subreddit NAME [--sort hot|new|top|rising] [--limit N] [--account L]
python3 reddit_skill.py search QUERY [--subreddit NAME] [--limit N] [--account L]

# Write (CONFIRMATION REQUIRED)
python3 reddit_skill.py post SUBREDDIT --title "..." [--body "..."|--url "..."] [--account L]
python3 reddit_skill.py comment POST_URL --body "..." [--account L]
```

All commands print JSON. Errors use the channel-skill envelope:

```json
{"ok": false, "error": "no_session", "message": "No saved session for account 'matteisn'. Run: reddit_skill.py login --account matteisn"}
```

## First-Run UX (no state)

If Matt runs `accounts` on a fresh install:

```json
{"ok": true, "accounts": [], "note": "No accounts authenticated. Run: reddit_skill.py login --account <label>"}
```

If Matt runs `me` / `subreddit` / `search` / `post` / `comment` with no account state:

```json
{"ok": false, "error": "no_session", "message": "No saved session. Run: reddit_skill.py login --account <label> first."}
```

The skill never auto-opens a browser or attempts a login flow unless the explicit `login` verb is invoked.

## How Login Works (Manual, Visible, One-Time)

1. `login --account matteisn` launches Chromium with `headless=False`.
2. It navigates to `https://www.reddit.com/login/`.
3. Matt logs in by hand (including 2FA / passkey).
4. The script polls every 2s for the post-login redirect (URL no longer contains `/login`).
5. Once detected, it calls `context.storage_state(path=...)` and exits.
6. Future verbs reuse the saved state — no further UI.

## How Reads Work

The skill loads the persisted context, navigates to the relevant URL, and parses the rendered HTML (Reddit ships a JSON-LD-ish structure inside the page). For subreddit listing and search, it scrapes the post grid. For `me`, it hits `https://www.reddit.com/api/me.json` from inside the authenticated context — this still works for logged-in sessions because it rides the session cookie, not an API key.

## How Writes Work

The skill navigates to:
- `https://www.reddit.com/r/<sub>/submit` for posts (text or link)
- The target post URL for comments

It fills the title/body/URL fields via the Reddit web UI's form selectors, then clicks Submit. Selectors live in `selectors.json` in the skill directory so they can be updated when Reddit redesigns without code changes.

## Output Format

All commands print a single JSON object to stdout:

```json
{"ok": true, "verb": "subreddit", "account": "matteisn", "data": {...}}
```

Errors:

```json
{"ok": false, "verb": "post", "error": "missing_utm", "message": "Zerg URL detected without utm_source — route through utm-attribution first."}
```

## Selectors (Drift Resilience)

`~/.claude/skills/reddit-skill/selectors.json` is the single source of truth for Reddit's DOM hooks. When Reddit ships a UI change and the skill breaks, edit this file — don't edit the .py.

## Security Notes

- Sessions in `state/<account>/storage_state.json` ARE auth — keep mode-600.
- Never log session contents.
- Never run `login` headlessly. UI flow only.
- `logout` deletes state — does NOT revoke the Reddit-side session (Matt revokes from Reddit settings if needed).

## Limitations (v1)

- No image/video upload (text + link posts only)
- No vote / save / message-inbox verbs (deferred to v2 if needed)
- No flair selection (Reddit subreddit flair varies wildly — manual for now)
- Single page of search/listing results per call (no auto-pagination)

## Why Playwright, Not API

Reddit's Data API gated non-enterprise OAuth access in their 2026-05-09 policy update. Existing API tokens still work for `identity` + `read` but new app registrations are blocked from `submit` and `vote` without a paid tier. Playwright sidesteps this — it's the same browser session Matt would use manually, just scripted.

This is consistent with how `twitter-skill` would need to evolve if X tightens free-tier write access further.
