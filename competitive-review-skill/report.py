#!/usr/bin/env python3
"""
report.py — write the full vault output for a competitive review.

Outputs to MattZerg/Competitive/<category>/:
  index.md         (top-level summary + "What changed")
  matrix.md        (feature × competitor table)
  gaps.md          (4-bucket gap analysis, ranked)
  positioning.md   (differentiator one-liners + headline candidates)
  drift.md         (spec ↔ live mismatches, only if any)
  competitors/<name>.md   (per-competitor deep notes)

Also writes a JSON handoff to landing-page-skill/insights/competitive_<category>_<ts>.json.

Archives any prior run to archive/<date>/ before writing.

Usage:
    python3 report.py <category> --product <ZergProduct> [--no-positioning]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from lib import claude, priors, state, vault, config as cfg, internal, news

LP_INSIGHTS_DIR = Path.home() / ".claude" / "skills" / "landing-page-skill" / "insights"


POSITIONING_PROMPT = """You are a positioning strategist advising the Zerg team on the "{product}" product.

Below is the competitive landscape for category "{category}":
- Our differentiators (we-have-they-don't): {ours}
- Common complaints across competitors: {complaints}
- Whitespace opportunities (no one has it): {whitespace}
- Key table-stakes gaps we need to close: {gaps}

INTERNAL FRICTION (Matt's own complaints from Slack/standup — first-party signal):
{internal_friction}

PRODUCT SPEC (excerpt)
{spec_excerpt}

Produce a positioning + messaging brief as JSON:

{{
  "elevator_pitch": "one sentence — what we are, who it's for, why it's different",
  "core_differentiator_lines": [
    "≤12-word punchy one-liner stating a differentiator (3-5 of these)"
  ],
  "headline_candidates": [
    {{"headline": "...", "subhead": "...", "angle": "speed|simplicity|pricing|integration|agent-native|reliability|other"}}
  ],
  "messaging_pillars": [
    {{"pillar": "name", "promise": "what we promise", "proof_points": ["concrete claim", "..."]}}
  ],
  "anti_pitch": [
    "what we are NOT — competitor patterns we should avoid imitating, with reason"
  ],
  "icp_refinement": "who this product is most for, given the competitive landscape",
  "objection_handling": [
    {{"objection": "X is cheaper / more mature / etc", "response": "how we counter"}}
  ]
}}

Be specific. Quote real competitor patterns where relevant. Return only valid JSON. No prose."""


def render_index(s: dict, prior_diff: str, priors_summary: str) -> str:
    """Index.md is the navigation + skim layer. Frontload synthesis; demote reference material.

    Layout: TL;DR → What changed → Top 5 priorities → Strongest positioning angle →
    Where to look (file-by-file nav table) → At a glance counts → Compact priors at bottom.
    """
    summary = s.get("compare_summary", {})
    rankings = s.get("rankings", [])
    drift = s.get("drift", [])
    competitors = list(s.get("scans", {}).keys())
    positioning = s.get("positioning") or {}
    prior_audits = s.get("prior_audits") or []
    today = datetime.now().strftime("%Y-%m-%d")

    n_ts = summary.get("table_stakes_count", 0)
    n_dp = summary.get("differentiator_parity_count", 0)
    n_white = summary.get("whitespace_count", 0)
    n_diff = summary.get("we_have_they_dont_count", 0)
    n_drift = len(drift)
    top_gap = rankings[0] if rankings else None
    short_fn = cfg.positioning_short_filename().replace(".md", "")
    has_deep = cfg.positioning_format() == "two_files_short_and_deep"
    deep_fn = cfg.positioning_deep_filename().replace(".md", "") if has_deep else None

    body: list[str] = []
    body.append(f"# {s.get('product','?')} — {s.get('category','?')} competitive review")
    body.append(f"_Generated {today}. {len(competitors)} competitors scanned._\n")

    # ---------- TL;DR ----------
    body.append("## TL;DR\n")
    elevator = (positioning.get("elevator_pitch") or "").strip()
    if elevator:
        body.append(f"_{elevator}_\n")
    tldr_bits = []
    if n_ts:
        tldr_bits.append(f"**{n_ts} table-stakes gaps** to close")
    if n_diff:
        tldr_bits.append(f"**{n_diff} differentiators** to surface")
    if n_white:
        tldr_bits.append(f"**{n_white} whitespace** opportunities")
    if n_drift:
        tldr_bits.append(f"**{n_drift} spec↔site drift** items")
    if tldr_bits:
        body.append(" · ".join(tldr_bits) + ".\n")
    if top_gap:
        body.append(
            f"Highest-priority gap: **{top_gap['feature']}** "
            f"(frequency {top_gap['frequency']}, score {top_gap['score']}).\n"
        )

    # ---------- What changed (only if diff exists) ----------
    if prior_diff:
        body.append("## What changed since last review\n")
        body.append(prior_diff)
        body.append("")

    # ---------- Top 5 priorities ----------
    if rankings:
        body.append("## Top 5 priorities\n")
        body.append("| # | Score | Bucket | Feature | Freq | Fit | Cost |")
        body.append("|---|------:|--------|---------|-----:|----:|------|")
        for i, r in enumerate(rankings[:5], 1):
            body.append(
                f"| {i} | {r['score']} | {r['bucket']} | {r['feature']} | "
                f"{r['frequency']} | {r['fit']} | {r['cost']} |"
            )
        if len(rankings) > 5:
            body.append(f"\n_Full top-{len(rankings)} list in [[gaps|gaps.md]]._")
        body.append("")

    # ---------- Strongest positioning angle ----------
    headlines = positioning.get("headline_candidates") or []
    diff_lines = positioning.get("core_differentiator_lines") or []
    if headlines:
        h = headlines[0]
        body.append("## Strongest positioning angle\n")
        head = (h.get("headline") or "").strip()
        sub = (h.get("subhead") or "").strip()
        if head:
            body.append(f"> **{head}**")
        if sub:
            body.append(f">")
            body.append(f"> _{sub}_")
        body.append(f"\n_Full brief: [[{short_fn}|{cfg.positioning_short_filename()}]]_\n")
    elif diff_lines:
        body.append("## Differentiator one-liners\n")
        for line in diff_lines[:3]:
            body.append(f"- {line}")
        body.append(f"\n_Full brief: [[{short_fn}|{cfg.positioning_short_filename()}]]_\n")

    # ---------- Where to look ----------
    body.append("## Where to look in this folder\n")
    body.append("| File | What's in it | Open when |")
    body.append("|---|---|---|")
    body.append("| [[gaps|gaps.md]] | 4-bucket gap analysis + full ranking | Planning what to build |")
    body.append(
        f"| [[{short_fn}|{cfg.positioning_short_filename()}]] | "
        f"Elevator + differentiator lines + headlines | Working on copy |"
    )
    if has_deep and deep_fn:
        body.append(
            f"| [[{deep_fn}|{cfg.positioning_deep_filename()}]] | "
            f"Pillars, anti-pitch, objection handling | Working on sales / longer messaging |"
        )
    body.append(
        f"| [[matrix|matrix.md]] | "
        f"{summary.get('n_features','?')}-feature × {len(competitors)}-competitor presence table | "
        f"Validating what each competitor has |"
    )
    body.append(
        "| [[pricing|pricing.md]] | Tier prices per competitor + free-tier limits | "
        "Anchoring undercut positioning, sales objection handling |"
    )
    if drift:
        body.append("| [[drift|drift.md]] | Spec↔site mismatches | Resolving what we claim vs. ship |")
    body.append(
        "| `competitors/` | Per-competitor deep notes (features, sentiment, recent ships) | "
        "Researching one specific competitor |"
    )
    body.append("")

    # ---------- At a glance ----------
    body.append("## At a glance\n")
    body.append(f"- **Competitors scanned ({len(competitors)}):** {', '.join(competitors)}")
    body.append(f"- **Features identified:** {summary.get('n_features', '?')}")
    body.append(
        f"- **Bucket counts:** {n_ts} table-stakes · {n_dp} differentiator-parity · "
        f"{n_white} whitespace · {n_diff} we-have-they-don't"
    )
    if n_drift:
        body.append(f"- **Drift items:** {n_drift}")
    body.append("")

    # ---------- Reference: priors (compact one-liner each) ----------
    if prior_audits:
        body.append(f"## Reference: prior audits ({len(prior_audits)})\n")
        for p in prior_audits:
            body.append(f"- `{p['filename']}` _(score {p['score']})_")

    return "\n".join(body)


def render_matrix(s: dict) -> str:
    matrix = s.get("matrix", [])
    competitors = list(s.get("scans", {}).keys())
    if not matrix:
        return "# Feature matrix\n\n_No matrix computed._"

    cols = competitors + ["us_spec", "us_live"]
    header = "| Feature | Category | Bucket | Freq | Conf | " + " | ".join(cols) + " |"
    sep = "|---|---|---|---:|---|" + "|".join(["---"] * len(cols)) + "|"
    rows = [header, sep]

    # Sort by bucket then frequency
    bucket_order = {
        "table_stakes": 0,
        "differentiator_parity": 1,
        "we_have_they_dont": 2,
        "whitespace": 3,
    }
    conf_marker = {"high": "🟢", "medium": "🟡", "low": "🔴"}
    for m in sorted(matrix, key=lambda r: (bucket_order.get(r.get("bucket", ""), 9), -r.get("frequency", 0))):
        presence = m.get("presence", {})
        cells = [presence.get(c, "?") for c in cols]
        conf = m.get("confidence", "low")
        conf_label = f"{conf_marker.get(conf, '⚪')} {conf}"
        rows.append(
            f"| {m.get('feature','?')} | {m.get('category','?')} | {m.get('bucket','?')} | "
            f"{m.get('frequency','?')} | {conf_label} | " + " | ".join(cells) + " |"
        )

    note = (
        "_Confidence: 🟢 high (≥3 competitors confirm in docs/pricing) · "
        "🟡 medium (1-2 in docs OR several in landing) · 🔴 low (inferred from marketing only)_"
    )
    return "# Feature matrix\n\n" + note + "\n\n" + "\n".join(rows) + "\n"


def render_pricing(s: dict) -> str:
    """Render pricing.md — tier prices table per competitor + per-competitor sections."""
    scans = s.get("scans", {})
    rows = []
    for dom, scan in scans.items():
        a = scan.get("analysis", {}) or {}
        if not a or a.get("error"):
            continue
        pricing = a.get("pricing") or a.get("pricing_signal") or {}
        rows.append((dom, a.get("name") or dom, pricing))

    if not rows:
        return "# Pricing\n\n_No pricing data captured._"

    body = ["# Pricing\n",
            "_Tier prices for every competitor in this review. Used to anchor undercut positioning._\n"]

    # Top-level summary table
    body.append("## Tier-by-tier summary\n")
    body.append("| Competitor | Free tier limits | Cheapest paid | Mid | Top paid | Enterprise |")
    body.append("|---|---|---|---|---|---|")
    for dom, name, p in rows:
        free = (p.get("free_tier") or {}) if isinstance(p.get("free_tier"), dict) else {}
        free_lim = free.get("limits") or ("yes" if free.get("available") else "—")
        tiers = p.get("tiers") or []
        def fmt_tier(t):
            if not t:
                return "—"
            seat = t.get("price_per_seat_per_month")
            flat = t.get("price_flat_per_month")
            price = seat or flat or "?"
            return f"{t.get('name','?')}: {price}"
        cheap = fmt_tier(tiers[0]) if len(tiers) >= 1 else "—"
        mid = fmt_tier(tiers[1]) if len(tiers) >= 2 else "—"
        top = fmt_tier(tiers[-1]) if len(tiers) >= 3 else "—"
        ent = p.get("enterprise") or "—"
        body.append(f"| {name} ({dom}) | {free_lim} | {cheap} | {mid} | {top} | {ent} |")
    body.append("")

    # Per-competitor detail
    body.append("## Per-competitor detail\n")
    for dom, name, p in rows:
        body.append(f"### {name}")
        body.append(f"- **Model:** {p.get('model','?')}")
        free = (p.get("free_tier") or {}) if isinstance(p.get("free_tier"), dict) else {}
        if free.get("available") or free.get("limits"):
            body.append(f"- **Free tier:** {free.get('limits') or 'yes'}")
        for t in (p.get("tiers") or []):
            seat = t.get("price_per_seat_per_month")
            flat = t.get("price_flat_per_month")
            price = seat or flat or "?"
            yr = t.get("yearly_discount_pct")
            yr_note = f" (yearly save {yr}%)" if yr else ""
            inc = t.get("headline_inclusions") or ""
            body.append(f"- **{t.get('name','?')}:** {price}{yr_note} — {inc}")
        if p.get("enterprise"):
            body.append(f"- **Enterprise:** {p['enterprise']}")
        if p.get("notes"):
            body.append(f"- _Notes: {p['notes']}_")
        body.append("")

    return "\n".join(body)


def render_gaps(s: dict) -> str:
    matrix = s.get("matrix", [])
    rankings = s.get("rankings", [])
    rank_by_feature = {r["feature"]: r for r in rankings}

    body = ["# Gap analysis\n"]

    for bucket, label in [
        ("table_stakes", "Table stakes (we should close — competitors mostly have it)"),
        ("differentiator_parity", "Differentiator parity (strategic call)"),
        ("whitespace", "Whitespace (no one has it — opportunity)"),
        ("we_have_they_dont", "Our differentiators (we-have-they-don't)"),
    ]:
        items = [m for m in matrix if m.get("bucket") == bucket]
        items.sort(key=lambda m: m.get("frequency", 0), reverse=True)
        body.append(f"## {label}\n")
        if not items:
            body.append("_None._\n")
            continue
        for m in items:
            feature = m.get("feature", "?")
            r = rank_by_feature.get(feature)
            extra = ""
            if r:
                extra = f" — **score {r['score']}** (fit {r['fit']}, cost {r['cost']})"
            body.append(f"- **{feature}** (freq {m.get('frequency', '?')}){extra}")
            if m.get("evidence"):
                body.append(f"  - {m['evidence']}")
        body.append("")

    if rankings:
        body.append("## Top-10 ranked\n")
        body.append("| # | Score | Bucket | Feature | Freq | Fit | Cost |")
        body.append("|---|------:|--------|---------|-----:|----:|------|")
        for i, r in enumerate(rankings[:10], 1):
            body.append(
                f"| {i} | {r['score']} | {r['bucket']} | {r['feature']} | "
                f"{r['frequency']} | {r['fit']} | {r['cost']} |"
            )

    return "\n".join(body)


def render_drift(s: dict) -> str:
    drift = s.get("drift", [])
    if not drift:
        return ""
    body = ["# Spec ↔ Site drift\n"]
    body.append("Features the spec note claims that the live site doesn't show, or vice versa.\n")
    body.append("| Feature | Spec says | Live says | Note |")
    body.append("|---|---|---|---|")
    for d in drift:
        body.append(
            f"| {d.get('feature','?')} | {d.get('spec_says','?')} | "
            f"{d.get('live_says','?')} | {d.get('note','')} |"
        )
    return "\n".join(body)


def render_competitor(scan: dict) -> str:
    a = scan.get("analysis", {}) or {}
    body = [f"# {a.get('name', scan.get('name','?'))}"]
    body.append(f"\n_{scan.get('url','')}_\n")
    if a.get("tagline"):
        body.append(f"> {a['tagline']}\n")
    if a.get("value_proposition"):
        body.append(f"**Value prop:** {a['value_proposition']}\n")
    body.append(f"**Segment:** {a.get('target_segment','?')}  |  **ICP:** {a.get('ideal_customer','?')}\n")

    if a.get("differentiators"):
        body.append("## Differentiators\n")
        for d in a["differentiators"]:
            body.append(f"- {d}")

    if a.get("features"):
        body.append("\n## Features\n")
        for f in a["features"]:
            body.append(f"- **{f.get('name','?')}** [{f.get('tier','?')}]: {f.get('description','')}")

    if a.get("integrations"):
        body.append("\n## Integrations\n")
        body.append(", ".join(a["integrations"]))

    if a.get("recent_ships"):
        body.append("\n## Recent ships\n")
        for r in a["recent_ships"]:
            body.append(f"- **{r.get('date','?')}** — {r.get('what','?')}")

    sentiment = a.get("user_sentiment", {})
    if sentiment.get("praised") or sentiment.get("complaints"):
        body.append("\n## Sentiment\n")
        for p in sentiment.get("praised", []):
            body.append(f"- ✅ {p}")
        for c in sentiment.get("complaints", []):
            body.append(f"- ❌ {c}")

    if a.get("pricing_signal"):
        body.append("\n## Pricing signal\n")
        body.append(f"```json\n{json.dumps(a['pricing_signal'], indent=2)}\n```")

    # Recent signals (news.py — HN last 90d + GitHub stars)
    news_data = scan.get("news") or {}
    if news_data.get("recent_hn") or news_data.get("github"):
        body.append("")
        body.append(news.render_for_competitor_note(news_data.get("recent_hn") or [], news_data.get("github")))

    body.append(f"\n## Sources scanned\n")
    for src, data in scan.get("sources", {}).items():
        if isinstance(data, dict):
            url = data.get("url") or "—"
            err = data.get("error")
            if err:
                body.append(f"- {src}: ❌ {err}")
            else:
                body.append(f"- {src}: {url}")

    return "\n".join(body)


def generate_positioning(s: dict, product: str, category: str) -> dict | None:
    matrix = s.get("matrix", [])
    spec = s.get("spec", {})
    spec_text = (spec.get("body", "") or "")[:3000]

    ours = [m["feature"] for m in matrix if m.get("bucket") == "we_have_they_dont"]
    whitespace = [m["feature"] for m in matrix if m.get("bucket") == "whitespace"]
    table_gaps = [m["feature"] for m in matrix if m.get("bucket") == "table_stakes"][:10]

    complaints = []
    for scan in s.get("scans", {}).values():
        analysis = scan.get("analysis", {}) or {}
        for c in (analysis.get("user_sentiment", {}) or {}).get("complaints", []):
            complaints.append(f"({analysis.get('name','?')}) {c}")

    # Internal friction: pull Matt's own complaints from Slack/conversations
    competitor_names = []
    for sc in s.get("scans", {}).values():
        a = sc.get("analysis", {}) or {}
        if a.get("name"):
            competitor_names.append(a["name"])
    internal_quotes = internal.find_internal_friction(category, competitor_names, limit=8)

    prompt = POSITIONING_PROMPT.format(
        product=product,
        category=category,
        ours=", ".join(ours[:15]) or "(none yet)",
        complaints="; ".join(complaints[:15]) or "(none captured)",
        whitespace=", ".join(whitespace[:10]) or "(none identified)",
        gaps=", ".join(table_gaps) or "(none)",
        internal_friction=internal.render_for_prompt(internal_quotes),
        spec_excerpt=spec_text,
    )

    try:
        return claude.call_claude_json(prompt, timeout=300)
    except Exception as e:
        print(f"  [warn] positioning generation failed: {e}", file=sys.stderr)
        return None


def render_positioning_short(p: dict) -> str:
    """Short positioning brief: elevator + 5 differentiator one-liners + 3 headlines.

    Per stage_3_report._implications: "~10 lines: elevator + 5 differentiator one-liners + 3 headlines"
    """
    if not p:
        return "# Positioning brief\n\n_Generation failed._"
    body = ["# Positioning brief\n"]
    if p.get("elevator_pitch"):
        body.append(f"**Elevator pitch:** {p['elevator_pitch']}\n")

    lines = (p.get("core_differentiator_lines") or [])[:5]
    if lines:
        body.append("\n## Differentiator one-liners\n")
        for line in lines:
            body.append(f"- {line}")

    headlines = (p.get("headline_candidates") or [])[:3]
    if headlines:
        body.append("\n## Headline candidates\n")
        for h in headlines:
            body.append(f"- **{h.get('headline','?')}**")
            body.append(f"  - _{h.get('subhead','')}_")
            body.append(f"  - angle: {h.get('angle','?')}")

    body.append(f"\n_Full brief — pillars, anti-pitch, objection handling — in [[{cfg.positioning_deep_filename().replace('.md','')}|{cfg.positioning_deep_filename()}]]._")
    return "\n".join(body)


def render_positioning_deep(p: dict) -> str:
    """Full positioning brief with pillars, anti-pitch, objection handling."""
    if not p:
        return "# Positioning brief (deep)\n\n_Generation failed._"
    body = ["# Positioning brief (deep)\n"]
    if p.get("elevator_pitch"):
        body.append(f"**Elevator pitch:** {p['elevator_pitch']}\n")
    if p.get("icp_refinement"):
        body.append(f"**ICP:** {p['icp_refinement']}\n")

    if p.get("core_differentiator_lines"):
        body.append("\n## Differentiator one-liners\n")
        for line in p["core_differentiator_lines"]:
            body.append(f"- {line}")

    if p.get("headline_candidates"):
        body.append("\n## Headline candidates\n")
        for h in p["headline_candidates"]:
            body.append(f"- **{h.get('headline','?')}**")
            body.append(f"  - _{h.get('subhead','')}_")
            body.append(f"  - angle: {h.get('angle','?')}")

    if p.get("messaging_pillars"):
        body.append("\n## Messaging pillars\n")
        for m in p["messaging_pillars"]:
            body.append(f"### {m.get('pillar','?')}")
            body.append(f"- promise: {m.get('promise','?')}")
            for proof in m.get("proof_points", []):
                body.append(f"  - proof: {proof}")

    if p.get("anti_pitch"):
        body.append("\n## What we are NOT\n")
        for a in p["anti_pitch"]:
            body.append(f"- {a}")

    if p.get("objection_handling"):
        body.append("\n## Objection handling\n")
        for o in p["objection_handling"]:
            body.append(f"- **{o.get('objection','?')}** → {o.get('response','?')}")

    return "\n".join(body)


# Backwards-compat alias — older callers / tests may reference the old name.
render_positioning = render_positioning_deep


def compute_diff(s: dict, prior_dir: Path | None) -> str:
    if not prior_dir:
        return ""
    prior_index = prior_dir / "index.md"
    if not prior_index.exists():
        return ""
    # Cheap diff: list new vs dropped competitors and changed counts
    try:
        prior_text = prior_index.read_text(encoding="utf-8")
    except Exception:
        return ""
    competitors_now = set(s.get("scans", {}).keys())
    # Extract previous competitor list from "Competitors scanned: N (a, b, c)"
    import re
    m = re.search(r"Competitors scanned:\*\*\s*\d+\s*\(([^)]+)\)", prior_text)
    competitors_prev = set()
    if m:
        competitors_prev = {c.strip() for c in m.group(1).split(",")}
    added = sorted(competitors_now - competitors_prev)
    dropped = sorted(competitors_prev - competitors_now)

    lines = []
    if added:
        lines.append(f"- **New competitors:** {', '.join(added)}")
    if dropped:
        lines.append(f"- **Dropped competitors:** {', '.join(dropped)}")
    if not lines:
        lines.append(f"- Competitor set unchanged ({len(competitors_now)} competitors).")
    lines.append(f"- Prior run archived at `archive/{prior_dir.name}/`.")
    return "\n".join(lines)


def write_handoff(s: dict, category: str, product: str) -> Path | None:
    """Write a JSON file landing-page-skill can consume on a follow-up audit."""
    if not LP_INSIGHTS_DIR.exists():
        LP_INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    handoff = {
        "type": "competitive_review_handoff",
        "category": category,
        "product": product,
        "generated_at": datetime.now().isoformat(),
        "competitor_urls": [c.get("url") for c in s.get("candidates", []) if c.get("url")],
        "matrix": s.get("matrix", []),
        "rankings": s.get("rankings", []),
        "drift": s.get("drift", []),
        "summary": s.get("compare_summary", {}),
    }
    out = LP_INSIGHTS_DIR / f"competitive_{vault.slugify(category)}_{ts}.json"
    out.write_text(json.dumps(handoff, indent=2, default=str), encoding="utf-8")
    return out


def main():
    parser = argparse.ArgumentParser(description="Write competitive review to vault")
    parser.add_argument("category")
    parser.add_argument("--product", required=True)
    parser.add_argument("--no-positioning", action="store_true", help="Skip the positioning brief generation")
    args = parser.parse_args()

    s = state.load(args.category)
    if not s.get("matrix"):
        print("Error: no matrix in state. Run compare.py first.", file=sys.stderr)
        sys.exit(1)

    # Archive prior run BEFORE writing
    prior = vault.archive_prior_run(args.category)
    if prior:
        print(f"[report] archived prior run to {prior}", file=sys.stderr)

    out_dir = vault.ensure_category_dir(args.category)

    # Priors (Conversations/Claude/)
    competitor_names = [c.get("name", "") for c in s.get("candidates", [])]
    prior_audits = priors.find_prior_audits(args.category, competitor_names)
    state.update(args.category, prior_audits=prior_audits)
    priors_summary = priors.summarize_priors(prior_audits)

    # Diff (against archive)
    prior_diff = compute_diff(s, prior)

    # Positioning brief
    positioning = None
    if not args.no_positioning:
        print("[report] generating positioning brief...", file=sys.stderr)
        positioning = generate_positioning(s, args.product, args.category)
        state.update(args.category, positioning=positioning)

    # Frontmatter for index
    today = datetime.now().strftime("%Y-%m-%d")
    fm = {
        "created": today,
        "updated": today,
        "tags": "competitive",
        "category": args.category,
        "product": args.product,
        "competitors": str(len(s.get("scans", {}))),
    }

    # Write files
    vault.write_note(out_dir / "index.md", fm, render_index(s, prior_diff, priors_summary))
    (out_dir / "matrix.md").write_text(render_matrix(s), encoding="utf-8")
    (out_dir / "pricing.md").write_text(render_pricing(s), encoding="utf-8")
    (out_dir / "gaps.md").write_text(render_gaps(s), encoding="utf-8")
    if positioning:
        if cfg.positioning_format() == "two_files_short_and_deep":
            (out_dir / cfg.positioning_short_filename()).write_text(
                render_positioning_short(positioning), encoding="utf-8"
            )
            (out_dir / cfg.positioning_deep_filename()).write_text(
                render_positioning_deep(positioning), encoding="utf-8"
            )
        else:
            (out_dir / cfg.positioning_short_filename()).write_text(
                render_positioning_deep(positioning), encoding="utf-8"
            )
    drift_text = render_drift(s)
    if drift_text:
        (out_dir / "drift.md").write_text(drift_text, encoding="utf-8")

    # Per-competitor notes
    comp_dir = out_dir / "competitors"
    comp_dir.mkdir(parents=True, exist_ok=True)
    for dom, scan in s.get("scans", {}).items():
        slug = vault.slugify(scan.get("name") or dom)
        (comp_dir / f"{slug}.md").write_text(render_competitor(scan), encoding="utf-8")

    # Handoff
    handoff = write_handoff(s, args.category, args.product)

    pos_files = ""
    if positioning:
        if cfg.positioning_format() == "two_files_short_and_deep":
            pos_files = f", {cfg.positioning_short_filename()}, {cfg.positioning_deep_filename()}"
        else:
            pos_files = f", {cfg.positioning_short_filename()}"
    print(f"\n[report] wrote competitive review to:")
    print(f"  {out_dir}")
    print(f"  index.md, matrix.md, gaps.md{pos_files}{', drift.md' if drift_text else ''}")
    print(f"  competitors/ ({len(s.get('scans', {}))} files)")
    if handoff:
        print(f"  handoff: {handoff}")


if __name__ == "__main__":
    main()
