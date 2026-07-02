---
name: brand-check
description: 'Review rendered graphics, SVGs, swag mockups, slide pages, PDFs, landing-page screenshots, and collateral for brand application quality. Use when Codex needs to audit logo usage, wordmark placement, brand hierarchy, palette, typography, spacing, asset consistency, or production-context fit against an existing brand guide before shipping or presenting visuals.'
---

# Brand Check

Run a brand-application QA pass. This skill is the layer between pure composition review and product/content review: it asks whether the visual uses the brand system correctly, credibly, and consistently in context.

## Anchors

This skill draws its voice and pattern catalog from:

- **Voice fingerprint:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_considered_voice.md`
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md`
- **Domain corpus:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/brand_feedback_corpus.md`
- **Catalog patterns to cite by slug** (Section B UI / product design): ui-weight-vs-importance
- **Catalog patterns to cite by slug** (Section C Prose / writing): body-caption-mismatch
- **Catalog patterns to cite by slug** (Section E CRO / marketing): shipped-vs-roadmap-visibility, capability-claim-unverified
- **Catalog patterns to cite by slug** (Section F Brand): brand-color-restraint, umbrella-naming, brand-token-codemod, theme-prop-vs-route-sniff
- **Catalog patterns to cite by slug** (Section G Viz / video): scorecard-deltas

Read these BEFORE producing output. Cite patterns by slug from the catalog.

## Workflow

1. Load source brand rules:
   - Prefer the project’s `brand-guide.md`, design tokens, logo files, or existing approved collateral.
   - If no brand guide exists, infer cautiously from approved assets and state the uncertainty.
2. Inspect the rendered asset and source when available:
   - Rendered PNG/PDF catches visual collisions and poor hierarchy.
   - SVG/HTML/source catches exact colors, text, logo file choices, and hidden asset misuse.
3. Run the brand gate:
   - Read `references/brand-application-gate.md`.
   - For physical goods, also use `swag-design`; run its `scripts/mockup_preflight.py` when SVG mockups are available.
   - For composition-only issues, pair with `graphic-layout`.
4. Produce findings first:
   - Order by severity.
   - Cite the violated brand rule or inferred approved pattern.
   - Include concrete fix directions, not generic taste comments.
5. Decide whether to patch:
   - If the user asked to review, do not edit unless asked.
   - If the user asked to fix or make production-ready assets, revise and re-run the gate.

## Review Categories

- Logo usage: correct asset, scale, clear space, contrast, full-logo vs mark hierarchy, no distortion.
- Placement: logo sits in a believable brand zone for the medium; not pasted into arbitrary whitespace.
- Brand hierarchy: one hero idea; brand attribution supports rather than competes.
- Palette: approved colors, sufficient contrast, no off-brand defaults or accidental AI/purple gloss.
- Typography: approved families or credible fallback; exact text is legible at review and real size.
- Layout fit: brand elements respect object/page anatomy, margins, safe areas, and production zones.
- Consistency: repeated assets share a system without becoming mechanically identical.
- Production readiness: print method, embroidery detail, die-cut tolerance, mug handle safe area, slide export constraints.

## Fail-Closed Rules

- Do not call a physical-goods mockup “ready” if the swag preflight has HIGH findings.
- Do not present a review PDF if a rendered preview visibly has logos bleeding off items, labels hidden by silhouettes, or an item silhouette that is the wrong object type.
- When the issue is deterministic and the correction is obvious, patch it before responding rather than merely reporting it.

## Severity

- HIGH: Would make the asset look unprofessional, off-brand, unreadable, physically implausible, or vendor-risky.
- MEDIUM: Credible direction but needs hierarchy, spacing, scale, or consistency corrections.
- LOW: Polish, optional system refinement, or minor preference.

## Output Format

Use this structure:

```markdown
Findings
- HIGH — [short issue]. Rule: [brand rule/category]. Evidence: [asset/location]. Fix: [specific action].
- MEDIUM — ...

Open Questions
- [Only include if needed.]

Brand Verdict
[Pass / Needs revision / Blocked], with one sentence.
```

## Resources

- `references/brand-application-gate.md`: core checklist for brand QA.
- `references/medium-specific-branding.md`: placement and production notes by medium.
- `scripts/scan_svg_brand_tokens.py`: optional SVG scanner for colors, image references, and text strings.
