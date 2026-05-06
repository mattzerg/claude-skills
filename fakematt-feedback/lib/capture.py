"""Browser capture: spider the target, screenshot pages, gather DOM/console/network/axe.

Uses playwright Python API directly (one persistent context) — calling
playwright_skill.py per-action would be ~200 subprocess hops per run.

axe-core is loaded from the CDN on first scan and injected on each page.
"""

from __future__ import annotations

import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

from playwright.sync_api import (
    BrowserContext,
    Page,
    sync_playwright,
)

AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"

# Viewport ladder. Order matters: capture starts at desktop, walks down to
# mobile, returns to desktop for the rest of the per-page work. Each entry
# produces one screenshot per page.
VIEWPORTS = [
    {"name": "desktop", "width": 1440, "height": 900},
    {"name": "small_desktop", "width": 1024, "height": 768},
    {"name": "tablet", "width": 768, "height": 1024},
    {"name": "mobile", "width": 390, "height": 844},
]
DEFAULT_VIEWPORT = {"width": VIEWPORTS[0]["width"], "height": VIEWPORTS[0]["height"]}
MOBILE_VIEWPORT = {"width": VIEWPORTS[-1]["width"], "height": VIEWPORTS[-1]["height"]}


@dataclass
class PageCapture:
    url: str
    title: str
    final_url: str
    screenshot_desktop: str
    screenshot_mobile: str
    text_content: str
    links: list[str]
    primary_cta: str | None
    h1: str | None
    headings: list[str]
    forms: list[dict]
    console: list[dict] = field(default_factory=list)
    network_errors: list[dict] = field(default_factory=list)
    axe_violations: list[dict] = field(default_factory=list)
    perf: dict[str, Any] = field(default_factory=dict)
    # New: per-viewport screenshots (desktop + small_desktop + tablet + mobile)
    # `screenshot_desktop` and `screenshot_mobile` above are kept for back-compat
    # and mirror the corresponding entries here.
    screenshots: dict[str, str] = field(default_factory=dict)
    # New: interactive probing results — list of {label, before, after}
    # captured by clicking detected affordances (buttons, sortable headers).
    interactions: list[dict] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "title": self.title,
            "h1": self.h1,
            "headings": self.headings,
            "primary_cta": self.primary_cta,
            "forms": self.forms,
            "links_sample": self.links[:30],
            "console": self.console[:20],
            "network_errors": self.network_errors[:20],
            "axe_violations": self.axe_violations[:30],
            "perf": self.perf,
            "text_excerpt": self.text_content[:3000],
            "screenshot_desktop": self.screenshot_desktop,
            "screenshot_mobile": self.screenshot_mobile,
            "screenshots": self.screenshots,
            "interactions": self.interactions,
        }


def _is_internal(target_url: str, link: str) -> bool:
    if not link:
        return False
    if link.startswith(("mailto:", "tel:", "javascript:", "#")):
        return False
    abs_url = urljoin(target_url, link)
    abs_url, _ = urldefrag(abs_url)
    return urlparse(abs_url).netloc == urlparse(target_url).netloc


def _normalize(target_url: str, link: str) -> str:
    abs_url = urljoin(target_url, link)
    abs_url, _ = urldefrag(abs_url)
    return abs_url


def _extract_links(page: Page, current_url: str) -> list[str]:
    hrefs = page.eval_on_selector_all(
        "a[href]",
        "els => els.map(e => e.getAttribute('href'))",
    )
    out = []
    for h in hrefs:
        if _is_internal(current_url, h):
            out.append(_normalize(current_url, h))
    # Dedupe preserve-order
    seen = set()
    deduped = []
    for u in out:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def _detect_primary_cta(page: Page) -> str | None:
    """Heuristic: largest visible button or button-like link above the fold."""
    js = """
    () => {
      const candidates = [...document.querySelectorAll('a, button')];
      const above = candidates.filter(el => {
        const r = el.getBoundingClientRect();
        return r.top >= 0 && r.top < window.innerHeight && r.width > 40 && r.height > 24;
      });
      if (!above.length) return null;
      above.sort((a, b) => {
        const ra = a.getBoundingClientRect();
        const rb = b.getBoundingClientRect();
        return (rb.width * rb.height) - (ra.width * ra.height);
      });
      const top = above[0];
      return (top.innerText || top.textContent || '').trim().slice(0, 80);
    }
    """
    try:
        return page.evaluate(js)
    except Exception:
        return None


