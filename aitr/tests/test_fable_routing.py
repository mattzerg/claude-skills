"""Claude Fable 5 routing mechanics — token_multiplier, refusal_risk, whitelist.

Locks the 2026-06-10 catalog addition: Fable 5 is high-stakes-eligible but must
not displace Opus by default (no published benchmarks yet, ~2.6x effective
cost), must carry its tokenizer inflation in cost estimates, and must be
penalized away from security/bio-adjacent tasks its classifiers may refuse.
"""
import json
from pathlib import Path

import pytest

from ranker import (
    REFUSAL_RISK_PENALTY,
    estimated_cost_usd,
    rank,
    refusal_risk_penalty,
)

SNAPSHOT = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "snapshot" / "search.json").read_text()
)
ROUTING_TABLE = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "routing_table.json").read_text()
)


def _model(model_id: str) -> dict:
    return next(m for m in SNAPSHOT["models"] if m["id"] == model_id)


FABLE = "anthropic__claude-fable-5"
OPUS = "anthropic__claude-opus-4-8"


# ---- catalog shape -----------------------------------------------------------


def test_fable_present_and_ga():
    m = _model(FABLE)
    assert m["status"] == "ga"
    assert m["model_class"] == "fable"
    assert m["context_window"] == 1_000_000
    assert m["pricing"]["input_per_mtok"] == 10
    assert m["pricing"]["output_per_mtok"] == 50


def test_fable_in_high_stakes_whitelist():
    assert "fable" in ROUTING_TABLE["high_stakes_whitelist"]


# ---- token_multiplier --------------------------------------------------------


def test_token_multiplier_inflates_estimated_cost():
    plain = {"pricing": {"input_per_mtok": 10, "output_per_mtok": 50}}
    inflated = dict(plain, token_multiplier=1.3)
    base = estimated_cost_usd(plain, 10_000)
    assert estimated_cost_usd(inflated, 10_000) == pytest.approx(1.3 * base)


def test_missing_multiplier_defaults_to_one():
    m = {"pricing": {"input_per_mtok": 5, "output_per_mtok": 25}}
    assert estimated_cost_usd(m, 10_000) == pytest.approx(
        (10_000 * 5 + 2000 * 25) / 1_000_000
    )


def test_fable_snapshot_entry_carries_multiplier():
    assert _model(FABLE)["token_multiplier"] == pytest.approx(1.3)
    # Fable's effective cost must exceed Opus by more than the sticker 2x.
    fable_cost = estimated_cost_usd(_model(FABLE), 10_000)
    opus_cost = estimated_cost_usd(_model(OPUS), 10_000)
    assert fable_cost / opus_cost == pytest.approx(2.6, rel=0.01)


# ---- refusal_risk ------------------------------------------------------------


def test_refusal_risk_matches_security_notes():
    pen, domain = refusal_risk_penalty(
        _model(FABLE), {"notes": "Security review of the auth diff for vulns"}
    )
    assert pen == REFUSAL_RISK_PENALTY
    assert domain == "cyber"


def test_refusal_risk_ignores_benign_notes():
    pen, _ = refusal_risk_penalty(_model(FABLE), {"notes": "copyedit the launch post"})
    assert pen == 0.0


def test_refusal_risk_noop_without_field():
    pen, _ = refusal_risk_penalty(_model(OPUS), {"notes": "security review"})
    assert pen == 0.0


def test_security_noted_review_ranks_opus_above_fable():
    sig = {
        "task_kind": "code-review",
        "caller": "pr-gate",
        "quality_floor": "high-stakes",
        "artifact_size_tokens": 8000,
        "provider_constraint": "anthropic-only",
        "notes": "security review: check the session-token handling for vulns",
    }
    out = rank(sig, SNAPSHOT, ROUTING_TABLE)
    ranking = [c.model for c in out]
    assert out[0].model_class != "fable"
    if FABLE in ranking:
        assert ranking.index(OPUS) < ranking.index(FABLE)


# ---- whitelist eligibility -----------------------------------------------------


def test_fable_survives_high_stakes_whitelist_filter():
    """Fable competes at high-stakes (whitelist-first keeps it in the pool)."""
    sig = {
        "task_kind": "code-review",
        "caller": "pr-gate",
        "quality_floor": "high-stakes",
        "artifact_size_tokens": 8000,
        "provider_constraint": "anthropic-only",
    }
    out = rank(sig, SNAPSHOT, ROUTING_TABLE, top_n=10)
    assert FABLE in [c.model for c in out]


def test_fable_does_not_win_metered_medium_task():
    """At medium floor with a cost budget, Fable's 2.6x effective cost must
    keep it off the top — the cheap-capable field wins."""
    sig = {
        "task_kind": "draft-prose",
        "caller": "fakematt-slack",
        "quality_floor": "medium",
        "artifact_size_tokens": 2000,
        "cost_budget_usd": 0.05,
    }
    out = rank(sig, SNAPSHOT, ROUTING_TABLE)
    assert out[0].model_class != "fable"


def test_fable_wins_flat_high_stakes_once_benchmarks_publish():
    """Forward-lock: when Anthropic publishes evals above Opus levels, Fable
    becomes the legitimate top pick at high-stakes for FLAT-billing
    anthropic-only callers (cost deweighted — subscription marginal cost ~$0).
    Metered callers keep the cost term, where Fable's 2.6x keeps Opus on top."""
    catalog = json.loads(json.dumps(SNAPSHOT))  # deep copy
    for m in catalog["models"]:
        if m["id"] == FABLE:
            m["benchmarks"] = {
                "swe_bench_verified": 0.92,
                "swe_bench_pro": 0.75,
                "terminal_bench": 0.80,
            }
    sig = {
        "task_kind": "code-review",
        "caller": "pr-gate",
        "quality_floor": "high-stakes",
        "artifact_size_tokens": 8000,
        "provider_constraint": "anthropic-only",
        "billing_mode": "flat",
    }
    out = rank(sig, catalog, ROUTING_TABLE)
    assert out[0].model == FABLE

    # Same signal but metered: cost term active, Opus stays on top.
    sig_metered = dict(sig, billing_mode="metered")
    out_metered = rank(sig_metered, catalog, ROUTING_TABLE)
    assert out_metered[0].model == OPUS


def test_flat_billing_without_benchmarks_keeps_opus_on_top():
    """Today (no Fable benchmarks): even with cost deweighted, Opus's benchmark
    profile beats Fable's tag-only capability — no accidental upgrade."""
    sig = {
        "task_kind": "code-review",
        "caller": "pr-gate",
        "quality_floor": "high-stakes",
        "artifact_size_tokens": 8000,
        "provider_constraint": "anthropic-only",
        "billing_mode": "flat",
    }
    out = rank(sig, SNAPSHOT, ROUTING_TABLE)
    assert out[0].model_class == "opus"
