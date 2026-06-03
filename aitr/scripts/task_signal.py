"""Signal schema for aitr — what callers pass to `aitr pick`.

A signal describes a task that needs a model. The ranker takes (signal, catalog)
and returns a list of candidates ordered by composite fit score.

This module is pure: no I/O, no dependencies beyond stdlib. Tested independently
in tests/test_signal.py.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Tuple

TASK_KINDS: Tuple[str, ...] = (
    "code-review",
    "prose-review",
    "brainstorm",
    "draft-prose",
    "structured-extract",
    "sql",
    "image-gen",
    "summarize",
    "refute",
    "research",
    "classify",
)

QUALITY_FLOORS: Tuple[str, ...] = ("cheap-ok", "medium", "high-stakes")
PROVIDER_CONSTRAINTS: Tuple[str, ...] = ("any", "anthropic-only", "openai-only", "google-only")
MODALITIES: Tuple[str, ...] = ("vision", "tools", "extended-thinking", "audio")


class SignalError(ValueError):
    """Raised when a signal field is missing or invalid."""


@dataclass(frozen=True)
class Signal:
    task_kind: str
    caller: str
    artifact_size_tokens: int = 4000
    latency_budget_seconds: Optional[int] = None
    cost_budget_usd: Optional[float] = None
    quality_floor: str = "medium"
    provider_constraint: str = "any"
    modality_required: Optional[str] = None
    # Free-form context for the decision log. Not used by the ranker.
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.task_kind:
            raise SignalError("task_kind is required")
        if self.task_kind not in TASK_KINDS:
            raise SignalError(
                f"unknown task_kind: {self.task_kind!r} (expected one of {TASK_KINDS})"
            )
        if not self.caller:
            raise SignalError("caller is required")
        if self.artifact_size_tokens < 0:
            raise SignalError("artifact_size_tokens must be >= 0")
        if self.latency_budget_seconds is not None and self.latency_budget_seconds <= 0:
            raise SignalError("latency_budget_seconds must be > 0 if set")
        if self.cost_budget_usd is not None and self.cost_budget_usd < 0:
            raise SignalError("cost_budget_usd must be >= 0 if set")
        if self.quality_floor not in QUALITY_FLOORS:
            raise SignalError(
                f"unknown quality_floor: {self.quality_floor!r} (expected one of {QUALITY_FLOORS})"
            )
        if self.provider_constraint not in PROVIDER_CONSTRAINTS:
            raise SignalError(
                f"unknown provider_constraint: {self.provider_constraint!r} (expected one of {PROVIDER_CONSTRAINTS})"
            )
        if self.modality_required is not None and self.modality_required not in MODALITIES:
            raise SignalError(
                f"unknown modality_required: {self.modality_required!r} (expected one of {MODALITIES})"
            )

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


def parse_kv_args(pairs: list[str]) -> dict:
    """Parse `key=value` CLI args into a dict. Values are kept as strings;
    the typed converters below cast them. Empty `pairs` returns {}."""
    out: dict = {}
    for raw in pairs:
        if "=" not in raw:
            raise SignalError(f"expected key=value, got {raw!r}")
        key, _, val = raw.partition("=")
        key = key.strip()
        val = val.strip()
        if not key:
            raise SignalError(f"empty key in {raw!r}")
        out[key] = val
    return out


def _coerce_int(field_name: str, raw: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise SignalError(f"{field_name} must be an integer, got {raw!r}") from exc


def _coerce_float(field_name: str, raw: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise SignalError(f"{field_name} must be a number, got {raw!r}") from exc


def signal_from_kv(kv: dict) -> Signal:
    """Build a Signal from a dict of string-valued fields (as produced by
    parse_kv_args). Unknown keys raise."""
    known = {
        "task_kind",
        "caller",
        "artifact_size_tokens",
        "latency_budget_seconds",
        "cost_budget_usd",
        "quality_floor",
        "provider_constraint",
        "modality_required",
        "notes",
    }
    unknown = set(kv.keys()) - known
    if unknown:
        raise SignalError(f"unknown signal fields: {sorted(unknown)}")

    return Signal(
        task_kind=kv.get("task_kind", ""),
        caller=kv.get("caller", ""),
        artifact_size_tokens=_coerce_int(
            "artifact_size_tokens", kv.get("artifact_size_tokens", "4000")
        ),
        latency_budget_seconds=(
            _coerce_int("latency_budget_seconds", kv["latency_budget_seconds"])
            if "latency_budget_seconds" in kv and kv["latency_budget_seconds"] != ""
            else None
        ),
        cost_budget_usd=(
            _coerce_float("cost_budget_usd", kv["cost_budget_usd"])
            if "cost_budget_usd" in kv and kv["cost_budget_usd"] != ""
            else None
        ),
        quality_floor=kv.get("quality_floor", "medium"),
        provider_constraint=kv.get("provider_constraint", "any"),
        modality_required=kv.get("modality_required") or None,
        notes=kv.get("notes") or None,
    )


def signal_from_json(payload: str) -> Signal:
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SignalError(f"invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise SignalError("signal JSON must be an object")
    # JSON already carries native types; pass through as a kv dict-of-strings
    # via signal_from_kv would coerce strings only — instead build directly.
    if "task_kind" not in obj:
        raise SignalError("task_kind is required")
    if "caller" not in obj:
        raise SignalError("caller is required")
    return Signal(
        task_kind=obj["task_kind"],
        caller=obj["caller"],
        artifact_size_tokens=int(obj.get("artifact_size_tokens", 4000)),
        latency_budget_seconds=obj.get("latency_budget_seconds"),
        cost_budget_usd=obj.get("cost_budget_usd"),
        quality_floor=obj.get("quality_floor", "medium"),
        provider_constraint=obj.get("provider_constraint", "any"),
        modality_required=obj.get("modality_required"),
        notes=obj.get("notes"),
    )
