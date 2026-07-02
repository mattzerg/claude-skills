#!/usr/bin/env python3
"""
compare.py — reconcile our-side (vault spec + live scrape) against competitor scans,
build a canonical feature matrix, classify gaps into 4 buckets, detect spec↔live drift.

Architecture: instead of one mega-synthesis Claude call (which times out for 9+ competitors),
this runs three staged passes:

  Stage A — Canonical feature inventory: list ~50 canonical feature names + categories.
            One small Claude call (small output).
  Stage B — Presence matrix: for each chunk of 15 features, ask Claude to return
            presence ("yes"/"partial"/"no"/"unknown") for every competitor + Us(spec) + Us(live).
            Multiple small Claude calls.
  Stage C — Drift detection: small focused call over Us(spec) vs Us(live).

Frequency, bucket assignment, and final structure are computed in Python from the presence matrix.

Reads state from discover/scan; writes:
  - state.spec        (product spec note contents)
  - state.live        (live URL scrape)
  - state.matrix      (feature × competitor + Us(spec) + Us(live) + bucket)
  - state.drift       (spec vs live mismatches)

Usage:
    python3 compare.py <category> --product <ZergProduct> [--chunk 15]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from lib import claude, scraper, state, vault

INVENTORY_PROMPT = """You are a competitive intelligence analyst building a feature inventory for the "{category}" product category.

Below are feature lists scraped from {n} competitors. Produce a CANONICAL feature inventory that consolidates duplicates and standardizes naming.

Rules:
1. Use lowercase canonical noun phrases (e.g. "sub-issues", "github integration", "sso", "kanban view").
2. Same capability with different names → ONE row.
3. Be EXHAUSTIVE — aim for 40-70 features that span the whole category surface. Don't drop niche-but-real features.
4. Group into categories: core, integrations, ai, admin, ux, automation, collaboration, reporting, mobile, other.

Return JSON only:
{{
  "features": [
    {{"name": "canonical-feature-name", "category": "core|integrations|ai|admin|ux|automation|collaboration|reporting|mobile|other"}}
  ]
}}

No prose. No markdown.

=== COMPETITOR FEATURES ===
{competitor_features}
"""


PRESENCE_PROMPT = """You are filling in a feature presence matrix for the "{category}" category.

For each canonical feature in the LIST below, mark presence in each source as one of:
- "yes"     — clearly present, confirmed in source content
- "partial" — limited form, gated to enterprise tier, or in beta
- "no"      — clearly absent
- "unknown" — not enough information either way

CANONICAL FEATURES (this chunk):
{features_chunk}

SOURCES TO MARK
================
{sources_block}

