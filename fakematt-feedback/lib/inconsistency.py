"""Cross-page inconsistency detection.

Runs AFTER all pages are captured. Looks for the same field type rendered
differently across pages — the kind of thing the per-page critique step
can't see because each page critique runs independently.

Examples this catches:
- CEO h1 is "Firstname Lastname" while every other person h1 is "Lastname, Firstname"
- One page renders dates as "2026-04-30" while others render "Apr 30, 2026"
- A widget label is present on one variant but missing on another
- One template's empty state is "—" while another's is "0"

Returns a list of finding dicts in the same shape as critique.py findings,
so they merge cleanly into the report.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse

# These patterns characterize "name format" — used to bucket h1/title text
NAME_FIRST_LAST = re.compile(r"^[A-Z][a-zA-Z\-']+\s+[A-Z][a-zA-Z\-']+$")
NAME_LAST_COMMA_FIRST = re.compile(r"^[A-Z][a-zA-Z\-']+,\s+[A-Z][a-zA-Z\-']+$")
ISO_TIMESTAMP_RAW = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
DATE_HUMAN = re.compile(r"^[A-Z][a-z]{2}\s+\d{1,2},?\s+\d{4}$")
DATE_NUMERIC = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _name_format(text: str) -> str | None:
    if not text:
        return None
    text = text.strip()
    if NAME_LAST_COMMA_FIRST.match(text):
        return "lastname-comma-firstname"
    if NAME_FIRST_LAST.match(text):
        return "firstname-lastname"
    return None


def _date_format(text: str) -> str | None:
    if not text:
        return None
    text = text.strip()
    if ISO_TIMESTAMP_RAW.match(text):
        return "iso-raw"
    if DATE_HUMAN.match(text):
        return "human-date"
    if DATE_NUMERIC.match(text):
        return "numeric-date"
    return None


def _path_template(url: str) -> str:
    """Same template-collapsing logic as the spider, kept simple here."""
    p = urlparse(url)
    path = re.sub(r"\d+", "{ID}", p.path or "/")
    return path


def find_inconsistencies(captures: list) -> list[dict]:
    """Each `capture` is a PageCapture (or .to_payload() dict). Run cheap
    sniffers across the set and emit findings for any field that has >1
    format observed across pages.

    Returns finding dicts compatible with the critique pipeline schema.
    """
    payloads = []
    for c in captures:
        if isinstance(c, dict):
            payloads.append(c)
        elif hasattr(c, "to_payload"):
            payloads.append(c.to_payload())
    if len(payloads) < 2:
        return []

    findings: list[dict] = []
    findings.extend(_check_h1_name_format(payloads))
    findings.extend(_check_iso_timestamps(payloads))
    findings.extend(_check_title_template_drift(payloads))
    return findings


def _check_h1_name_format(payloads: list[dict]) -> list[dict]:
    """Group H1s by URL template; if multiple H1s under one template use
    different name formats, flag it."""
    by_template: dict[str, list[tuple[str, str]]] = {}
    for p in payloads:
        url = p.get("final_url") or p.get("url") or ""
        h1 = (p.get("h1") or "").strip()
        if not h1:
            continue
        fmt = _name_format(h1)
        if not fmt:
            continue
        by_template.setdefault(_path_template(url), []).append((h1, fmt))

    out = []
    for template, items in by_template.items():
        formats = Counter(fmt for _, fmt in items)
        if len(formats) <= 1 or len(items) < 2:
            continue
        # We have drift within one template. Find the minority format.
        majority_fmt, _ = formats.most_common(1)[0]
        odd_ones = [name for name, fmt in items if fmt != majority_fmt]
        if not odd_ones:
            continue
        out.append({
            "finding_id": "inc-h1-name",
            "severity": "P1",
            "category": "consistency",
            "mode": "broken",
            "location": {"url": template, "selector": "h1", "screenshot": None},
            "finding": (
                f"Heading name format is inconsistent across the {template} template. "
                f"{len(items) - len(odd_ones)} pages use '{majority_fmt}', but "
                f"{len(odd_ones)} use a different format (e.g. {odd_ones[0]!r}). "
                "Pick one and apply it everywhere."
            ),
            "suggested_fix": f"Normalize to '{majority_fmt}' on every page in this template, or document which records are intentionally different and why.",
            "voice_provenance": None,
            "principle_provenance": ["p-recognition"],  # placeholder — Nielsen #4 consistency
            "target_kind_relevance": None,
            "role_assumption": None,
            "_source": "inconsistency_scanner",
        })
    return out


def _check_iso_timestamps(payloads: list[dict]) -> list[dict]:
    """Find raw ISO timestamps (`2026-04-30T17:08:21.123`) leaking into text content
    across multiple pages — strong signal of debug field rendering in user UI."""
    pages_with_raw_iso: list[str] = []
    for p in payloads:
        text = p.get("text_excerpt") or ""
        if ISO_TIMESTAMP_RAW.search(text):
            pages_with_raw_iso.append(p.get("final_url") or p.get("url") or "?")
    if len(pages_with_raw_iso) < 2:
        return []
    return [{
        "finding_id": "inc-iso-ts",
        "severity": "P1",
        "category": "copy",
        "mode": "broken",
        "location": {"url": pages_with_raw_iso[0], "selector": None, "screenshot": None},
        "finding": (
            f"Raw ISO 8601 timestamps are rendered to users on {len(pages_with_raw_iso)} pages "
            "(e.g. '2026-04-30T17:08:21.0902'). This is a developer-facing string format "
            "leaking into user UI."
        ),
        "suggested_fix": "Format as a human-readable relative time (e.g. '3 days ago') with the full timestamp on hover. Apply across all pages where last-synced/last-updated/created-at strings appear.",
        "voice_provenance": None,
        "principle_provenance": ["p-recognition"],
        "target_kind_relevance": None,
        "role_assumption": None,
        "_source": "inconsistency_scanner",
    }]


def _check_title_template_drift(payloads: list[dict]) -> list[dict]:
    """If the same URL template renders titles with very different lengths or
    structures (e.g. some have department, some don't), that's drift."""
    by_template: dict[str, list[str]] = {}
    for p in payloads:
        url = p.get("final_url") or p.get("url") or ""
        title = (p.get("title") or "").strip()
        if not title:
            continue
        by_template.setdefault(_path_template(url), []).append(title)

    out = []
    for template, titles in by_template.items():
        if len(titles) < 2:
            continue
        lengths = [len(t) for t in titles]
        if max(lengths) - min(lengths) > 30:  # >30 char swing within one template
            shortest = titles[lengths.index(min(lengths))]
            longest = titles[lengths.index(max(lengths))]
            out.append({
                "finding_id": "inc-title-len",
                "severity": "P2",
                "category": "consistency",
                "mode": "broken",
                "location": {"url": template, "selector": "<title>", "screenshot": None},
                "finding": (
                    f"<title> length varies a lot within the {template} template "
                    f"({min(lengths)} chars vs {max(lengths)} chars). "
                    f"Shortest: {shortest!r}. Longest: {longest!r}. "
                    "This usually means optional fields (department, region, etc.) are conditionally appended."
                ),
                "suggested_fix": "Define a single title structure for the template (e.g. '{Name} · {Role} — {Org}') and apply it uniformly. If some fields are optional, decide on a fallback.",
                "voice_provenance": None,
                "principle_provenance": ["p-recognition"],
                "target_kind_relevance": None,
                "role_assumption": None,
                "_source": "inconsistency_scanner",
            })
    return out
