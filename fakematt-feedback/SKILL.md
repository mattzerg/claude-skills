---
name: fakematt-feedback
description: Run structured product and UX reviews of URLs, local pages, Figma files, or static mockups with screenshots, a11y checks, and sourced Matt-voice findings. Different from cro-auditor (FUNNEL/CONVERSION-focused for marketing surfaces), webpage-layout (corpus-scored 6-axis grading), and landing-page-skill (GENERATES Zerg pages) — fakematt-feedback is the broad UX walkthrough pass that exercises whole-product flows. USE PROACTIVELY when Matt pastes a URL, Figma link, or screenshot and asks "what do you think", "review this", "tell me what's off", or before any product surface ships. Pairs with fakeidan (Idan-bar second pass) and landing-page-skill (single-page-only deep audit).
allowed-tools: Bash, Read, Write
---


# Fake Matt Feedback Skill

Sibling to `landing-page-skill` (single-page audit) and `competitive-review-skill` (category-level review). This one is the **product feedback** counterpart: walks the whole product, exercises flows, screenshots everything, and writes Matt-voice critique grounded in research.

## Anchors

This skill draws its voice and pattern catalog from:

- **Voice fingerprint (default — structured reviews):** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_considered_voice.md`
- **Voice fingerprint (live dogfood / `--voice fast`):** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_fast_voice.md`
- **Cross-surface voice patterns:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_voice_patterns.md`
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md`
- **Exemplar corpus (product feedback):** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_product_feedback_corpus.md`
- **Domain corpus (UI density):** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/ui_density_feedback_corpus.md`
- **Domain corpus (CRO / conversion):** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/cro_feedback_corpus.md`
- **Catalog patterns to cite by slug** (Section B UI / product design): main-sticking-action, ia-ordering, smart-defaults, ui-weight-vs-importance, blank-canvas-friction, library-recurring
- **Catalog patterns to cite by slug** (Section C Prose / writing): shipped-vs-roadmap-visibility, capability-claim-unverified
- **Catalog patterns to cite by slug** (Section E CRO / marketing): hero-clarity, single-cta, missing-cta, proof-gap

Read these BEFORE producing output. Cite patterns by slug from the catalog.

## Voice mode (`--voice fast|considered`)

This skill exposes a voice axis that controls which Matt-voice fingerprint anchors the critique register:

- **`--voice considered`** (default) — used for structured artifact reviews (the standard fakematt-feedback flow that writes to `MattZerg/Feedback/`, the Slack self-DM digest, anything that becomes a referenceable artifact). Anchored on `matt_considered_voice.md`.
- **`--voice fast`** — used for live dogfood passes where Matt is clicking through a product alongside the model and wants conversational, dive-in observations rather than a structured findings document. Anchored on `matt_fast_voice.md`. Skips vault write + Slack digest by default.

The default remains `--voice considered` for backward-compatible behavior. Mode is documented at the skill prompt layer; the harness loads the SKILL.md as text, so no code change is required to honor the parameter — the model reads the active anchor file when the flag is set.

## When to invoke

- "Run a feedback pass on `<url>`" / "what's wrong with this page" / "review this draft"
- "Audit `<localhost url>`" / "go look at `<fly_app>.fly.dev`"
- "Pretend you're me and tell me what's broken about this Figma file"
- Matt drops a URL or path with no further context — assume he wants the review

When in doubt, suggest running it. Always confirm the flow list before exercising the product.

## Phase flow (with confirmation gates)

1. **input** — resolve target into one of {live URL, local URL, Figma file, static folder/PDF}. Pre-checks (port up, file exists, Figma key valid).
2. **flows** — discover candidate flows. Order: spec-driven (parse `Projects/Zerg-Production/Zstack/<product>.md`) → auto-crawl baseline → free-form pass. **STOP, await confirmation.** User can add/remove.
3. **capture** — for each page + each flow step: full-page screenshot, DOM snapshot, console+network errors, axe-core a11y scan, mobile viewport pass.
4. **critique** — Claude call with two cached prompts (voice + principles). Emit structured findings with `voice_provenance` + `principle_provenance`.
5. **validate** — reject findings missing both provenance fields; flag voice-only as "opinion only".
6. **vault write** — show finding count + severity breakdown, **STOP, await confirmation**, then write to `MattZerg/Feedback/YYYY-MM-DD-<product>.md` with screenshots embedded.
7. **slack draft** — top-5 P0/P1 findings to Fake Matt's self-DM (`D0B109RDJQ6`). Never to a shared channel.

## Default invocation

> **Use `/usr/bin/python3` explicitly** — `python3` resolves to homebrew's 3.14, which lacks `playwright`. The skill needs `playwright` for browser capture.

```bash
/usr/bin/python3 ~/.claude/skills/fakematt-feedback/run.py <target> [flags]
# target = URL | http://localhost:port | figma://<file-key> | /path/to/screenshots
# flags:
#   --session NAME         playwright session for auth-walled targets
#   --max-pages N          default 8; template-aware sampling caps 2 per template
#   --persona ROLE         super-admin | admin | end-user | external-viewer
#   --target-kind KIND     marketing-page | internal-tool | b2b-saas-product | client-deliverable | dashboard
#   --no-confirm           skip gates (for scheduled/loop contexts)
#   --no-vault             skip writing to MattZerg/Feedback/
#   --no-slack             skip self-DM digest
#   --voice fast|considered
#                          which Matt-voice fingerprint to anchor critique register.
#                          default: considered (structured artifact reviews).
#                          fast: live dogfood pass; conversational, skips vault/slack by default.
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

