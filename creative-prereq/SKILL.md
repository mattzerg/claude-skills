---
name: creative-prereq
description: Hard pre-flight ritual before invoking ANY creative-generation tool (chatgpt-image-skill, blog-imagery, fakematt-email drafting from scratch, social copy gen, hero prompts, video shot lists). Forces source-reading, brainstorm-3-then-pick, memory-rule-check, prompt self-review BEFORE the tool fires. Operationalizes the "creative tasks need deliberate engagement" lesson from 2026-05-12 hero-image regen mess.
---


# Creative Pre-Flight Skill

Sibling to `pr-gate` (code), `send-gate` (email), `qa-gate` (engineering). This one gates **creative artifact generation** — image, prose, social copy, video plan.

## Anchors

This skill draws its voice and pattern catalog from:

- **Voice fingerprint:** inherits from the downstream creative tool's own anchor (e.g. `writing_style.md` for prose drafts, `feedback_hero_imagery_design_bar.md` for hero images) — the pre-flight ritual loads the per-artifact-type anchor automatically in Step 5.
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` — **primary reference for the pre-flight rituals**. Each Step 5 memory-rule-check should cite applicable pattern slugs from the catalog as part of the checklist's rule-compliance section.
- **Domain corpus:** per-artifact-type — see Step 2 of the ritual.
- **Catalog patterns to cite by slug** (Section A Universal / process): honest-scoping
- **Catalog patterns to cite by slug** (Section C Prose / writing): pulp-caption-discipline, cross-format-repetition
- **Catalog patterns to cite by slug** (Section E CRO / marketing): shipped-vs-roadmap-visibility, capability-claim-unverified
- **Catalog patterns to cite by slug** (Section G Viz / video): scorecard-deltas, demo-or-perish

Read these BEFORE producing output. Cite patterns by slug from the catalog.

## Why this exists

2026-05-12 — across one session I produced 4 boring AI heroes (v1 cosmic-abstract), then 4 lazy stat-cards (v2), then 4 split-frame "before/after" heroes (v3 — Matt: "boring"), then 4 atmospheric-generic heroes (v4 — fakeidan: "does not carry the specific thesis"), before finally landing a usable set on v5/v7 after Matt-and-Idan-style review forced the corrections. Pattern: I jumped from "make imagery" → "quick prompt" → "fire" without applying the rules that already existed in memory. Each round of failure was avoidable.

The fix isn't more rules (memory has ~50 HIGH PRIORITY ones already). The fix is **gating the lazy fast path at the tool layer** — a pre-flight ritual that runs BEFORE any creative tool, blocks invocation until the ritual completes, and forces the rules to be applied not just remembered.

Per `feedback_hero_imagery_design_bar.md` + `feedback_brand_anchor_vs_reference_heroes.md` + `feedback_imagery_tier_classification_strict.md` — those three rules together would have prevented every v1-v4 failure. They didn't because I treated them as "context to keep in mind" instead of a checklist to run.

## When to invoke

**Hard gate (MUST run before tool fires):**
- Before any `chatgpt-image-skill`, `nano-banana-pro`, `fal-image-skill`, `pollinations` invocation
- Before `blog-imagery` (which fans out the above)
- Before drafting prose from scratch via `fakematt-email`, `fakematt-slack`, `fakematt-personal` (NOT for reviewing existing prose — those are gates not generators)
- Before `social-distribution` agent for first-pass social drafts
- Before `video-scriptwriter` / `video-storyboarder` first drafts

**Skip when:**
- Iterating on an EXISTING artifact based on user feedback (the prior pre-flight already happened — just fire the iteration)
- Running review-mode skills (`fakematt-copyedit`, `fakeidan`, `graphic-layout`, `cro-auditor`) — those are gates, not generators
- The tool invocation is mechanical (e.g. re-rendering an approved SVG, propagating a hero to twitter/li variants)

## CLI

```bash
# Start a new pre-flight checklist for an artifact
python3 ~/.claude/skills/creative-prereq/run.py prepare <artifact-type> --slug <slug> [--source <path>]

# artifact-type = hero-image | prose-draft | social-copy | video-shot-list | other

