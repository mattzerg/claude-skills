#!/usr/bin/env python3
"""sync — bidirectional sync between vault publishing/ entries and Zergboard.

Vault is canonical source. Each Zergboard card description has a fenced state
block:

    <free body>

    ---
    <!-- zpub:state -->
    id: pub-...
    status: review
    publish_target: 2026-05-15
    gates.fakematt_copyedit: passed
    gates.signoff: pending
    blockers:
      - "..."
    updated_at: 2026-05-10T14:32:00Z
    <!-- /zpub:state -->

Sync compares vault `updated_at` vs the value in the fenced block and applies
the newer side. Last-write-wins; conflicts (both newer than each other within
60s) prefer vault and append to conflicts.log.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from zpub import (
    BOARD_CONFIG,
    CONFLICTS_PATH,
    DEFAULT_COLUMNS,
    PUB_DIR,
    META_DIR,
    STATUS_TO_COLUMN,
    Entry,
    VALID_GATE_VALUES,
    VALID_STATUSES,
    VALID_TYPES,
    _parse_iso8601,
    all_entries,
    now_iso,
    rag_state,
    save_entry,
    rebuild_index,
)

ZERGBOARD = Path.home() / ".claude/skills/zergboard-skill/zergboard_skill.py"

FENCE_OPEN = "<!-- zpub:state -->"
FENCE_CLOSE = "<!-- /zpub:state -->"

PRIORITY_FOR_RAG = {"red": "urgent", "amber": "high", "yellow": "high", "green": "medium"}


def _zb(*args: str, allow_fail: bool = False) -> dict[str, Any]:
    """Invoke zergboard-skill, return parsed JSON output."""
    cmd = ["python3", str(ZERGBOARD), *args]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 and not allow_fail:
        sys.stderr.write(f"zergboard-skill failed: {' '.join(args)}\n{res.stderr}\n")
        sys.exit(2)
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return {"raw": res.stdout, "error": res.stderr}


def _board_id() -> str:
    if not BOARD_CONFIG.exists():
        sys.stderr.write("no board.json — run `zpub bootstrap-board` first\n")
        sys.exit(1)
    return json.loads(BOARD_CONFIG.read_text())["board_id"]


# ---------- Bootstrap ----------

def bootstrap_board(force: bool = False) -> None:
    if BOARD_CONFIG.exists() and not force:
        cfg = json.loads(BOARD_CONFIG.read_text())
        print(f"board already configured: {cfg['board_id']}")
        print(f"  → https://zergboard.fly.dev/?board={cfg['board_id']}")
        print("  use --force to overwrite (does NOT delete live board)")
        return

    print("creating Zergboard 'Publishing' board...")
    result = _zb(
        "create-board", "Publishing",
        "--description", "Unified publishing/content tracker — synced from MattZerg/Projects/Zerg-Production/Growth/publishing/. Source of truth is vault; do not delete the fenced <!-- zpub:state --> block in card descriptions.",
        "--columns", *DEFAULT_COLUMNS,
    )
    board = result.get("board") or result
    board_id = board.get("id") if isinstance(board, dict) else None
    if not board_id:
        sys.stderr.write(f"could not extract board id from response: {result}\n")
        sys.exit(2)

    BOARD_CONFIG.write_text(json.dumps({
        "board_id": board_id,
        "board_name": "Publishing",
        "card_prefix": board.get("card_prefix"),
        "created_at": now_iso(),
    }, indent=2) + "\n")

    print(f"board created: {board_id}")
    print(f"  → https://zergboard.fly.dev/?board={board_id}")
    print(f"  → board.json written to {BOARD_CONFIG}")


# ---------- Fence parsing/rendering ----------

def _build_card_description(e: Entry) -> str:
    """Body text for a Zergboard card: free body + fenced state block."""
    body = e.body.rstrip()
    parts = [body] if body else []
    parts.append("")
    parts.append("---")
    parts.append(FENCE_OPEN)
    parts.append(f"id: {e.id}")
    parts.append(f"status: {e.status}")
    if e.publish_target:
        parts.append(f"publish_target: {e.publish_target}")
    if e.publish_actual:
        parts.append(f"publish_actual: {e.publish_actual}")
    parts.append(f"type: {e.type}")
    parts.append(f"owner: {e.owner}")
    for k, v in e.gates.items():
        parts.append(f"gates.{k}: {v}")
    if e.blockers:
        parts.append("blockers:")
        for b in e.blockers:
            parts.append(f"  - {b}")
    parts.append(f"updated_at: {e.updated_at}")
    parts.append(FENCE_CLOSE)
    return "\n".join(parts)


def _parse_fenced_state(description: str) -> Optional[dict[str, Any]]:
    if not description:
        return None
    m = re.search(
        re.escape(FENCE_OPEN) + r"\s*\n(.*?)\n\s*" + re.escape(FENCE_CLOSE),
        description, re.S,
    )
    if not m:
        return None
    block = m.group(1)
    state: dict[str, Any] = {"gates": {}, "blockers": []}
    in_blockers = False
    for raw in block.splitlines():
        line = raw.rstrip()
        if not line.strip():
            in_blockers = False
            continue
        if line.lstrip().startswith("- ") and in_blockers:
            state["blockers"].append(line.lstrip()[2:].strip().strip('"'))
            continue
        in_blockers = False
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"')
        if key == "blockers":
            in_blockers = True
            continue
        if key.startswith("gates."):
            state["gates"][key[len("gates."):]] = val
            continue
        state[key] = val
    return state


def _strip_fence(description: str) -> str:
    """Free body = description minus fence and the '---' separator above it."""
    if FENCE_OPEN not in description:
        return description.rstrip()
    head = description.split(FENCE_OPEN, 1)[0]
    head = re.sub(r"\n\s*---\s*\n?$", "", head)
    return head.rstrip()


# ---------- Sync ----------

def run_sync(direction: str = "both", dry_run: bool = False) -> None:
    board_id = _board_id()
    cards_resp = _zb("cards", board_id, "--limit", "500")
    cards_summary = cards_resp.get("cards", [])
    # cards summary lacks description — fetch full card per id
    full_cards: dict[str, dict[str, Any]] = {}
    for c in cards_summary:
        full = _zb("card", c["id"]).get("card", {})
        full_cards[c["id"]] = full

    entries = {e.id: e for e in all_entries()}
    by_card_id = {e.zergboard_card_id: e for e in entries.values() if e.zergboard_card_id}

    pulled = pushed = created = conflicts = 0

    # PULL — apply card -> vault if card is newer
    if direction in ("pull", "both"):
        for cid, card in full_cards.items():
            description = card.get("description") or ""
            state = _parse_fenced_state(description)
            if not state:
                continue
            entry_id = state.get("id")
            if not entry_id or entry_id not in entries:
                continue
            e = entries[entry_id]
            card_updated = _parse_iso8601(state.get("updated_at", "")) or dt.datetime.fromtimestamp(0, dt.timezone.utc)
            vault_updated = _parse_iso8601(e.updated_at) or dt.datetime.fromtimestamp(0, dt.timezone.utc)

            if card_updated <= vault_updated:
                continue

            # Conflict: both edited within 60s — prefer vault, log
            delta = abs((card_updated - vault_updated).total_seconds())
            if delta < 60 and vault_updated > dt.datetime.fromtimestamp(0, dt.timezone.utc):
                _log_conflict(e, "card-newer-but-recent-vault-edit",
                              vault_updated.isoformat(), card_updated.isoformat())
                conflicts += 1
                continue

            # Apply card state to entry
            changed = _apply_state_to_entry(e, state, card.get("id"))
            free_body = _strip_fence(description)
            if free_body and free_body != e.body.rstrip():
                e.body = free_body + "\n"
                changed = True
            if changed:
                e.updated_at = state.get("updated_at") or now_iso()
                if not dry_run:
                    save_entry(e)
                pulled += 1
                print(f"  pull: {e.id} ← card {card.get('external_id', card['id'][:8])}")

    # PUSH — apply vault -> card if vault is newer (or card doesn't exist yet)
    if direction in ("push", "both"):
        for e in entries.values():
            description_target = _build_card_description(e)
            color, _ = rag_state(e)
            priority = PRIORITY_FOR_RAG[color]
            target_column = STATUS_TO_COLUMN.get(e.status, "Drafting")

            if not e.zergboard_card_id or e.zergboard_card_id not in full_cards:
                # Create new card
                if dry_run:
                    print(f"  create: {e.id} → new card in {target_column}")
                    created += 1
                    continue
                # Zergboard `create` doesn't accept --due; we set it via `update` below.
                create_args = [
                    "python3", str(ZERGBOARD), "create", _board_id(),
                    "--title", e.title,
                    "--description", description_target,
                    "--priority", priority,
                    "--column", target_column,
                ]
                res = subprocess.run(create_args, capture_output=True, text=True)
                if res.returncode != 0:
                    print(f"  ! create failed for {e.id}: {res.stderr}", file=sys.stderr)
                    continue
                try:
                    payload = json.loads(res.stdout)
                except json.JSONDecodeError:
                    print(f"  ! bad response for {e.id}: {res.stdout[:200]}", file=sys.stderr)
                    continue
                card_id = payload.get("card", {}).get("id")
                if card_id:
                    e.zergboard_card_id = card_id
                    save_entry(e)
                    if e.publish_target:
                        subprocess.run(
                            ["python3", str(ZERGBOARD), "update", card_id, "--due", e.publish_target],
                            capture_output=True, text=True,
                        )
                    print(f"  create: {e.id} → card {card_id[:8]}")
                    created += 1
                continue

            # Existing card — push if vault newer
            card = full_cards[e.zergboard_card_id]
            card_state = _parse_fenced_state(card.get("description") or "")
            card_updated = _parse_iso8601((card_state or {}).get("updated_at", "")) or dt.datetime.fromtimestamp(0, dt.timezone.utc)
            vault_updated = _parse_iso8601(e.updated_at) or dt.datetime.fromtimestamp(0, dt.timezone.utc)

            if vault_updated <= card_updated:
                continue

            if dry_run:
                print(f"  push: {e.id} → card update")
                pushed += 1
                continue

            update_args = [
                "python3", str(ZERGBOARD), "update", e.zergboard_card_id,
                "--title", e.title,
                "--description", description_target,
                "--priority", priority,
            ]
            if e.publish_target:
                update_args += ["--due", e.publish_target]
            subprocess.run(update_args, capture_output=True, text=True)

            # Move column if needed
            current_col = card.get("column_name") or ""
            if current_col != target_column:
                subprocess.run(
                    ["python3", str(ZERGBOARD), "move", e.zergboard_card_id, "--column", target_column],
                    capture_output=True, text=True,
                )
            print(f"  push: {e.id} → card {e.zergboard_card_id[:8]}")
            pushed += 1

    rebuild_index()
    print(f"sync: {pushed} pushed, {pulled} pulled, {created} created, {conflicts} conflicts")
    if conflicts:
        print(f"  conflicts logged to {CONFLICTS_PATH}")


def _apply_state_to_entry(e: Entry, state: dict[str, Any], card_id: str) -> bool:
    """Mutate `e` in place based on parsed fenced-state. Return True if changed."""
    changed = False

    if "status" in state and state["status"] in VALID_STATUSES and state["status"] != e.status:
        e.status = state["status"]
        changed = True
    if "type" in state and state["type"] in VALID_TYPES and state["type"] != e.type:
        e.type = state["type"]
        changed = True
    if "publish_target" in state and state["publish_target"] != e.publish_target:
        e.publish_target = state["publish_target"]
        changed = True
    if "publish_actual" in state and state["publish_actual"] != e.publish_actual:
        e.publish_actual = state["publish_actual"]
        changed = True
    if "owner" in state and state["owner"] != e.owner:
        e.owner = state["owner"]
        changed = True
    new_gates = state.get("gates", {})
    valid_new = {k: v for k, v in new_gates.items() if v in VALID_GATE_VALUES}
    if valid_new != e.gates:
        e.gates = valid_new
        changed = True
    new_blockers = state.get("blockers", [])
    if new_blockers != e.blockers:
        e.blockers = new_blockers
        changed = True
    if e.zergboard_card_id != card_id:
        e.zergboard_card_id = card_id
        changed = True
    return changed


def _log_conflict(e: Entry, kind: str, vault_ts: str, card_ts: str) -> None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{now_iso()}\t{kind}\t{e.id}\tvault={vault_ts}\tcard={card_ts}\n"
    with CONFLICTS_PATH.open("a") as f:
        f.write(line)
