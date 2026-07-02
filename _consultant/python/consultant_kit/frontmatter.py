"""YAML frontmatter envelope every consultant artifact carries.

Schema:
    engagement: <slug>
    slug: <artifact-slug>
    date: YYYY-MM-DD
    skill: <skill-name>
    inputs: [path, ...]
    upstream: [path, ...]
    source_citations: [{claim, source, url, accessed}]
    extra: {arbitrary skill-specific fields}
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

import yaml


def envelope(
    *,
    engagement: str,
    slug: str,
    skill: str,
    inputs: list[str | Path] | None = None,
    upstream: list[str | Path] | None = None,
    source_citations: list[dict] | None = None,
    extra: dict | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    """Build the standard frontmatter dict."""
    return {
        "engagement": engagement,
        "slug": slug,
        "date": date or _dt.date.today().isoformat(),
        "skill": skill,
        "inputs": [str(p) for p in (inputs or [])],
        "upstream": [str(p) for p in (upstream or [])],
        "source_citations": source_citations or [],
        **(extra or {}),
    }


def dump(fm: dict[str, Any]) -> str:
    """Render frontmatter as a fenced YAML block ready to prepend to a markdown body."""
    yml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{yml}\n---\n"


def write_md(path: Path, fm: dict[str, Any], body: str) -> Path:
    """Write a markdown file with the envelope + body. Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = dump(fm) + "\n" + body.rstrip() + "\n"
    path.write_text(content, encoding="utf-8")
    return path


def parse(path: Path) -> tuple[dict[str, Any], str]:
    """Parse a markdown file with frontmatter. Returns (frontmatter_dict, body)."""
    text = Path(path).read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return ({}, text)
    end = text.find("\n---\n", 4)
    if end == -1:
        return ({}, text)
    fm = yaml.safe_load(text[4:end]) or {}
    body = text[end + 5 :]
    return (fm, body)
