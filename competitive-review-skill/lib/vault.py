"""Vault I/O — read product specs, write competitive notes, archive prior runs.
Vault root is hard-coded to Matt's MattZerg/ folder."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

VAULT_ROOT = Path(
    "/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg"
)
ZSTACK_DIR = VAULT_ROOT / "Projects" / "Zstack"
COMPETITIVE_DIR = VAULT_ROOT / "Competitive"
CONVERSATIONS_DIR = VAULT_ROOT / "Conversations" / "Claude"


def slugify(s: str) -> str:
    return re.sub(r"[^\w-]+", "-", s.lower()).strip("-")[:80]


def category_dir(category: str) -> Path:
    return COMPETITIVE_DIR / slugify(category)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse a leading YAML frontmatter block. Returns (frontmatter_dict, body)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    fm: dict = {}
    for line in block.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        # Strip surrounding quotes
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        fm[key] = val
    return fm, body


def read_product_spec(product: str) -> Optional[dict]:
    """Find product spec note (case-insensitive). Searches MattZerg/Projects/Zstack/<Product>.md
    first, then MattZerg/Projects/<Product>.md. Return {path, frontmatter, body, live_url}."""
    target = product.lower()
    search_dirs = [ZSTACK_DIR, VAULT_ROOT / "Projects"]
    for d in search_dirs:
        if not d.exists():
            continue
        for path in d.glob("*.md"):
            if path.stem.lower() == target:
                text = path.read_text(encoding="utf-8")
                fm, body = parse_frontmatter(text)
                live_url = None
                if fm.get("fly_app"):
                    live_url = f"https://{fm['fly_app']}.fly.dev"
                elif fm.get("url"):
                    live_url = fm["url"]
                return {
                    "path": str(path),
                    "name": path.stem,
                    "frontmatter": fm,
                    "body": body,
                    "live_url": live_url,
                }
    return None


def ensure_category_dir(category: str) -> Path:
    d = category_dir(category)
    (d / "competitors").mkdir(parents=True, exist_ok=True)
    (d / "archive").mkdir(parents=True, exist_ok=True)
    return d


def archive_prior_run(category: str) -> Optional[Path]:
    """Move existing top-level files (not archive/) into archive/YYYY-MM-DD/. Returns the archive path."""
    d = category_dir(category)
    if not d.exists():
        return None
    movable = [p for p in d.iterdir() if p.name != "archive" and p.name != "competitors"]
    competitors_dir = d / "competitors"
    has_competitors = competitors_dir.exists() and any(competitors_dir.iterdir())
    if not movable and not has_competitors:
        return None
    stamp = datetime.now().strftime("%Y-%m-%d")
    archive_path = d / "archive" / stamp
    # If today's archive already exists, append a time suffix
    if archive_path.exists():
        archive_path = d / "archive" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    archive_path.mkdir(parents=True, exist_ok=True)
    for p in movable:
        shutil.move(str(p), str(archive_path / p.name))
    if has_competitors:
        shutil.move(str(competitors_dir), str(archive_path / "competitors"))
    # Recreate competitors/ for the new run
    (d / "competitors").mkdir(parents=True, exist_ok=True)
    return archive_path


def write_note(path: Path, frontmatter: dict, body: str) -> None:
    """Write a markdown file with frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            fm_lines.append(f"{k}: [{', '.join(repr(x) for x in v)}]")
        else:
            fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    path.write_text("\n".join(fm_lines) + "\n\n" + body.strip() + "\n", encoding="utf-8")


def find_prior_run(category: str) -> Optional[Path]:
    """Most recent archive/ subfolder for the category, or None."""
    d = category_dir(category) / "archive"
    if not d.exists():
        return None
    subs = sorted([p for p in d.iterdir() if p.is_dir()], reverse=True)
    return subs[0] if subs else None
