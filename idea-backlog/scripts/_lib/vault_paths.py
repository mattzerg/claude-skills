"""Single source of truth for vault paths.

The vault now lives at `~/Obsidian/Zerg/MattZerg` (the 2026-06-30 migration off
iCloud). It is a plain, non-TCC directory that cron/launchd processes can read
AND write directly — so the old iCloud TCC-sidestep (read-mirror at
`~/.zerg-vault-mirror/` + writeback staging at `~/.zerg-vault-writeback/`,
flushed by retired launchd daemons) is no longer needed and has been collapsed.
Reads and writes both go straight to `~/Obsidian`. See
`~/.config/zerg/vault_path.py`.
"""
from __future__ import annotations

from pathlib import Path

_ICLOUD_VAULT_ROOT = Path.home() / "Obsidian" / "Zerg" / "MattZerg"
WRITEBACK_VAULT_ROOT = Path.home() / "Obsidian" / "Zerg" / "MattZerg"

# Reads and writes both resolve directly to the live ~/Obsidian vault.
VAULT_ROOT = Path.home() / "Obsidian" / "Zerg" / "MattZerg"

MHE_VAULT_ROOT = Path("/Users/mattheweisner/Obsidian/MHE")

IDEAS_ROOT = VAULT_ROOT / "Ideas"
INBOX_DIR = IDEAS_ROOT / "_inbox"
ARCHIVE_DIR = IDEAS_ROOT / "_archive"
META_DIR = IDEAS_ROOT / "_meta"
INDEX_JSON = META_DIR / "index.json"
EXTRACTION_LOG = META_DIR / "extraction-log.md"

CATEGORIES = (
    "zerg-product",
    "zerg-content",
    "zerg-tooling",
    "personal-venture",
    "personal-life",
    "shopping",
    "research",
)

# Legacy → new aliasing (for migration of existing files written under old names)
CATEGORY_LEGACY_ALIASES = {
    "product": "zerg-product",      # default; recategorize.py refines for personal-venture cases
    "content": "zerg-content",
    "tooling": "zerg-tooling",
    "personal": "personal-life",    # most existing "personal" items are lifestyle, not venture
    # "research" unchanged
}

TASKS_INBOX = VAULT_ROOT / "Tasks" / "inbox.md"

SCAN_EXCLUDE_DIRS = {
    # Already ingested or admin
    "Ideas",  # don't re-scan ourselves
    "_style",
    "templates",
    "assets",
    "copilot",
    # Time-series / log content (no idea density)
    "Conversations",
    "Daily",
    "Meetings",
    "Memes",
    # Reference / facts (people, places, companies)
    "People",
    "Personas",
    "Places",
    "Companies",
    "Firms",
    # Career artifacts (CVs, LinkedIn dumps)
    "Career",
    # Brand asset catalogs
    "Brand",
    # Skill-feedback / skill-admin
    "Feedback",
    "Skills",
    # Competitive matrices (already structured analysis, not idea source)
    "Competitive",
    # Hidden / vendor
    ".obsidian",
    "node_modules",
    "generated_images",
}

# Top-level admin/index files to skip (relative to vault root).
SCAN_EXCLUDE_FILES = {
    "AGENTS.md",
    "CLAUDE.md",
    "Welcome.md",
    "Vault Map.md",
    "README.md",
}


def category_dir(category: str) -> Path:
    if category not in CATEGORIES:
        raise ValueError(f"Unknown category: {category}. Valid: {CATEGORIES}")
    return IDEAS_ROOT / category


def workdir() -> Path:
    """Per-skill working directory (not in vault)."""
    p = Path.home() / ".claude" / "skills" / "idea-backlog" / "_workdir"
    p.mkdir(parents=True, exist_ok=True)
    return p
