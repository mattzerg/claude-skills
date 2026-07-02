---
name: swag-design
description: Design and review branded company swag, merch mockups, production artwork, vendor specs, and multi-item review PDFs. Use when Codex needs to place logos or campaign graphics on apparel, mugs, stickers, notebooks, hats, lanyards, patches, launch boxes, or other physical merchandise, especially when logo hierarchy, item-specific placement, print constraints, or vendor-ready files matter.
---

# Swag Design

Create swag as a product design system, not as flat graphics pasted onto objects. Always separate three deliverables: item mockups for review, production artwork for vendors, and a brief/spec that explains placement, materials, and print methods.

## Workflow

1. Gather brand assets and constraints:
   - Full logo/wordmark, compact mark, campaign graphic, palette, typography, and any exact text.
   - Item list, likely vendor/print method, quantity tier if known, and whether the output is concept-only or vendor-ready.
2. Build the item hierarchy before drawing:
   - Decide what each object should communicate at first glance.
   - Assign one primary brand element per item. Use the full logo somewhere, but do not let it fight the campaign graphic.
   - Place logos based on object anatomy: chest, cuff, hem, lid, handle side, spine, clasp, patch field, sticker backing.
3. Create item-specific mockups:
   - Show the artwork on realistic item silhouettes at believable scale.
   - Include enough item context that placement can be judged.
   - Do not use floating logos, arbitrary corners, or huge marks that ignore seams, folds, handles, brims, or print zones.
4. Create production artwork:
   - Keep exact text as editable text until final vendor export.
   - Use separate files for sticker, shirt print, embroidery, mug wrap, notebook cover, etc.
   - Include colors, dimensions, safe areas, and print method notes.
5. Run the placement gate before finalizing:
   - Read `references/placement-gate.md`.
   - Run `scripts/mockup_preflight.py <mockup-or-folder>`.
   - Treat any HIGH finding as a blocker; revise and rerun before rendering a review PDF or telling the user the asset is ready.
   - Fix any high-risk placement issues before presenting.
6. Package review:
   - Use `scripts/scaffold_swag_project.py` for a consistent folder layout when starting a new set.
   - Export one review PDF with item mockups first and production art second.

## Placement Rules

- Full logo requirement: If the user asks for the full logo on each item, place it in a secondary brand zone, not as a random overlay.
- Apparel: Put full logo at neck label, sleeve, hem tag, small chest, or back yoke when the front graphic is the hero.
- Hoodies: Respect zipper, pouch pocket, drawstrings, and chest anatomy. Use small embroidery on left chest or sleeve; avoid placing tiny detailed terminal art where embroidery cannot hold detail.
- Hats: Use compact mark on front; full wordmark can go on side/back strap, woven side label, or under-brim print.
- Mugs: Design around handle orientation. Put hero art opposite handle; full logo can sit on the handle side, inner rim, or under the command panel.
- Stickers: Use full logo on sticker backing, sheet header, or a secondary lockup inside the terminal header. Do not crowd the command text.
- Notebooks: Use spine, belly band, back cover, or corner stamp for logo; keep cover hero clean.
- Lanyards/keycards: Repeat logo on strap at intervals; put campaign graphic on badge/card face only if legible at small size.
- Patches: Simplify aggressively; full logo may need to become woven label text rather than full vector detail.

## File Standards

- Prefer editable SVG masters for deterministic text and geometry.
- Use bitmap image generation only for photorealistic concept mockups, not for final print text.
- Preserve exact user-provided text. Check visual text rendering, not just source text.
- Keep mockup files separate from production art files.
- If raster previews are needed, render from SVG and inspect at review size.
- Never open or present a review PDF until source preflight is clean of HIGH findings and the rendered contact sheet has been visually inspected.

## Resources

- `references/placement-gate.md`: mandatory preflight checklist for logo placement and merch realism.
- `references/mockup-quality-gate.md`: automatic and visual review rules for obvious mockup failures.
- `references/item-zones.md`: item-specific zones, hierarchy patterns, and print-method cautions.
- `scripts/scaffold_swag_project.py`: creates a vendor/review-ready project folder scaffold.
- `scripts/mockup_preflight.py`: fails on easy-to-detect SVG bleed, clipping, logo-in-hero misuse, and missing item anatomy.
