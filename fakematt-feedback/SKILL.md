---
name: fakematt-feedback
description: Run a structured product/UX review of a target (live URL, localhost, Figma file, or static mockups). Scans pages with template-aware sampling (won't crawl 200 person profiles, just 2 of each template), exercises flows via playwright, captures responsive viewports + axe a11y + console/network errors, then emits findings calibrated to cover what Matt would catch (consistency, IA, responsive, interactions, copy, additive features) — output is professional/technical/structured, NOT a Matt-voice cosplay. Each finding cites a research principle (NN/g, Baymard, Cialdini/Kahneman, Ogilvy/Schwartz, WCAG, etc.); voice citations are coverage-only. Supports `--persona` (super-admin/admin/end-user/external-viewer) and `--target-kind` (marketing-page/internal-tool/b2b-saas-product/client-deliverable/dashboard) so internal tools don't get marketing-CRO critique and admin controls don't get flagged for super-admins. USE PROACTIVELY when Matt asks for a product review, UX audit, design critique, "what's wrong with this page", "go look at <url>", or wants feedback before shipping. Never auto-posts to shared channels — Obsidian note + Fake Matt self-DM only.
allowed-tools: Bash, Read, Write
---

# Fake Matt Feedback Skill

Sibling to `landing-page-skill` (single-page audit) and `competitive-review-skill` (category-level review). This one is the **product feedback** counterpart: walks the whole product, exercises flows, screenshots everything, and writes Matt-voice critique grounded in research.

## When to invoke

- "Run a feedback pass on `<url>`" / "what's wrong with this page" / "review this draft"
- "Audit `<localhost url>`" / "go look at `<fly_app>.fly.dev`"
- "Pretend you're me and tell me what's broken about this Figma file"
- Matt drops a URL or path with no further context — assume he wants the review

When in doubt, suggest running it. Always confirm the flow list before exercising the product.

## Phase flow (with confirmation gates)

1. **input** — resolve target into one of {live URL, local URL, Figma file, static folder/PDF}. Pre-checks (port up, file exists, Figma key valid).
2. **flows** — discover candidate flows. Order: spec-driven (parse `Projects/Zstack/<product>.md`) → auto-crawl baseline → free-form pass. **STOP, await confirmation.** User can add/remove.
3. **capture** — for each page + each flow step: full-page screenshot, DOM snapshot, console+network errors, axe-core a11y scan, mobile viewport pass.
4. **critique** — Claude call with two cached prompts (voice + principles). Emit structured findings with `voice_provenance` + `principle_provenance`.
5. **validate** — reject findings missing both provenance fields; flag voice-only as "opinion only".
6. **vault write** — show finding count + severity breakdown, **STOP, await confirmation**, then write to `MattZerg/Feedback/YYYY-MM-DD-<product>.md` with screenshots embedded.
7. **slack draft** — top-5 P0/P1 findings to Fake Matt's self-DM (`D0B109RDJQ6`). Never to a shared channel.

## Default invocation

```bash
python3 ~/.claude/skills/fakematt-feedback/run.py <target> [flags]
# target = URL | http://localhost:port | figma://<file-key> | /path/to/screenshots
# flags:
#   --session NAME         playwright session for auth-walled targets
#   --max-pages N          default 8; template-aware sampling caps 2 per template
#   --persona ROLE         super-admin | admin | end-user | external-viewer
#   --target-kind KIND     marketing-page | internal-tool | b2b-saas-product | client-deliverable | dashboard
#   --no-confirm           skip gates (for scheduled/loop contexts)
#   --no-vault             skip writing to MattZerg/Feedback/
#   --no-slack             skip self-DM digest
```

For auth-walled internal tools, set up the session once with playwright-skill `--visible`, then pass `--session NAME` on subsequent runs. The skill symlinks to `~/.claude/skills/playwright-skill/sessions/`.

## Output

```
MattZerg/Feedback/
  YYYY-MM-DD-<product>.md           # the review
  _screenshots/<run-id>/             # full-page + per-step PNGs
~/.claude/skills/fakematt-feedback/state/<run-id>/
  insights.json                      # raw capture + findings
  trace.zip                          # playwright trace (optional)
```

Plus a Slack self-DM to `D0B109RDJQ6` with the top 5 findings + Obsidian deep-link.

## Conventions

- Vault root: `/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg`
- Self-DM channel: `D0B109RDJQ6` (Fake Matt's bot, per `project_slack_identity.md`)
- **Never** auto-post to shared channels (per `feedback_fakematt_no_autopost.md`)
- Voice corpus loaded from `~/.claude/feedback-corpus/voice/`
- Principles corpus loaded from `~/.claude/feedback-corpus/principles/`

## Requirements

- `pip install playwright pyyaml requests slack_sdk beautifulsoup4 anthropic`
- `playwright install chromium`
- `ANTHROPIC_API_KEY` env var (or `~/.claude/anthropic.json` with `{"api_key": "..."}`) — critique now uses the Anthropic SDK with prompt caching. Falls back to `claude --print` CLI if no key, but caching is lost and we've observed the CLI hang on 40K-char contexts; SDK is strongly preferred.
- `~/.claude/feedback-corpus/voice/fingerprint.md` and `principles/library.md` must exist (run `build_corpus.py` once if not)

## Known limitations

- v1: live URL + auto-crawl only. Local/Figma/static adapters and spec/confirm/free-form flow modes follow.
- Headless by default; pass `--visible` for first-time auth on a session.
- Matt edits to feedback notes are not yet back-fed into the corpus (planned: critique-gym hook).
