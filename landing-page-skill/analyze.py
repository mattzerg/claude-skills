#!/usr/bin/env python3
"""
Landing Page Analyzer — screenshot, scrape, and extract structured insights from any URL.
Uses the Claude Code CLI (claude --print) — no separate API key needed.

Usage:
    python3 analyze.py https://cursor.com [https://devin.ai ...] [options]

Options:
    --save DIR          Save JSON insights to directory (default: ./insights)
    --no-screenshot     Skip Playwright screenshot (faster, text-only)
"""

import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

SKILL_DIR = Path(__file__).parent
INSIGHTS_DIR = SKILL_DIR / "insights"
CLAUDE_BIN = str(Path.home() / ".local" / "bin" / "claude")

_AITR_SCRIPTS = Path.home() / ".claude" / "skills" / "aitr" / "scripts"
_ROUTED_MODEL = None


def _routed_model() -> str:
    """aitr-routed CLI model (flat Max-plan); loud fallback to sonnet-4-6. Memoized."""
    global _ROUTED_MODEL
    if _ROUTED_MODEL is None:
        if str(_AITR_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(_AITR_SCRIPTS))
        try:
            from skill_default import aitr_model_or
            _ROUTED_MODEL = aitr_model_or(
                "claude-sonnet-4-6", task_kind="prose-review", caller="landing-page-analyze",
                quality_floor="medium",
            modality_required="vision",
            )
        except ImportError:
            _ROUTED_MODEL = "claude-sonnet-4-6"
    return _ROUTED_MODEL


ANALYSIS_PROMPT = """You are a conversion-focused landing page analyst. Analyze this landing page and return a JSON object with the following structure. Be specific and quote actual text from the page where relevant.

{
  "url": "the URL analyzed",
  "company": "company name",
  "tagline": "the main headline (H1)",
  "subheadline": "the subheadline or hero body text",
  "value_proposition": "one-sentence distillation of what they're selling",
  "target_audience": "who this page is clearly aimed at",
  "primary_cta": {"text": "CTA button text", "placement": "hero/nav/sticky/etc"},
  "secondary_cta": {"text": "...", "placement": "..."},
  "social_proof": {
    "logos": ["company names shown"],
    "testimonials": ["key quotes"],
    "metrics": ["key numbers like '10k users' or '$2B processed'"],
    "press": ["publications mentioned"]
  },
  "pricing": {
    "model": "freemium/trial/contact-sales/self-serve/etc",
    "tiers": ["tier names if visible"],
    "price_anchoring": "how they frame value vs price"
  },
  "features": ["top 5 features/benefits mentioned"],
  "differentiators": ["explicit claims of uniqueness or superiority"],
  "trust_signals": ["security badges, certifications, guarantees, etc"],
  "navigation": ["main nav items"],
  "design_patterns": {
    "layout": "describe the overall layout",
    "color_scheme": "primary colors used",
    "typography": "font style characterization",
    "visual_style": "minimal/bold/technical/warm/etc",
    "notable_patterns": ["hero pattern", "animation types", "card styles"]
  },
  "emotional_tone": "urgent/confident/friendly/technical/aspirational/etc",
  "key_objections_addressed": ["objections or hesitations they proactively handle"],
  "missing_or_weak": ["things a strong landing page would have that this one lacks or does poorly"],
  "standout_elements": ["what this page does particularly well"],
  "score": {
    "clarity": 8,
    "credibility": 7,
    "conversion_focus": 9,
    "differentiation": 6,
    "overall": 7
  }
}

Return only valid JSON. No markdown, no preamble."""


def slugify(text):
    return re.sub(r'[^\w-]', '-', text.lower()).strip('-')[:60]


def get_domain(url):
    return urlparse(url).netloc.replace('www.', '')


def screenshot_and_scrape(url: str, save_dir: Path = None) -> tuple:
    """Take a screenshot and extract text content from a URL."""
    screenshot_path = None
    text_content = ""

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            print(f"  Loading {url}...")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)

            # Save screenshot to temp file
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            page.screenshot(path=tmp.name, full_page=True)
            screenshot_path = Path(tmp.name)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text_content = soup.get_text(separator="\n", strip=True)
            text_content = re.sub(r'\n{3,}', '\n\n', text_content)[:12000]
            browser.close()

        if save_dir and screenshot_path:
            domain = slugify(get_domain(url))
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = save_dir / f"{domain}_{ts}.png"
            screenshot_path.rename(dest)
            screenshot_path = dest
            print(f"  Screenshot saved: {dest.name}")

    except Exception as e:
        print(f"  Warning: Playwright error ({e}), falling back to requests...")
        screenshot_path = None
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text_content = soup.get_text(separator="\n", strip=True)
            text_content = re.sub(r'\n{3,}', '\n\n', text_content)[:12000]
        except Exception as e2:
            print(f"  Error: Could not fetch page ({e2})")

    return screenshot_path, text_content


