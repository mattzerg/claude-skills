"""Shared slug derivation for zpub tooling.

One slug story for the two consumers that used to disagree:
  - tools/check_gates.py  — hero lookup (<slug>-hero.png under the blog image dir)
  - pipeline.py           — content filename (<slug>.md / <slug>.ts in the repo)

Candidate order (most → least authoritative):
  1. cms-canonical-md surface path  (web/src/public/content/blog/<slug>.md)
  2. cms-canonical-ts surface path  (web/src/constants/blog/posts/<slug>.ts)
  3. explicit SLUG_HINTS entry-id map (manual overrides for odd cases)
  4. normalized blog-source title — both with and without a leading article
     ("The Active Software Revolution.md" → "active-software-revolution",
      "the-active-software-revolution")

Callers filter candidates against their own ground truth (file exists / git
ls-tree) — this module only proposes, never checks the filesystem.
"""
from __future__ import annotations

import re
from pathlib import Path

BLOG_MD_RE = re.compile(r"/content/blog/([^/]+)\.md")
BLOG_TS_RE = re.compile(r"/constants/blog/posts/([^/]+)\.ts")
_ARTICLE_RE = re.compile(r"^(the|a|an)-")

# Manual entry-id → slug overrides, for entries whose title normalization
# doesn't match the repo slug. Keep keys = REAL zpub entry ids.
SLUG_HINTS = {
    "pub-2026-thesis-active-software-revolution": "active-software-revolution",
    "pub-2026-thesis-continuous-software": "continuous-software",
    "pub-2026-thesis-gigacontext-threshold": "gigacontext-threshold",
    "pub-2026-thesis-nobody-reads-code": "nobody-reads-code-anymore",
    "pub-2026-05-demo-loop": "ai-systems-mission-critical",
}


def normalize_title(stem: str) -> str:
    """"The Active Software Revolution" → "the-active-software-revolution"."""
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")


def slug_candidates(entry_id: str, surfaces: list | None) -> list[str]:
    """Ordered, de-duplicated slug candidates for an entry."""
    out: list[str] = []

    def add(slug: str | None) -> None:
        if slug and slug not in out:
            out.append(slug)

    for surf in surfaces or []:
        if not isinstance(surf, dict):
            continue
        path = surf.get("path") or ""
        m = BLOG_MD_RE.search(path)
        if m:
            add(m.group(1))
        m = BLOG_TS_RE.search(path)
        if m:
            add(m.group(1))

    add(SLUG_HINTS.get(entry_id))

    for surf in surfaces or []:
        if not isinstance(surf, dict):
            continue
        if (surf.get("kind") or "").lower() == "blog-source":
            stem = Path(surf.get("path") or "").stem
            normalized = normalize_title(stem)
            add(_ARTICLE_RE.sub("", normalized))  # article stripped (historical default)
            add(normalized)                        # verbatim
    return out
