# Visual Richness Recipe Library

Pull from this when a site is graded "very simple" / low color presence / no motion / one-layer-deep. Each recipe has: corpus example URLs, the CSS implementation, the brand-token mapping, and gotchas.

Use these in priority order — biggest visible payoff first.

---

## R1. Full-bleed dark gradient band

**The single biggest "more eye-catching" lift.** Breaks the all-paper feel of editorial sites by introducing a dramatic colored panel — usually at the bottom (cross-link / footer area) or as a section transition.

**Corpus exemplars** that use this pattern:
- mercury.com — dark navy hero with neon accent strokes
- linear.app — gradient mesh full-bleed sections
- vercel.com — gradient hero band
- ramp.com — colored full-bleed strips between sections
- modal.com — gradient meshes throughout

**Recipe (CSS):**
```css
.full-bleed-band {
  margin: 6rem 0 0;                     /* breaks out of constrained main */
  padding: 4rem var(--gutter) 4.5rem;
  background: linear-gradient(135deg, #050b25 0%, var(--navy) 50%, var(--accent) 130%);
  position: relative;
  overflow: hidden;
}
.full-bleed-band::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 88% 18%, rgba(<accent-rgb>,0.34) 0%, transparent 40%),
    radial-gradient(circle at 8% 92%, rgba(<secondary-rgb>,0.18) 0%, transparent 45%),
    radial-gradient(circle at 50% 50%, rgba(255,255,255,0.04) 0%, transparent 60%);
  pointer-events: none;
}
.full-bleed-band > * { max-width: 56rem; margin: 0 auto; position: relative; z-index: 1; }
```

**Cards inside the band** use glass-morph treatment:
```css
.full-bleed-band a {
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.04);
  backdrop-filter: blur(2px);
  transition: border-color 0.2s, transform 0.2s, background 0.2s, box-shadow 0.2s;
}
.full-bleed-band a:hover {
  border-color: var(--accent);
  transform: translateY(-3px);
  background: rgba(<accent-rgb>,0.10);
  box-shadow: 0 12px 28px rgba(<accent-rgb>,0.20);
}
```

**Brand-token mapping:**
- matteisn (Eisner): `--accent: #0fbbbb` (teal), `--secondary: #0e7490` (teal-text)
- vang (capital + advisory): `--accent: #4b04af` (purple), `--secondary: #0ea5a5` (teal)
- zerg (cream paper): `--accent: #b3662f` (burnt-orange), `--secondary: #6FBE31` (brand-green)

