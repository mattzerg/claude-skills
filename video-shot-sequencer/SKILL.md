---
name: video-shot-sequencer
description: Turn a video concept, script, product brief, or raw footage idea into a timed shot sequence, beat sheet, b-roll plan, screen-recording plan, or visual order for product launch videos, demos, ads, explainers, founder announcements, social clips, case-study videos, brand films, and general video projects. Use when Codex needs to decide what the viewer sees, in what order, for how long, and why.
---

# Video Shot Sequencer

## Read before sequencing (measured anchors)

Load these on every run. Don't sequence on vibes when a measured value exists:

1. `references/sequence-techniques.md` — measured ordering catalog: per-beat duration budgets (UI 3–4s vs talk 1.5–2.5s), cut cadence by format, named ordering patterns, b-roll-to-hero ratio.
2. `_style/video_feedback_corpus.md` — Matt's taste layer; it wins over generic convention. Cite slugs (`pacing`, `shot-list-coverage`, `product-as-the-product`).
3. `~/.claude/skills/product-video-skill/techniques.md` — canonical shot recipes (§2) and MSL data (§3); cite, don't restate.
4. Score the sequence against `_style/video_quality_rubric.md` (Sequence section) and end the output with a one-line self-score — `Self-score: NN/100 (Sequence) — cap: none|<reason>`.

## Core Workflow

1. Identify the required arc: hook, setup, reveal, proof, expansion, close.
2. Convert every script beat into a visual beat. If a line has no visual event, rewrite the line or add a proof shot.
3. Choose the shot grammar from `references/shot-grammar.md` when the category is clear.
4. Sequence shots for comprehension first, energy second. Do not chase fast cuts if the product action needs time to read.
5. Mark source requirements for each shot: screen recording, live action, motion graphic, stock, still, screenshot, generated asset, or pickup.
6. Include edit intent: transition type, pace, emphasis, caption dependency, and whether the shot must work silently.
7. For software product clips, distinguish proof source from visual treatment. A shot can be proof-backed even when the final visual is a stylized UI rebuild.

## Timing Rules

- Hook: 0-3 seconds for social, ads, launch teasers, and homepage hero loops.
- Product proof: show the core transformation by 5-15 seconds when runtime is under 60 seconds.
- UI demos: hold long enough for the viewer to understand state change; use zooms or crops instead of tiny full-screen UI.
- Stylized UI demos: show one readable mechanic, then hold the completed state long enough for the claim to land.
- Talking head: cut to b-roll before the speaker explains abstractly for too long.
- End card: leave time for brand, CTA, and URL or product name to be read.

## Default Output

| Time | Shot | Visual Source | Audio / Copy | Edit Intent | Production Notes |
|---|---|---|---|---|---|

After the table, add:

- Missing assets
- Risky shots
- Suggested pickups
- Alternate opening sequence when first-frame performance matters

## Handoff

Use `$video-storyboarder` when shots need frame composition, `$video-production-planner` when shots need crews/assets/locations, and `$video-editing-director` when footage or renders need post-production direction.
