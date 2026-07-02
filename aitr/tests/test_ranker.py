"""Tests for the pure ranking function."""
import json
from pathlib import Path

import pytest

from ranker import (
    Candidate,
    RankerError,
    _jaccard,
    capability_score,
    cost_score,
    estimated_cost_usd,
    latency_score,
    rank,
)


SNAPSHOT = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "snapshot" / "search.json").read_text()
)
ROUTING_TABLE = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "routing_table.json").read_text()
)


def make_signal(**kwargs) -> dict:
    base = {
        "task_kind": "code-review",
        "caller": "test",
        "artifact_size_tokens": 4000,
        "quality_floor": "medium",
        "provider_constraint": "any",
    }
    base.update(kwargs)
    return base


# ---- Helper-function tests --------------------------------------------------

class TestJaccard:
    def test_basic_overlap(self):
        assert _jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)

    def test_full_overlap(self):
        assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint(self):
        assert _jaccard({"a"}, {"b"}) == 0.0

    def test_empty_both(self):
        assert _jaccard(set(), set()) == 0.0


class TestEstimatedCost:
    def test_haiku_cheap(self):
        m = next(m for m in SNAPSHOT["models"] if m["id"] == "anthropic__claude-haiku-4-5")
        cost = estimated_cost_usd(m, 4000)
        # 4000 * 1/1e6 + 2000 * 5/1e6 = 0.004 + 0.01 = 0.014
        assert cost == pytest.approx(0.014, rel=1e-3)

    def test_opus_expensive(self):
        m = next(m for m in SNAPSHOT["models"] if m["id"] == "anthropic__claude-opus-4-7")
        cost = estimated_cost_usd(m, 4000)
        # Current tracker pricing: $5/$25 per Mtok →
        # 4000 * 5/1e6 + 2000 * 25/1e6 = 0.02 + 0.05 = 0.07
        assert cost == pytest.approx(0.07, rel=1e-3)
        # The relative claim that actually matters: opus costs more than haiku
        haiku = next(m for m in SNAPSHOT["models"] if m["id"] == "anthropic__claude-haiku-4-5")
        assert cost > estimated_cost_usd(haiku, 4000)


class TestCostScore:
    def test_within_budget(self):
        # cost=0.05, budget=0.10 → score = 1 - 0.5 = 0.5
        assert cost_score(0.05, 0.10, cheapest_cost=0.01) == pytest.approx(0.5)

    def test_over_budget(self):
        assert cost_score(0.20, 0.10, cheapest_cost=0.01) == 0.0

    def test_no_budget_uses_ratio(self):
        # cheapest=0.01, candidate=0.05 → score = 0.01/0.05 = 0.2
        assert cost_score(0.05, None, cheapest_cost=0.01) == pytest.approx(0.2)

    def test_zero_cost(self):
        assert cost_score(0, None, cheapest_cost=0.01) == 1.0


class TestLatencyScore:
    def test_fast_tags_high_score(self):
        m = {"tags": ["fast", "small-model"]}
        assert latency_score(m, "fast", None) >= 0.9

    def test_extended_thinking_low(self):
        m = {"tags": ["extended-thinking", "reasoning"]}
        assert latency_score(m, "medium", None) <= 0.5

    def test_tight_budget_penalizes_slow(self):
        m = {"tags": ["extended-thinking"]}
        # 5-second budget + slow tags → hard penalty
        assert latency_score(m, "fast", 5) == 0.0


