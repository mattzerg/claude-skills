---
name: utm-attribution
description: Build UTM-instrumented links and validate them against ~/Obsidian/Zerg/MattZerg/Projects/Zstack/Growth/utm-convention.md. Every link Matt or Claude posts to any external surface (Twitter, LinkedIn, Reddit, Gmail, Discord, etc.) MUST be routed through this skill. Channel-skills hard-fail on raw links once this is wired. Logs every generated link to ~/Obsidian/Zerg/MattZerg/Projects/Zstack/Growth/links.md as the canonical UTM ledger. Validates utm_source/utm_medium/utm_campaign against the campaign catalog; rejects raw links and PII-bearing params. USE PROACTIVELY whenever building any external link to a Zerg property — landing page, blog post, Solutions offer, case study, signup CTA. Never pre-shortens (use bit.ly/zergai short links separately if needed).
allowed-tools: Bash, Read, Write
---

# UTM Attribution Skill (v0 stub — Phase 1 Day 5–8 build)

The "without it the dashboard lies" skill. Plan: `~/.claude/plans/i-am-planning-growth-splendid-bee.md`.

## Status

**v0 stub — not yet implemented.** Phase 1 Day 5–8 deliverable. ~100-line skill. The discipline matters more than feature breadth.

## What it does

Builds and validates UTM-instrumented links against the convention at `~/Obsidian/Zerg/MattZerg/Projects/Zstack/Growth/utm-convention.md`.

```bash
python3 ~/.claude/skills/utm-attribution/run.py build \
  --destination https://zergai.com/zergboard \
  --source twitter \
  --medium social \
  --campaign hn-zergboard-launch \
  --content thread-tweet-3
```

Output:
```
https://zergai.com/zergboard?utm_source=twitter&utm_medium=social&utm_campaign=hn-zergboard-launch&utm_content=thread-tweet-3
```

Plus appends a row to `Growth/links.md`:
```
| 2026-05-12 | hn-zergboard-launch | twitter | social | thread-tweet-3 | https://zergai.com/zergboard | <full url> |
```

## Validation rules (hard-fail)

1. Destination must be on `zergai.com` or a Zerg-owned subdomain (zergboard.ai, zerglytics.fly.dev, etc.)
2. `utm_source`, `utm_medium`, `utm_campaign` are REQUIRED — empty values rejected
3. All values lowercase, kebab-case, no spaces, no trailing punctuation
4. `utm_campaign` must match a campaign in the catalog (or `--register-campaign` to add it)
5. No PII in any UTM param (regex check: no `@`, no email-like, no name-pattern)
6. `utm_source` must be one of the allowed values OR pass `--register-source` flag

## Channel-skill integration

Phase 2: each channel skill (twitter-skill, linkedin-skill, reddit-skill, gmail-skill, etc.) imports a tiny validator from this skill. If a posted link points to a Zerg domain and lacks UTM params, the channel skill **hard-fails** with a message:

```
ERROR: link to zergai.com/zergboard is not UTM-instrumented.
       Run: python3 ~/.claude/skills/utm-attribution/run.py build --destination ...
```

This is the anti-drift guardrail. Without enforcement, dashboards lie.

## Modes

- `build` — generate a UTM link
- `validate` — check a link is correctly instrumented (used by channel skills)
- `ledger` — append a manually-built link to `Growth/links.md` (escape hatch)
- `audit` — scan recent posts on Twitter/LinkedIn/Reddit for un-instrumented zergai links (Phase 2)

## Output destinations

- **Stdout**: the UTM link, ready to copy-paste
- **Append**: `~/Obsidian/Zerg/MattZerg/Projects/Zstack/Growth/links.md` (canonical ledger)

## Build phases

- **Phase 1 (Day 5–8):** v0 — `build` + `validate` modes, file-based ledger append
- **Phase 1 (Day 14–22):** v0.1 — channel-skill validator imported
- **Phase 2 (Day 31–60):** v1 — `audit` mode runs weekly via cron, flags un-instrumented posts
- **Phase 2 (Day 60–90):** v1.1 — short-link integration if Matt opts into bit.ly/zergai

## Implementation notes

- Pure Python, no external deps (urllib.parse for URL building)
- Read `Growth/utm-convention.md` for campaign catalog (parse the table)
- Append, don't rewrite, the ledger
- File-based state — no DB
