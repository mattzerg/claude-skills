#!/usr/bin/env python3
"""
scan.py — scrape a single competitor across 6 source types and extract a structured
feature profile. Saves raw JSON to insights/<domain>_<ts>.json and merges into the
category state.

Usage:
    python3 scan.py <category> <competitor-url> [--name "Display Name"]
    python3 scan.py <category> --all                # scan every competitor in state

Sources scraped (best-effort; missing ones noted):
    landing, pricing, changelog, docs/integrations, G2 reviews, HN search, Reddit search
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from lib import claude, scraper, sources, state, vault, news

SKILL_DIR = Path(__file__).resolve().parent
INSIGHTS_DIR = SKILL_DIR / "insights"

URL_RESOLVE_PROMPT = """For the company "{name}" (homepage: {home}), suggest the most likely current URLs for these resources. Use your knowledge of common conventions for this product. Return JSON only.

{{
  "pricing":   "https://... or null",
  "changelog": "https://... or null",
  "docs":      "https://... or null",
  "integrations": "https://... or null",
  "g2":        "https://www.g2.com/products/<slug>/reviews or null"
}}

Prefer canonical URLs. If you genuinely don't know, use null. No prose."""


SCAN_PROMPT = """You are a competitive intelligence analyst extracting a structured feature profile for "{name}".

You have raw text from multiple sources for this product. Extract the most complete possible feature inventory.

Return JSON:
{{
  "name": "{name}",
  "url": "{home}",
  "tagline": "their main headline",
  "value_proposition": "one-sentence distillation",
  "target_segment": "enterprise / mid-market / SMB / dev / consumer / etc",
  "ideal_customer": "who they're clearly built for",
  "features": [
    {{
      "name": "feature name (canonical, lowercase noun phrase like 'sub-issues' or 'github integration')",
      "description": "one-line description",
      "evidence_source": "landing|pricing|docs|changelog|integrations|g2|hn|reddit|other",
      "evidence_quote": "short verbatim quote from source backing this claim (≤120 chars)",
      "tier": "free|paid|enterprise|all|unknown",
      "confidence": "high|medium|low"
    }}
  ],
  "integrations": ["named third-party integrations"],
  "differentiators": ["explicit claims of uniqueness"],
  "recent_ships": [
    {{"date": "YYYY-MM or YYYY", "what": "shipped feature/change", "source": "changelog excerpt"}}
  ],
  "user_sentiment": {{
    "praised": ["what users like — quote where possible"],
    "complaints": ["what users complain about — quote where possible"],
    "sources": ["g2 / hn / reddit"]
  }},
  "pricing": {{
    "model": "freemium|trial|contact-sales|self-serve|open-source",
    "currency": "USD",
    "free_tier": {{"available": true, "limits": "seat/usage caps as one short string, or null"}},
    "tiers": [
      {{
        "name": "tier name as marketed (Pro / Business / Team / etc.)",
        "price_per_seat_per_month": "$X or null if non-seat-based",
        "price_flat_per_month": "$X or null if seat-based",
        "yearly_discount_pct": "approx % off if shown, or null",
        "headline_inclusions": "1-line summary of what's included (≤120 chars)"
      }}
    ],
    "enterprise": "contact-sales|$X+|null",
    "notes": "any pricing weirdness — usage-based caps, seat minimums, regional, etc"
  }}
}}

Be exhaustive on the features list — competitive review needs the complete surface, not the marketing top-5. Extract every distinct capability mentioned in any source. Use lowercase-canonical feature names so the same feature across competitors collides cleanly (e.g. always "sso", not "SSO" or "Single Sign-On").

For pricing: capture EVERY tier visible on the pricing page. Tier prices are critical — they drive positioning. If a tier price is "contact us" mark it as null; if a free tier exists, capture its seat/storage/project caps in `free_tier.limits`.

Confidence: "high" when feature appears in docs OR pricing page (real surface); "medium" when on landing page only; "low" when only inferred from marketing copy.

Return only valid JSON. No markdown, no preamble.

=== SOURCES ===
{sources_block}
"""


def domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def join_url(base: str, path: str) -> str:
    p = urlparse(base)
    return urlunparse((p.scheme, p.netloc, path.lstrip("/") and "/" + path.lstrip("/"), "", "", ""))


def _try_paths(home: str, paths: list[str]) -> dict | None:
    """Try common paths until one returns non-trivial content."""
    for path in paths:
        url = join_url(home, path)
        result = scraper.fetch(url, timeout_ms=15000, settle_seconds=0.8)
        if result and len(result.get("text", "")) > 500:
            result["fallback_path"] = path
            return result
    return None


def resolve_source_urls(name: str, home: str) -> dict:
    """Ask Claude for canonical URLs; fall back to common-path guesses for any null."""
    prompt = URL_RESOLVE_PROMPT.format(name=name, home=home)
    try:
        resolved = claude.call_claude_json(prompt, timeout=120)
        if not isinstance(resolved, dict):
            resolved = {}
    except Exception as e:
        print(f"  [warn] URL resolve failed: {e}", file=sys.stderr)
        resolved = {}

    # G2 fallback
    if not resolved.get("g2"):
        resolved["g2"] = sources.g2_url_guess(name)
    return resolved


