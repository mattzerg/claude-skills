"""Tests for baseline + savings tracking (pick.py + weekly_report.py).

The baseline is the model every task would run on if aitr didn't exist
(default: anthropic__claude-opus-4-8). Every pick records what that task would
have cost on the baseline; weekly_report.py aggregates the delta.
"""
import json
from pathlib import Path

import pytest

from pick import DEFAULT_BASELINE_MODEL, compute_baseline, resolve_baseline_model
from weekly_report import build_report, compute_savings


SNAPSHOT = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "snapshot" / "search.json").read_text()
)


def _opus_record() -> dict:
    return next(m for m in SNAPSHOT["models"] if m["id"] == DEFAULT_BASELINE_MODEL)


class TestComputeBaseline:
    def test_default_baseline_found_in_catalog(self):
        out = compute_baseline(SNAPSHOT, {"artifact_size_tokens": 4000})
        assert out["baseline_model"] == DEFAULT_BASELINE_MODEL
        # Opus 4.8 at $5/$25: 4000*5/1e6 + 2000*25/1e6 = 0.02 + 0.05 = 0.07
        assert out["baseline_cost_usd"] == pytest.approx(0.07, rel=1e-3)

    def test_scales_with_artifact_size(self):
        small = compute_baseline(SNAPSHOT, {"artifact_size_tokens": 1000})
        large = compute_baseline(SNAPSHOT, {"artifact_size_tokens": 100_000})
        assert large["baseline_cost_usd"] > small["baseline_cost_usd"]

    def test_missing_baseline_model_returns_empty(self):
        catalog = {"models": [{"id": "some__other-model", "pricing": {"input_per_mtok": 1, "output_per_mtok": 2}}]}
        assert compute_baseline(catalog, {"artifact_size_tokens": 4000}) == {}

    def test_resolve_baseline_model_has_default(self):
        # Config may override, but the resolved value is always a non-empty string
        assert resolve_baseline_model()