def _extract_forms(page: Page) -> list[dict]:
    js = """
    () => [...document.querySelectorAll('form')].slice(0, 5).map(f => ({
      action: f.getAttribute('action') || '',
      fields: [...f.querySelectorAll('input, select, textarea')].slice(0, 20).map(i => ({
        type: i.type || i.tagName.toLowerCase(),
        name: i.getAttribute('name') || '',
        required: i.hasAttribute('required'),
      })),
    }))
    """
    try:
        return page.evaluate(js) or []
    except Exception:
        return []


def _run_axe(page: Page) -> list[dict]:
    """Inject axe-core and return violations array."""
    try:
        page.add_script_tag(url=AXE_CDN)
        result = page.evaluate("async () => await axe.run({ resultTypes: ['violations'] })")
        violations = result.get("violations", []) if isinstance(result, dict) else []
        # Trim to the essentials
        out = []
        for v in violations:
            out.append({
                "id": v.get("id"),
                "impact": v.get("impact"),
                "help": v.get("help"),
                "helpUrl": v.get("helpUrl"),
                "node_count": len(v.get("nodes") or []),
                "first_node_html": (v.get("nodes") or [{}])[0].get("html", "")[:200],
            })
        return out
    except Exception as exc:
        return [{"id": "_axe_inject_error", "impact": "info", "help": str(exc)[:200]}]


def _perf_metrics(page: Page) -> dict:
    js = """
    () => {
      const t = performance.getEntriesByType('navigation')[0];
      if (!t) return {};
      return {
        dom_content_loaded_ms: Math.round(t.domContentLoadedEventEnd - t.startTime),
        load_event_ms: Math.round(t.loadEventEnd - t.startTime),
        transfer_size_kb: Math.round((t.transferSize || 0) / 1024),
        encoded_body_size_kb: Math.round((t.encodedBodySize || 0) / 1024),
      };
    }
    """
    try:
        return page.evaluate(js) or {}
    except Exception:
        return {}


