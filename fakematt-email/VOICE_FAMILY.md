# Voice Family — architecture overview

A single document describing the four "Fake Matt" voice skills + their shared anchors. Future agents/sessions should read this to get oriented quickly. Lives in `fakematt-email/` because that's the entry-point skill, but covers the whole family.

## The four skills

| Skill | Purpose | Surface | Corpus |
|---|---|---|---|
| `fakematt-email` | Draft/revise professional emails | Outbound to non-family contacts | 55+ samples in `MattZerg/_style/professional_voice_corpus.md`, refreshed weekly |
| `fakematt-personal` | Draft/revise family/close-friend emails | Outbound to EXCLUDED-list contacts | 29 samples in `MattZerg/_style/personal_voice_corpus.md`, refreshed weekly |
| `fakematt-copyedit` | Review prose drafts (blog, thought pieces, social) | Vault writing pipeline | `MattZerg/_style/writing_style.md` + voice fingerprint |
| `fakematt-feedback` | Product/UX critique | External targets (URLs, Figma) | `~/.claude/feedback-corpus/` (262 quotes — separate model) |

## Anchor stack (loaded in order)

All four skills load `MattZerg/_style/voice_universals.md` first as the **shared substrate** — universal anti-patterns, voice tells (e.g. "Hope all is well!", "Let me know if [...]", "got tied up"), sentence-length norms, hedge vocabulary.

Then surface-specific:
- **email** → professional_voice.md + corpus + tier_map + corrections + subject_patterns
- **personal** → personal_voice.md + corpus + corrections + (Register-C section of professional_voice as fallback texture)
- **copyedit** → writing_style.md + AI-cleanup checklist + voice fingerprint
- **feedback** → feedback-corpus voice/principles (independent model, doesn't read voice_universals)

## Auto-routing between email + personal

`fakematt-email` and `fakematt-personal` mutually forward when the recipient doesn't match their domain:

- `fakematt-email --to dean.eisner@gmail.com` → tier_map says EXCLUDED → forwards to `fakematt-personal`
- `fakematt-personal --to bleidel@kbgrp.com` → tier_map says A → forwards to `fakematt-email`

So Matt can call either skill and the right one runs. Tier classification is the source of truth.

## Three self-improvement loops (per email + personal skill)

1. **Weekly refresh** (`refresh.py`) — Sunday cron, pulls last 7 days of sent mail filtered to that skill's domain (pro = non-EXCLUDED, personal = EXCLUDED only), strips quoted threads, appends to corpus.
2. **Daily learn** (`learn.py`) — Daily 6am cron, finds drafts that have since been sent, runs unified diff against actual sent body, ≥2 changed lines → appended to `corrections.md`. Old (>90d) corrections pruned. Next prompt reads corrections as anchor.
3. **Daily smoke test** (`smoke_test.py`) — Daily 7am cron, runs synthetic input, validates non-empty draft + brief + opener + closer. Failure → Slack alert to Fake Matt self-DM (D0B0T0ETDR8).

## Tier-map autocomplete

When a recipient isn't in `tier_map.json`, the LLM emits `RECOMMEND_TIER: A/B/C/EXCLUDED` in the brief; `run.py` parses it and persists to `tier_map.json` with `auto from <ts>` rationale. Map fills itself in over months.

## Vault context injection

`find_vault_context(email)` (in fakematt-email/run.py, imported by fakematt-personal) scans `MHE/People/`, `MattZerg/People/`, `Companies/`, `Firms/` for files whose `email:` frontmatter or filename matches the recipient. Matched file (4KB cap) injected into prompt. Tested working: Brian Leidel, Jelmer, Austin Shea, Dean, Catherine.

## Cron schedule

```
# Sunday refreshes (corpus pull, both skills)
0  5 * * 0  fakematt-email/refresh.py
30 5 * * 0  fakematt-personal/refresh.py

# Daily learn (sent-log diff → corrections)
0  6 * * *  fakematt-email/learn.py
30 6 * * *  fakematt-personal/learn.py

# Daily smoke (synthetic input, alert on failure)
0  7 * * *  fakematt-email/smoke_test.py
15 7 * * *  fakematt-personal/smoke_test.py
```

Crons offset by 30 / 30 / 15 min to avoid Gmail token contention.

## Health check

`python3 ~/.claude/skills/fakematt-email/voice_status.py` — prints a single status snapshot: anchor file ages, corpus sizes + last entry, tier_map counts (A/B/C/auto), sent-log totals + unchecked, corrections entries, log file ages, cron schedule.

Run it manually whenever you want to see if the system is working. Add to a daily Slack post if you want a recurring health beacon.

## File map

```
~/.claude/skills/fakematt-email/
├── SKILL.md          # invocation + tier table
├── run.py            # main: anchors → LLM → draft + brief
├── refresh.py        # weekly corpus refresh
├── learn.py          # daily diff loop
├── smoke_test.py     # daily synthetic check
├── voice_status.py   # one-shot health check
├── VOICE_FAMILY.md   # this file
├── tier_map.json     # recipient → register
├── sent-log.jsonl    # logged drafts (input to learn.py)
├── corrections.md    # diff log (output of learn.py, anchor input next run)
└── logs/             # refresh.log, learn.log, smoke.log

~/.claude/skills/fakematt-personal/
├── SKILL.md
├── run.py
├── refresh.py
├── learn.py
├── smoke_test.py
├── sent-log.jsonl
├── corrections.md
└── logs/

MattZerg/_style/                  (vault)
├── voice_universals.md           # shared substrate (anti-patterns, voice tells, norms)
├── professional_voice.md         # email register guide
├── professional_voice_corpus.md  # 55 raw samples
├── subject_patterns.md           # subject-line catalog
├── personal_voice.md             # personal/family voice guide
├── personal_voice_corpus.md      # 29 raw samples
├── writing_style.md              # blog/prose style
├── case_study_style.md
├── launch_announcement_style.md
└── one_pager_style.md
```

## When you should add to this family

A new "fakematt-*" skill is the right pattern when:
1. The output is something Matt sends/posts in his voice
2. There's a distinct corpus (≥20 samples) with measurable patterns
3. Existing skills don't naturally cover the surface

Bad candidates (don't add):
- Generic chatbot framing ("Matt's responses to anything") — too broad
- Single-shot translation tasks — overkill for a skill
- Internal-only / non-voice content (use a different family)
