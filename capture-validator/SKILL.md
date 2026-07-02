---
name: capture-validator
description: Hard-fail gate on screen-capture quality BEFORE a video is assembled. Validates that the recorded app window is full-screen (no menu bar, no dock, no desktop wallpaper bleed, axis-aligned, ≥1080p, no notification banners). Runs against a finished `.mp4` or a pre-record screenshot. Emits an annotated PNG showing every violation with a red box. Hard-fail by default; bypass via `CAPTURE_VALIDATOR_BYPASS=1` (logged). Used as the pre-assembly gate in the `video-production` agent and as a standalone check before any product/demo recording. Built to catch the specific failure mode where Michael's Tycoon recording shipped at a tilt with desktop wallpaper around the browser window.
allowed-tools: Bash, Read, Write
---

# Capture Validator

## Why this exists

The `11-capture-spec-for-michael-v2.md` doc told Michael to record full-screen. He didn't (browser at an angle, wallpaper visible, downscaled the UI illegibly). The doc was aspirational; nothing enforced it. This skill is the enforcement.

A video doesn't ship if the source captures fail the gate.

## Source modes

Two source modes, selected via `--source`:

- `default` (raw screen capture from QuickTime, OBS, `screencapture`, etc.) — runs the full gate below.
- `screen-studio` (composited output from Screen Studio) — skips OS-chrome / wallpaper / tilt / top-right notification checks (by construction inapplicable: SS composites the captured window onto a designer background, strips OS chrome, and outputs axis-aligned), runs `resolution` + a new `screen_studio_composition` check (inner window centered + adequate padding).

## Gate checks — `default` source (HARD-FAIL on any violation)

1. **Resolution** — first stream must be ≥1920×1080 native. Sub-HD fails.
2. **Full-frame UI** — the "app content" bounding box (detected via row/column edge density on a downscaled first frame) must cover ≥95% of frame area. If wallpaper bleeds in around an off-center window → FAIL.
3. **No tilt** — the app bounding box must be axis-aligned. Detected via Hough-style edge angle estimation; tolerance ±1°. Tilted recordings (Loom-style multi-app capture) → FAIL.
4. **No menu bar** — top 28-pixel band tested for the macOS menu-bar pattern (high-contrast text on uniform background, app names visible). If present → FAIL.
5. **No dock** — bottom ~80-pixel band tested for dock translucency / icon clusters. If present → FAIL.
6. **No notification banner** — top-right block tested for a banner-shaped contrast region. If present → FAIL.
7. **Window chrome** — corner pixels tested for rounded shadow indicating a windowed app rather than full-screen. If chrome detected → FAIL.

## Gate checks — `screen-studio` source (HARD-FAIL on any violation)

1. **Resolution** — same as default.
2. **Composition** — detects the inner captured-window rect via edge density; FAILs if off-center by >8% of frame in either axis OR any side has <1.5% padding (window crushed against edge / lost background). Also FAILs if no inner rect can be detected (composition came out flat).

Known gap: an OS notification that fires *inside* the captured window during recording would appear inside the SS inner rect, not at the frame edge, and is not currently detected. Add `screen_studio_notification_leak` if this bites.

## Soft warnings (don't fail; surface)

- **DND state** — best-effort check via `defaults read com.apple.notificationcenterui`; warns if DND is off during recording.

## CLI

```bash
# Validate a finished mp4 (raw capture)
python3 ~/.claude/skills/capture-validator/run.py validate <path/to/video.mp4>

# Validate a Screen Studio export
python3 ~/.claude/skills/capture-validator/run.py validate <path/to/video.mp4> --source screen-studio

# Pre-record check: capture a test frame and validate it
python3 ~/.claude/skills/capture-validator/run.py preflight

# Validate a single PNG (e.g., a screenshot)
python3 ~/.claude/skills/capture-validator/run.py validate-image <path/to/frame.png>

# Validate a Screen Studio still / preview frame
python3 ~/.claude/skills/capture-validator/run.py validate-image <path/to/frame.png> --source screen-studio
```

## Output

Per run, writes to `~/Downloads/capture-validator/<basename>/`:

- `report.json` — `{passed: bool, checks: [...], details: {...}}`
- `violations.png` — annotated first frame with red boxes around each violation + labels
- `frame.png` — the raw first frame extracted from the video (skipped if `validate-image`)

Exit code:
- `0` = all gates passed
- `1` = at least one HARD-FAIL violation
- `2` = could not analyze (corrupt video, missing file, etc.)

## Bypass

```bash
CAPTURE_VALIDATOR_BYPASS=1 python3 ~/.claude/skills/capture-validator/run.py validate <video.mp4>
```

Bypass is logged to `~/.claude/capture-validator/log.jsonl` with timestamp + file + checks-that-would-have-failed. Use only when:
- A re-record is impossible and the failure is cosmetic
- Demoing the validator itself (test fixture)
- Matt or Idan explicitly requested the override

## When to invoke

- **Pre-assembly gate** in `video-production` agent — before any video clip enters the edit, it runs through here.
- **Pre-record** by Michael / Matt / anyone capturing footage — `preflight` command runs after setup, before the real take.
- **Retroactive triage** on existing footage that "doesn't look right" — flags exactly what's wrong with a visual annotation.

## When NOT to use

- AI-generated video frames (FAL, Runway, Kling) — they don't have capture-quality failure modes this gate detects. Use `graphic-layout` skill instead.
- Talking-head / interview videos — the gate's full-frame-UI rule doesn't apply.
- Phone-recorded footage — different aspect / framing assumptions.

## Failure modes captured in memory

- See `~/Desktop/tycoon-video-2026-05-13/_superseded/11-capture-spec-for-michael.md` — the doc that wasn't enforced.
- See `feedback_video_pipeline.md` (created on first toolkit ship) — captures the lesson: documents don't enforce, gates do.
- See `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/video_feedback_corpus.md` for 3 referenced video-capture exemplars (Tycoon failure frame, the corrected re-record, and a Screen-Studio composition reference) — path-only reference; load on demand when triaging a borderline gate decision.

## Anchors

- **Catalog patterns to cite by slug** (Section B UI / product design): blank-canvas-friction, ui-weight-vs-importance
- **Catalog patterns to cite by slug** (Section E CRO / marketing): missing-cta, hero-clarity, proof-gap

## Files in this skill

- `SKILL.md` — this file
- `run.py` — CLI entrypoint (validate / preflight / validate-image)
- `lib/checks.py` — the pixel-level checks
- `lib/annotate.py` — draws violation boxes on the frame
- `tests/` — golden-set tests including the Tycoon failure frame

## Sibling skills

- `video-review` — runs AFTER assembly; calls this skill in its capture-quality auto-check.
- `product-video-skill` — produces the captures this gate validates.
