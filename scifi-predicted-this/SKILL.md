---
name: scifi-predicted-this
description: Bridge the OMPHALOS Sci-Fi Innovation Tracker to bulletin production. Given an in-world technology (or "next" from the backlog), pull its real-futurology grounding — antecedent (the sci-fi work that first dreamed it) + real analogue (the present-day tech) + "the crack" (how it breaks society) — and turn it into a dry-Ministry-bulletin VO script plus the "sci-fi predicted this" video-description hook, then hand off to omphalos_produce.py. USE when Matt says "make a bulletin about <tech>", "what does the tracker say about X", "next tracker bulletin", or when producing Omphalos worldbuilding content that should carry real futurology. Never auto-posts.
---

# scifi-predicted-this

Wires the grounded-technology bestiary (`scifi-reels/encyclopedia/technology.md`, 11 techs, each with a sci-fi
antecedent + real analogue + "the crack") into bulletin production, so every Omphalos bulletin carries a real
futurology payload — the channel's factual hook, not just aesthetic.

## Data access — `bridge.py`
- `python3 bridge.py list` — the 11 tech names.
- `python3 bridge.py get "<name>"` — structured record (fuzzy name match): summary, antecedent, analogue,
  similarity_kind, confidence, grounding (grounded/frontier/mixed), crack_title, crack.
- `python3 bridge.py hook "<name>"` — the ready-to-paste video-description line.
- `python3 bridge.py all` — every record as JSON.

## Workflow (tech → bulletin)
1. Pick a tech (Matt names one, or take the next un-produced from `bridge.py list` vs `production-log.md`).
2. `bridge.py get "<name>"` → the grounding.
3. **Write the VO** in the LOCKED dry-bureaucratic Ministry register (see `templates/ministry-bulletin/bulletin-scripts.md`
   for the 5 exemplars + register): a calm compliance/advisory broadcast that *implies* menace through banal
   logistics and lands on a chilling courtesy button. ~40–55 words (~15–18s). NEVER proclamatory clichés.
   The tech is referenced in-world (its Omphalos name), never the real analogue.
4. **The description hook** = `bridge.py hook "<name>"` (antecedent → real analogue + the crack). This is where
   the real futurology surfaces for the viewer — "sci-fi predicted this."
5. **Produce**: hand the VO + chosen PASS frames to `omphalos_produce.py` (or `omphalos_bulletin.py` directly),
   and record the run in `templates/ministry-bulletin/production-log.md`.

## Register guardrails (from the locked feedback)
- Dry, procedural, specific; horror from banality. Button lines like "thanks you for your continued
  predictability." NOT "your future is decided" / "the rain will fall on schedule."
- The VO stays in-world (Ministry voice); the real-tech grounding lives ONLY in the description hook.

## Do not
- Auto-post. Reproduce the antecedent works' text — only cite title/year as fact (that's what the hook does).
