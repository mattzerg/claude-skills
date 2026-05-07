"""Smooth-record helpers — in-browser CSS-driven motion during Playwright recording.

Why this exists: ffmpeg's `zoompan` filter creates per-frame integer pixel
scaling that produces visible shake/wobble at slow zoom rates (1.00→1.06 over
2.5s). This was the cause of v11/v12/v13 looking shaky.

The fix: do the motion *in-browser* via CSS transforms during recording. The
browser compositor handles sub-pixel interpolation natively. Playwright records
the smoothly-rendered output. ffmpeg just packages it without re-projecting
any pixels.

Use these helpers from a Playwright recording script. They inject a
transform-target wrapper around the page body so we can scale/translate the
whole UI smoothly without disrupting layout.

Example:
    from smooth_record import setup_smooth_record, smooth_zoom, smooth_pan_to
    setup_smooth_record(page)
    smooth_zoom(page, scale=1.04, duration_s=2.5, easing="linear")
    page.wait_for_timeout(2500)  # let the animation play out
    smooth_pan_to(page, x=-200, y=0, duration_s=1.5)
"""
from typing import Literal

EASING_PRESETS = {
    "linear": "linear",
    "ease": "cubic-bezier(0.25, 0.1, 0.25, 1)",
    "ease-in": "cubic-bezier(0.42, 0, 1, 1)",
    "ease-out": "cubic-bezier(0, 0, 0.58, 1)",
    "ease-in-out": "cubic-bezier(0.42, 0, 0.58, 1)",
    "ease-out-overshoot": "cubic-bezier(0.18, 0.89, 0.32, 1.28)",
}


SETUP_SCRIPT = r"""
(() => {
  if (document.getElementById('__pv_smooth_root')) return;

  // Wrap the entire body in a transform target. We manipulate this wrapper's
  // CSS transform/transition so we can zoom and pan the page contents
  // smoothly without disturbing the page's own layout calculations.
  const wrapper = document.createElement('div');
  wrapper.id = '__pv_smooth_root';
  wrapper.style.cssText = `
    position: fixed;
    top: 0; left: 0;
    width: 100vw; height: 100vh;
    transform-origin: 50% 50%;
    transform: scale(1) translate(0, 0);
    transition: none;
    pointer-events: auto;
    will-change: transform;
  `;
  // Move existing body children into the wrapper
  while (document.body.firstChild) {
    wrapper.appendChild(document.body.firstChild);
  }
  document.body.appendChild(wrapper);

  // Track current transform state so multiple sequential calls compose
  window.__pv_smooth_state = { scale: 1.0, x: 0, y: 0 };

  // Public API ----------------------------------------------------------------

  // smoothTransform: animate to absolute scale + translate over duration.
  // origin is in CSS percent ("50% 50%" = center; "0% 0%" = top-left).
  window.__pv_smooth_to = function(opts) {
    const { scale = null, x = null, y = null, duration_ms = 0,
            easing = 'linear', origin = '50% 50%' } = opts || {};
    const w = document.getElementById('__pv_smooth_root');
    if (!w) return;
    const s = window.__pv_smooth_state;
    const new_scale = (scale === null) ? s.scale : scale;
    const new_x = (x === null) ? s.x : x;
    const new_y = (y === null) ? s.y : y;
    w.style.transformOrigin = origin;
    w.style.transition = duration_ms > 0
      ? `transform ${duration_ms}ms ${easing}`
      : 'none';
    // Force reflow so the transition picks up the new transition value
    void w.offsetWidth;
    w.style.transform = `scale(${new_scale}) translate(${new_x}px, ${new_y}px)`;
    s.scale = new_scale; s.x = new_x; s.y = new_y;
  };

  // smoothReset: instantly reset to identity (no animation).
  window.__pv_smooth_reset = function() {
    const w = document.getElementById('__pv_smooth_root');
    if (!w) return;
    w.style.transition = 'none';
    w.style.transform = 'scale(1) translate(0, 0)';
    void w.offsetWidth;
    window.__pv_smooth_state = { scale: 1.0, x: 0, y: 0 };
  };
})();
"""


def setup_smooth_record(page) -> None:
    """Inject the smooth-record wrapper + helpers into a Playwright page.
    Call once after page load and BEFORE any motion calls.
    """
    page.evaluate(SETUP_SCRIPT)


def smooth_zoom(
    page,
    *,
    scale: float = 1.04,
    duration_s: float = 2.5,
    easing: Literal["linear", "ease", "ease-in", "ease-out",
                    "ease-in-out", "ease-out-overshoot"] = "linear",
    origin_x_pct: float = 50.0,
    origin_y_pct: float = 50.0,
) -> None:
    """Smoothly zoom to absolute scale around (origin_x_pct, origin_y_pct).
    Browser-rendered = no shake. Default = subtle Linear-style push-in.

    The call is non-blocking — start the zoom, then `page.wait_for_timeout`
    or perform other actions while the browser interpolates.
    """
    eas = EASING_PRESETS.get(easing, easing)
    page.evaluate(
        "(opts) => window.__pv_smooth_to(opts)",
        {
            "scale": scale,
            "duration_ms": int(duration_s * 1000),
            "easing": eas,
            "origin": f"{origin_x_pct}% {origin_y_pct}%",
        },
    )


def smooth_pan_to(
    page,
    *,
    x_px: float = 0,
    y_px: float = 0,
    duration_s: float = 1.5,
    easing: str = "ease-in-out",
) -> None:
    """Smoothly pan the wrapper. Negative x_px moves contents LEFT (camera
    appears to move right). Combine with a current zoom level to fly across
    the kanban.
    """
    eas = EASING_PRESETS.get(easing, easing)
    page.evaluate(
        "(opts) => window.__pv_smooth_to(opts)",
        {
            "x": x_px,
            "y": y_px,
            "duration_ms": int(duration_s * 1000),
            "easing": eas,
        },
    )


def smooth_zoom_pan(
    page,
    *,
    scale: float = 1.0,
    x_px: float = 0,
    y_px: float = 0,
    duration_s: float = 2.0,
    easing: str = "ease-in-out",
    origin_x_pct: float = 50.0,
    origin_y_pct: float = 50.0,
) -> None:
    """Combined zoom + pan in one smooth animation."""
    eas = EASING_PRESETS.get(easing, easing)
    page.evaluate(
        "(opts) => window.__pv_smooth_to(opts)",
        {
            "scale": scale,
            "x": x_px,
            "y": y_px,
            "duration_ms": int(duration_s * 1000),
            "easing": eas,
            "origin": f"{origin_x_pct}% {origin_y_pct}%",
        },
    )


def smooth_reset(page) -> None:
    """Instantly reset transform to identity (no animation). Use for hard
    cuts between scenes where the previous transform shouldn't carry over.
    """
    page.evaluate("() => window.__pv_smooth_reset()")