def _probe_interactions(page: Page, run_dir: Path, slug: str, *, max_interactions: int = 3) -> list[dict]:
    """Click a small set of high-signal interactive affordances and capture
    the resulting state. Targets:
      - sortable column headers (`th[aria-sort]`, `[role="columnheader"]`, `[data-sort]`)
      - toggle buttons (visible `<button>` not in a form, not a link)
      - elements with `cursor: pointer` that aren't anchors

    Each click captures a before+after pair so the critique can see what
    the affordance actually does. Capped at `max_interactions` to keep
    runtime bounded.

    Returns a list of {label, before, after, kind} dicts. Failures are
    swallowed — interactive probing is best-effort, not load-bearing.
    """
    out: list[dict] = []
    interactions_dir = run_dir / "screenshots" / "interactions"
    try:
        interactions_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return out

    # Detection script: returns up to N candidate selectors with metadata.
    # Prefers sortable headers > toggle buttons > pointer-cursor elements.
    detect_js = """
    (max_n) => {
      const candidates = [];
      const seen = new Set();

      const addCandidate = (el, kind, label) => {
        if (!el || seen.has(el)) return;
        const r = el.getBoundingClientRect();
        if (r.width < 16 || r.height < 16) return;
        if (r.top < 0 || r.top > window.innerHeight - 8) return;
        seen.add(el);
        // Build a stable selector: prefer id, then tag + classes
        let sel = '';
        if (el.id) sel = '#' + CSS.escape(el.id);
        else {
          const tag = el.tagName.toLowerCase();
          const cls = (el.className || '').toString().trim().split(/\\s+/).filter(Boolean).slice(0, 2).map(c => '.' + CSS.escape(c)).join('');
          sel = tag + cls;
        }
        candidates.push({ kind, label: label.slice(0, 60), selector: sel, x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) });
      };

      // 1. Sortable headers
      document.querySelectorAll('th[aria-sort], [role="columnheader"], th[data-sort], th[data-sortable], th button').forEach(el => {
        const label = (el.innerText || el.textContent || '').trim();
        if (label) addCandidate(el, 'sortable_header', `Sort by "${label}"`);
      });

      // 2. Toggle-ish buttons (not submits, not nav links)
      document.querySelectorAll('button:not([type="submit"])').forEach(el => {
        if (el.closest('form')) return;
        const label = (el.innerText || el.textContent || '').trim();
        if (!label || label.length > 60) return;
        // Skip obvious nav/dropdown carets that just open menus
        const aria = el.getAttribute('aria-label') || '';
        addCandidate(el, 'button', label || aria);
      });

      // 3. Click-to-expand counters in tables (numeric content with cursor:pointer)
      document.querySelectorAll('td a, td button, td [role="button"]').forEach(el => {
        const label = (el.innerText || el.textContent || '').trim();
        if (!label || !/^\\d+$/.test(label)) return;
        addCandidate(el, 'counter_click', `Click counter "${label}"`);
      });

      return candidates.slice(0, max_n);
    }
    """
    try:
        candidates = page.evaluate(detect_js, max_interactions * 2) or []
    except Exception:
        return out

    for i, cand in enumerate(candidates[: max_interactions]):
        try:
            before_path = interactions_dir / f"{slug}_int{i}_before.png"
            page.screenshot(path=str(before_path), full_page=False)
            # Click via coordinates (selector might be ambiguous)
            page.mouse.click(cand["x"], cand["y"])
            page.wait_for_timeout(800)
            after_path = interactions_dir / f"{slug}_int{i}_after.png"
            page.screenshot(path=str(after_path), full_page=False)
            out.append({
                "kind": cand["kind"],
                "label": cand["label"],
                "selector": cand.get("selector"),
                "before": str(before_path),
                "after": str(after_path),
            })
        except Exception as exc:
            # Best-effort; record the attempt with the error
            out.append({
                "kind": cand.get("kind"),
                "label": cand.get("label"),
                "error": str(exc)[:160],
            })
    return out


def _shoot(page: Page, path: Path, full_page: bool = True) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=full_page)
    return str(path)


def _get_text(page: Page) -> str:
    try:
        return page.evaluate("document.body.innerText || ''")
    except Exception:
        return ""


def _get_h1(page: Page) -> str | None:
    try:
        return page.eval_on_selector("h1", "el => el.innerText.trim()")
    except Exception:
        return None


def _get_headings(page: Page) -> list[str]:
    try:
        return page.eval_on_selector_all("h1, h2, h3", "els => els.map(e => e.innerText.trim()).slice(0, 30)")
    except Exception:
        return []


