"""Walk Growth/ and load all entities.

Read/write split — required by macOS TCC. Cron-launched Python can't read
iCloud Drive paths (see `project_vault_mirror.md`):

- READS use the local mirror at ~/.zerg-vault-mirror/ when available, via
  the `vault_path` helper at ~/.config/zerg/vault_path.py. The mirror is
  refreshed every 15 min by a LaunchAgent. Cron-safe.

- WRITES always target the canonical iCloud vault. If we're running in a
  cron context where iCloud is unreachable, writes fail loudly with
  PermissionError — DO NOT silently write to the mirror (the mirror is
  read-only, sync is one-way iCloud → mirror, and any cron write would be
  obliterated on the next 15-min rsync).
"""
from __future__ import annotations

import sys
from pathlib import Path

from . import frontmatter
from .schema import TYPE_DIRS, Entity


_HELPER_DIR = Path.home() / ".config" / "zerg"
if str(_HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(_HELPER_DIR))

try:
    from vault_path import VAULT_ROOT as _ICLOUD_VAULT  # type: ignore
    from vault_path import MIRROR_ROOT as _MIRROR_VAULT  # type: ignore
except ImportError:
    # Post-migration: live vault is ~/Obsidian (the old iCloud path was deleted).
    # This branch only runs if vault_path can't be imported; kept correct so the
    # codebase has zero live iCloud-vault references.
    _ICLOUD_VAULT = Path.home() / "Obsidian/Zerg/MattZerg"
    _MIRROR_VAULT = Path.home() / ".zerg-vault-mirror" / "MattZerg"


def _resolve_read_root() -> Path:
    """Prefer the live vault root (now ~/Obsidian/Zerg/MattZerg via vault_path —
    the old iCloud path was retired 2026-06-30). Fall back to the mirror symlink
    only if the primary is unreadable (cron / launchd TCC edge cases).

    NOTE: `_ICLOUD_VAULT` is a legacy name — it resolves to the live ~/Obsidian
    vault, not iCloud. Kept as-is to avoid churning its many call sites.
    """
    try:
        list(_ICLOUD_VAULT.iterdir())
        return _ICLOUD_VAULT
    except (PermissionError, OSError):
        pass
    if _MIRROR_VAULT.exists():
        return _MIRROR_VAULT
    return _ICLOUD_VAULT  # let downstream raise


# Canonical vault paths (live ~/Obsidian via the legacy _ICLOUD_VAULT name) — used for WRITES.
VAULT = _ICLOUD_VAULT
GROWTH_DIR = VAULT / "Projects" / "Zerg-Production" / "Growth"
META_DIR = GROWTH_DIR / "_meta"

# Read paths — iCloud-first, mirror-fallback (cron-safe).
READ_VAULT = _resolve_read_root()
READ_GROWTH_DIR = READ_VAULT / "Projects" / "Zerg-Production" / "Growth"
READ_META_DIR = READ_GROWTH_DIR / "_meta"


def load_all(growth_dir: Path = READ_GROWTH_DIR) -> list[Entity]:
    """Read all entity files. Defaults to the mirror-tolerant root."""
    out: list[Entity] = []
    for dir_name, etype in TYPE_DIRS.items():
        d = growth_dir / dir_name
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            if f.name.startswith("_"):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            meta, body = frontmatter.parse(text)
            if not meta:
                continue
            out.append(Entity(path=str(f), type=etype, meta=meta, body=body))
    return out


def load_by_type(etype: str, growth_dir: Path = READ_GROWTH_DIR) -> list[Entity]:
    return [e for e in load_all(growth_dir) if e.type == etype]


def load_one(entity_id: str, growth_dir: Path = READ_GROWTH_DIR) -> Entity | None:
    for e in load_all(growth_dir):
        if e.id == entity_id:
            return e
    return None


def writable_path(rel_path: str) -> Path:
    """Resolve a Growth/-relative path under the canonical iCloud vault for writing.

    Always returns the iCloud path. Caller handles PermissionError if iCloud
    is TCC-blocked (cron context — should not normally write from there).
    """
    return GROWTH_DIR / rel_path


def read_growth_file(rel_path: str) -> str | None:
    """Read a Growth/-relative file, checking staging → iCloud → mirror in order.

    Staging wins because the most-recent write from this same regenerate
    invocation might still be in `~/.zerg-vault-writeback/`, not yet
    flushed to iCloud (the flush daemon runs every 60s). iCloud is next
    if reachable. Mirror is last because it can lag up to 15 minutes.

    Returns the file content as a string, or None if not found anywhere.
    """
    candidates = [
        Path.home() / ".zerg-vault-writeback" / "MattZerg" / "Projects" / "Zerg-Production" / "Growth" / rel_path,
        GROWTH_DIR / rel_path,
        _MIRROR_VAULT / "Projects" / "Zerg-Production" / "Growth" / rel_path,
    ]
    for p in candidates:
        try:
            if p.exists():
                return p.read_text(encoding="utf-8")
        except (PermissionError, OSError):
            continue
    return None


def write_growth_file(rel_path: str, content):
    """Write to a Growth/-relative path, TCC-resilient.

    Tries direct iCloud write first (interactive context). On PermissionError
    (cron/launchd context), falls back to `vault_write()` which stages under
    `~/.zerg-vault-writeback/` for the vault-flush LaunchAgent to copy into
    iCloud within ~60s. See `feedback_cron_daemon_silent_tcc_failure.md`.

    Returns the path that was actually written (iCloud direct, or staging).
    """
    target = GROWTH_DIR / rel_path
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write — the vault is live-synced; tmp-in-same-dir + os.replace
        # avoids a partial-file read during an Obsidian Sync flush.
        tmp = target.with_name("." + target.name + ".tmp")
        if isinstance(content, str):
            tmp.write_text(content, encoding="utf-8")
        else:
            tmp.write_bytes(content)
        import os
        os.replace(tmp, target)
        return target
    except (PermissionError, OSError):
        pass
    # Staging fallback — vault_write expects a path relative to MattZerg/,
    # not Growth/, so prepend the Growth subpath.
    try:
        from vault_path import vault_write  # type: ignore[import-not-found]
    except ImportError:
        raise
    return vault_write(f"Projects/Zerg-Production/Growth/{rel_path}", content)
