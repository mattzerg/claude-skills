# richness-lift — https://zergai.com/

**Current**: `EDITORIAL-LEAN` (1/10 = 10%)
**Brand detected**: `zerg` (navy=#111514, accent=#b3662f)
**Top 3 missing recipes** (by visual-payoff priority):

- **R2** — Big-number pull-quote moment
- **R6** — Color-rich hover (lift + shadow)
- **R5** — Gradient mesh halo

---

## Paste-ready CSS patch

Append to your stylesheet, replace generic class names (`.full-bleed-band` / `.cv-row` / `.hero` etc.) with your site's actual class names where noted.

```css
/* R2 — Big-number pull-quote moment */
.big-number {
  margin: 5rem 0;
  padding: 3.5rem 2.5rem;
  background: linear-gradient(135deg, var(--paper, #fff) 0%, var(--section-bg, #f4f6fb) 100%);
  border-left: 5px solid #b3662f;
  border-radius: 0 8px 8px 0;
  position: relative;
}
.bn-row { display: grid; grid-template-columns: minmax(0,auto) minmax(0,1fr); gap: 2rem; align-items: center; }
.bn-num {
  font-family: var(--serif, "Fraunces", Georgia, serif);
  font-weight: 600;
  font-size: clamp(4rem, 9vw, 7rem);
  line-height: 0.9;
  letter-spacing: -0.04em;
  margin: 0;
  background: linear-gradient(135deg, #111514 0%, #8a4a1f 60%, #b3662f 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-feature-settings: "tnum" 1, "lnum" 1;
}
.bn-num em { font-style: italic; font-weight: 500; font-size: 0.55em; letter-spacing: -0.02em; }
.bn-label { font-family: var(--serif); font-style: italic; font-size: clamp(1.15rem,1.7vw,1.4rem); color: var(--navy-soft); margin: 0; max-width: 32ch; }
.bn-tag { display: inline-block; font-family: var(--headline); font-size: 0.72rem; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; color: #8a4a1f; margin-bottom: 0.85rem; }

```

```css
/* R6 — Color-rich hover (CV row / portfolio tile) */
.cv-row { position: relative; padding-left: 1.1rem; transition: background 0.2s, padding 0.2s; }
.cv-row::before {
  content: ""; position: absolute; left: 0; top: 1.1rem; bottom: 1.1rem;
  width: 3px; background: linear-gradient(180deg, #b3662f 0%, #111514 100%);
  opacity: 0; transform: scaleY(0.4); transform-origin: top;
  transition: opacity 0.25s, transform 0.25s; border-radius: 2px;
}
.cv-row:hover::before { opacity: 1; transform: scaleY(1); }
.cv-row:hover { background: linear-gradient(90deg, rgba(179,102,47,0.06) 0%, transparent 60%); padding-left: 1.4rem; }
.port-tile { transition: transform 0.25s, box-shadow 0.25s, filter 0.25s; }
.port-tile:hover { transform: translateY(-4px) scale(1.03); box-shadow: 0 16px 32px rgba(179,102,47,0.16); filter: brightness(1.10) saturate(1.15); }

```

```css
/* R5 — Gradient mesh halo (apply to hero ::before) */
.hero { position: relative; }
.hero::before {
  content: "";
  position: absolute;
  inset: -4rem -4rem auto auto;
  width: 28rem;
  height: 28rem;
  background:
    radial-gradient(circle at 70% 30%, rgba(179,102,47,0.16) 0%, transparent 55%),
    radial-gradient(circle at 30% 80%, rgba(17,21,20,0.08) 0%, transparent 60%);
  pointer-events: none;
  z-index: -1;
  border-radius: 50%;
  filter: blur(20px);
}

```

---

## Reference
Full recipe library + symptom→recipe table: `~/.claude/skills/webpage-layout/recipes/visual-richness.md`

After applying, re-run `python3 ~/.claude/skills/webpage-layout/run.py richness https://zergai.com/` to verify the lift.