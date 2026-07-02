---
name: video-editing-director
description: Direct video edits and post-production for product launch videos, demos, ads, explainers, founder videos, social clips, brand films, customer stories, interviews, webinars, and general marketing or business videos. Use when Codex needs to create an edit plan, assemble a paper edit, give revision notes, choose pacing, structure selects, specify captions, music, sound design, motion graphics, end cards, exports, or versioning across channels.
---

# Video Editing Director

## Read before directing the edit (measured anchors)

Load these on every run. Don't direct on vibes when a measured value exists:

1. `references/edit-techniques.md` — measured edit catalog: pacing/MSL by format, transition grammar (hard-cut default, no whoosh), music-out + end-card silence, mix levels, silence-trim.
2. `_style/video_feedback_corpus.md` — Matt's taste layer; it wins over generic convention. Cite slugs (`pacing`, `audio-levels`, `caption-burn-discipline`, `feedback-frame-level`).
3. `~/.claude/skills/product-video-skill/techniques.md` — canonical cut grammar (§3), motion recipes (§2), music/SFX (§6); cite, don't restate.
4. Score the cut against `_style/video_quality_rubric.md` (Edit section) and end the output with a one-line self-score — `Self-score: NN/100 (Edit) — cap: none|<reason>`. For post-render captions, run the `caption-burn` skill.

## Core Workflow

1. Identify the edit goal: assembly, rough cut notes, polish pass, channel cutdown, caption pass, trailer, highlight reel, or final delivery.
2. Map the video into beats with timestamps or scene labels. If footage is not available, use the script, shot list, or storyboard as the edit map.
3. Choose an edit approach from `references/edit-patterns.md` when the category is clear.
4. Give notes as actionable editor instructions: exact timing, what to cut, what to hold, what to cover with b-roll, what text to add, and what problem the note solves.
5. Preserve the viewer's comprehension. Fix pacing by removing duplicate ideas before simply speeding up cuts.
6. Specify export variants and platform constraints when the video is for launch, social, paid, homepage, or sales use.
7. For software-product videos, add a pre-show taste pass before mechanical review: first-frame quality, UI legibility, proof continuity, caption restraint, motion purpose, and end-card readability.

## Note Standards

- Lead with the highest-impact edit changes.
- Separate structural notes from polish notes.
- Use timestamps whenever a draft or transcript exists.
- Explain the intended viewer effect, not just the mechanical change.
- Flag claims, logos, customer names, unreleased UI, and pricing for approval.
- Include sound-off behavior: captions, supers, end cards, and lower thirds.
- For stylized UI edits, note which moments are staged and which claim or source proof they are based on.

## Default Outputs

For a paper edit:

| Order | Source / Select | Use | Audio | Visual Treatment | Notes |
|---|---|---|---|---|---|

For revision notes:

| Priority | Timestamp | Issue | Direction | Rationale |
|---|---|---|---|---|

For final delivery:

- Master export
- Aspect-ratio variants
- Caption files or burned captions
- Thumbnail / first frame
- End card
- File naming
- QA checklist

## Handoff

Use `$video-review` to run a pre-flight critique after a render exists. Use `graphic-layout` or `brand-check` when static frames, thumbnails, or brand usage need separate review.

## Source-tool awareness

When the source clips come from **Screen Studio**, the captured app is already centered on a designer background with smoothed cursor + auto-zoom baked in. Don't add a second background, second zoom, or second cursor effect in the edit — they fight the SS layer and look amateurish. Treat SS clips as already-polished and edit at the sequencing layer (cuts, music, captions, end card) only. `$video-production-planner` "Recording-Tool Routing" is the source of truth for what comes from where.
