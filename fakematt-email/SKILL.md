---
name: fakematt-email
description: Draft or revise professional emails in Matt's voice. Reads recipient address (or context) + your draft (or task description), pulls the right register from `~/Obsidian/Zerg/MattZerg/_style/professional_voice.md` (formal-warm / mid-casual / casual-pro), grounds output in `~/Obsidian/Zerg/MattZerg/_style/professional_voice_corpus.md` (55 real outgoing samples), and emits a Matt-voice draft + register classification + voice-tells used + anti-pattern check. Sibling to `fakematt-copyedit` (prose review) and `fakematt-feedback` (product review). USE PROACTIVELY when Matt asks "draft an email to X", "reply to this for me", "what would I say to Y", or before any external email leaves Matt's hand. Never auto-sends — outputs draft text + creates a Gmail draft only on explicit user confirmation.
allowed-tools: Bash, Read, Write
---

# Fake Matt Email Skill

Sibling to `fakematt-feedback` (product/UX review) and `fakematt-copyedit` (prose review). This one is the **email reply** counterpart: drafts professional emails in Matt's voice, with register-aware tone matching.

## When to invoke

- "Draft an email to [name] about [topic]"
- "Reply to this for me" (paste email or give Gmail message ID)
- "What would I say to [contact] about [situation]"
- Before any external professional email leaves Matt's hand
- When polishing an in-flight Gmail draft

When in doubt, suggest running it before the email goes out.

## Default invocation

```bash
python3 ~/.claude/skills/fakematt-email/run.py [flags]

# flags:
#   --to EMAIL              recipient address (used to look up register)
#   --task "..."            description of what the email should say
#   --revise PATH           path to a draft markdown file to polish
#   --reply-to-id MSGID     Gmail message ID to reply to (auto-loads thread context)
#   --register A|B|C        force a specific register (override tier_map)
#   --out-dir DIR           where to write draft (default: /tmp/fakematt-email/)
#   --create-draft          after generating, create a Gmail draft (still requires
#                           explicit confirm before send — user must approve in Gmail)
```

## Output files (per invocation)

For each draft request:

- **`<timestamp>-to-<recipient>.draft.md`** — the email draft itself, ready to copy-paste
- **`<timestamp>-to-<recipient>.brief.md`** — register classification, voice-tells used, anti-patterns checked, recipient context summary

## Three registers (from `professional_voice.md`)

| Register | Greeting | Sign-off | Body | Default for |
|---|---|---|---|---|
| **A — Formal-Warm** | "Hi [Name]," | "Best, Matthew" | Complete sentences, bullets for asks, sparing exclamations | Accountants, lawyers, fund partners, hiring managers, prospects |
| **B — Mid-Casual** | "Hi [Name]," | "Best, Matthew" or just "Matthew" | Conversational, hedges, "hope all is well!" | Warm peers, ongoing biz relationships |
| **C — Casual-Pro** | "Hey [Name]," or "[Name]," | drops or "Matt" | Looser, smileys :), em-dash asides, "hah", contractions | Close colleagues, peer founders, tenants, met-IRL contacts |

Skill auto-classifies via `tier_map.json` (recipient email → register) with fallback to LLM judgment based on prior-thread tone if recipient is new.

## Anchors used

- `~/Obsidian/Zerg/MattZerg/_style/professional_voice.md` — distilled rules, registers, templates, anti-patterns
- `~/Obsidian/Zerg/MattZerg/_style/professional_voice_corpus.md` — raw outgoing samples (grounding; refreshed weekly)
- `tier_map.json` — recipient → register lookup (auto-populated as new contacts emerge)
- `corrections.md` — diff log of Matt's edits to prior drafts (auto-populated daily)
- **Vault context** — `~/Obsidian/Zerg/MattZerg/People/<name>.md`, `MHE/People/<name>.md`, `Companies/`, `Firms/` files matching the recipient by `email:` frontmatter or filename are automatically injected
- `feedback_email_reply_voice.md` (memory) — catch-up email patterns (calendly fallback)

## Self-improvement loops

1. **Weekly corpus refresh** (Sun 5am, `refresh.py`): pulls last 7 days of new sent mail from both Gmail accounts, appends to corpus.
2. **Daily learning loop** (6am, `learn.py`): finds drafts that have since been sent, diffs against actual sent body, appends material edits to `corrections.md`. Next prompt sees those corrections — voice gets sharper as Matt edits.
3. **Tier-map autocomplete**: when a recipient isn't in `tier_map.json`, the skill emits a `RECOMMEND_TIER` line, which `run.py` parses and persists. After a few months of natural use, the tier map covers everyone Matt actually emails — no manual maintenance.

## Anti-patterns (won't generate)

The skill explicitly avoids these AI-template tells:
- "I hope this email finds you well" (Matt uses "Hope all is well!" with exclamation)
- "Please don't hesitate to reach out" (Matt uses "Let me know if you have any questions")
- Overly formal closers like "Sincerely," "Regards," "Kind regards"
- ALL-CAPS for emphasis (Matt uses *italics*)
- Long preamble before the ask — Matt gets to it in para 1-2

## Refresh

Voice corpus stays current via `refresh.py`:

```bash
python3 ~/.claude/skills/fakematt-email/refresh.py
```

- Pulls last 7 days of sent mail from both accounts (matteisn@gmail.com, matthew@zergai.com)
- Strips quoted threads + signatures
- Appends new outgoing samples to `~/Obsidian/Zerg/MattZerg/_style/professional_voice_corpus.md`
- Recomputes voice fingerprint stats in `~/Obsidian/Zerg/MattZerg/_style/professional_voice.md`

Recommended cron: weekly, Sundays at 4am. Add via `~/.claude/fakematt-today/` cron pattern.

## Hard rules

- **Never auto-sends.** Output is draft text + (optional) Gmail draft creation. User must confirm in Gmail before any send.
- **Never invents recipient context** that isn't in the thread. If the skill needs background it doesn't have, it asks.
- **Never crosses register boundaries** without an explicit `--register` flag. A formal-warm contact gets formal-warm output.
