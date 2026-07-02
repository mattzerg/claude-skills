#!/usr/bin/env python3
"""Phase 3c — Create Zergboard cards for unlinked hub entities.

Usage:
    create_zergboard_card.py <entity-id> [--dry-run] [--board NAME]
    create_zergboard_card.py --missing --type TYPE [--status S,S,...] [--dry-run]

For a single entity: creates one card on the type-appropriate board, writes
the new card UUID into `linked.zergboard_card` on the entity file.

For --missing: bulk-creates cards for all entities of the given type matching
the status filter that don't yet have `linked.zergboard_card` set.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from lib import frontmatter  # noqa: E402
from lib.entities import META_DIR, load_all, load_one  # noqa: E402


ZERGBOARD = Path.home() / ".claude" / "skills" / "zergboard-skill" / "zergboard_skill.py"


# Default board per entity type. Tuned to match BOARD_AFFINITY in sync_zergboard.py.
PRIMARY_BOARD = {
    "experiment": "Marketing",
    "content": "Marketing",
    "prospect": "B2B/BD",
    "bd_target": "B2B/BD",
    "launch": "Marketing",
    "theme": "Marketing",
    "metric": "Operations",
}

# Lane prefix per entity type — keeps cards readable & filterable.
LANE_PREFIX = {
    "experiment": "[Experiments]",
    "content": "[Content]",
    "prospect": "[Solutions]",
    "bd_target": "[BD]",
    "launch": "[Launches]",
    "theme": "[Themes]",
    "metric": "[Metrics]",
}

PRIORITY_MAP = {
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def _zb(args: list[str]) -> dict:
    res = subprocess.run(
        [sys.executable, str(ZERGBOARD), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(f"zergboard-skill failed: {res.stderr.strip() or res.stdout.strip()}")
    return json.loads(res.stdout) if res.stdout.strip() else {}


def _board_id_by_name(workspace_id: str, name: str) -> str | None:
    """Look up a board UUID by display name within the workspace."""
    cache_path = META_DIR / "zergboard-cards.json"
    if cache_path.exists():
        # Fast path: use cached board list
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            for b in cached.get("boards", []):
                if b.get("name") == name:
                    return b.get("id")
        except (OSError, ValueError):
            pass
    # Live fallback
    data = _zb(["boards", workspace_id])
    for b in data.get("boards", []):
        if b.get("name") == name:
            return b["id"]
    return None


def _workspace_id() -> str:
    """Use cached workspace id from prior sync; fall back to live lookup."""
    cache_path = META_DIR / "zergboard-cards.json"
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))["workspace_id"]
        except (OSError, KeyError, ValueError):
            pass
    data = _zb(["workspaces"])
    for w in data.get("workspaces", []):
        if w.get("name") == "Zerg":
            return w["id"]
    raise SystemExit("could not resolve Zerg workspace")


def _build_card_payload(entity) -> tuple[str, str, str]:
    """Return (board_name, title, description) for the card."""
    m = entity.meta
    etype = entity.type
    board = PRIMARY_BOARD.get(etype, "Marketing")
    lane = LANE_PREFIX.get(etype, "")
    title_core = m.get("title") or entity.id
    # Add a status hint for at-a-glance scanning
    status = m.get("status", "")
    title = f"{lane} {title_core}".strip()
    # Description: hub entity link + key fields
    rel_path = entity.path.split("/MattZerg/")[-1]
    parts = [
        f"_Hub entity:_ `MattZerg/{rel_path}`",
        f"_Status:_ `{status}` · _Owner:_ {m.get('owner') or '?'} · _Last touch:_ {m.get('last_touch') or '?'}",
        "",
    ]
    if etype == "experiment":
        parts += [
            f"**Hypothesis:** {m.get('hypothesis', '')}",
            f"**Success metric:** {m.get('success_metric', '')}",
            f"**Kill date:** {m.get('kill_date', '')}",
            f"**RICE:** {m.get('rice_score') or m.get('RICE_score', '')}",
        ]
    elif etype == "bd_target":
        parts += [
            f"**Category:** {m.get('category', '')}",
            f"**Why:** {m.get('why', '')}",
            f"**Next:** {m.get('next_action', '')}",
        ]
    elif etype == "prospect":
        parts += [
            f"**Category:** {m.get('category', '')}",
            f"**Score:** {m.get('score', '')}/100",
            f"**Source:** {m.get('source', '')}",
            f"**Next:** {m.get('next_action', '')}",
        ]
    elif etype == "content":
        parts += [
            f"**Kind:** {m.get('kind', '')}",
            f"**Target date:** {m.get('target_date', '')}",
        ]
    elif etype == "launch":
        parts += [
            f"**Product:** {m.get('product', '')}",
            f"**Ship date:** {m.get('ship_date') or 'TBD'}",
            f"**Channels:** {', '.join(m.get('channels') or [])}",
        ]
    parts += [
        "",
        "_Auto-managed by `gtm-hub` skill. Edit the entity file, not this card._",
    ]
    description = "\n".join(parts)
    return board, title, description


def _priority_for(entity) -> str:
    m = entity.meta
    if entity.type == "prospect":
        try:
            score = int(m.get("score") or 0)
        except (ValueError, TypeError):
            score = 0
        if score >= 85:
            return "high"
        if score >= 70:
            return "medium"
        return "low"
    if entity.type == "experiment":
        try:
            rice = int(m.get("rice_score") or m.get("RICE_score") or 0)
        except (ValueError, TypeError):
            rice = 0
        if rice >= 200:
            return "high"
        if rice >= 100:
            return "medium"
        return "low"
    if entity.type == "launch":
        return "high"
    return "medium"


def create_card(entity, *, override_board: str | None = None, dry_run: bool = False) -> str | None:
    """Create one card. Returns the new card UUID (or None on dry-run)."""
    m = entity.meta
    if isinstance(m.get("linked"), dict) and m["linked"].get("zergboard_card"):
        print(f"  - {entity.id}: already linked to {m['linked']['zergboard_card']}; skip")
        return m["linked"]["zergboard_card"]
    board_name, title, description = _build_card_payload(entity)
    board_name = override_board or board_name
    workspace_id = _workspace_id()
    board_id = _board_id_by_name(workspace_id, board_name)
    if not board_id:
        print(f"  ! {entity.id}: target board {board_name!r} not found", file=sys.stderr)
        return None
    priority = _priority_for(entity)
    if dry_run:
        print(f"  → would create on {board_name}: {title}  [priority={priority}]")
        return None
    # Actually create
    args = [
        "create",
        board_id,
        "--title", title,
        "--description", description,
        "--priority", priority,
    ]
    try:
        result = _zb(args)
    except RuntimeError as e:
        print(f"  ! {entity.id}: create failed — {e}", file=sys.stderr)
        return None
    card = result.get("card") or result
    new_id = card.get("id") if isinstance(card, dict) else None
    if not new_id:
        print(f"  ! {entity.id}: create succeeded but no id in response: {result}", file=sys.stderr)
        return None
    # Write back linked.zergboard_card
    text = Path(entity.path).read_text(encoding="utf-8")
    linked = dict(m.get("linked") or {}) if isinstance(m.get("linked"), dict) else {}
    linked["zergboard_card"] = new_id
    new_text = frontmatter.update_in_text(text, {"linked": linked})
    Path(entity.path).write_text(new_text, encoding="utf-8")
    print(f"  ✓ {entity.id} → card {card.get('external_id') or new_id[:8]} on {board_name}")
    return new_id


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("entity_id", nargs="?", help="single entity to create a card for")
    p.add_argument("--missing", action="store_true", help="bulk: create cards for all unlinked entities matching --type/--status")
    p.add_argument("--type", help="entity type filter (for --missing)")
    p.add_argument("--status", help="comma-sep status filter (for --missing)")
    p.add_argument("--board", help="override default board name")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not ZERGBOARD.exists():
        print(f"zergboard-skill not found at {ZERGBOARD}", file=sys.stderr)
        return 1

    if args.entity_id and not args.missing:
        entity = load_one(args.entity_id)
        if not entity:
            print(f"entity {args.entity_id!r} not found", file=sys.stderr)
            return 1
        create_card(entity, override_board=args.board, dry_run=args.dry_run)
        return 0

    if args.missing:
        if not args.type:
            print("--missing requires --type", file=sys.stderr)
            return 2
        wanted_statuses = set(s.strip() for s in (args.status or "").split(",") if s.strip())
        entities = [e for e in load_all() if e.type == args.type]
        if wanted_statuses:
            entities = [e for e in entities if e.meta.get("status") in wanted_statuses]
        entities = [
            e for e in entities
            if not (isinstance(e.meta.get("linked"), dict) and e.meta["linked"].get("zergboard_card"))
        ]
        print(f"{len(entities)} unlinked {args.type} entities to process"
              + (f" (statuses: {sorted(wanted_statuses)})" if wanted_statuses else ""))
        for e in entities:
            create_card(e, override_board=args.board, dry_run=args.dry_run)
        return 0

    print("usage: create_zergboard_card.py <entity-id> | --missing --type TYPE [--status S,S]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
