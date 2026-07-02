"""Common helpers for reading/writing idea files across the vault."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Iterator

# Ensure local _lib siblings are importable when scripts run as `python3 path/to/script.py`.
import sys
_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file, write_file  # noqa: E402
from vault_paths import (  # noqa: E402
    IDEAS_ROOT,
    INBOX_DIR,
    ARCHIVE_DIR,
    INDEX_JSON,
    WRITEBACK_VAULT_ROOT,
    CATEGORIES,
    category_dir,
)
from slugify import slugify  # noqa: E402


def today_iso() -> str:
    return dt.date.today().isoformat()


def make_id(title: str, when: str | None = None) -> str:
    when = when or today_iso()
    return f"idea-{when}-{slugify(title, max_len=50)}"


def default_meta(
    *,
    title: str,
    category: str,
    subcategory: str | None = None,
    tags: list[str] | None = None,
    status: str = "raw",
    sources: list[str] | None = None,
) -> dict[str, Any]:
    today = today_iso()
    return {
        "id": make_id(title),
        "title": title,
        "category": category,
        "subcategory": subcategory,
        "tags": tags or [],
        "status": status,
        "conviction": "medium",
        "effort": "unknown",
        "time_estimate": "unknown",
        "cost_estimate": "unknown",
        "created": today,
        "last_touched": today,
        "sources": sources or [],
        "related": [],
        "task_link": None,
    }


def default_body(*, idea: str = "", why: str = "", source_excerpt: str = "") -> str:
    return (
        f"## Idea\n{idea}\n\n"
        f"## Why interesting\n{why}\n\n"
        f"## Open questions\n- \n\n"
        + (f"## Source excerpt\n> {source_excerpt}\n" if source_excerpt else "")
    )


def iter_all_ideas(include_inbox: bool = False, include_archive: bool = False) -> Iterator[Path]:
    """Walk the Ideas/ tree and yield each .md idea file path.

    Walks: current CATEGORIES + any legacy top-level dir under Ideas/ that
    holds idea files (so a renamed taxonomy doesn't silently lose files
    until they're migrated).
    """
    if not IDEAS_ROOT.exists():
        return
    seen_dirs: set[Path] = set()
    for cat in CATEGORIES:
        cdir = category_dir(cat)
        if cdir.exists():
            seen_dirs.add(cdir)
            for p in cdir.rglob("*.md"):
                yield p
    # Catch any legacy top-level directory under Ideas/ that isn't _inbox/_archive/_meta.
    for cdir in IDEAS_ROOT.iterdir():
        if not cdir.is_dir():
            continue
        if cdir.name.startswith("_"):
            continue
        if cdir in seen_dirs:
            continue
        for p in cdir.rglob("*.md"):
            yield p
    if include_inbox and INBOX_DIR.exists():
        for p in INBOX_DIR.rglob("*.md"):
            yield p
    if include_archive and ARCHIVE_DIR.exists():
        for p in ARCHIVE_DIR.rglob("*.md"):
            yield p


def find_by_id(idea_id: str, *, include_inbox: bool = True, include_archive: bool = True) -> Path | None:
    for p in iter_all_ideas(include_inbox=include_inbox, include_archive=include_archive):
        try:
            meta, _ = read_file(p)
        except Exception:
            continue
        if meta.get("id") == idea_id:
            return p
    return None


def find_by_partial(needle: str) -> list[Path]:
    """Match against id or filename stem (case-insensitive)."""
    needle = needle.lower()
    out: list[Path] = []
    for p in iter_all_ideas(include_inbox=True, include_archive=True):
        try:
            meta, _ = read_file(p)
        except Exception:
            continue
        if needle in (meta.get("id") or "").lower() or needle in p.stem.lower():
            out.append(p)
    return out


def write_new_idea(meta: dict[str, Any], body: str, *, in_inbox: bool = False) -> Path:
    """Write a new idea file. Returns the chosen path. Slug collisions get -2/-3 suffixed."""
    slug = slugify(meta["title"])
    if in_inbox:
        base = INBOX_DIR / (meta.get("category") or "uncategorized")
    else:
        base = category_dir(meta["category"])
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{slug}.md"
    n = 2
    while path.exists():
        path = base / f"{slug}-{n}.md"
        n += 1
    write_file(path, meta, body)
    return path


def load_index() -> list[dict[str, Any]]:
    if INDEX_JSON.exists():
        try:
            return json.loads(INDEX_JSON.read_text())
        except Exception:
            return []
    return []


def save_index(rows: list[dict[str, Any]]) -> None:
    # Safety: never clobber a populated index with an empty one. This guards
    # against a transient mirror gap (e.g. category dirs not yet synced) making
    # iter_all_ideas() see zero files and staging an empty index over real data.
    if not rows:
        try:
            existing = load_index()
        except Exception:
            existing = []
        if existing:
            raise RuntimeError(
                "refusing to write empty index over %d existing rows "
                "(likely a transient vault/mirror read gap)" % len(existing)
            )
    # `default=str` handles datetime.date / datetime.datetime / UUID / etc.
    # that may end up in frontmatter values when YAML parses dates natively.
    payload = json.dumps(rows, indent=2, ensure_ascii=False, default=str)
    # Try a direct write first (works interactively). Under launchd/TCC the
    # iCloud path is read-only, so fall back to the writeback staging dir,
    # which com.matteisn.vault-flush rsyncs into the vault within ~60s.
    try:
        INDEX_JSON.parent.mkdir(parents=True, exist_ok=True)
        # Atomic primary write (the PermissionError fallback below is now rare —
        # the vault is a normal Obsidian-Sync folder, not TCC-restricted iCloud).
        _tmp = INDEX_JSON.with_name("." + INDEX_JSON.name + ".tmp")
        _tmp.write_text(payload, encoding="utf-8")
        import os as _os
        _os.replace(_tmp, INDEX_JSON)
        return
    except (PermissionError, OSError):
        pass
    target = WRITEBACK_VAULT_ROOT / "Ideas" / "_meta" / "index.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    import os
    os.replace(tmp, target)


def touch_meta(meta: dict[str, Any]) -> dict[str, Any]:
    meta["last_touched"] = today_iso()
    return meta