def _capture_one(context: BrowserContext, url: str, run_dir: Path, console: list, net_err: list) -> PageCapture | None:
    page = context.new_page()
    page.on("console", lambda msg: console.append({"type": msg.type, "text": msg.text[:300]}))
    page.on("requestfailed", lambda req: net_err.append({
        "url": req.url[:300], "method": req.method, "error": req.failure or ""
    }))
    page.on("response", lambda res: net_err.append({
        "url": res.url[:300], "status": res.status,
    }) if res.status >= 400 else None)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception as exc:
        page.close()
        net_err.append({"url": url, "error": f"navigation failed: {exc}"[:300]})
        return None
    final_url = page.url
    title = page.title()
    h1 = _get_h1(page)
    headings = _get_headings(page)
    primary_cta = _detect_primary_cta(page)
    forms = _extract_forms(page)
    text_content = _get_text(page)
    perf = _perf_metrics(page)

    safe_slug = re.sub(r"[^\w\-]", "_", urlparse(url).path.strip("/") or "home")[:80] or "home"

    # Walk the viewport ladder. Each viewport produces one screenshot.
    screenshots: dict[str, str] = {}
    for vp in VIEWPORTS:
        page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
        page.wait_for_timeout(300)
        path = run_dir / "screenshots" / f"{safe_slug}_{vp['name']}.png"
        path = Path(_shoot(page, path))
        screenshots[vp["name"]] = str(path)
    # Reset to desktop for the rest of the per-page work
    page.set_viewport_size(DEFAULT_VIEWPORT)
    page.wait_for_timeout(200)

    desktop_path = Path(screenshots["desktop"])
    mobile_path = Path(screenshots["mobile"])

    # Axe runs on the desktop viewport
    axe_violations = _run_axe(page)
    links = _extract_links(page, final_url)

    # Interactive probing: click up to N affordances and capture state changes
    interactions = _probe_interactions(page, run_dir, safe_slug, max_interactions=3)

    page.close()

    pc = PageCapture(
        url=url,
        title=title,
        final_url=final_url,
        screenshot_desktop=str(desktop_path),
        screenshot_mobile=str(mobile_path),
        text_content=text_content,
        links=links,
        primary_cta=primary_cta,
        h1=h1,
        headings=headings,
        forms=forms,
        axe_violations=axe_violations,
        perf=perf,
        screenshots=screenshots,
        interactions=interactions,
    )
    # Pull console + net_err that fired during this page's lifetime
    pc.console = list(console)
    pc.network_errors = list(net_err)
    console.clear()
    net_err.clear()
    return pc


_TEMPLATE_DIGITS = re.compile(r"\d+")
_TEMPLATE_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_TEMPLATE_SLUG = re.compile(r"[a-f0-9]{20,}")


def _template_key(url: str) -> str:
    """Collapse URL to a template signature so we can sample (not exhaust) each
    template type. /people/1001 and /people/1007 both map to /people/{ID}.
    """
    p = urlparse(url)
    path = p.path or "/"
    path = _TEMPLATE_UUID.sub("{UUID}", path)
    path = _TEMPLATE_DIGITS.sub("{ID}", path)
    path = _TEMPLATE_SLUG.sub("{SLUG}", path)
    return f"{p.netloc}{path}"


def crawl_and_capture(
    start_url: str,
    run_dir: Path,
    *,
    max_pages: int = 12,
    max_per_template: int = 2,
    session_dir: Path | None = None,
) -> list[PageCapture]:
    """BFS spider, capturing each page. Stops at max_pages or queue empty.

    Template-aware sampling: at most `max_per_template` pages per URL pattern
    (e.g. only 2 of N person profiles, not all of them). The start URL always
    captures regardless of template count.
    """
    run_dir.mkdir(parents=True, exist_ok=True)

    captures: list[PageCapture] = []
    visited: set[str] = set()
    template_count: dict[str, int] = {}
    queue: deque[str] = deque([start_url])
    start_template = _template_key(start_url)

    with sync_playwright() as p:
        ctx_kwargs: dict = {"viewport": DEFAULT_VIEWPORT, "ignore_https_errors": True}
        if session_dir and session_dir.exists():
            browser = p.chromium.launch_persistent_context(str(session_dir), headless=True, **ctx_kwargs)
            context = browser
        else:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(**ctx_kwargs)

        console: list = []
        net_err: list = []

        while queue and len(captures) < max_pages:
            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)
            tkey = _template_key(url)
            if tkey != start_template and template_count.get(tkey, 0) >= max_per_template:
                print(f"  [skip:{tkey}] template cap reached")
                continue
            print(f"  [{len(captures)+1}/{max_pages}] capturing {url} ({tkey})")
            template_count[tkey] = template_count.get(tkey, 0) + 1
            cap = _capture_one(context, url, run_dir, console, net_err)
            if cap is None:
                continue
            captures.append(cap)
            for link in cap.links:
                if link not in visited and link not in queue:
                    queue.append(link)
            time.sleep(0.3)

        try:
            context.close()
        except Exception:
            pass
        if "browser" in locals() and hasattr(browser, "close"):
            try:
                browser.close()
            except Exception:
                pass

    return captures
