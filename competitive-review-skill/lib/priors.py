"""Find prior competitive audits in MattZerg/Conversations/Claude/."""

from __future__ import annotations

import re
from pathlib import Path

from . import vault

# Match category/competitor signal in either filename or first 4KB of body
_KEYWORDS_FALLBACK = ["competitive", "competitor", "audit", "vs ", "alternative"]


def _candidate_files() -> list[Path]:
    if not vault.CONVERSATIONS_DIR.exists():
        return []
    return sorted(vault.CONVERSATIONS_DIR.glob("*.md"), reverse=True)


def find_prior_audits(category: str, competitors: list[str], *, limit: int = 8) -> list[dict]:
    """Return list of {path, filename, score, snippet} for files that mention category or any competitor."""
    cat_slug = vault.slugify(category)
    cat_terms = [t for t in re.split(r"[-_\s]+", cat_slug) if t and len(t) > 2]
    comp_terms = [vault.slugify(c).split("-")[0] for c in competitors if c]
    needles = list({*cat_terms, *comp_terms})

    results = []
    for path in _candidate_files():
        try:
            head = path.read_text(encoding="utf-8", errors="ignore")[:8000].lower()
        except Exception:
            continue
        score = 0
        matched = []
        for n in needles:
            if n and n in head:
                score += 2
                matched.append(n)
        for kw in _KEYWORDS_FALLBACK:
            if kw in head:
                score += 1
        # Filename hits worth more
        fname = path.name.lower()
        for n in needles:
            if n and n in fname:
                score += 3
        if score < 3:
            continue
        # Snippet: first ~400 chars after the first match
        first_hit = min((head.find(n) for n in matched if n in head), default=0)
        start = max(0, first_hit - 80)
        snippet = head[start : start + 400].replace("\n", " ")
        results.append(
            {
                "path": str(path),
                "filename": path.name,
                "score": score,
                "matched_terms": matched,
                "snippet": snippet,
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


def summarize_priors(priors: list[dict]) -> str:
    """Render priors as a markdown bullet list for inclusion in the report."""
    if not priors:
        return "_No prior audits found in `MattZerg/Conversations/Claude/`._"
    lines = []
    for p in priors:
        lines.append(f"- **{p['filename']}** (score {p['score']}, matched: {', '.join(p['matched_terms']) or '—'})")
        lines.append(f"  - {p['snippet'][:300]}…")
    return "\n".join(lines)