OUR PRODUCT (Zerg's "{product}")
SPEC NOTE (claims; from internal vault):
{spec_text}

LIVE SITE SCRAPE:
{live_text}
================

Return JSON only:
{{
  "rows": [
    {{
      "feature": "canonical-feature-name (must match exactly from LIST above)",
      "presence": {{
        {presence_keys_template}
        "us_spec": "yes|partial|no|unknown",
        "us_live": "yes|partial|no|unknown"
      }},
      "confidence": "high|medium|low",
      "source_summary": "one phrase saying where the strongest evidence comes from (e.g. 'docs page for Linear, pricing page for Asana')"
    }}
  ]
}}

Confidence rubric:
- "high": ≥3 competitors confirm presence in their docs/pricing (real surface, not marketing copy)
- "medium": 1-2 competitors confirm in docs OR several confirm via landing page only
- "low": only inferred from marketing copy or sentiment, not directly observed in product surface

Output ONE row per feature in the LIST. No prose. No markdown."""


DRIFT_PROMPT = """You are detecting spec ↔ live-site drift for the Zerg product "{product}".

Below is the team's internal SPEC note (what we claim), and a live SCRAPE of the public site (what users see).

Identify features the SPEC claims that the live site doesn't show, OR features the live site shows that the spec doesn't mention. For each, note whether it's a marketing gap (have it but don't surface it) or a spec-aspiration gap (claim something we don't actually ship).

SPEC NOTE
{spec_text}

LIVE SITE
{live_text}

Return JSON only:
{{
  "drift": [
    {{
      "feature": "lowercase canonical name",
      "spec_says": "yes|partial|no",
      "live_says": "yes|partial|no",
      "note": "marketing gap | spec aspiration | description mismatch | other; one sentence"
    }}
  ]
}}

Only include items where spec ≠ live in a meaningful way. Skip items where both are unknown. No prose."""


def build_competitor_features_block(scans: dict, max_features: int = 60) -> str:
    parts = []
    for dom, scan in scans.items():
        if scan.get("error"):
            continue
        analysis = scan.get("analysis", {})
        if not analysis or analysis.get("error"):
            continue
        features = analysis.get("features", [])
        feat_lines = [f"  - {f.get('name','?')}" for f in features[:max_features]]
        parts.append(f"--- {analysis.get('name', dom)} ({dom}) ---\n" + "\n".join(feat_lines))
    return "\n\n".join(parts)


def build_sources_block(scans: dict, max_features: int = 50) -> str:
    """Compact per-competitor source for presence-matrix calls."""
    parts = []
    for dom, scan in scans.items():
        if scan.get("error"):
            continue
        analysis = scan.get("analysis", {})
        if not analysis or analysis.get("error"):
            continue
        features = analysis.get("features", [])
        flat_names = [f.get("name", "") for f in features[:max_features]]
        differentiators = analysis.get("differentiators", [])
        integrations = analysis.get("integrations", [])[:30]
        parts.append(
            f"=== {dom} ({analysis.get('name','?')}) ===\n"
            f"features: {', '.join(flat_names)}\n"
            f"differentiators: {', '.join(differentiators)}\n"
            f"integrations: {', '.join(integrations)}"
        )
    return "\n\n".join(parts)


def chunk_features(features: list[dict], size: int) -> list[list[dict]]:
    return [features[i : i + size] for i in range(0, len(features), size)]


def _normalize(name: str) -> str:
    return (name or "").strip().lower().replace("_", "-").replace("  ", " ")


def merge_presence_rows(rows: list[dict], inventory: list[dict]) -> list[dict]:
    """Combine presence rows (across chunks) and attach category from inventory.
    Match feature names case-insensitively + with mild normalization. Falls back to
    fuzzy substring match for anything not exact."""
    inv_by_norm = {_normalize(f["name"]): f for f in inventory}
    merged = []
    seen_inv_keys = set()  # which inventory features we've covered

    for r in rows:
        raw_name = r.get("feature", "")
        norm = _normalize(raw_name)
        if not norm:
            continue
        # Exact normalized match
        match = inv_by_norm.get(norm)
        # Fuzzy fallback: substring either direction
        if not match:
            candidates = [k for k in inv_by_norm if norm in k or k in norm]
            if len(candidates) == 1:
                match = inv_by_norm[candidates[0]]
        if not match:
            continue
        if match["name"] in seen_inv_keys:
            continue
        seen_inv_keys.add(match["name"])
        merged.append(
            {
                "feature": match["name"],
                "category": match.get("category", "other"),
                "presence": r.get("presence", {}),
                "confidence": r.get("confidence", "low"),
                "source_summary": r.get("source_summary", ""),
            }
        )

    # Add any inventory items the rows missed (with all unknown)
    for f in inventory:
        if f["name"] not in seen_inv_keys:
            merged.append(
                {
                    "feature": f["name"],
                    "category": f.get("category", "other"),
                    "presence": {},
                }
            )
    return merged


def assign_buckets(matrix: list[dict], competitor_keys: list[str]) -> dict:
    """Compute frequency + bucket per row, in Python.

    Reads thresholds + partial-weight from lib.config (config.json wizard prefs)
    so changes there flow through without code edits.
    """
    from lib import config as cfg

    ts_threshold = cfg.bucket_threshold_table_stakes()      # default 0.75 (was 0.60)
    parity_lower = cfg.bucket_threshold_parity_lower()      # default 0.25
    partial_w = cfg.partial_presence_weight()               # default 0.5 (was 1.0)

    n_comp = len(competitor_keys)
    summary = {
        "n_features": len(matrix),
        "table_stakes_count": 0,
        "differentiator_parity_count": 0,
        "whitespace_count": 0,
        "we_have_they_dont_count": 0,
        "drift_count": 0,
        "_thresholds": {"table_stakes": ts_threshold, "parity_lower": parity_lower, "partial_weight": partial_w},
    }
    for row in matrix:
        presence = row.get("presence", {})
        # weighted frequency: yes=1.0, partial=partial_w, no/unknown=0.0
        freq_weighted = 0.0
        for k in competitor_keys:
            v = presence.get(k)
            if v == "yes":
                freq_weighted += 1.0
            elif v == "partial":
                freq_weighted += partial_w
        # frequency stored as integer for display (round half-up)
        row["frequency"] = int(round(freq_weighted))
        row["frequency_weighted"] = round(freq_weighted, 2)

        us_spec = presence.get("us_spec", "unknown")
        us_live = presence.get("us_live", "unknown")
        we_have = us_spec in ("yes", "partial") or us_live in ("yes", "partial")

        ratio = (freq_weighted / n_comp) if n_comp else 0
        if ratio >= ts_threshold and not we_have:
            row["bucket"] = "table_stakes"
            summary["table_stakes_count"] += 1
        elif parity_lower <= ratio < ts_threshold:
            row["bucket"] = "differentiator_parity"
            summary["differentiator_parity_count"] += 1
        elif freq_weighted == 0 and not we_have:
            row["bucket"] = "whitespace"
            summary["whitespace_count"] += 1
        elif we_have and ratio < parity_lower:
            row["bucket"] = "we_have_they_dont"
            summary["we_have_they_dont_count"] += 1
        else:
            # Edge case: high ratio AND we have it → just call it parity (covered)
            row["bucket"] = "differentiator_parity"
            summary["differentiator_parity_count"] += 1

        row["evidence"] = ""
    return summary


def main():
    parser = argparse.ArgumentParser(description="Build feature matrix + gap analysis (staged)")
    parser.add_argument("category")
    parser.add_argument("--product", required=True)
    parser.add_argument("--chunk", type=int, default=15, help="Features per presence-matrix Claude call")
    parser.add_argument("--max-features-per-competitor", type=int, default=50)
    parser.add_argument("--reuse-inventory", action="store_true",
                        help="Skip Stage A; reuse canonical inventory from existing state.matrix (feature, category) pairs")
    args = parser.parse_args()

    s = state.load(args.category)
    scans = s.get("scans", {})
    if not scans:
        print("Error: no scans in state. Run scan.py first.", file=sys.stderr)
        sys.exit(1)

    # Read spec
    spec = vault.read_product_spec(args.product)
    if not spec:
        print(f"Error: no product spec found at MattZerg/Projects/Zerg-Production/Zstack/{args.product}.md", file=sys.stderr)
        sys.exit(1)

    # Scrape live
    live_url = spec.get("live_url")
    if live_url:
        print(f"[compare] scraping live site: {live_url}", file=sys.stderr)
        live = scraper.fetch(live_url)
    else:
        live = {"url": "", "text": "", "error": "no live_url"}
    spec_text = (spec["body"] or "")[:4000]
    live_text = (live.get("text") or "")[:4000] if live else ""

    competitor_keys = [d for d, sc in scans.items() if sc.get("analysis") and not sc["analysis"].get("error")]

    # ============ STAGE A — Canonical inventory ============
    inventory = []
    if args.reuse_inventory:
        prev_matrix = s.get("matrix", [])
        inventory = [{"name": r["feature"], "category": r.get("category", "other")} for r in prev_matrix]
        print(f"[compare] Stage A: reusing {len(inventory)} features from prior state.matrix", file=sys.stderr)
    if not inventory:
        print(f"[compare] Stage A: canonical feature inventory ({len(competitor_keys)} competitors)", file=sys.stderr)
        feat_block = build_competitor_features_block(scans, max_features=args.max_features_per_competitor)
        inv_prompt = INVENTORY_PROMPT.format(
            category=args.category,
            n=len(competitor_keys),
            competitor_features=feat_block,
        )
        print(f"[compare]   prompt size: {len(inv_prompt)} chars", file=sys.stderr)
        inv_result = claude.call_claude_json(inv_prompt, timeout=900)
        inventory = inv_result.get("features", []) if isinstance(inv_result, dict) else []
        if not inventory:
            print(f"Error: empty canonical inventory: {inv_result}", file=sys.stderr)
            sys.exit(1)
        print(f"[compare]   {len(inventory)} canonical features", file=sys.stderr)

    # ============ STAGE B — Presence matrix in chunks ============
    sources_block = build_sources_block(scans, max_features=args.max_features_per_competitor)
    presence_keys_template = "\n        ".join(f'"{k}": "yes|partial|no|unknown",' for k in competitor_keys)

    chunks = chunk_features(inventory, args.chunk)
    print(f"[compare] Stage B: presence matrix in {len(chunks)} chunks of ~{args.chunk}", file=sys.stderr)
    all_rows = []
    for i, chunk in enumerate(chunks, 1):
        chunk_block = "\n".join(f"  - {f['name']} ({f.get('category','?')})" for f in chunk)
        prompt = PRESENCE_PROMPT.format(
            category=args.category,
            product=args.product,
            features_chunk=chunk_block,
            sources_block=sources_block,
            spec_text=spec_text,
            live_text=live_text,
            presence_keys_template=presence_keys_template,
        )
        print(f"[compare]   chunk {i}/{len(chunks)}: {len(chunk)} features, prompt {len(prompt)} chars", file=sys.stderr)
        try:
            result = claude.call_claude_json(prompt, timeout=600)
            rows = result.get("rows", []) if isinstance(result, dict) else []
            all_rows.extend(rows)
            print(f"[compare]     -> {len(rows)} rows returned", file=sys.stderr)
        except Exception as e:
            print(f"[compare]   chunk {i} failed: {e}", file=sys.stderr)

    matrix = merge_presence_rows(all_rows, inventory)
    summary = assign_buckets(matrix, competitor_keys)

    # ============ STAGE C — Drift detection ============
    print(f"[compare] Stage C: drift detection", file=sys.stderr)
    drift_prompt = DRIFT_PROMPT.format(product=args.product, spec_text=spec_text, live_text=live_text)
    drift = []
    try:
        drift_result = claude.call_claude_json(drift_prompt, timeout=300)
        drift = drift_result.get("drift", []) if isinstance(drift_result, dict) else []
        summary["drift_count"] = len(drift)
    except Exception as e:
        print(f"[compare]   drift detection failed: {e}", file=sys.stderr)

    # Persist
    matched_count = sum(1 for r in matrix if r.get("presence"))
    state.update(
        args.category,
        product=args.product,
        spec={"path": spec["path"], "frontmatter": spec["frontmatter"], "body": spec["body"]},
        live=live,
        matrix=matrix,
        raw_presence_rows=all_rows,  # for debugging
        drift=drift,
        compare_summary=summary,
        compared_at=datetime.now().isoformat(),
    )
    print(f"[compare] matched {matched_count}/{len(matrix)} features to presence rows", file=sys.stderr)

    print(f"\n[compare] done.")
    print(f"  Features:           {summary['n_features']}")
    print(f"  Table stakes gaps:  {summary['table_stakes_count']}")
    print(f"  Differentiator:     {summary['differentiator_parity_count']}")
    print(f"  Whitespace:         {summary['whitespace_count']}")
    print(f"  We-have-they-don't: {summary['we_have_they_dont_count']}")
    print(f"  Drift items:        {summary['drift_count']}")


if __name__ == "__main__":
    main()
