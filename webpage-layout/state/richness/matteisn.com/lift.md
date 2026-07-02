# richness-lift — https://matteisn.com

**Current**: `BOLD` (9/10 = 90%)
**Brand detected**: `matteisn` (navy=#273a96, accent=#0fbbbb)
**Top 1 missing recipes** (by visual-payoff priority):

- **R3** — Animated SVG mark (stroke-draw)

---

## Paste-ready CSS patch

Append to your stylesheet, replace generic class names (`.full-bleed-band` / `.cv-row` / `.hero` etc.) with your site's actual class names where noted.

```css
/* R3 — Animated SVG mark (stroke-draw on load) — requires SVG with stroked paths */
.brand-mark path,
.brand-mark circle {
  stroke-dasharray: 800;
  stroke-dashoffset: 800;
  animation: mark-draw 2.4s ease-out 0.3s forwards;
}
.brand-mark path:nth-of-type(2) { animation-delay: 0.7s; }
.brand-mark path:nth-of-type(3) { animation-delay: 1.0s; }
.brand-mark circle { animation: mark-pop 0.4s ease-out 1.8s backwards; }
@keyframes mark-draw { to { stroke-dashoffset: 0; } }
@keyframes mark-pop { 0% { opacity: 0; transform: scale(0.4); transform-origin: center; } 100% { opacity: 1; transform: scale(1); } }
@media (prefers-reduced-motion: reduce) {
  .brand-mark path, .brand-mark circle { animation: none; stroke-dashoffset: 0; }
}

```

---

## Reference
Full recipe library + symptom→recipe table: `~/.claude/skills/webpage-layout/recipes/visual-richness.md`

After applying, re-run `python3 ~/.claude/skills/webpage-layout/run.py richness https://matteisn.com` to verify the lift.