---
name: visual-bible-critic
description: Score a generated frame (FLUX still or i2v keyframe) against the Omphalos visual bible and PASS/FAIL it BEFORE it enters a reel. The automated guardrail that stops soft / muted / low-res / non-cyberpunk / off-style frames from shipping (the failure that produced the regressed "Wending" reel). Use in the Omphalos production pipeline after every FLUX generation and before assembly; auto-reroll on FAIL. Scores 9 axes (futurism, palette, scale, density, motion, text-absence, materiality, composition, relevance) + hard-fails.
---

# visual-bible-critic

Gates every frame against `scifi-reels/omphalos-visual-bible-v1.md`. **PASS = every axis ≥ floor (default 7) AND no hard-fail.** Hard-fails: garbled generated text, present-day-Earth, sparse/empty, soft/low-res, morph/wobble, fantasy/painterly.

## Two backends
- **AUTO** (headless/cron): set `ANTHROPIC_API_KEY`, then `critic.py score FRAME …` calls Claude vision and prints the JSON verdict (exit 0=PASS, 1=FAIL).
- **AGENT** (inside Claude Code, no key): `critic.py prompt FRAME … --title … --location … --vo-beat …` prints the scoring prompt; dispatch a vision subagent (Explore/general) with the frame + that prompt; it returns the JSON schema; apply PASS/FAIL (every axis ≥ floor and no hard_fails). `critic.py score` without a key prints agent-mode instructions + the schema.

## Usage
```bash
python3 ~/.claude/skills/visual-bible-critic/critic.py score \
  /path/frame.png --title "The Census" --location "Crown/Ministry" \
  --vo-beat "the spire counts the city" --model flux-pro --floor 7 --json-out report.json
```

## Where it plugs into the pipeline (mandatory)
```
FLUX Pro still  ──►  visual-bible-critic  ──┬─ PASS ─► keep (→ i2v / assembly)
   (fal-image)                              └─ FAIL ─► re-roll FLUX with reroll_params
                                                       (stronger negatives / new seed / composite text in post)
kling-pro i2v   ──►  visual-bible-critic (motion_smoothness) ──► PASS=cache clip / FAIL=re-render
```
No frame enters assembly without a PASS. This is the standard the soft Wending reel skipped.

## Notes
- **Generated text is a hard-fail by design.** FLUX renders gibberish Latin signage even with text negatives — so the workflow is: generate text-free frames, then composite Concord glyphs / 841 / the Hand in post (`assets/concord-script/`, `_pipeline` plates).
- Calibration target: old reels (`omphalos-841/e1-graffiti.png`, the `style-test` exemplars) → PASS; soft Wending frames (`~/Downloads/omphalos-EP-the-wending` frames) → FAIL.
- Default vision model `claude-sonnet-5` (fast/cheap for a per-frame gate); override `--vision-model`.
