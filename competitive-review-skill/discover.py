#!/usr/bin/env python3
"""
discover.py — find candidate competitors for a category.

Always scans broadly via Claude CLI (which has model-side knowledge of the market),
merges with any user-supplied seeds, and prints the candidate list as JSON
plus a human-readable summary. The orchestrator (or user) confirms before scan.

Usage:
    python3 discover.py <category> [seed1.com seed2.com ...] [--product ZergProduct] [--n 10]
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import urlparse

from lib import claude, state, vault

DISCOVER_PROMPT = """You are a competitive intelligence analyst. The user is reviewing the "{category}" product category{product_clause}.

User-supplied seed competitors:
{seeds}

Return a JSON array of {n} distinct, currently-active companies/products in this category. Include the seeds (re-fetch their canonical URLs and brief descriptions) plus the most relevant additional players. Prefer products that real teams actually evaluate against each other — not dead, niche, or obscure ones.

For each: {{
  "name": "company/product name",
  "url": "canonical homepage URL (https://...)",
  "one_liner": "what they do, ≤ 15 words",
  "segment": "enterprise / mid-market / SMB / dev-tool / consumer / open-source / etc",
  "is_seed": true|false
}}

Return only valid JSON array. No prose, no markdown."""


def normalize_url(s: str) -> str:
    s = s.strip()
    if not s:
        return ""
    if not s.startswith(("http://", "https://")):
        s = "https://" + s
    return s


def domain(url: str) -> str:
    return urlparse(url).netloc.lower().lstrip("www.")


def main():
    parser = argparse.ArgumentParser(description="Discover competitors for a category")
    parser.add_argument("category")
    parser.add_argument("seeds", nargs="*", help="Seed competitor URLs or names")
    parser.add_argument("--product", help="Zerg product name (for context only)")
    parser.add_argument("--n", type=int, default=10, help="Target candidate count (default 10)")
    args = parser.parse_args()

    seeds = [normalize_url(s) for s in args.seeds if s.strip()]
    seeds_block = "\n".join(f"- {s}" for s in seeds) if seeds else "(none — discover from scratch)"

    product_clause = f" against the Zerg product '{args.product}'" if args.product else ""
    prompt = DISCOVER_PROMPT.format(
        category=args.category,
        product_clause=product_clause,
        seeds=seeds_block,
        n=args.n,
    )

    print(f"\n[discover] category={args.category} seeds={len(seeds)} target={args.n}", file=sys.stderr)
    print(f"[discover] querying Claude for candidates...", file=sys.stderr)

    candidates = claude.call_claude_json(prompt)
    if not isinstance(candidates, list):
        print(f"Error: expected JSON array, got {type(candidates)}", file=sys.stderr)
        sys.exit(1)

    # Dedupe by domain; mark seeds even if model forgot
    seed_domains = {domain(s) for s in seeds}
    seen = set()
    deduped = []
    for c in candidates:
        url = normalize_url(c.get("url", ""))
        if not url:
            continue
        d = domain(url)
        if d in seen:
            continue
        seen.add(d)
        c["url"] = url
        c["domain"] = d
        c["is_seed"] = c.get("is_seed", False) or d in seed_domains
        deduped.append(c)

    # Persist to state
    state.update(args.category, product=args.product, seeds=seeds, candidates=deduped)

    # Output
    print("\n=== Candidate competitors ===")
    for i, c in enumerate(deduped, 1):
        marker = "[SEED]" if c.get("is_seed") else "      "
        print(f"  {i:2d}. {marker} {c['name']:<30s}  {c.get('url','')}")
        print(f"           {c.get('one_liner','')}  ({c.get('segment','?')})")
    print(f"\n{len(deduped)} candidates saved to state.")
    print("\nNext: confirm, add, or remove competitors, then run scan.py for each.")
    print(json.dumps({"candidates": deduped}, indent=2))


if __name__ == "__main__":
    main()
