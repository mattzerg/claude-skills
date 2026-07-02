"""aitr-routed model resolution for idea-backlog scripts.

LLM calls route through aitr (the internal model router) with a loud fallback to
the script's previous hardcoded default. Resolution is lazy + memoized so
--dry-run paths never log a phantom routing decision, and each script makes at
most one routing call per (task_kind, caller, floor).
"""
from __future__ import annotations

import sys
from pathlib import Path

FALLBACK_MODEL = "claude-sonnet-4-5"

_AITR_SCRIPTS = Path.home() / ".claude" / "skills" / "aitr" / "scripts"
_cache: dict = {}


def routed_model(
    task_kind: str,
    caller: str,
    *,
    quality_floor: str = "cheap-ok",
    fallback: str = FALLBACK_MODEL,
) -> str:
    """Return the aitr-picked claude model name for this task, or `fallback` loudly."""
    key = (task_kind, caller, quality_floor)
    if key in _cache:
        return _cache[key]
    if str(_AITR_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_AITR_SCRIPTS))
    try:
        from skill_default import aitr_model_or  # noqa: PLC0415 — lazy by design
        model = aitr_model_or(
            fallback,
            task_kind=task_kind,
            caller=caller,
            quality_floor=quality_floor,
        )
    except ImportError:
        print(f"[aitr] skill_default unavailable — using fallback {fallback}", file=sys.stderr)
        model = fallback
    _cache[key] = model
    return model
