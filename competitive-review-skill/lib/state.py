"""Per-category state file. Phases read/mutate/write so each can run independently."""

from __future__ import annotations

import json
from pathlib import Path

from . import vault

STATE_DIR = Path(__file__).resolve().parent.parent / "insights" / "state"


def state_path(category: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / f"{vault.slugify(category)}.json"


def load(category: str) -> dict:
    p = state_path(category)
    if not p.exists():
        return {"category": vault.slugify(category)}
    return json.loads(p.read_text(encoding="utf-8"))


def save(category: str, state: dict) -> Path:
    p = state_path(category)
    p.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    return p


def update(category: str, **fields) -> dict:
    state = load(category)
    state.update(fields)
    save(category, state)
    return state
