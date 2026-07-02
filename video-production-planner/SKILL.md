---
name: video-production-planner
description: Plan video production logistics for product launch videos, demos, founder videos, ads, explainers, customer stories, brand films, social videos, interviews, webinars, and general marketing or business videos. Use when Codex needs to turn a concept, script, shot list, or storyboard into a shoot plan, asset list, crew needs, screen-recording plan, schedule, call sheet outline, risk list, or production checklist.
---

# Video Production Planner

## Core Workflow

1. Identify the production mode: screen recording, stylized UI motion, live action, remote interview, motion graphics, mixed media, event capture, or AI/image-assisted.
2. Convert the script, shot list, or storyboard into required assets and capture tasks.
3. Build a production plan with owner, source, deadline, and status for every asset or shot.
4. Call out constraints early: talent availability, product state readiness, unreleased UI, legal approvals, customer permissions, music licensing, brand review, captioning, and platform variants.
5. Produce the lightest plan that can prevent missed footage. Do not overbuild a call sheet for a one-person screen recording unless the user asks.
6. For stylized UI motion, track both the proof source and the recreated UI asset. Do not let a proof recording become the production plan by accident.

## Production Modes

Read `references/production-modes.md` when the mode is unclear or the project combines multiple capture types.

Default to:

- Screen-recording checklist for product demos and launch videos.
- Stylized UI asset tracker for software launch clips when the user allows staged or recreated UI.
- Lean shoot plan for founder/social clips.
- Interview plan for customer stories and testimonials.
- Asset tracker for motion-heavy or mixed-media videos.

## Recording-Tool Routing

Pick the capture tool by shape of the video, not by habit:

| Shape | Tool | Why |
|---|---|---|
| Demo with clicks (product walkthrough, feature reveal, click-tracking) | **Screen Studio** (Mac, `/Applications/Screen Studio.app`) | Auto-zoom on cursor + smoothed cursor + designer background composite. Removes the wallpaper-bleed / tilt failure mode by construction. |
| Talking head + screen + b-roll (founder video, interview-over-screen) | QuickTime / OBS + multicam → `$video-editing-director` | SS doesn't do multi-source talking-head; needs an actual editor. |
| Long-form course or tutorial (>5 min, pause/resume, chaptered) | ScreenFlow | Pause/resume + project structure SS lacks. |
| AI-generated / motion-graphics | n/a — generated, not captured | Skip capture-validator; use `graphic-layout`. |

### Screen Studio pre-record checklist

Run this BEFORE hitting record, every time. Failure modes are silent.

1. **Permissions** — System Settings → Privacy & Security → grant Screen Recording AND Accessibility (the auto-zoom-on-click feature needs Accessibility; without it, no zooms fire and the recording looks like a flat screencap).
2. **Do Not Disturb on** — Screen Studio captures the actual screen; a notification fired mid-recording lands inside the captured window and is hard to crop out.
3. **Tab / window cleanup** — close everything not in the demo. SS will frame the captured window, but tab strips, sidebars, and adjacent monitors still leak into the capture if multi-window mode is picked.
4. **Capture mode** — pick "Window" (not "Full Screen") for app demos so SS auto-fits and composites cleanly.
5. **Pre-flight gate** — `python3 ~/.claude/skills/capture-validator/run.py preflight --source screen-studio` to confirm the staging frame composes correctly.

### Post-record gate

After export, run capture-validator in SS mode before the file enters the edit:

```bash
python3 ~/.claude/skills/capture-validator/run.py validate <export.mp4> --source screen-studio
```

This validates resolution (≥1080p) + composition (window centered, padding sane). Hard-fail by default; bypass via `CAPTURE_VALIDATOR_BYPASS=1` (logged).

## Default Output

Include the sections that match the task:

- Production assumptions
- Shot or asset tracker
- Screen-recording states
- Talent / location / gear
- Schedule
- Approvals
- Risk register
- Edit handoff package

Use this table for trackers:

| Item | Type | Owner | Source / Location | Due | Status | Notes |
|---|---|---|---|---|---|---|

## Handoff

When production is planned, use `$video-editing-director` for edit assembly, pacing, captions, music, versions, and delivery. Use `$video-review` after a draft render exists.
