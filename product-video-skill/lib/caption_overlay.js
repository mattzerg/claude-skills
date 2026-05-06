/**
 * Canonical caption overlay for Playwright-recorded product videos.
 *
 * Inject into the page once, then call `window.__zb_set_caption(text)` to
 * change the visible caption. Empty string clears.
 *
 * Typography rules baked in (per product-video-skill best practices):
 *   - 44px font (≥3% of 1080p frame height; readable on phone in feed)
 *   - White text on near-black 90% scrim (survives feed compression)
 *   - 0.25s fade-in, 0.25s fade-out
 *   - Bottom-third placement, clear of bottom 12% (platform UI strip)
 *   - Max width 70% of viewport, ≤2 lines, line-height 1.2
 *   - System sans, weight 700, letter-spacing -0.02em
 *
 * Works with the existing /tmp/zb_demo_record.py pattern; replaces the
 * inline OVERLAY string there with a single line:
 *     page.add_init_script(path=".../caption_overlay.js")
 *     # ... or page.evaluate(open(path).read())
 */
(() => {
  if (document.getElementById('__pv_overlay_root')) return;

  const wrap = document.createElement('div');
  wrap.id = '__pv_overlay_root';
  wrap.style.cssText = `
    position: fixed;
    left: 0; right: 0;
    top: 58%;
    z-index: 999999;
    pointer-events: none;
    display: flex;
    flex-direction: column;
    align-items: center;
  `;

  const card = document.createElement('div');
  card.id = '__pv_caption';
  card.style.cssText = `
    background: rgba(7, 17, 30, 0.92);
    color: #EBF1F8;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", system-ui, sans-serif;
    font-weight: 700;
    font-size: 44px;
    letter-spacing: -0.02em;
    line-height: 1.2;
    padding: 18px 32px;
    border-radius: 14px;
    max-width: 70vw;
    text-align: center;
    box-shadow: 0 30px 70px rgba(0, 0, 0, 0.55);
    opacity: 0;
    transform: translateY(20px);
    transition: opacity 0.25s ease, transform 0.25s ease;
    backdrop-filter: blur(12px);
    border: 1px solid rgba(213, 122, 50, 0.55);
  `;
  card.textContent = '';
  wrap.appendChild(card);
  document.body.appendChild(wrap);

  /**
   * Public API: set or clear the caption.
   * @param {string} text — pass "" to clear with fade-out.
   */
  window.__pv_set_caption = (text) => {
    const el = document.getElementById('__pv_caption');
    if (!el) return;
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    setTimeout(() => {
      el.textContent = text || '';
      if (text) {
        el.style.opacity = '1';
        el.style.transform = 'translateY(0)';
      }
    }, 200);
  };
})();
