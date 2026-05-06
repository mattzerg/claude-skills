"""Playwright + BeautifulSoup scraper. Single function returns (text, html_title) for a URL.
Falls back to urllib if Playwright fails (mirrors landing-page-skill/analyze.py)."""

from __future__ import annotations

import re
import time
from typing import Optional

from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

MAX_TEXT = 14000  # per-page cap to keep prompts bounded


def _clean(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)[:MAX_TEXT]
    return text, title


def fetch(url: str, *, timeout_ms: int = 25000, settle_seconds: float = 1.5) -> Optional[dict]:
    """Return {url, title, text, source} or None on total failure."""
    # Playwright path
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=USER_AGENT,
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            except Exception:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            time.sleep(settle_seconds)
            html = page.content()
            browser.close()
        text, title = _clean(html)
        return {"url": url, "title": title, "text": text, "source": "playwright"}
    except Exception as e:
        playwright_err = str(e)

    # urllib fallback
    try:
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        text, title = _clean(html)
        return {"url": url, "title": title, "text": text, "source": "urllib"}
    except Exception as e:
        return {
            "url": url,
            "title": "",
            "text": "",
            "source": "failed",
            "error": f"playwright: {playwright_err}; urllib: {e}",
        }


def fetch_many(urls: list[str]) -> list[dict]:
    """Sequential fetch — Playwright handles its own context per call."""
    return [fetch(u) for u in urls]