def scan_competitor(competitor: dict) -> dict:
    name = competitor["name"]
    home = competitor["url"]
    dom = competitor.get("domain") or domain(home)

    print(f"\n[scan] {name}  <{home}>", file=sys.stderr)
    profile: dict = {
        "name": name,
        "url": home,
        "domain": dom,
        "scanned_at": datetime.now().isoformat(),
        "sources": {},
    }

    # Landing
    landing = scraper.fetch(home)
    profile["sources"]["landing"] = landing or {"error": "fetch failed"}

    # Resolve other URLs
    resolved = resolve_source_urls(name, home)
    profile["resolved_urls"] = resolved

    for key in ("pricing", "changelog", "docs", "integrations", "g2"):
        url = resolved.get(key)
        result = None
        if url:
            print(f"  [{key}] {url}", file=sys.stderr)
            result = scraper.fetch(url, timeout_ms=20000, settle_seconds=1.0)
        if (not result or len(result.get("text", "")) < 300) and key in sources.COMMON_PATHS:
            fallback = _try_paths(home, sources.COMMON_PATHS[key])
            if fallback:
                print(f"  [{key}] fallback path worked: {fallback['fallback_path']}", file=sys.stderr)
                result = fallback
        profile["sources"][key] = result or {"error": "no content", "url": url}

    # HN + Reddit are JSON-API. Use the brand domain as a context term to filter generic junk.
    brand_context = [dom.split(".")[0]] if dom else []
    print(f"  [hn] searching...", file=sys.stderr)
    profile["sources"]["hn"] = {"hits": sources.hn_search(name, limit=8)}
    print(f"  [reddit] searching...", file=sys.stderr)
    profile["sources"]["reddit"] = {"hits": sources.reddit_search(name, context_terms=brand_context, limit=8)}

    # Build sources_block for Claude
    parts = []
    for key, data in profile["sources"].items():
        if isinstance(data, dict) and data.get("text"):
            parts.append(f"--- {key.upper()} ({data.get('url','')}) ---\n{data['text'][:6000]}")
        elif key == "hn" and data.get("hits"):
            hn_lines = [f"- ({h['points']}↑ {h['num_comments']}c) {h['title']}" for h in data["hits"]]
            parts.append("--- HACKER NEWS ---\n" + "\n".join(hn_lines))
        elif key == "reddit" and data.get("hits"):
            r_lines = [f"- (r/{h['subreddit']} {h['score']}↑ {h['num_comments']}c) {h['title']}" for h in data["hits"]]
            parts.append("--- REDDIT ---\n" + "\n".join(r_lines))

    sources_block = "\n\n".join(parts)[:30000]  # bound prompt size

    if not sources_block.strip():
        profile["analysis"] = {"error": "no source content gathered", "features": []}
        return profile

    prompt = SCAN_PROMPT.format(name=name, home=home, sources_block=sources_block)
    print(f"  [analyze] sending {len(sources_block)} chars to Claude...", file=sys.stderr)
    try:
        analysis = claude.call_claude_json(prompt, timeout=300)
        profile["analysis"] = analysis
    except Exception as e:
        profile["analysis"] = {"error": str(e), "features": []}

    # News signal: HN coverage in the last 90 days + GitHub stars (if OSS)
    print(f"  [news] checking recent signals...", file=sys.stderr)
    profile["news"] = {"recent_hn": news.recent_news(name, days=90, limit=5)}
    # Try to extract a github repo from any scraped text
    all_text = " ".join(
        (d.get("text") or "")[:3000]
        for d in profile["sources"].values()
        if isinstance(d, dict)
    )[:30000]
    repo = news.extract_github_repo(all_text)
    if repo:
        gh = news.github_stars(repo)
        if gh:
            profile["news"]["github"] = gh

    return profile


def save_profile(profile: dict) -> Path:
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = vault.slugify(profile["domain"])
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = INSIGHTS_DIR / f"{slug}_{ts}.json"
    out.write_text(json.dumps(profile, indent=2, default=str), encoding="utf-8")
    return out


def main():
    parser = argparse.ArgumentParser(description="Scan one or all competitors")
    parser.add_argument("category")
    parser.add_argument("url", nargs="?", help="Competitor URL (omit with --all)")
    parser.add_argument("--name", help="Display name (defaults to domain)")
    parser.add_argument("--all", action="store_true", help="Scan every competitor in state")
    args = parser.parse_args()

    s = state.load(args.category)
    candidates = s.get("candidates", [])

    if args.all:
        if not candidates:
            print("Error: no candidates in state. Run discover.py first.", file=sys.stderr)
            sys.exit(1)
        targets = candidates
    else:
        if not args.url:
            print("Error: pass a URL or --all", file=sys.stderr)
            sys.exit(1)
        url = args.url if args.url.startswith("http") else "https://" + args.url
        match = next((c for c in candidates if c.get("domain") == domain(url)), None)
        if match:
            targets = [match]
        else:
            targets = [{"name": args.name or domain(url), "url": url, "domain": domain(url)}]

    scans = s.get("scans", {})
    for c in targets:
        try:
            profile = scan_competitor(c)
            save_profile(profile)
            scans[c["domain"]] = profile
            time.sleep(1)  # polite spacing
        except Exception as e:
            print(f"  [error] {c['name']}: {e}", file=sys.stderr)
            scans[c["domain"]] = {"name": c["name"], "url": c["url"], "domain": c["domain"], "error": str(e)}

    state.update(args.category, scans=scans)
    print(f"\n[scan] {len(targets)} competitor(s) scanned. State updated.")


if __name__ == "__main__":
    main()
