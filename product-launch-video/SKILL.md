---
name: product-launch-video
description: Develop product launch videos from brief to creative strategy, concept, message, script, shot sequence, storyboard, production plan, edit direction, channel variants, measurement plan, and launch-ready assets. Use when planning or creating videos for feature launches, company launches, waitlists, funding/news moments, version releases, demos, hero homepage videos, social launch clips, Product Hunt assets, sales launch videos, or any launch-adjacent marketing video. Campaign-scoped orchestrator — for a quick 15–60s launch reel or demo clip defer to `product-video-skill` (owns first-touch), and route granular stages to the `video-scriptwriter` / `video-shot-sequencer` / `video-storyboarder` / `video-production-planner` / `video-editing-director` / `video-review` sub-skills rather than re-deriving them.
---

# Product Launch Video

## Verbs (run.py)

Headless entry points consumed by `launch-pack` Step 4 and `dogfood-walkthrough` Station 6:

- `python3 ~/.claude/skills/product-launch-video/run.py plan <slug>` — reads `~/zerg/<slug>/demo-video/shot-list.template.json`, `Growth/launches/<slug>.md` (brief frontmatter), and `Growth/measurement/<slug>.yaml`; writes `Growth/launches/<slug>/video-plan.md`. Accepts `--shot-list`, `--brief`, `--measurement`, `--out` overrides (compat with `launch-pack`), plus `--product <slug>` as an alias for the positional slug.
- `python3 ~/.claude/skills/product-launch-video/run.py audit <slug>` — verifies the rendered `video-plan.md` exists, the shot list parses, and the cited CTA event appears in the measurement spec's `required_events`.
- `python3 ~/.claude/skills/product-launch-video/run.py list` — enumerates per-product video plans at `Growth/launches/*/video-plan.md`.

## Output convention

- Canonical artifact: `MattZerg/Projects/Zerg-Production/Growth/launches/<slug>/video-plan.md`.
- CTA event sourced from `Growth/measurement/<slug>.yaml` → `kill_readiness_gate.must_emit_in_prod[0]` (falls back to `dashboard_bindings.line_1_activated_accounts`, then `<slug>_signup`).
- Deterministic string templates only — `run.py` never calls an LLM. For full creative work (script variants, storyboard, editing direction), invoke the orchestrating workflow below.

## Role

Use this as the orchestrating skill for product launch video work. It may call for `$video-scriptwriter`, `$video-shot-sequencer`, `$video-storyboarder`, `$video-production-planner`, `$video-editing-director`, and `$video-review` depending on how far the user wants to go.

For short 15-60s software product clips, route through `$product-video-skill` before rendering. `product-launch-video` owns the campaign/video-system strategy; `product-video-skill` owns the measured software-video craft bar: crop, pacing, motion recipes, caption doctrine, end cards, and pre-publish checks.

## Core Workflow

1. Extract the launch brief: product, audience, launch moment, promise, proof, constraint, channel, runtime, and CTA.
2. If the brief is thin, use `references/launch-brief-intake.md` to fill assumptions and mark hard unknowns.
3. Pick the launch video type or launch video system from `references/launch-video-types.md`.
4. Use `references/creative-strategy.md` when the request needs concept options, positioning, or a stronger reason for the video to exist.
5. Define the one-line thesis: "For [audience], [product] changes [old behavior] into [new behavior]."
6. Build the launch arc: hook, problem/context, reveal, proof, expansion, trust, CTA.
7. Use `references/video-pattern-library.md` to choose hook, proof, UI, and ending patterns when taste or format specificity matters.
8. For 15-60s software clips, read `$product-video-skill` before scripting or rendering. Use its measured reference catalog and motion recipes as the taste baseline.
9. For software product videos, use `references/software-product-motion-gate.md` before production. Decide whether the video is designed UI motion, polished live capture, or hybrid.
10. Draft the script in timed beats. Use `$video-scriptwriter` when the user mainly needs writing or variants.
11. Create a shot sequence. Use `$video-shot-sequencer` when visual order is the core task.
12. Create storyboard frames when composition, UI crop, animation, or shoot direction matters. Use `$video-storyboarder`. Do not skip keyframes for software-product motion.
13. Build a production plan when assets, screen states, talent, approvals, or deadlines are involved. Use `$video-production-planner` — its "Recording-Tool Routing" section is the source of truth for picking Screen Studio vs QuickTime/OBS vs ScreenFlow.
14. Specify edit direction, captions, sound, end card, aspect-ratio variants, and export requirements. Use `$video-editing-director`. For burned-in captions on the final render (mandatory on social cuts — corpus `caption-burn-discipline`), use the `caption-burn` skill as the post-assemble step (`run.py burn`); it composites brand-styled PNG overlays via ffmpeg.
15. Use `references/clip-slate-generator.md` when planning several 20-30 second clips around one anchor video.
16. Use `references/channel-versioning.md` before production if the launch has more than one distribution channel.
17. Use `references/measurement-plan.md` when the user asks how to evaluate the video, test variants, or connect it to launch performance.
18. After a draft render exists, use `$video-review` before showing or shipping.

