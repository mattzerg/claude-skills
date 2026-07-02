---
name: ship-gate
description: Block or clear a page, launch, dashboard, asset, video, or workflow for shipment by checking the required review artifacts, readiness signals, measurement path, and unresolved blockers. Use before publishing, sending, launching, or declaring something ready — run AFTER review-pack has produced the review artifacts (review-pack reviews; this skill gates).
---


# Ship Gate

This skill is the final readiness gate above the review stack. It does not replace `review-pack`, `launch-ops`, `cro-auditor`, `dashboard-spec`, or `experiment-designer`. Its job is to decide whether the artifact is actually ready to ship, what evidence is missing, and what blocks a clean `go`.

## When to invoke

- "Is this ready to ship?"
- "Run the final gate on this launch / page / dashboard / asset"
- "What still blocks publish?"
- "Give me the go / no-go call"
- Before publishing a marketing page, launch, public dashboard, experiment, one-pager, graphic asset, or product video

Use it when the review work may already exist but the actual readiness decision is still fuzzy.

## What this skill does

1. **Classifies the artifact and ship type**
2. **Names the required passes and evidence**
3. **Checks blockers across copy, product, measurement, assets, and ops**
4. **Returns a gate verdict**
5. **Defines the exact path to green**

## Canonical execution path — run.py

The mechanical `tools/*.py` checks run through `run.py`; never invoke them
individually when gating — the runner is fail-closed (a tool crash, timeout,
or unparseable output becomes a synthetic HIGH finding and the verdict is RED,
so silence can never pass as approval; posture from `pr-gate/run.py`). The
judgment rubric below stays with the model: required evidence, blocker
severity, and path-to-green are still yours to reason about — `run.py` only
supplies the mechanical evidence.

```bash
python3 ~/.claude/skills/ship-gate/run.py <artifact-path-or-url> \
    [--type page|pdf|image|launch|blog] [--json] [--timeout SECS]
```

- **Applicability map**: URL page/launch → `check_richness.py` +
  `check_palette.py audit`; local page → `check_palette.py classify` +
  `check_brand_hex_literals.py`; blog `.md` → `check_blog_imagery_coherence.py`
  + `check_metadata_drift.py`; pdf/image asset → `check_palette.py classify`
  (covers landing-page and one-pager renders). `--type` defaults to inference
  from the artifact.
- **Verdict**: GREEN (no findings) / YELLOW (MEDIUM only) / RED (any HIGH or
  fail-closed). Exit codes: 0 GREEN, 1 RED, 2 YELLOW.
- `--timeout` defaults to 30s per check; `check_richness.py` against slow
  pages may need `--timeout 180`.
- `--json` emits the manifest — cite it as the mechanical-evidence artifact in
  the gate verdict.

## Gate classes

### 1. Marketing page / signup page / pricing page

Require:
- `review-pack` routing or equivalent review plan
- `cro-auditor` findings
- `fakematt-copyedit` if meaningful prose is present
- `graphic-layout` if rendered assets are part of the page
- `tools/check_richness.py <url>` — visual-richness R1–R10 audit (block <4/10)
- `tools/check_palette.py audit <url>` — dual-palette routing per `feedback_zerg_brand.md`
- `tools/check_brand_hex_literals.py --diff <base>` — flag inline `bg-[#brand-hex]` Tailwind literals (regression guard for the 2026-05-11 codemod sweep; use named tokens per `MattZerg/Projects/Zerg-Production/Zstack/brand-tokens.md`)

Must be green on:
- message clarity
- CTA path
- proof / trust
- measurement path
- visual richness — fewer than 4 of R1–R10 applied is a hard block on external ship
- palette routing — cream for Zstack/non-tech, charcoal for Zerg-parent/technical

### 2. Launch

Require:
- `fakematt-launch`
- `launch-ops`
- `cro-auditor` on the destination path
- `launch-announcement` if a launch post exists
- asset reviews (`graphic-layout`, `video-review`) when relevant

Must be green on:
- source-of-truth state
- owner map
- CTA path
- measurement readiness
- asset readiness

### 3. Dashboard / public analytics / reporting readout

Require:
- `dashboard-spec`
- `ui-designer` if the reporting surface itself is being built
- `launch-ops` if the dashboard is part of a launch

Must be green on:
- metric definitions
- event instrumentation
- owner and read cadence
- freshness target
- public-safe exposure, if external

### 4. Experiment

Require:
- `experiment-designer`
- `dashboard-spec` if metrics or events are not already explicit
- `cro-auditor` or `fakematt-feedback` when the test came from audit work

Must be green on:
- controlled comparison
- success metric
- kill threshold
- sample target
- confounder check

### 5. Asset / one-pager / video

