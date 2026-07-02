---
name: omphalos-reel
description: 'Stage the next Omphalos reel end-to-end at $0 (no FAL spend without explicit go): canon read order (bible craft bar → encyclopedia → lore ledger) → creative-prereq video-shot-list gate → 3 concepts w/ format-rotation check → 6-beat Chronicler vo-script (hook/world/turn/reveal/tension/thesis) → VO via omphalos_vo.py (chronicler=George locked; diegetic cast benched) → spec scaffold/lint/queue via new_reel.py → stop before any frame generation. Thin wrapper over scifi-reels/assets/_pipeline (like standup over fakematt-today). Composes creative-prereq (gate), lore.py (continuity lint + fall-clock), reel_review.py (Stage-A pre-check). USE PROACTIVELY when Matt says "stage the next reel", "new Omphalos reel", "next reel in the slate", "build the <format> reel", "make a reel about X", or after a Stage-A verdict clears a slate slot. Never runs genframes/--final or spends FAL without explicit go; never auto-posts.'
---

# Omphalos Reel — staging ritual

One entry point for producing the next reel in the Omphalos channel. Everything here is **$0** — the only FAL spends (FLUX frames, Kling-Pro heroes) happen later via `unlock_queue.sh` / `reel_build.py --final`, both Matt-gated.

## Paths

- Project: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg/Projects/Zerg-Production/scifi-reels/` (quote it — spaces)
- Pipeline `<P>` = `<project>/assets/_pipeline/`
- Canon: `omphalos-universe-bible-v1-2026-06-07.md` (LOCKED craft bar — never relitigate), `encyclopedia/` (12 notes incl. Intrigue Engine), `lore-ledger.jsonl` (CLI: `lore.py`), `season-1-map.md` (the slate), `channel-log.md` (Stage A state), `channel-plan.md` (rotation, captions, feedback loop).

## The ritual (in order — do not skip steps)

1. **Canon read order**: bible §Craft bar + §Recurring formats + §Production pipeline → `season-1-map.md` (which slot is next, its assigned sign/foreshadow) → `channel-log.md` Stage A (last format used; pending reviews) → `python3 "<P>/lore.py" clock` + `lore.py deposits <last-reel>` → the 2-3 encyclopedia notes relevant to the slot (Intrigue Engine notes for spine reels).
2. **Gate**: `python3 ~/.claude/skills/creative-prereq/run.py prepare video-shot-list --slug omphalos-<slug>` — fill EVERY section (3 concepts, pick+why, craft-bar checkboxes, shot table, video cap tests). `run.py validate <checklist>` must pass before generation.
3. **Rotation check**: concept's format ≠ previous reel's format (channel-plan §3). The season map pre-assigns formats — deviate only with a reason written into the checklist.
4. **vo-script**: copy `templates/vo-script.template.md` into the reel dir; 6 numbered lines on the 6-beat spine (hook/world/turn/reveal/tension/thesis); target **30-44s spoken** (the Chronicler reads ~1.4 w/s slow-register: ~12-18 words/line; ALWAYS tighten if total VO >46s — past reels drifted long). Run `python3 "<P>/lore.py" lint <vo-script.md>`: fix ERRORs (retired terms), weigh WARNs, register new deposits via `lore.py add`.
5. **VO**: `python3 "<P>/omphalos_vo.py" script <vo-script.md> --voice chronicler --prefix <2-letter>`. Diegetic cast lines (season map reels 10+) need the benched role's `voice_id` set in `voices.json` first — bench files for Matt at `<project>/assets/vo-bench/`. Cast lines nest inside Chronicler quotes (bible narrator system).
6. **Spec**: `python3 "<P>/new_reel.py" scaffold <slug> --format <fmt> --prefix <2-letter>` then fill: frames_gen prompts (craft-bar grammar: "Photorealistic cinematic film still, … anamorphic, ARRI Alexa, film grain, grounded science fiction"; per-location tonal dial; ZERO digits — numbers are POST overlays), motion variety, hero ≤3 with subtle no-zoom i2v prompts, score from `assets/music/` (note CC-BY attribution in captions pack), clock block per season map (folk/official/vo + `clock_overlay.py spec-block` for the overlay JSON), text overlays (841/Concord script via `<P>` plates).
7. **Lint + queue**: `new_reel.py lint <spec>` (fix all ERRORs) → `new_reel.py queue <spec> --format <fmt>` → update `season-1-map.md` row status + `captions-launch-pack.md` (caption MUST end on an unanswered question/term; never mention the clock or digits).
8. **STOP.** Print the unlock command (`bash "<P>/unlock_queue.sh" <slug>_spec.json`) and the cost estimate (~$0.36 frames + ~$0.50/hero). Do not run it. Frames/finals are Matt-gated.

## After frames land (FAL unlocked, drafts built)

- `python3 "<P>/reel_review.py" <draft.mp4> --spec <spec>` → paste findings + empty Stage-A scorecard for Matt (the 1-5 scores are HIS, never auto-filled).
- On Stage-A pass: `reel_build.py <spec> --final` (budget-gated, confirm prompt) — only with Matt's explicit go.
- Plant the sign: `lore.py clock <sign#> --reel <slug>` when the escalation sign lands on-screen.

## Hard rules (memory-backed)

- Craft bar is LOCKED (no serif titles, no zoom prompts, numbers in POST, ≤3 heroes, animatic-first, ≤~9 FAL calls/reel).
- Versioned filenames on every Matt-facing artifact (`-vN-YYYY-MM-DD`).
- Never auto-post to any platform; captions pack is drafts-only.
- FAL spend always through `fal_budget.Budget` (cap $2 est/session, `FAL_SESSION_CAP` override) + `OMPHALOS_QUEUE_CAP` for batches.