# Validate that a checklist is fully filled in (no [TO FILL] markers remaining)
python3 ~/.claude/skills/creative-prereq/run.py validate <checklist-path>
```

## The ritual (what `prepare` emits as a checklist)

Each checklist has these required sections — every `[TO FILL]` must be filled before the artifact tool fires:

### Step 1: Read the source
- Read the full post body / brief / spec
- Identify the central mechanism the article describes (one sentence)
- Identify the visceral image a reader would sketch after reading (one phrase)

### Step 2: Read the reference set
- For hero-image: Read at least 3 of {build-now-hero, alphaevolve-hero, business-velocity-hero, agents-that-remember-hero}.png
- For prose-draft: Read the corresponding `_style/*.md` anchor + 2 voice corpus samples
- For social-copy: Read the source post + 2 prior social posts on the same channel
- Note observed brand/voice register (one paragraph)

### Step 3: Brainstorm 3 concepts
Each concept must:
- Have one dominant element (NOT split-frame / NOT abstract concept-prompts)
- Be specific enough to fail Cap Test #2 (can NOT be a hero/draft/post for ANY OTHER article)
- Show the MECHANISM the article describes, NOT just the AESTHETIC of the topic

### Step 4: Pick one + write WHY
The WHY must reference the article's specific mechanism, NOT just "this looks good" or "this fits the brand."

### Step 5: Check against memory rules (auto-loaded per artifact-type)
Hero-image checklist auto-loads:
- `feedback_hero_imagery_design_bar.md` — Cap Tests #1-#4
- `feedback_imagery_tier_classification_strict.md` — Tier 1 vs Tier 2
- `feedback_brand_anchor_vs_reference_heroes.md` — Brand register is RICH not minimalist
- `feedback_blog_imagery_coherence.md` — Hero + body language must MATCH

Prose-draft checklist auto-loads:
- `_style/voice_universals.md`
- The per-surface style anchor (writing_style.md / professional_voice.md / etc.)
- `feedback_minimize_prs.md` if applicable

### Step 6: Write the prompt
200-300 words for hero. ~100 words for social. Article-specific. Show mechanism.

### Step 7: Pre-flight self-review (cap tests)
- Cap Test #1 (split-frame): no "LEFT/RIGHT" or "vs" in the prompt
- Cap Test #2 (specificity): "would this work for any OTHER article?" If yes → REJECT
- Cap Test #3 (mechanism): "does the prompt show the article's mechanism or just the topic's aesthetic?"
- Cap Test #4 (brand): wider palette + richer detail (not "minimalist cosmic")

### Step 8: Fire
Only after Steps 1-7 are complete. Tool invocation + output path logged.

### Step 9: Post-fire visual review
- Open rendered artifact
- Apply Cap Tests #2 and #3 to the rendered output
- Run a review skill (fakeidan / graphic-layout / fakematt-copyedit) on the rendered artifact
- Decision: accept / iterate / reject

## Validation rule

The `validate` mode greps the checklist for `[TO FILL]` markers. If ANY remain, validation FAILS and the tool should not fire. Each section step is a separate validation block — you can pass Step 1-4 and fail Step 5, in which case fire is blocked at Step 5.

## Anti-patterns this catches

- Lazy split-frame prompts ("LEFT: passive. RIGHT: active.") — Cap Test #1
- Atmospheric-generic prompts ("cosmic abstract data-flow") — Cap Test #2
- Aesthetic-not-mechanism prompts ("wind-carved landscape" for an article about active agent decisions) — Cap Test #3
- "Minimalist navy + amber" prompts when references show richer palette range — Cap Test #4
- Treating memory rules as context-to-keep-in-mind instead of checklist-to-apply — entire ritual

## Output

Checklists land at `/tmp/creative-prereq/<slug>-<artifact-type>.checklist.md`. Each run logs to `~/.claude/creative-prereq/log.jsonl` so the discipline can be measured.

## Implementation status

v1 (this commit): SKILL.md + run.py + checklist templates. Discipline is enforced by author (me) reading the checklist before firing. No automated hook yet.

v2 (followup): Add a hook to `~/.claude/settings.json` PreToolUse for `Bash` invocations matching the creative-tool path patterns, which checks for a fresh, complete `creative-prereq` checklist before allowing the bash to run.
