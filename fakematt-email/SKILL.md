---
name: fakematt-email
description: 'Draft or revise professional emails in Matt''s voice with context-aware routing. Reads recipient/context + task/draft, chooses A/B/C register from `professional_voice.md`, distinguishes `matt_personal_professional` vs `matt_zerg_professional` using `fakematt_contexts.md`, grounds output in real outgoing samples, and emits draft + register/context brief. USE PROACTIVELY (mandatory entry-point — do NOT draft directly) when Matt asks any of: "draft an email", "draft a reply", "reply to this", "reply in my voice", "what would I say to X", "respond to this email", "write back to", "send a reply", or before ANY external professional/Zerg email leaves Matt''s hand. Hypothesis 2026-05-28: stronger trigger phrases lift skill invocation in -p mode from 0/5 to ≥1/5 golden cases within 14 days. Never auto-sends.'
allowed-tools: Bash, Read, Write
---


# Fake Matt Email Skill

Sibling to `fakematt-feedback` (product/UX review) and `fakematt-copyedit` (prose review). This one is the **email reply** counterpart: drafts professional emails in Matt's voice, with register-aware tone matching and an identity-context axis.

## ⚠ THE ONE RULE THAT MATTERS

**ALWAYS draft through `run.py`. NEVER compose email text conversationally in-session.**

The CLI is where the voice machinery lives: measured structural priors from 19,000+ real sent emails, verbatim exemplar retrieval, Opus-class drafting, and a deterministic resemblance check. An email drafted "by hand" in the session bypasses ALL of it.

**Task-type exception (2026-06-02, Matt-confirmed 3x):** first-contact vendor RFQs follow the Threadbird template (~150-220 words, bulleted quantities/design/asks, self-intro) — NOT the global short-prose envelope. `run.py` auto-detects this task type (`is_first_contact_rfq`) and swaps both the prompt block and the structural check to the RFQ envelope. The canonical exemplar is sent message `19e88531749c0919` (Threadbird); the canonical rule is `feedback_first_contact_rfq_minimalism.md`. Do not "fix" RFQ drafts by compressing them to short prose — that is the failure mode Matt rejected.