**Gotchas:**
- The `margin: 6rem 0 0` requires the band to be a sibling of `<main>`, not inside it. If your `<main>` has `max-width`, the band must be positioned outside that wrapper or the trick is `margin: 0 calc(50% - 50vw)` to break out.
- `backdrop-filter: blur` doesn't render in some older browsers — degrades gracefully to flat translucent bg.
- WCAG: white text on dark navy is fine, but accent-color text needs verification (aim 4.5:1 on the gradient's mid-tone, not the lightest).

---

## R2. Big-number pull-quote moment

**The mid-page typography anchor.** Pull the single most impressive stat, render it OVERSIZED in brand gradient, pair with editorial italic context.

**Corpus exemplars:**
- stripe.com — "1,200,000+ businesses" hero stat
- plaid.com — "8,000+ apps" callout
- ramp.com — big number sections
- mercury.com — "$X+ deposits" stats

**Recipe (HTML):**
```html
<section class="big-number" aria-label="Headline number">
  <div class="bn-row">
    <p class="bn-num">$0&rarr;$60<em>m</em></p>
    <div>
      <span class="bn-tag">Most recent</span>
      <p class="bn-label">TVL scaled at <strong>Dinari</strong> in 18 months — from $0 to $60m+ at 100%+ MoM.</p>
    </div>
  </div>
</section>
```

**Recipe (CSS):**
```css
.big-number {
  margin: 5rem 0;
  padding: 3.5rem 2.5rem;
  background: linear-gradient(135deg, var(--paper) 0%, var(--section-bg) 100%);
  border-left: 5px solid var(--accent);
  border-radius: 0 8px 8px 0;
  position: relative;
  overflow: hidden;
}
.big-number::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 92% 12%, rgba(<accent-rgb>,0.10) 0%, transparent 50%),
    radial-gradient(circle at 8% 88%, rgba(<navy-rgb>,0.06) 0%, transparent 55%);
  pointer-events: none;
}
.bn-row { display: grid; grid-template-columns: minmax(0,auto) minmax(0,1fr); gap: 2rem; align-items: center; position: relative; z-index: 1; }
.bn-num {
  font-family: var(--serif);
  font-weight: 600;
  font-size: clamp(4rem, 9vw, 7rem);
  line-height: 0.9;
  letter-spacing: -0.04em;
  margin: 0;
  background: linear-gradient(135deg, var(--navy) 0%, var(--accent-text) 60%, var(--accent) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-feature-settings: "tnum" 1, "lnum" 1;
}
.bn-num em { font-style: italic; font-weight: 500; font-size: 0.55em; letter-spacing: -0.02em; }
.bn-label { font-family: var(--serif); font-style: italic; font-size: clamp(1.15rem,1.7vw,1.4rem); color: var(--navy-soft); margin: 0; max-width: 32ch; }
.bn-tag { display: inline-block; font-family: var(--headline); font-size: 0.72rem; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; color: var(--accent-text); margin-bottom: 0.85rem; }
@media (max-width: 700px) { .big-number { padding: 2.5rem 1.5rem; } .bn-row { grid-template-columns: 1fr; gap: 1rem; } }
```

**Gotchas:**
- Don't duplicate stats from the existing stat-band — the big-number should be the SINGLE most impressive number, not a repeat.
- `<em>` inside `.bn-num` for unit suffixes ("m", "+", "%") gives a tasteful smaller italic without breaking the gradient text-clip. The `background: inherit` trick on `em` keeps the gradient flowing.
- On mobile collapse the grid to 1 column; keep the gradient num oversized but reduce padding.

---

## R3. Animated SVG mark (stroke-draw on load)

**Hero element brand-mark animation.** The geometric SVG mark draws stroke-by-stroke as the page loads. Editorial-bold without being distracting.

**Corpus exemplars:**
- linear.app — animated logo on hero load
- mercury.com — animated path strokes
- framer.com — heavy motion

**Recipe (CSS, given an SVG with `<path>` and `<circle>` children):**
```css
.brand-mark path,
.brand-mark circle {
  stroke-dasharray: 800;
  stroke-dashoffset: 800;
  animation: mark-draw 2.4s ease-out 0.3s forwards;
}
.brand-mark path:nth-of-type(2) { animation-delay: 0.7s; }
.brand-mark path:nth-of-type(3) { animation-delay: 1.0s; }
.brand-mark path:nth-of-type(4) { animation-delay: 1.3s; }
.brand-mark circle { animation: mark-pop 0.4s ease-out 1.8s backwards; }

@keyframes mark-draw { to { stroke-dashoffset: 0; } }
@keyframes mark-pop {
  0% { opacity: 0; transform: scale(0.4); transform-origin: center; }
  100% { opacity: 1; transform: scale(1); }
}
@media (prefers-reduced-motion: reduce) {
  .brand-mark path, .brand-mark circle { animation: none; stroke-dashoffset: 0; }
}
```

**Gotchas:**
- The SVG must have `stroke` attributes on its paths (not just fill) for stroke-dasharray to animate.
- `stroke-dasharray: 800` is a "long enough" trick — adjust if your paths are longer than ~800 path-length.
- Sequencing the `nth-of-type` delays creates a pleasing "drawing" rhythm. Adjust per-mark count.
- `prefers-reduced-motion` MUST be honored — the snap to final state is required.

---

## R4. Animated gradient drop cap

**The first letter of the lede shimmers a brand-color gradient on load.** Editorial-personal sites get a tasteful "this is intentional design" moment.

**Corpus exemplars:**
- robinrendle.com — colorful drop caps
- frankchimero.com — typographic flourishes

**Recipe (CSS):**
```css
.lede-cap {
  float: left;
  font-family: var(--serif);
  font-weight: 700;
  font-size: 5rem;
  line-height: 0.82;
  margin: 0.18rem 0.45rem -0.05rem -0.05rem;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, var(--navy) 0%, var(--accent-text) 50%, var(--accent) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  background-size: 220% 220%;
  animation: cap-shimmer 1.6s ease-out 0.3s 1 backwards;
}
@keyframes cap-shimmer {
  0%   { background-position: 100% 0%; opacity: 0.4; transform: translateY(4px); }
  60%  { opacity: 1; transform: translateY(0); }
  100% { background-position: 0% 100%; }
}
@media (prefers-reduced-motion: reduce) { .lede-cap { animation: none; } }
```

**Gotchas:**
- HTML pattern: wrap the first letter `<span class="lede-cap">H</span>ead of Growth at...`. Don't use `::first-letter` — gradient text-clip doesn't work consistently with that pseudo-element.
- `background-size: 220%` lets the gradient SHIFT during animation, not just fade in.
- Pair with `prefers-reduced-motion` always.

---

## R5. Gradient mesh halo

**Subtle radial-gradient blur behind the hero adds depth without going stencil.**

**Corpus exemplars:**
- linear.app — gradient meshes throughout
- vercel.com — subtle hero gradients
- raycast.com — full-bleed gradient meshes

**Recipe (CSS):**
```css
.hero { position: relative; }
.hero::before {
  content: "";
  position: absolute;
  inset: -4rem -4rem auto auto;
  width: 28rem;
  height: 28rem;
  background:
    radial-gradient(circle at 70% 30%, rgba(<accent-rgb>,0.16) 0%, transparent 55%),
    radial-gradient(circle at 30% 80%, rgba(<navy-rgb>,0.10) 0%, transparent 60%);
  pointer-events: none;
  z-index: -1;
  border-radius: 50%;
  filter: blur(20px);
}
```

**Gotchas:**
- The blur + transparency combo can pixel-shift on Safari. Test there.
- `z-index: -1` puts it behind text; verify the hero `<section>` has `z-index: 0` or higher to anchor the stacking context, otherwise the halo can fall behind body bg.
- Mobile: collapse to a smaller halo or omit on mobile to save paint cost.

---

## R6. Color-rich hover (CV row / portfolio tile)

**Hover states with CHARACTER — not just border-color shifts.** Slide-in accent bars, color shifts, scale + saturation pops.

**Corpus exemplars:**
- mercury.com — accent strokes on hover
- ramp.com — bold hover transitions
- linear.app — smooth color shifts

**Recipe — CV row (slide-in accent bar + color shift + nudge):**
```css
.cv-row {
  position: relative;
  padding-left: 1.1rem;
  transition: background 0.2s, padding 0.2s;
}
.cv-row::before {
  content: "";
  position: absolute;
  left: 0;
  top: 1.1rem;
  bottom: 1.1rem;
  width: 3px;
  background: linear-gradient(180deg, var(--accent) 0%, var(--navy) 100%);
  opacity: 0;
  transform: scaleY(0.4);
  transform-origin: top;
  transition: opacity 0.25s, transform 0.25s;
  border-radius: 2px;
}
.cv-row:hover::before { opacity: 1; transform: scaleY(1); }
.cv-row:hover {
  background: linear-gradient(90deg, rgba(<accent-rgb>,0.06) 0%, transparent 60%);
  padding-left: 1.4rem;
}
.cv-row:hover .cv-where strong { color: var(--accent-text); transition: color 0.2s; }
```

**Recipe — portfolio tile (lift + saturation pop):**
```css
.port-tile { transition: transform 0.25s, box-shadow 0.25s, filter 0.25s; }
.port-tile:hover {
  transform: translateY(-4px) scale(1.03);
  box-shadow: 0 16px 32px rgba(<accent-rgb>,0.28);
  filter: brightness(1.10) saturate(1.15);
}
```

**Gotchas:**
- The `filter: brightness + saturate` combo on dark colored tiles is the move that makes them feel "alive" without changing the design.
- Don't add hover effects on touch devices (they linger uglily on tap). Wrap in `@media (hover: hover)` if you want to be strict.

---

## R7. Scroll-triggered fade-ins (IntersectionObserver)

**Sections gently drift up + fade as they enter viewport.** Adds polish on long pages without demanding attention.

**Corpus exemplars:**
- mercury.com, framer.com — scroll-driven motion throughout
- linear.app — gentle reveal patterns

**Recipe (CSS):**
```css
.fade-in-init {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.65s cubic-bezier(0.22,1,0.36,1), transform 0.65s cubic-bezier(0.22,1,0.36,1);
}
.fade-in-init.fade-in-visible { opacity: 1; transform: translateY(0); }
@media (prefers-reduced-motion: reduce) {
  .fade-in-init { opacity: 1; transform: none; transition: none; }
}
```

**Recipe (JS — inline `<script>`):**
```js
(function () {
  if (!('IntersectionObserver' in window)) return;
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var sels = '.block, .testimonials, .vang-aside, .newsletter, .ecosystem, .opening, .big-number, .stat-band, .hero-banner';
  var els = document.querySelectorAll(sels);
  els.forEach(function (el) { el.classList.add('fade-in-init'); });
  var obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) {
        e.target.classList.add('fade-in-visible');
        obs.unobserve(e.target);
      }
    });
  }, { threshold: 0.08, rootMargin: '0px 0px -6% 0px' });
  els.forEach(function (el) { obs.observe(el); });
})();
```

**Gotchas:**
- Add `fade-in-init` class via JS, not in markup, so non-JS users still see content (progressive enhancement).
- `threshold: 0.08` + `rootMargin: '0px 0px -6% 0px'` triggers when ~8% of the element enters from the bottom edge. Tune per-page feel.
- Disable for `prefers-reduced-motion` users — the snap-on visibility is correct behavior.

---

## R8. Typographic stat strip (the anti-stencil pattern)

**Replace the boxed 4-stat strip (instant AI-stencil flag) with a single typographic line.** Same content, no template feel.

**Corpus exemplars:**
- sive.rs — pure typography
- robinrendle.com — typographic strips
- pmarchive.com — sentence-as-stats

**Recipe (HTML):**
```html
<ul class="stat-band" aria-label="Career numbers">
  <li><span class="stat-num">$0&rarr;$60m</span><span class="stat-label">TVL at Dinari</span></li>
  <li><span class="stat-num">15&times;</span><span class="stat-label">Touch Surgery</span></li>
  ...
</ul>
```

**Recipe (CSS):**
```css
.stat-band {
  list-style: none;
  margin: 1.5rem 0 4rem;
  padding: 1.5rem 0;
  border-top: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 2rem;
  align-items: baseline;
}
.stat-band li { display: flex; align-items: baseline; gap: 0.55rem; }
.stat-num {
  font-family: var(--serif);
  font-weight: 600;
  font-size: 1.2rem;
  color: var(--navy);
  font-feature-settings: "tnum";
}
.stat-label {
  font-family: var(--body);
  font-size: 0.92rem;
  color: var(--navy-faint);
  line-height: 1.45;
}
```

**Gotchas:**
- This is intentionally NOT bold/eye-catching — it's the cleanness move. Pair with a R2 big-number anchor mid-page if you want a dramatic moment to coexist.
- Hairline rules above + below tie it to the editorial register.

---

## R9. Editorial section ornament (§ on rule)

**Small typographic glyph centered on a hairline rule, between major section beats.** Editorial richness, no decorative cost.

**Recipe (HTML):** `<hr class="ornament" aria-hidden="true" />`

**Recipe (CSS):**
```css
.ornament {
  border: 0;
  margin: 3.5rem auto 1rem;
  height: 1.6rem;
  position: relative;
  background-image: linear-gradient(var(--rule), var(--rule));
  background-position: center center;
  background-repeat: no-repeat;
  background-size: 100% 1px;
  max-width: 8rem;
}
.ornament::after {
  content: "§";
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: var(--paper);
  padding: 0 0.7rem;
  font-family: var(--serif);
  font-style: italic;
  font-weight: 500;
  color: var(--accent-text);
  font-size: 1.15rem;
}
```

**Gotchas:**
- Replace `§` with a brand-meaningful glyph if you have one (★, ◆, custom SVG inline).
- Don't overuse — every 1-2 major section beats max. More than that becomes noise.

---

## R10. Editorial "currently" sidebar callout

**Small structured "what I'm working on / building / reading" callout in the hero — the personal-site corpus topper signature.**

**Corpus exemplars:**
- pmarchive.com — current-focus list
- robinrendle.com — "Now" sidebar
- sive.rs — extensive personal context

**Recipe (HTML):**
```html
<aside class="opening-currently" aria-label="Currently">
  <p class="oc-rubric">Currently</p>
  <ul>
    <li><span class="oc-key">Building</span><span class="oc-val">Zstack — boards, calendars, mail — for AI agents</span></li>
    <li><span class="oc-key">Investing</span><span class="oc-val">Vang Capital Fund I in flight, Fund II in 2026</span></li>
    <li><span class="oc-key">Advising</span><span class="oc-val">1–2 engagements / quarter</span></li>
  </ul>
</aside>
```

**Recipe (CSS):**
```css
.opening-currently { border-top: 1px solid var(--rule); padding-top: 1.1rem; }
.oc-rubric { font-family: var(--headline); font-size: 0.72rem; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; color: var(--navy-faint); margin: 0 0 0.7rem; }
.opening-currently ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.55rem; }
.opening-currently li { display: grid; grid-template-columns: 5rem 1fr; gap: 0.7rem; align-items: baseline; font-size: 0.88rem; line-height: 1.5; color: var(--navy); }
.opening-currently .oc-key { font-family: var(--headline); font-weight: 600; font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent-text); padding-top: 0.1rem; }
```

**Gotchas:**
- ONLY ground this in real public facts. Don't fabricate "reading X / listening Y" without checking — the personal-site distinctiveness comes from authenticity.

---

## Brand tokens — paste-in shortcuts

| Site | --navy | --accent | --accent-text (AA) | --secondary |
|---|---|---|---|---|
| matteisn (Eisner) | `#273a96` | `#0fbbbb` (teal) | `#0e7490` | `#4dd1d1` |
| vang.capital + vang-advisory | `#0a1641` | `#4b04af` (purple) | `#4b04af` | `#0ea5a5` (teal) |
| zergai.com (cream paper) | `#111514` | `#b3662f` (burnt-orange) | `#8a4a1f` | `#6FBE31` (green) |

Always verify any text color hits ≥4.5:1 against the bg it sits on (use `https://webaim.org/resources/contrastchecker/`).

---

## When to apply which

| Symptom | Recipe |
|---|---|
| "Looks very simple" / sparse | R1 (full-bleed band) + R2 (big number) |
| Audit flags low distinctiveness | R10 (currently sidebar) + R4 (drop cap) + R9 (ornaments) |
| 4-stat boxed strip flagged AI-stencil | R8 (typographic strip replacement) |
| Hero feels flat | R5 (gradient mesh halo) + R3 (animated mark) |
| CV/portfolio rows feel inert | R6 (color-rich hover) |
| Long page feels static | R7 (scroll fade-ins) |
| Color presence too low (axis ≤7) | R1 + R2 + R6 |
| Density too uniform | R2 (oversized number) breaks rhythm |

---

## Cross-references

- **Implementation history**: matteisn.com, vang.capital, vangadvisory.com all carry the full R1–R10 playbook (deployed 2026-05-08). See `~/matteisn-site/style.css` and `~/vang-capital-site/style.css` and `~/vang-advisory-site/style.css` for production CSS.
- **Sibling skills**: `webpage-layout` (audit + score), `website-designer` (anti-pattern catch), `landing-page-skill` (Zerg-page generation), `graphic-layout` (rendered-asset review).
- **Image-gen tools** for illustration moments not covered here: `chatgpt-image-skill` (preferred), `nano-banana-pro`, `fal-image-skill`.
