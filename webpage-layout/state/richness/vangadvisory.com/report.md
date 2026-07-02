# visual-richness audit — https://vangadvisory.com/

**Verdict**: `BOLD`  ·  **Recipes applied**: `7/10` (70%)
**Generated**: 2026-05-11T04:29:02.886032Z

| Recipe | Applied | Hits | Notes |
|---|---|---|---|
| **R1** Full-bleed dark gradient band | ✅ | 3/3 | linear-gradient\([^)]+#0[0-9a-f]{5}, radial-gradient\([^)]+rgba\( |
| **R2** Big-number pull-quote moment | ✅ | 3/3 | \.bn-num\b|class=[\"']bn-num, font-size:\s*clamp\([^)]*[5-9]rem |
| **R3** Animated SVG mark (stroke-draw) | ✅ | 2/3 | stroke-dasharray, stroke-dashoffset |
| **R4** Animated gradient drop cap | — | 1/3 | not detected |
| **R5** Gradient mesh halo | ✅ | 3/3 | radial-gradient\([^)]+rgba\(, filter:\s*blur |
| **R6** Color-rich hover (lift + shadow) | ✅ | 3/3 | :hover[^{]*\{[^}]*transform:\s*translatey\([^)]*-[1-9], :hover[^{]*\{[^}]*box-sh |
| **R7** Scroll-triggered fade-ins (IntersectionObserver) | ✅ | 3/3 | intersectionobserver, fade-in-init|fade-in-visible |
| **R8** Typographic stat strip (anti-stencil) | ✅ | 3/3 | \.stat-band\b, border-top.*?var\(--rule\)|border-top:\s*1px |
| **R9** Editorial section ornament (§ on rule) | — | 0/3 | not detected |
| **R10** Editorial 'currently' sidebar callout | — | 0/3 | not detected |

## Reference
Recipes: `~/.claude/skills/webpage-layout/recipes/visual-richness.md`
Detection is heuristic (HTML/CSS pattern match, ~70% accuracy). False negatives more common than false positives.
Production reference (BOLD verdict expected): matteisn.com, vang.capital, vangadvisory.com.