class TestCapabilityScore:
    def test_full_tag_overlap(self):
        m = {"tags": ["code", "reasoning", "extended-thinking"]}
        rules = {"preferred_tags": ["code", "reasoning", "extended-thinking"]}
        assert capability_score(m, rules) == 1.0

    def test_no_overlap(self):
        m = {"tags": ["image"]}
        rules = {"preferred_tags": ["code"]}
        assert capability_score(m, rules) == 0.0

    def test_benchmark_boost(self):
        m = {"tags": ["code"], "benchmarks": {"humaneval": 0.95}}
        rules = {"preferred_tags": ["code", "reasoning"], "benchmark_key": "humaneval"}
        # base = 1/2 = 0.5; blended = 0.5*0.5 + 0.5*0.95 = 0.725 (50/50 tag/benchmark)
        assert capability_score(m, rules) == pytest.approx(0.725)

    def test_benchmark_profile_weighted_average(self):
        # Multi-benchmark profile: weighted avg of the scores the model publishes.
        m = {"tags": ["code"], "benchmarks": {"swe_bench_verified": 0.9, "terminal_bench": 0.5}}
        rules = {"preferred_tags": ["code"], "benchmark_profile": {"swe_bench_verified": 0.5, "terminal_bench": 0.5}}
        # base = jaccard({code},{code}) = 1.0; bench = (0.9+0.5)/2 = 0.7
        # blended = 0.5*1.0 + 0.5*0.7 = 0.85
        assert capability_score(m, rules) == pytest.approx(0.85)

    def test_profile_falls_back_to_tags_when_no_benchmarks(self):
        m = {"tags": ["code"], "benchmarks": {}}
        rules = {"preferred_tags": ["code", "reasoning"], "benchmark_profile": {"swe_bench_verified": 1.0}}
        # No profile benchmark present → tag-only, no penalty
        assert capability_score(m, rules) == pytest.approx(0.5)

    def test_elo_normalized_against_catalog(self):
        # Arena Elo (>1) normalized via min-max range; 1500 with range (1400,1500) → 1.0
        m = {"tags": [], "benchmarks": {"arena_elo": 1500}}
        rules = {"preferred_tags": [], "benchmark_profile": {"arena_elo": 1.0}}
        norm = {"arena_elo": (1400.0, 1500.0)}
        # base = 0 (no tags); bench = 1.0; blended = 0.5*0 + 0.5*1.0 = 0.5
        assert capability_score(m, rules, benchmark_norm=norm) == pytest.approx(0.5)


# ---- End-to-end rank() tests against the bundled snapshot ------------------

class TestRankCodeReview:
    def test_high_stakes_prefers_opus_or_gpt55pro(self):
        sig = make_signal(task_kind="code-review", quality_floor="high-stakes",
                          artifact_size_tokens=8000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE)
        assert out[0].model_class in {"opus", "gpt-5.5-pro"}

    def test_cheap_ok_prefers_cost_efficient_capable_model(self):
        # Quality-led code-review (capability-weighted, benchmark-grounded) doesn't
        # force a tiny model at cheap-ok — but relaxing the floor must admit a
        # cheaper pick than high-stakes does. The real invariant: cheap-ok's
        # winner costs <= the high-stakes winner (a cost-efficient yet capable
        # model like deepseek-v4 wins, not the frontier whitelist lock).
        cheap = rank(make_signal(task_kind="code-review", quality_floor="cheap-ok"),
                     SNAPSHOT, ROUTING_TABLE)
        hs = rank(make_signal(task_kind="code-review", quality_floor="high-stakes"),
                  SNAPSHOT, ROUTING_TABLE)
        assert cheap[0].estimated_cost_usd <= hs[0].estimated_cost_usd
        # And the cheap-ok winner is still genuinely capable (benchmark-backed)
        assert cheap[0].capability >= 0.5


class TestRankProseReview:
    def test_prefers_anthropic_writing_models(self):
        # High-stakes prose review (what fakematt-copyedit actually sends) must go
        # to an Anthropic voice model. At medium floor the router may legitimately
        # cost-optimize to a cheaper writing-capable model (e.g. Gemini 3.5 Flash)
        # — that behavior is covered by the golden routing suite instead.
        sig = make_signal(task_kind="prose-review", quality_floor="high-stakes",
                          artifact_size_tokens=8000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE)
        assert out[0].provider == "anthropic"

    def test_anthropic_only_constraint_picks_voice_model(self):
        sig = make_signal(task_kind="prose-review", quality_floor="medium",
                          artifact_size_tokens=8000, provider_constraint="anthropic-only")
        out = rank(sig, SNAPSHOT, ROUTING_TABLE)
        # Within Anthropic, the voice-tagged models (opus/sonnet) must beat haiku
        assert out[0].model_class in ("opus", "sonnet")


class TestRankStructuredExtract:
    def test_prefers_fast_small_models(self):
        sig = make_signal(task_kind="structured-extract", quality_floor="cheap-ok",
                          artifact_size_tokens=2000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE)
        # Top model should be tagged fast or small-model
        top_model = next(m for m in SNAPSHOT["models"] if m["id"] == out[0].model)
        assert any(t in (top_model.get("tags") or []) for t in ("fast", "small-model"))


class TestRankRefute:
    def test_opposite_provider_filters_active(self):
        sig = make_signal(task_kind="refute", quality_floor="high-stakes",
                          artifact_size_tokens=4000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE, active_provider="anthropic")
        for c in out:
            assert c.provider != "anthropic"

    def test_opposite_provider_no_active_no_filter(self):
        sig = make_signal(task_kind="refute", quality_floor="high-stakes",
                          artifact_size_tokens=4000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE, active_provider=None)
        # Without an active provider, no provider filter is applied.
        assert len(out) >= 1


