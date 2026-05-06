---
name: fakematt-copyedit
description: Run a Fake Matt copyediting pass on prose drafts (blog posts, thought pieces, launch announcements, social copy). Reads one or more markdown files, anchors against `MattZerg/writing_style.md` + voice fingerprint, and emits an annotated review with inline comments + a separate interview file listing items where uncertainty is high enough to warrant a live discussion. Output is professional/structured (not Matt-voice cosplay) — comments cite the writing-style rule or voice principle they reference. USE PROACTIVELY when Matt asks for a copyedit, "review this draft", "have Fake Matt look at this", or before any prose ships externally. Never auto-posts to shared channels — writes to disk + Fake Matt self-DM only when explicitly asked.
allowed-tools: Bash, Read, Write
---

# Fake Matt Copyedit Skill

Sibling to `fakematt-feedback` (product/UX review). This one is the **prose review** counterpart: reads markdown drafts, runs them through the writing-style guide + voice fingerprint, emits structured edits with provenance and confidence.

## When to invoke

- "Have Fake Matt review these" / "copyedit this draft"
- Before any blog post, thought piece, launch announcement, or social copy ships
- When Matt drops a markdown path and asks for prose review with no further context
- After polishing a piece, as a sanity check before sending to Idan
- For batch review of multiple drafts at once (launch campaign with paired social variants)

When in doubt, suggest running it before pieces leave the vault.

## Default invocation

```bash
python3 ~/.claude/skills/fakematt-copyedit/run.py <markdown_path> [<more_paths>...] [flags]

# flags:
#   --out-dir DIR        where to write reviews + interview file (default: /tmp/fakematt-copyedit/)
#   --model MODEL        Claude model (default: claude-opus-4-7)
#   --no-pdf             skip PDF conversion + Preview open
#   --quick              shorter review (skip social-variant analysis)
```

## Output files (per invocation)

For each input file `<draft>.md`:

- **`<draft>.review.md`** — annotated draft with inline comments. Each comment is a blockquote that cites a rule (writing_style.md section), confidence (HIGH / MEDIUM / LOW), and either a rewrite suggestion or a discussion question.
- **`<draft>.interview.md`** — extracted list of LOW-confidence items requiring a live conversation with the author. Format: numbered items with the source quote, the concern, and the question to discuss.

Plus one combined file:

- **`session-summary.md`** — index of all reviews in this run with counts (HIGH/MEDIUM/LOW), files reviewed, model used, time taken.

When `--no-pdf` is not set, the script also runs the same PDF conversion as `/tmp/md_to_pdf.py` and opens all review + interview files in Preview as a single window.

## Confidence levels

- **HIGH** — clear violation of a documented rule (writing_style.md or AI-cleanup checklist). The fix is unambiguous; just apply it.
  - Example: "em-dash count exceeds the 2-3 per 500 words threshold from writing_style.md → suggest replacing X em-dashes with periods/commas/colons"
- **MEDIUM** — pattern that the style guide flags, but where the fix depends on context. Suggest a default rewrite but note alternatives.
  - Example: "this line is the third parallel triplet in the section; consider breaking the cadence — but if rhetorical drumbeat is intended, keep"
- **LOW** — voice/intent uncertain enough that the fix needs author input. **These auto-route to the interview file.**
  - Example: "the closing 'That's the future we're building toward' matches Idan's documented ending pattern but tone-checks ambiguous given the audience for this specific piece — discuss"

## Anchors used

- `MattZerg/writing_style.md` — primary style bible (Scott Adams principles, AI-tells, Idan's voice patterns)
- `MattZerg/CLAUDE.md` "AI Writing Cleanup" section — punctuation + structure + rhetorical patterns to fix
- `~/.claude/feedback-corpus/voice/fingerprint.md` — Matt's positioning instincts (relevant for launch posts that double as marketing)
- Reference pieces named in writing_style.md (Idan's published Substack + Zerg blog posts) for voice calibration

These are loaded as context for every run; cached if/when the skill moves to SDK-with-cache later.

## Output register

**Professional/technical/structured, NOT Matt-voice cosplay.** Per `feedback_fakematt_feedback_voice.md`. The voice corpus is a coverage map (what to look for), not a style guide for the review itself.

Each finding cites:
- **Rule:** which line/section of writing_style.md (or AI-cleanup checklist)
- **Confidence:** HIGH / MEDIUM / LOW
- **Suggestion:** rewrite OR question OR "no action — flagging for awareness"

## What this skill is NOT

- Not a fact-checker. Doesn't verify claims, citations, or links.
- Not a hero-image generator. (See nano-banana-pro / fal-image-skill / Pollinations fallback.)
- Not a publishing skill. Doesn't push to Zadmin or schedule posts.
- Not for code review. (See review / security-review skills.)
- Not a Matt-voice cosplay. Output is plain analytical prose with citations.

## Safety

- **Never auto-posts.** Writes to disk only. If Matt asks for a Slack copy, drops it in his self-DM (matching `fakematt-feedback` rule).
- **Doesn't modify the source draft.** Reviews are written to a separate file so the author can choose what to apply.
- **No memory writes.** This skill reads memory (style anchors) but doesn't write to it.
