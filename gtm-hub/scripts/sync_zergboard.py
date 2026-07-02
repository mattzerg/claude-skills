#!/usr/bin/env python3
"""Phase 3a — Zergboard sync (read-side).

Pulls cards from the Zerg workspace's boards via zergboard-skill, caches them
to `_meta/zergboard-cards.json`, and writes `linked.zergboard_card` onto hub
entities when a high-confidence title match exists.

This is the read-only direction: hub learns about board state. The opposite
direction (hub mutation → board) is Phase 3b.

Usage:
    sync_zergboard.py [--workspace UUID|name] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from lib import frontmatter  # noqa: E402
from lib.entities import META_DIR, load_all  # noqa: E402


ZERGBOARD = Path.home() / ".claude" / "skills" / "zergboard-skill" / "zergboard_skill.py"
DEFAULT_WORKSPACE = "Zerg"  # the org with the GTM boards

# Which boards we attempt to link entities against. Other boards are still cached.
LINK_BOARDS = {"Marketing", "B2B/BD", "Website", "Operations"}

# Per-entity-type allowlist: only match against cards from these boards.
# Prevents e.g. a BD target named "Cloudflare" matching a Marketing
# content-distribution card just because the partner name overlaps.
BOARD_AFFINITY = {
    "experiment": {"Marketing", "Operations", "ZergBoard"},
    "content": {"Marketing", "Website"},
    "prospect": {"B2B/BD"},
    "bd_target": {"B2B/BD"},
    "launch": {"Marketing"},
    "theme": {"Marketing"},
    "metric": {"Operations"},
    "workstream": {"Marketing", "B2B/BD", "Website", "Operations"},
}


def _zb(args: list[str]) -> dict:
    """Run zergboard-skill and return parsed JSON. Raises on non-zero."""
    res = subprocess.run(
        [sys.executable, str(ZERGBOARD), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(f"zergboard-skill failed: {res.stderr.strip() or res.stdout.strip()}")
    if not res.stdout.strip():
        return {}
    return json.loads(res.stdout)


def resolve_workspace(name_or_id: str) -> tuple[str, str]:
    data = _zb(["workspaces"])
    for w in data.get("workspaces", []):
        if w["id"] == name_or_id or w.get("name") == name_or_id or w.get("slug") == name_or_id:
            return w["id"], w["name"]
    raise SystemExit(f"workspace {name_or_id!r} not found")


def pull_cards(workspace_id: str) -> tuple[list[dict], list[dict]]:
    """Return (boards, cards-flat) for a workspace."""
    boards_data = _zb(["boards", workspace_id])
    boards = boards_data.get("boards", [])
    all_cards: list[dict] = []
    out_boards: list[dict] = []
    for b in boards:
        bid = b["id"]
        try:
            cd = _zb(["cards", bid, "--limit", "500"])
        except RuntimeError as e:
            print(f"  ! could not pull cards for {b.get('name')}: {e}", file=sys.stderr)
            continue
        cards = cd.get("cards", [])
        out_boards.append({
            "id": bid,
            "name": b.get("name"),
            "card_count": len(cards),
        })
        for c in cards:
            all_cards.append({
                "id": c["id"],
                "external_id": c.get("external_id"),
                "title": c.get("title", ""),
                "status": c.get("status"),
                "column": c.get("column_name"),
                "state_kind": c.get("state_kind"),
                "priority": c.get("priority"),
                "board_id": bid,
                "board_name": b.get("name"),
                "due_at": c.get("due_at"),
            })
    return out_boards, all_cards


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _strip_lane(title: str) -> str:
    """Remove leading `[Lane]` prefix from a card title."""
    return re.sub(r"^\s*\[[^\]]+\]\s*", "", title or "")


def match_score(entity_title: str, entity_id: str, entity_type: str, card_title: str) -> int:
    """Return 0-100 confidence the card represents this entity."""
    if not entity_title or not card_title:
        return 0
    ct = _strip_lane(card_title)
    et = _norm(entity_title)
    cn = _norm(ct)
    if not et or not cn:
        return 0
    # Exact match on entity-id (e.g., exp-001) in card title
    if entity_id and entity_id.lower() in (card_title or "").lower():
        return 100
    # Entity title is a substring of card title (or vice versa for long card titles)
    if et in cn:
        # Stronger if it's the start
        return 90 if cn.startswith(et) else 75
    if cn in et and len(cn) > 8:
        return 70
    # Token overlap
    et_tokens = set(et.split())
    cn_tokens = set(cn.split())
    if not et_tokens:
        return 0
    overlap = len(et_tokens & cn_tokens)
    if overlap >= 3 and overlap >= len(et_tokens) // 2:
        return 50
    return 0


def link_entities(cards: list[dict], dry_run: bool) -> dict:
    """For each entity without `linked.zergboard_card`, find best card match."""
    entities = load_all()
    link_cards = [c for c in cards if c["board_name"] in LINK_BOARDS]
    stats = {
        "entities_total": len(entities),
        "already_linked": 0,
        "newly_linked": 0,
        "ambiguous": 0,
        "no_match": 0,
        "broken_link": 0,
    }
    cards_by_id = {c["id"]: c for c in cards}
    for entity in entities:
        meta = entity.meta
        linked = meta.get("linked") or {}
        if isinstance(linked, dict) and linked.get("zergboard_card"):
            existing = linked["zergboard_card"]
            if existing not in cards_by_id:
                stats["broken_link"] += 1
            else:
                stats["already_linked"] += 1
            continue
        # Score every link-eligible card, restricted to boards relevant to this entity type
        allowed = BOARD_AFFINITY.get(entity.type, set())
        title = meta.get("title") or entity.id
        scores = [
            (match_score(title, entity.id, entity.type, c["title"]), c)
            for c in link_cards
            if not allowed or c["board_name"] in allowed
        ]
        scores = [(s, c) for s, c in scores if s > 0]
        scores.sort(key=lambda x: -x[0])
        if not scores:
            stats["no_match"] += 1
            continue
        top_score, top_card = scores[0]
        if top_score < 75:
            stats["no_match"] += 1
            continue
        # Ambiguity check: a second card scoring >= 75 also
        if len(scores) > 1 and scores[1][0] >= 75 and (top_score - scores[1][0]) < 15:
            stats["ambiguous"] += 1
            continue
        # High-confidence link — write it back
        stats["newly_linked"] += 1
        print(f"  → {entity.type:<11} {entity.id:<28} ↔ {top_card.get('external_id') or top_card['id'][:8]:<10} {top_card['title'][:60]} (score {top_score})")
        if dry_run:
            continue
        text = Path(entity.path).read_text(encoding="utf-8")
        new_linked = dict(linked) if isinstance(linked, dict) else {}
        new_linked["zergboard_card"] = top_card["id"]
        new_text = frontmatter.update_in_text(text, {"linked": new_linked})
        Path(entity.path).write_text(new_text, encoding="utf-8")
    return stats


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not ZERGBOARD.exists():
        print(f"zergboard-skill not found at {ZERGBOARD}", file=sys.stderr)
        return 1

    ws_id, ws_name = resolve_workspace(args.workspace)
    print(f"workspace: {ws_name} ({ws_id})")

    boards, cards = pull_cards(ws_id)
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "workspace_id": ws_id,
        "workspace_name": ws_name,
        "boards": boards,
        "cards": cards,
    }
    out = META_DIR / "zergboard-cards.json"
    META_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"wrote {out} — {len(cards)} cards across {len(boards)} boards")

    stats = link_entities(cards, dry_run=args.dry_run)
    verb = "would-link" if args.dry_run else "linked"
    print(
        f"  entities: {stats['entities_total']} total · "
        f"{stats['already_linked']} pre-linked · "
        f"{verb} {stats['newly_linked']} · "
        f"{stats['ambiguous']} ambiguous · "
        f"{stats['no_match']} no-match · "
        f"{stats['broken_link']} broken-links"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
