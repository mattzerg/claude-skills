# Creative Pre-Flight Checklist: Video Shot List — {{SLUG}}

**Source:** {{SOURCE}}
**Generated:** {{DATE}}
**Status:** [TO FILL: in-progress / complete]

> Video variant. For an Omphalos reel the anchor is the project's LOCKED craft bar
> (`omphalos-universe-bible-v1` §Craft bar + §Production pipeline + §Visual language v2);
> for other video work substitute the project's own bible/brief. Numbers in any
> generation prompt are an automatic reject — meaningful text/numbers are POST-composited.

---

## Step 1 — Read the source

- [ ] Read the bible/brief craft-bar + format sections (or the full brief if short)
- [ ] Read the format's relevant lore/context notes
- [ ] Check rotation/slate state (e.g. `channel-log.md` Stage A: last format used, pending slots)

**Central beat of this video (one sentence):**
[TO FILL]

**The image a viewer screenshots (one phrase):**
[TO FILL]

---

## Step 2 — Read the reference set

- [ ] Watch/skim 2 approved prior videos in the same universe/series (incl. the keystone)
- [ ] Note the register: pacing, VO cadence, tonal dial for this location/format
- [ ] If a continuity CLI exists (`lore.py clock` / `lore.py deposits`), capture its output here

**Observed register (paragraph):**
[TO FILL]

---

## Step 3 — Brainstorm 3 concepts

Each concept must:
- Be tagged with its FORMAT and pass the rotation rule (never two of the same format back-to-back)
- Be specific enough to fail Cap Test #2 (could NOT be any other video in the series)
- Show the underlying MECHANISM/thesis, not just the topic's aesthetic

**Concept A — Name + format:** [TO FILL]
**Description:**
[TO FILL]

**Concept B — Name + format:** [TO FILL]
**Description:**
[TO FILL]

**Concept C — Name + format:** [TO FILL]
**Description:**
[TO FILL]

---

## Step 4 — Pick one + write WHY

**Picked:** [TO FILL: A / B / C]

**Why (must reference the format's lore job / the series' mechanism, not "looks cool"):**
[TO FILL]

---

## Step 5 — Check against craft-bar / memory rules

- [ ] Photoreal engine + hard negatives on every frame prompt (incl. `numbers, digits, text, letters`)
- [ ] Meaningful numbers/text composited in POST only — zero digits in any generation prompt
- [ ] Motion: subtle/no-zoom i2v prompts only; hero shots ≤3; $0 smooth motion elsewhere
- [ ] Shot variety: no two adjacent shots share scale/angle/subject
- [ ] Per-location tonal dial applied (gritty vs clean per place, not one flat look)
- [ ] Duration band respected (Omphalos: 30-50s)
- [ ] Music from the real-track library w/ license noted; animatic-first ($0 draft before any paid motion)
- [ ] All PASS? [TO FILL: yes / no — list violations]

---

## Step 6 — Shot list + VO

VO beats (6-beat default): hook / world / turn / reveal / tension / thesis.

| # | Frame file | Prompt summary (one line) | Motion | Hero? | VO line | Handle |
|---|---|---|---|---|---|---|
| 1 | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] |
| 2 | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] |
| 3 | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] |
| 4 | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] |
| 5 | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] |
| 6 | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] |

---

## Step 7 — Pre-flight self-review (video cap tests)

- [ ] **Cap Test #1 (motion):** No zoom/push prompts in any i2v prompt (push-ins are POST-only). PASS? [TO FILL: y/n]
- [ ] **Cap Test #2 (specificity):** "Could this shot list belong to any other video/format in the series?" If yes → REJECT. PASS? [TO FILL: y/n]
- [ ] **Cap Test #3 (numbers):** Zero digits anywhere in a generation prompt. PASS? [TO FILL: y/n]
- [ ] **Cap Test #4 (variety):** No two adjacent shots with same scale/angle/subject. PASS? [TO FILL: y/n]

**All cap tests pass?** [TO FILL: yes / no — if no, return to Step 3 or 6]

---

## Step 8 — Fire

**Tool/pipeline:** [TO FILL — e.g. omphalos-reel: omphalos_vo.py + new_reel.py scaffold/lint/queue]
**Spec path:** [TO FILL]
**Spend declaration:** [TO FILL — "$0 draft only" unless owner approved paid motion]
**Status:** [TO FILL: fired / staged / failed]

---

## Step 9 — Post-fire review

- [ ] Run the draft checker (`reel_review.py <draft> --spec <spec>`) or equivalent; paste findings
- [ ] Verify VO files (ffprobe) + script-line match
- [ ] Stage-A scorecard ready for owner (hook / turn / feeling / lore / craft — owner scores, never auto-filled)

**Findings:** [TO FILL]
**Decision:** [TO FILL: accept / iterate / reject]
