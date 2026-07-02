---
name: ambient-reel
description: Build simple ambient "future cities" reels — atmospheric AI-generated b-roll of drones, maglev/bullet trains, eVTOLs, autonomous vehicles navigating future cities, set to electronic music, NO on-screen text, vertical 9:16, beat-aware, loop-friendly. Use when Matt wants aesthetic "future is now" reels (the IG wallpaper-reel vibe) — distinct from the narrative Omphalos sci-fi serial (omphalos-reel) and from product/launch videos. Generates via fal-video-skill (kling/luma t2v/i2v), assembles via ffmpeg with one unified grade, crops aspect variants, and gates through video-review.
---

# ambient-reel

Atmospheric future-city reels: footage + electronic music, no text, made to be saved and re-watched (the "wallpaper effect"). Lean orchestrator over existing tools — owns only the ambient assembler, variant-crop, and budget gate.

## Hard rules
- **No on-screen text.** Ever. (Matt direction 2026-06-30.) The aesthetic is pure footage + music.
- **One look across the whole reel.** One time-of-day, one camera-move family, one grade — coherence is optical, not just color.
- **Generate native 9:16.** Do NOT center-crop a 16:9 master down to 9:16 (loses ~56% of frame). Crop only *down* to 1:1.
- **Music: real tracks OK for personal/unlisted; clearance is a per-reel decision at publish time.** Cleared "sound-alikes" of Burial/Aphex/etc. are largely fiction — for published cuts, frame as "good cleared electronic at the same BPM/mood."

## Proven facts (2026-06-30 first real test, ~$0.25)
- FAL works; the skill's `luma` endpoint is **deprecated** — use `kling-t2v` (Kling v3) or another current model.
- Kling renders **720×24fps natively** (not 1080/30). The assembler upscales→1080×1920 and retimes→30fps so output passes `video-review` (which requires 30/60fps + ≥1080p). For true premium detail, generate at a higher-res tier or add a real upscaler.
- A single `kling-t2v` aerial future-city clip at ~$0.25 reads as genuinely premium (not slop). Cross-clip coherence across independently-generated shots is the remaining unknown — test it before scaling.

## Pipeline (lean)
1. **Prompt** — `lib/prompt_grammar.py expand --brief briefs/future-cities.yaml` → N prompts = shot template + locked style suffix + shared negative prompt. One subject + one camera move + one time-of-day per clip.
2. **Budget gate** — `lib/budget.py probe` (locked == no FAL key). Estimate per clip; hard session cap (default $2.50, `AMBIENT_FAL_CAP`). Ledger: `work/fal_ledger.jsonl`.
3. **Generate** — `fal-video-skill/fal_video_skill.py t2v "<prompt>" --model kling-t2v -d 5 -a 9:16 -n "<neg>" -o clip.mp4`. (Still-first → i2v is more coherent for compositional shots; default t2v is fine for atmospheric b-roll.) Over-generate ~1.2× for simple shots, more for hard ones; select the best.
4. **Assemble** — `lib/assemble_ambient.py --clips ... --music TRACK --out reel_9x16.mp4 --clip-seconds 4 --grade teal_amber`. Normalizes every clip to 1080×1920/30fps, applies ONE grade, hard-cuts on a fixed grid, beds music (loudnorm + short fades), exports H.264 +faststart. `--no-audio` for a silent visual-coherence pass.
5. **Variants** — `lib/variant_crop.py --input reel_9x16.mp4 --target 1:1 --out reel_1x1.mp4` (cover-crop down; blurred-pad up).
6. **Gate** — `video-review/run.py reel_9x16.mp4`. For ambient, hook-timing / end-card / cut-cadence / end-silence checks are explainer semantics — treat as informational (no-text looping music reel legitimately has none). A passing gate = plumbing is right; **a passing gate is NOT a judgment that the reel is good — eyeball the footage.**

## Deferred (do NOT gold-plate until real reels justify it)
BPM/onset beat-sync (librosa), true seamless-loop seam handling (end-frame conditioning / A→B→A), film-emulation finishing stack (grain+halation+haze), coherence metrics in the gate (optical-flow direction-discontinuity), designed-sound pass. See `season-1-serial.md` §7 + the 2026-06-30 review board for the full craft backlog.

## Grades
`teal_amber` (default), `blue_hour`, `neon_noir`, `warm_dawn`, `none` — in `lib/assemble_ambient.py::GRADES`.