Require:
- `graphic-layout` for rendered still assets
- `video-review` for product videos
- `fakematt-copyedit` when substantial text is in the artifact
- `tools/check_palette.py classify <surface>` if the asset will land on a Zerg surface — verify the design uses the routed palette before render

Must be green on:
- composition
- text accuracy
- format readiness
- channel-fit
- palette match for the destination surface

### 6. Blog post

Require:
- `fakematt-copyedit` on the prose
- `blog-imagery` for the asset bundle (or hand-rendered SVG set for technical posts)
- `tools/check_blog_imagery_coherence.py <md-path>` — body-SVG posts must use SVG-coded hero/LI/X
- `tools/check_metadata_drift.py <slug>` — body MD ↔ `.ts` excerpt ↔ `seo.description` ↔ alt-text alignment

Must be green on:
- imagery coherence — Tier 1 (SVG) and Tier 2 (AI imagery) cannot mix on one post
- metadata alignment — high-confidence proper-noun drift between body and `.ts` is a hard block; copy-paste excerpt/seo.description is yellow
- author routing per `feedback_blog_author_routing.md`
- distribution channel selection per `feedback_blog_vs_product_launch_distribution.md`

## Output shape

Return:

1. **Artifact type**
2. **Required evidence**
3. **Gate status** — `green`, `yellow`, or `red`
4. **Blocking issues**
5. **Exact path to green**
6. **Ship note** — what can be shipped now, if anything

## Gate status rules

- `green` — required evidence exists, no unresolved ship blockers remain
- `yellow` — artifact is usable for internal review or limited circulation, but external ship blockers remain
- `red` — missing required evidence or known blockers make ship unsafe

## Anchors

- `references/ship_gate_patterns.md`
- `tools/README.md` — runnable brand-discipline checks (richness, imagery coherence, metadata drift, palette routing)
- `review-pack` for the expected review stack
- `launch-ops` for launch readiness state
- `dashboard-spec` for metric and instrumentation readiness
- `experiment-designer` for experiment discipline

This gate inherits voice and pattern from the skills it orchestrates (review-pack, launch-ops, dashboard-spec, experiment-designer, cro-auditor, fakematt-*, fakeidan, graphic-layout, video-review). References:

- Voice index: `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_voice_patterns.md`
- Pattern catalog: `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md`
- Upstream skills' own anchors apply transitively.
- **Catalog patterns to cite by slug** (Section A Universal / process): honest-scoping
- **Catalog patterns to cite by slug** (Section B UI / product design): cherry-on-top
- **Catalog patterns to cite by slug** (Section E CRO / marketing): shipped-vs-roadmap-visibility, proof-gap, missing-cta, hero-clarity
- **Catalog patterns to cite by slug** (Section G Viz / video): scorecard-deltas, demo-or-perish
- **Catalog patterns to cite by slug** (Section I Launch / deck): deferred-with-reason, one-product-at-a-time

Findings surfaced by this gate should cite pattern slugs from the catalog.

## Working rules

- Separate **review complete** from **ship ready**. An artifact can be well-reviewed and still not be ready.
- Name the evidence artifact you are relying on: review markdown, launch runbook, dashboard spec, experiment doc, screenshot set, or video report.
- Treat broken CTA paths, missing instrumentation, unresolved proof claims, or absent owners as real blockers.
- For external-facing artifacts, check whether the broader positioning claim is supported by proof, not just whether the prose sounds good.
- Prefer a small blocker list with explicit fixes over a vague long punch list.
- If the artifact is only safe for internal circulation, say so plainly.

## Hard rules

- Do not declare `green` if a required review pass has not happened.
- Do not declare `green` if the measurement path for the primary success outcome is blind.
- Do not collapse `yellow` and `red`; distinguish "not polished enough" from "unsafe to ship."
- Do not treat channel adaptation or asset polish as the only issue when the underlying claim is unproven.
- Do not invent evidence. If proof, metrics, approvals, or asset reviews are missing, block the ship.

## Relationship to sibling skills

- `review-pack` — defines the right review sequence
- `launch-ops` — operational launch readiness
- `dashboard-spec` — reporting and metric readiness
- `experiment-designer` — experiment readiness
- `cro-auditor` — funnel readiness
- `graphic-layout` / `video-review` — asset pre-flight

## History

- 2026-07-02 — resolved the 2026-05-09 deferred palette wiring: both hook
  targets (`landing-page-skill/SKILL.md`, `one-pager-skill/SKILL.md`) exist,
  and the hook now lives in `run.py`'s applicability map instead of per-skill
  SKILL.md references — `check_palette.py classify` fires for page, pdf,
  image, and launch artifacts, which covers landing-page and one-pager
  outputs at gate time.