## Launch-Specific Standards

- Lead with the external change, not the internal release.
- Show the product doing the hardest-to-believe thing early.
- Do not make launch videos into full tours; leave secondary features for follow-up clips.
- Use concrete UI states, customer language, benchmarks, quotes, or workflow before/after proof.
- Keep the CTA matched to the launch stage: waitlist, sign up, try, watch demo, book, read announcement, or share.
- Plan variants at the concept stage: 16:9, 9:16, 1:1, silent autoplay, homepage loop, launch post embed, and paid/social cutdowns as needed.
- When the brief implies both depth and distribution, plan a launch video system: one anchor video around 75-100 seconds plus several 20-30 second modular clips.
- Flag claims that need legal, customer, security, or product approval.
- Prefer one strong launch mechanic over a complete feature inventory.
- Make the first visual frame useful even when autoplay is paused.
- For software videos, never treat a raw proof recording as launch-ready just because the product action is real. Design the visual layer around the proof.
- Treat "AI-powered", "fast", "simple", "seamless", and "all-in-one" as unsupported until made concrete by product proof.

## Default Output

When the user asks broadly, produce:

1. Creative direction
2. Audience and thesis
3. Timed script
4. Shot sequence
5. Storyboard outline
6. Production needs
7. Edit direction
8. Channel variants
9. Measurement plan when relevant
10. Open questions and approval risks

Use `references/launch-package-template.md` for a production-bound package or when the user says "end to end", "full package", "launch video", "go", or similar.

Use the launch video system template plus `references/clip-slate-generator.md` when the user mentions multiple videos, short clips, launch campaign assets, a 90-second video plus shorter videos, or a need to support several channels/audiences.

Use `references/worked-example-launch-system.md` when a run needs a concrete model for the expected level of specificity.

Keep the first pass compact enough to be useful. Expand a section only when the user asks or the project is production-bound.

## Quality Gate

Score the package against `_style/video_quality_rubric.md` — use the per-craft section matching each artifact produced (Script / Storyboard / Sequence / Edit), and the Review section once a cut exists. A capped artifact (e.g. opens-on-chrome, no-captions-on-social, broken hero frame) does not ship until the cap clears. Then check:

- Does the core product transformation appear by the first third of the runtime?
- Could the first frame work as a thumbnail or paused social frame?
- Is every major claim supported by a visible product moment, customer proof, benchmark, or marked source need?
- For software-product motion, did we choose designed UI motion, polished live capture, or hybrid and document what is staged versus verified?
- Are keyframes/storyboards complete before rendering?
- Are the visual beats specific enough for a designer, editor, or screen recorder to act on?
- Are channel variants planned before production, not left as an afterthought?
- Is the first-frame, hook, CTA, and runtime adapted to each priority channel?
- Does each short clip have a distinct job, or are several clips just weaker duplicates?
- Is there a simple success signal tied to the launch goal?
- Are approval risks explicit?
