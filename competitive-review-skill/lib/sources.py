"""Source-URL resolution + lightweight JSON-API fetchers for HN and Reddit."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Optional

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Common path guesses per source type — scan.py asks Claude to refine these per competitor.
COMMON_PATHS = {
    "pricing": ["/pricing", "/plans", "/pricing-plans"],
    "changelog": ["/changelog", "/releases", "/whats-new", "/updates", "/release-notes"],
    "docs": ["/docs", "/documentation", "/help", "/api", "/integrations"],
}


def _get_json(url: str, *, timeout: int = 15) -> Optional[dict | list]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def hn_search(query: str, *, limit: int = 10) -> list[dict]:
    """Hacker News via Algolia. Returns list of {title, url, points, num_comments, created_at, story_url}."""
    q = urllib.parse.quote(query)
    url = f"https://hn.algolia.com/api/v1/search?query={q}&tags=story&hitsPerPage={limit}"
    data = _get_json(url)
    if not data or "hits" not in data:
        return []
    out = []
    for h in data["hits"][:limit]:
        out.append(
            {
                "title": h.get("title") or h.get("story_title") or "",
                "url": h.get("url"),
                "points": h.get("points"),
                "num_comments": h.get("num_comments"),
                "created_at": h.get("created_at"),
                "hn_url": f"https://news.ycombinator.com/item?id={h.get('objectID')}",
            }
        )
    return out


_RELEVANT_SUBREDDITS = {
    "saas", "webdev", "programming", "selfhosted", "javascript", "typescript",
    "devops", "sysadmin", "startups", "entrepreneur", "smallbusiness",
    "productivity", "projectmanagement", "agile", "scrum", "freelance",
    "marketing", "sales", "ycombinator", "experienceddevs",
}


def reddit_search(query: str, *, context_terms: list[str] | None = None, limit: int = 10) -> list[dict]:
    """Reddit JSON search. May 403 — caller treats as best-effort.
    Quotes the query (so 'linear' becomes '"linear"' for an exact match) and optionally appends
    context terms (e.g. ['app', 'project management']) to filter generic junk.
    Post-filters to relevant subreddits when results overflow.
    """
    parts = [f'"{query}"']
    if context_terms:
        parts.extend(context_terms)
    q = urllib.parse.quote(" ".join(parts))
    url = f"https://old.reddit.com/search.json?q={q}&sort=top&t=year&limit={max(limit*3, 25)}"
    data = _get_json(url)
    if not data or "data" not in data:
        return []
    posts = []
    for c in data["data"].get("children", []):
        d = c.get("data", {})
        posts.append(
            {
                "title": d.get("title", ""),
                "subreddit": d.get("subreddit", ""),
                "score": d.get("score", 0),
                "num_comments": d.get("num_comments", 0),
                "permalink": f"https://reddit.com{d.get('permalink', '')}",
                "selftext": (d.get("selftext") or "")[:500],
            }
        )
    # Prefer relevant subreddits, then fill from rest
    relevant = [p for p in posts if (p["subreddit"] or "").lower() in _RELEVANT_SUBREDDITS]
    rest = [p for p in posts if p not in relevant]
    return (relevant + rest)[:limit]


def g2_url_guess(name: str) -> str:
    """Best-effort G2 reviews URL — many products live at g2.com/products/<slug>/reviews."""
    slug = urllib.parse.quote(name.lower().replace(" ", "-"))
    return f"https://www.g2.com/products/{slug}/reviews"
