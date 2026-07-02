# visual-richness audit — https://zergboard-preview.pages.dev/

**Verdict**: `EDITORIAL-LEAN`  ·  **Recipes applied**: `2/10` (20%)
**Generated**: 2026-05-10T04:00:20.744160Z

| Recipe | Applied | Hits | Notes |
|---|---|---|---|
| **R1** Full-bleed dark gradient band | — | 1/3 | not detected |
| **R2** Big-number pull-quote moment | — | 1/3 | not detected |
| **R3** Animated SVG mark (stroke-draw) | — | 0/3 | not detected |
| **R4** Animated gradient drop cap | — | 0/3 | not detected |
| **R5** Gradient mesh halo | ✅ | 2/3 | filter:\s*blur, ::before |
| **R6** Color-rich hover (lift + shadow) | — | 0/3 | not detected |
| **R7** Scroll-triggered fade-ins (IntersectionObserver) | — | 1/3 | not detected |
| **R8** Typographic stat strip (anti-stencil) | ✅ | 2/3 | border-top.*?var\(--rule\)|border-top:\s*1px, display:\s*flex |
| **R9** Editorial section ornament (§ on rule) | — | 0/3 | not detected |
| **R10** Editorial 'currently' sidebar callout | — | 0/3 | not detected |

## Reference
Recipes: `~/.claude/skills/webpage-layout/recipes/visual-richness.md`
Detection is heuristic (HTML/CSS pattern match, ~70% accuracy). False negatives more common than false positives.
Production reference (BOLD verdict expected): matteisn.com, vang.capital, vangadvisory.com.