- Vault root: `/Users/mattheweisner/Obsidian/Zerg/MattZerg`
- Self-DM channel: `D0B109RDJQ6` (Fake Matt's bot, per `project_slack_identity.md`)
- **Never** auto-post to shared channels (per `feedback_fakematt_no_autopost.md`)
- Voice corpus loaded from `~/.claude/feedback-corpus/voice/`
- Principles corpus loaded from `~/.claude/feedback-corpus/principles/`

## Graphic / image-asset checks (mandatory at HIGH confidence)

When the target includes any rendered image asset (blog hero, body figure, share variant, annotated screenshot, GIF frame, one-pager PDF page, slide), inspect each PNG/PDF page directly and run the six-rule check from `feedback_graphic_basics.md`. These are HIGH-confidence findings on par with voice anti-patterns in prose:

1. **Edge clip** — any text/badge within 60px of an edge, or any element clipped at the boundary
2. **Top/bottom strip balance** — top and bottom paddings within 1.5× of each other; no continuous empty horizontal strip >150px
3. **Title casing** on titles, section headers, structural labels
4. **Density floor** — ≥4 distinct ideas per body figure; flag minimalist/sparse compositions
5. **Label/connector overlap** — no text sitting on a connector line, on top of another text element, or on top of a UI primitive it labels
6. **Same-image-twice** — body figures must read as visually distinct from hero/share variants; same scene with minor variation = repetitive

Per-finding format: cite `feedback_graphic_basics.md` rule N as the principle, attach the rendered image excerpt or coordinate where the violation lives. Matt has called these out 3× now (AdaExplore body-2 2026-05-04, Zergboard body-2 v1 2026-05-06, Zergboard body-2 v4 2026-05-06) — treat as basic, non-negotiable.

## Requirements

- `pip install playwright pyyaml requests slack_sdk beautifulsoup4 anthropic`
- `playwright install chromium`
- `ANTHROPIC_API_KEY` env var (or `~/.claude/anthropic.json` with `{"api_key": "..."}`) — critique now uses the Anthropic SDK with prompt caching. Falls back to `claude --print` CLI if no key, but caching is lost and we've observed the CLI hang on 40K-char contexts; SDK is strongly preferred.
- `~/.claude/feedback-corpus/voice/fingerprint.md` and `principles/library.md` must exist (run `build_corpus.py` once if not)

## Known limitations

- v1: live URL + auto-crawl only. Local/Figma/static adapters and spec/confirm/free-form flow modes follow.
- Headless by default; pass `--visible` for first-time auth on a session.
- Matt edits to feedback notes are not yet back-fed into the corpus (planned: critique-gym hook).
