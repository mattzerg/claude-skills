"""Cascade application — execute structured updates on linked entities.

A decision entity can include a `cascade` frontmatter field:

    cascade:
      <option-key>:
        - entity: <id|relpath>
          set:
            field: value
          append:
            field: text
        - entity: <id|relpath>
          ...

When `gtm decide <id> <option-key>` runs, the cascade matching that option-key
is applied: each action updates the target entity's frontmatter (`set`) and/or
appends to a markdown body section (`append`).

Idempotency: cascades run only on the forward transition open|deferred →
decided. Re-running is blocked by act.py's `allowed_from` guard.

Safety: `--dry-run` mode previews actions without writing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import frontmatter
from .entities import GROWTH_DIR, READ_GROWTH_DIR, load_one


def _resolve_entity_path(ref: str) -> Path | None:
    """Locate the canonical (iCloud, writable) path for an entity ref.

    Ref can be:
      - an entity id (e.g., `zergboard-public-launch`)
      - a Growth/-relative path (e.g., `launches/zergboard-public-launch.md`)
      - an absolute path
    Returns the iCloud-canonical Path even if the entity was loaded from mirror.
    """
    if not ref:
        return None
    # Absolute path
    if ref.startswith("/"):
        return Path(ref)
    # Looks like a Growth/-relative path with `/`
    if "/" in ref:
        # Strip any leading "Growth/" if present
        ref = ref.removeprefix("Growth/")
        return GROWTH_DIR / ref
    # Bare id — look up via load_one (mirror-tolerant read)
    entity = load_one(ref)
    if entity:
        # entity.path is the mirror-or-iCloud read path. Map to canonical write path.
        p = Path(entity.path)
        try:
            rel = p.resolve().relative_to(READ_GROWTH_DIR.resolve())
            return GROWTH_DIR / rel
        except (ValueError, OSError):
            return p
    return None


def execute(cascade_spec: dict | None, option_key: str, *, dry_run: bool = False) -> list[str]:
    """Apply the cascade for `option_key`. Returns a list of human-readable
    action summaries. Empty list = nothing matched or no cascade defined.
    """
    if not cascade_spec or not isinstance(cascade_spec, dict):
        return []
    actions = cascade_spec.get(option_key)
    if not actions or not isinstance(actions, list):
        return []

    log: list[str] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        target_ref = action.get("entity")
        target = _resolve_entity_path(target_ref) if target_ref else None
        if not target or not target.exists():
            log.append(f"⚠ skipped — entity not found: {target_ref}")
            continue
        set_updates = action.get("set") or {}
        append_updates = action.get("append") or {}
        text = target.read_text(encoding="utf-8")

        # SET: structured frontmatter update via existing helper
        if isinstance(set_updates, dict) and set_updates:
            if dry_run:
                pretty = ", ".join(f"{k}={v}" for k, v in set_updates.items())
                log.append(f"  would-set {target.name}: {pretty}")
            else:
                text = frontmatter.update_in_text(text, set_updates)
                pretty = ", ".join(f"{k}={v}" for k, v in set_updates.items())
                log.append(f"  ✓ set {target.name}: {pretty}")

        # APPEND: add text to body sections. action.append = {section: text}
        if isinstance(append_updates, dict) and append_updates:
            if dry_run:
                for section, line in append_updates.items():
                    log.append(f"  would-append to {target.name} § {section}: {line[:60]}")
            else:
                for section, line in append_updates.items():
                    text = _append_under_section(text, section, line)
                    log.append(f"  ✓ append {target.name} § {section}: {line[:60]}")

        if not dry_run:
            target.write_text(text, encoding="utf-8")
    return log


def _append_under_section(text: str, section: str, line: str) -> str:
    """Append `line` immediately after the `## <section>` header in `text`.

    If the section doesn't exist, append a new section at end of body.
    """
    marker = f"\n## {section}\n"
    idx = text.find(marker)
    if idx < 0:
        # Append new section at end
        sep = "" if text.endswith("\n") else "\n"
        return text + f"{sep}\n## {section}\n\n{line}\n"
    # Insert right after the marker (preserving the blank line if present)
    cut = idx + len(marker)
    # Skip a single blank line after the marker if any
    if text[cut:cut + 1] == "\n":
        cut += 1
    return text[:cut] + line + "\n" + text[cut:]
