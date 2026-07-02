---
name: video-scriptwriter
description: Write, revise, and diagnose scripts for product launch videos, brand films, founder-led announcements, ads, demos, explainers, social videos, case-study videos, and other marketing or general-purpose video formats. Use when Codex needs to turn a brief into narration, dialogue, captions, on-screen copy, a hook, voiceover, interview questions, talking points, or multiple script variants with timing and channel constraints.
---

# Video Scriptwriter

## Read before drafting (measured anchors)

Load these on every run. Don't draft on vibes when a measured value exists:

1. `references/script-techniques.md` — measured script catalog: VO cadence (2.3–2.7 w/s scripted), words-per-beat budgets, hook word-counts, VO-vs-on-screen split. Frame/caption-sourced.
2. `_style/video_feedback_corpus.md` — Matt's taste layer. Where it disagrees with generic convention, it wins. Cite pattern slugs (`hook-in-first-3s`, `voice-cosplay-guard`, `product-as-the-product`).
3. `~/.claude/skills/product-video-skill/techniques.md` — canonical shot/cut/caption frame data (cite §, don't restate).
4. Score the draft against `_style/video_quality_rubric.md` (Script section) and end the output with a one-line self-score — `Self-score: NN/100 (Script) — cap: none|<reason>`.

## Core Workflow

1. Clarify the job the video must do: audience, channel, desired action, product or story proof, runtime, format, and production constraints. If any field is missing, make a conservative assumption and name it.
2. Choose the script shape from `references/script-patterns.md` when the user gives a category. For product launches, prefer `$product-launch-video` when the ask includes concept, shot planning, production, or edit direction beyond script text.
3. Draft in timed beats, not prose blocks. Include columns for time, audio or dialogue, on-screen text, visual intent, and notes when useful.
4. Keep each beat anchored in a visible event, proof point, or emotional turn. Avoid generic lines that could fit any product.
5. Produce at least one sharper alternate hook when the first 3 seconds matter, especially for social, ads, launch clips, and homepage videos.
6. End with a concrete next action. Match the CTA to the channel: visit, sign up, book, join waitlist, watch demo, reply, or share.

## Script Standards

- Start from the viewer's current pain, desire, or curiosity, not from the company's internal milestone.
- Use one controlling idea. If the brief has multiple messages, rank them and cut the rest into supporting beats or separate videos.
- Put names, UI states, proof, numbers, and concrete nouns on screen whenever possible.
- Let visuals carry explanation. Do not narrate what the viewer can plainly see.
- Write for spoken cadence: short sentences, clean turns, and no nested clauses in voiceover.
- Design for sound-off playback when the channel is social, paid, homepage, or in-product.
- Make captions and on-screen text complementary; do not duplicate full voiceover unless accessibility or platform norms require it.

## Output Formats

For new scripts, default to:

| Time | Audio / Dialogue | On-screen Text | Visual | Notes |
|---|---|---|---|---|

For founder or talking-head scripts, include:

- Cold open
- Main talking points
- Exact lines for the first 15 seconds
- Suggested pickups or alternate phrasings
- B-roll prompts

For revision requests, lead with the rewritten script, then list the material changes and unresolved assumptions.

## Handoff

When the script will proceed to production, include the next useful artifact:

- Use `$video-shot-sequencer` for a timed shot list.
- Use `$video-storyboarder` for frame-by-frame boards.
- Use `$video-production-planner` for shoot logistics and asset needs.
- Use `$video-editing-director` for edit notes, pacing, music, captions, and export direction.
- Use `$video-review` for pre-flight critique after an edit exists.