If `run.py` errors, report the error and stop. Do not fall back to drafting conversationally.

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
#   --identity-context auto|matt_personal_professional|matt_zerg_professional
#                           force whether this is Matt personally or Matt at Zerg
#   --out-dir DIR           where to write draft (default: /tmp/fakematt-email/)
#   --create-draft          after generating, create a Gmail draft (still requires
#                           explicit confirm before send — user must approve in Gmail)
#   --model MODEL           Claude model id. When omitted, aitr picks one
#                           (task_kind=draft-prose, quality_floor=high-stakes);
#                           falls back to claude-opus-4-8. Voice drafting NEVER
#                           runs below Opus-class — cheap models produce the
#                           "too clearly AI / too dumb" failure mode.
```

The chosen model and aitr's reason are printed to stderr (`[aitr] fakematt-email: …`).

## How voice works (2026-06-02 architecture — exemplar-first)

Generation is grounded in what Matt's real emails ARE, not in abstracted "voice tells":

1. **Measured structural priors** (`voice_priors.py`, cached in `structural_priors.json`):
   computed over 742 real sent emails 2024–2026 (automated/script mail filtered out).
   Segment-aware: fresh sends median 62 words / p90 339; replies median 30 / p90 101.
   Injected as hard constraints.
2. **Verbatim exemplars** — every draft sees ≥5 real Matt emails: recipient-dyad
   history first, then surface-matched, then task-similarity retrieval (so new
   recipients on novel asks still get grounded).
3. **Composition pass** — the model plans content (recipient needs / single ask /
   what to cut) before drafting. Fixes information-hierarchy quality, not just style.
4. **Deterministic structural check** — post-generation, the draft is measured
   against the priors (length, bullets, self-intro, template openers, headers).
   Violations trigger one auto-revision pass; unresolved violations are flagged
   at the top of the brief.

Rules/patterns are supporting context only. When a rule conflicts with what the
exemplars show, the exemplars win.

## Output files (per invocation)

For each draft request:

- **`<timestamp>-to-<recipient>.draft.md`** — the email draft itself, ready to copy-paste
- **`<timestamp>-to-<recipient>.brief.md`** — content plan, register classification, RESEMBLANCE_CHECK self-report, open questions
- **`<timestamp>-to-<recipient>.trace.md`** — decision trace: register source, recipient memory, structural check verdict

## Three registers (from `professional_voice.md`)

| Register | Greeting | Sign-off | Default for |
|---|---|---|---|
| **A — Formal-Warm** | "Hi [Name]," | "Best, Matthew" | Accountants, lawyers, fund partners, hiring managers, prospects |
| **B — Mid-Casual** | "Hi [Name]," or none | "Best, Matthew", "Thanks, Matt", or just "Matthew" | Warm peers, vendors, ongoing biz relationships |
| **C — Casual-Pro** | "Hey [Name]," or "[Name]," | drops or "Matt" | Close colleagues, peer founders, tenants, met-IRL contacts |

Register controls greeting/closer conventions only. Length, structure, and rhythm
come from the exemplars — a Register A email is still short plain prose, not a
formal structured document.

Skill auto-classifies via `tier_map.json` (recipient email → register) with fallback to LLM judgment based on prior-thread tone if recipient is new.

## Identity contexts

Register controls warmth/formality. Identity context controls which rule stack is active:

| Context | Use when | Extra discipline |
|---|---|---|
| `matt_personal_professional` | Matt writes professionally as himself outside Zerg positioning | Preserve Matt voice; do not apply Zerg public-prose bans mechanically |
| `matt_zerg_professional` | Matt writes as a Zerg operator, Head of Growth, founder proxy, or company representative | Keep Matt voice, plus Zerg claim discipline: no grandiosity, source/soften load-bearing claims, label roadmapped capabilities if forwardable |

Default `auto` treats `matthew@zergai.com`, Zerg topics, or Zerg recipient/context signals as `matt_zerg_professional`; otherwise it uses `matt_personal_professional`.

## Anchors used

- **`raw_outgoing/`** — 19,000+ real sent emails (2015–2026, both accounts), the PRIMARY voice source via exemplar retrieval
- **`voice_priors.py` / `structural_priors.json`** — measured structural envelope (length/bullets/openers/closers distributions)
- `MattZerg/_style/professional_voice.md` — register conventions (greeting/closer per register)
- `MattZerg/_style/fakematt_contexts.md` — identity-context routing and conflict resolution
- `tier_map.json` — recipient → register lookup (auto-populated as new contacts emerge)
- `corrections.md` — diff log of Matt's edits to prior drafts (auto-populated daily)
- **Vault context** — `MattZerg/People/<name>.md`, `MHE/People/<name>.md`, `Companies/`, `Firms/` files matching the recipient by `email:` frontmatter or filename (generic inboxes like support@/info@/hello@ skip the filename fallback)
- `recipient_patterns/` + sent-log history — per-recipient dyad memory

## Self-improvement loops

1. **Weekly corpus refresh** (Sun 5am, `refresh.py`): pulls last 7 days of new sent mail from both Gmail accounts, appends to corpus.
2. **Daily learning loop** (6am, `learn.py`): finds drafts that have since been sent, diffs against actual sent body, appends material edits to `corrections.md`. Next prompt sees those corrections — voice gets sharper as Matt edits.
3. **Tier-map autocomplete**: when a recipient isn't in `tier_map.json`, the skill emits a `RECOMMEND_TIER` line, which `run.py` parses and persists.
4. **Structural priors refresh**: `structural_priors.json` recomputes automatically every 7 days from the raw corpus (`python3 voice_priors.py --recompute` to force).

## Reliability checks

```bash
python3 ~/.claude/skills/fakematt-email/voice_status.py --doctor
python3 ~/.claude/skills/fakematt-email/sent_log_audit.py --days 7
python3 ~/.claude/skills/fakematt-email/smoke_test.py
python3 ~/.claude/skills/fakematt-personal/smoke_test.py
python3 ~/.claude/skills/fakematt-email/regression_check.py
python3 ~/.claude/skills/fakematt-email/voice_priors.py --show          # structural priors
python3 ~/.claude/skills/fakematt-email/voice_priors.py --check FILE    # check any draft
```

The doctor reports skill-copy drift, Claude wrapper/model availability, anchor/corpus freshness, sent-log backlog, LaunchAgent/crontab status, and last refresh/learn/smoke runs.

Use `sent_log_audit.py --days N --apply` to mark stale local-only drafts as `abandoned` after the learning loop has had enough time to match any sent Gmail messages.

## Anti-patterns (structural check rejects these)

These are measured against the real corpus (segment-aware), not asserted as rules:

- **Length beyond the segment p90** (replies: 101 words; fresh sends: 339) — the loudest AI tell is padding
- **Bullet lists in replies** (3.2% real usage; fresh sends are looser at 16%)
- **Self-introduction with role/title** (1.4–5.3% real usage) — the from-address carries identity
- **Section headers / labeled blocks** — emails are not documents
- **Pure AI-template phrases** — "I hope this email finds you well", "Please don't hesitate to reach out", "Sincerely,", "I'm excited to", "I wanted to reach out"

**Exception — first-contact vendor RFQs** (`is_first_contact_rfq` in `voice_priors.py`): the check inverts. Bullets and self-intro are REQUIRED, the envelope is 150-220 words, and missing template beats (quantities lead-in, flex line, punchline, asks lead-in, art-files line) are the violations. See the Threadbird template note at the top of this file.

Note: corpus statistics exclude automated/script-generated mail (Apps Script error
notifications were 55% of the raw corpus before filtering — see `AUTOMATED_RE`).

## Refresh

Voice corpus stays current via `refresh.py`:

```bash
python3 ~/.claude/skills/fakematt-email/refresh.py     # weekly sent-mail append
python3 ~/.claude/skills/fakematt-email/sweep_outgoing.py --account matthew@zergai.com   # deep backfill
```

## Hard rules

- **Never auto-sends.** Output is draft text + (optional) Gmail draft creation. User must confirm in Gmail before any send.
- **Never invents recipient context** that isn't in the thread. If the skill needs background it doesn't have, it asks.
- **Never crosses register boundaries** without an explicit `--register` flag.
- **Never drafts conversationally.** All email text comes out of `run.py`. See "THE ONE RULE THAT MATTERS" above.
