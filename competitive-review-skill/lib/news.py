"""News / momentum / fundraising signal per competitor.

Cheap, no-API-key sources:
- HN Algolia API filtered to last 90 days
- GitHub star count (when the competitor is OSS — extracted from docs/landing scrape)

Public API:
    recent_news(name, *, days=90, limit=5) -> list of {title, url, points, comments, age_days}
    github_stars(repo) -> {stars, forks, last_commit, age_days} or None
    extract_github_repo(scrape_text) -> "org/repo" string or None
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Optional

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _get_json(url: str, *, timeout: int = 15) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def recent_news(name: str, *, days: int = 90, limit: int = 5) -> list[dict]:
    """HN Algolia search restricted to the last N days. Surfaces 'what's the market saying lately'."""
    cutoff = int(time.time()) - days * 86400
    q = urllib.parse.quote(f'"{name}"')
    url = (
        f"https://hn.algolia.com/api/v1/search_by_date"
        f"?query={q}&tags=story&numericFilters=created_at_i>{cutoff}&hitsPerPage={limit}"
    )
    data = _get_json(url)
    if not data or "hits" not in data:
        return []
    out = []
    for h in data["hits"][:limit]:
        created_at = h.get("created_at_i")
        age_days = int((time.time() - created_at) / 86400) if created_at else None
        out.append({
            "title": h.get("title") or h.get("story_title") or "",
            "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
            "points": h.get("points") or 0,
            "comments": h.get("num_comments") or 0,
            "age_days": age_days,
            "hn_url": f"https://news.ycombinator.com/item?id={h.get('objectID')}",
        })
    out.sort(key=lambda r: (r["points"] or 0), reverse=True)
    return out


_GH_REPO_RE = re.compile(r"github\.com/([A-Za-z0-9][A-Za-z0-9\-_.]*)/([A-Za-z0-9][A-Za-z0-9\-_.]*)")


def extract_github_repo(text: str) -> Optional[str]:
    """Find a github.com/org/repo reference in scraped text. Returns first valid match.
    Skips org-only refs and known non-product repos (.github, docs)."""
    if not text:
        return None
    for org, repo in _GH_REPO_RE.findall(text):
        # Skip standard non-product references
        if repo.lower() in {".github", "docs", "site", "homepage", "www"}:
            continue
        # Skip if part of a URL fragment
        return f"{org}/{repo}"
    return None


def github_stars(repo: str) -> Optional[dict]:
    """GitHub API public endpoint — 60 req/hour unauthenticated. Returns stars + activity."""
    if not repo or "/" not in repo:
        return None
    url = f"https://api.github.com/repos/{repo}"
    data = _get_json(url, timeout=10)
    if not data or data.get("message") in {"Not Found", "API rate limit exceeded"}:
        return None
    pushed_at = data.get("pushed_at")
    last_commit_age = None
    if pushed_at:
        try:
            dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            last_commit_age = int((datetime.now(timezone.utc) - dt).total_seconds() / 86400)
        except Exception:
            pass
    return {
        "repo": repo,
        "stars": data.get("stargazers_count") or 0,
        "forks": data.get("forks_count") or 0,
        "open_issues": data.get("open_issues_count") or 0,
        "last_commit_days_ago": last_commit_age,
        "language": data.get("language"),
        "description": data.get("description"),
        "homepage": data.get("homepage"),
    }


def render_for_competitor_note(news_items: list[dict], gh: Optional[dict]) -> str:
    """Markdown block for a competitor's deep note."""
    parts = ["## Recent signals\n"]
    if gh:
        parts.append(f"**GitHub: [{gh['repo']}](https://github.com/{gh['repo']})**")
        parts.append(f"- {gh['stars']:,} stars · {gh['forks']:,} forks · {gh['open_issues']:,} open issues")
        if gh.get("last_commit_days_ago") is not None:
            parts.append(f"- Last commit {gh['last_commit_days_ago']} days ago")
        if gh.get("language"):
            parts.append(f"- Primary language: {gh['language']}")
        parts.append("")
    if news_items:
        parts.append("**Recent HN coverage (last 90 days):**")
        for n in news_items:
            age = f"{n['age_days']}d ago" if n["age_days"] is not None else "?"
            parts.append(f"- [{n['title']}]({n['hn_url']}) — {n['points']} points, {n['comments']} comments ({age})")
        parts.append("")
    if not gh and not news_items:
        parts.append("_No GitHub repo found and no HN coverage in the last 90 days._")
    return "\n".join(parts)
