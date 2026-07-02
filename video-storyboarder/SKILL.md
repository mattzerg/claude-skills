---
name: video-storyboarder
description: Create text storyboards, frame plans, visual boards, animatics, and storyboard prompts for product launch videos, demos, ads, explainers, founder-led announcements, social clips, brand films, case studies, and general video projects. Use when Codex needs to define frame composition, camera angle, UI crop, motion, graphic treatment, transitions, or per-frame production notes before filming, recording, animating, or editing.
---

# Video Storyboarder

## Read before boarding (measured anchors)

Load these on every run. Don't board on vibes when a measured value exists:

1. `references/storyboard-techniques.md` — measured composition catalog: text sizing (% frame ht), hold=reading-time, frame-content mix, aspect-ratio safe-area, defined jargon (focal subject, proof invariant).
2. `_style/video_feedback_corpus.md` — Matt's taste layer; it wins over generic convention. Cite slugs (`feedback-frame-level`, `on-screen-text-readability`, `product-as-the-product`).
3. `~/.claude/skills/product-video-skill/techniques.md` — canonical caption/frame measurements (cite §4/§5/§7).
4. Score the board against `_style/video_quality_rubric.md` (Storyboard section) and end the output with a one-line self-score — `Self-score: NN/100 (Storyboard) — cap: none|<reason>`.

## Core Workflow

1. Start from a script, shot list, or brief. If none exists, create a minimal beat list before storyboarding.
2. Decide the board fidelity: text-only board, thumbnail prompts, animatic notes, or production storyboard.
3. Use the frame fields in `references/storyboard-template.md`; keep each frame tied to a specific narrative beat.
4. Specify what changes inside the frame: camera move, cursor movement, UI transition, object motion, expression, text reveal, or cut.
5. Check legibility for the target aspect ratio. Mark frames that need separate 16:9, 9:16, or 1:1 compositions.
6. Include production constraints: required assets, location, talent, props, screen states, brand elements, and pickup risk.
7. For software-product videos, mark whether each frame is live capture, designed UI motion, or hybrid. Identify what is staged and what product claim it supports.

## Composition Rules

- Make the first frame readable as a thumbnail when the video is for social, ads, or launch distribution.
- Keep one subject of attention per frame unless the split-screen comparison is the point.
- Put UI, captions, and faces where platform overlays will not cover them.
- Use close-ups for proof; use wide shots for context.
- Treat on-screen text as part of the composition, not a caption afterthought.
- Do not use a raw full-screen app view as the default composition. Crop or rebuild the UI so the viewer can read the product action.
- For stylized UI motion, board the first frame, proof setup, transformation, proof hold, and end card before rendering.
- Mark impossible or expensive frames early instead of hiding them in prose.

## Default Output

Use a table for compact work and sections for detailed boards.

| Frame | Time | Composition | Action / Motion | Text / Graphics | Audio | Assets / Notes |
|---|---|---|---|---|---|---|

For image generation or illustration handoff, add a `Prompt` line under each frame, but avoid generating images unless the user asks for visual assets.

## Handoff

Use `$video-production-planner` after the board is approved for shoot logistics. Use `$video-editing-director` when the board needs an edit map, motion treatment, music, caption, or delivery plan.