class TestRankHardFilters:
    def test_modality_required_filters(self):
        sig = make_signal(task_kind="prose-review", modality_required="vision",
                          artifact_size_tokens=4000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE)
        for c in out:
            model = next(m for m in SNAPSHOT["models"] if m["id"] == c.model)
            assert "vision" in (model.get("modalities") or [])

    def test_provider_constraint_filters(self):
        sig = make_signal(task_kind="code-review", provider_constraint="openai-only",
                          artifact_size_tokens=4000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE)
        assert all(c.provider == "openai" for c in out)

    def test_artifact_too_large_filters_models(self):
        sig = make_signal(task_kind="research", artifact_size_tokens=150000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE)
        # All survivors must have context_window >= 150k * 1.3 = 195k
        for c in out:
            assert c.context_window >= 195000

    def test_raises_when_no_candidate_survives(self):
        sig = make_signal(task_kind="image-gen", modality_required="audio")
        # No model in snapshot has audio modality
        with pytest.raises(RankerError):
            rank(sig, SNAPSHOT, ROUTING_TABLE)


class TestRankQualityFloor:
    def test_high_stakes_whitelist_bypass(self):
        # High-stakes whitelist allows opus even when capability score is low.
        sig = make_signal(task_kind="sql", quality_floor="high-stakes",
                          artifact_size_tokens=4000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE, top_n=50)
        # Opus doesn't have "sql" tag but should be in results via whitelist
        assert any("opus" in c.model for c in out)


class TestHighStakesWhitelistRestriction:
    """2026-06-03 decision: high-stakes is whitelist-FIRST. When whitelisted-class
    models survive hard filters, only they compete — cheap perfect-tag-fit models
    can't win high-stakes work on cost."""

    def test_unconstrained_high_stakes_excludes_non_whitelisted(self):
        whitelist = set(ROUTING_TABLE["high_stakes_whitelist"])
        sig = make_signal(task_kind="brainstorm", quality_floor="high-stakes",
                          artifact_size_tokens=12000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE, top_n=50)
        # Every candidate must be a whitelisted class — deepseek-r1 (perfect
        # reasoning tag fit, cheap) must NOT appear.
        assert out, "high-stakes brainstorm must produce candidates"
        for c in out:
            assert c.model_class in whitelist, f"{c.model} ({c.model_class}) not whitelisted"

    def test_high_stakes_winner_is_frontier_class(self):
        sig = make_signal(task_kind="brainstorm", quality_floor="high-stakes",
                          artifact_size_tokens=12000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE)
        assert out[0].model_class in ("opus", "gpt-5.5-pro")

    def test_constraint_excluding_whitelist_falls_back(self):
        # google-only excludes every whitelisted class (opus/gpt-5.5-pro are
        # anthropic/openai). The restriction must NOT fire — the open field
        # competes, and whether anything clears the capability floor is up to
        # the normal floor logic.
        sig = make_signal(task_kind="summarize", quality_floor="high-stakes",
                          provider_constraint="google-only",
                          artifact_size_tokens=4000)
        try:
            out = rank(sig, SNAPSHOT, ROUTING_TABLE, top_n=50)
            # If candidates exist, none can be whitelisted (google has none) —
            # proving the fallback path ran rather than erroring on the restriction.
            whitelist = set(ROUTING_TABLE["high_stakes_whitelist"])
            for c in out:
                assert c.model_class not in whitelist
        except RankerError:
            # Acceptable: no google model clears the high-stakes capability floor.
            # The point is the restriction itself didn't preempt the attempt.
            pass

    def test_medium_floor_unaffected_by_whitelist(self):
        # The restriction only applies at high-stakes; medium keeps the open field.
        sig = make_signal(task_kind="summarize", quality_floor="medium",
                          artifact_size_tokens=4000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE, top_n=50)
        whitelist = set(ROUTING_TABLE["high_stakes_whitelist"])
        assert any(c.model_class not in whitelist for c in out)


class TestRankBenchmarks:
    def test_benchmark_boost_promotes_strong_swe_bench(self):
        # routing_table's code-review benchmark_key is swe_bench_verified (the key
        # the ai-tracker catalog publishes). The top code-review pick must be a
        # model with a real published SWE-bench Verified score.
        sig = make_signal(task_kind="code-review", quality_floor="medium",
                          artifact_size_tokens=4000)
        out = rank(sig, SNAPSHOT, ROUTING_TABLE)
        top_model = next(m for m in SNAPSHOT["models"] if m["id"] == out[0].model)
        assert (top_model.get("benchmarks") or {}).get("swe_bench_verified", 0) >= 0.5
