"""Production-caller routing locks.

The 9 skill scripts wired to aitr (2026-06-03/04) each send a fixed signal. A
catalog refresh or routing_table edit must not silently send a cheap batch task
to a frontier model, or downgrade high-stakes prose off Opus. These are HARD
assertions (not the threshold-based golden suite) so any single regression fails
the build.

Each caller executes via Max-plan OAuth through the claude CLI, so all signals
carry provider_constraint=anthropic-only — the universe here is opus/sonnet/haiku.
"""
import json
from pathlib import Path

import pytest

from ranker import rank

SNAPSHOT = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "snapshot" / "search.json").read_text()
)
ROUTING_TABLE = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "routing_table.json").read_text()
)


def _pick_class(task_kind, caller, quality_floor, modality=None, artifact=4000):
    sig = {
        "task_kind": task_kind,
        "caller": caller,
        "quality_floor": quality_floor,
        "provider_constraint": "anthropic-only",
        "artifact_size_tokens": artifact,
        "billing_mode": "flat",
    }
    if modality:
        sig["modality_required"] = modality
    out = rank(sig, SNAPSHOT, ROUTING_TABLE, top_n=3)
    return out[0].model_class, [c.model_class for c in out]


# (task_kind, caller, floor, modality, allowed_top_classes)
# allowed = the set of classes whose selection as #1 is acceptable. A cheap task
# resolving to "opus" — or a high-stakes draft resolving to "haiku" — fails.
ADOPTED = [
    ("structured-extract", "idea-backlog-extract", "cheap-ok", None, {"haiku", "sonnet"}),
    ("classify", "idea-backlog-score", "cheap-ok", None, {"haiku", "sonnet"}),
    ("classify", "idea-backlog-recategorize", "cheap-ok", None, {"haiku", "sonnet"}),
    ("classify", "fakematt-operator-intake", "medium", None, {"haiku", "sonnet"}),
    ("draft-prose", "fakematt-operator-intake", "medium", None, {"sonnet", "opus"}),
    ("classify", "fakematt-today-calibrate", "medium", None, {"haiku", "sonnet"}),
    ("draft-prose", "case-study-skill", "high-stakes", None, {"opus"}),
    ("draft-prose", "launch-announcement", "high-stakes", None, {"opus"}),
    ("research", "competitive-review-skill", "medium", None, {"opus", "sonnet"}),
    ("prose-review", "webpage-layout", "medium", "vision", {"sonnet", "opus"}),
    # Second adoption tier (2026-06-04)
    ("draft-prose", "one-pager-skill", "high-stakes", None, {"opus"}),
    ("prose-review", "fakeidan", "high-stakes", None, {"opus"}),
    ("code-review", "fakeidan", "high-stakes", None, {"opus"}),
    ("prose-review", "fakematt-feedback", "medium", "vision", {"sonnet", "opus"}),
    ("prose-review", "landing-page-analyze", "medium", "vision", {"sonnet", "opus"}),
    ("prose-review", "landing-page-audit", "medium", None, {"sonnet", "opus"}),
    ("draft-prose", "landing-page-build", "medium", None, {"sonnet", "opus"}),
]


@pytest.mark.parametrize(
    "task_kind,caller,floor,modality,allowed",
    ADOPTED,
    ids=[f"{c[1]}:{c[0]}" for c in ADOPTED],
)
def test_adopted_caller_stays_in_band(task_kind, caller, floor, modality, allowed):
    top, top3 = _pick_class(task_kind, caller, floor, modality)
    assert top in allowed, (
        f"{caller} ({task_kind}/{floor}) picked {top!r}; expected one of {sorted(allowed)}. "
        f"top-3: {top3}"
    )


def test_cheap_callers_never_pick_frontier():
    """The bright-line invariant: no cheap-ok / classify batch caller may resolve
    to opus as its top pick — that's the regression billing-mode work guards against."""
    cheap = [(c[0], c[1], c[2], c[3]) for c in ADOPTED if c[2] == "cheap-ok"]
    for task_kind, caller, floor, modality in cheap:
        top, top3 = _pick_class(task_kind, caller, floor, modality)
        assert top != "opus", f"{caller} cheap task escalated to opus! top-3: {top3}"


def test_high_stakes_prose_stays_opus():
    for task_kind, caller, floor, modality, allowed in ADOPTED:
        if floor == "high-stakes" and task_kind == "draft-prose":
            top, _ = _pick_class(task_kind, caller, floor, modality)
            assert top == "opus", f"{caller} high-stakes prose downgraded off opus to {top!r}"


def test_vision_caller_keeps_vision_model():
    # webpage-layout needs vision; the pick must be a model that has the modality
    sig_class, _ = _pick_class("prose-review", "webpage-layout", "medium", "vision")
    record = next(m for m in SNAPSHOT["models"] if m["model_class"] == sig_class and m["status"] == "ga")
    assert "vision" in (record.get("modalities") or [])