def call_claude(prompt: str, image_path: Path = None) -> str:
    """Call Claude CLI, optionally with an image attachment."""
    cmd = [CLAUDE_BIN, "--print", "--model", _routed_model()]

    if image_path and image_path.exists():
        # Embed image as base64 in prompt
        img_b64 = base64.b64encode(image_path.read_bytes()).decode()
        full_prompt = f"{prompt}\n\n[IMAGE_BASE64_PNG:{img_b64[:100]}...]"
        # Claude CLI doesn't support image stdin directly, so omit image
        # and rely on text content instead
        full_prompt = prompt
    else:
        full_prompt = prompt

    result = subprocess.run(
        cmd + ["--tools", ""],
        input=full_prompt,
        capture_output=True,
        text=True,
        timeout=300
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr.strip()}")
    return result.stdout.strip()


def analyze_with_claude(url: str, text: str) -> dict:
    """Send page content to Claude CLI for structured analysis."""
    prompt = f"URL: {url}\n\nPage text content:\n{text}\n\n{ANALYSIS_PROMPT}"
    print(f"  Analyzing with Claude...")
    raw = call_claude(prompt)

    # Strip markdown code fences if present
    raw = re.sub(r'^```(?:json)?\n?', '', raw)
    raw = re.sub(r'\n?```$', '', raw)
    # Strip preamble before first {
    idx = raw.find('{')
    if idx > 0:
        raw = raw[idx:]
    # Strip trailing text after final }
    last = raw.rfind('}')
    if last != -1:
        raw = raw[:last+1]

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  Warning: JSON parse error ({e})")
        return {"url": url, "raw": raw, "parse_error": str(e)}


def analyze_url(url: str, save_dir: Path, take_screenshot: bool) -> dict:
    domain = get_domain(url)
    print(f"\n[{domain}]")

    screenshot_save = save_dir if take_screenshot else None
    screenshot_path, text = screenshot_and_scrape(url, screenshot_save)

    if not text:
        print(f"  Error: No content retrieved from {url}")
        return {"url": url, "error": "No content retrieved"}

    insights = analyze_with_claude(url, text)
    insights["analyzed_at"] = datetime.now().isoformat()
    insights["url"] = url

    slug = slugify(domain)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = save_dir / f"{slug}_{ts}.json"
    out_path.write_text(json.dumps(insights, indent=2))
    print(f"  Saved: {out_path.name}")

    # Clean up temp screenshot if not saved to save_dir
    if screenshot_path and screenshot_path.exists() and screenshot_path.parent != save_dir:
        screenshot_path.unlink()

    return insights


def print_summary(insights: dict):
    url = insights.get("url", "?")
    company = insights.get("company", get_domain(url))
    print(f"\n{'='*60}")
    print(f"  {company} — {url}")
    print(f"{'='*60}")
    print(f"\nHeadline:   {insights.get('tagline', 'N/A')}")
    print(f"Value Prop: {insights.get('value_proposition', 'N/A')}")
    print(f"Audience:   {insights.get('target_audience', 'N/A')}")
    print(f"Tone:       {insights.get('emotional_tone', 'N/A')}")

    cta = insights.get("primary_cta", {})
    print(f"Primary CTA: \"{cta.get('text', 'N/A')}\" ({cta.get('placement', '?')})")

    score = insights.get("score", {})
    if score:
        print(f"\nScores: Clarity {score.get('clarity','-')}/10 | Credibility {score.get('credibility','-')}/10 | "
              f"Conversion {score.get('conversion_focus','-')}/10 | Differentiation {score.get('differentiation','-')}/10 | "
              f"Overall {score.get('overall','-')}/10")

    for label, key in [("Standout", "standout_elements"), ("Weaknesses", "missing_or_weak")]:
        items = insights.get(key, [])
        if items:
            sign = "+" if key == "standout_elements" else "-"
            print(f"\n{label}:")
            for item in items[:3]:
                print(f"  {sign} {item}")


def main():
    parser = argparse.ArgumentParser(description="Analyze landing pages with Claude")
    parser.add_argument("urls", nargs="+", help="URLs to analyze")
    parser.add_argument("--save", default=str(INSIGHTS_DIR), help="Directory to save JSON insights")
    parser.add_argument("--no-screenshot", action="store_true", help="Skip screenshots (faster)")
    args = parser.parse_args()

    save_dir = Path(args.save)
    save_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for url in args.urls:
        if not url.startswith("http"):
            url = "https://" + url
        insights = analyze_url(url, save_dir, not args.no_screenshot)
        results.append(insights)
        print_summary(insights)

    print(f"\n\nAnalyzed {len(results)} page(s). Insights saved to: {save_dir}")


if __name__ == "__main__":
    main()