class TestComputeSavings:
    def _native_decision(self, actual: float, baseline: float) -> dict:
        return {
            "model": "anthropic__claude-sonnet-4-6",
            "estimated_cost_usd": actual,
            "baseline_model": DEFAULT_BASELINE_MODEL,
            "baseline_cost_usd": baseline,
            "savings_usd": round(baseline - actual, 5),
            "signal": {"artifact_size_tokens": 4000},
        }

    def _legacy_decision(self, actual: float, artifact: int = 4000) -> dict:
        # Pre-2026-06-03 records: no baseline fields
        return {
            "model": "anthropic__claude-sonnet-4-6",
            "estimated_cost_usd": actual,
            "signal": {"artifact_size_tokens": artifact},
        }

    def test_native_records_summed(self):
        decisions = [self._native_decision(0.02, 0.07), self._native_decision(0.01, 0.07)]
        out = compute_savings(decisions, catalog_body=SNAPSHOT)
        assert out["native_count"] == 2
        assert out["retro_count"] == 0
        assert out["total_savings_usd"] == pytest.approx(0.05 + 0.06)

    def test_legacy_records_recomputed_at_current_pricing(self):
        # Legacy sonnet pick: BOTH sides recomputed at current pricing —
        # sonnet (3/15): 4000*3/1e6 + 2000*15/1e6 = 0.042
        # opus baseline (5/25): 0.07 → savings = 0.028
        # (The recorded 0.02 is ignored: legacy costs reflect stale snapshot pricing.)
        decisions = [self._legacy_decision(0.02)]
        out = compute_savings(decisions, catalog_body=SNAPSHOT)
        assert out["retro_count"] == 1
        assert out["total_savings_usd"] == pytest.approx(0.07 - 0.042, rel=1e-3)

    def test_legacy_pick_of_baseline_model_is_zero_savings(self):
        # Picking the baseline model itself = no savings by definition, even when the
        # legacy record carries an inflated cost from the stale-pricing era.
        decisions = [{
            "model": DEFAULT_BASELINE_MODEL,
            "estimated_cost_usd": 0.21,  # stale-era inflated cost
            "signal": {"artifact_size_tokens": 4000},
        }]
        out = compute_savings(decisions, catalog_body=SNAPSHOT)
        assert out["retro_count"] == 1
        assert out["total_savings_usd"] == pytest.approx(0.0, abs=1e-9)

    def test_mixed_native_and_legacy(self):
        decisions = [self._native_decision(0.02, 0.07), self._legacy_decision(0.02)]
        out = compute_savings(decisions, catalog_body=SNAPSHOT)
        assert out["native_count"] == 1
        assert out["retro_count"] == 1
        # native 0.05 + legacy retro (0.07 - 0.042) = 0.078
        assert out["total_savings_usd"] == pytest.approx(0.05 + 0.028, rel=1e-3)

    def test_negative_savings_allowed(self):
        # The router may pick something pricier than baseline for quality reasons
        decisions = [self._native_decision(0.20, 0.07)]
        out = compute_savings(decisions, catalog_body=SNAPSHOT)
        assert out["total_savings_usd"] == pytest.approx(-0.13)

    def test_delegations_ignored(self):
        decisions = [{"verb": "delegate", "delegate_to": "image-skill", "signal": {}}]
        out = compute_savings(decisions, catalog_body=SNAPSHOT)
        assert out["native_count"] == 0
        assert out["retro_count"] == 0
        assert out["total_spend_usd"] == 0.0

    def test_no_catalog_marks_legacy_uncounted(self):
        decisions = [self._legacy_decision(0.02)]
        out = compute_savings(decisions, catalog_body=None)
        assert out["retro_count"] == 0
        assert out["uncounted"] == 1

    def _metered(self, actual, baseline):
        d = self._native_decision(actual, baseline)
        d["signal"]["billing_mode"] = "metered"
        return d

    def _flat(self, actual, baseline):
        d = self._native_decision(actual, baseline)
        d["signal"]["billing_mode"] = "flat"
        return d

    def test_only_metered_savings_count_as_dollars(self):
        # One metered pick (real $0.05 saved) + one flat pick (also nominally
        # $0.05 but $0 marginal on Max-OAuth) → real dollar savings = 0.05 only.
        decisions = [self._metered(0.02, 0.07), self._flat(0.02, 0.07)]
        out = compute_savings(decisions, catalog_body=SNAPSHOT)
        assert out["metered_count"] == 1
        assert out["flat_count"] == 1
        assert out["metered_savings_usd"] == pytest.approx(0.05)
        # Notional total still sums both (for reference), but it's not the headline
        assert out["total_savings_usd"] == pytest.approx(0.10)

    def test_all_flat_means_zero_real_dollars(self):
        decisions = [self._flat(0.02, 0.07), self._flat(0.01, 0.07)]
        out = compute_savings(decisions, catalog_body=SNAPSHOT)
        assert out["metered_savings_usd"] == 0.0
        assert out["flat_count"] == 2
        assert out["metered_count"] == 0

    def test_untagged_records_count_as_unknown(self):
        decisions = [self._native_decision(0.02, 0.07)]  # no billing_mode in signal
        out = compute_savings(decisions, catalog_body=SNAPSHOT)
        assert out["unknown_count"] == 1
        assert out["metered_savings_usd"] == 0.0


class TestReportRendersSavings:
    def test_savings_section_in_report(self, tmp_path):
        # Build a minimal decisions log with one native + one legacy record
        log = tmp_path / "decisions.log"
        records = [
            {
                "decision_id": "aitr-test-1",
                "model": "anthropic__claude-sonnet-4-6",
                "estimated_cost_usd": 0.02,
                "baseline_model": DEFAULT_BASELINE_MODEL,
                "baseline_cost_usd": 0.07,
                "savings_usd": 0.05,
                "catalog_source": "live",
                "signal": {"task_kind": "draft-prose", "caller": "test", "artifact_size_tokens": 4000},
                "caller": "test",
                "ts": "2026-06-03T00:00:00+00:00",
            },
            {
                "decision_id": "aitr-test-2",
                "model": "anthropic__claude-opus-4-8",
                "estimated_cost_usd": 0.07,
                "catalog_source": "snapshot",
                "signal": {"task_kind": "prose-review", "caller": "test", "artifact_size_tokens": 4000},
                "caller": "test",
                "ts": "2026-06-03T00:00:00+00:00",
            },
        ]
        log.write_text("\n".join(json.dumps(r) for r in records) + "\n")

        from datetime import datetime, timezone

        report = build_report(
            decisions_log=log,
            feedback_dirs=[tmp_path / "no-feedback"],
            days=365,
            now=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
        )
        assert "## Savings vs baseline" in report
        assert "Real dollar savings" in report
        # Neither record carries billing_mode → both report as headroom, not dollars
        assert "pre-date billing-mode tagging" in report
        # The notional reference line still shows the underlying numbers
        assert "notional" in report
