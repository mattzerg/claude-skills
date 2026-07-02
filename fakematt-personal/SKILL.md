---
name: fakematt-personal
description: 'Draft or revise direct PERSONAL/family emails in Matt''s voice — separate from professional/Zerg emails (which use fakematt-email with the right identity context). Anchored on `MattZerg/_style/personal_voice.md` + personal corpus. Differs from fakematt-email by dropping formal register, allowing dive-in, and supporting warm "Lots of love" closes. USE PROACTIVELY for direct family/close-friend notes. If a family/friend thread includes a third party, business ask, or Zerg representation, route to fakematt-email instead. Never auto-sends.'
allowed-tools: Bash, Read, Write
---


# Fake Matt Personal Skill

The **personal/family** counterpart to `fakematt-email`. When Matt is writing directly to Dean, Christine, Catherine, Sarah, Leslie, Jens, or any other excluded-from-professional contact, use this skill.

If the thread includes a third party, a business-facing ask, or Matt representing Zerg, route to `fakematt-email` with `matt_personal_professional` or `matt_zerg_professional` identity context. The recipient relationship alone is not enough; the surface context decides the voice stack.

## When to invoke

- "Draft an email to Mom/Dad/Sarah about X"
- "Reply to Christine for me"
- "Draft a thank-you to Catherine"
- "Quick note to Jens about Y"
- Whenever the recipient is in the EXCLUDED list of `fakematt-email`'s tier_map

## Default invocation

```bash
python3 ~/.claude/skills/fakematt-personal/run.py [flags]

# flags (subset of fakematt-email):
#   --to EMAIL              recipient address
#   --task "..."            description of what the email should accomplish
#   --revise PATH           path to a draft markdown file to polish
#   --reply-to-id MSGID     Gmail message ID to reply to (auto-loads thread)
#   --reply-account EMAIL   Gmail account (default matteisn@gmail.com)
#   --tone affection|neutral|terse  override the default tone (auto-picked from context)
#   --out-dir DIR           output dir (default: /tmp/fakematt-personal/)
#   --create-draft          create Gmail draft (still needs your send)
#   --subject               explicit subject (otherwise inferred or carried from --reply-to-id)
#   --model MODEL           Claude model id (default: shared Claude wrapper default)
```

## Three tones (vs. fakematt-email's three registers)

| Tone | Example greeting | Closer | When |
|---|---|---|---|
| **affection** | "Hi Mom," / "Hey Catherine," | "Lots of love <3" + Matthew | Reaching out to family after silence; cards; warm threads |
| **neutral** | (dives in) | (drops closer) | Continuing an active family thread |
| **terse** | (dives in) | (no closer) | Family logistics — chairs, gifts, $ transfers |

Auto-picked from prior-thread tone unless `--tone` is set.

## Anchors

- `MattZerg/_style/personal_voice.md` — distilled rules + tones + sample textures (PRIMARY voice anchor for this skill)
- `MattZerg/_style/personal_voice_corpus.md` — 29 raw outgoing samples (excludes Jens technical-paste threads)
- `MattZerg/People/<name>.md`, `MHE/People/<name>.md` — vault context auto-injected
- **Cross-reference (cross-surface voice substrate):** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_voice_patterns.md` — read for cross-surface voice consistency; personal_voice.md still wins on conflicts (closer, opener flexibility, no-bullet rule)
- **Catalog patterns to cite by slug** (Section C Prose / writing): throat-clearing-preamble

## Hard rules

- **Never "Best, Matthew" with family.** Closer is "Lots of love <3" + Matthew, or "Matt", or nothing.
- **No bullet lists** — too businesslike for family. Prose only.
- **When third parties are cc'd** (e.g., a UMich contact intro from Dean), DEFAULT TO professional voice instead — route to fakematt-email.
- **When the message represents Zerg**, route to fakematt-email with `matt_zerg_professional`, even if a close contact is involved.
- **Never auto-sends.** Same as fakematt-email.

## Caveat

The personal voice corpus is small (29 samples, ~10 truly casual). The skill leans on Matt's professional Casual-Pro voice (Register C) as a fallback floor. Differences are mostly in closer + opener flexibility, not in body texture.
