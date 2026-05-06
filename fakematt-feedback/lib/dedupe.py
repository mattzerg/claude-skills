"""Cross-page finding deduplication.

After per-page critique, the same issue often gets flagged on every page that
exhibits it (e.g. missing `lang` attribute on `<html>` shows up 5x — once per
template). This module merges those into one finding with a list of affected
pages.

Strategy: bucket findings by `(category, normalized_finding_signature)` where
the signature is a short prefix of the finding text with stable elements (URLs,
selector strings, page-specific specifics) stripped out. If 2+ findings share
a bucket, merge into one with `affected_pages: [url1, url2, ...]` and the
fix from the most thorough variant (longest `suggested_fix`).
"""

from __future__ import annotations

import re
from collections import defaultdict


_ATTR_NTH = re.compile(r"\[[^\]]*\]|nth-child\(\d+\)|nth-of-type\(\d+\)|#[\w\-]+|\.[\w\-]+")
_DIGITS = re.compile(r"\d+")
_PUNCT = re.compile(r"[^\w\s]")
_WHITESPACE = re.compile(r"\s+")

# Anchor keywords — if the finding text mentions one of these, it's part of
# the bucket key. Catches cases where two findings hit the same selector but
# diagnose different problems (e.g. <input> with missing label vs <input>
# with wrong type).
_ANCHOR_KEYWORDS = [
    "lang attribute", "aria-label", "aria-labelledby", "tab order", "focus",
    "heading order", "heading hierarchy", "alt text", "color contrast",
    "name format", "iso timestamp", "broken link", "404", "405",
    "primary cta", "secondary cta", "trust band", "social proof", "testimonial",
    "empty state", "error state", "loading state", "skeleton",
    "responsive", "mobile", "tablet", "viewport",
    "lazy load", "performance", "lighthouse",
    "drop shadow", "border radius", "spacing", "padding", "margin",
    "click target", "tap target", "minimum size",
    "duplicate", "redundant", "stale", "outdated",
]


def _selector_root(selector: str) -> str:
    """Reduce a CSS selector to its root tag/id, stripping attribute selectors,
    nth indices, and class chains. `select[data-v-0db96779]` → `select`,
    `tr.row-3 td:nth-child(2)` → `tr td`."""
    if not selector:
        return ""
    cleaned = _ATTR_NTH.sub("", selector)
    cleaned = _PUNCT.sub(" ", cleaned)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip().lower()
    return cleaned[:60]


def _anchor_keywords_in(text: str) -> str:
    """Return a sorted, comma-joined list of anchor keywords found in the
    finding text. This is the most reliable signal for grouping rephrased
    versions of the same issue. Strips punctuation/backticks first so that
    "missing the required `lang` attribute" still matches "lang attribute"."""
    text_lower = _PUNCT.sub(" ", (text or "").lower())
    text_lower = _WHITESPACE.sub(" ", text_lower)
    found = sorted({kw for kw in _ANCHOR_KEYWORDS if kw in text_lower})
    return ",".join(found) if found else ""


def _signature(finding: dict) -> str:
    """Stable bucket key. Combines:
      - category (e.g. accessibility)
      - principle_provenance IDs (e.g. p-0002,p-0110)
      - root selector tag (e.g. html, select, input)
      - anchor keywords from the finding text (e.g. lang attribute)

    Two findings flagged on different pages with different wording but same
    underlying issue (same a11y rule on the same element type) collapse to
    one bucket."""
    cat = finding.get("category") or "?"
    pps = finding.get("principle_provenance") or []
    if isinstance(pps, str):
        pps = [pps]
    pps_key = ",".join(sorted(p for p in pps if p))
    loc = finding.get("location") or {}
    sel = _selector_root(loc.get("selector") or "")
    anchors = _anchor_keywords_in(finding.get("finding") or "")
    # Fall back to the first 50 chars of normalized text if no anchor keywords —
    # better than collapsing every finding-without-anchors into one bucket
    if not anchors:
        text = (finding.get("finding") or "").lower()
        text = _DIGITS.sub("N", text)
        text = _PUNCT.sub(" ", text)
        text = _WHITESPACE.sub(" ", text).strip()
        anchors = text[:50]
    return f"{cat}::{pps_key}::{sel}::{anchors}"


def dedupe_findings(findings: list[dict]) -> tuple[list[dict], dict]:
    """Returns (deduped_findings, stats) where stats has dedupe counts.

    Each merged finding gets:
      - `affected_pages`: list of unique URLs where the issue was flagged
      - `merged_count`: how many original findings were folded in
      - `is_site_wide`: True if affected_pages count >= 3 (heuristic for
        rolling up to a "Site-wide issues" section in the report)

    Single-instance findings are returned unchanged (no `merged_count` etc.).
    """
    buckets: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        if "_error" in f or not f.get("finding"):
            continue
        buckets[_signature(f)].append(f)

    out: list[dict] = []
    merged_total = 0
    for sig, group in buckets.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        merged_total += len(group) - 1
        # Pick the canonical finding: longest, most-detailed text
        canonical = max(group, key=lambda f: len((f.get("finding") or "")) + len((f.get("suggested_fix") or "")))
        # Collect pages
        pages: list[str] = []
        for f in group:
            url = (f.get("location") or {}).get("url") or ""
            if url and url not in pages:
                pages.append(url)
        merged = dict(canonical)
        merged["affected_pages"] = pages
        merged["merged_count"] = len(group)
        merged["is_site_wide"] = len(pages) >= 3
        # Highest-severity wins if any disagreed
        sev_rank = {"P0": 0, "P1": 1, "P2": 2}
        worst_sev = min((f.get("severity", "P2") for f in group), key=lambda s: sev_rank.get(s, 3))
        merged["severity"] = worst_sev
        out.append(merged)

    # Sort: site-wide P0s first, then by severity, then by merged_count desc
    sev_rank = {"P0": 0, "P1": 1, "P2": 2}
    out.sort(key=lambda f: (
        not f.get("is_site_wide", False),
        sev_rank.get(f.get("severity", "P2"), 3),
        -f.get("merged_count", 1),
    ))

    return out, {
        "input_count": len(findings),
        "output_count": len(out),
        "merged_count": merged_total,
        "site_wide_count": sum(1 for f in out if f.get("is_site_wide")),
    }
