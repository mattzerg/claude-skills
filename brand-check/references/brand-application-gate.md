# Brand Application Gate

## Required Checks

1. Approved asset use:
   - Full logo and compact mark come from the approved logo files or match them exactly.
   - No stretched, outlined, shadowed, individually recolored, or improvised logo.
2. Logo hierarchy:
   - The brand mark/wordmark has a clear role: signature, issuer, seal, or hero.
   - If a campaign graphic is the hero, the full logo is secondary and placed in a stable brand zone.
3. Clear space and contrast:
   - Logo has breathing room at least proportional to the mark height.
   - White logo only appears on dark/high-contrast surfaces.
   - Dark/currentColor logo only appears on light/high-contrast surfaces.
4. Placement credibility:
   - Logo placement follows the medium’s anatomy: garment zones, object faces, handle orientation, page margins, slide grid.
   - No arbitrary corner placement unless the corner is an established brand/signature zone.
5. Palette:
   - Colors are from approved tokens or clearly intentional extensions.
   - Avoid generic AI purple/blue gradients unless brand-approved.
6. Typography:
   - Use approved fonts when known.
   - Exact text is visually readable and not clipped, merged, or distorted.
7. System consistency:
   - Multi-asset sets share spacing, scale logic, line weights, and logo treatment.
   - Repetition should feel like a system, not copy/paste.
8. Production context:
   - Detail level matches print method and physical size.
   - Vendor-safe areas are respected.

## Common Failure Patterns

- Full logo added only because requested, with no placement strategy.
- Brand mark and wordmark duplicated too many times on the same small object.
- Logo placed above the hero graphic on apparel, causing a “conference sponsor” look.
- Full logo inserted inside the campaign graphic and also outside it, creating redundancy.
- Text/wordmark appears correct in SVG but is visually too small or clipped in preview.
- Off-brand mockup background or generic presentation style changes brand feel.

## Automatic Preflight For Swag

For SVG-based swag mockups, run the `swag-design` preflight before delivering:

```bash
python3 ~/.codex/skills/swag-design/scripts/mockup_preflight.py <mockup-folder>
```

Treat HIGH findings as blockers. This catches source-level bleed, clipped text, full logos inside terminal/campaign hero groups, redundant wordmarks, rotated wordmark risk, and missing item anatomy markers.
